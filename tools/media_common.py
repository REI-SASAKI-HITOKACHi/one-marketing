"""lp/media/ 配下のページ（無料点検・読本・洗いどき）で共通に使う部品。

デザイントークンとベースCSSは lp/survey/index.html から取り出して使う（LPとトーンを揃える）。
LP本体（lp/aircon 等）はLP担当の持ち物なので、ここからは一切触らない。
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SURVEY = ROOT / "lp" / "survey" / "index.html"
PRICES = ROOT / "data" / "prices.json"

UNEI = "ワンヒッター株式会社"
UNEI_ADDR = "〒134-0081 東京都江戸川区北葛西5-14-11"
UNEI_TEL = "080-8043-8259"          # 本舗の番号は出さない
UNEI_TANTOU = "佐々木 嶺"
UNEI_SITE = "https://one-hitter.jp/"
PRIVACY = "https://one-hitter.jp/privacy_policy/"
LINE_URL = "https://lin.ee/7kD9WGN"
LP_BASE = "https://one-hitter-lp.netlify.app"
BOOKING = "https://onehitter-yoyaku.netlify.app/"  # 2026-09-12 旧ホスト one-hitter-booking はセーフブラウジング判定のため載せ替え（20260912-10）
TENKEN_URL = "https://one-hitter-tenken.netlify.app"      # 無料点検サイト（未作成なら --create で作る）
DOKUHON_URL = "https://one-hitter-dokuhon.netlify.app"    # 読本サイト（同上）
GOOGLE_FONTS = "https://fonts.googleapis.com/css2?family=Barlow:wght@500;600;700&family=Shippori+Mincho+B1:wght@600;700&family=Zen+Kaku+Gothic+New:wght@400;500;700;900&display=swap"


def esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


def yen(n) -> str:
    return f"{int(n):,}円"


def prices() -> dict:
    d = json.loads(PRICES.read_text(encoding="utf-8"))
    menus = {m["名称"]: m for m in d["本メニュー"]}
    opts = {o["名称"]: o for o in d.get("オプション", [])} if isinstance(d.get("オプション"), list) else {}
    return {"menus": menus, "opts": opts, "raw": d}


def base_css() -> str:
    html = SURVEY.read_text(encoding="utf-8")
    m = re.search(r"<style>(.*?)</style>", html, re.S)
    if not m:
        sys.exit("lp/survey/index.html から <style> を取り出せませんでした")
    css = m.group(1)
    for block in ("/* NPS 0-10 */", "/* ★評価 */"):
        i = css.find(block)
        if i < 0:
            continue
        j = css.find("/* 選択肢 */", i)
        if j > i:
            css = css[:i] + css[j:]
    return css.strip()


COMMON_CSS = """
/* ============ lp/media 共通 ============ */
.logo b{letter-spacing:.02em;font-family:"Shippori Mincho B1",serif;font-size:18px;}
.bar .unei{margin-left:auto;font-size:10.5px;color:var(--muted);text-align:right;line-height:1.5;}
.meiji{font-size:13px;line-height:1.8;color:var(--ink);background:var(--surface);border:2px solid var(--accent);border-radius:10px;padding:12px 14px;}
.meiji b{color:var(--accent-deep);}
.note{font-size:12.5px;color:var(--muted);line-height:1.7;}
.field select{padding:12px 14px;border:1.5px solid var(--line-strong);border-radius:8px;font-family:inherit;font-size:16px;background:var(--surface);color:var(--ink);width:100%;}
.field input[type=file]{padding:10px;font-size:14px;}
.field input[type=date]{padding:12px 14px;border:1.5px solid var(--line-strong);border-radius:8px;font-family:inherit;font-size:16px;background:var(--surface);color:var(--ink);width:100%;}
.agree{display:flex;gap:10px;align-items:flex-start;font-size:13px;line-height:1.7;}
.agree input{width:20px;height:20px;margin-top:2px;flex:0 0 auto;}
.thumbs{display:flex;gap:6px;flex-wrap:wrap;}
.thumbs img,.thumbs video{width:72px;height:72px;object-fit:cover;border-radius:6px;border:1px solid var(--line);}
.tbl{width:100%;border-collapse:collapse;font-size:13.5px;}
.tbl th,.tbl td{border-bottom:1px solid var(--line);padding:8px 6px;text-align:left;vertical-align:top;line-height:1.6;}
.tbl th{color:var(--muted);font-weight:500;white-space:nowrap;width:34%;}
.tbl td .v{font-family:"Barlow",sans-serif;font-variant-numeric:tabular-nums;white-space:nowrap;}
.akawaku{border:3px solid var(--cta);border-radius:10px;padding:14px 15px;background:var(--surface);font-size:13.5px;line-height:1.85;}
.akawaku h3{color:var(--cta-text);font-size:16px;margin-bottom:6px;}
.unei-tbl{display:grid;grid-template-columns:110px 1fr;gap:8px 12px;font-size:13.5px;line-height:1.8;}
.unei-tbl dt{color:var(--muted);}
.unei-tbl dd{margin:0;}
.photo{margin:0;}
.photo img{width:100%;height:auto;display:block;border-radius:10px;border:1px solid var(--line);}
.photo figcaption{font-size:12px;color:var(--muted);line-height:1.6;margin-top:6px;}
.photo .stamp{display:inline-block;font-size:10.5px;letter-spacing:.06em;background:var(--invert);color:#fff;border-radius:4px;padding:2px 7px;margin-right:6px;}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:8px;}
.pair .photo img{aspect-ratio:1/1;object-fit:cover;}
.qr{display:flex;flex-direction:column;align-items:center;gap:8px;background:#fff;border-radius:12px;padding:16px;border:1px solid var(--line);}
.qr canvas,.qr img{width:220px;height:220px;}
.pin{max-width:320px;margin:40px auto;}
@media print{.bar,footer,.noprint{display:none !important;} body{background:#fff;color:#000;padding:0;} .wrap{max-width:none;} .akawaku{border-color:#c00;}}
"""


def head(title: str, desc: str, brand: str, brand_sub: str, extra_css: str = "", home: str = "./", unei_href: str = "./unei.html") -> str:
    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<meta name="robots" content="noindex,nofollow">
<meta name="theme-color" content="#0E7C93">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{GOOGLE_FONTS}">
<style>
{base_css()}
{COMMON_CSS}
{extra_css}
</style>
</head>
<body>
<header class="bar">
  <div class="bar-in">
    <a class="logo" href="{home}" style="text-decoration:none;color:inherit"><b>{esc(brand)}</b><small>{esc(brand_sub)}</small></a>
    <span class="unei">運営：{UNEI}<br><a href="{unei_href}" style="color:inherit">運営者情報</a></span>
  </div>
</header>
<main class="wrap">
"""


def foot(brand: str, line2: str, unei_href: str = "./unei.html") -> str:
    return f"""
</main>
<footer>
  <div class="wrap">
    <b>{esc(brand)}</b>
    <p>
      運営：{UNEI}（ハウスクリーニング業）／{UNEI_ADDR}／{UNEI_TEL}<br>
      {line2}<br>
      <a href="{unei_href}">運営者情報</a>
      <a href="{PRIVACY}" target="_blank" rel="noopener">個人情報の取扱いについて</a>
    </p>
  </div>
</footer>
</body>
</html>
"""


def unei_page(brand: str, brand_sub: str, rows: list, back_label: str = "戻る") -> str:
    dl = "".join(f"<dt>{esc(k)}</dt><dd>{v}</dd>" for k, v in rows)
    body = f"""
  <div class="intro">
    <span class="eyebrow">運営者情報</span>
    <h1>「{esc(brand)}」について</h1>
    <p class="lead">このページは、ハウスクリーニング業を営む {UNEI} が運営しています。</p>
  </div>
  <div class="q"><dl class="unei-tbl">{dl}</dl></div>
  <p style="margin-top:14px"><a class="btn ghost" href="./">{esc(back_label)}</a></p>
"""
    return head(f"運営者情報｜{brand}", f"{brand}の運営者情報", brand, brand_sub) + body + foot(brand, "")


UNEI_ROWS_COMMON = [
    ("運営会社", UNEI),
    ("所在地", UNEI_ADDR),
    ("電話", UNEI_TEL),
    ("代表・担当", UNEI_TANTOU),
    ("事業内容", "ハウスクリーニング（東京都・千葉県・神奈川県）"),
    ("個人情報", f'いただいた情報は、日程のご連絡・報告書やご案内の送付にのみ使います。営業目的の電話はしません。詳細は <a href="{PRIVACY}" target="_blank" rel="noopener">個人情報の取扱い</a> をご覧ください。'),
    ("お問い合わせ", f'<a href="{UNEI_SITE}" target="_blank" rel="noopener">公式サイト</a> または上記の電話番号へ。'),
]
