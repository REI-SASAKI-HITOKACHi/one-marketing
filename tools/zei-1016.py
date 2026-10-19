#!/usr/bin/env python3
"""オプション価格の二重課税を直す（依頼 20261016-03-lp・オーナー指摘 10/16）。

  python3 tools/zei-1016.py <HTML> ...      # その場で書き換える（2回目以降は何もしない）
  python3 tools/zei-1016.py --check <HTML> ...   # 古い金額が残っていないかだけ見る（残っていれば終了コード1）

元から税込の形の11項目に ×1.1 を重ねていた（docs/価格の税込税抜-調査結果.md の 9/6 の決めごとに反していた）。
オーナー原文「オプションメニューが税込み金額に税がかかってしまっている。例）浴室エプロン内部：税抜き7,000円が正当」。
正：室外機セット 5,500／防カビコート 3,300／防虫キャップ 1,100／防水パン 3,300／排水溝 3,300／コンロ（同時施工）5,500／
    お掃除時短コーティング 19,800／エプロン内部 7,700／浴室換気扇 3,300／鏡の水垢 3,300／空室清掃 52,800〜
変えない：浴室乾燥機 8,580・セット 15,180・追い焚き（同時）16,610・洗面台 7,480・繁忙期加算 3,300
"""
import re, sys, pathlib

# （古い書き方, 新しい書き方）。ページの決まった言い回しに限って当てる
OKIKAE = [
    ('value="6050" data-nm="室外機セット"', 'value="5500" data-nm="室外機セット"'),
    ('室外機セット +6,050円', '室外機セット +5,500円'),
    ('室外機セット 6,050円', '室外機セット 5,500円'),
    ('value="3630" data-nm="防カビコート"', 'value="3300" data-nm="防カビコート"'),
    ('防カビコート +3,630円', '防カビコート +3,300円'),
    ('防カビコート 3,630円', '防カビコート 3,300円'),
    ('防カビコート（通常 3,630円）', '防カビコート（通常 3,300円）'),
    ('value="1210" data-nm="防虫キャップ"', 'value="1100" data-nm="防虫キャップ"'),
    ('防虫キャップ +1,210円', '防虫キャップ +1,100円'),
    ('防虫キャップ 1,210円', '防虫キャップ 1,100円'),
    ('data-nm="コンロクリーニング" data-single="10780" data-set="6050"', 'data-nm="コンロクリーニング" data-single="10780" data-set="5500"'),
    ('室外機セット<small>+6,050円</small>', '室外機セット<small>+5,500円</small>'),
    ('防カビコート<small>+3,630円</small>', '防カビコート<small>+3,300円</small>'),
    ('防虫キャップ<small>+1,210円</small>', '防虫キャップ<small>+1,100円</small>'),
    ('室外機セット</span><span class="pr">6,050円', '室外機セット</span><span class="pr">5,500円'),
    ('防カビコート</span><span class="pr">3,630円', '防カビコート</span><span class="pr">3,300円'),
    ('防虫キャップ</span><span class="pr">1,210円', '防虫キャップ</span><span class="pr">1,100円'),
    ('（コンロは4,730円）', '（コンロは5,280円）'),   # 単体 10,780 − 同時施工 5,500
    # 浴室の枠（tools/chuuki-1008.py が data/prices.json から作ったもの）
    ('の高圧洗浄</span><b>8,470円</b>', 'の高圧洗浄</span><b>7,700円</b>'),
    ('除去</span><b>3,630円</b>', '除去</span><b>3,300円</b>'),
    ('浴室換気扇の洗浄</span><b>3,630円</b>', '浴室換気扇の洗浄</span><b>3,300円</b>'),
    # 「よくある頼み方」カードの最初の数字（キッチン＋レンジフード＋コンロ）。JS が動けば計算し直すが、
    # HTML に書いた初めの値がコンロ 6,050 のままだった（10/19 の着地点検で発見・依頼 20261019-02-lp）
    ('data-role="tot">39,710<small>', 'data-role="tot">39,160<small>'),
    ('data-role="dec">49,610円', 'data-role="dec">49,060円'),
]
FURUI = re.compile(r'(?<![\d,])(6,050|3,630|1,210|8,470|21,780|58,080|4,730|39,710|49,610)円|data-role="tot">39,710|value="(6050|3630|1210|8470)"|data-set="6050"')


def apply(s):
    for a, b in OKIKAE:
        s = s.replace(a, b)
    return s


def nokori(s):
    t = re.sub(r'<style[^>]*>.*?</style>', '', s, flags=re.S)
    return sorted(set(m.group(0) for m in FURUI.finditer(t)))


def main(args):
    check = args and args[0] == "--check"
    paths = args[1:] if check else args
    bad = 0
    for p in map(pathlib.Path, paths):
        s = p.read_text(encoding="utf-8")
        if not check:
            t = apply(s)
            if t != s:
                p.write_text(t, encoding="utf-8")
            s = t
        n = nokori(s)
        print(f"{'NG' if n else 'OK'} {p}" + (f"：古い金額が残っている {n}" if n else ""))
        bad += bool(n)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
