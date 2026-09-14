#!/usr/bin/env python3
"""和真さん向け「2027年の計画」の説明資料（PDF）を作る。

【なぜこの形か】
  数字は tools/plan2027.py から直接引く。手で書き写すとズレるため。
  本文はオーナー（佐々木）の言葉として常体で書いてある。社内資料。

【使い方】
  python3 tools/build-wakazuma-2027.py
  → docs/presentations/2027年の計画_社内用.html と .pdf を出力

  PDF化は Chromium の --print-to-pdf を使う（/opt/pw-browsers/chromium）。
  日本語フォントは IPAGothic（システムにあるもの）。
"""
import importlib.util
import os
import pathlib
import subprocess
import sys

KONO = pathlib.Path(__file__).resolve().parent
ROOT = KONO.parent
SHUTSURYOKU = ROOT / 'docs' / 'presentations'
CHROMIUM = '/opt/pw-browsers/chromium'

spec = importlib.util.spec_from_file_location('plan2027', KONO / 'plan2027.py')
plan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plan)

AN = '中立'
GYOU = plan.keisan(AN)
G = plan.goukei(GYOU)


def en(v):
    return f"{v:,}"


# ---------------------------------------------------------------
# 月次P/L（前半6か月／後半6か月に分ける。A4縦に収めるため）
# ---------------------------------------------------------------
RETSU = [
    ('売上', '売上', True),
    ('件数', '件数', False),
    ('平均単価', '平均単価', False),
    ('原価_資材費', '　資材費', False),
    ('原価_外注費', '　外注費（協力業者）', False),
    ('原価_補助人件費', '　補助人件費（時給）', False),
    ('原価_計', '原価 計', True),
    ('売上総利益', '売上総利益', False),
    ('販管_人件費_和真', '　人件費：和真', False),
    ('販管_人件費_新人', '　人件費：新人（社保込）', False),
    ('販管_採用費装備', '　採用費・装備', False),
    ('販管_広告費', '　広告費', False),
    ('販管_ロイヤリティ', '　ロイヤリティ（変動）', False),
    ('販管_ロイヤリティ固定', '　ロイヤリティ（固定）', False),
    ('販管_固定経費', '　固定経費', False),
    ('販管_その他変動費', '　変動経費', False),
    ('販管_計', '販売管理費 計', True),
    ('営業利益', '営業利益', True),
    ('融資返済', '融資返済', False),
    ('経常利益', '経常利益', True),
]


def pl_hyou(tsuki_kara, tsuki_made, nenkei=False):
    rs = [r for r in GYOU if tsuki_kara <= r['月'] <= tsuki_made]
    out = ['<table class="pl"><thead><tr><th class="k">項目</th>']
    for r in rs:
        cls = ' class="q"' if r['月'] in (3, 6, 9, 12) else ''
        shime = '<br><span class="qm">四半期末</span>' if r['月'] in (3, 6, 9, 12) else ''
        out.append(f'<th{cls}>{r["月"]}月{shime}</th>')
    if nenkei:
        out.append('<th class="t">年計</th>')
    out.append('</tr></thead><tbody>')
    for key, mei, futoji in RETSU:
        out.append(f'<tr{" class=b" if futoji else ""}><th class="k">{mei}</th>')
        for r in rs:
            v = r[key]
            c = []
            if r['月'] in (3, 6, 9, 12):
                c.append('q')
            if v < 0:
                c.append('neg')
            cls = ' class="%s"' % ' '.join(c) if c else ''
            out.append(f'<td{cls}>{en(v)}</td>')
        if nenkei:
            tv = G[key]
            out.append(f'<td class="t{" neg" if tv < 0 else ""}">{en(tv)}</td>')
        out.append('</tr>')
    out.append('</tbody></table>')
    return '\n'.join(out)


def shihanki_hyou():
    """四半期は累計で見る（オーナー 2026-09-14）。締めるたびに「年の着地に乗っているか」が分かる形。"""
    out = ['<table class="sum"><thead><tr><th>締め</th><th>累計 売上</th><th>累計 件数</th>'
           '<th>累計 営業利益</th><th>累計 経常利益</th><th>年計に対する進捗</th></tr></thead><tbody>']
    u = k = e = j = 0
    for q, (a, b) in {1: (1, 3), 2: (4, 6), 3: (7, 9), 4: (10, 12)}.items():
        rs = [r for r in GYOU if a <= r['月'] <= b]
        u += sum(r['売上'] for r in rs)
        k += sum(r['件数'] for r in rs)
        e += sum(r['営業利益'] for r in rs)
        j += sum(r['経常利益'] for r in rs)
        out.append(f'<tr><th>{b}月末</th><td>{en(u)}</td><td>{k}</td>'
                   f'<td>{en(e)}</td><td class="{"neg" if j < 0 else ""}">{en(j)}</td>'
                   f'<td>{u / G["売上"] * 100:.0f}%</td></tr>')
    out.append('</tbody></table>')
    return '\n'.join(out)


# ---------------------------------------------------------------
# グラフ（売上と経常利益の2段。x軸を共有する小さな倍数）
# ---------------------------------------------------------------
def graph():
    W, HAKO = 700, 44          # 全体幅／1か月あたりの幅
    X0 = 62
    U_TOP, U_TAKA = 26, 122    # 売上パネル
    K_TOP, K_TAKA = 196, 104   # 経常利益パネル
    u_max = 3_500_000
    k_max, k_min = 1_400_000, -200_000

    def ux(i):
        return X0 + i * HAKO

    def uy(v):
        return U_TOP + U_TAKA - v / u_max * U_TAKA

    def ky(v):
        return K_TOP + (k_max - v) / (k_max - k_min) * K_TAKA

    s = [f'<svg viewBox="0 0 {W} 330" class="graph" role="img" '
         f'aria-label="2027年の月別売上と経常利益">']
    # 売上パネル
    s.append('<text class="gt" x="8" y="18">売上（円）</text>')
    for v in (1_000_000, 2_000_000, 3_000_000):
        s.append(f'<line class="gg" x1="{X0}" y1="{uy(v):.1f}" x2="{W - 20}" y2="{uy(v):.1f}"/>')
        s.append(f'<text class="ga" x="{X0 - 6}" y="{uy(v) + 3.5:.1f}" text-anchor="end">{v // 10000}万</text>')
    s.append(f'<line class="gx" x1="{X0}" y1="{uy(0):.1f}" x2="{W - 20}" y2="{uy(0):.1f}"/>')
    for i, r in enumerate(GYOU):
        x = ux(i)
        y = uy(r['売上'])
        q = r['月'] in (3, 6, 9, 12)
        s.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="30" height="{uy(0) - y:.1f}" '
                 f'fill="{"#0a5c50" if q else "#2f9385"}" rx="2"/>')
        s.append(f'<text class="gv" x="{x + 15:.1f}" y="{y - 5:.1f}" text-anchor="middle">'
                 f'{r["売上"] // 10000}</text>')
    # 経常利益パネル
    s.append('<text class="gt" x="8" y="188">経常利益（円）</text>')
    for v in (1_000_000,):
        s.append(f'<line class="gg" x1="{X0}" y1="{ky(v):.1f}" x2="{W - 20}" y2="{ky(v):.1f}"/>')
        s.append(f'<text class="ga" x="{X0 - 6}" y="{ky(v) + 3.5:.1f}" text-anchor="end">{v // 10000}万</text>')
    s.append(f'<line class="gx" x1="{X0}" y1="{ky(0):.1f}" x2="{W - 20}" y2="{ky(0):.1f}"/>')
    s.append(f'<text class="ga" x="{X0 - 6}" y="{ky(0) + 3.5:.1f}" text-anchor="end">0</text>')
    for i, r in enumerate(GYOU):
        x = ux(i)
        v = r['経常利益']
        y = ky(max(v, 0))
        h = abs(ky(v) - ky(0))
        iro = '#c0392b' if v < 0 else ('#0a5c50' if r['月'] in (3, 6, 9, 12) else '#2f9385')
        s.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="30" height="{max(h, 1.2):.1f}" fill="{iro}" rx="2"/>')
        ty = y - 5 if v >= 0 else ky(v) + 11
        s.append(f'<text class="gv" x="{x + 15:.1f}" y="{ty:.1f}" text-anchor="middle" '
                 f'fill="{"#c0392b" if v < 0 else "#20302d"}">{round(v / 10000)}</text>')
        s.append(f'<text class="gm" x="{x + 15:.1f}" y="322" text-anchor="middle">{r["月"]}</text>')
    s.append('<text class="gm" x="30" y="322">月</text>')
    s.append('</svg>')
    return '\n'.join(s)


# ---------------------------------------------------------------
# 2028〜2030年のシミュレーション
# ---------------------------------------------------------------
CHOUKI = {a: plan.chouki(a) for a in ('保守的', '中', '良')}


def chouki_hyou():
    out = ['<table class="futsu nobreak" style="font-size:8.6pt">',
           '<thead><tr><th rowspan="2">年</th>'
           '<th colspan="2">保守的</th><th colspan="2">中</th><th colspan="2">良</th></tr>'
           '<tr><th>売上</th><th>経常利益</th><th>売上</th><th>経常利益</th>'
           '<th>売上</th><th>経常利益</th></tr></thead><tbody>']
    for i in range(4):
        y = CHOUKI['保守的'][i]['年']
        tds = []
        for a in ('保守的', '中', '良'):
            r = CHOUKI[a][i]
            tds.append(f'<td>{r["売上_万"]:,}万</td><td><b>{r["経常利益_万"]:,}万</b></td>')
        cls = ' class="b"' if i == 0 else ''
        nen = f'<b>{y}年</b><br><span class="kome">計画</span>' if i == 0 else f'<b>{y}年</b>'
        out.append(f'<tr{cls}><td>{nen}</td>' + ''.join(tds) + '</tr>')
    out.append('</tbody></table>')
    # 前提の表
    out.append('<table class="futsu nobreak" style="font-size:8.6pt;margin-top:10px">'
               '<thead><tr><th>置いた前提（2030年時点）</th><th>保守的</th><th>中</th><th>良</th></tr></thead><tbody>')
    kv = [('自社で獲った新規のリピート率', lambda a: f"{plan.CHOUKI_AN[a]['リピート率']*100:.0f}%"),
          ('自社ネット新規（月）', lambda a: f"{plan.CHOUKI_AN[a]['ネット新規_月件数'][3]}件"),
          ('アクティブな提携先', lambda a: f"{plan.CHOUKI_AN[a]['提携社数'][3]}社"),
          ('施工件数（年）', lambda a: f"{CHOUKI[a][3]['件数']:,}件"),
          ('社員（和真を含む）', lambda a: f"{CHOUKI[a][3]['社員数']}人"),
          ('本舗案件が売上に占める割合',
           lambda a: f"{CHOUKI[a][3]['本舗_万']/CHOUKI[a][3]['売上_万']*100:.0f}%")]
    for mei, f in kv:
        out.append(f'<tr><td>{mei}</td>' + ''.join(f'<td>{f(a)}</td>' for a in ('保守的', '中', '良')) + '</tr>')
    out.append('</tbody></table>')
    return '\n'.join(out)


def chouki_graph():
    W = 760
    X = {2026: 70, 2027: 200, 2028: 330, 2029: 460, 2030: 590}
    TOP, TAKA, YMAX = 42, 214, 6000

    def gy(v):
        return TOP + TAKA - v / YMAX * TAKA

    s = [f'<svg viewBox="0 0 {W} 310" class="graph" role="img" '
         f'aria-label="2026年から2030年までの売上の見通し。保守的・中・良の3パターン">']
    for v in (2000, 4000, 6000):
        s.append(f'<line class="gg" x1="60" y1="{gy(v):.1f}" x2="{W - 110}" y2="{gy(v):.1f}"/>')
        s.append(f'<text class="ga" x="54" y="{gy(v) + 3.5:.1f}" text-anchor="end">{v:,}万</text>')
    s.append(f'<line class="gx" x1="60" y1="{gy(0):.1f}" x2="{W - 110}" y2="{gy(0):.1f}"/>')
    s.append(f'<text class="ga" x="54" y="{gy(0) + 3.5:.1f}" text-anchor="end">0</text>')
    # 実績→計画（太い実線）
    s.append(f'<polyline points="{X[2026]},{gy(1700):.1f} {X[2027]},{gy(2600):.1f}" '
             f'fill="none" stroke="#0a5c50" stroke-width="3"/>')
    iro = {'保守的': '#8aa39d', '中': '#2f9385', '良': '#0a5c50'}
    for a in ('保守的', '中', '良'):
        r = CHOUKI[a]
        pts = [f'{X[2027]},{gy(2600):.1f}'] + [f'{X[2027 + i]},{gy(r[i]["売上_万"]):.1f}' for i in (1, 2, 3)]
        s.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{iro[a]}" '
                 f'stroke-width="2.4" stroke-dasharray="7 4"/>')
        for i in (1, 2, 3):
            s.append(f'<circle cx="{X[2027 + i]}" cy="{gy(r[i]["売上_万"]):.1f}" r="4.5" fill="{iro[a]}"/>')
        e = r[3]
        s.append(f'<text class="gl" x="{X[2030] + 12}" y="{gy(e["売上_万"]) - 2:.1f}" fill="{iro[a]}">{a}</text>')
        s.append(f'<text class="gv" x="{X[2030] + 12}" y="{gy(e["売上_万"]) + 12:.1f}">'
                 f'{e["売上_万"]:,}万</text>')
    for y, v in ((2026, 1700), (2027, 2600)):
        s.append(f'<circle cx="{X[y]}" cy="{gy(v):.1f}" r="5" fill="#fff" stroke="#0a5c50" stroke-width="2.5"/>')
        s.append(f'<text class="gv" x="{X[y]}" y="{gy(v) - 11:.1f}" text-anchor="middle">{v:,}万</text>')
    for y in X:
        s.append(f'<text class="gm" x="{X[y]}" y="{gy(0) + 20:.1f}" text-anchor="middle">{y}</text>')
    s.append(f'<text class="gm" x="{X[2026]}" y="{gy(0) + 34:.1f}" text-anchor="middle">見込み</text>')
    s.append(f'<text class="gm" x="{X[2027]}" y="{gy(0) + 34:.1f}" text-anchor="middle">計画</text>')
    s.append('</svg>')
    return '\n'.join(s)


# ---------------------------------------------------------------
HTML = """<meta charset="utf-8">
<title>2027年の計画（社内用）</title>
<style>
@page { size: A4 portrait; margin: 15mm 13mm 14mm; }
* { box-sizing: border-box; }
html { font-size: 10.5pt; }
body {
  font-family: "IPAPGothic","IPAGothic",sans-serif;
  color: #20302d; line-height: 1.75; margin: 0;
  -webkit-print-color-adjust: exact; print-color-adjust: exact;
}
h1,h2,h3 { line-height: 1.45; margin: 0; }
p { margin: 0 0 0.85em; }
strong { font-weight: bold; }
.sec { page-break-before: always; }
.nobreak { page-break-inside: avoid; }

/* 表紙 */
.hyoushi { height: 246mm; display: flex; flex-direction: column; justify-content: center; }
.hyoushi .kaisha { font-size: 10pt; letter-spacing: .28em; color: #5c6d69; }
.hyoushi h1 { font-size: 30pt; margin: 14px 0 0; letter-spacing: .04em; }
.hyoushi .sub { font-size: 13pt; color: #3d4f4b; margin-top: 10px; }
.hyoushi .rule { height: 3px; background: #0a5c50; width: 74px; margin: 26px 0; }
.hyoushi .meta { font-size: 9.5pt; color: #5c6d69; line-height: 2; }
.hyoushi .box { border: 1px solid #c9d4d0; padding: 16px 20px; margin-top: 30px; background: #f4f7f5; }
.hyoushi .box b { font-size: 12pt; }

/* 見出し */
h2 { font-size: 16pt; border-bottom: 2.5px solid #0a5c50; padding-bottom: 6px; margin-bottom: 16px; }
h2 .no { font-size: 10pt; color: #0a5c50; letter-spacing: .12em; display: block; margin-bottom: 2px; }
h3 { font-size: 12pt; margin: 20px 0 8px; color: #0a5c50; }
h4 { font-size: 10.5pt; margin: 14px 0 4px; }

/* 本文 */
.lead { font-size: 12pt; line-height: 1.85; }
.hikari { background: linear-gradient(transparent 62%, #b8e4dc 62%); font-weight: bold; }

/* 箱 */
.box { border: 1px solid #c9d4d0; background: #f4f7f5; padding: 12px 16px; margin: 14px 0; }
.box.kiiro { background: #fdf6e6; border-color: #e3d3a8; }
.box.aka { background: #fbeeec; border-color: #e8c4be; }
.box p:last-child { margin-bottom: 0; }
.box .midashi { font-weight: bold; margin-bottom: 4px; }

/* 表 */
table { border-collapse: collapse; width: 100%; margin: 10px 0 4px; }
th, td { border: 1px solid #d5ded9; padding: 3px 5px; text-align: right; }
th { background: #eef3f0; font-weight: bold; text-align: center; }
td:first-child, th.k { text-align: left; }
table.pl { font-size: 7.1pt; }
table.pl th.k { width: 30%; background: #f6f9f7; font-weight: normal; }
table.pl tr.b th.k, table.pl tr.b td { font-weight: bold; background: #eef3f0; }
table.pl th.q, table.pl td.q { background: #e3efec; }
table.pl tr.b th.q, table.pl tr.b td.q { background: #d2e6e1; }
table.pl .qm { font-size: 5.6pt; font-weight: normal; color: #0a5c50; }
table.pl td.t, table.pl th.t { background: #e8ede9; font-weight: bold; }
table.sum { font-size: 9pt; }
table.sum tr.b th, table.sum tr.b td { background: #eef3f0; font-weight: bold; }
table.futsu { font-size: 9.2pt; }
table.futsu td:first-child, table.futsu th:first-child { text-align: left; }
.neg { color: #c0392b; font-weight: bold; }

/* グラフ */
svg.graph { width: 100%; height: auto; display: block; margin: 8px 0 4px; }
.gt { font-size: 9px; fill: #5c6d69; font-family: "IPAPGothic",sans-serif; }
.ga { font-size: 8px; fill: #8a9a95; font-family: "IPAPGothic",sans-serif; }
.gm { font-size: 9px; fill: #5c6d69; font-family: "IPAPGothic",sans-serif; }
.gl { font-size: 10px; font-weight: bold; font-family: "IPAPGothic",sans-serif; }
.gv { font-size: 8.5px; fill: #20302d; font-family: "IPAPGothic",sans-serif; }
.gg { stroke: #e2e9e5; stroke-width: 1; }
.gx { stroke: #9fb0ab; stroke-width: 1.2; }

/* リスト */
ul, ol { margin: 6px 0 10px; padding-left: 1.4em; }
li { margin-bottom: 5px; }
.kome { font-size: 9pt; color: #5c6d69; }
.step { display: flex; gap: 10px; margin-bottom: 8px; }
.step .n { flex: none; width: 22px; height: 22px; border-radius: 50%; background: #0a5c50;
           color: #fff; font-size: 9pt; text-align: center; line-height: 22px; font-weight: bold; }
/* 和真に約束する数値 */
.yakusoku { margin-top: 22px; border: 2.5px solid #0a5c50; padding: 16px 20px 12px; background: #f4f7f5; }
.yakusoku .yh { font-size: 13.5pt; font-weight: bold; color: #0a5c50; letter-spacing: .04em;
                border-bottom: 1px solid #bfd2cc; padding-bottom: 8px; margin-bottom: 12px; }
.yakusoku .yblk { margin-bottom: 12px; }
.yakusoku .ydate { font-weight: bold; font-size: 11pt; margin-bottom: 2px; }
.yakusoku ul { margin: 2px 0 0; padding-left: 1.5em; }
.yakusoku li { margin-bottom: 2px; }
.yakusoku li b { font-size: 11.5pt; }

footer { margin-top: 26px; padding-top: 8px; border-top: 1px solid #d5ded9;
         font-size: 8.5pt; color: #5c6d69; }
</style>

<div class="hyoushi">
  <div class="kaisha">ONE HITTER　ワンヒッター株式会社</div>
  <h1>2027年の計画</h1>
  <div class="sub">売上 2,600万円 ／ 経常利益 507万円</div>
  <div class="rule"></div>
  <div class="meta">
    社内用　―　和真 へ<br>
    2026年9月14日　作成：佐々木<br>
    ※この資料の数字は当面この前提で動く。<b>下方修正はしない。</b>
  </div>
  <div class="box">
    <b>この資料で伝えたいこと</b>
    <p style="margin-top:8px">
      来年から会社のスケールを上げる。人を1人増やす。<br>
      そのぶん固定費が年600万増えるから、売上を5割伸ばしてようやく利益が今年と同じになる。<br>
      <span class="hikari">増やすべきは現場の頑張りじゃなくて、仕事が入ってくる入口のほうだ。</span>
    </p>
  </div>
</div>

<div class="sec">
<h2><span class="no">1</span>いまの会社の状態</h2>

<p class="lead">まず、いまどうなっているかを共有しておきたい。</p>

<p>売上の伸びは、こうなっている。</p>

<table class="futsu nobreak">
<thead><tr><th>年</th><th>件数</th><th>売上</th><th>平均単価</th><th>前年比</th></tr></thead>
<tbody>
<tr><td>2023年</td><td>320</td><td>11,120,782</td><td>34,752</td><td>―</td></tr>
<tr><td>2024年</td><td>408</td><td>12,949,587</td><td>31,739</td><td>+16.4%</td></tr>
<tr><td>2025年</td><td>444</td><td>15,660,628</td><td>35,271</td><td>+20.9%</td></tr>
<tr><td>2026年（見込み）</td><td>約469</td><td><b>17,000,000</b></td><td>約36,250</td><td><b>+8.6%</b></td></tr>
</tbody></table>

<p>2023年が+16%、2024年が+21%で伸びていた。2026年は+8.6%で終わる見込みだ。予算は2,000万で置いていたから、達成率でいうと8割5分。<strong>伸び率は落ちている。</strong></p>

<p>ただ、止まった理由ははっきりしている。そして直せる。</p>

<div class="box aka nobreak">
<div class="midashi">原因は現場じゃない。入口がないことだ。</div>
<p>2026年の9〜12月に入っている受注37件のうち、<strong>73%は和真が現場で取った次回予約</strong>だ。HP・LINE・SMS・地図検索から来た受注は、この4か月で<strong>ゼロ</strong>。</p>
<p>つまり会社の売上が、和真が目の前のお客様に声をかけるかどうかだけで決まっている。それで回っているのは正直すごいことだけど、これ以上は伸びない。和真の1日は24時間しかないから。</p>
</div>

<p>一方で、<strong>枠は空いている。</strong>所要時間と移動時間から計算し直したら、稼働率はピークの6月でも65%、普通の月は20〜50%だった。9〜12月だけで<strong>約940時間、セットにして188件分</strong>が空いたままになっている。</p>

<p><span class="hikari">受けられないんじゃなくて、来ていない。</span>だから来年は、入口を作るところに金と人を突っ込む。</p>

<h3>それと、お客様は既に957人いる</h3>

<table class="futsu nobreak">
<thead><tr><th>　</th><th>人数／金額</th><th>　</th><th>人数</th></tr></thead>
<tbody>
<tr><td>台帳のお客様</td><td>957名</td><td>12か月以上ご無沙汰</td><td>583名</td></tr>
<tr><td>総受注額</td><td>52,300,292円</td><td>換気扇をまだ頼んでいない</td><td>807名</td></tr>
<tr><td>平均LTV</td><td>54,650円</td><td>浴室をまだ頼んでいない</td><td>780名</td></tr>
<tr><td>2回以上ご利用</td><td>25.0%</td><td>前回が9〜12月の方</td><td>253名</td></tr>
</tbody></table>

<p>エアコンだけ頼んだ621人の平均は38,345円、エアコンと水回り両方の75人は88,371円。<strong>1人あたり5万円の差</strong>がある。この差を621人に当てると3,100万円になる。来年の売上目標とほぼ同じ額が、既にいるお客様の中に眠っている。</p>
</div>

<div class="sec">
<h2><span class="no">2</span>2027年の目標</h2>

<div class="box nobreak">
<p style="font-size:14pt;line-height:1.6;margin-bottom:6px"><strong>売上 2,600万円　／　経常利益 507万円　／　施工 649件</strong></p>
<p class="kome" style="margin:0">2026年の見込み（1,700万円）から +53%。</p>
</div>

<p>「+53%も伸ばして、利益は今年とほとんど変わらないのか」と思うはずだ。<strong>そのとおりだ。</strong>理由は、来年から固定費が年600万円増えるから。増えた売上は、ほぼそのまま人と協力業者に出ていく。</p>

<table class="futsu nobreak">
<thead><tr><th>新しく増える固定費</th><th>年額</th><th>中身</th></tr></thead>
<tbody>
<tr><td>和真の報酬</td><td>+168万</td><td>今年9月分から固定給40万＋プール10万＝月50万（年600万）。前の歩合（経常利益×45%）だと今年は432万</td></tr>
<tr><td>正社員1名の給与</td><td>320万</td><td>3月入社。試用期間6か月は月30万、9月から35万</td></tr>
<tr><td>その社会保険（会社負担）</td><td>48万</td><td>―</td></tr>
<tr><td>採用費・装備</td><td>50万</td><td>1〜2月に出る</td></tr>
<tr class="b"><td><b>合計</b></td><td><b>約586万</b></td><td>売上に関係なく毎月出ていく</td></tr>
</tbody></table>

<p>この約590万が先に出ていくので、売上がそれを超えて伸びないと利益は減る。計算するとこうなる。</p>

<table class="futsu nobreak">
<thead><tr><th>　</th><th>必要な売上</th></tr></thead>
<tbody>
<tr><td>赤字にならない最低ライン（損益分岐点）</td><td><b>約1,980万円</b></td></tr>
<tr><td>2026年と同じ利益（約528万円）を残すライン</td><td><b>約2,630万円</b></td></tr>
<tr><td><b>2027年の目標</b></td><td><b>2,600万円</b></td></tr>
</tbody></table>

<div class="box kiiro nobreak">
<div class="midashi">だから 2,600万は「安全な目標」じゃない。</div>
<p><strong>2,600万は、今年と同じ利益を出すのにギリギリ届かない線</strong>だ（経常利益 507万に対して、今年の水準は528万）。ここを下回ると、去年より稼いだのに利益は減る、という年になる。</p>
<p style="margin-bottom:0">利益をきちんと増やすには、<strong>2,630万を超えるか、協力業者の支払条件を詰めるか</strong>のどちらかが要る。後者については §4 に実績を書いた。</p>
</div>

<h3>届かなかったら、どうなるか</h3>

<p>2,600万に届かず、来年も今年と同じやり方のままだと、だいたい2,000万で終わる。そのときの数字も並べておく。</p>

<table class="futsu nobreak">
<thead><tr><th>　</th><th>2027年の目標</th><th>今と同じやり方だと</th></tr></thead>
<tbody>
<tr><td>売上</td><td><b>2,600万</b></td><td>2,000万</td></tr>
<tr><td>施工件数</td><td><b>649件</b></td><td>513件</td></tr>
<tr><td>平均単価</td><td><b>40,062円</b></td><td>38,986円</td></tr>
<tr><td>経常利益</td><td><b>507万</b></td><td>153万</td></tr>
<tr><td>2026年（528万）との差</td><td>▲21万</td><td class="neg">▲375万</td></tr>
<tr><td>赤字になる月</td><td>2月だけ</td><td class="neg">2月・8月・9月・12月</td></tr>
</tbody></table>

<p>2,000万でも黒字ではある。ただし<strong>利益は今年より375万減って、年に4か月が赤字月になる。</strong>そうなったら固定費を削りにいくことになる（新しい人の入社を遅らせる、HP関連費を切る、など）。<span class="hikari">やり方を変えないと、人を増やしたぶんだけ苦しくなる年になる。</span></p>
</div>

<div class="sec">
<h2><span class="no">3</span>月ごとの数字</h2>

<p>目標の2,600万を、月に割ったものが下の表だ。<strong>四半期末（3月・6月・9月・12月）は色を変えてある。</strong>ここで数字を締めて、次の3か月のやり方を決める。</p>

__GRAPH__

<div class="box nobreak">
<div class="midashi">この表の読み方</div>
<ul style="margin-bottom:0">
<li><strong>2月が唯一の赤字月（▲4.2万）。</strong>これは毎年そうで、2026年の2月も経常利益は50,401円しかなかった。1〜2月は年間でいちばん薄い。</li>
<li>ただし来年は、その薄い時期に新しい人件費が乗る。1〜2月を埋める手は<strong>ネット集客・早期予約・提携先からの受注</strong>の3つだ。<strong>単価の安い仕事で埋めにいくことはしない。</strong>薄利どころか逆鞘になる。</li>
<li><strong>6月が最大</strong>（売上340万・経常利益128万）。5〜7月と12月は繁忙期加算+3,300円が乗る。</li>
<li><strong>8月と9月が落ちる。</strong>エアコンが終わって年末が始まるまでの谷だ。ここを埋めるのが来年いちばんの課題。</li>
</ul>
</div>

<h3 style="page-break-before:always">1月〜6月</h3>
__PL_ZENHAN__

<h3>7月〜12月</h3>
__PL_KOUHAN__

<h3>四半期の締め（累計で見る）</h3>
__SHIHANKI__
</div>

<div class="sec">
<h2><span class="no">4</span>費目の中身</h2>

<p>上の表に出てくる費目を説明しておく。<strong>数字はぜんぶ2026年の実績から取っている。</strong>思いつきの数字は入っていない。</p>

<h3>人件費</h3>
<table class="futsu nobreak">
<thead><tr><th>　</th><th>金額</th><th>中身</th></tr></thead>
<tbody>
<tr><td>和真</td><td>月50万（年600万）</td><td>固定給40万＋プール10万。プールは3か月ごとに払い出す</td></tr>
<tr><td>新人</td><td>3〜8月 月30万<br>9〜12月 月35万</td><td>表の金額は社会保険の会社負担15%を乗せたもの。3月入社</td></tr>
<tr><td>補助（時給）</td><td>月1〜6万</td><td>2026年の通常月は約1万円。繁忙期に増やす</td></tr>
</tbody></table>

<h3>外注費（協力業者）</h3>
<p>協力業者3社に回す分。<strong>件数 × 16,900円</strong>で置いてある（平均売価26,000円の65%を支払う前提）。年間で約100件、169万円。繁忙期に増えて、1〜2月はゼロ。</p>
<p class="kome">※支払条件はまだ決めていない。歩合（売価の65%）／メニューごとの固定単価／日当の3案がある。計画上は歩合で置いた。決まったら数字を差し替える。</p>
<p class="kome">※実績でいうと、2026年8月に業務提携の大型案件で応援を入れたときは、<strong>売上1,841,740円に対して876,135円（47.6%）</strong>を払っている。計画で置いている65%より安く回せている。ここを実績どおりに詰められれば、利益はもう少し残る。</p>

<h3>広告費</h3>
<p>年80万。<strong>年額を先に決めるんじゃなくて、小さく試して結果が出たら上げる。</strong>
テスト（段0）は<strong>2026年12月末までに済ませておく</strong>ので、2027年は結果を持った状態で1月に入る。</p>
<table class="futsu nobreak">
<thead><tr><th>段</th><th>月額</th><th>時期</th><th>次の段へ上がる条件</th></tr></thead>
<tbody>
<tr><td>0　テスト</td><td>5万</td><td><b>2026年内に実施</b></td><td>―（結果を持って2027年に入る）</td></tr>
<tr><td>1</td><td>5〜6万</td><td>1〜4月</td><td>CPAが9,500円以下</td></tr>
<tr><td>2　繁忙期</td><td>12万</td><td>5〜7月</td><td>段1を2か月続けてクリア</td></tr>
<tr><td>3　年末</td><td>7万</td><td>10〜11月</td><td>段2をクリア</td></tr>
</tbody></table>
<p>CPA（1件取るのにかかる広告費）の上限は<strong>9,500円</strong>。この額の出どころはこうだ。</p>
<table class="futsu nobreak">
<tbody>
<tr><td style="width:56%">楽ラクーン経由の<b>1件あたりの平均売上（平均単価）</b></td><td>27,549円</td></tr>
<tr><td>そこにかかる手数料（実測で約35%）</td><td>約9,500円</td></tr>
</tbody></table>
<p>つまり<strong>いまも1件あたり9,500円を払って仕事を買っている。</strong>広告で同じ9,500円以内で1件取れるなら、そちらのほうが得だという意味になる。しかも楽ラクーンのお客様は100人に2人しか戻ってこないが、自社で獲ったお客様は連絡先がうちの資産になる。<strong>月のCPAが9,500円を超えたら、その月で止める。</strong></p>
<p class="kome">※Facebook広告は<strong>今後やる。</strong>いまは優先順位を下げているだけだ。前にやったとき（CPC95円・1件6,000円）は、やり方がすべて杜撰だった。作り直して試す。チラシの単独配布はしない（週2,000枚で反応0）。</p>

<h3>ロイヤリティ</h3>
<p>本舗経由の売上にかかる分と、毎月固定で出る50,050円。2026年は年間で約213万円出ている。<strong>本舗の比率を31.7%から22%に下げる</strong>ので、売上が6割伸びてもロイヤリティはあまり増えない設計にしてある。</p>
<p class="kome">※自社（ONE HITTER）の平均単価は52,374円、本舗経由は28,176円で1.86倍の差がある。そのうえ本舗にはロイヤリティがかかる。だから本舗の件数を減らすんじゃなく、自社の件数を増やして比率を下げる。本舗のお客様への営業は、これまでどおり「おそうじ本舗」として行う。</p>

<h3>固定経費と変動経費</h3>
<p><strong>固定経費は月159,708円。</strong>賠償保険43,760／駐車場21,000／HPローン22,000／HITOWA HPC利用料22,000／日新火災18,050／佐々木経費10,000／通信費8,470／マネーフォワード6,578／HITOWAサイト保守4,400／CANVA 1,800／HITOWAサポート1,650。</p>
<p><strong>変動経費は売上の6.8%。</strong>ガソリン・コインパーキング・紹介料・消耗品など。2026年の実績から出した。</p>
<p><strong>融資返済は月38,059円</strong>で固定。</p>

<div class="box kiiro nobreak">
<div class="midashi">HP関連費について、ひとつ言っておく</div>
<p>HPローン22,000＋HITOWA HPC利用料22,000＋サイト保守4,400で、<strong>月48,400円、年58万円</strong>払っている。それに対してHP経由の売上は<strong>2026年で年63,100円（4件）</strong>だ。ほぼ丸々赤字になっている。</p>
<p>来年これを黒字にできなければ、契約そのものを見直す。</p>
</div>
</div>

<div class="sec">
<h2><span class="no">5</span>どこから売上を作るか</h2>

<p>流入経路を4つのブロックに分けた。</p>

<table class="futsu nobreak">
<thead><tr><th>ブロック</th><th>2026年</th><th>2027年</th><th>差</th></tr></thead>
<tbody>
<tr><td>① 自社リピート資産（リピート・早期予約・紹介・定期便）</td><td>617万</td><td>850万</td><td>+233万</td></tr>
<tr><td>② 法人・提携（業務提携・営業・入札）</td><td>657万</td><td>840万</td><td>+183万</td></tr>
<tr><td>③ マッチングサイト（楽ラクーン・スケジュールマッチング）</td><td>390万</td><td>390万</td><td><b>据え置き</b></td></tr>
<tr class="b"><td>④ <b>自社ネット新規</b>（LP・SNS・地図検索・アフィリエイト・LINE/SMS再販）</td><td><b>13万</b></td><td><b>500万</b></td><td><b>+487万</b></td></tr>
<tr><td>⑤ その他（チラシほか）</td><td>21万</td><td>20万</td><td>―</td></tr>
<tr class="b"><td>合計</td><td>1,698万</td><td>2,600万</td><td>+902万</td></tr>
</tbody></table>

<p><span class="hikari">増える902万のうち、487万が④、183万が②だ。</span>この2つが動かなければ、他を全部うまくやっても目標には届かない。</p>

<h3>① 自社リピート資産　617万 → 850万</h3>
<p>台帳の957人がすべて。獲得コストはほぼゼロで、いちばん確実な伸びしろだ。</p>
<p><strong>和真にお願いしたいのはここだ。現場で「次の1箇所」を出すこと。</strong>換気扇をまだ頼んでいない人が807人、浴室が780人いる。エアコンで入ったお客様に、その場で水回りの話をする。それだけで1人あたりの金額が5万円変わる。</p>
<p class="kome">※1年以上前のお客様に電話するのは効かない（2025年12月に15件かけて成約0）。効くのは<strong>施工から7日以内</strong>に、LINEかSMSで、季節に合ったメニューを出すこと。そのぶんの文面と送信はこっちで作る。現場の手数は増やさない。</p>

<h3>② 法人・提携　657万 → 840万</h3>
<p>業務提携の平均単価は<strong>100,128円</strong>。個人の2倍以上で、LTVは186,272円、リピート率45%。全経路の中でいちばん強い。<strong>ここを伸ばす。</strong></p>

<p>提携先の実態を数え直した。<strong>台帳に載っているのは16社、実際に取引があるのは18社。ただし直近12か月に受注があるのは10社だけだ。</strong></p>

<table class="futsu nobreak">
<thead><tr><th>　</th><th>社数</th><th>中身</th></tr></thead>
<tbody>
<tr><td>取引実績のある先</td><td>18社</td><td>うち2社（インテリアエージェント・テック山口）は管理タブに登録漏れ</td></tr>
<tr><td><b>アクティブ（直近12か月に受注あり）</b></td><td><b>10社</b></td><td>レジェンド／才木工業／クラスリフォーム／タカラサービス／かさい電器／エコハウス／プレジャー／フォワード98／インテリアエージェント／テック山口</td></tr>
<tr><td>休眠（1年以上受注なし）</td><td>8社</td><td>青山リアルティー／ドア／山本組／小澤建設／エル・アップ／キノビト／はるか／本舗船堀店</td></tr>
<tr><td>2026年に10万円を超えた先</td><td class="neg">6社</td><td>アクティブ10社のうち4社は小口のまま</td></tr>
</tbody></table>

<div class="box aka nobreak">
<div class="midashi">問題は数じゃない。1社に寄りすぎていることだ。</div>
<p><strong>レジェンド様1社で、2026年の業務提携売上の62%。</strong>上位3社（レジェンド・タカラサービス・かさい電器）で77%。8月の大型案件1,683,000円（BREXA神奈川教習所・天カセ51台＋ロスナイ17台）もレジェンド様だ。</p>
<p><strong>レジェンド様はこのまま伸ばす。</strong>そこは動かさない。問題は、<strong>その横にもう2〜3社、同じ規模の先を作れていないこと</strong>だ。いまの形だとレジェンド様が1年止まった瞬間に年間売上の1割が消える。<span class="hikari">2027年は「アクティブな提携先を増やす」ことを命題にする。</span></p>
</div>

<table class="futsu nobreak">
<thead><tr><th>　</th><th>2026年</th><th>2027年の目標</th></tr></thead>
<tbody>
<tr><td>アクティブな提携先</td><td>10社</td><td><b>15社</b></td></tr>
<tr><td>年100万円以上の先</td><td>1社</td><td><b>4社</b></td></tr>
<tr><td>業務提携の受注金額（通年）</td><td>約584万</td><td><b>約750万</b></td></tr>
<tr><td>業務提携の受注件数（通年）</td><td>約58件</td><td><b>約75件</b></td></tr>
</tbody></table>

<p>やることは2つ。<strong>休眠している8社を起こすこと</strong>（一度取引があるので、冷たい営業じゃない）と、<strong>いまのアクティブ10社のうち小口の4社を育てること</strong>。あとは施設リスト291件への営業。冷たいテレアポはやらない（過去に40件→0アポ、140件→0アポ）。</p>

<p class="kome">※提携先の管理タブが2026年4月で止まっていて、5〜8月ぶんが転記されていなかった。いま直している。</p>

<div class="box nobreak">
<div class="midashi">和真から出てきた、いちばん良い話</div>
<p>台帳に「山口様」で入っている6/17と8/2の2件が、<strong>株式会社テック山口</strong>という法人で、提携先でもあると分かった。もともと<strong>本舗で出会ったお客様</strong>だ。それが自社の仕事になり、さらに法人の仕事を連れてきた。</p>
<p style="margin-bottom:0"><strong>本舗は新規を取りにいかない。でも本舗で出会った人を自社に連れてくるのは、別の話だ。</strong>自社の単価は本舗の1.86倍で、ロイヤリティもかからない。この筋道が実在することの証拠が出た。打診は和真がお客様の様子を見て判断することなので、こちらから一斉に何かを送ることはしない。<strong>やったら台帳の「ＯＨ打診」に記録だけ残してほしい。</strong>何が効いたか分からないと次に活かせない。</p>
</div>

<h3>③ 本舗案件　390万 → 390万（据え置き）</h3>
<p>楽ラクーンやスケジュールマッチング経由の案件のこと。<strong>2027年は今年と同じ数字に置く。自然に来る分だけ受けて、積極的には動かない。</strong></p>
<p>理由は、手数料を35%払って、戻ってくるのが<strong>100人に2人</strong>だけだからだ。数を増やしても資産にならない。②の提携先を伸ばすぶん、ここは据え置く。</p>
<p class="kome">※ただし<strong>本舗のお客様でも、リピーターは伸ばしたい。</strong>リピートで来てくれる分はロイヤリティも低く、うちに残る額が大きい。新規を取りにいかないだけで、一度来てくれた方には次も声をかける。</p>

<h3>④ 自社ネット新規　13万 → 500万</h3>
<p>次のページで詳しく書く。<strong>ここが2027年の勝負どころだ。</strong></p>
</div>

<div class="sec">
<h2><span class="no">6</span>自社ネット新規 ―― いま回していること</h2>

<p>これは<strong>今月（2026年9月）から動かし始めている。</strong>年末までこのまま回して、その結果を持って新年度に入る。</p>

<table class="futsu nobreak">
<thead><tr><th>いま動かしているもの</th><th>状態</th></tr></thead>
<tbody>
<tr><td>Instagram・Facebook</td><td>週5本の投稿を開始</td></tr>
<tr><td>公式サイトのブログ</td><td>週1本。3年止まっていたのを再開</td></tr>
<tr><td>Googleビジネスプロフィール（地図検索）</td><td>週1回の投稿＋クチコミ返信。★5.0・24件</td></tr>
<tr><td>年末大掃除LP</td><td>10月1日公開</td></tr>
<tr><td>アフィリエイト（レントラックス）</td><td>掲載開始。成果報酬3,000円</td></tr>
<tr><td>Web予約フォーム</td><td>稼働中（yoyaku.onehitter.jp）</td></tr>
<tr><td>公式LINE</td><td>友だち330人</td></tr>
<tr><td>既存客へのSMS再販</td><td>冬季の案内を配信中</td></tr>
<tr><td>読本サイト（赤ちゃん版・ペット版）</td><td>公開済み</td></tr>
<tr><td>無料点検</td><td>内視鏡カメラ購入済み。到着後に開始</td></tr>
</tbody></table>

<p>4か月回した結果がどうなるかは、正直わからない。だから<strong>3つのパターンで見ている。</strong></p>

<h3>パターンA　外れる（2027年1月時点で月2〜3件）</h3>
<p>SNSはフォロワーが増えただけで予約にならない。ブログは検索順位が上がりきらない。地図検索は表示回数が増えても予約にならない。アフィリエイトの送客ゼロ。</p>
<p><strong>→ その場合は広告で買いにいく。</strong>SNSは本数を減らして質に振る。ブログは続ける（検索で効くまで6〜12か月かかるので、4か月で判断しない）。</p>

<h3>パターンB　想定どおり（月5〜8件）</h3>
<p>年末LPから月4〜5件、地図検索から月2件、SMS再販とアフィリエイトで数件。</p>
<p><strong>→ 効いた導線だけに広告を足す。効かなかったものは止める。</strong>計画の2,600万は、このパターンBを前提に置いてある。</p>

<h3>パターンC　当たる（月10件以上）</h3>
<p>年末LP・地図検索・アフィリエイトが噛み合って、12月に月10件を超える。</p>
<p><strong>→ 1月から広告を一気に上げる。</strong>協力業者の契約も前倒しする。</p>

<div class="box nobreak">
<div class="midashi">どのパターンになっても、1月にやることは同じだ。</div>
<p>12月末までの4か月で、<strong>どの導線から何件来たかを1件ずつ記録に残す。</strong>予約フォームにもLPにも、どこから来たか分かる印（?src=）を付けてある。</p>
<p>効かなかったものも「効かなかった」という知見として残す。<span class="hikari">来年は当て推量じゃなく、記録から始める。</span>それが一番大事なところだ。</p>
</div>

<h3>今後の打ち手の一つ ―― ハウスクリーニングをギフトとして売る</h3>

<p>上に書いた10個が当面の中心で、それを回しきるのが先だ。そのうえで、来年のうちに<strong>もう1本、入口を足す。</strong></p>

<p><strong>ハウスクリーニングを贈り物として売る。</strong>これは和真も知ってのとおり、<strong>過去に何度かやろうとして、そのたび中途半端に終わってきた施策</strong>だ。今度は本気でやる。中途半端に終わった理由もはっきりしていて、<strong>片手間でやっていたからだ。</strong>来年は別ブランドとして切り出して、専用のページと商品設計を用意する。</p>

<p>出産祝い、新築祝い、引越し祝い、母の日、法人の福利厚生や株主優待。カタログギフトの1メニューとして載っていることはあるが、<strong>ここを専門にしてポジションを取っている会社はまだ見当たらない。</strong>いま獲りにいけば先頭に立てる。狙いは3つある。</p>

<div class="step"><div class="n">1</div><div>
<b>買う人と使う人が別だから、1件で新規の接点が2つできる。</b>しかも贈られた側は「体験したあと」でリピートの土俵に乗る。<b>獲得コストは贈り主が払ってくれている。</b>いまのマッチングサイトは1件9,500円払って、戻ってくるのは100人に2人。構造がまるごと逆になる。
</div></div>

<div class="step"><div class="n">2</div><div>
<b>先に金が入る。</b>ギフト券として売れば、代金を受け取ってから施工する。<b>1〜2月のいちばん薄い時期に前受けの現金が入る</b>のは大きい。上の月次表で2月が赤字になっているが、ここに効く。
</div></div>

<div class="step"><div class="n">3</div><div>
<b>材料はもう揃っている。</b>いま公開した読本（赤ちゃん版）は「子どもが生まれる家のエアコンを洗う」話で、出産祝いの導線としてそのまま使える。贈り物は「外さないこと」が全てだが、うちには★5.0が24件、満足度98.6%、ルミテスターのATP値42,194→409という証拠がある。
</div></div>

<p><strong>やるなら別ブランドにする。</strong>ONE HITTERは「エアコンクリーニングの会社」として探されるが、ギフトは探し方がまったく違う。同じ看板だと両方ぼやけるし、ギフトは「いくらの贈り物か」が主語になるので、セットで2〜3万円の商品設計になる。</p>

<p class="kome">※制約もある。施工できるのは東京・千葉・神奈川だけなので、購入画面で郵便番号を必ず確認する仕組みが要る。ギフト券の有効期限と表示のルール（資金決済法・景品表示法）も先に確認する。使われずに期限が切れた分を収益の柱にはしない。</p>

<p><strong>2027年の2,600万には入れていない。</strong>まずは上の10個をきちんと回す。ギフトはその横で準備を進めて、5月の母の日あたりで一度試す。<span class="hikari">今度こそ途中でやめない。</span></p>
</div>

<div class="sec">
<h2><span class="no">7</span>人を増やす</h2>

<h3>正社員1名を3月<u>まで</u>に入れる</h3>

<table class="futsu nobreak">
<thead><tr><th>時期</th><th>月給</th><th>状態</th></tr></thead>
<tbody>
<tr><td>2027年3月〜8月（6か月）</td><td><b>30万円</b></td><td>試用期間。<b>この6か月で独り立ちしてもらう</b></td></tr>
<tr><td>2027年9月〜</td><td><b>35万円</b></td><td>本採用</td></tr>
<tr><td>2028年3月（入社1年後）</td><td><b>40万円</b></td><td>ここを目指す</td></tr>
</tbody></table>

<p><strong>3月「まで」だ。</strong>計画上は3月入社で組んでいるが、いい人がいるなら前倒しする。早いぶんだけ繁忙期に効く。</p>

<h3>協力業者を1〜2月に決めて、3月から動かす</h3>

<p><strong>これまでに付き合いのある先が複数ある。</strong>ゼロから探すわけじゃない。その中から選ぶ。</p>

<p>位置づけは「安く回す先」じゃなくて、<strong>繁忙期に取りこぼさないための保険</strong>だ。5〜7月と年末は、うちの2人だけだと確実に断る日が出る。<span class="hikari">断った1件は二度と戻ってこない。</span></p>

<p>支払条件は3案ある。まだ決めていない。</p>
<table class="futsu nobreak">
<thead><tr><th>案</th><th>考え方</th><th>リスクを負うのは</th></tr></thead>
<tbody>
<tr><td>A　歩合</td><td>売価の65%を支払う</td><td>協力業者</td></tr>
<tr><td>B　固定単価</td><td>メニューごとに支払額を決める（平均55%くらい）</td><td>半々</td></tr>
<tr><td>C　日当</td><td>1日いくらで来てもらう</td><td><b>うち</b>（稼働を埋める責任を負う）</td></tr>
</tbody></table>
<p class="kome">※繁忙期だけC、それ以外はAというハイブリッドが実務的だと思っている。3社とも同じ条件にする必要もない。</p>

<div class="box nobreak">
<div class="midashi">和真に頼みたいのは、この3つだ。</div>
<div class="step"><div class="n">1</div><div>
<b>新人を6か月で独り立ちさせること。</b>6月には1人で現場を回せる状態にしたい。試用期間の6か月はそのために置いてある。
</div></div>
<div class="step"><div class="n">2</div><div>
<b>付き合いのある協力業者について、事業者ごとのレビューを俺に共有してほしい。</b>腕・段取り・人柄・どのメニューが得意か・どこまで任せられるか。<b>そのうえで報酬と条件設計の意見がほしい。</b>上の3案のどれが合うか、いくらなら受けてもらえるか、和真の感覚がいちばん正確だ。ここは俺が机の上で決めるより、和真の意見に頼りたい。
</div></div>
<div class="step"><div class="n">3</div><div>
<b>協力業者の品質を見ること。</b>★5.0が崩れたら、この資料に書いたギフトも広告もLPも、全部止まる。うちの一番の資産は、いまのところクチコミと満足度だ。<b>品質を維持する仕組みはこっちで作る。</b>施工チェックリストと写真報告の型は用意するから、和真には現場で見てもらう形にしたい。
</div></div>
</div>
</div>

<div class="sec">
<h2><span class="no">8</span>四半期ごとに見る数字</h2>

<p>締めは<strong>これまでどおり毎月やる。</strong>そのうえで、四半期末（3月末・6月末・9月末・12月末）は特に数字を突き合わせて、次の3か月のやり方を決める。</p>

<table class="futsu nobreak">
<thead><tr><th>累計（その時点まで）</th><th>3月末</th><th>6月末</th><th>9月末</th><th>12月末</th></tr></thead>
<tbody>
<tr><td>累計 売上</td><td>457万</td><td>1,312万</td><td>1,926万</td><td><b>2,600万</b></td></tr>
<tr><td>累計 件数</td><td>115件</td><td>324件</td><td>480件</td><td><b>649件</b></td></tr>
<tr><td>累計 経常利益</td><td>43万</td><td>293万</td><td>395万</td><td><b>507万</b></td></tr>
<tr><td>年計に対する進捗</td><td>18%</td><td>50%</td><td>74%</td><td><b>100%</b></td></tr>
</tbody></table>

<p>そのうえで、四半期末に確認するのは次の2つだけでいい。</p>

<div class="box nobreak">
<div class="step"><div class="n">1</div><div>
<b>自社ネット新規が、月に何件来たか。</b>（目標：月12件・年143件）<br>
<span class="kome">これが動かなければ、他を全部やっても届かない。逆にここが動けば他は後からついてくる。</span>
</div></div>
<div class="step"><div class="n">2</div><div>
<b>提携先からの受注金額と件数。</b>（2026年 約584万・約58件 → 2027年 <b>約750万・約75件</b>）<br>
<span class="kome">社数だけ数えても意味がない。アクティブ10社→15社を追いかけつつ、見るのは金額と件数だ。</span>
</div></div>
</div>

<h3>各四半期でやること</h3>
<table class="futsu nobreak">
<thead><tr><th>時期</th><th>やること</th></tr></thead>
<tbody>
<tr><td><b>1〜3月</b><br>年間の底</td><td>早期予約15%割引を既存のお客様へ。<b>休眠している提携先8社を起こす</b>。協力業者を決めて3月から稼働。<b>新人を3月までに入れる</b>。広告は12月までのテスト結果を受けて出す。ギフトブランドの立ち上げ準備</td></tr>
<tr><td><b>4〜6月</b><br>最大の稼ぎ時</td><td>エアコン需要期。5〜7月は繁忙期加算+3,300円。新人のOJTを回して<b>6月に独り立ち</b>。広告を月12万まで上げる。ピークは協力業者で吸収（本舗案件は回せないので自社案件のあふれ分）。母の日でギフトの初回テスト</td></tr>
<tr><td><b>7〜9月</b><br>谷を埋める</td><td>7月のあとに来る谷が最大の課題。<b>提携先を増やす（アクティブ10社→15社）</b>、施設リスト291件への営業。エアコン以外（換気扇・浴室）へのクロスセル。<b>同時2現場の体制をここで確立する</b></td></tr>
<tr><td><b>10〜12月</b><br>年末商戦</td><td>年末LPは10月1日に公開されている状態で入る（検索が立ち上がるのが10月中旬）。12月の繁忙期加算を「11月までに予約する理由」として使う。既存客への案内を3波。ギフトを年末・お歳暮で本格的に出す</td></tr>
</tbody></table>

<div class="yakusoku nobreak">
<div class="yh">★ 和真に約束する数値</div>

<div class="yblk">
<div class="ydate">▼ 2027年3月末時点</div>
<ul>
<li>累積売上額：<b>457万円</b></li>
<li>固定給＋プールを支払い続けたうえで<b>営業黒字</b></li>
<li><b>従業員1名追加</b>（試用期間）</li>
</ul>
</div>

<div class="yblk">
<div class="ydate">▼ 2027年9月末時点</div>
<ul>
<li>累積売上額：<b>1,926万円</b></li>
<li>累積経常利益額：<b>450万円</b></li>
<li><b>同時2現場施工可能体制の確立</b></li>
</ul>
</div>
</div>

<div class="sec">
<h2><span class="no">9</span>ここまでが厳しい話だ。その先を書いておく</h2>

<p class="lead">2027年の話は、正直きつい。売上を5割伸ばして、利益は横ばい。増えた分はほぼ全部、人と協力業者に出ていく。</p>

<p><strong>ただしそれは、2027年が「仕込みの年」だからだ。</strong></p>

<p>2027年にやることの本質は、その年の売上を作ることじゃない。<strong>自社で獲った新規のお客様を、翌年戻ってくる形で積み上げること</strong>だ。</p>

<div class="box nobreak">
<div class="midashi">なぜ2027年を超えると景色が変わるのか</div>
<p>自社ネット新規の143件は、その年だけ見れば500万にしかならない。だが<strong>自社で獲ったお客様は36%が翌年戻ってくる</strong>（マッチングサイト経由は100人に2人だけ）。しかも戻ってきたときの単価は<strong>1.13倍</strong>になる（一度うちを使った人は、次はセットで頼むから）。</p>
<p style="margin-bottom:0"><strong>つまり2027年に143件獲れば、2028年は何もしなくても約50件が戻ってくる。その上にまた新しい143件が乗る。</strong>これが2年、3年と続く。<span class="hikari">一度作った入口は、次の年も勝手に動く。</span></p>
</div>

<h3>2028〜2030年（2027年を達成できた場合）</h3>

<p>ロジックは2027年の計画から<strong>一切変えていない。</strong>変えたのは3つの前提だけだ ―― 自社で獲った新規のリピート率、自社ネット新規の月件数、アクティブな提携先の社数。<strong>本舗案件は3年とも390万で据え置き</strong>のままだ。</p>

__CHOUKI_GRAPH__

__CHOUKI_HYOU__

<h3>この表から読み取ってほしいこと</h3>

<div class="step"><div class="n">1</div><div>
<b>やがて、利益の伸びが売上の伸びを追い越す。</b>中と良は2028年から、保守的でも2029年からそうなる（保守的の2029年は売上+10%に対して利益+38%）。リピートのお客様は獲得コストがゼロだから、積み上がるほど利益率が上がる。2027年の507万に対して、2028年は586〜975万。
</div></div>

<div class="step"><div class="n">2</div><div>
<b>いちばん控えめに見ても、3年で経常利益は今年の2倍になる。</b>保守的（リピート率30%・ネット新規は月18件どまり・提携18社）でも2030年に売上3,502万・経常利益1,032万。2026年の528万に対して2.0倍だ。
</div></div>

<div class="step"><div class="n">3</div><div>
<b>利益が踊り場になる年がある。</b>中の2029年がそれだ ―― 売上は+23%なのに利益は+2%で止まる。<b>3人目を入れる年だからだ。</b>人件費は階段状に上がるので、増やした年は一度伸びが止まる（良も同じ年に増やすので鈍る）。<b>そこで焦らないこと。翌年に戻る</b>（中の2030年は利益+72%）。
</div></div>

<div class="step"><div class="n">4</div><div>
<b>本舗の比率が下がっていく。</b>2027年15% → 2030年で保守11%・中8%・良7%。伸ばさなくても、自社が伸びるぶん比率が下がる。単価もロイヤリティも有利な側の比重が自然に上がっていく。
</div></div>

<div class="box nobreak">
<div class="midashi">だから2027年なんだ。</div>
<p>2,600万を達成することの意味は、その年の利益じゃない。<strong>2028年以降の土台を作ることだ。</strong></p>
<ul style="margin-bottom:6px">
<li>2027年に獲った自社のお客様が、2028年・2029年と戻ってくる</li>
<li>2027年に立ち上げたネットの入口は、そのまま翌年も回り続ける</li>
<li>2027年に増やした提携先は、翌年も発注してくる（リピート率45%）</li>
</ul>
<p style="margin-bottom:0"><span class="hikari">一番きついのは最初の1年だ。そこを超えれば、数字は自分で伸び始める。</span><br>
<strong>和真と2人で、まずはそこまで行く。</strong></p>
</div>

<p class="kome" style="margin-top:14px">※この3年の数字は、2027年の計画を達成できた場合の見通しであって、約束の数値ではない。約束するのは前ページの2つだ。ただ、<strong>2027年を超えた先にこれがあるということは、先に共有しておきたかった。</strong></p>
</div>

<footer>
ワンヒッター株式会社　社内用　2026年9月14日<br>
数字の出どころ：2026年 売上/顧客情報管理（年間成績・支出/成績・分析_件数単価流入_v2・顧客管理台帳）。
計算は tools/plan2027.py。2026年の実績と突き合わせて、販売管理費で誤差0.11%まで合わせてある。<br>
※協力業者の支払条件、ギフト事業の詳細、広告の出稿先は未確定。決まり次第この資料を差し替える。<b>ただし上の数値目標は下方修正しない。</b>
</footer>
</div>
"""


def main():
    SHUTSURYOKU.mkdir(parents=True, exist_ok=True)
    html = (HTML
            .replace('__GRAPH__', graph())
            .replace('__PL_ZENHAN__', pl_hyou(1, 6))
            .replace('__PL_KOUHAN__', pl_hyou(7, 12, nenkei=True))
            .replace('__SHIHANKI__', shihanki_hyou())
            .replace('__CHOUKI_GRAPH__', chouki_graph())
            .replace('__CHOUKI_HYOU__', chouki_hyou()))
    h = SHUTSURYOKU / '2027年の計画_社内用.html'
    h.write_text(html, encoding='utf-8')
    print(f'HTML: {h}  ({len(html):,} 文字)')

    pdf = SHUTSURYOKU / '2027年の計画_社内用.pdf'
    if not os.path.exists(CHROMIUM):
        print(f'Chromium が見つからないのでPDFは作れない: {CHROMIUM}', file=sys.stderr)
        return
    r = subprocess.run([
        CHROMIUM, '--headless', '--no-sandbox', '--disable-gpu',
        '--no-pdf-header-footer', '--virtual-time-budget=8000',
        f'--print-to-pdf={pdf}', h.as_uri(),
    ], capture_output=True, text=True, timeout=180)
    if pdf.exists():
        print(f'PDF : {pdf}  ({pdf.stat().st_size:,} バイト)')
    else:
        print('PDF の生成に失敗した', file=sys.stderr)
        print(r.stderr[-2000:], file=sys.stderr)


if __name__ == '__main__':
    main()
