#!/usr/bin/env python3
"""紹介カード（名刺サイズ・両面）を作る。依頼 20260926-01-lp の③。

  python3 tools/make-shokai-card.py

生成物（print/shokai-card/）:
  card.html                        元のHTML（表・裏の2ページ。Google Fontsを参照）
  ONE_HITTER_紹介カード_入稿用.pdf    97×61mm（塗り足し3mm込み）×2ページ。1ページ目が表
  preview-omote.png / preview-ura.png  確認用（仕上がり91×55mmで切り抜いたもの）

【制度】消費者→消費者の紹介は「紹介した本人の次回料金から一律1,000円割引」
       （docs/cmo-savedata.md「紹介の制度」）。紹介された方への割引は無い。
       カードに新しい割引を書かないこと（お金の判断はオーナー）。
【見た目】現場で配っているアンケートQRカード（lp/survey/qr/card.html）とそろえる。
       同じ人が同じ場面で手渡すため。
【印刷】お金を使うので、入稿はオーナー確認のあと。
"""
import base64
import io
import os
import pathlib

import segno

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "print" / "shokai-card"
URL = "https://yoyaku.onehitter.jp/?src=shokai"
TEL = "080-8043-8259"

# 仕上がり 91×55mm、塗り足し 3mm。文字は仕上がり線から 3mm 以上内側に置く。
TRIM_W, TRIM_H, BLEED = 91, 55, 3


def qr_data_uri() -> str:
    # 紙は汚れる・折れるので誤り訂正は H（アンケートQRカードと同じ）
    qr = segno.make(URL, error="h")
    buf = io.BytesIO()
    qr.save(buf, kind="png", scale=20, border=0, dark="#14323D", light="#ffffff")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


HTML = """<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<title>ONE HITTER 紹介カード</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Zen+Kaku+Gothic+New:wght@500;700;900&family=Barlow:wght@600;700&display=swap">
<style>
@page {{ size: {pw}mm {ph}mm; margin: 0; }}
* {{ margin:0; padding:0; box-sizing:border-box; }}
html,body {{ background:#fff; }}
body {{ font-family:"Zen Kaku Gothic New","IPAGothic",sans-serif; color:#14323D;
        -webkit-print-color-adjust:exact; print-color-adjust:exact; }}
.page {{ width:{pw}mm; height:{ph}mm; position:relative; overflow:hidden; background:#fff;
         page-break-after:always; break-after:page; }}
.page:last-child {{ page-break-after:auto; break-after:auto; }}
/* 仕上がり枠（塗り足しの内側）。中身はさらに 3mm 内側 */
.trim {{ position:absolute; left:{b}mm; top:{b}mm; width:{tw}mm; height:{th}mm; }}
.safe {{ position:absolute; left:6.2mm; right:3.6mm; top:3.4mm; bottom:3.2mm; display:flex; flex-direction:column; }}
/* 左の帯は塗り足しまで伸ばす（断裁ずれで白が出ないように） */
.stripe {{ position:absolute; left:0; top:0; bottom:0; width:{sw}mm; background:#0E7C93; }}

.brand {{ font-family:Barlow,sans-serif; font-weight:700; font-size:7pt; letter-spacing:.06em; color:#0E7C93; line-height:1.1; }}
.brand small {{ font-family:"Zen Kaku Gothic New","IPAGothic",sans-serif; font-weight:500; font-size:5pt;
               color:#6F8288; letter-spacing:0; margin-left:1.4mm; }}
.chip {{ position:absolute; right:3.6mm; top:3.2mm; font-size:5.6pt; font-weight:700; color:#fff; background:#0E7C93;
         border-radius:.8mm; padding:.6mm 1.6mm; letter-spacing:.08em; }}

/* 表 */
.omote h1 {{ font-size:10.4pt; font-weight:900; line-height:1.3; margin-top:4.4mm; letter-spacing:-.01em; }}
.kinyu {{ display:flex; align-items:flex-end; gap:1.2mm; margin-top:1.4mm; }}
.kinyu .line {{ flex:0 0 42mm; height:6.4mm; border-bottom:.3mm solid #14323D; }}
.kinyu .sama {{ font-size:9pt; font-weight:700; padding-bottom:.4mm; }}
.omote .lead {{ font-size:6.3pt; line-height:1.55; color:#3E5A63; margin-top:2.6mm; }}
.omote .lead em {{ font-style:normal; font-weight:700; color:#14323D;
                   background:linear-gradient(transparent 60%,#FFE566 60%); padding:0 .3mm; }}
.omote .proof {{ margin-top:auto; font-size:5.2pt; line-height:1.45; color:#6F8288; }}
.omote .proof b {{ font-family:Barlow,sans-serif; font-size:8pt; color:#0E7C93; letter-spacing:.01em; }}

/* 裏 */
.ura h2 {{ font-size:8.2pt; font-weight:900; line-height:1.38; margin-top:2.4mm; letter-spacing:-.01em; }}
.ura h2 em {{ font-style:normal; background:linear-gradient(transparent 60%,#FFE566 60%); padding:0 .3mm; }}
.row {{ display:flex; gap:3mm; margin-top:1.8mm; align-items:flex-start; }}
.qr {{ flex:none; width:19mm; text-align:center; }}
.qr img {{ width:19mm; height:19mm; display:block; image-rendering:pixelated; }}
.qr .cap {{ font-size:5pt; line-height:1.3; color:#3E5A63; margin-top:.8mm; font-weight:700; }}
.how {{ flex:1; display:flex; flex-direction:column; gap:1.3mm; }}
.how .item {{ font-size:5.8pt; line-height:1.45; word-break:auto-phrase; color:#3E5A63; }}
.how .item b {{ display:block; font-size:6.4pt; color:#14323D; }}
.how .tel {{ font-family:Barlow,sans-serif; font-weight:700; font-size:10.5pt; color:#14323D; letter-spacing:.02em; line-height:1.1; }}
.how .tel small {{ font-family:"Zen Kaku Gothic New","IPAGothic",sans-serif; font-size:5.2pt; font-weight:500; color:#6F8288; margin-left:1mm; }}
.ura .foot {{ margin-top:1.2mm; font-size:5pt; line-height:1.45; color:#6F8288; }}
.ura .perk {{ font-size:5.4pt; line-height:1.45; color:#8A5B12; background:#FFF4E3; border:.25mm solid #E2A845;
             border-radius:.8mm; padding:.7mm 1.4mm; margin-top:1.8mm; }}
</style></head><body>

<section class="page omote"><div class="stripe"></div><div class="trim">
  <div class="chip">ご紹介カード</div>
  <div class="safe">
    <div class="brand">ONE HITTER<small>ワンヒッター株式会社</small></div>
    <h1>ハウスクリーニングの<br>ワンヒッターです</h1>
    <div class="kinyu"><div class="line"></div><div class="sama">様からのご紹介</div></div>
    <p class="lead">エアコン・浴室・キッチンまわりのお掃除を承っています。<br><em>お見積り以上の追加請求はありません。</em></p>
    <p class="proof"><b>98.6%</b> のお客様が「他の人に勧めたい」と回答<br>（ご利用後アンケート 2023年1月〜2025年12月／回答209名中206名・自社調べ）</p>
  </div>
</div></section>

<section class="page ura"><div class="stripe"></div><div class="trim">
  <div class="safe">
    <div class="brand">ONE HITTER<small>ワンヒッター株式会社</small></div>
    <h2>ご予約のときに、<em>ご紹介者のお名前</em>を<br>お伝えください</h2>
    <div class="row">
      <div class="qr"><img src="{qr}" alt=""></div>
      <div class="how">
        <div class="item"><b>WEBで予約（空き枠が見られます）</b>QRを読み取り、「ご要望」の欄にご紹介者のお名前をお書きください</div>
        <div class="item"><b>お電話で</b><span class="tel">{tel}<small>8:00〜20:00</small></span></div>
      </div>
    </div>
    <p class="perk">ご紹介くださった方に、次回のお掃除 <b>1,000円割引</b> をお贈りします</p>
    <p class="foot">対応エリア：東京都・千葉県・神奈川県<br>ワンヒッター株式会社　東京都江戸川区北葛西5-14-11 5F</p>
  </div>
</div></section>

</body></html>
"""


def build_html() -> str:
    return HTML.format(
        pw=TRIM_W + BLEED * 2, ph=TRIM_H + BLEED * 2, b=BLEED,
        tw=TRIM_W, th=TRIM_H, sw=BLEED + 2.2, qr=qr_data_uri(), tel=TEL,
    )


def render(html_path: pathlib.Path) -> None:
    from playwright.sync_api import sync_playwright
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    with sync_playwright() as p:
        b = p.chromium.launch(
            executable_path="/opt/pw-browsers/chromium", headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--ssl-version-max=tls1.2", "--disable-quic"],
            proxy={"server": proxy} if proxy else None,
        )
        pg = b.new_page(device_scale_factor=4)
        pg.goto(html_path.as_uri(), wait_until="networkidle")
        pg.evaluate("document.fonts.ready")
        fams = pg.evaluate("[...document.fonts].filter(f=>f.status==='loaded').map(f=>f.family)")
        if not any("Zen Kaku" in f for f in fams):
            raise SystemExit("Zen Kaku Gothic New が読み込めていません。代替フォントのまま印刷用PDFを作らないため止めます。")
        pdf = OUT / "ONE_HITTER_紹介カード_入稿用.pdf"
        pg.pdf(path=str(pdf), width=f"{TRIM_W + BLEED*2}mm", height=f"{TRIM_H + BLEED*2}mm",
               print_background=True, margin={"top": "0", "right": "0", "bottom": "0", "left": "0"})
        # 確認用PNG：仕上がり（塗り足しを除いた 91×55mm）で切り抜く
        pg.emulate_media(media="print")
        for i, name in enumerate(["omote", "ura"]):
            el = pg.locator(".trim").nth(i)
            el.screenshot(path=str(OUT / f"preview-{name}.png"))
        b.close()
        print("読み込めたフォント:", sorted(set(fams)))
        print(pdf.relative_to(ROOT))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    src = OUT / "card.html"
    src.write_text(build_html(), encoding="utf-8")
    render(src)
    for n in ("preview-omote.png", "preview-ura.png"):
        print((OUT / n).relative_to(ROOT))
    print("QR →", URL)


if __name__ == "__main__":
    main()
