#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2027年度 メインスプレッドシート（.xlsx）を生成する。

    python3 tools/build-sheet-2027.py

出力: spreadsheet/2027/2027_売上顧客情報管理.xlsx

方針（オーナー 2026-09-13）:
  「社内資料としてオーバースペックにならないように、とにかく生産性が上がる、
    目標を達成可能にするためのスプシ」
  → 飾りより「毎日入力する人が迷わないこと」「目標との差がひと目で分かること」。

作りの決めごと:
  * Google スプレッドシート独自関数（QUERY / ARRAYFORMULA）は使わない。
    xlsx 経由だと壊れるため。SUMIFS / COUNTIFS / IFERROR / INDEX / EDATE のみ。
  * シート名に「/」は Excel で使えないので外した（例: 1月_売上顧客）。
  * 月次 P/L は経費入力表の「下」ではなく「右」（M列以降）に固定で置く。
    2026年版は経費行を足すたびに P/L がずれていた（6月+19行・7月+33行）。
  * 個人情報（氏名・電話・住所）の実データは一切入れない。列とプルダウンだけ。
"""

import json
import os
import subprocess
import sys
from datetime import date, timedelta

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import CellIsRule, FormulaRule

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "spreadsheet", "2027")
OUT_PATH = os.path.join(OUT_DIR, "2027_売上顧客情報管理.xlsx")

# ---------------------------------------------------------------- 見た目

C_HEAD = "1F3864"        # ヘッダー（濃紺）
C_BAND = "D9E2F3"        # 自動集計の帯
C_GOAL = "FFF2CC"        # 目標の帯
C_INPUT = "FFFFFF"       # 入力してよいセル
C_LOCK = "F2F2F2"        # 数式（触らない）
C_SECT = "E2EFDA"        # セクション見出し
C_WARN = "FFC7CE"        # 警告（赤）
C_OK = "C6EFCE"          # 良好（緑）

F_HEAD = Font(bold=True, color="FFFFFF", size=10)
F_SECT = Font(bold=True, size=11, color="1F3864")
F_TITLE = Font(bold=True, size=14, color="1F3864")
F_NOTE = Font(size=9, color="7F7F7F")
F_BOLD = Font(bold=True, size=10)
F_NORM = Font(size=10)

FILL_HEAD = PatternFill("solid", fgColor=C_HEAD)
FILL_BAND = PatternFill("solid", fgColor=C_BAND)
FILL_GOAL = PatternFill("solid", fgColor=C_GOAL)
FILL_LOCK = PatternFill("solid", fgColor=C_LOCK)
FILL_SECT = PatternFill("solid", fgColor=C_SECT)
FILL_WARN = PatternFill("solid", fgColor=C_WARN)
FILL_OK = PatternFill("solid", fgColor=C_OK)

THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

YEN = '#,##0'
YEN0 = '"¥"#,##0'
PCT = '0.0%'
DATE = 'yyyy/mm/dd'
NUM1 = '0.0'

# ---------------------------------------------------------------- 計画値

MONTHS = list(range(1, 13))

# ④自社ネット新規の月別目標（中立 年143件を月次件数で按分。6月だけ+1して143に合わせた）
# ④自社ネット新規の月別目標（年143件）。件数の季節性 × 立ち上がり係数（1月0.55→12月1.16）。
# 1〜2月は広告が段0（月5万）でテスト中なので5件に抑え、下期に寄せてある。
# 広告の段設計は docs/2027-数値目標.md §5。合計は必ず143にすること
NET_NEW_TARGET = [5, 5, 8, 10, 14, 17, 15, 10, 12, 16, 18, 13]

# 広告費の月別予算（中立 年80万・docs/2027-数値目標.md §5「段の設計」）
AD_BUDGET = [50000, 50000, 60000, 60000, 120000, 120000,
             120000, 30000, 30000, 70000, 70000, 20000]
AD_STAGE = ["段0（テスト）", "段0（テスト）", "段1", "段1", "段2（繁忙期）", "段2（繁忙期）",
            "段2（繁忙期）", "段1", "段1", "段3（年末）", "段3（年末）", "段1"]

CPA_LIMIT = 9500
LOAN_REPAY = 38059
ROYALTY_FIXED = 50050

BUSY_MONTHS = [5, 6, 7, 12]   # 繁忙期加算 3,300円


def load_plan():
    """tools/plan2027.py --json を正とする。"""
    out = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "plan2027.py"), "--json"],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def load_prices():
    with open(os.path.join(ROOT, "data", "prices.json"), encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- 選択肢

L_URIAGE_SHURUI = ["One Hitter", "本舗"]

L_RYUNYU = [
    # 2026年からの継続
    "リピート", "早期予約", "楽ラクーン", "業務提携", "スケジュールマッチング",
    "おそうじ定期便", "紹介", "営業", "チラシ(OH)", "HP", "入札案件",
    "チラシ(本舗)", "SMS",
    # 2027年の追加
    "LP", "SNS", "GBP(地図検索)", "公式LINE", "アフィリエイト", "LINE/SMS再販", "ギフト",
    "その他",
]

# ④自社ネット新規に数える流入経路（docs/2027-数値目標.md §4-④）
L_NET_NEW = ["HP", "LP", "SNS", "GBP(地図検索)", "公式LINE",
             "アフィリエイト", "LINE/SMS再販", "SMS"]

L_MENU = [
    "エアコン(ノーマル)", "エアコン(ロボ)", "浴室", "換気扇", "天カセ",
    "おそうじ定期便", "空室", "まるごと(備考に内容)", "洗濯機(ノーマル)",
    "洗濯機(ドラム)", "定期清掃", "業務用エアコン1方向", "追焚配管",
    "排水溝高圧洗浄", "トイレ",
]

# 資材費の単価を掛ける対象（P/L の台数カウント）
M_AIRCON = ["エアコン(ノーマル)", "エアコン(ロボ)", "天カセ", "業務用エアコン1方向"]
M_KANKISEN = ["換気扇"]
M_YOKUSHITSU = ["浴室"]

L_TANTOU = ["和真", "新人", "協力業者A", "協力業者B", "協力業者C", "その他"]
L_SOUKI = ["未記録", "提案済み", "成約", "見送り"]
L_FOLLOW = ["未記録", "実施", "不通", "対象外"]
L_NYUKIN = ["現金", "(OH)クレカ", "(OH)QR決済", "(本舗)クレカ", "(本舗)QR決済",
            "請求書(翌月)", "請求書(2か月後)"]
L_OH = ["未記録", "打診済み", "成約", "見送り"]
L_ROY = ["38%", "10%", "個別ロイ", "ロイ相殺"]
L_TF = ["TRUE", "FALSE"]

# 科目：保険料・通信費を独立させ、外注費を新設、人件費を現場（原価）と固定給（販管費）に分割
L_KAMOKU = [
    "交通費", "保険料", "通信費", "広告費", "耐久品", "備品",
    "個別ロイ", "現場人件費(原価)", "固定給(販管費)", "外注費", "その他(備考へ)",
]
KAMOKU_GENKA = ["外注費", "現場人件費(原価)"]     # 原価に回す科目

L_TODO_STATE = ["未着手", "進行中", "完了", "対象外"]
L_TODO_PRI = ["高", "中", "低"]
L_TEIKEI_STAGE = ["リスト化", "接触済み", "商談中", "条件提示", "成約", "見送り"]
L_GYOSHA_KEIYAKU = ["歩合(売価%)", "固定単価(メニュー別)", "日当", "未契約"]
L_GYOSHA_HINSHITSU = ["良", "可", "要改善"]
L_YOYAKU_STATE = ["未対応", "連絡済み", "日程確定", "受注", "不成立"]
L_SAIHAN_STATE = ["未案内", "送信済", "反応あり", "受注", "対象外"]
L_SAIHAN_SHUDAN = ["SMS", "公式LINE", "電話", "DM", "メール"]
L_MEIGI = ["自社", "本舗"]
L_SOUSHIN = ["自社", "本舗", "連絡不可"]
L_KINTAI_KUBUN = ["現場", "移動", "事務", "研修", "休み"]
L_AD_HANTEI = ["次の段へ上がる", "据え置き", "段を下げる", "止める", "未判定"]
L_AD_DAN = ["段0（テスト）", "段1", "段2（繁忙期）", "段3（年末）", "出さない"]

# 選択肢マスターに載せる（タブ名, 見出し, 値）
MASTER_LISTS = [
    ("A", "売上種類", L_URIAGE_SHURUI),
    ("B", "流入経路", L_RYUNYU),
    ("C", "実施メニュー", L_MENU),
    ("D", "施工担当", L_TANTOU),
    ("E", "早期予約提案", L_SOUKI),
    ("F", "フォローコール", L_FOLLOW),
    ("G", "入金経路", L_NYUKIN),
    ("H", "ＯＨ打診", L_OH),
    ("I", "本舗ロイ区分", L_ROY),
    ("J", "TRUE/FALSE", L_TF),
    ("K", "科目", L_KAMOKU),
    ("L", "TODO状態", L_TODO_STATE),
    ("M", "TODO優先度", L_TODO_PRI),
    ("N", "提携ステージ", L_TEIKEI_STAGE),
    ("O", "協力業者 契約形態", L_GYOSHA_KEIYAKU),
    ("P", "協力業者 品質", L_GYOSHA_HINSHITSU),
    ("Q", "Web予約 状態", L_YOYAKU_STATE),
    ("R", "再販 案内状況", L_SAIHAN_STATE),
    ("S", "再販 手段", L_SAIHAN_SHUDAN),
    ("T", "名義", L_MEIGI),
    ("U", "送信系統", L_SOUSHIN),
    ("V", "勤怠 区分", L_KINTAI_KUBUN),
    ("W", "広告 段", L_AD_DAN),
    ("X", "広告 判定", L_AD_HANTEI),
    ("Y", "④自社ネット新規に数える流入経路", L_NET_NEW),
]

MASTER_SHEET = "選択肢マスター"

# シート名（Excel は「/」が使えないのでスラッシュを外した）
def s_uriage(m):
    return f"{m}月_売上顧客"


def s_shishutsu(m):
    return f"{m}月_支出成績"


# 売上顧客タブの列（1始まり）
U_COLS = [
    ("通し番号", 9),
    ("売上種類", 11),
    ("施工日付", 12),
    ("流入経路", 17),
    ("流入元の識別子(?src=)", 20),
    ("氏名", 16),
    ("TEL(-無し)", 14),
    ("郵便番号(-無し)", 11),
    ("住所", 30),
    ("売上（税込）", 12),
    ("実施メニュー", 20),
    ("施工担当", 12),
    ("フォローコール日", 14),
    ("早期予約提案", 12),
    ("フォローコール", 12),
    ("備考(お客様の声)", 34),
    ("入金経路", 14),
    ("入金額照合", 11),
    ("ＯＨ打診", 11),
    ("本舗ロイ区分", 12),
    ("お客様周辺/環境情報", 24),
    ("カウント用", 10),
]
U_IDX = {name: i + 1 for i, (name, _) in enumerate(U_COLS)}
UC = {name: get_column_letter(i) for name, i in U_IDX.items()}

U_FIRST = 5        # データ開始行
U_LAST = 504       # データ終了行

E_FIRST = 3        # 経費入力の開始行
E_LAST = 302       # 経費入力の終了行


# ---------------------------------------------------------------- 小道具

def title(ws, text, sub=None):
    ws["A1"] = text
    ws["A1"].font = F_TITLE
    if sub:
        ws["A2"] = sub
        ws["A2"].font = F_NOTE
    ws.row_dimensions[1].height = 22


def header_row(ws, row, names, start_col=1):
    for i, n in enumerate(names):
        c = ws.cell(row=row, column=start_col + i, value=n)
        c.font = F_HEAD
        c.fill = FILL_HEAD
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = BORDER
    ws.row_dimensions[row].height = 30


def widths(ws, spec, start_col=1):
    for i, w in enumerate(spec):
        ws.column_dimensions[get_column_letter(start_col + i)].width = w


def label(ws, cell, text, fill=None, font=None):
    c = ws[cell]
    c.value = text
    c.font = font or F_BOLD
    if fill:
        c.fill = fill
    return c


def dv(ws, values, ranges, allow_blank=True):
    """選択肢マスターの列を参照するプルダウンを付ける。"""
    col = None
    for letter, name, vals in MASTER_LISTS:
        if vals is values:
            col = letter
            break
    if col is None:
        raise ValueError("選択肢マスターに無いリスト")
    n = len(values)
    ref = f"'{MASTER_SHEET}'!${col}$2:${col}${n + 1}"
    v = DataValidation(type="list", formula1=ref, allow_blank=allow_blank, showDropDown=False)
    ws.add_data_validation(v)
    for r in ranges:
        v.add(r)


def rng(col, r1=U_FIRST, r2=U_LAST):
    return f"${col}${r1}:${col}${r2}"


def sum_countifs(sheet, col, values, r1=U_FIRST, r2=U_LAST):
    """COUNTIFS を値の数だけ足す。配列定数は Google 変換で壊れるので使わない。"""
    pre = f"'{sheet}'!" if sheet else ""
    parts = [f'COUNTIFS({pre}{rng(col, r1, r2)},"{v}")' for v in values]
    return "+".join(parts)


def sum_sumifs(sheet, sum_col, crit_col, values, r1=U_FIRST, r2=U_LAST):
    pre = f"'{sheet}'!" if sheet else ""
    parts = [f'SUMIFS({pre}{rng(sum_col, r1, r2)},{pre}{rng(crit_col, r1, r2)},"{v}")'
             for v in values]
    return "+".join(parts)


# ================================================================ 各タブ

def build_master(wb):
    ws = wb.create_sheet(MASTER_SHEET)
    ws.sheet_properties.tabColor = "BFBFBF"
    for letter, name, vals in MASTER_LISTS:
        c = ws[f"{letter}1"]
        c.value = name
        c.font = F_HEAD
        c.fill = FILL_HEAD
        c.alignment = Alignment(horizontal="center", wrap_text=True)
        for i, v in enumerate(vals):
            ws[f"{letter}{i + 2}"] = v
        ws.column_dimensions[letter].width = max(12, min(26, len(name) * 2))
    ws.row_dimensions[1].height = 34
    ws.freeze_panes = "A2"
    # 使い方
    last = get_column_letter(len(MASTER_LISTS) + 2)
    ws[f"{last}1"] = "【このタブは全タブのプルダウンの元データです。並べ替え・行削除をしないこと。"
    ws[f"{last}2"] = "　選択肢を足すときは、列のいちばん下に追記してから、使う側のタブの入力規則の範囲を伸ばしてください】"
    ws[f"{last}1"].font = F_SECT
    ws[f"{last}2"].font = F_NOTE
    return ws


def build_uriage(wb, m, plan_m, net_target):
    name = s_uriage(m)
    ws = wb.create_sheet(name)
    ws.sheet_properties.tabColor = "2E75B6"

    widths(ws, [w for _, w in U_COLS])

    # --- 1行目：入力の案内
    ws["A1"] = f"◆ {m}月の売上・顧客。入力は {U_FIRST} 行目から。2行目＝今月の目標、4行目＝自動集計（数式・触らない）"
    ws["A1"].font = F_SECT
    ws.row_dimensions[1].height = 18

    Cc = UC
    tot_uriage = f"SUM({rng(Cc['売上（税込）'])})"
    tot_kensu = f"COUNTA({rng(Cc['施工日付'])})"

    # --- 2行目：目標
    goals = [
        ("A2", "今月目標(売上)", "B2", plan_m["売上"], YEN),
        ("C2", "売上 現在", "D2", "=$%s$4" % Cc["売上（税込）"], YEN),
        ("E2", "過不足", "F2", "=D2-B2", YEN),
        ("G2", "達成率", "H2", "=IFERROR(D2/B2,0)", PCT),
        ("I2", "必要件数", "J2", plan_m["件数"], '0"件"'),
        ("K2", "件数 現在", "L2", "=$%s$4" % Cc["流入経路"], '0"件"'),
        ("M2", "残り件数", "N2", "=J2-L2", '0"件"'),
        ("O2", "④ネット新規 目標", "P2", net_target, '0"件"'),
        ("Q2", "④ 現在", "R2", "=$%s$4" % Cc["備考(お客様の声)"], '0"件"'),
    ]
    for lc, ltext, vc, val, fmt in goals:
        label(ws, lc, ltext, FILL_GOAL)
        ws[lc].alignment = Alignment(horizontal="right")
        c = ws[vc]
        c.value = val
        c.number_format = fmt
        c.fill = FILL_GOAL
        c.font = Font(bold=True, size=11)
    ws.row_dimensions[2].height = 20
    ws.conditional_formatting.add(
        "F2", CellIsRule(operator="lessThan", formula=["0"], fill=FILL_WARN))
    ws.conditional_formatting.add(
        "F2", CellIsRule(operator="greaterThanOrEqual", formula=["0"], fill=FILL_OK))
    ws.conditional_formatting.add(
        "H2", CellIsRule(operator="lessThan", formula=["0.9"], fill=FILL_WARN))
    ws.conditional_formatting.add(
        "H2", CellIsRule(operator="greaterThanOrEqual", formula=["1"], fill=FILL_OK))
    ws.conditional_formatting.add(
        "R2", CellIsRule(operator="lessThan", formula=["P2"], fill=FILL_WARN))

    # --- 3行目：ヘッダー
    header_row(ws, 3, [n for n, _ in U_COLS])

    # --- 4行目：自動集計（ラベルは表示形式に埋め込む）
    agg = [
        ("通し番号", '"▼自動集計"', None, '@'),
        ("売上種類", f'=COUNTIFS({rng(Cc["売上種類"])},"One Hitter")', None, '"自社 "0"件"'),
        ("施工日付", f'=COUNTIFS({rng(Cc["売上種類"])},"本舗")', None, '"本舗 "0"件"'),
        ("流入経路", f"={tot_kensu}", None, '"合計 "0"件"'),
        ("流入元の識別子(?src=)",
         f"=IFERROR({tot_uriage}/{tot_kensu},0)", None, '"単価 "#,##0'),
        ("氏名",
         f'=IFERROR(SUMIFS({rng(Cc["売上（税込）"])},{rng(Cc["売上種類"])},"One Hitter")'
         f'/COUNTIFS({rng(Cc["売上種類"])},"One Hitter"),0)', None, '"自社単価 "#,##0'),
        ("TEL(-無し)",
         f'=IFERROR(SUMIFS({rng(Cc["売上（税込）"])},{rng(Cc["売上種類"])},"本舗")'
         f'/COUNTIFS({rng(Cc["売上種類"])},"本舗"),0)', None, '"本舗単価 "#,##0'),
        ("売上（税込）", f"={tot_uriage}", None, '"合計 "#,##0'),
        ("備考(お客様の声)", "=" + sum_countifs(None, Cc["流入経路"], L_NET_NEW), None, '"④ "0"件"'),
        ("入金経路",
         "=" + sum_sumifs(None, Cc["売上（税込）"], Cc["流入経路"], L_NET_NEW), None, '"④売上 "#,##0'),
    ]
    for colname, formula, _x, fmt in agg:
        c = ws.cell(row=4, column=U_IDX[colname])
        c.value = formula if str(formula).startswith("=") else f"={formula}"
        c.number_format = fmt
        c.fill = FILL_BAND
        c.font = F_BOLD
        c.border = BORDER
        c.alignment = Alignment(horizontal="center")
    for i in range(1, len(U_COLS) + 1):
        ws.cell(row=4, column=i).fill = FILL_BAND
    ws.row_dimensions[4].height = 20

    # --- 入力行の書式
    for r in range(U_FIRST, U_LAST + 1):
        ws.cell(row=r, column=U_IDX["施工日付"]).number_format = DATE
        ws.cell(row=r, column=U_IDX["フォローコール日"]).number_format = DATE
        ws.cell(row=r, column=U_IDX["売上（税込）"]).number_format = YEN
        ws.cell(row=r, column=U_IDX["通し番号"]).number_format = '0'

    # --- プルダウン
    R = lambda col: f"{UC[col]}{U_FIRST}:{UC[col]}{U_LAST}"
    dv(ws, L_URIAGE_SHURUI, [R("売上種類")])
    dv(ws, L_RYUNYU, [R("流入経路")])
    dv(ws, L_MENU, [R("実施メニュー")])
    dv(ws, L_TANTOU, [R("施工担当")])
    dv(ws, L_SOUKI, [R("早期予約提案")])
    dv(ws, L_FOLLOW, [R("フォローコール")])
    dv(ws, L_NYUKIN, [R("入金経路")])
    dv(ws, L_TF, [R("入金額照合")])
    dv(ws, L_OH, [R("ＯＨ打診")])
    dv(ws, L_ROY, [R("本舗ロイ区分")])

    ws.freeze_panes = f"A{U_FIRST}"
    ws.auto_filter.ref = f"A3:{get_column_letter(len(U_COLS))}{U_LAST}"
    return ws


def build_shishutsu(wb, m, plan_m):
    name = s_shishutsu(m)
    ws = wb.create_sheet(name)
    ws.sheet_properties.tabColor = "C55A11"
    src = s_uriage(m)
    Cc = UC

    # ---------------- 左：経費入力表（A〜H）
    ws["A1"] = f"◆ {m}月の経費入力。3行目から下へ足していってよい。右の月次P/Lは行が動かないので壊れない"
    ws["A1"].font = F_SECT
    ecols = ["No.", "日付", "時刻", "品目", "科目", "金額", "備考", "現金立替え"]
    header_row(ws, 2, ecols)
    widths(ws, [6, 12, 8, 26, 18, 12, 26, 11])
    for r in range(E_FIRST, E_LAST + 1):
        ws.cell(row=r, column=2).number_format = DATE
        ws.cell(row=r, column=3).number_format = 'hh:mm'
        ws.cell(row=r, column=6).number_format = YEN
    dv(ws, L_KAMOKU, [f"E{E_FIRST}:E{E_LAST}"])
    dv(ws, L_TF, [f"H{E_FIRST}:H{E_LAST}"])
    ws.freeze_panes = "A3"

    # ---------------- 右：月次P/L（M〜O）※行は固定
    def kamoku(k):
        return f'SUMIFS($F${E_FIRST}:$F${E_LAST},$E${E_FIRST}:$E${E_LAST},"{k}")'

    ws["M1"] = "▼ 月次P/L（この位置は固定。左の経費表を何行足してもずれません）"
    ws["M1"].font = F_SECT
    ws["M1"].fill = FILL_SECT
    header_row(ws, 2, ["項目", "金額", "計算の中身"], start_col=13)
    widths(ws, [26, 15, 52], start_col=13)

    cnt_air = sum_countifs(src, Cc["実施メニュー"], M_AIRCON)
    cnt_kan = sum_countifs(src, Cc["実施メニュー"], M_KANKISEN)
    cnt_yok = sum_countifs(src, Cc["実施メニュー"], M_YOKUSHITSU)

    roy38 = (f"SUMIFS('{src}'!{rng(Cc['売上（税込）'])},"
             f"'{src}'!{rng(Cc['本舗ロイ区分'])},\"38%\")*0.38")
    roy10 = (f"SUMIFS('{src}'!{rng(Cc['売上（税込）'])},"
             f"'{src}'!{rng(Cc['本舗ロイ区分'])},\"10%\")*0.1")

    pl = [
        # (row, 項目, 数式 or 値, number_format, メモ, is_total)
        (3,  "売上",                f"='{src}'!${Cc['売上（税込）']}$4", YEN,
         f"{m}月_売上顧客 の合計売上", True),
        (4,  "エアコン台数(参考)",   f"={cnt_air}", '0"台"',
         "エアコン(ノーマル/ロボ)・天カセ・業務用1方向", False),
        (5,  "換気扇台数(参考)",     f"={cnt_kan}", '0"台"', "実施メニュー＝換気扇", False),
        (6,  "浴室台数(参考)",       f"={cnt_yok}", '0"台"', "実施メニュー＝浴室", False),
        (7,  "資材費",              "=N4*373+N5*176+N6*149", YEN,
         "エアコン373 + 換気扇176 + 浴室149", False),
        (8,  "外注費（協力業者）",   f"={kamoku('外注費')}", YEN,
         "経費表の科目＝外注費。★2027年から原価として独立", False),
        (9,  "現場人件費（原価）",   f"={kamoku('現場人件費(原価)')}", YEN,
         "経費表の科目＝現場人件費(原価)", False),
        (10, "原価合計",            "=N7+N8+N9", YEN, "資材費＋外注費＋現場人件費", True),
        (11, "売上総利益",          "=N3-N10", YEN, "売上 − 原価合計", True),
        (13, "経費合計（左の表）",   f"=SUM($F${E_FIRST}:$F${E_LAST})", YEN,
         "左の経費入力表の金額合計", False),
        (14, "− 原価へ回した分",    "=-(N8+N9)", YEN, "外注費・現場人件費は原価で数えたので戻す", False),
        (15, "− 個別ロイ（下で計上）", f"=-{kamoku('個別ロイ')}", YEN,
         "★二重計上を防ぐため、ここで一度引く", False),
        (16, "ロイヤリティ 固定分",  f"=IF($N$3+$N$13=0,0,{ROYALTY_FIXED})", YEN,
         "★50,050円。左の経費表には入力しないこと（まだ動いていない月は0）", False),
        (17, "ロイヤリティ 38%分",  f"={roy38}", YEN, "本舗ロイ区分＝38% の売上 × 38%", False),
        (18, "ロイヤリティ 10%分",  f"={roy10}", YEN, "本舗ロイ区分＝10% の売上 × 10%", False),
        (19, "ロイヤリティ 個別実額", f"={kamoku('個別ロイ')}", YEN,
         "経費表の科目＝個別ロイ（toB・楽ラクーン等）", False),
        (20, "ロイヤリティ 合計",    "=N16+N17+N18+N19", YEN, "固定＋38%＋10%＋個別", True),
        (21, "販売管理費",          "=N13+N14+N15+N20", YEN,
         "経費合計 − 原価分 − 個別ロイ ＋ ロイヤリティ合計", True),
        (22, "営業利益",            "=N11-N21", YEN, "売上総利益 − 販売管理費", True),
        (23, "融資返済",            f"=IF($N$3+$N$13=0,0,{LOAN_REPAY})", YEN,
         "固定 38,059円（まだ動いていない月は0）", False),
        (24, "経常利益",            "=N22-N23", YEN, "営業利益 − 融資返済", True),
        (26, "経常利益率",          "=IFERROR(N24/N3,0)", PCT, "経常利益 ÷ 売上", False),
    ]
    for r, nm, val, fmt, memo, is_tot in pl:
        a = ws.cell(row=r, column=13, value=nm)
        a.font = F_BOLD if is_tot else F_NORM
        a.border = BORDER
        b = ws.cell(row=r, column=14, value=val)
        b.number_format = fmt
        b.border = BORDER
        b.font = Font(bold=True, size=11) if is_tot else F_NORM
        if isinstance(val, str) and val.startswith("="):
            b.fill = FILL_LOCK
        c = ws.cell(row=r, column=15, value=memo)
        c.font = F_NOTE

    ws.conditional_formatting.add(
        "N22", CellIsRule(operator="lessThan", formula=["0"], fill=FILL_WARN))
    ws.conditional_formatting.add(
        "N24", CellIsRule(operator="lessThan", formula=["0"], fill=FILL_WARN))
    ws.conditional_formatting.add(
        "N24", CellIsRule(operator="greaterThan", formula=["0"], fill=FILL_OK))

    # 計画との比較
    ws["M28"] = "▼ 計画（中立）との比較"
    ws["M28"].font = F_SECT
    ws["M28"].fill = FILL_SECT
    comp = [
        (29, "計画 売上", plan_m["売上"], YEN, ""),
        (30, "実績 − 計画（売上）", "=N3-N29", YEN, "マイナスなら赤"),
        (31, "計画 経常利益", plan_m["経常利益"], YEN, ""),
        (32, "実績 − 計画（経常）", "=N24-N31", YEN, "マイナスなら赤"),
        (33, "計画 件数", plan_m["件数"], '0"件"', ""),
        (34, "実績 件数", f"='{src}'!${Cc['流入経路']}$4", '0"件"', ""),
    ]
    for r, nm, val, fmt, memo in comp:
        ws.cell(row=r, column=13, value=nm).font = F_NORM
        b = ws.cell(row=r, column=14, value=val)
        b.number_format = fmt
        ws.cell(row=r, column=15, value=memo).font = F_NOTE
    for cell in ("N30", "N32"):
        ws.conditional_formatting.add(
            cell, FormulaRule(formula=[f"AND($N$3>0,{cell}<0)"], fill=FILL_WARN))
        ws.conditional_formatting.add(
            cell, FormulaRule(formula=[f"AND($N$3>0,{cell}>=0)"], fill=FILL_OK))

    # 入力の決まり（ここに書いておかないと毎年同じ間違いをする）
    notes = [
        "【ロイヤリティはこのP/Lだけで数えます】",
        "  ・固定分 50,050円は左の経費表に入力しないこと（2026年版はここが二重計上の疑いだった）",
        "  ・個別ロイは左の経費表に科目「個別ロイ」で入力する。P/Lは15行目で引いて19行目で足すので、数えるのは1回だけ",
        "【人件費は2つに分けます】",
        "  ・現場人件費(原価) … 現場に出た分。原価に入る",
        "  ・固定給(販管費) … 和真さんの固定給40万＋プール10万、新人の給与。販管費に入る",
        "  ・歩合（経常利益×45%）の行は2027年から使いません",
        "【保険料・通信費は「その他」に入れないこと】",
        "  ・賠償保険 43,760／通信費 8,470／日新火災 18,050 ＝ 月70,280円。科目を独立させました",
    ]
    for i, t in enumerate(notes):
        c = ws.cell(row=36 + i, column=13, value=t)
        c.font = F_SECT if t.startswith("【") else F_NOTE

    # 科目別の集計（Q〜R）
    ws["Q2"] = "▼ 科目別 集計"
    ws["Q2"].font = F_SECT
    ws["Q2"].fill = FILL_SECT
    header_row(ws, 3, ["科目", "金額"], start_col=17)
    widths(ws, [20, 14], start_col=17)
    for i, k in enumerate(L_KAMOKU):
        ws.cell(row=4 + i, column=17, value=k).font = F_NORM
        c = ws.cell(row=4 + i, column=18, value=f"={kamoku(k)}")
        c.number_format = YEN
        c.fill = FILL_LOCK
    r = 4 + len(L_KAMOKU)
    ws.cell(row=r, column=17, value="合計").font = F_BOLD
    cc = ws.cell(row=r, column=18, value=f"=SUM(R4:R{r - 1})")
    cc.number_format = YEN
    cc.font = F_BOLD
    return ws


def build_nenkan(wb, plan, plan_year):
    ws = wb.create_sheet("年間成績")
    ws.sheet_properties.tabColor = "1F3864"
    title(ws, "2027年 年間成績（予算対実績・月別P/L）",
          "青い数字は計画。白い数字は各月タブから自動で入ります。手入力するのは「2026年 売上」の行だけです。")

    widths(ws, [26] + [13] * 12 + [14, 44])

    # --- 上の要約
    summary = [
        (4,  "年間 計画売上",        "=$N$18", YEN),
        (5,  "売上 実績累計",        "=$N$20", YEN),
        (6,  "対計画 差額",          "=B5-B4", YEN),
        (7,  "達成率",               "=IFERROR(B5/B4,0)", PCT),
        (9,  "年間 計画 経常利益",   plan_year["経常利益"], YEN),
        (10, "経常利益 実績累計",    "=$N$43", YEN),
        (12, "④自社ネット新規 年間目標", "=$N$29", '0"件"'),
        (13, "④自社ネット新規 実績",  "=$N$30", '0"件"'),
        (14, "経常利益がマイナスの月数", "=COUNTIF($B$43:$M$43,\"<0\")", '0"か月"'),
    ]
    for r, nm, val, fmt in summary:
        label(ws, f"A{r}", nm, FILL_SECT)
        c = ws[f"B{r}"]
        c.value = val
        c.number_format = fmt
        c.font = Font(bold=True, size=12)
    ws.conditional_formatting.add(
        "B6", CellIsRule(operator="lessThan", formula=["0"], fill=FILL_WARN))
    ws.conditional_formatting.add(
        "B6", CellIsRule(operator="greaterThanOrEqual", formula=["0"], fill=FILL_OK))
    ws.conditional_formatting.add(
        "B7", CellIsRule(operator="lessThan", formula=["0.9"], fill=FILL_WARN))
    ws.conditional_formatting.add(
        "B14", CellIsRule(operator="greaterThan", formula=["0"], fill=FILL_WARN))
    ws["D4"] = "★ ここだけ見れば「計画に乗っているか」が分かります。詳しくはダッシュボード。"
    ws["D4"].font = F_NOTE

    # --- 月別表（17行目〜。2026年版に合わせた）
    header_row(ws, 17, ["項目"] + [f"{m}月" for m in MONTHS] + ["年計", "説明"])

    mon = plan["中立"]["月次"]

    def row(r, name, per_month, fmt, total="sum", note="", bold=False, fill=None):
        c = ws.cell(row=r, column=1, value=name)
        c.font = F_BOLD if bold else F_NORM
        c.border = BORDER
        if fill:
            c.fill = fill
        for i, m in enumerate(MONTHS):
            cc = ws.cell(row=r, column=2 + i, value=per_month(m, i))
            cc.number_format = fmt
            cc.border = BORDER
            if bold:
                cc.font = F_BOLD
            if fill:
                cc.fill = fill
        t = ws.cell(row=r, column=14)
        if total == "sum":
            t.value = f"=SUM(B{r}:M{r})"
        elif total == "last":
            t.value = f"=M{r}"
        elif total == "avg":
            t.value = f"=IFERROR(AVERAGE(B{r}:M{r}),0)"
        elif total is None:
            t.value = None
        else:
            t.value = total.format(r=r)
        t.number_format = fmt
        t.font = F_BOLD
        t.border = BORDER
        ws.cell(row=r, column=15, value=note).font = F_NOTE

    U4 = lambda m, col: f"='{s_uriage(m)}'!${UC[col]}$4"
    P = lambda m, cell: f"='{s_shishutsu(m)}'!${cell}"

    row(18, "予算（計画売上）", lambda m, i: mon[i]["売上"], YEN, "sum",
        "tools/plan2027.py の中立", bold=True, fill=FILL_GOAL)
    row(19, "年間割合", lambda m, i: f"=IFERROR(B{18}/$N$18,0)".replace("B18", f"{get_column_letter(2+i)}18"),
        PCT, "sum", "その月が年間の何%か")
    row(20, "売上実績", lambda m, i: U4(m, "売上（税込）"), YEN, "sum",
        "各月タブの合計売上", bold=True)
    row(21, "売上累計", lambda m, i: ("=B20" if i == 0 else f"={get_column_letter(1+i)}21+{get_column_letter(2+i)}20"),
        YEN, "last", "実績の積み上げ")
    row(22, "予算累計", lambda m, i: ("=B18" if i == 0 else f"={get_column_letter(1+i)}22+{get_column_letter(2+i)}18"),
        YEN, "last", "計画の積み上げ")
    row(23, "★対計画の差額（当月）",
        lambda m, i: f"={get_column_letter(2+i)}20-{get_column_letter(2+i)}18", YEN, "sum",
        "毎月いちばんに見る数字。マイナスなら赤", bold=True)
    row(24, "★累計の対計画の差額",
        lambda m, i: f"={get_column_letter(2+i)}21-{get_column_letter(2+i)}22", YEN, "last",
        "年の着地を決める数字。マイナスなら赤", bold=True)
    row(25, "達成率（当月）",
        lambda m, i: f"=IFERROR({get_column_letter(2+i)}20/{get_column_letter(2+i)}18,0)", PCT, "avg")
    row(26, "達成率（累計）",
        lambda m, i: f"=IFERROR({get_column_letter(2+i)}21/{get_column_letter(2+i)}22,0)", PCT, "last")
    row(27, "件数 計画", lambda m, i: mon[i]["件数"], '0', "sum", "", fill=FILL_GOAL)
    row(28, "件数 実績", lambda m, i: U4(m, "流入経路"), '0', "sum")
    row(29, "④自社ネット新規 計画", lambda m, i: NET_NEW_TARGET[i], '0', "sum",
        "年143件（中立）。HP/LP/SNS/GBP/公式LINE/アフィリ/LINE・SMS再販", fill=FILL_GOAL)
    row(30, "★④自社ネット新規 実績", lambda m, i: U4(m, "備考(お客様の声)"), '0', "sum",
        "2027年の最重要KPI。これが動かないと他は後追い", bold=True)
    row(31, "平均単価 実績", lambda m, i: U4(m, "流入元の識別子(?src=)"), YEN, "avg")
    row(32, "エアコン台数", lambda m, i: P(m, "N$4"), '0', "sum")
    row(33, "換気扇台数", lambda m, i: P(m, "N$5"), '0', "sum")
    row(34, "浴室台数", lambda m, i: P(m, "N$6"), '0', "sum")
    row(35, "資材費", lambda m, i: P(m, "N$7"), YEN, "sum")
    row(36, "外注費", lambda m, i: P(m, "N$8"), YEN, "sum", "協力業者3社へ回した分")
    row(37, "現場人件費（原価）", lambda m, i: P(m, "N$9"), YEN, "sum")
    row(38, "原価合計", lambda m, i: P(m, "N$10"), YEN, "sum")
    row(39, "売上総利益", lambda m, i: P(m, "N$11"), YEN, "sum", bold=True)
    row(40, "販売管理費", lambda m, i: P(m, "N$21"), YEN, "sum", "固定給・ロイヤリティ込み")
    row(41, "営業利益", lambda m, i: P(m, "N$22"), YEN, "sum", bold=True)
    row(42, "融資返済", lambda m, i: P(m, "N$23"), YEN, "sum")
    row(43, "経常利益", lambda m, i: P(m, "N$24"), YEN, "sum", bold=True)
    row(44, "経常利益 累計",
        lambda m, i: ("=B43" if i == 0 else f"={get_column_letter(1+i)}44+{get_column_letter(2+i)}43"),
        YEN, "last")
    row(45, "2026年 売上（手入力）", lambda m, i: None, YEN, "sum",
        "★年末に2026年の確定値を貼ってください。ここだけ手入力です", fill=FILL_INPUT_SAFE)
    row(46, "前年比", lambda m, i: f"=IFERROR({get_column_letter(2+i)}20/{get_column_letter(2+i)}45,\"\")",
        PCT, '=IFERROR(N20/N45,"")', "2027 ÷ 2026")

    # --- ダッシュボードが「今月時点の累計」を出すための行
    ws.cell(row=48, column=1, value="▼ ここから下はダッシュボード用の累計です（触らないでください）").font = F_SECT
    row(49, "④自社ネット新規 計画 累計",
        lambda m, i: ("=B29" if i == 0 else f"={get_column_letter(1+i)}49+{get_column_letter(2+i)}29"),
        '0', "last", "ダッシュボード用")
    row(50, "④自社ネット新規 実績 累計",
        lambda m, i: ("=B30" if i == 0 else f"={get_column_letter(1+i)}50+{get_column_letter(2+i)}30"),
        '0', "last", "ダッシュボード用")
    row(51, "経常利益 計画（月次）", lambda m, i: mon[i]["経常利益"], YEN, "sum",
        "tools/plan2027.py の中立", fill=FILL_GOAL)
    row(52, "経常利益 計画 累計",
        lambda m, i: ("=B51" if i == 0 else f"={get_column_letter(1+i)}52+{get_column_letter(2+i)}51"),
        YEN, "last", "ダッシュボード用")
    row(53, "売上 計画（月次・再掲）", lambda m, i: f"={get_column_letter(2+i)}18", YEN, "sum",
        "ダッシュボード用")

    # 実績が入っていない月まで赤くすると、1月から画面が真っ赤になって意味を失う。
    # 「その月に売上が入っているか」を条件にしている。
    for r, base in ((23, 20), (24, 21)):
        ws.conditional_formatting.add(
            f"B{r}:N{r}", FormulaRule(formula=[f"AND(B${base}>0,B{r}<0)"], fill=FILL_WARN))
        ws.conditional_formatting.add(
            f"B{r}:N{r}", FormulaRule(formula=[f"AND(B${base}>0,B{r}>=0)"], fill=FILL_OK))
    ws.conditional_formatting.add(
        "B43:N43", FormulaRule(formula=["AND(B$20>0,B43<0)"], fill=FILL_WARN))
    ws.conditional_formatting.add(
        "B25:N25", FormulaRule(formula=["AND(B$20>0,B25<0.9)"], fill=FILL_WARN))
    ws.conditional_formatting.add(
        "B26:N26", FormulaRule(formula=["AND(B$21>0,B26<0.9)"], fill=FILL_WARN))
    ws.conditional_formatting.add(
        "B30:M30", FormulaRule(formula=["AND(B$20>0,B30<B29)"], fill=FILL_WARN))

    ws.freeze_panes = "B18"
    return ws


FILL_INPUT_SAFE = PatternFill("solid", fgColor="FFFFFF")


def build_keikaku(wb, plan):
    ws = wb.create_sheet("2027年計画")
    ws.sheet_properties.tabColor = "7030A0"
    title(ws, "2027年 計画（正式目標＝中立）",
          "tools/plan2027.py --json の値をそのまま。ここは実績で書き換えないこと。")

    keys = [
        ("売上", YEN), ("件数", '0'), ("平均単価", YEN), ("本舗売上", YEN),
        ("原価_資材費", YEN), ("原価_外注費", YEN), ("原価_補助人件費", YEN), ("原価_計", YEN),
        ("売上総利益", YEN),
        ("販管_固定経費", YEN), ("販管_ロイヤリティ固定", YEN), ("販管_ロイヤリティ", YEN),
        ("販管_広告費", YEN), ("販管_人件費_和真", YEN), ("販管_人件費_新人", YEN),
        ("販管_採用費装備", YEN), ("販管_その他変動費", YEN), ("販管_計", YEN),
        ("営業利益", YEN), ("融資返済", YEN), ("経常利益", YEN), ("外注件数", '0'),
    ]
    header_row(ws, 4, ["項目"] + [f"{m}月" for m in MONTHS] + ["年計"])
    widths(ws, [24] + [12] * 12 + [14])
    mon = plan["中立"]["月次"]
    yr = plan["中立"]["年計"]
    for i, (k, fmt) in enumerate(keys):
        r = 5 + i
        ws.cell(row=r, column=1, value=k).font = F_BOLD if k in ("売上", "件数", "経常利益") else F_NORM
        for j, m in enumerate(MONTHS):
            c = ws.cell(row=r, column=2 + j, value=mon[j][k])
            c.number_format = fmt
            c.border = BORDER
        t = ws.cell(row=r, column=14, value=yr.get(k))
        t.number_format = fmt
        t.font = F_BOLD

    r0 = 5 + len(keys) + 2
    ws.cell(row=r0, column=1, value="▼ 3パターンの年計（参考）").font = F_SECT
    header_row(ws, r0 + 1, ["シナリオ", "売上", "件数", "平均単価", "経常利益", "広告費(年)",
                            "④自社ネット新規(年)", "備考"])
    widths(ws, [14, 14, 10, 12, 14, 12, 18, 40], start_col=1)
    extra = {"保守": ("25万", 61, "テストして伸びなかった形"),
             "中立": ("80万", 143, "★正式目標。段2まで上がった形"),
             "攻め": ("100万", 192, "段3まで上がった形")}
    for i, name in enumerate(["保守", "中立", "攻め"]):
        y = plan[name]["年計"]
        r = r0 + 2 + i
        vals = [name, y["売上"], y["件数"], y["平均単価"], y["経常利益"],
                extra[name][0], extra[name][1], extra[name][2]]
        for j, v in enumerate(vals):
            c = ws.cell(row=r, column=1 + j, value=v)
            c.border = BORDER
            if j in (1, 3, 4):
                c.number_format = YEN
            if name == "中立":
                c.font = F_BOLD
                c.fill = FILL_GOAL

    r1 = r0 + 6
    for i, t in enumerate([
        "【判定ゲート】",
        "  3月末 … Q1累計が 380万に届いているか（保守290万／攻め465万）。届かなければ保守の組み方へ切り替え",
        "  6月末 … 上期累計が中立比85%以上か。下回れば広告の段を落とし、協力業者の稼働を縮小",
        "  9月末 … Q3累計が中立比85%以上か。年末商戦の打ち手を前倒し。10月1日のLP公開は死守",
        "  12月末 … 通年着地を2028年の人員計画へ",
        "",
        "【前提】正社員1名を3月入社／協力業者3社を1〜2月に契約し3月から稼働（オーナー指示 2026-09-13）",
        "【出典】docs/2027-数値目標.md ／ tools/plan2027.py",
    ]):
        ws.cell(row=r1 + i, column=1, value=t).font = F_SECT if t.startswith("【") else F_NOTE
    return ws


def build_dashboard(wb, plan_year):
    ws = wb.create_sheet("ダッシュボード")
    ws.sheet_properties.tabColor = "C00000"
    title(ws, "ダッシュボード — 計画に乗っているか、1画面で",
          "B3 に「今月の数字（1〜12）」を入れると、その月の数字に切り替わります。")
    widths(ws, [28, 16, 16, 16, 4, 26, 16, 16, 30])

    label(ws, "A3", "今月（1〜12を入れる）", FILL_GOAL)
    ws["B3"] = 1
    ws["B3"].fill = FILL_GOAL
    ws["B3"].font = Font(bold=True, size=14)
    ws["B3"].number_format = '0"月"'
    ws["C3"] = "← ここだけ手で変えます"
    ws["C3"].font = F_NOTE

    def idx(row):
        return f"INDEX('年間成績'!$B${row}:$M${row},1,$B$3)"

    # 今月ブロック
    ws["A5"] = "▼ 今月"
    ws["A5"].font = F_SECT
    ws["A5"].fill = FILL_SECT
    ws["B5"] = "計画"
    ws["C5"] = "実績"
    ws["D5"] = "差額"
    for c in ("B5", "C5", "D5"):
        ws[c].font = F_HEAD
        ws[c].fill = FILL_HEAD
        ws[c].alignment = Alignment(horizontal="center")

    month_rows = [
        (6, "売上", 18, 20, YEN),
        (7, "件数", 27, 28, '0"件"'),
        (8, "★④自社ネット新規", 29, 30, '0"件"'),
    ]
    for r, nm, pr, ar, fmt in month_rows:
        label(ws, f"A{r}", nm)
        for col, row_ in (("B", pr), ("C", ar)):
            c = ws[f"{col}{r}"]
            c.value = f"={idx(row_)}"
            c.number_format = fmt
            c.border = BORDER
        d = ws[f"D{r}"]
        d.value = f"=C{r}-B{r}"
        d.number_format = fmt
        d.font = F_BOLD
        d.border = BORDER
        ws.conditional_formatting.add(
            f"D{r}", CellIsRule(operator="lessThan", formula=["0"], fill=FILL_WARN))
        ws.conditional_formatting.add(
            f"D{r}", CellIsRule(operator="greaterThanOrEqual", formula=["0"], fill=FILL_OK))

    label(ws, "A9", "達成率（当月）")
    ws["C9"] = f"=IFERROR(C6/B6,0)"
    ws["C9"].number_format = PCT
    ws["C9"].font = Font(bold=True, size=12)
    ws.conditional_formatting.add(
        "C9", CellIsRule(operator="lessThan", formula=["0.9"], fill=FILL_WARN))
    ws.conditional_formatting.add(
        "C9", CellIsRule(operator="greaterThanOrEqual", formula=["1"], fill=FILL_OK))

    label(ws, "A10", "経常利益（当月）")
    for col, row_ in (("B", 51), ("C", 43)):
        c = ws[f"{col}10"]
        c.value = f"={idx(row_)}"
        c.number_format = YEN
        c.border = BORDER
    ws["C10"].font = Font(bold=True, size=12)
    ws["D10"] = "=C10-B10"
    ws["D10"].number_format = YEN
    ws["D10"].font = F_BOLD
    ws["D10"].border = BORDER
    ws.conditional_formatting.add(
        "C10", CellIsRule(operator="lessThan", formula=["0"], fill=FILL_WARN))
    ws.conditional_formatting.add(
        "D10", CellIsRule(operator="lessThan", formula=["0"], fill=FILL_WARN))
    ws.conditional_formatting.add(
        "D10", CellIsRule(operator="greaterThanOrEqual", formula=["0"], fill=FILL_OK))

    # 累計ブロック
    ws["A12"] = "▼ 年間累計"
    ws["A12"].font = F_SECT
    ws["A12"].fill = FILL_SECT
    ws["B12"] = "計画"
    ws["C12"] = "実績"
    ws["D12"] = "差額"
    for c in ("B12", "C12", "D12"):
        ws[c].font = F_HEAD
        ws[c].fill = FILL_HEAD
        ws[c].alignment = Alignment(horizontal="center")

    cum = [
        (13, "売上 累計", f"={idx(22)}", f"={idx(21)}", YEN),
        (14, "★④自社ネット新規 累計", f"={idx(49)}", f"={idx(50)}", '0"件"'),
        (15, "経常利益 累計", f"={idx(52)}", f"={idx(44)}", YEN),
    ]
    for r, nm, p, a, fmt in cum:
        label(ws, f"A{r}", nm)
        ws[f"B{r}"] = p
        ws[f"B{r}"].number_format = fmt
        ws[f"C{r}"] = a
        ws[f"C{r}"].number_format = fmt
        ws[f"D{r}"] = f"=C{r}-B{r}"
        ws[f"D{r}"].number_format = fmt
        ws[f"D{r}"].font = F_BOLD
        for col in "BCD":
            ws[f"{col}{r}"].border = BORDER
        ws.conditional_formatting.add(
            f"D{r}", CellIsRule(operator="lessThan", formula=["0"], fill=FILL_WARN))
        ws.conditional_formatting.add(
            f"D{r}", CellIsRule(operator="greaterThanOrEqual", formula=["0"], fill=FILL_OK))
    ws["E13"] = "※ 「今月」までの累計どうしで比べています。年計画は 売上26,000,000円・④143件・経常利益5,851,371円（中立）"
    ws["E13"].font = F_NOTE

    # ④の月別
    ws["A17"] = "▼ ★④自社ネット新規（2027年の最重要KPI）"
    ws["A17"].font = F_SECT
    ws["A17"].fill = FILL_SECT
    widths(ws, [12] * 13, start_col=2)
    ws["A18"] = "月"
    ws["A19"] = "目標"
    ws["A20"] = "実績"
    ws["A21"] = "差"
    for i, m in enumerate(MONTHS):
        col = get_column_letter(2 + i)
        ws[f"{col}18"] = f"{m}月"
        ws[f"{col}18"].font = F_HEAD
        ws[f"{col}18"].fill = FILL_HEAD
        ws[f"{col}18"].alignment = Alignment(horizontal="center")
        ws[f"{col}19"] = f"='年間成績'!{col}29"
        ws[f"{col}20"] = f"='年間成績'!{col}30"
        ws[f"{col}21"] = f"={col}20-{col}19"
        for r in (19, 20, 21):
            ws[f"{col}{r}"].border = BORDER
            ws[f"{col}{r}"].number_format = '0'
    ws["N18"] = "年計"
    ws["N18"].font = F_HEAD
    ws["N18"].fill = FILL_HEAD
    ws["N19"] = "=SUM(B19:M19)"
    ws["N20"] = "=SUM(B20:M20)"
    ws["N21"] = "=N20-N19"
    ws.conditional_formatting.add(
        "B21:N21", CellIsRule(operator="lessThan", formula=["0"], fill=FILL_WARN))
    ws.conditional_formatting.add(
        "B21:N21", CellIsRule(operator="greaterThanOrEqual", formula=["0"], fill=FILL_OK))

    # 先行指標・警告
    ws["A23"] = "▼ 先行指標と警告"
    ws["A23"].font = F_SECT
    ws["A23"].fill = FILL_SECT
    alerts = [
        (24, "提携先 社数（成約）", "=COUNTIF('提携先_パイプライン'!$E$5:$E$104,\"成約\")", 4,
         "1社増えると年100万円規模で効く"),
        (25, "協力業者 契約社数", "=COUNTA('協力業者_管理'!$A$5:$A$24)-COUNTIF('協力業者_管理'!$B$5:$B$24,\"未契約\")", 3,
         "1〜2月に契約、3月から稼働"),
        (26, "経常利益がマイナスの月数", "='年間成績'!$B$14", 0,
         "★赤字月。0であること"),
        (27, "CPAが9,500円を超えた月数", "=COUNTIF('広告_段管理'!$F$5:$F$16,\">9500\")", 0,
         "★超えた月はその月で広告を止める"),
        (28, "Web予約 未対応の件数", "=COUNTIF('Web予約受信'!$B$5:$B$504,\"未対応\")", 0,
         "★放置ゼロ。当日中に連絡"),
    ]
    ws["B23"] = "現在"
    ws["C23"] = "目標/上限"
    ws["D23"] = "意味"
    for c in ("B23", "C23", "D23"):
        ws[c].font = F_HEAD
        ws[c].fill = FILL_HEAD
        ws[c].alignment = Alignment(horizontal="center")
    for r, nm, f, tgt, memo in alerts:
        label(ws, f"A{r}", nm)
        ws[f"B{r}"] = f
        ws[f"B{r}"].font = Font(bold=True, size=12)
        ws[f"B{r}"].border = BORDER
        ws[f"C{r}"] = tgt
        ws[f"C{r}"].border = BORDER
        ws[f"D{r}"] = memo
        ws[f"D{r}"].font = F_NOTE
    for r in (24, 25):
        ws.conditional_formatting.add(
            f"B{r}", CellIsRule(operator="lessThan", formula=[f"C{r}"], fill=FILL_WARN))
        ws.conditional_formatting.add(
            f"B{r}", CellIsRule(operator="greaterThanOrEqual", formula=[f"C{r}"], fill=FILL_OK))
    for r in (26, 27, 28):
        ws.conditional_formatting.add(
            f"B{r}", CellIsRule(operator="greaterThan", formula=["0"], fill=FILL_WARN))
        ws.conditional_formatting.add(
            f"B{r}", CellIsRule(operator="equal", formula=["0"], fill=FILL_OK))

    ws["A30"] = "【毎月これだけ見れば足ります】① ④自社ネット新規の件数　② 提携先の社数　③ 累計の対計画の差額"
    ws["A30"].font = F_SECT
    ws["A31"] = "④が動かなければ、他は全部後追いにしかなりません（docs/2027-数値目標.md §8）。"
    ws["A31"].font = F_NOTE
    return ws


def build_netinflow(wb):
    ws = wb.create_sheet("ネット流入_週次")
    ws.sheet_properties.tabColor = "00B050"
    title(ws, "ネット流入 週次（★2027年の最重要）",
          "毎週金曜に埋める。CPAは自動計算。9,500円を超えたセルは赤くなります＝その月は広告を止める合図。")
    cols = ["週", "週の開始日(月)", "月", "SNS投稿数", "ブログ本数", "GBP投稿数", "クチコミ返信数",
            "予約フォーム到達数", "受注件数", "広告費", "CPA(自動)", "主な施策・気づき"]
    widths(ws, [6, 14, 6, 10, 10, 10, 12, 14, 10, 12, 12, 46])

    label(ws, "A3", "週あたりの目安", FILL_GOAL)
    ws["D3"] = 5
    ws["E3"] = 1
    ws["F3"] = 2
    ws["G3"] = "全件"
    ws["K3"] = CPA_LIMIT
    ws["K3"].number_format = YEN
    ws["L3"] = "SNS週5本・ブログ週1本・GBP週2本・クチコミは全件返信。CPA上限9,500円（docs/流入経路の分析.md §4）"
    ws["L3"].font = F_NOTE
    for c in ("D3", "E3", "F3", "G3", "K3"):
        ws[c].fill = FILL_GOAL
        ws[c].font = F_BOLD

    header_row(ws, 4, cols)
    start = date(2027, 1, 4)   # 2027年の最初の月曜
    for i in range(52):
        r = 5 + i
        d = start + timedelta(weeks=i)
        ws.cell(row=r, column=1, value=i + 1).number_format = '0'
        c = ws.cell(row=r, column=2, value=d)
        c.number_format = DATE
        ws.cell(row=r, column=3, value=f"=IFERROR(MONTH($B{r}),\"\")").number_format = '0'
        ws.cell(row=r, column=10).number_format = YEN
        cpa = ws.cell(row=r, column=11, value=f'=IFERROR($J{r}/$I{r},"")')
        cpa.number_format = YEN
        cpa.fill = FILL_LOCK
        for col in range(1, 13):
            ws.cell(row=r, column=col).border = BORDER

    ws.conditional_formatting.add(
        "K5:K56", CellIsRule(operator="greaterThan", formula=[str(CPA_LIMIT)], fill=FILL_WARN))
    ws.conditional_formatting.add(
        "K5:K56", CellIsRule(operator="between", formula=["1", str(CPA_LIMIT)], fill=FILL_OK))

    # 月別ロールアップ
    ws["N3"] = "▼ 月別ロールアップ（自動）"
    ws["N3"].font = F_SECT
    ws["N3"].fill = FILL_SECT
    header_row(ws, 4, ["月", "予約フォーム到達", "受注件数", "広告費", "CPA"], start_col=14)
    widths(ws, [8, 16, 12, 12, 12], start_col=14)
    for i, m in enumerate(MONTHS):
        r = 5 + i
        ws.cell(row=r, column=14, value=m).number_format = '0"月"'
        ws.cell(row=r, column=15, value=f'=SUMIFS($H$5:$H$56,$C$5:$C$56,{m})')
        ws.cell(row=r, column=16, value=f'=SUMIFS($I$5:$I$56,$C$5:$C$56,{m})')
        c = ws.cell(row=r, column=17, value=f'=SUMIFS($J$5:$J$56,$C$5:$C$56,{m})')
        c.number_format = YEN
        c2 = ws.cell(row=r, column=18, value=f'=IFERROR($Q{r}/$P{r},"")')
        c2.number_format = YEN
        for col in range(14, 19):
            ws.cell(row=r, column=col).border = BORDER
    ws.conditional_formatting.add(
        "R5:R16", CellIsRule(operator="greaterThan", formula=[str(CPA_LIMIT)], fill=FILL_WARN))
    ws.freeze_panes = "A5"
    return ws


def build_ad(wb):
    ws = wb.create_sheet("広告_段管理")
    ws.sheet_properties.tabColor = "ED7D31"
    title(ws, "広告 段管理 — 小さく試して、成果が出たら加速する",
          "年額を先に決めない。段と、次の段へ上がる条件を先に決める（docs/2027-数値目標.md §5）。")
    cols = ["月", "段", "予算(円)", "実績(円)", "獲得件数", "CPA(自動)", "判定", "判定の目安(自動)", "メモ"]
    widths(ws, [8, 16, 12, 12, 12, 12, 18, 30, 40])
    header_row(ws, 4, cols)
    for i, m in enumerate(MONTHS):
        r = 5 + i
        ws.cell(row=r, column=1, value=m).number_format = '0"月"'
        ws.cell(row=r, column=2, value=AD_STAGE[i])
        c = ws.cell(row=r, column=3, value=AD_BUDGET[i])
        c.number_format = YEN
        c.fill = FILL_GOAL
        ws.cell(row=r, column=4).number_format = YEN
        cpa = ws.cell(row=r, column=6, value=f'=IFERROR($D{r}/$E{r},"")')
        cpa.number_format = YEN
        cpa.fill = FILL_LOCK
        ws.cell(row=r, column=7, value="未判定")
        g = ws.cell(row=r, column=8,
                    value=f'=IF($E{r}=0,"データなし",IF($F{r}>{CPA_LIMIT},'
                          f'"止める（CPA超過）","この月はクリア"))')
        g.fill = FILL_LOCK
        for col in range(1, 10):
            ws.cell(row=r, column=col).border = BORDER
    r = 17
    ws.cell(row=r, column=1, value="年計").font = F_BOLD
    ws.cell(row=r, column=3, value="=SUM(C5:C16)").number_format = YEN
    ws.cell(row=r, column=4, value="=SUM(D5:D16)").number_format = YEN
    ws.cell(row=r, column=5, value="=SUM(E5:E16)")
    ws.cell(row=r, column=6, value='=IFERROR(D17/E17,"")').number_format = YEN
    for col in range(1, 7):
        ws.cell(row=r, column=col).font = F_BOLD

    dv(ws, L_AD_DAN, ["B5:B16"])
    dv(ws, L_AD_HANTEI, ["G5:G16"])
    ws.conditional_formatting.add(
        "F5:F17", CellIsRule(operator="greaterThan", formula=[str(CPA_LIMIT)], fill=FILL_WARN))
    ws.conditional_formatting.add(
        "F5:F17", CellIsRule(operator="between", formula=["1", str(CPA_LIMIT)], fill=FILL_OK))

    ws["K3"] = "▼ 段の定義とルール"
    ws["K3"].font = F_SECT
    ws["K3"].fill = FILL_SECT
    rules = [
        ("段0（テスト）", "月5万", "1〜2月に実施。ここは無条件で出す"),
        ("段1", "月6〜10万", "段0でCPA 9,500円以下なら上がる"),
        ("段2（繁忙期）", "月12〜15万", "段1を2か月連続クリア。5〜7月に当てる"),
        ("段3（年末）", "月7〜10万", "段2をクリア。10〜11月に当てる"),
        ("", "", ""),
        ("上限", "CPA 9,500円", "マッチングPFに払っている実質手数料と同額"),
        ("止める条件", "", "月次でCPAが9,500円を超えたら、その月で止める。次の段へ上がらない"),
        ("上げる条件", "", "2か月連続でCPA 9,500円以下、かつ受注が実際に付いている"),
        ("使わない", "", "Facebook広告は再開しない（CPC95.39円で撃沈済み）。チラシ単独配布もしない"),
        ("出さない", "", "レントラックスとの関係上、指名検索への出稿はしない"),
    ]
    header_row(ws, 4, ["段／ルール", "金額", "内容"], start_col=11)
    widths(ws, [16, 14, 56], start_col=11)
    for i, (a, b, c) in enumerate(rules):
        ws.cell(row=5 + i, column=11, value=a).font = F_BOLD
        ws.cell(row=5 + i, column=12, value=b)
        ws.cell(row=5 + i, column=13, value=c).font = F_NORM
    return ws


def build_teikei(wb):
    ws = wb.create_sheet("提携先_パイプライン")
    ws.sheet_properties.tabColor = "4472C4"
    title(ws, "提携先パイプライン — 2社 → 4社（中立）",
          "業務提携は平均単価100,128円・LTV186,272円・リピート率45%。1社増えると年100万円規模で効きます。")
    label(ws, "A3", "成約 社数", FILL_GOAL)
    ws["B3"] = '=COUNTIF($E$5:$E$104,"成約")'
    ws["B3"].font = Font(bold=True, size=14)
    ws["B3"].fill = FILL_GOAL
    label(ws, "C3", "目標", FILL_GOAL)
    ws["D3"] = 4
    ws["D3"].fill = FILL_GOAL
    ws["E3"] = "保守3社／中立4社／攻め6社。入口は施設ターゲットリスト291件と、不動産管理会社の空室清掃（相手の繁忙期2〜3月＝当社の閑散期）"
    ws["E3"].font = F_NOTE
    ws.conditional_formatting.add(
        "B3", CellIsRule(operator="lessThan", formula=["D3"], fill=FILL_WARN))
    ws.conditional_formatting.add(
        "B3", CellIsRule(operator="greaterThanOrEqual", formula=["D3"], fill=FILL_OK))

    cols = ["先方名", "業種", "担当者", "初回接触日", "ステージ", "紹介件数(累計)",
            "売上(累計)", "次アクション", "次アクション期日", "担当", "メモ"]
    widths(ws, [26, 16, 14, 13, 14, 13, 14, 30, 14, 12, 36])
    header_row(ws, 4, cols)
    for r in range(5, 105):
        ws.cell(row=r, column=4).number_format = DATE
        ws.cell(row=r, column=7).number_format = YEN
        ws.cell(row=r, column=9).number_format = DATE
    dv(ws, L_TEIKEI_STAGE, ["E5:E104"])
    ws.freeze_panes = "A5"
    ws.auto_filter.ref = "A4:K104"
    return ws


def build_gyosha(wb):
    ws = wb.create_sheet("協力業者_管理")
    ws.sheet_properties.tabColor = "A9D08E"
    title(ws, "協力業者 管理 — 3社（1〜2月に契約・3月から稼働）",
          "「安く回す先」ではなく「ピークを取りこぼさないための保険」。品質が崩れると入口が全部止まります。")
    for cell, text, val in (("A3", "契約済み 社数", '=COUNTIFS($B$5:$B$24,"<>未契約",$A$5:$A$24,"<>")'),
                            ("C3", "目標", 3),
                            ("E3", "年間 外注件数 目標", 100)):
        label(ws, cell, text, FILL_GOAL)
        vc = ws.cell(row=3, column=ws[cell].column + 1, value=val)
        vc.fill = FILL_GOAL
        vc.font = Font(bold=True, size=13)
    ws["G3"] = "支払条件は未決定（案A歩合65%／案Bメニュー別固定単価／案C日当22,000円）。12月中に方針を決める（docs/2027-数値目標.md §6）"
    ws["G3"].font = F_NOTE

    cols = ["社名", "契約形態", "条件（%・単価・日当）", "対応エリア", "契約日",
            "今年回した件数", "支払額(累計)", "クレーム件数", "写真提出率", "品質", "メモ"]
    widths(ws, [24, 20, 22, 20, 13, 14, 14, 13, 12, 10, 36])
    header_row(ws, 4, cols)
    for r in range(5, 25):
        ws.cell(row=r, column=5).number_format = DATE
        ws.cell(row=r, column=7).number_format = YEN
        ws.cell(row=r, column=9).number_format = PCT
    dv(ws, L_GYOSHA_KEIYAKU, ["B5:B24"])
    dv(ws, L_GYOSHA_HINSHITSU, ["J5:J24"])
    ws.conditional_formatting.add(
        "H5:H24", CellIsRule(operator="greaterThan", formula=["0"], fill=FILL_WARN))

    ws["A27"] = "【必ず守ること】"
    ws["A27"].font = F_SECT
    for i, t in enumerate([
        "・協力業者の案件でも、お客様に届くもの（連絡・名乗り）は台帳の「最新の施工の名義」と機械で照合してから出す",
        "　（tools/derive-soushin-keitou.py の meigi_hyou()。2026-09-11に名義取り違えの事故あり）",
        "・施工チェックリストと写真報告を必須にする。契約書に品質条項を入れる",
        "・★5.0（24件）と満足度98.6%が崩れると、入口が全部止まります",
    ]):
        ws.cell(row=28 + i, column=1, value=t).font = F_NOTE
    return ws


def build_yoyaku(wb):
    ws = wb.create_sheet("Web予約受信")
    ws.sheet_properties.tabColor = "00B0F0"
    title(ws, "Web予約 受信ログ（予約フォーム・LP）",
          "受信したら当日中に連絡。受注になったら月次タブへ転記して「台帳へ転記済み」をTRUEに。")
    for i, (nm, f, fmt) in enumerate([
        ("受信件数", '=COUNTA($A$5:$A$504)', '0"件"'),
        ("受注件数", '=COUNTIF($B$5:$B$504,"受注")', '0"件"'),
        ("受注率", '=IFERROR(COUNTIF($B$5:$B$504,"受注")/COUNTA($A$5:$A$504),0)', PCT),
        ("未対応", '=COUNTIF($B$5:$B$504,"未対応")', '0"件"'),
    ]):
        col = 1 + i * 2
        label(ws, f"{get_column_letter(col)}3", nm, FILL_GOAL)
        c = ws.cell(row=3, column=col + 1, value=f)
        c.number_format = fmt
        c.fill = FILL_GOAL
        c.font = Font(bold=True, size=12)
    ws.conditional_formatting.add(
        "H3", CellIsRule(operator="greaterThan", formula=["0"], fill=FILL_WARN))

    cols = ["受信日時", "状態", "お名前", "連絡先", "ご希望日", "ご希望の内容",
            "流入元(?src=)", "台帳へ転記済み", "対応メモ"]
    widths(ws, [18, 12, 18, 16, 14, 30, 20, 14, 40])
    header_row(ws, 4, cols)
    for r in range(5, 505):
        ws.cell(row=r, column=1).number_format = 'yyyy/mm/dd hh:mm'
        ws.cell(row=r, column=5).number_format = DATE
    dv(ws, L_YOYAKU_STATE, ["B5:B504"])
    dv(ws, L_TF, ["H5:H504"])
    ws.freeze_panes = "A5"
    ws.auto_filter.ref = "A4:I504"
    ws["A506"] = "※ 個人情報が入る表です。共有範囲を広げないこと。お客様に送るURLは独自ドメインから（docs/事故報告-2026-09-12-セーフブラウジング.md）"
    ws["A506"].font = F_NOTE
    return ws


LEDGER_COLS = [
    ("顧客ID", 11), ("名義", 10), ("送信系統", 11), ("氏名", 18), ("フリガナ", 18),
    ("法人/個人", 11), ("紹介者（法人名など）", 24), ("TEL1", 15), ("TEL2", 15),
    ("郵便番号", 11), ("都県", 9), ("住所", 30), ("メール", 22), ("公式LINE", 11),
    ("初回施工日", 13), ("初回の入口", 16), ("最終施工日", 13), ("最終施工の名義", 14),
    ("施工回数", 10), ("総受注額", 13), ("平均単価", 12), ("主な流入経路", 16),
    ("実施済みメニュー（全文）", 34), ("エアコン", 10), ("換気扇", 10), ("浴室", 10),
    ("洗濯機", 10), ("トイレ/洗面", 12), ("次回案内予定月", 14), ("連絡可否", 11),
    ("満足度/クチコミ", 14), ("備考", 34),
]


def build_daichou(wb):
    ws = wb.create_sheet("顧客管理台帳")
    ws.sheet_properties.tabColor = "8FAADC"
    title(ws, "顧客管理台帳（2027年版・空の器）",
          "2026年からの実データ移行は年末にオーナーが行います。ヘッダーは15行目、データは16行目から（2026年版と同じ）。")
    widths(ws, [w for _, w in LEDGER_COLS])

    ws["A4"] = "▼ ダッシュボード（自動）"
    ws["A4"].font = F_SECT
    ws["A4"].fill = FILL_SECT
    D1, D2 = 16, 2015
    stats = [
        (5, "顧客数", f'=COUNTA($A${D1}:$A${D2})', '0"名"'),
        (6, "2回以上ご利用", f'=COUNTIF($S${D1}:$S${D2},">=2")', '0"名"'),
        (7, "リピート率", f'=IFERROR(COUNTIF($S${D1}:$S${D2},">=2")/COUNTA($A${D1}:$A${D2}),0)', PCT),
        (8, "総受注額", f'=SUM($T${D1}:$T${D2})', YEN),
        (9, "平均LTV", f'=IFERROR(SUM($T${D1}:$T${D2})/COUNTA($A${D1}:$A${D2}),0)', YEN),
        (10, "自社名義", f'=COUNTIF($B${D1}:$B${D2},"自社")', '0"名"'),
        (11, "本舗名義", f'=COUNTIF($B${D1}:$B${D2},"本舗")', '0"名"'),
        (12, "連絡不可（楽ラクーン等）", f'=COUNTIF($C${D1}:$C${D2},"連絡不可")', '0"名"'),
    ]
    for r, nm, f, fmt in stats:
        label(ws, f"A{r}", nm)
        c = ws[f"B{r}"]
        c.value = f
        c.number_format = fmt
        c.font = Font(bold=True, size=12)
        c.fill = FILL_LOCK
    ws["D5"] = "2026年実績：957名・平均LTV 54,650円・リピート率25.0%。2027年目標 リピート率30%（中立）"
    ws["D5"].font = F_NOTE
    ws["D7"] = "★お客様に届くもの（SMS・LINE・電話）は、この台帳の「最終施工の名義」と機械照合してから作ること"
    ws["D7"].font = F_SECT
    ws["D8"] = "　tools/derive-soushin-keitou.py の meigi_hyou()。列の値を信じないこと（2026-09-11 名義取り違え事故）"
    ws["D8"].font = F_NOTE
    ws["D9"] = "★楽ラクーン経由はフォロー連絡ができません。送信系統＝連絡不可 にしてリストから恒久的に外します"
    ws["D9"].font = F_NOTE
    ws["D10"] = "★紹介者（法人）と実際のご利用者（個人）が別の案件があります。氏名欄・TEL欄に押し込まないこと"
    ws["D10"].font = F_NOTE

    header_row(ws, 15, [n for n, _ in LEDGER_COLS])
    for r in range(D1, D2 + 1):
        ws.cell(row=r, column=15).number_format = DATE
        ws.cell(row=r, column=17).number_format = DATE
        ws.cell(row=r, column=20).number_format = YEN
        ws.cell(row=r, column=21).number_format = YEN
    dv(ws, L_MEIGI, [f"B{D1}:B{D2}", f"R{D1}:R{D2}"])
    dv(ws, L_SOUSHIN, [f"C{D1}:C{D2}"])
    dv(ws, L_RYUNYU, [f"P{D1}:P{D2}", f"V{D1}:V{D2}"])
    ws.freeze_panes = f"E{D1}"
    ws.auto_filter.ref = f"A15:{get_column_letter(len(LEDGER_COLS))}{D2}"
    return ws


def build_saihan(wb):
    ws = wb.create_sheet("再販リスト")
    ws.sheet_properties.tabColor = "BDD7EE"
    title(ws, "再販リスト — 案内時期が来た方を抽出する器",
          "顧客管理台帳から貼り付けて使います。次回案内月は EDATE（最終施工日, サイクル月数）で自動計算。")
    cols = ["顧客ID", "名義", "送信系統", "氏名", "TEL", "最終施工日", "実施メニュー",
            "サイクル(月)", "次回案内月(自動)", "案内状況", "案内日", "手段", "結果", "メモ"]
    widths(ws, [11, 10, 11, 18, 15, 13, 22, 11, 14, 12, 13, 11, 20, 30])
    header_row(ws, 4, cols)
    for r in range(5, 1005):
        ws.cell(row=r, column=6).number_format = DATE
        ws.cell(row=r, column=9, value=f'=IFERROR(EDATE($F{r},$H{r}),"")').number_format = DATE
        ws.cell(row=r, column=9).fill = FILL_LOCK
        ws.cell(row=r, column=11).number_format = DATE
    dv(ws, L_MEIGI, ["B5:B1004"])
    dv(ws, L_SOUSHIN, ["C5:C1004"])
    dv(ws, L_SAIHAN_STATE, ["J5:J1004"])
    dv(ws, L_SAIHAN_SHUDAN, ["L5:L1004"])
    ws.freeze_panes = "A5"
    ws.auto_filter.ref = "A4:N1004"

    ws["P3"] = "▼ 推奨サイクル"
    ws["P3"].font = F_SECT
    ws["P3"].fill = FILL_SECT
    header_row(ws, 4, ["メニュー", "サイクル(月)", "案内の時期"], start_col=16)
    widths(ws, [22, 13, 26], start_col=16)
    cycles = [
        ("エアコン(ノーマル/ロボ)", 12, "3〜4月・9〜10月に案内"),
        ("浴室", 12, "施工の11か月後"),
        ("換気扇（レンジフード）", 12, "11〜12月（年末）"),
        ("洗濯機", 12, "施工の11か月後"),
        ("トイレ/洗面", 12, "他メニューと同時提案"),
        ("追焚配管", 24, "浴室と同時提案"),
        ("おそうじ定期便", 1, "毎月"),
        ("定期清掃（法人）", 1, "契約による"),
    ]
    for i, (a, b, c) in enumerate(cycles):
        ws.cell(row=5 + i, column=16, value=a)
        ws.cell(row=5 + i, column=17, value=b)
        ws.cell(row=5 + i, column=18, value=c).font = F_NOTE

    ws["P15"] = "【送る前に必ず】"
    ws["P15"].font = F_SECT
    for i, t in enumerate([
        "・楽ラクーン経由は連絡不可。送信系統で外す",
        "・スケジュールマッチング／入札案件は「本舗の番号」から",
        "・名乗り（ワンヒッター／おそうじ本舗）は台帳の最終施工の名義と機械照合してから",
        "・実施メニュー列だけで「未購入」を判定しない。備考の全文キーワード照合を併用",
        "　（2026年分だけで21行・14名が該当。既に施工済みのお客様へ売り込むことになる）",
    ]):
        ws.cell(row=16 + i, column=16, value=t).font = F_NOTE
    return ws


def build_bunseki_kensuu(wb):
    ws = wb.create_sheet("分析_件数単価流入")
    ws.sheet_properties.tabColor = "FFD966"
    title(ws, "分析：月別の件数・単価と、流入経路別の内訳",
          "すべて月次タブを SUMIFS / COUNTIFS で参照しています。手入力するところはありません。")
    widths(ws, [24] + [12] * 12 + [14])

    header_row(ws, 4, ["項目"] + [f"{m}月" for m in MONTHS] + ["年計"])
    rows = [
        ("件数", lambda m: f"='{s_uriage(m)}'!${UC['流入経路']}$4", '0', "sum"),
        ("売上", lambda m: f"='{s_uriage(m)}'!${UC['売上（税込）']}$4", YEN, "sum"),
        ("平均単価", lambda m: f"='{s_uriage(m)}'!${UC['流入元の識別子(?src=)']}$4", YEN, "avg"),
        ("自社件数", lambda m: f"='{s_uriage(m)}'!${UC['売上種類']}$4", '0', "sum"),
        ("本舗件数", lambda m: f"='{s_uriage(m)}'!${UC['施工日付']}$4", '0', "sum"),
        ("自社単価", lambda m: f"='{s_uriage(m)}'!${UC['氏名']}$4", YEN, "avg"),
        ("本舗単価", lambda m: f"='{s_uriage(m)}'!${UC['TEL(-無し)']}$4", YEN, "avg"),
        ("④自社ネット新規 件数", lambda m: f"='{s_uriage(m)}'!${UC['備考(お客様の声)']}$4", '0', "sum"),
        ("④自社ネット新規 売上", lambda m: f"='{s_uriage(m)}'!${UC['入金経路']}$4", YEN, "sum"),
    ]
    for i, (nm, f, fmt, tot) in enumerate(rows):
        r = 5 + i
        ws.cell(row=r, column=1, value=nm).font = F_BOLD
        for j, m in enumerate(MONTHS):
            c = ws.cell(row=r, column=2 + j, value=f(m))
            c.number_format = fmt
            c.border = BORDER
        t = ws.cell(row=r, column=14,
                    value=f"=SUM(B{r}:M{r})" if tot == "sum" else f"=IFERROR(AVERAGE(B{r}:M{r}),0)")
        t.number_format = fmt
        t.font = F_BOLD

    # 流入経路別（件数／売上）
    base = 16
    for blk, (blabel, kind) in enumerate([("▼ 流入経路別 件数", "count"), ("▼ 流入経路別 売上", "sum")]):
        top = base + blk * (len(L_RYUNYU) + 4)
        ws.cell(row=top, column=1, value=blabel).font = F_SECT
        ws.cell(row=top, column=1).fill = FILL_SECT
        header_row(ws, top + 1, ["流入経路"] + [f"{m}月" for m in MONTHS] + ["年計"])
        for i, ch in enumerate(L_RYUNYU):
            r = top + 2 + i
            ws.cell(row=r, column=1, value=ch).font = F_NORM
            for j, m in enumerate(MONTHS):
                sh = s_uriage(m)
                if kind == "count":
                    f = f"=COUNTIFS('{sh}'!{rng(UC['流入経路'])},$A{r})"
                    fmt = '0'
                else:
                    f = (f"=SUMIFS('{sh}'!{rng(UC['売上（税込）'])},"
                         f"'{sh}'!{rng(UC['流入経路'])},$A{r})")
                    fmt = YEN
                c = ws.cell(row=r, column=2 + j, value=f)
                c.number_format = fmt
                c.border = BORDER
            t = ws.cell(row=r, column=14, value=f"=SUM(B{r}:M{r})")
            t.number_format = '0' if kind == "count" else YEN
            t.font = F_BOLD
        rt = top + 2 + len(L_RYUNYU)
        ws.cell(row=rt, column=1, value="合計").font = F_BOLD
        for j in range(13):
            col = get_column_letter(2 + j)
            c = ws.cell(row=rt, column=2 + j,
                        value=f"=SUM({col}{top+2}:{col}{rt-1})")
            c.number_format = '0' if kind == "count" else YEN
            c.font = F_BOLD
    ws.freeze_panes = "B5"
    return ws


def build_bunseki_ltv(wb):
    ws = wb.create_sheet("分析_流入経路とLTV")
    ws.sheet_properties.tabColor = "F4B183"
    title(ws, "入口ごとのLTVとリピート率 — 広告CPA上限9,500円の根拠",
          "2026年実績（docs/流入経路の分析.md、319件＋顧客管理台帳）。2027年の列は年末に埋めます。")

    ws["A4"] = ("★広告CPAの上限は9,500円。マッチングPFに払っている実質手数料（35%・1件あたり約9,500円）と同額。"
                "ここを下回る限り、出すほど有利です。しかも自社経由のお客様はリピート率36%なので2回目以降が上乗せされます。")
    ws["A4"].font = F_SECT

    header_row(ws, 6, ["初回の入口", "2026 施工数", "2026 平均施工回数", "2026 平均LTV",
                       "2026 リピート率", "2027 施工数", "2027 平均LTV", "2027 リピート率", "メモ"])
    widths(ws, [30, 13, 16, 14, 14, 13, 14, 14, 44])
    data = [
        ("マッチングPF（楽ラクーン・スケジュールマッチング等）", 100, 1.02, 28172, 0.02,
         "35%の手数料を払って、二度と戻ってこないお客様を借りている状態"),
        ("業務提携", 40, 2.52, 186272, 0.45, "他の入口とは桁が違う。2社→4社が2027年の②ブロック"),
        ("自社直販（HP・紹介・営業・チラシ・SMS）", 28, 1.26, 42823, 0.26,
         "LTVは1.5倍・リピートは18倍。ここを増やすのが④ブロック"),
    ]
    for i, (nm, n, avg, ltv, rep, memo) in enumerate(data):
        r = 7 + i
        ws.cell(row=r, column=1, value=nm)
        ws.cell(row=r, column=2, value=n)
        ws.cell(row=r, column=3, value=avg).number_format = '0.00'
        ws.cell(row=r, column=4, value=ltv).number_format = YEN
        ws.cell(row=r, column=5, value=rep).number_format = PCT
        ws.cell(row=r, column=7).number_format = YEN
        ws.cell(row=r, column=8).number_format = PCT
        ws.cell(row=r, column=9, value=memo).font = F_NOTE
        for c in range(1, 10):
            ws.cell(row=r, column=c).border = BORDER

    ws["A12"] = "▼ 2026年 流入経路別の売上（全319件・12,636,141円）"
    ws["A12"].font = F_SECT
    ws["A12"].fill = FILL_SECT
    header_row(ws, 13, ["流入経路", "件数", "売上", "単価", "メモ"])
    ref = [
        ("リピート", 69, 3130845, 45374, ""),
        ("楽ラクーン", 67, 1845833, 27549, "フォロー連絡 不可"),
        ("早期予約", 65, 1510138, 23232, ""),
        ("業務提携", 40, 4005135, 100128, "2026年8月の大型案件1,841,740円を含む。再現前提にしない"),
        ("スケジュールマッチング", 31, 831050, 26808, "本舗の番号から連絡"),
        ("おそうじ定期便", 12, 117600, 9800, ""),
        ("紹介", 11, 379460, 34496, ""),
        ("営業", 8, 391820, 48977, ""),
        ("チラシ(OH)", 4, 77800, 19450, ""),
        ("HP", 4, 63100, 15775, "★売上全体の0.5%。HP関連費は年580,800円。2027年に必ず黒字化させる"),
        ("その他（入札・チラシ本舗・SMS等）", 8, 283360, None, ""),
    ]
    for i, (nm, n, uri, tan, memo) in enumerate(ref):
        r = 14 + i
        ws.cell(row=r, column=1, value=nm)
        ws.cell(row=r, column=2, value=n)
        ws.cell(row=r, column=3, value=uri).number_format = YEN
        if tan:
            ws.cell(row=r, column=4, value=tan).number_format = YEN
        ws.cell(row=r, column=5, value=memo).font = F_NOTE
        for c in range(1, 6):
            ws.cell(row=r, column=c).border = BORDER

    ws["A27"] = "【正直に書いておく限界】"
    ws["A27"].font = F_SECT
    for i, t in enumerate([
        "・マッチングPFの規約で、そこ経由のお客様との直接取引が禁じられている可能性があります。再販の前に契約書の確認が要ります",
        "・台帳の「回数」は通算値。2026年に初めて来たお客様の観察期間は最長8か月です（1〜6月に絞った再計算でもマッチングPFは2%のまま）",
        "・業務提携のLTVには法人・寮・店舗の大型案件が含まれます。個人のお客様と単純比較はできません",
        "・おそうじ本舗（フランチャイズ）経由の分は、送信主体が異なるため自社直販に含めていません",
    ]):
        ws.cell(row=28 + i, column=1, value=t).font = F_NOTE
    return ws


def build_mitsumori(wb, prices):
    ws = wb.create_sheet("見積ルール")
    ws.sheet_properties.tabColor = "D0CECE"
    title(ws, "見積ルール・料金表（全て税込）",
          "正データは data/prices.json。ここは焼き込みです。数字を変えるときは prices.json と公開物（公式サイトTOP・LP）も必ず揃えること。")
    ws["A3"] = ("★5・6・7・12月は全メニューに繁忙期加算 ¥3,300（税込）が加算されます。"
                "オプションの防カビコート¥3,630・浴室換気扇洗浄¥3,630と数字が近いので取り違えないこと。")
    ws["A3"].font = F_SECT

    header_row(ws, 5, ["本メニュー", "単体（税込）", "同時施工（税込）", "所要"])
    widths(ws, [34, 15, 16, 12, 4, 34, 15, 16, 40])
    r = 6
    for it in prices["本メニュー"]:
        ws.cell(row=r, column=1, value=it["名称"])
        ws.cell(row=r, column=2, value=it["単体"]).number_format = YEN0
        if it.get("同時施工"):
            ws.cell(row=r, column=3, value=it["同時施工"]).number_format = YEN0
        ws.cell(row=r, column=4, value=it.get("所要", ""))
        for c in range(1, 5):
            ws.cell(row=r, column=c).border = BORDER
        r += 1

    header_row(ws, 5, ["オプション", "価格（税込）"], start_col=6)
    r = 6
    for it in prices["オプション"]:
        ws.cell(row=r, column=6, value=it["名称"])
        ws.cell(row=r, column=7, value=it["価格"]).number_format = YEN0
        for c in (6, 7):
            ws.cell(row=r, column=c).border = BORDER
        r += 1

    r2 = 8 + len(prices["本メニュー"])
    ws.cell(row=r2, column=1, value="▼ 法人メニュー").font = F_SECT
    header_row(ws, r2 + 1, ["メニュー", "価格（税込）", "備考"])
    for i, it in enumerate(prices.get("法人", [])):
        rr = r2 + 2 + i
        ws.cell(row=rr, column=1, value=it["名称"])
        ws.cell(row=rr, column=2, value=it["価格"]).number_format = YEN0
        ws.cell(row=rr, column=3, value=it.get("下限表記", ""))

    r3 = r2 + 3 + len(prices.get("法人", [])) + 1
    ws.cell(row=r3, column=1, value="▼ 割引・紹介のルール").font = F_SECT
    lines = []
    for k, v in prices.get("早期予約割引", {}).items():
        if not k.startswith("_"):
            lines.append((f"早期予約割引 {k}", str(v)))
    for k, v in prices.get("同時施工割引", {}).items():
        if not k.startswith("_"):
            lines.append((f"同時施工割引 {k}", str(v)))
    for k, v in prices.get("紹介", {}).items():
        if not k.startswith("_"):
            lines.append((f"紹介料 {k}", str(v)))
    lines.append(("繁忙期加算", f"{prices['繁忙期加算']['金額']}円（対象月 {prices['繁忙期加算']['対象月']}）"))
    for i, (a, b) in enumerate(lines):
        ws.cell(row=r3 + 1 + i, column=1, value=a).font = F_NORM
        ws.cell(row=r3 + 1 + i, column=2, value=b).font = F_NORM

    r4 = r3 + 2 + len(lines)
    for i, t in enumerate([
        "【必ず守ること】",
        "・料金はパンフレットPDFが正。公式サイトの料金表には誤りがあります（docs/site-audit.md）",
        "・2021年4月から総額表示が義務。必ず「（税込）」を併記すること",
        "・満足度は 98.6%（209名中206名／2023年1月〜2025年12月）。「98.8%」は根拠と一致しないので使わないこと",
        "・対応エリアは東京都・千葉県・神奈川県（埼玉は実績ありだが積極開拓しない）",
        f"・この表の出典：data/prices.json（{prices.get('_出典','')}）",
    ]):
        ws.cell(row=r4 + i, column=1, value=t).font = F_SECT if t.startswith("【") else F_NOTE
    return ws


def build_todo(wb):
    ws = wb.create_sheet("TODO")
    ws.sheet_properties.tabColor = "FFE699"
    title(ws, "TODO", "状態を「完了」にしたら行を消さないこと。あとで何をやったか分からなくなります。")
    for i, (nm, st) in enumerate([("未着手", "未着手"), ("進行中", "進行中"),
                                  ("完了", "完了"), ("対象外", "対象外")]):
        col = 1 + i * 2
        label(ws, f"{get_column_letter(col)}3", nm, FILL_GOAL)
        c = ws.cell(row=3, column=col + 1, value=f'=COUNTIF($E$5:$E$304,"{st}")')
        c.number_format = '0"件"'
        c.fill = FILL_GOAL
        c.font = Font(bold=True, size=12)
    cols = ["No.", "件名", "内容", "担当", "状態", "期限", "優先度", "更新日", "メモ"]
    widths(ws, [6, 28, 46, 14, 12, 13, 10, 13, 30])
    header_row(ws, 4, cols)
    for r in range(5, 305):
        ws.cell(row=r, column=6).number_format = DATE
        ws.cell(row=r, column=8).number_format = DATE
    dv(ws, L_TODO_STATE, ["E5:E304"])
    dv(ws, L_TODO_PRI, ["G5:G304"])
    ws.conditional_formatting.add(
        "A5:I304", FormulaRule(formula=['$E5="完了"'], fill=FILL_LOCK))
    ws.freeze_panes = "A5"
    ws.auto_filter.ref = "A4:I304"
    return ws


def build_kintai(wb):
    ws = wb.create_sheet("勤怠管理")
    ws.sheet_properties.tabColor = "C9C9C9"
    title(ws, "勤怠管理", "労働時間は自動計算（終了−開始−休憩）。現場人件費（原価）の根拠になります。")
    cols = ["日付", "月(自動)", "氏名", "開始", "終了", "休憩(h)", "労働時間(h・自動)", "現場数", "区分", "メモ"]
    widths(ws, [13, 9, 14, 9, 9, 10, 16, 10, 12, 34])
    header_row(ws, 4, cols)
    for r in range(5, 1005):
        ws.cell(row=r, column=1).number_format = DATE
        ws.cell(row=r, column=2, value=f'=IFERROR(MONTH($A{r}),"")').number_format = '0'
        ws.cell(row=r, column=2).fill = FILL_LOCK
        ws.cell(row=r, column=4).number_format = 'hh:mm'
        ws.cell(row=r, column=5).number_format = 'hh:mm'
        c = ws.cell(row=r, column=7, value=f'=IFERROR(($E{r}-$D{r})*24-$F{r},"")')
        c.number_format = NUM1
        c.fill = FILL_LOCK
    dv(ws, L_TANTOU, ["C5:C1004"])
    dv(ws, L_KINTAI_KUBUN, ["I5:I1004"])
    ws.freeze_panes = "A5"
    ws.auto_filter.ref = "A4:J1004"

    ws["L3"] = "▼ 月別 集計（自動）"
    ws["L3"].font = F_SECT
    ws["L3"].fill = FILL_SECT
    header_row(ws, 4, ["月", "労働時間(h)", "現場数"], start_col=12)
    widths(ws, [8, 14, 12], start_col=12)
    for i, m in enumerate(MONTHS):
        r = 5 + i
        ws.cell(row=r, column=12, value=m).number_format = '0"月"'
        ws.cell(row=r, column=13,
                value=f'=SUMIFS($G$5:$G$1004,$B$5:$B$1004,{m})').number_format = NUM1
        ws.cell(row=r, column=14, value=f'=SUMIFS($H$5:$H$1004,$B$5:$B$1004,{m})')
    ws.cell(row=17, column=12, value="年計").font = F_BOLD
    ws.cell(row=17, column=13, value="=SUM(M5:M16)").number_format = NUM1
    ws.cell(row=17, column=14, value="=SUM(N5:N16)")
    return ws


def build_memo(wb):
    ws = wb.create_sheet("メモ・変更履歴")
    ws.sheet_properties.tabColor = "D9D9D9"
    title(ws, "メモ・変更履歴",
          "このスプレッドシートに手を入れたら1行足すこと。元に戻せるようにしておくのが目的です。")
    cols = ["日付", "変更したタブ", "変更内容", "変更した人", "元に戻す方法", "バックアップの場所"]
    widths(ws, [13, 22, 52, 14, 34, 34])
    header_row(ws, 4, cols)
    seed = [
        (date(2026, 9, 13), "全タブ", "2027年度版を新規作成（tools/build-sheet-2027.py で生成）",
         "CMO配下スレッド", "同スクリプトを再実行すれば同じものが出ます",
         "リポジトリ one-marketing / spreadsheet/2027/"),
        (date(2026, 9, 13), "◯月_支出成績",
         "月次P/Lを経費入力表の右（M列）へ移動。2026年版は経費行を足すとP/Lがずれていた（6月+19行・7月+33行）",
         "CMO配下スレッド", "—", "—"),
        (date(2026, 9, 13), "◯月_支出成績",
         "科目に 保険料・通信費・外注費 を追加。人件費を「現場人件費(原価)」と「固定給(販管費)」に分割",
         "CMO配下スレッド", "—", "—"),
        (date(2026, 9, 13), "◯月_支出成績",
         "ロイヤリティの二重計上を解消。P/Lの1か所だけで数える（15行目で引いて19行目で足す）",
         "CMO配下スレッド", "—", "—"),
        (date(2026, 9, 13), "◯月_売上顧客",
         "列を追加：流入元の識別子(?src=)／施工担当。④自社ネット新規を機械で数えられるようにした",
         "CMO配下スレッド", "—", "—"),
        (date(2026, 9, 13), "年間成績",
         "和真配分の行を削除し、「対計画の差額」「累計の対計画の差額」を追加",
         "CMO配下スレッド", "—", "—"),
    ]
    for i, row in enumerate(seed):
        r = 5 + i
        for j, v in enumerate(row):
            c = ws.cell(row=r, column=1 + j, value=v)
            c.border = BORDER
            c.alignment = Alignment(wrap_text=True, vertical="top")
            if j == 0:
                c.number_format = DATE
    for r in range(5 + len(seed), 205):
        ws.cell(row=r, column=1).number_format = DATE

    ws["A210"] = "【このスプレッドシートを直すときの3原則】"
    ws["A210"].font = F_SECT
    for i, t in enumerate([
        "1. 過去の実績データを書き換えない（施工日付・売上・氏名・住所・メニュー等の記録）",
        "2. 変更前にバックアップを取る（Driveでコピー）",
        "3. 変更履歴を残す（この表 または docs/sheet-changelog.md）",
        "",
        "この3つを守るなら、集計タブ・入力規則・書式の変更や新規タブの追加は、確認を取らずに進めてよい（オーナー方針）。",
    ]):
        ws.cell(row=211 + i, column=1, value=t).font = F_NOTE
    return ws


TOC = [
    ("【まず見る】", None, None),
    ("目次", "このタブ。どこに何があるか", "迷ったとき"),
    ("ダッシュボード", "今月と累計の対計画、④自社ネット新規、提携先社数、赤字月の警告", "毎朝／毎週月曜"),
    ("【毎日・毎月の入力】", None, None),
    ("1月_売上顧客 〜 12月_売上顧客", "1件1行で施工を記録。2行目に今月の目標、4行目に自動集計", "施工したその日"),
    ("1月_支出成績 〜 12月_支出成績", "左が経費入力、右（M列）が月次P/L。P/Lは行が動きません", "経費が出たとき／月末"),
    ("【計画と実績】", None, None),
    ("2027年計画", "中立（正式目標）の月次と、保守・攻めの年計。実績で書き換えない", "年初・四半期の判定ゲート"),
    ("年間成績", "予算対実績・月別P/L・対計画の差額。2026年売上の行だけ手入力", "毎月1日"),
    ("【2027年の新しい取り組み】", None, None),
    ("ネット流入_週次", "SNS・ブログ・GBP・予約フォーム・受注・広告費・CPA。CPA9,500円超は赤", "毎週金曜"),
    ("広告_段管理", "段0→段3。月ごとに予算・実績・CPA・次の段へ上がるかの判定", "月末"),
    ("提携先_パイプライン", "2社→4社。先方名・ステージ・紹介件数・次アクション", "接触のたび"),
    ("協力業者_管理", "3社。契約条件・回した件数・支払額・品質（クレーム・写真提出）", "月末"),
    ("Web予約受信", "予約フォーム／LPからの受信ログ。流入元(?src=)と台帳への転記チェック", "受信したその日"),
    ("【顧客と再販】", None, None),
    ("顧客管理台帳", "ヘッダー15行目・データ16行目から。2027年版は空の器（移行は年末）", "施工の記録後"),
    ("再販リスト", "メニュー別サイクルで案内時期が来た方を抽出する器", "再販の波を出す前"),
    ("分析_件数単価流入", "月別の件数・単価と流入経路別の内訳。すべて自動", "見たいとき"),
    ("分析_流入経路とLTV", "入口ごとのLTVとリピート率。広告CPA上限9,500円の根拠", "広告の判断のとき"),
    ("【運用】", None, None),
    ("見積ルール", "料金表（税込）と割引・紹介のルール。正データは data/prices.json", "見積のとき"),
    ("TODO", "状態・期限・優先度。完了しても行を消さない", "随時"),
    ("勤怠管理", "日付・氏名・時間・現場数。現場人件費（原価）の根拠", "毎日"),
    ("メモ・変更履歴", "このスプレッドシートに手を入れた記録", "手を入れたとき"),
    ("選択肢マスター", "全タブのプルダウンの元データ。並べ替え・行削除をしないこと", "選択肢を足すとき"),
]


def build_toc(wb):
    ws = wb["目次"]
    ws.sheet_properties.tabColor = "1F3864"
    title(ws, "2027年度 売上・顧客情報管理",
          "正式目標は「中立」：年 26,000,000円・649件。いちばん大事な先行指標は ④自社ネット新規（年143件）です。")
    widths(ws, [34, 60, 24])
    header_row(ws, 4, ["タブ", "何のためのタブか", "いつ使うか"])
    r = 5
    existing = set(wb.sheetnames)
    for name, desc, when in TOC:
        if desc is None:
            c = ws.cell(row=r, column=1, value=name)
            c.font = F_SECT
            c.fill = FILL_SECT
            ws.cell(row=r, column=2).fill = FILL_SECT
            ws.cell(row=r, column=3).fill = FILL_SECT
        else:
            link_target = name.split(" 〜 ")[0]
            if link_target in existing:
                c = ws.cell(row=r, column=1,
                            value=f'=HYPERLINK("#\'{link_target}\'!A1","{name}")')
                c.font = Font(size=10, color="0563C1", underline="single")
            else:
                c = ws.cell(row=r, column=1, value=name)
                c.font = F_NORM
            ws.cell(row=r, column=2, value=desc).font = F_NORM
            ws.cell(row=r, column=3, value=when).font = F_NORM
        for col in range(1, 4):
            ws.cell(row=r, column=col).border = BORDER
            ws.cell(row=r, column=col).alignment = Alignment(wrap_text=True, vertical="center")
        r += 1

    ws.cell(row=r + 1, column=1, value="【この表は必ず最新にすること】").font = F_SECT
    for i, t in enumerate([
        "タブを足したり名前を変えたら、この目次も直してください（2026年版は目次が古くて実在タブが載っていませんでした）。",
        "",
        "【2027年の決まり】",
        "・料金は data/prices.json が正（税込）。繁忙期加算 3,300円は5・6・7・12月",
        "・満足度は 98.6%（209名中206名）。「98.8%」は使わない",
        "・対応エリアは東京都・千葉県・神奈川県",
        "・お客様に届くもの（SMS・LINE・メール・電話台本）は、台帳の最新の施工の名義と機械照合してから作る",
        "・お客様が開くページは tools/check-public-page.py を通してから配信する",
        "",
        f"シート数：{len(wb.sheetnames)}タブ　／　生成：tools/build-sheet-2027.py",
    ]):
        ws.cell(row=r + 2 + i, column=1, value=t).font = F_NOTE
    ws.freeze_panes = "A5"
    return ws


# ================================================================ 検算

def verify(path, plan):
    from openpyxl import load_workbook
    wb = load_workbook(path)
    errs, oks = [], []

    names = wb.sheetnames
    oks.append(f"タブ数 = {len(names)}")

    # 1) 年間成績 予算行の合計
    ws = wb["年間成績"]
    vals = [ws.cell(row=18, column=2 + i).value for i in range(12)]
    total = sum(v for v in vals if isinstance(v, (int, float)))
    if total != 26000000:
        errs.append(f"年間成績 予算行の合計が {total}（期待 26,000,000）")
    else:
        oks.append("年間成績 予算行の合計 = 26,000,000 ✓")

    # 2) 件数計画
    kvals = [ws.cell(row=27, column=2 + i).value for i in range(12)]
    kt = sum(v for v in kvals if isinstance(v, (int, float)))
    if kt != 649:
        errs.append(f"年間成績 件数計画の合計が {kt}（期待 649）")
    else:
        oks.append("年間成績 件数計画の合計 = 649 ✓")

    # 3) ④の年間目標
    nvals = [ws.cell(row=29, column=2 + i).value for i in range(12)]
    nt = sum(v for v in nvals if isinstance(v, (int, float)))
    if nt != 143:
        errs.append(f"④自社ネット新規の年間目標が {nt}（期待 143）")
    else:
        oks.append("④自社ネット新規の年間目標 = 143 ✓")

    # 4) 各月タブの目標が計画と一致
    mon = plan["中立"]["月次"]
    for i, m in enumerate(MONTHS):
        w = wb[s_uriage(m)]
        if w["B2"].value != mon[i]["売上"]:
            errs.append(f"{s_uriage(m)} B2={w['B2'].value} 計画={mon[i]['売上']}")
        if w["J2"].value != mon[i]["件数"]:
            errs.append(f"{s_uriage(m)} J2={w['J2'].value} 計画={mon[i]['件数']}")
        if w["P2"].value != NET_NEW_TARGET[i]:
            errs.append(f"{s_uriage(m)} P2={w['P2'].value} ④目標={NET_NEW_TARGET[i]}")
        if vals[i] != mon[i]["売上"]:
            errs.append(f"年間成績 {m}月の予算={vals[i]} 計画={mon[i]['売上']}")
    if not any("B2=" in e or "J2=" in e or "P2=" in e for e in errs):
        oks.append("各月タブの今月目標（売上・件数・④）が計画と一致 ✓")

    # 5) 広告予算の年計
    wa = wb["広告_段管理"]
    ad = sum(wa.cell(row=5 + i, column=3).value for i in range(12))
    if ad != 800000:
        errs.append(f"広告_段管理 年間予算が {ad}（期待 800,000）")
    else:
        oks.append("広告_段管理 年間予算 = 800,000 ✓")

    # 6) 数式が参照するタブが全部存在するか
    import re
    pat = re.compile(r"'([^']+)'!")
    missing = set()
    for ws2 in wb.worksheets:
        for row in ws2.iter_rows():
            for c in row:
                if isinstance(c.value, str) and c.value.startswith("="):
                    for t in pat.findall(c.value):
                        if t not in names:
                            missing.add((ws2.title, t))
    if missing:
        for a, b in sorted(missing):
            errs.append(f"{a} が存在しないタブ '{b}' を参照")
    else:
        oks.append("すべての数式の参照先タブが存在する ✓")

    # 7) Google独自関数が混ざっていないか
    banned = ("QUERY(", "ARRAYFORMULA(", "GOOGLEFINANCE(", "IMPORTRANGE(", "SPARKLINE(", "FILTER(")
    bad = []
    for ws2 in wb.worksheets:
        for row in ws2.iter_rows():
            for c in row:
                if isinstance(c.value, str) and c.value.startswith("="):
                    for b in banned:
                        if b in c.value.upper():
                            bad.append((ws2.title, c.coordinate, b))
    if bad:
        for t in bad[:10]:
            errs.append(f"Google独自関数 {t[2]} が {t[0]}!{t[1]} にある")
    else:
        oks.append("Google独自関数（QUERY/ARRAYFORMULA等）は使っていない ✓")

    # 8) 個人情報らしき実データが無いか（月次タブと台帳のデータ行が空か）
    dirty = []
    for m in MONTHS:
        w = wb[s_uriage(m)]
        for r in range(U_FIRST, U_FIRST + 20):
            for col in range(1, len(U_COLS) + 1):
                if w.cell(row=r, column=col).value not in (None, ""):
                    dirty.append(f"{s_uriage(m)}!{get_column_letter(col)}{r}")
    w = wb["顧客管理台帳"]
    for r in range(16, 36):
        for col in range(1, 6):
            if w.cell(row=r, column=col).value not in (None, ""):
                dirty.append(f"顧客管理台帳!{get_column_letter(col)}{r}")
    if dirty:
        errs.append("データ行に値が入っている: " + ", ".join(dirty[:5]))
    else:
        oks.append("月次タブ・顧客管理台帳のデータ行は空（個人情報なし） ✓")

    # 9) シート名に / が無いか
    for n in names:
        if "/" in n:
            errs.append(f"シート名に / が入っている: {n}")
    if not any("シート名に /" in e for e in errs):
        oks.append("シート名に / は無い ✓")

    return oks, errs


# ================================================================ 再計算テスト

SELFTEST_EXPECT = {
    # 1月にダミー4件＋経費6件を入れたときに、こうなっていないとおかしい、という値
    "'1月_売上顧客'!B4": 3,          # 自社件数
    "'1月_売上顧客'!C4": 1,          # 本舗件数
    "'1月_売上顧客'!D4": 4,          # 合計件数
    "'1月_売上顧客'!E4": 30000,      # 単価
    "'1月_売上顧客'!G4": 25000,      # 本舗単価
    "'1月_売上顧客'!J4": 120000,     # 合計売上
    "'1月_売上顧客'!P4": 2,          # ④自社ネット新規 件数（LP＋HP）
    "'1月_売上顧客'!Q4": 50000,      # ④自社ネット新規 売上
    "'1月_売上顧客'!D2": 120000,
    "'1月_売上顧客'!F2": 120000 - 1440000,
    "'1月_売上顧客'!L2": 4,
    "'1月_売上顧客'!N2": 33,
    "'1月_売上顧客'!R2": 2,
    "'1月_支出成績'!N3": 120000,     # 売上
    "'1月_支出成績'!N4": 2,          # エアコン台数
    "'1月_支出成績'!N5": 1,          # 換気扇台数
    "'1月_支出成績'!N6": 1,          # 浴室台数
    "'1月_支出成績'!N7": 1071,       # 資材費 2*373+176+149
    "'1月_支出成績'!N8": 50700,      # 外注費
    "'1月_支出成績'!N9": 20000,      # 現場人件費
    "'1月_支出成績'!N10": 71771,     # 原価合計
    "'1月_支出成績'!N11": 48229,     # 売上総利益
    "'1月_支出成績'!N13": 641460,    # 経費合計
    "'1月_支出成績'!N14": -70700,    # 原価へ回した分
    "'1月_支出成績'!N15": -22000,    # 個別ロイを引く
    "'1月_支出成績'!N16": 50050,
    "'1月_支出成績'!N17": 9500,      # 25000*0.38
    "'1月_支出成績'!N18": 2000,      # 20000*0.10
    "'1月_支出成績'!N19": 22000,     # 個別ロイ実額
    "'1月_支出成績'!N20": 83550,     # ロイヤリティ合計（個別ロイは1回だけ）
    "'1月_支出成績'!N21": 632310,    # 販売管理費
    "'1月_支出成績'!N22": -584081,   # 営業利益
    "'1月_支出成績'!N24": -622140,   # 経常利益
    "'1月_支出成績'!R4": 5000,       # 科目別 交通費
    "'1月_支出成績'!R5": 43760,      # 科目別 保険料
    "'年間成績'!B18": 1440000,
    "'年間成績'!B20": 120000,
    "'年間成績'!B21": 120000,
    "'年間成績'!B22": 1440000,
    "'年間成績'!B23": -1320000,
    "'年間成績'!B24": -1320000,
    "'年間成績'!B28": 4,
    "'年間成績'!B30": 2,
    "'年間成績'!B32": 2,
    "'年間成績'!B35": 1071,
    "'年間成績'!B36": 50700,
    "'年間成績'!B43": -622140,
    "'年間成績'!B49": NET_NEW_TARGET[0],   # ④の1月目標。NET_NEW_TARGET を変えたら自動で追随する
    "'年間成績'!B50": 2,
    "'年間成績'!B51": load_plan()["中立"]["月次"][0]["経常利益"],   # 1月の計画経常利益。plan2027.py に追随する
    "'年間成績'!N18": 26000000,
    "'年間成績'!N27": 649,
    "'年間成績'!N29": 143,
    "'年間成績'!B4": 26000000,
    "'年間成績'!B5": 120000,
    "'ダッシュボード'!B6": 1440000,
    "'ダッシュボード'!C6": 120000,
    "'ダッシュボード'!D6": -1320000,
    "'ダッシュボード'!B7": 37,
    "'ダッシュボード'!C7": 4,
    "'ダッシュボード'!B8": NET_NEW_TARGET[0],
    "'ダッシュボード'!C8": 2,
    "'ダッシュボード'!B10": load_plan()["中立"]["月次"][0]["経常利益"],   # 1月の計画経常利益。plan2027.py に追随する
    "'ダッシュボード'!C10": -622140,
    "'ダッシュボード'!B13": 1440000,
    "'ダッシュボード'!C13": 120000,
    "'ダッシュボード'!B14": NET_NEW_TARGET[0],
    "'ダッシュボード'!C14": 2,
    "'ダッシュボード'!B15": load_plan()["中立"]["月次"][0]["経常利益"],   # 1月の計画経常利益。plan2027.py に追随する
    "'分析_件数単価流入'!B5": 4,
    "'分析_件数単価流入'!B6": 120000,
    "'分析_件数単価流入'!B12": 2,      # ④自社ネット新規 件数
    "'分析_件数単価流入'!B13": 50000,  # ④自社ネット新規 売上
}


try:                                        # pycel のプラグインとして読ませる用
    from pycel.lib.function_helpers import excel_helper as _xl_helper
    from pycel.excelutil import flatten as _xl_flatten

    @_xl_helper()
    def counta(*args):
        """pycel は COUNTA を実装していないので補う。"""
        return sum(1 for v in _xl_flatten(args) if v is not None and v != "")
except ImportError:
    pass


def selftest(path):
    """ダミーデータを入れた複製を実際に再計算して、数式が生きているか確かめる。

    pycel が入っているときだけ動く（pip install pycel）。無ければ黙って飛ばす。
    """
    try:
        from pycel import ExcelCompiler
    except ImportError:
        print("\n--- 再計算テスト ---\n  skip（pycel が入っていません: pip install pycel）")
        return True

    import shutil
    import tempfile
    from openpyxl import load_workbook as _lw

    tmp = os.path.join(tempfile.mkdtemp(), "selftest.xlsx")
    shutil.copy(path, tmp)
    wb = _lw(tmp)
    u = wb[s_uriage(1)]
    rows = [
        (1, "One Hitter", date(2027, 1, 5), "LP", "lp_ga", None, None, None, None,
         20000, "エアコン(ノーマル)", "和真"),
        (2, "One Hitter", date(2027, 1, 6), "HP", "hp", None, None, None, None,
         30000, "浴室", "和真"),
        (3, "本舗", date(2027, 1, 7), "楽ラクーン", "", None, None, None, None,
         25000, "換気扇", "協力業者A"),
        (4, "One Hitter", date(2027, 1, 8), "リピート", "", None, None, None, None,
         45000, "エアコン(ロボ)", "和真"),
    ]
    for i, r in enumerate(rows):
        for j, v in enumerate(r):
            u.cell(row=U_FIRST + i, column=1 + j, value=v)
    u.cell(row=U_FIRST, column=U_IDX["本舗ロイ区分"], value="10%")
    u.cell(row=U_FIRST + 2, column=U_IDX["本舗ロイ区分"], value="38%")

    e = wb[s_shishutsu(1)]
    exp = [
        (1, date(2027, 1, 10), None, "ガソリン", "交通費", 5000),
        (2, date(2027, 1, 11), None, "賠償保険", "保険料", 43760),
        (3, date(2027, 1, 12), None, "協力業者A 3件", "外注費", 50700),
        (4, date(2027, 1, 13), None, "現場補助", "現場人件費(原価)", 20000),
        (5, date(2027, 1, 25), None, "和真 固定給", "固定給(販管費)", 500000),
        (6, date(2027, 1, 26), None, "toBロイ", "個別ロイ", 22000),
    ]
    for i, r in enumerate(exp):
        for j, v in enumerate(r):
            e.cell(row=E_FIRST + i, column=1 + j, value=v)
    wb.save(tmp)

    ec = ExcelCompiler(tmp, plugins=(__name__,))
    ng = []
    for k, want in SELFTEST_EXPECT.items():
        try:
            got = ec.evaluate(k)
        except Exception as ex:
            ng.append(f"{k} 評価できない（{type(ex).__name__}）")
            continue
        if not (isinstance(got, (int, float)) and abs(got - want) < 0.01):
            ng.append(f"{k} = {got}（期待 {want}）")
    print(f"\n--- 再計算テスト（ダミー4件＋経費6件を入れて実際に計算） ---")
    if ng:
        for x in ng:
            print("  NG  " + x)
    else:
        print(f"  OK  {len(SELFTEST_EXPECT)}セルすべて期待どおり ✓")
    return not ng


# ================================================================ main

def main():
    plan = load_plan()
    prices = load_prices()
    plan_year = plan["中立"]["年計"]
    mon = plan["中立"]["月次"]

    wb = Workbook()
    wb.active.title = "目次"

    build_dashboard_later = None
    build_master(wb)

    # 先に月次タブを作る（他のタブが参照するため）
    for i, m in enumerate(MONTHS):
        build_uriage(wb, m, mon[i], NET_NEW_TARGET[i])
    for i, m in enumerate(MONTHS):
        build_shishutsu(wb, m, mon[i])

    build_keikaku(wb, plan)
    build_nenkan(wb, plan, plan_year)
    build_netinflow(wb)
    build_ad(wb)
    build_teikei(wb)
    build_gyosha(wb)
    build_yoyaku(wb)
    build_daichou(wb)
    build_saihan(wb)
    build_bunseki_kensuu(wb)
    build_bunseki_ltv(wb)
    build_mitsumori(wb, prices)
    build_todo(wb)
    build_kintai(wb)
    build_memo(wb)
    build_dashboard(wb, plan_year)
    build_toc(wb)

    # タブの並び替え（目次 → ダッシュボード → 月次 → 計画 → 施策 → 顧客 → 運用 → マスター）
    order = ["目次", "ダッシュボード"]
    order += [s_uriage(m) for m in MONTHS]
    order += [s_shishutsu(m) for m in MONTHS]
    order += ["2027年計画", "年間成績",
              "ネット流入_週次", "広告_段管理", "提携先_パイプライン", "協力業者_管理", "Web予約受信",
              "顧客管理台帳", "再販リスト", "分析_件数単価流入", "分析_流入経路とLTV",
              "見積ルール", "TODO", "勤怠管理", "メモ・変更履歴", MASTER_SHEET]
    assert set(order) == set(wb.sheetnames), set(order) ^ set(wb.sheetnames)
    wb._sheets = [wb[n] for n in order]
    wb.active = 0

    os.makedirs(OUT_DIR, exist_ok=True)
    wb.save(OUT_PATH)
    print(f"出力: {OUT_PATH}")
    print(f"タブ数: {len(wb.sheetnames)}")

    oks, errs = verify(OUT_PATH, plan)
    print("\n--- 検算 ---")
    for o in oks:
        print("  OK  " + o)
    for e in errs:
        print("  NG  " + e)
    ok2 = selftest(OUT_PATH)
    if errs or not ok2:
        sys.exit(1)
    print("\n検算：問題なし")


if __name__ == "__main__":
    main()
