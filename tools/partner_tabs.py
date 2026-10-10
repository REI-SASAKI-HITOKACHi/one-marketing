# -*- coding: utf-8 -*-
"""提携先専用ページの「タブ2つ」の形（①見積依頼 ②現調依頼）。tools/build-partner.py から使う。

【なぜ】第6回MTG 6-4 No.4（オーナー決定・原文は docs/cmo-savedata.md）
  ① 見積依頼：料金表を反映してその場で料金を確認できる／任意で高速代の試算（最寄りIC〜船堀橋IC）／
     見積内容から作業時間を割り出して、枠を確保できる日を直近から5つ／顧客名など必須・任意の入力／
     CTA「この内容で見積を依頼する」
  ② 現調依頼：現調1時間。住所（区市まで）から移動時間を見込んで、候補枠をカレンダーで出す／
     CTA「この日時で現調を依頼する」
  「すべてにおいてUIUXを最優先」「AI味を極力排除して洗練されたデザイン」。

【使うデータ】
  - 料金：c["ryokin"]（例 data/partner-price/takara.json）。区分・単価・段・作業時間・税の表示はすべてこのファイル。
    段は gun（家庭用／業務用）ごとの台数の合計で決まる。お掃除機能付きは shurui（メーカー・シリーズ）ごとに1行（tenkai()）。
  - 高速代・移動時間：data/partner-area.json（tools/build-kousoku-ic.py がドラぷらから作る）。
  - 空き枠：予約ページと同じ Apps Script（JSONP）。落ちたら yoyaku.onehitter.jp/slots.json（同じ中身）を試す。

【移動時間の見込み方（空き枠）】
  Apps Script は既存の予定の前後に60分の移動を空けて枠を返す（tools/booking-api.gs SETTEI.idouFun）。
  片道の移動 T 分が60分を超える現場では、前後に足りない分 x＝(T−60) を30分単位に切り上げ、
  minutes＝作業（または現調60分）＋2x で聞き、返ってきた開始時刻に x を足して表示する。
  こうすると「前の予定の終わり＋T分」以降に着き、「終わり＋T分」までに次の予定へ戻れる枠だけが残る。

【送信】Netlify フォーム "partner"（全社共通・静的な隠しフォーム）。項目は FORM_FIELDS。
  取り込み（毎時点検の partner 取り込み）は 2026-10-10 時点で無い。作るときに読む項目：
    種別（見積依頼／現調依頼／仮押さえ）・提携先・ご担当・ページ・請求先・お客様名・お客様の電話・
    現場の住所・現場のお名前・きっかけ・内容・内訳・目安金額・作業時間の目安・高速代の目安・
    移動時間の目安・希望日時・ご要望・料金表・送信元の確認
"""
import json

# Netlify フォーム "partner" の項目。全社のページに同じ名前で置く（同じフォーム名で項目がずれると、
# Netlify がどちらかの項目しか登録しないことがあるため。青山様の1画面ページにも隠しで置く）。
FORM_FIELDS = ["種別", "提携先", "ご担当", "ページ", "請求先", "お客様名", "お客様の電話", "現場の住所", "現場のお名前",
               "きっかけ", "内容", "内訳", "明細", "見積書の送り先", "目安金額", "作業時間の目安", "高速代の目安", "移動時間の目安", "希望日時",
               "ご要望", "料金表", "送信元の確認"]

CSS = """
:root{--navy:#122F60;--navy-2:#36376A;--orange:#FF6600;--cta:#C44800;--cta-h:#A33C00;
  --bg:#F2F3F5;--surface:#fff;--line:#E0E3E8;--line-2:#C9CED6;--ink:#191C22;--sub:#545B67;--muted:#8B919B;
  --ok-bg:#EEF2F8;--err:#B3261E;color-scheme:light}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font-family:"Noto Sans JP","Hiragino Sans","Yu Gothic UI",system-ui,sans-serif;
  font-size:16px;line-height:1.6;font-feature-settings:"palt" 0;-webkit-tap-highlight-color:transparent}
button,input,textarea,select{font:inherit;color:inherit}
.num{font-variant-numeric:tabular-nums;letter-spacing:.01em}
.wrap{width:min(640px,100% - 32px);margin-inline:auto}

.top{background:var(--navy);color:#fff}
.top .wrap{padding:14px 0 13px}
.top .co{font-size:12px;letter-spacing:.08em;color:#AFBDD6;margin:0 0 2px}
.top .for{font-size:16px;margin:0;color:#fff;font-weight:700;letter-spacing:.02em}
.top .for span{font-weight:400;font-size:13px;color:#D5DDEB;margin-left:6px}

.tabs{position:sticky;top:0;z-index:20;background:var(--surface);border-bottom:1px solid var(--line)}
.tabs .wrap{display:grid;grid-template-columns:1fr 1fr}
.tab{appearance:none;background:none;border:0;padding:14px 4px 12px;font-size:16px;font-weight:700;color:var(--muted);
  position:relative;cursor:pointer;min-height:52px}
.tab[aria-selected=true]{color:var(--navy)}
.tab[aria-selected=true]::after{content:"";position:absolute;left:18%;right:18%;bottom:-1px;height:3px;background:var(--orange);border-radius:2px 2px 0 0}
.tab:focus-visible{outline:2px solid var(--navy);outline-offset:-4px}

.panel{padding:8px 0 28px}
.panel[hidden]{display:none}
.lead{font-size:14px;color:var(--sub);margin:14px 0 4px}
.sec{margin:22px 0 0}
.sec > h2{font-size:13px;font-weight:700;color:var(--sub);letter-spacing:.08em;margin:0 0 8px;display:flex;justify-content:space-between;align-items:baseline}
.sec > h2 small{font-weight:400;letter-spacing:0;color:var(--muted);font-size:12px}
.box{background:var(--surface);border:1px solid var(--line);border-radius:10px;overflow:hidden}

.item{display:flex;align-items:center;gap:12px;padding:12px 12px 12px 16px;border-top:1px solid var(--line)}
.item:first-child{border-top:0}
.item .nm{flex:1;min-width:0}
.item .nm b{display:block;font-size:15px;font-weight:500;line-height:1.45}
.item .nm span{display:block;font-size:12px;color:var(--sub);line-height:1.5;margin-top:1px}
.item .nm em{font-style:normal;color:var(--ink);font-weight:500}
.item .nm span:empty{display:none}
.grp{padding:12px 16px 4px;border-top:1px solid var(--line);background:#FAFBFC}
.grp b{display:block;font-size:15px;font-weight:500;line-height:1.45}
.grp span{display:block;font-size:12px;color:var(--sub);line-height:1.5}
.item.ko{background:#FAFBFC;border-top:1px dashed var(--line);padding:9px 12px 9px 28px}
.item.ko .nm b{font-size:14px}
.step{display:flex;align-items:center;border:1px solid var(--line-2);border-radius:8px;overflow:hidden;flex:none}
.step button{width:44px;height:44px;border:0;background:#fff;font-size:22px;line-height:1;color:var(--navy);cursor:pointer;display:grid;place-items:center}
.step button:active{background:var(--ok-bg)}
.step button:disabled{color:#C5CAD2;cursor:default;background:#fff}
.step output{width:40px;text-align:center;font-weight:700;font-size:17px;color:var(--muted);border-inline:1px solid var(--line);line-height:44px}
.step output.on{color:var(--navy)}
.utiwake{border-top:1px solid var(--line);padding:12px 16px;background:#FAFBFC;font-size:13px;color:var(--sub)}
.utiwake ul{list-style:none;margin:0;padding:0}
.utiwake li{display:flex;justify-content:space-between;gap:12px;padding:2px 0}
.utiwake li span:last-child{white-space:nowrap;color:var(--ink)}
.utiwake li{padding:4px 0}.utiwake li small{font-size:12px;color:var(--muted)}
.utiwake p{margin:6px 0 0;font-size:12px;color:var(--muted)}

.field{padding:12px 16px;border-top:1px solid var(--line)}
.field:first-child{border-top:0}
.field label{display:flex;align-items:baseline;gap:8px;font-size:13px;color:var(--sub);margin:0 0 6px}
.field label .req{font-size:11px;color:var(--cta);font-weight:700}
.field label .opt{font-size:11px;color:var(--muted)}
.field input[type=text],.field input[type=tel],.field input[type=email],.field textarea{width:100%;border:1px solid var(--line-2);border-radius:8px;padding:11px 12px;
  font-size:16px;background:#fff;min-height:46px}
.field textarea{min-height:76px;resize:vertical}
.field input::-webkit-calendar-picker-indicator{display:none !important}
.field input:focus,.field textarea:focus{outline:none;border-color:var(--navy);box-shadow:0 0 0 3px rgba(18,47,96,.12)}
.field.bad input,.field.bad textarea{border-color:var(--err)}
.field .msg{display:none;color:var(--err);font-size:13px;margin:6px 0 0}
.field.bad .msg{display:block}
.atena{padding:14px 16px 4px;font-size:14px;color:var(--sub)}.atena b{color:var(--ink);font-weight:700}
.chk{display:flex;align-items:center;gap:10px;padding:14px 16px;border-top:1px solid var(--line);font-size:15px;cursor:pointer;min-height:52px}
.chk input{width:20px;height:20px;margin:0;accent-color:var(--navy);flex:none}
.chk .opt{font-size:11px;color:var(--muted)}

.area{margin:8px 0 0;font-size:13px;color:var(--sub);min-height:0}
.area:empty{display:none}
.area b{color:var(--ink);font-weight:500}
.toll{margin:10px 0 0;border:1px solid var(--line);border-radius:8px;padding:10px 12px;background:#FAFBFC}
.toll .row{display:flex;justify-content:space-between;align-items:baseline;gap:12px}
.toll .k{font-size:13px;color:var(--sub)}
.toll .v{font-size:17px;font-weight:700;color:var(--ink)}
.toll p{margin:4px 0 0;font-size:12px;color:var(--muted)}
.toll a,.link{color:var(--navy);text-underline-offset:3px}

.days{list-style:none;margin:0;padding:0}
.day{padding:12px 16px 14px;border-top:1px solid var(--line)}
.day:first-child{border-top:0}
.day .dl{font-size:14px;font-weight:700;margin:0 0 8px;display:flex;gap:8px;align-items:baseline}
.day .dl .sat{color:#1F5FAE}.day .dl .sun{color:#B3261E}
.chips{display:flex;flex-wrap:wrap;gap:8px}
.chip{min-width:72px;height:40px;padding:0 12px;border:1px solid var(--line-2);border-radius:8px;background:#fff;font-size:15px;cursor:pointer;color:var(--ink)}
.chip.on{background:var(--navy);border-color:var(--navy);color:#fff;font-weight:700}
.chip.more{border-style:dashed;color:var(--sub);min-width:0}
.state{padding:18px 16px;font-size:14px;color:var(--sub);display:flex;gap:10px;align-items:flex-start}
.state .spin{width:16px;height:16px;border:2px solid var(--line-2);border-top-color:var(--navy);border-radius:50%;flex:none;margin-top:3px;animation:sp .8s linear infinite}
@keyframes sp{to{transform:rotate(360deg)}}
@media (prefers-reduced-motion:reduce){.state .spin{animation:none}}
.moreday{display:block;width:100%;border:0;border-top:1px solid var(--line);background:#fff;padding:14px;font-size:14px;color:var(--navy);cursor:pointer}

.cal{padding:12px 12px 6px}
.cal .mon{font-size:14px;font-weight:700;margin:2px 4px 8px}
.cal .grid{display:grid;grid-template-columns:repeat(7,1fr);gap:2px;text-align:center}
.cal .wd{font-size:11px;color:var(--muted);padding:2px 0 6px}
.cal .wd.sat{color:#1F5FAE}.cal .wd.sun{color:#B3261E}
.cal .d{appearance:none;border:0;background:none;height:46px;border-radius:8px;font-size:15px;color:#BAC0C8;position:relative;padding:0;cursor:default}
.cal .d.ok{color:var(--ink);font-weight:700;cursor:pointer}
.cal .d.ok::after{content:"";position:absolute;left:50%;bottom:7px;width:4px;height:4px;margin-left:-2px;border-radius:50%;background:var(--orange)}
.cal .d.on{background:var(--navy);color:#fff}
.cal .d.on::after{background:#fff}
.cal .d.today{text-decoration:underline;text-underline-offset:4px}
.cal .blank{height:46px}
.calnote{font-size:12px;color:var(--muted);margin:2px 16px 12px}
.times{border-top:1px solid var(--line);padding:12px 16px 14px}
.times h3{font-size:14px;margin:0 0 8px}

.bar{position:fixed;left:0;right:0;bottom:0;z-index:30;background:var(--surface);border-top:1px solid var(--line);
  padding:10px 0 calc(12px + env(safe-area-inset-bottom));box-shadow:0 -6px 16px rgba(18,28,45,.06)}
.bar[hidden]{display:none}
.bar .sum{display:flex;justify-content:space-between;align-items:baseline;gap:12px;margin:0 0 8px;min-height:28px}
.bar .sum .k{font-size:12px;color:var(--sub)}
.bar .sum .v{font-size:22px;font-weight:700;color:var(--navy);line-height:1.2}
.bar .sum .v small{font-size:12px;font-weight:400;color:var(--sub);margin-left:4px}
.bar .sum .r{font-size:12px;color:var(--sub);text-align:right;line-height:1.4}
.cta{display:block;width:100%;min-height:52px;border:0;border-radius:10px;background:var(--cta);color:#fff;font-size:17px;font-weight:700;cursor:pointer;letter-spacing:.02em}
.cta:hover{background:var(--cta-h)}
.cta:disabled{background:#B9BEC6;cursor:default}

.sheet{position:fixed;inset:0;z-index:50;display:flex;align-items:flex-end;justify-content:center;background:rgba(14,20,32,.45)}
.sheet[hidden]{display:none}
.sheet .in{background:#fff;width:min(640px,100%);max-height:88vh;overflow:auto;border-radius:14px 14px 0 0;padding:20px 16px calc(16px + env(safe-area-inset-bottom))}
.sheet h2{font-size:18px;margin:0 0 4px;color:var(--navy)}
.sheet .sub{font-size:13px;color:var(--sub);margin:0 0 14px}
.sheet dl{margin:0;border-top:1px solid var(--line)}
.sheet dl div{display:grid;grid-template-columns:7.5em 1fr;gap:10px;padding:10px 0;border-bottom:1px solid var(--line);font-size:14px}
.sheet dt{color:var(--sub)}
.sheet dd{margin:0;white-space:pre-line;word-break:break-word}
.sheet dd.big{font-size:18px;font-weight:700;color:var(--navy)}
.sheet .btns{display:grid;gap:8px;margin-top:16px}
.ghost{min-height:48px;border:1px solid var(--line-2);border-radius:10px;background:#fff;font-size:15px;color:var(--ink);cursor:pointer}
.fine{font-size:12px;color:var(--muted);margin:12px 0 0;line-height:1.6}
.fine a{color:var(--sub)}

footer{border-top:1px solid var(--line);padding:18px 0 calc(136px + env(safe-area-inset-bottom));font-size:12px;color:var(--sub);background:var(--bg)}
footer p{margin:0 0 8px}
footer a{color:var(--sub)}
.hp{position:absolute;left:-9999px}
.smsg{display:none;color:var(--err);font-size:13px;margin:6px 2px 0}
.sec.bad .smsg{display:block}
.sec.bad > .box{border-color:var(--err)}
"""

JS = r"""
(function(){
  var C = __CONF__;
  var P = C.price, A = C.areas;
  function $(id){ return document.getElementById(id); }
  function yen(n){ return n.toLocaleString('ja-JP') + '円'; }
  function esc(s){ return String(s).replace(/[&<>"]/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  function jikan(min){ var h = Math.floor(min / 60), m = min % 60; return (h ? h + '時間' : '') + (m ? m + '分' : (h ? '' : '0分')); }
  function hhmm(t, plus){ var p = t.split(':'), m = (+p[0]) * 60 + (+p[1]) + (plus || 0); return Math.floor(m / 60) + ':' + ('0' + (m % 60)).slice(-2); }
  function youbiCls(label){ return /（土）/.test(label) ? 'sat' : (/（日）/.test(label) ? 'sun' : ''); }

  /* ---------- 住所 → 区市（data/partner-area.json） ---------- */
  function seiki(s){ return (s.normalize ? s.normalize('NFKC') : s).replace(/\s+/g, '').replace(/^(東京都|千葉県|神奈川県|埼玉県)/, ''); }
  function sagasu(s){
    var t = seiki(s || ''), best = null, len = 0;
    if (!t) { return null; }
    A.forEach(function(a){ a.match.forEach(function(m){ if (t.indexOf(m) === 0 && m.length > len) { best = a; len = m.length; } }); });
    return best;
  }
  function dpUrl(a){ return C.dp + '?startArrive=true&startPlaceKana=' + encodeURIComponent(C.kitenIc) + '&arrivePlaceKana=' + encodeURIComponent(a.ic); }
  function zure(a){ var t = a ? a.idou_fun : 60; return t > 60 ? Math.ceil((t - 60) / 30) * 30 : 0; }

  /* ---------- 空き枠（Apps Script JSONP → だめなら slots.json） ---------- */
  var BUCKETS = [60, 90, 120, 150, 180, 210, 240, 300, 360, 420, 480], cache = {};
  function bucket(min){ for (var i = 0; i < BUCKETS.length; i++) { if (min <= BUCKETS[i]) { return BUCKETS[i]; } } return 480; }
  function jsonp(url){
    return new Promise(function(res, rej){
      var name = '__cb' + Date.now() + Math.floor(Math.random() * 1e4), sc = document.createElement('script');
      var t = setTimeout(function(){ owari(); rej(new Error('timeout')); }, 10000);
      function owari(){ clearTimeout(t); try { delete window[name]; } catch (e) { window[name] = undefined; } if (sc.parentNode) { sc.parentNode.removeChild(sc); } }
      window[name] = function(d){ owari(); res(d); };
      sc.onerror = function(){ owari(); rej(new Error('network')); };
      sc.src = url + '&callback=' + name; document.body.appendChild(sc);
    });
  }
  function waku(min){
    if (cache[min]) { return cache[min]; }
    cache[min] = jsonp(C.api + '?action=slots&minutes=' + min).then(function(d){
      if (!d || !d.ok) { throw new Error('ng'); }
      return d.slots || [];
    }).catch(function(){
      return fetch(C.slotsJson, { cache: 'no-store' }).then(function(r){ return r.json(); }).then(function(d){
        var b = d && d.buckets && d.buckets[String(bucket(min))];
        if (!b) { throw new Error('ng'); }
        return b;
      });
    }).catch(function(e){ delete cache[min]; throw e; });
    return cache[min];
  }
  function shoyou(work, a){
    var x = zure(a), m = work + 2 * x;
    if (m > 480) { x = 0; m = work; }
    return { minutes: Math.min(480, m), zure: x };
  }

  /* ---------- タブ ---------- */
  var tabs = [$('t-mitsu'), $('t-genchou')];
  function hiraku(i, push){
    tabs.forEach(function(t, j){ t.setAttribute('aria-selected', i === j ? 'true' : 'false'); t.tabIndex = i === j ? 0 : -1; });
    $('p-mitsu').hidden = i !== 0; $('p-genchou').hidden = i !== 1;
    $('b-mitsu').hidden = i !== 0; $('b-genchou').hidden = i !== 1;
    if (push && history.replaceState) { history.replaceState(null, '', i ? '#genchou' : '#mitsumori'); }
    if (i === 1) { genchouYomu(); }
  }
  tabs.forEach(function(t, i){
    t.addEventListener('click', function(){ hiraku(i, true); window.scrollTo(0, 0); });
    t.addEventListener('keydown', function(e){ if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') { var j = 1 - i; hiraku(j, true); tabs[j].focus(); } });
  });

  /* ---------- ① 見積：料金 ----------
     区分（P.items）は takara.json の kubun を Python 側で平らにしたもの（お掃除機能付きはメーカー・シリーズごとに1行）。
     台数の段は gun（家庭用＝katei／業務用＝gyomu）ごとの合計で決まり、その組の全台に掛かる。上限を超えた組はお見積り。 */
  var q = {}; P.items.forEach(function(k){ q[k.id] = 0; });
  var mSel = null;   // {date, label, time, start}
  function dan3(list, n){
    var u = Math.max(1, n), t = list[list.length - 1][2];
    list.forEach(function(d){ if (u >= d[0] && u <= d[1]) { t = d[2]; } });
    return t;
  }
  function tankaOf(k, n){
    if (k.kind === 'tanka') { return k.tanka; }
    if (k.kind === 'dan') { return dan3(k.dan, n); }
    if (k.kind === 'hiki') { return k.tanka - dan3(k.hiki, n); }
    return 0;
  }
  function gunUnits(){
    var u = {}; Object.keys(P.gun).forEach(function(g){ u[g] = 0; });
    P.items.forEach(function(k){ if (k.gun) { u[k.gun] += q[k.id]; } });
    return u;
  }
  function koeta(u, g){ return !!g && u[g] > P.gun[g].jougen; }
  function keisan(){
    var u = gunUnits(), units = 0, lines = [], meisai = [], total = 0, mitsu = [], work = 0, naiyou = [], ijou = false, over = [];
    Object.keys(u).forEach(function(g){ units += u[g]; if (koeta(u, g)) { over.push(P.gun[g].name); } });
    var mon = mSel ? parseInt(mSel.date.slice(5, 7), 10) : 0, H = P.hanbouki || {};
    var hanbou = (H.months || []).indexOf(mon) >= 0 && units > 0 && units <= (H.jogai_daisu || 0);
    P.items.forEach(function(k){
      var n = q[k.id]; if (!n) { return; }
      var nm = k.nm, tani = k.unit || '台';
      work += k.fun * n; naiyou.push(nm + ' ' + n + tani);
      if (k.kind === 'mitsumori') { mitsu.push(k.name + ' ' + n + tani); return; }
      if (koeta(u, k.gun)) { mitsu.push(nm + ' ' + n + tani + '（' + P.gun[k.gun].name + ' ' + (P.gun[k.gun].jougen + 1) + '台以上）'); return; }
      var t = tankaOf(k, u[k.gun] || 0);
      if (hanbou && k.gun) { t += H.kasan; }
      if (k.ijou) { ijou = true; }
      total += t * n;
      lines.push([nm, yen(t) + (k.ijou ? '〜' : '') + ' × ' + n + tani, yen(t * n) + (k.ijou ? '〜' : '')]);
      meisai.push({ hinmei: nm, suuryou: n, tani: tani, tanka: t, ijou: !!k.ijou });
    });
    var wari = P.waribiki_ritsu ? Math.floor(total * P.waribiki_ritsu / 100) : 0;
    return { u: u, units: units, lines: lines, meisai: meisai, total: total - wari, wari: wari, mitsu: mitsu, work: work, naiyou: naiyou, hanbou: hanbou, mon: mon, over: over, ijou: ijou };
  }
  function kingaku(r){ return yen(r.total) + (r.ijou ? '〜' : ''); }
  /* 料金表が税抜のとき（タカラ様：過去の見積書は小計＋消費税10%）、税込の合計も添える */
  function zeikomi(r){ return C.zei === '税抜' ? '税込 ' + yen(Math.round(r.total * 1.1)) + (r.ijou ? '〜' : '') : ''; }
  function egakuItems(r){
    P.items.forEach(function(k){
      var out = $('q-' + k.id), n = q[k.id];
      out.value = n; out.className = n ? 'on num' : 'num';
      $('m-' + k.id).disabled = !n;
      var pr = $('pr-' + k.id);
      if (k.kind === 'dan' || k.kind === 'hiki') {
        pr.innerHTML = koeta(r.u, k.gun) ? '1台 <em>お見積り</em>' : '1台 <em class="num">' + yen(tankaOf(k, r.u[k.gun] || 0)) + (k.ijou ? '〜' : '') + '</em>';
      }
    });
  }
  function egakuMitsu(){
    var r = keisan(); egakuItems(r);
    var u = $('utiwake');
    if (!r.lines.length && !r.mitsu.length) { u.hidden = true; }
    else {
      var h = '<ul>' + r.lines.map(function(l){ return '<li><span>' + esc(l[0]) + '<br><small class="num">' + l[1] + '</small></span><span class="num">' + l[2] + '</span></li>'; }).join('');
      if (r.wari) { h += '<li><span>お取引先さま割引</span><span class="num">−' + yen(r.wari) + '</span></li>'; }
      r.mitsu.forEach(function(s){ h += '<li><span>' + esc(s) + '</span><span>お見積り</span></li>'; });
      h += '</ul>';
      var notes = [], dai = [];
      Object.keys(r.u).forEach(function(g){ if (r.u[g] > 1 && !koeta(r.u, g)) { dai.push(P.gun[g].name + ' ' + r.u[g] + '台'); } });
      if (dai.length) { notes.push(dai.join('・') + 'の単価です。'); }
      if (r.ijou) { notes.push('型番が分からない分は最低額で計算しています（現地で型番を確かめて確定します）。'); }
      if (r.hanbou) { notes.push('繁忙期（' + r.mon + '月）のため1台 ' + yen(P.hanbouki.kasan) + 'を含みます。'); }
      if (r.over.length) { notes.push(P.chuuki); }
      if (notes.length) { h += '<p>' + notes.join('') + '</p>'; }
      u.innerHTML = h; u.hidden = false;
    }
    var bv = $('bm-v'), br = $('bm-r'), zl = [C.zei, zeikomi(r), r.mitsu.length ? 'ほかお見積り' : ''].filter(Boolean).join('・');
    if (r.lines.length) { bv.innerHTML = '<span class="num">' + kingaku(r) + '</span>' + (zl ? '<small>' + zl + '</small>' : ''); }
    else if (r.mitsu.length) { bv.innerHTML = 'お見積り'; }
    else { bv.innerHTML = '<span style="color:var(--muted)">—</span>'; }
    br.innerHTML = r.work ? '作業 約' + jikan(r.work) + '<br>高速代・駐車場代は別' : '台数を選んでください';
    return r;
  }

  /* ---------- ① 見積：住所・高速代 ---------- */
  var mArea = null;
  /* 都内23区は高速代をいただかない（オーナー 2026-10-10「都内23区は取らないから０にして」） */
  function nijuusan(a){ return !!a && a.pref === '東京都' && /区$/.test(a.name); }
  function egakuArea(inp, out, tollBox){
    var v = inp.value.trim(), a = sagasu(v);
    if (!v) { out.innerHTML = ''; if (tollBox) { tollBox.hidden = true; } return null; }
    if (!a) {
      out.innerHTML = '区市町村から入れると、移動時間と高速代の目安が出ます。';
      if (tollBox) {
        tollBox.hidden = false;
        tollBox.innerHTML = '<div class="row"><span class="k">高速代の目安</span><span class="v" style="font-size:14px;font-weight:500">この地域は目安表にありません</span></div>' +
          '<p><a href="' + C.dpTop + '" target="_blank" rel="noopener">ドラぷらで調べる</a>（出発：' + C.kitenIc + '）</p>';
      }
      return null;
    }
    out.innerHTML = '<b>' + esc(a.pref + ' ' + a.name) + '</b>　江戸川区から車で片道 約' + a.idou_fun + '分' + (a.eria_gai ? '<br>対応エリア（東京・千葉・神奈川）の外です。日程はご相談になります。' : '');
    if (tollBox) {
      tollBox.hidden = false;
      if (nijuusan(a)) {
        tollBox.innerHTML = '<div class="row"><span class="k">高速代</span><span class="v">0円</span></div><p>都内23区は高速代をいただきません。</p>';
      } else if (a.ippan) {
        tollBox.innerHTML = '<div class="row"><span class="k">高速代の目安</span><span class="v">0円</span></div><p>近いので一般道で伺います。</p>';
      } else {
        tollBox.innerHTML = '<div class="row"><span class="k">高速代の目安（往復）</span><span class="v num">' + yen(a.etc * 2) + '</span></div>' +
          '<p>' + esc(a.ic_hyouji) + 'IC ⇄ ' + C.kitenIc + 'IC・ETC普通車・片道 ' + yen(a.etc) + '（' + C.areaJiten + ' 時点の平日料金）。実費でのご請求です。<br>' +
          '<a href="' + dpUrl(a) + '" target="_blank" rel="noopener">ドラぷらで正確な料金を見る</a></p>';
      }
    }
    return a;
  }
  function tollText(a, v){
    if (!v) { return ''; }
    if (!a) { return '目安表に無い地域（ドラぷらで要確認）'; }
    if (nijuusan(a)) { return '0円（都内23区は高速代なし）'; }
    if (a.ippan) { return '0円（一般道）'; }
    return '往復 ' + yen(a.etc * 2) + '（ETC普通車・' + a.ic_hyouji + 'IC⇄' + C.kitenIc + 'IC・ドラぷら ' + C.areaJiten + ' 時点）';
  }

  /* ---------- ① 見積：空き日（直近5日） ---------- */
  var mShow = 5, mKey = '', mTimer = 0, mOpen = {};
  function mitsuWaku(){
    clearTimeout(mTimer);
    mTimer = setTimeout(function(){
      var r = keisan(), box = $('m-slots'), note = $('m-slotnote');
      if (!r.work) { mKey = ''; note.textContent = '作業時間に合わせて、作業できる日を直近から出します。'; box.innerHTML = '<div class="state">台数を選ぶと、作業できる日が出ます。</div>'; return; }
      var nagai = r.work > 480, s = shoyou(bucket(Math.max(60, Math.min(r.work, 480))), mArea), key = s.minutes + '/' + s.zure;
      note.textContent = '作業 約' + jikan(r.work) + '（1名）' + (s.zure ? '・移動 片道 約' + mArea.idou_fun + '分' : '') + 'で入れる開始時刻です。';
      if (key === mKey) { return; }
      mKey = key; mShow = 5; mOpen = {};
      box.innerHTML = '<div class="state"><span class="spin" aria-hidden="true"></span>空き状況を確認しています</div>';
      waku(s.minutes).then(function(slots){
        if (key !== mKey) { return; }
        egakuMitsuWaku(slots, s.zure, nagai);
      }).catch(function(){
        if (key !== mKey) { return; }
        mKey = '';
        box.innerHTML = '<div class="state">空き状況を読み込めませんでした。ご希望の日時を「ご要望」にお書きください（お電話 ' + C.tel + ' でも承ります）。</div>';
      });
    }, 250);
  }
  var mSlots = [], mZure = 0, mNagai = false;
  function egakuMitsuWaku(slots, z, nagai){
    mSlots = slots; mZure = z; mNagai = nagai;
    var box = $('m-slots'), h = '';
    if (nagai) { h += '<div class="state">1日では終わらない量です。初日を選んでいただければ、2日目以降はご相談します。</div>'; }
    if (!slots.length) { box.innerHTML = h + '<div class="state">3週間先まで、この長さで入れる日がありません。ご希望の日時を「ご要望」にお書きください。</div>'; return; }
    h += '<ul class="days">';
    slots.slice(0, mShow).forEach(function(d){
      var times = d.times.map(function(t){ return hhmm(t, z); }), lim = mOpen[d.date] ? times.length : 6;
      h += '<li class="day"><p class="dl"><span class="' + youbiCls(d.label) + '">' + esc(d.label) + '</span></p><div class="chips">';
      times.slice(0, lim).forEach(function(t){
        var on = mSel && mSel.date === d.date && mSel.time === t;
        h += '<button type="button" class="chip num' + (on ? ' on' : '') + '" data-d="' + d.date + '" data-l="' + esc(d.label) + '" data-t="' + t + '" aria-pressed="' + on + '">' + t + '</button>';
      });
      if (times.length > lim) { h += '<button type="button" class="chip more" data-open="' + d.date + '">ほか ' + (times.length - lim) + '件</button>'; }
      h += '</div></li>';
    });
    h += '</ul>';
    if (slots.length > mShow) { h += '<button type="button" class="moreday" id="m-more">もっと先の日を見る</button>'; }
    box.innerHTML = h;
  }
  $('m-slots').addEventListener('click', function(e){
    var b = e.target.closest('button'); if (!b) { return; }
    if (b.id === 'm-more') { mShow += 5; egakuMitsuWaku(mSlots, mZure, mNagai); return; }
    if (b.dataset.open) { mOpen[b.dataset.open] = true; egakuMitsuWaku(mSlots, mZure, mNagai); return; }
    if (b.dataset.t) {
      mSel = (mSel && mSel.date === b.dataset.d && mSel.time === b.dataset.t) ? null : { date: b.dataset.d, label: b.dataset.l, time: b.dataset.t };
      egakuMitsuWaku(mSlots, mZure, mNagai); egakuMitsu(); $('m-pick').textContent = mSel ? '選んだ日時：' + mSel.label + ' ' + mSel.time + '〜' : '';
    }
  });

  P.items.forEach(function(k){
    function set(v){ q[k.id] = Math.max(0, Math.min(99, v)); egakuMitsu(); mitsuWaku(); kesu($('mf-items')); }
    $('m-' + k.id).onclick = function(){ set(q[k.id] - 1); };
    $('p-' + k.id).onclick = function(){ set(q[k.id] + 1); };
  });
  $('m-addr').addEventListener('input', function(){
    var a = egakuArea(this, $('m-area'), $('m-toll'));
    var changed = (a && a.name) !== (mArea && mArea.name); mArea = a;
    if (changed) { mitsuWaku(); }
  });

  /* ---------- ② 現調 ---------- */
  var gArea = null, gSel = null, gKey = '', gSlots = [], gZure = 0, gTimer = 0, gDay = '';
  function genchouYomu(){
    clearTimeout(gTimer);
    gTimer = setTimeout(function(){
      var v = $('g-addr').value.trim(), box = $('g-cal');
      if (!v) { gKey = ''; box.innerHTML = '<div class="state">先に現調先の住所（区市まで）を入れてください。移動時間を見込んだ空き日が出ます。</div>'; $('g-times').hidden = true; return; }
      var s = shoyou(C.genchouFun, gArea), key = s.minutes + '/' + s.zure;
      $('g-note').textContent = '現調 ' + C.genchouFun + '分' + (gArea ? '・移動 片道 約' + gArea.idou_fun + '分を前後に見込んでいます。' : '・移動は標準（片道1時間まで）で見込んでいます。');
      if (key === gKey) { return; }
      gKey = key;
      box.innerHTML = '<div class="state"><span class="spin" aria-hidden="true"></span>空き状況を確認しています</div>'; $('g-times').hidden = true;
      waku(s.minutes).then(function(slots){ if (key !== gKey) { return; } gSlots = slots; gZure = s.zure; egakuCal(); })
        .catch(function(){ if (key !== gKey) { return; } gKey = ''; box.innerHTML = '<div class="state">空き状況を読み込めませんでした。ご希望の日時を「ご要望」にお書きください（お電話 ' + C.tel + ' でも承ります）。</div>'; });
    }, 250);
  }
  function ymd(d){ return d.getFullYear() + '-' + ('0' + (d.getMonth() + 1)).slice(-2) + '-' + ('0' + d.getDate()).slice(-2); }
  function egakuCal(){
    var box = $('g-cal'), by = {};
    gSlots.forEach(function(d){ by[d.date] = d; });
    if (gSel && !by[gSel.date]) { gSel = null; }
    if (gDay && !by[gDay]) { gDay = ''; }
    if (!gDay && gSlots.length) { gDay = gSlots[0].date; }
    var today = new Date(); today.setHours(0, 0, 0, 0);
    var last = new Date(today); last.setDate(last.getDate() + C.saichouNichi);
    var start = new Date(today); start.setDate(start.getDate() - ((start.getDay() + 6) % 7));
    var end = new Date(last); end.setDate(end.getDate() + (6 - ((end.getDay() + 6) % 7)));
    var wd = ['月','火','水','木','金','土','日'];
    var h = '<p class="mon">' + (today.getMonth() + 1) + '月' + (last.getMonth() !== today.getMonth() ? '〜' + (last.getMonth() + 1) + '月' : '') + '</p><div class="grid">' +
      wd.map(function(w, i){ return '<span class="wd' + (i === 5 ? ' sat' : i === 6 ? ' sun' : '') + '">' + w + '</span>'; }).join('');
    for (var d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
      var k = ymd(d), ok = !!by[k], on = gDay === k, inRange = d >= today && d <= last;
      var txt = (d.getDate() === 1 || +d === +start) && inRange ? (d.getMonth() + 1) + '/' + d.getDate() : String(d.getDate());
      if (!inRange) { h += '<span class="blank" aria-hidden="true"></span>'; continue; }
      h += '<button type="button" class="d num' + (ok ? ' ok' : '') + (on ? ' on' : '') + (+d === +today ? ' today' : '') + '"' + (ok ? ' data-d="' + k + '" aria-pressed="' + on + '"' : ' disabled') +
        ' aria-label="' + (d.getMonth() + 1) + '月' + d.getDate() + '日' + (ok ? ' 空きあり' : ' 空きなし') + '">' + txt + '</button>';
    }
    h += '</div>';
    box.innerHTML = '<div class="cal">' + h + '</div>' + (gSlots.length ? '<p class="calnote">点のある日が、現調に伺える日です。</p>' : '<div class="state">3週間先まで空きがありません。ご希望の日時を「ご要望」にお書きください。</div>');
    egakuTimes();
  }
  function egakuTimes(){
    var w = $('g-times'), d = null;
    gSlots.forEach(function(x){ if (x.date === gDay) { d = x; } });
    if (!d) { w.hidden = true; return; }
    var h = '<h3><span class="' + youbiCls(d.label) + '">' + esc(d.label) + '</span> の空き</h3><div class="chips">';
    d.times.forEach(function(t0){
      var t = hhmm(t0, gZure), on = gSel && gSel.date === d.date && gSel.time === t;
      h += '<button type="button" class="chip num' + (on ? ' on' : '') + '" data-t="' + t + '" aria-pressed="' + on + '">' + t + '</button>';
    });
    w.innerHTML = h + '</div>'; w.hidden = false; w.dataset.d = d.date; w.dataset.l = d.label;
  }
  $('g-cal').addEventListener('click', function(e){ var b = e.target.closest('button[data-d]'); if (!b) { return; } gDay = b.dataset.d; egakuCal(); });
  $('g-times').addEventListener('click', function(e){
    var b = e.target.closest('button[data-t]'); if (!b) { return; }
    var w = $('g-times');
    gSel = (gSel && gSel.date === w.dataset.d && gSel.time === b.dataset.t) ? null : { date: w.dataset.d, label: w.dataset.l, time: b.dataset.t };
    egakuTimes(); egakuGBar(); kesu($('gf-when'));
  });
  function egakuGBar(){
    $('bg-v').innerHTML = gSel ? '<span class="num">' + esc(gSel.label) + ' ' + gSel.time + '〜' + hhmm(gSel.time, C.genchouFun) + '</span>' : '<span style="color:var(--muted);font-size:16px">日時を選んでください</span>';
  }
  $('g-addr').addEventListener('input', function(){
    var a = egakuArea(this, $('g-area'), null);
    gArea = a; genchouYomu();
  });

  /* 住所は、もう一方のタブが空なら写す（同じ現場の見積と現調を続けて頼めるように） */
  function utsusu(from, to, after){ from.addEventListener('change', function(){ if (!to.value.trim()) { to.value = from.value; after(); } }); }
  utsusu($('m-addr'), $('g-addr'), function(){ gArea = egakuArea($('g-addr'), $('g-area'), null); gKey = ''; });
  utsusu($('g-addr'), $('m-addr'), function(){ mArea = egakuArea($('m-addr'), $('m-area'), $('m-toll')); mitsuWaku(); });
  utsusu($('m-name'), $('g-name'), function(){});
  utsusu($('g-name'), $('m-name'), function(){});
  utsusu($('m-tel'), $('g-tel'), function(){});
  utsusu($('g-tel'), $('m-tel'), function(){});

  /* ---------- 確かめて送る ---------- */
  function kesu(f){ if (f) { f.classList.remove('bad'); } }
  ['m-addr','m-name','g-addr','g-name','m-ate'].filter(function(id){ return $(id); }).forEach(function(id){ $(id).addEventListener('input', function(){ kesu(this.closest('.field')); }); });
  function dame(list){
    list.forEach(function(f){ f.classList.add('bad'); });
    var f = list[0]; f.scrollIntoView({ behavior: 'smooth', block: 'center' });
    var i = f.querySelector('input,textarea'); if (i) { setTimeout(function(){ i.focus({ preventScroll: true }); }, 300); }
  }
  var okuru = null;
  function kakunin(title, sub, rows, data){
    $('s-title').textContent = title; $('s-sub').textContent = sub;
    $('s-dl').innerHTML = rows.filter(function(r){ return r[1]; }).map(function(r){ return '<div><dt>' + esc(r[0]) + '</dt><dd' + (r[2] ? ' class="big num"' : '') + '>' + esc(r[1]) + '</dd></div>'; }).join('');
    okuru = data; $('s-send').disabled = false; $('s-send').textContent = '送信する';
    $('sheet').hidden = false; document.body.style.overflow = 'hidden'; $('s-send').focus();
  }
  function tojiru(){ $('sheet').hidden = true; document.body.style.overflow = ''; }
  $('s-back').onclick = tojiru;
  $('sheet').addEventListener('click', function(e){ if (e.target === this) { tojiru(); } });
  document.addEventListener('keydown', function(e){ if (e.key === 'Escape' && !$('sheet').hidden) { tojiru(); } });
  $('s-send').onclick = function(){
    if (!okuru) { return; }
    var f = $('form'), btn = this;
    /* 前の送信の値を残さない（2026-10-10 見積の内訳が現調依頼に混ざって届いた） */
    f.querySelectorAll('input[type="hidden"]').forEach(function(el){ if (['form-name', '提携先', 'ページ', '請求先', '料金表'].indexOf(el.name) < 0) { el.value = ''; } });
    Object.keys(okuru).forEach(function(k){ var el = f.querySelector('[name="' + k + '"]'); if (el) { el.value = okuru[k]; } });
    f.querySelector('[name="送信元の確認"]').value = 'ブラウザから送信';
    btn.disabled = true; btn.textContent = '送信しています…';
    var body = new URLSearchParams(new FormData(f)).toString();
    function okuruFetch(n){
      /* 送り先は送信後のページ（実在する静的ページ）。「/」は lp.onehitter.jp では転送（301）されて記録されない（10/10 実測） */
      return fetch(f.getAttribute('action'), { method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: body, redirect: 'manual' })
        .then(function(res){ if (!res.ok || res.redirected || res.type === 'opaqueredirect') { throw new Error(res.status); } })
        .catch(function(e){ if (n > 0) { return new Promise(function(ok){ setTimeout(ok, 1500); }).then(function(){ return okuruFetch(n - 1); }); } throw e; });
    }
    /* 2026-10-10 見積依頼の送信が ERR_CONNECTION_CLOSED で落ちた（オーナー）。画面遷移の送信をやめ、切れたら1回やり直す */
    okuruFetch(1).then(function(){ location.href = f.getAttribute('action'); }).catch(function(){
      btn.disabled = false; btn.textContent = 'もう一度送信する';
      $('s-sub').textContent = '通信が切れて送れませんでした。もう一度「送信する」を押すか、お電話（' + C.tel + '）でお知らせください。';
    });
  };
  function kyoutsuu(pre){
    return { 'お客様名': $(pre + '-name').value.trim(), 'お客様の電話': $(pre + '-tel').value.trim(), '現場の住所': $(pre + '-addr').value.trim(),
      '現場のお名前': $(pre + '-site').value.trim(), 'ご要望': $(pre + '-biko').value.trim(), 'ご担当': ($(pre + '-tantou').value.trim() || C.tantou).replace(/\s*様$/, ''),
      'きっかけ': $(pre + '-card').checked ? 'ご紹介カード' : '' };
  }
  $('m-cta').onclick = function(){
    var r = keisan(), bad = [];
    if (!r.lines.length && !r.mitsu.length) { bad.push($('mf-items')); }
    /* 見積書の送り先（オーナー 2026-10-10）：いつもの宛先＋追加分。「追加分だけ」も選べる */
    var ateIn = $('m-ate'), tsuika = ateIn ? ateIn.value.split(/[,、，\s]+/).map(function(x){ return x.trim(); }).filter(Boolean) : [];
    var ateOnly = $('m-ate-only') && $('m-ate-only').checked;
    if (ateIn && (tsuika.some(function(x){ return !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(x); }) || (ateOnly && !tsuika.length))) { bad.push(ateIn.closest('.field')); }
    if (bad.length) { return dame(bad); }
    var d = kyoutsuu('m'), kin = r.lines.length ? kingaku(r) + (C.zei ? '（' + C.zei + (zeikomi(r) ? '・' + zeikomi(r) : '') + '）' : '') + (r.mitsu.length ? '＋お見積り分' : '') : 'お見積り';
    var uti = r.lines.map(function(l){ return l[0] + '　' + l[1] + ' ＝ ' + l[2]; }).concat(r.mitsu.map(function(s){ return s + '：お見積り'; }));
    if (r.wari) { uti.push('お取引先さま割引 −' + yen(r.wari)); }
    if (r.hanbou) { uti.push('繁忙期加算を含む'); }
    if (r.ijou) { uti.push('型番が分からない分は最低額（現地で確定）'); }
    var toll = tollText(mArea, d['現場の住所']), hi = mSel ? mSel.label + ' ' + mSel.time + '〜' : '';
    var ate = (ateOnly ? [] : (C.mitsuAte ? [C.mitsuAte] : [])).concat(tsuika.filter(function(x){ return x !== C.mitsuAte; }));
    d['見積書の送り先'] = ate.join(', ');
    d['種別'] = '見積依頼'; d['内容'] = r.naiyou.join('／'); d['内訳'] = uti.join('\n'); d['明細'] = JSON.stringify(r.meisai); d['目安金額'] = kin;
    d['作業時間の目安'] = '約' + jikan(r.work) + '（1名）'; d['高速代の目安'] = toll; d['移動時間の目安'] = mArea ? '片道 約' + mArea.idou_fun + '分' : '';
    d['希望日時'] = hi || '未選択（あとで調整）';
    kakunin('この内容で見積を依頼します', '内容を確かめて「送信する」を押してください。担当の渡辺からご連絡します。', [
      ['お客様', d['お客様名'] + (d['現場のお名前'] ? '（' + d['現場のお名前'] + '）' : '')], ['電話', d['お客様の電話']], ['現場', d['現場の住所']],
      ['内容', r.naiyou.join('\n')], ['目安の料金', kin, true], ['作業時間', d['作業時間の目安']], ['高速代', toll],
      ['希望日時', d['希望日時']], ['ご要望', d['ご要望']], ['ご紹介カード', d['きっかけ'] ? '見たお客様' : ''], ['見積書の送り先', d['見積書の送り先']], ['ご依頼者', C.kaisha + ' ' + d['ご担当'] + '様']
    ], d);
  };
  $('g-cta').onclick = function(){
    var bad = [];
    if (!$('g-addr').value.trim()) { bad.push($('g-addr').closest('.field')); }
    if (!gSel && !$('g-biko').value.trim()) { bad.push($('gf-when')); }
    if (!$('g-name').value.trim()) { bad.push($('g-name').closest('.field')); }
    if (bad.length) { return dame(bad); }
    var d = kyoutsuu('g'), hi = gSel ? gSel.label + ' ' + gSel.time + '〜' + hhmm(gSel.time, C.genchouFun) + '（現調' + C.genchouFun + '分）' : 'ご要望欄のとおり';
    d['種別'] = '現調依頼'; d['内容'] = '現地調査（' + C.genchouFun + '分）'; d['希望日時'] = hi;
    d['移動時間の目安'] = gArea ? '片道 約' + gArea.idou_fun + '分' : '目安表に無い地域';
    d['高速代の目安'] = tollText(gArea, d['現場の住所']);
    kakunin('この日時で現調を依頼します', '内容を確かめて「送信する」を押してください。担当の渡辺から確定のご連絡をします。', [
      ['日時', hi, true], ['現調先', d['現場の住所']], ['お客様', d['お客様名'] + (d['現場のお名前'] ? '（' + d['現場のお名前'] + '）' : '')],
      ['電話', d['お客様の電話']], ['ご要望', d['ご要望']], ['ご紹介カード', d['きっかけ'] ? '見たお客様' : ''], ['ご依頼者', C.kaisha + ' ' + d['ご担当'] + '様']
    ], d);
  };

  egakuMitsu(); mitsuWaku(); egakuGBar();
  hiraku(location.hash === '#genchou' ? 1 : 0, false);
})();
"""


def _esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


def tenkai(price: dict) -> list:
    """takara.json の kubun を、ページの1行＝1区分に平らにする（shurui＝お掃除機能付きのメーカー・シリーズは1種類1行）。
    nm は内訳・送信内容に出す名前。_ で始まる注記は落とす。"""
    items = []
    for k in price["kubun"]:
        base = {kk: v for kk, v in k.items() if not kk.startswith("_") and kk != "shurui"}
        if k.get("shurui"):
            for i, s in enumerate(k["shurui"]):
                it = dict(base, id=s["id"], name=s["name"], sub=s.get("kataban", ""), tanka=s["tanka"],
                          ijou=bool(s.get("ijou")), nm=k["name"] + "・" + s["name"], oya=k["id"], first=i == 0)
                items.append(it)
        else:
            base["nm"] = k["name"]
            items.append(base)
    return items


def _hajime(k: dict) -> str:
    """台数0のときに出す1台の単価（段の最初）。"""
    if k["kind"] == "dan":
        return f'1台 <em class="num">{k["dan"][0][2]:,}円</em>'
    if k["kind"] == "hiki":
        return f'1台 <em class="num">{k["tanka"] - k["hiki"][0][2]:,}円{"〜" if k.get("ijou") else ""}</em>'
    if k["kind"] == "tanka":
        return f'1台 <em class="num">{k["tanka"]:,}円</em>'
    return "現地を確認してお見積り"


def _gyou(k: dict, ko: bool = False) -> str:
    sub = _esc(k["sub"]) if k.get("sub") and k["kind"] != "mitsumori" else ""
    label = _esc(k.get("nm") or k["name"])
    return f"""<div class="item{' ko' if ko else ''}"><div class="nm"><b>{_esc(k['name'])}</b><span>{sub}</span><span id="pr-{k['id']}">{_hajime(k)}</span></div>
        <div class="step"><button type="button" id="m-{k['id']}" aria-label="{label}を減らす" disabled>−</button><output id="q-{k['id']}" class="num" aria-live="polite">0</output><button type="button" id="p-{k['id']}" aria-label="{label}を増やす">＋</button></div></div>"""


def page(key: str, c: dict, price: dict, area: dict, api: str, tel: str, footer: str) -> str:
    areas = [{k: a.get(k) for k in ("name", "pref", "match", "ic", "ic_hyouji", "etc", "idou_fun", "ippan", "eria_gai")} for a in area["areas"]]
    items = tenkai(price)
    zei = price.get("zei_hyouji", "")
    conf = {
        "price": {"items": items, "gun": price["gun"], "hanbouki": price["hanbouki"], "waribiki_ritsu": price["waribiki_ritsu"], "chuuki": price["chuuki"]},
        "zei": zei,
        "areas": areas, "areaJiten": area["時点"].replace("-", "/"),
        "kitenIc": "船堀橋", "dp": "https://www.driveplaza.com/dp/SearchQuick", "dpTop": "https://www.driveplaza.com/dp/SearchTop",
        "api": api, "slotsJson": "https://yoyaku.onehitter.jp/slots.json", "tel": tel,
        "genchouFun": 60, "saichouNichi": 21, "kaisha": c["kaisha"], "tantou": c["tantou"], "mitsuAte": c.get("mitsu_ate", ""),
    }
    rows = []
    oya = {k["id"]: k for k in price["kubun"]}
    for k in items:
        if k.get("oya"):
            if k["first"]:
                g = oya[k["oya"]]
                rows.append(f'<div class="grp"><b>{_esc(g["name"])}</b><span>{_esc(g.get("sub", ""))}</span></div>')
            rows.append(_gyou(k, ko=True))
        else:
            rows.append(_gyou(k))
    kouho = []
    for a in area["areas"]:
        if a["eria_gai"]:
            continue
        for m in a["match"]:
            if (a["name"].startswith(("横浜市", "川崎市")) and (len(m) <= 3 or not m.startswith(("横浜市", "川崎市")))) or "ヶ" in m and len(a["match"]) > 1 and m != a["match"][0]:
                continue
            if a["pref"] + m not in kouho:
                kouho.append(a["pref"] + m)
    datalist = "".join(f'<option value="{_esc(v)}">' for v in kouho)
    hidden = "\n  ".join(f'<input type="hidden" name="{f}" value="">' for f in FORM_FIELDS if f not in ("提携先", "ページ", "請求先", "料金表"))
    js = JS.replace("__CONF__", json.dumps(conf, ensure_ascii=False))

    def kyoutsuu(pre, addr_label, addr_ph, biko_ph):
        req = '<span class="opt">任意</span>' if pre == 'm' else '<span class="req">必須</span>'   # 見積は住所・お客様名とも任意（オーナー 2026-10-10）
        return f"""
    <section class="sec">
      <h2>{'現調先' if pre == 'g' else '現場とお客様'}</h2>
      <div class="box">
        <div class="field"><label for="{pre}-addr">{addr_label}{req}</label>
          <input id="{pre}-addr" type="text" list="areas" autocomplete="off" enterkeyhint="next" placeholder="{addr_ph}"><p class="msg">住所を入れてください（区市まででも結構です）。</p>
          <p class="area" id="{pre}-area"></p>{'<div class="toll" id="m-toll" hidden></div>' if pre == 'm' else ''}</div>
        <div class="field"><label for="{pre}-name">お客様名{req}</label>
          <input id="{pre}-name" type="text" autocomplete="off" enterkeyhint="next" placeholder="例：江戸前ハーブ 様／山田 様"><p class="msg">お客様名を入れてください。</p></div>
        <div class="field"><label for="{pre}-tel">お客様の電話<span class="opt">任意</span></label>
          <input id="{pre}-tel" type="tel" inputmode="tel" autocomplete="off" enterkeyhint="next" placeholder="当日の連絡先があれば"></div>
        <div class="field"><label for="{pre}-site">店舗名・物件名<span class="opt">任意</span></label>
          <input id="{pre}-site" type="text" autocomplete="off" enterkeyhint="next"></div>
        <label class="chk"><input type="checkbox" id="{pre}-card">ご紹介カードを見たお客様<span class="opt">任意</span></label>
      </div>
    </section>""", f"""
    <section class="sec">
      <h2>ご要望</h2>
      <div class="box">
        <div class="field"><label for="{pre}-biko">ご要望・立ち会い・駐車場など<span class="opt">任意</span></label>
          <textarea id="{pre}-biko" placeholder="{biko_ph}"></textarea></div>
        <div class="field"><label for="{pre}-tantou">貴社のご担当<span class="opt">変わるときだけ</span></label>
          <input id="{pre}-tantou" type="text" value="{_esc(c['tantou'])}様" autocomplete="off"></div>
      </div>
    </section>"""

    mitsu_ate = c.get("mitsu_ate", "")
    ate_box = f"""
    <section class="sec">
      <h2>見積書の送り先</h2>
      <div class="box">
        <p class="atena">いつもの宛先：<b>{_esc(mitsu_ate)}</b></p>
        <div class="field"><label for="m-ate">追加の送り先<span class="opt">任意</span></label>
          <input id="m-ate" type="email" inputmode="email" autocomplete="email" multiple placeholder="例：fukahori@takara-co.jp（複数はカンマ区切り）"><p class="msg">メールアドレスの形を確かめてください。</p></div>
        <label class="chk"><input type="checkbox" id="m-ate-only">追加した送り先だけに送る</label>
      </div>
    </section>""" if mitsu_ate else ""
    m_top, m_bottom = kyoutsuu("m", "現場の住所", "例：大田区大森本町（区市まででも可）", "例：営業時間外（20時以降）希望、駐車スペースなし、立ち会いは店長 など")
    g_top, g_bottom = kyoutsuu("g", "現調先の住所（区市まで）", "例：墨田区／横浜市港北区", "例：見てほしい機種と台数、立ち会いの方、駐車場の有無 など")

    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="robots" content="noindex,nofollow">
<meta name="theme-color" content="#122F60">
<title>{_esc(c['kaisha'])}様 専用フォーム｜見積・現調のご依頼｜ワンヒッター株式会社</title>
<!-- tools/build-partner.py（tools/partner_tabs.py）で生成。手で直さない。料金は {c['ryokin']}、高速代・移動時間は data/partner-area.json。 -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
<header class="top"><div class="wrap"><p class="co">ワンヒッター株式会社　エアコン洗浄のご依頼</p><p class="for">{_esc(c['kaisha'])}<span>様 専用フォーム</span></p></div></header>
<nav class="tabs" role="tablist" aria-label="ご依頼の種類"><div class="wrap">
  <button type="button" class="tab" role="tab" id="t-mitsu" aria-controls="p-mitsu" aria-selected="true">見積依頼</button>
  <button type="button" class="tab" role="tab" id="t-genchou" aria-controls="p-genchou" aria-selected="false" tabindex="-1">現調依頼</button>
</div></nav>

<main>
  <div class="panel wrap" id="p-mitsu" role="tabpanel" aria-labelledby="t-mitsu">
    <p class="lead">台数を入れると、料金と作業できる日がすぐに出ます。</p>
    <section class="sec" id="mf-items">
      <h2>機種と台数<small>{(zei + '・') if zei else ''}台数が多いほど1台が安く</small></h2>
      <div class="box">
        {''.join(rows)}
        <div class="utiwake" id="utiwake" hidden></div>
      </div>
      <p class="smsg">台数を1つ以上選んでください。</p>
    </section>
    {m_top}
    <section class="sec">
      <h2>作業できる日<small>直近から</small></h2>
      <p class="lead" id="m-slotnote" style="margin:-2px 0 8px;font-size:13px"></p>
      <div class="box" id="m-slots"></div>
      <p class="lead" id="m-pick" style="color:var(--navy);font-weight:700;font-size:14px" aria-live="polite"></p>
    </section>
    {m_bottom}
    {ate_box}
    <p class="fine">表示は目安です。現場の状況で変わる場合は、作業の前にご説明します。高速代・駐車場代は実費です。いただいた内容はご依頼の対応のためだけに使います（<a href="https://lp.onehitter.jp/privacy/">個人情報の取扱いについて</a>）。</p>
  </div>

  <div class="panel wrap" id="p-genchou" role="tabpanel" aria-labelledby="t-genchou" hidden>
    <p class="lead">現調は1時間です。住所を入れると、移動時間を見込んで伺える日時が出ます。</p>
    {g_top}
    <section class="sec" id="gf-when">
      <h2>日時<small>現調 1時間</small></h2>
      <p class="lead" id="g-note" style="margin:-2px 0 8px;font-size:13px"></p>
      <div class="box"><div id="g-cal"></div><div class="times" id="g-times" hidden></div></div>
      <p class="smsg">日時を選ぶか、ご希望の日時を「ご要望」にお書きください。</p>
    </section>
    {g_bottom}
    <p class="fine">いただいた内容はご依頼の対応のためだけに使います（<a href="https://lp.onehitter.jp/privacy/">個人情報の取扱いについて</a>）。</p>
  </div>
</main>

<div class="bar" id="b-mitsu"><div class="wrap">
  <div class="sum"><div><div class="k">目安の料金</div><div class="v" id="bm-v"></div></div><div class="r" id="bm-r"></div></div>
  <button type="button" class="cta" id="m-cta">この内容で見積を依頼する</button>
</div></div>
<div class="bar" id="b-genchou" hidden><div class="wrap">
  <div class="sum"><div><div class="k">現調の日時</div><div class="v" id="bg-v" style="font-size:18px"></div></div></div>
  <button type="button" class="cta" id="g-cta">この日時で現調を依頼する</button>
</div></div>

<div class="sheet" id="sheet" hidden role="dialog" aria-modal="true" aria-labelledby="s-title"><div class="in">
  <h2 id="s-title"></h2><p class="sub" id="s-sub"></p>
  <dl id="s-dl"></dl>
  <div class="btns"><button type="button" class="cta" id="s-send">送信する</button><button type="button" class="ghost" id="s-back">戻って直す</button></div>
  <p class="fine">お急ぎはお電話 {tel} でも承ります。</p>
</div></div>

<datalist id="areas">{datalist}</datalist>
<form id="form" name="partner" method="POST" action="/partner/thanks/" data-netlify="true" netlify-honeypot="bot-field" hidden>
  <input type="hidden" name="form-name" value="partner">
  <p class="hp"><label>入力しないでください <input name="bot-field"></label></p>
  <input type="hidden" name="提携先" value="{_esc(c['kaisha'])}">
  <input type="hidden" name="ページ" value="{key}">
  <input type="hidden" name="請求先" value="{_esc(c['seikyu'])}">
  <input type="hidden" name="料金表" value="{_esc(price.get('ban', price.get('jiten', '')))}">
  {hidden}
</form>
{footer}
<script>{js}</script>
</body>
</html>
"""
