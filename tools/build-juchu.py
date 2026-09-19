#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""受注フォーム（和真さんのスマホ用）を組み立てる。

  オーナー決定（2026-09-19・MTGシート 第3回 3-4 議題1）
    「受注フォームアプリを作成する。売上記録に必要な項目を原則選択式で入力可能な
      フォームを作成し、スプシとカレンダーの双方に自動反映させる仕様にする。
      和真の操作工数をなるべく減らす設計にする。」

  あわせて決めたこと（同日カード）
    ・反映は毎時でよい（予約フォームと同じ経路。送信は即時、反映は最大1時間後）
    ・**カレンダーの予定はフォームが作る**（和真さんの入力を1回にする）
    ・**受注が決まった時点**で入れる（金額は見込みでよく、あとから直せる）

  料金と所要時間は data/prices.json から入れる。**手で書き写さない**
  （写すとずれる。ずれた金額が台帳に入ると、あとの分析が全部ずれる）。

  出す先: lp/juchu/index.html
  配信先: oh-naibu-sms-k7q3x（**社内用ホスト**）
    ★お客様用ホストに社内ツールを置かないこと。2026-09-12 のセーフブラウジング事故の教訓。
"""
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "lp" / "juchu" / "index.html"
KITEI_SHOYOU = 60


def shoyou(m):
    n = re.search(r"(\d+)", str(m.get("所要") or ""))
    return int(n.group(1)) if n else KITEI_SHOYOU


def main():
    d = json.loads((ROOT / "data" / "prices.json").read_text(encoding="utf-8"))
    menu = [{"na": m["名称"], "tan": m["単体"],
             "dou": m.get("同時施工", m["単体"]), "fun": shoyou(m)}
            for m in d["本メニュー"]]
    opt = [{"na": o["名称"], "kin": o["価格"]} for o in d["オプション"]]
    hanki = d["繁忙期加算"]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(HTML.replace("__MENU__", json.dumps(menu, ensure_ascii=False))
                       .replace("__OPT__", json.dumps(opt, ensure_ascii=False))
                       .replace("__HANKI__", json.dumps(hanki, ensure_ascii=False)),
                   encoding="utf-8")
    print(f"書き出しました: {OUT}  {OUT.stat().st_size:,} bytes")
    print(f"  本メニュー {len(menu)}件／オプション {len(opt)}件／繁忙期加算 {hanki['金額']}円（{hanki['対象月']}月）")


HTML = r"""<!doctype html>
<html lang="ja"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>受注の記録｜社内用</title>
<style>
 :root{--ao:#1565c0;--fuchi:#d5dce3;--usu:#f6f8fa;--moji:#1a2330;--gure:#5b6876}
 *{box-sizing:border-box}
 body{margin:0;background:#eef1f4;color:var(--moji);
      font:16px/1.7 -apple-system,BlinkMacSystemFont,"Hiragino Sans","Noto Sans JP",sans-serif}
 .w{max-width:560px;margin:0 auto;padding:0 14px 120px}
 header{background:var(--moji);color:#fff;padding:14px;position:sticky;top:0;z-index:5}
 header b{font-size:17px}
 header span{display:block;font-size:12px;opacity:.75;margin-top:2px}
 section{background:#fff;border:1px solid var(--fuchi);border-radius:12px;margin:14px 0;padding:14px}
 h2{font-size:14px;margin:0 0 10px;color:var(--gure);letter-spacing:.04em}
 .hitsu{color:#c62828;font-size:11px;margin-left:4px}
 .erabu{display:flex;flex-wrap:wrap;gap:8px}
 .erabu button{flex:1 1 auto;min-width:96px;padding:12px 10px;font-size:15px;border-radius:10px;
   border:1.5px solid var(--fuchi);background:#fff;color:var(--moji);cursor:pointer}
 .erabu button[aria-pressed=true]{background:var(--ao);border-color:var(--ao);color:#fff;font-weight:700}
 label{display:block;font-size:13px;color:var(--gure);margin:12px 0 4px}
 input[type=text],input[type=tel],input[type=date],input[type=time],input[type=number],textarea{
   width:100%;padding:12px;font-size:16px;border:1.5px solid var(--fuchi);border-radius:10px;background:#fff}
 textarea{min-height:76px}
 .menu-gyo{display:flex;align-items:center;gap:8px;padding:8px 0;border-bottom:1px solid var(--usu)}
 .menu-gyo span{flex:1;font-size:14px}
 .menu-gyo .kazu{width:54px;text-align:center;padding:8px 4px}
 .menu-gyo em{font-style:normal;font-size:12px;color:var(--gure);width:72px;text-align:right}
 .gk{background:var(--usu);border-radius:10px;padding:12px;margin-top:12px}
 .gk div{display:flex;justify-content:space-between;font-size:14px;padding:3px 0}
 .gk .go{font-size:20px;font-weight:700;border-top:1px solid var(--fuchi);margin-top:6px;padding-top:8px}
 .chu{font-size:12px;color:var(--gure);margin-top:6px}
 .err{color:#c62828;font-size:13px;margin-top:4px;display:none}
 .err.deru{display:block}
 .soku{position:fixed;left:0;right:0;bottom:0;background:#fff;border-top:1px solid var(--fuchi);
   padding:10px 14px calc(10px + env(safe-area-inset-bottom));z-index:9}
 .soku button{width:100%;max-width:560px;margin:0 auto;display:block;padding:15px;font-size:17px;font-weight:700;
   background:var(--ao);color:#fff;border:0;border-radius:12px;cursor:pointer}
 .soku button:disabled{background:#9db4cc}
 .owari{display:none;text-align:center;padding:40px 14px}
 .owari.deru{display:block}
 .owari h1{font-size:20px}
 .owari .maru{font-size:48px}
 .hp{position:absolute;left:-9999px}
</style></head><body>

<header><b>受注の記録</b><span>社内用。お客様には出しません</span></header>

<div class="w" id="honbun">

<section>
  <h2>1　どちらの受注ですか<span class="hitsu">必須</span></h2>
  <div class="erabu" id="shurui">
    <button type="button" data-v="One Hitter">ワンヒッター</button>
    <button type="button" data-v="本舗">おそうじ本舗</button>
  </div>
  <p class="err" id="e-shurui">どちらか選んでください</p>
</section>

<section>
  <h2>2　どこからの受注ですか<span class="hitsu">必須</span></h2>
  <div class="erabu" id="keiro">
    <button type="button" data-v="早期予約">早期予約</button>
    <button type="button" data-v="リピート">リピート</button>
    <button type="button" data-v="業務提携">業務提携</button>
    <button type="button" data-v="知人紹介">知人紹介</button>
    <button type="button" data-v="おそうじ定期便">定期便</button>
    <button type="button" data-v="Web">Web</button>
    <button type="button" data-v="その他">その他</button>
  </div>
  <p class="err" id="e-keiro">選んでください</p>
  <div id="houjin-box" hidden>
    <label>提携先・紹介元のお名前</label>
    <input type="text" id="houjin" placeholder="例）株式会社レジェンド">
  </div>
</section>

<section>
  <h2>3　いつ施工しますか<span class="hitsu">必須</span></h2>
  <label>施工日</label>
  <input type="date" id="hi">
  <p class="err" id="e-hi">施工日を入れてください</p>
  <label>開始時刻</label>
  <input type="time" id="jikoku" value="09:00" step="900">
  <p class="chu">終了時刻は、選んだメニューの所要時間から自動で計算します。</p>
</section>

<section>
  <h2>4　何をしますか<span class="hitsu">必須</span></h2>
  <div id="menu"></div>
  <details style="margin-top:10px">
    <summary style="font-size:14px;color:var(--gure);cursor:pointer">オプションを足す</summary>
    <div id="opt" style="margin-top:8px"></div>
  </details>
  <div class="gk">
    <div><span>小計</span><b id="g-sho">0円</b></div>
    <div id="g-hanki-gyo" hidden><span>繁忙期加算</span><b id="g-hanki">0円</b></div>
    <div><span>所要の目安</span><b id="g-fun">—</b></div>
    <div class="go"><span>見込み金額</span><b id="g-go">0円</b></div>
  </div>
  <p class="err" id="e-menu">1つ以上選んでください</p>
  <label>値引きや調整をしたときは、実際の金額を入れてください（税込）</label>
  <input type="number" id="jissai" inputmode="numeric" placeholder="空のままなら上の見込み金額を使います">
  <p class="chu">あとからスプレッドシートで直せます。この場では、だいたいで構いません。</p>
</section>

<section>
  <h2>5　お客様<span class="hitsu">必須はお名前だけ</span></h2>
  <label>お名前<span class="hitsu">必須</span></label>
  <input type="text" id="name" placeholder="例）山本　美佑紀">
  <p class="err" id="e-name">お名前を入れてください</p>
  <label>ご住所</label>
  <input type="text" id="addr" placeholder="例）江戸川区中央4-2-13-905">
  <label>お電話番号</label>
  <input type="tel" id="tel" inputmode="numeric" placeholder="ハイフン無しでも可">
  <label>郵便番号</label>
  <input type="text" id="zip" inputmode="numeric" placeholder="ハイフン無し">
</section>

<section>
  <h2>6　現場のメモ（任意）</h2>
  <textarea id="memo" placeholder="駐車場・エアコンの下・浴室をお借りする了承・製造年数など。カレンダーの説明欄に入ります"></textarea>
</section>

<input class="hp" type="text" id="hp" tabindex="-1" autocomplete="off">
</div>

<div class="soku" id="soku"><button type="button" id="send">この内容で記録する</button></div>

<div class="owari" id="owari">
  <div class="maru">✓</div>
  <h1>記録しました</h1>
  <p id="owari-naka"></p>
  <p class="chu">スプレッドシートとカレンダーへは、**1時間以内**に自動で入ります。<br>すぐに見たいときは、マーケ部長に言ってください。</p>
  <p style="margin-top:24px"><button type="button" id="tsugi"
     style="padding:12px 20px;font-size:15px;border-radius:10px;border:1.5px solid var(--fuchi);background:#fff">
     続けてもう1件入れる</button></p>
</div>

<form hidden method="post" name="juchu" data-netlify="true" netlify-honeypot="bot-field">
  <input type="hidden" name="form-name" value="juchu">
  <input type="text" name="bot-field">
  <input type="text" name="売上種類"><input type="text" name="施工日付">
  <input type="text" name="開始時刻"><input type="text" name="流入経路">
  <input type="text" name="氏名"><input type="text" name="TEL">
  <input type="text" name="郵便番号"><input type="text" name="住所">
  <input type="text" name="売上（税込）"><input type="text" name="実施メニュー">
  <input type="text" name="所要の目安（分）"><input type="text" name="法人名">
  <input type="text" name="備考"><input type="text" name="見込み金額">
  <input type="text" name="入力日時">
</form>

<script>
(function(){
  var MENU = __MENU__, OPT = __OPT__, HANKI = __HANKI__;
  var $ = function(id){ return document.getElementById(id); };
  var jotai = { shurui:'', keiro:'', kazu:{}, optKazu:{} };

  /* ---- 選択ボタン ---- */
  function botan(oyaId, key){
    var oya = $(oyaId);
    oya.addEventListener('click', function(e){
      var b = e.target.closest('button'); if (!b) { return; }
      Array.prototype.forEach.call(oya.querySelectorAll('button'), function(x){
        x.setAttribute('aria-pressed', String(x === b));
      });
      jotai[key] = b.dataset.v;
      if (key === 'keiro') {
        $('houjin-box').hidden = !(jotai.keiro === '業務提携' || jotai.keiro === '知人紹介');
      }
      kakusu('e-' + key);
    });
  }
  botan('shurui','shurui'); botan('keiro','keiro');

  /* ---- メニュー ---- */
  function gyoTsukuru(oya, hai, kazuIre, tanka){
    hai.forEach(function(m, i){
      var d = document.createElement('div'); d.className = 'menu-gyo';
      d.innerHTML = '<span>' + m.na + '</span><em>' + tanka(m).toLocaleString() + '円</em>';
      var n = document.createElement('input');
      n.type = 'number'; n.className = 'kazu'; n.min = '0'; n.value = '0';
      n.inputMode = 'numeric'; n.setAttribute('aria-label', m.na + ' の台数');
      n.addEventListener('input', function(){
        var v = Math.max(0, parseInt(n.value || '0', 10) || 0);
        kazuIre[i] = v; keisan(); kakusu('e-menu');
      });
      d.appendChild(n); oya.appendChild(d);
    });
  }
  gyoTsukuru($('menu'), MENU, jotai.kazu, function(m){ return m.tan; });
  gyoTsukuru($('opt'), OPT, jotai.optKazu, function(o){ return o.kin; });

  /* ---- 金額と所要時間 ----
     箇所が2つ以上のときは「同時施工」の値段になる（data/prices.json のとおり）。
     所要は、1種目増えるごとに30分ひく。ひくのは最大60分まで（2026-09-04 のMTG決定）。 */
  function erandaKazu(){
    var n = 0; for (var k in jotai.kazu) { n += jotai.kazu[k]; } return n;
  }
  function keisan(){
    var shurui = 0, ko = 0, sho = 0, fun = 0;
    MENU.forEach(function(m, i){
      var n = jotai.kazu[i] || 0; if (!n) { return; }
      shurui += 1; ko += n; fun += m.fun * n;
    });
    MENU.forEach(function(m, i){
      var n = jotai.kazu[i] || 0; if (!n) { return; }
      sho += (ko >= 2 ? m.dou : m.tan) * n;
    });
    OPT.forEach(function(o, i){
      var n = jotai.optKazu[i] || 0; if (n) { sho += o.kin * n; }
    });
    if (shurui >= 2) { fun -= Math.min(60, (shurui - 1) * 30); }
    var tsuki = $('hi').value ? Number($('hi').value.slice(5,7)) : 0;
    var kasan = (sho && HANKI['対象月'].indexOf(tsuki) !== -1) ? HANKI['金額'] : 0;
    $('g-hanki-gyo').hidden = !kasan;
    $('g-hanki').textContent = kasan.toLocaleString() + '円';
    $('g-sho').textContent = sho.toLocaleString() + '円';
    $('g-go').textContent = (sho + kasan).toLocaleString() + '円';
    $('g-fun').textContent = fun ? (fun >= 60 ? Math.floor(fun/60) + '時間' + (fun%60 ? (fun%60)+'分' : '') : fun + '分') : '—';
    jotai.sho = sho; jotai.kasan = kasan; jotai.fun = fun || 60;
  }
  $('hi').addEventListener('change', keisan);
  keisan();

  /* ---- 検査 ---- */
  function dasu(id){ $(id).classList.add('deru'); }
  function kakusu(id){ var e = $(id); if (e) { e.classList.remove('deru'); } }
  ['name','hi'].forEach(function(id){
    $(id).addEventListener('input', function(){ kakusu('e-' + id); });
  });

  function menuMoji(){
    var a = [];
    MENU.forEach(function(m, i){ var n = jotai.kazu[i] || 0; if (n) { a.push(m.na + (n > 1 ? ' ×' + n : '')); } });
    OPT.forEach(function(o, i){ var n = jotai.optKazu[i] || 0; if (n) { a.push(o.na + (n > 1 ? ' ×' + n : '')); } });
    return a.join('／');
  }

  $('send').addEventListener('click', function(){
    if ($('hp').value) { return; }
    var ng = null;
    if (!jotai.shurui) { dasu('e-shurui'); ng = ng || 'shurui'; }
    if (!jotai.keiro)  { dasu('e-keiro');  ng = ng || 'keiro'; }
    if (!$('hi').value){ dasu('e-hi');     ng = ng || 'hi'; }
    if (!erandaKazu()) { dasu('e-menu');   ng = ng || 'menu'; }
    if (!$('name').value.trim()) { dasu('e-name'); ng = ng || 'name'; }
    if (ng) {
      var e = document.querySelector('.err.deru');
      if (e) { e.scrollIntoView({behavior:'smooth', block:'center'}); }
      return;
    }
    var mikomi = jotai.sho + jotai.kasan;
    var jissai = parseInt($('jissai').value || '0', 10) || 0;
    var atai = {
      'form-name': 'juchu',
      '売上種類': jotai.shurui,
      '施工日付': $('hi').value,
      '開始時刻': $('jikoku').value || '09:00',
      '流入経路': jotai.keiro,
      '氏名': $('name').value.trim(),
      'TEL': $('tel').value.trim(),
      '郵便番号': $('zip').value.trim(),
      '住所': $('addr').value.trim(),
      '売上（税込）': String(jissai || mikomi),
      '見込み金額': String(mikomi),
      '実施メニュー': menuMoji(),
      '所要の目安（分）': String(jotai.fun),
      '法人名': $('houjin').value.trim(),
      '備考': $('memo').value.trim(),
      '入力日時': new Date().toISOString()
    };
    var body = Object.keys(atai).map(function(k){
      return encodeURIComponent(k) + '=' + encodeURIComponent(atai[k]);
    }).join('&');
    var b = $('send'); b.disabled = true; b.textContent = '記録しています…';
    fetch('/', { method:'POST', headers:{'Content-Type':'application/x-www-form-urlencoded'}, body: body })
      .then(function(r){ if (!r.ok) { throw new Error('http ' + r.status); }
        $('honbun').style.display = 'none'; $('soku').style.display = 'none';
        $('owari').classList.add('deru');
        $('owari-naka').textContent = atai['施工日付'] + ' ' + atai['開始時刻'] + '　'
          + atai['氏名'] + 'さま　' + Number(atai['売上（税込）']).toLocaleString() + '円';
        window.scrollTo(0,0);
      })
      .catch(function(){
        b.disabled = false; b.textContent = 'この内容で記録する';
        alert('記録できませんでした。電波の良いところでもう一度お試しください。\n何度も失敗するときは、マーケ部長に連絡してください。');
      });
  });

  $('tsugi').addEventListener('click', function(){ location.reload(); });
})();
</script>
</body></html>
"""

if __name__ == "__main__":
    main()
