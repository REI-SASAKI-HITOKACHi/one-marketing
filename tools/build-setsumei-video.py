#!/usr/bin/env python3
"""施設のスタッフ向けに「カードを置くだけです」を説明する約1分半の横型動画（16:9・MP4）を作る。

産院・小児科・ペットショップ・動物病院に A6 カードの設置をお願いするとき、メールに添えて送る。
文字だけのスライドを順に見せる（写真・人物は使わない。施設側に余計な印象を与えないため）。
音声は入れない（受付で音を出さずに見られるように。台本は別ファイルに出すので、後からナレーションを付けられる）。

見た目はカード（build-a6-card.py v2）と読本ページに合わせる：
  紙色の地に黒に近い墨の文字。見出しは しっぽり明朝 700、本文は Zen角ゴシック New 400。
  色はアクセント1色だけで、見出しの下の短い罫にしか使わない（施設宛ての資料なので売り込み色を出さない）。

使い方:
  python3 tools/build-setsumei-video.py            # 赤ちゃん版・ペット版の両方
  python3 tools/build-setsumei-video.py pet
  出力: dist/dokuhon/setsumei-<案>.mp4 と dist/dokuhon/setsumei-script.md（台本＋秒数）
        （dist/ は .gitignore 済み。動画はコミットしない）

スライド 3・4 には build-a6-card.py が作るカード表面（見出しA＝数字型）を入れる（無ければその場で作る）。
ffmpeg は imageio-ffmpeg 同梱の libx264 付きを使う（build-shorts.py と同じ）。
"""
import importlib.util
import pathlib
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "dist" / "dokuhon"
FONTS = ROOT / "assets" / "fonts"
MINCHO_B = FONTS / "ShipporiMinchoB1-700.ttf"     # 見出し
GOTHIC_R = FONTS / "ZenKakuGothicNew-400.ttf"     # 本文
GOTHIC = FONTS / "ZenKakuGothicNew-500.ttf"       # ページ番号などの小さい字

W, H, FPS = 1920, 1080, 30
MARGIN = 140
FADE = 0.5                      # スライド間のクロスフェード秒
HEAD_SIZE, SUB_SIZE = 64, 34
HEAD_LH, SUB_LH = 1.5, 1.7

# カードと同じパレット（docs/読本-設計メモ.md）。紙色だけは動画用に少し暖かい白
PAPER = (0xFB, 0xFA, 0xF7)
INK = (0x17, 0x1A, 0x1C)
INK2 = (0x4A, 0x50, 0x54)
INK3 = (0x7C, 0x83, 0x88)
ACCENT = (0x0E, 0x6E, 0x82)

# スライド 3・4 に使うカードの見出し案。A＝数字型（読本の冒頭と同じ数字なので、動画でも A を見せる）
CARD_HEADLINE = "A"

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
    # 電話番号は 080-8043-8259 だけ（本舗の番号は出さない。media_common.UNEI_TEL と同じ）
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


def font(path: pathlib.Path, size: int) -> ImageFont.FreeTypeFont:
    if not path.exists():
        sys.exit(f"フォントがありません: {path}（python3 tools/fetch-fonts.py）")
    return ImageFont.truetype(str(path), size)


def wrap(text: str, f: ImageFont.FreeTypeFont, max_w: int) -> list:
    """日本語は単語で切れないので、1文字ずつ幅を測って折り返す。行頭に句読点・閉じ括弧が来ないようにする（build-a6-card.py と同じ）"""
    out = []
    for para in text.split("\n"):
        line = ""
        for ch in para:
            if f.getlength(line + ch) <= max_w or not line:
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


def card_front(variant: str) -> Image.Image:
    """カード表面（見出しA・施設ID=card）。dist に無ければ build-a6-card.py を読み込んで作る（ファイル名にハイフンがあるので importlib）"""
    path = OUT / f"card-{variant}-{CARD_HEADLINE}-card-front.png"
    if not path.exists():
        spec = importlib.util.spec_from_file_location("build_a6_card", ROOT / "tools" / "build-a6-card.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.build(variant, CARD_HEADLINE, "card", False)
    return Image.open(path).convert("RGB")


def slide_image(idx: int, head: str, sub: str, card: Image.Image | None) -> Image.Image:
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    text_w = W - 2 * MARGIN

    if card is not None:
        # 右にカードを立てて置き、文字は左の列に収める
        ch = H - 2 * MARGIN
        cw = int(card.width * ch / card.height)
        c = card.resize((cw, ch), Image.LANCZOS)
        cx = W - MARGIN - cw
        # 白いカードが紙色の地に沈まないよう、薄い影と細い枠で1枚の紙に見せる
        d.rectangle((cx + 10, MARGIN + 10, cx + cw + 10, MARGIN + ch + 10), fill=(0xE6, 0xE3, 0xDC))
        img.paste(c, (cx, MARGIN))
        d.rectangle((cx, MARGIN, cx + cw, MARGIN + ch), outline=(0xD3, 0xD0, 0xC9), width=2)
        text_w = cx - 80 - MARGIN

    # 見出しと補足を縦中央に置く
    fh, fs = font(MINCHO_B, HEAD_SIZE), font(GOTHIC_R, SUB_SIZE)
    hl, sl = wrap(head, fh, text_w), wrap(sub, fs, text_w)
    hlh, slh = round(HEAD_SIZE * HEAD_LH), round(SUB_SIZE * SUB_LH)
    rule_gap_top, rule_h, rule_gap_bottom = 16, 5, 44
    total = len(hl) * hlh + rule_gap_top + rule_h + rule_gap_bottom + len(sl) * slh
    y = (H - total) // 2
    y = draw_lines(d, MARGIN, y, hl, fh, INK, HEAD_LH)
    y += rule_gap_top
    d.rectangle((MARGIN, y, MARGIN + 120, y + rule_h), fill=ACCENT)   # アクセント色はこの短い罫だけ
    y += rule_h + rule_gap_bottom
    draw_lines(d, MARGIN, y, sl, fs, INK2, SUB_LH)

    # 隅にページ番号（施設の方が「あと何枚か」を分かるように）
    f = font(GOTHIC, 26)
    t = f"{idx}/{len(SLIDES)}"
    d.text((W - MARGIN - f.getlength(t), H - MARGIN + 50), t, font=f, fill=INK3)
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
