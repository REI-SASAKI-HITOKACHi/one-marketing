#!/usr/bin/env python3
"""担当（渡辺さん）のイラストを本番の全LPに差し込む（依頼 20261107-01-lp・嶺さん 11/7 配信OK）。

    python3 tools/staff-honban-1107.py          # deploy/netlify/ の LP 10本に差し込む（2回流しても重ならない）

- 画像は lp/_staff/staff.jpg の1か所（嶺さん GPT 版・第一候補 600×600）。各ページの img/staff.jpg に写す
- 置き場所：「Who comes（伺うのは…／下請けに出しません）」の見出しの直下。年末LP（nenmatsu）はその欄が無いので、
  「WEB予約・お見積り」の見出しの直下（申込の直前＝迷うところに人の顔）
- 形は学習版（lp/aircon-c の staff-il）と同じ：132px の丸＋「品質管理責任者：渡辺」＋一言（フルネームは出さない＝嶺さん 11/7）。CSS が無いページには足す
- 元は本番と同じ deploy/netlify（11/7 に本番を取得して、違いは Netlify のフォーム書き換えだけと確認）
"""
import pathlib
import re
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
NETLIFY = ROOT / "deploy" / "netlify"
STAFF = ROOT / "lp" / "_staff" / "staff.jpg"
PAGES = ["aircon", "aircon-b", "aircon-c", "aircon-d", "aircon-e", "kabi", "mizumawari", "mizumawari-b", "nenmatsu", "nenmatsu-b"]

FIG = ('    <figure class="staff-il"><img src="img/staff.jpg" width="132" height="132" '
       'alt="当日伺う担当、渡辺のイラスト" loading="lazy" decoding="async">'
       '<figcaption><b>品質管理責任者：渡辺</b>当日伺う担当です。ご連絡から作業当日まで、担当は変わりません。</figcaption></figure>\n')
CSS = ('<style>/* 担当のイラスト（tools/staff-honban-1107.py） */'
       '.staff-il{margin:0 0 22px;display:flex;gap:16px;align-items:center;}'
       '.staff-il img{width:132px;height:132px;aspect-ratio:1/1;border-radius:50%;object-fit:cover;background:#F2EFE9;flex:none;}'
       '.staff-il figcaption{font-size:14px;line-height:1.75;color:inherit;opacity:.88;}'
       '.staff-il figcaption b{display:block;font-size:16px;opacity:1;}</style>\n')
MARK = 'class="staff-il"><img src="img/staff.jpg"'


def sashikomu(h, name):
    if MARK in h:
        return h, "済み"
    if name == "nenmatsu":
        m = re.search(r'<h2>WEB予約・お見積り</h2>.*?\n    </div>\n', h, re.S)
    else:
        m = re.search(r'<span class="eyebrow">Who comes</span>.*?\n    </div>\n', h, re.S)
    if not m:
        sys.exit(f"[{name}] 差し込む場所が見つからない。止めます")
    h = h[:m.end()] + FIG + h[m.end():]
    if ".staff-il{" not in h:
        h = h.replace("</head>", CSS + "</head>", 1)
    return h, "差し込み"


def main():
    if not STAFF.exists():
        sys.exit("lp/_staff/staff.jpg が無い。止めます")
    for name in PAGES:
        f = NETLIFY / name / "index.html"
        h, kekka = sashikomu(f.read_text(encoding="utf-8"), name)
        f.write_text(h, encoding="utf-8")
        img = NETLIFY / name / "img"
        img.mkdir(exist_ok=True)
        shutil.copy2(STAFF, img / "staff.jpg")
        print(f"{name}: {kekka}（figure {h.count(MARK)}）")


if __name__ == "__main__":
    main()
