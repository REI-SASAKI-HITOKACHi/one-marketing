#!/usr/bin/env python3
"""lp/<name>/index.html を、そのままサーバーに置ける HTML 文書に組み立てる。

lp/ 配下は Artifact 用に <html> や <head> を持たない断片として書いてあるので、
公開用にはここで文書として包み、フォームの送信先を PHP に繋ぎ替える。

  python3 tools/build-site.py php       →  deploy/htdocs/  （PHPでフォームを受ける）
  python3 tools/build-site.py netlify   →  deploy/netlify/ （Netlify Formsが受ける）
"""
import html
import json
import pathlib
import re
import shutil
import sys

def strip_comments(html: str) -> str:
    """公開する文書からコメントを落とす。

    lp/ 配下のソースには、なぜその値なのかを書いた注記を残してある。
    ただし公開ページのソースに設計メモが並んでいるのは正常な状態ではないので、
    書き出すときに外す。CSSのコメントは <style> の中だけを対象にする
    （JavaScript の中の /* */ を巻き込まないため）。
    """
    html = re.sub(r"<!--.*?-->", "", html, flags=re.S)

    def _style(m):
        return m.group(1) + re.sub(r"/\*.*?\*/", "", m.group(2), flags=re.S) + m.group(3)

    html = re.sub(r"(<style[^>]*>)(.*?)(</style>)", _style, html, flags=re.S)
    # コメントを抜いた跡に残る空行を畳む
    html = re.sub(r"\n[ \t]*\n[ \t]*\n+", "\n\n", html)
    return html


ROOT = pathlib.Path(__file__).resolve().parent.parent

# 配信先ごとに、フォームの受け口と出力先が変わる
TARGETS = {
    # ロリポップなど、PHPが動くサーバー
    "php": {"out": ROOT / "deploy" / "htdocs"},
    # Netlify。フォームはNetlify Formsが受ける
    "netlify": {"out": ROOT / "deploy" / "netlify"},
}

BASE_URL = "https://lp.one-hitter.jp"

# 計測の設定と、埋め込むスクリプトの置き場所
TRACKING_DIR = ROOT / "tracking"
MEASUREMENT_JSON = TRACKING_DIR / "measurement.json"
EVENTS_JS = TRACKING_DIR / "events.js"
THANKS_TEMPLATE = ROOT / "tools" / "templates" / "thanks.html"

PAGES = {
    "aircon": {
        "dir": "aircon",
        "lp_id": "aircon",
        "lp_variant": "A",
        "title": "エアコンクリーニング 10,780円／60分｜東京・千葉・神奈川｜ONE HITTER",
        "desc": "フィルター掃除では届かない、熱交換器と送風ファンの黒カビを分解洗浄。"
                "ノーマルエアコン10,780円（税込）・60分、お見積り以上の追加請求はありません。"
                "東京・千葉・神奈川、最短即日。",
        "label": "エアコン",
        "og": "aircon/img/og.jpg",
        "og_line1": "エアコン内部のカビを、分解洗浄",
        "og_line2": "ノーマル 10,780円（税込）／60分・東京 千葉 神奈川",
    },
    # パターンAに対するA/Bテスト用の対抗案。ヒーローだけが違う
    "aircon-b": {
        "dir": "aircon-b",
        # 計測上は同じ「エアコン」の商品で、ヒーローだけが違う対抗案。
        # lp_id を揃え lp_variant で分けることで、GA4で A/B を並べて比べられる。
        "lp_id": "aircon",
        "lp_variant": "B",
        "title": "エアコン分解洗浄 1台10,780円／60分 最短即日｜東京・千葉・神奈川｜ONE HITTER",
        "desc": "エアコンを分解し、熱交換器と送風ファンを専用機材で洗浄。"
                "ノーマル10,780円（税込）・60分、お掃除機能付き17,380円（税込）・120分。"
                "お見積り以上の追加請求はありません。東京・千葉・神奈川、最短即日。",
        "label": "エアコン（B）",
        "og": "aircon-b/img/og.jpg",
        "og_line1": "エアコン分解洗浄 1台 10,780円／60分",
        "og_line2": "最短即日・追加請求なし・東京 千葉 神奈川",
    },
    "mizumawari": {
        "dir": "mizumawari",
        "lp_id": "mizumawari",
        "lp_variant": "A",
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

# 計測タグの差し込み口。HEAD の中にあるこの目印を、実物のタグに置き換える。
TRACKING_SLOT = "<!-- ASP・広告計測タグはこの下に貼ってください -->"


def load_measurement() -> dict:
    """tracking/measurement.json を読む。無ければ「全部空」として扱う。

    IDが空でもビルドは通り、タグは出力されない。計測の仕組みだけ先に入れておき、
    GA4の準備ができたら設定ファイルを書き換えて再ビルドすればよい、という作りにしている。
    """
    if not MEASUREMENT_JSON.exists():
        return {}
    data = json.loads(MEASUREMENT_JSON.read_text(encoding="utf-8"))
    # "_readme" や "_note" は人間向けのメモなので、出力には持ち込まない
    return prune_notes(data)


def prune_notes(node):
    if isinstance(node, dict):
        return {k: prune_notes(v) for k, v in node.items() if not k.startswith("_")}
    if isinstance(node, list):
        return [prune_notes(v) for v in node]
    return node


def tel_for(cfg: dict, dir_name: str) -> str:
    """このLPで表示する電話番号。コールトラッキングの発番があればそちらを使う。"""
    call = cfg.get("call_tracking") or {}
    return ((call.get("numbers") or {}).get(dir_name) or "").strip() \
        or (call.get("default_number") or DEFAULT_TEL).strip()


DEFAULT_TEL = "080-8043-8259"


def swap_tel(src: str, number: str) -> str:
    """LPに書かれている既定の番号を、計測用の発番に差し替える。

    LPのソース（lp/ 配下）には手を触れず、書き出すときだけ差し替える。
    表示用（ハイフンあり）と tel: リンク用（ハイフンなし）の両方が本文にあるので、
    どちらも置き換える。番号を戻したいときは measurement.json を空にするだけでよい。
    """
    if number == DEFAULT_TEL:
        return src
    digits = re.sub(r"[^0-9]", "", number)
    src = src.replace(DEFAULT_TEL, number)
    src = src.replace(re.sub(r"[^0-9]", "", DEFAULT_TEL), digits)
    return src


def tracking_head(cfg: dict, page: dict, tel: str = "") -> str:
    """<head> に入れる分。gtag の読み込みと、このページが何なのかの申告。"""
    ga4 = ((cfg.get("ga4") or {}).get("measurement_id") or "").strip()
    ads = ((cfg.get("google_ads") or {}).get("conversion_id") or "").strip()
    phone_label = ((cfg.get("google_ads") or {}).get("phone_conversion_label") or "").strip()
    pixel = ((cfg.get("meta") or {}).get("pixel_id") or "").strip()

    out = ["<!-- ONE HITTER 計測タグ／設定は tracking/measurement.json、設計は docs/measurement-spec.md -->"]
    out.append("<script>window.OH_M=" + json.dumps(
        {"page": page, "google_ads": cfg.get("google_ads") or {}, "debug": bool(cfg.get("debug"))},
        ensure_ascii=False, separators=(",", ":")) + ";</script>")

    if ga4 or ads:
        # 読み込みは1本でよい。gtag('config') を並べれば両方に届く。
        first = ga4 or ads
        lines = ['<script async src="https://www.googletagmanager.com/gtag/js?id=%s"></script>' % first,
                 "<script>",
                 "window.dataLayer=window.dataLayer||[];",
                 "function gtag(){dataLayer.push(arguments);}",
                 "gtag('js',new Date());"]
        if ga4:
            lines.append("gtag('config','%s',{'lp_id':'%s','lp_variant':'%s'});"
                         % (ga4, page["lp_id"], page["lp_variant"]))
        if ads:
            lines.append("gtag('config','%s');" % ads)
        if ads and phone_label and tel:
            # Google広告の「電話番号の動的挿入」。広告経由で来た人にだけ、
            # ページ上の電話番号をGoogle広告専用の転送番号に自動で差し替える。
            # 転送先は結局この番号なので、受電の仕方は変わらない。追加費用は無い。
            # ここに書く番号は、ページに表示されている番号と一致していないと差し替わらない。
            lines.append("gtag('config','%s/%s',{'phone_conversion_number':'%s'});"
                         % (ads, phone_label, tel))
        lines.append("</script>")
        out += lines
    else:
        out.append("<!-- GA4・広告タグは未設定。tracking/measurement.json にIDを入れて再ビルドすると出力されます -->")

    if pixel:
        out += ["<script>",
                "!function(f,b,e,v,n,t,s){if(f.fbq)return;n=f.fbq=function(){n.callMethod?"
                "n.callMethod.apply(n,arguments):n.queue.push(arguments)};if(!f._fbq)f._fbq=n;"
                "n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;"
                "t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}"
                "(window,document,'script','https://connect.facebook.net/en_US/fbevents.js');",
                "fbq('init','%s');fbq('track','PageView');" % pixel,
                "</script>"]

    return "\n".join(out)


def tracking_body() -> str:
    """</body> の直前に入れる分。クリックや送信を拾う本体。"""
    js = EVENTS_JS.read_text(encoding="utf-8") if EVENTS_JS.exists() else ""
    if not js:
        return ""
    return "<script>\n" + js + "</script>"


def build_thanks(cfg: dict, meta: dict, out: pathlib.Path) -> None:
    """送信完了ページを組み立てる。

    ここは「Netlify Forms が受理した後にしか出ない画面」なので、成果
    （generate_lead）を数える場所として一番信用できる。
    以前は aircon と mizumawari の2枚を手で置いていたため、あとから足した
    aircon-b の分が無く、送信すると404になっていた。テンプレートから
    全ページ分を生成するように変えて、取りこぼしが起きないようにする。
    """
    tpl = THANKS_TEMPLATE.read_text(encoding="utf-8")
    tel = tel_for(cfg, meta["dir"])
    page = {"kind": "thanks", "lp_id": meta["lp_id"], "lp_variant": meta["lp_variant"],
            "lead_value": (cfg.get("lead_value") or {}).get(meta["dir"], 0)}

    doc = (tpl.replace("%%DIR%%", meta["dir"])
              .replace("%%TEL_HREF%%", re.sub(r"[^0-9]", "", tel))
              .replace("%%TEL_TEXT%%", html.escape(tel))
              .replace("%%TRACKING_HEAD%%", tracking_head(cfg, page, tel))
              .replace("%%TRACKING_BODY%%", tracking_body()))

    (out / meta["dir"] / "thanks.html").write_text(doc, encoding="utf-8")


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
    draw.rectangle([0, th - 186, tw, th], fill=(13, 59, 92, 232))   # --ink
    draw.text((56, th - 160), line1, font=ImageFont.truetype(JP_FONT, 44), fill=(255, 255, 255, 255))
    draw.text((56, th - 92), line2, font=ImageFont.truetype(JP_FONT, 25), fill=(168, 194, 210, 255))  # --on-ink-2
    draw.text((56, th - 48), "ONE HITTER", font=ImageFont.truetype(LATIN_FONT, 26), fill=(111, 208, 228, 255))  # --aqua-ink

    out = Image.alpha_composite(im, band).convert("RGB")
    out.save(dst, quality=82, optimize=True, progressive=True)


def build_page(name: str, meta: dict, target: str, out: pathlib.Path, cfg: dict) -> None:
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

    # 断片の先頭に Artifact 時代の <title> が残っていて、包むと <body> の中に
    # 2つ目のタイトルが入っていた。GA4は page_title を見るので、紛れの元になる。
    # 正しいタイトルは HEAD 側で付けているので、こちらは落とす。
    src = re.sub(r"^\s*<title>.*?</title>\s*", "", src, count=1, flags=re.S)
    head_meta = {k: v for k, v in meta.items()
                 if not k.startswith("og_") and k not in ("label", "lp_id", "lp_variant")}
    doc = HEAD.format(base=BASE_URL, **head_meta) + src + TAIL

    # 電話番号を計測用の発番に差し替える（設定が空なら何も起きない）
    tel = tel_for(cfg, meta["dir"])
    doc = swap_tel(doc, tel)

    dst = out / meta["dir"]
    dst.mkdir(parents=True, exist_ok=True)
    doc = strip_comments(doc)

    # 計測タグの差し込み。コメントを落としたあとに入れる
    # （strip_comments に消されないようにするため）。
    page = {"kind": "lp", "lp_id": meta["lp_id"], "lp_variant": meta["lp_variant"]}
    if TRACKING_SLOT not in doc:
        # strip_comments が目印ごと消すので、</head> を手がかりに入れる
        doc = doc.replace("</head>", tracking_head(cfg, page, tel) + "\n</head>", 1)
    else:
        doc = doc.replace(TRACKING_SLOT, tracking_head(cfg, page, tel), 1)
    doc = doc.replace("</body>", tracking_body() + "\n</body>", 1)

    (dst / "index.html").write_text(doc, encoding="utf-8")
    build_thanks(cfg, meta, out)

    img_src = ROOT / "lp" / name / "img"
    img_dst = dst / "img"
    if img_dst.exists():
        shutil.rmtree(img_dst)
    shutil.copytree(img_src, img_dst)

    make_og(img_dst / "hero-bg.jpg", img_dst / "og.jpg", meta["og_line1"], meta["og_line2"])

    print(f"{dst.relative_to(ROOT)}/index.html  {len(doc)//1024}KB  "
          f"画像{len(list(img_dst.iterdir()))}点")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "php"
    if target not in TARGETS:
        raise SystemExit(f"配信先は {' / '.join(TARGETS)} のいずれかです")
    out = TARGETS[target]["out"]
    out.mkdir(parents=True, exist_ok=True)
    cfg = load_measurement()

    ga4 = ((cfg.get("ga4") or {}).get("measurement_id") or "").strip() or "未設定"
    ads = ((cfg.get("google_ads") or {}).get("conversion_id") or "").strip() or "未設定"
    print(f"[{target}] → {out.relative_to(ROOT)}/")
    print(f"  計測： GA4 {ga4} ／ Google広告 {ads}")

    for name, meta in PAGES.items():
        tel = tel_for(cfg, meta["dir"])
        if tel != DEFAULT_TEL:
            print(f"  {meta['dir']}: 電話番号を {tel} に差し替え（コールトラッキング）")
        build_page(name, meta, target, out, cfg)
