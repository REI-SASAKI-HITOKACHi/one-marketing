#!/usr/bin/env python3
"""担当者の写真から、LP「伺うのは、自社の職人です」欄用のイラスト案（SVG）を3案つくる。

20261107-02-web-inflow（cmo・オーナー指示）。手元（このコンテナ内）だけで処理し、写真を外部に渡さない。
写真はリポジトリに入れない（パスで渡す）。出力も preview/staff/ に出す（git の対象外）。

  python3 tools/make-staff-illust-v2.py 写真.jpg --crop 50,20,1000,1000 --name kazuma

案：
  a  平塗り（色数を絞る）  … 写真の色面をそのまま平塗りに。似ている感じを残す
  b  平塗り＋墨線          … 平塗りに、目・眉・口・鼻・髪の線を足して表情を戻す
  c  かなり絞った版        … 色数を減らして絵らしく。似ている感じは下がる
出力：<name>-{a,b,c}.svg と、確認用の <name>-{a,b,c}.png（1200px正方形・背景色つき）
必要なもの: Pillow, numpy, opencv-python-headless, vtracer
"""
import argparse
import pathlib

import cv2
import numpy as np
import vtracer

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "preview" / "staff"
HAIKEI = (232, 240, 238)   # lp の薄い青緑（BGRではなくRGB）
SIZE = 1200


def segment(img):
    h, w = img.shape[:2]
    mask = np.full((h, w), cv2.GC_PR_BGD, np.uint8)
    mask[:20, :] = cv2.GC_BGD
    mask[:, :20] = cv2.GC_BGD
    mask[:, -20:] = cv2.GC_BGD
    mask[int(h * .12):, int(w * .25):int(w * .75)] = cv2.GC_PR_FGD
    mask[int(h * .38):, int(w * .38):int(w * .62)] = cv2.GC_FGD
    mask[int(h * .88):, int(w * .08):] = cv2.GC_FGD
    bgd = np.zeros((1, 65)); fgd = np.zeros((1, 65))
    cv2.grabCut(img, mask, None, bgd, fgd, 6, cv2.GC_INIT_WITH_MASK)
    m = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    m = cv2.GaussianBlur(m, (0, 0), 2.2)
    return (m > 127).astype(np.uint8) * 255


def flat(img, mask, k, smooth):
    s = img
    for _ in range(smooth):
        s = cv2.bilateralFilter(s, 9, 40, 9)
    lab = cv2.cvtColor(s, cv2.COLOR_BGR2LAB)
    pts = lab[mask > 0].reshape(-1, 3).astype(np.float32)
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5)
    _, lab_i, cen = cv2.kmeans(pts, k, None, crit, 4, cv2.KMEANS_PP_CENTERS)
    q = np.zeros_like(lab)
    q[mask > 0] = cen[lab_i.flatten()].astype(np.uint8)
    q = cv2.medianBlur(cv2.cvtColor(q, cv2.COLOR_LAB2BGR), 7)
    bg = np.array(HAIKEI[::-1], np.uint8)
    out = np.where(mask[..., None] > 0, q, bg)
    return out


def lines(img, mask, strength):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    g = cv2.GaussianBlur(g, (0, 0), 1.6)
    th = cv2.adaptiveThreshold(g, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 41, strength)
    inner = cv2.erode(mask, np.ones((15, 15), np.uint8))
    th = cv2.bitwise_and(th, inner)
    th = cv2.morphologyEx(th, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(th)
    keep = np.zeros_like(th)
    for i in range(1, n):
        if st[i, cv2.CC_STAT_AREA] >= 60:
            keep[lab == i] = 255
    return keep


def regions(img):
    """色で人物を分ける：肌・髪・作業着・背景。壁の影（無彩色の灰）は人物に含めない"""
    h, w = img.shape[:2]
    sm = cv2.bilateralFilter(img, 9, 50, 9)
    hsv = cv2.cvtColor(sm, cv2.COLOR_BGR2HSV)
    H, S, V = hsv[..., 0].astype(int), hsv[..., 1].astype(int), hsv[..., 2].astype(int)
    yy = np.arange(h)[:, None].repeat(w, 1)
    dark = V < 92
    skin = ((H <= 22) | (H >= 170)) & (S > 45) & (V > 60) & (~dark)
    skin = cv2.morphologyEx(skin.astype(np.uint8) * 255, cv2.MORPH_CLOSE, np.ones((11, 11), np.uint8)) > 0
    hair = dark & (yy < h * 0.5)
    shirt = dark & (yy >= h * 0.5)
    return skin, hair, shirt


def clean(m, close=15, open_=7, blur=9):
    m = (m.astype(np.uint8) * 255)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (close, close)))
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (open_, open_)))
    n, lab, st, _ = cv2.connectedComponentsWithStats(m)
    if n > 1:
        big = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
        m = np.where(lab == big, 255, 0).astype(np.uint8)
    m = cv2.GaussianBlur(m, (0, 0), blur / 3)
    return m > 127


def illust(img, tones=3, line=True):
    skin, hair, shirt = regions(img)
    skin_m = clean(skin, 25, 9)
    hair_m = clean(hair, 15, 5)
    shirt_m = clean(shirt, 35, 15)
    h, w = img.shape[:2]
    out = np.zeros_like(img)
    out[:] = np.array(HAIKEI[::-1], np.uint8)
    # 作業着：2階調（地色＋少し明るい面）
    out[shirt_m] = (74, 70, 66)
    gl = cv2.cvtColor(cv2.GaussianBlur(img, (0, 0), 14), cv2.COLOR_BGR2GRAY).astype(int)
    thr = np.percentile(gl[shirt_m], 55) if shirt_m.any() else 0
    out[shirt_m & (gl > thr)] = (88, 83, 78)
    # 肌：影・地・ハイライトの3階調（ぼかした明度で分ける＝面がなめらかになる）
    lab = cv2.cvtColor(cv2.GaussianBlur(img, (0, 0), 7), cv2.COLOR_BGR2LAB)[..., 0].astype(int)
    sv = lab[skin_m]
    lo, hi = np.percentile(sv, 28), np.percentile(sv, 86)
    out[skin_m] = (150, 178, 214)                    # 地（BGR）
    out[skin_m & (lab < lo)] = (118, 146, 190)       # 影
    if tones >= 3:
        out[skin_m & (lab > hi)] = (176, 200, 230)   # ハイライト
    out[hair_m] = (44, 38, 34)
    if line:
        g = cv2.GaussianBlur(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (0, 0), 1.8)
        th = cv2.adaptiveThreshold(g, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 51, 11)
        face = np.zeros((h, w), np.uint8)
        face[int(h * .27):int(h * .72), int(w * .28):int(w * .72)] = 255
        th = cv2.bitwise_and(th, cv2.bitwise_and(face, cv2.erode(skin_m.astype(np.uint8) * 255, np.ones((9, 9), np.uint8))))
        th = cv2.morphologyEx(th, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        n, lab2, st, _ = cv2.connectedComponentsWithStats(th)
        keep = np.zeros_like(th)
        for i in range(1, n):
            if st[i, cv2.CC_STAT_AREA] >= 90:
                keep[lab2 == i] = 255
        keep = cv2.dilate(keep, np.ones((3, 3), np.uint8))
        out[keep > 0] = (34, 30, 30)
    return out


def to_svg(rgb_bgr, path):
    tmp = path.with_suffix(".tmp.png")
    cv2.imwrite(str(tmp), rgb_bgr)
    vtracer.convert_image_to_svg_py(str(tmp), str(path), colormode="color", hierarchical="stacked",
                                    mode="spline", filter_speckle=14, color_precision=6,
                                    layer_difference=24, corner_threshold=60, length_threshold=5.0,
                                    splice_threshold=45, path_precision=2)
    tmp.unlink()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("photo")
    ap.add_argument("--crop", required=True, help="x,y,w,h（元写真のピクセル）")
    ap.add_argument("--name", default="staff")
    a = ap.parse_args()
    x, y, w, h = (int(v) for v in a.crop.split(","))
    img = cv2.imread(a.photo)[y:y + h, x:x + w]
    img = cv2.resize(img, (SIZE, SIZE), interpolation=cv2.INTER_CUBIC)
    mask = segment(img)
    OUT.mkdir(parents=True, exist_ok=True)
    fa = flat(img, mask, 9, 3)
    fc = flat(img, mask, 5, 4)
    ln = lines(img, mask, 9)
    fb = fa.copy()
    fb[ln > 0] = (28, 24, 22)
    for key, im in (("a", fa), ("b", fb), ("c", fc)):
        to_svg(im, OUT / f"{a.name}-{key}.svg")
        cv2.imwrite(str(OUT / f"{a.name}-{key}-raster.png"), im)
    print("ok", OUT)


if __name__ == "__main__":
    main()
