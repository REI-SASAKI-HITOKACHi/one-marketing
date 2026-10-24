#!/usr/bin/env python3
"""汚水の写真・文から、台数・杯数を外す（全スレッドの決まり 20261021-04-lp）。

  python3 tools/osui-1024.py <HTML> ...          # その場で書き換える（2回目以降は何もしない）
  python3 tools/osui-1024.py --check <HTML> ...  # 残っていないかだけ見る

決まり（cmo 10/21）：汚水（バケツ・洗い出した水）の写真には「1台ぶん」「バケツ1杯」など台数・杯数を書かない。
どのバケツがどの台か記録が無いため（docs/photo-inventory-2026-09.md）。言えるのは「この日の作業で出た水」「洗い出した水」まで。
画面に出る文（figcaption）も、画像の説明（alt）も対象。
"""
import pathlib, re, sys

OKIKAE = [
    ('alt="洗浄で流れ出た汚水がバケツ一杯にたまっている"', 'alt="洗浄で流れ出た汚水"'),
    ('alt="回収した汚水がバケツ3つ分たまっている"', 'alt="回収した汚水"'),
    ('alt="1台のエアコンを洗浄して回収した、真っ黒な汚水がバケツ一杯にたまっている"', 'alt="この日の作業で洗い出した、真っ黒な汚水"'),
    ('<b>この水は、エアコン1台から出たものです。</b>', '<b>この水は、この日の作業で洗い出したものです。</b>'),
    ('alt="洗浄で出た汚水のバケツ"><figcaption>1台分</figcaption>', 'alt="洗浄で出た汚水のバケツ"><figcaption>回収した汚水</figcaption>'),   # lp/takara
]
NG = re.compile(r'(汚水|洗い出した水|バケツ)[^<>"]{0,30}([0-9一二三四五]+(杯|つ分)|一杯|台(ぶん|分))|[0-9一二三]台(ぶん|分|から出た)[^<>"]{0,10}(汚水|水)|エアコン1台から出た|>[0-9一二三]台(ぶん|分)<')


def apply(s):
    for a, b in OKIKAE:
        s = s.replace(a, b)
    return s


def nokori(s):
    return sorted(set(m.group(0) for m in NG.finditer(s)))


if __name__ == "__main__":
    args = sys.argv[1:]
    check = bool(args) and args[0] == "--check"
    bad = 0
    for p in map(pathlib.Path, args[1:] if check else args):
        s = p.read_text(encoding="utf-8")
        if not check:
            t = apply(s)
            if t != s:
                p.write_text(t, encoding="utf-8")
            s = t
        n = nokori(s)
        print(("NG " if n else "OK ") + str(p) + (f"：残っている {n}" if n else ""))
        bad += bool(n)
    sys.exit(1 if bad else 0)
