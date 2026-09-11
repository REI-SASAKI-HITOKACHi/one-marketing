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
  --cache <path> … 控えの場所（既定 ~/.cache/one-hitter/meigi-cache.json。gitの外）
  --saidoku      … 控えが新しくても台帳48タブを読み直す
"""
import collections, datetime, importlib.util, json, pathlib, re, sys, urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('sc', ROOT / 'tools' / 'sheets_client.py')
sc = importlib.util.module_from_spec(spec); spec.loader.exec_module(sc)
_tok = None


def tok_get():
    """認証は最初に使うときだけ行う。import しただけでは認証しない（認証の無い環境で import しても落ちない。顧客接点担当の指摘 2026-09-11）。"""
    global _tok
    if _tok is None:
        _tok = sc.access_token(sc.load_credentials())
    return _tok

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
        meta = sc.call(tok_get(), f'/{ss}', query={'fields': 'sheets.properties.title'})
        tabs = [s['properties']['title'] for s in meta['sheets'] if re.match(r'^\d{1,2}月_売上', s['properties']['title'])]
        for tab in tabs:
            v = sc.call(tok_get(), f"/{ss}/values/{urllib.parse.quote(tab + '!A1:T500', safe='')}").get('values', [])
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


CACHE_KITEI = pathlib.Path.home() / '.cache' / 'one-hitter' / 'meigi-cache.json'   # gitの外（電話番号と氏名が入る）
CACHE_JUMYOU = 12 * 3600   # 秒。これより古い控えは読み直す（台帳は毎日増える）


def jobs_yomu(cache=None, saidoku=False):
    """施工の一覧を返す。控えがあって新しければそれを使う。"""
    import time
    cache = pathlib.Path(cache) if cache else CACHE_KITEI
    if cache.exists() and not saidoku and time.time() - cache.stat().st_mtime < CACHE_JUMYOU:
        return [(datetime.date.fromisoformat(a), b, c, d) for a, b, c, d in json.load(open(cache))]
    jobs = yomu_shikou()
    cache.parent.mkdir(parents=True, exist_ok=True)
    json.dump([(str(a), b, c, d) for a, b, c, d in jobs], open(cache, 'w'), ensure_ascii=False)
    return jobs


def meigi_hyou(cache=None):
    """電話番号→(名義, 最新施工日) と 氏名→(名義, 最新施工日) の2つの辞書を返す。
    名義は 自社／本舗。決められないお客様は入っていない。
    他のツール（build-sms-list.py など）はこれで送信系統を照合する。"""
    jobs = jobs_yomu(cache)
    by_tel, by_name = collections.defaultdict(list), collections.defaultdict(list)
    for j in jobs:
        if j[3] not in MEIGI: continue
        if j[1]: by_tel[j[1]].append(j)
        if j[2]: by_name[j[2]].append(j)
    saishin = lambda L: (lambda j: (MEIGI[j[3]], str(j[0])))(max(L, key=lambda c: c[0]))
    return {k: saishin(L) for k, L in by_tel.items()}, {k: saishin(L) for k, L in by_name.items()}


def meigi_shiraberu(hyou, tel, name):
    """(名義, 最新施工日) か None。電話番号で引いたものと氏名で引いたものを合わせ、いちばん新しい施工の名義を返す。
    台帳には同じお客様でも電話番号が空の行・別の番号の行があるので（2026-09-11 に2件確認）、片方だけでは最新を取り逃す。"""
    by_tel, by_name = hyou
    kouho = [x for x in (by_tel.get(tel_norm(tel)), by_name.get(name_norm(name))) if x]
    return max(kouho, key=lambda x: x[1]) if kouho else None


def main():
    write = '--write' in sys.argv
    cache = sys.argv[sys.argv.index('--cache') + 1] if '--cache' in sys.argv else None
    jobs = jobs_yomu(cache, saidoku='--saidoku' in sys.argv)
    by_tel, by_name = collections.defaultdict(list), collections.defaultdict(list)
    for j in jobs:
        if j[1]: by_tel[j[1]].append(j)
        if j[2]: by_name[j[2]].append(j)
    v = sc.call(tok_get(), f"/{SS}/values/{urllib.parse.quote(TAB + '!A1:Y1000', safe='')}")['values']
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
        sc.call(tok_get(), f'/{SS}/values:batchUpdate', method='POST',
                payload={'valueInputOption': 'RAW', 'data': data[i:i + 100]})
    print(f'書きました: {len(data)} セル')


if __name__ == '__main__':
    main()
