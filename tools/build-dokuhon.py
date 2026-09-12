#!/usr/bin/env python3
"""読本（節目チャネルのQRの先）v2 を lp/media/dokuhon/ に組み立てる。

v1 はオーナーから「AI臭い・冒頭で引き付けない・デザインが悪い・シチュエーションを想定していない」と
差し戻された（2026-09-11）。設計は docs/読本-設計メモ.md。**文章は tools/dokuhon_content.py** にあり、
ここは組版だけ。数字と引用は docs/読本-出典.md にある取得原文以外を使わない。

  akachan/index.html   赤ちゃん版
  pet/index.html       ペット版
  setti/index.html     施設の承諾フォーム
  unei.html            運営者情報

使い方:
  python3 tools/build-dokuhon.py
"""
import pathlib
import sys

from PIL import Image, ImageOps

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import media_common as C  # noqa: E402
import dokuhon_content as K  # noqa: E402

OUTDIR = C.ROOT / "lp" / "media" / "dokuhon"
PHOTOS_SRC = C.ROOT / "assets" / "photos"
BRAND = "読本"
BRAND_SUB = "家の中の見えない汚れ"
FORM_SETTI = "dokuhon-setti"

# 読本ページ専用のCSS。LPのトークンは使わず「白い紙」に固定する（設計メモ：紙の質感。ダークモードは捨てる）
BOOK_CSS = """
:root{--paper:#FBFAF7;--ink:#171A1C;--ink-2:#4A5054;--ink-3:#7C8388;--rule:#E3E0D9;--accent:#0E6E82;--accent-ink:#0A5262;}
*{box-sizing:border-box;}
html{background:var(--paper);}
body{margin:0;background:var(--paper);color:var(--ink);font-family:"Zen Kaku Gothic New","Hiragino Sans","Yu Gothic",system-ui,sans-serif;font-size:17px;line-height:2;-webkit-font-smoothing:antialiased;letter-spacing:.01em;}
a{color:var(--accent-ink);}
.serif{font-family:"Shippori Mincho B1","Hiragino Mincho ProN","Yu Mincho",serif;}
.col{max-width:560px;margin:0 auto;padding:0 22px;}
/* 冒頭 */
.opener{display:flex;flex-direction:column;padding:72px 22px 28px;max-width:560px;margin:0 auto;}
.opener .num{font-family:"Shippori Mincho B1",serif;font-weight:800;font-size:clamp(84px,26vw,132px);line-height:1;letter-spacing:-.02em;color:var(--ink);}
.opener .num small{font-size:.42em;letter-spacing:0;margin-left:.06em;}
.opener .line{font-family:"Shippori Mincho B1",serif;font-weight:700;font-size:clamp(22px,6vw,28px);line-height:1.65;margin-top:26px;text-wrap:balance;}
.opener .src{font-size:11.5px;color:var(--ink-3);line-height:1.6;margin-top:22px;}
.opener .src a{color:var(--ink-3);text-decoration:none;border-bottom:1px solid var(--rule);}
.opener .bigq{font-family:"Shippori Mincho B1",serif;font-weight:800;font-size:clamp(30px,8.6vw,42px);line-height:1.45;letter-spacing:-.01em;margin:0;text-wrap:balance;}
.opener .bigq + .src{margin-top:12px;}
.opener .down{margin-top:30px;font-size:12px;color:var(--ink-3);letter-spacing:.14em;}
/* 章 */
.ch{padding:56px 0 8px;}
.ch .no{font-family:"Shippori Mincho B1",serif;font-size:15px;color:var(--accent);border-top:1.5px solid var(--accent);display:inline-block;padding:8px 14px 0 0;}
.ch h2{font-family:"Shippori Mincho B1",serif;font-weight:700;font-size:clamp(24px,6.6vw,30px);line-height:1.5;margin:18px 0 24px;text-wrap:balance;}
p{margin:0 0 1.35em;}
p.lead{font-family:"Shippori Mincho B1",serif;font-size:19px;line-height:1.9;}
p.big{font-family:"Shippori Mincho B1",serif;font-weight:700;font-size:clamp(21px,5.8vw,26px);line-height:1.7;margin:28px 0;}
.kazu{margin:30px 0 24px;}
.kazu b{display:block;font-family:"Shippori Mincho B1",serif;font-weight:800;font-size:clamp(56px,17vw,84px);line-height:1;letter-spacing:-.02em;}
.kazu b small{font-size:.45em;}
.kazu span{display:block;font-size:14px;color:var(--ink-2);line-height:1.7;margin-top:8px;}
/* 写真：横幅いっぱい */
figure.ph{margin:26px -22px 30px;}
figure.ph img{display:block;width:100%;height:auto;}
figure.ph figcaption{padding:8px 22px 0;font-size:12px;color:var(--ink-3);line-height:1.7;}
figure.ph figcaption b{color:var(--ink-2);font-weight:500;}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:4px;margin:26px -22px 8px;}
.pair img{display:block;width:100%;aspect-ratio:3/4;object-fit:cover;}
.pair + .cap{font-size:12px;color:var(--ink-3);line-height:1.7;margin:0 0 30px;}
/* 引用 */
.q{margin:26px 0;padding:0 0 0 18px;border-left:2px solid var(--ink);font-size:15.5px;line-height:1.95;color:var(--ink);}
.q cite{display:block;font-style:normal;font-size:11.5px;color:var(--ink-3);margin-top:8px;line-height:1.6;}
.q cite a{color:var(--ink-3);text-decoration:none;border-bottom:1px solid var(--rule);}
p.fact{font-size:15.5px;line-height:1.95;}
p.fact .fsrc{display:block;font-size:11.5px;color:var(--ink-3);margin-top:6px;}
p.fact .fsrc a{color:var(--ink-3);text-decoration:none;border-bottom:1px solid var(--rule);}
/* 身分 */
.reveal{margin:40px 0;padding:34px 0;border-top:1px solid var(--ink);border-bottom:1px solid var(--ink);}
.reveal p{font-family:"Shippori Mincho B1",serif;font-size:clamp(20px,5.6vw,25px);line-height:1.75;margin:0;}
.reveal .who{font-family:"Zen Kaku Gothic New",sans-serif;font-size:13px;color:var(--ink-2);margin-top:16px;line-height:1.7;}
/* できる・できない */
.dk{margin:0 0 18px;padding:18px 0 0;border-top:1px solid var(--rule);}
.dk h3{display:block;font-family:"Zen Kaku Gothic New",sans-serif;font-weight:700;font-size:15.5px;line-height:1.6;margin:0 0 6px;}
.dk.ng h3{color:#8E2F1A;}
.dk p{font-size:15.5px;line-height:1.9;margin:0;}
/* 終わり */
.end{font-family:"Shippori Mincho B1",serif;font-size:19px;line-height:2;margin:48px 0 0;}
/* 商品 */
.offer{margin:56px -22px 0;padding:44px 22px 48px;background:#F1EEE7;}
.offer .no{font-family:"Shippori Mincho B1",serif;font-size:13px;letter-spacing:.3em;color:var(--accent);}
.offer h2{font-family:"Shippori Mincho B1",serif;font-weight:700;font-size:clamp(22px,6vw,27px);line-height:1.5;margin:8px 0 6px;}
.offer .sub{font-size:14px;color:var(--ink-2);margin:0 0 22px;}
.offer .ln{display:flex;justify-content:space-between;gap:12px;font-size:15px;padding:9px 0;border-bottom:1px solid #DAD5CB;}
.offer .ln .v{font-variant-numeric:tabular-nums;white-space:nowrap;}
.offer .ln.sum{font-size:19px;font-weight:700;border-bottom:2px solid var(--ink);}
.offer .fine{font-size:12.5px;color:var(--ink-2);line-height:1.8;margin:12px 0 22px;}
.btn{display:block;text-align:center;text-decoration:none;font-weight:700;font-size:17px;padding:17px 18px;border-radius:6px;background:var(--ink);color:#fff;}
.btn.sec{background:transparent;color:var(--ink);border:1.5px solid var(--ink);margin-top:10px;}
.proof{font-size:12.5px;color:var(--ink-2);line-height:1.8;margin:18px 0 0;}
.tenken{margin-top:36px;padding-top:26px;border-top:1px solid #DAD5CB;}
.tenken b{display:block;font-family:"Shippori Mincho B1",serif;font-size:18px;margin-bottom:6px;}
.tenken p{font-size:14.5px;line-height:1.9;margin:0 0 14px;}
/* 出典・奥付 */
.src{font-size:11.5px;color:var(--ink-3);line-height:1.8;padding:36px 0 56px;}
.src ol{padding-left:1.3em;margin:8px 0 0;}
.src a{color:var(--ink-3);word-break:break-all;}
.src .unei{margin-top:18px;}
@media (min-width:700px){body{font-size:18px;} figure.ph{margin-left:0;margin-right:0;} .pair{margin-left:0;margin-right:0;} .offer{margin-left:0;margin-right:0;border-radius:4px;}}
"""


def head_book(title: str, desc: str) -> str:
    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{C.esc(title)}</title>
<meta name="description" content="{C.esc(desc)}">
<meta name="robots" content="noindex,nofollow">
<meta name="theme-color" content="#FBFAF7">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Shippori+Mincho+B1:wght@700;800&family=Zen+Kaku+Gothic+New:wght@400;500;700&display=swap">
<style>{BOOK_CSS}</style>
</head>
<body>
"""


def render_block(b: dict, ctx: dict) -> str:
    t = b["t"]
    e = C.esc
    if t == "opener":
        return (f'<section class="opener"><div class="num">{b["num"]}</div>'
                f'<p class="line">{b["line"]}</p><div class="down">↓ 続きは3分ほど</div><p class="src">{b["src"]}</p></section><div class="col">')
    if t == "opener_q":
        name, url = K.SRC[b["src"]]
        return (f'<section class="opener"><p class="bigq">「{e(b["q"])}」</p><p class="src">出典　<a href="{url}" target="_blank" rel="noopener">{e(name)}</a></p>'
                f'<p class="line">{b["line"]}</p><div class="down">↓ 続きは3分ほど</div></section><div class="col">')
    if t == "ch":
        return f'<div class="ch"><span class="no">{e(b["no"])}</span><h2>{b["h"]}</h2></div>'
    if t == "p":
        cls = b.get("cls", "")
        return f'<p class="{cls}">{b["x"]}</p>'
    if t == "fact":
        name, url = K.SRC[b["src"]]
        return f'<p class="fact">{b["x"]}<span class="fsrc">出典　<a href="{url}" target="_blank" rel="noopener">{e(name)}</a></span></p>'
    if t == "kazu":
        return f'<div class="kazu"><b>{b["num"]}</b><span>{b["x"]}</span></div>'
    if t == "photo":
        fn, cap = K.PHOTOS[b["id"]]
        return f'<figure class="ph"><img src="../photos/{fn}" alt="{e(cap)}" loading="lazy"><figcaption><b>{e(b.get("lab", ""))}</b>{"　" if b.get("lab") else ""}{e(cap)}</figcaption></figure>'
    if t == "pair":
        a, bb = K.PHOTOS[b["ids"][0]], K.PHOTOS[b["ids"][1]]
        return (f'<div class="pair"><img src="../photos/{a[0]}" alt="{e(a[1])}" loading="lazy"><img src="../photos/{bb[0]}" alt="{e(bb[1])}" loading="lazy"></div>'
                f'<p class="cap">{e(b["cap"])}</p>')
    if t == "q":
        name, url = K.SRC[b["src"]]
        return f'<blockquote class="q">「{e(b["x"])}」<cite>出典　<a href="{url}" target="_blank" rel="noopener">{e(name)}</a></cite></blockquote>'
    if t == "reveal":
        return f'<div class="reveal"><p class="serif">{b["x"]}</p><p class="who">{b["who"]}</p></div>'
    if t == "dk":
        return f'<div class="dk {b.get("cls", "")}"><h3>{e(b["h"])}</h3><p>{b["x"]}</p></div>'
    if t == "end":
        return f'<p class="end">{b["x"]}</p>'
    if t == "offer":
        return offer_html(b, ctx)
    raise SystemExit(f"未知のブロック: {t}")


def offer_html(b: dict, ctx: dict) -> str:
    P = ctx["prices"]
    m = P["menus"]
    rows = ""
    total = 0
    for name, key, kind in b["items"]:
        v = m[key]["単体"] if kind == "単体" else m[key]["同時施工"]
        total += v
        rows += f'<div class="ln"><span>{C.esc(name)}</span><span class="v">{C.yen(v)}</span></div>'
    rows += f'<div class="ln sum"><span>合計（税込）</span><span class="v">{C.yen(total)}</span></div>'
    tenken = ""
    if b.get("tenken_bridge"):
        tenken = (f'<div class="tenken"><b>まだ決めない、という方へ</b><p>{b["tenken_bridge"]}</p>'
                  f'<a class="btn sec" id="btn-tenken" href="{C.TENKEN_URL}/">{C.esc(b["tenken_cta"])}</a></div>')
    auto = m["エアコンクリーニング（お掃除機能付き）"]["単体"]
    busy = P["raw"]["繁忙期加算"]["金額"]
    return f"""
  <section class="offer">
    <span class="no">{C.esc(b["no"])}</span>
    <h2>{b["h"]}</h2>
    <p class="sub">{b["sub"]}</p>
    {rows}
    <p class="fine">出張費・駐車場代・追加作業費はありません。お掃除機能付きのエアコンは {C.yen(auto)}。5〜7月と12月は繁忙期の加算 {C.yen(busy)}。作業のあと、洗った水をそのままお見せします。</p>
    <a class="btn" id="btn-yoyaku" href="{C.BOOKING}">日程を見て予約する</a>
    <p class="proof">ご利用後のアンケートで「他の人にすすめたい」 {K.SURVEY}。Googleのクチコミ ★5.0（{K.REVIEW_COUNT}件・{K.REVIEW_ASOF}）。東京都・千葉県・神奈川県。</p>
    {tenken}
  </section>
"""


def sources_html(keys) -> str:
    items = "".join(f'<li>{C.esc(K.SRC[k][0])}<br><a href="{K.SRC[k][1]}" target="_blank" rel="noopener">{K.SRC[k][1]}</a></li>' for k in keys)
    return (f'<div class="src"><b>出典</b><ol>{items}</ol>'
            f'<p>引用は原文のままです。写真はすべて当社が施工した現場で撮ったもので、合成も加工もしていません。お宅が分かる写真は使っていません。</p>'
            f'<p class="unei">この読み物を書いたのは {C.UNEI}（{C.UNEI_ADDR}・{C.UNEI_TEL}）です。カードを置いてくださった施設には、ご利用があった場合に紹介料をお支払いすることがあります（医療法人など、受け取れない施設を除く）。お客様の料金には上乗せしません。<br>'
            f'<a href="../unei.html">運営者情報</a>　<a href="{C.PRIVACY}" target="_blank" rel="noopener">個人情報の取扱い</a></p></div>')


def build_book(kind: str, P: dict) -> str:
    art = K.ARTICLES[kind]
    ctx = {"prices": P, "kind": kind}
    body = "".join(render_block(b, ctx) for b in art["blocks"])
    body += sources_html(art["sources"]) + "</div>"
    js = f"""
<script>
(function(){{
  var src = (new URLSearchParams(location.search)).get('src') || '{kind}';
  var y = document.getElementById('btn-yoyaku'), t = document.getElementById('btn-tenken');
  if (y) y.href = '{C.BOOKING}?src=' + encodeURIComponent('dokuhon-' + src);
  if (t) t.href = '{C.TENKEN_URL}/?src=' + encodeURIComponent('dokuhon-' + src);
}})();
</script>
</body></html>"""
    return head_book(art["title"], art["desc"]) + body + js


# ---------------- 施設の承諾フォームと運営者情報は v1 のまま（LPトークンのデザイン）
def build_setti() -> str:
    body = f"""
  <div class="intro">
    <span class="eyebrow">設置のご連絡（1分）</span>
    <h1>カードを置いていただける施設の方へ</h1>
    <p class="lead" style="font-size:14.5px">ありがとうございます。設置場所だけお知らせください。折り返し、貴施設専用のQRカード（PDF）と、毎週の閲覧数のお知らせをお送りします。</p>
  </div>
  <form class="survey-form" id="f" onsubmit="return false;" novalidate>
    <div class="q">
      <div class="field"><label for="s-name">施設名</label><input id="s-name" type="text" autocomplete="organization" placeholder="例：◯◯レディースクリニック／◯◯ペットショップ"></div>
      <div class="field"><label for="s-houjin">運営法人の正式名称（分かれば）</label><input id="s-houjin" type="text" placeholder="例：医療法人社団◯◯会／株式会社◯◯／個人"><p class="hint" id="s-houjin-hint"></p></div>
      <div class="field"><label for="s-kind">施設の種別</label><select id="s-kind"><option value="">選んでください</option>
        <option>産婦人科・産院</option><option>小児科</option><option>子育て支援・保育</option><option>ベビー用品店</option>
        <option>ペットショップ</option><option>動物病院</option><option>トリミング</option><option>その他</option></select></div>
      <div class="field"><label for="s-tantou">ご担当者名</label><input id="s-tantou" type="text" autocomplete="name"></div>
      <div class="field"><label for="s-mail">メールアドレス（週次のお知らせ先）</label><input id="s-mail" type="email" inputmode="email" autocomplete="email"></div>
      <div class="field"><label for="s-addr">施設の住所</label><input id="s-addr" type="text" autocomplete="street-address"></div>
      <div class="field"><label for="s-place">カードを置く場所</label><select id="s-place"><option value="">選んでください</option><option>受付・レジ横</option><option>待合</option><option>掲示板</option><option>その他</option></select></div>
      <div class="field"><label>カードの用意</label>
        <label class="agree"><input type="radio" name="print" value="PDFを自分で印刷"><span>PDFを送ってもらい、施設で印刷する（A6・普通紙で構いません）</span></label>
        <label class="agree"><input type="radio" name="print" value="印刷して郵送"><span>印刷したカードを郵送してほしい（1〜2週間）</span></label></div>
      <label class="agree"><input type="checkbox" id="s-agree"><span>カードはいつでも撤去できること、週次のお知らせはメール1通で止められることを確認しました。</span></label>
      <input type="text" id="s-hp" name="bot-field" tabindex="-1" autocomplete="off" class="hp" aria-hidden="true">
      <p class="err" id="se"></p>
      <button type="button" class="btn lg" id="send">この内容で送る</button>
    </div>
    <section class="q done" id="done" hidden>
      <div class="head"><h2>ありがとうございます。</h2></div>
      <p class="why" style="font-size:13.5px">貴施設のID：<b id="d-id" class="num"></b><br>このIDの入ったQRカード（PDF）を、いただいたメールアドレスへ1営業日以内にお送りします。下は、貴施設専用の読本のQRです（このままスクリーンショットで使っていただいても構いません）。</p>
      <div class="qr"><div id="qrcode"></div><p class="note" id="d-url" style="word-break:break-all;text-align:center"></p></div>
      <p class="note" id="d-houshuu" style="margin-top:10px"></p>
    </section>
  </form>
<script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
<script>
(function(){{
  var $ = function(id){{ return document.getElementById(id); }};
  var Q = new URLSearchParams(location.search);
  var NASHI = ['医療法人','社会福祉法人','学校法人','特定非営利','区立','市立','都立','県立','国立'];
  function houshuuKata(h){{ for (var i=0;i<NASHI.length;i++) if (h.indexOf(NASHI[i]) >= 0) return '報酬なし型'; return '12%型'; }}
  $('s-houjin').addEventListener('input', function(){{
    $('s-houjin-hint').textContent = (houshuuKata(this.value) === '報酬なし型') ? '医療法人・社会福祉法人・学校法人・自治体などの施設には紹介料をお支払いしません（情報提供のみ）。' : '';
  }});
  function makeId(){{ var s = ''; var a = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'; for (var i=0;i<6;i++) s += a[Math.floor(Math.random()*a.length)]; return 'F' + s; }}
  var sending = false;
  $('send').addEventListener('click', function(){{
    if (sending || $('s-hp').value) return;
    var pr = document.querySelector('input[name="print"]:checked');
    if (!$('s-name').value.trim()) return $('se').textContent = '施設名を入れてください。';
    if (!$('s-kind').value) return $('se').textContent = '施設の種別を選んでください。';
    if (!$('s-mail').value.trim()) return $('se').textContent = 'メールアドレスを入れてください（QRカードの送付先です）。';
    if (!$('s-place').value) return $('se').textContent = 'カードを置く場所を選んでください。';
    if (!pr) return $('se').textContent = 'カードの用意を選んでください。';
    if (!$('s-agree').checked) return $('se').textContent = '確認にチェックをお願いします。';
    var id = Q.get('f') || makeId();
    var kind = $('s-kind').value, hen = (/産|小児|子育て|保育|ベビー/.test(kind)) ? 'akachan' : (/ペット|動物|トリミング/.test(kind)) ? 'pet' : 'akachan';
    var url = '{C.DOKUHON_URL}/' + hen + '/?src=' + id;
    var atai = {{ '施設ID': id, '施設名': $('s-name').value.trim(), '法人名': $('s-houjin').value.trim(), '報酬型': houshuuKata($('s-houjin').value), '種別': kind, '読本': hen,
      '担当者': $('s-tantou').value.trim(), 'メール': $('s-mail').value.trim(), '住所': $('s-addr').value.trim(), '設置場所': $('s-place').value, 'カード': pr.value, '読本URL': url, '送信時刻': new Date().toISOString() }};
    var fd = new FormData(); fd.append('form-name', '{FORM_SETTI}'); Object.keys(atai).forEach(function(k){{ fd.append(k, atai[k]); }});
    sending = true; $('send').disabled = true; $('send').textContent = '送信しています…';
    fetch(location.pathname, {{method:'POST', body:fd}}).then(function(r){{ if (!r.ok) throw new Error('送信できませんでした（'+r.status+'）');
      $('d-id').textContent = id; $('d-url').textContent = url; new QRCode($('qrcode'), {{text:url, width:220, height:220}});
      $('d-houshuu').textContent = (atai['報酬型'] === '12%型') ? '貴施設のカードからご利用があった場合、ご利用額の12%を月末締め・翌月末にお支払いします（支払通知を自動でお送りします）。' : '貴施設には紹介料をお支払いしない形（情報提供のみ）でお願いしています。';
      $('f').querySelector('.q').hidden = true; document.querySelector('.intro').hidden = true; $('done').hidden = false; window.scrollTo(0,0);
    }}).catch(function(e){{ sending = false; $('send').disabled = false; $('send').textContent = 'この内容で送る'; $('se').textContent = String(e.message||e); }});
  }});
}})();
</script>
<form name="{FORM_SETTI}" data-netlify="true" netlify-honeypot="bot-field" hidden>
  <input type="hidden" name="form-name" value="{FORM_SETTI}"><input type="text" name="bot-field">
  <input type="text" name="施設ID"><input type="text" name="施設名"><input type="text" name="法人名"><input type="text" name="報酬型"><input type="text" name="種別"><input type="text" name="読本">
  <input type="text" name="担当者"><input type="text" name="メール"><input type="text" name="住所"><input type="text" name="設置場所"><input type="text" name="カード"><input type="text" name="読本URL"><input type="text" name="送信時刻">
</form>
"""
    return C.head("カード設置のご連絡｜ワンヒッター 読本", "施設の方の設置連絡フォーム", BRAND, BRAND_SUB, "", home="../", unei_href="../unei.html") + body + C.foot(BRAND, "", unei_href="../unei.html")


def build_top() -> str:
    body = """
  <div class="intro"><span class="eyebrow">読本</span><h1>家の中の見えない汚れ</h1></div>
  <div class="q" style="display:flex;flex-direction:column;gap:10px">
    <a class="btn lg" href="./akachan/">赤ちゃんが来る前に</a>
    <a class="btn lg" href="./pet/">この子が来る前に</a>
    <a class="btn ghost" href="./setti/">施設の方：カード設置のご連絡</a>
  </div>
"""
    return C.head("読本｜ワンヒッター", "家の中の見えない汚れ", BRAND, BRAND_SUB) + body + C.foot(BRAND, "")


def build_unei() -> str:
    rows = C.UNEI_ROWS_COMMON + [
        ("この読み物について", "赤ちゃん・ペットを迎えるご家庭向けに、公的機関・メーカーの公表資料の引用と、当社が施工した現場の写真だけで書いています。健康への影響は断定していません。末尾に当社のクリーニングと無料点検のご案内があります。"),
        ("設置施設への紹介料", "カードを置いてくださった施設のうち、株式会社・個人事業などの施設には、ご利用額の12%を紹介料としてお支払いすることがあります。医療法人・社会福祉法人・学校法人・自治体の施設にはお支払いしません。お客様の料金に上乗せはありません。"),
    ]
    return C.unei_page(BRAND, BRAND_SUB, rows, "読本に戻る")


def copy_photos():
    dst = OUTDIR / "photos"
    dst.mkdir(parents=True, exist_ok=True)
    for fn, _ in K.PHOTOS.values():
        src = PHOTOS_SRC / fn
        if not src.exists():
            sys.exit(f"写真がありません: {src}")
        im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
        im.thumbnail((1400, 1400))
        im.save(dst / fn, "JPEG", quality=84, optimize=True, progressive=True)


def main():
    P = C.prices()
    copy_photos()
    for kind in K.ARTICLES:
        d = OUTDIR / kind
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(build_book(kind, P), encoding="utf-8")
    (OUTDIR / "setti").mkdir(exist_ok=True)
    (OUTDIR / "setti" / "index.html").write_text(build_setti(), encoding="utf-8")
    (OUTDIR / "index.html").write_text(build_top(), encoding="utf-8")
    (OUTDIR / "unei.html").write_text(build_unei(), encoding="utf-8")
    print("書き出しました:", OUTDIR)


if __name__ == "__main__":
    main()
