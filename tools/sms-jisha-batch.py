#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""自社名義の「次に送る人」を洗い出して、**送ってよいかを機械で確かめる**。

## 何を見るか（1つでも落ちたら、その人は出さない）

1. **宛先の名義** … 台帳の「最新の施工の名義」と `meigi_hyou()` で照合。
   **シートの `送信系統` 列は信じない**（2026-09-11 の事故の原因はこの列だった）
2. **本文の中身** … 自社の文面に本舗のもの（店名・本舗の受付番号）が混ざっていないか
3. **本文があるか** … 空の行は送れない

## 対象

| タブ | 条件 |
|---|---|
| `冬季見込み客_2026` | 送信系統=自社 ／ 配信区分=送信可 ／ 送信済み列が空 |
| `お詫びSMS_20260912` | 送信済み列が空（＝まだ送り直していない行） |

## 使い方

    . ~/.config/one-hitter/line.env
    python3 tools/sms-jisha-batch.py            # 一覧と検算
    python3 tools/sms-jisha-batch.py --本文     # 本文もそのまま出す（長い）

**このツールは何も書き込みません。送信もしません。** 下書きの確認だけです。
"""

import importlib.util
import math
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
UNIT = 70          # KDDI：1通＝70文字
PRICE = 11.0       # 税込11円/通
HONBUN = "--本文" in sys.argv


def yomu(tok, tab, head_row):
    v = sc.call(tok, f"/{SS}/values/"
                + urllib.parse.quote(f"{tab}!A{head_row}:AA1200", safe="")).get("values", [])
    head = v[0]
    ix = {c: i for i, c in enumerate(head)}
    out = []
    for n, r in enumerate(v[1:], start=head_row + 1):
        # ★ここで dict に固めること。
        #   クロージャ（def g(k): ... r ...）を返すと、**全行が最後の行を指す**。
        #   2026-09-19、それで「全員が同じ本文」になる一覧を作りかけた。
        d = {c: (str(r[i]).strip() if i < len(r) else "") for c, i in ix.items()}
        if not d.get("顧客名") and not d.get("電話番号"):
            continue
        out.append((n, d))
    return out


def tsuu(s):
    return max(1, math.ceil(len(s) / UNIT))


def main():
    tok = sc.access_token(sc.load_credentials())
    hyou, riyuu = meigi.hyou_yomu()
    if hyou is None:
        # ★読めない＝照合できない＝送らない。握りつぶさない
        print(f"🛑 台帳を読めません → {riyuu}")
        print("   照合できないので、このバッチは出せません。")
        return 1

    taishou = []

    for n, d in yomu(tok, "冬季見込み客_2026", 5):
        if d.get("送信系統") == "自社" and d.get("配信区分") == "送信可" and not d.get("送信済み"):
            taishou.append(("冬季見込み客_2026", n, d))
    for n, d in yomu(tok, "お詫びSMS_20260912", 3):
        if not d.get("送信済み"):
            taishou.append(("お詫びSMS_20260912", n, d))

    print(f"次に送る候補: {len(taishou)}名")

    okuru, tomeru = [], []
    for tab, n, d in taishou:
        name, tel, body = d.get("顧客名", ""), d.get("電話番号", ""), d.get("送信する本文", "")
        warui = []
        # ① 宛先の名義（列ではなく台帳）
        mg = meigi.shiraberu(hyou, tel, name)
        if not mg or not mg[0]:
            warui.append(("宛先", "台帳と照合できない（最新の施工が引けない）"))
        elif mg[0] != "自社":
            warui.append(("宛先", f"台帳の名義は「{mg[0]}」。自社の文面は送れない"))
        # ② 本文の中身
        if not body:
            warui.append(("本文", "空。送る本文がない"))
        else:
            for w in meigi.honbun_ihan("自社", body):
                warui.append(("本文", w))
        rec = {"タブ": tab, "行": n, "名": name, "tel": tel, "本文": body,
               "名義": (mg[0] if mg else None), "最終施工": (mg[1] if mg else None)}
        (tomeru if warui else okuru).append((rec, warui))

    print(f"\n★ 送れる: {len(okuru)}名 ／ 🛑 止める: {len(tomeru)}名")

    if tomeru:
        print("\n===== 🛑 出さない行 =====")
        for rec, warui in tomeru:
            print(f"  {rec['タブ']} 行{rec['行']} {rec['名']}")
            for doko, why in {(a, b) for a, b in warui}:
                print(f"      [{doko}] {why}")

    if okuru:
        naga = sorted(len(r["本文"]) for r, _ in okuru)
        total = sum(tsuu(r["本文"]) for r, _ in okuru)
        print("\n===== 送れる行の内訳 =====")
        for rec, _ in okuru:
            print(f"  {rec['タブ']:<20} 行{rec['行']:>4} {rec['名'][:16]:<18} "
                  f"{len(rec['本文']):>4}文字 {tsuu(rec['本文'])}通  最終施工 {rec['最終施工']}")
        print(f"\n文字数：最短 {naga[0]} / 中央 {naga[len(naga)//2]} / 最長 {naga[-1]}")
        print(f"KDDI で送った場合：{total}通 × {PRICE:.0f}円 = {total*PRICE:,.0f}円"
              f"（1人あたり {total/len(okuru):.2f}通）")
        print("※ いまは和真さんの手送りなので、この費用はかかりません。KDDI に回したときの目安です。")
        if HONBUN:
            for rec, _ in okuru:
                print(f"\n--- {rec['タブ']} 行{rec['行']} {rec['名']} ---")
                print(rec["本文"])

    print("\n何も書き込んでいません。送信もしていません。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
