#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""休眠先3社（エル・アップ様・キノビト様・インテリアエージェント様）への「提案の1枚」（A4・各社1枚）を作る。

【何のためか】第6回MTG 6-4 No.17 のオーナー決定（原文は docs/休眠先3社-送付物-2026-10.md §6）。
  - エル・アップ様（荒川区町屋の地場のリフォーム会社）… 顧客接点を増やし、リフォーム工事の受注機会につなげる道具としてのハウスクリーニング
  - キノビト様（江戸川区一之江の不動産売買・仲介）… 売主様・買主様との接点を増やし、追加のご提案の機会にする
  - インテリアエージェント様（原状回復・リフォームのフランチャイズ。建具は施工メニューの一部）… 同じ考え方で、
    御社の現場で手が回らない「業務用エアコンの洗浄」の協力業者として
  各社のホームページを読んで（出典は docs の §6-1）、色と書体もそれぞれのサイトに寄せた。

【決まり】金額は載せない／空室清掃は売り込まない（オーナー決定 9/14）／お客様のご相談は提携先が受けて当社に回す
  （オーナー 9/22）＝カードの連絡先は先方／当社は工事を売らない。名乗りは meigi_hyou() で3社とも「自社」（10/9）。
  専用ページの URL は載せない（まだ作っていない。返事が来てから tools/build-partner.py に足す）。

  python3 tools/build-kyumin3-proposal.py      # dist/kyumin3/ に 3社ぶんの PDF と PNG を出す

書体：Noto Sans JP・しっぽり明朝B1 が入っていれば使う（~/.fonts に置く）。無ければ IPA ゴシックで代わりに出る。
"""
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "dist" / "kyumin3"
OUT.mkdir(parents=True, exist_ok=True)

ASOF = "2026年10月"
ADDR = "ワンヒッター株式会社　〒134-0081 東京都江戸川区北葛西5-14-11 クオーディア西葛西503"
TEL = "TEL 080-8043-8259（8:00〜20:00）"
HYOUKA = "ご利用後アンケートで 98.6%（209名中206名、2023年1月〜2025年12月）のお客様が「他人に勧めたい」。Googleクチコミ ★5.0"

BASE_CSS = """
  @page { size: A4; margin: 0; }
  html, body { margin: 0; padding: 0; }
  * { box-sizing: border-box; }
  body { width: 210mm; color: var(--ink); background: #fff;
         font-family: "Noto Sans JP", "IPAPGothic", "IPA Pゴシック", sans-serif; font-size: 9.3pt; line-height: 1.55;
         -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  .page { width: 210mm; height: 296mm; padding: 0; position: relative; overflow: hidden; display: flex; flex-direction: column; }
  .body { padding: 1.5mm 14mm 0; flex: 1; display: flex; flex-direction: column; }
  p { margin: 0 0 1.6mm; }
  b { font-weight: 700; }
  h2 { font-size: 11.2pt; margin: 4.2mm 0 1.8mm; line-height: 1.3; }
  ul { margin: 0; padding-left: 4.2mm; }
  li { margin: 0 0 1mm; }
  table { border-collapse: collapse; width: 100%; }
  th, td { text-align: left; vertical-align: top; padding: 1.1mm 2mm; font-size: 8.9pt; line-height: 1.45; }
  .gets { display: grid; grid-template-columns: repeat(3, 1fr); gap: 3mm; }
  .get { border-radius: 2mm; padding: 2.2mm 3mm; }
  .get .n { font-size: 8pt; letter-spacing: .12em; }
  .get h3 { font-size: 10.4pt; margin: .4mm 0 1mm; line-height: 1.35; }
  .get p { font-size: 8.7pt; line-height: 1.5; margin: 0; }
  .flow { display: grid; grid-template-columns: 1fr 5mm 1fr 5mm 1fr 5mm 1fr; align-items: stretch; }
  .step { border-radius: 2mm; padding: 2mm 2.4mm; font-size: 8.6pt; line-height: 1.45; }
  .step .who { display: inline-block; font-size: 7.6pt; padding: .2mm 1.6mm; border-radius: 1mm; margin-bottom: 1mm; }
  .step b { display: block; font-size: 9.2pt; margin-bottom: .3mm; }
  .arrow { display: flex; align-items: center; justify-content: center; font-size: 11pt; }
  .tools { display: grid; grid-template-columns: 1fr 1fr; gap: 1.6mm 5mm; }
  .tool { padding-left: 5mm; position: relative; font-size: 8.8pt; line-height: 1.45; }
  .tool::before { content: ""; position: absolute; left: 0; top: 1.3mm; width: 2.6mm; height: 2.6mm; border-radius: .6mm; background: var(--accent); }
  .tool b { display: block; }
  .rec { margin-top: auto; border-radius: 2mm; padding: 2mm 3.2mm; font-size: 8.4pt; line-height: 1.5; }
  .rec .t { font-weight: 700; margin-right: 2mm; }
  .ask { margin: 3mm 0 0; padding: 2.2mm 3.4mm; border-radius: 2mm; font-size: 9.2pt; line-height: 1.55; }
  .foot { padding: 2.6mm 14mm 5mm; font-size: 7.8pt; display: flex; justify-content: space-between; gap: 4mm; }
  .note { font-size: 7.8pt; opacity: .8; margin-top: 1.2mm; }
"""


def flow_html(steps):
    """steps = [(who, 見出し, 本文), ...] 4つ"""
    cells = []
    for i, (who, head, text) in enumerate(steps):
        if i:
            cells.append('<div class="arrow">▶</div>')
        cells.append(f'<div class="step"><span class="who">{who}</span><b>{head}</b>{text}</div>')
    return '<div class="flow">' + "".join(cells) + "</div>"


def gets_html(gets):
    return '<div class="gets">' + "".join(
        f'<div class="get"><div class="n">POINT {i}</div><h3>{h}</h3><p>{t}</p></div>'
        for i, (h, t) in enumerate(gets, 1)) + "</div>"


def tools_html(tools):
    return '<div class="tools">' + "".join(f'<div class="tool"><b>{h}</b>{t}</div>' for h, t in tools) + "</div>"


# ---------------------------------------------------------------------------
# 1. 株式会社エル・アップ様（l-up.jp：紺 #394b73・オレンジ #ff721d・水色 #4ea0b8。ゴシック）
# ---------------------------------------------------------------------------
ELUP = {
    "file": "elup-proposal-2026-10",
    "title": "OBのお客様との接点づくりのご提案",
    "css": """
  :root { --ink: #23314f; --main: #394b73; --accent: #ff721d; --sub: #4ea0b8; --pale: #eef3f8; }
  .hero { background: var(--main); color: #fff; padding: 6.5mm 14mm 5mm; position: relative; }
  .hero::after { content: ""; position: absolute; left: 0; right: 0; bottom: 0; height: 1.6mm; background: var(--accent); }
  .hero .to { font-size: 9pt; opacity: .9; }
  .hero h1 { font-size: 17.5pt; line-height: 1.36; margin: 1.6mm 0 1.6mm; letter-spacing: .02em; }
  .hero h1 em { font-style: normal; color: #ffd2b5; }
  .hero .lead { font-size: 8.9pt; line-height: 1.6; opacity: .95; margin: 0; }
  h2 { color: var(--main); padding-left: 2.6mm; border-left: 1.6mm solid var(--accent); }
  .get { background: var(--pale); border-top: 1.2mm solid var(--sub); }
  .get .n { color: var(--sub); font-weight: 700; }
  .get h3 { color: var(--main); }
  .step { background: #fff; border: .35mm solid #c9d4e3; }
  .step .who { background: var(--main); color: #fff; }
  .step.us .who { background: var(--accent); }
  .arrow { color: var(--accent); }
  table.scene th { background: var(--main); color: #fff; font-weight: 500; }
  table.scene td { border-bottom: .3mm solid #d8dfe9; }
  table.scene td:first-child { color: var(--main); font-weight: 700; width: 38%; }
  .rec { background: var(--pale); }
  .ask { border: .5mm solid var(--accent); background: #fff7f1; }
  .foot { background: var(--main); color: #fff; }
""",
    "hero": """
  <div class="to">株式会社エル・アップ　御中</div>
  <h1>リフォームのあとも、お客様とつながる。<br><em>「お手入れ」</em>を、御社の接点にしませんか。</h1>
  <p class="lead">御社が掲げる「一度のリフォームのお付き合いが、その後の生涯のお付き合いに」。工事と工事のあいだの数年をつなぐのが、
  エアコン・追い焚き配管・換気扇などの<b>お手入れ</b>です。ご相談の窓口は御社のまま、作業は当社が御社の名前のもとで引き受けます。</p>
""",
    "sections": [
        ("御社にとっての3つの得", gets_html([
            ("工事のあとも、お客様に<br>連絡する理由ができる",
             "エアコン・追い焚き配管・換気扇は、1〜2年ごとにお手入れの時期が来ます。お引渡しのあとも「御社に頼めば済む」関係が続きます。"),
            ("お手入れの現場が、<br>次の工事の相談の入口に",
             "交換の時期が近い設備に気づいたら、お客様に「エル・アップさんにご相談を」とお伝えし、御社にもお知らせします。当社は工事をお受けしません。"),
            ("御社の手間は<br>増やさない",
             "受付は御社、日程の調整と作業は当社。御社のお客様には、御社のご紹介として伺います。"),
        ])),
        ("ご依頼の流れ", flow_html([
            ("御社", "お引渡しのとき", "御社のお名前と窓口入りのご紹介カードをお渡し。OBのお客様へのお便りに一行添えるだけでも。"),
            ("お客様", "御社にご相談", "「エアコンを洗ってほしい」など、いつもの御社の窓口へ。"),
            ("御社", "当社へ回す", "御社専用のご依頼ページで、住所・内容・日時をタップ。1分で終わります。"),
            ("当社", "伺って、ご報告", "作業のあと、御社にご報告。気づいた設備のこともあわせてお伝えします。"),
        ]).replace('<div class="step"><span class="who">当社', '<div class="step us"><span class="who">当社')),
        ("こんな場面で", """
<table class="scene">
<tr><th>場面</th><th>お客様におすすめできるお手入れ</th></tr>
<tr><td>水まわり・内装のお引渡しのとき</td><td>工事が終わったお部屋のエアコン（お掃除機能付きも）。お引渡しとあわせてご提案できます</td></tr>
<tr><td>お引渡しから1年ほど</td><td>追い焚き配管・浴室換気扇・レンジフード。「1年たちましたが、いかがですか」のご連絡に添えて</td></tr>
<tr><td>夏・冬の前</td><td>エアコンの分解洗浄。店舗・事務所の業務用（天井カセット・天吊り・床置き）も</td></tr>
<tr><td>洗濯機のにおい・汚れのご相談</td><td>ドラム式・縦型の分解洗浄（御社のご依頼で何度も伺っています）</td></tr>
</table>"""),
        ("御社にお渡しするもの（ご用意はすべて当社で）", tools_html([
            ("ご紹介カード（名刺サイズ）", "御社のお名前と窓口入り。デザイン案を3つお作りします"),
            ("お便り・チラシ用の原稿", "OBのお客様へのお便りに差し込める数行の文面"),
            ("御社専用のご依頼ページ", "会社名は入力済み。住所・内容・日時を選ぶだけ。空いている日もその場で分かります"),
            ("月1回の空き日のお知らせ", "お客様にすぐ日程をお伝えできるように"),
        ])),
    ],
    "rec": '<span class="t">これまでのお取引</span>2024年2月〜2025年7月に9件（追い焚き配管・洗濯機・エアコン・換気扇ほか）。'
           '詳しくは別紙「これまでのお取引の記録」をご覧ください。御社の施工エリア（荒川・足立・墨田・台東・北・文京）は、すべて当社の対応エリアです。',
    "ask": "<b>まずは、カードに載せる御社の窓口（お電話番号・ご担当者のお名前）をお知らせください。</b>"
           "いただいた内容でカードのデザイン案とご依頼ページをお作りし、ご確認いただいてからお使いいただけるようにします。",
}

# ---------------------------------------------------------------------------
# 2. 株式会社キノビト様（kinobito.co.jp：木の茶 #906857・金 #daaf08 / #b67b03・生成り #fee9a0。見出しは明朝）
# ---------------------------------------------------------------------------
KINOBITO = {
    "file": "kinobito-proposal-2026-10",
    "title": "ご契約のあとも続く接点のご提案",
    "css": """
  :root { --ink: #3b2f2a; --main: #906857; --accent: #b67b03; --gold: #daaf08; --cream: #fdf6e3; --pale: #f6efe9; }
  h1, h2, h3, .get h3, .step b, .serif { font-family: "Shippori Mincho B1", "IPAPGothic", serif; font-weight: 700; }
  .hero { background: var(--cream); padding: 6.5mm 14mm 5mm; border-bottom: .5mm solid var(--gold); position: relative; }
  .hero::before { content: ""; position: absolute; left: 14mm; top: 0; width: 22mm; height: 1.6mm; background: var(--main); }
  .hero .to { font-size: 9pt; color: var(--main); }
  .hero h1 { font-size: 17.5pt; line-height: 1.36; margin: 1.6mm 0 1.6mm; color: #4a3428; letter-spacing: .03em; }
  .hero h1 em { font-style: normal; color: var(--accent); }
  .hero .lead { font-size: 8.9pt; line-height: 1.6; margin: 0; }
  h2 { color: var(--main); font-size: 12pt; display: flex; align-items: center; gap: 2.4mm; }
  h2::after { content: ""; flex: 1; height: .3mm; background: #e2d3c7; }
  .get { background: var(--pale); border: .3mm solid #e6d8cc; }
  .get .n { color: var(--accent); font-weight: 700; }
  .get h3 { color: #4a3428; }
  .step { background: #fff; border: .35mm solid #e2d3c7; }
  .step .who { background: var(--main); color: #fff; }
  .step.us .who { background: var(--accent); }
  .arrow { color: var(--gold); }
  table.scene th { background: var(--main); color: #fff; font-weight: 500; }
  table.scene td { border-bottom: .3mm solid #eadfd5; }
  table.scene td:first-child { color: var(--main); font-weight: 700; width: 34%; }
  .rec { background: var(--cream); border-left: 1.2mm solid var(--gold); }
  .ask { border: .4mm solid var(--main); background: #fff; }
  .foot { background: #4a3428; color: #f6efe9; }
""",
    "hero": """
  <div class="to">株式会社キノビト　御中</div>
  <h1>ご契約のあとも、お客様と<br>つながりつづける<em>「お手入れ」</em>のご提案</h1>
  <p class="lead">御社が見つけた「暖かな家」を、住みはじめから気持ちよく。売主様・買主様のお住まいのエアコンや水まわりのお手入れを、
  御社からのご提案としてお客様に届けませんか。ご相談の窓口は御社のまま、作業は同じ江戸川区（北葛西）の当社が引き受けます。</p>
""",
    "sections": [
        ("御社にとっての3つの得", gets_html([
            ("売主様に<br>「内覧の前のひと手間」",
             "売却のご相談のあと、エアコン・浴室・キッチンを整えるご提案ができます。お住まいのままでも伺えます。"),
            ("買主様に<br>「ご入居前のお手入れ」",
             "お引渡しからご入居までに、エアコン・換気扇・浴室を。ご契約のあとも、お住まいのことは御社に、という関係が続きます。"),
            ("御社の追加のご提案に、<br>手間はかけない",
             "受付は御社、日程の調整と作業は当社。お客様には御社のご紹介として伺い、作業のあとは御社にご報告します。"),
        ])),
        ("ご依頼の流れ", flow_html([
            ("御社", "ご契約・ご相談のとき", "御社のお名前と窓口入りのご紹介カードを、書類と一緒にお渡し。"),
            ("お客様", "御社にご相談", "「入居前にエアコンを」など、いつもの御社の窓口へ。"),
            ("御社", "当社へ回す", "御社専用のご依頼ページで、住所・内容・日時をタップ。1分で終わります。"),
            ("当社", "伺って、ご報告", "江戸川区・市川市はすぐ近く。作業のあと、御社にご報告します。"),
        ]).replace('<div class="step"><span class="who">当社', '<div class="step us"><span class="who">当社')),
        ("こんな場面で", """
<table class="scene">
<tr><th>場面</th><th>お客様におすすめできるお手入れ</th></tr>
<tr><td>売却のご相談・査定のあと</td><td>内覧の前に、浴室・キッチン・エアコン。においと水あかが気になる場所から</td></tr>
<tr><td>ご契約からお引渡しまで</td><td>買主様のご入居前に、エアコン・換気扇・浴室。家具が入る前がいちばん作業しやすい時期です</td></tr>
<tr><td>ご入居から1年ほど</td><td>エアコン・洗濯機・追い焚き配管。「お住まいはいかがですか」のご連絡に添えて</td></tr>
</table>"""),
        ("御社にお渡しするもの（ご用意はすべて当社で）", tools_html([
            ("ご紹介カード（名刺サイズ）", "御社のお名前と窓口入り。御社のホームページの色合いでお作りします"),
            ("ご契約のお客様へのご案内文", "メール・LINEにそのまま使える数行の文面"),
            ("御社専用のご依頼ページ", "会社名は入力済み。住所・内容・日時を選ぶだけ。空いている日もその場で分かります"),
            ("月1回の空き日のお知らせ", "お客様にすぐ日程をお伝えできるように"),
        ])),
    ],
    "rec": '<span class="t">これまでのお取引</span>2024年6月から2025年2月まで、3回ご依頼をいただきました（江戸川区ほか）。ありがとうございました。',
    "ask": "<b>まずは、カードに載せる御社の窓口（お電話番号・ご担当者のお名前）をお知らせください。</b>"
           "いただいた内容でカードとご依頼ページをお作りし、ご確認いただいてからお使いいただけるようにします。",
}

# ---------------------------------------------------------------------------
# 3. インテリアエージェント様（rv21.jp：黒 #32373c / #333・赤 #d40707 / #e5232d。太いゴシック）
# ---------------------------------------------------------------------------
INTERIOR = {
    "file": "interior-agent-proposal-2026-10",
    "title": "業務用エアコン洗浄の協力のご提案",
    "css": """
  :root { --ink: #262a2e; --main: #32373c; --accent: #d40707; --pale: #f4f4f4; }
  .hero { background: var(--main); color: #fff; padding: 6.5mm 14mm 5mm; position: relative; }
  .hero::before { content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 4mm; background: var(--accent); }
  .hero .to { font-size: 9pt; opacity: .85; }
  .hero h1 { font-size: 17.5pt; line-height: 1.36; margin: 1.6mm 0 1.6mm; font-weight: 900; letter-spacing: .01em; }
  .hero h1 em { font-style: normal; color: #ff5a5a; }
  .hero .lead { font-size: 8.9pt; line-height: 1.6; opacity: .95; margin: 0; }
  h2 { color: var(--main); font-weight: 900; padding: .6mm 0 .6mm 3mm; border-left: 1.8mm solid var(--accent); }
  .get { background: var(--pale); border-top: 1.2mm solid var(--accent); }
  .get .n { color: var(--accent); font-weight: 900; }
  .get h3 { color: var(--main); font-weight: 900; }
  .step { background: #fff; border: .35mm solid #cfcfcf; }
  .step .who { background: var(--main); color: #fff; }
  .step.us .who { background: var(--accent); }
  .arrow { color: var(--accent); }
  table.scene th { background: var(--main); color: #fff; font-weight: 500; }
  table.scene td { border-bottom: .3mm solid #ddd; }
  table.scene td:first-child { font-weight: 700; width: 30%; }
  .rec { background: var(--pale); border-left: 1.2mm solid var(--accent); }
  .ask { border: .5mm solid var(--accent); background: #fff5f5; }
  .foot { background: var(--main); color: #fff; }
""",
    "hero": """
  <div class="to">インテリアエージェント　御中</div>
  <h1>業務用エアコンの洗浄は、<br><em>1台から</em>当社が引き受けます。</h1>
  <p class="lead">昨年9月の港区高輪、今年6月の南麻布では、天井カセット型エアコンのご依頼をいただきありがとうございました。
  原状回復・リフォームの現場で「エアコンの洗浄だけ手が回らない」「業務用の台数が多い」ときの協力業者として、引き続きお使いください。</p>
""",
    "sections": [
        ("御社にとっての3つの得", gets_html([
            ("オフィスの原状回復で、<br>エアコン洗浄まで受けられる",
             "天井カセット・天吊り・床置きを、1台から大きな現場まで（1現場で天井カセット51台の実績）。御社のご提案の幅が広がります。"),
            ("忙しい時期の<br>受け皿に",
             "退去や移転が重なる時期も、エアコン洗浄だけ当社に。月1回、当社の空き日をお知らせします。"),
            ("御社の名前で、<br>御社のお客様へ",
             "管理会社様・オーナー様・企業のご担当者様には、御社の協力業者として伺います。作業のあとは御社にご報告します。"),
        ])),
        ("ご依頼の流れ", flow_html([
            ("御社", "現場が決まったら", "御社専用のご依頼ページで、現場の住所・機種・台数・日時を選ぶだけ。"),
            ("当社", "空き日で仮押さえ", "選んだ台数に合う空き日がその場で出ます。そのまま仮押さえ。"),
            ("当社", "現場で作業", "天井カセット・天吊り・床置き・壁掛けを分解洗浄。"),
            ("当社", "御社へご報告", "作業のあと、御社の現場ご担当者にご報告します。"),
        ]).replace('<div class="step"><span class="who">当社', '<div class="step us"><span class="who">当社')),
        ("お受けできる機種", """
<table class="scene">
<tr><th>機種</th><th>内容</th></tr>
<tr><td>天井カセット型</td><td>2方向・4方向など。パネルを外しての分解洗浄を1台から</td></tr>
<tr><td>天吊り型・床置き型</td><td>店舗・事務所の業務用。複数台・大きな現場もご相談ください</td></tr>
<tr><td>壁掛け型</td><td>ノーマル・お掃除機能付き。在宅のリフォーム現場でも</td></tr>
<tr><td>あわせて</td><td>室外機の洗浄、フィルター清掃のみのご依頼も承ります</td></tr>
</table>"""),
        ("御社にお渡しするもの（ご用意はすべて当社で）", tools_html([
            ("御社専用のご依頼ページ", "会社名は入力済み。本部・各支店のどちらからでもお使いいただけます"),
            ("月1回の空き日のお知らせ", "現場の日程を組むときに"),
            ("お客様向けの作業説明（1枚）", "御社のお見積りに添えられる、機種ごとの作業内容の説明"),
            ("作業のご報告", "現場ごとに、御社のご担当者へ"),
        ])),
    ],
    "rec": '<span class="t">これまでのお取引</span>2025年9月 港区（高輪）天井カセット型（2方向）1台／2026年6月 港区（南麻布）天井カセット型 1台ほか。ありがとうございました。',
    "ask": "<b>ご依頼の窓口になる方（ご担当の支店・お名前・メールアドレス）をお知らせください。</b>"
           "御社専用のご依頼ページをお作りし、ご確認いただいてからお使いいただけるようにします。",
}


def build(c):
    secs = "".join(f"<h2>{h}</h2>{body}" for h, body in c["sections"])
    html = f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<title>{c['title']}</title>
<style>{BASE_CSS}{c['css']}</style></head>
<body><div class="page">
<div class="hero">{c['hero']}</div>
<div class="body">
{secs}
<div class="ask">{c['ask']}</div>
<div style="height:2.4mm"></div>
<div class="rec">{c['rec']}<div class="note">{HYOUKA}</div></div>
</div>
<div class="foot"><span>{ADDR}</span><span>{TEL}　{ASOF}</span></div>
</div></body></html>
"""
    h = OUT / f"{c['file']}.html"
    h.write_text(html, encoding="utf-8")
    return h


def find_chrome():
    for d in sorted(pathlib.Path("/opt/pw-browsers").glob("chromium-*")):
        hits = list(d.glob("**/chrome"))
        if hits:
            return str(hits[0])
    for c in ("/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome"):
        if pathlib.Path(c).exists():
            return c
    raise SystemExit("Chromium が見つかりません")


def main():
    chrome = find_chrome()
    base = [chrome, "--headless=new", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer"]
    for c in (ELUP, KINOBITO, INTERIOR):
        h = build(c)
        pdf, png = h.with_suffix(".pdf"), h.with_suffix(".png")
        subprocess.run(base + [f"--print-to-pdf={pdf}", str(h)], check=True, capture_output=True)
        subprocess.run(base + ["--window-size=794,1250", "--hide-scrollbars", "--force-device-scale-factor=2",
                               "--screenshot=" + str(png), str(h)], check=True, capture_output=True)
        pages = pdf.read_bytes().count(b"/Type /Page") - pdf.read_bytes().count(b"/Type /Pages")
        print(f"書きました: {pdf.name}（{pages}ページ） / {png.name}")
        if pages != 1:
            print("  ⚠ 1枚に収まっていません")


if __name__ == "__main__":
    main()
