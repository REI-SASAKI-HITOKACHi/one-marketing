#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""青山リアルティ・アドバイザーズさま向け「取引の記録」（A4・1枚）を HTML → PDF/PNG で作る。

【何のためか】docs/提携先-休眠先を起こす3パターン.md のパターン①。
  最後の依頼（2025年9月 床置き型エアコン5台）から1年あまり止まっている提携先に、
  これまでの作業を1枚で見せて、エアコン（業務用・床置き・天カセ）の依頼を再開していただく。
  空室清掃は売り込まない（オーナー決定 2026-09-14「超薄利で下手したら逆鞘」）。記録として載せるだけ。

【根拠】2023〜2025年の売上スプシの月次タブ（N月_売上/顧客）の「青山リアルティ」行（2026-10-08 読み取りのみ）。
  名乗りは meigi_hyou() で全行「自社」を確認済み（2026-10-08）。金額は載せない。

  python3 tools/build-aoyama-record.py   # dist/aoyama/ に PDF と PNG を出す
"""
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "dist" / "aoyama"
OUT.mkdir(parents=True, exist_ok=True)

ASOF = "2026年10月9日"

# 台帳（月次タブ）と和真さんのカレンダー（予定の場所・説明）を突き合わせた7件（2026-10-09）。
#  - 2024/06/12 空室：5/31 の現調が中野区松が丘 → 6/10 鍵受け取り → 6/12 清掃 の流れから中野区
#  - 2024/11/19：11/13 の現調「自社ビルの屋上ドレン詰まり・港区南青山」→ 11/19「高圧洗浄」
#  - 2024/11/29：サニーデイ恵比寿の店舗（荒木様からの依頼として）
#  - 2025/09/19：港区麻布十番の店舗（和美躰様）
# 2023/06/07 の駐車場料金の行、2025年4月タブの金額空欄の行（千駄ヶ谷空室の控え）は作業の重複なので数えない。
JOBS = [
    ("2023年6月",  "渋谷区（神宮前）",   "空室クリーニング（お掃除機能付きエアコン 2台を含む）"),
    ("2023年6月",  "渋谷区（恵比寿西）", "空室クリーニング（エアコン分解洗浄・浴室・バルコニー）"),
    ("2024年6月",  "中野区",             "空室クリーニング"),
    ("2024年11月", "港区（南青山）",     "御社ビル屋上の排水口（ドレン）の高圧洗浄"),
    ("2024年11月", "渋谷区（恵比寿）",   "店舗のエアコン 2台＋室外機 2台"),
    ("2025年7月",  "渋谷区（千駄ヶ谷）", "空室クリーニング"),
    ("2025年9月",  "港区（麻布十番）",   "店舗の床置き型エアコン 5台"),
]
PARTNER_URL = "https://lp.onehitter.jp/partner/aoyama-k4x9/"

rows = "".join(f"<tr><td>{d}</td><td>{a}</td><td>{m}</td></tr>" for d, a, m in JOBS)

CSS = """
  html, body { margin: 0; padding: 0; }
  body { font-family: "IPAPGothic", "IPA Pゴシック", "Noto Sans CJK JP", sans-serif;
         color: #1a1a1a; font-size: 10.2pt; line-height: 1.55; }
  h1 { font-size: 16pt; margin: 0 0 2mm; letter-spacing: .02em; }
  .meta { font-size: 9pt; color: #555; margin: 0 0 5mm; display: flex; justify-content: space-between; }
  h2 { font-size: 11.4pt; margin: 4.5mm 0 1.6mm; padding-left: 2.2mm; border-left: 3.5pt solid #1f5f8b; }
  p { margin: 0 0 1.8mm; }
  table { border-collapse: collapse; width: 100%; margin: 1mm 0 1.5mm; }
  th, td { border-bottom: 1px solid #d9d9d9; padding: 1mm 2mm; text-align: left; font-size: 9.6pt; }
  th { background: #eef3f7; font-weight: normal; color: #333; }
  ul { margin: 0 0 1.5mm; padding-left: 4.5mm; }
  li { margin: 0 0 .8mm; }
  .box { border: 1.5px solid #1f5f8b; border-radius: 2mm; padding: 3mm 4mm; margin-top: 4mm; background: #f7fafc; }
  .box h2 { margin-top: 0; border: none; padding: 0; font-size: 12.5pt; }
  .foot { margin-top: 6mm; padding-top: 2mm; border-top: 1px solid #bbb; font-size: 9pt; color: #333;
          display: flex; justify-content: space-between; }
"""

HTML = f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<title>これまでのお取引の記録</title>
<style>@page {{ size: A4; margin: 14mm 15mm 12mm 15mm; }}{CSS}</style></head>
<body>
<h1>これまでのお取引の記録　2023年6月〜2025年9月</h1>
<div class="meta"><span>青山リアルティ・アドバイザーズ株式会社　荒木 様</span><span>ワンヒッター株式会社　{ASOF}</span></div>

<p>これまで多くのご依頼をいただき、ありがとうございました。御社の物件で伺った作業を1枚にまとめました。</p>

<h2>1　御社からのご依頼</h2>
<table>
<tr><th>ご依頼の月</th><th>場所</th><th>内容</th></tr>
{rows}
</table>
<p>最後にいただいたのは、2025年9月の床置き型エアコン 5台の洗浄でした。</p>

<h2>2　当社の今</h2>
<ul>
<li>ご利用後アンケートで、98.6%（209名中206名、2023年1月〜2025年12月）のお客様に「満足」とお答えいただいています。</li>
<li>Googleクチコミは★5.0です。</li>
<li>1現場で天井カセット51台＋換気設備17台（2026年8月）の洗浄を行うなど、業務用の大きな現場にも対応しています。</li>
</ul>

<div class="box">
<h2>こんなご依頼を承ります</h2>
<ul>
<li><b>業務用エアコン</b>：天井カセット・天吊り・床置き型。台数が多くても承ります。</li>
<li><b>排水口・ドレンの高圧洗浄</b>：屋上や共用部の詰まりも承ります。</li>
<li><b>フィルター清掃だけ</b>でも承ります。分解洗浄の台と組み合わせることもできます。</li>
<li>製造から10年を超えた機器は、洗浄の前にご相談します。</li>
</ul>
<p>物件のご入居前や、テナント様からのご相談などで必要なときは、お気軽にご連絡ください。<br><b>御社専用のご依頼ページ</b>：{PARTNER_URL}　（台数を選ぶとその場で料金と空いている日時が出て、そのまま仮押さえできます）</p>
</div>

<div class="foot">
<span>ワンヒッター株式会社　〒134-0081 東京都江戸川区北葛西5-14-11 クオーディア西葛西503</span>
<span>TEL 080-8043-8259（8:00〜20:00）</span>
</div>
</body></html>
"""

html = OUT / "aoyama-record-2026-10.html"
pdf = OUT / "aoyama-record-2026-10.pdf"
png = OUT / "aoyama-record-2026-10.png"
html.write_text(HTML, encoding="utf-8")

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
subprocess.run(base + [f"--print-to-pdf={pdf}", str(html)], check=True, capture_output=True)
subprocess.run(base + ["--window-size=1240,1754", "--screenshot=" + str(png), str(html)], check=True, capture_output=True)
print("書きました:", pdf, "/", png)
