#!/usr/bin/env python3
"""Instagram/Facebook 広告用クリエイティブ（2テーマ×静止画1・縦動画1）と確認ページを作る。

依頼 20261024-03-web-inflow（オーナー指示「広告用のクリエイティブを作成して嶺へプレゼンして」）。
  python3 tools/build-ad-creatives.py     → dist/ad-creatives/ に PNG・MP4・確認ページ（確認ページ.png）

テーマ
  A エアコン：11月の作業は1台10%引き（お掃除機能なし 9,702円・税込）
  B 年末の水まわり：レンジフード・浴室・キッチン 11月10%引き（1箇所 16,632円・税込）

守ること
  ・本舗のロゴ・社名・番号、お客様の名前、電話番号を入れない（素材は assets/photos と 10/19 の現場動画。目視済み）
  ・出張費・「追加料金なし」の言い切りを書かない／汚水に台数・杯数を書かない
  ・文字は見出し1つ＋価格の帯。冒頭の1秒に最も汚れた画を置く（動画）
  ・元動画の音は使わない。BGMは make-reel-bgm.py の自作合成音
要るもの: ffmpeg（imageio_ffmpeg）、Pillow、numpy、assets/fonts、~/.cache/one-hitter/line-video/2026-10-19
"""
import pathlib
import subprocess
import sys

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
FF = imageio_ffmpeg.get_ffmpeg_exe()
PHOTOS = ROOT / "assets" / "photos"
FONTS = ROOT / "assets" / "fonts"
SRC = pathlib.Path.home() / ".cache/one-hitter/line-video/2026-10-19"
OUT = ROOT / "dist" / "ad-creatives"
TMP = OUT / "_tmp"

INK, INK_DEEP = (13, 59, 92), (6, 26, 42)
PAPER, CTA, MARK = (250, 247, 242), (192, 48, 12), (255, 214, 90)

BANNED = ["最安", "No.1", "今だけ", "残りわずか", "98.8", "出張費が一切", "出張費無料", "追加料金なし",
          "本舗", "日本一", "完全無料", "必ず落ち", "1台ぶん", "バケツ1杯"]

A_OFFER = ("11月の作業は1台10%引き", "お掃除機能なし  9,702円（税込）", "1箇所のご依頼が対象です",
           "11月のネット予約は、\n防カビコート（3,300円・税込）を1台分無料")
B_OFFER = ("11月の作業は10%引き", "レンジフード・浴室・キッチン  1箇所 16,632円（税込）", "1箇所のご依頼が対象です")
CTA_LABEL = "空いている日を見る"
SIGN = "ワンヒッター｜江戸川区北葛西　東京・千葉・神奈川"


def font(size, w=900):
    return ImageFont.truetype(str(FONTS / f"ZenKakuGothicNew-{w}.ttf"), size)


def check(*texts):
    for t in texts:
        for b in BANNED:
            if b in t:
                sys.exit(f"禁止語「{b}」が入っています: {t}")


def photo(name, crop=None):
    im = Image.open(PHOTOS / name).convert("RGB")
    if crop:
        w, h = im.size
        im = im.crop((int(w * crop[0]), int(h * crop[1]), int(w * crop[2]), int(h * crop[3])))
    return im


def gradient(w, h, a=INK, b=INK_DEEP):
    im = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(im)
    for y in range(h):
        k = y / h
        d.line([(0, y), (w, y)], fill=tuple(int(a[i] * (1 - k) + b[i] * k) for i in range(3)))
    return im


def fit_cover(im, w, h, cx=0.5, cy=0.5):
    s = max(w / im.width, h / im.height)
    im = im.resize((int(im.width * s) + 1, int(im.height * s) + 1), Image.LANCZOS)
    x = int((im.width - w) * cx)
    y = int((im.height - h) * cy)
    return im.crop((x, y, x + w, y + h))


def text_lines(d, xy, lines, f, fill, lh, shadow=True):
    x, y = xy
    for ln in lines:
        if shadow:
            d.text((x + 2, y + 3), ln, font=f, fill=(0, 0, 0, 110))
        d.text((x, y), ln, font=f, fill=fill)
        y += lh
    return y


def button(d, cx, y, label, w=760, h=118, size=44):
    d.rounded_rectangle((cx - w // 2, y, cx + w // 2, y + h), radius=h // 2, fill=CTA)
    f = font(size)
    d.text((cx - d.textlength(label, font=f) / 2, y + (h - size) / 2 - 4), label, font=f, fill=(255, 255, 255))


def offer_block(d, W, y, offer):
    a, b, c = offer[:3]
    d.text((64, y), a, font=font(76), fill=PAPER)
    y += 104
    d.text((64, y), b, font=font(40 if len(b) > 22 else 52), fill=MARK)
    y += 70
    if len(offer) > 3:
        for ln in offer[3].split("\n"):
            d.text((64, y), ln, font=font(40), fill=(255, 255, 255))
            y += 52
    d.text((64, y), c, font=font(32, 500), fill=(205, 220, 232))
    return y + 52


# ── 静止画（1080x1350 / 4:5）────────────────────────────────────────────
def still(name, head, img, offer, crop_pos=(0.5, 0.5)):
    check(head, *offer)
    W, H = 1080, 1350
    im = gradient(W, H)
    d = ImageDraw.Draw(im)
    text_lines(d, (64, 70), head, font(72), PAPER, 100)
    ph_h, y0 = (500, 810) if len(offer) > 3 else (620, 950)
    ph = fit_cover(img, W, ph_h, *crop_pos)
    im.paste(ph, (0, 300))
    d = ImageDraw.Draw(im)
    y = offer_block(d, W, y0, offer)
    button(d, W // 2, y + 6, CTA_LABEL, w=640, h=104, size=42)
    d.text((W - 64 - d.textlength(SIGN, font=font(24, 500)), H - 46), SIGN, font=font(24, 500), fill=(160, 185, 205))
    p = OUT / f"{name}.png"
    im.save(p)
    return p


# ── 動画（1080x1920）──────────────────────────────────────────────────
def ffmpeg(*a):
    subprocess.run([FF, "-y", "-loglevel", "error", *map(str, a)], check=True)


def overlay(head, chip=None):
    im = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    sc = Image.new("RGBA", (1080, 520), (0, 0, 0, 0))
    d = ImageDraw.Draw(sc)
    for y in range(520):
        d.line([(0, y), (1080, y)], fill=(6, 26, 42, int(200 * (1 - y / 520))))
    im.alpha_composite(sc, (0, 0))
    d = ImageDraw.Draw(im)
    text_lines(d, (64, 110), head, font(70), PAPER + (255,), 98)
    if chip:
        fc = font(34, 700)
        tw = d.textlength(chip, font=fc)
        d.rounded_rectangle((64, 1920 - 250, 64 + tw + 44, 1920 - 186), radius=14, fill=(8, 22, 32, 215))
        d.text((86, 1920 - 238), chip, font=fc, fill=(255, 255, 255, 255))
    return im


def end_card(path, offer):
    check(*offer)
    im = gradient(1080, 1920)
    d = ImageDraw.Draw(im)
    a, b, c = offer[:3]
    d.text((64, 640), a, font=font(84), fill=PAPER)
    parts = b.split("  ") if len(b) > 22 else [b]
    y = 770
    for ln in parts:
        d.text((64, y), ln, font=font(58), fill=MARK)
        y += 84
    if len(offer) > 3:
        for ln in offer[3].split("\n"):
            d.text((64, y + 6), ln, font=font(44), fill=(255, 255, 255))
            y += 60
    d.text((64, y + 6), c, font=font(36, 500), fill=(205, 220, 232))
    y += 100
    button(d, 540, y, CTA_LABEL, w=860, h=132, size=52)
    d.text((540 - d.textlength(SIGN, font=font(30, 500)) / 2, y + 190), SIGN, font=font(30, 500), fill=(160, 185, 205))
    im.save(path)


def seg_video(n, src, ss, take, dur, head, chip=None):
    ov = TMP / f"ov{n}.png"
    overlay(head, chip).save(ov)
    out = TMP / f"v{n}.mp4"
    speed = take / dur
    fc = (f"[0:v]setpts=PTS/{speed},fps=30,split[a][b];"
          f"[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=40:8[bg];"
          f"[b]scale=1080:1920:force_original_aspect_ratio=decrease[fg];"
          f"[bg][fg]overlay=(W-w)/2:(H-h)/2[v];[v][1:v]overlay=0:0,format=yuv420p[o]")
    ffmpeg("-ss", ss, "-t", take, "-i", src, "-i", ov, "-filter_complex", fc, "-map", "[o]", "-t", dur,
           "-r", 30, "-c:v", "libx264", "-crf", "20", "-an", out)
    return out


def seg_photo(n, img, dur, head, chip=None, zoom=(1.0, 1.07)):
    W, H = 1080, 1920
    bg = fit_cover(img, W, H).filter(ImageFilter.GaussianBlur(40))
    fg = img.copy()
    s = min(W / fg.width, H / fg.height)
    fg = fg.resize((int(fg.width * s), int(fg.height * s)), Image.LANCZOS)
    if fg.height < H * 0.55:                       # 横長は幅いっぱいに置き、上下はぼかしで埋める
        pass
    bg.paste(fg, ((W - fg.width) // 2, (H - fg.height) // 2))
    bg = bg.convert("RGBA")
    bg.alpha_composite(overlay(head, chip))
    still_path = TMP / f"p{n}.png"
    bg.convert("RGB").save(still_path)
    out = TMP / f"v{n}.mp4"
    frames = int(dur * 30)
    z = f"{zoom[0]}+({zoom[1]}-{zoom[0]})*on/{frames}"
    ffmpeg("-loop", 1, "-i", still_path, "-vf",
           f"scale=2160:3840,zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s=1080x1920:fps=30,format=yuv420p",
           "-t", dur, "-c:v", "libx264", "-crf", "20", "-an", out)
    return out


def assemble(name, parts, total):
    lst = TMP / f"{name}.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    bgm = TMP / f"{name}.wav"
    subprocess.run([sys.executable, str(ROOT / "tools" / "make-reel-bgm.py"), f"{total:.1f}", str(bgm)], check=True,
                   stdout=subprocess.DEVNULL)
    final = OUT / f"{name}.mp4"
    ffmpeg("-f", "concat", "-safe", 0, "-i", lst, "-i", bgm, "-map", "0:v", "-map", "1:a", "-c:v", "libx264",
           "-crf", "20", "-c:a", "aac", "-b:a", "160k", "-af", f"afade=t=out:st={total - 1.2:.1f}:d=1.2",
           "-t", f"{total:.2f}", "-movflags", "+faststart", final)
    return final


def video_a():
    check("洗い出した水です", "洗ったあとの内部です")
    clip = lambda n: next(SRC.glob(f"{n}_*.mp4"))
    parts = [
        seg_video(1, clip(376), 70, 3.0, 3.0, ["洗い出した水です"]),
        seg_video(2, clip(380), 0, 300, 3.0, ["5分間で、水はここまで"], "2026年10月19日・5分間を早送り"),
        seg_video(3, clip(369), 1, 2.5, 2.5, ["洗ったあとの内部です"], "2026年10月19日・エアコン"),
    ]
    ec = TMP / "endA.png"
    end_card(ec, A_OFFER)
    ffmpeg("-loop", 1, "-i", ec, "-t", 3.0, "-r", 30, "-vf", "format=yuv420p", "-c:v", "libx264", "-crf", "20", TMP / "endA.mp4")
    parts.append(TMP / "endA.mp4")
    return assemble("A2-エアコン-動画", parts, 11.5)


def video_b():
    heads = [
        (1, "ph-440.jpg", (0.0, 0.0, 0.7, 0.88), ["フィルターの油汚れです"], "2026年8月24日・レンジフード"),
        (2, "ph-748.jpg", (0.0, 0.0, 1.0, 0.86), ["レンジフードの奥を、", "見たことがありますか"], "2026年9月12日・レンジフード"),
        (3, "ph-443.jpg", None, ["取り外して、", "分解して洗います"], "作業中のファン"),
    ]
    parts = []
    for n, f, crop, h, chip in heads:
        check(*h)
        parts.append(seg_photo(n + 10, photo(f, crop), 3.0, h, chip))
    ec = TMP / "endB.png"
    end_card(ec, B_OFFER)
    ffmpeg("-loop", 1, "-i", ec, "-t", 2.5, "-r", 30, "-vf", "format=yuv420p", "-c:v", "libx264", "-crf", "20", TMP / "endB.mp4")
    parts.append(TMP / "endB.mp4")
    return assemble("B2-水まわり-動画", parts, 11.5)


def frames(video, name, ts):
    out = []
    for i, t in enumerate(ts):
        p = TMP / f"{name}-f{i}.png"
        ffmpeg("-ss", t, "-i", video, "-frames:v", 1, "-vf", "scale=216:384", p)
        out.append(Image.open(p).convert("RGB"))
    return out


def wrap(d, text, f, width):
    lines, cur = [], ""
    for ch in text:
        if d.textlength(cur + ch, font=f) > width:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    return lines + [cur]


DIFF = {
    "A1": "（11月のネット予約は防カビコート1台分無料の1行を追加）10/21に低いと言われた版に静止画は無かった。写真を画面の約半分に大きく置き、文字は見出し1つと価格の帯だけにした。",
    "A2": "静止画をゆっくり拡大した版から、10/19の現場で撮った動画に替えた。1秒目に洗い出した水の画、23秒→11.5秒、見出しは1場面1つ、価格は最後のカードに集約、元の音は使わず自作BGM。",
    "B1": "写真を画面の約半分に大きく置き、見出しは1つ。価格と対象（1箇所）を下の帯に固定し、押す場所を1つにした。",
    "B2": "21〜23秒→11.5秒、見出しは1場面1つ、1秒目をいちばん汚れの強い画（フィルターの油汚れ）に、価格は最後のカード。弱点：素材が静止画なので、動きは拡大だけ。和真さんの現場動画（水まわり）が撮れたら差し替える。",
}


def review_page(sa, sb, va, vb):
    W, H = 2400, 1560
    im = Image.new("RGB", (W, H), (246, 243, 238))
    d = ImageDraw.Draw(im)
    d.text((50, 30), "広告用クリエイティブ 確認ページ（Instagram／Facebook）", font=font(46), fill=INK_DEEP)
    d.text((50, 96), "2026-10-24 作成 ／ web-inflow ／ 出稿はしていません（お金は動きません）。出稿・差し替えはオーナー承認後。", font=font(26, 500), fill=(60, 70, 80))
    d.text((50, 134), "比較の基準：10/21 に「質が低い」と言われた版＝静止画をゆっくり動かした21〜23秒のリール3本。", font=font(26, 500), fill=(60, 70, 80))
    f24, f28 = font(24, 500), font(28, 700)
    for x0, title, s, v, k1, k2 in ((50, "A　エアコン（11月 1台10%引き・9,702円）", sa, va, "A1", "A2"),
                                    (1250, "B　年末の水まわり（11月10%引き・16,632円）", sb, vb, "B1", "B2")):
        d.text((x0, 200), title, font=font(36), fill=INK)
        im.paste(Image.open(s).resize((540, 675)), (x0, 262))
        d.text((x0, 948), "静止画 1080×1350（4:5）", font=f28, fill=INK_DEEP)
        y = 988
        for ln in wrap(d, "違い：" + DIFF[k1], f24, 540):
            d.text((x0, y), ln, font=f24, fill=(40, 50, 60))
            y += 34
        ts = (0.6, 4.2, 8.0, 11.6) if k2 == "A2" else (0.6, 3.6, 7.0, 11.4)
        for i, fr in enumerate(frames(v, k2, ts)):
            im.paste(fr, (x0 + 580 + (i % 2) * 226, 262 + (i // 2) * 394))
        d.text((x0 + 580, 1058), "縦動画 1080×1920（9:16）", font=f28, fill=INK_DEEP)
        y = 1098
        for ln in wrap(d, "違い：" + DIFF[k2], f24, 440):
            d.text((x0 + 580, y), ln, font=f24, fill=(40, 50, 60))
            y += 34
    d.text((50, 1370), "守った点：本舗のロゴ・社名・番号／お客様の名前／電話番号なし。出張費・「追加料金なし」の言い切りなし。汚水に台数・杯数なし。10%引きは「1箇所のご依頼が対象」。", font=f24, fill=(40, 50, 60))
    d.text((50, 1410), "確認できていない点：広告の審査（Meta）と、広告アカウント側の動画の表示は未確認。9,702円・16,632円は 税込の10%引き（10,780円・18,480円の90%）。", font=f24, fill=(40, 50, 60))
    d.text((50, 1450), "調査（docs/動画広告-業種を問わない調査-1枚-2026-10-24.md）から反映：冒頭の1〜3秒に最も見せたい画／15秒以内（11.5秒）／見出しは短く1つ／最後に具体的な行動。防カビ無料（11月のネット予約・エアコン・1回の予約につき1台分）はA1・A2に1行で入れた。防カビコートは cmo ブランチの price-master（10/16 訂正後）どおり 3,300円（税込）と表記。", font=f24, fill=(40, 50, 60))
    d.text((50, 1490), "ファイル：dist/ad-creatives/（A1・B1 PNG／A2・B2 MP4）。リポジトリには deliver/ad-creatives-2026-10/ に置く。", font=f24, fill=(40, 50, 60))
    p = OUT / "確認ページ.png"
    im.save(p)
    return p


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(exist_ok=True)
    sa = still("A1-エアコン-静止画", ["吹き出し口の奥に、", "黒い点はありませんか"], photo("ph-474.jpg"), A_OFFER, (0.5, 0.35))
    sb = still("B1-水まわり-静止画", ["換気扇のフィルター、", "この状態になっていませんか"], photo("ph-440.jpg", (0.0, 0.0, 0.7, 0.88)), B_OFFER, (0.4, 0.45))
    va = video_a()
    vb = video_b()
    print("A1", sa, "\nB1", sb, "\nA2", va, "\nB2", vb)
    print("確認ページ", review_page(sa, sb, va, vb))


if __name__ == "__main__":
    main()
