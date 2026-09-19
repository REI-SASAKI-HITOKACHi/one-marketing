#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""作業完了フォーム（和真さんのスマホ用）を組み立てる。

  オーナー決定（2026-09-19・MTGシート 第3回 3-4 議題5 / G245）原文
    ▼使用時の流れ
    施工開始時刻の30分後にマーケ部長が業務連絡グループLINEへ作業完了フォームを送信する。
    （→そのフォームのリンク先にアンケートフォームも格納する）
    →作業完了フォームの入力完了によりアンケート回収も済む導線を構築する
    ▼作業完了フォームの構成
    １．リンクを開くとトップ画面でお客様へのアンケート回答依頼画像が提示される
    １．５お客様がアンケート回答しながら施工担当者が次回予約を斡旋する
    ２．アンケート依頼画面下部に次へボタンを設置
    ３．作業完了フォーム本編
      ・施工写真添付欄（マーケ部長が即収集してSNS投稿へ反映させる）
        → 2026-09-19 オーナー指示で、複数を一度に選んで最大20枚まで。
          それ以上の現場は、残りを手でドライブへ上げる。
      ・作業終了時刻（データを蓄積・集計して後から施工時間計算の正確化への資産とする）
      ・施工内容（受注フォームの内容を自動表示して実際に施工した項目にチェック）
        表示＋追加受注欄（メニュー選択肢＋手入力欄｜追加受注がある場合は最終金額を
        マーケ部長が確認して売上シートへ反映させる ※自動反映でもOK）
      ・クレーム有無→有の場合は内容をフリー入力
      ・アンケート回答依頼済み
      ・次回予約提案済み
      ・汚れのBeforeAfterをお客様に確認してもらったか？
      ・お客様周辺情報（犬飼ってる、小さいこともありなど）のメモ欄
      ・現場で判断に迷ったこと（任意）

  【受注の内容をどう渡すか】★ここが設計の肝
    受注の内容（お名前・メニュー・金額）は **URLの # のうしろ**（フラグメント）に入れる。
      https://…/kanryo/#<base64url>
    ・# のうしろはサーバへ送られない。**お客様の情報をこのホストに置かない**で済む
    ・LINEのグループに出るのは、もともと和真さんとオーナーしか見ない場所
    ・置かないので、消し忘れも起きない

  【名乗り】
    画面1はお客様に見せる。**売上種類（ワンヒッター／おそうじ本舗）どおりの名乗りを出す。**
    受注の内容が無いとき（# が空）は、どちらの名前も出さない。
    2026-09-11 に本舗名義のお客様へワンヒッター名義で送ってしまった事故がある。

  出す先: lp/kanryo/index.html
  配信先: oh-naibu-sms-k7q3x（**社内用ホスト**／tools/deploy-juchu.py がまるごと送る）
"""
import base64
import io
import json
import pathlib

import segno

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "lp" / "kanryo" / "index.html"
SURVEY = "https://survey.onehitter.jp/?src=kanryo"


def qr_data_uri(url):
    q = segno.make(url, error="m")
    buf = io.BytesIO()
    q.save(buf, kind="png", scale=8, border=2, dark="#1a2330", light="#ffffff")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def main():
    oh = json.loads((ROOT / "data" / "prices.json").read_text(encoding="utf-8"))
    honpo = json.loads((ROOT / "data" / "prices-honpo.json").read_text(encoding="utf-8"))

    def hyou(d):
        return ([{"na": m["名称"], "kin": m["単体"]} for m in d["本メニュー"]]
                + [{"na": o["名称"], "kin": o["価格"]} for o in d["オプション"]])

    tsuika = {"One Hitter": hyou(oh), "本舗": hyou(honpo)}

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(HTML
                   .replace("__QR__", qr_data_uri(SURVEY))
                   .replace("__SURVEY__", SURVEY)
                   .replace("__TSUIKA__", json.dumps(tsuika, ensure_ascii=False)),
                   encoding="utf-8")
    print(f"書き出しました: {OUT}  {OUT.stat().st_size:,} bytes")
    print(f"  アンケート: {SURVEY}")
    print(f"  追加受注の選択肢: ワンヒッター {len(tsuika['One Hitter'])}件／本舗 {len(tsuika['本舗'])}件")


HTML = r"""<!doctype html>
<html lang="ja"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>作業完了｜社内用</title>
<style>
 :root{--ao:#1565c0;--fuchi:#d5dce3;--usu:#f6f8fa;--moji:#1a2330;--gure:#5b6876;--aka:#c62828;--midori:#2e7d32}
 *{box-sizing:border-box}
 body{margin:0;background:#eef1f4;color:var(--moji);
      font:16px/1.7 -apple-system,BlinkMacSystemFont,"Hiragino Sans","Noto Sans JP",sans-serif}
 .w{max-width:560px;margin:0 auto;padding:0 14px 120px}
 header{background:var(--moji);color:#fff;padding:14px;position:sticky;top:0;z-index:5}
 header b{font-size:17px}
 header span{display:block;font-size:12px;opacity:.75;margin-top:2px}
 section{background:#fff;border:1px solid var(--fuchi);border-radius:12px;margin:14px 0;padding:14px}
 h2{font-size:14px;margin:0 0 10px;color:var(--gure);letter-spacing:.04em}
 .hitsu{color:var(--aka);font-size:11px;margin-left:4px}
 label{display:block;font-size:13px;color:var(--gure);margin:12px 0 4px}
 input[type=text],input[type=time],input[type=number],textarea,select{
   width:100%;padding:12px;font-size:16px;border:1.5px solid var(--fuchi);border-radius:10px;background:#fff;
   color:var(--moji)}
 textarea{min-height:76px}
 .chu{font-size:12px;color:var(--gure);margin-top:6px}
 .err{color:var(--aka);font-size:13px;margin-top:4px;display:none}
 .err.deru{display:block}
 .kiku{display:flex;align-items:flex-start;gap:10px;padding:11px 0;border-bottom:1px solid var(--usu)}
 .kiku input{width:26px;height:26px;flex:0 0 auto;margin:0}
 .kiku span{font-size:14px;line-height:1.45}
 .erabu{display:flex;gap:8px}
 .erabu button{flex:1;padding:13px 10px;font-size:15px;border-radius:10px;
   border:1.5px solid var(--fuchi);background:#fff;color:var(--moji);cursor:pointer}
 .erabu button[aria-pressed=true]{background:var(--ao);border-color:var(--ao);color:#fff;font-weight:700}
 .erabu button.warui[aria-pressed=true]{background:var(--aka);border-color:var(--aka)}
 .juchu{background:var(--usu);border-radius:10px;padding:12px;font-size:14px}
 .juchu b{font-size:16px}
 .juchu div{padding:2px 0}
 .erabu-sha{position:relative;display:block;border:1.5px dashed var(--ao);border-radius:10px;
   padding:18px 12px;text-align:center;background:var(--usu);color:var(--ao);
   font-size:15px;font-weight:700;cursor:pointer}
 .erabu-sha input{position:absolute;inset:0;width:100%;height:100%;opacity:0;cursor:pointer}
 .sha-joutai{font-size:13px;color:var(--gure);margin-top:8px}
 .sha-joutai.ippai{color:var(--aka);font-weight:700}
 .shashin{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:10px}
 .sha{position:relative;aspect-ratio:1/1;border:1px solid var(--fuchi);border-radius:10px;
   overflow:hidden;background:var(--usu)}
 .sha img{width:100%;height:100%;object-fit:cover;display:block}
 .sha em{position:absolute;left:3px;bottom:3px;background:rgba(0,0,0,.55);color:#fff;font-style:normal;
   font-size:10px;padding:1px 5px;border-radius:6px}
 .sha button{position:absolute;right:3px;top:3px;width:28px;height:28px;padding:0;border:0;border-radius:50%;
   background:rgba(0,0,0,.62);color:#fff;font-size:16px;line-height:1;cursor:pointer}
 .kz{display:flex;align-items:center;gap:6px}
 .kz button{width:46px;height:46px;font-size:24px;line-height:1;border-radius:10px;
   border:1.5px solid var(--fuchi);background:#fff;color:var(--moji);cursor:pointer}
 .kz input{width:52px;text-align:center;padding:10px 2px;font-size:17px}
 .gyo{display:flex;align-items:center;gap:10px;padding:9px 0;border-bottom:1px solid var(--usu)}
 .gyo .na{flex:1;font-size:14px}
 .gyo .na em{display:block;font-style:normal;font-size:12px;color:var(--gure)}
 .gk{background:var(--usu);border-radius:10px;padding:12px;margin-top:12px}
 .gk div{display:flex;justify-content:space-between;font-size:14px;padding:3px 0}
 .gk .go{font-size:20px;font-weight:700;border-top:1px solid var(--fuchi);margin-top:6px;padding-top:8px}
 .soku{position:fixed;left:0;right:0;bottom:0;background:#fff;border-top:1px solid var(--fuchi);
   padding:10px 14px calc(10px + env(safe-area-inset-bottom));z-index:9}
 .soku button{width:100%;max-width:560px;margin:0 auto;display:block;padding:15px;font-size:17px;font-weight:700;
   background:var(--ao);color:#fff;border:0;border-radius:12px;cursor:pointer}
 .soku button:disabled{background:#9db4cc}

 /* ---- 画面1：お客様に見せる ---- */
 #okyaku{display:block;min-height:100vh;background:#fff;padding:26px 20px 40px;text-align:center}
 #okyaku h1{font-size:26px;line-height:1.5;margin:10px 0 4px}
 #okyaku .rei{font-size:15px;color:var(--gure);margin:0 0 22px}
 #okyaku .qr{width:230px;height:230px;margin:0 auto;display:block}
 #okyaku .qr-shita{font-size:15px;margin-top:10px}
 #okyaku .byou{display:inline-block;background:#fff8e1;border-radius:999px;padding:5px 16px;
   font-size:14px;font-weight:700;margin-bottom:18px}
 #okyaku .kono{display:inline-block;margin-top:18px;padding:14px 22px;font-size:16px;font-weight:700;
   background:var(--ao);color:#fff;border-radius:12px;text-decoration:none}
 #okyaku .nanori{margin-top:30px;font-size:13px;color:var(--gure)}
 #okyaku .tsugi{margin-top:34px;padding-top:18px;border-top:1px solid var(--fuchi)}
 #okyaku .tsugi button{padding:12px 24px;font-size:15px;border-radius:10px;
   border:1.5px solid var(--fuchi);background:#fff;color:var(--gure);cursor:pointer}
 #honbun{display:none}
 body.staff #okyaku{display:none}
 body.staff #honbun{display:block}
 .owari{display:none;text-align:center;padding:40px 14px}
 body.sumi .owari{display:block}
 body.sumi #honbun,body.sumi .soku,body.sumi #okyaku{display:none}
 .owari .maru{font-size:48px}
 .hp{position:absolute;left:-9999px}
</style></head><body>

<!-- ============ 画面1：お客様に見せる ============ -->
<div id="okyaku">
  <div class="byou">所要 30秒</div>
  <h1>本日はありがとう<br>ございました</h1>
  <p class="rei">よろしければ、仕上がりのご感想をお聞かせください。</p>
  <img class="qr" src="__QR__" alt="アンケートのQRコード">
  <p class="qr-shita">スマートフォンで読み取ってください</p>
  <a class="kono" href="__SURVEY__" target="_blank" rel="noopener">このスマホで回答する</a>
  <p class="nanori" id="nanori"></p>
  <div class="tsugi"><button type="button" id="tsugi">次へ（スタッフ用）</button></div>
</div>

<!-- ============ 画面2：作業完了フォーム本編 ============ -->
<header style="display:none" id="head"><b>作業完了フォーム</b><span>社内用。お客様には出しません</span></header>

<div class="w" id="honbun">

<section>
  <h2>この日の受注</h2>
  <div class="juchu" id="juchu">受注の内容が読み込めませんでした。手で入れてください。</div>
  <div id="te-name-box" hidden>
    <label>お客様のお名前<span class="hitsu">必須</span></label>
    <input type="text" id="te-name" placeholder="例）山本　美佑紀">
    <p class="err" id="e-name">お名前を入れてください</p>
  </div>
</section>

<section>
  <h2>1　施工写真<span class="hitsu">1枚以上</span></h2>
  <label class="erabu-sha" id="sha-erabu">写真を選ぶ（まとめて選べます）
    <input type="file" id="sha-file" accept="image/*" multiple>
  </label>
  <p class="sha-joutai" id="sha-joutai"></p>
  <div class="shashin" id="shashin"></div>
  <p class="chu">あとからもう一度選ぶと、前の写真に足されます。20枚まで入ります。<br>
     送る前に小さくするので、枚数が多くても重くなりません。<br>
     SNSに使うので、お宅が分かるもの（表札・窓の外・郵便物）は写さないでください。</p>
  <p class="err" id="e-shashin">写真を1枚以上入れてください</p>
</section>

<section>
  <h2>2　作業終了時刻<span class="hitsu">必須</span></h2>
  <input type="time" id="owari" step="300">
  <p class="chu" id="jitsu-chu"></p>
</section>

<section>
  <h2>3　施工内容<span class="hitsu">やったものにチェック</span></h2>
  <div id="naiyo"></div>
  <p class="err" id="e-naiyo">1つ以上チェックしてください</p>

  <h2 style="margin-top:18px">追加で受けたもの（あれば）</h2>
  <select id="tsuika-sel"><option value="">選んでください</option></select>
  <div class="kz" style="margin-top:8px">
    <button type="button" id="t-mns">−</button>
    <input type="text" id="t-kazu" inputmode="numeric" value="1">
    <button type="button" id="t-pls">＋</button>
    <button type="button" id="t-add" style="width:auto;flex:1;font-size:15px;font-weight:700;
      border-color:var(--ao);color:var(--ao)">追加する</button>
  </div>
  <div id="tsuika-list" style="margin-top:8px"></div>
  <label>一覧に無いものは、ここに書いてください</label>
  <input type="text" id="tsuika-te" placeholder="例）ベランダ高圧洗浄　5,500円">

  <div class="gk">
    <div><span>受注時の金額</span><b id="g-juchu">—</b></div>
    <div><span>追加ぶん</span><b id="g-tsuika">¥0</b></div>
    <div class="go"><span>最終金額</span><b id="g-go">—</b></div>
  </div>
  <label>実際にいただいた金額が違うときは、ここに入れてください（税込）</label>
  <input type="number" id="jissai" inputmode="numeric" placeholder="空のままなら上の最終金額を使います">
</section>

<section>
  <h2>4　クレームはありましたか<span class="hitsu">必須</span></h2>
  <div class="erabu" id="kure">
    <button type="button" data-v="なし">なし</button>
    <button type="button" data-v="あり" class="warui">あり</button>
  </div>
  <p class="err" id="e-kure">どちらか選んでください</p>
  <div id="kure-box" hidden>
    <label>何があったか、そのまま書いてください<span class="hitsu">必須</span></label>
    <textarea id="kure-naka" placeholder="言われたこと・こちらの対応・いまの状態"></textarea>
    <p class="err" id="e-kure-naka">内容を書いてください</p>
    <p class="chu">その場で直さなくて大丈夫です。すぐマーケ部長とオーナーに届きます。</p>
  </div>
</section>

<section>
  <h2>5　現場での確認</h2>
  <div id="kaku"></div>
</section>

<section>
  <h2>6　お客様のこと（任意）</h2>
  <label>覚えておきたいこと</label>
  <textarea id="shuhen" placeholder="例）犬を飼っている／小さいお子さんがいる／来客が多い／エアコンの下に仏壇"></textarea>
  <p class="chu">顧客台帳に移します。次にうかがうときの案内が変わります。</p>
  <label>現場で判断に迷ったこと（任意）</label>
  <textarea id="mayoi" placeholder="例）追加を勧めてよいか分からなかった／料金の聞かれ方に困った"></textarea>
</section>

<input class="hp" type="text" id="hp" tabindex="-1" autocomplete="off">
</div>

<div class="soku" id="soku" style="display:none"><button type="button" id="send">この内容で送る</button></div>

<div class="owari">
  <div class="maru">✓</div>
  <h1>お疲れさまでした</h1>
  <p id="owari-naka"></p>
  <p class="chu">写真と内容はマーケ部長に届きました。<br>売上シートへは1時間以内に入ります。</p>
</div>

<form hidden method="post" name="kanryo" data-netlify="true" netlify-honeypot="bot-field"
      enctype="multipart/form-data">
  <input type="hidden" name="form-name" value="kanryo">
  <input type="text" name="bot-field">
  <input type="text" name="受注ID"><input type="text" name="台帳"><input type="text" name="氏名">
  <input type="text" name="売上種類"><input type="text" name="施工日付">
  <input type="text" name="開始時刻"><input type="text" name="作業終了時刻">
  <input type="text" name="実所要（分）">
  <input type="text" name="実施した内容"><input type="text" name="やらなかった内容">
  <input type="text" name="追加受注"><input type="text" name="追加受注（手入力）">
  <input type="text" name="受注時の金額"><input type="text" name="追加金額"><input type="text" name="最終金額">
  <input type="text" name="クレーム"><input type="text" name="クレーム内容">
  <input type="text" name="アンケート依頼済み"><input type="text" name="次回予約提案済み">
  <input type="text" name="BeforeAfter確認済み">
  <input type="text" name="お客様周辺情報"><input type="text" name="迷ったこと">
  <input type="text" name="入力日時">
  <input type="file" name="施工写真1"><input type="file" name="施工写真2"><input type="file" name="施工写真3"><input type="file" name="施工写真4">
  <input type="file" name="施工写真5"><input type="file" name="施工写真6"><input type="file" name="施工写真7"><input type="file" name="施工写真8">
  <input type="file" name="施工写真9"><input type="file" name="施工写真10"><input type="file" name="施工写真11"><input type="file" name="施工写真12">
  <input type="file" name="施工写真13"><input type="file" name="施工写真14"><input type="file" name="施工写真15"><input type="file" name="施工写真16">
  <input type="file" name="施工写真17"><input type="file" name="施工写真18"><input type="file" name="施工写真19"><input type="file" name="施工写真20">
</form>

<script>
(function(){
  var TSUIKA = __TSUIKA__;
  var $ = function(id){ return document.getElementById(id); };
  var MAI = 20, MAX = 1600, SHITSU = 0.82;   // 20枚まで。超えたぶんはドライブへ手で
  var shashin = [];       // {blob, puri}
  var tsuikaHai = [];     // {na, kin, kazu}
  var jotai = { kure:'' };
  var J = null;           // 受注の内容（URLの # から）

  var KAKUNIN = [
    { key:'アンケート依頼済み',    na:'アンケートの回答をお願いした' },
    { key:'次回予約提案済み',      na:'次回のご予約をご提案した' },
    { key:'BeforeAfter確認済み',   na:'汚れの Before / After をお客様に見ていただいた' }
  ];
  var kakuIre = {};

  /* ---- 受注の内容を # から読む（サーバには送られない） ---- */
  function yomu(){
    var h = (location.hash || '').replace(/^#/, '');
    if (!h) { return null; }
    try {
      var s = h.replace(/-/g,'+').replace(/_/g,'/');
      while (s.length % 4) { s += '='; }
      return JSON.parse(decodeURIComponent(escape(atob(s))));
    } catch (e) { return null; }
  }
  J = yomu();

  /* ---- 画面1：名乗りは受注の内容どおり。読めないときは出さない ---- */
  (function(){
    var na = J && J.s === '本舗' ? 'おそうじ本舗' : (J && J.s ? 'ワンヒッター株式会社' : '');
    $('nanori').textContent = na;
  })();
  $('tsugi').addEventListener('click', function(){
    document.body.className = 'staff';
    $('head').style.display = ''; $('soku').style.display = '';
    window.scrollTo(0,0);
  });

  /* ---- 受注の内容を出す ---- */
  function en(n){ return '¥' + Number(n || 0).toLocaleString(); }
  (function(){
    if (!J) { $('te-name-box').hidden = false; return; }
    var d = $('juchu');
    d.innerHTML = '';
    function gyo(html){ var x = document.createElement('div'); x.innerHTML = html; d.appendChild(x); }
    var b = document.createElement('div');
    b.innerHTML = '<b></b>';
    b.querySelector('b').textContent = (J.n || '') + ' さま';
    d.appendChild(b);
    gyo('');
    d.lastChild.textContent = (J.d || '') + '　' + (J.t || '') + ' 開始　' + (J.s === '本舗' ? 'おそうじ本舗' : 'ワンヒッター');
    gyo(''); d.lastChild.textContent = (J.m || []).join('／');
    gyo(''); d.lastChild.textContent = '受注時の金額 ' + en(J.k);
  })();

  /* ---- 1 写真（その場で小さくする） ---- */
  function chiisaku(file, cb){
    var img = new Image(), url = URL.createObjectURL(file);
    img.onload = function(){
      var w = img.width, h = img.height, r = Math.min(1, MAX / Math.max(w, h));
      var c = document.createElement('canvas');
      c.width = Math.round(w * r); c.height = Math.round(h * r);
      c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
      c.toBlob(function(bl){ URL.revokeObjectURL(url); cb(bl || file, c.toDataURL('image/jpeg', 0.5)); },
               'image/jpeg', SHITSU);
    };
    img.onerror = function(){ URL.revokeObjectURL(url); cb(file, ''); };
    img.src = url;
  }
  (function(){
    var fin = $('sha-file'), oya = $('shashin'), jo = $('sha-joutai');

    function joutai(moji, warui){
      jo.textContent = moji || (shashin.length + '枚／' + MAI + '枚まで');
      jo.className = 'sha-joutai' + (warui ? ' ippai' : '');
    }
    function narabu(){
      oya.innerHTML = '';
      shashin.forEach(function(s, i){
        var d = document.createElement('div'); d.className = 'sha';
        if (s.puri) { var im = new Image(); im.src = s.puri; im.alt = (i+1) + '枚目'; d.appendChild(im); }
        var em = document.createElement('em');
        em.textContent = Math.round(s.blob.size / 1024) + 'KB';
        d.appendChild(em);
        var b = document.createElement('button');
        b.type = 'button'; b.textContent = '×';
        b.setAttribute('aria-label', (i+1) + '枚目を消す');
        b.addEventListener('click', function(){ shashin.splice(i, 1); narabu(); joutai(); });
        d.appendChild(b); oya.appendChild(d);
      });
    }
    fin.addEventListener('change', function(){
      var hai = Array.prototype.slice.call(fin.files || []);
      fin.value = '';                       // 同じ写真をもう一度選べるように空にする
      if (!hai.length) { return; }
      var aki = Math.max(0, MAI - shashin.length);
      var afure = Math.max(0, hai.length - aki);
      hai = hai.slice(0, aki);
      if (!hai.length) {
        joutai('写真は' + MAI + '枚までです。残りはドライブへ手でアップしてください。', 1);
        return;
      }
      var i = 0;
      (function tsugi(){
        if (i >= hai.length) {
          narabu();
          if (afure) {
            joutai(shashin.length + '枚。' + MAI + '枚を超えたので、'
                   + afure + '枚は入りませんでした。残りはドライブへ手でアップしてください。', 1);
          } else { joutai(); }
          kakusu('e-shashin');
          return;
        }
        joutai((i + 1) + '/' + hai.length + ' 枚を準備しています…');
        chiisaku(hai[i], function(bl, puri){
          shashin.push({ blob: bl, puri: puri });
          i += 1; narabu(); tsugi();
        });
      })();
    });
    joutai();
  })();

  /* ---- 2 作業終了時刻 ---- */
  (function(){
    var n = new Date();
    $('owari').value = ('0'+n.getHours()).slice(-2) + ':' + ('0'+(Math.round(n.getMinutes()/5)*5)%60).slice(-2);
    jitsu();
  })();
  function ji2fun(s){ var m = /^(\d{1,2}):(\d{2})$/.exec(String(s||'')); return m ? +m[1]*60 + +m[2] : null; }
  function jitsu(){
    var k = J && ji2fun(J.t), o = ji2fun($('owari').value);
    if (k === null || o === null || !k) { $('jitsu-chu').textContent = ''; return 0; }
    var f = o - k; if (f < 0) { f += 1440; }
    $('jitsu-chu').textContent = '開始 ' + J.t + ' から ' +
      (f >= 60 ? Math.floor(f/60) + '時間' + (f%60 ? (f%60)+'分' : '') : f + '分') + 'です。';
    return f;
  }
  $('owari').addEventListener('input', jitsu);

  /* ---- 3 施工内容 ---- */
  var naiyoIre = {};
  (function(){
    var hai = (J && J.m) || [];
    var oya = $('naiyo');
    if (!hai.length) { oya.innerHTML = '<p class="chu">受注の内容が読めないので、追加受注の欄に書いてください。</p>'; return; }
    hai.forEach(function(na, i){
      var l = document.createElement('label'); l.className = 'kiku';
      var c = document.createElement('input'); c.type = 'checkbox'; c.checked = true;
      naiyoIre[i] = true;
      c.addEventListener('change', function(){ naiyoIre[i] = c.checked; kakusu('e-naiyo'); });
      var s = document.createElement('span'); s.textContent = na;
      l.appendChild(c); l.appendChild(s); oya.appendChild(l);
    });
  })();

  /* ---- 3 追加受注 ---- */
  (function(){
    var hyou = TSUIKA[(J && J.s) || 'One Hitter'] || TSUIKA['One Hitter'];
    var sel = $('tsuika-sel');
    hyou.forEach(function(m){
      var o = document.createElement('option');
      o.value = m.na; o.textContent = m.na + '　' + en(m.kin);
      o.dataset.kin = String(m.kin);
      sel.appendChild(o);
    });
    function kazu(v){
      v = Math.max(1, Math.min(99, v || 1)); $('t-kazu').value = String(v); return v;
    }
    $('t-mns').addEventListener('click', function(){ kazu(parseInt($('t-kazu').value,10) - 1); });
    $('t-pls').addEventListener('click', function(){ kazu(parseInt($('t-kazu').value,10) + 1); });
    $('t-add').addEventListener('click', function(){
      var o = sel.selectedOptions[0]; if (!o || !o.value) { return; }
      tsuikaHai.push({ na:o.value, kin:Number(o.dataset.kin), kazu:kazu(parseInt($('t-kazu').value,10)) });
      sel.value = ''; $('t-kazu').value = '1'; kaku();
    });
  })();
  function kaku(){
    var oya = $('tsuika-list'); oya.innerHTML = '';
    tsuikaHai.forEach(function(t, i){
      var d = document.createElement('div'); d.className = 'gyo';
      var na = document.createElement('div'); na.className = 'na';
      na.innerHTML = '<span></span><em></em>';
      na.querySelector('span').textContent = t.na + (t.kazu > 1 ? ' ×' + t.kazu : '');
      na.querySelector('em').textContent = en(t.kin * t.kazu);
      var b = document.createElement('button');
      b.type = 'button'; b.textContent = '消す';
      b.style.cssText = 'padding:8px 12px;font-size:13px;border-radius:8px;border:1.5px solid var(--fuchi);background:#fff;color:var(--aka)';
      b.addEventListener('click', function(){ tsuikaHai.splice(i,1); kaku(); });
      d.appendChild(na); d.appendChild(b); oya.appendChild(d);
    });
    kingaku();
  }
  function tsuikaGokei(){
    var n = 0; tsuikaHai.forEach(function(t){ n += t.kin * t.kazu; }); return n;
  }
  function kingaku(){
    var moto = J && Number(J.k) || 0, ts = tsuikaGokei();
    $('g-juchu').textContent = moto ? en(moto) : '—';
    $('g-tsuika').textContent = en(ts);
    $('g-go').textContent = (moto || ts) ? en(moto + ts) : '—';
  }
  kingaku();

  /* ---- 4 クレーム ---- */
  $('kure').addEventListener('click', function(e){
    var b = e.target.closest('button'); if (!b) { return; }
    Array.prototype.forEach.call($('kure').querySelectorAll('button'), function(x){
      x.setAttribute('aria-pressed', String(x === b));
    });
    jotai.kure = b.dataset.v;
    $('kure-box').hidden = (jotai.kure !== 'あり');
    kakusu('e-kure');
  });

  /* ---- 5 現場での確認 ---- */
  (function(){
    var oya = $('kaku');
    KAKUNIN.forEach(function(k, i){
      var l = document.createElement('label'); l.className = 'kiku';
      var c = document.createElement('input'); c.type = 'checkbox';
      c.addEventListener('change', function(){ kakuIre[k.key] = c.checked; });
      var s = document.createElement('span'); s.textContent = k.na;
      l.appendChild(c); l.appendChild(s); oya.appendChild(l);
    });
  })();

  /* ---- 検査と送信 ---- */
  function dasu(id){ $(id).classList.add('deru'); }
  function kakusu(id){ var e = $(id); if (e) { e.classList.remove('deru'); } }
  ['te-name','kure-naka'].forEach(function(id){
    var e = $(id); if (e) { e.addEventListener('input', function(){ kakusu('e-' + (id==='te-name'?'name':'kure-naka')); }); }
  });

  $('send').addEventListener('click', function(){
    if ($('hp').value) { return; }
    var ng = null;
    if (!shashin.length) { dasu('e-shashin'); ng = 1; }
    var yatta = [], yaranai = [];
    ((J && J.m) || []).forEach(function(na, i){ (naiyoIre[i] ? yatta : yaranai).push(na); });
    if ((J && J.m || []).length && !yatta.length && !tsuikaHai.length) { dasu('e-naiyo'); ng = 1; }
    if (!jotai.kure) { dasu('e-kure'); ng = 1; }
    if (jotai.kure === 'あり' && !$('kure-naka').value.trim()) { dasu('e-kure-naka'); ng = 1; }
    if (!J && !$('te-name').value.trim()) { dasu('e-name'); ng = 1; }
    if (ng) {
      var e = document.querySelector('.err.deru');
      if (e) { e.scrollIntoView({behavior:'smooth', block:'center'}); }
      return;
    }
    var moto = J && Number(J.k) || 0, ts = tsuikaGokei();
    var jissai = parseInt($('jissai').value || '0', 10) || 0;
    var fd = new FormData();
    var atai = {
      'form-name': 'kanryo',
      '受注ID': (J && J.i) || '',
      '台帳': (J && J.r) || '',
      '氏名': (J && J.n) || $('te-name').value.trim(),
      '売上種類': (J && J.s) || '',
      '施工日付': (J && J.d) || '',
      '開始時刻': (J && J.t) || '',
      '作業終了時刻': $('owari').value,
      '実所要（分）': String(jitsu() || ''),
      '実施した内容': yatta.join('／'),
      'やらなかった内容': yaranai.join('／'),
      '追加受注': tsuikaHai.map(function(t){ return t.na + (t.kazu>1?' ×'+t.kazu:'') + ' ' + t.kin*t.kazu + '円'; }).join('／'),
      '追加受注（手入力）': $('tsuika-te').value.trim(),
      '受注時の金額': String(moto || ''),
      '追加金額': String(ts),
      '最終金額': String(jissai || (moto + ts)),
      'クレーム': jotai.kure,
      'クレーム内容': $('kure-naka').value.trim(),
      'アンケート依頼済み': kakuIre['アンケート依頼済み'] ? 'はい' : 'いいえ',
      '次回予約提案済み': kakuIre['次回予約提案済み'] ? 'はい' : 'いいえ',
      'BeforeAfter確認済み': kakuIre['BeforeAfter確認済み'] ? 'はい' : 'いいえ',
      'お客様周辺情報': $('shuhen').value.trim(),
      '迷ったこと': $('mayoi').value.trim(),
      '入力日時': new Date().toISOString()
    };
    Object.keys(atai).forEach(function(k){ fd.append(k, atai[k]); });
    shashin.forEach(function(s, i){
      fd.append('施工写真' + (i+1), new File([s.blob], '写真' + (i+1) + '.jpg', {type:'image/jpeg'}));
    });
    var b = $('send'); b.disabled = true; b.textContent = '送っています…';
    fetch('/', { method:'POST', body: fd })
      .then(function(r){ if (!r.ok) { throw new Error('http ' + r.status); }
        document.body.className = 'sumi';
        $('head').style.display = 'none';
        $('owari-naka').textContent = atai['氏名'] + ' さま　'
          + atai['作業終了時刻'] + ' 終了　写真 ' + shashin.length + '枚';
        window.scrollTo(0,0);
      })
      .catch(function(){
        b.disabled = false; b.textContent = 'この内容で送る';
        alert('送れませんでした。電波の良いところでもう一度お試しください。\n何度も失敗するときは、マーケ部長に連絡してください。');
      });
  });
})();
</script>
</body></html>
"""

if __name__ == "__main__":
    main()
