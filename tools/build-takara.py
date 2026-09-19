#!/usr/bin/env python3
"""タカラサービスさま向けの実績レポート（A4・1枚）と紹介カード（A6）を PDF にする。

依頼 20260919-02-web-inflow（2026-09-19 MTG オーナー決定・最優先）。
CMO の 9/19 23:46 の回答で、宛名・PDFのみ・`?src=teikei_takara` の3点が決まった。

数字は `docs/タカラサービス-実績レポートと紹介カード.md` に根拠を書いてある。
台帳（『【毎月更新】リピート/業務提携』『提携先_休眠度』）から機械で読んだものだけを使う。
**タカラサービスさま固有のリピート率は出せない**ので入れない（台帳に「紹介元」列が無い）。
**他社の名前・金額・構成比は入れない**（お客様に渡すものに他社の取引情報を混ぜない）。

料金は `docs/price-master.md` の税込。お掃除機能つきは別行にする
（1行にまとめると「10,780円で全部できる」と読まれる。2026-09-15 に同じ書き方で直した）。

お客様に見せるものに「説明のための説明」を書かない（2026-09-19 恒久ルール）。

使い方:
  python3 tools/build-takara.py            # 両方
  python3 tools/build-takara.py --report   # レポートだけ
  python3 tools/build-takara.py --card     # カードだけ
  出力: dist/takara/takara-report.pdf / takara-card.pdf（と確認用 PNG）
"""
import argparse
import pathlib
import sys

import qrcode
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from media_common import UNEI, UNEI_ADDR, UNEI_TANTOU, UNEI_TEL  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "dist" / "takara"
FONTS = ROOT / "assets" / "fonts"
MINCHO = FONTS / "ShipporiMinchoB1-800.ttf"
MINCHO_B = FONTS / "ShipporiMinchoB1-700.ttf"
GOTHIC = FONTS / "ZenKakuGothicNew-500.ttf"
GOTHIC_R = FONTS / "ZenKakuGothicNew-400.ttf"

DPI = 300
A4_MM = (210, 297)
A6_MM = (105, 148)

PAPER = (255, 255, 255)
INK = (0x17, 0x1A, 0x1C)
INK2 = (0x4A, 0x50, 0x54)
INK3 = (0x7C, 0x83, 0x88)
ACCENT = (0x0E, 0x6E, 0x82)

ATENA = "タカラサービス　ご担当者さま"
BOOKING_SRC = "https://yoyaku.onehitter.jp/?src=teikei_takara"
BOOKING_SHOW = "yoyaku.onehitter.jp"

# 台帳から読んだ数字（docs/タカラサービス-実績レポートと紹介カード.md に根拠）
KENSU = "17件"
RUIKEI = "777,690円（税込）"
KIKAN = "2023年9月29日 〜 2026年8月4日"
CHOKKIN = [("2026年7月10日", "75,020円"), ("2026年8月4日", "67,000円")]
CHOKKIN_KEI = "142,020円"
CHOKKIN_TAN = "71,010円"
ZENKIKAN_TAN = "45,746円"
MANZOKU = "98.6%"
MANZOKU_NAIWAKE = "2023年1月〜2025年12月／209名中206名"

# docs/price-master.md の税込価格
RYOKIN = [
    ("エアコン（お掃除機能なし）", "10,780円"),
    ("エアコン（お掃除機能つき）", "17,380円"),
    ("レンジフード", "18,480円"),
    ("浴室", "18,480円"),
]


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


def draw_lines(d: ImageDraw.ImageDraw, x: int, y: int, lines: list, f: ImageFont.FreeTypeFont, fill, lh: float) -> int:
    for ln in lines:
        d.text((x, y), ln, font=f, fill=fill)
        y += round(f.size * lh)
    return y


def midashi(d: ImageDraw.ImageDraw, x0: int, x1: int, y: int, text: str) -> int:
    """節の見出し。細い罫を1本引いて、その下に見出しを置く"""
    fm = font(GOTHIC, mm(4.0))
    d.text((x0, y), text, font=fm, fill=INK)
    y += round(fm.size * 1.35)
    d.line([(x0, y), (x1, y)], fill=INK3, width=mm(0.2))
    return y + mm(4)


def hyou(d: ImageDraw.ImageDraw, x0: int, x1: int, y: int, rows: list, lh: float = 1.9, big: bool = False) -> int:
    """左に項目・右に数字。数字は右そろえ。大きい数字（big）は少し大きく打つ"""
    fl = font(GOTHIC_R, mm(3.6))
    fr = font(MINCHO_B, mm(5.0) if big else mm(4.0))
    for label, value in rows:
        d.text((x0 + mm(2), y + (round(fr.size - fl.size) // 2 if big else 0)), label, font=fl, fill=INK2)
        d.text((x1 - fr.getlength(value), y), value, font=fr, fill=INK)
        y += round(fr.size * lh)
    return y


def report() -> Image.Image:
    w, h = mm(A4_MM[0]), mm(A4_MM[1])
    im = Image.new("RGB", (w, h), PAPER)
    d = ImageDraw.Draw(im)
    m = mm(22)
    x0, x1 = m, w - m
    cw = x1 - x0

    # 宛名
    y = mm(24)
    fa = font(MINCHO_B, mm(5.4))
    y = draw_lines(d, x0, y, [ATENA], fa, INK, 1.6)
    y += mm(6)

    # あいさつ
    fb = font(GOTHIC_R, mm(3.6))
    y = draw_lines(d, x0, y, wrap(
        "いつもご紹介をいただき、ありがとうございます。\n"
        "2023年9月から今月までの3年間の記録を、1枚にまとめました。", fb, cw), fb, INK2, 1.85)
    y += mm(10)

    # ご紹介いただいた工事
    y = midashi(d, x0, x1, y, "ご紹介いただいた工事")
    y = hyou(d, x0, x1, y, [
        ("ご依頼の件数", KENSU),
        ("累計", RUIKEI),
    ], lh=1.85, big=True)
    fs = font(GOTHIC_R, mm(3.2))
    y += mm(1)
    y = draw_lines(d, x0 + mm(2), y, [KIKAN], fs, INK3, 1.6)
    y += mm(9)

    # 直近のご依頼
    y = midashi(d, x0, x1, y, "直近のご依頼")
    y = hyou(d, x0, x1, y, [(dt, kin) for dt, kin in CHOKKIN], lh=1.75)
    d.line([(x0 + mm(2), y + mm(1)), (x1, y + mm(1))], fill=INK3, width=mm(0.2))
    y += mm(4)
    y = hyou(d, x0, x1, y, [
        ("2件で", CHOKKIN_KEI),
        ("1件あたり", CHOKKIN_TAN),
    ], lh=1.85, big=True)
    y += mm(2)
    y = draw_lines(d, x0 + mm(2), y, wrap(
        f"3年間の平均は1件あたり{ZENKIKAN_TAN}でしたので、最近は1件あたりの金額が大きくなっています。"
        "エアコンの台数がまとまったご依頼が増えたためです。", fs, cw - mm(2)), fs, INK2, 1.75)
    y += mm(9)

    # 満足度
    y = midashi(d, x0, x1, y, "お客様の満足度")
    fm = font(MINCHO, mm(13))
    d.text((x0 + mm(2), y), MANZOKU, font=fm, fill=INK)
    ty = y + mm(2)
    ty = draw_lines(d, x0 + mm(2) + fm.getlength(MANZOKU) + mm(6), ty, [MANZOKU_NAIWAKE], fs, INK3, 1.6)
    draw_lines(d, x0 + mm(2) + fm.getlength(MANZOKU) + mm(6), ty, ["施工後のアンケートで「満足」「やや満足」と", "お答えいただいた割合です。"], fs, INK2, 1.6)
    y += round(fm.size * 1.35) + mm(9)

    # 次のお願い
    y = midashi(d, x0, x1, y, "次にご紹介いただけるとありがたい場面")
    y = draw_lines(d, x0 + mm(2), y, wrap(
        "エアコンを新しく設置されるとき、その部屋の他のエアコンや、水まわりのご相談があれば、お声がけください。\n"
        "設置の当日でなくて構いません。「クリーニングもできる会社がある」と一言いただければ、"
        "こちらからお客様にご連絡します。", fb, cw - mm(2)), fb, INK2, 1.85)

    # 奥付
    fy = h - mm(24)
    d.line([(x0, fy - mm(7)), (x1, fy - mm(7))], fill=ACCENT, width=mm(0.35))
    fz = font(GOTHIC_R, mm(3.0))
    draw_lines(d, x0, fy, [
        f"{UNEI}　代表取締役 {UNEI_TANTOU}",
        UNEI_ADDR,
        f"電話 {UNEI_TEL}",
    ], fz, INK3, 1.6)
    return im


def card() -> Image.Image:
    w, h = mm(A6_MM[0]), mm(A6_MM[1])
    im = Image.new("RGB", (w, h), PAPER)
    d = ImageDraw.Draw(im)
    m = mm(9)
    x0, x1 = m, w - m
    cw = x1 - x0

    y = mm(13)
    segs = ["エアコンを設置したお部屋の、", "前からあるエアコンは、", "いつ洗いましたか。"]
    size = mm(7.0)
    while size > mm(4.5):
        fq = font(MINCHO_B, size)
        if max(fq.getlength(t) for t in segs) <= cw:
            break
        size -= mm(0.25)
    y = draw_lines(d, x0, y, segs, fq, INK, 1.6)
    y += mm(7)

    fn = font(GOTHIC, mm(3.6))
    y = draw_lines(d, x0, y, [UNEI], fn, INK, 1.5)
    fs = font(GOTHIC_R, mm(2.8))
    y = draw_lines(d, x0, y, ["江戸川区北葛西・ハウスクリーニング"], fs, INK3, 1.7)
    y += mm(3)

    fl = font(GOTHIC_R, mm(3.0))
    fr = font(MINCHO_B, mm(3.6))
    for label, value in RYOKIN:
        d.text((x0, y + mm(0.3)), label, font=fl, fill=INK2)
        d.text((x1 - fr.getlength(value), y), value, font=fr, fill=INK)
        y += round(fr.size * 1.65)
    fz = font(GOTHIC_R, mm(2.6))
    y += mm(1)
    y = draw_lines(d, x0, y, ["すべて税込です。"], fz, INK3, 1.6)
    y = draw_lines(d, x0, y, wrap(
        "出張費はかかりません。駐車スペースが無い場合は、コインパーキング代が実費になります。",
        fz, cw), fz, INK3, 1.6)

    # 下段：QR と連絡先
    qmm = 24
    qy = h - m - mm(qmm) - mm(6)
    d.line([(x0, qy - mm(5)), (x1, qy - mm(5))], fill=INK, width=mm(0.25))
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=0, box_size=10)
    qr.add_data(BOOKING_SRC)
    qr.make(fit=True)
    qim = qr.make_image(fill_color=INK, back_color=PAPER).convert("RGB").resize((mm(qmm), mm(qmm)), Image.NEAREST)
    im.paste(qim, (x1 - mm(qmm), qy))

    ft = font(GOTHIC, mm(3.4))
    fu = font(GOTHIC_R, mm(2.8))
    ty = qy + mm(1)
    d.text((x0, ty), "お電話", font=fu, fill=INK3)
    d.text((x0, ty + round(fu.size * 1.5)), UNEI_TEL, font=ft, fill=INK)
    ty += round(fu.size * 1.5) + round(ft.size * 1.9)
    d.text((x0, ty), "ご予約", font=fu, fill=INK3)
    d.text((x0, ty + round(fu.size * 1.5)), BOOKING_SHOW, font=ft, fill=INK)

    fg = font(GOTHIC_R, mm(2.7))
    t = "タカラサービスさまのご紹介"
    d.text((x0, h - m - mm(1.0)), t, font=fg, fill=INK3)
    return im


def save(im: Image.Image, stem: str) -> list:
    OUT.mkdir(parents=True, exist_ok=True)
    png, pdf = OUT / f"{stem}.png", OUT / f"{stem}.pdf"
    im.save(png)
    im.save(pdf, "PDF", resolution=DPI)
    return [png, pdf]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true", help="レポートだけ")
    ap.add_argument("--card", action="store_true", help="カードだけ")
    a = ap.parse_args()
    both = not (a.report or a.card)
    outs = []
    if both or a.report:
        outs += save(report(), "takara-report")
    if both or a.card:
        outs += save(card(), "takara-card")
    for p in outs:
        print("書き出し:", p.relative_to(ROOT))
    print("\n★ PDF までです。印刷はオーナー判断（お金が出るため）。外には出していません。")


if __name__ == "__main__":
    main()
