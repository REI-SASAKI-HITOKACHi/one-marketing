#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`冬季見込み客_2026` の中で、**送信系統と台帳の名義が食い違う行をシート上で止める。**

## なぜこれが要るか

2026-09-11、本舗名義のお客様3名にワンヒッター名義のSMSが届いた。原因は「送信系統」列を
信じてリストを作っていたこと。以来、送信の道具はすべて `meigi_hyou()` で照合してから
本文を作るようにしてある。

**それでも足りない。** CMO（2026-09-15）：

> 止め方は「ツールに任せる」ではなく「シート上でも止まっている」でなければいけません。

和真さんはスマホでこのシートを直接触る。**配信区分を手で「送信可」に戻したら、
道具を通らずに送れてしまう。** だから、食い違う行はシートの側でも止めておく。

## 何をするか

未送信の行を1つずつ、**台帳の「最新の施工の名義」と突き合わせる**。

| 見つかったもの | すること |
|---|---|
| **名義が食い違う**（系統=自社／台帳=本舗、またはその逆） | **配信区分を「保留」にし、理由を書き足す** |
| **台帳で照合できない** | 理由を書き足すだけ（配信区分は触らない） |

**理由は書き足しです。もとの理由（固定電話・楽ラクーン経由など）は消しません。**

## 使い方

    . ~/.config/one-hitter/line.env
    python3 tools/meigi-fuitchi-hold.py                  # 調べるだけ（既定）
    python3 tools/meigi-fuitchi-hold.py --confirm WRITE  # 控えを取ってから直す
"""

import datetime
import importlib.util
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
meigi = _mod("meigi_check", "meigi_check.py")

SS = "1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64"
TAB = "冬季見込み客_2026"
HEAD_ROW = 5
KYOU = datetime.date.today().isoformat()

WRITE = ("--confirm" in sys.argv and "WRITE" in sys.argv)


def a1(col):
    s = ""
    while col:
        col, r = divmod(col - 1, 26)
        s = chr(65 + r) + s
    return s


def main():
    tok = sc.access_token(sc.load_credentials())
    v = sc.call(tok, f"/{SS}/values/{urllib.parse.quote(TAB + f'!A{HEAD_ROW}:AH1200', safe='')}"
                ).get("values", [])
    if not v:
        sys.exit(f"{TAB} を読めません")
    h = v[0]
    ix = {c: i for i, c in enumerate(h)}

    def g(r, k):
        i = ix.get(k)
        return str(r[i]).strip() if i is not None and i < len(r) else ""

    hyou, riyuu = meigi.hyou_yomu()
    if hyou is None:
        sys.exit(f"台帳を読めないので照合できません → {riyuu}")

    kuichigai, dekinai = [], []
    for n, r in enumerate(v[1:], start=HEAD_ROW + 1):
        kei = g(r, "送信系統")
        if kei not in ("自社", "本舗") or g(r, "送信済み"):
            continue
        mi = meigi.shiraberu(hyou, g(r, "電話番号"), g(r, "顧客名"))
        rec = (n, g(r, "顧客名"), kei, g(r, "配信区分"), g(r, "送らない理由"))
        if mi is None:
            dekinai.append(rec + ("",))
        elif mi[0] != kei:
            kuichigai.append(rec + (f"台帳={mi[0]}／最新施工 {mi[1]}",))

    print(f"未送信の行を照合しました。")
    print(f"  ★名義が食い違う: {len(kuichigai)}件  → 配信区分を「保留」にします")
    for n, na, kei, ku, _, why in kuichigai:
        print(f"     行{n} {na}  系統={kei}／{why}  いまの区分={ku}")
    print(f"  台帳で照合できない: {len(dekinai)}件  → 理由を書き足すだけ（区分は触りません）")
    for n, na, kei, ku, _, _w in dekinai[:8]:
        print(f"     行{n} {na}  系統={kei}  いまの区分={ku}")
    if len(dekinai) > 8:
        print(f"     …ほか {len(dekinai)-8}件")

    if not WRITE:
        print("\n直しません（調べただけ）。直すには: --confirm WRITE")
        return 0
    if not kuichigai and not dekinai:
        print("\n直すものがありません。")
        return 0

    meta = sc.call(tok, f"/{SS}?fields=sheets.properties")
    gid = [s["properties"]["sheetId"] for s in meta["sheets"]
           if s["properties"]["title"] == TAB][0]
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    sc.call(tok, f"/{SS}:batchUpdate", "POST",
            {"requests": [{"duplicateSheet": {"sourceSheetId": gid,
                                              "newSheetName": f"控え_冬季見込み客_{stamp}"}}]})
    print(f"\n控えタブを作りました: 控え_冬季見込み客_{stamp}")

    c_ku, c_ri = a1(ix["配信区分"] + 1), a1(ix["送らない理由"] + 1)
    data = []
    for n, _na, kei, _ku, moto, why in kuichigai:
        tsuika = f"名義不一致（送信系統={kei}／{why}）{KYOU} 確認中"
        data.append({"range": f"{TAB}!{c_ku}{n}", "values": [["保留"]]})
        data.append({"range": f"{TAB}!{c_ri}{n}",
                     "values": [[(moto + "／" if moto else "") + tsuika]]})
    for n, _na, _kei, _ku, moto, _why in dekinai:
        tsuika = f"台帳で名義を照合できない（送信前に要確認）{KYOU}"
        if tsuika in moto:
            continue
        data.append({"range": f"{TAB}!{c_ri}{n}",
                     "values": [[(moto + "／" if moto else "") + tsuika]]})
    sc.call(tok, f"/{SS}/values:batchUpdate", "POST",
            {"valueInputOption": "RAW", "data": data})
    print(f"直しました: {len(data)}セル"
          f"（保留にした行 {len(kuichigai)}件／理由を書き足した行 {len(dekinai)}件）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
