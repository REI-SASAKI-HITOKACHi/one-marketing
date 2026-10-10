#!/usr/bin/env python3
"""次のA/B（エアコン）の対抗案 /aircon-e/ を、学習版 /aircon-c/ の配信物から作る。

    python3 tools/ab-aircon-e.py --src deploy/netlify/aircon-c --out deploy/netlify/aircon-e
    python3 tools/ab-aircon-e.py --src <dir> --out <dir> --check   # 作ったあと点検だけ（終了コード）

## 何のためのものか（docs/LP-次のABテスト-2026-10.md）

第6回MTG 6-4 No.7 のオーナー決定「学習後LPの方が成果が出ている。…次のABテストへ進んで」。
基準（対照）＝学習版 /aircon-c/（入口の直し 73823ec3 を当てたもの）。
対抗案 /aircon-e/ は **1か所だけ** 違う：

  最初の画面の主ボタンの上に「いちばん早い空き（エアコン1台・60分の場合）」として、
  予約ページと同じ空き枠から **直近3日** を日付ボタンで出す。押すと予約ページへ行き、
  「エアコン（ノーマル）1台」と押した日が選ばれた状態でカレンダー（2/4）から始まる。

それ以外（見出し・写真・料金・クチコミ・主ボタン・固定バー・フォーム）は aircon-c と1文字も変えない。
因果を読むため。写真も変えない。

## しくみ

- 空き枠は https://yoyaku.onehitter.jp/slots.json（Apps Script 直結の関数。lp/booking-functions/slots.js）を読む。
  別ホストなので、関数に Access-Control-Allow-Origin: https://lp.onehitter.jp を足した（CMO 2026-10-10・未配信）。
  読めないとき（3.5秒）は Apps Script を JSONP で読む。どちらも取れない・古い（24時間超）・空き0なら
  **ブロックごと出さない**（＝対照と同じ画面になる。壊れた日付を見せない）
- 日付ボタンは a[data-yoyaku][data-place="slot_chip"]。ページに元からある2つの仕組みがそのまま効く：
  ① 押した瞬間に lp=aircon-e・src・cid・ag・gclid をURLへ載せる ② GA4 cta_click（link_position=slot_chip）
- 出したときに GA4 `slot_chip_view`（n＝出した日数）を1回送る。表示率（取れなかった割合）を見るため
- 予約ページ側は ?menu=ac1&date=YYYY-MM-DD を読んで 2/4 から始める（tools/build-booking.py・CMO 2026-10-10・未配信）

## 置き換えるもの（aircon-c → aircon-e）

canonical・og:url／フォーム名 reserve-aircon-e・送信先 /aircon-e/thanks.html・隠し欄 lp・引き継ぎの lp・受付番号の接頭辞／
計測の lp_variant C → E（lp_id は aircon のまま。GA4 で C と E を並べる）／
写真は ../aircon-c/img/ を参照（複製しない）。

**配信はしない。** 配信はオーナーの承認のあと、LP担当が deploy/netlify/aircon-e/ を含めて行う。
"""

import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

CSS = """
/* ===== 次のA/B 対抗案E：いちばん早い空き（tools/ab-aircon-e.py が足す） ===== */
.aki{margin:2px 0 2px;}
.aki-h{font-size:13px;font-weight:700;color:var(--text);text-align:center;margin:0 0 7px;}
.aki-h span{font-weight:500;color:var(--steel);font-size:11.5px;}
.aki-row{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;}
.aki-chip{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:1px;min-height:52px;
  border:1.5px solid var(--ink);border-radius:10px;background:#fff;color:var(--ink);text-decoration:none;line-height:1.25;}
.aki-chip b{font-size:15px;font-weight:700;}
.aki-chip span{font-size:12px;font-weight:500;color:var(--text-2);}
.aki-chip:active{background:var(--paper-2);}
.aki-toki{font-size:10.5px;color:var(--steel);text-align:center;margin:5px 0 0;}
"""

HTML = """
      <div class="aki" id="aki" hidden>
        <p class="aki-h">いちばん早い空き<span>（エアコン1台・60分の場合）</span></p>
        <div class="aki-row" id="aki-row"></div>
        <p class="aki-toki" id="aki-toki"></p>
      </div>"""

JS = r"""
<script>
/* 次のA/B 対抗案E：いちばん早い空き（tools/ab-aircon-e.py が足す。docs/LP-次のABテスト-2026-10.md）
   予約ページと同じ空き枠から直近3日を出す。取れない・古い・0件ならブロックごと出さない。 */
(function () {
  var SLOTS = 'https://yoyaku.onehitter.jp/slots.json';
  var API = 'https://script.google.com/macros/s/AKfycbzuuMGVICQPoLlUrFBarb1zAgi_kVdc1vDrRJoyhAJ_tvOG-eHnmTHDGWhuvix3E3_odQ/exec';
  var YOYAKU = 'https://yoyaku.onehitter.jp/';
  var MINUTES = 60, MISERU = 3, FURUI_JIKAN = 24, SAITAN_NICHI = 1;   // SAITAN_NICHI は予約ページと同じ（最短翌日）
  var box = document.getElementById('aki'), row = document.getElementById('aki-row');
  if (!box || !row) return;

  function kyouPlus(n) {
    var d = new Date(); d.setDate(d.getDate() + n);
    return d.getFullYear() + '-' + ('0' + (d.getMonth() + 1)).slice(-2) + '-' + ('0' + d.getDate()).slice(-2);
  }
  function mijikai(d) {   // "2026-10-13" ＋ label の曜日 → "10/13（火）"
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(d.date || ''); if (!m) return '';
    var y = /（(.)）/.exec(d.label || '');
    return parseInt(m[2], 10) + '/' + parseInt(m[3], 10) + (y ? '（' + y[1] + '）' : '');
  }
  function egaku(list, toki) {
    var kagiri = kyouPlus(SAITAN_NICHI);
    var days = (list || []).filter(function (d) {
      return d && /^\d{4}-\d{2}-\d{2}$/.test(d.date || '') && d.date >= kagiri && d.times && d.times.length &&
             /^\d{1,2}:\d{2}$/.test(String(d.times[0]));
    }).slice(0, MISERU);
    if (!days.length) return;
    row.innerHTML = '';
    days.forEach(function (d) {
      var a = document.createElement('a');
      a.className = 'aki-chip';
      a.href = YOYAKU + '?menu=ac1&date=' + d.date;
      a.setAttribute('data-yoyaku', '');
      a.setAttribute('data-place', 'slot_chip');
      var b = document.createElement('b'); b.textContent = mijikai(d);
      var s = document.createElement('span'); s.textContent = String(d.times[0]) + '〜';
      a.appendChild(b); a.appendChild(s); row.appendChild(a);
    });
    var t = document.getElementById('aki-toki');
    if (t) t.textContent = (toki ? toki + ' 時点。' : '') + '押すと、その日の空き時間から選べます';
    box.hidden = false;
    try {
      var P = (window.OH_M || {}).page || {};
      if (typeof window.gtag === 'function') window.gtag('event', 'slot_chip_view',
        { n: days.length, lp_id: P.lp_id, lp_variant: P.lp_variant, page_kind: P.kind });
    } catch (e) {}
  }
  function jsonp(url, ms) {
    return new Promise(function (res, rej) {
      var name = '__aki' + Date.now(), sc = document.createElement('script');
      var t = setTimeout(function () { owari(); rej(new Error('timeout')); }, ms);
      function owari() { clearTimeout(t); try { delete window[name]; } catch (e) { window[name] = undefined; } if (sc.parentNode) sc.parentNode.removeChild(sc); }
      window[name] = function (d) { owari(); res(d); };
      sc.onerror = function () { owari(); rej(new Error('network')); };
      sc.src = url + '&callback=' + name;
      document.body.appendChild(sc);
    });
  }
  function apiKaraYomu() {
    return jsonp(API + '?action=slots&minutes=' + MINUTES, 6000).then(function (d) {
      if (!d || !d.ok) throw new Error('ng');
      egaku(d.slots || [], '');
    });
  }
  var ctl = ('AbortController' in window) ? new AbortController() : null;
  var tm = setTimeout(function () { if (ctl) ctl.abort(); }, 3500);
  fetch(SLOTS + '?t=' + Date.now(), ctl ? { cache: 'no-store', signal: ctl.signal } : { cache: 'no-store' })
    .then(function (r) { clearTimeout(tm); if (!r.ok) throw new Error('http ' + r.status); return r.json(); })
    .then(function (d) {
      var g = Date.parse(d && d.generated);
      if (isNaN(g) || (Date.now() - g) / 3600000 > FURUI_JIKAN) throw new Error('furui');
      var k = String(MINUTES);
      egaku((d.buckets || {})[k] || [], d.generatedLabel || '');
    })
    .catch(function () { apiKaraYomu().catch(function () { /* 出さない＝対照と同じ画面 */ }); });
})();
</script>
"""


def kaeru(s: str, old: str, new: str, count: int = 1, regex: bool = False) -> str:
    n = len(re.findall(old, s)) if regex else s.count(old)
    if n != count:
        sys.exit(f"想定と違う：{old[:70]!r} が {n} か所（{count} か所のはず）。aircon-c の配信物が変わった可能性。止めます")
    return re.sub(old, new, s) if regex else s.replace(old, new)


def make_index(h: str) -> str:
    h = kaeru(h, '<link rel="canonical" href="https://lp.onehitter.jp/aircon-c/">',
                 '<link rel="canonical" href="https://lp.onehitter.jp/aircon-e/">')
    h = kaeru(h, '<meta property="og:url" content="https://lp.onehitter.jp/aircon-c/">',
                 '<meta property="og:url" content="https://lp.onehitter.jp/aircon-e/">')
    h = kaeru(h, 'name="reserve-aircon-c"', 'name="reserve-aircon-e"')
    h = kaeru(h, 'action="/aircon-c/thanks.html"', 'action="/aircon-e/thanks.html"')
    h = kaeru(h, '<input type="hidden" name="form-name" value="reserve-aircon-c">',
                 '<input type="hidden" name="form-name" value="reserve-aircon-e">')
    h = kaeru(h, '<input type="hidden" name="lp" value="aircon-c">', '<input type="hidden" name="lp" value="aircon-e">')
    h = kaeru(h, "var hikitsugu = { lp: 'aircon-c',", "var hikitsugu = { lp: 'aircon-e',")
    h = kaeru(h, "-aircon-c-'", "-aircon-e-'")
    h = kaeru(h, '"lp_id":"aircon","lp_variant":"C"', '"lp_id":"aircon","lp_variant":"E"')
    h = kaeru(h, "'lp_id':'aircon','lp_variant':'C'", "'lp_id':'aircon','lp_variant':'E'")
    # 写真は aircon-c のものを参照（複製しない）
    h = re.sub(r'(src|href)="img/', r'\1="/aircon-c/img/', h)
    h = re.sub(r"url\((['\"]?)img/", r"url(\1/aircon-c/img/", h)
    # 1か所だけの違い：主ボタンの上に「いちばん早い空き」
    h = kaeru(h, '.hero-tel .num{font-size:17px;}\n', '.hero-tel .num{font-size:17px;}\n' + CSS)
    h = kaeru(h, '<p class="cta-lead">入力は1分・<b>予約時のお支払いはありません</b></p>',
                 '<p class="cta-lead">入力は1分・<b>予約時のお支払いはありません</b></p>' + HTML)
    h = kaeru(h, '</body>', JS + '</body>')
    if 'aircon-c' in re.sub(r'/aircon-c/img/', '', h):
        rest = sorted(set(re.findall(r'.{0,40}aircon-c.{0,40}', re.sub(r'/aircon-c/img/', '', h))))
        sys.exit('aircon-c が残っている：\n' + '\n'.join(rest))
    return h


def make_thanks(h: str) -> str:
    h = kaeru(h, '"lp_id":"aircon","lp_variant":"C"', '"lp_id":"aircon","lp_variant":"E"')
    h = kaeru(h, "'lp_id':'aircon','lp_variant':'C'", "'lp_id':'aircon','lp_variant':'E'")
    h = kaeru(h, 'href="/aircon-c/"', 'href="/aircon-e/"')
    h = re.sub(r'(src|href)="img/', r'\1="/aircon-c/img/', h)
    return h


def tenken(out: pathlib.Path) -> list:
    ng = []
    h = (out / 'index.html').read_text(encoding='utf-8')
    for k in ['id="aki"', 'data-place="slot_chip"' if False else 'slot_chip', '"lp_variant":"E"', 'reserve-aircon-e',
              "lp: 'aircon-e'", '?menu=ac1&date=']:
        if k not in h:
            ng.append(f'index.html に {k} が無い')
    for bad in ['98.8', '080-1755-7275', '23件', 'one-hitter.jp/privacy_policy']:
        if bad in h:
            ng.append(f'index.html に使ってはいけない {bad} がある')
    t = (out / 'thanks.html').read_text(encoding='utf-8')
    if '"lp_variant":"E"' not in t:
        ng.append('thanks.html の lp_variant が E でない')
    return ng


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', default=str(ROOT / 'deploy' / 'netlify' / 'aircon-c'))
    ap.add_argument('--out', default=str(ROOT / 'deploy' / 'netlify' / 'aircon-e'))
    ap.add_argument('--check', action='store_true', help='作らずに --out を点検だけする')
    a = ap.parse_args()
    src, out = pathlib.Path(a.src), pathlib.Path(a.out)
    if not a.check:
        if not (src / 'index.html').exists():
            sys.exit(f'{src}/index.html がありません。LP担当のブランチ（claude/lp-haishin-20261009 以降）の配信物を指してください')
        out.mkdir(parents=True, exist_ok=True)
        (out / 'index.html').write_text(make_index((src / 'index.html').read_text(encoding='utf-8')), encoding='utf-8')
        (out / 'thanks.html').write_text(make_thanks((src / 'thanks.html').read_text(encoding='utf-8')), encoding='utf-8')
        print(f'書き出しました: {out}/index.html, thanks.html（写真は /aircon-c/img/ を参照）')
    ng = tenken(out)
    if ng:
        print('NG:\n  ' + '\n  '.join(ng))
        sys.exit(1)
    print('点検OK（このあと python3 tools/check-public-page.py で公開ページの点検も通すこと）')


if __name__ == '__main__':
    main()
