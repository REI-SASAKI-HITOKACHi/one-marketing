#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2026年スプシの `9月〜12月_売上/顧客` の D列（流入経路）の入力規則に、選択肢を足す。

依頼 `20260926-01-crm`（planning・cmo の `20260925-01-planning` から）。10/9 の広告判定に要る。

    python3 tools/ryunyu-kisoku-tsuika.py          # 何が変わるかを出すだけ（既定）
    python3 tools/ryunyu-kisoku-tsuika.py --kaku   # 書く

- 足すのは「広告」「GBP(地図検索)」の2つ。**既存の選択肢（「地図検索」を含む）は1つも消さない。**
- **セルの値は触らない。** `repeatCell` の fields を `dataValidation` だけにしている。
- 入力規則は1セルずつ付いているので、同じ規則が続く範囲ごとに付け直す。
  規則の無いセルには付けない（元の形を変えない）。「厳格か」「プルダウン表示か」は元の規則のまま。
- 変える前の規則を `data/sheets/backup/` に JSON で控える（値の控えではなく規則の控え）。
- ★順番：**シートが先、`data/ryunyu-keiro.json`（受注フォームの選択肢）は後**。
  json を先に変えると、シートが受け付けない値をフォームが書きにいく。json は planning の持ち物。
"""
import datetime
import importlib.util
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("sc", os.path.join(ROOT, "tools", "sheets_client.py"))
sc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sc)

SS = "1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64"
TABS = [f"{m}月_売上/顧客" for m in (9, 10, 11, 12)]
TASU = ["広告", "GBP(地図検索)"]
KAKU = "--kaku" in sys.argv


def yomu(tok, tab):
    r = sc.call(tok, f"/{SS}", query={
        "ranges": f"{tab}!D1:D2000", "includeGridData": "true",
        "fields": "sheets(properties(title,sheetId),data(startRow,rowData.values(dataValidation)))"})
    sh = r["sheets"][0]
    rows = sh["data"][0].get("rowData", [])
    kisoku = [((rd.get("values") or [{}])[0]).get("dataValidation") for rd in rows]
    return sh["properties"]["sheetId"], kisoku


def atarashii(dv):
    vals = [v.get("userEnteredValue") for v in dv["condition"].get("values", [])]
    tarinai = [x for x in TASU if x not in vals]
    if not tarinai:
        return None
    nd = json.loads(json.dumps(dv))
    nd["condition"]["values"] = [{"userEnteredValue": x} for x in vals + tarinai]
    return nd


def main():
    tok = sc.access_token(sc.load_credentials())
    reqs, hikae, hyouji = [], {}, []
    for tab in TABS:
        gid, kisoku = yomu(tok, tab)
        hikae[tab] = kisoku
        i = 0
        while i < len(kisoku):
            dv = kisoku[i]
            j = i
            while j + 1 < len(kisoku) and kisoku[j + 1] == dv:
                j += 1
            if dv and dv.get("condition", {}).get("type") == "ONE_OF_LIST":
                nd = atarashii(dv)
                if nd:
                    reqs.append({"repeatCell": {
                        "range": {"sheetId": gid, "startRowIndex": i, "endRowIndex": j + 1,
                                  "startColumnIndex": 3, "endColumnIndex": 4},
                        "cell": {"dataValidation": nd}, "fields": "dataValidation"}})
                    hyouji.append(f"{tab} D{i+1}:D{j+1}（{j-i+1}セル・選択肢 "
                                  f"{len(dv['condition']['values'])}→{len(nd['condition']['values'])}）")
            i = j + 1
    for x in hyouji:
        print(" ", x)
    print(f"付け直す範囲: {len(reqs)}か所")
    if not reqs:
        print("足すものはありません（もう入っています）")
        return 0
    if not KAKU:
        print("書きません（既定）。書くには --kaku")
        return 0
    os.makedirs(os.path.join(ROOT, "data", "sheets", "backup"), exist_ok=True)
    p = os.path.join(ROOT, "data", "sheets", "backup",
                     f"流入経路の入力規則-9〜12月-{datetime.datetime.now():%Y%m%d-%H%M%S}.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(hikae, f, ensure_ascii=False)
    print("変える前の規則を控えました:", os.path.relpath(p, ROOT))
    sc.call(tok, f"/{SS}:batchUpdate", "POST", {"requests": reqs})
    # 読み直して確かめる
    ng = 0
    for tab in TABS:
        _, kisoku = yomu(tok, tab)
        for n, dv in enumerate(kisoku, 1):
            if dv and dv.get("condition", {}).get("type") == "ONE_OF_LIST":
                vals = [v.get("userEnteredValue") for v in dv["condition"]["values"]]
                if not all(x in vals for x in TASU) or "地図検索" not in vals and "地図検索" in \
                        [v.get("userEnteredValue") for v in (hikae[tab][n-1] or {}).get("condition", {}).get("values", [])]:
                    ng += 1
    print("読み直し:", "すべてOK" if not ng else f"★NG {ng}セル")
    return 1 if ng else 0


if __name__ == "__main__":
    sys.exit(main())
