#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""提携先さま ご紹介カード（名刺サイズ）の デザイン案 を出力する。

【何のためか】オーナー 2026-10-09：タカラサービス様（専用ページ＋カード）・青山リアルティー様（カード）に
  電話で了承をいただいた。カードのデザイン案を各社3つ、先にメールでお送りする。
  原稿は print/partner-cards/cards.html（12面＝2社×3案×表裏）。

  python3 tools/build-partner-cards.py
    → dist/partner-cards/<id>.png       各面の画像（塗り足し込み 97×61mm）
    → dist/partner-cards/cards-print.pdf 入稿用の見本（97×61mm×12ページ）
    → dist/partner-cards/takara-design-proposal.pdf / aoyama-design-proposal.pdf  先方に送る提案書（A4横1枚）

  Google Fonts を読むので、node の playwright をプロキシ経由で使う（python の playwright は入っていない）。
"""
import json
import os
import pathlib
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "print" / "partner-cards" / "cards.html"
OUT = ROOT / "dist" / "partner-cards"
OUT.mkdir(parents=True, exist_ok=True)
ASOF = "2026年10月9日"

PROPOSALS = {
    "takara": {
        "file": "takara-design-proposal",
        "to": "株式会社タカラサービス　深堀 様",
        "lead": "御社のお客様に「エアコンの洗浄も御社に頼める」とお伝えするためのカードです。"
                "御社のホームページの紺とオレンジを基調に、3つの方向でご用意しました。",
        "cases": [
            ("案1", "コーポレート",
             "御社サイトの紺の帯とオレンジの線をそのまま使った、いちばん正統派の案。"
             "「設置した会社が洗浄も」と一目で伝わります。"),
            ("案2", "洗浄前・洗浄後の写真",
             "当社施工の洗浄前後の写真で、用途が一瞬で伝わる案。"
             "裏面は「匂う・効かない・水が垂れる」の3つのサインで、渡した後に見返されます。"),
            ("案3", "白と余白",
             "白地に大きな見出しと紺の縦線だけ。製品カタログのように整い、"
             "設置のときにお渡しする名刺と並べても違和感がありません。"),
        ],
        "notes": [
            "名刺サイズ（91×55mm）・両面カラー。文字はすべて7pt以上です。",
            "お問い合わせ先は、仮に御社の全国対応番号 0120-655-080 を入れています。載せる番号・窓口名はご指定に差し替えます。",
            "ご相談の窓口は御社です。当社の名前は「施工：ワンヒッター株式会社」として小さく入れています（不要なら外します）。",
            "案の組み合わせ（例：案1の表＋案2の裏）や、文言の変更も承ります。",
        ],
    },
    "aoyama": {
        "file": "aoyama-design-proposal",
        "to": "青山リアルティー・アドバイザーズ株式会社　荒木 様",
        "lead": "御社が管理・運営される住まいのご入居者さまに、エアコンと水まわりのお手入れをご案内するカードです。"
                "御社のロゴの藍と、ホームページの生成り色を基に、住まいの格に合う3つの方向でご用意しました。",
        "cases": [
            ("案1", "生成りと金の細線",
             "生成りの地に藍の明朝、二重の金の細線。上質な住まいの案内状のような佇まいで、"
             "お部屋のご案内書類に添えても馴染みます。"),
            ("案2", "夜の藍とシャンパンゴールド",
             "深い藍のグラデーションにシャンパンゴールドの文字。もっとも格調の高い案で、"
             "レジデンスのフロントやコンシェルジュに置いても品位を損ないません。"),
            ("案3", "建築の線画",
             "白地に、高層の住まいを細い一本線で描いた案。モダンで知的な印象で、"
             "不動産の専門家である御社らしさを表します。"),
        ],
        "notes": [
            "名刺サイズ（91×55mm）・両面カラー。文字はすべて7pt以上です。",
            "お問い合わせ先は、仮に御社の代表番号 03-6455-5091 を入れています。載せる番号・窓口名はご指定に差し替えます。",
            "ご用命の窓口は御社です。当社の名前は「施工：ワンヒッター株式会社」として小さく入れています（不要なら外します）。",
            "案2の「ARA」の表記は、御社のご了承をいただける場合のみ使います。外した形もお作りできます。",
        ],
    },
}

CSS = """
@page { size: A4 landscape; margin: 0; }
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:"Noto Sans JP","IPAGothic",sans-serif;color:#1d2230;-webkit-print-color-adjust:exact;print-color-adjust:exact}
.sheet{width:297mm;height:210mm;padding:11mm 13mm 9mm;display:flex;flex-direction:column}
.head{display:flex;justify-content:space-between;align-items:flex-end;border-bottom:.4mm solid #1d2230;padding-bottom:2mm}
.head h1{font-size:16pt;font-weight:700;letter-spacing:.04em}
.head .to{font-size:10pt;margin-bottom:1mm}
.head .meta{text-align:right;font-size:8.6pt;color:#4a5060;line-height:1.5}
.lead{font-size:9pt;line-height:1.6;margin:2.6mm 0 3.4mm;color:#333}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:7mm;flex:1}
.case h2{font-size:10.4pt;font-weight:700;display:flex;align-items:baseline;gap:2mm}
.case h2 span{font-size:8pt;font-weight:700;color:#fff;background:#1d2230;padding:.3mm 1.8mm;border-radius:.6mm}
.case p{font-size:8.2pt;line-height:1.6;color:#3b4150;margin:1.4mm 0 2.4mm;min-height:17mm}
.card{width:100%;aspect-ratio:91/55;overflow:hidden;position:relative;box-shadow:0 .6mm 2.4mm rgba(0,0,0,.18);border:.15mm solid #ddd;margin-bottom:2.2mm}
.card img{position:absolute;width:calc(100% * 97 / 91);left:calc(-100% * 3 / 91);top:calc(-100% * 3 / 55);}
.lab{font-size:7.4pt;color:#7a8090;letter-spacing:.1em;margin-bottom:.8mm}
.notes{margin-top:auto;border-top:.2mm solid #c9ccd4;padding-top:2mm;font-size:7.8pt;color:#3b4150;line-height:1.6;columns:2;column-gap:8mm}
.notes li{list-style:none;padding-left:3mm;text-indent:-3mm;break-inside:avoid}
.notes li::before{content:"・"}
"""


def proposal_html(key):
    d = PROPOSALS[key]
    cols = []
    for i, (no, name, text) in enumerate(d["cases"], 1):
        cols.append(f"""<div class="case"><h2><span>{no}</span>{name}</h2><p>{text}</p>
<div class="lab">表</div><div class="card"><img src="{key}-{i}-omote.png"></div>
<div class="lab">裏</div><div class="card"><img src="{key}-{i}-ura.png"></div></div>""")
    notes = "".join(f"<li>{n}</li>" for n in d["notes"])
    return f"""<!doctype html><html lang="ja"><head><meta charset="utf-8"><title>ご紹介カード デザイン案</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700&display=block" rel="stylesheet">
<style>{CSS}</style></head><body><div class="sheet">
<div class="head"><div><p class="to">{d["to"]}</p><h1>ご紹介カード　デザイン案（3案）</h1></div>
<div class="meta">{ASOF}<br>ワンヒッター株式会社</div></div>
<p class="lead">{d["lead"]}</p>
<div class="grid">{"".join(cols)}</div>
<ul class="notes">{notes}</ul>
</div></body></html>"""


def main():
    jobs = []
    for key, d in PROPOSALS.items():
        h = OUT / f"{d['file']}.html"
        h.write_text(proposal_html(key), encoding="utf-8")
        jobs.append([str(h), str(OUT / f"{d['file']}.pdf")])
    js = r"""
const { chromium } = require(require('child_process').execSync('npm root -g').toString().trim() + '/playwright');
const [src, out, jobs] = [process.argv[2], process.argv[3], JSON.parse(process.argv[4])];
(async () => {
  const proxy = process.env.HTTPS_PROXY || process.env.https_proxy;
  const b = await chromium.launch(Object.assign({ args: ['--ignore-certificate-errors'] }, proxy ? { proxy: { server: proxy } } : {}));
  const pg = await b.newPage({ deviceScaleFactor: 4, viewport: { width: 400, height: 260 } });
  await pg.goto('file://' + src, { waitUntil: 'networkidle' });
  await pg.evaluate(() => document.fonts.ready); await pg.waitForTimeout(1500);
  const ids = await pg.$$eval('.page', els => els.map(e => e.id));
  for (const id of ids) await pg.locator('#' + id).screenshot({ path: out + '/' + id + '.png' });
  await pg.pdf({ path: out + '/cards-print.pdf', width: '97mm', height: '61mm', printBackground: true });
  const fonts = [...new Set(await pg.evaluate(() => [...document.fonts].filter(f => f.status === 'loaded').map(f => f.family)))];
  for (const [h, p] of jobs) {
    const q = await b.newPage();
    await q.goto('file://' + h, { waitUntil: 'networkidle' }); await q.evaluate(() => document.fonts.ready);
    await q.pdf({ path: p, width: '297mm', height: '210mm', printBackground: true });
    await q.setViewportSize({ width: 1123, height: 794 });
    await q.screenshot({ path: p.replace(/\.pdf$/, '.png'), fullPage: false });
  }
  console.log('面', ids.length, '／読めた字体', fonts.join(','));
  await b.close();
})();
"""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(js)
    try:
        subprocess.run(["node", f.name, str(SRC), str(OUT), json.dumps(jobs)], check=True, cwd=ROOT)
    finally:
        os.unlink(f.name)
    for _, p in jobs:
        print("書きました:", p)


if __name__ == "__main__":
    main()
