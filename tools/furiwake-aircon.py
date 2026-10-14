#!/usr/bin/env python3
"""/aircon/ に来た人を、初回だけ 50/50 で /aircon-c/ か /aircon-e/ に振り分ける（依頼 20261014-01-lp）。

    python3 tools/furiwake-aircon.py                                   # preview/furiwake/aircon/index.html に書き出す（確認用）
    python3 tools/furiwake-aircon.py --out deploy/netlify/aircon/index.html   # 配信物に入れる（オーナーのOKのあと）

## なぜ

Google広告の実験（URL の更新）で C 対 E を出す予定だったが、広告の実験の編集ができない（10/12・10/13）。
CMO 判断で、LP 側で振り分ける（docs/cmo-savedata.md 10/12）。判定表は measurement の
docs/AB-エアコンC対E-判定表.md（GA4 のページ /aircon-c/・/aircon-e/、lp_variant C／E で数える）。

## しくみ

- /aircon/index.html の中身を **aircon-c の配信物の写し**にする（写真は /aircon-c/img/ を参照）。
  canonical・og:url・robots は今の /aircon/ と同じ（https://lp.onehitter.jp/aircon/・noindex,follow）
- <head> のいちばん上の小さなスクリプトが、振り分けて location.replace で移る
  - 1回目：Math.random() で c か e を決め、localStorage と Cookie（90日）に残す
  - 2回目以降：残っている版に移る（同じ人には同じ版）
  - どちらにも残せない（プライベートブラウズ等）：**C**（毎回同じ版にするため）
  - クエリ（src・cid・ag・gclid など）と # 以降は**一文字も変えずに**付けて移る
  - replace なので、戻るボタンで /aircon/ に戻ってまた飛ばされることはない
- JS が動かない人：移らず、そのまま C の中身が出る（フォームの送信先も C）
- /aircon/ では GA4 の config を送らない（移る前の page_view が /aircon/ に1つ増え、判定表のユーザー数が狂うため）。
  移り先の /aircon-c/・/aircon-e/ が、いつもどおり lp_variant C／E で page_view を送る
- 確認用：URL の最後に #ab-c／#ab-e を付けると、その版に固定して移る（# は広告からは付かない）

## 注意（GA4 の読み方）

- /aircon/ 経由の人は、移り先の参照元が lp.onehitter.jp（自サイト）になる。広告は gclid がクエリで引き継がれるので
  google / cpc のまま数えられる。gclid の無い入口（アフィリエイト・自然検索）の参照元は (direct) に寄る
- 写しは aircon-c から作るので、**aircon-c を直したら必ず作り直す**（作り直さないと、JS の動かない人だけ古い C を見る）
"""
import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
GA4 = "G-DLJCTKGTDN"
KEY = "oh_ab_aircon_ce"

SWITCH = """<script>
/* C 対 E の振り分け（tools/furiwake-aircon.py・依頼 20261014-01-lp）。初回だけ 50/50、同じ人には同じ版。
   残せないときは C。クエリと # はそのまま引き継ぐ。JS が動かなければ、この下の C の中身がそのまま出る */
(function () {
  var K = 'KEY_', ban = null, kaketa = false;
  var h = location.hash || '';
  var kotei = /^#ab-(c|e)$/.exec(h);
  function yomu() {
    try { var v = localStorage.getItem(K); if (v === 'c' || v === 'e') return v; } catch (e) {}
    var m = document.cookie.match(new RegExp('(?:^|; )' + K + '=([ce])'));
    return m ? m[1] : null;
  }
  function kaku(v) {
    try { localStorage.setItem(K, v); if (localStorage.getItem(K) === v) kaketa = true; } catch (e) {}
    try { document.cookie = K + '=' + v + '; max-age=7776000; path=/; SameSite=Lax; Secure';
          if (document.cookie.indexOf(K + '=' + v) >= 0) kaketa = true; } catch (e) {}
  }
  if (kotei) { ban = kotei[1]; kaku(ban); h = ''; }
  else { ban = yomu(); if (!ban) { ban = Math.random() < 0.5 ? 'c' : 'e'; kaku(ban); if (!kaketa) ban = 'c'; } }
  window.OH_FURIWAKE = ban;
  try { document.documentElement.style.visibility = 'hidden'; } catch (e) {}
  location.replace('/aircon-' + ban + '/' + location.search + h);
})();
</script>""".replace("KEY_", KEY)


def kaeru(s, old, new, count=1):
    n = s.count(old)
    if n != count:
        sys.exit(f"想定と違う：{old[:70]!r} が {n} か所（{count} か所のはず）。aircon-c の配信物が変わった可能性。止めます")
    return s.replace(old, new)


def make(c: str) -> str:
    h = c
    # 検索エンジン向けは今の /aircon/ と同じ
    h = kaeru(h, '<link rel="canonical" href="https://lp.onehitter.jp/aircon-c/">',
                 '<link rel="canonical" href="https://lp.onehitter.jp/aircon/">')
    h = kaeru(h, '<meta property="og:url" content="https://lp.onehitter.jp/aircon-c/">',
                 '<meta property="og:url" content="https://lp.onehitter.jp/aircon/">')
    if '<meta name="robots" content="noindex,follow">' not in h:
        sys.exit("aircon-c に noindex,follow が無い。止めます")
    # 写真は aircon-c のものを参照
    h = re.sub(r'(src|href)="img/', r'\1="/aircon-c/img/', h)
    h = re.sub(r"url\((['\"]?)img/", r"url(\1/aircon-c/img/", h)
    # 振り分けは <head> のいちばん上（ほかの何より先に動かす）
    h = kaeru(h, '<meta charset="utf-8">', '<meta charset="utf-8">\n' + SWITCH)
    # /aircon/ では GA4・広告の config を送らない（移る前の page_view を数えない）
    h = kaeru(h, f"gtag('config','{GA4}',", f"if(!window.OH_FURIWAKE)gtag('config','{GA4}',")
    h = kaeru(h, "gtag('config','AW-18450975194');", "if(!window.OH_FURIWAKE)gtag('config','AW-18450975194');")
    return h


def tenken(h: str) -> list:
    ng = []
    for k in ['<link rel="canonical" href="https://lp.onehitter.jp/aircon/">', 'noindex,follow',
              "location.replace('/aircon-' + ban + '/' + location.search + h)", '"lp_variant":"C"']:
        if k not in h:
            ng.append(f"{k} が無い")
    if re.search(r'(src|href)="img/', h):
        ng.append("img/ の相対参照が残っている（/aircon/img/ は今の版の写真）")
    if h.find(SWITCH) > h.find("googletagmanager"):
        ng.append("振り分けが gtag より後ろにある")
    return ng


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(ROOT / "deploy" / "netlify" / "aircon-c" / "index.html"))
    ap.add_argument("--out", default=str(ROOT / "preview" / "furiwake" / "aircon" / "index.html"))
    a = ap.parse_args()
    h = make(pathlib.Path(a.src).read_text(encoding="utf-8"))
    ng = tenken(h)
    if ng:
        sys.exit("NG:\n  " + "\n  ".join(ng))
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(h, encoding="utf-8")
    print(f"書き出しました: {out}（中身は aircon-c の写し＋振り分け）")


if __name__ == "__main__":
    main()
