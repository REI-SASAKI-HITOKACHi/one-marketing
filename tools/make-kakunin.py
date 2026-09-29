#!/usr/bin/env python3
"""下書きLPの「確認用ページ」を1ファイルで作る。オーナー・CMOが手元で開いて見るためのもの。

  python3 tools/build-site.py netlify --draft mizumawari-b     # 先に下書きをビルド
  python3 tools/make-kakunin.py mizumawari-b [aircon-c ...]    # → preview/kakunin/<名前>.html

確認用なので、本番用の下書き（preview/netlify/<名前>/）から次を変える。
  ・計測タグ（GA4・Google広告・アフィリエイト・イベント送信）を外す … 開いても数字が汚れない
  ・申込ボタンを押しても送信しない
  ・写真をファイルに埋め込む（1ファイルで持ち運べる）／画面上端に「確認用」の帯
本番に出すものではない。preview/ は git にも配信物にも入らない。
"""
import base64
import io
import pathlib
import re
import sys

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
KEISOKU = ["googletagmanager", "gtag(", "dataLayer", "rentracks", "rt.js", "PAGE.lp_variant", "generate_lead"]


def kakunin(name: str) -> pathlib.Path:
    src_dir = ROOT / "preview" / "netlify" / name
    html = (src_dir / "index.html").read_text(encoding="utf-8")
    for block in re.findall(r"<script\b[^>]*>.*?</script>", html, flags=re.S):
        if any(k in block for k in KEISOKU):
            html = html.replace(block, "", 1)
    html = html.replace("<!-- ONE HITTER 計測タグ -->", "")

    def umekomi(m):
        im = Image.open(src_dir / m.group(1)).convert("RGB")
        im.thumbnail((800, 800))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=72)
        return 'src="data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode() + '"'
    html = re.sub(r'src="(img/[^"]+\.jpg)"', umekomi, html)

    html, n = re.subn(r'<form class="form"', '<form class="form" onsubmit="alert(\'確認用のページなので、送信はされません\');return false;"', html, count=1)
    if n != 1:
        raise SystemExit(f"{name}: フォームが見つかりません")
    obi = ('<div style="position:sticky;top:0;z-index:99;background:#FFE566;color:#13232E;font:700 12px/1.6 sans-serif;'
           f'text-align:center;padding:6px 10px">確認用：{name}（本番には出ていません・送信されません）</div>')
    html = html.replace("<body>", "<body>\n" + obi, 1)

    nokori = [k for k in KEISOKU + ["AW-", "G-DLJ"] if k in html]
    if nokori:
        raise SystemExit(f"{name}: 計測の痕跡が残っています {nokori}")
    out = ROOT / "preview" / "kakunin" / f"{name}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for n in sys.argv[1:]:
        p = kakunin(n)
        print(f"{p.relative_to(ROOT)}  {p.stat().st_size // 1024}KB")
