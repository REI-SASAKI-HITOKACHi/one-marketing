#!/usr/bin/env python3
"""ブログのアイキャッチ（写真が無い記事用の文字カード）を作る。

  python3 tools/build-blog-eyecatch.py            # 割り当て表（docs/blog/写真割り当て表.md）で「カード」になっている記事を全部
  python3 tools/build-blog-eyecatch.py 2026-10-16 # 日付で指定

1600×1200（4:3。施工写真と同じ比率）JPEG → assets/blog/eyecatch/<日付>.jpg
見出しは記事の題名の先頭（最初の「｜」「　」まで）。SNSカードと同じ「白い紙に黒い明朝」の方向。写真・アイコン・絵文字は使わない。
"""
import pathlib
import re
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import importlib.util

spec = importlib.util.spec_from_file_location("sc", pathlib.Path(__file__).resolve().parent / "build-sns-cards.py")
sc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sc)

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "blog" / "eyecatch"
W, H, M = 1600, 1200, 120


def headline_of(title: str) -> str:
    t = re.split(r"[｜　]", title.strip())[0]
    return t.replace("℃", "度")   # 明朝フォントに ℃ の字が無い


def render(title: str, category: str) -> Image.Image:
    im = Image.new("RGB", (W, H), sc.PAPER)
    d = ImageDraw.Draw(im)
    kf = sc.font(sc.GOTHIC, 38)
    d.text((M, M - 10), f"{category}｜自分でできる範囲のお話", font=kf, fill=sc.MUTED if hasattr(sc, "MUTED") else (0x7C, 0x83, 0x88))
    d.line([(M, M + 62), (W - M, M + 62)], fill=(0xE3, 0xE0, 0xD9), width=2)
    text = headline_of(title)
    for smax in range(150, 70, -6):     # 最後の行が1〜2字だけ（「上」「粒」）にならない大きさを探す
        f, lines, _ = sc.fit_headline(text, W - 2 * M, 3, smax, 70)
        if len(lines) == 1 or len(lines[-1]) >= 3:
            break
    bh = sc.text_block_height(lines, f, 1.45) + 80
    y = M + 62 + (H - 2 * M - 62 - 40 - bh) // 2 + 30
    y = sc.draw_hanging(d, M, y, lines, f, (0x17, 0x1A, 0x1C), 1.45)
    acc = getattr(sc, "ACCENT", (0x0E, 0x6E, 0x82))
    d.rectangle([M, y + 36, M + 150, y + 44], fill=acc)
    ff = sc.font(sc.GOTHIC, 36)
    d.line([(M, H - M - 40), (W - M, H - M - 40)], fill=(0xE3, 0xE0, 0xD9), width=2)
    d.text((M, H - M - 20), "ワンヒッター｜江戸川区のハウスクリーニング", font=ff, fill=(0x4A, 0x50, 0x54))
    return im


def main() -> None:
    table = ROOT / "docs" / "blog" / "写真割り当て表.md"
    want = set(sys.argv[1:])
    OUT.mkdir(parents=True, exist_ok=True)
    n = 0
    for row in table.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        if len(cells) < 6 or not re.fullmatch(r"\d{2}-\d{2}", cells[0]):
            continue
        date = "2026-" + cells[0]
        if "カード" not in cells[2] or (want and date not in want):
            continue
        art = next(pathlib.Path(ROOT / "docs" / "blog").glob(f"{date}-*.md"))
        s = art.read_text(encoding="utf-8")
        title = re.search(r'^title:\s*"?(.+?)"?\s*$', s, re.M).group(1)
        cat = re.search(r"^category:\s*(.+)$", s, re.M).group(1).strip()
        render(title, cat).save(OUT / f"{date}.jpg", quality=90)
        n += 1
        print("書き出し:", f"assets/blog/eyecatch/{date}.jpg", "｜", headline_of(title))
    print(n, "枚")


if __name__ == "__main__":
    main()
