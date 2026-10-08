#!/usr/bin/env python3
"""LPの文面の小さな直し（依頼 20261008-04-lp）。配信は交通費・浴室の内訳（tools/chuuki-1008.py）と一緒。

  python3 tools/bunmen-1010.py <ページ名> 元.html 出力.html

1. Googleクチコミの件数を書かない（件数は増えて古くなる。LP は23件、実数は25件）。「★5.0」と時点だけ残す
2. （設問の原文待ち）98.6% の脚注の言い回しを、アンケートの元の設問に揃える → web-inflow から原文が届いたら KYAKUCHU に足す

旧の見た目・v2 のどちらにも当たるよう、文字列の置き換えで当てる。1つも当たらないページは何もしない。
★公開はまだ。承認まで deploy/netlify には入れない（build-site.py の BUNMEN_PAGES は空）。
"""
import pathlib
import sys

KENSU = [
    ("Googleクチコミ<br>23件<sup>※2</sup>", "Googleクチコミ<sup>※2</sup>"),
    ("Googleの口コミ<br>23件の平均<sup>※2</sup>", "Googleの口コミ<br>平均<sup>※2</sup>"),
    ("※2 Googleクチコミ 23件・平均★5.0（2026年9月時点）", "※2 Googleクチコミの平均★5.0（2026年9月時点）"),
    ("※2 Googleビジネスプロフィールの評価（2026年9月時点・23件）", "※2 Googleビジネスプロフィールの評価（2026年9月時点）"),
    ("（2026年9月時点・23件・平均★5.0／", "（2026年9月時点・平均★5.0／"),
    ("のクチコミは<b>23件・平均★5.0</b>です", "のクチコミは<b>平均★5.0</b>です"),
    ("※2 Googleクチコミの件数と平均は2026年9月時点のものです（23件・平均★5.0）。", "※2 Googleクチコミの平均は2026年9月時点のものです（★5.0）。"),
    ("★5.0Googleクチコミ 23件（2026年9月時点）", "★5.0Googleクチコミ（2026年9月時点）"),
]
# 98.6% の脚注：設問の原文が届いたら（置き換え前, 置き換え後）を足す
KYAKUCHU: list = []


def apply(doc: str, page: str):
    hits = {}
    for a, b in KENSU + KYAKUCHU:
        n = doc.count(a)
        if n:
            doc = doc.replace(a, b)
            hits[a[:16]] = n
    if "23件" in doc:
        raise SystemExit(f"{page}: まだ「23件」が残っています（言い回しが増えた？）")
    return doc, hits


def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    page, src, dst = sys.argv[1], pathlib.Path(sys.argv[2]), pathlib.Path(sys.argv[3])
    out, hits = apply(src.read_text(encoding="utf-8"), page)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(out, encoding="utf-8")
    print(f"{page:13s} " + ("／".join(f"{k}…×{v}" for k, v in hits.items()) or "該当なし"))


if __name__ == "__main__":
    main()
