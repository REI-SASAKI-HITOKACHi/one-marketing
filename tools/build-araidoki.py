#!/usr/bin/env python3
"""「洗いどき相談所」（案A）の試作ページを組み立てる。

なぜ生成するのか:
  判定ルールは data/araidoki-rules.json、料金は data/prices.json が正。
  どちらもHTMLに手で書き写すとずれるので、必ずここから入れる。
  デザインのトークンとベースCSSは lp/survey/index.html から取り出して使う
  （lp/booking と同じ考え方。トーン&マナーを揃えるため）。

使い方:
  python3 tools/build-araidoki.py
  （出力: lp/media/araidoki/index.html, lp/media/araidoki/unei.html）

いまの段階:
  判定は固定分岐（写真は受け取るだけで、判定に使っていない）。
  写真AIを入れるときは、JSの hantei() を API 呼び出しに差し替える。
"""

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PRICES = ROOT / "data" / "prices.json"
RULES = ROOT / "data" / "araidoki-rules.json"
SURVEY = ROOT / "lp" / "survey" / "index.html"
OUTDIR = ROOT / "lp" / "media" / "araidoki"

BRAND = "洗いどき"
BRAND_EN = "araidoki"
TAGLINE = "掃除の相談所"
UNEI = "ワンヒッター株式会社"
UNEI_ADDR = "〒134-0081 東京都江戸川区北葛西5-14-11"
FORM_NAME = "araidoki-tehai"


def base_css() -> str:
    """アンケートページからデザイントークンとベースCSSを持ってくる"""
    html = SURVEY.read_text(encoding="utf-8")
    m = re.search(r"<style>(.*?)</style>", html, re.S)
    if not m:
        sys.exit("lp/survey/index.html から <style> を取り出せませんでした")
    css = m.group(1)
    for block in ("/* NPS 0-10 */", "/* ★評価 */"):
        i = css.find(block)
        if i < 0:
            continue
        j = css.find("/* 選択肢 */", i)
        if j > i:
            css = css[:i] + css[j:]
    return css.strip()


TSUIKA_CSS = """
/* ============ 相談所 固有 ============ */
.logo b{letter-spacing:.02em;font-family:"Shippori Mincho B1",serif;font-size:19px;}
.bar .unei{margin-left:auto;font-size:10.5px;color:var(--muted);text-align:right;line-height:1.5;}
.intro .honest{font-size:12.5px;color:var(--muted);line-height:1.7;border-left:3px solid var(--accent);padding-left:10px;}

/* 対象の選択 */
.targets{display:grid;grid-template-columns:1fr 1fr;gap:8px;}
.targets .opt .box{min-height:64px;font-size:15.5px;}

/* 判定 */
.verdict{border-radius:12px;padding:20px 18px;display:flex;flex-direction:column;gap:12px;box-shadow:var(--shadow);
  border:2px solid var(--line);background:var(--surface);}
.verdict .kind{font-family:"Barlow",sans-serif;font-size:11px;font-weight:700;letter-spacing:.14em;color:var(--muted);}
.verdict h2{font-size:clamp(19px,5vw,24px);line-height:1.5;}
.verdict.pro{border-color:var(--cta);}
.verdict.pro h2{color:var(--cta-text);}
.verdict.diy{border-color:var(--accent);}
.verdict.diy h2{color:var(--accent-deep);}
.verdict.wait{border-color:var(--ok);}
.verdict.wait h2{color:var(--ok);}
.verdict .konkyo{font-size:14px;line-height:1.85;color:var(--ink);}
.verdict .meyasu{font-size:11.5px;color:var(--muted);line-height:1.7;}

/* 概算 */
.gaisan{background:var(--surface-2);border:1px solid var(--line);border-radius:10px;padding:14px 15px;display:flex;flex-direction:column;gap:6px;}
.gaisan .ln{display:flex;justify-content:space-between;gap:12px;font-size:13.5px;color:var(--ink-soft);}
.gaisan .ln.sum{font-size:19px;font-weight:900;color:var(--ink);border-top:1px solid var(--line-strong);padding-top:8px;margin-top:2px;}
.gaisan .ln .v{font-family:"Barlow",sans-serif;font-variant-numeric:tabular-nums;white-space:nowrap;}
.gaisan .note{font-size:11.5px;color:var(--muted);line-height:1.7;}

/* DIY手順 */
.diy-steps{margin:0;padding-left:1.3em;font-size:13.5px;line-height:1.9;color:var(--ink);}
.diy-steps li.stop{color:var(--cta-text);font-weight:700;list-style:"⚠ ";}

/* 次の一手 */
.next{display:flex;flex-direction:column;gap:8px;}
.next .btn{width:100%;}

/* 手配フォーム */
.field select{padding:12px 14px;border:1.5px solid var(--line-strong);border-radius:8px;font-family:inherit;font-size:16px;
  background:var(--surface);color:var(--ink);width:100%;}
.field input[type=file]{padding:10px;font-size:14px;}
.agree{display:flex;gap:10px;align-items:flex-start;font-size:13px;line-height:1.7;}
.agree input{width:20px;height:20px;margin-top:2px;flex:0 0 auto;}
.maegaki{font-size:12.5px;color:var(--ink-soft);line-height:1.8;background:var(--surface-2);border-radius:8px;padding:10px 12px;}
.thumbs{display:flex;gap:6px;flex-wrap:wrap;}
.thumbs img{width:64px;height:64px;object-fit:cover;border-radius:6px;border:1px solid var(--line);}

/* 運営者ページ */
.unei-tbl{display:grid;grid-template-columns:110px 1fr;gap:8px 12px;font-size:13.5px;line-height:1.8;}
.unei-tbl dt{color:var(--muted);}
.unei-tbl dd{margin:0;}
"""


def esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


def head(title: str, desc: str) -> str:
    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<meta name="robots" content="noindex,nofollow">
<meta name="theme-color" content="#0E7C93">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow:wght@500;600;700&family=Shippori+Mincho+B1:wght@600&family=Zen+Kaku+Gothic+New:wght@400;500;700;900&display=swap">
<style>
{base_css()}
{TSUIKA_CSS}
</style>
</head>
<body>
<header class="bar">
  <div class="bar-in">
    <a class="logo" href="./" style="text-decoration:none;color:inherit"><b>{BRAND}</b><small>{BRAND_EN}｜{TAGLINE}</small></a>
    <span class="unei">運営：{UNEI}<br><a href="./unei.html" style="color:inherit">運営者情報</a></span>
  </div>
</header>
<main class="wrap">
"""


def foot() -> str:
    return f"""
</main>
<footer>
  <div class="wrap">
    <b>{BRAND}｜{TAGLINE}</b>
    <p>
      運営：{UNEI}（ハウスクリーニング業）<br>
      判定は目安です。実際の状態は、作業前に現物を確認してご説明します。<br>
      <a href="./unei.html">運営者情報</a>
      <a href="https://one-hitter.jp/privacy_policy/" target="_blank" rel="noopener">個人情報の取扱いについて</a>
    </p>
  </div>
</footer>
</body>
</html>
"""


def build_index(rules: dict, prices: dict) -> str:
    menus = {m["名称"]: m for m in prices["本メニュー"]}
    hanbou = prices["繁忙期加算"]
    # 判定に要る分だけを JS に渡す。金額はメニュー名で引く
    for t in rules["対象"]:
        for key in ("メニュー", "メニュー_お掃除機能付き"):
            if key in t and t[key] not in menus:
                sys.exit(f"prices.json に無いメニュー名: {t[key]}")
    data = {
        "判定": rules["判定"],
        "共通": rules["共通の質問"],
        "対象": rules["対象"],
        "手配": rules["手配"],
        "料金": {k: {"単体": v["単体"], "同時施工": v.get("同時施工"), "所要": v.get("所要", "")} for k, v in menus.items()},
        "繁忙期": {"月": hanbou["対象月"], "金額": hanbou["金額"]},
        "確認済み": bool(rules.get("_確認")),
    }
    js_data = json.dumps(data, ensure_ascii=False)

    areas = "".join(f'<option value="{esc(a)}">{esc(a)}</option>' for a in rules["手配"]["エリア"])

    body = f"""
  <div class="intro">
    <span class="eyebrow">{BRAND_EN}</span>
    <h1>そのエアコン、今洗うべき？<br>30秒で判定します。</h1>
    <p class="lead">プロに頼むべきかどうかを、正直にお答えします。<b>「今は不要」とお伝えすることもあります。</b>必要なときだけ、必要な分だけ。</p>
    <p class="honest">運営はハウスクリーニング業者（{UNEI}）ですが、判定はあらかじめ決めた基準で行い、手配のご希望がなければ連絡は一切しません。</p>
  </div>

  <div class="progress" id="progress">
    <span class="track"><span class="fill" id="bar" style="width:25%"></span></span>
    <span class="lab"><span id="steplab">1 / 4</span><span id="steptitle">何を洗う？</span></span>
  </div>

  <form class="survey-form" id="f" onsubmit="return false;" novalidate>

    <!-- ステップ1：対象 -->
    <section class="step" data-step="1">
      <div class="q">
        <div class="head"><h2>どこが気になりますか？</h2><p class="why">1つ選んでください。あとから他の場所も判定できます。</p></div>
        <div class="targets" id="targets"></div>
        <p class="err" id="e1"></p>
      </div>
    </section>

    <!-- ステップ2：状態 -->
    <section class="step" data-step="2" hidden>
      <div id="qs"></div>
      <div class="nav">
        <button type="button" class="btn ghost" data-back="1">戻る</button>
        <button type="button" class="btn lg" id="judge">判定する</button>
      </div>
      <p class="err" id="e2"></p>
    </section>

    <!-- ステップ3：判定 -->
    <section class="step" data-step="3" hidden>
      <div id="verdict"></div>
      <div class="q" id="gaisan-box" hidden>
        <div class="head"><h2>頼む場合の料金の目安</h2><p class="why">運営会社の料金表（税込）から出しています。提携事業者を手配する場合は、確定前に事業者名と料金を必ずお知らせします。</p></div>
        <div class="gaisan" id="gaisan"></div>
      </div>
      <div class="q" id="diy-box" hidden>
        <div class="head"><h2>ご自分でできること</h2><p class="why">ここまでで直ることが多いです。⚠ の先は分解が要るので、無理をしないでください。</p></div>
        <ol class="diy-steps" id="diy"></ol>
      </div>
      <div class="next" id="next"></div>
      <div class="nav"><button type="button" class="btn ghost" data-back="2">戻る</button></div>
    </section>

    <!-- ステップ4：手配 -->
    <section class="step" data-step="4" hidden>
      <div class="q">
        <div class="head"><h2 id="tehai-title">手配のご相談</h2></div>
        <p class="maegaki">{esc(rules["手配"]["前置き"])}</p>
        <div class="field"><label for="f-name">お名前</label><input id="f-name" type="text" autocomplete="name" placeholder="例：山田"></div>
        <div class="field"><label for="f-tel">お電話番号</label><input id="f-tel" type="tel" inputmode="tel" autocomplete="tel" placeholder="例：09012345678"><p class="hint">日程のご相談に1回だけお電話します。営業の電話はしません。</p></div>
        <div class="field"><label for="f-area">お住まいの地域</label><select id="f-area"><option value="">選んでください</option>{areas}</select></div>
        <div class="field"><label for="f-when">ご希望の時期</label><select id="f-when"><option value="">選んでください</option><option>今週中</option><option>2週間以内</option><option>1か月以内</option><option>時期は相談したい</option></select></div>
        <div class="field"><label for="f-photo">写真（任意・3枚まで）</label><input id="f-photo" type="file" accept="image/*" multiple><p class="hint">気になる場所を撮ってください。お部屋全体や表札など、お住まいが分かるものは写さないでください。</p><div class="thumbs" id="thumbs"></div></div>
        <div class="field"><label for="f-note">気になること（任意）</label><textarea id="f-note" placeholder="例：2台まとめて頼みたい／賃貸なので養生をしっかりしてほしい"></textarea></div>
        <label class="agree"><input type="checkbox" id="f-agree"><span>{esc(rules["手配"]["同意文"])}</span></label>
        <input type="text" id="f-hp" name="bot-field" tabindex="-1" autocomplete="off" style="position:absolute;left:-9999px" aria-hidden="true">
        <p class="err" id="e4"></p>
        <button type="button" class="btn lg" id="send">この内容で相談する</button>
        <div class="nav"><button type="button" class="btn ghost" data-back="3">戻る</button></div>
      </div>
    </section>

    <!-- 完了 -->
    <section class="step" data-step="5" hidden>
      <div class="q done">
        <div class="head"><h2>受け付けました。</h2></div>
        <p class="why" style="font-size:13.5px">運営会社（{UNEI}）から、<b>日程のご相談のお電話を1回</b>差し上げます。提携事業者が作業する場合は、その際に事業者名と料金をお伝えし、ご了承いただいてから確定します。</p>
        <div class="branch"><b>控え</b><p id="hikae" style="white-space:pre-wrap"></p></div>
      </div>
    </section>
  </form>

<script>
var D = {js_data};
(function(){{
  var $ = function(id){{ return document.getElementById(id); }};
  var form = $('f');
  var state = {{ target:null, ans:{{}}, verdict:null, rule:null, files:[] }};
  var STEP_TITLES = {{1:'何を洗う？',2:'いまの状態',3:'判定',4:'手配のご相談',5:'完了'}};

  function go(n){{
    var steps = form.querySelectorAll('.step');
    for (var i=0;i<steps.length;i++) steps[i].hidden = (steps[i].getAttribute('data-step') !== String(n));
    document.querySelector('.intro').hidden = (n !== 1);   /* 2歩目からは導入文を畳んで、質問を上に出す */
    $('bar').style.width = (Math.min(n,4)*25) + '%';
    $('steplab').textContent = Math.min(n,4) + ' / 4';
    $('steptitle').textContent = STEP_TITLES[n];
    window.scrollTo({{top:0, behavior:'smooth'}});
  }}
  form.addEventListener('click', function(e){{
    var b = e.target.closest('[data-back]'); if (b) go(Number(b.getAttribute('data-back')));
  }});

  function opt(name, o, multi){{
    var t = multi ? 'checkbox' : 'radio';
    var sub = o.サブ ? '<span class="sub">'+o.サブ+'</span>' : '';
    return '<label class="opt'+(multi?' check':'')+'"><input type="'+t+'" name="ui_'+name+'" value="'+o.値+'"'+(o.排他?' data-ex="1"':'')+'><span class="box"><span class="mark">✓</span><span>'+o.表示+'</span>'+sub+'</span></label>';
  }}

  /* ステップ1 */
  $('targets').innerHTML = D.対象.map(function(t){{ return opt('target', {{値:t.id, 表示:t.表示}}, false); }}).join('');
  $('targets').addEventListener('change', function(e){{
    state.target = D.対象.filter(function(t){{ return t.id === e.target.value; }})[0];
    state.ans = {{}};
    drawQs(); go(2);
  }});

  /* ステップ2 */
  function drawQs(){{
    var t = state.target;
    var html = '<div class="q"><div class="head"><h2>'+D.共通.前回.問い+'</h2></div><div class="opts">'+
      D.共通.前回.選択肢.map(function(o){{ return opt('prev', o, false); }}).join('')+'</div></div>';
    t.追加質問.forEach(function(q){{
      html += '<div class="q" style="margin-top:14px"><div class="head"><h2>'+q.問い+'</h2>'+(q.複数?'<p class="why">複数選べます</p>':'')+'</div><div class="opts">'+
        q.選択肢.map(function(o){{ return opt(q.id, o, !!q.複数); }}).join('')+'</div></div>';
    }});
    $('qs').innerHTML = html;
  }}
  $('qs').addEventListener('change', function(e){{
    var el = e.target; if (el.type !== 'checkbox') return;
    var group = $('qs').querySelectorAll('input[name="'+el.name+'"]');
    if (el.checked && el.getAttribute('data-ex')) {{
      for (var i=0;i<group.length;i++) if (group[i] !== el) group[i].checked = false;
    }} else if (el.checked) {{
      for (var j=0;j<group.length;j++) if (group[j].getAttribute('data-ex')) group[j].checked = false;
    }}
  }});

  function collect(){{
    var t = state.target, a = {{}};
    var p = $('qs').querySelector('input[name="ui_prev"]:checked');
    if (!p) return '「前回いつ洗ったか」を選んでください。';
    a.prev = p.value;
    for (var i=0;i<t.追加質問.length;i++) {{
      var q = t.追加質問[i];
      var sel = [].slice.call($('qs').querySelectorAll('input[name="ui_'+q.id+'"]:checked')).map(function(x){{ return x.value; }});
      if (!sel.length) return '「'+q.問い+'」に答えてください。';
      a[q.id] = q.複数 ? sel : sel[0];
    }}
    state.ans = a; return '';
  }}

  function weight(q, vals){{
    var w = 0; (Array.isArray(vals)?vals:[vals]).forEach(function(v){{
      var o = q.選択肢.filter(function(x){{ return x.値 === v; }})[0]; if (o && o.重み) w += o.重み; }});
    return w;
  }}
  function qById(id){{ return state.target.追加質問.filter(function(q){{ return q.id === id; }})[0]; }}

  /* 固定分岐。ルールは上から順に見て、最初に当たったものを採用する */
  function hantei(){{
    var a = state.ans, t = state.target;
    var symW = qById('sym') ? weight(qById('sym'), a.sym) : 0;
    var envW = qById('env') ? weight(qById('env'), a.env) : 0;
    for (var i=0;i<t.ルール.length;i++) {{
      var r = t.ルール[i], c = r.条件, ok = true;
      if (c.前回 && c.前回.indexOf(a.prev) < 0) ok = false;
      if (ok && c.sym含む) {{ var s = Array.isArray(a.sym)?a.sym:[a.sym]; ok = c.sym含む.some(function(v){{ return s.indexOf(v) >= 0; }}); }}
      if (ok && c.症状重み以下 !== undefined && !(symW <= c.症状重み以下)) ok = false;
      if (ok && c.症状重み以上 !== undefined && !(symW >= c.症状重み以上)) ok = false;
      if (ok && c.環境重み以下 !== undefined && !(envW <= c.環境重み以下)) ok = false;
      if (ok && c.環境重み以上 !== undefined && !(envW >= c.環境重み以上)) ok = false;
      if (ok) return r;
    }}
    return {{判定:'diy', 根拠:'状態がはっきりしないので、まずご自分でできることから試してください。写真を送っていただければ確認します。'}};
  }}

  function yen(n){{ return '¥' + Number(n).toLocaleString('ja-JP'); }}
  function menuName(){{
    var t = state.target;
    if (t.id === 'aircon' && state.ans.kind === 'auto') return t['メニュー_お掃除機能付き'];
    return t.メニュー;
  }}
  function drawGaisan(){{
    var name = menuName(), p = D.料金[name];
    var m = new Date().getMonth() + 1, busy = D.繁忙期.月.indexOf(m) >= 0;
    var total = p.単体 + (busy ? D.繁忙期.金額 : 0);
    var html = '<div class="ln"><span>'+name+'（1か所）</span><span class="v">'+yen(p.単体)+'</span></div>';
    if (busy) html += '<div class="ln"><span>繁忙期加算（'+D.繁忙期.月.join('・')+'月）</span><span class="v">+'+yen(D.繁忙期.金額)+'</span></div>';
    html += '<div class="ln sum"><span>目安（税込）</span><span class="v">'+yen(total)+'</span></div>';
    if (p.同時施工 && p.同時施工 < p.単体) html += '<div class="note">他の場所と同時に頼む場合、2か所目以降は '+yen(p.同時施工)+'（税込）です。</div>';
    if (p.所要) html += '<div class="note">作業時間の目安：'+p.所要+'</div>';
    html += '<div class="note">目安です。設置状況や汚れの程度で変わることがあり、その場合は作業前にご説明し、ご了承なく追加はしません。</div>';
    $('gaisan').innerHTML = html;
    state.gaisan = total;
  }}

  $('judge').addEventListener('click', function(){{
    var msg = collect(); $('e2').textContent = msg; if (msg) return;
    var r = hantei(); state.rule = r; state.verdict = r.判定;
    var v = D.判定[r.判定];
    $('verdict').innerHTML = '<div class="verdict '+r.判定+'"><span class="kind">'+state.target.表示+'｜判定</span><h2>'+v.見出し+'</h2><p class="konkyo">'+r.根拠+'</p><p class="meyasu">この判定は、いただいた回答から一般的な基準で出した目安です。' + (D.確認済み ? '基準は現場責任者が確認しています。' : '') + '</p></div>';
    $('gaisan-box').hidden = (r.判定 !== 'pro'); if (r.判定 === 'pro') drawGaisan();
    $('diy-box').hidden = (r.判定 === 'pro');
    if (r.判定 !== 'pro') {{
      $('diy').innerHTML = (state.target.DIYの手順||[]).map(function(s,i,arr){{ return '<li'+(i===arr.length-1?' class="stop"':'')+'>'+s+'</li>'; }}).join('');
    }}
    var nx = '';
    if (r.判定 === 'pro') nx += '<button type="button" class="btn lg" data-go="4" data-mode="tehai">手配を相談する（無料・電話は1回だけ）</button>';
    if (r.判定 === 'diy') nx += '<button type="button" class="btn lg" data-go="4" data-mode="photo">写真を送って確認してもらう（無料）</button>';
    if (r.判定 === 'wait') nx += '<a class="btn lg line" href="https://lin.ee/7kD9WGN" target="_blank" rel="noopener">次の洗いどきに知らせてもらう（LINE）</a>';
    nx += '<button type="button" class="btn ghost" data-go="1">別の場所も判定する</button>';
    $('next').innerHTML = nx; go(3);
  }});
  $('next').addEventListener('click', function(e){{
    var b = e.target.closest('[data-go]'); if (!b) return;
    var n = Number(b.getAttribute('data-go'));
    if (n === 4) $('tehai-title').textContent = (b.getAttribute('data-mode') === 'photo') ? '写真で確認してもらう' : '手配のご相談';
    if (n === 1) {{ var r = $('targets').querySelector('input:checked'); if (r) r.checked = false; }}
    go(n);
  }});

  /* 写真のサムネイル（判定には使っていない） */
  $('f-photo').addEventListener('change', function(){{
    state.files = [].slice.call(this.files).slice(0,3);
    $('thumbs').innerHTML = '';
    state.files.forEach(function(f){{ var img = document.createElement('img'); img.src = URL.createObjectURL(f); $('thumbs').appendChild(img); }});
  }});

  /* 送信。Netlify Forms へ同じ項目名でPOSTする（下の hidden form と合わせること） */
  var sending = false;
  $('send').addEventListener('click', function(){{
    if (sending || $('f-hp').value) return;
    var name = $('f-name').value.trim(), tel = $('f-tel').value.trim().replace(/[^0-9+]/g,'');
    if (!name) return $('e4').textContent = 'お名前を入れてください。';
    if (tel.length < 10) return $('e4').textContent = 'お電話番号を確認してください。';
    if (!$('f-area').value) return $('e4').textContent = 'お住まいの地域を選んでください。';
    if (!$('f-agree').checked) return $('e4').textContent = '提携事業者への情報提供に同意いただけない場合は、お受けできません。';
    $('e4').textContent = '';
    var fd = new FormData();
    var atai = {{
      'form-name': '{FORM_NAME}',
      '対象': state.target.表示,
      '判定': D.判定[state.verdict].短,
      '回答': JSON.stringify(state.ans),
      '概算': state.gaisan ? String(state.gaisan) : '',
      'お名前': name, 'お電話番号': tel, '地域': $('f-area').value, '希望時期': $('f-when').value,
      '気になること': $('f-note').value.trim(),
      '同意': '提携事業者への情報提供に同意',
      '流入元': (new URLSearchParams(location.search)).get('src') || ''
    }};
    Object.keys(atai).forEach(function(k){{ fd.append(k, atai[k]); }});
    state.files.forEach(function(f, i){{ fd.append('写真' + (i+1), f, f.name); }});
    sending = true; $('send').disabled = true; $('send').textContent = '送信しています…';
    fetch(location.pathname, {{ method:'POST', body: fd }}).then(function(r){{
      if (!r.ok) throw new Error('送信できませんでした（' + r.status + '）');
      $('hikae').textContent = '対象：'+atai['対象']+'\\n判定：'+atai['判定']+'\\n地域：'+atai['地域']+'\\n希望時期：'+(atai['希望時期']||'—');
      go(5);
    }}).catch(function(err){{
      sending = false; $('send').disabled = false; $('send').textContent = 'この内容で相談する';
      $('e4').textContent = String(err.message || err) + '　時間をおいてもう一度お試しください。';
    }});
  }});

  go(1);
}})();
</script>

<!-- Netlifyがデプロイ時にこのフォームを見つけて受け口を作る。画面には出さない。
     ★name を変えたら、送信側（atai）も必ず合わせること。 -->
<form name="{FORM_NAME}" data-netlify="true" netlify-honeypot="bot-field" enctype="multipart/form-data" hidden>
  <input type="hidden" name="form-name" value="{FORM_NAME}">
  <input type="text" name="bot-field">
  <input type="text" name="対象"><input type="text" name="判定"><input type="text" name="回答"><input type="text" name="概算">
  <input type="text" name="お名前"><input type="text" name="お電話番号"><input type="text" name="地域"><input type="text" name="希望時期">
  <input type="text" name="気になること"><input type="text" name="同意"><input type="text" name="流入元">
  <input type="file" name="写真1"><input type="file" name="写真2"><input type="file" name="写真3">
</form>
"""
    return head(f"{BRAND}｜そのエアコン、今洗うべき？ 30秒で判定", "エアコン・レンジフード・浴室・洗濯機を、今プロに頼むべきかを正直に判定します。「今は不要」と言うこともあります。") + body + foot()


def build_unei() -> str:
    body = f"""
  <div class="intro">
    <span class="eyebrow">運営者情報</span>
    <h1>「{BRAND}」について</h1>
    <p class="lead">このサイトは、ハウスクリーニング業を営む {UNEI} が運営しています。掃除を「必要なときだけ、必要な分だけ」頼めるように、まず判定をお伝えします。</p>
  </div>
  <div class="q">
    <dl class="unei-tbl">
      <dt>サイト名</dt><dd>{BRAND}（{BRAND_EN}）</dd>
      <dt>運営会社</dt><dd>{UNEI}</dd>
      <dt>所在地</dt><dd>{UNEI_ADDR}</dd>
      <dt>事業内容</dt><dd>ハウスクリーニング（東京都・千葉県・神奈川県）</dd>
      <dt>手配の仕組み</dt><dd>手配のご希望をいただいた場合、運営会社が受け付け、お住まいの地域とご希望日に合う事業者（運営会社または提携事業者）をご案内します。作業を行う事業者名と料金は、確定前に必ずお知らせし、ご了承いただいてから確定します。提携事業者から運営会社が紹介料を受け取ることがありますが、お客様の料金に上乗せはしません。</dd>
      <dt>判定について</dt><dd>回答内容から、あらかじめ定めた基準で「プロが要る／自分でできる／今は不要」の目安を出しています。実際の状態を保証するものではなく、作業前には必ず現物を確認してご説明します。</dd>
      <dt>個人情報</dt><dd>手配のためにいただいた情報は、作業を行う事業者への提供（同意いただいた場合）と、日程のご連絡にのみ使います。営業目的の連絡はしません。詳細は <a href="https://one-hitter.jp/privacy_policy/" target="_blank" rel="noopener">運営会社の個人情報の取扱い</a> をご覧ください。</dd>
      <dt>お問い合わせ</dt><dd>運営会社の <a href="https://one-hitter.jp/" target="_blank" rel="noopener">公式サイト</a> からお願いします。</dd>
    </dl>
  </div>
  <p style="margin-top:14px"><a class="btn ghost" href="./">判定に戻る</a></p>
"""
    return head(f"運営者情報｜{BRAND}", f"{BRAND}の運営者情報") + body + foot()


def main():
    rules = json.loads(RULES.read_text(encoding="utf-8"))
    prices = json.loads(PRICES.read_text(encoding="utf-8"))
    OUTDIR.mkdir(parents=True, exist_ok=True)
    (OUTDIR / "index.html").write_text(build_index(rules, prices), encoding="utf-8")
    (OUTDIR / "unei.html").write_text(build_unei(), encoding="utf-8")
    print("書き出しました:", OUTDIR / "index.html", OUTDIR / "unei.html")


if __name__ == "__main__":
    main()
