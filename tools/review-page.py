#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""オーナーに見てもらう資料を、画像と文面を1枚にまとめた HTML にする（右ウィンドウでそのまま見られる形）。

【なぜ】
  2026-10-10 オーナー「PDF出力だといちいち保存しないと内容を確認できなくて修正するのに膨大な時間がかかるから
  僕が合格を出すまではこの画面（右ウィンドウ）で見える状態で提示して」。
  → 合格前の提示は、この道具で作った HTML を SendUserFile(display='render') で出す。PDF は合格後に作って渡す。
  画像は data: URI で埋め込むので、HTML 1つで完結する（保存・別ファイル不要）。

【使い方】
  python3 tools/review-page.py spec.json 出力.html

  spec.json の形：
  {"title": "…", "lead": "…（冒頭の説明・任意）",
   "sections": [
     {"heading": "…", "note": "…（任意）",
      "images": ["dist/…/a.png", …],          # 任意
      "texts": [{"label": "メール本文", "body": "…"}]}  # 任意。コピーしやすいよう <pre> で出す
   ]}
"""
import base64
import html
import json
import pathlib
import sys


def img_tag(p: str) -> str:
    b = pathlib.Path(p).read_bytes()
    mime = "image/png" if p.lower().endswith(".png") else "image/jpeg"
    return f'<figure><img src="data:{mime};base64,{base64.b64encode(b).decode()}" alt=""><figcaption>{html.escape(pathlib.Path(p).name)}</figcaption></figure>'


def main() -> None:
    spec = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
    out = pathlib.Path(sys.argv[2])
    e = html.escape
    parts = [f"<h1>{e(spec['title'])}</h1>"]
    if spec.get("lead"):
        parts.append(f'<p class="lead">{e(spec["lead"])}</p>')
    # 右ウィンドウ（iframe）ではページ内リンク #… が効かない（2026-10-10 オーナー「②③のボタンが反応しない」）。
    # → ボタンで1つずつ表示を切り替える。JS が動かない環境でも全部見えるよう、既定は全表示にして JS で絞る
    toc = "".join(f'<button type="button" data-i="{i}">{e(s["heading"])}</button>' for i, s in enumerate(spec["sections"]))
    if len(spec["sections"]) > 1:   # 1件だけなら切り替えボタンを出さない（右ウィンドウでは別々のファイルで出すのが確実）
        parts.append(f'<nav>{toc}</nav>')
    for i, s in enumerate(spec["sections"]):
        parts.append(f'<section data-i="{i}"><h2>{e(s["heading"])}</h2>')
        if s.get("note"):
            parts.append(f'<p class="note">{e(s["note"])}</p>')
        for t in s.get("texts", []):
            parts.append(f'<h3>{e(t["label"])}</h3><pre>{e(t["body"])}</pre>')
        for p in s.get("images", []):
            parts.append(img_tag(p))
        parts.append("</section>")
    doc = f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(spec['title'])}</title>
<style>
:root{{--bg:#f6f7f9;--fg:#1f2937;--card:#fff;--line:#d9dee5;--accent:#f26b1d;--navy:#2f3f63}}
@media (prefers-color-scheme:dark){{:root{{--bg:#16181d;--fg:#e5e7eb;--card:#20242b;--line:#343a44;--navy:#9fb3e0}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font-family:"Noto Sans JP","Hiragino Sans",sans-serif;line-height:1.7}}
main{{max-width:900px;margin:0 auto;padding:16px}}
h1{{font-size:20px;margin:8px 0}} h2{{font-size:18px;border-left:5px solid var(--accent);padding-left:8px;margin:0 0 8px}}
h3{{font-size:14px;margin:14px 0 4px;color:var(--navy)}}
.lead,.note{{font-size:14px}} .note{{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:8px 10px}}
nav{{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0 16px;position:sticky;top:0;background:var(--bg);padding:6px 0;z-index:1}}
nav button{{font:inherit;font-size:14px;padding:6px 14px;border:1px solid var(--line);border-radius:999px;color:inherit;background:var(--card);cursor:pointer}}
nav button[aria-pressed=true]{{background:var(--navy);border-color:var(--navy);color:#fff}}
section{{margin:0 0 32px}}
pre{{white-space:pre-wrap;word-break:break-word;background:var(--card);border:1px solid var(--line);border-radius:6px;padding:12px;font-family:inherit;font-size:14px;margin:0}}
figure{{margin:12px 0}} img{{width:100%;height:auto;border:1px solid var(--line);border-radius:4px;background:#fff}}
figcaption{{font-size:12px;opacity:.7}}
</style></head><body><main>{''.join(parts)}</main>
<script>
(function(){{var bs=document.querySelectorAll('nav button'),ss=document.querySelectorAll('section[data-i]');
function show(i){{ss.forEach(function(s){{s.hidden=s.dataset.i!==i;}});bs.forEach(function(b){{b.setAttribute('aria-pressed',b.dataset.i===i);}});window.scrollTo(0,0);}}
bs.forEach(function(b){{b.addEventListener('click',function(){{show(b.dataset.i);}});}});if(bs.length)show('0');}})();
</script></body></html>"""
    out.write_text(doc, encoding="utf-8")
    print(f"書きました: {out}（{out.stat().st_size // 1024} KB）")


if __name__ == "__main__":
    main()
