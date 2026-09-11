#!/usr/bin/env python3
"""A6カードのデザインカンバス（Claude Design の校正用）を design/a6-card/ に書き出す。

なぜ：CMO指示「印刷物は design スキルで作って査読へ」。査読者（CMO・オーナー）が画面上で文字や余白を
直接直せるように、印刷用の tools/build-a6-card.py と同じ文言（tools/dokuhon_content.py の CARD）から
アートボード（.dc.html）を組む。ここで決まった文言は dokuhon_content.py に戻して、PDFは build-a6-card.py で出す。

A6 = 105×148mm → 96px/inch で 397×559px。フォントは Google Fonts（Shippori Mincho B1 / Zen Kaku Gothic New）。
  python3 tools/build-a6-card-canvas.py
"""
import base64
import io
import json
import pathlib
import sys

import qrcode

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import dokuhon_content as K  # noqa: E402
from media_common import DOKUHON_URL, UNEI, UNEI_ADDR, UNEI_TEL  # noqa: E402

OUT = pathlib.Path(__file__).resolve().parent.parent / "design" / "a6-card"
W, H = 397, 559
FONTS = "https://fonts.googleapis.com/css2?family=Shippori+Mincho+B1:wght@700;800&family=Zen+Kaku+Gothic+New:wght@400;500&display=swap"
CSS = """
body{margin:0;background:#ffffff;color:#171A1C;font-family:"Zen Kaku Gothic New","Hiragino Sans",sans-serif;-webkit-font-smoothing:antialiased;}
a{color:#0E6E82;} a:hover{color:#0A5262;}
.card{width:397px;height:559px;background:#ffffff;padding:40px 34px 34px 34px;box-sizing:border-box;display:flex;flex-direction:column;gap:0;}
.mincho{font-family:"Shippori Mincho B1","Hiragino Mincho ProN",serif;}
"""


def qr_b64(url: str) -> str:
    q = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=0, box_size=6)
    q.add_data(url)
    q.make(fit=True)
    im = q.make_image(fill_color="#171A1C", back_color="white").convert("RGB")
    b = io.BytesIO()
    im.save(b, "PNG", optimize=True)
    return base64.b64encode(b.getvalue()).decode()


def page(body: str) -> str:
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <script src="./support.js"></script>
</head>
<body>
<x-dc>
<helmet>
  <link rel="stylesheet" href="{FONTS}">
  <style>{CSS}</style>
</helmet>
{body}
</x-dc>
</body>
</html>
"""


def front(variant: str, headline: str) -> str:
    c = K.CARD[variant]
    qr = f"qr-{variant}.png"
    if headline == "A":
        top = f"""
  <div style="display:flex;flex-direction:column;gap:10px;">
    <div class="mincho" style="font-weight:800;font-size:64px;line-height:1;letter-spacing:-0.02em;">{c['num']}<span style="font-size:26px;margin-left:4px;">{c['unit']}</span></div>
    <p class="mincho" style="margin:0;font-weight:700;font-size:15.5px;line-height:1.7;text-wrap:pretty;">{c['line']}</p>
    <p style="margin:0;font-size:8.5px;line-height:1.5;color:#7C8388;">{c['num_src']}</p>
  </div>"""
    else:
        q = c["question"].replace("\n", "<br>")
        top = f"""
  <div style="display:flex;flex-direction:column;gap:10px;">
    <p class="mincho" style="margin:0;font-weight:700;font-size:27px;line-height:1.55;">{q}</p>
  </div>"""
    return page(f"""
<div class="card">
  {top}
  <div style="flex-grow:1;"></div>
  <div style="border-top:1px solid #171A1C;padding-top:16px;display:flex;gap:14px;align-items:flex-start;">
    <img src="{qr}" style="width:100px;height:100px;flex:0 0 auto;" alt="QR">
    <div style="display:flex;flex-direction:column;gap:8px;">
      <p class="mincho" style="margin:0;font-weight:700;font-size:12px;line-height:1.55;">{c['title']}</p>
      <p style="margin:0;font-size:9.5px;line-height:1.6;color:#4A5054;">スマホのカメラをかざすと開きます。読むだけ・無料。3分。</p>
    </div>
  </div>
</div>""")


def back(variant: str) -> str:
    c = K.CARD[variant]
    toc = "".join(f'<p class="mincho" style="margin:0;font-weight:700;font-size:10.5px;line-height:1.9;">{t}</p>' for t in c["toc"])
    url = f"{DOKUHON_URL}{c['path']}".replace("https://", "")
    return page(f"""
<div class="card" style="padding-top:46px;">
  <p class="mincho" style="margin:0 0 10px;font-weight:700;font-size:16px;line-height:1.55;">{c['title']}</p>
  <p style="margin:0 0 16px;font-size:10px;line-height:1.75;color:#4A5054;">{c['back']}</p>
  <p style="margin:0 0 2px;font-size:8.5px;color:#7C8388;">目次</p>
  <div style="display:flex;flex-direction:column;gap:0;">{toc}</div>
  <div style="width:40px;border-top:1.5px solid #0E6E82;margin:14px 0 12px;"></div>
  <p style="margin:0;font-size:8.5px;line-height:1.6;color:#7C8388;">QRが読めないときは、このアドレスを開いてください。</p>
  <p style="margin:0;font-size:9.5px;font-weight:500;line-height:1.6;">{url}</p>
  <div style="flex-grow:1;"></div>
  <div style="display:flex;flex-direction:column;gap:0;font-size:8px;line-height:1.55;color:#7C8388;">
    <p style="margin:0;">書いたのは {UNEI}（ハウスクリーニング）</p>
    <p style="margin:0;">{UNEI_ADDR}</p>
    <p style="margin:0;">電話 {UNEI_TEL}</p>
    <p style="margin:0;">読み物の末尾に、当社のクリーニングと無料点検のご案内があります。</p>
  </div>
</div>""")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for v in ("akachan", "pet"):
        (OUT / f"qr-{v}.png").write_bytes(base64.b64decode(qr_b64(f"{DOKUHON_URL}{K.CARD[v]['path']}?src=card")))
    boards = [("Main", front("akachan", "A")), ("AkachanB", front("akachan", "B")), ("AkachanBack", back("akachan")),
              ("PetA", front("pet", "A")), ("PetB", front("pet", "B")), ("PetBack", back("pet"))]
    for name, html in boards:
        (OUT / f"{name}.dc.html").write_text(html, encoding="utf-8")
    x = 0
    arts = []
    for i, (name, _) in enumerate(boards):
        row = 0 if i < 3 else 1
        arts.append({"file": f"{name}.dc.html", "x": (i % 3) * (W + 100), "y": row * (H + 160), "w": W, "h": H,
                     "title": {"Main": "赤ちゃん版 表・A 数字型", "AkachanB": "赤ちゃん版 表・B 問い型", "AkachanBack": "赤ちゃん版 裏",
                               "PetA": "ペット版 表・A", "PetB": "ペット版 表・B", "PetBack": "ペット版 裏"}[name], "print": "fixed"})
    canvas = {"artboards": arts,
              "annotations": [{"id": "memo-1", "x": 0, "y": -150, "w": 520, "text": "A6（105×148mm）。白地・黒の明朝・色なし（施設が普通紙で刷っても成立）。\nA 数字型は読本の冒頭と同じ数字。B 問い型はオーナー案。どちらかを選ぶ。\n文言を直したら tools/dokuhon_content.py に戻し、印刷用PDFは tools/build-a6-card.py で出す。"}],
              "launch": {"view": "canvas"}}
    (OUT / "canvas.json").write_text(json.dumps(canvas, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("書き出しました:", OUT)


if __name__ == "__main__":
    main()
