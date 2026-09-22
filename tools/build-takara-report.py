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

ASOF = "2026年9月22日"

# 台帳の氏名・実施メニュー・備考から（docs/タカラサービス-実績レポート-2026-09.md §3.1）。金額は出さない。
# ★施工先が台帳で確定していない行は、和真さんの回答（9/22 LINE）で埋める。埋まるまで「（確認中）」。
JOBS = [
    ("江戸前ハーブ 様（大田区）", "2024年3月", "エアコン（お掃除機能付き）"),
    ("江戸前ハーブ 様", "2024年4月", "エアコン 1台（再依頼）"),
    ("江戸前ハーブ 様", "2025年2月", "エアコン 4台（再依頼）"),
    ("江戸前ハーブ 様", "2025年7月", "置き型業務用エアコン 2台（再依頼）"),
    ("江戸前ハーブ 様", "2026年8月", "壁掛け4台＋天吊り1台（再依頼）"),
    ("株式会社サンリバー 様（目黒区・店舗）", "2024年5月", "業務用エアコン"),
    ("スタジオファイン 様", "2026年7月", "天井カセット"),
    ("24GYM 様", "2023年11月", "（確認中）"),
    ("（確認中）墨田区", "2023年9月", "業務用エアコン 複数台"),
    ("（確認中）", "2024年9月", "業務用エアコン／ドレンパン洗浄 2台"),
    ("（確認中）", "2026年2月", "床置き型 2台、壁掛け4台＋天吊り1台"),
]

rows = "".join(f"<tr><td>{c}</td><td>{d}</td><td>{m}</td></tr>" for c, d, m in JOBS)

CSS = """
  html, body { margin: 0; padding: 0; }
  body { font-family: "IPAPGothic", "IPA Pゴシック", "Noto Sans CJK JP", sans-serif;
         color: #1a1a1a; font-size: 10.1pt; line-height: 1.5; }
  h1 { font-size: 16pt; margin: 0 0 2mm; letter-spacing: .02em; }
  .meta { font-size: 9pt; color: #555; margin: 0 0 4mm; display: flex; justify-content: space-between; }
  h2 { font-size: 11.2pt; margin: 3.2mm 0 1.4mm; padding-left: 2.2mm; border-left: 3.5pt solid #1f5f8b; }
  p { margin: 0 0 1.6mm; }
  table { border-collapse: collapse; width: 100%; margin: 1mm 0 1.5mm; }
  th, td { border-bottom: 1px solid #d9d9d9; padding: .8mm 2mm; text-align: left; font-size: 9.4pt; }
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
<title>ご紹介いただいたお客様のご報告</title>
<style>@page {{ size: A4; margin: 12mm 14mm 10mm 14mm; }}{CSS}</style></head>
<body>
<h1>ご紹介いただいたお客様のご報告　2023年9月〜2026年8月</h1>
<div class="meta"><span>株式会社タカラサービス　ご担当者さま</span><span>ワンヒッター株式会社　{ASOF}</span></div>

<p>いつもご紹介をいただき、ありがとうございます。御社からご紹介いただいたお客様の3年分をまとめました。</p>

<h2>1　ご紹介いただいたお客様（13件）</h2>
<table>
<tr><th>お客様</th><th>ご依頼</th><th>内容</th></tr>
{rows}
</table>
<p><b>江戸前ハーブ様からは、2024年から毎年ご依頼をいただき、今年で5回目です。</b>初回はエアコン1台の追加から始まり、業務用の置き型、天吊りへと広がりました。</p>

<h2>2　お客様のご評価</h2>
<ul>
<li>サンリバー様は365日営業の店舗で、「冷房にすると酸っぱい匂いがする」とのご相談でした。内部を開けるとカビが広がっており、洗浄で解消しました。</li>
<li>Googleクチコミは 5.0（23件、2026年9月時点）です。</li>
<li>再依頼が続いているのは、仕上がりにご満足いただけている証拠と受け止めています。</li>
</ul>

<h2>3　こんなご依頼も承ります</h2>
<ul>
<li><b>大規模でも承ります。</b>1現場で天井カセット51台＋換気設備17台（2026年8月）、天吊り12台（2025年3月）の実績があります。</li>
<li><b>フィルターの簡易清掃だけでも承ります。</b>上の天吊り12台は、8台が分解洗浄、4台はフィルター清掃のみでした。</li>
<li>製造から10年を超えた機器は、洗浄前に御社へご相談します。入れ替えのご検討につながる情報は、そのままお伝えします。</li>
</ul>

<div class="box">
<h2>「洗浄も対応できます」を、御社のお客様にお伝えいただくために</h2>
<p>ご相談の窓口は、これまでどおり御社です。お客様への案内にお使いいただけるものを2つご用意しました。</p>
<ul>
<li><b>ご紹介カード（同封）</b>：訪問時にお渡しいただく名刺サイズのカード。洗浄のメリットと、ご相談先として御社の連絡先を載せています。</li>
<li><b>ご案内ページ（下のURL）</b>：メールでご案内いただくときにお使いください。汚れの写真、洗浄で変わること、目安の頻度、ご相談からの流れをまとめています。ご相談先は御社の連絡先にしています。</li>
</ul>
<p>案内ページ：https://lp.onehitter.jp/takara/　（御社の連絡先の表記は、ご確認のうえ差し替えます）</p>
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
  <p class="sub">設置から2年、エアコンの中はカビとホコリでいっぱいです。弊社の提携先のプロが、分解して洗います。</p>
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

report_html = OUT / "takara-report-2026-09.html"
report_pdf = OUT / "takara-report-2026-09.pdf"
report_png = OUT / "takara-report-2026-09.png"
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
