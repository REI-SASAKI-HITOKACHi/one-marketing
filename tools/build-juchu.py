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

  オーナー指示（2026-09-19 第3弾）
    ・提携先はプルダウン選択へ（表記ゆれ防止）。新規入力欄もほしい → data/teikei-saki.json
    ・**本舗はキャンペーンごとに料金が変わる。和真さんからLINEで知らせが来たら、
      その都度いちばん新しい料金を本部サイトで確認して data/prices-honpo.json に反映し、
      build → deploy まで流すこと。**（手順は docs/受注フォーム.md）

  オーナー指示（2026-09-19 第2弾・8点）
    1 流入経路は売上シートの選択肢を全部出す      → data/ryunyu-keiro.json
    2 ワンヒッターと本舗で料金が違う。本舗は本部HPの正規料金 → data/prices-honpo.json
    3 終了時刻の欄を開始時刻の下に置く
    4 既存の予定をフォーム上で見えるように（ダブルブッキング防止） → yotei.json
    5 数量に大きい ＋ − ボタン（直接入力も残す）
    6 郵便番号欄をなくし、住所から自動で入れる   → tools/yubin.py（**サーバ側**）
    7 ヒアリングのチェックボックス5項目
    8 起動が極端に重くなるものは事前に相談        → 重くなるものは無し（下記）

  【起動の重さについて】
    ・料金表は2つになるが、合わせても約6KBでHTMLに同梱。増分はごくわずか。
    ・郵便番号の索引（約850KB）は**端末へ送らない**。引くのは取り込み時（tools/yubin.py）。
    ・既存の予定は別ファイル yotei.json（約4KB）を**描画後に**読む。初期表示は待たない。

  料金と所要時間は data/prices.json（ワンヒッター）と data/prices-honpo.json（本舗）から
  入れる。**手で書き写さない**（写すとずれる。ずれた金額が台帳に入ると分析が全部ずれる）。

  出す先: lp/juchu/index.html ＋ lp/juchu/yotei.json
  配信先: oh-genba-form-m8x2q（**社内用ホスト**。2026-09-22 に oh-naibu-sms から分離）
    ★お客様用ホストに社内ツールを置かないこと。2026-09-12 のセーフブラウジング事故の教訓。
"""
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "lp" / "juchu" / "index.html"
YOTEI = ROOT / "lp" / "juchu" / "yotei.json"
YOTEI_MOTO = ROOT / "data" / "calendar" / "watanabe-events.json"
KITEI_SHOYOU = 60

# ヒアリング（2026-09-19 オーナー指示）。jouken は出す条件。
HEARING = [
    {"na": "駐車場が確保できる", "jouken": ""},
    {"na": "電気・水道をお借りする許可を得た", "jouken": ""},
    {"na": "エアコンの下にある物の移動を依頼した", "jouken": "エアコン"},
    {"na": "パーツの洗い場として浴室をお借りする承諾を得た", "jouken": "エアコン"},
    {"na": "保証年数を確認した（9年まで／洗濯機は7年まで）", "jouken": "家電"},
]
KADEN = ["エアコン", "洗濯機", "冷蔵庫", "食器洗い", "乾燥機", "空気清浄機"]


def shoyou(m):
    n = re.search(r"(\d+)", str(m.get("所要") or ""))
    return int(n.group(1)) if n else KITEI_SHOYOU


def hyou(d, kata):
    """料金表を1つ作る。kata は 'oh'（ワンヒッター）か 'honpo'（おそうじ本舗）。"""
    menu = []
    for m in d["本メニュー"]:
        r = {"na": m["名称"], "tan": m["単体"],
             "dou": m.get("同時施工", m["単体"]), "fun": shoyou(m)}
        if m.get("キャンペーン"):
            r["cam"] = m["キャンペーン"]
            r["camDou"] = m.get("キャンペーン同時施工", m["キャンペーン"])
        r["kaden"] = any(k in m["名称"] for k in KADEN)
        r["eakon"] = "エアコン" in m["名称"]
        menu.append(r)
    return {
        "kata": kata,
        "na": "ワンヒッター" if kata == "oh" else "おそうじ本舗",
        "menu": menu,
        "opt": [{"na": o["名称"], "kin": o["価格"]} for o in d["オプション"]],
        "hanki": d.get("繁忙期加算") or None,
        "matome": [m["名称"] for m in d["本メニュー"] if m.get("キャンペーン")] if kata == "honpo" else [],
    }


def yotei_dasu():
    """和真さんの既に塞がっている時間を、フォームが読める形で書き出す。
       ★氏名・住所・金額は入れない（元ファイルにも入っていない）。"""
    hai = []
    if YOTEI_MOTO.exists():
        moto = json.loads(YOTEI_MOTO.read_text(encoding="utf-8"))
        for e in moto.get("events", []):
            s, t = e.get("start") or {}, e.get("end") or {}
            if s.get("dateTime"):
                hai.append({"hi": s["dateTime"][:10], "kai": s["dateTime"][11:16],
                            "owa": (t.get("dateTime") or "")[11:16] or "",
                            "na": e.get("summary", "予定")})
            elif s.get("date"):
                hai.append({"hi": s["date"], "kai": "", "owa": "", "na": e.get("summary", "予定")})
        toku = moto.get("_meta", {}).get("取得日時", "")
    else:
        toku = ""
    hai.sort(key=lambda x: (x["hi"], x["kai"]))
    YOTEI.parent.mkdir(parents=True, exist_ok=True)
    YOTEI.write_text(json.dumps({"取得": toku, "予定": hai}, ensure_ascii=False) + "\n",
                     encoding="utf-8")
    return hai, toku


def main():
    oh = hyou(json.loads((ROOT / "data" / "prices.json").read_text(encoding="utf-8")), "oh")
    honpo_moto = json.loads((ROOT / "data" / "prices-honpo.json").read_text(encoding="utf-8"))
    honpo_toku = honpo_moto.get("取得日", "（不明）")
    honpo = hyou(honpo_moto, "honpo")
    keiro = json.loads((ROOT / "data" / "ryunyu-keiro.json").read_text(encoding="utf-8"))
    teikei = json.loads((ROOT / "data" / "teikei-saki.json").read_text(encoding="utf-8"))
    yotei, toku = yotei_dasu()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(HTML
                   .replace("__OH__", json.dumps(oh, ensure_ascii=False))
                   .replace("__HONPO__", json.dumps(honpo, ensure_ascii=False))
                   .replace("__KEIRO__", json.dumps(keiro["選択肢"], ensure_ascii=False))
                   .replace("__HOUJIN__", json.dumps(keiro["法人名を聞く"], ensure_ascii=False))
                   .replace("__HEARING__", json.dumps(HEARING, ensure_ascii=False))
                   .replace("__TEIKEI__", json.dumps(teikei["選択肢"], ensure_ascii=False)),
                   encoding="utf-8")
    print(f"書き出しました: {OUT}  {OUT.stat().st_size:,} bytes")
    print(f"  ワンヒッター 本メニュー {len(oh['menu'])}件／オプション {len(oh['opt'])}件"
          f"／繁忙期加算 {oh['hanki']['金額']}円（{oh['hanki']['対象月']}月）")
    print(f"  おそうじ本舗 本メニュー {len(honpo['menu'])}件／オプション {len(honpo['opt'])}件"
          f"／繁忙期加算なし（本部は土日祝の割増なし）")
    print(f"  流入経路 {len(keiro['選択肢'])}件／提携先 {len(teikei['選択肢'])}件／ヒアリング {len(HEARING)}件")
    print(f"  ★本舗の料金は {honpo_toku} 取得。キャンペーンが変わったら "
          f"data/prices-honpo.json を直して流し直すこと")
    print(f"  既存の予定 {YOTEI}  {YOTEI.stat().st_size:,} bytes（{len(yotei)}件・取得 {toku}）")


HTML = r"""<!doctype html>
<html lang="ja"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>受注の記録｜社内用</title>
<style>
 :root{--ao:#1565c0;--fuchi:#d5dce3;--usu:#f6f8fa;--moji:#1a2330;--gure:#5b6876;--aka:#c62828}
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
 .erabu{display:flex;flex-wrap:wrap;gap:8px}
 .erabu button{flex:1 1 auto;min-width:96px;padding:12px 10px;font-size:15px;border-radius:10px;
   border:1.5px solid var(--fuchi);background:#fff;color:var(--moji);cursor:pointer}
 .erabu.komakai button{min-width:0;flex:0 1 auto;padding:10px 12px;font-size:14px}
 .erabu button[aria-pressed=true]{background:var(--ao);border-color:var(--ao);color:#fff;font-weight:700}
 label{display:block;font-size:13px;color:var(--gure);margin:12px 0 4px}
 input[type=text],input[type=tel],input[type=date],input[type=time],input[type=number],textarea,select{
   width:100%;padding:12px;font-size:16px;border:1.5px solid var(--fuchi);border-radius:10px;background:#fff;
   color:var(--moji);-webkit-appearance:none;appearance:none}
 select{background-image:linear-gradient(45deg,transparent 50%,var(--gure) 50%),
   linear-gradient(135deg,var(--gure) 50%,transparent 50%);
   background-position:calc(100% - 18px) 21px,calc(100% - 12px) 21px;
   background-size:6px 6px,6px 6px;background-repeat:no-repeat;padding-right:36px}
 textarea{min-height:76px}
 .menu-gyo{display:flex;align-items:center;gap:10px;padding:9px 0;border-bottom:1px solid var(--usu)}
 .menu-gyo .na{flex:1;font-size:14px;line-height:1.45}
 .menu-gyo .na em{display:block;font-style:normal;font-size:12px;color:var(--gure)}
 .menu-gyo.aru{background:#f2f7fd;border-radius:8px;padding-left:8px;padding-right:8px}
 .kz{display:flex;align-items:center;gap:6px;flex:0 0 auto}
 .kz button{width:46px;height:46px;font-size:24px;line-height:1;border-radius:10px;
   border:1.5px solid var(--fuchi);background:#fff;color:var(--moji);cursor:pointer;
   -webkit-tap-highlight-color:transparent}
 .kz button:active{background:var(--usu)}
 .kz button.pls{border-color:var(--ao);color:var(--ao);font-weight:700}
 .kz input{width:52px;text-align:center;padding:10px 2px;font-size:17px}
 .gk{background:var(--usu);border-radius:10px;padding:12px;margin-top:12px}
 .gk div{display:flex;justify-content:space-between;font-size:14px;padding:3px 0}
 .gk .go{font-size:20px;font-weight:700;border-top:1px solid var(--fuchi);margin-top:6px;padding-top:8px}
 .chu{font-size:12px;color:var(--gure);margin-top:6px}
 .err{color:var(--aka);font-size:13px;margin-top:4px;display:none}
 .err.deru{display:block}
 .yotei{margin-top:10px;background:var(--usu);border-radius:10px;padding:10px;font-size:13px}
 .yotei b{font-size:12px;color:var(--gure);display:block;margin-bottom:4px}
 .yotei ul{margin:0;padding-left:18px}
 .yotei li.kasanaru{color:var(--aka);font-weight:700}
 .keikoku{background:#fff1f1;border:1.5px solid var(--aka);color:var(--aka);border-radius:10px;
   padding:10px;font-size:14px;font-weight:700;margin-top:8px;display:none}
 .keikoku.deru{display:block}
 .kiku{display:flex;align-items:flex-start;gap:10px;padding:10px 0;border-bottom:1px solid var(--usu)}
 .kiku input{width:26px;height:26px;flex:0 0 auto;margin:0}
 .kiku span{font-size:14px;line-height:1.45}
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
 summary{font-size:14px;color:var(--gure);cursor:pointer}
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
  <p class="chu" id="hyou-chu">選ぶと、その会社の料金表に切り替わります。</p>
</section>

<section>
  <h2>2　どこからの受注ですか<span class="hitsu">必須</span></h2>
  <div class="erabu komakai" id="keiro"></div>
  <p class="err" id="e-keiro">選んでください</p>
  <div id="houjin-box" hidden>
    <label>提携先・紹介元</label>
    <select id="houjin-sel"></select>
    <div id="houjin-shin" hidden>
      <label>新しい先のお名前<span class="hitsu">一覧に無いとき</span></label>
      <input type="text" id="houjin" placeholder="例）株式会社◯◯">
      <p class="chu">台帳にも足しておきます。会社名は正式名称でお願いします。</p>
    </div>
  </div>
</section>

<section>
  <h2>3　いつ施工しますか<span class="hitsu">必須</span></h2>
  <label>施工日</label>
  <input type="date" id="hi">
  <p class="err" id="e-hi">施工日を入れてください</p>
  <label>開始時刻</label>
  <input type="time" id="jikoku" value="09:00" step="900">
  <label>終了時刻<span style="font-weight:400">（メニューの所要から自動で入ります。直せます）</span></label>
  <input type="time" id="owari-jikoku" step="900">
  <p class="chu"><a href="#" id="owari-modosu">所要時間から入れ直す</a></p>
  <div class="keikoku" id="kasanari"></div>
  <div class="yotei" id="yotei"><b>この日の予定</b><span id="yotei-naka">施工日を入れると出ます</span></div>
</section>

<section>
  <h2>4　何をしますか<span class="hitsu">必須</span></h2>
  <div id="cam-box" hidden style="margin-bottom:10px">
    <label class="kiku" style="border:0;padding:0">
      <input type="checkbox" id="cam">
      <span>本部のキャンペーン価格で受けた（壁掛けエアコン）</span>
    </label>
  </div>
  <div id="menu"></div>
  <details style="margin-top:10px">
    <summary>オプションを足す</summary>
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
  <p class="chu" id="ryokin-chu">あとからスプレッドシートで直せます。この場では、だいたいで構いません。</p>
</section>

<section>
  <h2>5　現場の確認（ヒアリング）</h2>
  <div id="kiku"></div>
  <p class="chu">確認できた項目にチェックを入れてください。チェックの無い項目は「未確認」として記録します。</p>
</section>

<section>
  <h2>6　お客様<span class="hitsu">必須はお名前だけ</span></h2>
  <label>お名前<span class="hitsu">必須</span></label>
  <input type="text" id="name" placeholder="例）山本　美佑紀">
  <p class="err" id="e-name">お名前を入れてください</p>
  <label>ご住所</label>
  <input type="text" id="addr" placeholder="例）江戸川区中央4-2-13-905">
  <p class="chu">郵便番号は入れなくて構いません。住所から自動でスプレッドシートに入ります。</p>
  <label>お電話番号</label>
  <input type="tel" id="tel" inputmode="numeric" placeholder="ハイフン無しでも可">
</section>

<section>
  <h2>7　現場のメモ（任意）</h2>
  <textarea id="memo" placeholder="上のヒアリングに無いこと（製造年数・鍵の受け渡し・駐車場の場所など）。カレンダーの説明欄に入ります"></textarea>
</section>

<input class="hp" type="text" id="hp" tabindex="-1" autocomplete="off">
</div>

<div class="soku" id="soku"><button type="button" id="send">この内容で記録する</button></div>

<div class="owari" id="owari">
  <div class="maru">✓</div>
  <h1>記録しました</h1>
  <p id="owari-naka"></p>
  <p class="chu">スプレッドシートとカレンダーへは、1時間以内に自動で入ります。<br>すぐに見たいときは、マーケ部長に言ってください。</p>
  <p style="margin-top:24px"><button type="button" id="tsugi"
     style="padding:12px 20px;font-size:15px;border-radius:10px;border:1.5px solid var(--fuchi);background:#fff">
     続けてもう1件入れる</button></p>
</div>

<form hidden method="post" name="juchu" data-netlify="true" netlify-honeypot="bot-field">
  <input type="hidden" name="form-name" value="juchu">
  <input type="text" name="bot-field">
  <input type="text" name="売上種類"><input type="text" name="施工日付">
  <input type="text" name="開始時刻"><input type="text" name="終了時刻">
  <input type="text" name="流入経路">
  <input type="text" name="氏名"><input type="text" name="TEL">
  <input type="text" name="住所">
  <input type="text" name="売上（税込）"><input type="text" name="実施メニュー">
  <input type="text" name="所要の目安（分）"><input type="text" name="法人名">
  <input type="text" name="ヒアリング"><input type="text" name="備考">
  <input type="text" name="見込み金額"><input type="text" name="入力日時">
</form>

<script>
(function(){
  var HYOU = { 'One Hitter': __OH__, '本舗': __HONPO__ };
  var KEIRO = __KEIRO__, HOUJIN = __HOUJIN__, HEARING = __HEARING__, TEIKEI = __TEIKEI__;
  var SHINKI = '＋ 新しい先を入れる（一覧に無い）';
  var $ = function(id){ return document.getElementById(id); };
  var jotai = { shurui:'', keiro:'', kazu:{}, optKazu:{}, owariTe:false };
  var YOTEI = null;

  function hyou(){ return HYOU[jotai.shurui] || null; }
  function en(n){ return '¥' + Number(n).toLocaleString(); }

  /* ---- 選択ボタン ---- */
  function botanTsukuru(oya, hai){
    hai.forEach(function(v){
      var b = document.createElement('button');
      b.type = 'button'; b.dataset.v = v; b.textContent = v;
      oya.appendChild(b);
    });
  }
  botanTsukuru($('keiro'), KEIRO);

  /* ---- 提携先・紹介元（表記ゆれを防ぐためプルダウン。無い先は新規入力） ---- */
  (function(){
    var sel = $('houjin-sel');
    [''].concat(TEIKEI).concat([SHINKI]).forEach(function(v){
      var o = document.createElement('option');
      o.value = v; o.textContent = v || '選んでください';
      sel.appendChild(o);
    });
    sel.addEventListener('change', function(){
      $('houjin-shin').hidden = (sel.value !== SHINKI);
      if (sel.value !== SHINKI) { $('houjin').value = ''; }
    });
  })();
  function houjinMoji(){
    var sel = $('houjin-sel');
    if ($('houjin-box').hidden) { return ''; }
    return (sel.value === SHINKI) ? $('houjin').value.trim() : sel.value;
  }

  function botan(oyaId, key, ato){
    var oya = $(oyaId);
    oya.addEventListener('click', function(e){
      var b = e.target.closest('button'); if (!b) { return; }
      Array.prototype.forEach.call(oya.querySelectorAll('button'), function(x){
        x.setAttribute('aria-pressed', String(x === b));
      });
      jotai[key] = b.dataset.v;
      kakusu('e-' + key);
      if (ato) { ato(); }
    });
  }
  botan('shurui','shurui', function(){ hyouKirikae(); });
  botan('keiro','keiro', function(){
    $('houjin-box').hidden = HOUJIN.indexOf(jotai.keiro) === -1;
  });

  /* ---- メニューの行（＋ − ボタン付き） ---- */
  function gyoTsukuru(oya, hai, kazuIre, tanka){
    oya.innerHTML = '';
    hai.forEach(function(m, i){
      var d = document.createElement('div'); d.className = 'menu-gyo';
      var na = document.createElement('div'); na.className = 'na';
      na.innerHTML = '<span></span><em></em>';
      na.querySelector('span').textContent = m.na;
      na.querySelector('em').textContent = en(tanka(m));
      var kz = document.createElement('div'); kz.className = 'kz';
      var mi = document.createElement('button'); mi.type = 'button'; mi.className = 'mns';
      mi.textContent = '−'; mi.setAttribute('aria-label', m.na + ' を1つ減らす');
      var n = document.createElement('input');
      n.type = 'text'; n.inputMode = 'numeric'; n.value = '0';
      n.setAttribute('aria-label', m.na + ' の数量');
      var pu = document.createElement('button'); pu.type = 'button'; pu.className = 'pls';
      pu.textContent = '＋'; pu.setAttribute('aria-label', m.na + ' を1つ増やす');
      function ireru(v){
        v = Math.max(0, Math.min(99, v || 0));
        kazuIre[i] = v; n.value = String(v);
        d.className = 'menu-gyo' + (v ? ' aru' : '');
        keisan(); kikuKirikae(); kakusu('e-menu');
      }
      mi.addEventListener('click', function(){ ireru((kazuIre[i] || 0) - 1); });
      pu.addEventListener('click', function(){ ireru((kazuIre[i] || 0) + 1); });
      n.addEventListener('input', function(){ ireru(parseInt(n.value.replace(/\D/g,'') || '0', 10)); });
      kz.appendChild(mi); kz.appendChild(n); kz.appendChild(pu);
      d.appendChild(na); d.appendChild(kz); oya.appendChild(d);
    });
  }

  function hyouKirikae(){
    var h = hyou(); if (!h) { return; }
    jotai.kazu = {}; jotai.optKazu = {}; $('cam').checked = false;
    $('cam-box').hidden = (h.kata !== 'honpo');
    gyoTsukuru($('menu'), h.menu, jotai.kazu, function(m){ return tankaDasu(m, 1); });
    gyoTsukuru($('opt'), h.opt, jotai.optKazu, function(o){ return o.kin; });
    $('hyou-chu').textContent = h.na + 'の料金表です。'
      + (h.kata === 'honpo'
         ? '本部の正規料金（税込）。2台以上のエアコンは1台あたり2,200円引き。本舗は繁忙期加算を付けません。'
         : '同時施工が2つ以上のときは同時施工価格になります。');
    $('ryokin-chu').textContent = (h.kata === 'honpo'
      ? 'セット価格（水まわり3点など）で受けたときは、ここに実際の金額を入れてください。'
      : 'あとからスプレッドシートで直せます。この場では、だいたいで構いません。');
    keisan(); kikuKirikae();
  }

  /* ---- 単価 ----
     ワンヒッター：箇所が2つ以上なら「同時施工」価格（data/prices.json のとおり）
     おそうじ本舗：壁掛けエアコンが合計2台以上なら「2台以上」価格（本部のまとめ割）
                   追い焚き配管は、浴室も一緒のときだけ同時施工価格 */
  function eakonKazu(){
    var h = hyou(), n = 0;
    if (!h) { return 0; }
    h.menu.forEach(function(m, i){
      if (h.matome.indexOf(m.na) !== -1) { n += (jotai.kazu[i] || 0); }
    });
    return n;
  }
  function kosuGokei(){
    var n = 0; for (var k in jotai.kazu) { n += jotai.kazu[k]; } return n;
  }
  function tankaDasu(m, hyouji){
    var h = hyou(); if (!h) { return m.tan; }
    var cam = (h.kata === 'honpo' && $('cam').checked && m.cam);
    if (h.kata === 'honpo') {
      var matome = (h.matome.indexOf(m.na) !== -1) && eakonKazu() >= 2;
      if (m.na.indexOf('追い焚き') !== -1) {
        var furo = false;
        h.menu.forEach(function(x, i){ if (x.na.indexOf('浴室') !== -1 && (jotai.kazu[i]||0) > 0) { furo = true; } });
        return furo ? m.dou : m.tan;
      }
      if (cam) { return matome ? m.camDou : m.cam; }
      return matome ? m.dou : m.tan;
    }
    return (hyouji ? false : kosuGokei() >= 2) ? m.dou : m.tan;
  }

  function keisan(){
    var h = hyou();
    if (!h) { $('g-sho').textContent = en(0); $('g-go').textContent = en(0); return; }
    var shurui = 0, ko = 0, sho = 0, fun = 0;
    h.menu.forEach(function(m, i){
      var n = jotai.kazu[i] || 0; if (!n) { return; }
      shurui += 1; ko += n; fun += m.fun * n;
    });
    h.menu.forEach(function(m, i){
      var n = jotai.kazu[i] || 0; if (!n) { return; }
      sho += tankaDasu(m, 0) * n;
    });
    h.opt.forEach(function(o, i){
      var n = jotai.optKazu[i] || 0; if (n) { sho += o.kin * n; }
    });
    if (shurui >= 2) { fun -= Math.min(60, (shurui - 1) * 30); }
    var tsuki = $('hi').value ? Number($('hi').value.slice(5,7)) : 0;
    var kasan = (sho && h.hanki && h.hanki['対象月'].indexOf(tsuki) !== -1) ? h.hanki['金額'] : 0;
    $('g-hanki-gyo').hidden = !kasan;
    $('g-hanki').textContent = en(kasan);
    $('g-sho').textContent = en(sho);
    $('g-go').textContent = en(sho + kasan);
    $('g-fun').textContent = fun ? (fun >= 60 ? Math.floor(fun/60) + '時間' + (fun%60 ? (fun%60)+'分' : '') : fun + '分') : '—';
    jotai.sho = sho; jotai.kasan = kasan; jotai.fun = fun || 60;
    // 表示している単価も、同時施工かどうかで入れ替える
    var gyo = $('menu').querySelectorAll('.menu-gyo');
    h.menu.forEach(function(m, i){
      if (gyo[i]) { gyo[i].querySelector('em').textContent = en(tankaDasu(m, 0)); }
    });
    owariIreru();
  }
  $('cam').addEventListener('change', keisan);

  /* ---- 終了時刻 ---- */
  function fun2ji(f){
    f = ((f % 1440) + 1440) % 1440;
    return ('0' + Math.floor(f/60)).slice(-2) + ':' + ('0' + (f%60)).slice(-2);
  }
  function ji2fun(s){
    var m = /^(\d{1,2}):(\d{2})$/.exec(String(s || '')); 
    return m ? Number(m[1]) * 60 + Number(m[2]) : null;
  }
  function owariIreru(){
    if (jotai.owariTe) { kasanariMiru(); return; }
    var k = ji2fun($('jikoku').value);
    if (k === null) { kasanariMiru(); return; }
    $('owari-jikoku').value = fun2ji(k + (jotai.fun || 60));
    kasanariMiru();
  }
  $('owari-jikoku').addEventListener('input', function(){ jotai.owariTe = true; kasanariMiru(); });
  $('owari-modosu').addEventListener('click', function(e){
    e.preventDefault(); jotai.owariTe = false; owariIreru();
  });
  $('jikoku').addEventListener('input', function(){ owariIreru(); });

  /* ---- 既存の予定（ダブルブッキング防止） ----
     描画のあとで読む。読めなくてもフォームは普通に使える。 */
  function yoteiMiru(){
    var naka = $('yotei-naka'), hi = $('hi').value;
    if (!hi) { naka.textContent = '施工日を入れると出ます'; return; }
    if (!YOTEI) { naka.textContent = '予定を読み込み中…'; return; }
    var sono = YOTEI['予定'].filter(function(y){ return y.hi === hi; });
    if (!sono.length) {
      naka.textContent = 'この日に入っている予定はありません（' + (YOTEI['取得'] || '') + ' 時点）';
      return;
    }
    var k = ji2fun($('jikoku').value), o = ji2fun($('owari-jikoku').value);
    var ul = document.createElement('ul');
    sono.forEach(function(y){
      var li = document.createElement('li');
      li.textContent = (y.kai ? y.kai + '–' + (y.owa || '') + '　' : '終日　') + y.na;
      if (kasanaruka(y, k, o)) { li.className = 'kasanaru'; }
      ul.appendChild(li);
    });
    naka.innerHTML = '';
    naka.appendChild(ul);
    var chu = document.createElement('div');
    chu.className = 'chu';
    chu.textContent = YOTEI['取得'] ? (YOTEI['取得'] + ' 時点のカレンダーです') : '';
    naka.appendChild(chu);
  }
  function kasanaruka(y, k, o){
    if (!y.kai || k === null || o === null) { return false; }
    var a = ji2fun(y.kai), b = ji2fun(y.owa) ;
    if (a === null) { return false; }
    if (b === null || b <= a) { b = a + 60; }
    return k < b && a < o;
  }
  function kasanariMiru(){
    yoteiMiru();
    var hi = $('hi').value, keikoku = $('kasanari');
    if (!hi || !YOTEI) { keikoku.classList.remove('deru'); return; }
    var k = ji2fun($('jikoku').value), o = ji2fun($('owari-jikoku').value);
    var butsu = YOTEI['予定'].filter(function(y){ return y.hi === hi && kasanaruka(y, k, o); });
    if (butsu.length) {
      keikoku.textContent = '⚠ この時間は「' + butsu.map(function(y){ return y.na; }).join('・')
        + '」と重なっています。時刻を確かめてください。';
      keikoku.classList.add('deru');
    } else {
      keikoku.classList.remove('deru');
    }
  }
  $('hi').addEventListener('change', function(){ keisan(); kasanariMiru(); });

  /* ---- ヒアリング ---- */
  var kikuIre = {};
  function kikuTsukuru(){
    var oya = $('kiku'); oya.innerHTML = '';
    HEARING.forEach(function(h, i){
      var l = document.createElement('label'); l.className = 'kiku'; l.dataset.i = String(i);
      var c = document.createElement('input'); c.type = 'checkbox';
      c.addEventListener('change', function(){ kikuIre[i] = c.checked; });
      var s = document.createElement('span'); s.textContent = h.na;
      l.appendChild(c); l.appendChild(s); oya.appendChild(l);
    });
  }
  kikuTsukuru();
  function kikuKirikae(){
    var h = hyou(), eakon = false, kaden = false;
    if (h) {
      h.menu.forEach(function(m, i){
        if (!(jotai.kazu[i] || 0)) { return; }
        if (m.eakon) { eakon = true; }
        if (m.kaden) { kaden = true; }
      });
    }
    Array.prototype.forEach.call($('kiku').querySelectorAll('.kiku'), function(l){
      var j = HEARING[Number(l.dataset.i)].jouken;
      l.hidden = (j === 'エアコン' && !eakon) || (j === '家電' && !kaden);
    });
  }
  kikuKirikae();
  function kikuMoji(){
    var a = [];
    Array.prototype.forEach.call($('kiku').querySelectorAll('.kiku'), function(l){
      if (l.hidden) { return; }
      var i = Number(l.dataset.i);
      a.push((kikuIre[i] ? '✓' : '未確認：') + HEARING[i].na);
    });
    return a.join('／');
  }

  /* ---- 検査 ---- */
  function dasu(id){ $(id).classList.add('deru'); }
  function kakusu(id){ var e = $(id); if (e) { e.classList.remove('deru'); } }
  ['name','hi'].forEach(function(id){
    $(id).addEventListener('input', function(){ kakusu('e-' + id); });
  });

  function menuMoji(){
    var h = hyou(), a = [];
    if (!h) { return ''; }
    h.menu.forEach(function(m, i){ var n = jotai.kazu[i] || 0; if (n) { a.push(m.na + (n > 1 ? ' ×' + n : '')); } });
    h.opt.forEach(function(o, i){ var n = jotai.optKazu[i] || 0; if (n) { a.push(o.na + (n > 1 ? ' ×' + n : '')); } });
    return a.join('／');
  }

  $('send').addEventListener('click', function(){
    if ($('hp').value) { return; }
    var ng = null;
    if (!jotai.shurui) { dasu('e-shurui'); ng = ng || 'shurui'; }
    if (!jotai.keiro)  { dasu('e-keiro');  ng = ng || 'keiro'; }
    if (!$('hi').value){ dasu('e-hi');     ng = ng || 'hi'; }
    if (!kosuGokei())  { dasu('e-menu');   ng = ng || 'menu'; }
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
      '終了時刻': $('owari-jikoku').value || '',
      '流入経路': jotai.keiro,
      '氏名': $('name').value.trim(),
      'TEL': $('tel').value.trim(),
      '住所': $('addr').value.trim(),
      '売上（税込）': String(jissai || mikomi),
      '見込み金額': String(mikomi),
      '実施メニュー': menuMoji(),
      '所要の目安（分）': String(jotai.fun),
      '法人名': houjinMoji(),
      'ヒアリング': kikuMoji(),
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
        $('owari-naka').textContent = atai['施工日付'] + ' ' + atai['開始時刻']
          + (atai['終了時刻'] ? '–' + atai['終了時刻'] : '') + '　'
          + atai['氏名'] + 'さま　' + en(atai['売上（税込）']);
        window.scrollTo(0,0);
      })
      .catch(function(){
        b.disabled = false; b.textContent = 'この内容で記録する';
        alert('記録できませんでした。電波の良いところでもう一度お試しください。\n何度も失敗するときは、マーケ部長に連絡してください。');
      });
  });

  $('tsugi').addEventListener('click', function(){ location.reload(); });

  /* 予定は最後に読む（初期表示を待たせない） */
  fetch('yotei.json', {cache:'no-store'})
    .then(function(r){ return r.json(); })
    .then(function(j){ YOTEI = j; kasanariMiru(); })
    .catch(function(){ $('yotei-naka').textContent = '予定を読み込めませんでした（入力は続けられます）'; });
})();
</script>
</body></html>
"""

if __name__ == "__main__":
    main()
