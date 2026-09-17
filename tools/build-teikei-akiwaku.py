#!/usr/bin/env python3
"""提携先に送る「今月の空き枠」の本文を作る。

【なぜこれがあるか】
  提携先への接触が、月1回すら回っていない（2026年9〜12月の受注0件）。
  営業に回せる人がいないので、訪問も電話も続かない。
  続く形は「相手が使える情報を、人の手をほとんど使わずに送る」しかない。

  空き枠は `tools/build-slots.py` が予約フォーム用に毎時作っている。
  同じデータを、B2B向けに文章にするだけ。**新しく取るデータは無い。**

【設計の判断】
  ・時刻を全部並べない。「終日／午前／午後／夜」に畳む。
    提携先が知りたいのは「その日を押さえられるか」であって、30分刻みではない。
  ・空きが少ない日は落とす（既定2枠未満）。半端な枠を並べると、かえって
    「埋まっている会社」に見えず、ただ読みにくい。
  ・**並べるのは最大8日まで（既定）。** 18日ぶん並べると「暇な会社」に見える。
    多いぶんは「ほかにも空きがあります」と1行にする。**隠してはいない。**
  ・**既定の期間は14日。** 提携先が空き枠を見るのは「急ぎの案件を振れるか」で、
    1か月先の話ではない。
  ・**枠が少ない月ほど、そのまま出す。**「もうこれだけしか空いていない」は
    嘘のない催促になる。水増しはしない。

【使い方】
  python3 tools/build-teikei-akiwaku.py                  # 今日から14日ぶん
  python3 tools/build-teikei-akiwaku.py --nissu 28       # 期間を変える
  python3 tools/build-teikei-akiwaku.py --saidai 12     # 並べる日数の上限（既定8）
  python3 tools/build-teikei-akiwaku.py --shoyou 180     # 所要時間の枠で見る（既定120分）
  python3 tools/build-teikei-akiwaku.py --saitei 4       # その日の最低枠数

  ★送信はしない。本文を出すだけ。送るのはオーナー（外に出すものなので）。
"""
import argparse
import datetime as dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SLOTS = os.path.join(ROOT, 'lp', 'booking', 'slots.json')

# 午前／午後／夜の境目。施工の実態に合わせている（夜間対応もしているため夜を残す）
GOZEN_MADE = 12
YORU_KARA = 17


def taitai(times):
    """時刻の一覧を「終日／午前／午後／夜」に畳む。"""
    han = set()
    for t in times:
        h = int(t.split(':')[0])
        if h < GOZEN_MADE:
            han.add('午前')
        elif h < YORU_KARA:
            han.add('午後')
        else:
            han.add('夜')
    if han >= {'午前', '午後'}:
        return '終日' if '夜' in han else '午前・午後'
    return '・'.join(x for x in ('午前', '午後', '夜') if x in han)


def atsumeru(shoyou, nissu, saitei):
    with open(SLOTS, encoding='utf-8') as f:
        d = json.load(f)
    hi = d['buckets'].get(str(shoyou))
    if hi is None:
        sys.exit(f'所要 {shoyou} 分の枠がありません。ある: {", ".join(d["buckets"])}')

    kyou = dt.date.today()
    kagiri = kyou + dt.timedelta(days=nissu)
    out = []
    for x in hi:
        hiduke = dt.date.fromisoformat(x['date'])
        if not (kyou <= hiduke <= kagiri):
            continue
        if len(x['times']) < saitei:
            continue
        out.append((x['label'], taitai(x['times'])))
    return d.get('generatedLabel') or d.get('generated'), out


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--shoyou', type=int, default=120, help='所要時間（分）。既定120')
    p.add_argument('--nissu', type=int, default=14, help='何日先まで見るか。既定14')
    p.add_argument('--saidai', type=int, default=8, help='並べる日数の上限。既定8')
    p.add_argument('--saitei', type=int, default=2, help='その日の最低枠数。既定2')
    a = p.parse_args()

    itsu, hi = atsumeru(a.shoyou, a.nissu, a.saitei)

    if not hi:
        # 空きが無いのは事実。無理に文面を作らない
        print('★ 条件に合う空き枠がありません。今月は送らない、が正しい判断です。', file=sys.stderr)
        sys.exit(1)

    print('お世話になっております。ワンヒッター株式会社の佐々木です。')
    print()
    print('直近の空き状況をお送りします。')
    print()
    for label, tai in hi[:a.saidai]:
        print(f'　{label}　{tai}')
    amari = len(hi) - a.saidai
    if amari > 0:
        # 隠さない。ただし全部並べると「暇な会社」に見えるので1行に畳む
        print(f'　ほか{amari}日、空きがあります。')
    print()
    print('急ぎの案件が入りましたら、上記の日程でお受けできます。')
    print('埋まり次第この枠は消えますので、目安としてご覧ください。')
    print('お電話（080-8043-8259）でご連絡いただければ、その場で仮押さえいたします。')
    print()
    print('引き続きよろしくお願いいたします。')
    print()
    print('______________________')
    print('ワンヒッター株式会社')
    print('佐々木 嶺')
    print('080-6817-4796')
    print('info@one-hitter.her.jp')
    print('https://one-hitter.jp/')
    print('______________________')

    print(f'\n---\n※ 空き枠の元データ: {itsu} 時点 ／ 所要{a.shoyou}分 ／ '
          f'該当{len(hi)}日（うち{min(len(hi), a.saidai)}日を掲載）', file=sys.stderr)


if __name__ == '__main__':
    main()
