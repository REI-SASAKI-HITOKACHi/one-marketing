#!/usr/bin/env python3
"""SNS広告（Instagram／Facebook）用の縦型リール動画を、現場の実写だけで組み立てる。

これは `tools/build-shorts.py`（図鑑の1案件＝1本）とは別物。
あちらは投稿用、こちらは**広告用**で、作りが違う：

  - 文末に「プロフィールのリンクから」を入れない（広告の着地は予約ページ直行）
  - 画は 4:5 の窓に入れて上下に文字の場所を取る（スマホで字が読める大きさにする）
  - 動くのはカメラワーク（ゆっくり寄る・流す）と、作業前→作業後のワイプだけ

方針（ここを外すと嘘の実績になる）:
  - 使うのは現場で撮った実写だけ。生成AIで映像を作らない・足さない・直さない
  - 作業前→作業後のワイプは、同一箇所と確認済みのペアにしか使わない
    （根拠：docs/photo-inventory.md・docs/photo-inventory-2026-09.md）
  - 写ってはいけないもの（ロゴ・社名・電話番号・銘板・私物・人物）は crop で落とす
  - 禁止語（最安・No.1・今だけ・残りわずか・98.8%・電話番号）と
    「出張費が一切かからない」は書かない。検査は check() が自動で通す

使い方:
  python3 tools/build-ad-reels.py                       # 全部
  python3 tools/build-ad-reels.py aircon-kabi           # 1本だけ
  python3 tools/build-ad-reels.py --check               # 文言の検査だけ（描画しない）
  python3 tools/build-ad-reels.py --poster              # 各本の静止画（確認用）も出す

  素材: assets/photos/   （web-inflow ブランチにある。手元に無ければ
        git checkout origin/claude/web-inflow -- assets/photos）
  字:   assets/fonts/    （無ければ python3 tools/fetch-fonts.py）
  出力: dist/ad-reels/<id>.mp4（dist/ は .gitignore 済み。動画はコミットしない）

要るもの: pip3 install pillow imageio-ffmpeg
"""
import argparse
import json
import math
import pathlib
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

ROOT = pathlib.Path(__file__).resolve().parent.parent
PHOTOS = ROOT / "assets" / "photos"
FONTS = ROOT / "assets" / "fonts"
SPEC = ROOT / "data" / "ad-reels.json"
OUT = ROOT / "dist" / "ad-reels"

W, H, FPS = 1080, 1920, 30

# LP（lp/aircon/index.html）と同じ色を使う。着地の予約ページと地続きに見せるため。
INK = (13, 59, 92)          # --ink
INK_DEEP = (6, 26, 42)
PAPER = (250, 247, 242)     # --paper
AQUA = (111, 208, 228)      # --aqua-ink
CTA = (192, 48, 12)         # --cta
MARK = (255, 229, 102)      # --mark
ON_INK = (237, 244, 248)    # --on-ink
ON_INK_2 = (168, 194, 210)  # --on-ink-2

# 画の窓。4:5 より少し縦長。上に見出し、下にひとことの場所を取る
WIN_X, WIN_Y, WIN_W, WIN_H = 0, 352, 1080, 1356
MARGIN = 64

BANNED = ["最安", "No.1", "ＮＯ.1", "今だけ", "残りわずか", "98.8", "出張費が一切",
          "おそうじ本舗", "本舗", "日本一", "完全無料", "必ず落ち"]
# 電話番号そのもの（数字の並び）も入れない
import re as _re
PHONE = _re.compile(r"0\d{1,4}[-ー－]?\d{2,4}[-ー－]?\d{3,4}")


def font(name, size):
    return ImageFont.truetype(str(FONTS / name), size)


def F900(s): return font("ZenKakuGothicNew-900.ttf", s)
def F700(s): return font("ZenKakuGothicNew-700.ttf", s)
def F500(s): return font("ZenKakuGothicNew-500.ttf", s)
def F400(s): return font("ZenKakuGothicNew-400.ttf", s)


# ── 文字組み ────────────────────────────────────────────────────────────
NO_HEAD = "、。，．）」』】〉》〕］｝!?！？・ー"   # 行頭に来てはいけない
NO_TAIL = "（「『【〈《〔［｛"                      # 行末に来てはいけない


def wrap(text, f, max_w):
    """日本語は単語で切れないので1文字ずつ幅を測る。簡単な禁則処理つき"""
    out = []
    for para in text.split("\n"):
        cur = ""
        for ch in para:
            if cur and f.getlength(cur + ch) > max_w:
                # 行頭禁則：次が句読点などなら、その1文字は前の行に残す
                if ch in NO_HEAD:
                    cur += ch
                    out.append(cur)
                    cur = ""
                    continue
                # 行末禁則：いま行末にある括弧は次の行へ送る
                if cur[-1] in NO_TAIL:
                    out.append(cur[:-1])
                    cur = cur[-1] + ch
                    continue
                out.append(cur)
                cur = ch
            else:
                cur += ch
        out.append(cur)
    return out


def text_block(size_f, lines, color, line_h, align="left"):
    """文字だけのRGBA画像を返す。影は別に作る（にじませるため）"""
    w = max([int(size_f.getlength(l)) for l in lines] + [1]) + 8
    h = int(line_h * len(lines)) + 16
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for i, l in enumerate(lines):
        x = 0 if align == "left" else (w - size_f.getlength(l)) / 2
        d.text((x, i * line_h), l, font=size_f, fill=color + (255,))
    return img


def paste_text(canvas, block, xy, alpha=1.0, shadow=0.55, blur=14):
    """影をにじませてから文字を置く。ベタの縁取りより紙面がうるさくならない"""
    if alpha <= 0.004:
        return
    x, y = int(xy[0]), int(xy[1])
    if shadow > 0:
        sh = Image.new("RGBA", (block.width + blur * 4, block.height + blur * 4), (0, 0, 0, 0))
        mask = block.split()[3]
        solid = Image.new("RGBA", block.size, (0, 10, 18, 255))
        solid.putalpha(mask)
        sh.paste(solid, (blur * 2, blur * 2 + 4), solid)
        sh = sh.filter(ImageFilter.GaussianBlur(blur))
        sh.putalpha(sh.split()[3].point(lambda v: int(v * shadow * alpha)))
        canvas.alpha_composite(sh, (x - blur * 2, y - blur * 2))
    if alpha < 1.0:
        block = block.copy()
        block.putalpha(block.split()[3].point(lambda v: int(v * alpha)))
    canvas.alpha_composite(block, (x, y))


# ── 動きのカーブ ────────────────────────────────────────────────────────
def smooth(p):
    p = max(0.0, min(1.0, p))
    return p * p * (3 - 2 * p)


def ease_out(p):
    p = max(0.0, min(1.0, p))
    return 1 - (1 - p) ** 3


def ease_in_out(p):
    p = max(0.0, min(1.0, p))
    return 0.5 - 0.5 * math.cos(math.pi * p)


# ── 写真 ────────────────────────────────────────────────────────────────
_cache = {}


def load(name, crop=None):
    key = (name, tuple(crop) if crop else None)
    if key in _cache:
        return _cache[key]
    p = PHOTOS / name
    if not p.exists():
        sys.exit(f"写真が無い: {p}\n  git checkout origin/claude/web-inflow -- assets/photos")
    im = ImageOps.exif_transpose(Image.open(p)).convert("RGB")
    if crop:                       # [左, 上, 右, 下] を 0〜1 で。写ってはいけないものを落とす
        l, t, r, b = crop
        im = im.crop((int(l * im.width), int(t * im.height), int(r * im.width), int(b * im.height)))
    _cache[key] = im
    return im


def kenburns(im, p, kb, box_w, box_h):
    """box を覆う範囲を切り出して返す。p=0→1 で寄り・位置が動く"""
    z0, z1 = kb.get("z", [1.06, 1.16])
    f0 = kb.get("from", [0.5, 0.5])
    f1 = kb.get("to", [0.5, 0.5])
    e = smooth(p)
    z = z0 + (z1 - z0) * e
    fx = f0[0] + (f1[0] - f0[0]) * e
    fy = f0[1] + (f1[1] - f0[1]) * e
    s = max(box_w / im.width, box_h / im.height) * z
    cw, ch = box_w / s, box_h / s
    x = (im.width - cw) * fx
    y = (im.height - ch) * fy
    x = max(0, min(im.width - cw, x))
    y = max(0, min(im.height - ch, y))
    out = im.resize((box_w, box_h), Image.LANCZOS, box=(x, y, x + cw, y + ch))
    return out.filter(ImageFilter.UnsharpMask(radius=1.6, percent=48, threshold=3))


def backdrop(im):
    """窓の外。写真をぼかして暗く沈めたものを敷く。帯がのっぺりしないように"""
    b = im.resize((int(W * 0.30), int(H * 0.30)), Image.BILINEAR)
    b = b.filter(ImageFilter.GaussianBlur(22)).resize((int(W * 1.12), int(H * 1.12)), Image.BICUBIC)
    b = b.crop(((b.width - W) // 2, (b.height - H) // 2,
                (b.width - W) // 2 + W, (b.height - H) // 2 + H))
    tint = Image.new("RGB", (W, H), INK_DEEP)
    b = Image.blend(b, tint, 0.80)
    g = Image.new("L", (W, H), 0)
    gd = ImageDraw.Draw(g)
    for i in range(H):
        gd.line([(0, i), (W, i)], fill=int(26 + 40 * abs(i - H * 0.42) / H))
    b = Image.composite(Image.new("RGB", (W, H), INK_DEEP), b, g)
    return b


def scrim(img, top=0.0, bottom=0.0):
    """窓の上下に暗いグラデーションを足して、重なる文字を読めるようにする"""
    if top <= 0 and bottom <= 0:
        return img
    ov = Image.new("L", img.size, 0)
    d = ImageDraw.Draw(ov)
    ht = int(img.height * 0.34)
    for i in range(ht):
        a = int(255 * top * (1 - i / ht) ** 1.6)
        d.line([(0, i), (img.width, i)], fill=a)
        a2 = int(255 * bottom * (1 - i / ht) ** 1.6)
        d.line([(0, img.height - 1 - i), (img.width, img.height - 1 - i)], fill=a2)
    black = Image.new("RGB", img.size, (4, 12, 18))
    return Image.composite(black, img, ov)


# ── 1カットを描く ───────────────────────────────────────────────────────
def draw_window(canvas, photo_img, radius=0):
    canvas.paste(photo_img, (WIN_X, WIN_Y))
    d = ImageDraw.Draw(canvas)
    d.line([(0, WIN_Y), (W, WIN_Y)], fill=AQUA + (70,), width=2)
    d.line([(0, WIN_Y + WIN_H - 2), (W, WIN_Y + WIN_H - 2)], fill=AQUA + (70,), width=2)


def chip(canvas, xy, text, anchor="lt", alpha=1.0, fill=(8, 22, 32), fg=(255, 255, 255), size=34):
    if alpha <= 0.01:
        return
    f = F700(size)
    tw = f.getlength(text)
    pad_x, pad_y, h = int(size * 0.76), int(size * 0.35), int(size * 1.7)
    w = int(tw + pad_x * 2)
    x, y = xy
    if anchor[0] == "r":
        x -= w
    lay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lay)
    ld.rounded_rectangle((0, 0, w - 1, h - 1), radius=10, fill=fill + (235,))
    ld.text((pad_x, pad_y - 2), text, font=f, fill=fg + (255,))
    if alpha < 1:
        lay.putalpha(lay.split()[3].point(lambda v: int(v * alpha)))
    canvas.alpha_composite(lay, (int(x), int(y)))


def render_scene(sc, t, dur):
    """1カットを 1080x1920 の RGBA で返す。t はそのカットの中の経過秒"""
    p = min(1.0, t / dur) if dur else 0.0

    if sc["type"] == "end":
        return render_end(sc, t, dur)

    main = sc.get("photo") or sc["pair"][0]
    im = load(main, sc.get("crop"))
    bg = backdrop(im)
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    canvas.paste(bg, (0, 0))

    kb = sc.get("kb", {})
    win = kenburns(im, p, kb, WIN_W, WIN_H)

    if sc["type"] == "pair":
        after = load(sc["pair"][1], sc.get("crop2") or sc.get("crop"))
        win_b = kenburns(after, p, sc.get("kb2") or kb, WIN_W, WIN_H)
        w0, w1 = sc.get("wipe", [0.9, 2.4])
        wp = ease_in_out((t - w0) / max(0.01, (w1 - w0)))
        x = int(WIN_W * wp)
        if x > 0:
            win.paste(win_b.crop((0, 0, x, WIN_H)), (0, 0))
        win = scrim(win, top=sc.get("scrim_top", 0.30), bottom=sc.get("scrim_bottom", 0.0))
        draw_window(canvas, win)
        if 0 < x < WIN_W:                       # 境目の光る線
            edge = Image.new("RGBA", (120, WIN_H), (0, 0, 0, 0))
            ed = ImageDraw.Draw(edge)
            ed.rectangle((56, 0, 63, WIN_H), fill=AQUA + (255,))
            glow = edge.filter(ImageFilter.GaussianBlur(16))
            canvas.alpha_composite(glow, (WIN_X + x - 60, WIN_Y))
            canvas.alpha_composite(edge, (WIN_X + x - 60, WIN_Y))
        chip(canvas, (MARGIN, WIN_Y + 40), sc.get("label_a", "作業前"))
        chip(canvas, (W - MARGIN, WIN_Y + 40), sc.get("label_b", "作業後"),
             anchor="rt", alpha=ease_out((wp - 0.12) / 0.5), fill=(10, 64, 72), fg=PAPER)
    else:
        win = scrim(win, top=sc.get("scrim_top", 0.22), bottom=sc.get("scrim_bottom", 0.18))
        draw_window(canvas, win)
    a_out = 1.0 if dur - t > 0.34 else max(0.0, (dur - t) / 0.34)
    if sc.get("chip"):
        chip(canvas, (MARGIN, WIN_Y + 34), sc["chip"],
             alpha=ease_out((t - 0.7) / 0.6) * a_out, size=29)

    # 見出し（上）
    a_in = ease_out((t - sc.get("t_head", 0.12)) / 0.52)
    size = sc.get("head_size", 64)
    fh = F900(size)
    lines = wrap(sc["head"], fh, W - MARGIN * 2)
    lh = int(size * 1.34)
    blk = text_block(fh, lines, (255, 255, 255), lh)
    y_head = max(140, WIN_Y - 34 - lh * len(lines))
    paste_text(canvas, blk, (MARGIN, y_head + (1 - a_in) * 26), alpha=a_in * a_out)

    # ひとこと（下）
    if sc.get("cap"):
        a2 = ease_out((t - sc.get("t_cap", 0.5)) / 0.5) * a_out
        fc = F500(sc.get("cap_size", 38))
        cl = wrap(sc["cap"], fc, W - MARGIN * 2)
        cb = text_block(fc, cl, ON_INK_2, int(sc.get("cap_size", 38) * 1.45))
        paste_text(canvas, cb, (MARGIN, WIN_Y + WIN_H + 42 + (1 - a2) * 16),
                   alpha=a2, shadow=0.35, blur=10)
    return canvas


def render_end(sc, t, dur):
    canvas = Image.new("RGBA", (W, H), INK_DEEP + (255,))
    d = ImageDraw.Draw(canvas)
    for i in range(H):                       # 上が少し明るい縦のグラデーション
        k = i / H
        d.line([(0, i), (W, i)], fill=(
            int(INK[0] * (1 - k) + INK_DEEP[0] * k),
            int(INK[1] * (1 - k) + INK_DEEP[1] * k),
            int(INK[2] * (1 - k) + INK_DEEP[2] * k), 255))
    # 下に流れる淡い光
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((-280, H - 520, W + 280, H + 420), fill=AQUA + (34,))
    canvas.alpha_composite(glow.filter(ImageFilter.GaussianBlur(120)))

    y = 508
    a = ease_out(t / 0.6)
    f1 = F900(84)
    l1 = ["11月の作業は"]
    paste_text(canvas, text_block(f1, l1, PAPER, 112), (MARGIN, y + (1 - a) * 24),
               alpha=a, shadow=0.35)
    y += 120
    a2 = ease_out((t - 0.22) / 0.6)
    f2 = F900(124)
    blk = Image.new("RGBA", (W - MARGIN * 2, 170), (0, 0, 0, 0))
    bd = ImageDraw.Draw(blk)
    bd.text((0, 0), "10%", font=f2, fill=MARK + (255,))
    off = f2.getlength("10%") + 14
    bd.text((off, 20), "引き", font=F900(92), fill=PAPER + (255,))
    paste_text(canvas, blk, (MARGIN, y + (1 - a2) * 24), alpha=a2, shadow=0.35)
    y += 196

    a3 = ease_out((t - 0.45) / 0.6)
    f3 = F500(36)
    note = wrap("1箇所のご依頼が対象です。2箇所以上は対象外。\n金額は予約ページでご確認ください。", f3, W - MARGIN * 2)
    paste_text(canvas, text_block(f3, note, ON_INK_2, 54), (MARGIN, y), alpha=a3, shadow=0.3, blur=8)
    y += 54 * len(note) + 54

    # 予約ボタン
    a4 = ease_out((t - 0.7) / 0.6)
    pop = 1.0 + 0.045 * math.sin(max(0.0, t - 1.4) * 2.0) * (1 if t > 1.4 else 0)
    bw, bh = int(720 * pop), int(126 * pop)
    btn = Image.new("RGBA", (bw + 40, bh + 40), (0, 0, 0, 0))
    bd = ImageDraw.Draw(btn)
    bd.rounded_rectangle((20, 20, bw + 19, bh + 19), radius=bh // 2, fill=CTA + (255,))
    label = sc.get("cta", "空いている日を見て予約する")
    size = int(42 * pop)
    fb = F900(size)
    while fb.getlength(label) > bw - 56 and size > 24:   # ボタンからはみ出さないところまで詰める
        size -= 2
        fb = F900(size)
    tw = fb.getlength(label)
    bd.text((20 + (bw - tw) / 2, 20 + (bh - size) / 2 - 4), label, font=fb, fill=(255, 255, 255, 255))
    sh = btn.filter(ImageFilter.GaussianBlur(18))
    sh.putalpha(sh.split()[3].point(lambda v: int(v * 0.45 * a4)))
    canvas.alpha_composite(sh, ((W - bw - 40) // 2, int(y) + 10))
    if a4 < 1:
        btn.putalpha(btn.split()[3].point(lambda v: int(v * a4)))
    canvas.alpha_composite(btn, ((W - bw - 40) // 2, int(y)))
    y += bh + 92

    a5 = ease_out((t - 0.95) / 0.6)
    f5 = F700(40)
    l5 = ["ご利用後アンケート　満足 98.6%"]
    blk5 = text_block(f5, l5, ON_INK, 56, align="center")
    paste_text(canvas, blk5, ((W - blk5.width) // 2, y), alpha=a5, shadow=0.3, blur=8)
    y += 60
    f6 = F400(26)
    l6 = ["2023年1月〜2025年12月／回答209名中206名・自社調べ"]
    blk6 = text_block(f6, l6, ON_INK_2, 38, align="center")
    paste_text(canvas, blk6, ((W - blk6.width) // 2, y), alpha=a5, shadow=0.25, blur=6)
    return canvas


def chrome(canvas, t, total, hide=0.0):
    """全カットに出しっぱなしのもの：上の名乗りと、下の進み具合の線"""
    a = 1.0 - hide
    if a > 0.01:
        lay = Image.new("RGBA", (W, 120), (0, 0, 0, 0))
        d = ImageDraw.Draw(lay)
        d.rectangle((MARGIN, 10, MARGIN + 10, 42), fill=AQUA + (255,))
        f = F700(31)
        d.text((MARGIN + 26, 6), "ワンヒッター", font=f, fill=(255, 255, 255, 255))
        x = MARGIN + 26 + f.getlength("ワンヒッター") + 20
        fs = F500(29)
        d.text((x, 9), "東京・千葉・神奈川のハウスクリーニング", font=fs, fill=ON_INK_2 + (255,))
        lay.putalpha(lay.split()[3].point(lambda v: int(v * a)))
        sh = lay.filter(ImageFilter.GaussianBlur(10))
        sh.putalpha(sh.split()[3].point(lambda v: int(v * 0.5 * a)))
        canvas.alpha_composite(sh, (0, 62))
        canvas.alpha_composite(lay, (0, 60))
    d = ImageDraw.Draw(canvas)
    d.rectangle((0, H - 8, W, H), fill=(255, 255, 255, 46))
    d.rectangle((0, H - 8, int(W * min(1.0, t / total)), H), fill=AQUA + (255,))


# ── 組み立て ────────────────────────────────────────────────────────────
XFADE = 0.34


def timeline(scenes):
    starts, s = [], 0.0
    for sc in scenes:
        starts.append(s)
        s += sc["dur"] - XFADE
    total = s + XFADE
    return starts, total


def render_frame(scenes, starts, total, t):
    live = [(i, sc) for i, sc in enumerate(scenes)
            if starts[i] - 1e-6 <= t < starts[i] + sc["dur"] + 1e-6]
    if not live:
        live = [(len(scenes) - 1, scenes[-1])]
    base = None
    hide = 0.0
    for i, sc in live:
        lt = t - starts[i]
        img = render_scene(sc, max(0.0, lt), sc["dur"])
        if base is None:
            base = img
        else:
            k = smooth(lt / XFADE)
            base = Image.blend(base, img, k)
        if sc["type"] == "end":
            k = smooth(lt / XFADE) if len(live) > 1 else 1.0
            hide = max(hide, k)
    chrome(base, t, total, hide=hide)
    return base.convert("RGB")


def check(reel):
    """文言の検査。ここで止まるなら、止まったほうがいい"""
    bad = []
    for sc in reel["scenes"]:
        for k in ("head", "cap", "chip", "label_a", "label_b"):
            v = sc.get(k)
            if not v:
                continue
            for b in BANNED:
                if b in v:
                    bad.append(f"{reel['id']} / {k}: 禁止語「{b}」→ {v}")
            if PHONE.search(v):
                bad.append(f"{reel['id']} / {k}: 電話番号らしき数字 → {v}")
    return bad


def build(reel, poster=False, bgm=True, proxy=False, post=False):
    scenes = reel["scenes"]
    if post:
        # 通常投稿はリンクを押せない。広告用の「空いている日を見て予約する」は成立しないので差し替える
        scenes = [dict(sc) for sc in scenes]
        for sc in scenes:
            if sc["type"] == "end":
                sc["cta"] = reel.get("cta_post", "ご予約はプロフィールのリンクから")
    starts, total = timeline(scenes)
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / (f"{reel['id']}-投稿.mp4" if post else f"{reel['id']}.mp4")
    n = int(round(total * FPS))

    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        sys.exit("pip3 install imageio-ffmpeg が要ります")

    # BGM。他人の曲は権利の確認が要るので使わない。tools/make-reel-bgm.py でその場で合成する
    if bgm:
        from importlib.machinery import SourceFileLoader
        mb = SourceFileLoader("mb", str(ROOT / "tools" / "make-reel-bgm.py")).load_module()
        wav = OUT / f"bgm-{reel['id']}.wav"
        mb.write_wav(wav, mb.build(total))
        audio_in = ["-i", str(wav)]
    else:
        audio_in = ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"]

    cmd = [exe, "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           *audio_in,
           "-shortest",
           "-c:v", "libx264", "-preset", "slow", "-crf", "18",
           "-profile:v", "high", "-level", "4.0", "-pix_fmt", "yuv420p",
           "-x264-params", "keyint=60:min-keyint=30",
           "-c:a", "aac", "-b:a", "160k", "-ar", "44100",
           "-movflags", "+faststart", str(out)]
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(n):
        t = i / FPS
        fr = render_frame(scenes, starts, total, t)
        pr.stdin.write(fr.tobytes())
        if i % 60 == 0:
            print(f"  {reel['id']}  {t:5.1f}s / {total:.1f}s", flush=True)
    pr.stdin.close()
    if pr.wait() != 0:
        sys.exit("ffmpeg が失敗した")
    print(f"できた {out}  {total:.1f}秒  {out.stat().st_size/1024/1024:.1f}MB")

    if proxy:
        make_proxy(out)

    if poster:
        # 確認用：各カットの真ん中を1枚ずつ並べた静止画
        shots = []
        for i, sc in enumerate(scenes):
            shots.append(render_frame(scenes, starts, total, starts[i] + sc["dur"] * 0.72))
        cols = len(shots)
        sheet = Image.new("RGB", (cols * 360, 640), (12, 20, 28))
        for j, s in enumerate(shots):
            sheet.paste(s.resize((360, 640), Image.LANCZOS), (j * 360, 0))
        ps = OUT / f"{reel['id']}-コマ.jpg"
        sheet.save(ps, quality=90)
        print(f"できた {ps}")


def make_proxy(src: pathlib.Path):
    """確認用の軽い版（720x1280・2〜3MB）。Drive や LINE で配るときはこちら。
    入稿には使わない（Meta には 1080x1920 の本体を入れる）"""
    import imageio_ffmpeg
    exe = imageio_ffmpeg.get_ffmpeg_exe()
    dst = src.with_name(src.stem + "-軽量" + src.suffix)
    cmd = [exe, "-y", "-loglevel", "error", "-i", str(src),
           "-vf", "scale=720:1280:flags=lanczos",
           "-c:v", "libx264", "-preset", "slow", "-crf", "26",
           "-profile:v", "high", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(dst)]
    if subprocess.run(cmd).returncode != 0:
        sys.exit("ffmpeg が失敗した（軽量版）")
    print(f"できた {dst}  {dst.stat().st_size/1024/1024:.1f}MB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--check", action="store_true", help="文言の検査だけ")
    ap.add_argument("--poster", action="store_true", help="確認用の静止画も出す")
    ap.add_argument("--no-bgm", action="store_true", help="BGMを入れない（無音の音声だけ）")
    ap.add_argument("--proxy", action="store_true", help="確認用の軽量版（720x1280）も出す")
    ap.add_argument("--post", action="store_true", help="通常投稿版（末尾をプロフィールのリンク誘導にする）")
    a = ap.parse_args()

    reels = json.loads(SPEC.read_text(encoding="utf-8"))["reels"]
    if a.ids:
        reels = [r for r in reels if r["id"] in a.ids]
        if not reels:
            sys.exit("その id は無い")

    bad = [b for r in reels for b in check(r)]
    if bad:
        print("\n".join(bad))
        sys.exit("文言の検査で止めた")
    print(f"文言の検査 OK（{len(reels)}本）")
    if a.check:
        return
    for r in reels:
        build(r, poster=a.poster, bgm=not a.no_bgm, proxy=a.proxy, post=a.post)


if __name__ == "__main__":
    main()
