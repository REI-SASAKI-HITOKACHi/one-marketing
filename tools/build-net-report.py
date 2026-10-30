#!/usr/bin/env python3
"""オーナー向け「ネット流入の検証と見込み」（スマホで読む縦長PDF）。

  python3 tools/build-net-report.py

中身の正は docs/2026-ネット流入の検証と見込み-1021.md。数字はそこから写している。
PDF化は Chromium の --print-to-pdf（/opt/pw-browsers/chromium）。
"""
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / 'docs' / 'presentations'
CHROMIUM = '/opt/pw-browsers/chromium'
NAME = 'ネット流入の検証と見込み-2026-10-21'

CSS = """
@page { size: 100mm 178mm; margin: 7mm 6mm 7mm; }
* { box-sizing: border-box; }
html { font-size: 9.6pt; }
body { font-family: "IPAPGothic","IPAGothic",sans-serif; color: #1f2d2a; line-height: 1.7; margin: 0;
       -webkit-print-color-adjust: exact; print-color-adjust: exact; }
h1,h2,h3 { line-height: 1.35; margin: 0; }
p { margin: 0 0 .7em; }
.pg { page-break-after: always; }
.pg:last-child { page-break-after: auto; }
.kaisha { font-size: 7.5pt; letter-spacing: .2em; color: #5c6d69; }
h1 { font-size: 17pt; margin: 8px 0 4px; }
.sub { font-size: 9pt; color: #3d4f4b; }
.rule { height: 3px; background: #0a5c50; width: 46px; margin: 12px 0; }
h2 { font-size: 12.5pt; border-bottom: 2px solid #0a5c50; padding-bottom: 4px; margin-bottom: 9px; }
h2 .no { display: block; font-size: 7.5pt; color: #0a5c50; letter-spacing: .1em; }
h3 { font-size: 10pt; color: #0a5c50; margin: 10px 0 4px; }
.box { border: 1px solid #c9d4d0; background: #f4f7f5; padding: 8px 10px; margin: 8px 0; }
.box.aka { background: #fbeeec; border-color: #e8c4be; }
.box.kiiro { background: #fdf6e6; border-color: #e3d3a8; }
.box.midori { background: #eef7f3; border-color: #a9d3c4; }
.box p:last-child { margin-bottom: 0; }
.midashi { font-weight: bold; margin-bottom: 3px; }
.kpi { display: flex; gap: 5px; margin: 8px 0; }
.kpi .c { flex: 1; border: 1px solid #c9d4d0; background: #f4f7f5; padding: 6px 4px; text-align: center; }
.kpi .l { font-size: 7pt; color: #5c6d69; line-height: 1.3; }
.kpi .v { font-size: 13.5pt; font-weight: bold; color: #0a5c50; line-height: 1.25; }
.kpi .n { font-size: 6.8pt; color: #5c6d69; line-height: 1.3; }
.kpi .c.warn .v { color: #c0392b; }
table { border-collapse: collapse; width: 100%; margin: 6px 0; font-size: 8.4pt; }
th, td { border: 1px solid #d5ded9; padding: 3px 4px; text-align: right; }
th { background: #eef3f0; text-align: center; }
td:first-child, th:first-child { text-align: left; }
tr.b td { background: #eef3f0; font-weight: bold; }
.neg { color: #c0392b; font-weight: bold; }
.pos { color: #0a5c50; font-weight: bold; }
.mark { background: linear-gradient(transparent 60%, #b8e4dc 60%); font-weight: bold; }
ol, ul { margin: 4px 0 7px; padding-left: 1.3em; }
li { margin-bottom: 3px; }
.num { display: flex; gap: 7px; margin: 0 0 8px; }
.num .n { flex: none; width: 18px; height: 18px; border-radius: 50%; background: #0a5c50; color: #fff;
          font-size: 8pt; text-align: center; line-height: 18px; font-weight: bold; }
.num .t { flex: 1; }
.kome { font-size: 7.3pt; color: #5c6d69; line-height: 1.55; }
.bar { display: flex; align-items: center; gap: 5px; margin: 3px 0; font-size: 8pt; }
.bar .lab { width: 64px; flex: none; white-space: nowrap; }
.bar .w { flex: 1; background: #eef3f0; height: 13px; position: relative; }
.bar .f { height: 13px; background: #0a5c50; }
.bar .f.r { background: #c0392b; }
.bar .val { width: 52px; flex: none; text-align: right; }
"""

HTML = """<!doctype html><html lang="ja"><head><meta charset="utf-8">
<title>ネット流入の検証と見込み</title><style>__CSS__</style></head><body>

<section class="pg">
  <div class="kaisha">ONE HITTER　経営企画室</div>
  <h1>ネット流入の<br>検証と見込み</h1>
  <div class="sub">2027年計画 ④自社ネット新規に対して</div>
  <div class="rule"></div>
  <p class="kome">2026年10月21日　オーナー指示「この計画値は不変で必達。ネット流入に絞って現状の検証と今後の見込みを」への報告</p>

  <div class="box midori">
    <div class="midashi">計画の値（動かさない）</div>
    年 <b>500万・143件</b>（月12件）／1件 <b>¥34,965</b><br>広告費 年80万／1件の広告費の上限 <b>¥9,500</b>
  </div>

  <div class="box aka">
    <div class="midashi">結論</div>
    <div class="num"><div class="n">1</div><div class="t"><b>件数は計画に近づいた。</b>10月 8件（着地 9〜10件）。ただし<b>8件中7件が広告</b>。無料の経路はほぼ0件。</div></div>
    <div class="num"><div class="n">2</div><div class="t"><b>金額が足りない。</b>1件の平均 ¥14,251＝計画の<span class="neg">41%</span>。月12件取っても月 約¥17万（計画 約¥42万）。</div></div>
    <div class="num"><div class="n">3</div><div class="t"><b>広告が高い。</b>1件 約¥17,000＝上限の<span class="neg">約1.8倍</span>。</div></div>
  </div>
</section>

<section class="pg">
  <h2><span class="no">1　実績</span>件数は伸びた。中身は広告頼み</h2>
  <div class="kpi">
    <div class="c"><div class="l">10月の件数</div><div class="v">8件</div><div class="n">計画 月12件</div></div>
    <div class="c warn"><div class="l">1件の平均</div><div class="v">¥14,251</div><div class="n">計画 ¥34,965</div></div>
    <div class="c warn"><div class="l">広告の1件</div><div class="v">¥17,000</div><div class="n">上限 ¥9,500</div></div>
  </div>
  <table>
    <tr><th>期間</th><th>件数</th><th>売上</th></tr>
    <tr><td>1〜8月（HP経由）</td><td>年4件</td><td>¥63,100</td></tr>
    <tr><td>9月</td><td>1件</td><td>¥18,480</td></tr>
    <tr class="b"><td>10月（10/21時点）</td><td>8件</td><td>¥114,010</td></tr>
    <tr><td>10月 着地見込み</td><td>9〜10件</td><td>約¥13〜14万</td></tr>
    <tr><td>計画（月平均）</td><td>12件</td><td>約¥42万</td></tr>
  </table>
  <p class="kome">1〜8月は年4件だった。9月下旬に広告を始めてからの1か月で、それを2倍に上回った。</p>

  <h3>経路別の受注（9/20〜10/21）</h3>
  <div class="bar"><span class="lab">Google広告</span><span class="w"><span class="f" style="display:block;width:100%"></span></span><span class="val">8件</span></div>
  <div class="bar"><span class="lab">公式LINE</span><span class="w"><span class="f" style="display:block;width:12.5%"></span></span><span class="val">1件</span></div>
  <div class="bar"><span class="lab">SNS投稿</span><span class="w"></span><span class="val">0</span></div>
  <div class="bar"><span class="lab">ブログ</span><span class="w"></span><span class="val">0</span></div>
  <div class="bar"><span class="lab">GBP</span><span class="w"></span><span class="val">0</span></div>
  <div class="bar"><span class="lab">年末LP</span><span class="w"></span><span class="val">記録なし</span></div>
  <div class="bar"><span class="lab">アフィリ</span><span class="w"></span><span class="val">0</span></div>
  <div class="bar"><span class="lab">SMS再販</span><span class="w"></span><span class="val">未送信</span></div>
  <p class="kome">広告はキャンセル1件を除く。GBPから予約ページに来ていたのは機械のアクセスだけ（10/16確認）。アフィリエイトは配信状況を問い合わせ中。</p>
</section>

<section class="pg">
  <h2><span class="no">2　広告の効率</span>申込は取れる。初回では回収できていない</h2>
  <table>
    <tr><th></th><th>実績</th><th>計画</th></tr>
    <tr><td>広告費（9/20〜10/20）</td><td>約¥13.6万</td><td>段0 月5万</td></tr>
    <tr><td>受注</td><td>8件</td><td></td></tr>
    <tr class="b"><td>受注1件の広告費</td><td class="neg">約¥17,000</td><td>¥9,500</td></tr>
    <tr><td>広告受注の売上</td><td>¥122,788</td><td></td></tr>
    <tr><td>売上 ÷ 広告費</td><td class="neg">約0.9倍</td><td></td></tr>
  </table>
  <p class="kome">広告費は 9/20〜10/7 が実績（¥73,362）、それ以降は毎日の点検値と一部の日の概算。</p>

  <h3>どこで落ちているか</h3>
  <div class="box">
    LPを見た人のうち、予約ページへ進むのは <b>5%</b>（入口の直し後 <b>8%</b>）。<br>
    <span class="mark">92〜95%がLPで離れている。</span>ここが直れば同じ広告費で件数が増える。
  </div>

  <h3>明るい材料</h3>
  <div class="box midori">
    10/15夜に入札方式を切り替えてから5日で申込3件（1件キャンセル）。<b>申込1件 約¥6,200</b>。<br>
    <span class="kome">件数が少ないので、まだ当てにしない。10/23 に判定。</span>
  </div>
</section>

<section class="pg">
  <h2><span class="no">3　分かったこと</span>計画の前提とずれている3点</h2>
  <div class="num"><div class="n">1</div><div class="t"><b>広告は申込を取れる。</b>1か月で受注8件。計画の「パターンA（月2〜3件）」は抜けた。</div></div>
  <div class="num"><div class="n">2</div><div class="t"><b>広告の客は小口。</b>エアコン1〜2台・浴室単品が中心。計画の ¥34,965 は会社全体の平均単価で置いていたが、<span class="mark">広告で来る新規客の初回はその4割</span>。</div></div>
  <div class="num"><div class="n">3</div><div class="t"><b>無料の経路がまだ効いていない。</b>計画の「パターンB（月5〜8件）」は「年末LP 月4〜5件・地図検索 月2件・SMS再販とアフィリで数件」が前提。<span class="mark">今の8件は、その前提と違う経路（広告）で出ている。</span></div></div>
</section>

<section class="pg">
  <h2><span class="no">4　今後の見込み</span>このままでは500万に届かない</h2>
  <h3>11月</h3>
  <div class="box">
    <b>中心11件・売上 約¥16万</b>（8〜18件）。<br>広告 6〜11／直接 2／SMS 0〜3／紹介・HP 0〜2<br>
    <span class="kome">SMS を今週中に送ることが条件。12月は受付可能50件の枠が先に詰まる。</span>
  </div>

  <h3>2027年：このまま延長した場合</h3>
  <table>
    <tr><th></th><th>計画</th><th>このまま</th></tr>
    <tr><td>月の件数</td><td>12件</td><td>9〜11件</td></tr>
    <tr><td>1件の平均</td><td>¥34,965</td><td class="neg">¥14,251</td></tr>
    <tr><td>月の売上</td><td>約¥42万</td><td class="neg">約¥13〜16万</td></tr>
    <tr class="b"><td>年の売上</td><td>500万</td><td class="neg">約150〜190万</td></tr>
    <tr><td>143件の広告費</td><td>80万</td><td class="neg">約243万</td></tr>
  </table>
  <div class="box aka">
    <span class="mark">不足 約330万のうち、約300万は単価。</span><br>143件取れても1件 ¥14,251 なら 約204万。件数の不足は小さい。広告の効率は売上ではなく利益を削る（+約163万）。
  </div>
</section>

<section class="pg">
  <h2><span class="no">5　計画を守るために</span>3つとも要る（1つでは届かない）</h2>
  <div class="num"><div class="n">1</div><div class="t"><b>1件の単価を ¥30,000以上へ</b>（いま ¥14,251）<br>
    広告の着地を「複数台・水まわりセット・カビの完全分解」に寄せる。現場で「次の1箇所」。<br>
    <span class="kome">10/4 の広告客は当日に完全分解を追加して ¥18,502 に。</span></div></div>
  <div class="num"><div class="n">2</div><div class="t"><b>無料の経路で月6件</b>（いま 月1件）<br>
    SMS再販を確実に送る。ブログ・GBP・年末LP は検索が育つまで6〜12か月。<br>
    <span class="kome">2027年1〜3月は広告とSMSで件数を支え、4月以降に無料の経路が育つ前提で見る。</span></div></div>
  <div class="num"><div class="n">3</div><div class="t"><b>広告の1件を ¥9,500以下へ</b>（いま 約¥17,000）<br>
    LP→予約ページを 8%→15%。入札切り替えの効果（10/23判定）。</div></div>
  <div class="box kiiro">
    <b>③だけ達成しても</b>、単価が今のままなら 84件×¥14,251＝約120万。<span class="mark">①がいちばん効く。</span>
  </div>
</section>

<section class="pg">
  <h2><span class="no">6　決めてほしいこと</span>広告を止める線</h2>
  <div class="box kiiro">
    <p><b>計画書：</b>「月のCPAが9,500円を超えたら、その月で止める」</p>
    <p><b>10/9 の発言：</b>「単体赤字でも、お客様の平均LTVで回収する」</p>
    <p>いまは約¥17,000で止める線を超えているが、<b>後者で運用中</b>（受注1件 ¥30,500 までは「次の1回までで回収」の線で続ける）。</p>
  </div>
  <p><b>どちらで運用するか</b>を決めてください。</p>

  <h3>この先の日程</h3>
  <table>
    <tr><th>日付</th><th>何を</th></tr>
    <tr><td>10/23</td><td>入札切り替えの判定</td></tr>
    <tr><td>10/24まで</td><td>既存客SMSの送信</td></tr>
    <tr><td>11/1</td><td>広告予算の判定シート</td></tr>
    <tr><td>11月中</td><td>広告客の単価が上がったか</td></tr>
  </table>
  <p class="kome">出どころ：着地集計 10/21 09:43、計測担当の10/9判定表、GA4の経路別4段、毎日の広告点検。詳細は docs/2026-ネット流入の検証と見込み-1021.md</p>
</section>

</body></html>
"""


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    h = OUT / f'{NAME}.html'
    h.write_text(HTML.replace('__CSS__', CSS), encoding='utf-8')
    pdf = OUT / f'{NAME}.pdf'
    if not os.path.exists(CHROMIUM):
        sys.exit(f'Chromium が無い: {CHROMIUM}')
    subprocess.run([CHROMIUM, '--headless', '--no-sandbox', '--disable-gpu', '--no-pdf-header-footer',
                    '--virtual-time-budget=8000', f'--print-to-pdf={pdf}', h.as_uri()],
                   capture_output=True, text=True, timeout=180)
    print(f'PDF : {pdf}  ({pdf.stat().st_size:,} バイト)' if pdf.exists() else 'PDF の生成に失敗')


if __name__ == '__main__':
    main()
