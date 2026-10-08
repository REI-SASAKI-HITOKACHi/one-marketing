#!/usr/bin/env python3
"""広告LPの「申込の入口」を予約ページ（カレンダー）に寄せる（依頼 20261008-05-lp）。

  python3 tools/iriguchi.py <ページ名> 元.html 出力.html     # aircon / aircon-c / mizumawari / mizumawari-b

なぜ：measurement の判定表（10/9）で、広告LPを見た人の94〜100%がLP内フォームに手を付けずに離れていた
（入力開始率 aircon 2%・aircon-c 6%・mizumawari 3%・mizumawari-b 0%）。一方、予約ページは4閲覧で申込1。
LPを読んだあと「電話番号を渡す前に空いている日と金額を見たい」人を、予約ページへまっすぐ通す。

やること（ボタンの数は増やさない＝ファーストビューの高さを変えない。見た目の作り替えはしない）：
- ヘッダーの「WEB予約」 → 予約ページへ
- ファーストビューの主ボタン → 「空いている日を見て予約する」（予約ページ）
  学習版は「よくある頼み方と金額を見る」を、その下の小さい文字リンクにする
- 画面下の固定バーの右ボタン → 「空き日を見る」（予約ページ）
- 今の版の料金計算の下の「この内容で予約に進む」 → 2択（予約ページ／フォーム）。学習版は 10/1 から2択
- LP内のフォームはそのまま残す（2つ目の道）
- 予約ページへのクリックは cta_click（link_target=yoyaku・link_position=header/hero/sticky/estimate）
- どのLPから来たか（lp=）は、各LPの「別ホストへの引き継ぎ」がクリックの瞬間に付ける（b03a1288）

★配信はオーナー承認後。承認までは preview/iriguchi/ でだけ確認する。
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
Y = "https://yoyaku.onehitter.jp/"
MARK = 'data-oh="iriguchi"'

KYOTSU = [
    ('<a class="btn" href="#form">WEB予約</a>',
     f'<a class="btn" href="{Y}" data-yoyaku data-place="header">WEB予約</a>'),
]
STICKY = {
    "form": ('<a class="btn" href="#form">WEB予約する<small>入力5項目</small></a>',
             f'<a class="btn" href="{Y}" data-yoyaku data-place="sticky">空き日を見る<small>そのまま予約</small></a>'),
    "builder": ('<a class="btn" href="#builder">料金を見る<small>その場で確定</small></a>',
                f'<a class="btn" href="{Y}" data-yoyaku data-place="sticky">空き日を見る<small>料金もその場で</small></a>'),
}
HERO = {
    "aircon": ('<a class="btn lg" href="#form">かんたん5項目でWEB予約する</a>',
               f'<a class="btn lg" href="{Y}" data-yoyaku data-place="hero">空いている日を見て予約する</a>'),
    "mizumawari": ('<a class="btn lg" href="#builder">箇所を選んで、料金を見る</a>',
                   f'<a class="btn lg" href="{Y}" data-yoyaku data-place="hero">空いている日と料金を見る</a>'),
    "learned": ('<a class="btn lg" href="#rei">よくある頼み方と金額を見る</a>',
                f'<a class="btn lg" href="{Y}" data-yoyaku data-place="hero">空いている日を見て予約する</a>'
                '\n      <a class="iri-sub" href="#rei">よくある頼み方と金額を見る</a>'),
}
ESTIMATE_OLD = ('<a class="btn lg" href="#form">この内容で予約に進む</a>',
                f'<div class="iri-go2"><a class="btn lg" href="{Y}" data-yoyaku data-place="estimate">空いている日を見て予約する</a>'
                '<a class="btn lg ghost" href="#form">この内容でフォームから申し込む</a></div>')

PAGES = {
    "aircon":       {"hero": "aircon", "sticky": "form", "estimate": True},
    "mizumawari":   {"hero": "mizumawari", "sticky": "builder", "estimate": True},
    "aircon-c":     {"hero": "learned", "sticky": "form", "estimate": False},
    "mizumawari-b": {"hero": "learned", "sticky": "builder", "estimate": False},
}

CSS = """<style data-oh="iriguchi">
.iri-sub{display:block;text-align:center;margin-top:10px;font-size:14px;font-weight:700;color:var(--ink);text-decoration:underline;text-underline-offset:3px;}
.iri-go2{display:grid;gap:10px;width:100%;}
.iri-go2 .btn{width:100%;}
</style>"""

# 予約ページへのクリックの計測（学習版に 10/1 から入っているものと同じ形。今の版には無いので足す）
JS = """<script>
  /* 予約カレンダーへの直行ボタン（a[data-yoyaku]）のクリックを計測する（tools/iriguchi.py）。
     events.js の cta_click はページ内リンクしか拾わないので、別ホストへ出るボタンはここで送る */
  document.addEventListener('click', function (ev) {
    var a = ev.target && ev.target.closest ? ev.target.closest('a[data-yoyaku]') : null;
    if (!a) return;
    var M = window.OH_M || {}, P = M.page || {}, q;
    try { q = new URLSearchParams(location.search); } catch (e) { q = null; }
    var p = { link_position: a.getAttribute('data-place') || 'other', link_target: 'yoyaku',
              lp_id: P.lp_id, lp_variant: P.lp_variant, page_kind: P.kind,
              traffic_src: (q && q.get('src')) || 'direct', transport_type: 'beacon' };
    var cid = q && q.get('cid'); if (cid) p.traffic_cid = cid;
    if (typeof window.gtag === 'function') window.gtag('event', 'cta_click', p);
    if (typeof window.fbq === 'function') window.fbq('trackCustom', 'cta_click', p);
  }, true);
</script>"""


def rep(doc, a, b, page, what):
    if doc.count(a) != 1:
        raise SystemExit(f"{page}: {what} の差し替え先が {doc.count(a)} 個（1個のはず）。止めます")
    return doc.replace(a, b)


def apply(doc, page):
    if MARK in doc:
        return doc
    cfg = PAGES[page]
    for a, b in KYOTSU:
        doc = rep(doc, a, b, page, "ヘッダー")
    doc = rep(doc, *HERO[cfg["hero"]], page, "ファーストビュー")
    doc = rep(doc, *STICKY[cfg["sticky"]], page, "固定バー")
    if cfg["estimate"]:
        doc = rep(doc, *ESTIMATE_OLD, page, "料金の下")
    doc = doc.replace("</head>", CSS + "\n</head>", 1)
    if "予約カレンダーへの直行ボタン（a[data-yoyaku]）" not in doc:
        i = doc.rindex("</body>")
        doc = doc[:i] + JS + "\n" + doc[i:]
    if "hikitsugu = { lp:" not in doc:
        raise SystemExit(f"{page}: 予約ページへの引き継ぎ（lp=）が見当たりません")
    return doc


def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    page, src, dst = sys.argv[1], pathlib.Path(sys.argv[2]), pathlib.Path(sys.argv[3])
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(apply(src.read_text(encoding="utf-8"), page), encoding="utf-8")
    print(f"{page:13s} → {dst}")


if __name__ == "__main__":
    main()
