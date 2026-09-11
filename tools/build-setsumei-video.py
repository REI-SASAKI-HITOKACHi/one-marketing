#!/usr/bin/env python3
"""施設のスタッフ向けに「カードを置くだけです」を説明する約2分の横型動画（16:9・MP4）を作る。

産院・小児科・ペットショップ・動物病院に A6 カードの設置をお願いするとき、メールに添えて送る。
文字だけのスライドを順に見せる（写真・人物は使わない。施設側に余計な印象を与えないため）。
音声は入れない（受付で音を出さずに見られるように。台本は別ファイルに出すので、後からナレーションを付けられる）。

使い方:
  python3 tools/build-setsumei-video.py            # 赤ちゃん版・ペット版の両方
  python3 tools/build-setsumei-video.py pet
  出力: dist/dokuhon/setsumei-<案>.mp4 と dist/dokuhon/setsumei-script.md（台本＋秒数）
        （dist/ は .gitignore 済み。動画はコミットしない）

スライド 3・4 には build-a6-card.py が作るカード表面を入れる（無ければその場で作る）。
ffmpeg は imageio-ffmpeg 同梱の libx264 付きを使う（build-shorts.py と同じ）。
"""
import importlib.util
import pathlib
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "dist" / "dokuhon"
FONT = "/usr/share/fonts/opentype/ipafont-gothic/ipagp.ttf"

W, H, FPS = 1920, 1080, 30
MARGIN = 120
FADE = 0.5                      # スライド間のクロスフェード秒
HEAD_SIZE, SUB_SIZE = 64, 36

GROUND = (0xFA, 0xF7, 0xF2)
INK = (0x14, 0x32, 0x3D)
ACCENT = (0x0E, 0x7C, 0x93)
MUTED = (0x5A, 0x6B, 0x72)

# (秒, 見出し, 補足, カード画像を入れるか)。「{taishou}」は案ごとに置き換える
SLIDES = [
    (6, "A6のカードを1枚、置いていただくだけです。",
     "ワンヒッター株式会社（江戸川区北葛西）", False),
    (10, "このカードは、{taishou}を迎えるご家庭向けの読み物への入口です。",
     "エアコンや浴室の中に見えないまま溜まっている汚れを、現場の写真と東京都の調査の数字でお話しする読み物です。売り込みの資料ではありません。", False),
    (12, "置く場所は、受付・レジ横・待合のどこでも。",
     "立てて置ける卓上スタンド（100円ショップのカードスタンドで十分です）か、掲示板に画鋲で。", True),
    (10, "ご説明は要りません。",
     "利用者の方がスマホでQRを読むと、読み物が開きます。貴施設のスタッフの方が何かをする必要はありません。", True),
    (12, "毎週月曜に、何名が読まれたかをメールでお知らせします。",
     "貴施設のカードからの閲覧数・お申込み数だけをお伝えします（個人が分かる情報は含みません）。", False),
    (12, "ご利用があった場合の紹介料（該当する施設のみ）",
     "貴施設のカードからご利用があった場合、ご利用額の12%を月末締め・翌月末にお支払いします。医療法人・社会福祉法人など、受け取りが難しい施設には、情報提供のみでお願いしています。", False),
    (10, "カードの補充・撤去は、メール1通で。",
     "不要になったら、いつでも撤去してください。ご連絡をいただければ、報告メールも止めます。", False),
    (10, "ありがとうございます。",
     "ワンヒッター株式会社　080-8043-8259　東京都江戸川区北葛西5-14-11", False),
]
TAISHOU = {"akachan": "赤ちゃん", "pet": "ペット"}


def ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        sys.exit("pip3 install imageio-ffmpeg が要ります")


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


def draw_block(d, text, size, x, y, max_w, color=INK, line_gap=1.5):
    f = font(size)
    lines = wrap(text, f, max_w)
    lh = int(size * line_gap)
    for i, ln in enumerate(lines):
        d.text((x, y + i * lh), ln, font=f, fill=color)
    return y + len(lines) * lh


def card_front(variant: str) -> Image.Image:
    """カード表面。dist に無ければ build-a6-card.py を読み込んで作る（ファイル名にハイフンがあるので importlib）"""
    path = OUT / f"card-{variant}-card-front.png"
    if not path.exists():
        spec = importlib.util.spec_from_file_location("build_a6_card", ROOT / "tools" / "build-a6-card.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.build(variant)
    return Image.open(path).convert("RGB")


def slide_image(idx: int, head: str, sub: str, card: Image.Image | None) -> Image.Image:
    img = Image.new("RGB", (W, H), GROUND)
    d = ImageDraw.Draw(img)
    text_w = W - 2 * MARGIN

    if card is not None:
        # 右にカードを立てて置き、文字は左の列に収める
        ch = H - 2 * MARGIN
        cw = int(card.width * ch / card.height)
        c = card.resize((cw, ch), Image.LANCZOS)
        cx = W - MARGIN - cw
        # 紙らしく見えるよう薄い影と枠
        d.rectangle((cx + 10, MARGIN + 10, cx + cw + 10, MARGIN + ch + 10), fill=(0xE3, 0xDD, 0xD3))
        img.paste(c, (cx, MARGIN))
        d.rectangle((cx, MARGIN, cx + cw, MARGIN + ch), outline=(0xC9, 0xC2, 0xB6), width=2)
        text_w = cx - 80 - MARGIN

    # 見出しと補足を縦中央に置く
    fh, fs = font(HEAD_SIZE), font(SUB_SIZE)
    hl, sl = wrap(head, fh, text_w), wrap(sub, fs, text_w)
    hlh, slh = int(HEAD_SIZE * 1.5), int(SUB_SIZE * 1.7)
    total = len(hl) * hlh + 28 + 24 + len(sl) * slh
    y = (H - total) // 2
    y = draw_block(d, head, HEAD_SIZE, MARGIN, y, text_w, color=INK, line_gap=1.5)
    y += 12
    d.rectangle((MARGIN, y, MARGIN + 140, y + 6), fill=ACCENT)
    y += 40
    draw_block(d, sub, SUB_SIZE, MARGIN, y, text_w, color=INK, line_gap=1.7)

    # 隅にページ番号（施設の方が「あと何枚か」を分かるように）
    f = font(26)
    t = f"{idx}/{len(SLIDES)}"
    d.text((W - MARGIN - f.getlength(t), H - MARGIN + 40), t, font=f, fill=MUTED)
    return img


def slides_for(variant: str):
    t = TAISHOU[variant]
    return [(secs, head.format(taishou=t), sub, use_card) for secs, head, sub, use_card in SLIDES]


def frames(variant: str):
    """各スライドを指定秒ぶん出す。切り替えは 0.5 秒のクロスフェード（次のスライドの冒頭を前と混ぜる。秒数は変えない）"""
    card = card_front(variant)
    imgs = [slide_image(i + 1, h, s, card if use_card else None) for i, (_, h, s, use_card) in enumerate(slides_for(variant))]
    nfade = int(FADE * FPS)
    prev = None
    for (secs, *_), img in zip(slides_for(variant), imgs):
        n = int(secs * FPS)
        for i in range(n):
            if prev is not None and i < nfade:
                yield Image.blend(prev, img, (i + 1) / nfade)
            else:
                yield img
        prev = img


def build(variant: str) -> pathlib.Path:
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"setsumei-{variant}.mp4"
    cmd = [ffmpeg_exe(), "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-an",                                   # 無音（音声トラック自体を持たない）
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium", "-crf", "20",
           "-movflags", "+faststart", str(out)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n = 0
    for img in frames(variant):
        p.stdin.write(img.tobytes()); n += 1
    p.stdin.close(); p.wait()
    if p.returncode:
        sys.exit("ffmpeg が失敗しました")
    print(f"{out.relative_to(ROOT)}  {n / FPS:.1f}秒  {out.stat().st_size / 1e6:.1f}MB")
    return out


def write_script(variants) -> pathlib.Path:
    """台本。施設へのメール本文や、あとでナレーションを付けるときの読み原稿に使う"""
    lines = ["# カード設置の説明動画 台本", "",
             "`tools/build-setsumei-video.py` が出力する `setsumei-<案>.mp4` のスライド文言と秒数。",
             "音声は入っていない。ナレーションを付けるときはこの文言をそのまま読む。", ""]
    for v in variants:
        t = 0
        lines += [f"## {TAISHOU[v]}版（setsumei-{v}.mp4）", "",
                  "| # | 開始 | 秒 | 見出し | 補足 | カード |", "|---|---|---|---|---|---|"]
        for i, (secs, head, sub, use_card) in enumerate(slides_for(v), 1):
            lines.append(f"| {i} | {t // 60}:{t % 60:02d} | {secs} | {head} | {sub} | {'表面' if use_card else ''} |")
            t += secs
        lines += ["", f"合計 {t // 60}分{t % 60:02d}秒", ""]
    path = OUT / "setsumei-script.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"{path.relative_to(ROOT)}")
    return path


def main():
    variants = [a for a in sys.argv[1:] if a in TAISHOU] or list(TAISHOU)
    for v in variants:
        build(v)
    write_script(variants)


if __name__ == "__main__":
    main()
