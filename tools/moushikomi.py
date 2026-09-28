#!/usr/bin/env python3
"""LP申込フォームに「人が読める申込内容」と見積の項目を足す。依頼 20260928-02-lp。

オーナー指示（2026-09-28）：
  「エアコン含めて申込フォームの台数カウントできないの致命的だよね？
    lp広告回ってるから既存フォームを壊さない様に修正して。
    あと、僕と和真への通知も申込内容がそのまま理解できるようにしたいんだけど。」

【何をするか】
  1. フォームの subject の直後に隠し項目を足す（Netlifyは配信時のHTMLにある項目しか受け取らない）
       申込内容  … 人が読む1通の要約（改行区切り）。通知メールで最初に目に入る位置
       見積総額  … 数字だけ（画面に出ていなければ空）
       見積内訳  … 画面の内訳そのまま
       見積操作  … シミュレーターを触ったか（あり／未操作）
       エアコン系：台数・タイプ・オプション・繁忙期／水まわり系：箇所数
  2. 送信の瞬間に、**画面に出している計算結果を読み取って**入れる。計算は二重に持たない
  3. 既存の name・form-name・action・thanks・計測は1つも変えない／消さない

【なぜ「見積操作」が要るか】
  シミュレーターには初期値がある（エアコン：ノーマル×1台、水まわり：浴室＋キッチン）。
  触らずに申し込んだ人も、初期値を頼んだように見えてしまう。

【使い方】
  build-site.py が書き出す直前に apply() を呼ぶ（v2 を含む今後のビルドでも残る）。
  いま本番にある配信物だけを直すときは：
    python3 tools/moushikomi.py deploy/netlify/{aircon,aircon-b,mizumawari,nenmatsu}/index.html
  何度かけても同じ結果になる（2回目以降は何もしない）。
"""
import pathlib
import re
import sys

# ページごとの設定。キーは lp/ のディレクトリ名（= PAGES の dir）
PAGE = {
    "aircon":     {"kind": "aircon",  "label": "エアコンLP"},
    "aircon-b":   {"kind": "aircon",  "label": "エアコンLP（B）"},
    "mizumawari": {"kind": "builder", "label": "水まわりセット", "menu": "水まわりセット"},
    "nenmatsu":   {"kind": "builder", "label": "年末大掃除LP",   "menu": "年末大掃除", "nenmatsu": True},
}

MARK = 'data-oh="moushikomi"'
SUBJECT = re.compile(r'(\n([ \t]*)<input type="hidden" name="subject" value="[^"]*">)')

FIELDS = {
    "aircon":  ["申込内容", "見積総額", "見積内訳", "見積操作", "台数", "タイプ", "オプション", "繁忙期"],
    "builder": ["申込内容", "見積総額", "見積内訳", "見積操作", "箇所数"],
}

JS = r"""<script MARK>
/* 申込内容のまとめ（tools/moushikomi.py が差し込む。依頼 20260928-02-lp）
   送信の瞬間に「画面に出している見積」を読み取って隠し項目に入れる。計算はしない。 */
(function(){
  var f = document.querySelector('form.form'); if (!f) return;
  var KIND = 'KIND_', LABEL = 'LABEL_', MENU = 'MENU_', NENMATSU = NENMATSU_;
  var sousa = false;
  var box = KIND === 'aircon' ? document.querySelector('.calc') : document.getElementById('picks');
  if (box) box.addEventListener('change', function(){ sousa = true; });

  function put(n, v){ var e = f.querySelector('input[name="' + n + '"]'); if (e) e.value = v; }
  function val(n){ var e = f.querySelector('[name="' + n + '"]'); return e ? String(e.value || '').trim() : ''; }
  // <br> を改行にしてから文字だけ取り出す（表示の状態に左右されない）
  function lines(el){
    if (!el) return [];
    var d = document.createElement('div');
    d.innerHTML = el.innerHTML.replace(/<br\s*\/?>/gi, '\n');
    return (d.textContent || '').split('\n').map(function(s){ return s.replace(/\s+/g, ' ').trim(); })
      .filter(function(s){ return s; });
  }
  function text(el){ return el ? (el.textContent || '').replace(/\s+/g, ' ').trim() : ''; }
  // 端末の時計の設定に関係なく日本時間で書く
  function nichiji(){
    var d = new Date();
    try {
      return new Intl.DateTimeFormat('ja-JP', { timeZone: 'Asia/Tokyo', year: 'numeric', month: '2-digit',
        day: '2-digit', hour: '2-digit', minute: '2-digit' }).format(d);
    } catch (e) {
      var p = function(n){ return (n < 10 ? '0' : '') + n; };
      return d.getFullYear() + '/' + p(d.getMonth() + 1) + '/' + p(d.getDate()) + ' ' + p(d.getHours()) + ':' + p(d.getMinutes());
    }
  }

  f.addEventListener('submit', function(){
    try {
      var totalTxt = text(document.getElementById('total'));
      var total = /[0-9]/.test(totalTxt) ? totalTxt.replace(/[^0-9]/g, '') : '';
      var top = [], uchi = [];
      if (!sousa) top.push('※料金シミュレーターは操作されていません（初期値のまま）');

      if (KIND === 'aircon') {
        var t = document.querySelector('input[name=type]:checked');
        var tname = t ? String(t.parentNode.querySelector('span').firstChild.nodeValue || '').trim() : '';
        var q = document.querySelector('input[name=qty]:checked');
        var qname = q ? text(q.parentNode.querySelector('span')) : '';
        var pk = document.querySelector('input[name=peak]:checked');
        var peak = pk && pk.value !== '0';
        var opts = [];
        document.querySelectorAll('.calc input.opt:checked').forEach(function(o){ opts.push(o.dataset.nm); });
        uchi = lines(document.getElementById('breakdown'));

        top.push('エアコンクリーニング（' + tname + '）× ' + qname);
        top.push('オプション：' + (opts.length ? opts.join('、') + ' × ' + qname : 'なし'));
        if (peak) top.push('繁忙期（5〜7月・12月）：あり');
        uchi.forEach(function(s){ if (s.indexOf('特典') !== -1) top.push(s); });
        put('台数', q ? (q.value === '4' ? '4台以上' : q.value) : '');
        put('タイプ', tname);
        put('オプション', opts.length ? opts.join('、') : 'なし');
        put('繁忙期', peak ? 'あり' : 'なし');
        var menu = val('menu');
        if (menu && menu !== 'エアコンクリーニング（' + tname + '）') top.push('フォームで選んだメニュー：' + menu);
      } else {
        var chosen = Array.prototype.slice.call(document.querySelectorAll('#picks input:checked'));
        chosen.forEach(function(p){
          var cell = p.parentNode.querySelector('[data-role=pr]');
          var em = cell ? cell.querySelector('em') : null;
          var kind = text(em), price = text(cell).replace(kind, '').trim();
          uchi.push('・' + p.dataset.nm + ' ' + price + (kind ? '（' + kind + '）' : ''));
        });
        ['single', 'saved'].forEach(function(id){
          var v = document.getElementById(id);
          if (v && v.parentNode) uchi.push(text(v.parentNode.firstElementChild) + ' ' + text(v));
        });
        top.push(MENU + '（' + (chosen.length ? chosen.length + '箇所' : '箇所の選択なし') + '）');
        chosen.forEach(function(p){ top.push('・' + p.dataset.nm); });
        put('箇所数', String(chosen.length));
      }

      if (total) top.push('見積総額 ' + Number(total).toLocaleString('ja-JP') + '円（税込）');
      if (KIND === 'aircon' && uchi.join('').indexOf('4台以上') !== -1) top.push('※4台以上は個別にお見積り');
      if (KIND !== 'aircon') top.push('※この見積に繁忙期加算は含みません（5〜7月・12月は1箇所につき+3,300円）');
      if (NENMATSU) top.push('※11月30日までのご予約は通常価格（申込日で判断）');
      top.push('ご希望の時期：' + (val('when') || '（記入なし）'));
      top.push('');
      top.push('【見積の内訳（画面の表示）】');
      top = top.concat(uchi.length ? uchi : ['（なし）']);
      top.push('');
      top.push('お名前：' + val('name') + '／電話：' + val('tel') + '／郵便番号：' + val('zip'));
      top.push('申込日時：' + nichiji() + '／' + LABEL + (val('order_id') ? '／受付番号 ' + val('order_id') : ''));

      put('申込内容', top.join('\n'));
      put('見積総額', total);
      put('見積内訳', uchi.join('\n'));
      put('見積操作', sousa ? 'あり' : '未操作');
    } catch (e) {
      /* まとめが作れなくても、申し込みそのものは止めない */
      put('申込内容', '（申込内容のまとめを作れませんでした。各項目をご確認ください）');
    }
  });
})();
</script>"""


def apply(doc: str, name: str) -> str:
    """doc（書き出す直前のHTML）に隠し項目とまとめのスクリプトを足す。"""
    if name not in PAGE:
        return doc
    if MARK in doc:
        return doc  # もう入っている
    cfg = PAGE[name]
    m = SUBJECT.search(doc)
    if not m:
        raise SystemExit(f"{name}: フォームの subject が見つかりません。申込内容の項目を足せないので止めます。")
    if doc.count('name="subject"') != 1:
        raise SystemExit(f"{name}: subject が複数あります。どのフォームに足すか決められないので止めます。")
    indent = m.group(2)
    inputs = "".join(f'\n{indent}<input type="hidden" name="{n}" value="">' for n in FIELDS[cfg["kind"]])
    doc = doc[:m.end()] + inputs + doc[m.end():]

    js = (JS.replace("MARK", MARK)
            .replace("KIND_", cfg["kind"])
            .replace("LABEL_", cfg["label"])
            .replace("MENU_", cfg.get("menu", ""))
            .replace("NENMATSU_", "true" if cfg.get("nenmatsu") else "false"))
    # 受付番号（order_id）のスクリプトより後に登録する＝送信時に後から動く
    i = doc.rindex("</body>")
    return doc[:i] + js + "\n" + doc[i:]


def main(paths) -> None:
    for s in paths:
        p = pathlib.Path(s)
        name = p.parent.name
        before = p.read_text(encoding="utf-8")
        after = apply(before, name)
        if after == before:
            print(f"{p}  変更なし（入っているか、対象外）")
            continue
        p.write_text(after, encoding="utf-8")
        print(f"{p}  隠し項目 {len(FIELDS[PAGE[name]['kind']])} 個とまとめのスクリプトを追加")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
