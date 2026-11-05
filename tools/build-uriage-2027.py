#!/usr/bin/env python3
"""2027年の売上・顧客ファイル（別ファイル）を v0 として組み立てる。

【なぜ】
  10/6 頃 MTG（F642・オーナー原文）「暇なときに2027年版のこのファイルを作成しておいて。内容は大幅にブラッシュアップさせてほしい。
  嶺と和真の使いやすさを最優先して」→ 10/10 に同じファイルへ 2027年の月タブを足しただけで、別ファイル化と見直しが未対応だった。
  11/5 オーナー「最初から100点を目指さずにこれまでに出てる改善点を反映したバージョン0を一旦作成して。
  その後MTGのたびに使用感をレビューして11月中の完成を目指そう。」

【何をするか】
  ファイル（嶺さんの Drive・サービスアカウントに編集権限）に、次のタブを作り直す（中身は毎回作り直す。v0 の間は入力されたものは無い前提）
    使い方・改善点 / 売上 / 月次 / 支出 / 出納帳
  旧ファイル（2026）の「2027年n月_売上/顧客」タブの行を『売上』へ写す（旧タブは消さない・フォームの書き込み先もまだ旧ファイルのまま）

    python3 tools/build-uriage-2027.py            # 組み立て
    python3 tools/build-uriage-2027.py --dry-run  # 写す行だけ見る
"""
import sys
import urllib.parse

sys.path.insert(0, __import__("os").path.dirname(__file__))
import sheets_client as sc  # noqa: E402

NEW = "1UBxM_YdTaX3yh1VDfiwPwSwOae_-b-jBHInXZ5BV6S4"
OLD = "1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64"

KEIRO = ["営業", "業務提携", "チラシ(OH)", "チラシ(本舗)", "LINE", "HP", "SMS", "早期予約", "リピート",
         "スケジュールマッチング", "入札案件", "広告", "予約ページ", "LP", "地図検索", "紹介", "その他"]
NET = ["広告", "予約ページ", "LP", "地図検索", "HP", "LINE", "SMS"]   # MTG 9-1 の「ネット経由」と同じ
NYUKIN = ["現金", "(OH)クレカ", "(本舗)クレカ", "QR決済", "振込", "請求書(当月)", "請求書(翌月)", "請求書(2か月後)", "その他"]
JOTAI = ["仮", "確定", "完了", "キャンセル"]
SHISHUTSU = ["広告費", "交通費", "耐久品", "備品", "人件費", "融資", "保険料", "通信費", "その他"]

URIAGE_H = ["受注ID", "月", "状態", "売上種類", "施工日", "開始", "流入経路", "ネット経由", "氏名", "顧客ID", "電話",
            "郵便番号", "住所", "実施メニュー", "売上（税込）", "割引の内訳", "紹介者", "入金経路", "入金済み",
            "フォローコール日", "備考（お客様の声・現場メモ）"]
COL = {h: chr(ord("A") + i) for i, h in enumerate(URIAGE_H)}

KAIZEN = [
    ["No.", "改善点", "どこから出た話か", "v0 でやったこと", "使ってみて（嶺さん・和真さん記入）", "次の版で直すこと（CMO）"],
    ["1", "2026年とファイルを分ける", "10/6頃 MTG（F642）オーナー", "このファイルを新しく作った（嶺さんの Drive）", "", ""],
    ["2", "月ごとのタブをやめて、売上を1枚にする", "10月タブの二重記入 ¥252,500（第6回）・タブをまたぐ集計のずれ", "『売上』1枚。月は施工日から自動。月ごとに見たいときはフィルタ", "", ""],
    ["3", "【仮】・確定・完了・キャンセルを同じ表で見る", "カレンダーにあって台帳に無い施工が16件（第3回）", "『状態』列（プルダウン）。キャンセルは灰色、仮は黄色", "", ""],
    ["4", "入金経路と入金済みを1か所で", "第4回『出納帳と売上の入金経路を作業完了フォームと連動』", "『入金経路』プルダウン＋『入金済み』チェック。完了なのに入金済みでない行はオレンジ", "", ""],
    ["5", "割引の中身を備考に埋もれさせない", "早期割引が入らない不具合（11/5）・12月の特例10%（11/3）", "『割引の内訳』列（例：早期予約15%／リピート−1,000／紹介−1,000／特例）", "", ""],
    ["6", "紹介者を残して、紹介割引を数えられるように", "第5回（10/3）紹介割引の決まり", "『紹介者』列", "", ""],
    ["7", "ネット経由を毎回手で数えない", "MTG 9-1 の手集計", "『ネット経由』を流入経路から自動。『月次』で件数と売上が出る", "", ""],
    ["8", "二重記入に気づけるように", "10月の二重記入", "受注IDが重なった行は赤", "", ""],
    ["9", "行番号ではなく、名前でお客様を探せるように", "和真さんの要望（行番号で聞かれても分からない）", "氏名＋顧客ID（顧客管理台帳の C0000）を並べた", "", ""],
    ["10", "支出を1枚に。Google広告の実費・ETC代を毎月入れる", "11/5 Google広告がどの月にも入っていなかった・和真さん『ETC代計上月ごとに』", "『支出』1枚（月は自動）。毎月入れる行のひな形を置いた", "", ""],
    ["11", "出納帳を同じファイルに。現金の売上を自動で並べる", "第4回・第9回の現金のずれ（長様・藤田様）", "『出納帳』に、入金経路が現金の売上を自動で一覧。下に手で入れる出納の表", "", ""],
    ["12", "見やすさ（折り返さない・見出し固定）", "オーナー『行が太くなりすぎて見づらい』", "全タブ折り返しなし・1行目固定・フィルタ付き", "", ""],
    ["13", "和真さんの報酬（固定40万＋プール10万）を月次で自動", "T031（報酬の新制度がシートに入っていない）", "『月次』に会社利益まで自動（固定40万＋プール10万で計算）", "", ""],
    ["", "", "", "", "", ""],
    ["★", "まだやっていないこと（次の版）", "", "受注フォーム・作業完了フォーム・取り込みツールの書き込み先をこのファイルへ切り替える（12月中に試し・1/1 本番）／顧客管理台帳の移し方／月ごとの予算（経営企画室の2027計画から）", "", ""],
]


def tok():
    return sc.access_token(sc.load_credentials())


def furui_2027(t):
    meta = sc.call(t, f"/{OLD}", query={"fields": "sheets.properties(title)"})
    out = []
    for name in [s["properties"]["title"] for s in meta["sheets"] if s["properties"]["title"].startswith("2027年")]:
        v = sc.call(t, f"/{OLD}/values/{urllib.parse.quote(name + '!A1:P200', safe='')}",
                    query={"valueRenderOption": "FORMATTED_VALUE"}).get("values", [])
        hi = next((i for i, r in enumerate(v) if "施工日付" in r), None)
        if hi is None:
            continue
        h = v[hi]
        ix = {c: i for i, c in enumerate(h)}
        g = lambda r, k: (r[ix[k]] if k in ix and ix[k] < len(r) else "")
        for r in v[hi + 1:]:
            if not g(r, "氏名").strip() or not str(g(r, "施工日付")).startswith("2027"):
                continue  # 集計行（件数・合計）は写さない
            out.append({"売上種類": g(r, "売上種類"), "施工日": g(r, "施工日付"), "流入経路": g(r, "流入経路"),
                        "氏名": g(r, "氏名"), "電話": g(r, "TEL(-無し)"), "郵便番号": g(r, "郵便番号(-無し)"),
                        "住所": g(r, "住所"), "売上（税込）": g(r, "売上（税込）").replace("¥", "").replace(",", ""),
                        "実施メニュー": g(r, "実施メニュー"), "入金経路": g(r, "入金経路"),
                        "備考（お客様の声・現場メモ）": (g(r, "備考(お客様の声)") + f"　【旧ファイル {name} から写した】").strip()})
    return out


def main():
    t = tok()
    rows = furui_2027(t)
    print(f"旧ファイルの2027年の行: {len(rows)}")
    for r in rows:
        print("  ", r["施工日"], r["氏名"], r["売上（税込）"], r["実施メニュー"][:20])
    if "--dry-run" in sys.argv:
        return

    meta = sc.call(t, f"/{NEW}", query={"fields": "sheets.properties"})
    aru = {s["properties"]["title"]: s["properties"]["sheetId"] for s in meta["sheets"]}
    names = ["使い方・改善点", "売上", "月次", "支出", "出納帳"]
    req = []
    # いまあるタブを1つ残して全部消し、作り直す（v0 の間だけ）
    keep = list(aru.items())[0]
    req.append({"updateSheetProperties": {"properties": {"sheetId": keep[1], "title": "_tmp"}, "fields": "title"}})
    for na, sid in list(aru.items())[1:]:
        req.append({"deleteSheet": {"sheetId": sid}})
    for i, na in enumerate(names):
        req.append({"addSheet": {"properties": {"title": na, "index": i, "gridProperties": {"frozenRowCount": 1}}}})
    req.append({"deleteSheet": {"sheetId": keep[1]}})
    res = sc.call(t, f"/{NEW}:batchUpdate", method="POST", payload={"requests": req})
    meta = sc.call(t, f"/{NEW}", query={"fields": "sheets.properties"})
    sid = {s["properties"]["title"]: s["properties"]["sheetId"] for s in meta["sheets"]}

    # ---------- 値 ----------
    uri = [URIAGE_H]
    for n, r in enumerate(rows, start=1):
        line = []
        for h in URIAGE_H:
            if h == "受注ID":
                line.append(f"旧-{n:03d}")
            elif h == "状態":
                line.append("確定")
            elif h in ("月", "ネット経由", "フォローコール日"):
                line.append("")
            else:
                line.append(r.get(h, ""))
        uri.append(line)
    c = COL
    hdr_formula = {
        "月": f'={{"月";ARRAYFORMULA(IF({c["施工日"]}2:{c["施工日"]}="","",MONTH({c["施工日"]}2:{c["施工日"]})&"月"))}}',
        "ネット経由": '={"ネット経由";ARRAYFORMULA(IF(' + c["流入経路"] + '2:' + c["流入経路"] + '="","",IF(REGEXMATCH('
                     + c["流入経路"] + '2:' + c["流入経路"] + ',"^(' + "|".join(NET) + ')$"),"ネット","")))}',
        "フォローコール日": f'={{"フォローコール日";ARRAYFORMULA(IF({c["施工日"]}2:{c["施工日"]}="","",{c["施工日"]}2:{c["施工日"]}+7))}}',
    }
    for h, f in hdr_formula.items():
        uri[0][URIAGE_H.index(h)] = f

    U = "売上"
    m_rows = [["月", "売上（キャンセル除く）", "件数", "うち自社", "うち本舗", "ネット経由 件数", "ネット経由 売上",
               "支出合計", "粗い利益（売上−支出）", "和真さん報酬（固定40万＋プール10万）", "会社利益", "予算", "達成率"]]
    for m in range(1, 13):
        r = m + 1
        mm = f'"{m}月"'
        rng = lambda col: f"{U}!{c[col]}:{c[col]}"
        m_rows.append([
            f"{m}月",
            f'=SUMIFS({rng("売上（税込）")},{rng("月")},{mm},{rng("状態")},"<>キャンセル")',
            f'=COUNTIFS({rng("月")},{mm},{rng("状態")},"<>キャンセル")',
            f'=COUNTIFS({rng("月")},{mm},{rng("状態")},"<>キャンセル",{rng("売上種類")},"One Hitter")',
            f'=COUNTIFS({rng("月")},{mm},{rng("状態")},"<>キャンセル",{rng("売上種類")},"本舗")',
            f'=COUNTIFS({rng("月")},{mm},{rng("状態")},"<>キャンセル",{rng("ネット経由")},"ネット")',
            f'=SUMIFS({rng("売上（税込）")},{rng("月")},{mm},{rng("状態")},"<>キャンセル",{rng("ネット経由")},"ネット")',
            f'=SUMIFS(支出!E:E,支出!B:B,{mm})',
            f"=B{r}-H{r}",
            "500000",
            f"=I{r}-J{r}",
            "",
            f'=IF(L{r}="","",B{r}/L{r})',
        ])
    m_rows.append(["合計", "=SUM(B2:B13)", "=SUM(C2:C13)", "=SUM(D2:D13)", "=SUM(E2:E13)", "=SUM(F2:F13)", "=SUM(G2:G13)",
                   "=SUM(H2:H13)", "=SUM(I2:I13)", "=SUM(J2:J13)", "=SUM(K2:K13)", "=SUM(L2:L13)", '=IF(L14=0,"",B14/L14)'])

    s_rows = [['日付', '={"月";ARRAYFORMULA(IF(A2:A="","",MONTH(A2:A)&"月"))}', "区分", "内容", "金額", "支払方法", "備考"]]
    for m in range(1, 13):
        s_rows.append([f"2027/{m}/1", "", "広告費", "Google広告（実費・月末に計測担当が入れる）", "", "三井住友（オーナーズVisa）", "毎月入れる行（11/5 の反省）"])
        s_rows.append([f"2027/{m}/1", "", "交通費", "ETC代（月ごと）", "", "", "和真さん 11/5『ETC代計上月ごとに』"])

    d_rows = [["▼ 入金経路が『現金』の売上（自動）", "", "", "", "", "", "", "▼ 出納帳（手で入れる）", "", "", "", "", ""],
              ["", "", "", "", "", "", "", "日付", "区分", "相手", "内容", "金額（入金＋／出金−）", "残高"]]
    d_rows[1][0] = (f'=QUERY({U}!A:U,"select {c["施工日"]},{c["氏名"]},{c["売上（税込）"]},{c["状態"]},{c["入金済み"]},{c["受注ID"]} '
                    f'where {c["入金経路"]} = \'現金\' and {c["状態"]} <> \'キャンセル\' order by {c["施工日"]}",1)')
    for r in range(3, 203):
        d_rows.append(["", "", "", "", "", "", "", "", "", "", "", "", f'=IF(L{r}="","",SUM($L$3:L{r}))'])
    d_rows[2][12] = '=IF(L3="","",SUM($L$3:L3))'

    kaku = [
        {"range": "使い方・改善点!A1", "values": KAIZEN},
        {"range": "売上!A1", "values": uri},
        {"range": "月次!A1", "values": m_rows},
        {"range": "支出!A1", "values": s_rows},
        {"range": "出納帳!A1", "values": d_rows},
    ]
    sc.call(t, f"/{NEW}/values:batchUpdate", method="POST", payload={"valueInputOption": "USER_ENTERED", "data": kaku})

    # ---------- 書式・入力規則 ----------
    def kisoku(sheet, col, vals, n=1000):
        ci = ord(col) - ord("A")
        return {"setDataValidation": {"range": {"sheetId": sid[sheet], "startRowIndex": 1, "endRowIndex": n,
                                                "startColumnIndex": ci, "endColumnIndex": ci + 1},
                                      "rule": {"condition": {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": v} for v in vals]},
                                               "showCustomUi": True, "strict": False}}}

    def kisoku_hi(sheet, col, n=1000):
        ci = ord(col) - ord("A")
        return {"setDataValidation": {"range": {"sheetId": sid[sheet], "startRowIndex": 1, "endRowIndex": n,
                                                "startColumnIndex": ci, "endColumnIndex": ci + 1},
                                      "rule": {"condition": {"type": "DATE_IS_VALID"}, "strict": False}}}

    req = []
    for na in names:
        req.append({"repeatCell": {"range": {"sheetId": sid[na]},
                                   "cell": {"userEnteredFormat": {"wrapStrategy": "CLIP", "verticalAlignment": "MIDDLE",
                                                                  "textFormat": {"fontSize": 10}}},
                                   "fields": "userEnteredFormat(wrapStrategy,verticalAlignment,textFormat.fontSize)"}})
        req.append({"repeatCell": {"range": {"sheetId": sid[na], "startRowIndex": 0, "endRowIndex": 1},
                                   "cell": {"userEnteredFormat": {"backgroundColor": {"red": 0.216, "green": 0.278, "blue": 0.31},
                                                                  "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}}}},
                                   "fields": "userEnteredFormat(backgroundColor,textFormat)"}})
    req.append({"setBasicFilter": {"filter": {"range": {"sheetId": sid["売上"], "startRowIndex": 0, "startColumnIndex": 0,
                                                         "endColumnIndex": len(URIAGE_H)}}}})
    req.append({"setBasicFilter": {"filter": {"range": {"sheetId": sid["支出"], "startRowIndex": 0, "startColumnIndex": 0, "endColumnIndex": 7}}}})
    req += [kisoku("売上", c["状態"], JOTAI), kisoku("売上", c["売上種類"], ["One Hitter", "本舗"]),
            kisoku("売上", c["流入経路"], KEIRO), kisoku("売上", c["入金経路"], NYUKIN), kisoku_hi("売上", c["施工日"]),
            kisoku("支出", "C", SHISHUTSU), kisoku_hi("支出", "A")]
    ci = ord(c["入金済み"]) - ord("A")
    req.append({"setDataValidation": {"range": {"sheetId": sid["売上"], "startRowIndex": 1, "endRowIndex": 1000,
                                                "startColumnIndex": ci, "endColumnIndex": ci + 1},
                                      "rule": {"condition": {"type": "BOOLEAN"}}}})
    # 数値・日付の表示
    def fmt(sheet, col, pat, typ="NUMBER", r0=1, r1=1000):
        ci = ord(col) - ord("A")
        return {"repeatCell": {"range": {"sheetId": sid[sheet], "startRowIndex": r0, "endRowIndex": r1,
                                         "startColumnIndex": ci, "endColumnIndex": ci + 1},
                               "cell": {"userEnteredFormat": {"numberFormat": {"type": typ, "pattern": pat}}},
                               "fields": "userEnteredFormat.numberFormat"}}
    req += [fmt("売上", c["売上（税込）"], "¥#,##0"), fmt("売上", c["施工日"], "yyyy/mm/dd(ddd)", "DATE"),
            fmt("売上", c["フォローコール日"], "yyyy/mm/dd", "DATE"), fmt("支出", "E", "¥#,##0"), fmt("支出", "A", "yyyy/mm/dd", "DATE"),
            fmt("出納帳", "L", "¥#,##0", r0=2), fmt("出納帳", "M", "¥#,##0", r0=2), fmt("出納帳", "C", "¥#,##0", r0=2),
            fmt("出納帳", "H", "yyyy/mm/dd", "DATE", r0=2), fmt("出納帳", "A", "yyyy/mm/dd", "DATE", r0=2)]
    for col in "BDEFGHIJKL":
        req.append(fmt("月次", col, "¥#,##0", r0=1, r1=14) if col not in "CDEF" else fmt("月次", col, "0", r0=1, r1=14))
    req.append(fmt("月次", "M", "0.0%", r0=1, r1=14))
    # 条件付き書式（売上）
    last = chr(ord("A") + len(URIAGE_H) - 1)
    rng = {"sheetId": sid["売上"], "startRowIndex": 1, "endRowIndex": 1000, "startColumnIndex": 0, "endColumnIndex": len(URIAGE_H)}
    def cf(formula, rgb):
        return {"addConditionalFormatRule": {"rule": {"ranges": [rng], "booleanRule": {
            "condition": {"type": "CUSTOM_FORMULA", "values": [{"userEnteredValue": formula}]},
            "format": {"backgroundColor": {"red": rgb[0], "green": rgb[1], "blue": rgb[2]}}}}, "index": 0}}
    req += [cf(f'=${c["状態"]}2="キャンセル"', (0.85, 0.85, 0.85)),
            cf(f'=${c["状態"]}2="仮"', (1, 0.973, 0.882)),
            cf(f'=AND(${c["状態"]}2="完了",${c["入金済み"]}2<>TRUE)', (1, 0.878, 0.698)),
            cf(f'=AND(${c["受注ID"]}2<>"",COUNTIF(${c["受注ID"]}:${c["受注ID"]},${c["受注ID"]}2)>1)', (1, 0.8, 0.8))]
    # 列幅
    widths = {"売上": [90, 50, 70, 90, 110, 55, 100, 70, 110, 70, 105, 75, 220, 200, 95, 150, 90, 100, 60, 105, 300],
              "使い方・改善点": [40, 300, 300, 380, 260, 260], "月次": [60, 150, 55, 70, 70, 110, 120, 100, 150, 220, 120, 100, 70],
              "支出": [100, 50, 80, 280, 100, 170, 260], "出納帳": [100, 120, 90, 70, 70, 90, 20, 100, 70, 120, 220, 150, 100]}
    for na, ws in widths.items():
        for i, w in enumerate(ws):
            req.append({"updateDimensionProperties": {"range": {"sheetId": sid[na], "dimension": "COLUMNS", "startIndex": i, "endIndex": i + 1},
                                                      "properties": {"pixelSize": w}, "fields": "pixelSize"}})
    # 出納帳は2行目も見出し
    req.append({"repeatCell": {"range": {"sheetId": sid["出納帳"], "startRowIndex": 1, "endRowIndex": 2, "startColumnIndex": 7, "endColumnIndex": 13},
                               "cell": {"userEnteredFormat": {"textFormat": {"bold": True}, "backgroundColor": {"red": 0.925, "green": 0.937, "blue": 0.945}}},
                               "fields": "userEnteredFormat(textFormat,backgroundColor)"}})
    req.append({"updateSheetProperties": {"properties": {"sheetId": sid["出納帳"], "gridProperties": {"frozenRowCount": 2}},
                                          "fields": "gridProperties.frozenRowCount"}})
    req.append({"repeatCell": {"range": {"sheetId": sid["使い方・改善点"], "startRowIndex": 1, "endRowIndex": 40, "startColumnIndex": 4, "endColumnIndex": 5},
                               "cell": {"userEnteredFormat": {"backgroundColor": {"red": 1, "green": 0.973, "blue": 0.882}}},
                               "fields": "userEnteredFormat.backgroundColor"}})
    sc.call(t, f"/{NEW}:batchUpdate", method="POST", payload={"requests": req})
    print(f"✅ 組み立てました: https://docs.google.com/spreadsheets/d/{NEW}/edit")


if __name__ == "__main__":
    main()
