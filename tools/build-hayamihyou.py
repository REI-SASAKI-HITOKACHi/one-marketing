#!/usr/bin/env python3
"""読本（赤ちゃん版）の「手入れの回数 早見表」＋「やってはいけない4つ」を、冷蔵庫に貼る A4 1枚の PDF にする。

オーナー指摘（2026-09-13）：「本当に役に立つのはその表の下に早見表のみをPDFでダウンロードできるボタン。
冷蔵庫に貼る前提ならレイアウトやデザインも工夫が必要。次の7章も含めて1枚もの。禁止4事項は下部3割くらい」。

中身は tools/dokuhon_content.py の AKACHAN から取る（表と7章の見出し）。文字は増やさない。
出力: lp/media/dokuhon/akachan/hayamihyou.pdf（build-dokuhon.py の pdfbtn が指す）

使い方:
  python3 tools/build-hayamihyou.py            # PDF と確認用 PNG（scratchpad）を書き出す
"""
import asyncio
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import media_common as C  # noqa: E402
import dokuhon_content as K  # noqa: E402

OUT = C.ROOT / "lp" / "media" / "dokuhon" / "akachan" / "hayamihyou.pdf"
FONTS = C.ROOT / "assets" / "fonts"
FACES = [("Shippori Mincho B1", 700, "ShipporiMinchoB1-700.ttf"), ("Shippori Mincho B1", 800, "ShipporiMinchoB1-800.ttf"),
         ("Zen Kaku Gothic New", 400, "ZenKakuGothicNew-400.ttf"), ("Zen Kaku Gothic New", 500, "ZenKakuGothicNew-500.ttf"),
         ("Zen Kaku Gothic New", 700, "ZenKakuGothicNew-700.ttf")]
# 早見表の「出典」列に出す短い名前（PDFは紙なので ※n ではなく名前。URLは末尾に1行）
TANSHUKU = {"tokyo4": "東京都 指針No.4", "tokyo5": "東京都 指針No.5", "mhlw_legio": "厚生労働省", "tokyo31": "東京都 指針No.31",
            "tokyo32": "東京都 指針No.32", "pana_lint": "パナソニック", "panasonic": "パナソニック", "toshiba": "東芝", "tokyo8": "東京都 指針No.8",
            "tokyo27": "東京都 指針No.27", "tokyo9": "東京都 指針No.9", "kokusen": "国民生活センター", "daikin": "ダイキン"}


def plain(s: str) -> str:
    return re.sub(r"<[^>]+>", " ", s).replace("  ", " ").strip()


def collect():
    blocks = K.AKACHAN["blocks"]
    table = next(b for b in blocks if b["t"] == "table" and b["head"][0] == "どこ")
    # 7章：dk ng の見出しと、直後の引用（1文）
    ng = []
    i7 = next(i for i, b in enumerate(blocks) if b["t"] == "ch" and b["no"] == "7")
    for i in range(i7 + 1, len(blocks)):
        b = blocks[i]
        if b["t"] == "reveal":
            break
        if b["t"] == "dk" and b.get("cls") == "ng":
            # 直後が引用ならその1文。引用が無い項目（「布団を干したあと、たたく」）は dk の本文をそのまま
            q, src = "", ""
            nxt = blocks[i + 1] if i + 1 < len(blocks) else {}
            if nxt.get("t") == "q":
                q, src = nxt["x"], TANSHUKU.get(nxt["src"], K.SRC[nxt["src"]][0])
            else:
                q = plain(b["x"]).replace("5章に書いたとおり。", "")  # 紙では章の参照は要らない
            ng.append((b["h"], q, src))
    return table, ng


def html(table, ng) -> str:
    faces = "".join(f"@font-face{{font-family:'{f}';font-weight:{w};src:url('file://{FONTS / fn}') format('truetype');}}" for f, w, fn in FACES)
    rows = ""
    for where, how, src in table["rows"]:
        srcs = "／".join(TANSHUKU.get(k, K.SRC[k][0]) for k in src)
        how_html = how.replace("<small>", '<span class="s">').replace("</small>", "</span>")
        rows += f'<tr><th>{where}</th><td>{how_html}</td><td class="src">{srcs}</td></tr>'
    ngs = ""
    for h, q, src in ng:
        qq = (f'<p>「{C.esc(q)}」<span class="src">{C.esc(src)}</span></p>' if src else f'<p>{C.esc(q)}</p>') if q else ""
        ngs += f'<div class="ng"><b>{C.esc(h)}</b>{qq}</div>'
    return f"""<!doctype html><html lang="ja"><head><meta charset="utf-8"><style>
{faces}
@page{{size:A4;margin:0;}}
*{{box-sizing:border-box;}}
html,body{{margin:0;padding:0;background:#fff;color:#171A1C;font-family:"Zen Kaku Gothic New",sans-serif;-webkit-print-color-adjust:exact;print-color-adjust:exact;}}
.page{{width:210mm;height:297mm;padding:14mm 14mm 10mm;display:flex;flex-direction:column;}}
.head{{display:flex;align-items:flex-end;justify-content:space-between;border-bottom:2px solid #171A1C;padding-bottom:4mm;margin-bottom:5mm;}}
.head h1{{font-family:"Shippori Mincho B1",serif;font-weight:800;font-size:22pt;line-height:1.3;margin:0;letter-spacing:.02em;}}
.head h1 small{{display:block;font-family:"Zen Kaku Gothic New",sans-serif;font-weight:500;font-size:9.5pt;color:#4A5054;letter-spacing:.08em;margin-bottom:2mm;}}
.head .who{{font-size:8.5pt;color:#7C8388;text-align:right;line-height:1.5;}}
table{{border-collapse:collapse;width:100%;font-size:11.5pt;line-height:1.45;}}
thead th{{font-weight:500;font-size:8.5pt;color:#7C8388;text-align:left;padding:0 3mm 2mm 0;border-bottom:1px solid #171A1C;letter-spacing:.08em;}}
tbody th{{text-align:left;font-family:"Shippori Mincho B1",serif;font-weight:700;font-size:12.5pt;padding:3.2mm 3mm 3.2mm 0;border-bottom:1px solid #E3E0D9;white-space:nowrap;width:34mm;vertical-align:top;}}
tbody td{{padding:3.2mm 3mm 3.2mm 0;border-bottom:1px solid #E3E0D9;vertical-align:top;}}
tbody td .s{{display:block;font-size:8.5pt;color:#7C8388;line-height:1.4;}}
tbody td.src{{font-size:8.5pt;color:#7C8388;width:38mm;line-height:1.4;}}
.spacer{{flex:1;}}
.band{{border:2px solid #8E2F1A;border-radius:3mm;padding:5mm 6mm 4mm;margin-top:5mm;}}
.band h2{{font-family:"Shippori Mincho B1",serif;font-weight:700;font-size:14pt;color:#8E2F1A;margin:0 0 3mm;letter-spacing:.04em;}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:3mm 7mm;}}
.ng b{{display:block;font-size:11pt;line-height:1.4;margin-bottom:1mm;}}
.ng b::before{{content:"✕ ";color:#8E2F1A;}}
.ng p{{margin:0;font-size:8.8pt;line-height:1.5;color:#4A5054;}}
.ng p .src{{display:block;color:#7C8388;font-size:7.5pt;}}
.foot{{margin-top:4mm;font-size:7.5pt;color:#7C8388;line-height:1.5;display:flex;justify-content:space-between;gap:6mm;}}
</style></head><body><div class="page">
<div class="head"><h1><small>赤ちゃんが来る前に知っておきたい、家の中の見えない汚れ</small>手入れの回数、早見表</h1>
<div class="who">{C.esc(C.UNEI)}<br>{C.DOKUHON_URL.replace("https://", "")}/akachan/</div></div>
<table><thead><tr><th>どこ</th><th>どのくらい</th><th>出典</th></tr></thead><tbody>{rows}</tbody></table>
<div class="spacer"></div>
<div class="band"><h2>やってはいけない、4つ</h2><div class="grid">{ngs}</div></div>
<div class="foot"><span>数字と「」内はすべて公表資料の原文。東京都「健康・快適居住環境の指針」（hokeniryo.metro.tokyo.lg.jp）／厚生労働省／国民生活センター／各メーカーの公式ページ。全文と出典一覧は上のアドレスの読み物で。</span><span>2026年9月版</span></div>
</div></body></html>"""


async def render(h: str):
    from playwright.async_api import async_playwright
    scratch = pathlib.Path("/tmp/claude-0/-home-user-one-marketing/d45c5ec4-10bd-5587-9fda-1015852d829b/scratchpad/shots")
    scratch.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        pg = await b.new_page(viewport={"width": 794, "height": 1123})
        await pg.set_content(h)
        await pg.wait_for_timeout(600)
        await pg.pdf(path=str(OUT), format="A4", print_background=True, prefer_css_page_size=True)
        await pg.screenshot(path=str(scratch / "hayamihyou.png"), full_page=True)
        await b.close()


def main():
    for _, _, fn in FACES:
        if not (FONTS / fn).exists():
            sys.exit(f"フォントがありません: {FONTS / fn}（python3 tools/fetch-fonts.py）")
    table, ng = collect()
    if len(ng) != 4:
        sys.exit(f"7章の「やってはいけない」が4つでない: {len(ng)}")
    asyncio.run(render(html(table, ng)))
    print("書き出し:", OUT, f"{OUT.stat().st_size / 1024:.0f}KB")


if __name__ == "__main__":
    main()
