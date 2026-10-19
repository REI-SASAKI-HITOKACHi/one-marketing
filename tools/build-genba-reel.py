#!/usr/bin/env python3
"""現場で撮った動画（LINE経由）から、通常投稿のリールを1本つくる。

素材は tools/line-douga.py で落とした mp4（リポジトリには入れない）。
  python3 tools/line-douga.py 367 386 ~/.cache/one-hitter/line-video/2026-10-19
使い方:
  python3 tools/build-genba-reel.py            # dist/genba-reels/genba-20261019-a.mp4
  python3 tools/build-genba-reel.py --poster   # 確認用の静止画（各場面の中間）も出す

・元動画の音は使わない（会話に氏名・住所が入るおそれがあり、全編を聞いて確かめていないため）。BGMは make-reel-bgm.py（自作の合成音）。
・文字は見出し1行と日付の札だけ。ロゴ・社名・お客様名・電話は入れない。
・早送りは、かけた倍率を必ず札に書く。
要るもの: ffmpeg（imageio_ffmpeg）、Pillow、numpy、tools/fetch-fonts.py のフォント
"""
import argparse
import pathlib
import subprocess
import sys

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
FF = imageio_ffmpeg.get_ffmpeg_exe()
SRC = pathlib.Path.home() / ".cache/one-hitter/line-video/2026-10-19"
OUT = ROOT / "dist" / "genba-reels"
FONTS = ROOT / "assets" / "fonts"
W, H = 1080, 1920
INK_DEEP, INK = (6, 26, 42), (13, 59, 92)
PAPER, CTA = (250, 247, 242), (192, 48, 12)
DATE = "2026年10月19日・エアコン"

# (行番号, 開始秒, 取り込む秒数, 出力の秒数, 見出し, 札)
SCENES = [
    (380, 0, 300, 8.0, "洗っている間に、\n水はこう変わります", DATE + "・5分間を約38倍に早送り"),
    (376, 62, 5, 5.0, "洗い出した水です", DATE),
    (369, 1, 4, 4.0, "洗ったあとの内部です", DATE),
    (373, 1, 3.5, 3.5, "洗ったあとの内部です", DATE),
]
END_SEC = 3.0


def font(size, w=900):
    return ImageFont.truetype(str(FONTS / f"ZenKakuGothicNew-{w}.ttf"), size)


def overlay(head, chip):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sc = Image.new("RGBA", (W, 520), (0, 0, 0, 0))
    d = ImageDraw.Draw(sc)
    for y in range(520):
        d.line([(0, y), (W, y)], fill=(6, 26, 42, int(190 * (1 - y / 520))))
    im.alpha_composite(sc, (0, 0))
    d = ImageDraw.Draw(im)
    f = font(66)
    y = 110
    for ln in head.split("\n"):
        d.text((64, y + 3), ln, font=f, fill=(0, 0, 0, 120))
        d.text((64, y), ln, font=f, fill=PAPER + (255,))
        y += 96
    fc = font(34, 700)
    tw = d.textlength(chip, font=fc)
    d.rounded_rectangle((64, H - 250, 64 + tw + 44, H - 250 + 64), radius=14, fill=(8, 22, 32, 215))
    d.text((86, H - 250 + 12), chip, font=fc, fill=(255, 255, 255, 255))
    return im


def end_card():
    im = Image.new("RGB", (W, H), INK_DEEP)
    d = ImageDraw.Draw(im)
    for y in range(H):
        k = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(INK[i] * (1 - k) + INK_DEEP[i] * k) for i in range(3)))
    f = font(60)
    for i, ln in enumerate(["江戸川区のハウスクリーニング", "ワンヒッター"]):
        tw = d.textlength(ln, font=f)
        d.text(((W - tw) / 2, 700 + i * 96), ln, font=f, fill=PAPER)
    bw, bh, by = 900, 130, 1000
    d.rounded_rectangle(((W - bw) / 2, by, (W + bw) / 2, by + bh), radius=bh // 2, fill=CTA)
    fb = font(46)
    lab = "ご予約はプロフィールのリンクから"
    d.text(((W - d.textlength(lab, font=fb)) / 2, by + 36), lab, font=fb, fill=(255, 255, 255))
    return im


def run(args):
    subprocess.run([FF, "-y", "-loglevel", "error"] + args, check=True)


def build(poster=False):
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = OUT / "_tmp"
    tmp.mkdir(exist_ok=True)
    parts = []
    for i, (n, ss, take, dur, head, chip) in enumerate(SCENES):
        src = next(SRC.glob(f"{n}_*.mp4"))
        ov = tmp / f"ov{i}.png"
        overlay(head, chip).save(ov)
        out = tmp / f"s{i}.mp4"
        speed = take / dur
        vf = (f"[0:v]setpts=PTS/{speed},fps=30,split[a][b];"
              f"[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=40:8[bg];"
              f"[b]scale={W}:{H}:force_original_aspect_ratio=decrease[fg];"
              f"[bg][fg]overlay=(W-w)/2:(H-h)/2[v];[v][1:v]overlay=0:0,format=yuv420p[o]")
        run(["-ss", str(ss), "-t", str(take), "-i", str(src), "-i", str(ov), "-filter_complex", vf,
             "-map", "[o]", "-t", str(dur), "-r", "30", "-c:v", "libx264", "-crf", "20", "-an", str(out)])
        parts.append(out)
    ec = tmp / "end.png"
    end_card().save(ec)
    eo = tmp / "end.mp4"
    run(["-loop", "1", "-i", str(ec), "-t", str(END_SEC), "-r", "30", "-vf", "format=yuv420p",
         "-c:v", "libx264", "-crf", "20", str(eo)])
    parts.append(eo)
    total = sum(s[3] for s in SCENES) + END_SEC
    lst = tmp / "list.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    bgm = OUT / "bgm.wav"
    subprocess.run([sys.executable, str(ROOT / "tools" / "make-reel-bgm.py"), f"{total:.1f}", str(bgm)], check=True)
    final = OUT / "genba-20261019-a.mp4"
    run(["-f", "concat", "-safe", "0", "-i", str(lst), "-i", str(bgm),
         "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-crf", "20", "-c:a", "aac", "-b:a", "160k",
         "-af", f"afade=t=out:st={total-1.5:.1f}:d=1.5", "-t", f"{total:.2f}", "-movflags", "+faststart", str(final)])
    print(final, f"{total:.1f}秒")
    if poster:
        t = 0.0
        for i, s in enumerate(SCENES):
            run(["-ss", f"{t + s[3] / 2:.2f}", "-i", str(final), "-frames:v", "1", str(OUT / f"poster{i}.png")])
            t += s[3]
        run(["-ss", f"{total - 1:.2f}", "-i", str(final), "-frames:v", "1", str(OUT / "poster-end.png")])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--poster", action="store_true")
    build(ap.parse_args().poster)
