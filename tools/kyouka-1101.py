#!/usr/bin/env python3
"""LP 強化の下書き（docs/LP-強化調査-2026-11-01.md の 2. と 4. をすべて当てはめる・オーナー指示 11/1）。

    python3 tools/kyouka-1101.py                         # deploy/machi/kyouka/<名前>/ に下書きを作る（配信しない）
    python3 tools/kyouka-1101.py --yokushitsu-ag bath,B_浴室,123456789   # 浴室の広告グループの ?ag= の値（カンマ区切り）
    python3 tools/kyouka-1101.py --edogawa-cid 23456789  # 江戸川区の広告キャンペーンの ?cid= の値（カンマ区切り）
    python3 tools/kyouka-1101.py --check                 # 書き出した下書きを点検だけする

元は今の配信物（deploy/netlify/<名前>/index.html＝本番と同じ）。deploy/netlify は書き換えない。
置き換えはすべて「置き換え前の文字列が想定どおりの数だけあるか」を確かめ、違えば止まる。
C と E には同じ変更を入れる。/aircon/ は直した C から tools/furiwake-aircon.py の make() で作る（道具は変えない）。

## 入れるもの（調査 2. の項目との対応）

- 2-5・弱点3（広告・季節との一致）：1画面目の見出しを作業月（日本時間）で切り替える。11〜12月＝暖房の臭い／年内、
  1〜4月＝冷房の前、5〜7月＝今の冷房の見出し、8〜10月＝夏のあと。JS が動かないときは季節によらない既定の見出し。
  /kabi/ の「9月の長雨で」をやめ、「この秋」の欄は 12/1 0:00 に隠す（Date.UTC(2026,10,30,15)）。
  浴室の広告グループ（?ag=）で /mizumawari/・-b の1画面目（見出し・説明・写真）を浴室に替える。URL は変えない。
  地域：?cid= が江戸川区のキャンペーン、または ?area=edogawa のときだけ「江戸川区北葛西の事務所から伺います」。
- 2-2・2-3・弱点2（相場より高い理由・信頼の材料を迷うところへ）：価格のすぐ下に 60分・分解・追加請求なしの1行。
  1画面目の「選ばれている理由」の3つ目を損害賠償保険に。見積りの予約ボタンと最後の予約ボタンの横に
  「自社の職人・損害賠償保険・追加請求なし・お支払いは作業のあと」。C・E の1画面目の金額を 6つ→2つ（10,780・9,702）。
- 2-3・弱点4（声）：1画面目の直下の声は今のまま。最後の予約ボタンの直前に、今LPに載っている声を原文のまま移す。
- 2-2・弱点1（誰が来るか）：1画面目の直下に「伺うのは、自社の職人です」。担当の写真は「写真が入る枠」（顔は勝手に使わない）。
  作業中の写真は、公開済みの blog-photos/IMG_8014.jpg（人は写っていない）を縮めて使う。
- 2-3・2-4・弱点5（申込の道）：主役は「空いている日を見て予約する」に文言をそろえる。電話は副、LINE は「相談」。
  LP 内フォームは「日にちが決まっていない・相談したい方」の折りたたみ（details）に格下げ。name・hidden 欄・計測はそのまま。
- 2-1・その他（重複を減らす）：帯の金額を本文の1行に寄せる。お掃除機能付き・繁忙期の行は「よくある頼み方」へ。
  「よくある頼み方」を1画面目の直後へ。同じ文の二重掲載を消す。
- 2-4（速さ）：1画面目の画像に fetchpriority・decoding、背景画像は 1200px に縮める。JPEG は画質を保って詰め直す（下書きの img/ に）。
- 2-5（AI Max）：title・description を季節によらない、はっきりした文に。古い季節・古い特典の文を残さない。
- 2-6（法規）：「最短即日」は残し、「当日のご依頼はお電話で」を添える（オーナー 11/1：電話で依頼されたときは即日対応している。予約ページの最短は翌日）。
  レンジフードの組写真（hood-before／after）は別物と確認済み（docs/photo-inventory.md 2026-09-06）なので、
  「同じ箇所の施工前後」としての掲載をやめる。「一切」を外す（決まりの「一切かからない」と同じ扱い）。
"""
import argparse
import importlib.util
import json
import pathlib
import re
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "deploy" / "netlify"
OUT = ROOT / "deploy" / "machi" / "kyouka"
MARK = 'data-oh="kyouka"'
NAMES = ["aircon-c", "aircon-e", "kabi", "mizumawari", "mizumawari-b", "nenmatsu", "nenmatsu-b"]
KIEru = "Date.UTC(2026, 10, 30, 15, 0, 0)"   # 12月1日 0:00（日本時間）。既存の帯と同じ書き方


def kaeru(s, old, new, count=1, name=""):
    n = s.count(old)
    if n != count:
        sys.exit(f"[{name}] 想定と違う：{old[:80]!r} が {n} か所（{count} か所のはず）。元の配信物が変わった可能性。止めます")
    return s.replace(old, new)


def kaeru_re(s, pat, new, count=1, name="", flags=re.S):
    m = re.findall(pat, s, flags)
    if len(m) != count:
        sys.exit(f"[{name}] 想定と違う：/{pat[:80]}/ が {len(m)} か所（{count} か所のはず）。止めます")
    return re.sub(pat, new, s, flags=flags)


def nuku_re(s, pat, name=""):
    """1か所だけあるはずの塊を抜き出して、(抜いた残り, 塊) を返す"""
    m = list(re.finditer(pat, s, re.S))
    if len(m) != 1:
        sys.exit(f"[{name}] 想定と違う：/{pat[:80]}/ が {len(m)} か所（1 か所のはず）。止めます")
    return s[:m[0].start()] + s[m[0].end():], m[0].group(0)


# ---------------------------------------------------------------------------
# 共通の見た目
# ---------------------------------------------------------------------------
CSS = """<style data-oh="kyouka">
/* LP強化の下書き（tools/kyouka-1101.py） */
.naze{margin:0;padding:6px 10px;background:var(--surface,#fff);border-left:3px solid var(--aqua,#0C6B7F);
  font-size:13px;line-height:1.6;color:var(--text-2,#3C5262);}
.hero .ba-hero img{aspect-ratio:16/10;}
.naze b{color:var(--text,#13232E);}
.trust .v.hoken,.trust .t.hoken{font-family:"Noto Sans JP",sans-serif;font-weight:800;font-size:19px;line-height:1.35;}
.peak-now{flex-basis:100%;font-size:12.5px;font-weight:700;color:var(--text-2,#3C5262);}
.peak-now[hidden]{display:none;}
.kisetsu-ue{font-size:13.5px;font-weight:700;color:var(--text-2,#3C5262);letter-spacing:.04em;margin:0 0 -6px;}
.kisetsu-ue[hidden]{display:none;}
.hero-tel{text-align:center;font-size:13.5px;margin:0;}
.hero-tel a{color:var(--text,#13232E);font-weight:700;text-decoration:none;border-bottom:1px solid var(--rule-2,#B4C5D0);}
.line-soudan{display:block;text-align:center;font-size:13.5px;font-weight:700;color:#05813A;text-decoration:underline;text-underline-offset:3px;}
.tantou{padding:24px 0;background:var(--surface,#fff);border-bottom:1px solid var(--rule,#D7E1E7);}
.tantou-in{display:flex;gap:14px;align-items:center;}
.tantou-kao{flex:0 0 96px;width:96px;height:96px;margin:0;border-radius:12px;overflow:hidden;}
.kyouka-waku{border:2px dashed #C0300C;background:#FFF6F2;color:#8F2408;font-size:10px;font-weight:700;line-height:1.4;
  display:flex;align-items:center;justify-content:center;text-align:center;padding:6px;}
.tantou-h{font-family:"Shippori Mincho B1","Yu Mincho",serif;font-weight:800;font-size:18px;line-height:1.5;color:var(--ink,#0D3B5C);margin:0 0 4px;}
.tantou-txt p.tantou-p{font-size:14.5px;line-height:1.8;color:var(--text-2,#3C5262);margin:0;}
.tantou-sagyou{margin:14px 0 0;}
.tantou-sagyou img{display:block;width:100%;height:auto;aspect-ratio:4/3;object-fit:cover;border-radius:8px;}
.tantou-sagyou figcaption{font-size:12px;color:var(--steel,#536A78);line-height:1.7;margin-top:4px;}
.anshin{list-style:none;margin:6px 0 0;padding:0;display:flex;flex-wrap:wrap;gap:2px 12px;justify-content:center;
  font-size:12.5px;font-weight:700;line-height:1.7;color:var(--text-2,#3C5262);}
.anshin li::before{content:"✓ ";color:var(--ok,#1B6B4F);}
.koe-mae{margin:0 0 18px;padding:16px 18px;background:var(--surface,#fff);border-left:3px solid var(--aqua,#0C6B7F);}
.koe-mae q{display:block;font-family:"Shippori Mincho B1","Yu Mincho",serif;font-weight:600;font-size:16px;line-height:2;quotes:"「" "」";color:var(--text,#13232E);}
.koe-mae figcaption{font-size:12px;color:var(--steel,#536A78);margin-top:6px;line-height:1.7;}
.cal-first{margin:0 0 22px;padding:16px 18px;background:var(--surface,#fff);border:1px solid var(--rule,#D7E1E7);border-radius:12px;display:grid;gap:12px;}
.cal-first p{margin:0;font-size:14px;line-height:1.8;color:var(--text-2,#3C5262);}
.cal-first p b{display:block;font-size:15px;color:var(--ink,#0D3B5C);}
.cal-first p.alt{font-size:13px;text-align:center;}
.cal-first p.alt a{color:var(--ink,#0D3B5C);font-weight:700;white-space:nowrap;}
details.soudan{border:1px solid var(--rule-2,#B4C5D0);border-radius:12px;background:var(--surface,#fff);padding:0 16px;margin:6px 0 0;}
details.soudan > summary{display:flex;flex-direction:column;gap:2px;padding:14px 0;font-size:15px;font-weight:700;color:var(--ink,#0D3B5C);
  cursor:pointer;list-style:none;}
details.soudan > summary::-webkit-details-marker{display:none;}
details.soudan > summary::before{content:"＋ 開く";font-family:inherit;font-size:11px;color:var(--steel,#536A78);order:2;}
details.soudan[open] > summary::before{content:"－ 閉じる";}
details.soudan > summary small{font-size:12.5px;font-weight:500;color:var(--text-2,#3C5262);}
details.soudan p{padding:0;}
details.soudan .form{margin:0 -16px;border-left:0;border-right:0;border-bottom:0;}
details.soudan .form-lead{font-size:14px;margin:0 0 14px;}
.soudan-link{display:block;text-align:center;font-size:13.5px;font-weight:700;color:var(--ink,#0D3B5C);text-decoration:underline;text-underline-offset:3px;padding:6px 0;}
</style>
"""

ANSHIN = ('<ul class="anshin" aria-label="安心の材料"><li>自社の職人が伺います</li><li>損害賠償保険に加入</li>'
          '<li>お見積り以上の追加請求なし</li><li>お支払いは作業のあと</li></ul>')

SOUDAN_LINK = '<a class="soudan-link" href="#form">日にちが決まっていない方・相談したい方は、フォームから</a>'


def tantou(img_src):
    return f"""<section class="tantou" id="tantou">
  <div class="wrap">
    <div class="tantou-in">
      <figure class="tantou-kao kyouka-waku" aria-label="下書き：担当の写真が入る枠">【下書き】担当（渡辺）の写真が入る枠<br>顔の掲載はオーナー確認のあと</figure>
      <div class="tantou-txt">
        <p class="tantou-h">伺うのは、自社の職人です</p>
        <p class="tantou-p">ご予約の受付から当日の作業まで、担当の渡辺が行います。下請けには出しません。</p>
      </div>
    </div>
    <figure class="tantou-sagyou"><img src="{img_src}" alt="作業中のエアコン。床と壁を養生し、カバーを外して洗っているところ" width="800" height="600" loading="lazy" decoding="async"><figcaption>作業中のエアコン（養生して、カバーとルーバーを外したところ）</figcaption></figure>
  </div>
</section>
"""


def hero_script(conf):
    """1画面目の出し分け。インラインで1回（ちらつかないように）、ページの最後でもう1回（広告向けの差し替えの後に）"""
    return """<script>
/* LP強化（tools/kyouka-1101.py）。1画面目を、作業の月（日本時間）・広告グループ（?ag=）・地域（?cid= / ?area=）に合わせる。
   JS が動かないときは HTML の既定の見出しのまま。値は表示に使うだけで、どこにも送らない */
window.ohKyouka = function () {
  var C = CONF_;
  var m = 0; try { m = new Date(Date.now() + 9 * 3600000).getUTCMonth() + 1; } catch (e) {}
  var q = null; try { q = new URLSearchParams(location.search); } catch (e) {}
  var ag = q ? String(q.get('ag') || '').toLowerCase() : '';
  var k = C.tsuki ? C.tsuki[String(m)] : '';
  var v = null;
  if (C.bath && ag && C.bathKeys.indexOf(ag) !== -1) { v = C.bath; k = 'bath'; }
  else if (k && C.v && C.v[k]) { v = C.v[k]; }
  function put(id, html) {
    var el = document.getElementById(id); if (!el || html == null) return;
    el.innerHTML = html; el.hidden = !html;
  }
  if (v) {
    for (var id in v) { if (id !== 'img' && Object.prototype.hasOwnProperty.call(v, id)) put(id, v[id]); }
    (v.img || []).forEach(function (x) {
      var el = document.getElementById(x[0]); if (!el) return;
      if (el.getAttribute('src') !== x[1]) el.setAttribute('src', x[1]);
      el.setAttribute('alt', x[2]);
    });
  }
  (C.kakusu || []).forEach(function (id) {
    var el = document.getElementById(id);
    if (el && Date.now() >= Date.UTC(2026, 10, 30, 15, 0, 0)) el.hidden = true;   /* 12月1日 0:00（日本時間）を過ぎたら出さない */
  });
  var cid = q ? String(q.get('cid') || '') : '', area = q ? String(q.get('area') || '').toLowerCase() : '';
  if (C.edogawa && ((cid && C.edogawaCids.indexOf(cid) !== -1) || area === 'edogawa')) put('hero-area', C.edogawa);
  document.documentElement.setAttribute('data-oh-kisetsu', k || '');
};
window.ohKyouka();
</script>
""".replace("CONF_", json.dumps(conf, ensure_ascii=False))


END_SCRIPT = """<script data-oh="kyouka">
/* LP強化（tools/kyouka-1101.py）。広告向けの差し替え（上の処理）の後に、1画面目の出し分けをもう一度当てる */
if (window.ohKyouka) window.ohKyouka();
/* 相談フォーム（折りたたみ）。#form へのリンクを押したとき・#form で来たときは開く */
(function () {
  var d = document.getElementById('soudan'); if (!d) return;
  document.addEventListener('click', function (ev) {
    var a = ev.target && ev.target.closest ? ev.target.closest('a[href="#form"],a[href="#soudan"]') : null;
    if (a) d.open = true;
  }, true);
  if (location.hash === '#form' || location.hash === '#soudan') d.open = true;
})();
/* 繁忙期（5〜7月・12月）だけ、1画面目の価格の下に加算の1行を出す（それ以外の月は「よくある頼み方」の注記で足りる） */
(function () {
  var el = document.getElementById('peak-now'); if (!el) return;
  var m = new Date(Date.now() + 9 * 3600000).getUTCMonth() + 1;
  if ((m >= 5 && m <= 7) || m === 12) el.hidden = false;
})();
</script>
"""

AREA_EDOGAWA = "✓ 江戸川区北葛西の事務所から伺います（東京・千葉・神奈川）"
TSUKI_4 = {"1": "haru", "2": "haru", "3": "haru", "4": "haru", "5": "natsu", "6": "natsu", "7": "natsu",
           "8": "aki", "9": "aki", "10": "aki", "11": "fuyu", "12": "fuyu"}

ZIP_OLD = "'｜対応エリアです。最短即日でお伺いできます。'"
ZIP_NEW = "'｜対応エリアです。最短即日でお伺いできます（当日のご依頼はお電話で）。'"


def meta(h, title_old, title_new, desc_old=None, desc_new=None, name=""):
    h = kaeru(h, f"<title>{title_old}</title>", f"<title>{title_new}</title>", name=name)
    h = kaeru(h, f'<meta property="og:title" content="{title_old}">', f'<meta property="og:title" content="{title_new}">', name=name)
    if desc_old:
        h = kaeru(h, f'<meta name="description" content="{desc_old}">', f'<meta name="description" content="{desc_new}">', name=name)
        h = kaeru(h, f'<meta property="og:description" content="{desc_old}">', f'<meta property="og:description" content="{desc_new}">', name=name)
    return h


def kyoutsuu(h, name, sticky_small):
    """全ページ共通：CSS・予約ボタンの文言・電話/LINE の位置づけ・最短即日・最後のスクリプト"""
    h = kaeru(h, '\n<div class="bar">', "\n" + CSS + '\n<div class="bar">', name=name)
    h = kaeru(h, 'data-place="header">WEB予約</a>', 'data-place="header">空き日を見て予約</a>', name=name)
    h = kaeru(h, '<a class="btn line" href="https://lin.ee/7kD9WGN">LINE<small>防カビ無料</small></a>',
              '<a class="btn line" href="https://lin.ee/7kD9WGN">LINE相談<small>防カビ無料</small></a>', name=name)
    h = kaeru_re(h, r'data-place="sticky">空き日を見る<small>[^<]*</small></a>',
                 f'data-place="sticky">空き日を見て予約<small>{sticky_small}</small></a>', name=name)
    h = kaeru(h, 'id="nov-link">空いている日を見る</a>', 'id="nov-link">空いている日を見て予約</a>', name=name)
    h = kaeru(h, ZIP_OLD, ZIP_NEW, name=name)
    # CMO 決定（2026-11-04）：聞かれていない比較・但し書きを①②とも外す
    h = re.sub(r"\n\s*<p>この業界はフランチャイズと下請けが主流です。ONE HITTER は違います。</p>", "", h)
    h = h.replace("効果には個人差があります。", "")
    h = kaeru(h, "</body>", END_SCRIPT + "</body>", name=name)
    return h


def soudan_form(h, name, form_name, lead_old, koe_html, add_cal_first=False, h2_old="<h2>WEB予約・お見積り</h2>"):
    """#form：声 → 空いている日を見て予約（主役） → 相談フォーム（折りたたみ）"""
    i = h.find('<section class="alt" id="form">')
    if i < 0:
        i = h.find('<section id="form">')
    if i < 0:
        sys.exit(f"[{name}] #form が無い")
    head, body = h[:i], h[i:]
    body = kaeru(body, h2_old, "<h2>ご予約・ご相談</h2>", name=name)
    body = kaeru(body, lead_old, "", name=name)
    cal = ('    <div class="cal-first">\n'
           '      <p><b>空いている日を見て、そのまま予約できます</b>お名前やお電話番号を入れる前に、予約カレンダーで空き状況を確認して、そのまま予約できます。</p>\n'
           '      <a class="btn lg" href="https://yoyaku.onehitter.jp/" data-yoyaku data-place="form">空いている日を見て予約する</a>\n'
           '      ' + ANSHIN + '\n'
           '      <p class="alt">お電話 <a href="tel:08080438259"><span class="num">080-8043-8259</span></a>（8:00〜20:00）／<a href="https://lin.ee/7kD9WGN">LINEで相談</a></p>\n'
           '    </div>\n')
    if add_cal_first:
        body = kaeru(body, f'    <form class="form" name="{form_name}"', cal + f'    <form class="form" name="{form_name}"', name=name)
    else:
        body = kaeru(body, '<p><b>先に、空いている日を見たい方へ</b>',
                     '<p><b>空いている日を見て、そのまま予約できます</b>', name=name)
        body = kaeru(body, 'data-place="form">空いている日を見て予約する</a>\n',
                     'data-place="form">空いている日を見て予約する</a>\n      ' + ANSHIN + '\n', name=name)
    body = kaeru(body, '    <div class="cal-first">', koe_html + '    <div class="cal-first">', name=name)
    summary = ('    <details class="soudan" id="soudan">\n'
               '      <summary>日にちが決まっていない・相談したい方<small>お名前とお電話番号を送ると、担当から日程のご連絡をします</small></summary>\n'
               '      <p class="form-lead">入力は5項目、1分ほどです。<b>予約の時点では費用は発生しません。</b>ご返信は当日中、遅くとも翌営業日にいたします。</p>\n')
    body = kaeru(body, f'    <form class="form" name="{form_name}"', summary + f'    <form class="form" name="{form_name}"', name=name)
    j = body.find(f'<form class="form" name="{form_name}"')
    k = body.find("</form>", j)
    body = body[:k] + "</form>\n    </details>" + body[k + len("</form>"):]
    return head + body


def koe_ido(h, qtext, name, cap):
    """声を1件、#koe から抜いて、最後の予約ボタンの直前の形にする（原文のまま）"""
    pat = (r'\n[ \t]*<div class="voice">\s*(?:<div class="head">(?:(?!</div>).)*</div>\s*)?<q>'
           + re.escape(qtext) + r'</q>\s*(?:<span class="who">[^<]*</span>\s*)?</div>')
    h, _ = nuku_re(h, pat, name=name)
    blk = f'    <figure class="koe-mae"><q>{qtext}</q><figcaption>{cap}</figcaption></figure>\n'
    return h, blk


def kei(h, name):
    """よくある頼み方などへのフォームの道（ghost ボタン）を、相談の小さなリンクに"""
    n = 0
    for old in ['<a class="btn lg ghost stack" href="#form">この内容で予約に進む<small class="sub">お名前とお電話番号を送り、日程はご連絡で</small></a>',
                '<a class="btn lg ghost" href="#form">この内容でフォームから申し込む</a>']:
        c = h.count(old)
        if c:
            h = h.replace(old, SOUDAN_LINK)
            n += c
    if n != 1:
        sys.exit(f"[{name}] フォームへの ghost ボタンが {n} 個（1 個のはず）")
    h = kaeru_re(h, r'(<a class="btn lg(?: stack)?" href="https://yoyaku\.onehitter\.jp/" data-yoyaku data-place="estimate">.*?</a>)',
                 lambda m: m.group(1) + ANSHIN, name=name)
    return h


HOOD_B = r'\n      <div class="ba">\n        <figure><img src="img/hood-before\.jpg"[^\n]*\n[^\n]*hood-after\.jpg[^\n]*\n[^\n]*</p>\n      </div>'
HOOD_A = (r'\n    <div class="ba">\n      <figure class="shot" style="margin:0">\n        <img src="img/hood-before\.jpg"[^\n]*\n'
          r'(?:[^\n]*\n){6}    </div>\n    <p class="shot-note"><b>レンジフード｜グリスフィルター</b>[^\n]*</p>')


# ---------------------------------------------------------------------------
# エアコン（C・E・kabi）
# ---------------------------------------------------------------------------
AIR_V = {
    "fuyu": {"hero-h1": "暖房をつけたら<br><span class=\"hl\">カビ臭い</span>。<br>年内に、奥のカビまで。",
             "hero-sub": "原因は、フィルターの奥のカビ。分解して洗います。"},
    "haru": {"hero-h1": "冷房を使い始める前に、<br>エアコンの奥の<br><span class=\"hl\">カビ</span>を落としておく。",
             "hero-sub": "フィルター掃除では届かない熱交換器と送風ファンまで、分解して洗います。"},
    "natsu": {"hero-h1": "フィルターを掃除しても<br><span class=\"hl\">カビ臭い</span>。<br>原因は、内部のカビです。",
              "hero-sub": "熱交換器の奥まで、分解して洗います。"},
    "aki": {"hero-h1": "夏に使ったエアコンは、<br>奥に<span class=\"hl\">カビ</span>が<br>残りやすい時期です。",
            "hero-sub": "暖房に切り替える前に、熱交換器と送風ファンまで分解して洗います。"},
}
AIR_H1_KITEI = '<h1 id="hero-h1">エアコンの<span class="hl">カビ臭さ</span>は、<br>フィルターの奥から。</h1>'
AIR_SUB_KITEI = '<p class="hero-sub" id="hero-sub">熱交換器と送風ファンまで、分解して洗います。</p>'

KABI_V = {
    "fuyu": {"kisetsu-ue": "毎日エアコンを洗う職人より",
             "hero-h1": "暖房をつけたら、<br>エアコンが<span class=\"hl\">カビ臭い</span>。",
             "hero-sub": "そのにおいは、フィルターの奥の送風ファンや熱交換器に残ったカビかもしれません。分解して洗います。"},
    "haru": {"kisetsu-ue": "毎日エアコンを洗う職人より",
             "hero-h1": "冷房の季節の前に、<br>エアコンの奥の<br><span class=\"hl\">カビ</span>を落としておく。",
             "hero-sub": "においの元は、フィルターの奥の送風ファンや熱交換器のカビかもしれません。分解して洗います。"},
    "natsu": {"kisetsu-ue": "毎日エアコンを洗う職人より",
              "hero-h1": "冷房をつけたら、<br>エアコンが<span class=\"hl\">カビ臭い</span>。",
              "hero-sub": "そのにおいは、フィルターの奥の送風ファンや熱交換器に残ったカビかもしれません。分解して洗います。"},
    "aki": {"kisetsu-ue": "毎日エアコンを洗う職人より",
            "hero-h1": "夏に使ったエアコン、<br>奥に<span class=\"hl\">カビ</span>が<br>残っていませんか。",
            "hero-sub": "冷房で湿った熱交換器や送風ファンには、カビが残りやすくなります。暖房に切り替える前に、分解して洗います。"},
}

BAND_AIR_C = ('<p class="nov-in"><b>11月の作業は、エアコン1台10%引き</b><span class="nov-sub">ネット予約なら防カビコート無料。ノーマル 9,702円・お掃除機能付き 15,642円</span>')
BAND_AIR_KABI = ('<p class="nov-in"><b>11月のお掃除は、今のご予約で10%お得</b><span class="nov-sub">エアコン1台のご依頼・12月は割引なし</span>')
BAND_AIR_NEW = ('<p class="nov-in"><b>11月の作業は、エアコン1台10%引き</b><span class="nov-sub">ネット予約なら防カビコート（3,300円）も無料</span>')

NAZE_AIR = ('    <p class="naze" id="naze"><b>60分かけて分解し、熱交換器の奥まで洗います。</b>'
            'お見積り以上の追加請求はありません。</p>\n')

NOV_PRICE = ('      <span class="nov-price" id="nov-price">11月の作業なら <b>9,702円</b>（1台のご依頼は10%引き）</span>\n'
             '      <script>if (Date.now() >= Date.UTC(2026, 10, 30, 15, 0, 0)) { document.getElementById(\'nov-price\').hidden = true; }</script>\n')
NOV_PRICE_CSS = ('.hero-price .nov-price{flex-basis:100%;margin:2px 0 0;padding:6px 10px;border-radius:8px;background:#FCEAE4;color:#8F2408;font-size:14px;font-weight:700;line-height:1.5;}\n'
                 '.hero-price .nov-price[hidden]{display:none;}\n'
                 '.hero-price .nov-price b{font-family:"Oswald",sans-serif;font-size:22px;font-weight:500;margin:0 2px;}\n')

HOKEN_LI = '<li><span class="v hoken">保険</span><span class="k">損害賠償保険に<br>加入しています</span></li>'
ZERO_LI = '<li><span class="v">0<small>円</small></span><span class="k">お見積り後の<br>追加請求</span></li>'


def hero_trust_hoken(h, name):
    i = h.find('<ul class="trust" aria-label="選ばれている理由">')
    if i < 0:
        sys.exit(f"[{name}] 1画面目の trust が無い")
    j = h.find("</ul>", i)
    blk = h[i:j]
    blk2 = kaeru(blk, ZERO_LI, HOKEN_LI, name=name)
    return h[:i] + blk2 + h[j:]


def ato_gq(h, html, name):
    """1画面目の声（gq-band）の直後に差し込む"""
    i = h.find('<section class="gq-band">')
    if i < 0 or h.count('<section class="gq-band">') != 1:
        sys.exit(f"[{name}] gq-band が1つではない")
    j = h.find("</section>\n", i) + len("</section>\n")
    return h[:j] + "\n" + html + h[j:]


def rei_ue(h, name, rei_open='<section class="alt" id="rei">', after='<section class="tantou" id="tantou">'):
    """「よくある頼み方」を、1画面目の声の直後へ"""
    h, rei = nuku_re(h, re.escape(rei_open) + r'.*?</section>\n\n', name=name)
    rei = rei.replace('<section class="alt" id="rei">', '<section id="rei">', 1)
    i = h.find(after)
    j = h.find("</section>\n", i) + len("</section>\n")
    return h[:j] + "\n" + rei + h[j:].lstrip("\n")


def aircon(h, name):
    kabi = name == "kabi"
    img = "img/" if name != "aircon-e" else "/aircon-c/img/"
    if kabi:
        h = meta(h, "エアコンが臭い・暖房にしたらカビ臭いときに｜エアコンクリーニング 10,780円｜ONE HITTER",
                 "エアコンが臭い・つけるとカビ臭いときに｜エアコンクリーニング 10,780円・60分｜ONE HITTER",
                 "エアコンが臭い、暖房に切り替えたらカビ臭い。そのにおいは、フィルターの奥の熱交換器や送風ファンのカビかもしれません。分解して洗います。ノーマル10,780円（税込）・60分。お見積り以上の追加請求はありません。東京・千葉・神奈川。",
                 "エアコンが臭い、つけるとカビ臭い。そのにおいは、フィルターの奥の熱交換器や送風ファンのカビかもしれません。分解して洗います。ノーマル10,780円（税込）・60分。お見積り以上の追加請求はありません。自社の職人が伺います。東京・千葉・神奈川。", name)
    else:
        h = meta(h, "エアコンクリーニング 10,780円／60分｜フィルター掃除で取れないカビ臭さに｜ONE HITTER",
                 "エアコンクリーニング ノーマル10,780円・60分｜分解して奥のカビまで洗う｜東京・千葉・神奈川｜ONE HITTER", name=name)
    h = kyoutsuu(h, name, "カレンダーから")
    # 帯：否定をやめ、金額は本文の1行へ寄せる（重複を減らす）
    h = kaeru(h, BAND_AIR_KABI if kabi else BAND_AIR_C, BAND_AIR_NEW, name=name)
    # 見出し（作業月で切り替え。既定は季節によらない文）
    if kabi:
        h = kaeru(h, '    <p class="nagaame-ue">毎日エアコンを洗う職人より、この秋のお知らせ</p>\n',
                  '    <p class="nagaame-ue" id="kisetsu-ue">毎日エアコンを洗う職人より</p>\n', name=name)
        h = kaeru(h, '<h1>9月の長雨で、<br>エアコンの奥に<span class="hl">カビ</span>が<br>増えています。</h1>',
                  '<h1 id="hero-h1">エアコンが<span class="hl">カビ臭い</span>のは、<br>フィルターの奥の<br>カビかもしれません。</h1>', name=name)
        h = kaeru(h, '    <p class="nagaame-sub">暖房をつけたら、エアコンが臭い。</p>\n', '', name=name)
        h = kaeru(h, '<p class="hero-sub" id="hero-sub">いま伺うお宅では、送風ファンの奥に黒いカビが残っているエアコンが目立ちます。暖房をつけて臭ったら、それが合図です。</p>',
                  '<p class="hero-sub" id="hero-sub">そのにおいは、フィルターの奥の送風ファンや熱交換器に残ったカビかもしれません。分解して洗います。</p>', name=name)
        # 「この秋」の欄（2026年10月の現場の話）は 12/1 に隠す
        h = kaeru(h, '<section id="kisetsu">', '<section id="kisetsu" data-kieru="2026-12-01">', name=name)
        conf = {"tsuki": TSUKI_4, "v": KABI_V, "kakusu": ["kisetsu", "nov-rei"]}
    else:
        h = kaeru(h, '<h1>フィルターを掃除しても<br><span class="hl">カビ臭い</span>。<br>原因は、内部のカビです。</h1>', AIR_H1_KITEI, name=name)
        h = kaeru(h, '<p class="hero-sub" id="hero-sub">熱交換器の奥まで、分解して洗います。</p>', AIR_SUB_KITEI, name=name)
        conf = {"tsuki": TSUKI_4, "v": AIR_V, "kakusu": ["nov-rei"]}
    conf.update({"edogawa": AREA_EDOGAWA, "edogawaCids": ARGS.edogawa})
    # 価格：1画面目の金額を「通常」と「11月」の2つに。お掃除機能付き・繁忙期の行は「よくある頼み方」へ
    h = kaeru(h, '      <span class="s">お掃除機能付きは 17,380円／120分<br><span class="peak-line" id="peak-line">5〜7月・12月は +3,300円（いまは加算なし）</span></span>\n',
              '      <span class="peak-now" id="peak-now" hidden>いまは繁忙期です（5〜7月・12月は1台 +3,300円）</span>\n', name=name)
    if kabi:
        h = kaeru(h, '<span class="k">（税込）／60分</span>\n', '<span class="k">（税込）／60分</span>\n' + NOV_PRICE, name=name)
        h = kaeru(h, '.peak-line{font-weight:700;}', NOV_PRICE_CSS + '.peak-line{font-weight:700;}', name=name)
    h = kaeru(h, '    </div>\n\n    <div class="ba-hero">', '    </div>\n' + NAZE_AIR + '\n    <div class="ba-hero">', name=name)
    # 速さ：1画面目の写真
    h = kaeru(h, f'<img src="{img}fan-before.jpg" alt="エアコンの送風ファン。施工前は羽根がホコリとカビで灰色になっている" width="800" height="600">',
              f'<img src="{img}fan-before.jpg" alt="エアコンの送風ファン。施工前は羽根がホコリとカビで灰色になっている" width="800" height="600" fetchpriority="high" decoding="async">', name=name)
    h = kaeru(h, f'<img src="{img}fan-after.jpg" alt="同じ送風ファン。施工後は羽根の黒い地が見えている" width="800" height="600">',
              f'<img src="{img}fan-after.jpg" alt="同じ送風ファン。施工後は羽根の黒い地が見えている" width="800" height="600" decoding="async">', name=name)
    h = hero_trust_hoken(h, name)
    # 1画面目の出し分けの処理は、1画面目の直後に
    h = kaeru(h, '</section>\n\n<section class="gq-band">', '</section>\n' + hero_script(conf) + '\n<section class="gq-band">', name=name)
    # 広告向けの差し替えで説明文を上書きしない（季節の説明文を残す）
    h = kaeru_re(h, r"      sashikae\('hero-sub',  '[^\n]*'\);\n",
                 "      /* hero-sub の差し替えはやめた（季節の説明文と価格下の1行が受け持つ。tools/kyouka-1101.py） */\n", name=name)
    # 誰が来るか（1画面目の声の直下）→ よくある頼み方
    h = ato_gq(h, tantou(img + "sagyou.jpg"), name)
    h = rei_ue(h, name)
    # 「よくある頼み方」の1台の札にも、11月の金額（1画面目と食い違わないように。12/1 に隠す）
    h = kaeru(h, '<span class="from">作業は60分</span>',
              '<span class="from">作業は60分<span id="nov-rei"><br>11月の作業なら 9,702円</span></span>', name=name)
    # 申込の道
    h = kei(h, name)
    h, koe = koe_ido(h, "エアコン掃除を頼むのが初めてだったので不安が大きかったですが、思ってた以上に丁寧な感じで、掃除する前に段階を踏んでから取り掛かっていたのでよかった。担当してくれた方も気さくな人だったので不安はなくなりました。また利用したいです。",
                     name, "62歳 女性・エアコンクリーニング（公式サイト「お客様の声」より、原文のまま）")
    h = soudan_form(h, name, f"reserve-{name}",
                    '    <p class="form-lead">入力は5項目、1分ほどです。<b>予約の時点では費用は発生しません。</b>ご返信は当日中、遅くとも翌営業日にいたします。</p>\n',
                    koe)
    return h


# ---------------------------------------------------------------------------
# 水まわり（A：/mizumawari/・B：/mizumawari-b/）
# ---------------------------------------------------------------------------
MIZU_UE = {
    "fuyu": {"kisetsu-ue": "年末の大掃除の前に、水まわりをまとめて"},
    "haru": {"kisetsu-ue": "新しい季節の前に、水まわりをまとめて"},
    "natsu": {"kisetsu-ue": "湿気でカビが出やすい季節の、浴室と洗濯機に"},
    "aki": {"kisetsu-ue": "夏のあいだの水まわりの汚れを、まとめて"},
}
BATH_SUB = "浴室クリーニングは18,480円（税込）・120分。床・壁・天井・鏡・ドアまで洗います。追い焚き配管など、2箇所目からはセット価格になります。"


def mizumawari(h, name):
    h = meta(h, "水まわりクリーニング まとめて依頼で1箇所3,300円おトク｜ONE HITTER",
             "水まわりクリーニング 浴室・キッチン・洗濯機 まとめて依頼で1箇所3,300円おトク｜ONE HITTER",
             "キッチン・浴室・レンジフード・洗濯機・追い焚き配管。2箇所目からは同時施工価格。浴室＋キッチンで33,660円（税込）、半日で完了。東京・千葉・神奈川、最短即日。",
             "浴室・キッチン・レンジフード・洗濯機・追い焚き配管。2箇所目からは同時施工価格。浴室＋キッチンで33,660円（税込）、半日で完了。お見積り以上の追加請求はありません。自社の職人が伺います。東京・千葉・神奈川、最短即日（当日のご依頼はお電話で）。", name)
    h = kyoutsuu(h, name, "料金もその場で")
    h = kaeru(h, '<p class="nov-in"><b>11月のお掃除は、今のご予約で10%お得</b><span class="nov-sub">1箇所のご依頼・12月は繁忙期（1箇所+3,300円）</span>',
              '<p class="nov-in"><b>11月の作業は、1箇所だけのご依頼なら10%引き</b><span class="nov-sub">2箇所目からはセット価格</span>', name=name)
    # 1画面目
    h = kaeru(h, '<img src="img/hero-bg.jpg" alt="" width="1600" height="1067" fetchpriority="high" decoding="async">',
              '<img src="img/hero-bg.jpg" id="hero-bg-img" alt="" width="1200" height="800" fetchpriority="high" decoding="async">', name=name)
    h = kaeru(h, '<span class="area" id="hero-area">✓ 東京・千葉・神奈川 対応／最短即日</span>',
              '<span class="area" id="hero-area">✓ 東京・千葉・神奈川 対応／最短即日（当日のご依頼はお電話で）</span>\n'
              '    <p class="kisetsu-ue" id="kisetsu-ue" hidden></p>', name=name)
    h = kaeru(h, '<h1>水まわりは、<br><span class="hl">まとめて頼むほど安い。</span></h1>',
              '<h1 id="hero-h1">水まわりは、<br><span class="hl">まとめて頼むほど安い。</span></h1>', name=name)
    h = kaeru(h, '      <a class="btn lg" href="https://yoyaku.onehitter.jp/" data-yoyaku data-place="hero">空いている日と料金を見る</a>\n'
                 '      <a class="btn lg tel-cta" id="hero-tel" href="tel:08080438259" hidden>電話で相談する<span class="tel-no">080-8043-8259</span><span class="tel-time">8:00〜20:00／担当 渡辺</span></a>\n'
                 '      <a class="btn lg line" href="https://lin.ee/7kD9WGN">LINEで相談・予約する</a>\n',
              '      <a class="btn lg" href="https://yoyaku.onehitter.jp/" data-yoyaku data-place="hero">空いている日を見て予約する</a>\n'
                 '      <p class="hero-tel" id="hero-tel">お電話でも <a href="tel:08080438259"><span class="num">080-8043-8259</span></a>（8:00〜20:00）</p>\n'
                 '      <a class="line-soudan" href="https://lin.ee/7kD9WGN">LINEで相談する</a>\n', name=name)
    h = kaeru(h, '    <p class="perk" id="hero-perk">',
              '    <p class="peak-now" id="peak-now" hidden>いまは繁忙期です（5〜7月・12月は1箇所 +3,300円）</p>\n'
              '    <p class="naze" id="naze">下請けに出さず、自社の職人が1箇所ずつ洗います（浴室・キッチンは各120分）。<b>お見積り以上の追加請求はありません。</b></p>\n'
              '    <p class="perk" id="hero-perk">', name=name)
    h = kaeru(h, '<div><span class="t num">0円</span><span class="b">お見積り後の<br>追加請求</span></div>',
              '<div><span class="t hoken">保険</span><span class="b">損害賠償保険に<br>加入しています</span></div>', name=name)
    conf = {"tsuki": TSUKI_4, "v": MIZU_UE, "edogawa": AREA_EDOGAWA, "edogawaCids": ARGS.edogawa,
            "bathKeys": [x.lower() for x in ARGS.yokushitsu],
            "bath": {"kisetsu-ue": "浴室クリーニング",
                     "hero-h1": "浴室のカビと水アカ、<br><span class=\"hl\">追い焚き配管まで</span><br>まとめて洗います。",
                     "hero-sub": BATH_SUB,
                     "img": [["hero-bg-img", "img/bath-hero.jpg", "作業を終えた浴室（実際の施工後）"]]}}
    h = kaeru(h, '\n<section>\n  <div class="wrap">\n    <div class="sec-h">\n      <span class="eyebrow">Scenes</span>',
              "\n" + hero_script(conf) + tantou("img/sagyou.jpg") +
              '\n<section>\n  <div class="wrap">\n    <div class="sec-h">\n      <span class="eyebrow">Scenes</span>', name=name)
    # 広告向けの差し替え：電話を見出しの上へ動かさない（電話は副）。説明文の「一切」を外す
    h = kaeru(h, "      if (tel && area && area.parentNode) {\n        tel.hidden = false;\n        tel.classList.add('tel-cta-ue');\n        area.parentNode.insertBefore(tel, area.nextSibling);\n      }\n",
              "      /* 電話を見出しの上へ動かすのはやめた（主役は予約ボタン1本・電話は副。tools/kyouka-1101.py） */\n", name=name)
    h = kaeru(h, "<b>お見積りは無料で、見積り以上の追加請求は一切ありません。</b>", "<b>お見積りは無料で、お見積り以上の追加請求はありません。</b>", name=name)
    h = kaeru(h, "<p>お見積り以上の追加請求は一切ありません。当日その場で", "<p>お見積り以上の追加請求はありません。当日その場で", name=name)
    h = kaeru(h, "<p>ありません。お見積り以上の追加請求は一切いたしません。", "<p>ありません。お見積り以上の追加請求はいたしません。", name=name)
    # 重複を減らす
    h = kaeru(h, '    <p class="shot-note">分解して取り出した洗濯槽の裏側。市販のクリーナーでは、ここまで届きません。</p>\n', '', name=name)
    h = kaeru(h, '      <p>表示は単体でご依頼いただいた場合の価格です。</p>\n      <p class="paid-note">※駐車スペースがない場合は、コインパーキング代を実費でいただきます。金額は事前にお伝えします。遠方（目安：高速道路を使う地域）は、交通費をいただく場合があります。お見積りのお電話でご案内します。</p>\n',
              '      <p>表示は単体でご依頼いただいた場合の価格です。</p>\n', name=name)
    # 法規：別物のレンジフードを「施工前後」として出さない
    h = kaeru_re(h, HOOD_A, "", name=name)
    # 申込の道
    h = kei(h, name)
    h, koe = koe_ido(h, "丁寧な説明、対応で安心して任せられました。他の業者と比較しても低価格なところも利用する決め手になりました。",
                     name, "27歳 女性（公式サイト「お客様の声」より、原文のまま）")
    h = soudan_form(h, name, "reserve-mizumawari", "      <p>入力は5項目。ご返信は当日中、遅くとも翌営業日にいたします。</p>\n", koe, add_cal_first=True)
    return h


def mizumawari_b(h, name):
    h = kyoutsuu(h, name, "料金もその場で")
    h = kaeru(h, '<p class="nov-in"><b>11月のお掃除は、今のご予約で10%お得</b><span class="nov-sub">1箇所のご依頼・12月は繁忙期（1箇所+3,300円）</span>',
              '<p class="nov-in"><b>11月の作業は、1箇所だけのご依頼なら10%引き</b><span class="nov-sub">2箇所目からはセット価格</span>', name=name)
    h = kaeru(h, '<p class="hero-eyebrow">水まわりの、まとめ頼み</p>', '<p class="hero-eyebrow" id="kisetsu-ue">水まわりの、まとめ頼み</p>', name=name)
    h = kaeru(h, '<h1>浴室とキッチン、<br><span class="mk">2箇所で<span class="num">33,660</span>円</span>。</h1>',
              '<h1 id="hero-h1">浴室とキッチン、<br><span class="mk">2箇所で<span class="num">33,660</span>円</span>。</h1>', name=name)
    h = kaeru(h, '<p class="hero-sub" id="hero-sub">2箇所目から、同時施工の価格になります。<b>お見積り以上の追加請求はありません。</b></p>',
              '<p class="hero-sub" id="hero-sub">2箇所目から、同時施工の価格になります。浴室・キッチンは、それぞれ120分かけて洗います。<b>お見積り以上の追加請求はありません。</b></p>\n'
              '    <p class="peak-now" id="peak-now" hidden>いまは繁忙期です（5〜7月・12月は1箇所 +3,300円）</p>', name=name)
    h = kaeru(h, '<figure><img src="img/drum-before.jpg" alt="洗濯槽の内側。施工前は黒カビが全体に付着している" width="760" height="760">',
              '<figure><img src="img/drum-before.jpg" id="hero-ba1" alt="洗濯槽の内側。施工前は黒カビが全体に付着している" width="760" height="760" fetchpriority="high" decoding="async">', name=name)
    h = kaeru(h, '<figure class="after"><img src="img/drum-after.jpg" alt="同じ洗濯槽の内側。施工後は白い地が見えている" width="760" height="760">',
              '<figure class="after"><img src="img/drum-after.jpg" id="hero-ba2" alt="同じ洗濯槽の内側。施工後は白い地が見えている" width="760" height="760" decoding="async">', name=name)
    h = kaeru(h, '<p class="ba-hero-cap">洗濯槽の内側｜実際の施工前と施工後（同じ箇所）</p>',
              '<p class="ba-hero-cap" id="hero-ba-cap">洗濯槽の内側｜実際の施工前と施工後（同じ箇所）</p>', name=name)
    h = hero_trust_hoken(h, name)
    mizu_ue_b = {k: {"kisetsu-ue": v["kisetsu-ue"]} for k, v in MIZU_UE.items()}
    conf = {"tsuki": TSUKI_4, "v": mizu_ue_b, "edogawa": AREA_EDOGAWA, "edogawaCids": ARGS.edogawa,
            "bathKeys": [x.lower() for x in ARGS.yokushitsu],
            "bath": {"kisetsu-ue": "浴室クリーニング",
                     "hero-h1": "浴室は<span class=\"mk\"><span class=\"num\">18,480</span>円</span>。<br>2箇所目から、セット価格。",
                     "hero-sub": "床・壁・天井・鏡・ドアまで、120分かけて洗います。追い焚き配管やキッチンと一緒なら、2箇所目はセット価格です。<b>お見積り以上の追加請求はありません。</b>",
                     "hero-ba-cap": "浴室の鏡｜実際の施工前と施工後（同じ箇所）",
                     "img": [["hero-ba1", "img/mirror-before.jpg", "浴室の鏡。施工前は水アカで白く曇っている"],
                             ["hero-ba2", "img/mirror-after.jpg", "同じ浴室の鏡。施工後は映り込みがはっきりしている"]]}}
    h = kaeru(h, '</section>\n\n<section class="gq-band">', '</section>\n' + hero_script(conf) + '\n<section class="gq-band">', name=name)
    h = kaeru(h, "<b>お見積りは無料で、見積り以上の追加請求は一切ありません。</b>", "<b>お見積りは無料で、お見積り以上の追加請求はありません。</b>", name=name)
    h = ato_gq(h, tantou("img/sagyou.jpg"), name)
    h = rei_ue(h, name, rei_open='<section id="rei">')
    h = kaeru_re(h, HOOD_B, "", name=name)
    h = kei(h, name)
    h, koe = koe_ido(h, "丁寧な説明、対応で安心して任せられました。他の業者と比較しても低価格なところも利用する決め手になりました。",
                     name, "27歳 女性（公式サイト「お客様の声」より、原文のまま）")
    h = soudan_form(h, name, "reserve-mizumawari-b",
                    '    <p class="form-lead">入力は5項目、1分ほどです。<b>予約の時点では費用は発生しません。</b>ご返信は当日中、遅くとも翌営業日にいたします。</p>\n', koe)
    return h


# ---------------------------------------------------------------------------
# 年末（A：/nenmatsu/・B：/nenmatsu-b/）
# ---------------------------------------------------------------------------
NEN_TSUKI = {str(m): ("natsu" if 5 <= m <= 7 else "futsuu") for m in range(1, 11)}
NEN_TSUKI.update({"11": "nov", "12": "dec"})
SETBOX_FUTSUU = ('<div class="top">よくあるご依頼｜レンジフード＋浴室の2箇所</div><div class="mid">'
                 '<div class="big"><span class="num">33,660</span><span class="unit">円</span></div>'
                 '<div class="note">レンジフードクリーニング 18,480円 ＋ 浴室クリーニング 15,180円（セット価格・税込）</div></div>')
SETBOX_NATSU = ('<div class="top">よくあるご依頼｜レンジフード＋浴室の2箇所</div><div class="mid">'
                '<div class="big"><span class="num">40,260</span><span class="unit">円</span><span class="unit" style="font-size:13px">／5〜7月の作業</span></div>'
                '<div class="note">レンジフードクリーニング 18,480円 ＋ 浴室クリーニング 15,180円（セット価格）に、繁忙期料金 1箇所 3,300円 × 2 を含みます（税込）。</div></div>')
SETBOX_DEC = ('<div class="top">年末に多いご依頼｜レンジフード＋浴室の2箇所</div><div class="mid">'
              '<div class="big"><span class="num">40,260</span><span class="unit">円</span><span class="unit" style="font-size:13px">／12月の作業</span></div>'
              '<div class="note">レンジフードクリーニング 18,480円 ＋ 浴室クリーニング 15,180円（セット価格）に、12月の繁忙期料金 1箇所 3,300円 × 2 を含みます（税込）。</div></div>')


def nenmatsu(h, name):
    h = meta(h, "年末大掃除 11月までなら通常価格｜レンジフード・浴室・キッチン｜ONE HITTER",
             "年末大掃除のハウスクリーニング｜レンジフード・浴室・キッチン｜東京・千葉・神奈川｜ONE HITTER", name=name)
    h = kyoutsuu(h, name, "料金もその場で")
    h = kaeru(h, '<p class="nov-in"><b>11月のお掃除は、今のご予約で10%お得</b><span class="nov-sub">1箇所だけのご依頼・12月は繁忙期（1箇所+3,300円）</span>',
              '<p class="nov-in"><b>11月の作業は、1箇所だけのご依頼なら10%引き</b><span class="nov-sub">2箇所目からはセット価格</span>', name=name)
    h = kaeru(h, '<img src="img/hero-bg.jpg" alt="" width="1600" height="1067" fetchpriority="high" decoding="async">',
              '<img src="img/hero-bg.jpg" alt="" width="1200" height="800" fetchpriority="high" decoding="async">', name=name)
    h = kaeru(h, '<span class="area">✓ 東京・千葉・神奈川 対応／年末の予約 受付中</span>',
              '<span class="area" id="hero-area">✓ 東京・千葉・神奈川 対応／自社の職人が伺います</span>', name=name)
    h = kaeru(h, '<h1>年末の大掃除は、<br><span class="hl">11月までが安い。</span></h1>',
              '<h1 id="hero-h1">年末の大掃除は、<br><span class="hl">11月までが安い。</span></h1>', name=name)
    h = kaeru(h, '<p class="sub">12月は繁忙期料金となり', '<p class="sub" id="hero-sub">12月は繁忙期料金となり', name=name)
    h = kaeru(h, '      <a class="btn lg" href="https://yoyaku.onehitter.jp/" data-yoyaku data-place="hero">11月中の空いている日を見る</a>\n'
                 '      <a class="iri-sub" href="#builder">箇所を選んで、年末の料金を見る</a>\n'
                 '      <a class="btn lg line" href="https://lin.ee/7kD9WGN">LINE登録で 防カビコーティング無料</a>\n',
              '      <a class="btn lg" href="https://yoyaku.onehitter.jp/" data-yoyaku data-place="hero">空いている日を見て予約する</a>\n'
                 '      <a class="iri-sub" href="#builder">箇所を選んで、料金を見る</a>\n'
                 '      <p class="hero-tel" id="hero-tel">お電話でも <a href="tel:08080438259"><span class="num">080-8043-8259</span></a>（8:00〜20:00）</p>\n'
                 '      <a class="line-soudan" href="https://lin.ee/7kD9WGN">LINEで相談する（ご登録で防カビコーティング無料）</a>\n', name=name)
    h = kaeru(h, '    <div class="setbox">\n      <div class="top">年末に多いご依頼｜レンジフード＋浴室の2箇所</div>',
              '    <div class="setbox" id="setbox">\n      <div class="top">年末に多いご依頼｜レンジフード＋浴室の2箇所</div>', name=name)
    h = kaeru(h, '    <div class="trust">\n      <div><span class="t num">98.6%</span>',
              '    <p class="naze" id="naze">レンジフードは90分、浴室は120分かけて洗います。下請けに出さず、自社の職人が伺います。<b>お見積り以上の追加請求はありません。</b></p>\n\n'
              '    <div class="trust">\n      <div><span class="t num">98.6%</span>', name=name)
    h = kaeru(h, '<div><span class="t num">0円</span><span class="b">お見積り後の<br>追加請求</span></div>',
              '<div><span class="t hoken">保険</span><span class="b">損害賠償保険に<br>加入しています</span></div>', name=name)
    h = kaeru(h, '<section class="alt">\n  <div class="wrap">\n    <div class="sec-h">\n      <span class="eyebrow">Price</span>\n      <h2>12月から、料金が上がります</h2>',
              '<section class="alt" id="kigen">\n  <div class="wrap">\n    <div class="sec-h">\n      <span class="eyebrow">Price</span>\n      <h2>12月から、料金が上がります</h2>', name=name)
    h = kaeru(h, 'data-place="aki">11月中の空き枠を確認する</a>', 'data-place="aki">空いている日を見て予約する</a>', name=name)
    conf = {"tsuki": NEN_TSUKI, "kakusu": ["kigen"], "edogawa": AREA_EDOGAWA, "edogawaCids": ARGS.edogawa,
            "v": {"nov": {},
                  "dec": {"hero-h1": "年末の大掃除を、<br><span class=\"hl\">年内にまとめて。</span>",
                          "hero-sub": "レンジフード、浴室、キッチン、洗濯機。年末に手が回らない場所を、半日でまとめて片付けます。12月は繁忙期のため、1箇所につき3,300円が加わります。",
                          "setbox": SETBOX_DEC},
                  "futsuu": {"hero-h1": "大掃除は、<br><span class=\"hl\">まとめて頼むほど安い。</span>",
                             "hero-sub": "レンジフード、浴室、キッチン、洗濯機。2箇所目から、同時施工の価格になります。",
                             "setbox": SETBOX_FUTSUU},
                  "natsu": {"hero-h1": "大掃除は、<br><span class=\"hl\">まとめて頼むほど安い。</span>",
                            "hero-sub": "レンジフード、浴室、キッチン、洗濯機。2箇所目から、同時施工の価格になります。5〜7月は繁忙期のため、1箇所につき3,300円が加わります。",
                            "setbox": SETBOX_NATSU}}}
    h = kaeru(h, '\n<section>\n  <div class="wrap">\n    <div class="sec-h">\n      <span class="eyebrow">Scenes</span>',
              "\n" + hero_script(conf) + tantou("img/sagyou.jpg") +
              '\n<section>\n  <div class="wrap">\n    <div class="sec-h">\n      <span class="eyebrow">Scenes</span>', name=name)
    h = kaeru(h, "<p>お見積り以上の追加請求は一切ありません。当日その場で", "<p>お見積り以上の追加請求はありません。当日その場で", name=name)
    h = kaeru(h, "<p>ありません。お見積り以上の追加請求は一切いたしません。", "<p>ありません。お見積り以上の追加請求はいたしません。", name=name)
    h = kaeru_re(h, HOOD_A, "", name=name)
    h = kei(h, name)
    h, koe = koe_ido(h, "まず作業前に現状を見せていただきました。…クリーニング後は、新品同様にピッカピカになり大満足。",
                     name, "M様・洗濯機と換気扇（Googleクチコミ・2024年4月。原文のまま、「…」は中略）")
    h = soudan_form(h, name, "reserve-nenmatsu", "      <p>入力は5項目。ご返信は当日中、遅くとも翌営業日にいたします。</p>\n", koe, add_cal_first=True)
    return h


def nenmatsu_b(h, name):
    h = meta(h, "年末大掃除 レンジフード＋浴室33,660円 11月30日の作業まで｜ONE HITTER",
             "年末大掃除 レンジフード＋浴室をまとめて｜東京・千葉・神奈川｜ONE HITTER", name=name)
    h = kyoutsuu(h, name, "料金もその場で")
    h = kaeru(h, '<p class="nov-in"><b>11月のお掃除は、今のご予約で10%お得</b><span class="nov-sub">1箇所だけのご依頼・12月は繁忙期（1箇所+3,300円）</span>',
              '<p class="nov-in"><b>11月の作業は、1箇所だけのご依頼なら10%引き</b><span class="nov-sub">2箇所目からはセット価格</span>', name=name)
    h = kaeru(h, '<p class="hero-area" id="hero-area">✓ 東京・千葉・神奈川／年末の予約 受付中</p>',
              '<p class="hero-area" id="hero-area">✓ 東京・千葉・神奈川／自社の職人が伺います</p>', name=name)
    h = kaeru(h, '<p class="hero-eyebrow">年末の大掃除は、11月中の作業が安い</p>', '<p class="hero-eyebrow" id="kisetsu-ue">年末の大掃除は、11月中の作業が安い</p>', name=name)
    h = kaeru(h, '<h1>レンジフードと浴室、<br><span class="mk">2箇所で<span class="num">33,660</span>円</span>。</h1>',
              '<h1 id="hero-h1">レンジフードと浴室、<br><span class="mk">2箇所で<span class="num">33,660</span>円</span>。</h1>', name=name)
    h = kaeru(h, '<p class="hero-sub" id="hero-sub"><b>11月30日までの作業なら、この通常価格です。</b>12月は1箇所につき3,300円が加わり、40,260円になります。</p>',
              '<p class="hero-sub" id="hero-sub"><b>11月30日までの作業なら、この通常価格です。</b>12月は1箇所につき3,300円が加わり、40,260円になります。</p>\n'
              '    <p class="naze" id="naze">レンジフードは90分、浴室は120分かけて洗います。お見積り以上の追加請求はありません。</p>', name=name)
    # 法規：レンジフードの組写真は別物（docs/photo-inventory.md 2026-09-06）。検証済みの浴室の鏡の組に替える
    h = kaeru(h, '<figure><img src="img/hood-before.jpg" alt="レンジフードのグリスフィルター。施工前は網目が油で埋まっている" width="800" height="600"><span class="lb">BEFORE</span></figure>',
              '<figure><img src="img/mirror-before.jpg" alt="浴室の鏡。施工前は水アカで白く曇っている" width="800" height="600" fetchpriority="high" decoding="async"><span class="lb">BEFORE</span></figure>', name=name)
    h = kaeru(h, '<figure class="after"><img src="img/hood-after.jpg" alt="同じグリスフィルター。施工後は網目が抜けている" width="800" height="600"><span class="lb">AFTER</span></figure>',
              '<figure class="after"><img src="img/mirror-after.jpg" alt="同じ浴室の鏡。施工後は映り込みがはっきりしている" width="800" height="600" decoding="async"><span class="lb">AFTER</span></figure>', name=name)
    h = kaeru(h, '<p class="ba-hero-cap">レンジフードのフィルター｜実際の施工前と施工後（同じ箇所）</p>',
              '<p class="ba-hero-cap">浴室の鏡｜実際の施工前と施工後（同じ箇所）</p>', name=name)
    h = hero_trust_hoken(h, name)
    h = kaeru(h, 'data-place="deadline">11月中の空き枠を確認する</a>', 'data-place="deadline">空いている日を見て予約する</a>', name=name)
    conf = {"tsuki": NEN_TSUKI, "kakusu": ["kigen"], "edogawa": AREA_EDOGAWA, "edogawaCids": ARGS.edogawa,
            "v": {"nov": {},
                  "dec": {"kisetsu-ue": "12月の作業（繁忙期の料金を含みます）",
                          "hero-h1": "レンジフードと浴室、<br><span class=\"mk\">2箇所で<span class=\"num\">40,260</span>円</span>。",
                          "hero-sub": "12月は繁忙期のため、1箇所につき3,300円を含みます。年末に手が回らない場所を、まとめて片付けます。"},
                  "futsuu": {"kisetsu-ue": "大掃除は、まとめて頼むほど安い",
                             "hero-sub": "2箇所目から、同時施工の価格になります。"},
                  "natsu": {"kisetsu-ue": "5〜7月の作業（繁忙期の料金を含みます）",
                            "hero-h1": "レンジフードと浴室、<br><span class=\"mk\">2箇所で<span class=\"num\">40,260</span>円</span>。",
                            "hero-sub": "5〜7月は繁忙期のため、1箇所につき3,300円を含みます。2箇所目から、同時施工の価格になります。"}}}
    h = kaeru(h, '</section>\n\n<section class="gq-band">', '</section>\n' + hero_script(conf) + '\n<section class="gq-band">', name=name)
    h = ato_gq(h, tantou("img/sagyou.jpg"), name)
    h = kei(h, name)
    h, koe = koe_ido(h, "今回3回目の利用です。…クリーニング後は汚れを見せてくれるので、こんなに汚れていたんだと確認できます。",
                     name, "Y様（Googleクチコミ・2026年4月。原文のまま、「…」は中略）")
    h = soudan_form(h, name, "reserve-nenmatsu-b",
                    '    <p class="form-lead">入力は5項目、1分ほどです。<b>予約の時点では費用は発生しません。</b>ご返信は当日中、遅くとも翌営業日にいたします。</p>\n', koe)
    return h


# ---------------------------------------------------------------------------
# 画像（下書きの img/ に。元は上書きしない）
# ---------------------------------------------------------------------------
def gazou(name, out_img):
    from PIL import Image  # pip install pillow
    src_img = SRC / name / "img"
    if name == "aircon-e":
        return []   # E は /aircon-c/img/ を使う
    out_img.mkdir(parents=True, exist_ok=True)
    for f in src_img.iterdir():
        if f.is_file():
            shutil.copy2(f, out_img / f.name)
    log = []

    def tsumeru(fname, size=None, quality=80, src=None, crop=None):
        s = pathlib.Path(src) if src else src_img / fname
        im = Image.open(s)
        im = im.convert("RGB")
        if crop:
            im = im.crop(crop)
        if size and im.size != size:
            im = im.resize(size, Image.LANCZOS)
        tmp = out_img / (fname + ".tmp")
        im.save(tmp, "JPEG", quality=quality, optimize=True, progressive=True)
        before = s.stat().st_size
        if not src and not crop and tmp.stat().st_size >= before and size is None:
            tmp.unlink()
            log.append(f"{fname}: そのまま（詰め直しても小さくならない）")
            return
        tmp.replace(out_img / fname)
        log.append(f"{fname}: {before // 1024}KB → {(out_img / fname).stat().st_size // 1024}KB" + (f"（{size[0]}×{size[1]}）" if size else ""))

    # 作業中の写真（公開済みの blog-photos/IMG_8014.jpg。人は写っていない）
    tsumeru("sagyou.jpg", size=(800, 600), quality=72, src=SRC / "blog-photos" / "IMG_8014.jpg")
    if name in ("aircon-c", "kabi"):
        tsumeru("fan-before.jpg"); tsumeru("fan-after.jpg")
    if name in ("mizumawari", "nenmatsu"):
        tsumeru("hero-bg.jpg", size=(1200, 800), quality=76)
    if name == "mizumawari":
        tsumeru("bath-hero.jpg", size=(1200, 800), quality=76, src=SRC / "nenmatsu" / "img" / "bath-after-2.jpg", crop=(0, 400, 1200, 1200))
    if name in ("mizumawari-b",):
        tsumeru("drum-before.jpg")
    return log


# ---------------------------------------------------------------------------
# 点検（計測を壊していないか・決まりに反していないか）
# ---------------------------------------------------------------------------
def tenken(name, before, after):
    ng = []
    oh = lambda s: re.search(r"window\.OH_M=(\{.*?\});</script>", s).group(1)
    if oh(before) != oh(after):
        ng.append("OH_M が変わった")
    for pat in [r"gtag\('config'[^\n]*", r'<input type="hidden"[^>]*>', r'name="[^"]+"', r'<form [^>]*>']:
        a, b = sorted(re.findall(pat, before)), sorted(re.findall(pat, after))
        if a != b:
            ng.append(f"{pat} の並びが変わった（{len(a)}→{len(b)}）")
    for k in ["send('generate_lead'", "send('phone_click'", "send('form_submit'", "data-oh=\"moushikomi\"", "送信元の確認"]:
        if before.count(k) != after.count(k):
            ng.append(f"{k} の数が変わった")
    txt = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", after, flags=re.S)
    for w in ["98.8", "出張費無料", "一切かからない", "完全分解", "背抜き", "ファンを外", "今だけ", "先着", "No.1", "9月の長雨"]:
        if w in txt:
            ng.append(f"使わない言い方「{w}」が本文にある")
    for tel in re.findall(r"0\d{1,3}-\d{2,4}-\d{4}", txt):
        if tel not in ("080-8043-8259", "03-5674-8758"):
            ng.append(f"電話番号 {tel}")
    if after.count('data-yoyaku') < before.count('data-yoyaku'):
        ng.append("予約ボタン（data-yoyaku）が減った")
    if "hood-after.jpg" in after:
        ng.append("別物のレンジフードの組写真が残っている")
    return ng


def main():
    global ARGS
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(SRC))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--yokushitsu-ag", default="bath,B_浴室", help="浴室の広告グループの ?ag= の値（カンマ区切り。{adgroupid} の数字を足す）")
    ap.add_argument("--edogawa-cid", default="", help="江戸川区のキャンペーンの ?cid= の値（カンマ区切り）")
    ap.add_argument("--only", default="", help="作るページを絞る（カンマ区切り）")
    ARGS = ap.parse_args()
    ARGS.yokushitsu = [x for x in ARGS.yokushitsu_ag.split(",") if x]
    ARGS.edogawa = [x for x in ARGS.edogawa_cid.split(",") if x]
    src, out = pathlib.Path(ARGS.src), pathlib.Path(ARGS.out)
    names = [n for n in NAMES if not ARGS.only or n in ARGS.only.split(",")]
    fn = {"aircon-c": aircon, "aircon-e": aircon, "kabi": aircon, "mizumawari": mizumawari,
          "mizumawari-b": mizumawari_b, "nenmatsu": nenmatsu, "nenmatsu-b": nenmatsu_b}
    bad = False
    for n in names:
        before = (src / n / "index.html").read_text(encoding="utf-8")
        if MARK in before:
            sys.exit(f"[{n}] すでに強化済みの HTML が元になっている。止めます")
        after = fn[n](before, n)
        ng = tenken(n, before, after)
        (out / n).mkdir(parents=True, exist_ok=True)
        (out / n / "index.html").write_text(after, encoding="utf-8")
        log = gazou(n, out / n / "img")
        print(f"[{n}] 書き出しました: {out / n / 'index.html'}（{len(before.encode()) // 1024}KB → {len(after.encode()) // 1024}KB）")
        for l in log:
            print(f"    画像 {l}")
        for x in ng:
            print(f"    NG {x}")
            bad = True
    if "aircon-c" in names:
        spec = importlib.util.spec_from_file_location("furiwake", ROOT / "tools" / "furiwake-aircon.py")
        fw = importlib.util.module_from_spec(spec); spec.loader.exec_module(fw)
        h = fw.make((out / "aircon-c" / "index.html").read_text(encoding="utf-8"))
        ng = fw.tenken(h)
        if ng:
            sys.exit("/aircon/ の作り直しで NG:\n  " + "\n  ".join(ng))
        (out / "aircon").mkdir(parents=True, exist_ok=True)
        (out / "aircon" / "index.html").write_text(h, encoding="utf-8")
        print(f"[aircon] 書き出しました: {out / 'aircon' / 'index.html'}（直した C の写し＋振り分け）")
    if bad:
        sys.exit(1)


if __name__ == "__main__":
    main()
