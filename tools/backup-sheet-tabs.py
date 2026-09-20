#!/usr/bin/env python3
"""消す前のタブを、リポジトリの中に控える。

【なぜこの形か】
  サービスアカウントは Drive の保存容量が0なので、ファイルをコピーできない。
  Drive コネクタの copy_file も、この環境では使えなかった
  （Operation is not implemented, or supported, or enabled）。

  そこで「ファイルごと複製する」のをやめて、**消す対象のタブだけを
  リポジトリの中に落とす。** git の履歴に残るので、消したあとでも
  いつでも取り出せる。同じファイルの中にタブを増やす必要も無い。

  gzip して置く（生 500KB → 43KB 程度）。

【使い方】★タブ名は必ず渡すこと

  python3 tools/backup-sheet-tabs.py "冬季見込み客_2026" "【毎月更新】リピート/業務提携"
  python3 tools/backup-sheet-tabs.py "冬季見込み客_2026" --verify
  python3 tools/backup-sheet-tabs.py --mukashi         # 下の MUKASHI（2026-09-18 の16本）

  出力先 data/sheets/backup/<タブ名>.json.gz

【2026-09-20 の直し（20260920-01-crm）】

  引数なしで実行すると **誰がやっても落ちていた。** 理由は2つ。

  1. 対象が MUKASHI（2026-09-18 に消した16本）の直書きだった。**もう1本も存在しない。**
  2. 1本読めないだけで `RuntimeError` が上がり、**残り全部が道連れ**になっていた。

  全スレッドに「控えはこれで」と案内した道具なので、**引数で受ける形**にし、
  **読めないタブは飛ばして続ける**ようにした。**最後に、何本飛ばしたかを必ず出す。**

  ★読めなかったタブがあれば **終了コード 1** で終わる。
    「控えが取れた」と思い込んだまま次へ進まないため。

  ★ハマりどころ：`sheets_client.call()` は API がエラーを返すと **`sys.exit()` する。**
    `sys.exit()` は `SystemExit` で、**`except Exception` では捕まらない。**
    だから `except (Exception, SystemExit)` で受けている。ここを Exception だけに
    戻すと、また1本で全部が止まる。
"""
import gzip
import io
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'sheets', 'backup')
SHEET = '1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64'

# 2026-09-18 の一斉整理で消した16本。**記録として残すだけ。もう存在しない。**
#   --mukashi を付けたときだけ使う（当時の再現用）。既定では見ない。
MUKASHI = [
    # A群：われわれが作った作業控え（7本）
    '控え_冬季見込み客_20260915-002440',
    '控え_冬季見込み客_20260915-0024',
    '控え_冬季見込み客_20260914-1805',
    '控え_冬季見込み客_20260914-1754',
    '控え_冬季見込み客_20260911-1311',
    '控え_業務提携_20260914-1755',
    '控え_業務提携_20260913-2326',
    # B群：2026-09-11 の履歴書き換えの退避先（9本）
    # ★オーナー指示のバックアップそのもの。ここを落とすのが今回の主目的
    '履歴退避_冬季見込み客_20260910-0431',
    '履歴退避_冬季見込み客_20260910-0548',
    '履歴退避_冬季見込み客_20260910-0645',
    '履歴退避_冬季見込み客_20260910-1015',
    '履歴退避_冬季見込み客_20260910-2350',
    '履歴退避_冬季見込み客_20260911-0130',
    '履歴退避_冬季見込み客_20260911-0146',
    '履歴退避_冬季見込み客_20260911-0540',
    '履歴退避_冬季見込み客_20260911-1310',
]

TABS = []          # 実際に扱う対象。main() が引数から入れる


def _sc():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'sc', os.path.join(ROOT, 'tools', 'sheets_client.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def yomu(tab, tok):
    """タブを読む。**読めなければ例外**。呼ぶ側で拾って飛ばすこと。

    ★以前は subprocess で sheets_client を叩いていたが、大きいタブで
      180秒のタイムアウトに当たって黙って止まった（2026-09-19）。直接読む。
    """
    import urllib.parse
    sc = _sc()
    return sc.call(tok, f'/{SHEET}/values/'
                   + urllib.parse.quote(f'{tab}!A1:AZ2000', safe='')).get('values', [])


def gyousuu(rows):
    """空でない行の数"""
    return sum(1 for x in rows if x and any(str(c).strip() for c in x))


def verify():
    ok = True
    for tab in TABS:
        p = os.path.join(OUT, tab + '.json.gz')
        if not os.path.exists(p):
            print(f'  ✗ {tab}  控えが無い')
            ok = False
            continue
        with gzip.open(p, 'rt', encoding='utf-8') as f:
            rows = json.load(f)
        n = gyousuu(rows)
        mark = 'OK' if n > 0 else '★中身が空'
        if n == 0:
            ok = False
        print(f'  {mark:8} {tab}  {n}行  {os.path.getsize(p):,} bytes')
    return ok


def main():
    global TABS
    watasareta = [a for a in sys.argv[1:] if not a.startswith('--')]
    if watasareta:
        TABS = watasareta
    elif '--mukashi' in sys.argv:
        TABS = list(MUKASHI)
        print('★ 2026-09-18 に消した16本を対象にします（もう存在しないはずです）')
    else:
        print(__doc__)
        print('★ タブ名を1つ以上渡してください。')
        sys.exit(2)
    print(f'対象 {len(TABS)}本: {TABS}')

    if '--verify' in sys.argv:
        print('\n--- 控えの検査 ---')
        sys.exit(0 if verify() else 1)

    sc = _sc()
    tok = sc.access_token(sc.load_credentials())
    # 先にタブの一覧を取る。無い名前は読みに行く前に弾く（エラーメッセージが分かりやすい）
    try:
        meta = sc.call(tok, f'/{SHEET}', query={'fields': 'sheets.properties.title'})
        aru = {x['properties']['title'] for x in meta['sheets']}
    except (Exception, SystemExit):
        aru = None
        print('⚠ タブの一覧が取れませんでした。1本ずつ読みに行きます')
    os.makedirs(OUT, exist_ok=True)
    total = 0
    toreta, tobashita = [], []
    for tab in TABS:
        if aru is not None and tab not in aru:
            tobashita.append((tab, 'そのタブはスプレッドシートにありません'))
            print(f'  ✗ {tab}  そのタブはありません → 飛ばします')
            continue
        # ★1本読めなくても、残りを道連れにしない。
        #   SystemExit も捕まえること（sheets_client.call は sys.exit する）
        try:
            rows = yomu(tab, tok)
        except (Exception, SystemExit) as e:
            tobashita.append((tab, str(e)[:120]))
            print(f'  ✗ {tab}  読めません → 飛ばします（{str(e)[:80]}）')
            continue
        n = gyousuu(rows)
        if n == 0:
            # 空のものを控えても意味が無いどころか、
            # 「控えた」という誤った安心を生む
            tobashita.append((tab, '中身が空'))
            print(f'  ★ {tab}  中身が空。控えを作らない')
            continue
        p = os.path.join(OUT, tab + '.json.gz')
        with gzip.open(p, 'wt', encoding='utf-8') as f:
            json.dump(rows, f, ensure_ascii=False)
        sz = os.path.getsize(p)
        total += sz
        toreta.append(tab)
        print(f'  ✓ {tab}  {n}行  {sz:,} bytes')

    print(f'\n控えた {len(toreta)}本 / 飛ばした {len(tobashita)}本 / 合計 {total:,} bytes')
    for tab, why in tobashita:
        print(f'  飛ばした: {tab}  ← {why}')

    print('\n--- 取ったものを読み直して検査 ---')
    TABS = toreta
    ok = verify()
    print('\n※ ★コミットを忘れないこと。git に入って初めて控えです')
    # 飛ばしたものがあれば、控えが揃っていないので 1 で終わる
    sys.exit(0 if (ok and not tobashita) else 1)


if __name__ == '__main__':
    main()
