#!/usr/bin/env python3
"""全タブの1行目に「▶ MTGシートへ」ボタン（リンク）を置き、1行目を固定する。値は既存セルを1つも書き換えない。

    python3 tools/mtg-button.py            # どこに置くかを出すだけ
    python3 tools/mtg-button.py --jikkou   # 置く
    python3 tools/mtg-button.py --jikkou --tab "月次_2026-10"   # 1タブだけ

## なぜ（オーナー指示 2026-09-26）
「mtgシートと他のシートの行き来がし辛いから各シートにmtgシートへ移動するボタンを設置して固定表示して欲しい」

## 置き方の規則
- **行も列も挿入しない。** 受注フォーム・名乗り照合・広告スクリプトなどが「何行目・何列目」で読み書きしているため、
  挿入すると壊れる。置くのは **1行目の空いているセル** だけ。
- 1行目のタイトル文字を隠さない位置を、列幅と文字数から計算して選ぶ（固定列の中なら優先）。
- 1行目が見出しで埋まっているタブ（予約_Web など機械が書く表）は、見える範囲に空きが無いので置かない（一覧に出す）。
- 1行目を固定（固定行が0のタブだけ1にする。すでに固定があるタブはそのまま）。
- 1行目の A から始まる横長の結合（タイトル用）は、ボタンの場所を空けるために解除し、タイトルは「はみ出し表示」にする。
- ボタンは `=HYPERLINK("#gid=<MTGシート>","▶ MTGシートへ")`。青地・白文字・太字。もう置いてあるタブは同じセルに置き直す。
"""
import re
import sys
import pathlib
from urllib.parse import quote

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import sheets_client as sc  # noqa: E402

SID = "1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64"
MTG = "MTGシート"
LABEL = "▶ MTGシートへ"
LABEL_SHORT = "▶MTG"  # 幅が足りない場所（売上タブのA・B列など）はこちら
BTN_PX = 115          # ボタンの文字が収まる幅
BTN_PX_SHORT = 48
MAX_X = 1100          # これより右は、ふつうの画面では見えない
BLUE = {"red": 0.10, "green": 0.45, "blue": 0.91}
WHITE = {"red": 1, "green": 1, "blue": 1}


def text_px(s: str, size: float) -> float:
    w = 0.0
    for ch in s:
        w += size * (1.45 if ord(ch) > 0x2E80 else 0.62)
    return w + 8


def col(n):  # 0 -> A
    s = ""
    n += 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def plan(sheet, mtg_gid):
    p = sheet["properties"]
    g = p.get("gridProperties", {})
    data = (sheet.get("data") or [{}])[0]
    widths = [cm.get("pixelSize", 100) for cm in data.get("columnMetadata", [])]
    ncols = len(widths)
    starts = [0]
    for w in widths:
        starts.append(starts[-1] + w)
    row = (data.get("rowData") or [{}])[0].get("values", []) if data.get("rowData") else []
    cells = []
    for j in range(ncols):
        c = row[j] if j < len(row) else {}
        v = c.get("formattedValue", "")
        f = (c.get("userEnteredValue") or {}).get("formulaValue", "")
        size = ((c.get("effectiveFormat") or {}).get("textFormat") or {}).get("fontSize", 10)
        cells.append((v, f, size))
    # すでに置いたボタン
    for j, (v, f, _) in enumerate(cells):
        if f and f"#gid={mtg_gid}" in f:
            return j, [], (LABEL if "シートへ" in f else LABEL_SHORT)
    # 横長の結合（1行目・A始まり）
    merges = [m for m in sheet.get("merges", []) if m["startRowIndex"] == 0 and m["endRowIndex"] >= 1]
    unmerge = []
    merged_cols = set()
    for m in merges:
        if m["startColumnIndex"] == 0 and m["endColumnIndex"] - m["startColumnIndex"] >= 3:
            unmerge.append(m)
        else:
            merged_cols.update(range(m["startColumnIndex"], m["endColumnIndex"]))
    # 候補：固定列の中の空き → タイトルの右
    fc = g.get("frozenColumnCount", 0)

    def ok(j):
        """置ければラベルを返す。置けなければ None。"""
        if j in merged_cols or cells[j][0] or cells[j][1] or starts[j] > MAX_X:
            return None
        # 左隣に文字があって、それがこのセルまではみ出しているなら隠してしまう
        for k in range(j):
            v, _, size = cells[k]
            if v and starts[k] + text_px(v, size) > starts[j] and all(not cells[x][0] for x in range(k + 1, j)):
                return None
        span = 0
        x = j
        while x < ncols and not cells[x][0] and not cells[x][1] and x not in merged_cols:
            span += widths[x]
            x += 1
            if span >= BTN_PX:
                return LABEL
        return LABEL_SHORT if span >= BTN_PX_SHORT else None
    order = list(range(min(fc, ncols))) + [j for j in range(ncols) if j >= fc]
    for j in order:
        lab = ok(j)
        if lab:
            return j, unmerge, lab
    # 長い表記が入る場所が無ければ、短い表記の場所を探す（上の ok は短い表記も返すので、ここは空きなし）
    return None, unmerge, "空きなし"


def main():
    jikkou = "--jikkou" in sys.argv
    only = sys.argv[sys.argv.index("--tab") + 1] if "--tab" in sys.argv else None
    tok = sc.access_token(sc.load_credentials())
    props = sc.call(tok, f"/{SID}", query={"fields": "sheets.properties(sheetId,title)"})["sheets"]
    titles = [x["properties"]["title"] for x in props if not only or x["properties"]["title"] == only]
    mtg_gid = next(x["properties"]["sheetId"] for x in props if x["properties"]["title"] == MTG)
    fields = ("sheets(properties(sheetId,title,index,gridProperties),merges,"
              "data(columnMetadata.pixelSize,rowData.values(formattedValue,userEnteredValue,effectiveFormat.textFormat.fontSize)))")
    qs = "&".join("ranges=" + quote(f"'{t}'!A1:AZ1", safe="") for t in titles)
    sheets = sc.call(tok, f"/{SID}?includeGridData=true&fields={quote(fields, safe='')}&{qs}")["sheets"]
    reqs, vals, nashi = [], [], []
    for s in sheets:
        p = s["properties"]
        if p["title"] == MTG:
            continue
        j, unmerge, why = plan(s, mtg_gid)
        sid = p["sheetId"]
        if j is None:
            nashi.append(p["title"])
            print(f"  ✗ {p['title']}：1行目の見える範囲に空きなし（置かない）")
            continue
        print(f"  ✓ {p['title']}：{col(j)}1「{why}」" + ("　※タイトルの結合を解除" if unmerge else ""))
        for m in unmerge:
            reqs.append({"unmergeCells": {"range": m}})
            reqs.append({"repeatCell": {"range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1,
                                                  "startColumnIndex": 0, "endColumnIndex": 1},
                                        "cell": {"userEnteredFormat": {"wrapStrategy": "OVERFLOW_CELL"}},
                                        "fields": "userEnteredFormat.wrapStrategy"}})
        vals.append({"range": f"'{p['title']}'!{col(j)}1",
                     "values": [[f'=HYPERLINK("#gid={mtg_gid}","{why}")']]})
        reqs.append({"repeatCell": {"range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1,
                                              "startColumnIndex": j, "endColumnIndex": j + 1},
                                    "cell": {"userEnteredFormat": {
                                        "backgroundColor": BLUE, "wrapStrategy": "OVERFLOW_CELL",
                                        "horizontalAlignment": "LEFT", "verticalAlignment": "MIDDLE",
                                        "textFormat": {"bold": True, "fontSize": 10, "foregroundColor": WHITE,
                                                       "underline": False}}},
                                    "fields": "userEnteredFormat(backgroundColor,wrapStrategy,horizontalAlignment,verticalAlignment,textFormat)"}})
        if p.get("gridProperties", {}).get("frozenRowCount", 0) == 0:
            reqs.append({"updateSheetProperties": {"properties": {"sheetId": sid, "gridProperties": {"frozenRowCount": 1}},
                                                   "fields": "gridProperties.frozenRowCount"}})
    print(f"\n置く {len(vals)} タブ／置けない {len(nashi)} タブ")
    if not jikkou:
        print("（--jikkou を付けていないので置いていません）")
        return
    if reqs:
        sc.call(tok, f"/{SID}:batchUpdate", method="POST", payload={"requests": reqs})
    if vals:
        sc.call(tok, f"/{SID}/values:batchUpdate", method="POST",
                payload={"valueInputOption": "USER_ENTERED", "data": vals})
    print("✅ 置きました。")


if __name__ == "__main__":
    main()
