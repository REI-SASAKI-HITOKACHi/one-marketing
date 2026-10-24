#!/usr/bin/env python3
"""聞かれていない否定・但し書きの3文を消す（依頼 20261019-02-lp・CMO 判断 10/19 09:53）。

  python3 tools/tadashi-1020.py <HTML> ...          # その場で書き換える（2回目以降は何もしない）
  python3 tools/tadashi-1020.py --check <HTML> ...  # 残っていないかだけ見る

オーナー（10/18）「非常にAI感の強い表現だから学習してね」→ docs/LP原稿の書き方.md
CMO：2・3・4 は外す。1（固定バー「しつこい営業・訪問はいたしません」）は全LP共通の部品なので残す（10/24 MTG で確認）。
対象は今回 /nenmatsu-b/・/mizumawari-b/。同じ文はほかのLPにもある（広げるかは CMO 判断）。

10/24 オーナー決定（第8回MTG 8-4 No.7「但し書き一覧の削除と『いちばんお得』の直し」→「直す（推奨）」）で全LPに広げた：
- 1（固定バー「しつこい営業・訪問はいたしません」）も消す
- エアコンLPの「お急ぎでなければ、4月・8〜11月のご予約がいちばんお得です。」は予約ページの計算（1台だけなら
  作業日が1〜2月 15%・3〜4月と8〜11月 10%）と合わないので、事実どおりの1文に置き換える
- 参考に載せた「訪問営業も電話営業もしていません。」はオーナーに直接は聞いていないので残す（cmo に確認）
"""
import pathlib, sys

KESU = [
    '品質を落として下げているわけではありません。',
    '当日になって、知らない会社の作業員が来ることはありません。',
    '不要な箇所を抱き合わせでおすすめすることはありません。',
]


STICKY = '\n  <p class="sticky-note">しつこい営業・訪問はいたしません</p>'
OKIKAE = [
    ('お急ぎでなければ、4月・8〜11月のご予約がいちばんお得です。',
     '1台だけのご依頼は、作業日が1〜4月・8〜11月なら10〜15%引きになります。'),
]


def apply(s):
    for k in KESU:
        s = s.replace(k, '')
    s = s.replace(STICKY, '')
    for a, b in OKIKAE:
        s = s.replace(a, b)
    return s


def nokori(s):
    return [k for k in KESU + ['しつこい営業・訪問はいたしません', 'いちばんお得'] if k in s]


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
