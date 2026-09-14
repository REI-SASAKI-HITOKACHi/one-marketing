#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""広告文と着地ページの記載が食い違っていないかを実地で見る。

価格や実績値の食い違いは Google の審査落ちの定番。**配信前に必ず通す。**
広告文は data/ads/段0-広告文.md、着地ページは本番のHTMLを取ってきて突き合わせる。

  python3 tools/check-ad-consistency.py

ブラウザ担当が 2026-09-15 に手で行った突合を、そのまま道具にしたもの。
"""
import re, sys, urllib.request, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
ADS_MD = ROOT / "data" / "ads" / "段0-広告文.md"
PAGES = {
    "aircon": "https://lp.onehitter.jp/aircon/",
    "mizumawari": "https://lp.onehitter.jp/mizumawari/",
}

# 本文に出てはいけないもの。値と、なぜ駄目かの理由。
KINSHI = {
    "98.8": "根拠と一致しない（正は98.6%＝209名中206名）",
    "9,800": "旧・税抜の価格。税込10,780円が正（パンフレットPDF）",
    "9800円": "旧・税抜の価格",
}
# 広告文に出したら、着地ページにも載っていなければならないもの
TAIOU = {
    "10,780": "税込の入口価格。広告に出すならページにも同じ数字が要る",
    "98.6": "満足度。実績値を広告に出すと Google は根拠の記載を見る",
}
# 98.6 を出すなら、根拠（期間・母数）もページ側に要る
KONKYO = ["2023年", "アンケート"]


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "one-hitter-check/1.0"})
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")


def main():
    if not ADS_MD.exists():
        print(f"広告文が見つかりません: {ADS_MD}", file=sys.stderr)
        return 2
    ad = ADS_MD.read_text(encoding="utf-8")

    ng, warn = [], []

    # 1. 広告文そのものに禁止語が無いか
    for v, why in KINSHI.items():
        if v in ad:
            ng.append(f"広告文に '{v}' … {why}")

    pages = {}
    for name, url in PAGES.items():
        try:
            pages[name] = get(url)
            print(f"{name}: 取得 OK（{len(pages[name]):,} バイト） {url}")
        except Exception as e:
            ng.append(f"{name}: 取得できません（{e}） {url}")

    for name, html in pages.items():
        # 2. ページに禁止語が残っていないか
        for v, why in KINSHI.items():
            n = html.count(v)
            if n:
                ng.append(f"{name} に '{v}' が {n} 件 … {why}")
        # 3. 広告に出す値が、ページにも載っているか
        for v, why in TAIOU.items():
            if v in ad and v not in html:
                ng.append(f"{name} に '{v}' が無い … {why}")
        # 4. 98.6 を出すなら根拠も
        if "98.6" in ad and "98.6" in html:
            miss = [k for k in KONKYO if k not in html]
            if miss:
                warn.append(f"{name}: 98.6% の根拠が見当たらない（{' / '.join(miss)}）")

    for w in warn:
        print("⚠ " + w)
    if ng:
        print("\n食い違いがあります。配信しないでください：", file=sys.stderr)
        for x in ng:
            print("  ✗ " + x, file=sys.stderr)
        return 1
    print("\n✅ 広告文と着地ページの記載に食い違いはありません。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
