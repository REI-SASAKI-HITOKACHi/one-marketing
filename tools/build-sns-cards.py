#!/usr/bin/env python3
"""Instagram 用の文字カード（型D 自分でできるコツ／型E クチコミ引用）を作る。

  1080×1350（4:5）JPEG q90 → dist/cards/<id>[-<slug>].jpg

方向は読本 v2 と同じ「雑誌の特集ページ」（docs/読本-設計メモ.md）。
白い紙に黒い明朝の大きな見出し。色は1色（LPの深い青緑）を、短い罫と手順の番号にだけ。
写真・アイコン・絵文字・グラデーションは使わない。

文言は data/sns-cards/<id>.json から取る（キャプション側の原稿と同じ文にするため）。
  {"id": "w01-2", "kind": "D", "headline": "...", "lines": ["...", "..."], "footnote": "..."}
  {"id": "w01-1", "kind": "E", "headline": "「…」", "lines": ["..."], "credit": "K様　★★★★★　Googleクチコミより（2026年4月）", "footnote": "※…"}
  "slug" を付けると出力名が <id>-<slug>.jpg になる（第1週の旧名との互換用）。

使い方:
  python3 tools/build-sns-cards.py            # data/sns-cards/*.json を全部
  python3 tools/build-sns-cards.py w02-1 w02-2
  python3 tools/build-sns-cards.py --preview out.png   # 全カードのモンタージュ（確認用）
"""
import argparse
import json
import pathlib
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
SPECS = ROOT / "data" / "sns-cards"
OUT = ROOT / "dist" / "cards"
FONTS = ROOT / "assets" / "fonts"
MINCHO = FONTS / "ShipporiMinchoB1-800.ttf"
MINCHO_B = FONTS / "ShipporiMinchoB1-700.ttf"
GOTHIC = FONTS / "ZenKakuGothicNew-500.ttf"
GOTHIC_R = FONTS / "ZenKakuGothicNew-400.ttf"

W, H = 1080, 1350
M = 88                      # 四辺の余白
CW = W - 2 * M              # 本文の幅

PAPER = (0xFB, 0xFA, 0xF7)
INK = (0x17, 0x1A, 0x1C)
INK2 = (0x4A, 0x50, 0x54)
INK3 = (0x7C, 0x83, 0x88)
ACCENT = (0x0E, 0x6E, 0x82)
HAIR = (0xD6, 0xD8, 0xD8)   # 罫（紙に溶ける薄さ）

KICKER = {"D": "自分でできる範囲のお話", "E": "お客様の声"}
FOOTER = "ワンヒッター｜江戸川区のハウスクリーニング"

_cache = {}


def font(path: pathlib.Path, size: int) -> ImageFont.FreeTypeFont:
    key = (path, size)
    if key not in _cache:
        if not path.exists():
            sys.exit(f"フォントがありません: {path}（python3 tools/fetch-fonts.py）")
        _cache[key] = ImageFont.truetype(str(path), size)
    return _cache[key]


def wrap(text: str, f: ImageFont.FreeTypeFont, width: int) -> list:
    """描画幅で折り返す。\\n は強制改行。行頭に句読点・閉じ括弧・長音・小書き仮名が来ないようにする（禁則）"""
    NO_HEAD = "、。，．」）』】〕〉》・ー〜…!?！？ぁぃぅぇぉっゃゅょァィゥェォッャュョ％%"
    NO_TAIL = "「（『【〔〈《"
    RUN = set("0123456789.%℃°ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")
    out = []
    for para in text.split("\n"):
        # 数字・欧文の連なり（79.7%、40℃、Google）は1語として扱い、途中で折らない
        tokens, buf = [], ""
        for ch in para:
            if ch in RUN:
                buf += ch
            else:
                if buf:
                    tokens.append(buf)
                    buf = ""
                tokens.append(ch)
        if buf:
            tokens.append(buf)
        line = ""
        for tk in tokens:
            if f.getlength(line + tk) <= width or not line:
                line += tk
            elif tk in NO_HEAD:
                line += tk          # ぶら下げ
            else:
                if line and line[-1] in NO_TAIL and len(line) > 1:
                    out.append(line[:-1])
                    line = line[-1] + tk
                else:
                    out.append(line)
                    line = tk
        out.append(line)
    return out


def fit_headline(text: str, width: int, max_lines: int, size_max: int, size_min: int):
    """幅に収まる最大サイズを探す。max_lines 以内に入らなければ、行数を1つ増やしてもう一度"""
    for lines_cap in (max_lines, max_lines + 1):
        size = size_max
        while size >= size_min:
            f = font(MINCHO, size)
            lines = wrap(text, f, width)
            if len(lines) <= lines_cap and all(f.getlength(ln) <= width * 1.02 for ln in lines):
                return f, lines, lines_cap != max_lines
            size -= 2
    f = font(MINCHO, size_min)
    return f, wrap(text, f, width), True


def draw_hanging(d: ImageDraw.ImageDraw, x: int, y: int, lines: list, f: ImageFont.FreeTypeFont, fill, lh: float) -> int:
    """行を描く。行頭が「（ のときは、括弧の左の空きぶんだけ外に出して縦をそろえる（ぶら下げ）"""
    for ln in lines:
        dx = 0
        if ln and ln[0] in "「（『【":
            bb = f.getbbox(ln[0])
            dx = -min(bb[0], round(f.size * 0.5))
        d.text((x + dx, y), ln, font=f, fill=fill)
        y += round(f.size * lh)
    return y


def text_block_height(lines: list, f: ImageFont.FreeTypeFont, lh: float) -> int:
    return round(f.size * lh) * len(lines)


def frame(d: ImageDraw.ImageDraw, kind: str) -> tuple:
    """上：小さな見出し語と細い罫。下：奥付。戻り値は (本文の開始y, 本文の終わりy)"""
    fk = font(GOTHIC, 26)
    y = M
    kicker = KICKER[kind]
    # 字間を少し空ける（雑誌の柱）
    x = M
    for ch in kicker:
        d.text((x, y), ch, font=fk, fill=INK3)
        x += fk.getlength(ch) + 4
    y += 26 + 22
    d.line([(M, y), (W - M, y)], fill=HAIR, width=2)
    top = y + 76

    ff = font(GOTHIC, 24)
    fy = H - M - 24
    d.line([(M, fy - 30), (W - M, fy - 30)], fill=HAIR, width=2)
    d.text((M, fy), FOOTER, font=ff, fill=INK2)
    bottom = fy - 30 - 44
    return top, bottom


def render_D(spec: dict) -> Image.Image:
    im = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(im)
    top, bottom = frame(d, "D")

    fh, hl, overflow = fit_headline(spec["headline"], CW, 3, 92, 60)
    if overflow:
        print(f"  注意: {spec['id']} の見出しが3行に収まらないので行数を増やしています", file=sys.stderr)
    y = draw_hanging(d, M, top, hl, fh, INK, 1.34)
    y += 30
    d.line([(M, y), (M + 84, y)], fill=ACCENT, width=6)
    y += 66

    # 手順：番号は明朝（アクセント色）、本文はゴシック
    fn = font(MINCHO_B, 40)
    fb = font(GOTHIC_R, 37)
    indent = 66
    for i, ln in enumerate(spec.get("lines", []), 1):
        d.text((M, y + 2), str(i), font=fn, fill=ACCENT)
        y = draw_hanging(d, M + indent, y, wrap(ln, fb, CW - indent), fb, INK, 1.62)
        y += 22

    # 注記：下に寄せる（奥付の上）。手順と重なるときは手順の直下
    fz = font(GOTHIC_R, 27)
    zl = wrap(spec.get("footnote", ""), fz, CW)
    zh = text_block_height(zl, fz, 1.6)
    zy = max(y + 40, bottom - zh)
    draw_hanging(d, M, zy, zl, fz, INK2, 1.6)
    return im


def render_E(spec: dict) -> Image.Image:
    im = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(im)
    top, bottom = frame(d, "E")

    fh, hl, overflow = fit_headline(spec["headline"], CW, 3, 84, 50)
    if overflow:
        print(f"  注意: {spec['id']} の引用が3行に収まらないので4行にしています", file=sys.stderr)
    y = draw_hanging(d, M, top, hl, fh, INK, 1.42)
    y += 30
    d.line([(M, y), (M + 84, y)], fill=ACCENT, width=6)
    y += 44

    # 出典（画像内に必ず入れる）：氏名・★・媒体・年月。★も文字として同じ色で描く
    fc = font(GOTHIC, 30)
    d.text((M, y), spec["credit"], font=fc, fill=INK)
    y += 30 + 70

    fb = font(GOTHIC_R, 34)
    for ln in spec.get("lines", []):
        y = draw_hanging(d, M, y, wrap(ln, fb, CW), fb, INK, 1.7)
        y += 18

    fz = font(GOTHIC_R, 25)
    zl = wrap(spec.get("footnote", ""), fz, CW)
    zh = text_block_height(zl, fz, 1.6)
    zy = max(y + 40, bottom - zh)
    draw_hanging(d, M, zy, zl, fz, INK3, 1.6)
    return im


def build(spec_path: pathlib.Path) -> pathlib.Path:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    kind = spec["kind"]
    if kind == "E" and not spec.get("credit"):
        sys.exit(f"{spec_path.name}: 型E には credit（氏名・★・出典）が要ります")
    im = render_D(spec) if kind == "D" else render_E(spec)
    OUT.mkdir(parents=True, exist_ok=True)
    name = spec["id"] + (f"-{spec['slug']}" if spec.get("slug") else "") + ".jpg"
    p = OUT / name
    im.save(p, "JPEG", quality=90, subsampling=0, optimize=True)
    return p


def montage(paths: list, out: pathlib.Path, thumb_w: int = 540, cols: int = 3):
    th = round(thumb_w * H / W)
    rows = (len(paths) + cols - 1) // cols
    gap = 16
    sheet = Image.new("RGB", (cols * thumb_w + (cols + 1) * gap, rows * th + (rows + 1) * gap), (0xE6, 0xE4, 0xDF))
    for i, p in enumerate(paths):
        im = Image.open(p).resize((thumb_w, th), Image.LANCZOS)
        r, c = divmod(i, cols)
        sheet.paste(im, (gap + c * (thumb_w + gap), gap + r * (th + gap)))
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*", help="カードID（省略で全部）")
    ap.add_argument("--preview", help="全カードのモンタージュPNGを書き出す")
    a = ap.parse_args()
    specs = sorted(SPECS.glob("*.json"))
    if a.ids:
        specs = [s for s in specs if s.stem in a.ids]
        missing = set(a.ids) - {s.stem for s in specs}
        if missing:
            sys.exit(f"仕様がありません: {', '.join(sorted(missing))}（data/sns-cards/）")
    outs = []
    for s in specs:
        p = build(s)
        outs.append(p)
        print("書き出し:", p.relative_to(ROOT))
    if a.preview:
        montage(outs, pathlib.Path(a.preview))
        print("プレビュー:", a.preview)


if __name__ == "__main__":
    main()
