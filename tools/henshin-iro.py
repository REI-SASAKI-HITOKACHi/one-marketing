#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SMS送信リストで、**返信をくださったお客様の行に色を付ける**。

オーナー指示（2026-09-19 MTG／3-3【B】No.5）：

> 返信のあるお客様が視覚的に判るように設定しておいてほしい

## どの列で「返信あり」と見るか

**1列では足りません。** 返信の印が、タブごとに別の列に散っているためです。

| タブ | 見る列 |
|---|---|
| `冬季見込み客_2026` | `送信済み`＝返信あり ／ `返信メモ` ／ `返信の分類` |
| `お詫びSMS_20260912` | `送信済み`＝返信あり ／ **`元の状態`＝返信あり** ／ `返信メモ` ／ `返信の分類` |

**お詫びタブは `元の状態` を見ないと2名落ちます**（堀江さま・黒田さま。`送信済み` は「送信済み」のまま）。

## ★ ルールは先頭（index 0）に入れること

`冬季見込み客_2026` には**条件付き書式が66本**すでに入っていて、その多くが
`=$F6<>""`（本文のある行ぜんぶ）で背景色を塗っています。
**条件付き書式は先に当たったものが勝つ**ので、末尾に足すと**緑は一生表示されません。**

## 控え

**タブの複製ではなく、いまのルールを JSON で `data/backup/` に書き出します。**
書式だけの変更なので、こちらのほうが正確に戻せます（タブも増えません）。

## 使い方

    . ~/.config/one-hitter/line.env
    python3 tools/henshin-iro.py                  # 調べるだけ（既定）
    python3 tools/henshin-iro.py --confirm WRITE  # 控えを取ってからルールを入れる
"""

import datetime
import importlib.util
import json
import os
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _mod(name, path):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


sc = _mod("sc", "sheets_client.py")

SS = "1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64"
MIDORI = {"red": 0.788, "green": 0.902, "blue": 0.788}   # 薄い緑 #C9E6C9
INJI = "【返信あり】薄い緑"                                 # 目印。二度足しを止めるのに使う

TAIGI = [
    # (タブ, 見出しの行, 列数, 条件式)
    ("冬季見込み客_2026", 5, 27,
     '=OR($E6="返信あり",$G6<>"",$AA6<>"")'),
    ("お詫びSMS_20260912", 3, 9,
     '=OR($D4="返信あり",$F4="返信あり",$G4<>"",$I4<>"")'),
]

WRITE = ("--confirm" in sys.argv and "WRITE" in sys.argv)


def main():
    tok = sc.access_token(sc.load_credentials())
    m = sc.call(tok, f"/{SS}", query={
        "fields": "sheets(properties(sheetId,title,gridProperties),conditionalFormats)"})
    ha = {s["properties"]["title"]: s for s in m["sheets"]}

    hikae, reqs = {}, []
    for tab, head_row, cols, shiki in TAIGI:
        s = ha.get(tab)
        if not s:
            print(f"🛑 {tab} が見つかりません")
            continue
        gid = s["properties"]["sheetId"]
        rows = s["properties"].get("gridProperties", {}).get("rowCount", 1000)
        ima = s.get("conditionalFormats", []) or []
        hikae[tab] = ima
        aru = [i for i, cf in enumerate(ima)
               if shiki in json.dumps(cf, ensure_ascii=False)]
        print(f"\n===== {tab} =====")
        print(f"  いまの条件付き書式: {len(ima)}本")
        if aru:
            print(f"  ○ 同じ条件のルールが {aru} 番目にすでにあります。足しません")
            continue
        # 背景色を塗る既存ルールが前にあると、末尾に足しても表示されない
        nuru = sum(1 for cf in ima
                   if "backgroundColor" in json.dumps(cf))
        print(f"  うち背景色を塗るもの: {nuru}本 → **先頭（index 0）に入れます**")
        print(f"  条件: {shiki}")
        print(f"  範囲: A{head_row+1}:{chr(64+cols) if cols<=26 else 'AA'}{rows}（1行=1色）")
        reqs.append({"addConditionalFormatRule": {
            "index": 0,
            "rule": {
                "ranges": [{"sheetId": gid,
                            "startRowIndex": head_row, "endRowIndex": rows,
                            "startColumnIndex": 0, "endColumnIndex": cols}],
                "booleanRule": {
                    "condition": {"type": "CUSTOM_FORMULA",
                                  "values": [{"userEnteredValue": shiki}]},
                    "format": {"backgroundColor": MIDORI},
                },
            }}})

    if not WRITE:
        print("\n書き込みません（調べただけ）。実行するには: --confirm WRITE")
        return 0
    if not reqs:
        print("\n入れるものがありません。")
        return 0

    p = os.path.join(ROOT, "data", "backup",
                     f"joken-tsuki-shoshiki-{datetime.datetime.now():%Y%m%d-%H%M%S}.json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(hikae, f, ensure_ascii=False, indent=2)
    print(f"\nいまのルールを {os.path.relpath(p, ROOT)} に書き出しました（これが控えです）")

    sc.call(tok, f"/{SS}:batchUpdate", "POST", {"requests": reqs})
    print(f"{len(reqs)}本のルールを先頭に入れました。")
    print("※ 既存のルールは1本も消していません。前に1本ずつ足しただけです。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
