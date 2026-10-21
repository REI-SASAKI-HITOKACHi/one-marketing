#!/usr/bin/env python3
"""10/24 MTG でオーナーに見せる1枚：LPに残っている「聞かれていない但し書き」を、今と消した後で並べる（依頼 20261021-01-lp）。

    python3 tools/make-tadashi-ichiran.py      # docs/提示-但し書き一覧-1024.html と docs/img/但し書き一覧-1024MTG.png を作る

ページごとの有無は deploy/netlify（＝本番と同じ中身）から数える。配信はしない。
"""
import html
import os
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_HTML = ROOT / "docs" / "提示-但し書き一覧-1024.html"
OUT_PNG = ROOT / "docs" / "img" / "但し書き一覧-1024MTG.png"

PAGES = [
    ("aircon", "/aircon/", "エアコン入口（C対E）"),
    ("aircon-c", "/aircon-c/", "エアコン 学習版C"),
    ("aircon-e", "/aircon-e/", "エアコン 学習版E"),
    ("aircon-d", "/aircon-d/", "エアコン 学習版D"),
    ("aircon-b", "/aircon-b/", "エアコン 今の版B"),
    ("kabi", "/kabi/", "カビ特化"),
    ("mizumawari", "/mizumawari/", "水まわり 今の版"),
    ("mizumawari-b", "/mizumawari-b/", "水まわり 学習版"),
    ("nenmatsu", "/nenmatsu/", "年末 今の版"),
    ("nenmatsu-b", "/nenmatsu-b/", "年末 学習版"),
]

# 決める単位。mae＝この文の前にある文（そのまま残る）、ato＝後ろにある文（そのまま残る）
BUN = [
    dict(k="1", s="しつこい営業・訪問はいたしません", basho="画面下の固定バー（電話・LINE・予約ボタンの下の1行）",
         mae="", ato="", hoka="全LP共通の部品。消すとボタンの下の1行がなくなるだけ"),
    dict(k="2", s="品質を落として下げているわけではありません。", basho="「価格」の節",
         mae="間に会社が入らないぶん、紹介手数料が乗りません。その差をそのまま価格にしています。", ato=""),
    dict(k="3", s="当日になって、知らない会社の作業員が来ることはありません。", basho="「担当」の節",
         mae="ご予約を受けた私たち自身が伺います。", ato="ご連絡から作業まで、担当は変わりません。",
         hoka="見出し「伺うのは、ご予約を受けた私たちです」と、よくある質問「下請けに出しません」で同じことを言っている"),
    dict(k="4", s="不要な箇所を抱き合わせでおすすめすることはありません。", basho="よくある質問「1箇所だけでもお願いできますか？」の答え",
         mae="もちろんです。「必要なときに、必要な分だけ」が私たちの考え方です。", ato=""),
]
SANKOU = dict(s="訪問営業も電話営業もしていません。", basho="エアコン系の「価格」の節（2 の前の文）")


def body_text(p):
    h = p.read_text(encoding="utf-8")
    return re.sub(r'<(script|style)[^>]*>.*?</\1>', '', h, flags=re.S)


def ari():
    t = {}
    for d, _, _ in PAGES:
        b = body_text(ROOT / "deploy" / "netlify" / d / "index.html")
        t[d] = {x["k"]: x["s"] in b for x in BUN}
        t[d]["s"] = SANKOU["s"] in b
    return t


def e(s):
    return html.escape(s)


def build():
    t = ari()
    rows = []
    for x in BUN:
        n = sum(t[d][x["k"]] for d, _, _ in PAGES)
        ima = f'{e(x["mae"])}<mark>{e(x["s"])}</mark>{e(x["ato"])}'
        ato = f'{e(x["mae"])}{e(x["ato"])}' if (x["mae"] or x["ato"]) else '<span class="nashi">（この1行がなくなる）</span>'
        hoka = f'<p class="hoka">{e(x["hoka"])}</p>' if x.get("hoka") else ''
        rows.append(f'''<section class="bun">
  <div class="no">{x["k"]}</div>
  <div class="naka">
    <p class="basho">{e(x["basho"])}<span class="kazu">残っているページ {n}</span></p>
    <div class="ni"><div><b>今</b><p>{ima}</p></div><div><b>消した後</b><p>{ato}</p></div></div>
    {hoka}
  </div>
  <div class="kime"><span>消す</span><span>残す</span></div>
</section>''')
    head = "".join(f'<th><span>{e(lab)}</span><small>{e(u)}</small></th>' for _, u, lab in PAGES)
    body = []
    for x in BUN:
        tds = "".join(f'<td class="{"a" if t[d][x["k"]] else "n"}">{"●" if t[d][x["k"]] else "―"}</td>' for d, _, _ in PAGES)
        body.append(f'<tr><th>{x["k"]}</th>{tds}</tr>')
    tds = "".join(f'<td class="{"s" if t[d]["s"] else "n"}">{"○" if t[d]["s"] else "―"}</td>' for d, _, _ in PAGES)
    body.append(f'<tr class="sankou"><th>参考</th>{tds}</tr>')
    return f'''<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>但し書きの一覧（10/24 MTG）</title>
<style>
:root{{--ink:#1d2530;--sub:#5b6573;--rule:#d9dee5;--ground:#f6f7f9;--card:#fff;--mark:#fde2dc;--markline:#c2412d;--ok:#1f6f4a;}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--ground);color:var(--ink);font-family:"IPAGothic","IPAPGothic","Noto Sans CJK JP",sans-serif;}}
.page{{width:1200px;padding:36px 40px 32px;}}
h1{{font-size:28px;margin:0 0 6px;letter-spacing:.02em}}
.lead{{margin:0 0 4px;color:var(--sub);font-size:15px;line-height:1.7}}
.gen{{margin:0 0 22px;font-size:15px;line-height:1.7;background:var(--card);border:1px solid var(--rule);border-radius:8px;padding:10px 14px}}
.gen q{{font-weight:700}}
.bun{{display:grid;grid-template-columns:44px 1fr 108px;gap:14px;align-items:start;background:var(--card);border:1px solid var(--rule);border-radius:8px;padding:14px 16px;margin-bottom:10px}}
.no{{font-size:26px;font-weight:700;color:var(--markline);text-align:center;line-height:1.2}}
.basho{{margin:0 0 8px;font-size:14px;color:var(--sub);display:flex;justify-content:space-between}}
.kazu{{font-weight:700;color:var(--ink)}}
.ni{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
.ni b{{display:block;font-size:12.5px;color:var(--sub);margin-bottom:3px;letter-spacing:.08em}}
.ni p{{margin:0;font-size:16px;line-height:1.75}}
.ni>div+div p{{color:var(--ok)}}
mark{{background:var(--mark);color:var(--ink);text-decoration:line-through;text-decoration-color:var(--markline);text-decoration-thickness:2px;padding:0 2px}}
.nashi{{color:var(--sub)}}
.hoka{{margin:8px 0 0;font-size:13px;color:var(--sub)}}
.kime{{display:grid;gap:6px;padding-top:22px}}
.kime span{{border:1.5px solid var(--rule);border-radius:6px;text-align:center;padding:5px 0;font-size:15px;color:var(--sub)}}
.kime span::before{{content:"□ "}}
h2{{font-size:17px;margin:20px 0 8px}}
table{{border-collapse:collapse;width:100%;background:var(--card);font-size:14px}}
th,td{{border:1px solid var(--rule);padding:6px 4px;text-align:center}}
thead th span{{display:block;font-size:12.5px}}
thead th small{{display:block;color:var(--sub);font-weight:400;font-size:11px}}
tbody th{{width:56px;font-size:16px;color:var(--markline)}}
td.a{{color:var(--markline);font-size:16px}} td.n{{color:#b8bfc8}} td.s{{color:var(--sub)}}
tr.sankou th{{font-size:12px;color:var(--sub)}}
.chuu{{margin:10px 0 0;font-size:13px;color:var(--sub);line-height:1.7}}
</style></head><body><div class="page">
<h1>聞かれていない但し書き：残すか、消すか</h1>
<p class="lead">10/24 MTG・LP担当。お客様に聞かれていない否定や但し書きを、先回りして書いている文です。<b>4つとも「消す」か「残す」かを決めてください</b>。消しても前後の文はそのまま残ります。</p>
<p class="gen">きっかけ：10/18 オーナー <b>「あえて『ファンは付けたまま洗う』なんて表現しなくていいよ。…非常にAI感の強い表現だから学習してね」</b>　→ 10/20、/mizumawari-b/・/nenmatsu-b/ からは 2・3・4 を消して配信済み（CMO 判断）</p>
{"".join(rows)}
<h2>どのページに残っているか（● 残っている／― もう無い）</h2>
<table><thead><tr><th></th>{head}</tr></thead><tbody>{"".join(body)}</tbody></table>
<p class="chuu">参考 ○：{e(SANKOU["basho"])}「{e(SANKOU["s"])}」も同じ型の文です。2 と一緒に決めてもらえれば、同じ便で直します。<br>
エアコンの C と E には同じ文が入っているので、消しても C対E のテストの条件は変わりません。決まったら下書きを作り、配信は 10/23 の入札判定のあとにします。</p>
</div></body></html>'''


def main():
    OUT_HTML.write_text(build(), encoding="utf-8")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--no-sandbox", "--disable-dev-shm-usage"])
        pg = b.new_page(viewport={"width": 1200, "height": 800}, device_scale_factor=2)
        pg.goto(OUT_HTML.as_uri())
        pg.locator(".page").screenshot(path=str(OUT_PNG))
        b.close()
    print(f"書き出しました: {OUT_HTML.relative_to(ROOT)} / {OUT_PNG.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
