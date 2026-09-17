#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`◯月_支出/成績` の科目別集計が、明細の最終行まで届いているかを調べる。

## なぜ要るか

2026-09-17、planning から「6月と7月の広告費が、集計欄のほうが明細より少ない」と指摘があった
（`20260917-01-crm`）。調べると **原因は金額ではなく「式の範囲」** だった。

```
6月  F72 合計    =(SUM(F2:F71))-J80      ← 明細の最終行 71 まで届いている
     F77 広告費  =SUMIF($E$2:$E$70,…)    ← 70 で止まっている。71行目の ¥1,320 が落ちる
```

**明細を下に足しても、科目別の集計式の範囲は自動では伸びません。**
このタブは「行を足して使う」形なので、**足すたびに、どれかの科目が静かに小さくなります。**

## 何に効くか（ここを間違えないこと）

**営業利益には効きません。** 販管費は `合計(F72)` から作られていて、こちらは範囲が届いています。
**効くのは「科目ごとの内訳の表示」だけです。** ただし例外が1つあります。

- `人件費` の集計セルは **原価合計（B列）と販管費の式の両方に入っています。**
  ここが落ちると、**原価が小さく・販管費が大きく**出ます（営業利益は相殺されて動きません）。

## 使い方

    . ~/.config/one-hitter/line.env
    python3 tools/shukei-hani-check.py                  # 調べるだけ（既定）
    python3 tools/shukei-hani-check.py --confirm WRITE  # 範囲を明細の最終行まで伸ばす

`--confirm WRITE` の前に、**変更前の式を `data/backup/shukei-shiki-<日時>.json` に必ず書き出します。**
（Driveのコピーはサービスアカウントに容量が無くて取れないため。`docs/crm-savedata.md` 2026-09-15）
"""

import datetime
import importlib.util
import json
import os
import re
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
TABS = [f"{m}月_支出/成績" for m in range(1, 13)]
# 明細は A〜H。ここに行が足されていく
MEISAI_COLS = "ABCDEFGH"
WRITE = ("--confirm" in sys.argv and "WRITE" in sys.argv)

# 「F2:F70」「$E$2:$E$49」のような、同一タブ内の縦方向の範囲
HANI = re.compile(r"(?<![\w!:$])(\$?)([A-H])(\$?)(\d+)\s*:\s*(\$?)([A-H])(\$?)(\d+)(?![\w(])")


def col_i(c):
    return ord(c) - 64


def a1(col, row):
    s = ""
    while col:
        col, r = divmod(col - 1, 26)
        s = chr(65 + r) + s
    return s + str(row)


def saigo_no_gyou(rows):
    """明細（A〜H）に中身がある最後の行。**A列の連番だけの行は数えない。**"""
    last = 1
    for i, r in enumerate(rows, start=1):
        # B〜H のどれかに中身があれば「明細の行」
        if any(str(c).strip() for c in r[1:8]):
            last = i
    return last


def shirabe(tok, tab):
    q = urllib.parse.quote(f"{tab}!A1:Z200", safe="")
    shiki = sc.call(tok, f"/{SS}/values/{q}", query={"valueRenderOption": "FORMULA"}).get("values", [])
    atai = sc.call(tok, f"/{SS}/values/{q}", query={"valueRenderOption": "FORMATTED_VALUE"}).get("values", [])
    # 明細の最終行は、集計ブロックより上で見る。集計ブロックは「合計」の行から始まる
    goukei_gyou = None
    for i, r in enumerate(shiki, start=1):
        for c in r:
            if str(c).strip() == "合計":
                goukei_gyou = i
                break
        if goukei_gyou:
            break
    meisai = shiki[: (goukei_gyou - 1) if goukei_gyou else len(shiki)]
    last = saigo_no_gyou(meisai)

    warui = []
    for i, r in enumerate(shiki, start=1):
        for j, c in enumerate(r, start=1):
            c = str(c)
            if not c.startswith("="):
                continue
            for m in HANI.finditer(c):
                r1, r2 = int(m.group(4)), int(m.group(8))
                if m.group(2) != m.group(6):      # 縦の範囲だけ見る（A1:H1 のような横は除く）
                    continue
                if r1 > 2 or r2 >= last:          # 明細の頭から始まって、最終行に届いていないものだけ
                    continue
                v = ""
                if i - 1 < len(atai) and j - 1 < len(atai[i - 1]):
                    v = str(atai[i - 1][j - 1])
                warui.append({"セル": a1(j, i), "式": c, "いまの値": v,
                              "範囲": m.group(0), "範囲の終わり": r2, "明細の最終行": last})
                break
    return last, warui, shiki


def naoshita_shiki(shiki, last):
    """明細の頭から始まる縦の範囲だけを、最終行まで伸ばす。**他は1文字も触らない。**"""
    def sub(m):
        r1, r2 = int(m.group(4)), int(m.group(8))
        if m.group(2) != m.group(6) or r1 > 2 or r2 >= last:
            return m.group(0)
        return f"{m.group(1)}{m.group(2)}{m.group(3)}{r1}:{m.group(5)}{m.group(6)}{m.group(7)}{last}"
    return HANI.sub(sub, shiki)


def main():
    tok = sc.access_token(sc.load_credentials())
    subete, naosu = {}, []
    for tab in TABS:
        last, warui, _ = shirabe(tok, tab)
        subete[tab] = {"明細の最終行": last, "届いていない式": warui}
        print(f"\n===== {tab}　明細の最終行 {last} =====")
        if not warui:
            print("  すべて届いています")
            continue
        for w in warui:
            kamoku = w["式"]
            print(f"  ⚠️ {w['セル']:>5}  {w['範囲']:>12} → {last} まで伸ばす"
                  f"（いま {w['いまの値']}）")
            print(f"        {kamoku[:100]}")
            naosu.append((tab, w["セル"], w["式"], naoshita_shiki(w["式"], last)))

    print(f"\n★ 届いていない式：{len(naosu)}件")
    print("※ 販管費・営業利益は『合計』から作られており、そちらの範囲は届いています。")
    print("※ ただし **人件費の集計セルは原価合計と販管費の両方に入っています**。落ちると内訳がずれます。")

    if not WRITE:
        p = os.path.join(ROOT, "data", "backup",
                         f"shukei-shiki-{datetime.datetime.now():%Y%m%d-%H%M%S}-調査のみ.json")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(subete, f, ensure_ascii=False, indent=2)
        print(f"\n調べただけです。変更前の式を {os.path.relpath(p, ROOT)} に残しました。")
        print("直すには: --confirm WRITE")
        return 0

    # ---- 書く前に、変更前の式を必ず残す ----
    p = os.path.join(ROOT, "data", "backup",
                     f"shukei-shiki-{datetime.datetime.now():%Y%m%d-%H%M%S}.json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump({"変更前": subete,
                   "変更する式": [{"タブ": t, "セル": c, "前": a, "後": b} for t, c, a, b in naosu]},
                  f, ensure_ascii=False, indent=2)
    print(f"\n変更前の式を {os.path.relpath(p, ROOT)} に書き出しました（これが控えです）")

    data = [{"range": f"{t}!{c}", "values": [[b]]} for t, c, a, b in naosu]
    for i in range(0, len(data), 50):
        sc.call(tok, f"/{SS}/values:batchUpdate", "POST",
                {"valueInputOption": "USER_ENTERED", "data": data[i:i + 50]})
    print(f"{len(data)}個の式の範囲を伸ばしました。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
