#!/usr/bin/env python3
"""公開中の公式サイトのブログを、原稿と画像の両面から機械で点検する。

【なぜ】2026-10-08 オーナー指摘「使われてる写真はすべて使いまわしになっていて、かつピンボケしていて
  なんの画像かもわからない」「指摘した写真は載ってない」。調べると 2026年の記事16本すべてのアイキャッチが
  同じ 64×48px の画像（864バイト）だった。9/24 にブラウザ担当が「種画像 → 差し替え」の2段で入れたが、
  差し替えが入らないまま残っていた。CMO は「1本に画像が出ている」ことしか見ておらず、気づかなかった。
  9/27 の記事も、リポジトリで書き直した版が CMS に反映されないまま古い題名で公開されていた。

【何を見るか】サイトマップから 2026年以降の記事を全部取り、1本ずつ
  1. アイキャッチ画像の実寸（JPEG/PNG の大きさ）… 横 800px 未満は NG（ピンボケの元）
  2. 同じ画像が他の記事と重複していないか（中身のハッシュで比べる）
  3. 題名が原稿（web-inflow ブランチ docs/blog/*.md の title）のどれかと一致するか
  4. 本文に画像が1枚もない記事（事例記事＝題名に「事例」を含むのに0枚）は NG

    python3 tools/check-blog-public.py          # NG があれば最後に「NG: N件」
    python3 tools/check-blog-public.py --quiet  # NG の行だけ

読むだけ。CMS には何も書かない。
"""
import argparse
import hashlib
import re
import struct
import subprocess
import sys
import urllib.request

SITE = "https://one-hitter.jp"
GENKOU_BRANCH = "origin/claude/web-inflow"
MIN_W = 800


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "one-hitter-blog-check"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read()


def gazou_sunpou(b):
    """JPEG / PNG の幅・高さ。分からなければ (0, 0)"""
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", b[16:24])
    if b[:2] == b"\xff\xd8":
        i = 2
        while i < len(b) - 9:
            if b[i] != 0xFF:
                i += 1
                continue
            m = b[i + 1]
            if m in (0xC0, 0xC1, 0xC2):
                h, w = struct.unpack(">HH", b[i + 5:i + 9])
                return w, h
            i += 2 + struct.unpack(">H", b[i + 2:i + 4])[0]
    return 0, 0


def genkou_daimei():
    try:
        names = subprocess.run(["git", "ls-tree", "-r", "--name-only", GENKOU_BRANCH, "docs/blog/"],
                               capture_output=True, text=True, check=True).stdout.split()
    except subprocess.CalledProcessError:
        return {}
    out = {}
    for n in names:
        if not n.endswith(".md"):
            continue
        s = subprocess.run(["git", "show", f"{GENKOU_BRANCH}:{n}"], capture_output=True, text=True).stdout
        m = re.search(r'^title:\s*"?(.+?)"?\s*$', s, re.M)
        if m:
            out[m.group(1).strip()] = n
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    subprocess.run(["git", "fetch", "-q", "origin", GENKOU_BRANCH.split("/", 1)[1]], capture_output=True)
    daimei = genkou_daimei()
    sm = get(SITE + "/sitemap.xml").decode("utf-8", "ignore")
    urls = sorted(set(re.findall(r"https://one-hitter\.jp/blog/(20[2-9]\d\d{4}-\d+)/", sm)))
    urls = [u for u in urls if u >= "20260000"]
    ng, kiroku, hashes = [], [], {}
    for slug in urls:
        url = f"{SITE}/blog/{slug}/"
        h = get(url).decode("utf-8", "ignore")
        t = re.sub(r"\s*\|.*", "", re.search(r"<title>(.*?)</title>", h, re.S).group(1)).strip()
        imgs = [x for x in re.findall(r'<img[^>]+src="(/_img/ja/article/\d+/image/[^"]*)"', h) if "300_300" not in x]
        mondai = []
        if not imgs:
            mondai.append("アイキャッチ無し")
        for x in imgs[:1]:
            b = get(SITE + re.sub(r"/image/.*", "/image/", x))
            w, hh = gazou_sunpou(b)
            d = hashlib.sha1(b).hexdigest()[:10]
            hashes.setdefault(d, []).append(slug)
            if w < MIN_W:
                mondai.append(f"画像が小さい（{w}×{hh}px・{len(b)}バイト）")
        honbun = len(re.findall(r"<img[^>]+src=\"(?!/_img/ja/(?:resource|cms_parts))[^\"]+\"", h)) - len(imgs)
        if "事例" in t and honbun <= 0 and len(imgs) <= 1:
            mondai.append("事例記事なのに本文の写真が0枚")
        if daimei and t not in daimei:
            mondai.append("題名が原稿と違う（古い版のまま？）")
        kiroku.append((slug, t, mondai))
    for d, ss in hashes.items():
        if len(ss) > 1:
            for slug, t, mondai in kiroku:
                if slug in ss:
                    mondai.append(f"アイキャッチが他の{len(ss) - 1}本と同じ画像")
    for slug, t, mondai in kiroku:
        if mondai:
            ng.append(slug)
            print(f"NG {slug} {t[:30]}：" + "／".join(mondai))
        elif not a.quiet:
            print(f"OK {slug} {t[:30]}")
    print(f"記事 {len(kiroku)}本／NG: {len(ng)}件")
    sys.exit(1 if ng else 0)


if __name__ == "__main__":
    main()
