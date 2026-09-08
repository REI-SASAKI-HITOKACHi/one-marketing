#!/usr/bin/env python3
"""既存のお客様向け Web予約ページ（lp/booking/index.html）を組み立てる。

なぜ生成するのか:
  料金を手で書き写すと data/prices.json とずれる。ずれた金額をお客様に
  見せるのが一番まずいので、価格は必ず data/prices.json から入れる。
  デザインのトークンとベースCSSは lp/survey/index.html から取り出して使う。
  トーン&マナーを揃えるためで、これは既存の lp/survey/ と同じ考え方。

使い方:
  python3 tools/build-booking.py
  （出力: lp/booking/index.html）
"""

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PRICES = ROOT / "data" / "prices.json"
SURVEY = ROOT / "lp" / "survey" / "index.html"
OUT = ROOT / "lp" / "booking" / "index.html"

# Apps Script のウェブアプリURL。デプロイ後にここを差し替える。
# 空のままでも画面は動くが、空き枠は「準備中」と出る。
API_URL = ""

TEL = "080-8043-8259"

# ネット申込特典（税込）。セット価格がどれも付かない組み合わせのときだけ引く。
# 1箇所だけのご注文は対象外（2026-09-08 オーナー決定）。
NET_TOKUTEN = 2200

# 所要時間が prices.json に無いメニューの既定値（分）
KITEI_SHOYOU = 60


def shoyou_fun(m: dict) -> int:
    t = str(m.get("所要") or "")
    n = re.search(r"(\d+)", t)
    return int(n.group(1)) if n else KITEI_SHOYOU


def base_css() -> str:
    """アンケートページからデザイントークンとベースCSSをそのまま持ってくる"""
    html = SURVEY.read_text(encoding="utf-8")
    m = re.search(r"<style>(.*?)</style>", html, re.S)
    if not m:
        sys.exit("lp/survey/index.html から <style> を取り出せませんでした")
    css = m.group(1)
    # アンケート専用の部品（NPSの0-10、★評価）は予約ページでは使わないので落とす
    for block in ("/* NPS 0-10 */", "/* ★評価 */"):
        i = css.find(block)
        if i < 0:
            continue
        j = css.find("/* 選択肢 */", i)
        if j > i:
            css = css[:i] + css[j:]
    return css.strip()


TSUIKA_CSS = """
/* ============ 予約ページ固有 ============ */

/* トップの「電話で予約する」。フォームが合わない方をここで受け止める */
.denwa{display:flex;flex-direction:column;gap:9px;background:var(--surface);
  border:2px solid var(--accent);border-radius:12px;padding:15px 16px;box-shadow:var(--shadow);}
.denwa .btn{width:100%;min-height:56px;font-size:17px;}
.denwa .lab{font-size:12.5px;color:var(--muted);line-height:1.7;}
.denwa .lab b{color:var(--ink);}
.matawa{display:flex;align-items:center;gap:10px;color:var(--muted);font-size:12px;}
.matawa::before,.matawa::after{content:"";flex:1 1 auto;height:1px;background:var(--line);}


/* メニューの行。個数を増減できるようにしている（エアコンは複数台が普通のため） */
.menu-list{display:flex;flex-direction:column;gap:8px;}
.menu-row{display:grid;grid-template-columns:1fr auto;gap:10px 12px;align-items:center;
  border:1.5px solid var(--line-strong);border-radius:10px;padding:11px 13px;background:var(--surface);
  transition:.12s;}
.menu-row.on{border-color:var(--accent);background:var(--accent-soft);}
.menu-row .nm{display:flex;flex-direction:column;gap:2px;min-width:0;}
.menu-row .nm b{font-size:14.5px;font-weight:700;line-height:1.5;}
.menu-row .nm small{font-size:11.5px;color:var(--muted);}
.stepper{display:flex;align-items:center;gap:4px;}
.stepper button{width:40px;height:40px;border-radius:8px;border:1.5px solid var(--line-strong);
  background:var(--surface);color:var(--ink);font-size:20px;line-height:1;font-family:inherit;
  cursor:pointer;display:grid;place-items:center;}
.stepper button:disabled{opacity:.35;cursor:default;}
.stepper .n{min-width:32px;text-align:center;font-family:"Barlow",sans-serif;font-weight:700;font-size:17px;}

/* 合計 */
.total{background:var(--surface-2);border:1px solid var(--line);border-radius:10px;padding:14px 15px;
  display:flex;flex-direction:column;gap:6px;}
.total .ln{display:flex;justify-content:space-between;gap:12px;font-size:13px;color:var(--ink-soft);}
.total .ln.sum{font-size:17px;font-weight:900;color:var(--ink);border-top:1px solid var(--line-strong);
  padding-top:8px;margin-top:2px;}
.total .ln .v{font-family:"Barlow",sans-serif;font-variant-numeric:tabular-nums;white-space:nowrap;}
.total .ln.off .v{color:var(--ok);}
.total .ln.add .v{color:var(--cta-text);}
.total .note{font-size:11.5px;color:var(--muted);line-height:1.7;}

/* 日付と時刻 */
.days{display:flex;flex-direction:column;gap:10px;}
.day{border:1px solid var(--line);border-radius:10px;background:var(--surface);padding:12px 13px;
  display:flex;flex-direction:column;gap:9px;}
.day .dl{font-size:14px;font-weight:700;}
.day .dl .we{color:var(--cta-text);}
.times{display:grid;grid-template-columns:repeat(auto-fill,minmax(84px,1fr));gap:7px;}
.times button{min-height:44px;border-radius:8px;border:1.5px solid var(--line-strong);background:var(--surface);
  color:var(--ink);font-family:"Barlow",sans-serif;font-weight:700;font-size:15px;cursor:pointer;}
.times button.on{background:var(--accent);border-color:var(--accent);color:var(--on-accent);}
.loading{font-size:13px;color:var(--muted);padding:18px 0;text-align:center;}
.more{align-self:center;}

/* 確認 */
.kakunin{display:flex;flex-direction:column;gap:0;}
.kakunin .r{display:grid;grid-template-columns:88px 1fr;gap:10px;padding:9px 0;border-bottom:1px solid var(--line);
  font-size:13.5px;line-height:1.7;}
.kakunin .r:last-child{border-bottom:0;}
.kakunin .r dt{color:var(--muted);font-size:12.5px;}
.kakunin .r dd{margin:0;font-weight:700;word-break:break-word;}
"""


def build() -> str:
    data = json.loads(PRICES.read_text(encoding="utf-8"))
    menus = []
    for m in data["本メニュー"]:
        menus.append({
            "n": m["名称"],
            "t": m["単体"],
            # 同時施工価格。無ければ単体と同じ（＝2箇所目でも安くならない）
            "d": m.get("同時施工", m["単体"]),
            "m": shoyou_fun(m),
        })
    hanbouki = data["繁忙期加算"]
    souki = data["早期予約割引"]

    setting = {
        "menus": menus,
        "hanbouki": {"tsuki": hanbouki["対象月"], "gaku": hanbouki["金額"]},
        # 早期予約割引は「月 → 割引率」に展開しておく（画面側で判定を書かなくて済む）
        "souki": {
            1: souki["1-2月"], 2: souki["1-2月"],
            3: souki["3-4月"], 4: souki["3-4月"],
            5: souki["5-7月"], 6: souki["5-7月"], 7: souki["5-7月"],
            8: souki["8-10月"], 9: souki["8-10月"], 10: souki["8-10月"],
            11: souki["11-12月"], 12: souki["11-12月"],
        },
        "netTokuten": NET_TOKUTEN,
        "api": API_URL,
        "tel": TEL,
    }

    css = base_css() + "\n" + TSUIKA_CSS
    js_setting = json.dumps(setting, ensure_ascii=False, indent=0).replace("\n", "")

    return TEMPLATE.replace("{{CSS}}", css).replace("{{SETTEI}}", js_setting).replace("{{TEL}}", TEL)


TEMPLATE = r"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ご予約｜ONE HITTER ワンヒッター株式会社</title>
<meta name="description" content="ワンヒッター株式会社のご予約ページです。空いている日時をその場で選べます。">
<meta name="robots" content="noindex,nofollow">
<meta name="theme-color" content="#0E7C93">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow:wght@500;600;700&family=Shippori+Mincho+B1:wght@600&family=Zen+Kaku+Gothic+New:wght@400;500;700;900&display=swap">

<style>
{{CSS}}
</style>
</head>
<body>

<header class="bar">
  <div class="bar-in">
    <span class="logo"><b>ONE HITTER</b><small>ワンヒッター株式会社</small></span>
    <a class="tel" href="tel:{{TEL}}"><span class="n">{{TEL}}</span><small>受付 渡辺／8:00–20:00</small></a>
  </div>
</header>

<main class="wrap">

  <div class="intro">
    <span class="eyebrow">Booking</span>
    <h1>空いている日時から<br>そのままご予約いただけます。</h1>
    <p class="lead">前回ご利用いただいたお客様専用のページです。所要 <b>約2分</b>。担当の空き状況をそのまま出しているので、そのままご予約いただけます。お電話でも承ります。</p>
    <div class="ctx"><span>東京・千葉・神奈川</span><span>表示はすべて税込</span><span>追加請求なし</span></div>
  </div>

  <!-- フォームが合わない方、急ぎの方の逃げ道。いちばん上に置く -->
  <div class="denwa">
    <a class="btn tel" href="tel:{{TEL}}">電話で予約する（担当：渡辺）</a>
    <span class="lab"><b>{{TEL}}／受付 8:00〜20:00</b><br>
      日程のご相談や、フォームに無いご依頼はお電話が早いです。</span>
  </div>
  <p class="matawa">または、下から日時を選ぶ</p>

  <div class="progress" id="progress">
    <span class="track"><span class="fill" id="bar"></span></span>
    <span class="lab"><span id="steplab">1 / 4</span><span id="steptitle">ご希望の内容</span></span>
  </div>

  <div class="survey-form">

    <!-- ===================== 1. メニュー ===================== -->
    <section class="q" id="s1">
      <div class="head">
        <span class="tag-req">必須</span>
        <h2>ご希望の内容をお選びください</h2>
        <p class="why">箇所数だけお選びいただければ大丈夫です。オプション（防カビコート・室外機など）は、担当からの確認のお電話で承ります。</p>
      </div>
      <div class="menu-list" id="menus"></div>
      <div class="total" id="total" hidden></div>
      <p class="err" id="e1"></p>
      <div class="nav"><button class="btn lg" id="n1">日時を選ぶ</button></div>
    </section>

    <!-- ===================== 2. 日時 ===================== -->
    <section class="q" id="s2" hidden>
      <div class="head">
        <span class="tag-req">必須</span>
        <h2>ご希望の日時をお選びください</h2>
        <p class="why">担当（渡辺）のいまの空き状況です。ここに出ている枠なら、そのままお伺いできます。作業時間は<b id="yotei-fun">—</b>を見込んでいます。</p>
      </div>
      <div id="slots"><p class="loading">空き状況を確認しています…</p></div>
      <p class="err" id="e2"></p>
      <div class="nav">
        <button class="btn ghost" data-back="1">もどる</button>
        <button class="btn lg" id="n2">お客様情報へ</button>
      </div>
    </section>

    <!-- ===================== 3. お客様情報 ===================== -->
    <section class="q" id="s3" hidden>
      <div class="head">
        <span class="tag-req">必須</span>
        <h2>ご連絡先をお願いします</h2>
        <p class="why">前回とお変わりなければ、お名前とお電話番号だけで結構です。ご住所は当日の道順の確認に使います。</p>
      </div>
      <div class="field">
        <label for="f-name">お名前</label>
        <input id="f-name" type="text" autocomplete="name" placeholder="例）田中 太郎">
      </div>
      <div class="field">
        <label for="f-tel">お電話番号</label>
        <input id="f-tel" type="tel" inputmode="tel" autocomplete="tel" placeholder="例）090-1234-5678">
        <span class="hint">前日に確認のご連絡を差し上げます。</span>
      </div>
      <div class="field">
        <label for="f-addr">ご住所</label>
        <input id="f-addr" type="text" autocomplete="street-address" placeholder="例）千葉県船橋市〇〇1-2-3 〇〇マンション101">
      </div>
      <div class="field">
        <label for="f-note">ご要望（任意）</label>
        <textarea id="f-note" placeholder="例）駐車場はありません／2階のエアコンです／前回と同じ場所です"></textarea>
      </div>
      <div class="hp"><label>この欄は入力しないでください<input type="text" id="f-hp" tabindex="-1" autocomplete="off"></label></div>
      <p class="err" id="e3"></p>
      <div class="nav">
        <button class="btn ghost" data-back="2">もどる</button>
        <button class="btn lg" id="n3">内容を確認する</button>
      </div>
    </section>

    <!-- ===================== 4. 確認 ===================== -->
    <section class="q" id="s4" hidden>
      <div class="head">
        <h2>この内容でよろしいですか</h2>
        <p class="why">送信いただいた時点では、まだ確定ではありません。担当から確認のお電話を差し上げて、そこで確定します。</p>
      </div>
      <dl class="kakunin" id="kakunin"></dl>
      <div class="total" id="total2"></div>
      <p class="err" id="e4"></p>
      <div class="nav">
        <button class="btn ghost" data-back="3">もどる</button>
        <button class="btn lg" id="send">この内容で予約する</button>
      </div>
    </section>

    <!-- ===================== 完了 ===================== -->
    <section class="done" id="done" hidden>
      <div class="thanks">
        <h2>ご予約ありがとうございます。</h2>
        <p id="done-when"></p>
        <p>担当の渡辺より、確認のお電話を差し上げます。<br>その時点で確定となります。</p>
      </div>
      <div class="card small">
        <h3>ご変更・キャンセル</h3>
        <p>お電話をお願いします。前日までにご連絡いただければ費用はかかりません。</p>
        <a class="btn tel" href="tel:{{TEL}}">{{TEL}} に電話する</a>
      </div>
    </section>

  </div>
</main>

<footer>
  <div class="wrap">
    <b>ワンヒッター株式会社（ONE HITTER）</b>
    <p>対応エリア：東京都・千葉県・神奈川県<br>受付 8:00–20:00　<a href="tel:{{TEL}}">{{TEL}}</a></p>
    <p>表示価格はすべて税込です。お見積り以上の追加請求はいたしません。</p>
  </div>
</footer>

<script>
(function(){
  'use strict';
  var S = {{SETTEI}};
  var $ = function(id){ return document.getElementById(id); };

  var state = {
    qty: {},          // メニュー名 -> 個数
    date: '', time: '',
    slots: null,
  };

  /* ---------------- 金額と所要時間 ----------------
     ルールは data/prices.json のとおり。
       ・2箇所目以降は同時施工価格
       ・早期予約割引は複数箇所（＝同時施工割引）とは併用しない
       ・5,6,7,12月は1箇所あたり繁忙期加算
     ここで出すのはあくまで概算。確定は担当が電話でお伝えする。 */
  function erabareta(){
    return S.menus.filter(function(m){ return (state.qty[m.n] || 0) > 0; });
  }
  function kasho(){
    var n = 0;
    S.menus.forEach(function(m){ n += (state.qty[m.n] || 0); });
    return n;
  }
  function shoyouFun(){
    var f = 0;
    S.menus.forEach(function(m){ f += (state.qty[m.n] || 0) * m.m; });
    return f;
  }
  function kingaku(){
    var n = kasho();
    if (!n) { return null; }

    /* 1箇所ずつに展開する */
    var tan = [];
    S.menus.forEach(function(m){
      for (var i = 0; i < (state.qty[m.n] || 0); i++) { tan.push(m); }
    });

    /* コンロのセット価格は、原則キッチンと同時のときだけ（パンフレットp10・p11） */
    var kitchen = (state.qty['キッチンクリーニング'] || 0) > 0;
    function setKakaku(m){
      return (m.n === 'コンロクリーニング' && !kitchen) ? m.t : m.d;
    }

    var tanpin = 0;
    tan.forEach(function(m){ tanpin += m.t; });

    var shoukei;
    if (n === 1) {
      shoukei = tan[0].t;
    } else {
      /* ★単品のまま残すのは「割引額がいちばん小さい1箇所」。
         いちばん高い箇所を単品にすると、セット価格を持つ箇所が単品側へ追いやられ、
         割引が消える（例：トイレ＋浴室で割引0になっていた）。 */
      var narabi = tan.slice().sort(function(a, b){
        return (a.t - setKakaku(a)) - (b.t - setKakaku(b));
      });
      shoukei = narabi[0].t;
      for (var i = 1; i < narabi.length; i++) { shoukei += setKakaku(narabi[i]); }
    }
    var setBiki = tanpin - shoukei;

    var tsuki = state.date ? parseInt(state.date.slice(5, 7), 10) : 0;

    /* 早期予約割引は1箇所のときだけ（複数箇所は同時施工割引がすでに効いている） */
    var ritsu = (n === 1 && tsuki) ? (S.souki[tsuki] || 0) : 0;
    var waribiki = Math.round(shoukei * ritsu);

    /* どの組み合わせでもセット価格が付かないときの、ネット申込特典。
       1箇所だけのご注文は対象外（2026-09-08 オーナー決定） */
    var netto = (n >= 2 && setBiki === 0) ? S.netTokuten : 0;

    var kasan = (tsuki && S.hanbouki.tsuki.indexOf(tsuki) >= 0) ? S.hanbouki.gaku * n : 0;

    return {
      kasho: n, tanpin: tanpin, shoukei: shoukei, setBiki: setBiki,
      ritsu: ritsu, waribiki: waribiki, netto: netto,
      kasan: kasan, gokei: shoukei - waribiki - netto + kasan,
    };
  }
  function yen(v){ return '¥' + v.toLocaleString('ja-JP'); }
  function funHyouji(f){
    if (f < 60) { return f + '分'; }
    var h = Math.floor(f / 60), m = f % 60;
    return h + '時間' + (m ? m + '分' : '');
  }

  /* ---------------- メニューの描画 ---------------- */
  function menuByName(n){
    for (var i = 0; i < S.menus.length; i++) { if (S.menus[i].n === n) { return S.menus[i]; } }
    return null;
  }
  function drawMenus(){
    var box = $('menus');
    box.innerHTML = '';
    S.menus.forEach(function(m){
      var row = document.createElement('div');
      row.className = 'menu-row';
      row.innerHTML =
        '<div class="nm"><b></b><small></small></div>' +
        '<div class="stepper">' +
          '<button type="button" aria-label="減らす">−</button>' +
          '<span class="n">0</span>' +
          '<button type="button" aria-label="増やす">＋</button>' +
        '</div>';
      row.querySelector('b').textContent = m.n;
      row.querySelector('small').textContent = yen(m.t) + '（税込）／ ' + funHyouji(m.m);
      var btns = row.querySelectorAll('.stepper button');
      btns[0].addEventListener('click', function(){ kaeru(m.n, -1, row); });
      btns[1].addEventListener('click', function(){ kaeru(m.n, 1, row); });
      row._m = m;
      box.appendChild(row);
    });
    drawTotal();
  }
  function kaeru(name, d, row){
    var v = (state.qty[name] || 0) + d;
    if (v < 0) { v = 0; }
    if (v > 9) { v = 9; }
    state.qty[name] = v;
    row.querySelector('.n').textContent = String(v);
    row.querySelector('.stepper button').disabled = (v === 0);
    row.classList.toggle('on', v > 0);
    /* 箇所数が変わると所要時間が変わる＝すでに選んだ枠が使えるとは限らないので消す */
    state.date = ''; state.time = ''; state.slots = null;
    drawTotal();
  }

  function totalHTML(k){
    if (!k) { return ''; }
    var h = [];
    h.push(ln('単品でのご依頼なら（' + k.kasho + '箇所）', yen(k.tanpin), ''));
    if (k.setBiki) {
      h.push(ln('セット価格の割引', '−' + yen(k.setBiki), 'off'));
      h.push('<p class="note">同時にご依頼いただく箇所は、セット価格を適用しています。</p>');
    }
    if (k.netto) {
      h.push(ln('ネット申込特典', '−' + yen(k.netto), 'off'));
      h.push('<p class="note">セット価格の対象がない組み合わせのため、'
             + 'このページからのお申し込み特典を適用しています。</p>');
    }
    if (k.waribiki) {
      h.push(ln('早期予約割引 ' + Math.round(k.ritsu * 100) + '%OFF', '−' + yen(k.waribiki), 'off'));
    }
    if (k.kasan) {
      h.push(ln('繁忙期加算（' + k.kasho + '箇所）', '+' + yen(k.kasan), 'add'));
    }
    h.push(ln('概算合計（税込）', yen(k.gokei), 'sum'));
    h.push('<p class="note">現地の状況により変わることがあります。確定金額は担当からのお電話でお伝えします。' +
           (state.date ? '' : '日時をお選びいただくと、割引と加算を反映した金額になります。') + '</p>');
    return h.join('');
  }
  function ln(l, v, cls){
    return '<div class="ln ' + (cls || '') + '"><span>' + l + '</span><span class="v">' + v + '</span></div>';
  }
  function drawTotal(){
    var k = kingaku();
    var box = $('total');
    box.hidden = !k;
    box.innerHTML = totalHTML(k);
  }

  /* ---------------- 空き枠 ----------------
     Apps Script は fetch だとCORSで詰まりやすいので、JSONPで取りに行く。 */
  var jsonpN = 0;
  function jsonp(url){
    return new Promise(function(res, rej){
      var name = '__cb' + (++jsonpN) + '_' + Date.now();
      var sc = document.createElement('script');
      var t = setTimeout(function(){ owari(); rej(new Error('timeout')); }, 20000);
      function owari(){
        clearTimeout(t);
        delete window[name];
        if (sc.parentNode) { sc.parentNode.removeChild(sc); }
      }
      window[name] = function(d){ owari(); res(d); };
      sc.onerror = function(){ owari(); rej(new Error('network')); };
      sc.src = url + (url.indexOf('?') < 0 ? '?' : '&') + 'callback=' + name;
      document.body.appendChild(sc);
    });
  }

  function loadSlots(){
    var box = $('slots');
    if (!S.api) {
      box.innerHTML = '<p class="loading">ただいま日時の自動表示を準備しています。<br>' +
        'お手数ですが <a href="tel:{{TEL}}">{{TEL}}</a> までお電話ください。</p>';
      return;
    }
    box.innerHTML = '<p class="loading">空き状況を確認しています…</p>';
    jsonp(S.api + '?action=slots&minutes=' + shoyouFun()).then(function(d){
      if (!d || !d.ok) { throw new Error((d && d.error) || 'error'); }
      state.slots = d.slots || [];
      drawSlots();
    }).catch(function(){
      box.innerHTML = '<p class="loading">空き状況をうまく取得できませんでした。<br>' +
        'お手数ですが <a href="tel:{{TEL}}">{{TEL}}</a> までお電話ください。</p>';
    });
  }

  var MISERU = 5;   // 最初は5日ぶんだけ出す。長いリストは選びにくい
  function drawSlots(){
    var box = $('slots');
    box.innerHTML = '';
    if (!state.slots.length) {
      box.innerHTML = '<p class="loading">申し訳ありません、3週間先まで空きがありませんでした。<br>' +
        'お手数ですが <a href="tel:{{TEL}}">{{TEL}}</a> までご相談ください。</p>';
      return;
    }
    var wrap = document.createElement('div');
    wrap.className = 'days';
    state.slots.slice(0, MISERU).forEach(function(d){
      var el = document.createElement('div');
      el.className = 'day';
      var lab = document.createElement('div');
      lab.className = 'dl';
      lab.textContent = d.label;
      if (/（[土日]）/.test(d.label)) { lab.innerHTML = '<span class="we">' + d.label + '</span>'; }
      el.appendChild(lab);
      var tl = document.createElement('div');
      tl.className = 'times';
      d.times.forEach(function(t){
        var b = document.createElement('button');
        b.type = 'button';
        b.textContent = t;
        if (state.date === d.date && state.time === t) { b.className = 'on'; }
        b.addEventListener('click', function(){
          state.date = d.date; state.time = t;
          drawSlots();
          $('e2').textContent = '';
        });
        tl.appendChild(b);
      });
      el.appendChild(tl);
      wrap.appendChild(el);
    });
    box.appendChild(wrap);
    if (state.slots.length > MISERU) {
      var more = document.createElement('button');
      more.type = 'button';
      more.className = 'btn ghost sm more';
      more.textContent = 'もっと先の日程を見る';
      more.addEventListener('click', function(){ MISERU += 7; drawSlots(); });
      box.appendChild(more);
    }
  }

  /* ---------------- 画面の進行 ---------------- */
  var STEPS = ['s1', 's2', 's3', 's4'];
  var TITLES = ['ご希望の内容', '日時', 'ご連絡先', '確認'];
  var ima = 1;
  function go(n){
    ima = n;
    STEPS.forEach(function(id, i){ $(id).hidden = (i + 1 !== n); });
    $('done').hidden = true;
    $('progress').hidden = false;
    $('bar').style.width = (n / 4 * 100) + '%';
    $('steplab').textContent = n + ' / 4';
    $('steptitle').textContent = TITLES[n - 1];
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  $('n1').addEventListener('click', function(){
    if (!kasho()) { $('e1').textContent = 'ご希望の内容を1つ以上お選びください。'; return; }
    $('e1').textContent = '';
    $('yotei-fun').textContent = 'およそ' + funHyouji(shoyouFun());
    go(2);
    loadSlots();
  });

  $('n2').addEventListener('click', function(){
    if (!state.date) { $('e2').textContent = 'ご希望の日時をお選びください。'; return; }
    $('e2').textContent = '';
    go(3);
  });

  $('n3').addEventListener('click', function(){
    var name = $('f-name').value.trim();
    var tel = $('f-tel').value.trim();
    var addr = $('f-addr').value.trim();
    if (!name) { $('e3').textContent = 'お名前をご入力ください。'; return; }
    if (!/[0-9]{9,}/.test(tel.replace(/[^0-9]/g, ''))) {
      $('e3').textContent = 'お電話番号をご確認ください。'; return;
    }
    if (addr.length < 6) { $('e3').textContent = 'ご住所をご入力ください。'; return; }
    $('e3').textContent = '';
    drawKakunin();
    go(4);
  });

  Array.prototype.forEach.call(document.querySelectorAll('[data-back]'), function(b){
    b.addEventListener('click', function(){ go(parseInt(b.getAttribute('data-back'), 10)); });
  });

  function menuText(){
    var a = [];
    S.menus.forEach(function(m){
      var q = state.qty[m.n] || 0;
      if (q > 0) { a.push(m.n + (q > 1 ? ' ×' + q : '')); }
    });
    return a.join('／');
  }
  function nichijiText(){
    var d = null;
    (state.slots || []).forEach(function(x){ if (x.date === state.date) { d = x; } });
    return (d ? d.label : state.date) + ' ' + state.time + '〜';
  }
  function drawKakunin(){
    var k = kingaku();
    var rows = [
      ['ご希望', menuText()],
      ['日時', nichijiText()],
      ['所要', 'およそ' + funHyouji(shoyouFun())],
      ['お名前', $('f-name').value.trim() + ' 様'],
      ['お電話', $('f-tel').value.trim()],
      ['ご住所', $('f-addr').value.trim()],
    ];
    var note = $('f-note').value.trim();
    if (note) { rows.push(['ご要望', note]); }
    $('kakunin').innerHTML = rows.map(function(r){
      return '<div class="r"><dt>' + r[0] + '</dt><dd></dd></div>';
    }).join('');
    Array.prototype.forEach.call($('kakunin').querySelectorAll('dd'), function(dd, i){
      dd.textContent = rows[i][1];
    });
    $('total2').innerHTML = totalHTML(k);
  }

  /* ---------------- 送信 ----------------
     Content-Type は text/plain。application/json にするとブラウザが
     プリフライトを飛ばし、Apps Script がそれに答えられないため。 */
  var okuttechuu = false;
  $('send').addEventListener('click', function(){
    if (okuttechuu) { return; }
    if ($('f-hp').value) { return; }   // 自動投稿よけ
    if (!S.api) {
      $('e4').textContent = 'ただいま送信の準備中です。お手数ですが ' + S.tel + ' までお電話ください。';
      return;
    }
    var k = kingaku();
    var body = {
      name: $('f-name').value.trim(),
      tel: $('f-tel').value.trim(),
      address: $('f-addr').value.trim(),
      note: $('f-note').value.trim(),
      date: state.date, time: state.time,
      menu: menuText(),
      minutes: shoyouFun(),
      amount: k ? k.gokei : 0,
    };
    okuttechuu = true;
    $('send').disabled = true;
    $('send').textContent = '送信しています…';
    $('e4').textContent = '';

    fetch(S.api, {
      method: 'POST',
      headers: { 'Content-Type': 'text/plain;charset=utf-8' },
      body: JSON.stringify(body),
    }).then(function(r){ return r.json(); }).then(function(d){
      if (!d || !d.ok) { throw new Error((d && (d.message || d.error)) || '送信できませんでした'); }
      $('done-when').textContent = d.label + '〜 でお伺いします。';
      STEPS.forEach(function(id){ $(id).hidden = true; });
      $('progress').hidden = true;
      $('done').hidden = false;
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }).catch(function(err){
      okuttechuu = false;
      $('send').disabled = false;
      $('send').textContent = 'この内容で予約する';
      $('e4').textContent = String(err.message || err) +
        '　お手数ですが ' + S.tel + ' までお電話ください。';
    });
  });

  drawMenus();
  go(1);
})();
</script>

</body>
</html>
"""


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    html = build()
    OUT.write_text(html, encoding="utf-8")
    print(f"書き出しました: {OUT.relative_to(ROOT)}  {len(html.encode()):,} bytes")
    if not API_URL:
        print("※ API_URL が空です。Apps Scriptをデプロイしたら、このファイルの")
        print("   API_URL に /exec のURLを入れて、もう一度実行してください。")


if __name__ == "__main__":
    main()
