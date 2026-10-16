#!/usr/bin/env python3
"""/mizumawari/ に来た広告の人を、学習版 /mizumawari-b/ 7：今の版 3 に振り分ける（依頼 20261016-01-lp）。

    python3 tools/furiwake-mizumawari.py                                        # preview/furiwake/mizumawari/ に書き出す（確認用）
    python3 tools/furiwake-mizumawari.py --out deploy/netlify/mizumawari/index.html   # 配信物に当てる（オーナーのOKのあと）

## なぜ

第6回MTG 6-7 オーナー原文（F711・F713）「学習版のサンプルを増やしたいから配分を学習版に７：３で寄せて。」

## エアコン（tools/furiwake-aircon.py）との違い

- /mizumawari/ の中身は**今の版のまま**（写しにしない）。今の版に当たった人は移らず、そのまま見る
- **振り分けるのは Google 広告から来た人だけ**（URL に gclid／gbraid／wbraid がある、または src が gads で始まる）。
  /mizumawari/ はレントラックス（アフィリエイト）の登録先で、成果タグは今の版と、そのサンクスにしか入っていない
  （tracking/measurement.json の rentracks.pages）。アフィリエイトの人を学習版へ移すと成果が数えられなくなるので、
  広告以外の人（アフィリエイト・自然検索・QR・SMS など）は今までどおり今の版
- 学習版に移る人は、/mizumawari/ では GA4・広告の config を送らない（移る前の page_view を今の版に数えない）

## 共通

- 初回だけ 7:3（Math.random() < 0.7 で学習版）。localStorage と Cookie（90日）に残し、同じ人には同じ版
- 残せない人（プライベートブラウズ等）・JS が動かない人：今の版
- クエリと # は一文字も変えずに引き継ぐ（location.replace なので戻るボタンで往復しない）
- 確認用：URL の最後に #ab-b／#ab-a でその版に固定（広告で来たかどうかに関係なく効く）
- 自動操作のブラウザ（navigator.webdriver）は移さない＝今の版。tools/measure-production.py の点検が
  毎回同じ版を見るため（広告の gclid 付きで今の版を点検している）
"""
import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
GA4 = "G-DLJCTKGTDN"
AW = "AW-18450975194"
KEY = "oh_ab_mizumawari_ba"
MARK = "tools/furiwake-mizumawari.py"

SWITCH = """<script>
/* 学習版7：今の版3 の振り分け（MARK_・依頼 20261016-01-lp）。広告から来た人だけ。同じ人には同じ版。
   残せないとき・JS が動かないときは今の版（このページ）。クエリと # はそのまま引き継ぐ */
(function () {
  var K = 'KEY_', ban = null, kaketa = false, q;
  var h = location.hash || '';
  var kotei = /^#ab-(a|b)$/.exec(h);
  try { q = new URLSearchParams(location.search); } catch (e) { q = null; }
  var koukoku = !!(q && (q.get('gclid') || q.get('gbraid') || q.get('wbraid') || /^gads/.test(q.get('src') || '')));
  if (!kotei && (!koukoku || navigator.webdriver)) return;
  function yomu() {
    try { var v = localStorage.getItem(K); if (v === 'a' || v === 'b') return v; } catch (e) {}
    var m = document.cookie.match(new RegExp('(?:^|; )' + K + '=([ab])'));
    return m ? m[1] : null;
  }
  function kaku(v) {
    try { localStorage.setItem(K, v); if (localStorage.getItem(K) === v) kaketa = true; } catch (e) {}
    try { document.cookie = K + '=' + v + '; max-age=7776000; path=/; SameSite=Lax; Secure';
          if (document.cookie.indexOf(K + '=' + v) >= 0) kaketa = true; } catch (e) {}
  }
  if (kotei) { ban = kotei[1]; kaku(ban); h = ''; }
  else { ban = yomu(); if (!ban) { ban = Math.random() < 0.7 ? 'b' : 'a'; kaku(ban); if (!kaketa) ban = 'a'; } }
  if (ban !== 'b') { if (kotei) history.replaceState(null, '', location.pathname + location.search); return; }
  window.OH_FURIWAKE = 'b';
  try { document.documentElement.style.visibility = 'hidden'; } catch (e) {}
  location.replace('/mizumawari-b/' + location.search + h);
})();
</script>""".replace("KEY_", KEY).replace("MARK_", MARK)


def kaeru(s, old, new, count=1):
    n = s.count(old)
    if n != count:
        sys.exit(f"想定と違う：{old[:70]!r} が {n} か所（{count} か所のはず）。止めます")
    return s.replace(old, new)


def make(h: str) -> str:
    if MARK in h:
        return h
    if '"lp_id":"mizumawari","lp_variant":"A"' not in h:
        sys.exit("今の版の mizumawari（lp_variant A）ではないようです。止めます")
    h = kaeru(h, '<meta charset="utf-8">', '<meta charset="utf-8">\n' + SWITCH)
    h = kaeru(h, f"gtag('config','{GA4}',", f"if(!window.OH_FURIWAKE)gtag('config','{GA4}',")
    h = kaeru(h, f"gtag('config','{AW}');", f"if(!window.OH_FURIWAKE)gtag('config','{AW}');")
    return h


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(ROOT / "deploy" / "netlify" / "mizumawari" / "index.html"))
    ap.add_argument("--out", default=str(ROOT / "preview" / "furiwake" / "mizumawari" / "index.html"))
    a = ap.parse_args()
    h = make(pathlib.Path(a.src).read_text(encoding="utf-8"))
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(h, encoding="utf-8")
    print(f"書き出しました: {out}（今の版＋広告の人だけ 7:3 の振り分け）")


if __name__ == "__main__":
    main()
