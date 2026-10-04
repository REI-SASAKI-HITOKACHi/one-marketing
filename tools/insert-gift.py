#!/usr/bin/env python3
"""年末LPに、ギフトの「お知らせを受け取る」入口（lp/_parts/gift-oshirase.html）を差し込む。

  python3 tools/insert-gift.py 元.html 出力.html

- 差し込む位置は「よくあるご質問」の節の直前（原稿 §1：Voice の直後・FAQ の前）。
- 年末LPの今の見た目（旧）にも v2 にも入る。見つからなければ止める。
- 部品の HTML コメントは落とす（公開物にメモを残さない）。

★掲出はオーナー承認事項（依頼 20261004-02-lp）。承認までは preview/ にだけ出し、
  deploy/netlify には入れない。deploy/netlify に入れると、別の用事の配信で一緒に公開されてしまう。
  承認後は： python3 tools/insert-gift.py deploy/netlify/nenmatsu/index.html deploy/netlify/nenmatsu/index.html
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PART = ROOT / "lp" / "_parts" / "gift-oshirase.html"
MARK = 'id="gift-form"'


def insert(html: str) -> str:
    if MARK in html:
        raise SystemExit("すでにギフトの入口が入っています（二重に差し込まない）")
    faq = html.find("よくあるご質問")
    if faq < 0:
        raise SystemExit("「よくあるご質問」が見つかりません。差し込む位置を決められないので止めます")
    sec = html.rfind("<section", 0, faq)
    if sec < 0:
        raise SystemExit("「よくあるご質問」を含む <section> が見つかりません")
    part = re.sub(r"<!--.*?-->\s*", "", PART.read_text(encoding="utf-8"), flags=re.S)
    return html[:sec] + part + "\n" + html[sec:]


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    src, dst = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
    out = insert(src.read_text(encoding="utf-8"))
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(out, encoding="utf-8")
    print(f"{dst}  （{src} にギフトの入口を差し込み）")


if __name__ == "__main__":
    main()
