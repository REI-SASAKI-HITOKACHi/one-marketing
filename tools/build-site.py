#!/usr/bin/env python3
"""lp/<name>/index.html を、そのままサーバーに置ける HTML 文書に組み立てる。

lp/ 配下は Artifact 用に <html> や <head> を持たない断片として書いてあるので、
公開用にはここで文書として包み、フォームの送信先を PHP に繋ぎ替える。

  python3 tools/build-site.py php       →  deploy/htdocs/  （PHPでフォームを受ける）
  python3 tools/build-site.py netlify   →  deploy/netlify/ （Netlify Formsが受ける）
"""
import pathlib
import re
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

# 配信先ごとに、フォームの受け口と出力先が変わる
TARGETS = {
    # ロリポップなど、PHPが動くサーバー
    "php": {"out": ROOT / "deploy" / "htdocs"},
    # Netlify。フォームはNetlify Formsが受ける
    "netlify": {"out": ROOT / "deploy" / "netlify"},
}

BASE_URL = "https://lp.one-hitter.jp"

PAGES = {
    "aircon": {
        "dir": "aircon",
        "title": "エアコンクリーニング 10,780円／60分｜東京・千葉・神奈川｜ONE HITTER",
        "desc": "フィルター掃除では届かない、熱交換器と送風ファンの黒カビを分解洗浄。"
                "ノーマルエアコン10,780円（税込）・60分、お見積り以上の追加請求はありません。"
                "東京・千葉・神奈川、最短即日。",
        "label": "エアコン",
        "og": "aircon/img/og.jpg",
        "og_line1": "エアコン内部のカビを、分解洗浄",
        "og_line2": "ノーマル 10,780円（税込）／60分・東京 千葉 神奈川",
    },
    "mizumawari": {
        "dir": "mizumawari",
        "title": "水まわりクリーニング まとめて依頼で1箇所3,300円おトク｜ONE HITTER",
        "desc": "キッチン・浴室・レンジフード・洗濯機・追い焚き配管。2箇所目からは同時施工価格。"
                "浴室＋キッチンで33,660円（税込）、半日で完了。東京・千葉・神奈川、最短即日。",
        "label": "水まわりセット",
        "og": "mizumawari/img/og.jpg",
        "og_line1": "水まわりは、まとめて頼むほど安い",
        "og_line2": "浴室＋キッチン 33,660円（税込）・東京 千葉 神奈川",
    },
}

HEAD = """<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<!-- 広告の受け皿なので、公式サイトと検索結果で食い合わないよう検索避けにしています。
     検索にも載せたくなったら、この1行を消してください。 -->
<meta name="robots" content="noindex,follow">
<link rel="canonical" href="{base}/{dir}/">
<meta property="og:type" content="website">
<meta property="og:site_name" content="ワンヒッター株式会社">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{base}/{dir}/">
<meta property="og:image" content="{base}/{og}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:locale" content="ja_JP">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#0E7C93">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<!-- ASP・広告計測タグはこの下に貼ってください -->
</head>
<body>
"""

TAIL = """
</body>
</html>
"""

FORM_OPEN = '<form class="form" onsubmit="return false;">'

FORM_PHP = """<form class="form" action="/form/send.php" method="post">
      <input type="hidden" name="lp" value="{dir}">
      <div class="hp" aria-hidden="true">
        <label for="f-x">この欄には入力しないでください</label>
        <input id="f-x" name="x_field" type="text" tabindex="-1" autocomplete="off">
      </div>"""

# Netlify Forms は、配信されたHTMLからこの form を見つけて受け口を用意する。
# name と form-name が一致していることと、honeypot の欄名の申告が要る。
FORM_NETLIFY = """<form class="form" name="reserve-{dir}" method="post"
      action="/{dir}/thanks.html" data-netlify="true" netlify-honeypot="x_field">
      <input type="hidden" name="form-name" value="reserve-{dir}">
      <input type="hidden" name="subject" value="【LP予約】{label}">
      <input type="hidden" name="lp" value="{dir}">
      <div class="hp" aria-hidden="true">
        <label for="f-x">この欄には入力しないでください</label>
        <input id="f-x" name="x_field" type="text" tabindex="-1" autocomplete="off">
      </div>"""

HP_CSS = (
    "\n/* 自動投稿よけ。人間には見せない */\n"
    ".hp{position:absolute;left:-9999px;width:1px;height:1px;overflow:hidden;}\n"
)



JP_FONT = "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf"
LATIN_FONT = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"


def make_og(src: pathlib.Path, dst: pathlib.Path, line1: str, line2: str) -> None:
    """LINEやSNSに貼られたときのサムネイル（1200x630）をヒーロー写真から作る。"""
    from PIL import Image, ImageDraw, ImageFont

    im = Image.open(src)
    tw, th = 1200, 630
    ratio = tw / th
    if im.width / im.height > ratio:
        nw = int(im.height * ratio)
        im = im.crop(((im.width - nw) // 2, 0, (im.width - nw) // 2 + nw, im.height))
    else:
        nh = int(im.width / ratio)
        top = int((im.height - nh) * 0.35)
        im = im.crop((0, top, im.width, top + nh))
    im = im.resize((tw, th), Image.LANCZOS).convert("RGBA")

    band = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    draw = ImageDraw.Draw(band)
    draw.rectangle([0, th - 186, tw, th], fill=(20, 50, 61, 232))
    draw.text((56, th - 160), line1, font=ImageFont.truetype(JP_FONT, 44), fill=(255, 255, 255, 255))
    draw.text((56, th - 92), line2, font=ImageFont.truetype(JP_FONT, 25), fill=(201, 217, 222, 255))
    draw.text((56, th - 48), "ONE HITTER", font=ImageFont.truetype(LATIN_FONT, 26), fill=(78, 192, 212, 255))

    out = Image.alpha_composite(im, band).convert("RGB")
    out.save(dst, quality=82, optimize=True, progressive=True)


def build_page(name: str, meta: dict, target: str, out: pathlib.Path) -> None:
    src = (ROOT / "lp" / name / "index.html").read_text(encoding="utf-8")

    if FORM_OPEN not in src:
        raise SystemExit(f"{name}: フォームの開始タグが見つかりません")
    form = FORM_NETLIFY if target == "netlify" else FORM_PHP
    src = src.replace(FORM_OPEN, form.format(dir=meta["dir"], label=meta["label"]))

    # 蜂蜜罠のスタイルを、既存の .form の定義のすぐ後ろに足す
    anchor = ".form{background:var(--surface);"
    if anchor not in src:
        raise SystemExit(f"{name}: .form のスタイルが見つかりません")
    line_end = src.index("\n", src.index(anchor))
    src = src[:line_end] + HP_CSS.rstrip("\n") + src[line_end:]

    src = src.replace("</body>", "")  # 断片には無いはずだが念のため
    head_meta = {k: v for k, v in meta.items() if not k.startswith("og_") and k != "label"}
    doc = HEAD.format(base=BASE_URL, **head_meta) + src + TAIL

    dst = out / meta["dir"]
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "index.html").write_text(doc, encoding="utf-8")

    img_src = ROOT / "lp" / name / "img"
    img_dst = dst / "img"
    if img_dst.exists():
        shutil.rmtree(img_dst)
    shutil.copytree(img_src, img_dst)

    make_og(img_dst / "hero.jpg", img_dst / "og.jpg", meta["og_line1"], meta["og_line2"])

    print(f"{dst.relative_to(ROOT)}/index.html  {len(doc)//1024}KB  "
          f"画像{len(list(img_dst.iterdir()))}点")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "php"
    if target not in TARGETS:
        raise SystemExit(f"配信先は {' / '.join(TARGETS)} のいずれかです")
    out = TARGETS[target]["out"]
    out.mkdir(parents=True, exist_ok=True)
    print(f"[{target}] → {out.relative_to(ROOT)}/")
    for name, meta in PAGES.items():
        build_page(name, meta, target, out)
