#!/usr/bin/env python3
"""施工先の近隣に配るチラシ（A5・片面）を作る。依頼 20260926-01-lp の②。

  python3 tools/make-chirashi.py

生成物（print/chirashi/）:
  chirashi.html                         元のHTML（Google Fontsを参照）
  ONE_HITTER_近隣チラシ_A5_入稿用.pdf    154×216mm（A5 148×210mm＋塗り足し3mm）
  preview.png                           確認用（仕上がり寸法で切り抜いたもの）

【金額】data/prices.json から読む。手で打たない（price-master と食い違わないため）。
【写真】年末LP（lp/nenmatsu/img/）で公開済みのビフォーアフター。写り込みは確認済み。
【名乗り】ワンヒッター株式会社。本舗のロゴ・社名・番号は入れない。
【印刷】お金を使うので、入稿はオーナー確認のあと。
"""
import base64
import io
import json
import os
import pathlib

import segno
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "print" / "chirashi"
URL = "https://yoyaku.onehitter.jp/?src=flyer"
TEL = "080-8043-8259"
TRIM_W, TRIM_H, BLEED = 148, 210, 3
IMG = ROOT / "lp" / "nenmatsu" / "img"


def yen(n: int) -> str:
    return f"{n:,}"


def prices() -> dict:
    d = json.loads((ROOT / "data" / "prices.json").read_text(encoding="utf-8"))
    menu = {m["名称"]: m for m in d["本メニュー"]}
    need = ["エアコンクリーニング（ノーマル）", "エアコンクリーニング（お掃除機能付き）",
            "浴室クリーニング", "レンジフードクリーニング"]
    for n in need:
        if n not in menu:
            raise SystemExit(f"data/prices.json に「{n}」がありません。名称が変わっていないか確かめてください。")
    bath, hood = menu["浴室クリーニング"], menu["レンジフードクリーニング"]
    if bath.get("同時施工") != hood.get("同時施工"):
        raise SystemExit("浴室とレンジフードの同時施工価格が違います。チラシの「各」の書き方を見直してください。")
    hanbo = d["繁忙期加算"]
    tsuki = hanbo["対象月"]
    return {
        "ac": yen(menu[need[0]]["単体"]), "ac2": yen(menu[need[1]]["単体"]),
        "bath": yen(bath["単体"]), "hood": yen(hood["単体"]), "set": yen(bath["同時施工"]),
        "hanbo": yen(hanbo["金額"]),
        # [5, 6, 7, 12] → 「5〜7月・12月」
        "hanbo_tsuki": tsuki_label(tsuki),
    }


def tsuki_label(ms: list) -> str:
    ms = sorted(ms)
    runs, start, prev = [], ms[0], ms[0]
    for m in ms[1:] + [None]:
        if m is not None and m == prev + 1:
            prev = m
            continue
        runs.append(f"{start}月" if start == prev else f"{start}〜{prev}月")
        if m is not None:
            start = prev = m
    return "・".join(runs)


def photo(name: str, px: int = 1000) -> str:
    im = Image.open(IMG / f"{name}.jpg").convert("RGB")
    im.thumbnail((px, px))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=88)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def qr() -> str:
    q = segno.make(URL, error="h")
    buf = io.BytesIO()
    q.save(buf, kind="png", scale=20, border=0, dark="#14323D", light="#ffffff")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


HTML = """<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<title>ONE HITTER 近隣チラシ</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Zen+Kaku+Gothic+New:wght@500;700;900&family=Barlow:wght@600;700&display=swap">
<style>
@page {{ size:{pw}mm {ph}mm; margin:0; }}
* {{ margin:0; padding:0; box-sizing:border-box; }}
html,body {{ background:#fff; }}
body {{ font-family:"Zen Kaku Gothic New","IPAGothic",sans-serif; color:#14323D;
        -webkit-print-color-adjust:exact; print-color-adjust:exact; }}
.page {{ width:{pw}mm; height:{ph}mm; position:relative; overflow:hidden; background:#fff; }}
.trim {{ position:absolute; left:{b}mm; top:{b}mm; width:{tw}mm; height:{th}mm; }}
/* 上の帯は塗り足しまで伸ばす */
.band {{ position:absolute; left:0; right:0; top:0; height:{bandh}mm; background:#0E7C93; }}
.safe {{ position:absolute; left:7mm; right:7mm; top:6mm; bottom:6mm; display:flex; flex-direction:column; }}

.head {{ display:flex; justify-content:space-between; align-items:flex-start; color:#fff; height:22mm; }}
.kinjo {{ font-size:13pt; font-weight:900; line-height:1.35; letter-spacing:.01em; }}
.kinjo small {{ display:block; font-size:7.6pt; font-weight:500; opacity:.92; margin-top:.8mm; letter-spacing:0; }}
.brand {{ text-align:right; font-family:Barlow,sans-serif; font-weight:700; font-size:11pt; letter-spacing:.08em; line-height:1.1; }}
.brand small {{ display:block; font-family:"Zen Kaku Gothic New","IPAGothic",sans-serif; font-weight:500; font-size:6.4pt; letter-spacing:0; margin-top:.8mm; opacity:.92; }}

h1 {{ font-size:19pt; font-weight:900; line-height:1.3; letter-spacing:-.01em; margin-top:6.5mm; }}
h1 em {{ font-style:normal; background:linear-gradient(transparent 62%,#FFE566 62%); padding:0 .6mm; }}
.lead {{ font-size:8.4pt; line-height:1.7; color:#3E5A63; margin-top:2mm; }}

.pairs {{ display:grid; grid-template-columns:1fr 1fr; gap:4mm; margin-top:4.5mm; }}
.pair h3 {{ font-size:8.4pt; font-weight:700; margin-bottom:1.3mm; }}
.ba {{ display:grid; grid-template-columns:1fr 1fr; gap:1mm; }}
.ba figure {{ position:relative; }}
.ba img {{ width:100%; height:22mm; object-fit:cover; display:block; border-radius:.8mm; }}
.ba figcaption {{ position:absolute; left:1mm; top:1mm; font-size:6pt; font-weight:700; color:#fff; background:rgba(20,50,61,.82);
                  padding:.3mm 1.2mm; border-radius:.5mm; }}
.ba figure.after figcaption {{ background:#0E7C93; }}

.price {{ margin-top:4.2mm; border-top:.35mm solid #14323D; }}
.price .row {{ display:flex; align-items:baseline; gap:2mm; padding:1.7mm 0 1.5mm; border-bottom:.2mm solid #C9D6DB; }}
.price .name {{ flex:1; font-size:9.6pt; font-weight:700; }}
.price .name small {{ font-size:7pt; font-weight:500; color:#5D7680; margin-left:1.2mm; }}
.price .yen {{ font-family:Barlow,sans-serif; font-weight:700; font-size:17pt; letter-spacing:.01em; line-height:1; }}
.price .yen .u {{ font-family:"Zen Kaku Gothic New","IPAGothic",sans-serif; font-size:8pt; font-weight:700; margin-left:.4mm; }}
.price .yen .tax {{ font-family:"Zen Kaku Gothic New","IPAGothic",sans-serif; font-size:6.4pt; font-weight:500; color:#5D7680; margin-left:.6mm; }}
.price .sub {{ display:flex; justify-content:flex-end; align-items:baseline; gap:1.4mm; font-size:7.4pt; color:#3E5A63; margin-top:-1mm; padding-bottom:1.6mm; border-bottom:.2mm solid #C9D6DB; }}
.price .sub b {{ font-family:Barlow,sans-serif; font-size:11pt; color:#14323D; }}
.set {{ margin-top:2.2mm; font-size:7.8pt; line-height:1.55; color:#8A5B12; background:#FFF4E3; border:.25mm solid #E2A845; border-radius:.8mm; padding:1.4mm 2.2mm; }}
.set b {{ font-family:Barlow,sans-serif; font-size:10pt; color:#A83714; }}

.trust {{ display:flex; gap:3mm; margin-top:3mm; align-items:center; }}
.trust .num {{ font-family:Barlow,sans-serif; font-weight:700; font-size:22pt; color:#0E7C93; line-height:1; letter-spacing:-.01em; }}
.trust p {{ font-size:7.8pt; line-height:1.5; }}
.trust p small {{ display:block; font-size:5.8pt; color:#6F8288; line-height:1.45; margin-top:.4mm; }}
.promise {{ margin-top:2.2mm; font-size:8.4pt; font-weight:700; }}
.promise em {{ font-style:normal; background:linear-gradient(transparent 60%,#FFE566 60%); padding:0 .4mm; }}

.cta {{ margin-top:auto; display:flex; gap:4mm; align-items:center; border:.5mm solid #14323D; border-radius:1.6mm; padding:2.6mm 3.6mm; }}
.cta img {{ width:23mm; height:23mm; display:block; image-rendering:pixelated; flex:none; }}
.cta .t {{ flex:1; }}
.cta .t b {{ display:block; font-size:10.4pt; font-weight:900; line-height:1.35; }}
.cta .t span {{ display:block; font-size:7.2pt; color:#3E5A63; line-height:1.5; margin-top:.6mm; }}
.cta .tel {{ font-family:Barlow,sans-serif; font-weight:700; font-size:19pt; letter-spacing:.02em; line-height:1; margin-top:1.6mm; }}
.cta .tel small {{ font-family:"Zen Kaku Gothic New","IPAGothic",sans-serif; font-size:7pt; font-weight:500; color:#5D7680; margin-left:1.4mm; letter-spacing:0; }}

.foot {{ margin-top:2.4mm; font-size:6.2pt; line-height:1.6; color:#5D7680; }}
.foot b {{ color:#14323D; }}
</style></head><body>
<section class="page"><div class="band"></div><div class="trim"><div class="safe">

  <div class="head">
    <div class="kinjo">ただいま、この近くで<br>作業をしています<small>お騒がせしております。ご近所のお宅のお掃除に伺っています。</small></div>
    <div class="brand">ONE HITTER<small>ワンヒッター株式会社</small></div>
  </div>

  <h1>エアコン・お風呂・<br>レンジフードの<em>分解洗浄</em></h1>
  <p class="lead">ご自宅では届かない奥の汚れまで、部品を外して洗います。<br>東京都・千葉県・神奈川県でお伺いしています。</p>

  <div class="pairs">
    <div class="pair"><h3>エアコンの吹き出し口</h3><div class="ba">
      <figure><img src="{ac_b}" alt=""><figcaption>作業前</figcaption></figure>
      <figure class="after"><img src="{ac_a}" alt=""><figcaption>作業後</figcaption></figure>
    </div></div>
    <div class="pair"><h3>レンジフードのフィルター</h3><div class="ba">
      <figure><img src="{hood_b}" alt=""><figcaption>作業前</figcaption></figure>
      <figure class="after"><img src="{hood_a}" alt=""><figcaption>作業後</figcaption></figure>
    </div></div>
  </div>

  <div class="price">
    <div class="row"><div class="name">エアコンクリーニング<small>壁掛け・1台</small></div>
      <div class="yen">{ac}<span class="u">円</span><span class="tax">（税込）</span></div></div>
    <div class="sub">お掃除機能付き <b>{ac2}</b>円（税込）</div>
    <div class="row"><div class="name">浴室クリーニング</div>
      <div class="yen">{bath}<span class="u">円</span><span class="tax">（税込）</span></div></div>
    <div class="row"><div class="name">レンジフードクリーニング</div>
      <div class="yen">{hood}<span class="u">円</span><span class="tax">（税込）</span></div></div>
  </div>
  <p class="set">浴室とレンジフードを同時にご依頼いただくと、それぞれ <b>{set}</b>円（税込）になります。</p>

  <div class="trust">
    <div class="num">98.6%</div>
    <p>のお客様が「他の人に勧めたい」と回答<small>ご利用後アンケート 2023年1月〜2025年12月／回答209名中206名・自社調べ</small></p>
  </div>
  <p class="promise"><em>お見積り以上の追加請求はありません。</em></p>

  <div class="cta">
    <img src="{qr}" alt="">
    <div class="t">
      <b>空き枠を見て、WEBで予約</b>
      <span>カメラでQRを読み取るだけです。日にちは後から変更できます。</span>
      <div class="tel">{tel}<small>お電話 8:00〜20:00</small></div>
    </div>
  </div>

  <p class="foot"><b>ワンヒッター株式会社</b>　東京都江戸川区北葛西5-14-11 5F<br>
    表示価格はすべて税込です。{hanbo_tsuki}は繁忙期のため、1箇所あたり {hanbo}円 を加算します。</p>

</div></div></section>
</body></html>
"""


def build_html() -> str:
    return HTML.format(
        pw=TRIM_W + BLEED * 2, ph=TRIM_H + BLEED * 2, b=BLEED, tw=TRIM_W, th=TRIM_H,
        bandh=BLEED + 28, tel=TEL, qr=qr(),
        ac_b=photo("ac-vent-before"), ac_a=photo("ac-vent-after"),
        hood_b=photo("hood-before"), hood_a=photo("hood-after"),
        **prices(),
    )


def render(src: pathlib.Path) -> None:
    from playwright.sync_api import sync_playwright
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    with sync_playwright() as p:
        b = p.chromium.launch(
            executable_path="/opt/pw-browsers/chromium", headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--ssl-version-max=tls1.2", "--disable-quic"],
            proxy={"server": proxy} if proxy else None,
        )
        pg = b.new_page(device_scale_factor=3)
        pg.goto(src.as_uri(), wait_until="networkidle")
        pg.evaluate("document.fonts.ready")
        fams = pg.evaluate("[...document.fonts].filter(f=>f.status==='loaded').map(f=>f.family)")
        if not any("Zen Kaku" in f for f in fams):
            raise SystemExit("Zen Kaku Gothic New が読み込めていません。代替フォントのまま入稿用PDFを作らないため止めます。")
        # はみ出し検査：中身が仕上がり線から 5mm 以上内側にあるか
        worst = pg.evaluate("""()=>{const mm=96/25.4,t=document.querySelector('.trim').getBoundingClientRect();let w=99;
          document.querySelectorAll('.safe *').forEach(e=>{const r=e.getBoundingClientRect(); if(!r.width) return;
            w=Math.min(w,(r.left-t.left)/mm,(t.right-r.right)/mm,(r.top-t.top)/mm,(t.bottom-r.bottom)/mm);}); return w;}""")
        if worst < 5:
            raise SystemExit(f"文字が仕上がり線から {worst:.1f}mm の位置にあります（5mm以上必要）。レイアウトを詰めてください。")
        pdf = OUT / "ONE_HITTER_近隣チラシ_A5_入稿用.pdf"
        pg.pdf(path=str(pdf), width=f"{TRIM_W + BLEED*2}mm", height=f"{TRIM_H + BLEED*2}mm",
               print_background=True, margin={"top": "0", "right": "0", "bottom": "0", "left": "0"})
        pg.locator(".trim").screenshot(path=str(OUT / "preview.png"))
        b.close()
        print(f"仕上がり線からの最小余白: {worst:.1f}mm")
        print(pdf.relative_to(ROOT))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    src = OUT / "chirashi.html"
    src.write_text(build_html(), encoding="utf-8")
    render(src)
    print((OUT / "preview.png").relative_to(ROOT))
    print("QR →", URL)


if __name__ == "__main__":
    main()
