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
# 誘導先。既存のお客様なので、売り込みのページではなく申込フォームへ直接送る
# （2026-09-08 オーナー指示「LPではなく申込フォームを送る」）
#
#   MOUSHIKOMI  … いま送れるもの。年末LPの申込フォームに直接着地する
#   YOYAKU_FORM … 既存客向けの予約フォーム。空き枠から選べる。
#                 T022（Apps Scriptのデプロイ）が終わったら MOUSHIKOMI をこちらに差し替える
#
# ★ 2026-09-08、誘導先を one-hitter-nenmatsu.netlify.app から
#   one-hitter-lp.netlify.app/nenmatsu/ へ変えた。
#   前者は申込フォームが動いていなかった（POSTが404、遷移先のthanksも404）。
#   お客様が申し込めないページへ送るところだった。実測で確認済み。
MOUSHIKOMI = 'https://one-hitter-lp.netlify.app/nenmatsu/?src=sms#form'
YOYAKU_FORM = 'https://one-hitter-booking.netlify.app/?src=sms'

TEL_UKETSUKE = '080-8043-8259'    # ワンヒッターの受付（和真）
TEL_HONPO = '080-1344-3137'       # おそうじ本舗としての受付（和真）
# ★この2つを取り違えないこと。本舗のお客様にワンヒッターの番号を出してはいけない。

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
    # 前回の実行で入れたテスト行は読み飛ばす（毎回入れ直すため）
    if any(str(c).strip().startswith('【実機テスト】') for c in r[:3]):
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


# ============================== 次にすすめる箇所 ==============================
# 2026-09-08 オーナー決定のルール。
#   ・前回がエアコン                    → 水まわりをすすめる
#   ・前回がエアコン以外で1年以上たっている → 同じ箇所をもう一度
#   ・前回がエアコン以外で1年未満        → まだやっていない別の箇所
#
# 料金には触れない。箇所の提案だけをする。

MIZUMAWARI = '浴室やキッチンなどの水まわり'

# まだやっていない箇所を出すときの順番。上から、まだの箇所を選ぶ
HOKA_NO_JUNBAN = [
    ('浴室', '浴室クリーニング'),
    ('レンジフード', 'レンジフードクリーニング'),
    ('換気扇', '換気扇クリーニング'),
    ('キッチン', 'キッチンクリーニング'),
    ('洗濯機', '洗濯機クリーニング'),
    ('トイレ', 'トイレクリーニング'),
    ('洗面台', '洗面台クリーニング'),
]


def yatta(uchiwake):
    """施工メニュー（内訳）から、やったことのある箇所の名前を集める"""
    out = set()
    for koma in (uchiwake or '').split('／'):
        na = koma.split('×')[0].strip()
        if na:
            out.add(na)
    return out


def eakon_ka(na):
    return na.startswith('エアコン') or na in ('天カセ',)


def teian(r):
    """次にすすめる箇所を1つ返す"""
    uchiwake = g(r, '施工メニュー（内訳）')
    zenkai = (uchiwake.split('／')[0].split('×')[0].strip()) if uchiwake else ''
    if not zenkai:
        return ''
    if eakon_ka(zenkai):
        return MIZUMAWARI
    try:
        keika = float(g(r, '経過(月)') or 0)
    except ValueError:
        keika = 0
    if keika >= 12:
        return menu_hitotsu(uchiwake)          # 同じ箇所をもう一度
    sumi = yatta(uchiwake)
    for na, iikata in HOKA_NO_JUNBAN:
        if na not in sumi:
            return iikata                       # まだやっていない別の箇所
    return MIZUMAWARI


# 本文のひな形は「送信系統ごと」に持つ。
#
# 本舗経由のお客様には、おそうじ本舗として営業する。
# ワンヒッターへの打診（OH打診）は、和真が現場で接客しながら人が判断すること。
# SMSで一律にやることではない（2026-09-08 オーナー指摘）。
#
# ひな形が空の系統は「保留」になり、本文もSMSリンクも作らない。
# 誤って送ることがないようにするため。
HINAGATA_PATH = {
    '自社': f'{ROOT}/data/sms-template.txt',
    '本舗': f'{ROOT}/data/sms-template-honpo.txt',
}


def hinagata(path):
    """# で始まる行を落として、本文のひな形だけ返す。空なら空リストを返す"""
    gyou = []
    for ln in open(path, encoding='utf-8').read().split('\n'):
        if ln.lstrip().startswith('#'):
            continue
        gyou.append(ln)
    while gyou and not gyou[0].strip():
        gyou.pop(0)
    while gyou and not gyou[-1].strip():
        gyou.pop()
    return gyou


HINAGATA = {k: hinagata(v) for k, v in HINAGATA_PATH.items()}
if not HINAGATA['自社']:
    sys.exit(f"{HINAGATA_PATH['自社']} に本文がありません。")
for k, v in HINAGATA.items():
    print(f'ひな形 {k}:', '未確定（この系統は保留になります）' if not v else f'{len(v)}行')
SASHIKOMI = re.compile(r'"([^"]+)"')


def honbun(r, keitou):
    """ひな形の "…" を1人ずつの値に差し替える。
    差し替えるものが空だった行は、その行ごと落とす。
    （「昨年11月に…でお世話になりました」が「に でお世話になりました」に
      なってしまうのを防ぐため）"""
    atai = {
        '顧客名': sei(g(r, '氏名')),
        'フルネーム': g(r, '氏名'),
        '名乗り': ('おそうじ本舗の渡辺です' if keitou == '本舗'
                   else 'ハウスクリーニング ワンヒッターの渡辺です'),
        '施工時期': itsu(g(r, '最終施工日')),
        '前回メニュー': menu_hitotsu(g(r, '施工メニュー（内訳）')),
        'おすすめ': g(r, '今回おすすめ').replace('・', 'と'),
        'ご提案': teian(r),
        '申込フォームURL': MOUSHIKOMI,
        '予約フォームURL': YOYAKU_FORM,
        '電話番号': TEL_UKETSUKE,
        '本舗の電話番号': TEL_HONPO,
    }
    kata = HINAGATA.get(keitou if keitou in HINAGATA else '自社', [])
    if not kata:
        return ''          # ひな形が無い系統は本文を作らない
    shiranai = set()
    dekita = []
    for ln in kata:
        kara = False

        def hiku(m):
            nonlocal kara
            key = m.group(1)
            if key not in atai:
                shiranai.add(key)
                return m.group(0)      # 知らない目印はそのまま残す
            v = atai[key]
            if not v:
                kara = True
            return v

        atarashii_gyou = SASHIKOMI.sub(hiku, ln)
        if kara:
            continue                    # 差し替えるものが空なら、その行は出さない
        dekita.append(atarashii_gyou)
    if shiranai:
        SHIRANAI.update(shiranai)
    # 続いた空行はひとつにまとめる
    out = []
    for ln in dekita:
        if not ln.strip() and (not out or not out[-1].strip()):
            continue
        out.append(ln)
    return '\n'.join(out).strip()


SHIRANAI = set()   # ひな形に出てきた、知らない差し込みの目印


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
    keitou = g(r, '送信系統')
    hon = honbun(r, keitou)
    if not hon:
        data.append(('保留', f'{keitou}向けの文面が未確定。'
                     f'{HINAGATA_PATH.get(keitou, "")} を埋めると送信可になります',
                     num, ''))
        continue
    data.append(('送信可', '', num, hon))

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

# ============================== 実機テスト用の行 ==============================
# D列の「▶送る」がスマホで効くかどうかは、実機で試すしかない。
# 本物のお客様の行で試すと誤送信の危険があるので、いちばん上に
# 自分あて（受付番号）の行を固定で置く。
TEST_TEL = '08080438259'
TEST_HONBUN = ('【テスト】この画面が宛先と本文入りで開いていれば成功です。\n'
               'そのまま送信して、届いたらグループLINEに一言ください。')
test_gyou = ['テスト', '【実機テスト】自分あて', "'" + TEST_TEL,
             f'=HYPERLINK("{sms_link(TEST_TEL, TEST_HONBUN)}","▶ 送る")',
             TEST_HONBUN, '', '', '9/9', 'テスト',
             'D列が効くかを確かめるための行。消して構いません', '', '', '',
             '', '', '', '', '', '', '', '', '', '', '', '']
atarashii.insert(0, test_gyou[:len(ATAMA)])

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
if SHIRANAI:
    print()
    print('★ ひな形に、知らない差し込みの目印がありました:',
          '、'.join(sorted(SHIRANAI)))
    print('  そのまま本文に残っています。data/sms-template.txt の説明を見てください。')

print()
print('--- 本文の例（先頭3件）---')
for x in okr[:3]:
    print(f'\n[{x[1]}]\n{x[4]}')
