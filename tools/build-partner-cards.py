#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""提携先さま ご紹介カード（名刺サイズ）の デザイン案 と 提案書 を出力する。

【何のためか】オーナー 2026-10-09：タカラサービス様（専用ページ＋カード）・青山リアルティー様（カード）に
  電話で了承をいただいた。カードのデザイン案を各社3つ、先にメールでお送りする。
  同日「デザインの練度をとにかく上げてくれ。導線設計もちゃんと設計して」→ 提案書は2ページ（1＝3案、2＝ご紹介の流れ）。
  原稿は print/partner-cards/cards.html（12面＝2社×3案×表裏）。

  python3 tools/build-partner-cards.py
    → dist/partner-cards/<id>.png         各面の画像（塗り足し込み 97×61mm）
    → dist/partner-cards/cards-print.pdf   入稿用の見本（97×61mm×12ページ）
    → dist/partner-cards/takara-design-proposal.pdf / aoyama-design-proposal.pdf  先方に送る提案書（A4横2ページ）
       （確認用に -p1.png / -p2.png も出す）

  検査（問題があれば一覧を出して終了コード1）：
    - 文字が仕上がり線から4mm内側（紙の端から7mm）に収まっているか／7pt以上か
    - 段落の最後の行が1〜2字だけになっていないか（孤立文字）／別の段落と重なっていないか
    - QRが読めて、中身が data-url と一致するか（jsQR で 384dpi と 96dpi 相当の2通り）

  Google Fonts と QR のライブラリ（cdnjs / jsDelivr）を読むので、node の playwright をプロキシ経由で使う
  （python の playwright と PIL は入っていない）。
"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "print" / "partner-cards" / "cards.html"
OUT = ROOT / "dist" / "partner-cards"
OUT.mkdir(parents=True, exist_ok=True)
ASOF = "2026年10月10日"

# 提案書2ページ目に載せる、提携先の担当者が使う専用ページ（tools/build-partner.py が作る）
PARTNER_PAGES = {
    "takara": ROOT / "lp" / "partner" / "takara-7q2m" / "index.html",
}
# 青山様の専用ページは作らない（オーナー決定 2026-10-10「青山リアルティ様は専用ページ作らないからね」）。
# 青山様の流れは「お電話・メールでこれまでどおり当社へ」。

PROPOSALS = {
    "takara": {
        "file": "takara-design-proposal",
        "theme": "tk",
        "to": "株式会社タカラサービス　深堀 様",
        "lead": "御社のお客様に「エアコンの洗浄も御社に頼める」とお伝えするカードです。"
                "御社のホームページの紺とオレンジを基に、性格の違う3案をご用意しました。どの案も、お問い合わせ先は御社です。",
        "cases": [
            ("案1", "コーポレート",
             "紺一色の表に、御社の名前を大きく。設置のときにお渡しする名刺と並べても、"
             "同じ会社のものとひと目で分かる、いちばん正統な案です。"),
            ("案2", "分解洗浄の排水",
             "表は、エアコンを分解して洗ったときに出た水の写真。汚れの量がひと目で伝わります。"
             "裏は「匂う・効かない・水が垂れる」の3つのサインで、思い当たった時に見返されます。"),
            ("案3", "記録カード",
             "裏に「設置・前回の洗浄・次回の目安」を書ける欄。リモコンのそばに置いていただくと、"
             "次の洗浄の時期に御社の番号が目に入ります。日付は書かずにお渡しいただいても使えます。"),
        ],
        "notes": [
            "名刺サイズ（91×55mm）・両面カラー。文字はすべて7pt以上、仕上がりの線から4mm以上内側です。",
            "お問い合わせ先は、仮に御社の 0120-655-080 を入れています。載せる番号・窓口名はご指定に差し替えます。",
            "裏面のQRは、御社ホームページのエアコンクリーニングのページ（takara-co.jp/cleaning/）につながります。いまの御社の受付のまま、お客様がお申し込みいただけます。",
            "カードには当社の名前・連絡先を一切載せていません。御社のサービスとしてお渡しください。",
            "案2の写真は、当社が壁掛けエアコンを分解洗浄したときの実際の排水です。業務用の写真への差し替えもできます。",
            "表と裏の組み合わせ（例：案1の表＋案3の裏）や、文言の変更も承ります。",
        ],
        "flow": [
            ("お客様", "c", "カードを見て、御社へ",
             "裏面のQRで御社のクリーニングのページへ。お電話なら「洗浄のカードを見た」と。", "card"),
            ("御社", "p", "ご相談を受ける",
             "台数・機種・場所を伺います。いつもの受付のままです。", "call"),
            ("御社 → 当社", "p", "専用ページで当社へ",
             "見積依頼は台数を入れるだけで、料金（交通費込み）と最短の日がその場で出ます。現地調査は空き枠を選ぶだけです。", "phone"),
            ("当社", "o", "確定のご連絡・施工",
             "日時が決まりしだい御社へ確定のご連絡。当日は当社が伺って分解洗浄します。", "kakutei"),
            ("当社 → 御社", "o", "御社へご報告",
             "洗浄前後の写真と、気づいた点を御社へお送りします。お客様へは御社からお伝えください。", "report"),
        ],
        "vis": {
            "card": '<div class="card"><img src="takara-1-ura.png"></div><p class="cap">QRの行き先は、御社のクリーニングのページ（takara-co.jp/cleaning/）です</p>',
            "call": '<div class="bub"><small>お客様から御社へ</small>「洗浄のカードを見た」</div>',
            "phone": '<div class="phone"><div><img src="flow-takara-partner.png"></div></div><p class="cap">御社専用ページ<br>lp.onehitter.jp/partner/<br>takara-7q2m/</p>',
            "kakutei": '<div class="bub"><small>当社から御社へ</small>○月○日○時に伺います。<br>担当：渡辺</div>',
            "report": '<div class="ph2"><figure><img src="../../lp/aircon/img/fin-before.jpg"><figcaption>洗浄前</figcaption></figure><figure><img src="../../lp/aircon/img/fin-after.jpg"><figcaption>洗浄後</figcaption></figure></div>',
        },
        "burden": ("御社のお手間はここだけ",
                   "お電話を受けて、専用ページで<b>台数と現場</b>を入れて送るだけ。<br>御社向けの料金（交通費込み）と空き枠はその場で分かります。"),
        "boxes": [
            ("カード経由のご相談の数え方",
             "カードを見たお客様からのご相談は、専用ページの「ご紹介カードを見たお客様」に"
             "チェックを入れていただくだけで集計でき、件数は当社からお知らせします。"),
            ("窓口とご請求",
             "ご相談の窓口は御社です。カードにも当社の連絡先は載せていません。ご請求・お支払いはこれまでどおりです。"),
        ],
    },
    "aoyama": {
        "file": "aoyama-design-proposal",
        "theme": "ar",
        "to": "青山リアルティー・アドバイザーズ株式会社　荒木 様",
        "lead": "御社が管理・運営される住まいのご入居者さまに、エアコンと水まわりのお手入れをご案内するカードです。"
                "御社のロゴの藍と、ホームページの生成り色を基に、住まいの格に合う3つの方向でご用意しました。",
        "cases": [
            ("案1", "生成りの案内状",
             "生成りの地に藍の明朝、金の細い枠を一本。上質な住まいの案内状のような佇まいで、"
             "お部屋のご案内書類に添えても馴染みます。"),
            ("案2", "夜の藍",
             "深い藍に、金の「ARA」と一行だけ。もっとも格調の高い案で、"
             "フロントやコンシェルジュのカウンターに置いても品位を損ないません。"),
            ("案3", "縦組み",
             "白い紙に、藍の縦書き。和の便箋のような静けさで、裏は御社の藍に生成りの文字。"
             "日本の住まいの手入れらしさを、いちばん素直に表した案です。"),
        ],
        "notes": [
            "名刺サイズ（91×55mm）・両面カラー。文字はすべて7pt以上、仕上がりの線から4mm以上内側です。",
            "金色の線と文字は、箔押しで仕上げる想定です。用紙は手触りのある厚手の紙をご提案します。",
            "お問い合わせ先は、仮に御社の代表番号 03-6455-5091 を入れています。載せる番号・窓口名はご指定に差し替えます。",
            "カードには当社の名前・連絡先を一切載せていません。御社のご案内としてお渡しください。",
            "案2の「ARA」の表記は、御社のご了承をいただける場合のみ使います（正式なロゴのデータに差し替えます）。外した形もお作りできます。",
            "表と裏の組み合わせや、文言の変更も承ります。",
        ],
        "flow": [
            ("ご入居者さま", "c", "カードを見て、御社へ",
             "お電話で「お手入れのご案内を見た」とお申し付けいただきます。", "card"),
            ("御社", "p", "ご用命を受ける",
             "お部屋・内容・ご希望の日時を伺います。いつもの受付のままです。", "call"),
            ("御社 → 当社", "p", "これまでどおり当社へ",
             "お電話・メールで、お部屋・内容・ご希望の日時をお知らせください。日程の調整は当社が行います。", "phone"),
            ("当社", "o", "確定のご連絡・お伺い",
             "日時が決まりしだい御社へ確定のご連絡。当日は当社が伺います。", "kakutei"),
            ("当社 → 御社", "o", "御社へご報告",
             "作業の前後の写真とご報告を御社へお送りします。", "report"),
        ],
        "vis": {
            "card": '<div class="card"><img src="aoyama-1-ura.png"></div><p class="cap">お部屋のご案内書類に添えて、またはフロントに</p>',
            "call": '<div class="bub"><small>ご入居者さまから御社へ</small>「お手入れのご案内を見た」</div>',
            "phone": '<div class="bub"><small>御社から当社へ（お電話・メール）</small>○○様 ○○号室<br>エアコン2台・浴室<br>ご希望 ○日の午前</div>',
            "kakutei": '<div class="bub"><small>当社から御社へ</small>○月○日○時に伺います。<br>担当：渡辺</div>',
            "report": '<div class="ph2"><figure><img src="../../lp/aircon/img/fin-before.jpg"><figcaption>洗浄前</figcaption></figure><figure><img src="../../lp/aircon/img/fin-after.jpg"><figcaption>洗浄後</figcaption></figure></div>',
        },
        "burden": ("御社のお手間はここだけ",
                   "お電話を受けて、<b>お部屋・内容・ご希望の日時</b>を当社へお知らせいただくだけ。<br>日程の調整・作業・ご報告は当社が行います。"),
        "boxes": [
            ("カード経由のご用命の数え方",
             "お電話で「お手入れのご案内を見た」と伺ったら、当社へのご連絡の際に「カード経由」と"
             "一言添えてください。カード経由の件数を当社で集計し、お知らせします。"),
            ("窓口とご請求",
             "ご用命の窓口は御社です。カードにも当社の連絡先は載せていません。ご請求・お支払いはこれまでどおりです。"),
        ],
    },
}

CSS = """
@page { size: A4 landscape; margin: 0; }
*{margin:0;padding:0;box-sizing:border-box}
p,li{text-wrap:pretty;word-break:auto-phrase}  /* 文節で改行（Chrome の日本語） */
body{font-family:"Noto Sans JP",sans-serif;color:#1d2230;-webkit-print-color-adjust:exact;print-color-adjust:exact;font-feature-settings:"palt" 1}
.sheet{width:297mm;height:210mm;padding:12mm 14mm 10mm;display:flex;flex-direction:column;break-after:page;overflow:hidden;background:#fff}
.tk{--ac:#122F60;--ac2:#FF6600;--soft:#EEF2F8;--rule:#CBD3E2}
.ar{--ac:#2D2A8D;--ac2:#B0905A;--soft:#F7F3E6;--rule:#D9CFB4}
.ar .hf{font-family:"Shippori Mincho B1",serif;font-feature-settings:normal;font-weight:600}
.head{display:flex;justify-content:space-between;align-items:flex-end;border-bottom:.5mm solid var(--ac);padding-bottom:2.4mm}
.head .to{font-size:10pt;margin-bottom:1.4mm;color:#333}
.head h1{font-size:17pt;font-weight:700;letter-spacing:.04em;color:var(--ac)}
.head h1 small{font-size:10pt;font-weight:500;color:#5a6070;margin-left:3mm;letter-spacing:.02em}
.head .meta{text-align:right;font-size:8.6pt;color:#4a5060;line-height:1.6}
.lead{font-size:9.2pt;line-height:1.7;margin:3mm 0 4mm;color:#333}
/* 1ページ目：3案 */
.grid{display:grid;grid-template-columns:repeat(3,1fr);column-gap:10mm}
.case h2{font-size:11pt;font-weight:700;display:flex;align-items:center;gap:2.2mm;color:var(--ac)}
.case h2 span{font-family:"Noto Sans JP",sans-serif;font-size:8pt;font-weight:700;color:#fff;background:var(--ac);padding:.4mm 2mm;letter-spacing:.06em}
.case p{font-size:8.4pt;line-height:1.66;color:#3b4150;margin:1.6mm 0 3mm;height:17mm}
.case .card{width:74mm}
.card{width:100%;aspect-ratio:91/55;overflow:hidden;position:relative;box-shadow:0 .5mm 2mm rgba(0,0,0,.16);outline:.1mm solid rgba(0,0,0,.08)}
.card img{position:absolute;width:calc(100% * 97 / 91);left:calc(-100% * 3 / 91);top:calc(-100% * 3 / 55)}
.lab{font-size:7.4pt;color:#7a8090;letter-spacing:.14em;margin:0 0 1mm}
.lab.u{margin-top:2.6mm}
.notes{margin-top:auto;border-top:.2mm solid var(--rule);padding-top:2.4mm;font-size:7.8pt;color:#3b4150;line-height:1.6;columns:2;column-gap:9mm}
.notes li{list-style:none;padding-left:3mm;text-indent:-3mm;break-inside:avoid;margin-bottom:.4mm}
.notes li::before{content:"・"}
/* 2ページ目：ご紹介の流れ（5段。御社の段＝2・3を色の面で囲む） */
.flow{display:grid;grid-template-columns:repeat(5,1fr);grid-template-rows:auto auto auto auto;column-gap:8mm;margin-top:6mm;position:relative}
.panel{grid-column:2 / span 2;grid-row:1 / span 4;margin:0 -4mm;background:var(--soft);border-top:1mm solid var(--ac2)}
.plab{grid-column:2 / span 2;grid-row:1;padding-top:2.6mm;font-size:9.4pt;color:var(--ac);letter-spacing:.04em}
.st{grid-row:2;position:relative;display:flex;flex-direction:column;padding-top:4mm}
.st+.st::before{content:"";position:absolute;left:-6.2mm;top:4.6mm;width:4.4mm;height:4.4mm;
  background:no-repeat center/contain url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 10 10'%3E%3Cpath d='M2 1l5 4-5 4' fill='none' stroke='%239aa3b5' stroke-width='1.4'/%3E%3C/svg%3E")}
.st .who{align-self:flex-start;font-size:8pt;font-weight:700;letter-spacing:.06em;padding:.7mm 2.4mm;border-radius:5mm;line-height:1.4}
.st.c .who{background:#E6E8EE;color:#4a5060}
.st.p .who{background:var(--ac);color:#fff}
.st.o .who{background:#fff;color:var(--ac);box-shadow:inset 0 0 0 .3mm var(--ac)}
.st .no{font-family:"Barlow",sans-serif;font-weight:700;font-size:8pt;color:var(--ac2);letter-spacing:.12em;margin-top:3.4mm}
.st h3{font-size:11.6pt;font-weight:700;color:var(--ac);margin-top:.4mm;letter-spacing:.02em}
.st p{font-size:8.4pt;line-height:1.68;color:#3b4150;margin-top:1.6mm}
.vis{grid-row:3;padding-top:4.4mm;display:flex;flex-direction:column;align-items:flex-start}
.vis .card{width:100%}
.vis .cap{font-size:7.6pt;color:#6a7080;margin-top:1.6mm;line-height:1.5}
.phone{width:33mm;height:56mm;border-radius:4mm;background:#1d2230;padding:1.4mm;box-shadow:0 .6mm 2.4mm rgba(0,0,0,.18)}
.phone div{width:100%;height:100%;border-radius:2.4mm;overflow:hidden;background:#fff}
.phone img{width:100%;display:block}
.bub{position:relative;background:#fff;border:.3mm solid var(--rule);border-radius:2.4mm;padding:2.6mm 3mm;font-size:8.6pt;line-height:1.6;color:#2b3140;margin-top:2mm}
.bub::after{content:"";position:absolute;left:5mm;bottom:-1.7mm;width:3mm;height:3mm;background:#fff;border-right:.3mm solid var(--rule);border-bottom:.3mm solid var(--rule);transform:rotate(45deg)}
.bub small{display:block;font-size:7.4pt;color:#6a7080;margin-bottom:.6mm}
.ph2{display:grid;grid-template-columns:1fr 1fr;gap:1mm;width:100%}
.ph2 figure{margin:0}
.ph2 img{width:100%;aspect-ratio:4/3;object-fit:cover;display:block;filter:saturate(.8)}
.ph2 figcaption{font-size:7.4pt;color:#6a7080;margin-top:.6mm}
.burden{grid-column:2 / span 2;grid-row:4;padding:3.4mm 0 4mm;font-size:8.8pt;line-height:1.7;color:#2b3140}
.burden b{color:var(--ac)}
.boxes{margin-top:auto;display:grid;grid-template-columns:1.5fr 1fr;column-gap:9mm;border-top:.2mm solid var(--rule);padding-top:3.4mm}
.boxes h4{font-size:9pt;font-weight:700;color:var(--ac);margin-bottom:.8mm}
.boxes p{font-size:8.2pt;line-height:1.66;color:#3b4150}
"""


def proposal_html(key):
    d = PROPOSALS[key]
    th = d["theme"]
    cols = []
    for i, (no, name, text) in enumerate(d["cases"], 1):
        cols.append(f"""<div class="case"><h2><span>{no}</span><b class="hf">{name}</b></h2><p>{text}</p>
<div class="lab">表</div><div class="card"><img src="{key}-{i}-omote.png"></div>
<div class="lab u">裏</div><div class="card"><img src="{key}-{i}-ura.png"></div></div>""")
    notes = "".join(f"<li>{n}</li>" for n in d["notes"])
    steps, viss = [], []
    for i, (who, cls, title, text, vis) in enumerate(d["flow"], 1):
        steps.append(f'<div class="st {cls}" style="grid-column:{i}"><span class="who">{who}</span><span class="no">STEP {i:02d}</span>'
                     f'<h3 class="hf">{title}</h3><p>{text}</p></div>')
        v = d["vis"].get(vis, "")
        if v:
            viss.append(f'<div class="vis" style="grid-column:{i}">{v}</div>')
    bt, bp = d["burden"]
    boxes = "".join(f"<div><h4 class=\"hf\">{h}</h4><p>{p}</p></div>" for h, p in d["boxes"])
    head = lambda title, sub: (f'<div class="head"><div><p class="to">{d["to"]}</p><h1 class="hf">{title}<small>{sub}</small></h1></div>'
                               f'<div class="meta">{ASOF}<br>ワンヒッター株式会社</div></div>')
    return f"""<!doctype html><html lang="ja"><head><meta charset="utf-8"><title>ご紹介カード デザイン案</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&family=Barlow:wght@700&family=Shippori+Mincho+B1:wght@600&display=block" rel="stylesheet">
<style>{CSS}</style></head><body class="{th}">
<div class="sheet" id="p1">
{head("ご紹介カード　デザイン案", "3案・表と裏")}
<p class="lead">{d["lead"]}</p>
<div class="grid">{"".join(cols)}</div>
<ul class="notes">{notes}</ul>
</div>
<div class="sheet" id="p2">
{head("ご紹介の流れ", "カードを受け取った方から、施工のご報告まで")}
<div class="flow"><div class="panel"></div><b class="plab hf">{bt}</b>{"".join(steps)}{"".join(viss)}<p class="burden">{bp}</p></div>
<div class="boxes">{boxes}</div>
</div>
</body></html>"""


JS = r"""
const { chromium } = require(require('child_process').execSync('npm root -g').toString().trim() + '/playwright');
const fs = require('fs');
const [src, out, jobs, partners] = [process.argv[2], process.argv[3], JSON.parse(process.argv[4]), JSON.parse(process.argv[5])];
(async () => {
  const proxy = process.env.HTTPS_PROXY || process.env.https_proxy;
  const b = await chromium.launch(Object.assign({ args: ['--ignore-certificate-errors'] }, proxy ? { proxy: { server: proxy } } : {}));
  const probs = [];
  // ---- 各面 ----
  const pg = await b.newPage({ deviceScaleFactor: 4, viewport: { width: 400, height: 260 } });
  await pg.goto('file://' + src, { waitUntil: 'networkidle' });
  await pg.evaluate(() => document.fonts.ready); await pg.waitForTimeout(1500);
  const ids = await pg.$$eval('.page', els => els.map(e => e.id));
  for (const id of ids) await pg.locator('#' + id).screenshot({ path: out + '/' + id + '.png' });
  // 検査：安全域・7pt・孤立文字・重なり
  probs.push(...await pg.evaluate(() => {
    const MM = 96 / 25.4, MIN = 7 * 96 / 72 - 0.01, res = [];
    const isInl = e => getComputedStyle(e).display === 'inline';
    document.querySelectorAll('.page').forEach(p => {
      const pr = p.getBoundingClientRect(), L = pr.left + 7 * MM - 0.5, T = pr.top + 7 * MM - 0.5, R = pr.right - 7 * MM + 0.5, B = pr.bottom - 7 * MM + 0.5;
      const blocks = new Set(), w = document.createTreeWalker(p, NodeFilter.SHOW_TEXT); let n;
      while ((n = w.nextNode())) {
        if (!n.textContent.trim()) continue;
        const el = n.parentElement, fs = parseFloat(getComputedStyle(el).fontSize);
        if (fs < MIN) res.push(p.id + ' 7pt未満 ' + (fs * 72 / 96).toFixed(2) + 'pt「' + n.textContent.trim().slice(0, 14) + '」');
        const rg = document.createRange(); rg.selectNodeContents(n);
        for (const r of rg.getClientRects()) {
          if (r.width < 0.5) continue;
          const sh = Math.max(0, (r.height - fs) / 2);   // 行の箱から字面（全角の枠）へ
          if (r.left < L || r.top + sh < T || r.right > R || r.bottom - sh > B)
            res.push(p.id + ' 安全域外「' + n.textContent.trim().slice(0, 14) + '」');
        }
        let e = el; while (isInl(e)) e = e.parentElement; blocks.add(e);
      }
      const boxes = [];
      blocks.forEach(e => {
        const cs = getComputedStyle(e), f = parseFloat(cs.fontSize), v = cs.writingMode !== 'horizontal-tb';
        const rg = document.createRange(); rg.selectNodeContents(e);
        const rs = [...rg.getClientRects()].filter(r => r.width > 0.5 && r.height > 0.5), ls = [];
        rs.forEach(r => {
          const c = v ? r.left + r.width / 2 : r.top + r.height / 2; let l = ls.find(x => c >= x.s && c <= x.e);
          if (!l) { l = { s: v ? r.left : r.top, e: v ? r.right : r.bottom, a: 1e9, b: -1e9 }; ls.push(l); }
          l.s = Math.min(l.s, v ? r.left : r.top); l.e = Math.max(l.e, v ? r.right : r.bottom);
          l.a = Math.min(l.a, v ? r.top : r.left); l.b = Math.max(l.b, v ? r.bottom : r.right);
        });
        if (ls.length > 1) ls.forEach(l => { if ((l.b - l.a) / f < 2.3) res.push(p.id + ' 孤立文字の疑い「' + e.textContent.trim().slice(0, 18) + '」'); });
        rs.forEach(r => boxes.push({ e, r }));
      });
      for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
        const A = boxes[i], Bx = boxes[j];
        if (A.e === Bx.e || A.e.contains(Bx.e) || Bx.e.contains(A.e)) continue;
        const ox = Math.min(A.r.right, Bx.r.right) - Math.max(A.r.left, Bx.r.left), oy = Math.min(A.r.bottom, Bx.r.bottom) - Math.max(A.r.top, Bx.r.top);
        if (ox > 1.5 && oy > 1.5) res.push(p.id + ' 文字の重なり「' + A.e.textContent.trim().slice(0, 10) + '」×「' + Bx.e.textContent.trim().slice(0, 10) + '」');
      }
    });
    return [...new Set(res)];
  }));
  // 検査：QR を画像から読み取る
  const qrs = await pg.$$eval('.qr[data-url]', els => els.map(e => {
    const r = e.getBoundingClientRect(); return { id: e.closest('.page').id, url: e.dataset.url, mm: r.width * 25.4 / 96, n: +e.dataset.modules };
  }));
  await pg.addScriptTag({ url: 'https://cdn.jsdelivr.net/npm/jsqr@1.4.0/dist/jsQR.min.js' });
  for (const q of qrs) {
    const data = 'data:image/png;base64,' + fs.readFileSync(out + '/' + q.id + '.png').toString('base64');
    const got = await pg.evaluate(async d => {
      const im = new Image(); im.src = d; await im.decode(); const r = [];
      for (const s of [1, 0.25]) {
        const c = document.createElement('canvas'); c.width = Math.round(im.width * s); c.height = Math.round(im.height * s);
        const x = c.getContext('2d'); x.drawImage(im, 0, 0, c.width, c.height);
        const k = jsQR(x.getImageData(0, 0, c.width, c.height).data, c.width, c.height); r.push(k ? k.data : null);
      }
      return r;
    }, data);
    const ok = got.every(g => g === q.url);
    console.log('QR', q.id, q.url, q.mm.toFixed(1) + 'mm', q.n + 'モジュール', '1モジュール' + (q.mm / (q.n + 6)).toFixed(2) + 'mm', ok ? '読取OK' : '読取NG ' + JSON.stringify(got));
    if (!ok) probs.push(q.id + ' QRが読めない／中身が違う');
  }
  await pg.pdf({ path: out + '/cards-print.pdf', width: '97mm', height: '61mm', printBackground: true });
  const fonts = [...new Set(await pg.evaluate(() => [...document.fonts].filter(f => f.status === 'loaded').map(f => f.family)))];
  // ---- 専用ページの画面（提案書2ページ目のスマホ枠に入れる）。空き枠の取得は止める（実際の予定を写さない） ----
  for (const [key, html] of Object.entries(partners)) {
    const q = await b.newPage({ deviceScaleFactor: 3, viewport: { width: 360, height: 600 } });
    await q.route(/script\.google\.com/, r => r.abort());
    await q.goto('file://' + html, { waitUntil: 'networkidle' }); await q.evaluate(() => document.fonts.ready);
    await q.screenshot({ path: out + '/flow-' + key + '-partner.png', clip: { x: 0, y: 0, width: 360, height: 600 } });
    await q.close();
  }
  // ---- 提案書 ----
  for (const [h, p] of jobs) {
    const q = await b.newPage({ deviceScaleFactor: 1.5, viewport: { width: 1123, height: 794 } });
    await q.goto('file://' + h, { waitUntil: 'networkidle' }); await q.evaluate(() => document.fonts.ready); await q.waitForTimeout(500);
    await q.pdf({ path: p, width: '297mm', height: '210mm', printBackground: true });
    for (const sid of ['p1', 'p2']) await q.locator('#' + sid).screenshot({ path: p.replace(/\.pdf$/, '-' + sid + '.png') });
    // 提案書のはみ出し（中身が A4 の外へ）を見る
    const of = await q.evaluate(() => [...document.querySelectorAll('.sheet')].filter(s => s.scrollHeight > s.clientHeight + 1 || s.scrollWidth > s.clientWidth + 1).map(s => s.id));
    if (of.length) probs.push(p + ' はみ出し ' + of.join(','));
    await q.close();
  }
  console.log('面', ids.length, '／読めた字体', fonts.join(','));
  if (probs.length) { console.log('検査で見つかったこと:\n  ' + probs.join('\n  ')); process.exitCode = 1; }
  else console.log('検査：安全域・7pt・孤立文字・重なり・QR・提案書のはみ出し 問題なし');
  await b.close();
})();
"""


def main():
    jobs = []
    for key, d in PROPOSALS.items():
        h = OUT / f"{d['file']}.html"
        h.write_text(proposal_html(key), encoding="utf-8")
        jobs.append([str(h), str(OUT / f"{d['file']}.pdf")])
    old = OUT / "takara-design-proposal.png"   # 1ページ版のときの確認画像（-p1/-p2 に置き換え）
    for f in (old, OUT / "aoyama-design-proposal.png"):
        if f.exists():
            f.unlink()
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(JS)
    try:
        r = subprocess.run(["node", f.name, str(SRC), str(OUT), json.dumps(jobs),
                            json.dumps({k: str(v) for k, v in PARTNER_PAGES.items()})], cwd=ROOT)
    finally:
        os.unlink(f.name)
    for _, p in jobs:
        print("書きました:", p)
    sys.exit(r.returncode)


if __name__ == "__main__":
    main()
