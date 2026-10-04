#!/usr/bin/env python3
"""2026年 9〜12月の着地見込みの材料を、2026年シートから読んで集計だけを書き出す（読むだけ）。

経営企画室（planning）は鍵を持たないので、鍵のある環境（CMO）で1回流してもらい、
出力の JSON をコミットしてもらう。JSON には氏名・電話・住所を一切入れない（件数と金額だけ）。

使い方:
  python3 tools/chakuchi-shuukei.py                 # data/chakuchi/2026Q4-<日時>.json に書く
  python3 tools/chakuchi-shuukei.py --kijun 2026-10-08   # 「施工済み／予約」の境目の日（既定は今日 JST）
  python3 tools/chakuchi-shuukei.py --backup <控え.json.gz>  # 鍵なしの動作確認（控えは数式なので金額の一部は0）

出すもの:
  1. 9〜12月_売上/顧客：売上種類 × 流入経路 × 施工済み/予約 の 件数・売上。
     W列などの「早期予約の確定」列があれば 確定/未確定 も分ける。ネット経由（広告・予約ページ・LP・地図検索・HP ほか）の小計
  2. 9〜12月_支出/成績：A〜F列の「見出し → 右隣の数値」の組（50行目以降。P/L の部分）。
     H列より右（アルバイトの氏名・時給など）は読まない
"""
import argparse
import datetime
import gzip
import json
import os
import sys
import urllib.parse

KOKO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(KOKO, 'tools'))

SS = '1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64'
TSUKI = [9, 10, 11, 12]
JST = datetime.timezone(datetime.timedelta(hours=9))
KIJUN_HI = datetime.date(1899, 12, 30)

# CMO の数え方（20261004-01-planning）に合わせる。アフィリエイトのLPもネット経由に入れる
NET = ['広告', '予約ページ', 'LP', 'LP(アフィリエイト)', '地図検索', 'HP']


def uriage_tab(m):
    return f'{m}月_売上/顧客'


def shishutsu_tab(m):
    return f'{m}月_支出/成績'


def yomu_api(rng):
    import sheets_client as sc
    if not hasattr(yomu_api, 'token'):
        yomu_api.token = sc.access_token(sc.load_credentials())
    res = sc.call(yomu_api.token, f'/{SS}/values/{urllib.parse.quote(rng, safe="")}',
                  query={'valueRenderOption': 'UNFORMATTED_VALUE',
                         'dateTimeRenderOption': 'SERIAL_NUMBER'})
    return res.get('values', [])


def hizuke(v):
    if isinstance(v, (int, float)) and v > 30000:
        return KIJUN_HI + datetime.timedelta(days=int(v))
    if isinstance(v, str):
        for f in ('%Y/%m/%d', '%Y-%m-%d', '%m/%d'):
            try:
                d = datetime.datetime.strptime(v.strip(), f).date()
                return d if f != '%m/%d' else None
            except ValueError:
                pass
    return None


def retsu(hdr, *mei):
    for i, h in enumerate(hdr):
        h = str(h or '')
        if any(m in h for m in mei):
            return i
    return None


def shuukei_uriage(rows, kijun):
    """rows はタブ全体（1行目＝目標行、2行目＝見出し、3行目＝自動集計、4行目から明細）"""
    if len(rows) < 2:
        return {'エラー': 'タブが空'}
    hdr = rows[1]
    c_shu, c_hi = retsu(hdr, '売上種類'), retsu(hdr, '施工日付')
    c_keiro, c_kin = retsu(hdr, '流入経路'), retsu(hdr, '売上（税込）', '売上(税込)')
    c_kaku = retsu(hdr, '早期予約の確定')
    if None in (c_shu, c_hi, c_keiro, c_kin):
        return {'エラー': f'見出しが見つからない: {hdr[:12]}'}
    meisai = {}
    hizuke_nashi = 0
    for r in rows[3:]:
        g = lambda i: r[i] if i is not None and i < len(r) else ''
        shu = str(g(c_shu)).strip()
        if not shu:
            continue
        d = hizuke(g(c_hi))
        if d is None:
            hizuke_nashi += 1
            jotai = '日付なし'
        else:
            jotai = '施工済み' if d <= kijun else '予約'
        kin = g(c_kin)
        kin = kin if isinstance(kin, (int, float)) else 0
        kaku = str(g(c_kaku)).strip() if c_kaku is not None else ''
        k = '|'.join([shu, str(g(c_keiro)).strip() or '(空)', jotai, kaku or '-'])
        e = meisai.setdefault(k, [0, 0])
        e[0] += 1
        e[1] += kin
    gokei = {}
    for k, (n, kin) in meisai.items():
        shu, keiro, jotai, kaku = k.split('|')
        for kk in (f'{shu}|{jotai}', f'全体|{jotai}', f'{shu}|計', '全体|計'):
            e = gokei.setdefault(kk, [0, 0])
            e[0] += n
            e[1] += kin
        if keiro in NET:
            for kk in (f'ネット経由|{jotai}', 'ネット経由|計'):
                e = gokei.setdefault(kk, [0, 0])
                e[0] += n
                e[1] += kin
    return {'明細（売上種類|流入経路|状態|早期予約の確定）': dict(sorted(meisai.items())),
            '小計': dict(sorted(gokei.items())),
            '施工日付が読めない行': hizuke_nashi,
            '早期予約の確定の列': hdr[c_kaku] if c_kaku is not None else None}


def shuukei_shishutsu(rows):
    """A〜F列の『文字の見出し → 右隣の数値』を50行目以降から拾う"""
    kumi = []
    for i, r in enumerate(rows):
        if i + 1 < 50:
            continue
        for j in range(0, min(len(r), 6) - 1):
            mi, atai = r[j], r[j + 1]
            if isinstance(mi, str) and mi.strip() and isinstance(atai, (int, float)) \
                    and not isinstance(atai, bool):
                kumi.append([f'{chr(65 + j)}{i + 1}', mi.strip().replace('\n', ' '), atai])
    return kumi


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--kijun', help='施工済み/予約の境目の日 YYYY-MM-DD（既定は今日 JST）')
    ap.add_argument('--backup', help='鍵なしの動作確認用に控えの json.gz を読む')
    a = ap.parse_args()
    ima = datetime.datetime.now(JST)
    kijun = datetime.date.fromisoformat(a.kijun) if a.kijun else ima.date()

    if a.backup:
        bk = json.load(gzip.open(a.backup))
        yomu = lambda tab: bk.get(tab, [])
    else:
        yomu = lambda tab: yomu_api(f"'{tab}'!A1:Z520")

    out = {'作成': ima.strftime('%Y-%m-%d %H:%M JST'), '基準日（この日までが施工済み）': str(kijun),
           'ネット経由に数えた流入経路': NET, '売上': {}, '支出/成績': {}}
    for m in TSUKI:
        out['売上'][f'{m}月'] = shuukei_uriage(yomu(uriage_tab(m)), kijun)
        out['支出/成績'][f'{m}月'] = shuukei_shishutsu(
            yomu(shishutsu_tab(m)) if not a.backup else bk.get(shishutsu_tab(m), []))

    if a.backup:
        print(json.dumps(out, ensure_ascii=False, indent=1)[:4000])
        return
    os.makedirs(os.path.join(KOKO, 'data', 'chakuchi'), exist_ok=True)
    p = os.path.join(KOKO, 'data', 'chakuchi', f"2026Q4-{ima.strftime('%Y%m%d-%H%M')}.json")
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print('書きました:', os.path.relpath(p, KOKO))
    for m in TSUKI:
        s = out['売上'][f'{m}月'].get('小計', {})
        print(f'  {m}月 自社 {s.get("One Hitter|計", [0, 0])} 本舗 {s.get("本舗|計", [0, 0])} '
              f'ネット {s.get("ネット経由|計", [0, 0])}  ［件数, 売上］')


if __name__ == '__main__':
    main()
