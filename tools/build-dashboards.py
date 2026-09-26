#!/usr/bin/env python3
"""2026年シートに「見るだけのタブ」を作る（入力は不要。元のタブから数式で自動集計）。

    python3 tools/build-dashboards.py --web              # WEB集客_ダッシュボード
    python3 tools/build-dashboards.py --fuyu             # 冬季見込み客_ダッシュボード
    python3 tools/build-dashboards.py --getsuji 2026-09  # 月次_2026-09（締めMTG用）
    python3 tools/build-dashboards.py --ga4              # WEB集客のGA4欄だけ更新（値の書き込み）
    python3 tools/build-dashboards.py --all --getsuji 2026-09

## 方針（2026-09-26 オーナー依頼）

- ①WEB集客の進捗と成果が分かる1枚 ②冬季見込み客の全体の動きが分かる1枚
  ③月別シートを手間が最小になる形で作り直す（既存タブは消さない。まず9月分だけ）
- **どのタブも人が入力する場所は無い。** 元データは今までどおり
  `◯月_売上/顧客`（受注フォームが自動で書き込む先）・`◯月_支出/成績`・`広告_日次`・`予約_Web`・
  `冬季見込み客_2026`・`TODO`。ここを数式で読む。
- 例外は2つだけ。WEB集客の「定義」欄（Web経由とみなす流入経路・月の目標）は人が書き換えてよい。
  GA4欄は Sheets から GA4 を読めないので、このスクリプトが値を書き込む（`--ga4`）。
- 同じタブ名があれば中身を消して作り直す（このスクリプトが作ったタブだけが対象。元データのタブには書かない）。
"""

import argparse
import datetime as dt
import json
import pathlib
import re
import sys
import urllib.error
import urllib.request
from urllib.parse import quote

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import sheets_client as sc  # noqa: E402

SID = "1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64"
YEAR = 2026
GA4_PROPERTY = "381320625"
GA4_SCOPE = "https://www.googleapis.com/auth/analytics.readonly"

WEB_TAB = "WEB集客_ダッシュボード"
FUYU_TAB = "冬季見込み客_ダッシュボード"
FUYU_SRC = "冬季見込み客_2026"

# このスクリプトが作ってよいタブ（ここに無い名前は消さない・書かない）
def getsuji_tab(ym: str) -> str:
    return f"月次_{ym}"


def q(tab: str) -> str:
    return "'" + tab.replace("'", "''") + "'"


def uri(tab: str) -> str:
    return q(tab)


def col(n: int) -> str:  # 1 -> A
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def uriage(m: int) -> str:
    return f"{m}月_売上/顧客"


def shishutsu(m: int) -> str:
    return f"{m}月_支出/成績"


# ---------------------------------------------------------------- 書き込みの道具
NAVY = {"red": 0.12, "green": 0.22, "blue": 0.39}
SEC = {"red": 0.85, "green": 0.89, "blue": 0.95}
TH = {"red": 0.95, "green": 0.95, "blue": 0.95}
KPI = {"red": 1.0, "green": 0.98, "blue": 0.90}
DEF = {"red": 1.0, "green": 0.96, "blue": 0.80}
WHITE = {"red": 1, "green": 1, "blue": 1}
GRAY = {"red": 0.4, "green": 0.4, "blue": 0.4}


class Tab:
    def __init__(self, title: str, ncols: int):
        self.title = title
        self.ncols = ncols
        self.cells = {}
        self.fmts = []   # (r1, c1, r2, c2, kind)
        self.widths = {}
        self.r = 1

    def put(self, r, c, v):
        self.cells[(r, c)] = v

    def row(self, r, values, c0=1):
        for i, v in enumerate(values):
            if v is not None and v != "":
                self.put(r, c0 + i, v)

    def fmt(self, r1, c1, r2, c2, kind):
        self.fmts.append((r1, c1, r2, c2, kind))

    # よく使う形
    def title_band(self, text, note):
        self.put(1, 1, text)
        self.fmt(1, 1, 1, self.ncols, "title")
        self.put(2, 1, note)
        self.fmt(2, 1, 2, self.ncols, "note")
        self.put(3, 1, '="最終再計算：" & TEXT(NOW(), "yyyy/mm/dd hh:mm") & "（数式は開くたびに再計算）"')
        self.fmt(3, 1, 3, self.ncols, "note")
        self.r = 5

    def section(self, text):
        self.put(self.r, 1, text)
        self.fmt(self.r, 1, self.r, self.ncols, "section")
        self.r += 1

    def header(self, values):
        self.row(self.r, values)
        self.fmt(self.r, 1, self.r, len(values), "th")
        self.r += 1

    def note(self, text):
        self.put(self.r, 1, text)
        self.fmt(self.r, 1, self.r, self.ncols, "note")
        self.r += 1

    def grid(self):
        nrows = max(r for r, _ in self.cells) if self.cells else 1
        out = []
        for r in range(1, nrows + 1):
            out.append([self.cells.get((r, c), "") for c in range(1, self.ncols + 1)])
        return out


def fmt_request(sheet_id, r1, c1, r2, c2, kind):
    rng = {"sheetId": sheet_id, "startRowIndex": r1 - 1, "endRowIndex": r2,
           "startColumnIndex": c1 - 1, "endColumnIndex": c2}
    f = {}
    if kind == "title":
        f = {"backgroundColor": NAVY, "textFormat": {"bold": True, "fontSize": 14, "foregroundColor": WHITE},
             "verticalAlignment": "MIDDLE"}
    elif kind == "section":
        f = {"backgroundColor": SEC, "textFormat": {"bold": True, "fontSize": 11}}
    elif kind == "th":
        f = {"backgroundColor": TH, "textFormat": {"bold": True}, "wrapStrategy": "WRAP",
             "verticalAlignment": "MIDDLE"}
    elif kind == "note":
        f = {"textFormat": {"italic": True, "foregroundColor": GRAY, "fontSize": 9}}
    elif kind == "kpi":
        f = {"backgroundColor": KPI, "textFormat": {"bold": True, "fontSize": 13}, "horizontalAlignment": "CENTER"}
    elif kind == "def":
        f = {"backgroundColor": DEF}
    elif kind == "bold":
        f = {"textFormat": {"bold": True}}
    elif kind == "total":
        f = {"textFormat": {"bold": True}, "borders": {"top": {"style": "SOLID"}}}
    elif kind == "yen":
        f = {"numberFormat": {"type": "CURRENCY", "pattern": '"¥"#,##0;-"¥"#,##0'}}
    elif kind == "pct":
        f = {"numberFormat": {"type": "PERCENT", "pattern": "0.0%"}}
    elif kind == "int":
        f = {"numberFormat": {"type": "NUMBER", "pattern": "#,##0"}}
    elif kind == "date":
        f = {"numberFormat": {"type": "DATE", "pattern": "m/d"}}
    elif kind == "wrap":
        f = {"wrapStrategy": "WRAP", "verticalAlignment": "TOP"}
    fields = "userEnteredFormat(" + ",".join(
        {"backgroundColor": "backgroundColor", "textFormat": "textFormat", "numberFormat": "numberFormat",
         "wrapStrategy": "wrapStrategy", "verticalAlignment": "verticalAlignment",
         "horizontalAlignment": "horizontalAlignment", "borders": "borders"}[k] for k in f) + ")"
    return {"repeatCell": {"range": rng, "cell": {"userEnteredFormat": f}, "fields": fields}}


class Sheet:
    def __init__(self):
        self.tok = sc.access_token(sc.load_credentials())
        self.refresh()

    def refresh(self):
        m = sc.call(self.tok, f"/{SID}", query={"fields": "sheets.properties(sheetId,title,index)"})
        self.tabs = {s["properties"]["title"]: s["properties"] for s in m["sheets"]}

    def get(self, rng, mode="FORMATTED_VALUE"):
        return sc.call(self.tok, f"/{SID}/values/" + quote(rng, safe=""),
                       query={"valueRenderOption": mode}).get("values", [])

    def batch(self, reqs):
        if reqs:
            sc.call(self.tok, f"/{SID}:batchUpdate", method="POST", payload={"requests": reqs})

    def prepare(self, title, index=None, rows=400, cols=16):
        """タブを用意する。あれば中身と書式を消す。無ければ作る。"""
        if title in self.tabs:
            sid = self.tabs[title]["sheetId"]
            self.batch([
                {"unmergeCells": {"range": {"sheetId": sid}}},
                {"updateCells": {"range": {"sheetId": sid}, "fields": "userEnteredValue,userEnteredFormat"}},
                {"updateSheetProperties": {"properties": {"sheetId": sid, "gridProperties": {
                    "rowCount": rows, "columnCount": cols, "frozenRowCount": 0}},
                    "fields": "gridProperties(rowCount,columnCount,frozenRowCount)"}},
            ])
        else:
            props = {"title": title, "gridProperties": {"rowCount": rows, "columnCount": cols}}
            if index is not None:
                props["index"] = index
            self.batch([{"addSheet": {"properties": props}}])
            self.refresh()
            sid = self.tabs[title]["sheetId"]
        return sid

    def write(self, tab: Tab, index=None, freeze=0):
        grid = tab.grid()
        sid = self.prepare(tab.title, index=index, rows=max(len(grid) + 20, 100), cols=tab.ncols)
        sc.call(self.tok, f"/{SID}/values/" + quote(f"{q(tab.title)}!A1", safe=""), method="PUT",
                payload={"values": grid}, query={"valueInputOption": "USER_ENTERED"})
        reqs = [fmt_request(sid, *f) for f in tab.fmts]
        for c, w in tab.widths.items():
            reqs.append({"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS",
                         "startIndex": c - 1, "endIndex": c}, "properties": {"pixelSize": w}, "fields": "pixelSize"}})
        reqs.append({"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "ROWS",
                     "startIndex": 0, "endIndex": 1}, "properties": {"pixelSize": 36}, "fields": "pixelSize"}})
        if freeze:
            reqs.append({"updateSheetProperties": {"properties": {"sheetId": sid, "gridProperties": {
                "frozenRowCount": freeze}}, "fields": "gridProperties.frozenRowCount"}})
        self.batch(reqs)
        return sid


def check_errors(sh: Sheet, title: str):
    vals = sh.get(f"{q(title)}!A1:Z400")
    bad = []
    for i, row in enumerate(vals, 1):
        for j, v in enumerate(row, 1):
            if isinstance(v, str) and re.match(r"^#(REF|VALUE|N/A|ERROR|NAME|DIV/0|NUM)", v):
                bad.append(f"{col(j)}{i}:{v}")
    print(f"  {title}: エラーセル {len(bad)} 件", ("→ " + ", ".join(bad[:20])) if bad else "")
    return bad


# ---------------------------------------------------------------- ① WEB集客
WEB_DEF = ["HP", "LP(アフィリエイト)", "地図検索", "Google口コミ", "GBP", "広告", "予約ページ", "Web"]
DIG_DEF = ["SMS", "LINE", "LINE/SMS再販"]
TARGETS = {11: 10, 12: 25}
WEB_DEF_ROW0 = 140   # 定義欄の見出し行。月次タブからも参照する
WEB_NDEF = 12
WEB_DEF_RANGE = f"{q(WEB_TAB)}!$A${WEB_DEF_ROW0 + 2}:$A${WEB_DEF_ROW0 + 1 + WEB_NDEF}"  # docs/cmo-plan.md「60日（〜11月上旬）月10件」「120日（〜年末）月25件」


def build_web(sh: Sheet):
    t = Tab(WEB_TAB, 14)
    t.widths = {1: 150, 2: 90, 3: 95, 4: 110, 5: 95, 6: 85, 7: 95, 8: 110, 9: 100, 10: 80, 11: 80, 12: 110, 13: 95, 14: 90}
    t.title_band(
        "WEB集客ダッシュボード　自社案件のネット経由受注（CMOのミッション）",
        "入力不要。◯月_売上/顧客（D列 流入経路）・広告_日次・予約_Web・TODO を数式で集計。"
        "数え方は一番下の「定義」欄で変えられる（黄色のセルだけ書き換えてよい）。GA4欄は CMO が毎日書き込む。")

    # 定義欄の位置を先に決める（数式から参照するため）
    DEF_ROW0 = WEB_DEF_ROW0
    ndef = WEB_NDEF
    WEB = f"$A${DEF_ROW0 + 2}:$A${DEF_ROW0 + 1 + ndef}"
    DIG = f"$B${DEF_ROW0 + 2}:$B${DEF_ROW0 + 1 + ndef}"

    # --- 今月
    t.section('="■ 今月（" & MONTH(TODAY()) & "月）"')
    t.header(["Web経由受注（件）", "目標（件）", "達成率", "Web経由売上", "自社受注に占める割合",
              "広告費", "クリック", "広告CV", "獲得単価", "予約ページ申込", "SMS・LINE経由（件）"])
    kpi_row = t.r
    t.r += 1
    t.note("※ 獲得単価＝広告費 ÷ Web経由受注。広告CVは Google広告の管理画面の数字（電話・フォーム）で、受注とは別。")
    t.r += 1

    # --- 月別推移
    t.section(f"■ 月別推移（{YEAR}年・自社＝売上種類 One Hitter のみ）")
    t.header(["月", "目標（件）", "Web経由（件）", "Web経由売上", "自社受注（件）", "Web比率",
              "SMS・LINE経由（件）", "SMS・LINE経由売上", "広告費", "クリック", "広告CV",
              "獲得単価（広告費÷Web件数）", "予約ページ申込"])
    m0 = t.r
    for m in range(1, 13):
        r = m0 + m - 1
        T = uriage(m)
        B, D, I = (f"{q(T)}!${x}$4:${x}$504" for x in "BDI")
        key = f"{YEAR}-{m:02d}"
        ad = lambda c: f"=SUMPRODUCT((TEXT('広告_日次'!$B$2:$B$3000,\"yyyy-mm\")=\"{key}\")*1,'広告_日次'!${c}$2:${c}$3000)"
        t.row(r, [
            f"{m}月",
            TARGETS.get(m, ""),
            f'=SUMPRODUCT(({B}="One Hitter")*(COUNTIF({WEB},{D})>0)*({D}<>""))',
            f'=SUMPRODUCT(({B}="One Hitter")*(COUNTIF({WEB},{D})>0)*({D}<>""),{I})',
            f'=COUNTIF({B},"One Hitter")',
            f'=IF(E{r}=0,"",C{r}/E{r})',
            f'=SUMPRODUCT(({B}="One Hitter")*(COUNTIF({DIG},{D})>0)*({D}<>""))',
            f'=SUMPRODUCT(({B}="One Hitter")*(COUNTIF({DIG},{D})>0)*({D}<>""),{I})',
            ad("E"), ad("G"), ad("J"),
            f'=IF(I{r}=0,"",IF(C{r}=0,"受注0",I{r}/C{r}))',
            f"=SUMPRODUCT((LEFT(SUBSTITUTE(TEXT('予約_Web'!$A$2:$A$2000,\"yyyy-mm\"),\"/\",\"-\"),7)=\"{key}\")*('予約_Web'!$B$2:$B$2000<>\"テスト\")*('予約_Web'!$A$2:$A$2000<>\"\"))",
        ])
    tot = m0 + 12
    t.row(tot, ["合計", f"=SUM(B{m0}:B{tot-1})", f"=SUM(C{m0}:C{tot-1})", f"=SUM(D{m0}:D{tot-1})",
                f"=SUM(E{m0}:E{tot-1})", f'=IF(E{tot}=0,"",C{tot}/E{tot})', f"=SUM(G{m0}:G{tot-1})",
                f"=SUM(H{m0}:H{tot-1})", f"=SUM(I{m0}:I{tot-1})", f"=SUM(J{m0}:J{tot-1})", f"=SUM(K{m0}:K{tot-1})",
                f'=IF(I{tot}=0,"",IF(C{tot}=0,"受注0",I{tot}/C{tot}))', f"=SUM(M{m0}:M{tot-1})"])
    t.fmt(tot, 1, tot, 13, "total")
    t.fmt(m0, 2, tot, 2, "def")
    for c in (4, 8, 9, 12):
        t.fmt(m0, c, tot, c, "yen")
    t.fmt(m0, 6, tot, 6, "pct")
    t.r = tot + 1
    t.note("※ 目標（黄色）は docs/cmo-plan.md の「60日（〜11月上旬）ネット経由 月10件」「120日（〜年末）月25件」。書き換えてよい。")
    t.r += 1

    # 今月の行（月別推移から拾う）
    idx = "MONTH(TODAY())"
    rng = lambda c: f"INDEX(${c}${m0}:${c}${m0+11},{idx})"
    t.row(kpi_row, [
        f"={rng('C')}", f'=IF({rng("B")}="","（未設定）",{rng("B")})',
        f'=IFERROR({rng("C")}/{rng("B")},"")', f"={rng('D')}", f'=IFERROR({rng("F")},"")',
        f"={rng('I')}", f"={rng('J')}", f"={rng('K')}", f'=IFERROR({rng("L")},"")', f"={rng('M')}",
        f"={rng('G')}",
    ])
    t.fmt(kpi_row, 1, kpi_row, 11, "kpi")
    t.fmt(kpi_row, 3, kpi_row, 3, "pct")
    t.fmt(kpi_row, 5, kpi_row, 5, "pct")
    t.fmt(kpi_row, 4, kpi_row, 4, "yen")
    t.fmt(kpi_row, 6, kpi_row, 6, "yen")
    t.fmt(kpi_row, 9, kpi_row, 9, "yen")

    # --- 経路別
    t.section(f"■ 経路別（{YEAR}年累計・自社）")
    t.header(["流入経路", "区分", "件数（累計）", "売上（累計）", "今月の件数", "今月の売上"])
    e0 = t.r
    for k in range(ndef * 2):
        r = e0 + k
        src = f"$A${DEF_ROW0 + 2 + k}" if k < ndef else f"$B${DEF_ROW0 + 2 + k - ndef}"
        kubun = "Web経由" if k < ndef else "SMS・LINE"
        cnt = "+".join(f'COUNTIFS({q(uriage(m))}!$B$4:$B$504,"One Hitter",{q(uriage(m))}!$D$4:$D$504,$A{r})' for m in range(1, 13))
        amt = "+".join(f'SUMIFS({q(uriage(m))}!$I$4:$I$504,{q(uriage(m))}!$B$4:$B$504,"One Hitter",{q(uriage(m))}!$D$4:$D$504,$A{r})' for m in range(1, 13))
        cur_cnt = f'CHOOSE(MONTH(TODAY()),' + ",".join(
            f'COUNTIFS({q(uriage(m))}!$B$4:$B$504,"One Hitter",{q(uriage(m))}!$D$4:$D$504,$A{r})' for m in range(1, 13)) + ")"
        cur_amt = f'CHOOSE(MONTH(TODAY()),' + ",".join(
            f'SUMIFS({q(uriage(m))}!$I$4:$I$504,{q(uriage(m))}!$B$4:$B$504,"One Hitter",{q(uriage(m))}!$D$4:$D$504,$A{r})' for m in range(1, 13)) + ")"
        t.row(r, [f'=IF({src}="","",{src})', f'=IF($A{r}="","","{kubun}")',
                  f'=IF($A{r}="","",{cnt})', f'=IF($A{r}="","",{amt})',
                  f'=IF($A{r}="","",{cur_cnt})', f'=IF($A{r}="","",{cur_amt})'])
    t.fmt(e0, 4, e0 + ndef * 2 - 1, 4, "yen")
    t.fmt(e0, 6, e0 + ndef * 2 - 1, 6, "yen")
    t.r = e0 + ndef * 2
    t.note("※ 定義欄に経路を足すと、ここにも行が出る。空の行は何も表示しない。")
    t.r += 1

    # --- GA4
    ga4_row = t.r
    t.section("■ サイトの動き（GA4・月別。値は CMO が書き込む）")
    t.header(["月", "セッション計", "自然検索", "有料検索", "GBP経由（内数）", "SNS", "直接", "参照",
              "電話タップ", "LINEタップ", "フォーム送信・予約", "予約ボタン", "取得日"])
    g0 = t.r
    for m in range(1, 13):
        t.put(g0 + m - 1, 1, f"{m}月")
    t.r = g0 + 12
    t.note("※ GA4 の one-hitter.jp プロパティ（LP群も同じ）。/contact/ 完了ページのスパム（form_complete）は数えない。"
           "GBP経由は ?src=gbp で着地したセッション（自然検索・直接などの内数）。")
    t.r += 1

    # --- 施策
    t.section("■ 施策の進み（TODO タブの未完了。完了・対象外を除く。期限の早い順）")
    t.header(["ID", "状態", "期限", "担当", "やること"])
    t.put(t.r, 1, "=IFERROR(SORT(FILTER({TODO!A7:A200,TODO!B7:B200,TODO!C7:C200,TODO!D7:D200,TODO!E7:E200},"
                  "TODO!A7:A200<>\"\",TODO!B7:B200<>\"完了\",TODO!B7:B200<>\"対象外\"),3,TRUE),\"未完了はありません\")")
    t.fmt(t.r, 3, t.r + 40, 3, "date")
    t.fmt(t.r, 5, t.r + 40, 5, "wrap")
    t.widths[5] = 95
    assert t.r + 42 < DEF_ROW0, "施策欄が定義欄にかぶる"
    t.r = DEF_ROW0

    # --- 定義
    t.section("■ 定義（黄色のセルは書き換えてよい。ここを変えると上の数字の数え方が全部変わる）")
    t.header(["Web経由とみなす流入経路", "SMS・LINE経由とみなす流入経路"])
    for k in range(ndef):
        r = DEF_ROW0 + 2 + k
        if k < len(WEB_DEF):
            t.put(r, 1, WEB_DEF[k])
        if k < len(DIG_DEF):
            t.put(r, 2, DIG_DEF[k])
    t.fmt(DEF_ROW0 + 2, 1, DEF_ROW0 + 1 + ndef, 2, "def")
    t.r = DEF_ROW0 + 2 + ndef
    t.note("※ 値は ◯月_売上/顧客 D列（流入経路）の選択肢と同じ文字で書く。「GBP」「広告」「予約ページ」は"
           "経営企画室に選択肢の追加を依頼中（20260925-01-planning）。追加されれば自動で数えはじめる。")
    t.note("※ 自社（One Hitter）の行だけを数える。SMS・LINE は既存のお客様への再販なので Web経由とは分けて表示。")

    sid = sh.write(t, index=1, freeze=0)
    json.dump({"ga4_first_row": g0}, open(ROOT / "data" / "dashboard-web-layout.json", "w"))
    return sid, g0


# ---------------------------------------------------------------- GA4 の値
def ga4_report(tok, body):
    req = urllib.request.Request(f"https://analyticsdata.googleapis.com/v1beta/properties/{GA4_PROPERTY}:runReport",
                                 data=json.dumps(body).encode(), method="POST")
    req.add_header("Authorization", "Bearer " + tok)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def write_ga4(sh: Sheet, g0=None):
    if g0 is None:
        g0 = json.load(open(ROOT / "data" / "dashboard-web-layout.json"))["ga4_first_row"]
    tok = sc.access_token(sc.load_credentials(), scope=GA4_SCOPE)
    today = dt.date.today()
    dr = [{"startDate": f"{YEAR}-01-01", "endDate": today.isoformat()}]
    data = {m: {} for m in range(1, 13)}

    ch = ga4_report(tok, {"dateRanges": dr, "dimensions": [{"name": "yearMonth"}, {"name": "sessionDefaultChannelGroup"}],
                          "metrics": [{"name": "sessions"}], "limit": 1000})
    for row in ch.get("rows", []):
        ym, g = row["dimensionValues"][0]["value"], row["dimensionValues"][1]["value"]
        m = int(ym[4:])
        v = int(row["metricValues"][0]["value"])
        d = data[m]
        d["計"] = d.get("計", 0) + v
        key = {"Organic Search": "自然検索", "Paid Search": "有料検索", "Organic Social": "SNS", "Paid Social": "SNS",
               "Direct": "直接", "Referral": "参照"}.get(g)
        if key:
            d[key] = d.get(key, 0) + v

    gbp = ga4_report(tok, {"dateRanges": dr, "dimensions": [{"name": "yearMonth"}],
                           "metrics": [{"name": "sessions"}],
                           "dimensionFilter": {"filter": {"fieldName": "landingPagePlusQueryString",
                                                          "stringFilter": {"matchType": "CONTAINS", "value": "src=gbp"}}}})
    for row in gbp.get("rows", []):
        data[int(row["dimensionValues"][0]["value"][4:])]["GBP"] = int(row["metricValues"][0]["value"])

    names = ["phone_click", "teltap", "line_click", "generate_lead", "form_submit", "booking_start"]
    ev = ga4_report(tok, {"dateRanges": dr, "dimensions": [{"name": "yearMonth"}, {"name": "eventName"}],
                          "metrics": [{"name": "eventCount"}],
                          "dimensionFilter": {"filter": {"fieldName": "eventName",
                                                         "inListFilter": {"values": names}}}})
    for row in ev.get("rows", []):
        m = int(row["dimensionValues"][0]["value"][4:])
        n = row["dimensionValues"][1]["value"]
        v = int(row["metricValues"][0]["value"])
        k = {"phone_click": "電話", "teltap": "電話", "line_click": "LINE", "generate_lead": "フォーム",
             "form_submit": "フォーム", "booking_start": "予約ボタン"}[n]
        data[m][k] = data[m].get(k, 0) + v

    rows = []
    for m in range(1, 13):
        d = data[m]
        if m > today.month:
            rows.append([""] * 12)
            continue
        rows.append([d.get("計", 0), d.get("自然検索", 0), d.get("有料検索", 0), d.get("GBP", 0), d.get("SNS", 0),
                     d.get("直接", 0), d.get("参照", 0), d.get("電話", 0), d.get("LINE", 0), d.get("フォーム", 0),
                     d.get("予約ボタン", 0), today.strftime("%m/%d") + (" 途中" if m == today.month else "")])
    sc.call(sh.tok, f"/{SID}/values/" + quote(f"{q(WEB_TAB)}!B{g0}:M{g0 + 11}", safe=""), method="PUT",
            payload={"values": rows}, query={"valueInputOption": "RAW"})
    print(f"  GA4 を書き込みました（{WEB_TAB} B{g0}:M{g0 + 11}）")


# ---------------------------------------------------------------- ② 冬季見込み客
def build_fuyu(sh: Sheet):
    t = Tab(FUYU_TAB, 9)
    t.widths = {1: 230, 2: 150, 3: 95, 4: 95, 5: 95, 6: 95, 7: 110, 8: 110, 9: 200}
    t.title_band(
        "冬季見込み客ダッシュボード　2026年 秋冬の既存客への案内（SMS）",
        f"入力不要。{FUYU_SRC} と 9〜12月_売上/顧客 を数式で集計。送信の記録は今までどおり {FUYU_SRC} の E列（送信済み）で付ける。")
    S = q(FUYU_SRC)
    A, B, C, E, G, H, I, J, K, M, Z, AA = (f"{S}!${x}$6:${x}$1035" for x in
                                          ["A", "B", "C", "E", "G", "H", "I", "J", "K", "M", "Z", "AA"])
    SENT = f'(({E}="送信済み")+({E}="返信あり"))'
    UNSENT = f'(({I}="送信可")*({E}=""))'
    OTHER = f'(({B}<>"")*(1-{SENT})*(1-{UNSENT}))'
    L = f'REGEXREPLACE(TO_TEXT({C}),"^0+|[^0-9]","")'
    NM = lambda rng: f'REGEXREPLACE(TO_TEXT({rng}),"[\\s　]|様|さま|さん","")'
    LN = NM(B)
    mons = [9, 10, 11, 12]
    SALES_TEL = "REGEXREPLACE(TO_TEXT({" + ";".join(f"{q(uriage(m))}!$F$4:$F$504" for m in mons) + '}),"^0+|[^0-9]","")'
    SALES_N = NM("{" + ";".join(f"{q(uriage(m))}!$E$4:$E$504" for m in mons) + "}")
    SALES_D = "{" + ";".join(f"{q(uriage(m))}!$C$4:$C$504" for m in mons) + "}"
    SALES_I = "{" + ";".join(f"{q(uriage(m))}!$I$4:$I$504" for m in mons) + "}"
    START = "DATE(2026,9,9)"

    def matched(group):
        """電話番号（先頭の0と記号を除く）か、氏名（空白・様を除く）のどちらかで一致した売上行。"""
        return (f"((ISNUMBER(MATCH({SALES_TEL},FILTER({L},{group}),0))*({SALES_TEL}<>\"\"))+"
                f"(ISNUMBER(MATCH({SALES_N},FILTER({LN},{group}),0))*({SALES_N}<>\"\")))>0,{SALES_D}>={START}")

    def f_people(group):
        return f'=IFERROR(ARRAYFORMULA(ROWS(UNIQUE(FILTER({SALES_N},{matched(group)})))),0)'

    def f_rows(group):
        return f'=IFERROR(ARRAYFORMULA(ROWS(FILTER({SALES_N},{matched(group)}))),0)'

    def f_amt(group):
        return f'=IFERROR(ARRAYFORMULA(SUM(FILTER({SALES_I},{matched(group)}))),0)'

    # --- 全体
    t.section("■ 全体の進み")
    t.header(["段階", "人数", "率", "率の分母"])
    r0 = t.r
    stages = [
        ("リスト掲載", f'=COUNTA({B})', "", ""),
        ("　送信可（名乗り照合・SMS可）", f'=COUNTIF({I},"送信可")', f"=IFERROR(B{r0+1}/B{r0},\"\")", "掲載"),
        ("　送った（送信済み＋返信あり）", f'=COUNTIF({E},"送信済み")+COUNTIF({E},"返信あり")', f"=IFERROR(B{r0+2}/B{r0+1},\"\")", "送信可"),
        ("　　返信あり", f'=COUNTIF({E},"返信あり")', f"=IFERROR(B{r0+3}/B{r0+2},\"\")", "送った"),
        ("　　　うち予約", f'=COUNTIF({AA},"予約")', f"=IFERROR(B{r0+4}/B{r0+2},\"\")", "送った"),
        ("　　不通・エラー", f'=COUNTIF({E},"不通・エラー")', f"=IFERROR(B{r0+5}/B{r0+2},\"\")", "送った"),
        ("　対象外にした", f'=COUNTIF({E},"対象外")', "", ""),
        ("　まだ送っていない（送信可）", f'=COUNTIFS({I},"送信可",{E},"")', f"=IFERROR(B{r0+7}/B{r0+1},\"\")", "送信可"),
        ("　　うち 目安日を過ぎている", f'=ARRAYFORMULA(SUMPRODUCT(({I}="送信可")*({E}="")*(IF(ISNUMBER({H}),{H},99999)<TODAY())))', "", ""),
        ("　　うち KDDI一括で送る予定", f'=COUNTIFS({I},"送信可",{E},"",{H},"KDDI一括")', "", ""),
        ("　　うち 目安日が空", f'=COUNTIFS({I},"送信可",{E},"",{H},"")', "", ""),
    ]
    for k, (a, b, c, d) in enumerate(stages):
        t.row(r0 + k, [a, b, c, d])
    t.fmt(r0, 3, r0 + len(stages) - 1, 3, "pct")
    t.fmt(r0 + 2, 1, r0 + 2, 3, "bold")
    t.r = r0 + len(stages) + 1

    # --- 受注
    t.section("■ 受注につながったか（9/9 以降の施工を、電話番号か氏名で突き合わせ。9〜12月_売上/顧客）")
    t.header(["グループ", "人数", "施工した人", "施工率", "施工件数", "売上"])
    r1 = t.r
    for k, (name, grp) in enumerate([("送った人", SENT), ("送信可だが未送信（比較用）", UNSENT)]):
        r = r1 + k
        t.row(r, [name, f"=ARRAYFORMULA(SUMPRODUCT({grp}))", f_people(grp), f'=IFERROR(C{r}/B{r},"")',
                  f_rows(grp), f_amt(grp)])
    tr = r1 + 1
    t.row(tr + 1, ["差（送った人 − 未送信）", "", "", f'=IFERROR(D{r1}-D{tr},"")'])
    t.fmt(tr + 1, 1, tr + 1, 4, "total")
    t.fmt(r1, 4, tr + 1, 4, "pct")
    t.fmt(r1, 6, tr, 6, "yen")
    t.r = tr + 2
    t.note("※ 効果は「送った人」と「送信可だが未送信」の施工率の差で読む（どちらも送ってよい人なので比べられる）。")
    t.note("※ 送らない人（除外・SMS不可など）は載せない。すでに次回の予約が入っていて除外した人が多く、施工率が高く出て比較を誤らせるため。")
    t.r += 1

    # --- 系統別
    t.section("■ 名義別（M列 送信系統）")
    t.header(["名義", "掲載", "送信可", "送った", "返信あり", "未送信（送信可）", "送った人の施工（人）", "送った人の売上"])
    r2 = t.r
    for k, kei in enumerate(["自社", "本舗"]):
        r = r2 + k
        g = f'({SENT}*({M}="{kei}"))'
        t.row(r, [kei, f'=COUNTIF({M},"{kei}")', f'=COUNTIFS({M},"{kei}",{I},"送信可")',
                  f'=COUNTIFS({M},"{kei}",{E},"送信済み")+COUNTIFS({M},"{kei}",{E},"返信あり")',
                  f'=COUNTIFS({M},"{kei}",{E},"返信あり")', f'=COUNTIFS({M},"{kei}",{I},"送信可",{E},"")',
                  f_people(g), f_amt(g)])
    t.fmt(r2, 8, r2 + 1, 8, "yen")
    t.r = r2 + 3

    # --- 優先度別
    t.section("■ 優先度別（A列）")
    t.header(["優先", "セグメント", "掲載", "送信可", "送った", "返信あり", "未送信（送信可）", "送った人の施工（人）"])
    r3 = t.r
    for k, p in enumerate(range(1, 11)):
        r = r3 + k
        pa = f'(TO_TEXT({A})="{p}")'
        g = f"({SENT}*{pa})"
        t.row(r, [p, f'=IFERROR(ARRAYFORMULA(INDEX(FILTER({K},{pa}),1)),"")',
                  f"=ARRAYFORMULA(SUMPRODUCT({pa}*({B}<>\"\")))",
                  f'=ARRAYFORMULA(SUMPRODUCT({pa}*({I}="送信可")))',
                  f"=ARRAYFORMULA(SUMPRODUCT({pa}*{SENT}))",
                  f'=ARRAYFORMULA(SUMPRODUCT({pa}*({E}="返信あり")))',
                  f"=ARRAYFORMULA(SUMPRODUCT({pa}*{UNSENT}))",
                  f_people(g)])
    t.r = r3 + 11

    # --- 目安日ごと
    t.section("■ 目安日（H列）ごとの消化")
    t.header(["目安", "予定", "送った", "返信あり", "対象外・不通", "未送信（送信可）"])
    r4 = t.r
    U = f"$A${r4}:$A${r4 + 25}"
    UQ = f'UNIQUE(FILTER({H},{H}<>""))'
    t.put(r4, 1, f'=IFERROR(SORT({UQ},ARRAYFORMULA(IF(ISNUMBER({UQ}),{UQ},99999)),TRUE),"")')
    t.fmt(r4, 1, r4 + 25, 1, "date")
    t.put(r4, 2, f'=ARRAYFORMULA(IF({U}="","",COUNTIF({H},{U})))')
    t.put(r4, 3, f'=ARRAYFORMULA(IF({U}="","",COUNTIFS({H},{U},{E},"送信済み")+COUNTIFS({H},{U},{E},"返信あり")))')
    t.put(r4, 4, f'=ARRAYFORMULA(IF({U}="","",COUNTIFS({H},{U},{E},"返信あり")))')
    t.put(r4, 5, f'=ARRAYFORMULA(IF({U}="","",COUNTIFS({H},{U},{E},"対象外")+COUNTIFS({H},{U},{E},"不通・エラー")))')
    t.put(r4, 6, f'=ARRAYFORMULA(IF({U}="","",COUNTIFS({H},{U},{I},"送信可",{E},"")))')
    t.r = r4 + 26

    # --- 送らない理由
    t.section("■ 送らない理由（J列）")
    JR = f'ARRAYFORMULA(IFERROR(REGEXREPLACE(REGEXEXTRACT(TO_TEXT({J}),"^[^／（(]*"),"\\s*20\\d\\d-\\d\\d-\\d\\d.*$",""),""))'
    t.put(t.r, 1, f"=QUERY({{{JR}}},\"select Col1, count(Col1) where Col1 <> '' group by Col1 order by count(Col1) desc label Col1 '理由（最初の一文）', count(Col1) '人数'\",0)")
    t.fmt(t.r, 1, t.r, 2, "th")
    t.fmt(t.r, 1, t.r + 30, 1, "wrap")
    t.r += 32

    # --- 返信
    t.section("■ 返信の中身（E列＝返信あり）")
    t.header(["顧客名", "名義", "返信メモ", "分類", "返信内容（本文）"])
    t.put(t.r, 1, f'=IFERROR(FILTER({{{B},{M},{G},{AA},{Z}}},{E}="返信あり"),"まだありません")')
    t.fmt(t.r, 1, t.r + 30, 5, "wrap")
    t.widths[3] = 200
    t.widths[5] = 260
    t.r += 32

    return sh.write(t, index=2)


# ---------------------------------------------------------------- ③ 月次
def find_label(vals, text, exact=True, only_col=None, min_row=50):
    """支出/成績タブの下半分（P/L）でラベルを探す。上半分の経費明細の科目と取り違えないよう min_row 以降だけ見る。"""
    for i, row in enumerate(vals, 1):
        if i < min_row:
            continue
        for j, v in enumerate(row, 1):
            if only_col and j != only_col:
                continue
            s = str(v).strip()
            if (s == text) if exact else (text in s):
                return i, j
    raise SystemExit(f"支出/成績タブに「{text}」が見つかりません")


def build_getsuji(sh: Sheet, ym: str):
    y, m = map(int, ym.split("-"))
    assert y == YEAR, "2026年シートだけ対応"
    title = getsuji_tab(ym)
    U = q(uriage(m))
    X = q(shishutsu(m))
    xv = sh.get(f"{X}!A1:Y120")
    mc = col(m + 1)          # 年間成績の月の列（1月=B）
    t = Tab(title, 10)
    t.widths = {1: 190, 2: 110, 3: 95, 4: 110, 5: 95, 6: 110, 7: 110, 8: 100, 9: 110, 10: 180}
    t.title_band(
        f"{y}年{m}月 月次（締めMTG用）",
        f"入力不要。元データは {uriage(m)}（受注フォームが自動で書き込む）と {shishutsu(m)}（経費）。"
        f"来月以降は python3 tools/build-dashboards.py --getsuji {y}-{m+1:02d} で同じ形が1本で出る。")
    RB, RC, RD, RE, RI, RJ, RK, RL, RM, RN, RO, RP, RU = (f"{U}!${x}$4:${x}$504" for x in
                                                          "BCDEIJKLMNOPU")

    # --- 成績
    t.section("■ 今月の成績")
    t.header(["売上目標", "売上実績", "達成率", "過不足", "あと何件（自社単価で）", "前年同月", "前年比", "前月", "前月比"])
    r = t.r
    prev = f"'年間成績'!{col(m)}20" if m > 1 else '""'
    t.row(r, [f"='年間成績'!{mc}18", f"=SUM({RI})", f'=IFERROR(B{r}/A{r},"")', f"=B{r}-A{r}",
              f'=IFERROR(IF(D{r}>=0,0,ROUNDUP(-D{r}/C{r+4},0)),"")',
              f"='年間成績'!{mc}34", f'=IFERROR(B{r}/F{r},"")', f"={prev}", f'=IFERROR(B{r}/H{r},"")'])
    t.fmt(r, 1, r, 9, "kpi")
    for c in (1, 2, 4, 6, 8):
        t.fmt(r, c, r, c, "yen")
    for c in (3, 7, 9):
        t.fmt(r, c, r, c, "pct")
    t.r += 1
    t.row(t.r, ["1月〜今月の累計", f"='年間成績'!{mc}21", "累計予算", f"=SUM('年間成績'!B18:{mc}18)",
                "累計の達成率", f'=IFERROR(B{t.r}/D{t.r},"")', "年間予算", "='年間成績'!N18"])
    t.fmt(t.r, 2, t.r, 2, "yen")
    t.fmt(t.r, 4, t.r, 4, "yen")
    t.fmt(t.r, 6, t.r, 6, "pct")
    t.fmt(t.r, 8, t.r, 8, "yen")
    t.fmt(t.r, 1, t.r, 1, "bold")
    t.r += 1
    t.row(t.r, ["うち施工済み（今日まで）", f'=SUMIFS({RI},{RC},"<="&TODAY())', "件数", f'=COUNTIFS({RB},"<>",{RC},"<="&TODAY())',
                "予定（明日以降）", f'=SUMIFS({RI},{RC},">"&TODAY())', "件数", f'=COUNTIFS({RB},"<>",{RC},">"&TODAY())'])
    t.fmt(t.r, 2, t.r, 2, "yen")
    t.fmt(t.r, 6, t.r, 6, "yen")
    t.fmt(t.r, 1, t.r, 1, "bold")
    t.r += 2

    # --- 件数と単価
    t.section("■ 件数と単価")
    t.header(["区分", "件数", "売上", "単価", "売上の構成比"])
    k0 = t.r
    t.row(k0, ["自社（One Hitter）", f'=COUNTIF({RB},"One Hitter")', f'=SUMIFS({RI},{RB},"One Hitter")',
               f'=IFERROR(C{k0}/B{k0},"")', f'=IFERROR(C{k0}/C{k0+2},"")'])
    t.row(k0 + 1, ["本舗", f'=COUNTIF({RB},"本舗")', f'=SUMIFS({RI},{RB},"本舗")',
                   f'=IFERROR(C{k0+1}/B{k0+1},"")', f'=IFERROR(C{k0+1}/C{k0+2},"")'])
    t.row(k0 + 2, ["合計", f"=COUNTA({RB})", f"=SUM({RI})", f'=IFERROR(C{k0+2}/B{k0+2},"")', ""])
    t.fmt(k0 + 2, 1, k0 + 2, 5, "total")
    t.row(k0 + 3, ["　うち法人（U列 法人名あり）", f'=COUNTIFS({RB},"<>",{RU},"<>")',
                   f'=SUMIFS({RI},{RB},"<>",{RU},"<>")', f'=IFERROR(C{k0+3}/B{k0+3},"")', f'=IFERROR(C{k0+3}/C{k0+2},"")'])
    t.row(k0 + 4, ["　うちネット経由（WEB集客の定義）",
                   f"=SUMPRODUCT(({RB}=\"One Hitter\")*(COUNTIF({WEB_DEF_RANGE},{RD})>0)*({RD}<>\"\"))",
                   f"=SUMPRODUCT(({RB}=\"One Hitter\")*(COUNTIF({WEB_DEF_RANGE},{RD})>0)*({RD}<>\"\"),{RI})",
                   f'=IFERROR(C{k0+4}/B{k0+4},"")', f'=IFERROR(C{k0+4}/C{k0+2},"")'])
    t.row(k0 + 5, ["稼働日数（施工のあった日）", f'=IFERROR(COUNTUNIQUE(FILTER({RC},{RB}<>"")),0)',
                   "稼働日あたり売上", f'=IFERROR(C{k0+2}/B{k0+5},"")'])
    t.fmt(k0, 3, k0 + 4, 4, "yen")
    t.fmt(k0 + 5, 4, k0 + 5, 4, "yen")
    t.fmt(k0, 5, k0 + 4, 5, "pct")
    t.r = k0 + 7
    # 「あと何件」は自社単価で割る
    t.cells[(r, 5)] = f'=IFERROR(IF(D{r}>=0,0,ROUNDUP(-D{r}/D{k0},0)),"")'

    # --- 流入経路別
    t.section("■ 流入経路別（多い順）")
    q0 = t.r
    t.put(q0, 1, f"=QUERY({{{RD},{RB},{RI}}},\"select Col1, count(Col2), sum(Col3), sum(Col3)/count(Col2) "
                 f"where Col2 is not null group by Col1 order by sum(Col3) desc "
                 f"label Col1 '流入経路', count(Col2) '件数', sum(Col3) '売上', sum(Col3)/count(Col2) '単価'\",0)")
    t.put(q0, 5, "構成比")
    t.put(q0 + 1, 5, f'=ARRAYFORMULA(IF(C{q0+1}:C{q0+18}="","",C{q0+1}:C{q0+18}/SUM({RI})))')
    t.put(q0, 6, "うち自社")
    t.put(q0 + 1, 6, f'=ARRAYFORMULA(IF(A{q0+1}:A{q0+18}="","",COUNTIFS({RD},A{q0+1}:A{q0+18},{RB},"One Hitter")))')
    t.fmt(q0, 1, q0, 6, "th")
    t.fmt(q0 + 1, 3, q0 + 18, 4, "yen")
    t.fmt(q0 + 1, 5, q0 + 18, 5, "pct")
    t.r = q0 + 20

    # --- メニュー別
    t.section("■ メニュー別（多い順）")
    q1 = t.r
    t.put(q1, 1, f"=QUERY({{{RJ},{RB},{RI}}},\"select Col1, count(Col2), sum(Col3), sum(Col3)/count(Col2) "
                 f"where Col2 is not null group by Col1 order by sum(Col3) desc "
                 f"label Col1 'メニュー', count(Col2) '件数', sum(Col3) '売上', sum(Col3)/count(Col2) '単価'\",0)")
    t.put(q1, 5, "構成比")
    t.put(q1 + 1, 5, f'=ARRAYFORMULA(IF(C{q1+1}:C{q1+18}="","",C{q1+1}:C{q1+18}/SUM({RI})))')
    t.fmt(q1, 1, q1, 5, "th")
    t.fmt(q1 + 1, 3, q1 + 18, 4, "yen")
    t.fmt(q1 + 1, 5, q1 + 18, 5, "pct")
    t.r = q1 + 20

    # --- 損益（支出/成績 から参照）
    t.section(f"■ 損益（{shishutsu(m)} の計算結果をそのまま表示）")
    t.header(["項目", "金額", "売上比", "", "経費の科目", "金額"])
    p0 = t.r
    pl = ["売上", "原価合計", "売上総利益", None, "営業利益", "融資返済", "経常利益", "和真利益", "会社利益"]
    for k, lab in enumerate(pl):
        rr = p0 + k
        if lab is None:
            i, j = find_label(xv, "販売管理費", exact=False, only_col=1)
            t.row(rr, ["販売管理費", f"={X}!{col(j+1)}{i}", f'=IFERROR(B{rr}/B{p0},"")'])
            continue
        i, j = find_label(xv, lab, only_col=1)
        t.row(rr, [lab, f"={X}!{col(j+1)}{i}", f'=IFERROR(B{rr}/B{p0},"")'])
    for k in (2, 4, 6, 8):
        t.fmt(p0 + k, 1, p0 + k, 3, "bold")
    kamoku = ["交通費", "耐久品", "備品", "融資", "広告費", "人件費", "本舗売上", "ロイヤリティ", "合計"]
    for k, lab in enumerate(kamoku):
        i, j = find_label(xv, lab, only_col=5)
        t.row(p0 + k, [lab, f"={X}!{col(j+1)}{i}"], c0=5)
    t.fmt(p0 + len(kamoku) - 1, 5, p0 + len(kamoku) - 1, 6, "total")
    t.fmt(p0, 2, p0 + 8, 2, "yen")
    t.fmt(p0, 3, p0 + 8, 3, "pct")
    t.fmt(p0, 6, p0 + 8, 6, "yen")
    t.r = p0 + 9
    # 和真・本舗
    i, j = find_label(xv, "和真給与")
    t.row(t.r, ["和真さんの給与", f"={X}!{col(j+1)}{i}", "", "", "和真さんの売上", f"={X}!{col(j+1)}{i+1}",
                "差額（会社負担）", f"={X}!{col(j+1)}{i+2}"])
    t.fmt(t.r, 2, t.r, 2, "yen"); t.fmt(t.r, 6, t.r, 6, "yen"); t.fmt(t.r, 8, t.r, 8, "yen")
    t.r += 1
    i, j = find_label(xv, "本舗合計")
    t.row(t.r, ["本舗の売上", f"={X}!{col(j)}{i+1}", "", "", "本舗へのロイヤリティ（固定分を含む）", f"={X}!{col(j)}{i+2}",
                "本舗売上に対する比率", f'=IFERROR(F{t.r}/B{t.r},"")'])
    t.fmt(t.r, 2, t.r, 2, "yen"); t.fmt(t.r, 6, t.r, 6, "yen"); t.fmt(t.r, 8, t.r, 8, "pct")
    t.r += 1
    key = f"{y}-{m:02d}"
    t.row(t.r, ["Google広告（管理画面の実績）",
                f"=SUMPRODUCT((TEXT('広告_日次'!$B$2:$B$3000,\"yyyy-mm\")=\"{key}\")*1,'広告_日次'!$E$2:$E$3000)",
                "", "", "支出タブへの計上",
                f'=IF(COUNTIF({X}!$D$2:$G$52,"*Google*")>0,"計上済み","未計上（カード引落しの月に支出タブへ）")'])
    t.fmt(t.r, 2, t.r, 2, "yen")
    t.r += 2

    # --- 経費の明細
    t.section(f"■ 経費の明細（{shishutsu(m)} の入力行）")
    t.header(["日付", "品目/品名", "科目", "金額", "備考"])
    t.put(t.r, 1, f'=IFERROR(FILTER({{{X}!B2:B52,{X}!D2:D52,{X}!E2:E52,{X}!F2:F52,{X}!G2:G52}},{X}!F2:F52<>""),"経費の入力なし")')
    t.fmt(t.r, 1, t.r + 30, 1, "date")
    t.fmt(t.r, 4, t.r + 30, 4, "yen")
    t.r += 32

    # --- 入金
    t.section("■ 入金・請求（O列 入金経路。P列 照合済みの割合）")
    q2 = t.r
    t.put(q2, 1, f"=QUERY({{ARRAYFORMULA(IF({RO}=\"\",\"（未入力）\",{RO})),{RB},{RI},ARRAYFORMULA(IF({RP}=TRUE,1,0))}},\"select Col1, count(Col2), sum(Col3), sum(Col4) "
                 f"where Col2 is not null group by Col1 order by sum(Col3) desc "
                 f"label Col1 '入金経路', count(Col2) '件数', sum(Col3) '売上', sum(Col4) '照合済み件数'\",0)")
    t.fmt(q2, 1, q2, 4, "th")
    t.fmt(q2 + 1, 3, q2 + 12, 3, "yen")
    t.r = q2 + 13

    # --- 締め前に直すもの
    t.section("■ 締め前に直すもの（空欄・要確認の行）")
    t.header(["No.", "施工日", "氏名", "売上", "流入経路", "入金経路", "足りないもの"])
    miss = (f'TRIM(IF({RD}="","流入経路／","")&IF(N(+{RI})=0,"金額／","")&IF({RO}="","入金経路／","")'
            f'&IF({RJ}="","メニュー／","")&IF(REGEXMATCH(TO_TEXT({RN}),"起こした行"),"★カレンダーから起こした行（名前・金額の確認）",""))')
    t.put(t.r, 1, f'=IFERROR(ARRAYFORMULA(FILTER({{{U}!$A$4:$A$504,{RC},{RE},{RI},{RD},{RO},{miss}}},{RB}<>"",{miss}<>"")),"直すものはありません")')
    t.fmt(t.r, 2, t.r + 30, 2, "date")
    t.fmt(t.r, 4, t.r + 30, 4, "yen")
    t.fmt(t.r, 7, t.r + 30, 7, "wrap")
    t.widths[7] = 160
    t.r += 32

    # --- リピートの種まき
    t.section("■ リピートの種まき（L列 早期予約提案・M列 フォローコール）")
    t.header(["早期予約提案", "件数", "", "フォローコール", "件数"])
    q3 = t.r
    t.put(q3, 1, f"=QUERY({{ARRAYFORMULA(IF({RL}=\"\",\"（空欄）\",{RL})),{RB}}},\"select Col1, count(Col2) where Col2 is not null group by Col1 order by count(Col2) desc label Col1 '', count(Col2) ''\",0)")
    t.put(q3, 4, f"=QUERY({{ARRAYFORMULA(IF({RM}=\"\",\"（空欄）\",{RM})),{RB}}},\"select Col1, count(Col2) where Col2 is not null group by Col1 order by count(Col2) desc label Col1 '', count(Col2) ''\",0)")
    t.r = q3 + 7
    t.row(t.r, ["フォローコール日を過ぎて未実施", f'=COUNTIFS({RB},"<>",{RK},"<="&TODAY(),{RM},"未記録")+COUNTIFS({RB},"<>",{RK},"<="&TODAY(),{RM},"")'])
    t.r += 2

    # --- 来月の受注残
    if m < 12:
        N = q(uriage(m + 1))
        t.section(f"■ 来月（{m+1}月）の受注残（{uriage(m+1)} に入っている分）")
        t.header(["件数", "売上", "来月の目標", "目標に対して"])
        t.row(t.r, [f"=COUNTA({N}!$B$4:$B$504)", f"=SUM({N}!$I$4:$I$504)", f"='年間成績'!{col(m+2)}18",
                    f'=IFERROR(B{t.r}/C{t.r},"")'])
        t.fmt(t.r, 2, t.r, 3, "yen")
        t.fmt(t.r, 4, t.r, 4, "pct")
        t.r += 2

    # --- 関連
    t.section("■ 関連")
    ids = {s: sh.tabs[s]["sheetId"] for s in (WEB_TAB, FUYU_TAB, uriage(m), shishutsu(m), "年間成績") if s in sh.tabs}
    links = [f'=HYPERLINK("#gid={v}","{k}")' for k, v in ids.items()]
    t.row(t.r, links)
    t.r += 1

    idx = sh.tabs[shishutsu(m)]["index"] + 1 if shishutsu(m) in sh.tabs else None
    return sh.write(t, index=idx)


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--web", action="store_true")
    ap.add_argument("--fuyu", action="store_true")
    ap.add_argument("--ga4", action="store_true", help="WEB集客のGA4欄だけ書き直す")
    ap.add_argument("--getsuji", metavar="YYYY-MM")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    if not (a.web or a.fuyu or a.ga4 or a.getsuji or a.all):
        ap.print_help()
        return
    sh = Sheet()
    made = []
    if a.web or a.all:
        _, g0 = build_web(sh)
        sh.refresh()
        write_ga4(sh, g0)
        made.append(WEB_TAB)
    elif a.ga4:
        write_ga4(sh)
    if a.fuyu or a.all:
        build_fuyu(sh)
        sh.refresh()
        made.append(FUYU_TAB)
    if a.getsuji:
        build_getsuji(sh, a.getsuji)
        sh.refresh()
        made.append(getsuji_tab(a.getsuji))
    for tname in made:
        check_errors(sh, tname)
        # MTGシートへのボタン（オーナー指示 2026-09-26。作り直すと消えるので毎回付け直す）
        import subprocess
        subprocess.run([sys.executable, str(ROOT / "tools" / "mtg-button.py"), "--jikkou", "--tab", tname],
                       capture_output=True, text=True)


if __name__ == "__main__":
    main()
