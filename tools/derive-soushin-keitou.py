#!/usr/bin/env python3
"""冬季見込み客_2026 の「送信系統」列を、台帳の「最新の施工の売上種類」から決め直す。

決まり（2026-09-11 オーナー）：
  「経路については最新が ONE-HITTER になっていれば、ONE-HITTER へ転換が成功している顧客」
  → 最新の施工が One Hitter 名義なら 自社、本舗名義なら 本舗。

台帳の読み方：
  2024〜2026年：各月タブの「売上種類」列（One Hitter／本舗／下請）
  2023年      ：「売上種類」列が無く、先頭の「流入経路」列に 本舗／One Hitter／本舗(ロイ)／下請 が入っている
                （その年の集計行が「自社件数／本舗件数／下請件数」なので、これが名義）
  下請、空欄  ：決められないので変えない

使い方：
  python3 tools/derive-soushin-keitou.py            # 差分を表示するだけ
  python3 tools/derive-soushin-keitou.py --write    # 送信系統列に書く（先に控えを取ること）
  --cache <path> … 台帳48タブの読み込み結果をJSONに控える／控えがあれば読む（APIの回数制限よけ）
"""
import collections, datetime, importlib.util, json, pathlib, re, sys, urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('sc', ROOT / 'tools' / 'sheets_client.py')
sc = importlib.util.module_from_spec(spec); spec.loader.exec_module(sc)
tok = sc.access_token(sc.load_credentials())

BOOKS = {'2023': '1mOGaxy5viO4peUUQqgJYQ9gp0tuev2c_Y8DrdDy-y3M',
         '2024': '1Q-dJ0Rh2AeYGhNYUyqoKOkG_Kgq4e1M0KcwkhMFb0J4',
         '2025': '1cpN2tu6NNIA5FSAAC3ejCK0jNNFNfn7GCwq0ghggK3o',
         '2026': '1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64'}
SS = BOOKS['2026']; TAB = '冬季見込み客_2026'
MEIGI = {'One Hitter': '自社', '本舗': '本舗', '本舗(ロイ)': '本舗'}


def tel_norm(t): return re.sub(r'\D', '', str(t or ''))
def name_norm(n): return re.sub(r'\s', '', str(n or ''))


def yomu_shikou():
    jobs = []
    for y, ss in BOOKS.items():
        meta = sc.call(tok, f'/{ss}', query={'fields': 'sheets.properties.title'})
        tabs = [s['properties']['title'] for s in meta['sheets'] if re.match(r'^\d{1,2}月_売上', s['properties']['title'])]
        for tab in tabs:
            v = sc.call(tok, f"/{ss}/values/{urllib.parse.quote(tab + '!A1:T500', safe='')}").get('values', [])
            hi = next((i for i, r in enumerate(v) if '施工日付' in r), None)
            if hi is None: continue
            h = v[hi]; ix = {c: i for i, c in enumerate(h)}
            g = lambda r, k: (r[ix[k]] if k in ix and ix[k] < len(r) else '').strip()
            for r in v[hi + 1:]:
                m = re.match(r'(\d{4})/(\d{1,2})/(\d{1,2})', g(r, '施工日付'))
                if not m: continue
                meigi = g(r, '売上種類') if '売上種類' in ix else g(r, '流入経路')   # 2023 は流入経路列が名義
                jobs.append((datetime.date(int(m[1]), int(m[2]), int(m[3])), tel_norm(g(r, 'TEL(-無し)')),
                             name_norm(g(r, '氏名')), meigi))
    return jobs


def main():
    write = '--write' in sys.argv
    cache = pathlib.Path(sys.argv[sys.argv.index('--cache') + 1]) if '--cache' in sys.argv else None
    if cache and cache.exists():
        jobs = [(datetime.date.fromisoformat(a), b, c, d) for a, b, c, d in json.load(open(cache))]
    else:
        jobs = yomu_shikou()
        if cache: json.dump([(str(a), b, c, d) for a, b, c, d in jobs], open(cache, 'w'), ensure_ascii=False)
    by_tel, by_name = collections.defaultdict(list), collections.defaultdict(list)
    for j in jobs:
        if j[1]: by_tel[j[1]].append(j)
        if j[2]: by_name[j[2]].append(j)
    v = sc.call(tok, f"/{SS}/values/{urllib.parse.quote(TAB + '!A1:Y1000', safe='')}")['values']
    hi = next(i for i, row in enumerate(v) if '送信系統' in row); h = v[hi]; ix = {c: i for i, c in enumerate(h)}
    g = lambda row, k: (row[ix[k]] if ix.get(k) is not None and ix[k] < len(row) else '')
    col = ix['送信系統']
    henkou, riyuu = [], collections.Counter()
    for n, row in enumerate(v[hi + 1:], start=hi + 2):   # n = シートの行番号
        ima = g(row, '送信系統')
        if not ima: continue
        cand = by_tel.get(tel_norm(g(row, '元の電話番号表記') or g(row, '電話番号'))) or by_name.get(name_norm(g(row, '顧客名')), [])
        cand = [c for c in cand if c[3] in MEIGI]
        if not cand:
            # 決められない行のうち、「オーナーに確認中」で保留にしていた行だけは、安全側（本舗）に倒す。
            # 本舗の文面はワンヒッターの名前もURLも出さないので、取り違えても本舗との関係を傷めない。
            if ima == '自社' and 'オーナーに確認中' in g(row, '送らない理由'):
                henkou.append((n, g(row, '顧客名'), ima, '本舗', '-', '名義の記録なし→安全側', g(row, '配信区分'), bool(g(row, '送信済み'))))
                riyuu['自社→本舗（決められないので安全側）'] += 1
            else:
                riyuu['決められない（名義の記録なし）'] += 1
            continue
        L = max(cand, key=lambda c: c[0])
        atarashii = MEIGI[L[3]]
        if atarashii != ima:
            henkou.append((n, g(row, '顧客名'), ima, atarashii, str(L[0]), L[3], g(row, '配信区分'), bool(g(row, '送信済み'))))
        riyuu[f'{ima}→{atarashii}'] += 1
    print('内訳:', dict(riyuu))
    print(f'変更 {len(henkou)} 行')
    for x in henkou[:200]:
        print(' 行%d %s: %s→%s（最新 %s %s／%s%s）' % (x[0], x[1], x[2], x[3], x[4], x[5], x[6], '・送信済み' if x[7] else ''))
    if not write:
        print('\n--write を付けると送信系統列に書きます'); return
    data = [{'range': f"{TAB}!{chr(ord('A') + col)}{x[0]}", 'values': [[x[3]]]} for x in henkou]
    for i in range(0, len(data), 100):
        sc.call(tok, f'/{SS}/values:batchUpdate', method='POST',
                payload={'valueInputOption': 'RAW', 'data': data[i:i + 100]})
    print(f'書きました: {len(data)} セル')


if __name__ == '__main__':
    main()
