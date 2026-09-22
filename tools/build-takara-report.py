#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""タカラサービスさま向け 実績レポート（A4・1枚）を HTML → PDF で作る。

【何のためのレポートか】（MTG 2026-09-04 #19 オーナー決定）
  該社の担当者に「①クリーニングニーズがある ②一定の顧客グリップ要素になる
  ③ONE-HITTER が有用な発注先である」と認識してもらい、東京での洗浄の発注を増やす。
  メールに添えて送る。中身の根拠は docs/タカラサービス-実績レポート-2026-09.md。

【使い方】
  python3 tools/build-takara-report.py            # dist/takara/ に HTML・PDF・PNG（確認用）を出す

数字を直すときは、下の DATA を直してから作り直す。台帳の値は手で書き換えない。
"""
import os
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "dist" / "takara"
OUT.mkdir(parents=True, exist_ok=True)

# ---- 台帳から読んだ数字（2026-09-22 CMO）。出所は docs/タカラサービス-実績レポート-2026-09.md §2 ----
DATA = {
    "asof": "2026年9月22日",
    "years": [  # 年, 件数, 金額（税込）
        ("2023年", 2, 72_100),
        ("2024年", 5, 182_960),
        ("2025年", 3, 117_390),
        ("2026年（8月まで）", 4, 268_620),
    ],
    "total_n": 14,
    "total_yen": 641_070,
    "recent": [  # 直近の内容（現場が分かる書き方はしない）
        ("2026年2月", "床置き型 2台", 59_600),
        ("2026年2月", "壁掛け4台＋天吊り1台", 67_000),
        ("2026年7月", "天井カセット", 75_020),
        ("2026年8月", "壁掛け4台＋天吊り1台", 67_000),
    ],
}


def yen(n):
    return f"{n:,}円"


rows_year = "".join(
    f"<tr><td>{y}</td><td class='n'>{n}件</td><td class='n'>{yen(v)}</td></tr>"
    for y, n, v in DATA["years"]
)
rows_recent = "".join(
    f"<tr><td>{d}</td><td>{m}</td><td class='n'>{yen(v)}</td></tr>"
    for d, m, v in DATA["recent"]
)

HTML = f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<title>ご紹介いただいた洗浄のご報告</title>
<style>
  @page {{ size: A4; margin: 14mm 15mm 12mm 15mm; }}
  html, body {{ margin: 0; padding: 0; }}
  body {{ font-family: "IPAPGothic", "IPA Pゴシック", "Noto Sans CJK JP", sans-serif;
         color: #1a1a1a; font-size: 10.6pt; line-height: 1.55; }}
  h1 {{ font-size: 16pt; margin: 0 0 2mm; letter-spacing: .02em; }}
  .meta {{ font-size: 9pt; color: #555; margin: 0 0 5mm; display: flex; justify-content: space-between; }}
  h2 {{ font-size: 11.5pt; margin: 4.5mm 0 1.6mm; padding-left: 2.2mm; border-left: 3.5pt solid #1f5f8b; }}
  p {{ margin: 0 0 1.6mm; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1mm 0 1.5mm; }}
  th, td {{ border-bottom: 1px solid #d9d9d9; padding: 1.1mm 2mm; text-align: left; font-size: 10pt; }}
  th {{ background: #eef3f7; font-weight: normal; color: #333; }}
  td.n, th.n {{ text-align: right; white-space: nowrap; }}
  tr.total td {{ border-top: 1.5px solid #1f5f8b; border-bottom: none; font-weight: bold; }}
  .two {{ display: grid; grid-template-columns: 1fr 1fr; gap: 6mm; }}
  ul {{ margin: 0 0 1.5mm; padding-left: 4.5mm; }}
  li {{ margin: 0 0 .8mm; }}
  .box {{ border: 1px solid #1f5f8b; border-radius: 2mm; padding: 2.4mm 3.5mm; margin-top: 2mm; background: #f7fafc; }}
  .box h2 {{ margin-top: 0; border: none; padding: 0; }}
  .foot {{ margin-top: 5mm; padding-top: 2mm; border-top: 1px solid #bbb; font-size: 9pt; color: #333;
           display: flex; justify-content: space-between; }}
  .small {{ font-size: 8.8pt; color: #555; }}
</style></head>
<body>
<h1>ご紹介いただいた洗浄のご報告　2023年9月〜2026年8月</h1>
<div class="meta"><span>株式会社タカラサービス　ご担当者さま</span><span>ワンヒッター株式会社　{DATA["asof"]}</span></div>

<p>いつもご紹介をいただき、ありがとうございます。御社からご紹介いただいたエアコン洗浄を、3年分まとめました。</p>

<div class="two">
<div>
<h2>1　ご紹介いただいた洗浄</h2>
<table>
<tr><th>年</th><th class="n">件数</th><th class="n">金額（税込）</th></tr>
{rows_year}
<tr class="total"><td>合計</td><td class="n">{DATA["total_n"]}件</td><td class="n">{yen(DATA["total_yen"])}</td></tr>
</table>
<p>2026年は8月までで、年間で最多です。</p>
<table>
<tr><th>直近のご依頼</th><th>内容</th><th class="n">金額（税込）</th></tr>
{rows_recent}
</table>
<p>再依頼が3回になった現場が1か所あります。2026年は2月と8月に、同じ内容のご依頼がありました。</p>
</div>
<div>
<h2>2　洗浄は、御社とお客様の接点になります</h2>
<p>設置から入れ替えまでの間、お客様との接点は故障や点検のときに限られがちです。洗浄が入ると、年に1回の接点ができます。</p>
<ul>
<li>365日運転の店舗で「冷房にすると酸っぱい匂い」のご相談があり、内部のカビを洗浄で解消しました。</li>
<li>製造から10年を超えた機器は、洗浄前にご相談しています。御社の方針と同じです。</li>
<li><b>ご提案：</b>洗浄のたびに、機器の状態（製造年・異音・ドレンの詰まり・部品の劣化）を御社へ報告します。入れ替えや修理をご提案する時期が分かります。</li>
</ul>
<h2>3　当社について</h2>
<ul>
<li>対応機種：天井カセット・天吊り・床置き・壁掛け・お掃除機能付き。ドレンパン洗浄も対応。</li>
<li>対応エリア：東京都・千葉県・神奈川県。御社の関東の工事拠点と重なります。</li>
<li>お支払い：請求書払い（翌月）。損害賠償保険に加入しています。</li>
<li>実績：エアコン洗浄 年間130件以上（2025年）。</li>
<li>料金（税込）：業務用エアコン 1台 32,780円、2〜10台は1台 27,280円。</li>
</ul>
</div>
</div>

<div class="box">
<h2>ご相談：お客様にお渡しいただく「洗浄のご案内カード」</h2>
<p>設置や修理でお客様を訪問されるとき、担当の方から名刺サイズのカードを1枚お渡しいただけないでしょうか。「設置から1〜2年で一度洗浄を」というご案内と、御社経由と分かる連絡先を載せます。ご依頼は当社が受け、施工の報告は御社にもお送りします。カードの制作費は当社が持ちます。ご要望があれば、原稿をお作りしてお送りします。</p>
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
for c in ("/opt/pw-browsers/chromium", "/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome"):
    p = pathlib.Path(c)
    if p.is_dir():
        hits = list(p.glob("**/chrome")) + list(p.glob("**/chromium"))
        if hits:
            chrome = str(hits[0]); break
    elif p.exists():
        chrome = c; break
if not chrome:
    for d in pathlib.Path("/opt/pw-browsers").glob("chromium-*"):
        hits = list(d.glob("**/chrome"))
        if hits:
            chrome = str(hits[0]); break
if not chrome:
    raise SystemExit("Chromium が見つかりません")

base = [chrome, "--headless=new", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer"]
subprocess.run(base + [f"--print-to-pdf={pdf_path}", str(html_path)], check=True, capture_output=True)
subprocess.run(base + ["--window-size=1240,1754", "--screenshot=" + str(png_path), str(html_path)],
               check=True, capture_output=True)
print("書きました:", pdf_path, "/", png_path)
