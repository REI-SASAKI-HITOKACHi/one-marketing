#!/usr/bin/env python3
"""担当者の写真から、LPに載せるイラスト（SVG＋WebP）を作る。

オーナー決定（2026-09-30）：顔写真そのものは載せず、解像度の高いイラストにする。
写真を外部の生成サービスに渡さずに済むよう、手元（このコンテナ内）だけで処理する。

  写真 → 肩から上を切り出す → 背景を抜く → 色を減らして平塗りにする → ベクター化（SVG）

使い方:
  python3 tools/make-staff-illust.py 写真.jpg                 # preview/staff/ に出す
  python3 tools/make-staff-illust.py 写真.jpg --crop 120,40,900,900
  python3 tools/make-staff-illust.py 写真.jpg --colors 10 --name kazuma

  --crop x,y,w,h   切り出す範囲（元写真のピクセル）。省略時は中央の正方形
  --colors N       色数（既定12。少ないほど絵っぽく、多いほど写真に近い）
  --keep-bg        背景を抜かない（抜けが悪いとき）
  --name NAME      出力ファイル名（既定 staff）

出力（preview/ は git の対象外）:
  preview/staff/<name>.svg        LPに載せる本体（拡大しても荒れない）
  preview/staff/<name>.webp       1200px の書き出し（SVGが重すぎるとき・Canva等での手直し用）
  preview/staff/<name>-check.html 和真さん本人に見せる確認用（実寸の枠に入れた見え方）

★写真はコミットしない（お客様写真と同じ扱い）。写真は data/ の外に置き、パスで渡す。
★できたイラストも、和真さん本人の確認が済むまで lp/ に入れない。
  確認が済んだら lp/_staff/staff.svg に置く。次の配信から学習版4本の staff-il 枠に出る
  （無いあいだは build-site.py が枠ごと外すので、本番に空の枠は出ない）。

★試した結果（2026-10-01）：自動の減色＋ベクター化は「写真をポスター加工した」程度で、
  表情や似ている感じが落ちる。本命は人の手（外注）か生成AI。このツールは予備と、
  外注・生成の結果を 1200px 正方形にそろえて確認ページを作る用途に使う。

必要なもの: Pillow, numpy, opencv-python, vtracer（pip install vtracer）
"""
import argparse
import html
import pathlib
import sys

import numpy as np
from PIL import Image, ImageOps

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "preview" / "staff"

# 学習版LP（v2）の色。背景の円と枠の色に使う
HAIKEI = (232, 240, 238)   # 薄い青緑。肌・作業着と喧嘩しない
SIZE = 1200                # 書き出しの一辺（2倍・3倍表示でも荒れない大きさ）


def kiridasu(img, crop):
    if crop:
        x, y, w, h = (int(v) for v in crop.split(","))
        img = img.crop((x, y, x + w, y + h))
    else:
        w, h = img.size
        s = min(w, h)
        # 縦長の写真は上寄せ（肩から上の写真は顔が上にある）
        top = 0 if h > w else 0
        img = img.crop(((w - s) // 2, top, (w - s) // 2 + s, top + s))
    return img.resize((SIZE, SIZE), Image.LANCZOS)


def haikei_wo_nuku(rgb):
    """GrabCut で人物を残す。人物は下端まで続く前提で、上と左右だけ余白を背景とみなす。"""
    import cv2
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    h, w = bgr.shape[:2]
    mask = np.zeros((h, w), np.uint8)
    rect = (int(w * .08), int(h * .04), int(w * .84), h - int(h * .04))
    bg, fg = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
    cv2.grabCut(bgr, mask, rect, bg, fg, 6, cv2.GC_INIT_WITH_RECT)
    hito = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 1, 0).astype(np.uint8)
    # いちばん大きい塊だけ残し、穴を埋める
    n, lab, st, _ = cv2.connectedComponentsWithStats(hito)
    if n > 1:
        big = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
        hito = (lab == big).astype(np.uint8)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25))
    hito = cv2.morphologyEx(hito, cv2.MORPH_CLOSE, k)
    # 縁をなめらかに（ギザギザがそのまま輪郭線になるため）
    hito = cv2.GaussianBlur(hito.astype(np.float32), (0, 0), 6)
    return (hito > .5).astype(np.uint8)


def hiranuri(rgb, hito, n_colors):
    """エッジを残してぼかし、k-means で色を減らす（平塗りのイラストに寄せる）。"""
    import cv2
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    # 髪や布の細かい明暗が「迷彩柄」にならないよう、強めにならしてから色を減らす
    for _ in range(4):
        bgr = cv2.bilateralFilter(bgr, 21, 55, 21)
    bgr = cv2.edgePreservingFilter(bgr, flags=cv2.RECURS_FILTER, sigma_s=90, sigma_r=0.45)
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    px = lab[hito == 1].reshape(-1, 3).astype(np.float32)
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 40, 0.5)
    cv2.setRNGSeed(7)   # 何度作っても同じ絵になるように
    _, lbl, cen = cv2.kmeans(px, n_colors, None, crit, 4, cv2.KMEANS_PP_CENTERS)
    q = np.zeros_like(lab)
    q[hito == 1] = cen[lbl.flatten()].astype(np.uint8)
    out = cv2.cvtColor(q, cv2.COLOR_LAB2RGB)
    # 細かい斑点をならす（ベクター化したときのゴミになる）
    out = cv2.medianBlur(out, 11)
    out[hito == 0] = HAIKEI
    return out


def vector_ka(rgb_img, path_png):
    import vtracer
    Image.fromarray(rgb_img).save(path_png)
    svg = vtracer.convert_raw_image_to_svg(
        _png_bytes(path_png),
        img_format="png", colormode="color", hierarchical="stacked", mode="spline",
        filter_speckle=10, color_precision=6, layer_difference=12,
        corner_threshold=60, length_threshold=4.0, splice_threshold=45, path_precision=2)
    # vtracer は width/height だけを書くので、枠に合わせて伸縮するよう viewBox を足す
    import re
    svg = re.sub(r'<svg([^>]*?)width="(\d+)" height="(\d+)"',
                 r'<svg\1viewBox="0 0 \2 \3"', svg, count=1)
    return svg


def _png_bytes(p):
    return pathlib.Path(p).read_bytes()


def kakunin_html(name, svg_name):
    """和真さん本人に見せる確認用。LPの「伺うのは私たちです」と同じ大きさの枠に入れる。"""
    return f"""<!doctype html><html lang="ja"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>担当者イラストの確認</title>
<style>
body{{margin:0;background:#f6f8f7;color:#1d2a27;font:16px/1.8 "Hiragino Sans","Noto Sans JP",sans-serif}}
main{{max-width:430px;margin:0 auto;padding:24px 16px 48px}}
h1{{font-size:18px;margin:0 0 4px}} p.note{{font-size:13px;color:#5b6b67;margin:0 0 20px}}
.staff-il{{margin:0 0 22px;display:flex;gap:16px;align-items:center}}
.staff-il img{{width:132px;height:132px;border-radius:50%;background:rgb{HAIKEI};flex:none}}
.staff-il figcaption{{font-size:14px;line-height:1.7}} .staff-il b{{display:block;font-size:17px}}
.big{{margin-top:28px}} .big img{{width:100%;height:auto;border-radius:12px;background:rgb{HAIKEI}}}
</style>
<main>
<h1>LPに載せるイラストの確認</h1>
<p class="note">実際のページと同じ大きさです。下は拡大したもの。気になるところ（髪型・眼鏡・表情など）があれば教えてください。</p>
<figure class="staff-il"><img src="{html.escape(svg_name)}" alt="担当者のイラスト">
<figcaption><b>担当 {html.escape(name)}</b>ご予約を受けた私たち自身が伺います。</figcaption></figure>
<div class="big"><img src="{html.escape(svg_name)}" alt=""></div>
</main></html>
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("photo")
    ap.add_argument("--crop")
    ap.add_argument("--colors", type=int, default=12)
    ap.add_argument("--keep-bg", action="store_true")
    ap.add_argument("--name", default="staff")
    ap.add_argument("--label", default="和真", help="確認用ページに出す名前")
    a = ap.parse_args()

    src = pathlib.Path(a.photo)
    if not src.exists():
        sys.exit(f"写真が見つかりません: {src}")
    try:
        src.resolve().relative_to(ROOT / "lp")
        sys.exit("写真を lp/ の中に置かないでください（公開物に混ざります）。リポジトリの外に置いてください")
    except ValueError:
        pass

    img = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    img = kiridasu(img, a.crop)
    rgb = np.array(img)
    hito = np.ones(rgb.shape[:2], np.uint8) if a.keep_bg else haikei_wo_nuku(rgb)
    flat = hiranuri(rgb, hito, a.colors)

    OUT.mkdir(parents=True, exist_ok=True)
    png = OUT / f"{a.name}-flat.png"
    svg = vector_ka(flat, png)
    (OUT / f"{a.name}.svg").write_text(svg, encoding="utf-8")
    Image.fromarray(flat).save(OUT / f"{a.name}.webp", quality=90, method=6)
    png.unlink()
    (OUT / f"{a.name}-check.html").write_text(kakunin_html(a.label, f"{a.name}.svg"), encoding="utf-8")

    kb = (OUT / f"{a.name}.svg").stat().st_size // 1024
    print(f"{OUT / (a.name + '.svg')}  {kb}KB  {SIZE}x{SIZE}  {a.colors}色")
    print(f"{OUT / (a.name + '.webp')}  {(OUT / (a.name + '.webp')).stat().st_size // 1024}KB")
    print(f"{OUT / (a.name + '-check.html')}  （和真さんに見せる確認用）")
    if kb > 300:
        print(f"  ※ SVG が {kb}KB と重い。--colors を減らすか、LPには WebP を使う")


if __name__ == "__main__":
    main()
