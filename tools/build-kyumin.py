#!/usr/bin/env python3
"""『提携先_休眠度』タブを『【毎月更新】リピート/業務提携』タブから作り直す。

    python3 tools/build-kyumin.py            # 下見（書かない）
    python3 tools/build-kyumin.py --jikkou   # 書く

## なぜ作ったか

このタブは 2026-09-19 に**手で**作られた。先頭に「毎月更新します」と書いてあるのに
更新する道具が無かったので、**提携タブが変わっても追いつかない。**

実際に 2026-09-20 に2つずれているのが見つかった（ネット流入施策担当が発見）。

| | タブの値 | 正 |
|---|--:|--:|
| クラスリフォーム | 14件 ¥1,244,640 | 20件 ¥1,528,520 |
| タカラサービス | 17件 ¥777,690 | 13件 ¥608,290 |

クラスリフォームのずれは **CMO の訂正より前から**あった（9/16・9/17 の2件が
提携タブに足された日に、この表を作り直さなかったため）。
**手で作る表は、作った瞬間から古くなる。**

## 何を守るか

- **D列「状態」の絵文字と E列「経過日数」は作り直す**（日が経てば必ず変わるので）
- **J列「今後の方針」は人の判断なので、提携先名をキーにそのまま引き継ぐ**
  （「切る（対応が杜撰）」などは機械には出せない）
- **17行目より上の説明文と、36行目以降のまとめ・「いちばん惜しい先」は触らない。**
  数字が変わったら、変わったことだけ知らせる（人が書き直す）
"""

import datetime
import importlib.util
import json
import os
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location('sc', os.path.join(ROOT, 'tools', 'sheets_client.py'))
sc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sc)

SID = '1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64'
TEIKEI = '【毎月更新】リピート/業務提携'
KYUMIN = '提携先_休眠度'
SAKI = 17            # 表の1行目
PAIR_OWARI = 68      # BQ(合計)より手前までが 日付/売上 の対


def yomu(tok, rng, render='UNFORMATTED_VALUE'):
    q = urllib.parse.quote(rng, safe='')
    res = sc.call(tok, f'/{SID}/values/{q}',
                  query={'valueRenderOption': render, 'dateTimeRenderOption': 'FORMATTED_STRING'})
    return res.get('values', [])


def kaku(tok, rng, values):
    q = urllib.parse.quote(rng, safe='')
    sc.call(tok, f'/{SID}/values/{q}', method='PUT',
            payload={'values': values}, query={'valueInputOption': 'RAW'})


def kingaku(s):
    s = str(s).replace('¥', '').replace('￥', '').replace(',', '').strip()
    return int(float(s)) if s else 0


def jotai(nissu):
    if nissu > 365:
        return '🔴 1年以上ない'
    if nissu >= 180:
        return '🟠 半年以上ない'
    if nissu >= 90:
        return '🟡 そろそろ'
    return '🟢 動いている'


def main():
    tok = sc.access_token(sc.load_credentials())
    kyou = datetime.date.today()

    # --- 提携タブを読んで、1社ぶんずつ数える ---
    src = yomu(tok, f"'{TEIKEI}'!A1:BU120", 'FORMATTED_VALUE')
    saki = []
    for row in src[1:]:
        na = str(row[1]).strip() if len(row) > 1 else ''
        if not na:
            continue
        gyoushu = str(row[2]).strip() if len(row) > 2 else ''
        hidzuke, gaku = [], 0
        for k in range(4, min(len(row), PAIR_OWARI), 2):
            d = str(row[k]).strip()
            a = str(row[k + 1]).strip() if k + 1 < len(row) else ''
            if d and a:
                hidzuke.append(d)
                gaku += kingaku(a)
            elif d or a:
                sys.exit(f'★{na}：対になっていないセルがあります（{d!r}/{a!r}）。中止します')
        if not hidzuke:
            continue
        saigo = max(datetime.date(*map(int, d.replace('-', '/').split('/'))) for d in hidzuke)
        saki.append({'名': na, '業種': gyoushu or '（未記入）', '件数': len(hidzuke),
                     '累計': gaku, '最終': saigo, '経過': (kyou - saigo).days})

    zentai = sum(s['累計'] for s in saki)
    saki.sort(key=lambda s: -s['経過'])          # 止まっている先ほど上

    # --- いまのタブを読んで、人が書いた「今後の方針」を引き継ぐ ---
    ima = yomu(tok, f"'{KYUMIN}'!A{SAKI}:J{SAKI + 80}", 'FORMATTED_VALUE')
    houshin, mae = {}, {}
    for row in ima:
        na = str(row[1]).strip() if len(row) > 1 else ''
        if not na or na == '提携先':
            break
        if len(row) > 9 and str(row[9]).strip():
            houshin[na] = str(row[9]).strip()
        mae[na] = (str(row[6]).strip() if len(row) > 6 else '',
                   str(row[7]).strip() if len(row) > 7 else '')

    # --- 変わったところを見せる ---
    print(f'基準日 {kyou}／提携先 {len(saki)}社／累計 ¥{zentai:,}\n')
    chigau = 0
    for s in saki:
        k, g = mae.get(s['名'], (None, None))
        atarashii = (str(s['件数']), f"{s['累計']:,}")
        if k is None:
            print(f"  ＋ {s['名']}（この表に無かった）  {atarashii[0]}件 ¥{atarashii[1]}")
            chigau += 1
        elif (k, g.replace('¥', '')) != atarashii:
            print(f"  ✎ {s['名']}  {k}件 ¥{g} → {atarashii[0]}件 ¥{atarashii[1]}")
            chigau += 1
    kieta = [n for n in mae if n not in {s['名'] for s in saki}]
    for n in kieta:
        print(f'  － {n}（提携タブに見当たりません。行は残します）')
    if not chigau and not kieta:
        print('  数字の変化はありません（経過日数だけ更新されます）')

    if '--jikkou' not in sys.argv:
        print('\n（下見だけです。書き込むには --jikkou）')
        return 0

    hyou = [[
        '', s['名'], s['業種'], jotai(s['経過']), s['経過'],
        s['最終'].strftime('%Y-%m-%d'), s['件数'], f"{s['累計']:,}",
        f"{s['累計'] / zentai * 100:.1f}%" if zentai else '',
        houshin.get(s['名'], ''),
    ] for s in saki]
    kaku(tok, f"'{KYUMIN}'!A{SAKI}:J{SAKI + len(hyou) - 1}", hyou)
    # 前より社数が減ったぶんを空にする（空文字を書くと COUNTA が数えるので clear を使う）
    if len(mae) > len(hyou):
        q = urllib.parse.quote(f"'{KYUMIN}'!A{SAKI + len(hyou)}:J{SAKI + len(mae) - 1}", safe='')
        sc.call(tok, f'/{SID}/values/{q}:clear', method='POST', payload={})
    print(f'\n書きました：{len(hyou)}社')

    # --- まとめの文（36行目以降）は人が書いたものなので触らない。ずれだけ知らせる ---
    ugoku = sum(1 for s in saki if s['経過'] <= 90)
    tomatta = [s for s in saki if s['経過'] > 365]
    print('\n--- 36行目以降のまとめ文を人が直すための数字 ---')
    print(f'  全 {len(saki)}社／90日以内に発注があるのは {ugoku}社')
    print(f'  1年以上ない {len(tomatta)}社の累計 ¥{sum(s["累計"] for s in tomatta):,}')
    print(f'  累計売上の全体 ¥{zentai:,}')
    for s in saki[:1] + [x for x in saki if x['累計'] == max(y['累計'] for y in saki)]:
        pass
    saidai = max(saki, key=lambda s: s['累計'])
    print(f'  最大は {saidai["名"]} ¥{saidai["累計"]:,}（{saidai["累計"] / zentai * 100:.1f}%）')
    print('  ★ この数字と 36〜45行目の文が食い違っていたら、人が書き直すこと')
    return 0


if __name__ == '__main__':
    sys.exit(main())
