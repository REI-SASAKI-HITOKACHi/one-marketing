#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""シートを書き換える前の控えを、**スプシのタブではなく git に**取る。

## なぜこの形か

もともとは同じシート内にタブを複製していた。サービスアカウントに Drive の
保存容量が無く、`copy_file` が使えなかったため（2026-09-14 の申し送り）。

**その結果タブが77本まで膨らみ、オーナーから「控え用のシートも多すぎ」と指摘が出た**
（2026-09-19）。**これからは git に置く**（`20260919-02-crm`・全スレ共通）。

| | タブに複製 | git に置く |
|---|---|---|
| 増えると | **オーナーが目的のタブを探せなくなる** | リポジトリの中なので邪魔にならない |
| 誰がいつ何を控えたか | タブ名の日時だけ | **コミットで分かる** |
| 戻し方 | 手でコピー | `tools/restore-sheet-tab.py <タブ名> --jikkou` |

## 使い方（書き換えるツールの中から）

    import hikae
    p = hikae.git_ni_toru(tok, "【毎月更新】リピート/業務提携")
    # → data/sheets/backup/<タブ名>-<日時>.json.gz を作って、パスを返す
    # ★読み直して検査するところまでやる。空なら例外を投げて、書き換えを止める。

**控えが取れなかったら書き換えない。** 例外をそのまま上に投げること。
"""

import datetime
import gzip
import json
import os
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "sheets", "backup")
SS = "1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64"


def _sc():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "sc", os.path.join(ROOT, "tools", "sheets_client.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def git_ni_toru(tok, tab, han="A1:BZ2000"):
    """タブの中身を data/sheets/backup/ に gzip で落とし、読み直して検査する。

    戻り値はリポジトリからの相対パス。**空だったら例外**（控えたつもりになるのが一番危ない）。
    """
    sc = _sc()
    rows = sc.call(tok, f"/{SS}/values/"
                   + urllib.parse.quote(f"{tab}!{han}", safe="")).get("values", [])
    n = sum(1 for r in rows if r and any(str(c).strip() for c in r))
    if n == 0:
        raise RuntimeError(f"{tab}: 中身が空。控えを作らない（書き換えも止めること）")
    os.makedirs(OUT, exist_ok=True)
    namae = f'{tab.replace("/", "_")}-{datetime.datetime.now():%Y%m%d-%H%M%S}.json.gz'
    p = os.path.join(OUT, namae)
    with gzip.open(p, "wt", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False)
    # 読み直す。書けたことと、読めることは別
    with gzip.open(p, "rt", encoding="utf-8") as f:
        yomi = json.load(f)
    if len(yomi) != len(rows):
        raise RuntimeError(f"{p}: 書いた行数と読めた行数が違う（{len(rows)} / {len(yomi)}）")
    rel = os.path.relpath(p, ROOT)
    print(f"控えを git に取りました: {rel}（{n}行 / {os.path.getsize(p):,} bytes・読み直し済み）")
    print("  ※ ★コミットを忘れないこと。git に入って初めて控えです")
    return rel
