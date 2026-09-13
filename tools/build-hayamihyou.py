#!/usr/bin/env python3
"""読本（赤ちゃん版）の「手入れの回数 早見表」＋「やってはいけない4つ」を、冷蔵庫に貼る A4 1枚の PDF にする。

オーナー指摘（2026-09-13）：「本当に役に立つのはその表の下に早見表のみをPDFでダウンロードできるボタン。
冷蔵庫に貼る前提ならレイアウトやデザインも工夫が必要。次の7章も含めて1枚もの。禁止4事項は下部3割くらい」。

中身は tools/dokuhon_content.py の AKACHAN から取る（表と7章の見出し）。文字は増やさない。
出力: lp/media/dokuhon/<akachan|pet>/hayamihyou.pdf（build-dokuhon.py の pdfbtn が指す）。3列目は出典ではなく「備考」（なぜそうするか。K.HAYAMI_BIKOU / K.NG_BIKOU）

使い方:
  python3 tools/build-hayamihyou.py [akachan|pet]   # PDF と確認用 PNG（scratchpad）を書き出す
"""
import asyncio
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import media_common as C  # noqa: E402
import dokuhon_content as K  # noqa: E402

OUTDIR = C.ROOT / "lp" / "media" / "dokuhon"
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


def collect(kind: str):
    blocks = K.ARTICLES[kind]["blocks"]
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
            # 紙には出典ではなく「なぜ」（備考）を載せる。オーナー指摘 2026-09-13
            bikou = K.NG_BIKOU.get(b["h"])
            if not bikou:
                raise SystemExit(f"NG_BIKOU に無い: {b['h']}")
            ng.append((b["h"], q, bikou))
    return table, ng


def html(kind: str, table, ng) -> str:
    title = K.ARTICLES[kind]["title"]
    bik = K.HAYAMI_BIKOU[kind]
    faces = "".join(f"@font-face{{font-family:'{f}';font-weight:{w};src:url('file://{FONTS / fn}') format('truetype');}}" for f, w, fn in FACES)
    rows = ""
    for where, how, _src in table["rows"]:
        if where not in bik:
            raise SystemExit(f"HAYAMI_BIKOU[{kind}] に無い行: {where}")
        how_html = how.replace("<small>", '<span class="s">').replace("</small>", "</span>")
        rows += f'<tr><th>{where}</th><td>{how_html}</td><td class="src">{C.esc(bik[where])}</td></tr>'
    ngs = ""
    for h, q, bikou in ng:
        qq = f'<p>「{C.esc(q)}」</p>' if q else ""
        ngs += f'<div class="ng"><b>{C.esc(h)}</b>{qq}<p class="why">{C.esc(bikou)}</p></div>'
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
tbody td.src{{font-size:8.8pt;color:#4A5054;width:62mm;line-height:1.45;}}
.spacer{{flex:1;}}
.band{{border:2px solid #8E2F1A;border-radius:3mm;padding:5mm 6mm 4mm;margin-top:5mm;}}
.band h2{{font-family:"Shippori Mincho B1",serif;font-weight:700;font-size:14pt;color:#8E2F1A;margin:0 0 3mm;letter-spacing:.04em;}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:3mm 7mm;}}
.ng b{{display:block;font-size:11pt;line-height:1.4;margin-bottom:1mm;}}
.ng b::before{{content:"✕ ";color:#8E2F1A;}}
.ng p{{margin:0;font-size:8.8pt;line-height:1.5;color:#4A5054;}}
.ng p .src{{display:block;color:#7C8388;font-size:7.5pt;}}
.ng p.why{{color:#171A1C;font-weight:500;margin-top:1mm;}}
.foot{{margin-top:4mm;font-size:7.5pt;color:#7C8388;line-height:1.5;display:flex;justify-content:space-between;gap:6mm;}}
</style></head><body><div class="page">
<div class="head"><h1><small>{C.esc(title)}</small>手入れの回数、早見表</h1>
<div class="who">{C.esc(C.UNEI)}<br>{C.DOKUHON_URL.replace("https://", "")}/{kind}/</div></div>
<table><thead><tr><th>どこ</th><th>どのくらい</th><th>備考</th></tr></thead><tbody>{rows}</tbody></table>
<div class="spacer"></div>
<div class="band"><h2>やってはいけない、4つ</h2><div class="grid">{ngs}</div></div>
<div class="foot"><span>回数と「」内の文は、東京都・厚生労働省・国民生活センター・メーカーの公表資料から。根拠の一覧は上のアドレスの読み物の末尾に。</span><span>2026年9月版</span></div>
</div></body></html>"""


async def render(h: str, out: pathlib.Path, kind: str):
    from playwright.async_api import async_playwright
    scratch = pathlib.Path("/tmp/claude-0/-home-user-one-marketing/d45c5ec4-10bd-5587-9fda-1015852d829b/scratchpad/shots")
    scratch.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        pg = await b.new_page(viewport={"width": 794, "height": 1123})
        await pg.set_content(h)
        await pg.wait_for_timeout(600)
        await pg.pdf(path=str(out), format="A4", print_background=True, prefer_css_page_size=True)
        await pg.screenshot(path=str(scratch / f"hayamihyou-{kind}.png"), full_page=True)
        await b.close()


def main():
    for _, _, fn in FACES:
        if not (FONTS / fn).exists():
            sys.exit(f"フォントがありません: {FONTS / fn}（python3 tools/fetch-fonts.py）")
    kinds = sys.argv[1:] or list(K.ARTICLES)
    for kind in kinds:
        table, ng = collect(kind)
        if len(ng) != 4:
            sys.exit(f"{kind}: 7章の「やってはいけない」が4つでない: {len(ng)}")
        out = OUTDIR / kind / "hayamihyou.pdf"
        asyncio.run(render(html(kind, table, ng), out, kind))
        print("書き出し:", out, f"{out.stat().st_size / 1024:.0f}KB")


if __name__ == "__main__":
    main()
