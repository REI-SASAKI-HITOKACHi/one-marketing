#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""株式会社エル・アップさま向け「取引の記録」（A4・1枚）を HTML → PDF/PNG で作る。

【何のためか】docs/提携先-休眠先を起こす3パターン.md のパターン①（TODO T059）。
  最後の依頼（2025年7月 空室47㎡＋エアコン2台）から1年あまり止まっているリフォーム会社に、
  これまでの作業を1枚で見せて、追い焚き配管・洗濯機・エアコンの依頼を再開していただく。
  空室清掃は売り込まない（オーナー決定 2026-09-14）。記録として載せるだけ。金額は載せない。

【根拠】2024〜2025年の売上スプシの月次タブ（N月_売上/顧客）で、氏名・備考に「エル・アップ／エルアップ」が入る9行
  （2026-10-09 読み取りのみ）と、和真さんのカレンダーの予定（題名・場所）を1件ずつ突き合わせた。
  - 7件＝提携タブ『【毎月更新】リピート/業務提携』の7件と同じ
  - ＋2件＝貴社のお客様（備考「エルアップ案件」「エルアップご紹介」・提携割引12%）。お客様の名前は出さない
  載せないもの：
  - カレンダー 2025/08/24「エルアップ 下川」… 台帳に行が無い（未記帳か取り消しか不明。和真さんに確認）
  - カレンダー 2024/09/10「エルアップ」… 台帳に行が無い（9/9 の空室の続きと見られる。数えない）
  - 2023/11/13 の訪問・2024/02/09 の提携説明（作業ではない）
  場所：2024/09・2025/06・2025/07 の3件は台帳にもカレンダーにも場所が無いので「—」。
  名乗り：meigi_hyou() で「自社」（最新の施工 2025-07-31・氏名5通り）を確認済み（2026-10-09）。

  python3 tools/build-elup-record.py   # dist/elup/ に PDF と PNG を出す
"""
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "dist" / "elup"
OUT.mkdir(parents=True, exist_ok=True)

ASOF = "2026年10月9日"

JOBS = [
    ("2024年2月",  "足立区（千住川原町）", "追い焚き配管の洗浄"),
    ("2024年4月",  "荒川区（西尾久）",     "換気扇（貴社のお客様）"),
    ("2024年4月",  "足立区（扇）",         "縦型洗濯機の分解洗浄"),
    ("2024年4月",  "荒川区（町屋）",       "ドラム式洗濯機＋エアコン 1台"),
    ("2024年6月",  "墨田区（菊川）",       "エアコン 1台（貴社のお客様）"),
    ("2024年6月",  "荒川区（町屋）",       "貴社事務所のエアコン 2台"),
    ("2024年9月",  "—",                    "空室クリーニング（キッチン・床・玄関まわり）"),
    ("2025年6月",  "—",                    "エアコン 4台（お掃除機能付き 1台を含む）"),
    ("2025年7月",  "—",                    "空室クリーニング（47㎡）＋エアコン 2台"),
]

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
<h1>これまでのお取引の記録　2024年2月〜2025年7月</h1>
<div class="meta"><span>株式会社エル・アップ　ご担当者 様</span><span>ワンヒッター株式会社　{ASOF}</span></div>

<p>これまで多くのご依頼をいただき、ありがとうございました。貴社からのご依頼で伺った作業を1枚にまとめました。</p>

<h2>1　貴社からのご依頼</h2>
<table>
<tr><th>ご依頼の月</th><th>場所</th><th>内容</th></tr>
{rows}
</table>
<p>最後にいただいたのは、2025年7月の空室クリーニング（47㎡）とエアコン 2台でした。</p>

<h2>2　当社の今</h2>
<ul>
<li>ご利用後アンケートで、98.6%（209名中206名、2023年1月〜2025年12月）のお客様に、ご家族や友人に勧めてもよいとお答えいただいています。</li>
<li>Googleクチコミは★5.0です。</li>
<li>1現場で天井カセット51台＋換気設備17台（2026年8月）の洗浄を行うなど、大きな現場にも対応しています。</li>
</ul>

<div class="box">
<h2>こんなご依頼を承ります</h2>
<ul>
<li><b>追い焚き配管</b>の洗浄</li>
<li><b>洗濯機</b>：ドラム式・縦型の分解洗浄</li>
<li><b>エアコン</b>：お掃除機能付きを含む壁掛け、業務用（天井カセット・天吊り・床置き）</li>
<li><b>換気扇・レンジフード</b></li>
<li>貴社のお客様をご紹介いただく場合も、これまでどおり提携割引（12%）でお受けします。</li>
</ul>
<p>お引き渡し前や、お客様からのご相談で必要なときは、メールへのご返信かお電話でお知らせください。</p>
</div>

<div class="foot">
<span>ワンヒッター株式会社　〒134-0081 東京都江戸川区北葛西5-14-11 クオーディア西葛西503</span>
<span>TEL 080-8043-8259（8:00〜20:00）</span>
</div>
</body></html>
"""

html = OUT / "elup-record-2026-10.html"
pdf = OUT / "elup-record-2026-10.pdf"
png = OUT / "elup-record-2026-10.png"
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
