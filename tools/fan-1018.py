#!/usr/bin/env python3
"""エアコンの作業説明の「ファンを取り外します」を、標準作業どおりに直す（依頼 20261017-04-lp・CMO 10/18）。

  python3 tools/fan-1018.py <HTML> ...          # その場で書き換える（2回目以降は何もしない）
  python3 tools/fan-1018.py --check <HTML> ...  # 残っていないかだけ見る

和真さん（業務連絡LINE 330・10/17 11:47）原文「ファンの取り外しは完全分解のオプションがある時のみだよ。」
標準（10,780円）はカバーとルーバーを外し、送風ファンは付けたまま専用の機材で洗う。
"""
import pathlib, re, sys

OKIKAE = [
    ('<li><b>分解</b><p>カバー・ルーバー・ファンを取り外します。</p></li>',
     '<li><b>取り外し</b><p>カバーとルーバーを外します。送風ファンは付けたまま、専用の機材で奥まで洗います'
     '（ファンを外しての洗浄は、完全分解のオプションのときです）。</p></li>'),
    ('<li><b>組み立て</b><p>分解した部品を元通りに戻します。</p></li>',
     '<li><b>取り付け</b><p>外したカバーとルーバーを元通りに戻します。</p></li>'),
    ('可能です。分解・洗浄・組み立てまで行い、原状に戻して', '可能です。カバーの取り外し・洗浄・取り付けまで行い、原状に戻して'),
    # 今の版（aircon・aircon-b）の言い回し
    ('<li><div><b>分解</b><p>カバー・ルーバー・ファンを取り外し</p></div></li>',
     '<li><div><b>取り外し</b><p>カバーとルーバーを外す（送風ファンは付けたまま）</p></div></li>'),
    ('<li><div><b>組み立て</b><p>分解した部品を元通りに</p></div></li>',
     '<li><div><b>取り付け</b><p>外したカバーとルーバーを元通りに</p></div></li>'),
    ('送風ファンを取り外し、熱交換器の奥まで専用機材で洗浄します。', 'カバーを外し、熱交換器と送風ファンの奥まで専用機材で洗浄します。'),
    ('エアコンを分解し、熱交換器と送風ファンを専用機材で洗浄。', 'カバーを外し、熱交換器と送風ファンを専用機材で洗浄。'),
    ('送風ファンを取り外し、熱交換器の奥まで分解洗浄', 'カバーを外し、熱交換器と送風ファンの奥まで洗浄'),
    ('エアコンを分解し、', 'エアコンのカバーを外し、'),
]
FURUI = re.compile(r'ファンを取り外し|分解・洗浄・組み立て|分解した部品|エアコンを分解し')


def apply(s):
    for a, b in OKIKAE:
        s = s.replace(a, b)
    return s


def nokori(s):
    return sorted(set(FURUI.findall(re.sub(r'<style[^>]*>.*?</style>', '', s, flags=re.S))))


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
