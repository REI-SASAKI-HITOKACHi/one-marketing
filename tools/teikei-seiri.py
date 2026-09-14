#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""『【毎月更新】リピート/業務提携』タブの後片付け。2つだけやる。

## 1. 株式会社テック山口 を提携先に追加し、6/17・8/2 の2件を紐づける

依頼 `20260914-02-crm`（オーナー指示 9/14 15:5x）。
和真さんの説明：「山口様は株式会社テック山口。元はおそうじ本舗で奥様のご自宅エアコン、
その後ワンヒッターで株式会社テック山口様からお仕事をいただいている」。
**＝本舗→自社への転換成功事例であり、業務提携先でもある。**

**過去行の氏名は書き換えない。**`◯月_売上/顧客` の「山口様」はそのまま残す。
法人名は**この提携タブの新しい行と備考**で紐づける。

## 2. BR列（「総合計」の列）に残っている古い平均単価を消す

9/14 に売上23〜32の列を足したとき、BS列に件数を数える新しい平均単価を入れた。
BR列には `=BQ7/19` のような**手打ちの割る数**の式が残っていて、新旧の平均単価が
二重に見える状態。CMO 判断（9/14 08:5x）で**消してよい**。
BR2（総合計 `=SUM(BQ2:BQ101)`）は残す。

## 使い方

    . ~/.config/one-hitter/line.env
    python3 tools/teikei-seiri.py                  # 計画を出すだけ（既定）
    python3 tools/teikei-seiri.py --confirm WRITE  # 実行する（控えタブを取ってから）
"""

import datetime
import importlib.util
import os
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("sc", os.path.join(ROOT, "tools", "sheets_client.py"))
sc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sc)

SS = "1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64"
TAB = "【毎月更新】リピート/業務提携"
WRITE = ("--confirm" in sys.argv and "WRITE" in sys.argv)

KAISHA = "株式会社テック山口"
BIKOU = ("台帳では「山口様」（C0878）。2026-09-14 オーナー確認で株式会社テック山口と判明。"
         "本舗→自社への転換成功事例。過去行の氏名は変更していない")
URIAGE = [("2026/06/17", 149000), ("2026/08/02", 91740)]

TOTAL_COL = 69   # BQ 合計
SOUGOU_COL = 70  # BR 総合計（2行目だけ残す）
PAIRS = 32


def a1(col):
    s = ""
    while col:
        col, r = divmod(col - 1, 26)
        s = chr(65 + r) + s
    return s


def main():
    tok = sc.access_token(sc.load_credentials())

    def get(rng, mode="FORMULA"):
        return sc.call(tok, f"/{SS}/values/{urllib.parse.quote(TAB + '!' + rng, safe='')}",
                       query={"valueRenderOption": mode}).get("values", [])

    meta = sc.call(tok, f"/{SS}?fields=sheets.properties")
    gid = [s["properties"]["sheetId"] for s in meta["sheets"]
           if s["properties"]["title"] == TAB][0]
    rows = get("A1:BU101")

    def cell(r, c):
        rr = rows[r - 1] if r - 1 <= len(rows) else []
        rr = rows[r - 1] if r - 1 < len(rows) else []
        return str(rr[c - 1]).strip() if c - 1 < len(rr) else ""

    namae2gyou = {}
    for r in range(2, 101):
        n = cell(r, 2)
        if n:
            namae2gyou[n] = r

    # ---- 1. テック山口 ----
    if KAISHA in namae2gyou:
        print(f"すでに「{KAISHA}」の行があります（行{namae2gyou[KAISHA]}）。追加しません。")
        shin_row = None
    else:
        shin_row = max(namae2gyou.values()) + 1
        print(f"追加する行: {shin_row}  {KAISHA}")
        for i, (d, k) in enumerate(URIAGE, 1):
            print(f"  売上{i}: {a1(3+2*i)}{shin_row}={d}  {a1(4+2*i)}{shin_row}=¥{k:,}")
        print(f"  備考: {BIKOU}")

    # ---- 2. BR列の古い平均単価 ----
    kesu = []
    for r in range(3, 101):
        f = cell(r, SOUGOU_COL)
        if f:
            kesu.append((r, f))
    print(f"\n消すセル（BR3〜BR101 の古い平均単価）: {len(kesu)}件")
    for r, f in kesu:
        print(f"  BR{r} = {f}   ← {cell(r,2) or '(企業名なし)'}")
    print("  ※ BR2（総合計）は残します:", cell(2, SOUGOU_COL))

    if not WRITE:
        print("\n書き込みません（計画のみ）。実行するには: --confirm WRITE")
        return 0

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
    sc.call(tok, f"/{SS}:batchUpdate", "POST",
            {"requests": [{"duplicateSheet": {"sourceSheetId": gid,
                                              "newSheetName": f"控え_業務提携_{stamp}"}}]})
    print(f"\n控えタブを作りました: 控え_業務提携_{stamp}")

    data = []
    if shin_row:
        gyou = [KAISHA, "", BIKOU]
        for d, k in URIAGE:
            gyou += [d, k]
        data.append({"range": f"{TAB}!B{shin_row}:{a1(4+2*len(URIAGE))}{shin_row}",
                     "values": [gyou]})
        uri = "+".join(f"{a1(4+2*p)}{shin_row}" for p in range(1, PAIRS + 1))
        hi = ",".join(f"{a1(3+2*p)}{shin_row}" for p in range(1, PAIRS + 1))
        data.append({"range": f"{TAB}!{a1(TOTAL_COL)}{shin_row}", "values": [[f"={uri}"]]})
        data.append({"range": f"{TAB}!{a1(TOTAL_COL+2)}{shin_row}",
                     "values": [[f'=IF(COUNTA({hi})=0,"",{a1(TOTAL_COL)}{shin_row}/COUNTA({hi}))']]})
    for r, _ in kesu:
        data.append({"range": f"{TAB}!{a1(SOUGOU_COL)}{r}", "values": [[""]]})
    sc.call(tok, f"/{SS}/values:batchUpdate", "POST",
            {"valueInputOption": "USER_ENTERED", "data": data})
    print(f"書き込みました: {len(data)}箇所")
    return 0


if __name__ == "__main__":
    sys.exit(main())
