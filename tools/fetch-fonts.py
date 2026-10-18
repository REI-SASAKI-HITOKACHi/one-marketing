#!/usr/bin/env python3
"""カード・動画・PDFの描画に使う日本語フォント（OFL）を Google Fonts から assets/fonts/ に落とす。

なぜ：Pillow/ffmpeg での文字描画は端末にあるフォントしか使えない。IPAゴシックだけでは
LP（Shippori Mincho B1 / Zen Kaku Gothic New）とトーンが揃わない。ファイルが大きいので
リポジトリには入れず（.gitignore）、必要なときにこれで取り直す。

  python3 tools/fetch-fonts.py
"""
import pathlib
import re
import urllib.request

OUT = pathlib.Path(__file__).resolve().parent.parent / "assets" / "fonts"
WANT = {"Shippori+Mincho+B1": ["700", "800"], "Zen+Kaku+Gothic+New": ["400", "500", "700", "900"], "Noto+Serif+JP": ["700"]}


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for fam, weights in WANT.items():
        css = get(f"https://fonts.googleapis.com/css2?family={fam}:wght@{';'.join(weights)}&display=swap").decode()
        for w in weights:
            out = OUT / f"{fam.replace('+', '')}-{w}.ttf"
            if out.exists():
                print("あり", out.name)
                continue
            # 日本語フォントは unicode-range で分割配信される。範囲指定なしの css2 は全体のTTFを1本返す
            m = re.search(rf"font-weight: {w};[^}}]*?url\((https://[^)]+\.ttf)\)", css, re.S)
            if not m:
                print("見つからず", fam, w)
                continue
            out.write_bytes(get(m.group(1)))
            print("取得", out.name, out.stat().st_size)


if __name__ == "__main__":
    main()
