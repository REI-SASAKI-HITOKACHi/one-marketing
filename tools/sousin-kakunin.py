#!/usr/bin/env python3
"""LPの予約フォームに「送信元の確認」の隠し欄を足す（依頼 20261008-01-lp）。

  python3 tools/sousin-kakunin.py deploy/netlify/<ページ>/index.html ...   # 書き換える（2回目以降は何もしない）

なぜ：10/8 04:24、python-requests から mizumawari のフォームへ、全項目が空の送信が届いた。
ハニーポット（x_field）は全LPに入っているが、ボットがその欄を送らなければ素通りする。
Netlify Forms は受け取り側で中身を検査できないので、**ブラウザで送ったときだけ埋まる欄**を足し、
取り込み側（予約_Web）で「この欄が空＝プログラムからの直接送信」と機械的に分けられるようにする。

- 値：「ブラウザ（入力 N秒）」。送信ボタンの submit のときにだけ入る（画面の必須チェックを通った後）
- 画面には何も出ない。文言・構成は変えない
- 送信の拒否はしない（拒否すると、JSが動かない環境の本物のお客様まで落とすため）
"""
import pathlib
import re
import sys

NAME = "送信元の確認"
MARK = f'name="{NAME}"'
SUBJECT = re.compile(r'(\n([ \t]*)<input type="hidden" name="subject" value="[^"]*">)')

JS = """<script>
/* 送信元の確認（tools/sousin-kakunin.py）。ブラウザで送ったときだけ埋まる。空なら機械的な直接送信 */
(function(){
  var f = document.querySelector('form.form'); if (!f) return;
  var t0 = Date.now();
  f.addEventListener('submit', function(){
    var e = f.querySelector('input[name="NAME_"]');
    if (e) e.value = 'ブラウザ（入力 ' + Math.round((Date.now() - t0) / 1000) + '秒）';
  });
})();
</script>""".replace("NAME_", NAME)


def apply(doc: str) -> str:
    if MARK in doc:
        return doc
    m = SUBJECT.search(doc)
    if not m or doc.count('name="subject"') != 1:
        return doc  # 予約フォームの無いページ（アンケート等）は対象外
    doc = doc[:m.end()] + f'\n{m.group(2)}<input type="hidden" {MARK} value="">' + doc[m.end():]
    i = doc.rindex("</body>")
    return doc[:i] + JS + "\n" + doc[i:]


def main(paths):
    for s in paths:
        p = pathlib.Path(s)
        before = p.read_text(encoding="utf-8")
        after = apply(before)
        print(f"{p}  {'追加' if after != before else '変更なし'}")
        if after != before:
            p.write_text(after, encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
