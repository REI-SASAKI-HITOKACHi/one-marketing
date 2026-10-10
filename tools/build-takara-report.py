#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""タカラサービスさま向け 実績レポート（A4・1枚）と、紹介カードの文面見本を HTML → PDF/PNG で作る。

【何のためのレポートか】（MTG 2026-09-04 #19 オーナー決定）
  該社の担当者に「①クリーニングニーズがある ②一定の顧客グリップ要素になる
  ③ONE-HITTER が有用な発注先である」と認識してもらい、東京での洗浄の発注を増やす。

【連携の流れ（オーナー 2026-09-22）】
  タカラサービスがお客様から相談を受ける → 当社へ照会する。当社が直接受ける流れにしない。
  紹介カード・案内ページは「洗浄も対応可能」をお客様に伝えるための道具。相談先はタカラサービス。

【使い方】
  python3 tools/build-takara-report.py   # dist/takara/ に レポート PDF/PNG と カード見本 PNG を出す

数字・氏名を直すときは JOBS を直してから作り直す。台帳の値は手で書き換えない。
"""
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "dist" / "takara"
OUT.mkdir(parents=True, exist_ok=True)

ASOF = "2026年10月10日"

# 台帳（月次タブ）と和真さんのカレンダー（予定の場所・題名）を突き合わせた14件（2026-10-09）。金額は出さない。
# 「貴社からのご依頼」だった行は、カレンダーで現場を特定して区を入れた（オーナー 10/9「住所（○○区）程度でも載せたい」）。
#  - 2023/09/29 墨田区菊川（台帳の住所）・天カセ2台（カレンダー「天カセ2台/タカラサービス様」）
#  - 2024/09/02・09/13 北区田端のフィットネスジム（カレンダー「タカラサービス 田端店」「フィットネスジム田端店」）
#  - 2026/02/03 の2行は江戸前ハーブ様（カレンダー「江戸前ハーブ 天吊1.ノーマル4.縦型2.」）
#  - 2025/08/20 大森本町の店舗はカレンダー題名「タカラルーム4.」＝タカラ経由と判断して入れた
#  - スタジオファイン様は場所の記録が無いので区を入れない
JOBS = [
    ("2023年9月",  "墨田区", "店舗",                     "業務用エアコン（天井カセット）2台"),
    ("2023年11月", "葛飾区", "24GYM 様",                 "業務用エアコン（ドレンパン清掃）"),
    ("2024年3月",  "大田区", "江戸前ハーブ 様",           "お掃除機能付きエアコン（複数台）"),
    ("2024年4月",  "大田区", "江戸前ハーブ 様",           "エアコン 1台"),
    ("2024年5月",  "目黒区", "株式会社サンリバー 様",     "業務用エアコン（天井カセット4方向）"),
    ("2024年9月",  "北区",   "フィットネスジム 様（田端）", "業務用エアコン（ドレンパン洗浄 2台）"),
    ("2024年9月",  "北区",   "フィットネスジム 様（田端）", "業務用エアコン"),
    ("2025年2月",  "大田区", "江戸前ハーブ 様",           "エアコン 4台"),
    ("2025年7月",  "大田区", "江戸前ハーブ 様",           "置き型の業務用エアコン 2台"),
    ("2025年8月",  "大田区", "江戸前ハーブ 様（大森本町の店舗）", "エアコン 4台"),
    ("2026年2月",  "大田区", "江戸前ハーブ 様",           "床置き型エアコン 2台"),
    ("2026年2月",  "大田区", "江戸前ハーブ 様",           "壁掛け 4台＋天吊り 1台"),
    ("2026年7月",  "—",      "スタジオファイン 様",       "天井カセット 2台"),
    ("2026年8月",  "大田区", "江戸前ハーブ 様（大森本町の店舗）", "壁掛け 4台＋天吊り 1台"),
]
NENBETSU = "2023年 2件／2024年 5件／2025年 3件／2026年 4件（9月まで）"
PARTNER_URL = "https://lp.onehitter.jp/partner/takara-7q2m/"

rows = "".join(f"<tr><td>{d}</td><td>{k}</td><td>{c}</td><td>{m}</td></tr>" for d, k, c, m in JOBS)

CSS = """
  html, body { margin: 0; padding: 0; }
  body { font-family: "IPAPGothic", "IPA Pゴシック", "Noto Sans CJK JP", sans-serif;
         color: #1a1a1a; font-size: 9.3pt; line-height: 1.38; }
  h1 { font-size: 16pt; margin: 0 0 2mm; letter-spacing: .02em; }
  .meta { font-size: 9pt; color: #555; margin: 0 0 4mm; display: flex; justify-content: space-between; }
  h2 { font-size: 11.2pt; margin: 2.6mm 0 1.2mm; padding-left: 2.2mm; border-left: 3.5pt solid #1f5f8b; }
  p { margin: 0 0 1.6mm; }
  table { border-collapse: collapse; width: 100%; margin: 1mm 0 1.5mm; }
  th, td { border-bottom: 1px solid #d9d9d9; padding: .3mm 1.6mm; text-align: left; font-size: 8.5pt; }
  th { background: #eef3f7; font-weight: normal; color: #333; }
  ul { margin: 0 0 1.5mm; padding-left: 4.5mm; }
  li { margin: 0 0 .6mm; }
  .box { border: 1.5px solid #1f5f8b; border-radius: 2mm; padding: 2.6mm 3.8mm; margin-top: 3mm; background: #f7fafc; }
  .box h2 { margin-top: 0; border: none; padding: 0; font-size: 12.5pt; }
  .foot { margin-top: 4.5mm; padding-top: 2mm; border-top: 1px solid #bbb; font-size: 9pt; color: #333;
          display: flex; justify-content: space-between; }
"""

REPORT = f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<title>貴社からご依頼いただいた洗浄のご報告</title>
<style>@page {{ size: A4; margin: 10mm 13mm 8mm 13mm; }}{CSS}</style></head>
<body>
<h1>貴社からご依頼いただいた洗浄のご報告　2023年9月〜2026年9月</h1>
<div class="meta"><span>株式会社タカラサービス　深堀 様</span><span>ワンヒッター株式会社　{ASOF}</span></div>

<p>いつも洗浄のご依頼をいただき、ありがとうございます。2023年9月から、貴社のお客様の現場に{len(JOBS)}件伺いました。3年分を1枚にまとめました。</p>

<h2>1　貴社からのご依頼（{len(JOBS)}件）</h2>
<table>
<tr><th>ご依頼の月</th><th>場所</th><th>現場（お客様）</th><th>内容</th></tr>
{rows}
</table>
<p>年ごとの件数：{NENBETSU}。<b>今年は9月までで、昨年を上回っています。</b>墨田・葛飾・目黒・北・大田の各区で伺いました。</p>
<p>貴社のご依頼で、江戸前ハーブ様には2024年から毎年伺い、今年8月で7回目になりました。お掃除機能付きエアコンから始まり、大森本町の店舗、業務用の置き型、天吊りへと広がっています。</p>

<h2>2　お客様の声と、当社の評価</h2>
<ul>
<li>サンリバー様は365日営業の店舗で、「冷房にすると酸っぱい匂いがする」とのご相談でした。内部を開けるとカビが広がっていたため、その場でご説明し、分解洗浄しました。</li>
<li>ご利用後アンケートで、98.6%（209名中206名、2023年1月〜2025年12月）のお客様に「他人に勧めたい」とお答えいただいています。Googleクチコミは★5.0です。</li>
</ul>

<h2>3　こんなご依頼も承ります</h2>
<ul>
<li><b>大規模でも承ります。</b>1現場で天井カセット51台＋換気設備17台（2026年8月）、天吊り12台（2025年3月）の実績があります。</li>
<li><b>フィルターの簡易清掃だけでも承ります。</b>上の天吊り12台は、8台が分解洗浄、4台はフィルター清掃のみでした。</li>
<li>製造から10年を超えた機器は、洗浄前に貴社へご相談します。入れ替えのご検討につながる情報は、そのままお伝えします。</li>
</ul>

<div class="box">
<h2>「洗浄も対応できます」を、貴社のお客様にお伝えいただくために</h2>
<p>ご相談の窓口は、これまでどおり貴社です。</p>
<ul>
<li><b>ご紹介カード</b>：訪問時にお渡しいただく名刺サイズのカード。当社の名前は載せず、貴社のサービスとしてお渡しいただけます。デザイン案3つを別紙でお送りします。</li>
<li><b>貴社専用のご依頼フォーム</b>：{PARTNER_URL}　台数を入れると、貴社向けの料金と作業できる日がその場で出ます。見積依頼・現調依頼のどちらも承ります。</li>
</ul>
</div>

<div class="foot">
<span>ワンヒッター株式会社　〒134-0081 東京都江戸川区北葛西5-14-11 クオーディア西葛西503</span>
<span>TEL 080-8043-8259（8:00〜20:00）</span>
</div>
</body></html>
"""

# ---- 紹介カード（タカラサービス版）の文面見本。オーナーのデザイン（Drive「紹介カード2026」）に流し込む ----
CARD = """<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><title>ご紹介カード 文面見本</title>
<style>
  body { margin: 0; padding: 24px; background: #ddd; font-family: "IPAPGothic", "IPA Pゴシック", sans-serif; color: #10233a; }
  .card { width: 91mm; height: 55mm; background: #fff; border: 1px solid #999; border-radius: 3mm; padding: 5mm 6mm; box-sizing: border-box;
          margin: 0 0 8mm; position: relative; }
  .tag { position: absolute; top: -7mm; left: 0; font-size: 9pt; color: #444; }
  h1 { font-size: 13pt; margin: 0 0 1mm; color: #0D3B5C; }
  .sub { font-size: 7.6pt; color: #333; margin: 0 0 2mm; line-height: 1.45; }
  ul { margin: 0 0 2mm; padding-left: 3.5mm; font-size: 7.8pt; line-height: 1.5; }
  li { margin: 0; }
  .menu { font-size: 7.6pt; color: #0D3B5C; border-top: 1px dotted #999; padding-top: 1.5mm; }
  .to { background: #eef3f7; border: 1px solid #b4c5d0; border-radius: 2mm; padding: 2mm 3mm; font-size: 8pt; line-height: 1.5; margin-top: 1.5mm; }
  .to b { color: #0D3B5C; font-size: 9.5pt; }
  .var { color: #b72c0a; }
  .foot { font-size: 6.8pt; color: #555; margin-top: 1.5mm; }
</style></head>
<body>
<div class="card"><div class="tag">表（案）</div>
  <h1>エアコンの洗浄も、お任せください。</h1>
  <p class="sub">設置から年数がたつと、エアコンの中にはカビとホコリがたまります。弊社の提携先のプロが、分解して洗います。</p>
  <ul>
    <li>匂いが消え、お客様と従業員の方が吸う空気がきれいになります</li>
    <li>熱交換器の目詰まりが取れ、本来の効きに戻ります</li>
    <li>汚れによる負荷と水漏れを防ぎ、機械が長持ちします</li>
    <li>中を開けるので点検にもなり、不具合に早く気づけます</li>
  </ul>
  <div class="menu">天井カセット／天吊り／床置き／壁掛け　フィルター清掃だけでも、数十台でも</div>
</div>

<div class="card"><div class="tag">裏（案）</div>
  <h1>洗浄のご相談は、こちらへ</h1>
  <p class="sub">設置をご担当した窓口が、そのまま承ります。「洗浄の案内カードを見た」とお伝えください。</p>
  <div class="to">
    <b class="var">株式会社タカラサービス</b>（可変：提携先名）<br>
    TEL <b class="var">0120-655-080</b>（可変）　メール <span class="var">info@takara-co.jp</span>（可変）<br>
    ご担当 <span class="var">〇〇</span>（可変）
  </div>
  <div class="foot">目安：飲食店・365日営業は年1回、オフィスは1〜2年に1回。製造10年超の機器は洗浄前にご相談します。<br>
  施工：ワンヒッター株式会社（東京都江戸川区）　東京・千葉・神奈川</div>
</div>
</body></html>
"""

report_html = OUT / "takara-report-2026-10.html"
report_pdf = OUT / "takara-report-2026-10.pdf"
report_png = OUT / "takara-report-2026-10.png"
card_html = OUT / "takara-card-moji.html"
card_png = OUT / "takara-card-moji.png"
report_html.write_text(REPORT, encoding="utf-8")
card_html.write_text(CARD, encoding="utf-8")

chrome = None
for d in sorted(pathlib.Path("/opt/pw-browsers").glob("chromium-*")):
    hits = list(d.glob("**/chrome"))
    if hits:
        chrome = str(hits[0]); break
if not chrome:
    for c in ("/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome"):
        if pathlib.Path(c).exists():
            chrome = c; break
if not chrome:
    raise SystemExit("Chromium が見つかりません")

base = [chrome, "--headless=new", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer"]
subprocess.run(base + [f"--print-to-pdf={report_pdf}", str(report_html)], check=True, capture_output=True)
subprocess.run(base + ["--window-size=1240,1754", "--screenshot=" + str(report_png), str(report_html)],
               check=True, capture_output=True)
subprocess.run(base + ["--window-size=480,560", "--screenshot=" + str(card_png), str(card_html)],
               check=True, capture_output=True)
print("書きました:", report_pdf, "/", report_png, "/", card_png)
