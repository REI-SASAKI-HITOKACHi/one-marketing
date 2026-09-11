#!/usr/bin/env python3
"""図鑑の1案件（data/zukan/<id>.json）から、縦型ショート動画（9:16・約20秒・MP4）を組み立てる。

方針（ここを外すと嘘の実績になる）:
  - 使うのは現場で撮った実写だけ。生成AIで映像を作らない・足さない・直さない。
    動くのはカメラワーク（ゆっくり寄る）と、作業前→作業後のワイプだけ。
  - 作業前→作業後のワイプは、JSONの「組写真」（同一箇所の確認済みペア）にしか使わない。
  - 全フレームに「実際の現場写真（合成なし）」の表示を入れる。
  - 文言は JSON の「見えたもの」「ひとこと」をそのまま使う（生成器で断定語の検査済み）。

使い方:
  python3 tools/build-shorts.py                 # data/zukan/ の全件
  python3 tools/build-shorts.py 2026-09-04-aircon
  出力: dist/shorts/<id>.mp4（dist/ は .gitignore 済み。動画はコミットしない）

ffmpeg は imageio-ffmpeg 同梱の libx264 付きを使う（pip3 install imageio-ffmpeg pillow）。
"""
import json
import pathlib
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "zukan"
PHOTOS = ROOT / "assets" / "photos"
OUT = ROOT / "dist" / "shorts"
FONT = "/usr/share/fonts/opentype/ipafont-gothic/ipagp.ttf"

W, H, FPS = 1080, 1920, 24
BG = (14, 30, 36)          # 帯の色（サイトの --ink に近い）
ACCENT = (78, 192, 212)
CTA = (240, 118, 75)
TAISHOU = {"aircon": "エアコン", "hood": "レンジフード", "bath": "浴室", "washer": "洗濯機", "kitchen": "キッチン", "toilet": "トイレ"}


def ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        sys.exit("pip3 install imageio-ffmpeg が要ります")


def font(size):
    return ImageFont.truetype(FONT, size)


def wrap(text, f, max_w):
    """日本語は単語で切れないので、1文字ずつ幅を測って折り返す"""
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


def draw_text(img, text, size, y, color=(255, 255, 255), max_w=W - 120, align="center", shadow=True, line_gap=1.35):
    d = ImageDraw.Draw(img)
    f = font(size)
    lines = wrap(text, f, max_w)
    lh = int(size * line_gap)
    for i, ln in enumerate(lines):
        tw = f.getlength(ln)
        x = (W - tw) / 2 if align == "center" else 60
        yy = y + i * lh
        if shadow:
            for dx, dy in ((2, 2), (-2, 2), (2, -2), (-2, -2), (0, 3)):
                d.text((x + dx, yy + dy), ln, font=f, fill=(0, 0, 0))
        d.text((x, yy), ln, font=f, fill=color)
    return y + len(lines) * lh


def load(name):
    im = ImageOps.exif_transpose(Image.open(PHOTOS / name)).convert("RGB")
    return im


def cover(im, w, h, zoom=1.0):
    """w×h を覆うように拡大し、中央を切り出す。zoom>1 で寄る"""
    s = max(w / im.width, h / im.height) * zoom
    nw, nh = int(im.width * s) + 1, int(im.height * s) + 1
    r = im.resize((nw, nh), Image.BILINEAR)
    x, y = (nw - w) // 2, (nh - h) // 2
    return r.crop((x, y, x + w, y + h))


def canvas(photo, zoom):
    """写真を中央に置き、上下を帯にする。横長は正方形、縦長は3:4で置く"""
    c = Image.new("RGB", (W, H), BG)
    if photo.width >= photo.height:
        area = (W, W)
    else:
        area = (W, 1440)
    p = cover(photo, area[0], area[1], zoom)
    c.paste(p, (0, (H - area[1]) // 2))
    return c, (H - area[1]) // 2, (H + area[1]) // 2


def badge(img):
    d = ImageDraw.Draw(img)
    f = font(28)
    t = "実際の現場写真（合成なし）"
    tw = f.getlength(t)
    d.rounded_rectangle((W - tw - 90, 60, W - 40, 116), radius=14, fill=(0, 0, 0))
    d.text((W - tw - 65, 70), t, font=f, fill=(255, 255, 255))


def frame_photo(photo, zoom, title, caption, top, bottom):
    img, y0, y1 = canvas(photo, zoom)
    badge(img)
    if title:
        draw_text(img, title, 56, max(140, y0 - 200), color=(255, 255, 255))
    if caption:
        # 下の帯に入りきらないときは写真の下端に重ねる
        yy = y1 + 40 if H - y1 >= 220 else y1 - 200
        draw_text(img, caption, 44, yy, color=(255, 255, 255))
    return img


def ease(t):
    return t * t * (3 - 2 * t)


def frames_kenburns(photo, secs, title, caption, z0=1.0, z1=1.12):
    n = int(secs * FPS)
    for i in range(n):
        z = z0 + (z1 - z0) * ease(i / max(n - 1, 1))
        yield frame_photo(photo, z, title, caption, None, None)


def frames_wipe(before, after, secs, caption):
    """作業前を見せ、左から右へ作業後が現れる。同一箇所のペアにしか使わない"""
    n = int(secs * FPS)
    hold = int(FPS * 0.9)
    b_img, y0, y1 = canvas(before, 1.0)
    a_img, _, _ = canvas(after, 1.0)
    for i in range(n):
        if i < hold:
            x = 0
        elif i >= n - hold:
            x = W
        else:
            x = int(W * ease((i - hold) / max(n - 2 * hold, 1)))
        img = b_img.copy()
        if x > 0:
            img.paste(a_img.crop((0, 0, x, H)), (0, 0))
        d = ImageDraw.Draw(img)
        if 0 < x < W:
            d.rectangle((x - 3, y0, x + 3, y1), fill=(255, 255, 255))
        badge(img)
        d.rounded_rectangle((40, y0 + 24, 250, y0 + 84), radius=12, fill=(0, 0, 0))
        d.text((62, y0 + 34), "BEFORE", font=font(34), fill=(255, 255, 255))
        if x > 300:
            d.rounded_rectangle((W - 220, y0 + 24, W - 40, y0 + 84), radius=12, fill=(0, 0, 0))
            d.text((W - 200, y0 + 34), "AFTER", font=font(34), fill=(255, 255, 255))
        draw_text(img, caption, 44, y1 + 40)
        yield img


# 締めのCTA。誘導先はLP（2026-09-11 オーナー決定：予約フォームでも相談所でもなくLP）。
# Instagramの本文にはリンクを貼れないので「プロフィールの『◯◯』のリンクから」と、リンク欄の表示名で指す
LINK_LABEL = {"aircon": "エアコン", "hood": "水まわり", "bath": "水まわり", "washer": "水まわり", "kitchen": "水まわり"}


def frames_end(photo, secs, hitokoto, taishou="aircon"):
    n = int(secs * FPS)
    base, y0, y1 = canvas(photo, 1.06)
    base = base.filter(ImageFilter.GaussianBlur(6))
    dark = Image.new("RGB", (W, H), (0, 0, 0))
    base = Image.blend(base, dark, 0.55)
    label = LINK_LABEL.get(taishou, "水まわり")
    for i in range(n):
        img = base.copy()
        badge(img)
        y = draw_text(img, hitokoto, 48, 520, max_w=W - 160)
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((120, y + 120, W - 120, y + 260), radius=70, fill=CTA)
        draw_text(img, "分解して、内部から洗います", 50, y + 158, shadow=False)
        draw_text(img, f"ご予約は プロフィールの「{label}」のリンクから", 38, y + 320, color=ACCENT, shadow=False)
        draw_text(img, "ワンヒッター｜江戸川区のハウスクリーニング", 32, y + 390, color=(200, 210, 214), shadow=False)
        yield img


def build(c: dict):
    t = TAISHOU[c["対象"]]
    title = f"{c['地名']}の{t}の中身"
    mieta = list(c["見えたもの"])
    before = [load(f) for f in c["写真"]["before"]]
    water = [load(f) for f in c["写真"]["汚水"]]
    pairs = [(load(b), load(a)) for b, a in c["組写真"]]

    seq = []
    # 1. つかみ：最初の1枚に題名
    seq.append(frames_kenburns(before[0], 2.5, title, f"撮影 {c['日付']}", 1.0, 1.05))
    # 2. 作業前の写真に「見えたもの」を1つずつ
    photos = before + water
    for i, p in enumerate(photos[:3]):
        cap = mieta[i] if i < len(mieta) else ("洗浄後に出た汚水" if p in water else "")
        seq.append(frames_kenburns(p, 3.5, None, cap, 1.0, 1.14))
    # 3. 同一箇所のペアがあればワイプ
    for b, a in pairs[:1]:
        seq.append(frames_wipe(b, a, 4.0, "同じ場所を、同じ角度から"))
    # 4. 締め
    seq.append(frames_end(before[0], 3.5, c["ひとこと"], c["対象"]))

    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"{c['id']}.mp4"
    cmd = [ffmpeg_exe(), "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",   # 無音の音声トラック（無音でも音声が無いと受け付けない媒体があるため）
           "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium", "-crf", "20",
           "-c:a", "aac", "-b:a", "64k", "-movflags", "+faststart", str(out)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n = 0
    for gen in seq:
        for img in gen:
            p.stdin.write(img.tobytes()); n += 1
    p.stdin.close(); p.wait()
    if p.returncode:
        sys.exit("ffmpeg が失敗しました")
    print(f"{out}  {n / FPS:.1f}秒  {out.stat().st_size / 1e6:.1f}MB")


def main():
    ids = sys.argv[1:]
    for path in sorted(SRC.glob("*.json")):
        c = json.loads(path.read_text(encoding="utf-8"))
        if ids and c["id"] not in ids:
            continue
        build(c)


if __name__ == "__main__":
    main()
