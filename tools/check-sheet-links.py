#!/usr/bin/env python3
"""スプレッドシートに入っている**第三者のサイト**を、セーフブラウジングに当てる。

    python3 tools/check-sheet-links.py            # 全部
    python3 tools/check-sheet-links.py --hayai    # 未判定のものだけ（2回目以降）

## なぜ要るか

`施設カード_進捗` には Places API で拾った**第三者のサイトが数百件**入っている。
**そのうちの1つが乗っ取られると、こちらのシートが巻き添えで「不審なファイル」になる。**

2026-09-20 に実際に起きた：スプレッドシート `2026_売上/顧客情報管理` に
Google の「不審なファイルです」警告が出た。
同じ日に、施設リストにあった `uenoland.com` が**韓国語のオンラインカジノ紹介サイトに
変わっていた**のも見つかっている（別件・ネット流入施策担当）。

**当社のホストを見る `check-safebrowsing.py` とは別物。**あちらは「自分の家」、これは「名簿に載っている他人の家」。

## 🔴 毎時の点検と同時に走らせないこと（2026-09-20 実害あり）

**`check-safebrowsing.py` と同じAPIを叩くので、レート制限を食い合う。**
この道具を裏で走らせたまま毎時の点検を回したところ、
**お客様が踏むホスト2つ（`lp.onehitter.jp`・`one-hitter.jp`）を含む4件が判定を取れなかった。**
止めたら全部すぐ取れた。

**当社のホストの点検が本業で、こちらは調べもの。**調べもののために本業を薄くしない。
**毎時ルーティンが走っていない時間に、1回ずつ手で回すこと。**
途中で止めても `--hayai` で続きから当たれる（判定済みは飛ばす）。

## 出るもの

`data/sheet-links-hantei.json` に判定を貯める。⚠ が出たら、その行を施設リストから外すこと。
"""

import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SID = '1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64'
KIROKU = os.path.join(ROOT, 'data', 'sheet-links-hantei.json')
URL = 'https://transparencyreport.google.com/transparencyreport/api/v3/safebrowsing/status?site='
LABEL = {1: '安全', 2: 'まだ判定なし', 3: '⚠ 安全でない', 4: '一部が安全でない', 6: 'データなし'}

# 当社のホストは check-safebrowsing.py の担当。ここでは見ない
JIBUN = re.compile(r'(onehitter|one-hitter|araidoki|oh-naibu)')
# 大手はいちいち当てない（判定は常に安全で、回数を食うだけ）
OOTE = re.compile(r'(google\.com|googleapis|instagram\.com|facebook\.com|twitter\.com|'
                  r'x\.com|youtube\.com|line\.me|apple\.com|amazon\.co)')

URLRE = re.compile(r'https?://([^/\s"\'()、。]+)')


def sheet_hosts():
    r = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'sheets_client.py'),
                        'tabs', SID], capture_output=True, text=True, timeout=120)
    tabs = [l.split(']', 1)[1].strip().rsplit('  (', 1)[0]
            for l in r.stdout.splitlines() if ']' in l]
    hosts = {}
    for t in tabs:
        rr = subprocess.run([sys.executable, os.path.join(ROOT, 'tools', 'sheets_client.py'),
                             'read', SID, f"'{t}'!A1:BZ1000", 'FORMULA'],
                            capture_output=True, text=True, timeout=240)
        if rr.returncode != 0:
            continue
        try:
            v = json.loads(rr.stdout)
        except Exception:
            continue
        for row in v:
            for cell in row:
                for h in URLRE.findall(str(cell)):
                    h = h.lower().rstrip('.')
                    if JIBUN.search(h) or OOTE.search(h):
                        continue
                    hosts.setdefault(h, set()).add(t)
    return hosts


def hantei(h):
    try:
        raw = urllib.request.urlopen(URL + h, timeout=20).read().decode('utf-8', 'ignore')
    except urllib.error.HTTPError as e:
        return None if e.code == 429 else f'HTTP {e.code}'
    except Exception:
        return None
    m = re.search(r'"sb\.ssr",(\d+)', raw)
    return int(m.group(1)) if m else None


def main():
    try:
        mae = json.load(open(KIROKU, encoding='utf-8'))
    except Exception:
        mae = {}

    print('⚠ この道具は check-safebrowsing.py と同じAPIを叩きます。'
          '毎時の点検と重なると、当社のホストの判定が取れなくなります。\n'
          '  重なっていそうなら Ctrl-C で止めて、あとで --hayai で続きから。\n')
    hosts = sheet_hosts()
    print(f'シートの中の第三者のサイト：{len(hosts)}ホスト\n')

    taisho = [h for h in hosts if not ('--hayai' in sys.argv and h in mae)]
    warui, toremasen = [], []
    for i, h in enumerate(sorted(taisho)):
        if i:
            time.sleep(4)          # 連続で叩くと 429 になる
        r = hantei(h)
        if r is None:
            toremasen.append(h)
            continue
        mae[h] = {'status': r, 'tabs': sorted(hosts[h])}
        if r in (3, 4):
            warui.append((h, r, sorted(hosts[h])))
            print(f'🔴 {h}: {LABEL.get(r, r)}   {sorted(hosts[h])}')

    os.makedirs(os.path.dirname(KIROKU), exist_ok=True)
    json.dump(mae, open(KIROKU, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1, sort_keys=True)

    print(f'\n判定できた {len(taisho) - len(toremasen)}／{len(taisho)}'
          f'　🔴 安全でない {len(warui)}件')
    if toremasen:
        print(f'※ レート制限で取れなかった {len(toremasen)}件。'
              f'--hayai を付けて後でやり直すと続きから当たります')
    if warui:
        print('\n★ 上のサイトを施設リストから外すこと。'
              'こちらのシートが巻き添えで「不審なファイル」になる。')
    return 1 if warui else 0


if __name__ == '__main__':
    sys.exit(main())
