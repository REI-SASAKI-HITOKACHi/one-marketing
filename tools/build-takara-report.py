#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""タカラサービスさま向け 実績レポート（A4・1枚）を HTML → PDF で作る。

【何のためのレポートか】（MTG 2026-09-04 #19 オーナー決定）
  該社の担当者に「①クリーニングニーズがある ②一定の顧客グリップ要素になる
  ③ONE-HITTER が有用な発注先である」と認識してもらい、東京での洗浄の発注を増やす。
  メールに、紹介カード（タカラサービス版・オーナーが作る）と一緒に添える。
  根拠は docs/タカラサービス-実績レポート-2026-09.md。

【オーナー修正 2026-09-22】金額は載せない／顧客名を載せる／リピートに触れる／
  相手が既に知っているメニュー・料金は書かない／紹介カードを主役にする。

【使い方】
  python3 tools/build-takara-report.py   # dist/takara/ に HTML・PDF・PNG（確認用）を出す
"""
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "dist" / "takara"
OUT.mkdir(parents=True, exist_ok=True)

ASOF = "2026年9月22日"

# 台帳の氏名・実施メニュー・備考から（docs/タカラサービス-実績レポート-2026-09.md §3.1）。金額は出さない。
JOBS = [
    ("江戸前ハーブ 様（大田区）", "2024年3月", "エアコン（お掃除機能付き）"),
    ("江戸前ハーブ 様", "2024年4月", "エアコン 1台（再依頼）"),
    ("江戸前ハーブ 様", "2025年2月", "エアコン 4台（再依頼）"),
    ("江戸前ハーブ 様", "2025年7月", "置き型業務用エアコン 2台（再依頼）"),
    ("江戸前ハーブ 様", "2026年8月", "壁掛け4台＋天吊り1台（再依頼）"),
    ("株式会社サンリバー 様（目黒区・店舗）", "2024年5月", "業務用エアコン"),
    ("スタジオファイン 様", "2026年7月", "天井カセット"),
    ("24GYM 様", "2023年11月", "—"),
    ("株式会社ドア 様（墨田区）", "2023年9月", "業務用エアコン 複数台"),
    ("御社から直接のご依頼", "2024年9月", "業務用エアコン／ドレンパン洗浄 2台"),
    ("御社から直接のご依頼", "2026年2月", "床置き型 2台、壁掛け4台＋天吊り1台"),
]

rows = "".join(f"<tr><td>{c}</td><td>{d}</td><td>{m}</td></tr>" for c, d, m in JOBS)

HTML = f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<title>ご紹介いただいたお客様のご報告</title>
<style>
  @page {{ size: A4; margin: 14mm 15mm 12mm 15mm; }}
  html, body {{ margin: 0; padding: 0; }}
  body {{ font-family: "IPAPGothic", "IPA Pゴシック", "Noto Sans CJK JP", sans-serif;
         color: #1a1a1a; font-size: 10.6pt; line-height: 1.55; }}
  h1 {{ font-size: 16pt; margin: 0 0 2mm; letter-spacing: .02em; }}
  .meta {{ font-size: 9pt; color: #555; margin: 0 0 4mm; display: flex; justify-content: space-between; }}
  h2 {{ font-size: 11.5pt; margin: 4mm 0 1.6mm; padding-left: 2.2mm; border-left: 3.5pt solid #1f5f8b; }}
  p {{ margin: 0 0 1.6mm; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1mm 0 1.5mm; }}
  th, td {{ border-bottom: 1px solid #d9d9d9; padding: 1mm 2mm; text-align: left; font-size: 9.8pt; }}
  th {{ background: #eef3f7; font-weight: normal; color: #333; }}
  ul {{ margin: 0 0 1.5mm; padding-left: 4.5mm; }}
  li {{ margin: 0 0 .9mm; }}
  .box {{ border: 1.5px solid #1f5f8b; border-radius: 2mm; padding: 2.6mm 3.8mm; margin-top: 3mm; background: #f7fafc; }}
  .box h2 {{ margin-top: 0; border: none; padding: 0; font-size: 12.5pt; }}
  .foot {{ margin-top: 4.5mm; padding-top: 2mm; border-top: 1px solid #bbb; font-size: 9pt; color: #333;
           display: flex; justify-content: space-between; }}
</style></head>
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
<li>製造から10年を超えた機器は、洗浄前にお客様とご相談し、入れ替えのご検討は御社をご案内します。</li>
</ul>

<div class="box">
<h2>同封の「ご紹介カード」をお客様にお渡しください</h2>
<p>設置や点検でお客様を訪問されるとき、同封のカードを1枚お渡しください。カードには御社からのご紹介である旨と、申込フォームのQRコードが入っています。ご依頼は当社が直接お受けし、御社のお客様からのご依頼は、毎月まとめて御社へご報告します。御社のお客様を、当社が丁寧に承ります。</p>
</div>

<div class="foot">
<span>ワンヒッター株式会社　〒134-0081 東京都江戸川区北葛西5-14-11 クオーディア西葛西503</span>
<span>TEL 080-8043-8259（8:00〜20:00）</span>
</div>
</body></html>
"""

html_path = OUT / "takara-report-2026-09.html"
pdf_path = OUT / "takara-report-2026-09.pdf"
png_path = OUT / "takara-report-2026-09.png"
html_path.write_text(HTML, encoding="utf-8")

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
subprocess.run(base + [f"--print-to-pdf={pdf_path}", str(html_path)], check=True, capture_output=True)
subprocess.run(base + ["--window-size=1240,1754", "--screenshot=" + str(png_path), str(html_path)],
               check=True, capture_output=True)
print("書きました:", pdf_path, "/", png_path)
