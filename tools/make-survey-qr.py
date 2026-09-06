#!/usr/bin/env python3
"""アンケートQRの現場用画像を作り直すスクリプト。

URL が変わったらこのファイルの SURVEY_BASE を書き換えて実行するだけでよい。
出力は lp/survey/qr/ の下。

  python3 tools/make-survey-qr.py

生成物:
  survey-<staff>.png / .svg  QR単体
  phone-<staff>.png          現場のスマホに保存して画面を見せる用（1080x1920）
  ONE_HITTER_アンケートQRカード_A4.pdf  印刷運用に切り替えるとき用（card.html が元）
"""
import base64
import io
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import urllib.parse

import segno

# ---- ここだけ書き換える -------------------------------------------------
SURVEY_BASE = "https://one-hitter-survey.netlify.app/"
# ------------------------------------------------------------------------

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "lp" / "survey" / "qr"
FONT_CSS = pathlib.Path(
    "/tmp/claude-0/-home-user-one-marketing/"
    "34dbdc4b-4c9e-56e1-b31d-44fec5a0facf/scratchpad/fonts/embedded.css"
)

TARGETS = [
    {"slug": "watanabe", "staff": "渡辺"},
    {"slug": "generic", "staff": None},
]


def survey_url(staff):
    params = {}
    if staff:
        params["staff"] = staff
    params["src"] = "qr"
    return SURVEY_BASE + "?" + urllib.parse.urlencode(params)


def qr_png_data_uri(url):
    """画面表示用。誤り訂正は M（画面は汚れないので H まで上げる必要がない）。"""
    qr = segno.make(url, error="m")
    buf = io.BytesIO()
    qr.save(buf, kind="png", scale=20, border=2, dark="#0f172a", light="#ffffff")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


CARD_HTML = """<!doctype html>
<meta charset="utf-8">
<style>
{fontcss}
* {{ margin:0; padding:0; box-sizing:border-box; }}
html, body {{ width:1080px; height:1920px; }}
body {{
  font-family:'Zen Kaku Gothic New','Noto Sans JP',sans-serif;
  background:#fff; color:#0f172a;
  display:flex; flex-direction:column;
}}
.head {{
  background:#0e6f7d; color:#fff;
  padding:66px 72px 60px;
}}
.head .name {{ font-size:52px; font-weight:700; letter-spacing:.02em; }}
.head .en {{
  font-family:'Barlow',sans-serif;
  font-size:32px; letter-spacing:.34em; margin-top:16px; opacity:.72;
}}
.body {{ flex:1; padding:96px 72px 0; display:flex; flex-direction:column; }}
h1 {{ font-size:74px; font-weight:700; line-height:1.35; letter-spacing:-.01em; }}
.sub {{ font-size:36px; color:#64748b; margin-top:34px; }}
.qrwrap {{ flex:1; display:flex; align-items:center; justify-content:center; }}
.qrwrap img {{ width:770px; height:770px; image-rendering:pixelated; }}
.offer {{
  border:3px solid #f0c98a; background:#fdf6ec; border-radius:26px;
  padding:44px 48px; margin-bottom:40px;
}}
.offer .lead {{ font-size:32px; color:#7c5a21; }}
.offer .big {{ font-size:52px; font-weight:700; color:#8a5a12; margin-top:18px; }}
.offer .note {{ font-size:30px; color:#a07c3f; margin-top:16px; }}
.staff {{ font-size:28px; color:#94a3b8; padding-bottom:56px; }}
</style>
<div class="head">
  <div class="name">ワンヒッター株式会社</div>
  <div class="en">ONE HITTER</div>
</div>
<div class="body">
  <h1>本日の仕上がりを<br>1分だけ教えてください</h1>
  <div class="sub">カメラを向けるだけです（アプリ不要）</div>
  <div class="qrwrap"><img src="{qr}" alt=""></div>
  <div class="offer">
    <div class="lead">この場で次回のご予約をいただくと</div>
    <div class="big">時期によって 最大 15%OFF</div>
    <div class="note">1〜2月がいちばんおトクです</div>
  </div>
  <div class="staff">{staff_line}</div>
</div>
"""


def render(html, out_png):
    with tempfile.TemporaryDirectory() as td:
        src = pathlib.Path(td) / "card.html"
        src.write_text(html, encoding="utf-8")
        shot = pathlib.Path(td) / "shot.png"
        subprocess.run(
            [
                "/opt/pw-browsers/chromium",
                "--headless=new",
                "--no-sandbox",
                "--disable-gpu",
                "--hide-scrollbars",
                "--force-device-scale-factor=1",
                "--window-size=1080,1920",
                f"--screenshot={shot}",
                src.as_uri(),
            ],
            check=True,
            capture_output=True,
            timeout=120,
        )
        out_png.write_bytes(shot.read_bytes())


def build_print_pdf(fontcss):
    """card.html の QR を差し替えて A4 の PDF を焼き直す。

    紙は汚れる・折れるので、こちらだけ誤り訂正を H にしている。
    card.html は Google Fonts を参照しているが、この環境から外部は引けないので
    レンダリング時だけフォントを埋め込んだものに差し替える。
    """
    card = (OUT / "card.html").read_text(encoding="utf-8")

    url = survey_url(None)
    qr = segno.make(url, error="h")
    buf = io.BytesIO()
    qr.save(buf, kind="png", scale=20, border=2)
    data_uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    card = re.sub(r'var QR = "data:image/png;base64,[^"]*";',
                  'var QR = "%s";' % data_uri, card, count=1)
    (OUT / "card.html").write_text(card, encoding="utf-8")

    render_src = re.sub(
        r'<link rel="preconnect".*?display=swap">',
        "<style>%s</style>" % fontcss,
        card, flags=re.S)

    pdf = OUT / "ONE_HITTER_アンケートQRカード_A4.pdf"
    with tempfile.TemporaryDirectory() as td:
        src = pathlib.Path(td) / "card.html"
        src.write_text(render_src, encoding="utf-8")
        out = pathlib.Path(td) / "out.pdf"
        subprocess.run(
            ["/opt/pw-browsers/chromium", "--headless=new", "--no-sandbox",
             "--disable-gpu", "--no-pdf-header-footer",
             f"--print-to-pdf={out}", src.as_uri()],
            check=True, capture_output=True, timeout=180)
        pdf.write_bytes(out.read_bytes())
    return pdf, url


def main():
    fontcss = FONT_CSS.read_text(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    made = []
    for t in TARGETS:
        url = survey_url(t["staff"])
        # 単体QRは他の資材（紙を含む）に流用されうるので、誤り訂正は H で作る。
        qr = segno.make(url, error="h")
        qr.save(OUT / f"survey-{t['slug']}.png", scale=20, border=2,
                dark="#0f172a", light="#ffffff")
        qr.save(OUT / f"survey-{t['slug']}.svg", scale=20, border=2,
                dark="#0f172a", light="#ffffff")
        html = CARD_HTML.format(
            fontcss=fontcss,
            qr=qr_png_data_uri(url),
            staff_line=f"担当：{t['staff']}" if t["staff"] else "&nbsp;",
        )
        phone = OUT / f"phone-{t['slug']}.png"
        render(html, phone)
        made.append((phone, url))
    made.append(build_print_pdf(fontcss))
    for p, url in made:
        print(f"{p.relative_to(ROOT)}  <- {url}")


if __name__ == "__main__":
    main()
