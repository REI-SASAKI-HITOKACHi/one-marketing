#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SMSの一斉配信から外した「お客様が会社そのもの」の方を、`法人_別対応` タブに分けて残す。

CMO（2026-09-15 09:04）：

> 外した3件は捨てないでください。`法人_別対応` として別リストに分けて、web-inflow へ回します。

外した理由は費用ではありません。**3通案の本文が「追い焚き配管」まで含む住居向け**なので、
法人の窓口に届くと雑に見えるからです。三井不動産・長谷工は、今後の取引額のほうが
231円よりはるかに大きい相手です。

外す／外さないの線引きは `data/sms-houjin-hantei.txt`（[別対応] の並び）。
判定の仕組みは `tools/sms-honpo-3tsu.py` の `houjin_hantei()`。

## 使い方

    . ~/.config/one-hitter/line.env
    python3 tools/houjin-betsutaiou-tab.py                  # 中身を見るだけ
    python3 tools/houjin-betsutaiou-tab.py --confirm WRITE  # タブを作る／作り直す
"""

import importlib.util
import os
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("sc", os.path.join(ROOT, "tools", "sheets_client.py"))
sc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sc)

s3 = importlib.util.spec_from_file_location("s3", os.path.join(ROOT, "tools", "sms-honpo-3tsu.py"))
sms = importlib.util.module_from_spec(s3)
s3.loader.exec_module(sms)

SS = "1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64"
MOTO = "冬季見込み客_2026"
TAB = "法人_別対応"
HEAD_ROW = 5

MIDASHI = ["顧客名", "電話番号", "郵便番号", "最終施工日", "施工メニュー（内訳）",
           "受注回数", "累計売上", "いまの配信区分", "今回の396名から外したか",
           "法人と見た理由", "元の行"]

WRITE = ("--confirm" in sys.argv and "WRITE" in sys.argv)


def main():
    tok = sc.access_token(sc.load_credentials())
    v = sc.call(tok, f"/{SS}/values/{urllib.parse.quote(MOTO + f'!A{HEAD_ROW}:AH1200', safe='')}"
                ).get("values", [])
    h = v[0]
    ix = {c: i for i, c in enumerate(h)}

    def g(r, k):
        i = ix.get(k)
        return str(r[i]).strip() if i is not None and i < len(r) else ""

    kettei = sms.hantei_yomu()
    tv = sc.call(tok, f"/{SS}/values/{urllib.parse.quote(sms.TEIKEI_TAB + '!B2:B101', safe='')}"
                 ).get("values", [])
    teikei = {row[0].strip() for row in tv if row and row[0].strip()}

    gyou = []
    for n, r in enumerate(v[1:], start=HEAD_ROW + 1):
        if g(r, "送信系統") != "本舗" or g(r, "送信済み"):
            continue
        namae = g(r, "顧客名")
        atsukai, riyuu = sms.houjin_hantei(namae, teikei, kettei)
        if atsukai != "別対応":
            continue
        ku = g(r, "配信区分")
        # ★「今回の396名から外した」のは、もともと送信可だった行だけ。
        #   それ以外は前から対象外（固定電話・楽ラクーン経由など）で、今回の判断とは別。
        soto = "はい（送信可だった）" if ku == "除外" and "法人_別対応へ" in g(r, "送らない理由") \
            else "いいえ（もともと対象外）"
        gyou.append([namae, g(r, "電話番号"), g(r, "郵便番号"), g(r, "最終施工日"),
                     g(r, "施工メニュー（内訳）"), g(r, "受注回数"), g(r, "累計売上"),
                     ku, soto, riyuu, str(n)])

    print(f"{TAB} に入れるもの: {len(gyou)}件")
    for x in gyou:
        print(f"  {x[0]:<28} {x[8]:<22} {x[9]}")
    if not WRITE:
        print("\n書き込みません。作るには: --confirm WRITE")
        return 0

    meta = sc.call(tok, f"/{SS}?fields=sheets.properties")
    aru = [s["properties"] for s in meta["sheets"] if s["properties"]["title"] == TAB]
    if not aru:
        sc.call(tok, f"/{SS}:batchUpdate", "POST",
                {"requests": [{"addSheet": {"properties": {"title": TAB}}}]})
        print(f"タブを作りました: {TAB}")
    atama = [
        ["法人_別対応 ／ SMSの一斉配信から外した「お客様が会社そのもの」の方"],
        ["外した理由は費用ではありません。3通案の本文が追い焚き配管まで含む住居向けで、"
         "法人の窓口に届くと雑に見えるためです（CMO 2026-09-15）。"],
        ["web-inflow の法人向け文面へ回します。線引きは data/sms-houjin-hantei.txt。"],
        [],
        MIDASHI,
    ]
    sc.call(tok, f"/{SS}/values/{urllib.parse.quote(TAB + '!A1', safe='')}",
            "PUT", {"values": atama + gyou}, query={"valueInputOption": "RAW"})
    print(f"書きました: 見出し + {len(gyou)}行")
    print("※ 電話番号は文字列のまま書いています（RAW・先頭の0が消えません）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
