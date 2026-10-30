#!/usr/bin/env python3
"""年末の繁忙期加算・通常価格の線引きを「作業日」で書く（依頼 20261030-01-lp・11/1 切り替え点検で発見）。

  python3 tools/sagyoubi-1030.py <HTML> ...          # その場で書き換える（2回目以降は何もしない）
  python3 tools/sagyoubi-1030.py --check <HTML> ...  # 残っていないかだけ見る

なぜ：繁忙期加算（12月は1箇所+3,300円）と早期予約割引は、作業日の月で決まる（オーナー決定 10/16「早期予約は施工月で判定」・
予約ページの計算も作業日の月）。年末LPは「11月30日までのご予約なら通常価格」と予約した日で書いていて、11/20 に予約して
12/10 に作業する人には予約ページで +3,300円 が出る（説明と金額が食い違う）。LP のフォームの控えにも「申込日で判断」とあり、
現場がこの注記で見積もると決定と違う金額になる。
「年内にとお考えでしたら、11月中のご予約をおすすめします」は空き枠の話（値段ではない）なので変えない。
"""
import pathlib, re, sys

OKIKAE = [
    ("※11月30日までのご予約は通常価格（申込日で判断）", "※11月30日までの作業は通常価格（作業日で判断。12月の作業は1箇所につき+3,300円）"),
    ("11月30日までのご予約なら、この通常価格です。", "11月30日までの作業なら、この通常価格です。"),
    ("大きい金額は11月30日までのご予約の通常価格、「12月のご予約だと」は", "大きい金額は11月30日までの作業の通常価格、「12月の作業だと」は"),
    ("年末の大掃除は、11月までのご予約が安い", "年末の大掃除は、11月中の作業が安い"),
    ("11月30日までのご予約なら通常価格", "11月30日までの作業なら通常価格"),
    ("11月30日のご予約まで｜ONE HITTER", "11月30日の作業まで｜ONE HITTER"),
    ("12月のご予約だと", "12月の作業だと"),
]
NG = re.compile(r"申込日で判断|11月30日までのご予約|11月30日のご予約まで|11月までのご予約が安い|12月のご予約だと")


def apply(s):
    for a, b in OKIKAE:
        s = s.replace(a, b)
    return s


def nokori(s):
    return sorted(set(NG.findall(s)))


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
