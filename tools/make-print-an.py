#!/usr/bin/env python3
"""近隣チラシと紹介カードの作り直し案（依頼 20261003-04-lp）。仕上がりの見た目PNGを出す。

  python3 tools/make-print-an.py            # 全案
  python3 tools/make-print-an.py chirashi-a # 1案だけ

生成物（print/an/）:
  <案>.html            元のHTML（Google Fontsを参照）
  <案>[-omote|-ura].png 仕上がり寸法で切り抜いた見た目（3倍）
  一覧.png             全案を並べたもの（CMO・オーナーの講評用）

★入稿用PDFはまだ作らない。オーナーの合格のあと、合格した案だけ塗り足し3mmで書き出す
  （make-chirashi.py / make-shokai-card.py の render と同じ検査を通す）。

【前の版（9/27）から直したこと】docs/チラシ・紹介カード作り直し.md
【金額】data/prices.json から読む。手で打たない。
【実績】98.6%（209名中206名）・Googleクチコミ★5.0（23件・2026年9月時点）。98.8% は使わない。
【写真】LPで公開済みのもの（lp/*/img）。本舗のロゴ・社名・番号、お客様の名前は写っていない。
【QR】独自ドメインの予約ページ。チラシは ?src=chirashi、カードは ?src=shokai。
      案ごとに &cid= を変えて、どの案から何件来たかを数えられるようにする。
"""
import base64
import io
import json
import os
import pathlib
import sys

import segno
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "print" / "an"
YOYAKU = "https://yoyaku.onehitter.jp/"
TEL = "080-8043-8259"
BLEED = 3

FONTS = ("https://fonts.googleapis.com/css2?family=Zen+Maru+Gothic:wght@700;900"
         "&family=BIZ+UDPGothic:wght@400;700&family=Barlow+Semi+Condensed:wght@600;700&display=swap")

# LP v2 と同じ色（lp/mizumawari-b の :root）。紙に刷るので明るさの調整はしない
C = dict(ink="#0D3B5C", ink2="#14506F", paper="#FAF7F2", paper2="#F0EAE1", text="#13232E",
         text2="#3C5262", steel="#536A78", rule="#D7E1E7", cta="#C0300C", ctafill="#B72C0A",
         ctasoft="#FCEAE4", aqua="#0C6B7F", aquasoft="#DDEDF1", mark="#FFE566", oninkk="#EDF4F8")


def yen(n):
    return f"{n:,}"


def prices():
    d = json.loads((ROOT / "data" / "prices.json").read_text(encoding="utf-8"))
    m = {x["名称"]: x for x in d["本メニュー"]}
    p = {
        "ac": m["エアコンクリーニング（ノーマル）"]["単体"],
        "ac2": m["エアコンクリーニング（お掃除機能付き）"]["単体"],
        "bath": m["浴室クリーニング"]["単体"],
        "kit": m["キッチンクリーニング"]["単体"],
        "hood": m["レンジフードクリーニング"]["単体"],
        "wash": m["洗濯機クリーニング"]["単体"],
        "oi": m["追い焚き配管クリーニング"]["単体"],
        "oi_set": m["追い焚き配管クリーニング"]["同時施工"],
        "set2": m["浴室クリーニング"]["同時施工"],
        "hanbo": d["繁忙期加算"]["金額"],
        "shokai": d["紹介"]["紹介された方"]["金額"],
        "shokai_moto": d["紹介"]["消費者から消費者"]["金額"],
    }
    # 「2箇所目から○円」と書くので、浴室・キッチン・レンジフードの同時施工価格がそろっているか確かめる
    sets = {m[k]["同時施工"] for k in ("浴室クリーニング", "キッチンクリーニング", "レンジフードクリーニング")}
    if len(sets) != 1:
        raise SystemExit("浴室・キッチン・レンジフードの同時施工価格がそろっていません。「2箇所目から」の書き方を見直してください。")
    if d["繁忙期加算"]["対象月"] != [5, 6, 7, 12]:
        raise SystemExit("繁忙期の対象月が変わっています。チラシの「12月は加算」の書き方を見直してください。")
    return {k: (yen(v) if isinstance(v, int) else v) for k, v in p.items()}


def photo(rel, px=1400, crop=None):
    im = Image.open(ROOT / "lp" / rel).convert("RGB")
    if crop:   # (左, 上, 右, 下) の比率
        w, h = im.size
        im = im.crop((int(w * crop[0]), int(h * crop[1]), int(w * crop[2]), int(h * crop[3])))
    im.thumbnail((px, px))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=88)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def qr(src, cid, dark=C["ink"]):
    q = segno.make(f"{YOYAKU}?src={src}&cid={cid}", error="m")
    buf = io.BytesIO()
    q.save(buf, kind="png", scale=20, border=0, dark=dark, light="#ffffff")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


BASE_CSS = """
@page {{ size:{pw}mm {ph}mm; margin:0; }}
* {{ margin:0; padding:0; box-sizing:border-box; }}
html,body {{ background:#fff; }}
body {{ font-family:"BIZ UDPGothic","IPAGothic",sans-serif; color:{text};
        -webkit-print-color-adjust:exact; print-color-adjust:exact; font-feature-settings:"palt" 1; }}
.page {{ width:{pw}mm; height:{ph}mm; position:relative; overflow:hidden; background:#fff; page-break-after:always; }}
.trim {{ position:absolute; left:{b}mm; top:{b}mm; width:{tw}mm; height:{th}mm; }}
.maru {{ font-family:"Zen Maru Gothic","BIZ UDPGothic",sans-serif; }}
.num {{ font-family:"Barlow Semi Condensed","BIZ UDPGothic",sans-serif; font-weight:700; letter-spacing:.005em;
        font-variant-numeric:tabular-nums; }}
.yen-u {{ font-family:"BIZ UDPGothic",sans-serif; font-weight:700; }}
.tax {{ font-family:"BIZ UDPGothic",sans-serif; font-weight:400; }}
mark {{ background:linear-gradient(transparent 58%,{mark} 58%); color:inherit; padding:0 .4mm; }}
.qr img {{ display:block; image-rendering:pixelated; }}
"""


def page(cls, inner, bleed_bg=""):
    return f'<section class="page {cls}">{bleed_bg}<div class="trim"><div class="safe">{inner}</div></div></section>'


def doc(title, css, pages, tw, th):
    base = BASE_CSS.format(pw=tw + BLEED * 2, ph=th + BLEED * 2, b=BLEED, tw=tw, th=th, **C)
    return (f'<!doctype html><html lang="ja"><head><meta charset="utf-8"><title>{title}</title>'
            f'<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="stylesheet" href="{FONTS}">'
            f'<style>{base}{css.format(**C)}</style></head><body>{"".join(pages)}</body></html>')


# ---------------------------------------------------------------------------
# チラシ案A「施工のお知らせ」：近所の掲示物の形。今日ここで何をしたかに和真さんが印を付ける
# ---------------------------------------------------------------------------
CSS_A = """
.safe {{ position:absolute; inset:8.4mm 7mm 6mm 7mm; display:flex; flex-direction:column; }}
.notice {{ border:.5mm solid {ink}; border-radius:1.4mm; padding:3.2mm 4mm 3.4mm; position:relative; }}
.notice .tag {{ position:absolute; top:-2.6mm; left:3.4mm; background:{ink}; color:#fff; font-size:7.4pt; font-weight:700;
               padding:.6mm 2.4mm; border-radius:.8mm; letter-spacing:.08em; }}
.notice h1 {{ font-size:17.5pt; font-weight:900; line-height:1.32; color:{ink}; letter-spacing:.01em; margin-top:.8mm; }}
.notice .date {{ display:flex; align-items:flex-end; gap:1.2mm; margin-top:2.4mm; font-size:9pt; font-weight:700; }}
.notice .date i {{ display:inline-block; width:9mm; border-bottom:.3mm solid {text}; height:5mm; }}
.notice .what {{ display:flex; flex-wrap:wrap; gap:1.2mm 3.6mm; margin-top:2mm; font-size:9pt; font-weight:700; }}
.notice .what span::before {{ content:""; display:inline-block; width:3.6mm; height:3.6mm; border:.35mm solid {text};
                               border-radius:.5mm; margin-right:1mm; vertical-align:-.7mm; background:#fff; }}
.notice .sorry {{ font-size:7.4pt; color:{text2}; margin-top:2mm; line-height:1.6; }}
.brandline {{ display:flex; justify-content:space-between; align-items:baseline; margin-top:3.4mm; }}
.brandline .who {{ font-size:8.4pt; font-weight:700; color:{ink}; }}
.brandline .who b {{ font-family:"Barlow Semi Condensed",sans-serif; font-size:12pt; letter-spacing:.1em; margin-right:1.6mm; }}
.brandline .area {{ font-size:7.4pt; color:{steel}; }}
.hero {{ display:grid; grid-template-columns:58mm 1fr; gap:4mm; margin-top:3.4mm; align-items:stretch; }}
.hero img {{ width:58mm; height:58mm; object-fit:cover; border-radius:1.2mm; display:block; }}
.hero .cap {{ display:flex; flex-direction:column; justify-content:center; }}
.hero .cap h2 {{ font-size:14pt; font-weight:900; line-height:1.38; color:{text}; }}
.hero .cap p {{ font-size:8pt; line-height:1.7; color:{text2}; margin-top:2mm; }}
.hero .cap .proof {{ margin-top:2.6mm; display:grid; gap:1.4mm; }}
.hero .cap .proof div {{ display:flex; align-items:baseline; gap:1.6mm; font-size:7.6pt; color:{text2}; }}
.hero .cap .proof b {{ font-size:15pt; color:{ink}; line-height:1; }}
.menu {{ display:grid; grid-template-columns:repeat(4,1fr); margin-top:4mm; border-top:.4mm solid {ink}; border-bottom:.4mm solid {ink}; }}
.menu div {{ padding:2.4mm 1mm 2.2mm; text-align:center; border-left:.2mm solid {rule}; }}
.menu div:first-child {{ border-left:0; }}
.menu .k {{ font-size:8.6pt; font-weight:700; }}
.menu .k small {{ display:block; font-size:6.2pt; font-weight:400; color:{steel}; margin-top:.3mm; }}
.menu .v {{ font-size:19pt; color:{cta}; line-height:1.05; margin-top:1mm; }}
.menu .v .yen-u {{ font-size:7.6pt; margin-left:.3mm; }}
.menu-note {{ font-size:7pt; color:{text2}; margin-top:1.6mm; line-height:1.6; }}
.menu-note b {{ color:{text}; }}
.cta {{ margin-top:auto; display:grid; grid-template-columns:27mm 1fr; gap:4mm; align-items:center;
        background:{paper}; border-radius:1.6mm; padding:3.4mm 4mm; }}
.cta .qr img {{ width:27mm; height:27mm; }}
.cta h3 {{ font-size:12.4pt; font-weight:900; line-height:1.35; color:{ink}; }}
.cta p {{ font-size:7.6pt; color:{text2}; margin-top:1mm; line-height:1.55; }}
.cta .tel {{ font-size:21pt; color:{ink}; line-height:1; margin-top:2mm; }}
.cta .tel small {{ font-family:"BIZ UDPGothic",sans-serif; font-size:7.2pt; font-weight:400; color:{steel}; margin-left:1.4mm; }}
.foot {{ margin-top:2.4mm; font-size:6.4pt; color:{steel}; line-height:1.55; }}
"""


def chirashi_a(p):
    inner = f"""
<div class="notice">
  <span class="tag">お知らせ</span>
  <h1 class="maru">ご近所のお宅で、<br>お掃除をさせていただきました</h1>
  <div class="date"><i></i>月<i></i>日　この近くで</div>
  <div class="what"><span>エアコン</span><span>お風呂</span><span>キッチン</span><span>洗濯機</span><span>そのほか</span></div>
  <p class="sorry">作業中は車の出入りなどでお騒がせいたしました。</p>
</div>
<div class="brandline"><div class="who"><b>ONE HITTER</b>ワンヒッター株式会社のハウスクリーニング</div>
  <div class="area">東京・千葉・神奈川</div></div>

<div class="hero">
  <img src="{photo('nenmatsu/img/water-bucket-black.jpg', 1100)}" alt="">
  <div class="cap">
    <h2 class="maru">エアコンを洗ったあとの<br>水です</h2>
    <p>部品を外して、ご自宅では届かない奥の送風ファンまで洗い流します。作業のあと、この水をお客様にもご覧いただいています。</p>
    <div class="proof">
      <div><b class="num">98.6%</b>が「人に勧めたい」<br>（ご利用者209名中206名）</div>
      <div><b class="num">★5.0</b>Googleクチコミ（23件）</div>
    </div>
  </div>
</div>

<div class="menu">
  <div><p class="k">エアコン<small>壁掛け・1台</small></p><p class="v num">{p['ac']}<span class="yen-u">円</span></p></div>
  <div><p class="k">お風呂<small>天井・換気扇まで</small></p><p class="v num">{p['bath']}<span class="yen-u">円</span></p></div>
  <div><p class="k">キッチン<small>シンク・天板・壁面</small></p><p class="v num">{p['kit']}<span class="yen-u">円</span></p></div>
  <div><p class="k">洗濯機<small>分解して槽の裏まで</small></p><p class="v num">{p['wash']}<span class="yen-u">円</span></p></div>
</div>
<p class="menu-note">すべて税込。お掃除機能付きエアコンは{p['ac2']}円。お風呂・キッチン・レンジフードは<b>2箇所目から{p['set2']}円</b>。<br>
<b>お見積り以上の追加請求はありません。</b>12月は1箇所{p['hanbo']}円の加算があるため、年内は11月中のご予約がおすすめです。</p>

<div class="cta">
  <div class="qr"><img src="{qr('chirashi', 'a')}" alt=""></div>
  <div><h3 class="maru">空いている日を見て、<br>そのまま予約できます</h3>
    <p>スマホのカメラでQRを読み取ってください。お見積りは無料です。</p>
    <p class="tel num">{TEL}<small>お電話 8:00〜20:00</small></p></div>
</div>
<p class="foot">ワンヒッター株式会社　東京都江戸川区北葛西5-14-11 5F</p>
"""
    return doc("近隣チラシ 案A", CSS_A, [page("a", inner)], 148, 210)


# ---------------------------------------------------------------------------
# チラシ案B「料金表」：何がいくらかを先に見せる。6つのメニューを写真つきの札に
# ---------------------------------------------------------------------------
CSS_B = """
.band {{ position:absolute; left:0; right:0; top:0; height:{bandh}mm; background:{ink}; }}
.safe {{ position:absolute; inset:6mm 7mm 6mm 7mm; display:flex; flex-direction:column; }}
.head {{ color:#fff; height:{headh}mm; display:flex; flex-direction:column; justify-content:space-between; }}
.head .top {{ display:flex; justify-content:space-between; align-items:baseline; font-size:7.6pt; color:#A8C2D2; }}
.head .top b {{ font-family:"Barlow Semi Condensed",sans-serif; font-size:12pt; letter-spacing:.12em; color:#fff; }}
.head h1 {{ font-size:19pt; font-weight:900; line-height:1.3; }}
.head h1 em {{ font-style:normal; color:{mark}; }}
.head p {{ font-size:7.8pt; color:#D5E3EC; line-height:1.6; }}
.grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:3mm 3mm; margin-top:5mm; }}
.card .ph {{ display:grid; grid-template-columns:1fr 1fr; gap:.6mm; position:relative; }}
.card .ph img {{ width:100%; height:27mm; object-fit:cover; display:block; }}
.card .ph img:first-child {{ border-radius:1mm 0 0 1mm; }}
.card .ph img:last-child {{ border-radius:0 1mm 1mm 0; }}
.card .ph::after {{ content:"前 → 後"; position:absolute; left:50%; bottom:1mm; transform:translateX(-50%); font-size:5.6pt; font-weight:700;
                    background:rgba(13,59,92,.86); color:#fff; padding:.2mm 1.4mm; border-radius:.6mm; white-space:nowrap; }}
.card h2 {{ font-size:9.4pt; font-weight:700; margin-top:1.6mm; }}
.card h2 small {{ font-size:6.2pt; font-weight:400; color:{steel}; margin-left:.8mm; }}
.card .v {{ font-size:18pt; color:{cta}; line-height:1; margin-top:.8mm; }}
.card .v .yen-u {{ font-size:7.6pt; margin-left:.3mm; }}
.card .v .tax {{ font-size:5.8pt; color:{steel}; margin-left:.5mm; }}
.set {{ margin-top:3.6mm; display:flex; align-items:center; gap:3mm; background:{ctasoft}; border-radius:1.2mm; padding:2.2mm 3.2mm; }}
.set b.big {{ font-size:16pt; color:{cta}; line-height:1; }}
.set p {{ font-size:7.8pt; line-height:1.55; }}
.trust {{ display:grid; grid-template-columns:repeat(3,1fr); margin-top:4.4mm; text-align:center; }}
.trust div {{ border-left:.2mm solid {rule}; padding:0 1mm; }}
.trust div:first-child {{ border-left:0; }}
.trust b {{ display:block; font-size:16pt; color:{ink}; line-height:1.05; }}
.trust span {{ font-size:6.6pt; color:{text2}; line-height:1.45; display:block; margin-top:.6mm; }}
.cta {{ margin-top:auto; display:grid; grid-template-columns:1fr 26mm; gap:4mm; align-items:center; border-top:.4mm solid {ink}; padding-top:3.4mm; }}
.cta h3 {{ font-size:12pt; font-weight:900; color:{ink}; line-height:1.35; }}
.cta p {{ font-size:7.4pt; color:{text2}; margin-top:.8mm; }}
.cta .tel {{ font-size:20pt; color:{ink}; line-height:1; margin-top:1.8mm; }}
.cta .tel small {{ font-family:"BIZ UDPGothic",sans-serif; font-size:7pt; font-weight:400; color:{steel}; margin-left:1.2mm; }}
.cta .qr img {{ width:26mm; height:26mm; }}
.foot {{ margin-top:2.2mm; font-size:6.2pt; color:{steel}; line-height:1.55; }}
"""


def chirashi_b(p):
    tiles = [
        ("エアコン", "壁掛け", p["ac"], "aircon/img/fan-before.jpg", "aircon/img/fan-after.jpg"),
        ("お風呂", "天井・換気扇まで", p["bath"], "mizumawari/img/pan-before.jpg", "mizumawari/img/pan-after.jpg"),
        ("洗濯機", "槽の裏まで分解", p["wash"], "mizumawari/img/drum-before.jpg", "mizumawari/img/drum-after.jpg"),
        ("レンジフード", "", p["hood"], "mizumawari/img/hood-before.jpg", "mizumawari/img/hood-after.jpg"),
        ("キッチン", "シンク・天板", p["kit"], "mizumawari/img/sink-before.jpg", "mizumawari/img/sink-after.jpg"),
        ("追い焚き配管", "汚れを数値で", p["oi"], "mizumawari/img/atp-before.jpg", "mizumawari/img/atp-after.jpg"),
    ]
    cards = "".join(
        f'<div class="card"><div class="ph"><img src="{photo(b, 600)}" alt=""><img src="{photo(a, 600)}" alt=""></div>'
        f'<h2>{k}<small>{s}</small></h2><p class="v num">{v}<span class="yen-u">円</span><span class="tax">税込</span></p></div>'
        for k, s, v, b, a in tiles)
    inner = f"""
<div class="head">
  <div class="top"><b>ONE HITTER</b><span>ワンヒッター株式会社</span></div>
  <h1 class="maru">ご近所で作業中です。<br><em>お掃除の料金表</em>を置いていきます</h1>
  <p>東京・千葉・神奈川のハウスクリーニング。部品を外して洗う分解洗浄です。<br>お掃除機能付きエアコンは{p['ac2']}円（税込）。</p>
</div>
<div class="grid">{cards}</div>
<div class="set"><b class="big num">{p['set2']}<span class="yen-u" style="font-size:7.6pt">円</span></b>
  <p>お風呂・キッチン・レンジフードは、<b>2箇所目からこの価格</b>（税込）。<br>まとめて頼むほどお得です。お見積り以上の追加請求はありません。</p></div>
<div class="trust">
  <div><b class="num">98.6%</b><span>「人に勧めたい」<br>ご利用者209名中206名</span></div>
  <div><b class="num">★5.0</b><span>Googleクチコミ<br>23件（2026年9月）</span></div>
  <div><b class="maru" style="font-size:12pt;padding-top:1.6mm">追加請求なし</b><span>金額にご納得いただいてから<br>作業に入ります</span></div>
</div>
<div class="cta">
  <div><h3 class="maru">空いている日を見て、そのまま予約</h3>
    <p>QRから予約カレンダーが開きます。お見積りは無料です。</p>
    <p class="tel num">{TEL}<small>お電話 8:00〜20:00</small></p></div>
  <div class="qr"><img src="{qr('chirashi', 'b')}" alt=""></div>
</div>
<p class="foot">ワンヒッター株式会社　東京都江戸川区北葛西5-14-11 5F　表示はすべて税込。5〜7月・12月は1箇所{p['hanbo']}円を加算します。</p>
"""
    css = CSS_B.replace("{bandh}", str(BLEED + 6 + 39)).replace("{headh}", "36")
    return doc("近隣チラシ 案B", css, [page("b", inner, '<div class="band"></div>')], 148, 210)


# ---------------------------------------------------------------------------
# チラシ案C（両面）：表は写真1枚で止めさせる。裏で料金と証拠と頼み方を全部
# ---------------------------------------------------------------------------
CSS_C = """
.c-omote .bg {{ position:absolute; inset:0; background:#0B1E2A; }}
.c-omote .bg img {{ position:absolute; left:0; top:0; width:100%; height:68%; object-fit:cover; display:block; }}
.c-omote .bg::after {{ content:""; position:absolute; left:0; right:0; top:46%; height:22%;
                       background:linear-gradient(rgba(11,30,42,0),#0B1E2A); }}
.safe {{ position:absolute; inset:6mm 7mm 6mm 7mm; display:flex; flex-direction:column; }}
.c-omote .safe {{ color:#fff; }}
.c-omote .top {{ display:flex; justify-content:space-between; align-items:center; }}
.c-omote .top span {{ background:rgba(11,30,42,.78); padding:1mm 2.4mm; border-radius:.8mm; font-size:7.6pt; font-weight:700; }}
.c-omote .top b {{ font-family:"Barlow Semi Condensed",sans-serif; font-size:12pt; letter-spacing:.12em;
                   background:rgba(11,30,42,.78); padding:.6mm 2.4mm; border-radius:.8mm; }}
.c-omote .main {{ margin-top:auto; }}
.c-omote h1 {{ font-size:25pt; font-weight:900; line-height:1.28; letter-spacing:.01em; }}
.c-omote h1 em {{ font-style:normal; color:{mark}; }}
.c-omote .sub {{ font-size:9pt; line-height:1.7; color:#D5E3EC; margin-top:3mm; }}
.c-omote .row {{ display:grid; grid-template-columns:1fr 25mm; gap:4mm; align-items:end; margin-top:5mm;
                 border-top:.3mm solid rgba(255,255,255,.35); padding-top:4mm; }}
.c-omote .price {{ font-size:9pt; font-weight:700; }}
.c-omote .price b {{ font-size:30pt; color:#fff; line-height:1; margin:0 .6mm; }}
.c-omote .price .yen-u {{ font-size:10pt; }}
.c-omote .price small {{ display:block; font-size:7.2pt; font-weight:400; color:#A8C2D2; margin-top:1.2mm; }}
.c-omote .qr {{ background:#fff; padding:1.6mm; border-radius:1mm; }}
.c-omote .qr img {{ width:21.8mm; height:21.8mm; }}
.c-omote .qr p {{ font-size:5.8pt; color:{ink}; text-align:center; margin-top:.8mm; font-weight:700; }}
.c-omote .ura {{ font-size:7.2pt; color:#A8C2D2; margin-top:3mm; text-align:right; }}

.c-ura h2 {{ font-size:13pt; font-weight:900; color:{ink}; line-height:1.35; }}
.c-ura h2 small {{ display:block; font-family:"BIZ UDPGothic",sans-serif; font-size:7.6pt; font-weight:400; color:{steel}; margin-top:.8mm; }}
.c-ura table {{ width:100%; border-collapse:collapse; margin-top:3mm; }}
.c-ura td {{ padding:2.5mm 0; border-bottom:.2mm solid {rule}; font-size:9.4pt; font-weight:700; vertical-align:baseline; }}
.c-ura td small {{ font-size:6.6pt; font-weight:400; color:{steel}; margin-left:1mm; }}
.c-ura td.v {{ text-align:right; font-size:16pt; color:{cta}; white-space:nowrap; }}
.c-ura td.v .yen-u {{ font-size:7.4pt; }}
.c-ura td.s {{ text-align:right; font-size:7pt; font-weight:400; color:{text2}; width:24mm; white-space:nowrap; padding-left:2mm; }}
.c-ura td.s b {{ font-family:"Barlow Semi Condensed",sans-serif; font-size:10.4pt; color:{text}; }}
.c-ura tr:first-child td {{ border-top:.4mm solid {ink}; }}
.c-ura .note {{ font-size:6.8pt; color:{text2}; margin-top:1.6mm; line-height:1.6; }}
.c-ura .proof {{ display:grid; grid-template-columns:1fr 1fr; gap:3mm; margin-top:5mm; }}
.c-ura .atp {{ background:{paper}; border-radius:1.2mm; padding:2.6mm 3mm; }}
.c-ura .atp h3 {{ font-size:8.2pt; font-weight:700; }}
.c-ura .atp .nums {{ display:flex; align-items:baseline; gap:1.6mm; margin-top:1.4mm; }}
.c-ura .atp .nums b {{ font-size:17pt; line-height:1; color:{steel}; }}
.c-ura .atp .nums b.after {{ color:{aqua}; }}
.c-ura .atp p {{ font-size:6.4pt; color:{text2}; line-height:1.5; margin-top:1.2mm; }}
.c-ura .voice {{ background:{paper}; border-radius:1.2mm; padding:2.6mm 3mm; display:grid; gap:1.8mm; align-content:start; }}
.c-ura .voice div {{ display:flex; align-items:baseline; gap:1.6mm; font-size:7pt; color:{text2}; line-height:1.4; }}
.c-ura .voice b {{ font-size:15pt; color:{ink}; line-height:1; white-space:nowrap; }}
.c-ura .promise {{ margin-top:4.6mm; display:grid; gap:1.6mm; }}
.c-ura .promise p {{ font-size:8pt; line-height:1.5; padding-left:4.4mm; position:relative; }}
.c-ura .promise p::before {{ content:"✓"; position:absolute; left:0; top:0; color:{aqua}; font-weight:700; }}
.c-ura .cta {{ margin-top:auto; display:grid; grid-template-columns:26mm 1fr; gap:4mm; align-items:center;
               background:{ink}; color:#fff; border-radius:1.6mm; padding:3.2mm 4mm; }}
.c-ura .cta .qr {{ background:#fff; padding:1.4mm; border-radius:.8mm; }}
.c-ura .cta .qr img {{ width:23.2mm; height:23.2mm; }}
.c-ura .cta h3 {{ font-size:11.4pt; font-weight:900; line-height:1.35; }}
.c-ura .cta p {{ font-size:7pt; color:#D5E3EC; margin-top:.8mm; }}
.c-ura .cta .tel {{ font-size:20pt; line-height:1; margin-top:1.8mm; }}
.c-ura .cta .tel small {{ font-family:"BIZ UDPGothic",sans-serif; font-size:6.8pt; font-weight:400; color:#A8C2D2; margin-left:1.2mm; }}
.c-ura .foot {{ margin-top:2.2mm; font-size:6.2pt; color:{steel}; }}
"""


def chirashi_c(p):
    omote = f"""
<div class="top"><span>ご近所で作業中です</span><b>ONE HITTER</b></div>
<div class="main">
  <h1 class="maru">エアコンを洗った<br>あとの<em>水</em>です。</h1>
  <p class="sub">部品を外して、見えない奥の送風ファンまで洗い流します。<br>作業のあと、この水をお客様にもご覧いただいています。</p>
  <div class="row">
    <p class="price">エアコン 壁掛け1台<b class="num">{p['ac']}</b><span class="yen-u">円</span>（税込）
      <small>お風呂・キッチン・洗濯機も承ります（料金は裏面）</small></p>
    <div class="qr"><img src="{qr('chirashi', 'c')}" alt=""><p>空き日を見る</p></div>
  </div>
  <p class="ura">料金・お客様の評価・ご予約の方法は裏面へ →</p>
</div>
"""
    bg = f'<div class="bg"><img src="{photo("nenmatsu/img/water-bucket-black.jpg", 1600)}" alt=""></div>'
    ura = f"""
<h2 class="maru">料金はこれだけです<small>すべて税込。お見積りは無料、お見積り以上の追加請求はありません。</small></h2>
<table>
  <tr><td>エアコン<small>壁掛け・1台</small></td><td class="v num">{p['ac']}<span class="yen-u">円</span></td><td class="s">お掃除機能付き <b>{p['ac2']}</b>円</td></tr>
  <tr><td>お風呂<small>天井・換気扇まで</small></td><td class="v num">{p['bath']}<span class="yen-u">円</span></td><td class="s">2箇所目から <b>{p['set2']}</b>円</td></tr>
  <tr><td>キッチン<small>シンク・天板・壁面</small></td><td class="v num">{p['kit']}<span class="yen-u">円</span></td><td class="s">2箇所目から <b>{p['set2']}</b>円</td></tr>
  <tr><td>レンジフード</td><td class="v num">{p['hood']}<span class="yen-u">円</span></td><td class="s">2箇所目から <b>{p['set2']}</b>円</td></tr>
  <tr><td>洗濯機<small>分解して槽の裏まで</small></td><td class="v num">{p['wash']}<span class="yen-u">円</span></td><td class="s"></td></tr>
  <tr><td>追い焚き配管</td><td class="v num">{p['oi']}<span class="yen-u">円</span></td><td class="s">同時施工で <b>{p['oi_set']}</b>円</td></tr>
</table>
<p class="note">「2箇所目から」「同時施工」は、ほかのお掃除と同じ日にご依頼の場合の2箇所目以降の価格です。<br>
5〜7月・12月は1箇所{p['hanbo']}円を加算します。年内のご予約は、11月中がおすすめです。</p>
<div class="proof">
  <div class="atp"><h3>見えない配管の汚れは、数字で</h3>
    <div class="nums"><b class="num">42,194</b><span>→</span><b class="num after">409</b></div>
    <p>追い焚き配管の汚れを、洗う前と後にお客様の目の前で測ります（実際の測定例。数値は条件で変わります）。</p></div>
  <div class="voice">
    <div><b class="num">98.6%</b><span>のお客様が「人に勧めたい」<br>（ご利用者209名中206名・自社調べ）</span></div>
    <div><b class="num">★5.0</b><span>Googleクチコミ 23件<br>（2026年9月時点）</span></div>
  </div>
</div>
<div class="promise">
  <p>作業の前に金額をお伝えし、ご納得いただいてから始めます。その場でお断りいただいても構いません。</p>
  <p>ご予約を受けた私たちが伺います。下請けの業者は来ません。</p>
</div>
<div class="cta">
  <div class="qr"><img src="{qr('chirashi', 'c')}" alt=""></div>
  <div><h3 class="maru">空いている日を見て、<br>そのまま予約できます</h3>
    <p>スマホのカメラでQRを読み取ってください。</p>
    <p class="tel num">{TEL}<small>お電話 8:00〜20:00</small></p></div>
</div>
<p class="foot">ワンヒッター株式会社　東京都江戸川区北葛西5-14-11 5F</p>
"""
    return doc("近隣チラシ 案C（両面）", CSS_C,
               [page("c-omote", omote, bg), page("c-ura", ura)], 148, 210)


# ---------------------------------------------------------------------------
# 紹介カード（91×55）。表で「1,000円引き」と「誰からの紹介か」、裏で頼み方
# ---------------------------------------------------------------------------
CSS_CARD = """
.safe {{ position:absolute; inset:3.6mm 4mm 3.4mm 4mm; display:flex; flex-direction:column; }}
.k-omote.dark .bgc {{ position:absolute; inset:0; background:{ink}; }}
.k-omote.dark .safe {{ color:#fff; }}
.k-omote .top {{ display:flex; justify-content:space-between; align-items:baseline; font-size:5.6pt; }}
.k-omote .top b {{ font-family:"Barlow Semi Condensed",sans-serif; font-size:8pt; letter-spacing:.12em; }}
.k-omote .top span {{ opacity:.85; }}
.k-omote .off {{ margin-top:2.2mm; font-size:7.4pt; font-weight:700; }}
.k-omote .off b {{ display:block; font-size:25pt; line-height:1; margin-top:.6mm; letter-spacing:.01em; }}
.k-omote.dark .off b {{ color:{mark}; }}
.k-omote .off b .yen-u {{ font-size:11pt; margin:0 .4mm; }}
.k-omote .off b .hiki {{ font-family:"Zen Maru Gothic",sans-serif; font-size:13pt; font-weight:900; }}
.k-omote .from {{ margin-top:auto; display:flex; align-items:flex-end; gap:1.4mm; font-size:7.6pt; font-weight:700; }}
.k-omote .from i {{ flex:1; border-bottom:.3mm solid currentColor; height:5.6mm; }}
.k-omote .what {{ font-size:5.6pt; margin-top:1.6mm; opacity:.85; }}
.k-omote .chips {{ display:flex; gap:1.2mm; margin-top:2.6mm; }}
.k-omote .chips span {{ border:.25mm solid currentColor; border-radius:.6mm; font-size:6.2pt; font-weight:700; padding:.5mm 1.6mm; opacity:.9; }}
.k-omote.photo .ph {{ position:absolute; right:0; top:0; bottom:0; width:{phw}mm; }}
.k-omote.photo .ph img {{ width:100%; height:50%; object-fit:cover; display:block; }}
.k-omote.photo .ph span {{ position:absolute; left:1mm; font-size:5pt; font-weight:700; background:rgba(13,59,92,.86); color:#fff; padding:.2mm 1mm; border-radius:.4mm; }}
.k-omote.photo .safe {{ right:{saferight}mm; }}
.k-omote.photo .off b {{ color:{cta}; }}
.k-omote.photo .top {{ color:{ink}; }}
.k-omote.photo .tag {{ align-self:flex-start; display:inline-block; background:{ink}; color:#fff; font-size:5.6pt; font-weight:700; padding:.4mm 1.6mm; border-radius:.5mm; margin-top:1.6mm; }}

.k-ura h2 {{ font-size:8.6pt; font-weight:900; color:{ink}; line-height:1.4; }}
.k-ura .body {{ display:grid; grid-template-columns:17mm 1fr; gap:3mm; margin-top:2mm; align-items:start; }}
.k-ura .qr img {{ width:17mm; height:17mm; }}
.k-ura .steps p {{ font-size:6.2pt; line-height:1.5; color:{text2}; }}
.k-ura .steps p b {{ color:{text}; }}
.k-ura .steps p.tel {{ font-size:12.4pt; color:{ink}; line-height:1; margin-top:1.4mm; }}
.k-ura .tel small {{ font-family:"BIZ UDPGothic",sans-serif; font-size:5.4pt; font-weight:400; color:{steel}; margin-left:.8mm; }}
.k-ura .menu {{ margin-top:auto; display:grid; grid-template-columns:repeat(4,1fr); border-top:.25mm solid {rule}; padding-top:1.4mm; }}
.k-ura .menu div {{ text-align:center; font-size:5.4pt; color:{text2}; }}
.k-ura .menu b {{ display:block; font-size:9.4pt; color:{text}; line-height:1.1; }}
.k-ura .both {{ font-size:5.6pt; color:{text2}; margin-top:1.4mm; text-align:center; }}
.k-ura .both b {{ color:{cta}; }}
"""


def card_ura(p, cid):
    return f"""
<h2 class="maru">ご予約のときに、ご紹介者のお名前をお伝えください</h2>
<div class="body">
  <div class="qr"><img src="{qr('shokai', cid)}" alt=""></div>
  <div class="steps">
    <p><b>WEB：</b>QRから空いている日を選び、「ご要望」の欄にご紹介者のお名前を。</p>
    <p><b>お電話：</b>「紹介カードを見た」とお伝えください。</p>
    <p class="tel num">{TEL}<small>8:00〜20:00</small></p>
  </div>
</div>
<div class="menu">
  <div><b class="num">{p['ac']}</b>エアコン</div><div><b class="num">{p['bath']}</b>お風呂</div>
  <div><b class="num">{p['kit']}</b>キッチン</div><div><b class="num">{p['wash']}</b>洗濯機</div>
</div>
<p class="both">円・税込（ここから{p['shokai']}円引き）。ご紹介くださった方も、次回<b>{p['shokai_moto']}円引き</b>になります。</p>
"""


def card_a(p):
    omote = f"""
<div class="top"><b>ONE HITTER</b><span>ハウスクリーニング／ワンヒッター株式会社</span></div>
<p class="off">ご紹介の方は、初回のお掃除が<b class="num">{p['shokai']}<span class="yen-u">円</span><span class="hiki">引き</span></b></p>
<div class="chips"><span>エアコン</span><span>お風呂</span><span>キッチン</span><span>洗濯機</span></div>
<div class="from"><i></i><span>様からのご紹介</span></div>
<p class="what">部品を外して洗う分解洗浄／東京・千葉・神奈川</p>
"""
    return doc("紹介カード 案A", CSS_CARD.replace("{phw}", "0").replace("{saferight}", "4"),
               [page("k-omote dark", omote, '<div class="bgc"></div>'), page("k-ura", card_ura(p, "a"))], 91, 55)


def card_b(p):
    phw = 31 + BLEED   # 写真は塗り足しまで
    omote = f"""
<div class="top"><b>ONE HITTER</b></div>
<span class="tag">ご紹介カード</span>
<p class="off">初回のお掃除が<b class="num">{p['shokai']}<span class="yen-u">円</span><span class="hiki">引き</span></b></p>
<div class="from"><i></i><span>様より</span></div>
<p class="what">ワンヒッター株式会社のハウスクリーニング</p>
"""
    ph = (f'<div class="ph"><img src="{photo("mizumawari/img/drum-before.jpg", 700)}" alt="">'
          f'<img src="{photo("mizumawari/img/drum-after.jpg", 700)}" alt="">'
          f'<span style="top:4mm">洗濯機 前</span><span style="top:50%;margin-top:1mm">後</span></div>')
    return doc("紹介カード 案B", CSS_CARD.replace("{phw}", str(phw)).replace("{saferight}", str(phw - BLEED + 4)),
               [page("k-omote photo", omote, ph), page("k-ura", card_ura(p, "b"))], 91, 55)


AN = {
    "chirashi-a": (chirashi_a, 148, 210, 5),
    "chirashi-b": (chirashi_b, 148, 210, 5),
    "chirashi-c": (chirashi_c, 148, 210, 5),
    "card-a": (card_a, 91, 55, 3),
    "card-b": (card_b, 91, 55, 3),
}


def render(name, html, tw, th, min_mm):
    from playwright.sync_api import sync_playwright
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    src = OUT / f"{name}.html"
    src.write_text(html, encoding="utf-8")
    outs = []
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium", headless=True,
                               args=["--no-sandbox", "--disable-dev-shm-usage", "--ssl-version-max=tls1.2", "--disable-quic"],
                               proxy={"server": proxy} if proxy else None)
        pg = b.new_page(device_scale_factor=3)
        pg.goto(src.as_uri(), wait_until="networkidle")
        pg.evaluate("document.fonts.ready")
        fams = pg.evaluate("[...document.fonts].filter(f=>f.status==='loaded').map(f=>f.family)")
        for need in ("Zen Maru Gothic", "BIZ UDPGothic", "Barlow Semi Condensed"):
            if not any(need in f for f in fams):
                raise SystemExit(f"{name}: {need} が読み込めていません。代替フォントの見た目で判断しないため止めます。")
        # はみ出し・詰まりの検査：文字が仕上がり線から min_mm 以上内側にあるか。
        # 中身が枠からあふれていないか（.safe の scrollHeight）も見る
        res = pg.evaluate("""(mn)=>{const mm=96/25.4;const out=[];
          document.querySelectorAll('.page').forEach((pgEl,i)=>{const t=pgEl.querySelector('.trim').getBoundingClientRect();
            let w=99, who='';
            pgEl.querySelectorAll('.safe *').forEach(e=>{if(!e.childNodes.length) return;
              const hasText=[...e.childNodes].some(n=>n.nodeType===3&&n.textContent.trim()); if(!hasText) return;
              const r=e.getBoundingClientRect(); if(!r.width) return;
              const d=Math.min((r.left-t.left)/mm,(t.right-r.right)/mm,(r.top-t.top)/mm,(t.bottom-r.bottom)/mm);
              if(d<w){w=d;who=e.textContent.trim().slice(0,16);}});
            const s=pgEl.querySelector('.safe'); out.push({i,w,who,over:s.scrollHeight-s.clientHeight});});
          return out;}""", min_mm)
        for r in res:
            if r["over"] > 1:
                raise SystemExit(f"{name} {r['i'] + 1}面: 中身が {r['over']}px あふれています。詰めてください。")
            if r["w"] < min_mm:
                raise SystemExit(f"{name} {r['i'] + 1}面: 「{r['who']}」が仕上がり線から {r['w']:.1f}mm（{min_mm}mm以上必要）")
        pages = pg.locator(".page .trim")
        n = pages.count()
        for i in range(n):
            suf = "" if n == 1 else ("-omote" if i == 0 else "-ura")
            out = OUT / f"{name}{suf}.png"
            pages.nth(i).screenshot(path=str(out))
            outs.append(out)
        b.close()
    print(f"{name}: 余白の最小 " + " / ".join(f"{r['w']:.1f}mm" for r in res) + "  " + ", ".join(o.name for o in outs))
    return outs


def ichiran(all_outs):
    """講評用に全案を並べる。チラシは A5 を同じ高さ、カードは2枚ずつ。"""
    H = 1400
    tiles = []
    for name, outs in all_outs:
        for o in outs:
            im = Image.open(o).convert("RGB")
            h = H if name.startswith("chirashi") else 420
            im = im.resize((int(im.width * h / im.height), h), Image.LANCZOS)
            tiles.append((name, o.stem, im))
    chira = [t for t in tiles if t[0].startswith("chirashi")]
    cards = [t for t in tiles if t[0].startswith("card")]
    gap = 40
    w1 = sum(t[2].width for t in chira) + gap * (len(chira) + 1)
    w2 = sum(t[2].width for t in cards) + gap * (len(cards) + 1)
    W = max(w1, w2)
    canvas = Image.new("RGB", (W, H + 420 + gap * 3), "#E6E2DA")
    x = gap
    for _, _, im in chira:
        canvas.paste(im, (x, gap)); x += im.width + gap
    x = gap
    for _, _, im in cards:
        canvas.paste(im, (x, H + gap * 2)); x += im.width + gap
    canvas.save(OUT / "一覧.png", optimize=True)
    print((OUT / "一覧.png").relative_to(ROOT))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    p = prices()
    names = sys.argv[1:] or list(AN)
    all_outs = []
    for n in names:
        fn, tw, th, mn = AN[n]
        all_outs.append((n, render(n, fn(p), tw, th, mn)))
    if not sys.argv[1:]:
        ichiran(all_outs)


if __name__ == "__main__":
    main()
