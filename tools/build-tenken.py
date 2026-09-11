#!/usr/bin/env python3
"""無料点検（型①「中を見せる」）のページ一式を lp/media/tenken/ に組み立てる。

設計は docs/無料点検-全体構造.md。ページは4つ＋運営者情報。

  index.html        お客様向け 申込ページ（noindex）。空き枠は slots.json（build-tenken-slots.py）から
  genba.html        渡辺さん向け 現場フォーム（写真・動画・ATP・所見3択・一言）。「その場申込のQR」を出す
  moushikomi.html   お客様のスマホで開く その場申込ページ（特商法の表示・電磁的交付の承諾・クーリングオフ告知）
  shomen.html       契約書面（印刷・PDF化用。tenken-inbox.py がここからPDFを作る）
  unei.html         運営者情報

料金は data/prices.json から入れる（手で書かない）。文面は docs/無料点検-文面-承認シート.md と同じものを使う。

使い方:
  python3 tools/build-tenken.py
"""
import datetime as dt
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import media_common as C  # noqa: E402

OUTDIR = C.ROOT / "lp" / "media" / "tenken"
BRAND = "無料点検"
BRAND_SUB = "ワンヒッター｜頼む前に、中を見ます"
FORM_MOUSHIKOMI = "tenken-moushikomi"   # 申込（お客様）
FORM_GENBA = "tenken-genba"             # 現場フォーム（渡辺さん）
FORM_KEIYAKU = "tenken-keiyaku"         # その場申込（契約の申込み）
GENBA_PIN = "2026"  # 現場フォームの簡易ロック。認証ではなく誤操作よけ。URL自体を公開しない

# 点検メニュー。つながる施工のメニュー名は prices.json のキーと一致させる
MENUS = [
    {"id": "A", "表示": "洗濯槽の裏側", "短": "洗濯槽", "道具": "内視鏡カメラ", "所要": "5〜8分",
     "施工": "洗濯機クリーニング", "対象": "縦型の洗濯機（ドラム式は槽のすき間にカメラが入らないため対象外）",
     "見えるもの": "洗濯槽と外側の槽のあいだに溜まっている黒いカビ（画面でその場でご覧いただきます）",
     "次回": "1年後"},
    {"id": "B", "表示": "追い焚き配管の中", "短": "追い焚き", "道具": "ATP測定器（ルミテスター）", "所要": "8〜12分",
     "施工": "追い焚き配管クリーニング", "対象": "追い焚き機能のある浴室",
     "見えるもの": "配管から出てくる水の汚れを数値（ATP）で測ります。数値はその場でお見せします",
     "次回": "半年後"},
]
OPTIONS = {"A": ["洗濯機 設置枠（防水パン）", "洗濯機 排水溝クリーニング"], "B": []}
SHOKEN = [("要洗浄", "洗浄をおすすめします"), ("様子見", "今回は様子見でよいと思います"), ("不要", "今回は不要です")]


def css():
    return """
.hero{display:flex;flex-direction:column;gap:10px;}
.menus{display:grid;grid-template-columns:1fr;gap:10px;}
.menu{border:1.5px solid var(--line);border-radius:12px;padding:14px 15px;background:var(--surface);display:flex;flex-direction:column;gap:6px;}
.menu h3{font-size:17px;}
.menu .m{font-size:13px;color:var(--muted);line-height:1.7;}
.slots{display:flex;flex-direction:column;gap:8px;}
.slot-day{font-size:13px;color:var(--muted);}
.times{display:flex;flex-wrap:wrap;gap:6px;}
.times label{cursor:pointer;}
.times input{position:absolute;opacity:0;}
.times span{display:inline-block;border:1.5px solid var(--line-strong);border-radius:8px;padding:6px 12px;font-family:"Barlow",sans-serif;font-size:15px;background:var(--surface);}
.times input:checked+span{border-color:var(--accent);background:var(--accent-soft);color:var(--accent-deep);font-weight:700;}
.nowaku{background:var(--surface-2);border-radius:10px;padding:12px 14px;font-size:13.5px;line-height:1.8;}
.fusen{font-size:12.5px;color:var(--muted);line-height:1.7;}
.shoken{display:grid;grid-template-columns:1fr;gap:8px;}
.big{font-size:22px;font-family:"Barlow",sans-serif;}
.keiyaku-sum{background:var(--surface-2);border-radius:10px;padding:12px 14px;}
.shomen h2{font-size:16px;margin-top:18px;border-left:4px solid var(--accent);padding-left:8px;}
.shomen .tbl th{width:30%;}
.shomen .sign{margin-top:12px;font-size:13px;}
.small-btns{display:flex;gap:8px;flex-wrap:wrap;}
"""


def hidden_form(name: str, fields: list, files: int = 0, videos: int = 0) -> str:
    inputs = "".join(f'<input type="text" name="{C.esc(f)}">' for f in fields)
    inputs += "".join(f'<input type="file" name="写真{i+1}">' for i in range(files))
    inputs += "".join(f'<input type="file" name="動画{i+1}">' for i in range(videos))
    return f"""
<!-- Netlifyがデプロイ時にこのフォームを見つけて受け口を作る。画面には出さない。
     ★name を変えたら、送信側も必ず合わせること。 -->
<form name="{name}" data-netlify="true" netlify-honeypot="bot-field" enctype="multipart/form-data" hidden>
  <input type="hidden" name="form-name" value="{name}"><input type="text" name="bot-field">{inputs}
</form>
"""


def js_common() -> str:
    return """
var $ = function(id){ return document.getElementById(id); };
var Q = new URLSearchParams(location.search);
function uketsukeId(prefix){
  var d = new Date(), p = function(n){ return (n<10?'0':'')+n; };
  var r = Math.random().toString(36).slice(2,6).toUpperCase();
  return prefix + d.getFullYear() + p(d.getMonth()+1) + p(d.getDate()) + '-' + r;
}
function postForm(formName, atai, files, onOk, onErr){
  var fd = new FormData(); fd.append('form-name', formName);
  Object.keys(atai).forEach(function(k){ fd.append(k, atai[k] == null ? '' : String(atai[k])); });
  (files||[]).forEach(function(f){ fd.append(f.name, f.file, f.file.name); });
  fetch(location.pathname, { method:'POST', body: fd }).then(function(r){
    if (!r.ok) throw new Error('送信できませんでした（' + r.status + '）'); onOk();
  }).catch(function(e){ onErr(String(e.message || e) + '　電波の良い場所で、もう一度お試しください。'); });
}
function jpDate(iso){ if(!iso) return ''; var d = new Date(iso+'T00:00:00'); if (isNaN(d)) return iso;
  return d.getFullYear()+'年'+(d.getMonth()+1)+'月'+d.getDate()+'日（'+'日月火水木金土'[d.getDay()]+'）'; }
function addDays(iso, n){ var d = new Date(iso+'T00:00:00'); d.setDate(d.getDate()+n); var p=function(x){return (x<10?'0':'')+x;}; return d.getFullYear()+'-'+p(d.getMonth()+1)+'-'+p(d.getDate()); }
"""


# ---------------------------------------------------------------- 申込ページ
def build_index(P: dict) -> str:
    m = P["menus"]
    menu_cards = ""
    for x in MENUS:
        price = m[x["施工"]]["単体"]
        menu_cards += f"""
    <label class="menu opt check"><input type="checkbox" name="menu" value="{x['id']}" style="position:absolute;opacity:0">
      <h3>{C.esc(x['表示'])}<span class="mark" style="float:right">✓</span></h3>
      <p class="m">{C.esc(x['道具'])}で、{C.esc(x['見えるもの'])}。所要 {C.esc(x['所要'])}。</p>
      <p class="m">対象：{C.esc(x['対象'])}</p>
      <p class="m">汚れていた場合のクリーニング料金：{C.esc(x['施工'])} <b class="num">{C.yen(price)}</b>（税込・追加請求なし）。汚れていなければ「今回は不要」とお伝えします。</p>
    </label>"""

    body = f"""
  <div class="intro hero">
    <span class="eyebrow">無料点検｜閑散期限定</span>
    <h1>洗濯槽の裏と、追い焚き配管の中。<br>頼む前に、無料でお見せします。</h1>
    <p class="lead">ふだん見えない場所を、内視鏡カメラとATP測定器で、<b>その場で一緒に見ます</b>。10分ほど。点検だけなら料金はいただきません。汚れていなければ「今回は不要」とお伝えします。</p>
    <div class="meiji">
      <b>先にお伝えしておきます。</b>伺うのは <b>{C.UNEI}</b>（江戸川区北葛西・ハウスクリーニング業）です。
      点検の結果、洗浄が必要と判断した場合は、<b>その場でクリーニングのご案内をすることがあります</b>（洗濯機クリーニング {C.yen(m['洗濯機クリーニング']['単体'])}／追い焚き配管クリーニング {C.yen(m['追い焚き配管クリーニング']['単体'])}、いずれも税込）。
      ご案内は1回だけ。「今回は結構です」で、その場で終わります。お申込みいただいても、施工は後日で、8日間はいつでもキャンセルできます。
    </div>
  </div>

  <form class="survey-form" id="f" onsubmit="return false;" novalidate>
    <div class="q">
      <div class="head"><h2>どこを見ますか？</h2><p class="why">両方でも構いません（所要は合計15〜20分）。</p></div>
      <div class="menus" id="menus">{menu_cards}</div>
      <div class="field" id="wm-kind" hidden style="margin-top:10px"><label for="f-wm">洗濯機の種類</label>
        <select id="f-wm"><option value="">選んでください</option><option>縦型</option><option>ドラム式</option><option>わからない</option></select>
        <p class="hint" id="wm-hint"></p></div>
      <p class="err" id="e1"></p>
    </div>

    <div class="q">
      <div class="head"><h2>ご希望の日時</h2><p class="why">出しているのは、近くで作業がある日の空き時間だけです。枠が無い場合は、次の枠が出たときにLINEでお知らせします。</p></div>
      <div class="slots" id="slots"><p class="note">空き枠を読み込んでいます…</p></div>
      <p class="err" id="e2"></p>
    </div>

    <div class="q">
      <div class="head"><h2>ご連絡先</h2></div>
      <div class="field"><label for="f-name">お名前</label><input id="f-name" type="text" autocomplete="name" placeholder="例：山田"></div>
      <div class="field"><label for="f-tel">お電話番号</label><input id="f-tel" type="tel" inputmode="tel" autocomplete="tel" placeholder="例：09012345678"><p class="hint">前日にSMSでご連絡します。営業の電話はしません。</p></div>
      <div class="field"><label for="f-addr">ご住所</label><input id="f-addr" type="text" autocomplete="street-address" placeholder="例：江戸川区北葛西5-14-11 ◯◯マンション101"><p class="hint">点検に伺うため、番地までお願いします。</p></div>
      <div class="field"><label for="f-mail">メールアドレス（任意）</label><input id="f-mail" type="email" inputmode="email" autocomplete="email" placeholder="報告書の送付先。空欄ならSMSで送ります"></div>
      <div class="field"><label for="f-note">気になること（任意）</label><textarea id="f-note" placeholder="例：洗濯物に黒いカスが付く／お湯張りのときに黒い粒が出る"></textarea></div>
      <label class="agree"><input type="checkbox" id="f-agree1"><span>点検の際に、クリーニングのご案内があることを了解しました。</span></label>
      <label class="agree"><input type="checkbox" id="f-agree2"><span>いただいた情報は、点検の日程連絡と報告書の送付に使い、同意なく第三者に渡さないことを確認しました（提携事業者が施工する場合は、事前にお知らせします）。</span></label>
      <input type="text" id="f-hp" name="bot-field" tabindex="-1" autocomplete="off" class="hp" aria-hidden="true">
      <p class="err" id="e3"></p>
      <button type="button" class="btn lg" id="send">無料点検を申し込む</button>
      <p class="fusen" style="margin-top:8px">点検は「ご依頼をいただいたお宅」にだけ伺います。飛び込みや電話でのお誘いは一切していません。</p>
    </div>

    <section class="q done" id="done" hidden>
      <div class="head"><h2>受け付けました。</h2></div>
      <p class="why" style="font-size:13.5px">受付番号 <b id="d-id" class="num"></b><br>
      確認のご連絡をSMS（メールをいただいた方はメール）でお送りします。前日にもう一度ご連絡します。<br>
      当日は <b id="d-when"></b> に、{C.UNEI}のスタッフが伺います（所要 約10〜20分）。</p>
      <div class="branch"><b>控え</b><p id="hikae" style="white-space:pre-wrap"></p></div>
      <p class="note" style="margin-top:8px">ご都合が変わったときは {C.UNEI_TEL} へお電話ください。</p>
    </section>
  </form>

<script>
{js_common()}
var MENUS = {json.dumps(MENUS, ensure_ascii=False)};
(function(){{
  var state = {{ slot:null }};
  /* メニュー */
  $('menus').addEventListener('change', function(){{
    var a = $('menus').querySelector('input[value="A"]').checked;
    $('wm-kind').hidden = !a;
  }});
  $('f-wm').addEventListener('change', function(){{
    $('wm-hint').textContent = (this.value === 'ドラム式') ? 'ドラム式は槽のすき間にカメラが入らないため、洗濯槽の点検はお受けできません。追い焚きの点検か、通常の洗濯機クリーニングのご相談は承ります。' : '';
  }});
  /* 空き枠 */
  fetch('./slots.json', {{cache:'no-store'}}).then(function(r){{ return r.ok ? r.json() : null; }}).then(drawSlots).catch(function(){{ drawSlots(null); }});
  function drawSlots(d){{
    var days = (d && d.days) || [];
    if (!days.length) {{
      $('slots').innerHTML = '<div class="nowaku">いま出せる枠がありません。<br>無料点検は、近くで作業がある日の空き時間にだけ伺っています（繁忙期の5〜7月・12月はお休みです）。<br><a class="btn line lg" style="margin-top:8px" href="{C.LINE_URL}" target="_blank" rel="noopener">次の枠が出たらLINEで知らせてもらう</a></div>';
      return;
    }}
    var html = '';
    days.forEach(function(day, i){{
      html += '<div class="slot-day">'+day.label+(day.area?'（'+day.area+'の近く）':'')+'</div><div class="times">' +
        day.times.map(function(t){{ return '<label><input type="radio" name="slot" value="'+day.date+' '+t+'"><span>'+t+'</span></label>'; }}).join('') + '</div>';
    }});
    if (d.generatedLabel) html += '<p class="note">空き状況 '+d.generatedLabel+' 時点</p>';
    $('slots').innerHTML = html;
    $('slots').addEventListener('change', function(e){{ if (e.target.name === 'slot') state.slot = e.target.value; }});
  }}
  /* 送信 */
  var sending = false;
  $('send').addEventListener('click', function(){{
    if (sending || $('f-hp').value) return;
    var menus = [].slice.call($('menus').querySelectorAll('input:checked')).map(function(x){{ return x.value; }});
    $('e1').textContent = ''; $('e2').textContent = ''; $('e3').textContent = '';
    if (!menus.length) return $('e1').textContent = '見る場所を1つ以上選んでください。';
    if (menus.indexOf('A') >= 0 && $('f-wm').value === 'ドラム式') return $('e1').textContent = 'ドラム式は洗濯槽の点検の対象外です。チェックを外してください。';
    if (!state.slot) return $('e2').textContent = 'ご希望の日時を選んでください。枠が無い場合はLINEでお知らせします。';
    var name = $('f-name').value.trim(), tel = $('f-tel').value.trim().replace(/[^0-9+]/g,''), addr = $('f-addr').value.trim();
    if (!name) return $('e3').textContent = 'お名前を入れてください。';
    if (tel.length < 10) return $('e3').textContent = 'お電話番号を確認してください。';
    if (addr.length < 6) return $('e3').textContent = 'ご住所を番地まで入れてください。';
    if (!$('f-agree1').checked || !$('f-agree2').checked) return $('e3').textContent = '2つの確認にチェックをお願いします。';
    var id = uketsukeId('T');
    var atai = {{ '受付番号': id, '点検メニュー': menus.map(function(v){{ return MENUS.filter(function(m){{return m.id===v;}})[0].表示; }}).join('・'),
      '洗濯機の種類': $('f-wm').value, '希望日時': state.slot, 'お名前': name, 'お電話番号': tel, 'ご住所': addr, 'メール': $('f-mail').value.trim(),
      '気になること': $('f-note').value.trim(), '同意': '勧誘あり了解・個人情報の利用目的確認', '流入元': Q.get('src') || '', '送信時刻': new Date().toISOString() }};
    sending = true; $('send').disabled = true; $('send').textContent = '送信しています…';
    postForm('{FORM_MOUSHIKOMI}', atai, [], function(){{
      $('d-id').textContent = id; $('d-when').textContent = jpDate(state.slot.slice(0,10)) + ' ' + state.slot.slice(11);
      $('hikae').textContent = '点検：'+atai['点検メニュー']+'\\n日時：'+atai['希望日時']+'\\nご住所：'+addr;
      document.querySelectorAll('#f > .q:not(#done)').forEach(function(el){{ el.hidden = true; }}); document.querySelector('.intro').hidden = true;
      $('done').hidden = false; window.scrollTo({{top:0,behavior:'smooth'}});
    }}, function(msg){{ sending = false; $('send').disabled = false; $('send').textContent = '無料点検を申し込む'; $('e3').textContent = msg; }});
  }});
}})();
</script>
""" + hidden_form(FORM_MOUSHIKOMI, ["受付番号", "点検メニュー", "洗濯機の種類", "希望日時", "お名前", "お電話番号", "ご住所", "メール", "気になること", "同意", "流入元", "送信時刻"])
    return C.head("頼む前に、無料で中を見ます｜ワンヒッターの無料点検", "洗濯槽の裏側と追い焚き配管の中を、内視鏡カメラとATP測定器でその場でお見せします。点検だけなら無料。汚れていなければ「今回は不要」とお伝えします。", BRAND, BRAND_SUB, css()) + body + C.foot(BRAND, "点検は本人のお申込みがあったお宅にだけ伺います。飛び込み・電話勧誘はしません。")


# ---------------------------------------------------------------- 現場フォーム
def build_genba(P: dict) -> str:
    m = P["menus"]
    menu_opts = "".join(f'<option value="{x["id"]}">{C.esc(x["表示"])}（{C.esc(x["道具"])}）</option>' for x in MENUS)
    menu_opts += '<option value="C">エアコン施工中の汚水（他の台のご案内）</option>'
    shoken = "".join(f'<label class="opt"><input type="radio" name="shoken" value="{k}"><span class="box"><span class="mark">✓</span><span>{k}<span class="sub">{v}</span></span></span></label>' for k, v in SHOKEN)
    body = f"""
  <div class="pin" id="pin">
    <div class="q"><div class="head"><h2>現場フォーム</h2><p class="why">スタッフ用です。</p></div>
      <div class="field"><label for="pin-in">番号</label><input id="pin-in" type="tel" inputmode="numeric" autocomplete="off"></div>
      <button type="button" class="btn lg" id="pin-ok">開く</button><p class="err" id="pin-err"></p></div>
  </div>

  <form class="survey-form" id="f" onsubmit="return false;" novalidate hidden>
    <div class="intro"><span class="eyebrow">スタッフ用</span><h1>点検の記録</h1>
      <p class="lead" style="font-size:14px">写真を撮って、3つ選んで、送るだけ。報告書の文章は自動で作ります。<br><b>お客様と一緒に画面を見てから</b>入力してください。</p></div>

    <div class="q">
      <div class="field"><label for="g-id">受付番号（申込メールにある T… の番号。ついで点検なら空欄）</label><input id="g-id" type="text" autocomplete="off" placeholder="例：T20261015-AB3K"></div>
      <div class="field"><label for="g-name">お客様のお名前</label><input id="g-name" type="text" autocomplete="off" placeholder="例：山田"></div>
      <div class="field"><label for="g-menu">見た場所</label><select id="g-menu"><option value="">選んでください</option>{menu_opts}</select></div>
      <div class="field"><label for="g-tsuide">きっかけ</label><select id="g-tsuide"><option>申込があった点検</option><option>施工のついで</option></select></div>
      <div class="field"><label for="g-kishu">機種・年数（分かれば）</label><input id="g-kishu" type="text" placeholder="例：パナソニック 縦型 2018年ごろ"></div>
      <div class="field" id="atp-box" hidden><label for="g-atp">ATPの数値（RLU）</label><input id="g-atp" type="number" inputmode="numeric" placeholder="例：1200"><p class="hint">採水前に「これから測ります」と一言。数値はそのままお見せする。</p></div>
    </div>

    <div class="q">
      <div class="head"><h2>写真（3〜5枚）と動画（1本・30秒まで）</h2><p class="why">お宅が分かるもの（表札・部屋全体・私物）を写さない。槽の中・循環口・バケツだけ。</p></div>
      <div class="field"><label for="g-photo">写真</label><input id="g-photo" type="file" accept="image/*" capture="environment" multiple><div class="thumbs" id="thumbs"></div></div>
      <div class="field"><label for="g-video">動画（任意）</label><input id="g-video" type="file" accept="video/*" capture="environment"><p class="hint">内視鏡アプリで録った動画をここに。大きすぎると送れないことがあります（目安30秒）。</p></div>
    </div>

    <div class="q">
      <div class="head"><h2>所見（1つ）</h2><p class="why">見たままで。「危険」「壊れる」は言わない・書かない。</p></div>
      <div class="opts shoken">{shoken}</div>
      <div class="field" style="margin-top:8px"><label for="g-hitokoto">お客様に伝えた一言（報告書にそのまま載ります）</label><textarea id="g-hitokoto" placeholder="例：槽の裏側の下のほうに黒いカビが帯状に付いていました。市販のクリーナーでは届かない場所です。"></textarea></div>
    </div>

    <div class="q">
      <div class="head"><h2>その場のご案内</h2><p class="why">所見が「要洗浄」のときだけ。ご案内は1回。「今回は結構です」と言われたら、ここで終わり。</p></div>
      <div class="opts">
        <label class="opt"><input type="radio" name="annai" value="QRを出した"><span class="box"><span class="mark">✓</span><span>ご案内して、申込QRを出した</span></span></label>
        <label class="opt"><input type="radio" name="annai" value="決めない→報告書"><span class="box"><span class="mark">✓</span><span>「今晩、報告書を送ります」で帰る</span></span></label>
        <label class="opt"><input type="radio" name="annai" value="案内なし"><span class="box"><span class="mark">✓</span><span>ご案内していない（不要・様子見・ついで）</span></span></label>
      </div>
      <div id="qrbox" class="qr" hidden style="margin-top:10px"><div id="qrcode"></div><p class="note" style="text-align:center">お客様のスマホで読んでもらう。料金と日程はお客様の画面に出ます。</p><a id="qrlink" href="#" target="_blank" rel="noopener" class="note">このスマホで開く（お客様に渡す場合）</a></div>
      <button type="button" class="btn ghost" id="mkqr" style="margin-top:8px">申込QRを出す</button>
    </div>

    <div class="q">
      <input type="text" id="g-hp" name="bot-field" tabindex="-1" autocomplete="off" class="hp" aria-hidden="true">
      <p class="err" id="ge"></p>
      <button type="button" class="btn lg" id="send">記録を送る</button>
    </div>

    <section class="q done" id="done" hidden><div class="head"><h2>送りました。</h2></div>
      <p class="why" style="font-size:13.5px">報告書は今日18時までに自動で作って、お客様へ送ります。次の現場へどうぞ。</p>
      <button type="button" class="btn ghost" onclick="location.reload()">次の記録</button></section>
  </form>

<script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
<script>
{js_common()}
var MENUS = {json.dumps(MENUS, ensure_ascii=False)};
(function(){{
  var PIN = '{GENBA_PIN}';
  function open(){{ $('pin').hidden = true; $('f').hidden = false; }}
  try {{ if (localStorage.getItem('genba-ok') === '1') open(); }} catch(e) {{}}
  $('pin-ok').addEventListener('click', function(){{
    if ($('pin-in').value.trim() === PIN) {{ try {{ localStorage.setItem('genba-ok','1'); }} catch(e) {{}} open(); }} else $('pin-err').textContent = '番号が違います。';
  }});
  $('g-menu').addEventListener('change', function(){{ $('atp-box').hidden = (this.value !== 'B'); }});
  var files = [];
  $('g-photo').addEventListener('change', function(){{
    files = [].slice.call(this.files).slice(0,5); $('thumbs').innerHTML = '';
    files.forEach(function(f){{ var img = document.createElement('img'); img.src = URL.createObjectURL(f); $('thumbs').appendChild(img); }});
  }});
  function keiyakuUrl(){{
    var id = $('g-id').value.trim() || uketsukeId('G'); $('g-id').value = id;
    var u = new URL('moushikomi.html', location.href);
    u.searchParams.set('id', id); u.searchParams.set('menu', $('g-menu').value || 'A'); u.searchParams.set('name', $('g-name').value.trim());
    return u.toString();
  }}
  $('mkqr').addEventListener('click', function(){{
    if (!$('g-menu').value || $('g-menu').value === 'C') return $('ge').textContent = 'エアコンの他の台は、通常の見積・予約の型で。QRは洗濯槽／追い焚きのみ。';
    var url = keiyakuUrl(); $('qrcode').innerHTML = ''; new QRCode($('qrcode'), {{ text:url, width:220, height:220 }});
    $('qrlink').href = url; $('qrbox').hidden = false;
    var r = document.querySelector('input[name="annai"][value="QRを出した"]'); if (r) r.checked = true;
  }});
  var sending = false;
  $('send').addEventListener('click', function(){{
    if (sending || $('g-hp').value) return;
    var sh = document.querySelector('input[name="shoken"]:checked'), an = document.querySelector('input[name="annai"]:checked');
    if (!$('g-name').value.trim()) return $('ge').textContent = 'お客様のお名前を入れてください。';
    if (!$('g-menu').value) return $('ge').textContent = '見た場所を選んでください。';
    if ($('g-menu').value !== 'C' && files.length < 1) return $('ge').textContent = '写真を1枚以上。';
    if (!sh) return $('ge').textContent = '所見を1つ選んでください。';
    if (!an) return $('ge').textContent = 'その場のご案内の結果を選んでください。';
    if (sh.value === '要洗浄' && an.value === '案内なし' && $('g-tsuide').value !== '施工のついで') return $('ge').textContent = '要洗浄なら、ご案内を1回してください（お断りされたら「報告書を送ります」を選ぶ）。';
    $('ge').textContent = '';
    var menu = $('g-menu').value, mname = menu === 'C' ? 'エアコン施工中の汚水' : MENUS.filter(function(x){{return x.id===menu;}})[0].表示;
    var atai = {{ '受付番号': $('g-id').value.trim() || uketsukeId('G'), 'お名前': $('g-name').value.trim(), '見た場所': mname, 'メニューID': menu, 'きっかけ': $('g-tsuide').value,
      '機種年数': $('g-kishu').value.trim(), 'ATP': $('g-atp').value, '所見': sh.value, '一言': $('g-hitokoto').value.trim(), 'その場の案内': an.value, '送信時刻': new Date().toISOString() }};
    var fl = files.map(function(f,i){{ return {{name:'写真'+(i+1), file:f}}; }});
    if ($('g-video').files[0]) fl.push({{name:'動画1', file:$('g-video').files[0]}});
    sending = true; $('send').disabled = true; $('send').textContent = '送信しています…（動画があると時間がかかります）';
    postForm('{FORM_GENBA}', atai, fl, function(){{ $('f').querySelectorAll('.q:not(#done), .intro').forEach(function(el){{ el.hidden = true; }}); $('done').hidden = false; window.scrollTo(0,0); }},
      function(msg){{ sending = false; $('send').disabled = false; $('send').textContent = '記録を送る'; $('ge').textContent = msg; }});
  }});
}})();
</script>
""" + hidden_form(FORM_GENBA, ["受付番号", "お名前", "見た場所", "メニューID", "きっかけ", "機種年数", "ATP", "所見", "一言", "その場の案内", "送信時刻"], files=5, videos=1)
    return C.head("現場フォーム｜無料点検", "スタッフ用", BRAND, BRAND_SUB, css()) + body + C.foot(BRAND, "スタッフ用ページ")


# ---------------------------------------------------------------- 契約書面の共通部品
def cooling_off_html(uketori: str = "この書面を受け取った日") -> str:
    return f"""
<div class="akawaku">
  <h3>クーリング・オフのお知らせ（必ずお読みください）</h3>
  1. お客様は、<b>{C.esc(uketori)}を含めて8日間</b>は、書面または電磁的記録（メール・LINEなど）により、<b>無条件で</b>この契約の申込みの撤回または契約の解除（クーリング・オフ）を行うことができます。<br>
  2. クーリング・オフは、その通知を発した時に効力を生じます。<br>
  3. クーリング・オフの場合、当社は損害賠償や違約金を請求しません。すでに役務（クリーニング）の提供を受けている場合でも、その対価は請求しません。すでにお支払いいただいた金銭がある場合は、速やかに全額をお返しします。<br>
  4. 役務の提供により土地・建物その他の工作物の現状が変更された場合、無償で元に戻すことをお客様は請求できます。<br>
  5. 通知先：{C.UNEI}（{C.UNEI_ADDR}／電話 {C.UNEI_TEL}／または、この書面をお送りしたメール・LINEへの返信）。<br>
  <span class="note">当社から事実と異なることを告げられ、または威迫されて、期間内にクーリング・オフを行わなかった場合は、改めてクーリング・オフができる旨の書面を受け取った日から8日間、クーリング・オフができます。</span>
</div>
"""


def shomen_table_js() -> str:
    """契約書面の表を、URLのパラメータ（またはフォームの値）から組むJS。moushikomi.html と shomen.html で共用"""
    return """
function shomenRows(v){
  return [
    ['書面の種類', '役務提供契約の申込書面（兼 契約書面）'],
    ['申込番号', v.id],
    ['申込日', v.date],
    ['事業者', UNEI.name + '<br>' + UNEI.addr + '<br>電話 ' + UNEI.tel + '<br>担当者：' + UNEI.tantou + '（点検担当：' + (v.staff||'当社スタッフ') + '）'],
    ['お客様', v.name + ' 様<br>' + v.addr + '<br>電話 ' + v.tel + (v.mail ? '<br>' + v.mail : '')],
    ['役務の内容', v.menu + '（' + v.detail + '）' + (v.opts ? '<br>オプション：' + v.opts : '')],
    ['役務の提供時期', v.when + '（施工の所要 ' + v.dur + '）'],
    ['役務の対価（税込）', '<span class="v">' + v.price + '</span>' + (v.discount ? '<br>' + v.discount : '') + '<br>上記以外の費用（出張費・駐車場代・追加作業費など）は請求しません。'],
    ['支払時期・方法', '施工完了後、当日にお支払い。お支払い方法は、施工日確定のご連絡の際にご案内します。'],
    ['契約の解除', 'クーリング・オフ期間（下記）を過ぎた後も、施工日の前日までのキャンセルは無料です。当日のキャンセルも費用はいただきませんが、次回のご予約はご相談させてください。'],
    ['書面の交付方法', v.denshi ? 'お客様の承諾により、電磁的方法（メール／LINE）で交付' : '紙で交付']
  ];
}
function shomenHtml(v){
  return '<table class="tbl">' + shomenRows(v).map(function(r){ return '<tr><th>'+r[0]+'</th><td>'+r[1]+'</td></tr>'; }).join('') + '</table>';
}
"""


def unei_js() -> str:
    return f"var UNEI = {json.dumps({'name': C.UNEI, 'addr': C.UNEI_ADDR, 'tel': C.UNEI_TEL, 'tantou': C.UNEI_TANTOU}, ensure_ascii=False)};"


# ---------------------------------------------------------------- その場申込ページ
def build_moushikomi(P: dict) -> str:
    m, o = P["menus"], P["opts"]
    menu_js = {}
    for x in MENUS:
        mm = m[x["施工"]]
        menu_js[x["id"]] = {"施工": x["施工"], "価格": mm["単体"], "同時": mm.get("同時施工"), "所要": mm.get("所要", ""),
                            "オプション": [{"名称": k, "価格": o[k]["価格"]} for k in OPTIONS[x["id"]] if k in o], "点検": x["表示"]}
    waribiki = P["raw"].get("早期予約割引", {})
    body = f"""
  <div class="intro">
    <span class="eyebrow">その場でのお申込み</span>
    <h1 id="h1">クリーニングのお申込み</h1>
    <p class="lead" style="font-size:14.5px">いま見ていただいた汚れを、後日、分解して洗います。<b>お申込みは今日でも、施工は後日。8日間はいつでも無条件でキャンセルできます。</b></p>
    <div class="meiji"><b>{C.UNEI}</b>（{C.UNEI_ADDR}・電話 {C.UNEI_TEL}）が、<b>クリーニングのご契約をおすすめする目的</b>でご案内しています。役務の内容と料金は下のとおりです。お断りいただいても、無料点検の報告書は今日中にお送りします。</div>
  </div>

  <form class="survey-form" id="f" onsubmit="return false;" novalidate>
    <div class="q">
      <div class="head"><h2>内容と料金（税込・追加請求なし）</h2></div>
      <div class="keiyaku-sum" id="sum"></div>
      <div id="opts" style="margin-top:8px"></div>
    </div>

    <div class="q">
      <div class="head"><h2>施工のご希望日</h2><p class="why">正式な日時は、明日までにSMSでご連絡して確定します。8日以内の施工をご希望の場合も、8日以内ならキャンセルできます。</p></div>
      <div class="field"><label for="k-date">第1希望の日</label><input id="k-date" type="date"></div>
      <div class="field"><label for="k-band">時間帯</label><select id="k-band"><option value="">選んでください</option><option>午前（9〜12時）</option><option>午後（13〜17時）</option><option>夕方（17時〜）</option><option>いつでも</option></select></div>
    </div>

    <div class="q">
      <div class="head"><h2>お客様の情報</h2></div>
      <div class="field"><label for="k-name">お名前（フルネーム）</label><input id="k-name" type="text" autocomplete="name"></div>
      <div class="field"><label for="k-tel">お電話番号</label><input id="k-tel" type="tel" inputmode="tel" autocomplete="tel"></div>
      <div class="field"><label for="k-addr">ご住所（施工先）</label><input id="k-addr" type="text" autocomplete="street-address" placeholder="例：江戸川区北葛西5-14-11 ◯◯マンション101"></div>
      <div class="field"><label for="k-mail">メールアドレス</label><input id="k-mail" type="email" inputmode="email" autocomplete="email"><p class="hint">契約書面をお送りします。メールをお使いでない方は、LINEかSMSでお送りするので空欄で構いません。</p></div>
    </div>

    <div class="q">
      <div class="head"><h2>書面のお受け取り</h2></div>
      <label class="agree"><input type="checkbox" id="k-denshi"><span><b>契約書面を、紙ではなく電磁的方法（メール／LINE／SMSのリンク）で受け取ることを承諾します。</b>紙をご希望の場合はチェックせず、スタッフにお伝えください（後日、郵送します）。</span></label>
      {cooling_off_html("書面を受け取った日")}
      <label class="agree" style="margin-top:10px"><input type="checkbox" id="k-yonda"><span>上のクーリング・オフの説明を読みました。</span></label>
      <input type="text" id="k-hp" name="bot-field" tabindex="-1" autocomplete="off" class="hp" aria-hidden="true">
      <p class="err" id="ke"></p>
      <button type="button" class="btn lg" id="send">この内容で申し込む</button>
      <p class="note" style="margin-top:8px">送信後、この画面に申込書面が表示されます。同じ内容を、メール（またはLINE／SMS）でもお送りします。</p>
    </div>

    <section class="q done shomen" id="done" hidden>
      <div class="head"><h2>お申込みを受け付けました。</h2></div>
      <p class="why" style="font-size:13.5px">下が申込書面です。<b>スクリーンショットで保存</b>してください。同じものを <span id="d-to"></span> にもお送りします。施工日は明日までにSMSで確定のご連絡をします。</p>
      <div id="shomen"></div>
      <div style="margin-top:12px">{cooling_off_html("書面を受け取った日")}</div>
      <div class="small-btns noprint" style="margin-top:12px"><button type="button" class="btn ghost" onclick="window.print()">印刷・PDFで保存</button></div>
    </section>
  </form>

<script>
{js_common()}
{unei_js()}
{shomen_table_js()}
var M = {json.dumps(menu_js, ensure_ascii=False)};
var WARIBIKI = {json.dumps({k: v for k, v in waribiki.items() if not k.startswith('_')}, ensure_ascii=False)};
(function(){{
  var menu = Q.get('menu') || 'A', id = Q.get('id') || uketsukeId('G'), staff = Q.get('staff') || '';
  var mm = M[menu] || M.A;
  if (Q.get('name')) $('k-name').value = Q.get('name');
  function waribikiRitsu(d){{
    if (!d) return 0; var mo = new Date(d+'T00:00:00').getMonth()+1;
    var k = (mo<=2)?'1-2月':(mo<=4)?'3-4月':(mo<=7)?'5-7月':(mo<=10)?'8-10月':'11-12月'; return WARIBIKI[k] || 0;
  }}
  function draw(){{
    var opts = [].slice.call(document.querySelectorAll('#opts input:checked')).map(function(x){{ return mm.オプション[Number(x.value)]; }});
    var base = mm.価格, sumOpt = opts.reduce(function(s,o){{ return s+o.価格; }}, 0);
    var r = waribikiRitsu($('k-date').value), disc = Math.round(base * r);
    var total = base - disc + sumOpt;
    var h = '<div class="ln" style="display:flex;justify-content:space-between"><span>'+mm.施工+'</span><span class="num">'+base.toLocaleString()+'円</span></div>';
    if (disc) h += '<div class="ln" style="display:flex;justify-content:space-between;color:var(--ok)"><span>閑散期割引（'+Math.round(r*100)+'%）</span><span class="num">−'+disc.toLocaleString()+'円</span></div>';
    opts.forEach(function(o){{ h += '<div class="ln" style="display:flex;justify-content:space-between"><span>'+o.名称+'</span><span class="num">'+o.価格.toLocaleString()+'円</span></div>'; }});
    h += '<div class="ln" style="display:flex;justify-content:space-between;font-size:20px;font-weight:900;border-top:1px solid var(--line-strong);margin-top:6px;padding-top:6px"><span>合計（税込）</span><span class="num">'+total.toLocaleString()+'円</span></div>';
    h += '<p class="note">所要 '+mm.所要+'。出張費・駐車場代・追加作業費は一切ありません。</p>';
    $('sum').innerHTML = h; return {{total:total, disc:disc, r:r, opts:opts}};
  }}
  $('opts').innerHTML = mm.オプション.length ? '<p class="note">ご希望があれば（任意）</p>' + mm.オプション.map(function(o,i){{ return '<label class="agree"><input type="checkbox" value="'+i+'"><span>'+o.名称+'　'+o.価格.toLocaleString()+'円</span></label>'; }}).join('') : '';
  $('opts').addEventListener('change', draw); $('k-date').addEventListener('change', draw); draw();
  var sending = false;
  $('send').addEventListener('click', function(){{
    if (sending || $('k-hp').value) return;
    var name = $('k-name').value.trim(), tel = $('k-tel').value.trim().replace(/[^0-9+]/g,''), addr = $('k-addr').value.trim(), mail = $('k-mail').value.trim();
    if (!$('k-date').value || !$('k-band').value) return $('ke').textContent = '施工のご希望日と時間帯を選んでください。';
    if (name.length < 2) return $('ke').textContent = 'お名前をフルネームで入れてください。';
    if (tel.length < 10) return $('ke').textContent = 'お電話番号を確認してください。';
    if (addr.length < 6) return $('ke').textContent = 'ご住所を番地まで入れてください。';
    if (!$('k-yonda').checked) return $('ke').textContent = 'クーリング・オフの説明をお読みのうえ、チェックをお願いします。';
    var g = draw(), today = new Date(), p = function(n){{ return (n<10?'0':'')+n; }};
    var todayIso = today.getFullYear()+'-'+p(today.getMonth()+1)+'-'+p(today.getDate());
    var v = {{ id:id, date: jpDate(todayIso), staff: staff, name:name, addr:addr, tel:tel, mail:mail, menu: mm.施工, detail: '無料点検（'+mm.点検+'）で確認した箇所の分解洗浄',
      opts: g.opts.map(function(o){{ return o.名称+' '+o.価格.toLocaleString()+'円'; }}).join('、'), when: jpDate($('k-date').value)+' '+$('k-band').value+'（第1希望。明日までにSMSで確定）', dur: mm.所要,
      price: g.total.toLocaleString()+'円', discount: g.disc ? '閑散期割引 '+Math.round(g.r*100)+'%（'+g.disc.toLocaleString()+'円引き）を含む' : '', denshi: $('k-denshi').checked }};
    var atai = {{ '申込番号': id, '受付番号': Q.get('id')||'', 'お名前': name, 'お電話番号': tel, 'ご住所': addr, 'メール': mail, '役務': mm.施工, '点検メニュー': mm.点検, 'オプション': v.opts,
      '希望日': $('k-date').value, '時間帯': $('k-band').value, '合計': String(g.total), '割引率': String(g.r), '電磁的交付の承諾': $('k-denshi').checked ? '承諾' : '紙を希望', 'クーリングオフ説明': '読了チェック',
      '書面': JSON.stringify(v), '送信時刻': new Date().toISOString(), '流入元': Q.get('src') || '点検' }};
    sending = true; $('send').disabled = true; $('send').textContent = '送信しています…';
    postForm('{FORM_KEIYAKU}', atai, [], function(){{
      $('d-to').textContent = mail ? mail : 'LINE／SMS'; $('shomen').innerHTML = shomenHtml(v);
      document.querySelectorAll('#f > .q:not(#done)').forEach(function(el){{ el.hidden = true; }}); document.querySelector('.intro').hidden = true;
      $('done').hidden = false; window.scrollTo({{top:0,behavior:'smooth'}});
    }}, function(msg){{ sending = false; $('send').disabled = false; $('send').textContent = 'この内容で申し込む'; $('ke').textContent = msg; }});
  }});
}})();
</script>
""" + hidden_form(FORM_KEIYAKU, ["申込番号", "受付番号", "お名前", "お電話番号", "ご住所", "メール", "役務", "点検メニュー", "オプション", "希望日", "時間帯", "合計", "割引率", "電磁的交付の承諾", "クーリングオフ説明", "書面", "送信時刻", "流入元"])
    return C.head("クリーニングのお申込み｜ワンヒッター 無料点検", "無料点検の場でのお申込み", BRAND, BRAND_SUB, css()) + body + C.foot(BRAND, "お申込み後8日間は無条件でキャンセルできます。")


# ---------------------------------------------------------------- 契約書面（印刷用）
def build_shomen() -> str:
    body = f"""
  <div class="shomen">
    <div class="intro"><span class="eyebrow">役務提供契約 申込書面（兼 契約書面）</span><h1 style="font-size:20px">ハウスクリーニング 申込書面</h1>
      <p class="note">この書面は、特定商取引に関する法律に基づいて交付するものです。大切に保管してください。</p></div>
    <div id="shomen"></div>
    <div style="margin-top:14px">{cooling_off_html("書面を受け取った日")}</div>
    <p class="sign">{C.UNEI}／{C.UNEI_ADDR}／電話 {C.UNEI_TEL}／担当 {C.UNEI_TANTOU}</p>
    <div class="small-btns noprint" style="margin-top:12px"><button type="button" class="btn ghost" onclick="window.print()">印刷・PDFで保存</button></div>
  </div>
<script>
{js_common()}
{unei_js()}
{shomen_table_js()}
(function(){{
  var v = null;
  try {{ v = JSON.parse(decodeURIComponent(escape(atob((location.hash||'#').slice(1)))) ); }} catch(e) {{}}
  if (!v) {{ try {{ v = JSON.parse(Q.get('v') || ''); }} catch(e) {{}} }}
  $('shomen').innerHTML = v ? shomenHtml(v) : '<p class="err">書面の内容が読み込めませんでした。お送りしたメールのリンクから開いてください。</p>';
}})();
</script>
"""
    return C.head("申込書面｜ワンヒッター", "契約書面", BRAND, BRAND_SUB, css()) + body + C.foot(BRAND, "")


def build_unei() -> str:
    rows = C.UNEI_ROWS_COMMON + [
        ("無料点検について", "お申込みいただいたお宅にだけ伺い、洗濯槽の裏側（内視鏡カメラ）と追い焚き配管（ATP測定）を、その場で一緒に見ます。点検だけなら料金はいただきません。汚れていなければ「今回は不要」とお伝えし、その件数も公開します。"),
        ("ご案内について", "点検の結果、洗浄が必要と判断した場合は、その場でクリーニングのご案内をすることがあります（ご案内は1回だけ。お断りいただければ終わります）。お申込みの際は、特定商取引法に基づく書面を交付し、8日間のクーリング・オフができます。"),
    ]
    return C.unei_page(BRAND, BRAND_SUB, rows, "申込ページに戻る")


def main():
    P = C.prices()
    for x in MENUS:
        if x["施工"] not in P["menus"]:
            sys.exit(f"prices.json に無いメニュー名: {x['施工']}")
    OUTDIR.mkdir(parents=True, exist_ok=True)
    (OUTDIR / "index.html").write_text(build_index(P), encoding="utf-8")
    (OUTDIR / "genba.html").write_text(build_genba(P), encoding="utf-8")
    (OUTDIR / "moushikomi.html").write_text(build_moushikomi(P), encoding="utf-8")
    (OUTDIR / "shomen.html").write_text(build_shomen(), encoding="utf-8")
    (OUTDIR / "unei.html").write_text(build_unei(), encoding="utf-8")
    if not (OUTDIR / "slots.json").exists():
        (OUTDIR / "slots.json").write_text(json.dumps({"generated": dt.datetime.now().isoformat(timespec="minutes"), "generatedLabel": "", "days": []}, ensure_ascii=False), encoding="utf-8")
    print("書き出しました:", OUTDIR)


if __name__ == "__main__":
    main()
