#!/usr/bin/env python3
"""11月施工の「ネット経由」を、毎日の着地集計（data/chakuchi/*.json）から日別に並べる（読むだけ）。

    python3 tools/net11-tsuiseki.py            # 表を出す
    python3 tools/net11-tsuiseki.py --md       # docs に貼る markdown の表

数え方（docs/2026-11月ネット10件の経路別逆算.md）
- 月次タブ：11月_売上/顧客 の流入経路が 広告・予約ページ・LP・地図検索・HP、または LINE・SMS（予約ページ経由に限る。10/18 規則）の行
- 予約_Web：ご希望日が11月で、状態がキャンセル・空送信でない申込（src で 広告／SMS／LINE／GBP／その他）。
  受注になって月次タブに入ると両方に出るので、**判定は月次タブの数で行い、予約_Web は「受注前の申込」の参考**
- 線（11/1 に4件）は同じ文書の「11/1 の線」
"""
import argparse
import glob
import json
import os
import re

KOKO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NET = {'広告', '予約ページ', 'LP', 'LP(アフィリエイト)', '地図検索', 'HP'}
KIZON = {'SMS', 'LINE'}
# 11/1 に4件へ向かう線（文書と同じ）。日付 → その日の朝に欲しい累計
SEN = {'10-20': 0, '10-22': 1, '10-24': 1, '10-27': 2, '10-29': 3, '10-31': 4, '11-01': 4}


def sen_of(md):
    keys = sorted(SEN)
    v = 0
    for k in keys:
        if md >= k:
            v = SEN[k]
    return v


def yomu(p):
    d = json.load(open(p, encoding='utf-8'))
    m = re.search(r'(\d{4})(\d{2})(\d{2})-(\d{4})', os.path.basename(p))
    hi = f'{m.group(2)}-{m.group(3)}' if m else '?'
    mei = d.get('売上', {}).get('11月', {}).get('明細（売上種類|流入経路|状態|早期予約の確定）', {})
    net = kiz = 0
    for k, (n, _kin) in mei.items():
        parts = k.split('|')
        if len(parts) < 2 or parts[0] != 'One Hitter':
            continue
        if parts[1] in NET:
            net += n
        elif parts[1] in KIZON:
            kiz += n
    yw = d.get('予約_Web', {}).get('件数（src|ご希望日の月|状態|受信日）', {})
    yo = {}
    for k, n in yw.items():
        src, tsuki, jotai = (k.split('|') + ['', '', ''])[:3]
        if tsuki == '11月' and jotai not in ('キャンセル', '空送信'):
            yo[src] = yo.get(src, 0) + n
    return hi, d.get('作成', ''), net, kiz, yo


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--md', action='store_true')
    a = ap.parse_args()
    rows = {}
    for p in sorted(glob.glob(os.path.join(KOKO, 'data', 'chakuchi', '2026Q4-*.json'))):
        hi, saku, net, kiz, yo = yomu(p)
        rows[hi] = (saku, net, kiz, yo)   # 同じ日は最後の集計で上書き
    hdr = ['日付', '集計', '月次タブ 広告・LP・HP・地図', '月次タブ LINE・SMS（予約ページ経由）', '**合計**', '線', '差',
           '予約_Web 受注前の申込（11月希望）']
    out = []
    for hi in sorted(rows):
        if hi < '10-17':
            continue
        saku, net, kiz, yo = rows[hi]
        gk = net + kiz
        sen = sen_of(hi)
        yos = '・'.join(f'{k}{v}' for k, v in sorted(yo.items())) or '0'
        out.append([hi.replace('-', '/'), saku[-9:], str(net), str(kiz), f'**{gk}**', str(sen),
                    f'{gk - sen:+d}', yos])
    if a.md:
        print('| ' + ' | '.join(hdr) + ' |')
        print('|' + '---|' * len(hdr))
        for r in out:
            print('| ' + ' | '.join(r) + ' |')
    else:
        for r in [hdr] + out:
            print('\t'.join(x.replace('**', '') for x in r))


if __name__ == '__main__':
    main()
