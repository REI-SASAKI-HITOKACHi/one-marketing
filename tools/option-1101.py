#!/usr/bin/env python3
"""予約ページに、エアコンのオプション（室外機セット・防カビコート）のチェック欄を足す下書き（依頼 20261101-01-lp）。

    python3 tools/option-1101.py      # deploy/machi/option/booking/index.html を作る（配信しない）

きっかけ：11/1 のネット予約で、ご要望欄に「室外機も」と書いて来られた（予約ページはオプションを「確認のお電話で」としていた）。

決めたこと（LP の見積り計算と同じ考え方）：
- エアコンを選んだときだけ、メニューの下に2つのチェック欄を出す。金額は data/prices.json（室外機セット 5,500円・防カビコート 3,300円）
- チェック1つで「エアコンの台数分」を足す（LP C・E の見積りと同じ。1台だけ付けたいときはご要望欄かお電話で）
- 足した分は概算合計に入れる。箇所には数えない（早期予約割引・繁忙期加算・ネット申込特典の判定は今のまま）
- 早期予約割引（11月10%）はエアコン本体の金額だけに掛かる＝今の kingaku() のまま。オプションは割り引かない
- 11月の作業は防カビコート1台分が無料（今の仕組み）。防カビにチェックしたら、無料の1台分を引いた残りの台数分だけ足す
- 「ご希望の内容」（スタッフに届く本文）に「＋室外機セット」等を足す。概算金額もこの合計で送る。Netlify の項目は増やさない
- 所要時間（空き枠の長さ）は変えない（オプションの作業時間の決まりが無いため。cmo に確認）
元にするのは本番と同じ予約ページ（cmo ブランチの lp/booking/index.html）。
"""
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
REF = "origin/claude/one-hitter-cmo-strategy-5qk4ux"
OUT = ROOT / "deploy" / "machi" / "option" / "booking" / "index.html"
MARK = 'id="opt-box"'


def git_show(path):
    return subprocess.run(["git", "-C", str(ROOT), "show", f"{REF}:{path}"],
                          capture_output=True, text=True, check=True).stdout


def kakaku():
    p = json.loads(git_show("data/prices.json"))
    d = {o["名称"]: o["価格"] for o in p["オプション"]}
    return d["エアコン 室外機セット"], d["エアコン 防カビコート"]


def edits(shitsu, bokabi):
    css = (
        '<style>.opt-box{margin:14px 0 4px;padding:14px 16px;border:1px solid var(--line);background:var(--surface);border-radius:10px;}'
        '.opt-box .opt-h{margin:0 0 8px;font-weight:700;font-size:15px;}'
        '.opt-box label{display:flex;gap:10px;align-items:flex-start;padding:10px 0;border-top:1px solid var(--line);cursor:pointer;}'
        '.opt-box label:first-of-type{border-top:0;}'
        '.opt-box input{width:22px;height:22px;margin:2px 0 0;flex:none;accent-color:var(--accent);}'
        '.opt-box b{display:block;}.opt-box small{display:block;color:var(--muted);font-size:13px;line-height:1.6;}'
        '.opt-box .opt-n{margin:8px 0 0;font-size:13px;color:var(--ink-soft);}</style>')
    box = (
        '      <div class="opt-box" id="opt-box" hidden>\n'
        '        <p class="opt-h">エアコンのオプション（ご希望の方だけ・税込）</p>\n'
        f'        <label><input type="checkbox" id="opt-shitsugaiki"><span><b>室外機セット　+{shitsu:,}円／台</b>'
        '<small>室外機もあわせてお掃除します。</small></span></label>\n'
        f'        <label><input type="checkbox" id="opt-bokabi"><span><b>防カビコート　+{bokabi:,}円／台</b>'
        '<small>お掃除のあと、カビが付きにくくなるコートを仕上げに塗ります。<span id="opt-bokabi-nov"></span></small></span></label>\n'
        '        <p class="opt-n" id="opt-n"></p>\n'
        '      </div>\n')
    js = """
  /* エアコンのオプション（tools/option-1101.py）。チェック1つでエアコンの台数分。箇所には数えない */
  S.opt = {shitsugaiki: {n: '室外機セット', gaku: %d}, bokabi: {n: '防カビコート', gaku: %d}};
  function acDaisu(){ return S.bokabi.taisho.reduce(function(a, n){ return a + (state.qty[n] || 0); }, 0); }
  function optOn(id){ var e = $('opt-' + id); return !!(e && e.checked && acDaisu() > 0); }
  /* 足す台数。防カビは11月の無料1台分を引いた残り */
  function optDai(id){
    if (!optOn(id)) { return 0; }
    var d = acDaisu();
    if (id === 'bokabi' && bokabiOf()) { d -= 1; }
    return d > 0 ? d : 0;
  }
  function optGaku(){ return optDai('shitsugaiki') * S.opt.shitsugaiki.gaku + optDai('bokabi') * S.opt.bokabi.gaku; }
  function drawOpts(){
    var d = acDaisu();
    $('opt-box').hidden = !d;
    $('opt-n').textContent = d >= 2 ? 'チェックすると、エアコン' + d + '台分になります。1台だけ付けたいときは、ご要望欄にお書きください。' : '';
    /* 11月の無料の案内は 12/1 0:00（日本時間）で消す */
    $('opt-bokabi-nov').textContent = Date.now() < Date.UTC(2026, 10, 30, 15) ? '11月の作業は1台分が無料です（チェックしなくても付きます）。' : '';
  }
""" % (shitsu, bokabi)
    return [
        # 1. 冒頭の説明
        ('オプション（防カビコート・室外機など）は、担当からの確認のお電話で承ります。',
         'エアコンの室外機セット・防カビコートは、メニューの下で選べます。そのほかのオプションは、担当からの確認のお電話で承ります。'),
        # 2. 欄（メニューの下・合計の上）
        ('      <div class="menu-list" id="menus"></div>\n',
         '      <div class="menu-list" id="menus"></div>\n' + box),
        # 3. CSS（浴室の内訳の style と同じく、本文中に置く）
        ('</style><div class="yk-box" id="yk-box">',
         '</style>' + css + '<div class="yk-box" id="yk-box">'),
        # 4. 関数（防カビの関数の後ろ）
        ("  function bokabiOf(){ return (state.date && state.date.slice(0, 7) === S.bokabi.tsuki && bokabiAircon()) ? S.bokabi.gaku : 0; }\n",
         "  function bokabiOf(){ return (state.date && state.date.slice(0, 7) === S.bokabi.tsuki && bokabiAircon()) ? S.bokabi.gaku : 0; }\n" + js),
        # 5. 合計に足す
        ("      kasan: kasan, gokei: shoukei - waribiki - netto + kasan,\n      bokabi: bokabiOf(),\n",
         "      kasan: kasan, gokei: shoukei - waribiki - netto + kasan + optGaku(),\n      bokabi: bokabiOf(),\n"
         "      shitsugaiki: optDai('shitsugaiki'), bokabiYuryo: optDai('bokabi'),\n"),
        # 6. 内訳の行（防カビ無料の行の前）
        ("    if (k.bokabi) {\n      h.push(ln('防カビコート（エアコン' + S.bokabi.kazu + '）', '<s>' + yen(k.bokabi) + '</s> 無料', 'off'));\n    }\n",
         "    if (k.shitsugaiki) {\n      h.push(ln('室外機セット（' + k.shitsugaiki + '台分）', '+' + yen(k.shitsugaiki * S.opt.shitsugaiki.gaku), 'add'));\n    }\n"
         "    if (k.bokabiYuryo) {\n      h.push(ln('防カビコート（' + (k.bokabi ? '無料分のほか ' : '') + k.bokabiYuryo + '台分）', '+' + yen(k.bokabiYuryo * S.opt.bokabi.gaku), 'add'));\n    }\n"
         "    if (k.bokabi) {\n      h.push(ln('防カビコート（エアコン' + S.bokabi.kazu + '）', '<s>' + yen(k.bokabi) + '</s> 無料', 'off'));\n    }\n"),
        # 7. 合計を描くたびに欄を出し直す
        ("  function drawTotal(){\n    var k = kingaku();\n",
         "  function drawTotal(){\n    drawOpts();\n    var k = kingaku();\n"),
        # 8. スタッフに届く「ご希望の内容」
        ("    return a.join('／') + (bokabiOf() ? '＋防カビコート無料（11月ネット予約・エアコン' + S.bokabi.kazu + '）' : '');\n",
         "    var o = '';\n"
         "    if (optDai('shitsugaiki')) { o += '＋室外機セット' + (optDai('shitsugaiki') > 1 ? ' ×' + optDai('shitsugaiki') : ''); }\n"
         "    if (optDai('bokabi')) { o += '＋防カビコート' + (bokabiOf() ? '（無料分のほか ' + optDai('bokabi') + '台）' : (optDai('bokabi') > 1 ? ' ×' + optDai('bokabi') : '')); }\n"
         "    return a.join('／') + o + (bokabiOf() ? '＋防カビコート無料（11月ネット予約・エアコン' + S.bokabi.kazu + '）' : '');\n"),
    ]


LISTEN = ("  Array.prototype.forEach.call(document.querySelectorAll('[data-back]'), function(b){\n",
          "  ['opt-shitsugaiki', 'opt-bokabi'].forEach(function(id){ $(id).addEventListener('change', drawTotal); });\n"
          "  Array.prototype.forEach.call(document.querySelectorAll('[data-back]'), function(b){\n")


def kaeru(s, old, new):
    n = s.count(old)
    if n != 1:
        sys.exit(f"想定と違う：{old[:60]!r} が {n} か所（1 か所のはず）。予約ページが変わった可能性。止めます")
    return s.replace(old, new)


def make(h, shitsu, bokabi):
    if MARK in h:
        return h
    for a, b in edits(shitsu, bokabi) + [LISTEN]:
        h = kaeru(h, a, b)
    return h


def main():
    shitsu, bokabi = kakaku()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(make(git_show("lp/booking/index.html"), shitsu, bokabi), encoding="utf-8")
    print(f"書き出しました: {OUT.relative_to(ROOT)}（室外機セット {shitsu:,}円・防カビコート {bokabi:,}円）")


if __name__ == "__main__":
    main()
