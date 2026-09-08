#!/usr/bin/env python3
"""T027 既存客への一斉送信リストを作る。

タブは増やさない。冬季見込み客_2026 に3列（配信区分／除外・保留の理由／送信バッチ）
を足すだけにする。

除外のルール
  ・Z_直近施工          … このタブの設計どおり、今回は送らない
  ・楽ラクーン経由      … オーナー指示で恒久除外（フォロー連絡不可）
  ・スケジュールマッチング … 規約で直接取引が禁じられていないか未確認のため保留
  ・電話番号なし        … SMSが送れない。公式LINE側で拾う

系統は必ず分ける（docs/SMS配信のリンク設計.md）。
本舗経由のお客様は送信主体が「おそうじ本舗江戸川中央店」になるため、
自社顧客と同じ文面で送ってはいけない。
"""
import json
import re
import subprocess
import importlib.util
import sys
import urllib.parse
from collections import Counter

spec = importlib.util.spec_from_file_location('sc', '/home/user/one-marketing/tools/sheets_client.py')
sc = importlib.util.module_from_spec(spec)
sys.modules['sc'] = sc
spec.loader.exec_module(sc)

SS = '1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64'
TAB = '冬季見込み客_2026'
tok = sc.access_token(sc.load_credentials())


def call(p, m='GET', pay=None, q=None):
    return sc.call(tok, urllib.parse.quote(p, safe='/:?&=,!'), method=m, payload=pay, query=q)


rows = json.loads(subprocess.run(
    ['python3', '/home/user/one-marketing/tools/sheets_client.py', 'read', SS,
     f'{TAB}!A6:Q1000'], capture_output=True, text=True).stdout)


def g(r, i):
    return str(r[i]).strip() if i < len(r) else ''


# SMSが届くのは携帯だけ。固定電話（03など）とIP電話（050）には届かない。
KEITAI = ('070', '080', '090')


def bangou(nama: str):
    """電話番号を数字だけにして、SMSが届く形かどうかを見る。
    「0364555092 （青山リアルティ様）」のような注記つきも拾えるようにする。"""
    sujji = re.sub(r'\D', '', nama)
    if not sujji:
        return '', '番号なし'
    if not (len(sujji) in (10, 11) and sujji.startswith('0')):
        return '', f'番号の形が不正（{nama}）'
    if not sujji.startswith(KEITAI):
        return '', f'固定電話・IP電話のためSMSが届かない（{nama}）'
    return sujji, ''


mizumi = set()   # 重複した番号をはじく
kekka = []       # (配信区分, 理由, 正規化番号)
for r in rows:
    seg, keiro, tel = g(r, 1), g(r, 14), g(r, 5)
    if seg.startswith('Z_'):
        kekka.append(('除外', '直近3ヶ月に施工済み', '')); continue
    if keiro == '楽ラクーン':
        kekka.append(('除外', '楽ラクーン経由（フォロー連絡不可）', '')); continue
    if keiro == 'スケジュールマッチング':
        kekka.append(('保留', 'マッチングPFの規約を確認するまで送らない', '')); continue
    num, err = bangou(tel)
    if not num:
        kekka.append(('SMS不可', err + '／公式LINE側で拾う', '')); continue
    if num in mizumi:
        kekka.append(('除外', '同じ電話番号が他の行にもある', num)); continue
    mizumi.add(num)
    kekka.append(('送信可', '', num))

# ---------- バッチを振る ----------
# 手作業で送れる量に合わせる。優先の高い順、自社系統から。
HITOHI = 10          # 1日あたりの件数（和真がスマホから手で送る）
KAISHI = '9/9'

okuru = [(i, r) for i, (r, k) in enumerate(zip(rows, kekka)) if k[0] == '送信可']


def yuusen(r):
    v = g(r, 0)
    return int(v) if v.isdigit() else 99


# 自社を先に、そのなかで優先順。本舗はKDDI開通後にまとめて送る
jisha = sorted([(i, r) for i, r in okuru if g(r, 3) == '自社'],
               key=lambda x: (yuusen(x[1]), -len(g(x[1], 12))))
honpo = sorted([(i, r) for i, r in okuru if g(r, 3) != '自社'],
               key=lambda x: (yuusen(x[1]), -len(g(x[1], 12))))

TEBIKI = 90          # 手作業フェーズで送る上限（9日分）
batch = {}
hizuke = ['9/9', '9/10', '9/11', '9/12', '9/15', '9/16', '9/17', '9/18', '9/19']
for n, (i, r) in enumerate(jisha):
    if n < TEBIKI:
        batch[i] = f'手動{hizuke[n // HITOHI]}'
    else:
        batch[i] = 'KDDI一括（自社）'
for i, r in honpo:
    batch[i] = 'KDDI一括（本舗）'

# ---------- 書き込み ----------
atama = [['配信区分', '除外・保留の理由', '送信バッチ', '正規化した電話番号']]
body = []
for i, (kubun, riyuu, num) in enumerate(kekka):
    body.append([kubun, riyuu, batch.get(i, ''), ("'" + num) if num else ''])

call(f'/{SS}/values/{TAB}!R5', 'PUT', {'values': atama + body},
     q={'valueInputOption': 'USER_ENTERED'})
print('列を追記しました（R〜U）:', len(body), '行')

meta = call(f'/{SS}')
SID = next(s['properties']['sheetId'] for s in meta['sheets']
           if s['properties']['title'] == TAB)
call(f'/{SS}:batchUpdate', 'POST', {'requests': [
    {'repeatCell': {
        'range': {'sheetId': SID, 'startRowIndex': 4, 'endRowIndex': 5,
                  'startColumnIndex': 17, 'endColumnIndex': 21},
        'cell': {'userEnteredFormat': {
            'backgroundColor': {'red': .95, 'green': .94, 'blue': .92},
            'textFormat': {'bold': True}}},
        'fields': 'userEnteredFormat(backgroundColor,textFormat)'}},
    {'repeatCell': {
        'range': {'sheetId': SID, 'startRowIndex': 5, 'endRowIndex': 5 + len(body),
                  'startColumnIndex': 20, 'endColumnIndex': 21},
        'cell': {'userEnteredFormat': {'numberFormat': {'type': 'TEXT'}}},
        'fields': 'userEnteredFormat.numberFormat'}},
] + [
    {'addConditionalFormatRule': {'rule': {
        'ranges': [{'sheetId': SID, 'startRowIndex': 5, 'endRowIndex': 5 + len(body),
                    'startColumnIndex': 17, 'endColumnIndex': 18}],
        'booleanRule': {
            'condition': {'type': 'TEXT_EQ', 'values': [{'userEnteredValue': go}]},
            'format': {'backgroundColor': {'red': iro[0], 'green': iro[1], 'blue': iro[2]}}}},
        'index': 0}}
    for go, iro in (('送信可', (.84, .94, .89)), ('保留', (1, .95, .80)),
                    ('除外', (.93, .93, .93)), ('SMS不可', (1, .89, .87)))
]})
print('書式をつけました')

print()
print('=== 集計 ===')
for k, v in Counter(x[0] for x in kekka).most_common():
    print(f'{v:5}  {k}')
print()
print('送信可の内訳')
for k, v in sorted(Counter(batch.values()).items()):
    print(f'{v:5}  {k}')

# 手作業フェーズの一覧を、そのままLINEに貼れる形で書き出す
with open('/tmp/claude-0/-home-user-one-marketing/'
          '34dbdc4b-4c9e-56e1-b31d-44fec5a0facf/scratchpad/sms_batches.json', 'w',
          encoding='utf-8') as f:
    out = {}
    for i, r in jisha[:TEBIKI]:
        b = batch[i]
        out.setdefault(b, []).append({
            'name': g(r, 4), 'tel': kekka[i][2], 'yuusen': yuusen(r),
            'menu': g(r, 12), 'osusume': g(r, 13),
            'saishu': g(r, 9), 'keika': g(r, 10),
        })
    json.dump(out, f, ensure_ascii=False, indent=1)
print('\n手作業フェーズの一覧を sms_batches.json に書き出しました')
