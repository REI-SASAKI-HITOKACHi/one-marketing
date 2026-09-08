#!/usr/bin/env python3
"""冬季見込み客_2026 を「スマホで送信作業をするシート」に組み替える。

【なぜこの形か】
  和真はスマホで、このシートとSMS送信画面を往復する。
  タップ数をできるだけ減らすことが、1時間あたりの送信件数をそのまま決める。

  A 優先        … どの人から声をかけるか
  B 顧客名
  C 電話番号     … 数字だけ。コピーしてそのまま貼れる
  D ▶SMSを開く   … sms: リンク。タップすると宛先と本文が入った状態でSMSが開く
  E 送信する本文  … Dが効かない端末向けの控え。ここをコピーしても送れる
  F 送信済み     … プルダウン1タップ
  G 返信メモ
  H以降 これまでの情報（消していない）

【本文は1人ずつ変える】
  「○○さま、昨年11月に換気扇クリーニングでお世話になりました、渡辺です」
  のように、前回のメニューと時期を入れる。台帳にある情報を使わない手はない。

【送らない人】
  ・楽ラクーン経由      … オーナー指示で恒久除外
  ・直近3ヶ月に施工済み  … このタブの設計どおり
  ・固定電話・IP電話    … SMSが届かない
  ・電話番号なし        … 送れない
  スケジュールマッチング経由は、和真がF列で「対象外」にする運用に変わった
  （2026-09-08 オーナー指示）。こちらでは除外しない。

使い方: python3 tools/build-sms-list.py
"""
import importlib.util
import json
import re
import subprocess
import sys
import urllib.parse
from collections import Counter

ROOT = '/home/user/one-marketing'
spec = importlib.util.spec_from_file_location('sc', f'{ROOT}/tools/sheets_client.py')
sc = importlib.util.module_from_spec(spec)
sys.modules['sc'] = sc
spec.loader.exec_module(sc)

SS = '1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64'
TAB = '冬季見込み客_2026'
LP = 'https://one-hitter-nenmatsu.netlify.app/?src=sms'
TEL_UKETSUKE = '080-8043-8259'

# 1日の目標。これを超えて送れた日のために、本文は全員分そろえておく
MOKUHYOU = 20
HIZUKE = ['9/9', '9/10', '9/11', '9/12', '9/15', '9/16', '9/17', '9/18', '9/19',
          '9/20', '9/21']

tok = sc.access_token(sc.load_credentials())


def call(p, m='GET', pay=None, q=None):
    return sc.call(tok, urllib.parse.quote(p, safe='/:?&=,!'), method=m, payload=pay, query=q)


# ============================== 読み込み ==============================
# 列の位置ではなく「見出しの名前」で読む。
# 一度このスクリプトで並べ替えたあとに、もう一度実行しても壊れないようにするため。
# （2026-09-08、位置で読んで電話番号を消してしまった。バックアップから戻した）

BEK = {   # 見出しの別名。新しい並びでも古い並びでも同じ意味の列を拾えるように
    '氏名': ('氏名', '顧客名'),
    'TEL': ('TEL', '元の電話番号表記', '電話番号'),
    '優先': ('優先',),
    'セグメント': ('セグメント',),
    '法人/個人': ('法人/個人',),
    '送信系統': ('送信系統',),
    '受注回数': ('受注回数',),
    '累計売上': ('累計売上',),
    '平均単価': ('平均単価',),
    '最終施工日': ('最終施工日',),
    '経過(月)': ('経過(月)',),
    '冬季施工回数': ('冬季施工回数',),
    '施工メニュー（内訳）': ('施工メニュー（内訳）',),
    '今回おすすめ': ('今回おすすめ',),
    '主な流入経路': ('主な流入経路',),
    '利用年': ('利用年',),
    '送信済み': ('送信済み',),
    '返信メモ': ('返信メモ',),
}

nama = json.loads(subprocess.run(
    ['python3', f'{ROOT}/tools/sheets_client.py', 'read', SS, f'{TAB}!A1:Z1000'],
    capture_output=True, text=True).stdout)

midashi_gyou = None
for i, r in enumerate(nama):
    if any(str(c).strip() in ('氏名', '顧客名') for c in r):
        midashi_gyou = i
        break
if midashi_gyou is None:
    sys.exit('見出しの行が見つかりません。氏名か顧客名の列があるはずです。')
midashi = [str(c).strip() for c in nama[midashi_gyou]]
print('見出しの行:', midashi_gyou + 1, '／列数', len(midashi))


def sagasu(key):
    for na in BEK[key]:
        if na in midashi:
            return midashi.index(na)
    return None


ichi = {k: sagasu(k) for k in BEK}
if ichi['TEL'] is None or ichi['氏名'] is None:
    sys.exit('氏名かTELの列が見つかりません。')

rows = []
for r in nama[midashi_gyou + 1:]:
    if not any(str(c).strip() for c in r):
        continue
    d = {}
    for k, i in ichi.items():
        d[k] = str(r[i]).strip() if (i is not None and i < len(r)) else ''
    rows.append(d)
print('データ行:', len(rows))


def g(r, key):
    return r.get(key, '')


# ============================== 電話番号 ==============================
KEITAI = ('070', '080', '090')   # SMSが届くのは携帯だけ


def bangou(nama):
    sujji = re.sub(r'\D', '', nama)
    if not sujji:
        return '', '番号なし'
    if not (len(sujji) in (10, 11) and sujji.startswith('0')):
        return '', f'番号の形が不正（{nama}）'
    if not sujji.startswith(KEITAI):
        return '', '固定電話・IP電話のためSMSが届かない'
    return sujji, ''


# ============================== 本文 ==============================
def sei(shimei):
    """姓だけ取り出す。「佐藤　有司 実家」「大塚 娘」のような書き方にも耐える"""
    s = re.split(r'[\s　]+', shimei.strip())
    return s[0] if s and s[0] else shimei.strip()


def itsu(saishu):
    """2025/11/07 → 「昨年11月」「今年4月」。日付が読めなければ空"""
    m = re.match(r'(\d{4})[/-](\d{1,2})', saishu)
    if not m:
        return ''
    toshi, tsuki = int(m.group(1)), int(m.group(2))
    IMA = 2026
    if toshi == IMA:
        return f'今年{tsuki}月'
    if toshi == IMA - 1:
        return f'昨年{tsuki}月'
    return f'{toshi}年{tsuki}月'


# 内訳の表記をお客様に見せる言い方へ
IIKAE = {
    'エアコン(ノーマル)': 'エアコンクリーニング',
    'エアコン(ロボ)': 'お掃除機能付きエアコンのクリーニング',
    '天カセ': '天井カセットエアコンのクリーニング',
    'まるごと(備考に内容)': 'お住まいのクリーニング',
    'レンジフード': 'レンジフードクリーニング',
    '換気扇': '換気扇クリーニング',
    '浴室': '浴室クリーニング',
    'キッチン': 'キッチンクリーニング',
    '洗濯機': '洗濯機クリーニング',
    'トイレ': 'トイレクリーニング',
    '洗面台': '洗面台クリーニング',
    'コンロ': 'コンロクリーニング',
    '追い焚き': '追い焚き配管クリーニング',
    '床WAX': '床のワックスがけ',
}


def menu_hitotsu(uchiwake):
    """「浴室×3／エアコン(ロボ)×2」→「浴室クリーニング」。いちばん多いものを1つ"""
    if not uchiwake:
        return ''
    atama = uchiwake.split('／')[0]
    namae = atama.split('×')[0].strip()
    return IIKAE.get(namae, namae + 'のクリーニング' if namae else '')


def honbun(r, keitou):
    """1人ずつの本文を組み立てる。長くしすぎない"""
    na = sei(g(r, '氏名'))
    toki = itsu(g(r, '最終施工日'))
    men = menu_hitotsu(g(r, '施工メニュー（内訳）'))
    osu = g(r, '今回おすすめ').replace('・', 'と')

    # 送信主体。本舗経由のお客様は、屋号を出し分ける
    nanori = ('おそうじ本舗江戸川中央店の渡辺です'
              if keitou == '本舗' else 'ハウスクリーニング ワンヒッターの渡辺です')

    a = [f'{na}さま']
    if toki and men:
        a.append(f'{toki}に{men}でお世話になりました、{nanori}。')
    elif men:
        a.append(f'先日は{men}をご利用いただき、ありがとうございました。{nanori}。')
    else:
        a.append(f'いつもご利用ありがとうございます。{nanori}。')
    a.append('その後、お掃除した箇所の調子はいかがでしょうか。')
    a.append('12月から1箇所あたり3,300円の繁忙期加算がかかります。'
             '11月末までのご予約なら通常価格です。')
    if osu:
        a.append(f'{osu}もあわせてご検討いただけます。')
    a.append(f'ご予約・ご相談はこちら\n{LP}')
    a.append('ご不要でしたらご返信ください。以後お送りしません。')
    return '\n'.join(a)


def sms_link(num, text):
    """タップするとSMSが宛先・本文入りで開く。RFC5724 の sms:番号?body=…"""
    return 'sms:' + num + '?body=' + urllib.parse.quote(text, safe='')


# ============================== 判定 ==============================
mizumi = set()
data = []   # (区分, 理由, 番号, 本文)
for r in rows:
    keiro, seg = g(r, '主な流入経路'), g(r, 'セグメント')
    if seg.startswith('Z_'):
        data.append(('除外', '直近3ヶ月に施工済み', '', '')); continue
    if keiro == '楽ラクーン':
        data.append(('除外', '楽ラクーン経由（フォロー連絡不可）', '', '')); continue
    num, err = bangou(g(r, 'TEL'))
    if not num:
        data.append(('SMS不可', err + '／公式LINEか電話で拾う', '', '')); continue
    if num in mizumi:
        data.append(('除外', '同じ電話番号が他の行にもある', num, '')); continue
    mizumi.add(num)
    data.append(('送信可', '', num, honbun(r, g(r, '送信系統'))))

# ============================== 並べ替えとバッチ ==============================
def yuusen(r):
    v = g(r, '優先')
    return int(v) if v.isdigit() else 99


okuru = [i for i, d in enumerate(data) if d[0] == '送信可']
# 自社を先に、そのなかで優先順。同じ優先なら受注回数の多い順
okuru.sort(key=lambda i: (0 if g(rows[i], '送信系統') == '自社' else 1,
                          yuusen(rows[i]),
                          -int(g(rows[i], '受注回数') or 0)))
batch = {}
for n, i in enumerate(okuru):
    hi = n // MOKUHYOU
    batch[i] = HIZUKE[hi] if hi < len(HIZUKE) else 'KDDI一括'

# ============================== 並べ直した表を作る ==============================
ATAMA = ['優先', '顧客名', '電話番号', '▶SMSを開く', '送信する本文',
         '送信済み', '返信メモ', '送信日の目安', '配信区分', '送らない理由',
         'セグメント', '法人/個人', '送信系統', '受注回数', '累計売上', '平均単価',
         '最終施工日', '経過(月)', '冬季施工回数', '施工メニュー（内訳）',
         '今回おすすめ', '主な流入経路', '利用年', '元の電話番号表記', '予備']

atarashii = []
for i, r in enumerate(rows):
    kubun, riyuu, num, hon = data[i]
    link = ''
    if kubun == '送信可':
        # 数式に " が入ると壊れるので、本文側の " は全角に寄せる
        t = hon.replace('"', '”')
        link = f'=HYPERLINK("{sms_link(num, hon)}","▶ 送る")'
    atarashii.append([
        g(r, '優先'), g(r, '氏名'), ("'" + num) if num else '', link, hon,
        g(r, '送信済み'), g(r, '返信メモ'), batch.get(i, ''), kubun, riyuu,
        g(r, 'セグメント'), g(r, '法人/個人'), g(r, '送信系統'), g(r, '受注回数'), g(r, '累計売上'),
        g(r, '平均単価'), g(r, '最終施工日'), g(r, '経過(月)'), g(r, '冬季施工回数'), g(r, '施工メニュー（内訳）'),
        g(r, '今回おすすめ'), g(r, '主な流入経路'), g(r, '利用年'), g(r, 'TEL'), g(r, '送信済み'),
    ])

# 送信可を上に、そのなかは送る順。送らない人は下へ
juni = {v: k for k, v in enumerate(okuru)}
kumi = list(zip(range(len(rows)), atarashii))
kumi.sort(key=lambda x: (0 if x[1][8] == '送信可' else 1,
                         juni.get(x[0], 9999)))
atarashii = [x[1] for x in kumi]

# ============================== 書き込み ==============================
meta = call(f'/{SS}')
sh = next(s for s in meta['sheets'] if s['properties']['title'] == TAB)
SID = sh['properties']['sheetId']
gp = sh['properties']['gridProperties']
if gp['columnCount'] < len(ATAMA):
    call(f'/{SS}:batchUpdate', 'POST', {'requests': [{'updateSheetProperties': {
        'properties': {'sheetId': SID, 'gridProperties': {'columnCount': len(ATAMA)}},
        'fields': 'gridProperties.columnCount'}}]})

SETSUMEI = ('スマホでの送信作業用。C列の番号かD列の「▶送る」をタップ → SMSが開く → '
            '送信 → F列で「送信済み」を選ぶ。D列が反応しない端末では、'
            'E列の本文をコピーしてください。'
            'スケジュールマッチング経由で送ってはいけない先は、F列で「対象外」にしてください。')

# いったん広めに消してから書き直す
call(f'/{SS}/values/{TAB}!A1:Y1000:clear', 'POST', {})
call(f'/{SS}/values/{TAB}!A1', 'PUT', {'values': [
    ['冬季見込み客リスト 2026／SMS送信シート'],
    [SETSUMEI],
    [''],
    [''],
    ATAMA,
] + atarashii}, q={'valueInputOption': 'USER_ENTERED'})
print('書き直しました:', len(atarashii), '行 ×', len(ATAMA), '列')


def gr(r0, r1, c0=0, c1=len(ATAMA)):
    return {'sheetId': SID, 'startRowIndex': r0, 'endRowIndex': r1,
            'startColumnIndex': c0, 'endColumnIndex': c1}


n = len(atarashii)
req = [
    # 先に固定を解除する。固定列が残っていると見出しのマージができない
    {'updateSheetProperties': {
        'properties': {'sheetId': SID,
                       'gridProperties': {'frozenRowCount': 0, 'frozenColumnCount': 0}},
        'fields': 'gridProperties.frozenRowCount,gridProperties.frozenColumnCount'}},
    {'unmergeCells': {'range': gr(0, 5)}},
    # 列幅。スマホで見るのでA〜Gを優先する
    *[{'updateDimensionProperties': {
        'range': {'sheetId': SID, 'dimension': 'COLUMNS',
                  'startIndex': i, 'endIndex': i + 1},
        'properties': {'pixelSize': w}, 'fields': 'pixelSize'}}
      for i, w in enumerate([48, 150, 120, 80, 420, 100, 160, 90, 80, 220])],
    {'repeatCell': {
        'range': gr(0, 1),
        'cell': {'userEnteredFormat': {
            'backgroundColor': {'red': .055, 'green': .196, 'blue': .239},
            'textFormat': {'bold': True, 'fontSize': 13,
                           'foregroundColor': {'red': 1, 'green': 1, 'blue': 1}}}},
        'fields': 'userEnteredFormat(backgroundColor,textFormat)'}},
    {'mergeCells': {'range': gr(0, 1), 'mergeType': 'MERGE_ROWS'}},
    {'mergeCells': {'range': gr(1, 3), 'mergeType': 'MERGE_ALL'}},
    {'repeatCell': {
        'range': gr(1, 3),
        'cell': {'userEnteredFormat': {'wrapStrategy': 'WRAP', 'verticalAlignment': 'TOP',
                                       'textFormat': {'fontSize': 10}}},
        'fields': 'userEnteredFormat(wrapStrategy,verticalAlignment,textFormat)'}},
    {'repeatCell': {
        'range': gr(4, 5),
        'cell': {'userEnteredFormat': {
            'backgroundColor': {'red': .95, 'green': .94, 'blue': .92},
            'textFormat': {'bold': True, 'fontSize': 10},
            'wrapStrategy': 'WRAP'}},
        'fields': 'userEnteredFormat(backgroundColor,textFormat,wrapStrategy)'}},
    # 本文は折り返して全部見えるように
    {'repeatCell': {
        'range': gr(5, 5 + n, 4, 5),
        'cell': {'userEnteredFormat': {'wrapStrategy': 'WRAP', 'verticalAlignment': 'TOP',
                                       'textFormat': {'fontSize': 9}}},
        'fields': 'userEnteredFormat(wrapStrategy,verticalAlignment,textFormat)'}},
    # 電話番号は文字列
    {'repeatCell': {
        'range': gr(5, 5 + n, 2, 3),
        'cell': {'userEnteredFormat': {'numberFormat': {'type': 'TEXT'},
                                       'textFormat': {'fontSize': 12}}},
        'fields': 'userEnteredFormat(numberFormat,textFormat)'}},
    # ▶送る を目立たせる
    {'repeatCell': {
        'range': gr(5, 5 + n, 3, 4),
        'cell': {'userEnteredFormat': {
            'horizontalAlignment': 'CENTER', 'verticalAlignment': 'MIDDLE',
            'backgroundColor': {'red': .77, 'green': .27, 'blue': .11},
            'textFormat': {'bold': True, 'fontSize': 12,
                           'foregroundColor': {'red': 1, 'green': 1, 'blue': 1},
                           'underline': False}}},
        'fields': 'userEnteredFormat(horizontalAlignment,verticalAlignment,'
                  'backgroundColor,textFormat)'}},
    # F列 送信済み のプルダウン
    {'setDataValidation': {
        'range': gr(5, 5 + n, 5, 6),
        'rule': {'condition': {'type': 'ONE_OF_LIST', 'values': [
            {'userEnteredValue': v} for v in
            ['送信済み', '返信あり', '予約になった', '不通・エラー', '対象外']]},
            'showCustomUi': True, 'strict': False}}},
]
# 送らない人の行を灰色に
req.append({'addConditionalFormatRule': {'rule': {
    'ranges': [gr(5, 5 + n)],
    'booleanRule': {
        'condition': {'type': 'CUSTOM_FORMULA',
                      'values': [{'userEnteredValue': '=$I6<>"送信可"'}]},
        'format': {'backgroundColor': {'red': .93, 'green': .93, 'blue': .93},
                   'textFormat': {'foregroundColor':
                                  {'red': .55, 'green': .55, 'blue': .55}}}}},
    'index': 0}})
# 送信済みになった行を薄い緑に
req.append({'addConditionalFormatRule': {'rule': {
    'ranges': [gr(5, 5 + n)],
    'booleanRule': {
        'condition': {'type': 'CUSTOM_FORMULA',
                      'values': [{'userEnteredValue': '=$F6<>""'}]},
        'format': {'backgroundColor': {'red': .88, 'green': .95, 'blue': .91}}}},
    'index': 0}})

req.append({'updateSheetProperties': {
    'properties': {'sheetId': SID, 'gridProperties': {'frozenRowCount': 5}},
    'fields': 'gridProperties.frozenRowCount'}})

call(f'/{SS}:batchUpdate', 'POST', {'requests': req})
print('書式をつけました')

print()
print('=== 集計 ===')
for k, v in Counter(x[8] for x in atarashii).most_common():
    print(f'{v:5}  {k}')
print()
print('系統別（送信可のみ）')
okr = [x for x in atarashii if x[8] == '送信可']
print(' ', dict(Counter(x[12] for x in okr)))
print(' 優先別:', dict(sorted(Counter(x[0] for x in okr).items())))
print()
print('本文の長さ  最短', min(len(x[4]) for x in okr),
      '／ 最長', max(len(x[4]) for x in okr),
      '／ 平均', sum(len(x[4]) for x in okr) // len(okr))
print()
print('--- 本文の例（先頭3件）---')
for x in okr[:3]:
    print(f'\n[{x[1]}]\n{x[4]}')
