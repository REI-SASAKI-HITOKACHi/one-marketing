#!/usr/bin/env python3
"""広告の着地LPに「11月の早期予約は10%お得」の帯（lp/_parts/band-11gatsu.html）を差し込む。

  python3 tools/insert-band.py <ページ名> 元.html 出力.html     # 例: aircon deploy/netlify/aircon/index.html ...

- 位置はヘッダー（.bar）のすぐ下、ファーストビュー（.hero）の前。旧の見た目にも v2 にも入る。
- 条件の文言はページごと（JOKEN）。予約ページの計算（ご依頼の合計が1つのときだけ早期予約割引）と同じ。
- build-site.py は BAND_PAGES のページに自動で入れる。既存4本の配信物は v2 で作り直さないので、
  この道具でコミット済みの deploy/netlify に直接当てる（依頼 20261005-01-lp）。
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PART = ROOT / "lp" / "_parts" / "band-11gatsu.html"
MARK = 'id="nov-band"'

JOKEN = {
    "aircon": "エアコン1台のご依頼",
    "aircon-c": "エアコン1台のご依頼",
    "aircon-d": "エアコン1台のご依頼",
    "aircon-b": "エアコン1台のご依頼",
    "mizumawari": "1箇所のご依頼",
    "mizumawari-b": "1箇所のご依頼",
}


def insert(html: str, page: str) -> str:
    if MARK in html:
        raise SystemExit(f"{page}: すでに帯が入っています（二重に差し込まない）")
    if page not in JOKEN:
        raise SystemExit(f"{page}: 条件の文言（JOKEN）がありません")
    m = re.search(r'\n<(div|section) class="hero">', html)
    if not m:
        raise SystemExit(f"{page}: ファーストビュー（class=\"hero\"）が見つかりません")
    part = re.sub(r"<!--.*?-->\s*", "", PART.read_text(encoding="utf-8"), flags=re.S)
    part = part.replace("{joken}", JOKEN[page])
    return html[:m.start()] + "\n" + part.rstrip("\n") + html[m.start():]


def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    page, src, dst = sys.argv[1], pathlib.Path(sys.argv[2]), pathlib.Path(sys.argv[3])
    out = insert(src.read_text(encoding="utf-8"), page)
    dst.write_text(out, encoding="utf-8")
    print(f"{dst}  （{page}：11月の帯を差し込み）")


if __name__ == "__main__":
    main()
