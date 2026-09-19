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

【使い方】
  python3 tools/backup-sheet-tabs.py            # 下の TABS の控えを取る
  python3 tools/backup-sheet-tabs.py --verify   # 取った控えを読み直して行数を出す

  python3 tools/backup-sheet-tabs.py "控え_業務提携_20260919-091000"
      タブ名を渡すと、そのタブだけを控える（TABS は見ない）。
      ★下の TABS は 2026-09-18 の一斉整理の記録なので、書き換えないこと。
      あとから増えた控えタブは、こうして名前で渡す。

  出力先 data/sheets/backup/<タブ名>.json.gz
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

# 削除の対象。docs/スプシ整理-2026売上.md の A群・B群
TABS = [
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

CLIENT = os.path.join(ROOT, 'tools', 'sheets_client.py')


def yomu(tab):
    r = subprocess.run(
        ['python3', CLIENT, 'read', SHEET, f"'{tab}'!A1:AZ2000"],
        capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        raise RuntimeError(f'{tab}: {r.stderr.strip()[:200]}')
    return json.loads(r.stdout)


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


def hikiwatasareta():
    """コマンドラインで渡されたタブ名。無ければ空。"""
    return [a for a in sys.argv[1:] if not a.startswith('--')]


def main():
    global TABS
    watasareta = hikiwatasareta()
    if watasareta:
        TABS = watasareta
        print(f'★ 渡されたタブだけを扱います: {TABS}')

    if '--verify' in sys.argv:
        print('--- 控えの検査 ---')
        sys.exit(0 if verify() else 1)

    os.makedirs(OUT, exist_ok=True)
    total = 0
    for tab in TABS:
        rows = yomu(tab)
        n = gyousuu(rows)
        if n == 0:
            # 空のものを控えても意味が無いどころか、
            # 「控えた」という誤った安心を生む
            print(f'★ {tab}  中身が空。控えを作らない')
            continue
        p = os.path.join(OUT, tab + '.json.gz')
        with gzip.open(p, 'wt', encoding='utf-8') as f:
            json.dump(rows, f, ensure_ascii=False)
        sz = os.path.getsize(p)
        total += sz
        print(f'  {tab}  {n}行  {sz:,} bytes')
    print(f'\n合計 {total:,} bytes')

    print('\n--- 取ったものを読み直して検査 ---')
    sys.exit(0 if verify() else 1)


if __name__ == '__main__':
    main()
