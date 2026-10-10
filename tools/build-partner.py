#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""提携先ごとの専用ご依頼ページ（lp/partner/<鍵>/index.html）を作る。

【なぜ】オーナー 2026-10-09「フォームは各社専用にして。手間を最小化するように気を付けて。
  あとその場で料金と空き枠を確認できるようにしたい」。
  - 会社名・担当者は最初から入っている（相手は入れない）。入れるのは 現場の住所・台数・日時 だけ
  - 台数を選ぶと、その場で目安の料金（税込）が出る。料金は docs/price-master.md の業務用・壁掛けの表と同じ計算
  - 空き枠は予約ページと同じ Apps Script（和真さんのカレンダーをその場で見る）から取る
  - URL は推測されにくい鍵つき（/partner/takara-7q2m/）。noindex

【料金の計算（price-master「業務用エアコンの台数割引」「複数台割引」）】
  台数はエアコン（業務用・壁掛け）の合計で段を決める。割引は全台に掛かる。
  業務用：1台 32,780／2〜10台 27,280／11〜20台 26,180／21〜50台 25,080（1台あたり・税込）
  壁掛けノーマル 10,780：5〜10台 −500／11〜20台 −1,000／21〜50台 −1,500（1台あたり）
  壁掛けお掃除機能付き 17,380：同じ段で −1,000／−1,500／−2,000
  室外機 6,050（オプション）。51台以上・フィルター清掃のみ・排水口の高圧洗浄はお見積り。
  繁忙期（5〜7月・12月）は 1台 +3,300。ただしエアコン5台超は加算なし（法人の決まり）。
  会社ごとの値引き率は COMPANIES の waribiki（既定 0。オーナーが決めたら入れる）。

【タカラサービス様は形が違う（第6回MTG 6-4 No.4・2026-10-10）】上部タブ2つ（①見積依頼 ②現調依頼）。
  中身は tools/partner_tabs.py。料金は data/partner-price/takara.json（タカラ様専用の料金表＝Drive「エアコン料金一覧表.pdf」
  2023-11-13 を 2026-10-10 に反映。お掃除機能付きはメーカー別、家庭用・業務用それぞれの台数で段）。高速代・移動時間は data/partner-area.json
  （tools/build-kousoku-ic.py がドラぷらから作る）。青山様は従来の1画面のまま。

【受け取り】Netlify フォーム "partner"（全社共通）。項目は partner_tabs.FORM_FIELDS で全社そろえる。通知メールが毎時点検で拾える。
【ご紹介カードの数え方】お客様が「カードを見た」と言ったら、提携先の担当者が「ご紹介カードを見たお客様」に
  チェック（任意・1タップ）→ フォームの「きっかけ＝ご紹介カード」で数える（print/partner-cards/cards.html の導線）。

  python3 tools/build-partner.py        # lp/partner/<鍵>/index.html を全社ぶん作る
  python3 tools/check-public-page.py lp/partner/*/index.html   # 配信前に必ず
"""
import json
import pathlib

import partner_tabs

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "lp" / "partner"

API = "https://script.google.com/macros/s/AKfycbzuuMGVICQPoLlUrFBarb1zAgi_kVdc1vDrRJoyhAJ_tvOG-eHnmTHDGWhuvix3E3_odQ/exec"
TEL = "080-8043-8259"

# 鍵は推測されにくい文字列にする（一覧からたどれないように）。変えるとURLが変わるので、送ったあとは変えない。
COMPANIES = {
    "takara-7q2m": {
        "kaisha": "株式会社タカラサービス", "tantou": "深堀",
        # 見積書の送り先のいつもの宛先（オーナー 2026-10-10）。先方が依頼時に追加でき、「追加分だけに送る」も選べる
        "mitsu_ate": "info@takara-co.jp",
        # 第6回MTG 6-4 No.4：上部タブ2つ（見積依頼／現調依頼）の形。料金は data/partner-price/takara.json が正。
        # タカラ様専用の料金表を 2026-10-10 に反映済み（takara.json の motoshiryou）。料金を変えるときは takara.json だけ直す。
        "katachi": "tabs", "ryokin": "data/partner-price/takara.json",
        "menus": ["gyomu", "normal", "robo", "shitsugaiki", "filter"],
        "waribiki": 0,
        "seikyu": "御社（これまでどおり）",
    },
    "aoyama-k4x9": {
        "kaisha": "青山リアルティー・アドバイザーズ株式会社", "tantou": "荒木",
        "menus": ["gyomu", "normal", "robo", "shitsugaiki", "drain"],
        "waribiki": 0,
        "seikyu": "御社（これまでどおり）",
    },
}

MENUS = {
    "gyomu":       {"n": "業務用エアコン（天井カセット・天吊り・床置き）", "kind": "gyomu", "m": 120},
    "normal":      {"n": "壁掛けエアコン（ノーマル）", "kind": "kabe", "t": 10780, "off": [500, 1000, 1500], "m": 60},
    "robo":        {"n": "壁掛けエアコン（お掃除機能付き）", "kind": "kabe", "t": 17380, "off": [1000, 1500, 2000], "m": 120},
    "shitsugaiki": {"n": "室外機の洗浄", "kind": "opt", "t": 6050, "m": 20},
    "filter":      {"n": "フィルター清掃のみ", "kind": "mitsumori", "m": 30},
    "drain":       {"n": "排水口・ドレンの高圧洗浄", "kind": "mitsumori", "m": 120, "unit": "か所"},
}
GYOMU = [(1, 1, 32780), (2, 10, 27280), (11, 20, 26180), (21, 50, 25080)]

CSS = """
:root{--ink:#0D3B5C;--paper:#F3F7F9;--surface:#fff;--text:#13232E;--text-2:#3C5262;--rule:#D7E1E7;
  --cta:#B72C0A;--cta-h:#8F2408;--aqua:#0C6B7F;--aqua-soft:#DDEDF1;color-scheme:light}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--text);font-family:"Noto Sans JP","Hiragino Sans","Yu Gothic UI",system-ui,sans-serif;
  font-size:16px;line-height:1.75;-webkit-text-size-adjust:100%}
.wrap{width:min(680px,100% - 32px);margin-inline:auto}
header{background:var(--ink);color:#EDF4F8;padding:24px 0 20px}
header .tag{font-size:13px;color:#A8C2D2;margin:0 0 4px}
header h1{font-size:21px;line-height:1.5;margin:0 0 6px}
header p{margin:0;font-size:14px;color:#D5E3EC}
main{padding:20px 0 4px}
.card{background:var(--surface);border:1px solid var(--rule);border-radius:10px;padding:18px 16px;margin:0 0 16px}
.card h2{font-size:17px;margin:0 0 10px;color:var(--ink)}
.step{display:inline-block;background:var(--ink);color:#fff;border-radius:50%;width:24px;height:24px;text-align:center;
  line-height:24px;font-size:13px;margin-right:6px}
label.f{display:block;font-weight:500;margin:12px 0 6px}
.req{font-size:11px;color:#fff;background:var(--cta);border-radius:3px;padding:0 6px;margin-left:6px;vertical-align:2px}
.opt{font-size:12px;color:var(--text-2);margin-left:6px;font-weight:400}
input[type=text],input[type=tel],textarea,select{width:100%;font:inherit;padding:10px 12px;border:1px solid #B4C5D0;border-radius:6px;background:#fff}
textarea{min-height:80px}
.row{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:10px 0;border-bottom:1px solid var(--rule)}
.row:last-child{border-bottom:0}
.row .nm{flex:1;font-size:15px}
.row .pr{display:block;font-size:12px;color:var(--text-2)}
.qty{display:flex;align-items:center;gap:6px}
.qty button{width:36px;height:36px;border-radius:50%;border:1px solid #B4C5D0;background:#fff;font-size:20px;line-height:1;cursor:pointer;color:var(--ink)}
.qty output{min-width:2.4em;text-align:center;font-weight:700}
.sum{background:var(--aqua-soft);border-radius:8px;padding:12px 14px;margin-top:12px}
.sum .big{font-size:24px;font-weight:700;color:var(--ink)}
.sum ul{margin:6px 0 0;padding-left:1.1em;font-size:14px}
.note{font-size:13px;color:var(--text-2)}
.days{display:grid;gap:10px}
.day .dl{font-weight:700;font-size:14px;margin:0 0 4px}
.day .we{color:#B72C0A}
.times{display:flex;flex-wrap:wrap;gap:6px}
.times button{border:1px solid #B4C5D0;background:#fff;border-radius:6px;padding:6px 10px;font:inherit;font-size:14px;cursor:pointer}
.times button.on{background:var(--ink);color:#fff;border-color:var(--ink)}
.more{margin-top:8px;background:none;border:0;color:var(--aqua);font:inherit;cursor:pointer;padding:0}
.pick{margin-top:8px;font-weight:700;color:var(--ink)}
button.send{display:block;width:100%;margin:16px 0 6px;padding:14px;font:inherit;font-weight:700;font-size:17px;color:#fff;background:var(--cta);border:0;border-radius:8px;cursor:pointer}
button.send:hover{background:var(--cta-h)}
.err{color:#B72C0A;font-size:14px;min-height:1em}
.hp{position:absolute;left:-9999px}
.chk{display:flex;align-items:center;gap:8px;margin:14px 0 0;font-size:15px;cursor:pointer}
.chk input{width:20px;height:20px;margin:0;accent-color:var(--ink)}
footer{border-top:1px solid var(--rule);padding:18px 0 28px;font-size:13px;color:var(--text-2)}
footer a{color:var(--aqua)}
"""

FOOTER = f"""<footer>
  <div class="wrap">
    <p><b>ワンヒッター株式会社</b>（代表取締役 佐々木 沙樹）<br>
      〒134-0081 東京都江戸川区北葛西5-14-11 クオーディア西葛西503<br>
      電話 <a href="tel:08080438259">{TEL}</a>（8:00〜20:00）<br>
      対応エリア：東京都・千葉県・神奈川県</p>
    <p><a href="https://lp.onehitter.jp/privacy/">個人情報の取扱いについて</a>　／　<a href="https://lp.onehitter.jp/tokushoho/">特定商取引法に基づく表記</a></p>
  </div>
</footer>"""

JS = r"""
(function(){
  var C = __CONF__;
  function $(id){ return document.getElementById(id); }
  function yen(n){ return n.toLocaleString('ja-JP') + '円'; }
  var q = {}; C.menus.forEach(function(k){ q[k] = 0; });
  var sel = { date: '', time: '', label: '' };

  function dan(n){ return n >= 21 ? 2 : n >= 11 ? 1 : n >= 5 ? 0 : -1; }
  function keisan(){
    var M = C.M, units = 0, lines = [], total = 0, mitsu = [], minutes = 0;
    C.menus.forEach(function(k){ var m = M[k]; if (m.kind === 'gyomu' || m.kind === 'kabe') { units += q[k]; } });
    var over = units > 50;
    var mon = sel.date ? parseInt(sel.date.slice(5, 7), 10) : 0;
    var hanbou = C.hanbou.indexOf(mon) >= 0 && units > 0 && units <= 5;
    C.menus.forEach(function(k){
      var m = M[k], n = q[k]; if (!n) { return; }
      minutes += m.m * n;
      if (m.kind === 'mitsumori') { mitsu.push(m.n + ' ' + n + (m.unit || '台')); return; }
      var tanka = 0;
      if (m.kind === 'gyomu') { C.gyomu.forEach(function(g){ if (units >= g[0] && units <= g[1]) { tanka = g[2]; } }); if (over) { tanka = C.gyomu[3][2]; } }
      else if (m.kind === 'kabe') { var d = dan(units); tanka = m.t - (d >= 0 ? m.off[d] : 0); }
      else { tanka = m.t; }
      if (hanbou && m.kind !== 'opt') { tanka += C.hanbouGaku; }
      var sub = tanka * n; total += sub;
      lines.push(m.n + '　' + yen(tanka) + ' × ' + n + (m.unit || '台') + ' ＝ ' + yen(sub));
    });
    var waribiki = C.waribiki ? Math.floor(total * C.waribiki / 100) : 0;
    return { units: units, lines: lines, total: total - waribiki, waribiki: waribiki, mitsu: mitsu, minutes: minutes, over: over, hanbou: hanbou };
  }

  function egakuSum(){
    var r = keisan(), box = $('sum');
    if (!r.lines.length && !r.mitsu.length) { box.innerHTML = '<p class="note">台数を選ぶと、目安の料金がここに出ます。</p>'; }
    else {
      var h = '';
      if (r.lines.length) { h += '<div>目安の料金（税込）</div><div class="big">' + yen(r.total) + '</div>'; }
      h += '<ul>' + r.lines.map(function(s){ return '<li>' + s + '</li>'; }).join('');
      if (r.waribiki) { h += '<li>提携先さま割引 −' + yen(r.waribiki) + '</li>'; }
      r.mitsu.forEach(function(s){ h += '<li>' + s + '：現地を確認してお見積り</li>'; });
      if (r.hanbou) { h += '<li>繁忙期（5〜7月・12月）のため 1台 +3,300円を含みます</li>'; }
      if (r.over) { h += '<li>51台以上は別途ご相談（表示は21〜50台の単価）</li>'; }
      h += '</ul><p class="note">エアコンの合計台数で単価の段が決まり、割引は全台に掛かります。駐車場代・高速代が掛かる現場は実費をいただく場合があります。</p>';
      box.innerHTML = h;
    }
    $('f-naiyou').value = C.menus.filter(function(k){ return q[k]; }).map(function(k){ return C.M[k].n + ' ' + q[k] + (C.M[k].unit || '台'); }).join('／');
    $('f-kingaku').value = r.lines.length ? yen(r.total) + (r.mitsu.length ? '＋お見積り分' : '') : (r.mitsu.length ? 'お見積り' : '');
    return r;
  }

  var lastMin = -1, slotsAll = [], miseru = 5;
  function bucket(min){ var b = [60,90,120,150,180,210,240,300,360,420,480]; for (var i = 0; i < b.length; i++) { if (min <= b[i]) { return b[i]; } } return 480; }
  function jsonp(url){
    return new Promise(function(res, rej){
      var name = '__cb' + Date.now() + Math.floor(Math.random() * 1000), sc = document.createElement('script');
      var t = setTimeout(function(){ owari(); rej(new Error('timeout')); }, 9000);
      function owari(){ clearTimeout(t); delete window[name]; if (sc.parentNode) { sc.parentNode.removeChild(sc); } }
      window[name] = function(d){ owari(); res(d); };
      sc.onerror = function(){ owari(); rej(new Error('network')); };
      sc.src = url + '&callback=' + name; document.body.appendChild(sc);
    });
  }
  function yomuWaku(){
    var r = keisan(), min = bucket(Math.max(60, r.minutes));
    if (min === lastMin) { return; }
    lastMin = min;
    var box = $('slots');
    box.innerHTML = '<p class="note">空き状況を確認しています…</p>';
    jsonp(C.api + '?action=slots&minutes=' + min).then(function(d){
      if (!d || !d.ok) { throw new Error('ng'); }
      slotsAll = d.slots || []; miseru = 5; egakuWaku(r.minutes > 480);
    }).catch(function(){
      box.innerHTML = '<p class="note">空き状況をうまく取得できませんでした。ご希望の日時を下の欄にお書きください（お電話 ' + C.tel + ' でも承ります）。</p>';
    });
  }
  function egakuWaku(nagai){
    var box = $('slots'); box.innerHTML = '';
    if (nagai) { box.innerHTML = '<p class="note">1日で終わらない量です。開始日をお選びいただければ、残りの日程はご相談します。</p>'; }
    if (!slotsAll.length) { box.innerHTML += '<p class="note">3週間先まで空きがありません。ご希望の日時を下の欄にお書きください。</p>'; return; }
    var w = document.createElement('div'); w.className = 'days';
    slotsAll.slice(0, miseru).forEach(function(d){
      var el = document.createElement('div'); el.className = 'day';
      el.innerHTML = '<div class="dl">' + (/（[土日]）/.test(d.label) ? '<span class="we">' + d.label + '</span>' : d.label) + '</div>';
      var tl = document.createElement('div'); tl.className = 'times';
      d.times.forEach(function(t){
        var b = document.createElement('button'); b.type = 'button'; b.textContent = t;
        if (sel.date === d.date && sel.time === t) { b.className = 'on'; }
        b.onclick = function(){ sel = { date: d.date, time: t, label: d.label }; $('f-hi').value = d.label + ' ' + t + '〜'; egakuSum(); egakuWaku(nagai); $('err').textContent = ''; };
        tl.appendChild(b);
      });
      el.appendChild(tl); w.appendChild(el);
    });
    box.appendChild(w);
    if (slotsAll.length > miseru) { var m = document.createElement('button'); m.type = 'button'; m.className = 'more'; m.textContent = 'ほかの日も見る'; m.onclick = function(){ miseru += 7; egakuWaku(nagai); }; box.appendChild(m); }
    if (sel.date) { var p = document.createElement('p'); p.className = 'pick'; p.textContent = '選んだ日時：' + sel.label + ' ' + sel.time + '〜'; box.appendChild(p); }
  }

  C.menus.forEach(function(k){
    var out = $('q-' + k);
    function set(v){ q[k] = Math.max(0, Math.min(99, v)); out.value = q[k]; egakuSum(); yomuWaku(); }
    $('m-' + k).onclick = function(){ set(q[k] - 1); };
    $('p-' + k).onclick = function(){ set(q[k] + 1); };
  });
  egakuSum(); yomuWaku();

  $('form').addEventListener('submit', function(e){
    var r = keisan();
    if (!$('f-genba').value.trim()) { e.preventDefault(); $('err').textContent = '現場の住所を入れてください（区・町名まででも結構です）。'; return; }
    if (!r.lines.length && !r.mitsu.length) { e.preventDefault(); $('err').textContent = 'ご依頼の内容（台数）を選んでください。'; return; }
    if (!sel.date && !$('f-biko').value.trim()) { e.preventDefault(); $('err').textContent = '日時を選ぶか、ご希望の日時を下の欄にお書きください。'; return; }
    $('f-sentaku').value = 'ブラウザから送信';
  });
})();
"""


# Netlify フォーム "partner" の項目を全社でそろえる（partner_tabs.FORM_FIELDS）。1画面ページに無い項目は空の隠しで置く。
_ICHIGAMEN = {"種別", "提携先", "ご担当", "ページ", "請求先", "内容", "目安金額", "希望日時", "送信元の確認",
              "現場の住所", "現場のお名前", "きっかけ", "ご要望"}
KYOUTSUU_HIDDEN = "\n  ".join(f'<input type="hidden" name="{f}" value="">' for f in partner_tabs.FORM_FIELDS if f not in _ICHIGAMEN)


def page(key: str, c: dict) -> str:
    if c.get("katachi") == "tabs":
        price = json.loads((ROOT / c["ryokin"]).read_text(encoding="utf-8"))
        area = json.loads((ROOT / "data" / "partner-area.json").read_text(encoding="utf-8"))
        return partner_tabs.page(key, c, price, area, API, TEL, FOOTER)
    conf = {
        "menus": c["menus"], "M": {k: MENUS[k] for k in c["menus"]}, "gyomu": GYOMU,
        "hanbou": [5, 6, 7, 12], "hanbouGaku": 3300, "waribiki": c.get("waribiki", 0),
        "api": API, "tel": TEL,
    }
    rows = []
    for k in c["menus"]:
        m = MENUS[k]
        if m["kind"] == "gyomu":
            pr = "1台 32,780円／2台以上 1台 27,280円〜"
        elif m["kind"] == "kabe":
            pr = f"1台 {m['t']:,}円（5台以上は割引）"
        elif m["kind"] == "opt":
            pr = f"1台 {m['t']:,}円"
        else:
            pr = "現地を確認してお見積り"
        rows.append(f"""<div class="row"><span class="nm">{m['n']}<span class="pr">{pr}</span></span>
      <span class="qty"><button type="button" id="m-{k}" aria-label="減らす">−</button><output id="q-{k}">0</output><button type="button" id="p-{k}" aria-label="増やす">＋</button></span></div>""")
    js = JS.replace("__CONF__", json.dumps(conf, ensure_ascii=False))
    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>{c['kaisha']}様 専用フォーム｜ご依頼｜ワンヒッター株式会社</title>
<!-- tools/build-partner.py で生成。手で直さない。 -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
<header>
  <div class="wrap">
    <p class="tag">{c['kaisha']}様 専用フォーム</p>
    <h1>洗浄のご依頼ページ</h1>
    <p>台数を選ぶと、その場で目安の料金と空いている日時が出ます。日時を選んで送れば仮押さえです。担当の渡辺から確定のご連絡をします。</p>
  </div>
</header>
<main class="wrap">
<form id="form" name="partner" method="POST" action="/partner/thanks/" data-netlify="true" netlify-honeypot="bot-field">
  <input type="hidden" name="form-name" value="partner">
  <p class="hp"><label>入力しないでください <input name="bot-field"></label></p>
  <input type="hidden" name="提携先" value="{c['kaisha']}">
  <input type="hidden" name="ご担当" value="{c['tantou']}">
  <input type="hidden" name="ページ" value="{key}">
  <input type="hidden" name="請求先" value="{c['seikyu']}">
  <input type="hidden" id="f-naiyou" name="内容" value="">
  <input type="hidden" id="f-kingaku" name="目安金額" value="">
  <input type="hidden" id="f-hi" name="希望日時" value="">
  <input type="hidden" id="f-sentaku" name="送信元の確認" value="">
  <input type="hidden" name="種別" value="仮押さえ">
  {KYOUTSUU_HIDDEN}

  <section class="card">
    <h2><span class="step">1</span>現場</h2>
    <label class="f" for="f-genba">現場の住所<span class="req">必須</span></label>
    <input id="f-genba" name="現場の住所" type="text" placeholder="例：大田区大森本町（区・町名まででも結構です）">
    <label class="f" for="f-genbamei">現場のお名前<span class="opt">任意・店舗名や物件名</span></label>
    <input id="f-genbamei" name="現場のお名前" type="text">
    <label class="chk"><input type="checkbox" name="きっかけ" value="ご紹介カード">ご紹介カードを見たお客様<span class="opt">任意</span></label>
  </section>

  <section class="card">
    <h2><span class="step">2</span>内容と台数</h2>
    {''.join(rows)}
    <div class="sum" id="sum"></div>
  </section>

  <section class="card">
    <h2><span class="step">3</span>日時</h2>
    <p class="note">選んだ台数で作業できる、空いている開始時刻です（担当のカレンダーをその場で見ています）。</p>
    <div id="slots"></div>
    <label class="f" for="f-biko">ご要望・ご希望の日時<span class="opt">任意</span></label>
    <textarea id="f-biko" name="ご要望" placeholder="例：営業時間外（20時以降）希望、駐車スペースなし、立ち会いは店長 など"></textarea>
  </section>

  <p class="err" id="err"></p>
  <button class="send" type="submit">この内容で仮押さえする</button>
  <p class="note">表示は目安です。現場の状況で変わる場合は、作業の前にご説明します。送信いただいた内容はご依頼の対応のためだけに使います（<a href="https://lp.onehitter.jp/privacy/">個人情報の取扱いについて</a>）。お急ぎはお電話 {TEL} でも承ります。</p>
</form>
</main>
{FOOTER}
<script>{js}</script>
</body>
</html>
"""


THANKS = f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>ご依頼を受け付けました｜ワンヒッター株式会社</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
<header><div class="wrap"><p class="tag">提携先様 専用</p><h1>ご依頼を受け付けました</h1>
<p>担当の渡辺から、1営業日以内にご連絡します。お急ぎの場合はお電話（{TEL}）でお知らせください。</p></div></header>
<main class="wrap"><div class="card"><p>続けて別の現場や現調をご依頼の場合は、ブラウザの「戻る」で前のページに戻ってお送りください。</p></div></main>
{FOOTER}
</body>
</html>
"""


def main():
    for key, c in COMPANIES.items():
        d = OUT / key
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(page(key, c), encoding="utf-8")
        print("書きました:", d / "index.html")
    (OUT / "thanks").mkdir(parents=True, exist_ok=True)
    (OUT / "thanks" / "index.html").write_text(THANKS, encoding="utf-8")
    print("書きました:", OUT / "thanks" / "index.html")


if __name__ == "__main__":
    main()
