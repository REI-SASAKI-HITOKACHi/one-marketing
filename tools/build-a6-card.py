#!/usr/bin/env python3
"""読本（一般向けの読み物）への入口になる A6 カードを、印刷入稿できる形で作る。

産院・小児科・ペットショップ・動物病院などの受付に置いてもらう1枚。
QR を読むと読本サイト（DOKUHON_URL）が開く。カードは読み物への入口であって、広告ではない。

方針（ここを外すと施設に置いてもらえなくなる）:
  - 子どもやペットの画像は使わない。文字と QR だけ。
  - 「掃除しませんか」の類の売り込み文言を入れない。読むだけ・無料であることだけを言う。
  - 電話番号は UNEI_TEL（ワンヒッターの番号）以外を絶対に印字しない。
  - どの施設に置いたカードから読まれたかを知るため、QR の URL に ?src=<施設ID> を入れる。
    施設IDは裏面の隅にも小さく刷る（どのカードがどこのものかを現物で確認できるように）。

使い方:
  python3 tools/build-a6-card.py                          # 両案・施設ID=card
  python3 tools/build-a6-card.py --src sanin01 --variant akachan
  python3 tools/build-a6-card.py --bleed                  # 3mm の塗り足し付き（印刷所入稿用）
  出力: dist/dokuhon/card-<案>-<施設ID>-front.png / -back.png / card-<案>-<施設ID>.pdf
        （dist/ は .gitignore 済み）

A6 = 105×148mm。300dpi で 1240×1748px。PDF は Pillow の PDF 保存（2ページ：表・裏）。
フォントは IPA Pゴシック（この環境に明朝が無いので、ゴシックのみ）。
"""
import argparse
import pathlib
import sys

import qrcode
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from media_common import DOKUHON_URL, UNEI, UNEI_ADDR, UNEI_TEL  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "dist" / "dokuhon"
FONT = "/usr/share/fonts/opentype/ipafont-gothic/ipagp.ttf"

DPI = 300
A6_MM = (105, 148)
BLEED_MM = 3
QR_MM = 34
MARGIN_MM = 9

# サイトの配色（lp/media と同じ）
GROUND = (0xFA, 0xF7, 0xF2)
INK = (0x14, 0x32, 0x3D)
ACCENT = (0x0E, 0x7C, 0x93)
CTA = (0xC4, 0x46, 0x1D)   # カードでは使わない（売り込み色を避ける）。定義だけ揃えておく
MUTED = (0x5A, 0x6B, 0x72)

# 見出しの \n は改行の指定。字数で自動折り返しすると「エ／アコン」のように語の途中で切れるので、読点と文節で切る
VARIANTS = {
    "akachan": {
        "headline": "赤ちゃんが来る前に、\nエアコンの中を\n見たことがありますか。",
        "sub": "江戸川区のハウスクリーニング店が、写真で全部お見せします（読むだけ・無料）",
        "path": "/akachan/",
        "dokuhon": "読本：赤ちゃんが来る前に知っておきたい、家の中の見えない汚れ",
    },
    "pet": {
        "headline": "この子が来る前に、\nエアコンの中を\n見たことがありますか。",
        "sub": "江戸川区のハウスクリーニング店が、写真で全部お見せします（読むだけ・無料）",
        "path": "/pet/",
        "dokuhon": "読本：この子が来る前に知っておきたい、家の中の見えない汚れ",
    },
}

BACK_TITLE = "このカードについて"
BACK_BODY = (
    "この読み物は、江戸川区北葛西のハウスクリーニング店 ワンヒッター株式会社 が作りました。"
    "エアコンや浴室の中に、目に見えないまま何が溜まっているかを、"
    "現場の写真と東京都の調査の数字でお話しします。"
)
BACK_NOTE = "読み物の末尾に、当社のクリーニングと無料点検のご案内があります。"
QR_CAPTION = "スマホのカメラで読み取ってください"


def mm(v: float) -> int:
    return round(v * DPI / 25.4)


def font(size):
    return ImageFont.truetype(FONT, size)


def wrap(text, f, max_w):
    """日本語は単語で切れないので、1文字ずつ幅を測って折り返す（build-shorts.py と同じ）"""
    lines, cur = [], ""
    for ch in text:
        if ch == "\n":
            lines.append(cur); cur = ""; continue
        if f.getlength(cur + ch) > max_w and cur:
            lines.append(cur); cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def draw_block(d, text, size, x, y, max_w, color=INK, line_gap=1.5, align="left"):
    """折り返して描き、次の y を返す"""
    f = font(size)
    lh = int(size * line_gap)
    for i, ln in enumerate(wrap(text, f, max_w)):
        xx = x + (max_w - f.getlength(ln)) if align == "right" else x
        d.text((xx, y + i * lh), ln, font=f, fill=color)
    return y + len(wrap(text, f, max_w)) * lh


def fit_headline(text, max_w, max_h, start=104, floor=56, max_lines=3):
    """見出しは 3 行以内・枠内に収まる最大の文字サイズを探す（案ごとに字数が違うため）"""
    size = start
    while size > floor:
        f = font(size)
        lines = wrap(text, f, max_w)
        lh = int(size * 1.4)
        if len(lines) <= max_lines and len(lines) * lh <= max_h:
            return size, lines, lh
        size -= 4
    f = font(floor)
    return floor, wrap(text, f, max_w), int(floor * 1.4)


def qr_url(variant: str, src: str) -> str:
    return f"{DOKUHON_URL}{VARIANTS[variant]['path']}?src={src}"


def qr_image(url: str, px: int) -> Image.Image:
    """紙は汚れる・折れるので誤り訂正は H。ドットがぼけないよう NEAREST で目標サイズに揃える"""
    q = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=2)
    q.add_data(url)
    q.make(fit=True)
    im = q.make_image(fill_color=INK, back_color="white").convert("RGB")
    return im.resize((px, px), Image.NEAREST)


def new_page(bleed: bool):
    """A6 の紙面。--bleed のときは四辺 3mm 広い紙面を作り、描画原点をその分ずらす"""
    b = mm(BLEED_MM) if bleed else 0
    w, h = mm(A6_MM[0]) + 2 * b, mm(A6_MM[1]) + 2 * b
    img = Image.new("RGB", (w, h), GROUND)
    return img, b


def front_image(variant: str, src: str = "card", bleed: bool = False) -> Image.Image:
    v = VARIANTS[variant]
    img, b = new_page(bleed)
    d = ImageDraw.Draw(img)
    pw, ph = mm(A6_MM[0]), mm(A6_MM[1])
    m = mm(MARGIN_MM)
    x0, x1 = b + m, b + pw - m
    cw = x1 - x0

    # 上 55%：見出し
    head_area_h = int(ph * 0.55) - m - mm(6)
    size, lines, lh = fit_headline(v["headline"], cw, head_area_h)
    y = b + m + mm(4)
    f = font(size)
    for ln in lines:
        d.text((x0, y), ln, font=f, fill=INK)
        y += lh

    # 細い罫線（アクセント色）
    y = b + int(ph * 0.55)
    d.rectangle((x0, y, x1, y + mm(0.6)), fill=ACCENT)
    y += mm(5)

    # サブ
    y = draw_block(d, v["sub"], 40, x0, y, cw, color=INK, line_gap=1.55)

    # 下：QR（左）と読み取り案内（右）
    qpx = mm(QR_MM)
    qy = b + ph - m - qpx
    qr = qr_image(qr_url(variant, src), qpx)
    img.paste(qr, (x0, qy))
    tx = x0 + qpx + mm(4)
    tw = x1 - tx
    ty = qy + mm(3)
    ty = draw_block(d, QR_CAPTION, 38, tx, ty, tw, color=INK, line_gap=1.45)
    ty += mm(3)
    draw_block(d, v["dokuhon"], 28, tx, ty, tw, color=MUTED, line_gap=1.5)
    return img


def back_image(variant: str, src: str = "card", bleed: bool = False) -> Image.Image:
    img, b = new_page(bleed)
    d = ImageDraw.Draw(img)
    pw, ph = mm(A6_MM[0]), mm(A6_MM[1])
    m = mm(MARGIN_MM)
    x0, x1 = b + m, b + pw - m
    cw = x1 - x0

    y = b + m + mm(4)
    y = draw_block(d, BACK_TITLE, 60, x0, y, cw, color=INK, line_gap=1.3)
    y += mm(2)
    d.rectangle((x0, y, x0 + mm(18), y + mm(0.6)), fill=ACCENT)
    y += mm(7)
    y = draw_block(d, BACK_BODY, 40, x0, y, cw, color=INK, line_gap=1.7)

    # 小さい文字：運営情報と案内。電話番号は UNEI_TEL のみ
    sy = b + ph - m - mm(28)
    sy = draw_block(d, f"運営：{UNEI}", 30, x0, sy, cw, color=INK, line_gap=1.6)
    sy = draw_block(d, UNEI_ADDR, 30, x0, sy, cw, color=INK, line_gap=1.6)
    sy = draw_block(d, UNEI_TEL, 30, x0, sy, cw, color=INK, line_gap=1.6)
    sy += mm(2)
    draw_block(d, BACK_NOTE, 30, x0, sy, cw, color=MUTED, line_gap=1.6)

    # 施設ID（既定の card のときは刷らない）
    if src != "card":
        f = font(22)
        t = f"設置施設ID：{src}"
        d.text((x1 - f.getlength(t), b + ph - mm(5) - 22), t, font=f, fill=MUTED)
    return img


def build(variant: str, src: str = "card", bleed: bool = False) -> list:
    OUT.mkdir(parents=True, exist_ok=True)
    front = front_image(variant, src, bleed)
    back = back_image(variant, src, bleed)
    stem = f"card-{variant}-{src}"
    paths = [OUT / f"{stem}-front.png", OUT / f"{stem}-back.png", OUT / f"{stem}.pdf"]
    front.save(paths[0], dpi=(DPI, DPI))
    back.save(paths[1], dpi=(DPI, DPI))
    front.save(paths[2], "PDF", resolution=DPI, save_all=True, append_images=[back])
    return paths


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--src", default="card", help="設置施設ID（QR の ?src= と裏面に入る）")
    ap.add_argument("--variant", default="all", choices=["all", *VARIANTS])
    ap.add_argument("--bleed", action="store_true", help="四辺 3mm の塗り足しを付ける")
    a = ap.parse_args()
    if not all(c.isalnum() or c in "-_" for c in a.src):
        sys.exit("--src は英数字と - _ だけにしてください（URL とファイル名に使うため）")
    variants = list(VARIANTS) if a.variant == "all" else [a.variant]
    for v in variants:
        for p in build(v, a.src, a.bleed):
            print(f"{p.relative_to(ROOT)}  {p.stat().st_size / 1e3:.0f}KB")
        print(f"  QR → {qr_url(v, a.src)}")


if __name__ == "__main__":
    main()
