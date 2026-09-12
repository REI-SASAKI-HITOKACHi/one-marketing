#!/usr/bin/env python3
"""2026-09-12 セーフブラウジング事故のお詫びSMS用タブを作る。

対象：冬季見込み客_2026 で「送信済み」「返信あり」になっている自社系統の人
      （旧リンク one-hitter-booking.netlify.app を受け取った人。9/11 13:10 の控えと同じ人数で、
        9/12 の差し替え後に送った人はいない）。
      「不通・エラー」は届いていないので除外。本舗系統の人には URL を送っていないので除外。
名乗り：CLAUDE.md の決まりどおり、台帳の最新の施工の名義と機械で突き合わせ、自社でない人は入れない。
本文：netlify.app のリンクを入れない（事故報告 §4-1）。誘導は返信・電話・公式サイトのみ。

使い方: python3 tools/build-owabi-sms.py [--dry-run]
"""
import importlib.util, sys, urllib.parse, datetime
ROOT = '/home/user/one-marketing'
DRY = '--dry-run' in sys.argv
def _load(name, path):
    s = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(s)
    sys.modules[name] = m; s.loader.exec_module(m); return m
sc = _load('sc', f'{ROOT}/tools/sheets_client.py')
dsk = _load('dsk', f'{ROOT}/tools/derive-soushin-keitou.py')

SS = '1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64'
MOTO = '冬季見込み客_2026'
TAB = 'お詫びSMS_20260912'
SMS_PAGE = 'https://oh-naibu-sms-k7q3x.netlify.app/s.html'
TEL = '080-8043-8259'

HONBUN = (
    '{name}さま\n'
    'ワンヒッター株式会社の渡辺でございます。\n'
    '先日お送りしたご案内のリンクを開くと「危険なサイト」と警告が出る状態になっており、'
    'ご心配をおかけして誠に申し訳ございません。\n'
    'Googleの安全確認の誤判定によるもので、ページはご予約の受付のみで、ウイルス等は含まれておりません。'
    '現在Googleへ見直しを申請しております。\n'
    'ご予約・ご相談は、このSMSへの返信か、お電話（' + TEL + '）で承ります。\n'
    '公式サイト https://one-hitter.jp/\n'
    'お手数をおかけし、重ねてお詫び申し上げます。'
)

def sms_link(num, text):
    return SMS_PAGE + '#to=' + urllib.parse.quote(num, safe='') + '&b=' + urllib.parse.quote(text, safe='')

tok = sc.access_token(sc.load_credentials())
call = lambda p, m='GET', pay=None: sc.call(tok, urllib.parse.quote(p, safe='/:?&=,!'), method=m, payload=pay)
rows = call(f'/{SS}/values/{MOTO}!A1:Z1200')['values']
hi = next(i for i, r in enumerate(rows) if '送信済み' in r and '電話番号' in r)
h = rows[hi]
def g(r, k):
    i = h.index(k); return r[i] if i < len(r) else ''
H = dsk.meigi_hyou()
taishou, jogai = [], []
for r in rows[hi + 1:]:
    st = g(r, '送信済み')
    if st not in ('送信済み', '返信あり'):
        continue
    name, num = g(r, '顧客名'), dsk.tel_norm(g(r, '電話番号'))
    m = dsk.meigi_shiraberu(H, g(r, '元の電話番号表記') or num, name)
    if not m or m[0] != '自社' or g(r, '送信系統') != '自社':
        jogai.append((name, st, g(r, '送信系統'), m and m[0])); continue
    if not num:
        jogai.append((name, st, '電話番号なし', '')); continue
    hon = HONBUN.format(name=name)
    taishou.append([name, "'" + num, '▶ 送る', '', hon, st, g(r, '返信メモ')])
print('対象', len(taishou), '件／除外', len(jogai), '件')
for j in jogai: print('  除外:', j)
print('本文の長さ', len(HONBUN.format(name='山田')), '文字')
if DRY:
    print('\n' + HONBUN.format(name='山田')); print('\n--dry-run のため書いていません'); sys.exit(0)

meta = call(f'/{SS}')
sh = next((s for s in meta['sheets'] if s['properties']['title'] == TAB), None)
if sh is None:
    res = call(f'/{SS}:batchUpdate', 'POST', {'requests': [{'addSheet': {'properties': {
        'title': TAB, 'gridProperties': {'rowCount': len(taishou) + 10, 'columnCount': 7, 'frozenRowCount': 3}}}}]})
    SID = res['replies'][0]['addSheet']['properties']['sheetId']
else:
    SID = sh['properties']['sheetId']
    call(f'/{SS}/values/{TAB}!A1:G1000:clear', 'POST', {})
SETSUMEI = ('【お詫びSMS】9/9〜11 に旧リンク付きの案内を送った自社名義のお客様。C列をタップ→SMSが開く→送信→D列で「送信済み」。'
            '本文にリンクは入れていません（新リンクは送らない。返信・電話で受ける）。1日30件まで、10〜19時。'
            f' 作成 {datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))):%Y-%m-%d %H:%M} CMO')
ATAMA = ['顧客名', '電話番号', '▶SMSを開く', '送信済み', '送信する本文', '元の状態', '返信メモ']
call(f'/{SS}/values/{TAB}!A1?valueInputOption=USER_ENTERED', 'PUT',
     {'values': [[SETSUMEI], [''], ATAMA] + taishou})
n = len(taishou)
gyou = [{'values': [{'userEnteredValue': {'stringValue': '▶ 送る'},
                     'textFormatRuns': [{'startIndex': 0, 'format': {'link': {'uri': sms_link(t[1][1:], t[4])}}}]}]}
        for t in taishou]
call(f'/{SS}:batchUpdate', 'POST', {'requests': [
    {'updateCells': {'range': {'sheetId': SID, 'startRowIndex': 3, 'endRowIndex': 3 + n, 'startColumnIndex': 2, 'endColumnIndex': 3},
                     'rows': gyou, 'fields': 'userEnteredValue,textFormatRuns'}},
    {'setDataValidation': {'range': {'sheetId': SID, 'startRowIndex': 3, 'endRowIndex': 3 + n, 'startColumnIndex': 3, 'endColumnIndex': 4},
                           'rule': {'condition': {'type': 'ONE_OF_LIST', 'values': [{'userEnteredValue': v} for v in ['送信済み', '返信あり', '不通・エラー', '対象外']]},
                                    'showCustomUi': True, 'strict': False}}},
    {'updateDimensionProperties': {'range': {'sheetId': SID, 'dimension': 'COLUMNS', 'startIndex': 4, 'endIndex': 5},
                                   'properties': {'pixelSize': 420}, 'fields': 'pixelSize'}},
    {'repeatCell': {'range': {'sheetId': SID, 'startRowIndex': 0, 'endRowIndex': 1, 'startColumnIndex': 0, 'endColumnIndex': 7},
                    'cell': {'userEnteredFormat': {'wrapStrategy': 'WRAP'}}, 'fields': 'userEnteredFormat.wrapStrategy'}},
    {'mergeCells': {'range': {'sheetId': SID, 'startRowIndex': 0, 'endRowIndex': 1, 'startColumnIndex': 0, 'endColumnIndex': 7}, 'mergeType': 'MERGE_ALL'}},
    {'updateDimensionProperties': {'range': {'sheetId': SID, 'dimension': 'ROWS', 'startIndex': 0, 'endIndex': 1},
                                   'properties': {'pixelSize': 70}, 'fields': 'pixelSize'}},
]})
print(f'タブ {TAB} に {n} 件書きました。sheetId={SID}')
