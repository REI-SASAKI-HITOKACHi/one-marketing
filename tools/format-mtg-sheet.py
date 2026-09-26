#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MTGシートに書式を入れる。値は1つも書き換えない。

【なぜツールにしたか】
  2026-09-19 に、レイアウトを直すためタブを作り直したところ、
  **値は復元できたが書式が全部消えた**（色分け・折り返し・列幅・プルダウン）。
  オーナーから「前回はあった色分けや工夫が無くなって見づらい」と指摘を受けた。

  書式を手で入れ直すと、次に作り直したときにまた消える。**何度でも当て直せる形にする。**

【使い方】
  python3 tools/format-mtg-sheet.py            # 何をするか出すだけ
  python3 tools/format-mtg-sheet.py --jikkou   # 当てる

★順番に注意（2026-09-19 に実際に踏んだ）
  このツールはセル全体の textFormat を上書きするので、**先に張ったリンクが消える。**
  値を書き換えたあとは、必ずこの順で流すこと。
    1. python3 tools/format-mtg-sheet.py   --jikkou   （色・折り返し・結合・プルダウン）
    2. python3 tools/format-mtg-numbers.py --jikkou   （￥・％・3桁区切り）
    3. python3 tools/link-mtg-sanshou.py   --jikkou   （リンク）★かならず最後

【何をするか】
  1. 全体を折り返し・上揃えに（長い文章が読めるようになる。いちばん効く）
  2. 列幅を、いちばん多い表の形に合わせる
  3. 行の種類で塗り分ける
       ━ 回の区切り … 濃紺グレー＋白文字
       ■ 章見出し   … 薄いグレー＋太字
       表の見出し   … もっと薄いグレー＋太字
       🔴 を含む行  … 薄い赤（見落とすと困るもの）
       ✅ を含む行  … 薄い緑（済んだもの）
       ★ で始まる行 … 薄い黄（今日いちばん見てほしいもの）
  4. 説明文の行（A列だけに中身がある長い行）は A〜I を結合して横幅いっぱいに
  5. 「決定」欄をプルダウンに（決定／保留／取り下げ／持ち帰り）。未記入は薄い黄で目立たせる
  6. 1行目を固定
"""
import json
import re
import subprocess
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sheets_client as sc

SS = "1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64"
TAB = "MTGシート"
HABA = [(0, 54), (1, 210), (2, 250), (3, 290), (4, 250), (5, 74), (6, 260), (7, 62), (8, 92)]
HYOU_MIDASHI = {"No.", "区分", "月日", "状態", "提携先", "月"}


def iro(r, g, b):
    return {"red": r / 255, "green": g / 255, "blue": b / 255}


KUGIRI, SHOU, MIDASHI = iro(55, 71, 79), iro(207, 216, 220), iro(236, 239, 241)
AKA, MIDORI, KI = iro(255, 235, 238), iro(232, 245, 233), iro(255, 248, 225)


def main():
    jikkou = "--jikkou" in sys.argv
    tok = sc.access_token(sc.load_credentials())
    meta = sc.call(tok, f"/{SS}", query={"fields": "sheets.properties"})
    sid = next((s["properties"]["sheetId"] for s in meta["sheets"]
                if s["properties"]["title"] == TAB), None)
    if sid is None:
        sys.exit(f"{TAB} タブがありません。")

    o = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "sheets_client.py"),
                        "read", SS, f"'{TAB}'!A1:I1000"], capture_output=True, text=True)
    if o.returncode:
        sys.exit(o.stderr[:300])
    rows = [[str(c) for c in r] for r in json.loads(o.stdout or "[]")]
    n = len(rows)

    req = []

    def gyo_shoshiki(i, fmt, fields):
        req.append({"repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": i, "endRowIndex": i + 1,
                      "startColumnIndex": 0, "endColumnIndex": 9},
            "cell": {"userEnteredFormat": fmt}, "fields": fields}})

    # 1. 折り返しと上揃え
    req.append({"repeatCell": {
        "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": n,
                  "startColumnIndex": 0, "endColumnIndex": 9},
        "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP", "verticalAlignment": "TOP",
                                       "textFormat": {"fontSize": 10}}},
        "fields": "userEnteredFormat(wrapStrategy,verticalAlignment,textFormat.fontSize)"}})

    # 2. 列幅
    for c, w in HABA:
        req.append({"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": c, "endIndex": c + 1},
            "properties": {"pixelSize": w}, "fields": "pixelSize"}})

    # 3. 行の種類で塗り分け
    kazu = {"区切り": 0, "章": 0, "表の見出し": 0, "🔴": 0, "✅": 0, "★": 0}
    for i, r in enumerate(rows):
        a = r[0] if r else ""
        zen = " ".join(r)
        if a.startswith("━"):
            gyo_shoshiki(i, {"backgroundColor": KUGIRI, "textFormat": {
                "bold": True, "fontSize": 12, "foregroundColor": iro(255, 255, 255)}},
                "userEnteredFormat(backgroundColor,textFormat)"); kazu["区切り"] += 1
        elif a.startswith("■"):
            gyo_shoshiki(i, {"backgroundColor": SHOU, "textFormat": {"bold": True, "fontSize": 11}},
                         "userEnteredFormat(backgroundColor,textFormat)"); kazu["章"] += 1
        elif a in HYOU_MIDASHI and len([c for c in r if c.strip()]) >= 3:
            gyo_shoshiki(i, {"backgroundColor": MIDASHI, "textFormat": {"bold": True}},
                         "userEnteredFormat(backgroundColor,textFormat)"); kazu["表の見出し"] += 1
        elif a.startswith("【"):
            gyo_shoshiki(i, {"textFormat": {"bold": True}}, "userEnteredFormat.textFormat")
        elif "🔴" in zen:
            gyo_shoshiki(i, {"backgroundColor": AKA}, "userEnteredFormat.backgroundColor"); kazu["🔴"] += 1
        elif "✅" in zen:
            gyo_shoshiki(i, {"backgroundColor": MIDORI}, "userEnteredFormat.backgroundColor"); kazu["✅"] += 1
        elif a.startswith("★"):
            gyo_shoshiki(i, {"backgroundColor": KI, "textFormat": {"bold": True}},
                         "userEnteredFormat(backgroundColor,textFormat)"); kazu["★"] += 1

    # 4. 説明文の行は横幅いっぱいに
    ketsugou = [i for i, r in enumerate(rows)
                if r and r[0].strip() and not any(c.strip() for c in r[1:])
                and not r[0].startswith("━")
                and (len(r[0]) >= 30 or r[0].startswith("■"))]
    for i in ketsugou:
        req.append({"mergeCells": {
            "range": {"sheetId": sid, "startRowIndex": i, "endRowIndex": i + 1,
                      "startColumnIndex": 0, "endColumnIndex": 9}, "mergeType": "MERGE_ALL"}})

    # 5. 「決定」欄のプルダウン
    kettei = []
    for i, r in enumerate(rows):
        if r and r[0] == "No." and len(r) > 5 and r[5] == "決定":
            j = i + 1
            while j < n and rows[j] and rows[j][0].strip() and re.fullmatch(r"\d+", rows[j][0].strip()):
                j += 1
            kettei.append((i + 1, j))
    for hajime, owari in kettei:
        req.append({"setDataValidation": {
            "range": {"sheetId": sid, "startRowIndex": hajime, "endRowIndex": owari,
                      "startColumnIndex": 5, "endColumnIndex": 6},
            "rule": {"condition": {"type": "ONE_OF_LIST", "values": [
                {"userEnteredValue": v} for v in ("決定", "保留", "取り下げ", "持ち帰り")]},
                "showCustomUi": True, "strict": False}}})
        req.append({"repeatCell": {
            "range": {"sheetId": sid, "startRowIndex": hajime, "endRowIndex": owari,
                      "startColumnIndex": 5, "endColumnIndex": 7},
            "cell": {"userEnteredFormat": {"backgroundColor": KI}},
            "fields": "userEnteredFormat.backgroundColor"}})

    # 6. 1行目を固定し、タイトルを大きく
    req.append({"updateSheetProperties": {
        "properties": {"sheetId": sid, "gridProperties": {"frozenRowCount": 1}},
        "fields": "gridProperties.frozenRowCount"}})
    gyo_shoshiki(0, {"backgroundColor": KUGIRI, "textFormat": {
        "bold": True, "fontSize": 14, "foregroundColor": iro(255, 255, 255)}},
        "userEnteredFormat(backgroundColor,textFormat)")

    # 行の高さを中身に合わせる（結合のあとに）
    req.append({"autoResizeDimensions": {"dimensions": {
        "sheetId": sid, "dimension": "ROWS", "startIndex": 0, "endIndex": n}}})

    print(f"対象: {TAB}（{n}行）")
    print(f"  塗り分け: " + " / ".join(f"{k} {v}" for k, v in kazu.items()))
    print(f"  横幅いっぱいにする説明行: {len(ketsugou)}行")
    print(f"  決定欄のプルダウン: {len(kettei)}か所 " + str([(a + 1, b) for a, b in kettei]))
    print(f"  リクエスト数: {len(req)}")
    if not jikkou:
        print("\n（--jikkou を付けていないので当てていません）")
        return
    sc.call(tok, f"/{SS}:batchUpdate", method="POST", payload={"requests": req})
    print("\n✅ 当てました。値は1つも書き換えていません。")


if __name__ == "__main__":
    main()
