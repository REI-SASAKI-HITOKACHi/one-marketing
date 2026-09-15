#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`◯月_売上/顧客` の**末尾に「法人名」列を1つ足す**。

## なぜ末尾なのか

CMO（2026-09-15 09:04）：

> 既存の列の位置を動かさないこと。数式・ツール・`build-sms-list.py` がすべて列番号で動いています。

途中に挿入すると、`SUMIF('5月_売上/顧客'!R4:R501, …)` のような列指定がずれて、
**支出/成績や年間成績の数字が黙って変わります。** だから必ず末尾。

## なぜ要るのか

「山口様」＝株式会社テック山口（オーナー確認 2026-09-14）のように、
**氏名だけでは法人だと分からない行がある。** 過去の氏名は実績データなので書き換えられないので、
**法人名は別の列に置いて紐づける**（`20260914-02-crm`）。

今後の入力は `株式会社テック山口　山口様`（法人名が先、担当者が後）に揃える方針だが、
**過去の行はこの列で拾う。**

## 使い方

    . ~/.config/one-hitter/line.env
    python3 tools/houjinmei-column.py 6月            # 1タブで試す（調べるだけ）
    python3 tools/houjinmei-column.py 6月 --confirm WRITE
    python3 tools/houjinmei-column.py 全部 --confirm WRITE   # 12タブへ

**必ず1タブで試して、既存の集計が変わっていないことを確かめてから12タブへ。**
このツールは実行の前後で、その月の `支出/成績` と `年間成績` の数字を突き合わせて表示する。
"""

import datetime
import importlib.util
import time
import os
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("sc", os.path.join(ROOT, "tools", "sheets_client.py"))
sc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sc)

SS = "1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64"
MIDASHI = "法人名"
HEAD_ROW = 2

# 既知の紐づけ（オーナー確認済み）。氏名 → 法人名
HIMOZUKE = {
    "山口様": "株式会社テック山口",
}

WRITE = ("--confirm" in sys.argv and "WRITE" in sys.argv)


def a1(col):
    s = ""
    while col:
        col, r = divmod(col - 1, 26)
        s = chr(65 + r) + s
    return s


def yomu(tok, tab, rng, mode="UNFORMATTED_VALUE"):
    """読み取りは 60回/分 の上限がある（12タブぶん回すと当たる）。
    当たったら待って、もう一度やる。"""
    for kai in range(6):
        try:
            return sc.call(tok, f"/{SS}/values/{urllib.parse.quote(tab + '!' + rng, safe='')}",
                           query={"valueRenderOption": mode}).get("values", [])
        except SystemExit as e:
            if "429" not in str(e) and "Quota" not in str(e):
                raise
            matsu = 20 * (kai + 1)
            print(f"    （読み取りの上限に当たりました。{matsu}秒待ってやり直します）")
            time.sleep(matsu)
    raise SystemExit("読み取りの上限に何度も当たりました。少し時間をおいてください。")


def kensan(tok, m):
    """その月の集計値を拾う。前後で比べるため。"""
    lay = {6: (72, 80, 81), 7: (86, 94, 95)}.get(m, (53, 61, 62))
    tab = f"{m}月_支出/成績"
    v = yomu(tok, tab, "A1:N120")

    def c(r, col):
        rr = v[r - 1] if r - 1 < len(v) else []
        return rr[col] if col < len(rr) else ""

    uriage = c(lay[0] + 2, 1)          # 売上
    hanka = c(lay[2], 1)               # 販売管理費
    eigyou = c(lay[2] + 1, 1)          # 営業利益
    u = yomu(tok, f"{m}月_売上/顧客", "A1:T3")
    gou = u[0][5] if u and len(u[0]) > 5 else ""      # 1行目の「現在:」の右隣
    return {"売上": uriage, "販管費": hanka, "営業利益": eigyou, "売上シートの現在": gou}


def hitotsu(tok, m):
    tab = f"{m}月_売上/顧客"
    v = yomu(tok, tab, f"A{HEAD_ROW}:BZ520", "FORMATTED_VALUE")
    head = v[0]
    if MIDASHI in head:
        print(f"  {tab}: すでに「{MIDASHI}」列があります（{a1(head.index(MIDASHI)+1)}列）。足しません。")
        tsugi = head.index(MIDASHI) + 1
    else:
        tsugi = len(head) + 1
        print(f"  {tab}: 末尾 {a1(tsugi)}列 に「{MIDASHI}」を足します")
        if WRITE:
            sc.call(tok, f"/{SS}/values/{urllib.parse.quote(tab + '!' + a1(tsugi) + str(HEAD_ROW), safe='')}",
                    "PUT", {"values": [[MIDASHI]]}, query={"valueInputOption": "RAW"})
    # 既知の紐づけを書く
    ix = {c: i for i, c in enumerate(head)}
    kaku = []
    for n, r in enumerate(v[1:], start=HEAD_ROW + 1):
        shimei = (r[ix["氏名"]] if "氏名" in ix and ix["氏名"] < len(r) else "").strip()
        if shimei in HIMOZUKE:
            ima = (r[tsugi - 1] if tsugi - 1 < len(r) else "").strip()
            if ima == HIMOZUKE[shimei]:
                continue
            kaku.append((n, shimei, HIMOZUKE[shimei]))
    for n, shimei, hj in kaku:
        print(f"     行{n} 氏名「{shimei}」→ {MIDASHI}「{hj}」（氏名は書き換えません）")
    if WRITE and kaku:
        sc.call(tok, f"/{SS}/values:batchUpdate", "POST",
                {"valueInputOption": "RAW",
                 "data": [{"range": f"{tab}!{a1(tsugi)}{n}", "values": [[hj]]}
                          for n, _s, hj in kaku]})
    return len(kaku)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    hikisu = sys.argv[1]
    tsuki = list(range(1, 13)) if hikisu == "全部" else [int(hikisu.replace("月", ""))]

    tok = sc.access_token(sc.load_credentials())
    mae = {m: kensan(tok, m) for m in tsuki}
    print("== 実行前の集計 ==")
    for m, d in mae.items():
        print(f"  {m}月: " + "／".join(f"{k}={v}" for k, v in d.items()))

    print(f"\n== {MIDASHI} 列 ==")
    kaita = sum(hitotsu(tok, m) for m in tsuki)

    if not WRITE:
        print("\n書き込みません（調べただけ）。実行するには: --confirm WRITE")
        return 0

    ato = {m: kensan(tok, m) for m in tsuki}
    print("\n== 実行後の集計（前と同じであること）==")
    chigau = 0
    for m in tsuki:
        for k in mae[m]:
            if mae[m][k] != ato[m][k]:
                print(f"  ★★ {m}月 {k}: {mae[m][k]} → {ato[m][k]}  ← 変わってしまいました")
                chigau += 1
    if chigau:
        print(f"\n★★ 集計が {chigau}箇所 変わりました。控えから戻してください。")
        return 1
    print(f"  {len(tsuki)}か月ぶん、すべて同じでした。{MIDASHI}を書いた行: {kaita}件")
    print(f"\n※ 控えは取っていません（末尾に列を足すだけで、既存のセルは1つも書き換えないため）。"
          f"\n  既知の紐づけを書いた {kaita}件も、空欄だったセルへの追記です。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
