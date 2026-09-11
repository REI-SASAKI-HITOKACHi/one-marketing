#!/usr/bin/env python3
"""読本への入口になる A6 カード（v2）。産院の待合・ペットショップのレジ横に置く1枚。

v1 は「デザインが悪い・シチュエーションを想定していない」と差し戻し（2026-09-11）。
設計は docs/読本-設計メモ.md：待合のパステル色の紙の中で目立つのは、白地に黒の大きな明朝。色を使わない。
施設が普通紙に自分で印刷しても成立するよう、ベタ塗りをしない。

  表：数字1つ（読本の冒頭と同じ）＋1文。QRは下1/4。「読むだけ・無料」は小さく
  裏：読本の題名、URL（QRが読めない人用）、出典、運営者、施設ID

見出しは2案（A 数字型／B 問い型）。オーナーが選ぶ。
文言は tools/dokuhon_content.py の CARD から取る（読本の冒頭と同じ数字・同じ出典にするため）。

使い方:
  python3 tools/build-a6-card.py                       # 全案・施設ID=card
  python3 tools/build-a6-card.py --src F7K2QX --variant akachan --headline A
  python3 tools/build-a6-card.py --bleed               # 3mm 塗り足し（印刷所入稿）
  出力: dist/dokuhon/card-<案>-<見出し>-<施設ID>-{front,back}.png と .pdf
"""
import argparse
import pathlib
import sys

import qrcode
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from media_common import DOKUHON_URL, UNEI, UNEI_ADDR, UNEI_TEL  # noqa: E402
import dokuhon_content as K  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "dist" / "dokuhon"
FONTS = ROOT / "assets" / "fonts"
MINCHO = FONTS / "ShipporiMinchoB1-800.ttf"
MINCHO_B = FONTS / "ShipporiMinchoB1-700.ttf"
GOTHIC = FONTS / "ZenKakuGothicNew-500.ttf"
GOTHIC_R = FONTS / "ZenKakuGothicNew-400.ttf"

DPI = 300
A6_MM = (105, 148)
BLEED_MM = 3
MARGIN_MM = 9
QR_MM = 30

PAPER = (255, 255, 255)
INK = (0x17, 0x1A, 0x1C)
INK2 = (0x4A, 0x50, 0x54)
INK3 = (0x7C, 0x83, 0x88)
ACCENT = (0x0E, 0x6E, 0x82)


def mm(v: float) -> int:
    return round(v * DPI / 25.4)


def font(path: pathlib.Path, size: int) -> ImageFont.FreeTypeFont:
    if not path.exists():
        sys.exit(f"フォントがありません: {path}（python3 tools/fetch-fonts.py）")
    return ImageFont.truetype(str(path), size)


def wrap(text: str, f: ImageFont.FreeTypeFont, width: int) -> list:
    """字数ではなく描画幅で折り返す。\\n は強制改行。行頭に句読点・閉じ括弧が来ないようにする"""
    out = []
    for para in text.split("\n"):
        line = ""
        for ch in para:
            if f.getlength(line + ch) <= width or not line:
                line += ch
            else:
                if ch in "、。」）":
                    line += ch
                    continue
                out.append(line)
                line = ch
        out.append(line)
    return out


def draw_lines(d: ImageDraw.ImageDraw, x: int, y: int, lines: list, f: ImageFont.FreeTypeFont, fill, lh: float, spacing: float = 0) -> int:
    for ln in lines:
        d.text((x, y), ln, font=f, fill=fill)
        y += round(f.size * lh)
    return y


def canvas(bleed: bool):
    w, h = mm(A6_MM[0]), mm(A6_MM[1])
    b = mm(BLEED_MM) if bleed else 0
    im = Image.new("RGB", (w + 2 * b, h + 2 * b), PAPER)
    return im, b, w, h


def front(variant: str, headline: str, src: str, bleed: bool) -> Image.Image:
    im, b, w, h = canvas(bleed)
    d = ImageDraw.Draw(im)
    m = mm(MARGIN_MM)
    x0, x1 = b + m, b + w - m
    cw = x1 - x0
    card = K.CARD[variant]
    url = f"{DOKUHON_URL}{card['path']}?src={src}"

    y = b + mm(11)
    if headline == "A":
        # 数字型：数字＋単位が幅に収まる最大サイズ（上限22mm）。その下に1文、出典
        num, unit = card["num"], card["unit"]
        size = mm(22)
        while size > mm(10):
            fn, fu = font(MINCHO, size), font(MINCHO, round(size * 0.42))
            if fn.getlength(num) + mm(1.5) + fu.getlength(unit) <= cw:
                break
            size -= mm(0.5)
        d.text((x0, y), num, font=fn, fill=INK)
        base = y + size  # ベースライン付近に単位をそろえる
        d.text((x0 + fn.getlength(num) + mm(1.5), base - round(size * 0.42) - mm(0.6)), unit, font=fu, fill=INK)
        y += round(size * 1.18) + mm(4)
        fl = font(MINCHO_B, mm(5.2))
        y = draw_lines(d, x0, y, wrap(card["line"], fl, cw), fl, INK, 1.7)
        fs = font(GOTHIC_R, mm(2.6))
        y += mm(2.5)
        y = draw_lines(d, x0, y, wrap(card["num_src"], fs, cw), fs, INK3, 1.5)
    else:
        # 問い型：\n の位置で切り、いちばん長い行が幅に収まる最大サイズ（上限9.5mm）
        segs = card["question"].split("\n")
        size = mm(9.5)
        while size > mm(5):
            fq = font(MINCHO_B, size)
            if max(fq.getlength(t) for t in segs) <= cw:
                break
            size -= mm(0.25)
        y += mm(4)
        y = draw_lines(d, x0, y, segs, fq, INK, 1.55)

    # 下段：QR＋読み物の題名。上段との間に細い罫
    qy = b + h - m - mm(QR_MM)
    d.line([(x0, qy - mm(6)), (x1, qy - mm(6))], fill=INK, width=mm(0.25))
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=0, box_size=10)
    qr.add_data(url)
    qr.make(fit=True)
    qim = qr.make_image(fill_color=INK, back_color=PAPER).convert("RGB").resize((mm(QR_MM), mm(QR_MM)), Image.NEAREST)
    im.paste(qim, (x0, qy))
    tx = x0 + mm(QR_MM) + mm(5)
    ft = font(MINCHO_B, mm(4.2))
    ty = qy + mm(1)
    ty = draw_lines(d, tx, ty, wrap(card["title"], ft, x1 - tx), ft, INK, 1.5)
    fs = font(GOTHIC, mm(3.1))
    ty += mm(2.5)
    ty = draw_lines(d, tx, ty, wrap("スマホのカメラをかざすと開きます。読むだけ・無料。3分。", fs, x1 - tx), fs, INK2, 1.6)
    return im


def back(variant: str, src: str, bleed: bool) -> Image.Image:
    im, b, w, h = canvas(bleed)
    d = ImageDraw.Draw(im)
    m = mm(MARGIN_MM)
    x0, x1 = b + m, b + w - m
    cw = x1 - x0
    card = K.CARD[variant]
    url = f"{DOKUHON_URL}{card['path']}"

    y = b + mm(12)
    ft = font(MINCHO_B, mm(5.4))
    y = draw_lines(d, x0, y, wrap(card["title"], ft, cw), ft, INK, 1.55)
    y += mm(2)
    fb = font(GOTHIC_R, mm(3.4))
    y = draw_lines(d, x0, y, wrap(card["back"], fb, cw), fb, INK2, 1.75)
    y += mm(5)
    fh = font(GOTHIC, mm(3.0))
    y = draw_lines(d, x0, y, ["目次"], fh, INK3, 1.6)
    fc = font(MINCHO_B, mm(3.6))
    y = draw_lines(d, x0, y, card["toc"], fc, INK, 1.8)
    y += mm(4)
    d.line([(x0, y), (x0 + mm(14), y)], fill=ACCENT, width=mm(0.35))
    y += mm(4)
    fs = font(GOTHIC_R, mm(2.9))
    y = draw_lines(d, x0, y, wrap("QRが読めないときは、このアドレスを開いてください。", fs, cw), fs, INK3, 1.6)
    fu = font(GOTHIC, mm(3.2))
    y = draw_lines(d, x0, y, [url.replace("https://", "")], fu, INK, 1.6)

    # 奥付
    fy = b + h - m - mm(16)
    fz = font(GOTHIC_R, mm(2.8))
    lines = [f"書いたのは {UNEI}（ハウスクリーニング）", UNEI_ADDR, f"電話 {UNEI_TEL}", "読み物の末尾に、当社のクリーニングと無料点検のご案内があります。"]
    fy = draw_lines(d, x0, fy, lines, fz, INK3, 1.55)
    if src != "card":
        fid = font(GOTHIC_R, mm(2.4))
        t = f"設置施設ID {src}"
        d.text((x1 - fid.getlength(t), b + h - m - mm(1.5)), t, font=fid, fill=INK3)
    return im


def build(variant: str, headline: str, src: str, bleed: bool) -> list:
    OUT.mkdir(parents=True, exist_ok=True)
    f = front(variant, headline, src, bleed)
    bk = back(variant, src, bleed)
    stem = f"card-{variant}-{headline}-{src}"
    f.save(OUT / f"{stem}-front.png")
    bk.save(OUT / f"{stem}-back.png")
    f.save(OUT / f"{stem}.pdf", "PDF", resolution=DPI, save_all=True, append_images=[bk])
    return [OUT / f"{stem}-front.png", OUT / f"{stem}-back.png", OUT / f"{stem}.pdf"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="card")
    ap.add_argument("--variant", default="all", choices=["all", *K.CARD.keys()])
    ap.add_argument("--headline", default="all", choices=["all", "A", "B"])
    ap.add_argument("--bleed", action="store_true")
    a = ap.parse_args()
    vs = list(K.CARD) if a.variant == "all" else [a.variant]
    hs = ["A", "B"] if a.headline == "all" else [a.headline]
    for v in vs:
        for hl in hs:
            for p in build(v, hl, a.src, a.bleed):
                print("書き出し:", p.relative_to(ROOT))


if __name__ == "__main__":
    main()
