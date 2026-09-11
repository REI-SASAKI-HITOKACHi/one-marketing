#!/usr/bin/env python3
"""冬季見込み客_2026 を「スマホで送信作業をするシート」に組み替える。

【なぜこの形か】
  和真はスマホで、このシートとSMS送信画面を往復する。
  タップ数をできるだけ減らすことが、1時間あたりの送信件数をそのまま決める。

  A 優先        … どの人から声をかけるか
  B 顧客名
  C 電話番号     … 数字だけ。コピーしてそのまま貼れる
  D ▶SMSを開く   … sms: リンク。タップすると宛先と本文が入った状態でSMSが開く
  E 送信済み     … プルダウン1タップ（2026-09-11 に本文と入れ替え。横スクロールせずに結果を入れるため）
  F 送信する本文  … Dが効かない端末向けの控え。ここをコピーしても送れる
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
  スケジュールマッチング経由は、和真がE列で「対象外」にする運用に変わった
  （2026-09-08 オーナー指示）。こちらでは除外しない。

使い方: python3 tools/build-sms-list.py
"""
import importlib.util
import datetime
import json
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from collections import Counter

ROOT = '/home/user/one-marketing'
# --dry-run … シートには一切書かない。文面を直したときの確認用。
DRY = '--dry-run' in sys.argv
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

# 予約フォームが「予約を受け付けられる状態か」を、本番ページを見て確かめる。
# Apps Script の /exec URL が未設定（api が空）のあいだは、
# お客様がフォームを開いても日時が出ず、送信もできない（電話案内が出るだけ）。
# その状態で220人へ送るのは事故なので、シートの先頭に警告を出す。
def yoyaku_ikiteruka():
    """予約フォームが本当に予約を受け付けられるか、本番ページを見て確かめる。
    (使える?, 理由) を返す。見に行けなかったときは「使える」と言わない。

    見るのは2つ。
      1. 空き枠のファイル（slots.json）があって、内容が古すぎないか
      2. Netlifyのフォームが登録されているか
         配信後のHTMLに data-netlify が残っていたら、それは未登録の印。
         年末LPで実際に起きた（POSTが404になっていた／2026-09-08）。
    """
    moto = YOYAKU_FORM.split('?')[0].rstrip('/')
    try:
        with urllib.request.urlopen(moto + '/', timeout=20) as res:
            html = res.read().decode('utf-8', 'replace')
    except Exception as e:
        return False, f'予約フォームを確認できませんでした（{e}）'

    if 'data-netlify' in html:
        return False, ('予約フォームの受け口が登録されていません。'
                       '配信後のHTMLに data-netlify が残っています。'
                       'このまま送るとお客様が申し込めません。')
    if re.search(r'"api"\s*:\s*""', html) and 'slots.json' not in html:
        return False, ('予約フォームが空き枠を読む先を持っていません。'
                       'tools/build-slots.py と配信をやり直してください。')

    try:
        with urllib.request.urlopen(moto + '/slots.json', timeout=20) as res:
            d = json.loads(res.read().decode('utf-8'))
    except Exception as e:
        return False, f'空き枠のファイル（slots.json）を読めませんでした（{e}）'

    waku = sum(len(x.get('times', [])) for x in (d.get('buckets', {}).get('120') or []))
    if not waku:
        return False, '空き枠が1つも出ていません。カレンダーと build-slots.py を確認してください。'

    try:
        tsukurareta = datetime.datetime.fromisoformat(d['generated'])
        keika = (datetime.datetime.now(tsukurareta.tzinfo) - tsukurareta).total_seconds() / 3600
    except Exception:
        return False, '空き枠のファイルに作成時刻がありません。'
    if keika > d.get('staleHours', 6):
        return False, (f'空き枠の情報が{keika:.0f}時間前のものです。'
                       'tools/build-slots.py をやり直してから送ってください。')
    return True, ''


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
    ['python3', f'{ROOT}/tools/sheets_client.py', 'read', SS, f'{TAB}!A1:Z2000'],   # 2026-09-11 2022年だけの顧客43名を足して1000行を超えた。1000のままだと末尾が読めず、作り直しで消えずに残る
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
    """姓だけ取り出す。「佐藤　有司 実家」「大塚 娘」のような書き方にも耐える。
    台帳には「青山リアルティ様（田辺様）」のように敬称や補足が入った行がある。
    そのまま「さま」を付けると「…様（田辺様）さま」になるので、先に落とす。"""
    na = shimei.strip()
    na = re.split(r'[（(]', na)[0].strip()          # 括弧の補足を落とす
    s = re.split(r'[\s\u3000]+', na)
    na = s[0] if s and s[0] else na
    na = re.sub(r'(様|さま|さん|殿|御中)$', '', na)   # 末尾の敬称を落とす
    return na or shimei.strip()


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
    # 台帳の表記ゆれ。内部の書き方がそのままお客様に出ないようにする
    '洗濯機(ノーマル)': '洗濯機クリーニング',
    '追焚配管': '追い焚き配管クリーニング',
    '空室': '空室クリーニング',
}


# 「その後、○○は快適に使用できていますでしょうか」と続けるための言い方。
# IIKAE から「クリーニング」を取って、モノの名前だけにする。
# 台帳の表記がそのまま使えるものは書かない（見つからなければ表記のまま返す）。
IIKAE_MONO = {
    'エアコン(ノーマル)': 'エアコン',
    'エアコン(ロボ)': 'お掃除機能付きエアコン',
    '天カセ': '天井カセットエアコン',
    'まるごと(備考に内容)': 'お住まい',
    '追い焚き': '追い焚き配管',
    '床WAX': '床',
    '洗濯機(ノーマル)': '洗濯機',
    '追焚配管': '追い焚き配管',
    # ★「空室」は空にする。退去後の原状回復なので、住んでいる人がいない。
    #   「その後、空室は快適に使用できていますでしょうか」は成り立たない。
    #   空にすると、ひな形のその行だけが丸ごと落ちる。
    '空室': '',
}


def menu_mono(uchiwake):
    """「浴室×3／エアコン(ロボ)×2」→「浴室」。クリーニングという語を付けない"""
    if not uchiwake:
        return ''
    namae = uchiwake.split('／')[0].split('×')[0].strip()
    if not namae:
        return ''
    return IIKAE_MONO.get(namae, namae)


def menu_hitotsu(uchiwake):
    """「浴室×3／エアコン(ロボ)×2」→「浴室クリーニング」。いちばん多いものを1つ"""
    if not uchiwake:
        return ''
    atama = uchiwake.split('／')[0]
    namae = atama.split('×')[0].strip()
    return IIKAE.get(namae, namae + 'のクリーニング' if namae else '')


# ============================== 次にすすめる箇所 ==============================
# ── 次のおすすめ箇所を自動で決める仕組みについて ──
#
# 2026-09-10 オーナー判断で取りやめ。
#   「オススメメニューの構想は複雑化（エラー確率上昇）するから一旦取りやめる」
# 前回メニューと経過月から次の箇所を出す teian() は削除した。
# 本舗の文面は、9〜11月の季節提案を全員に同じ文で出す固定文にしてある。
# 復活させたくなったら git log でこのコミットを見ること。


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


def ichinen_ijou(r):
    """前回から1年以上たっている方にだけ出す一文。それ以外は空を返す"""
    try:
        keika = float(g(r, '経過(月)') or 0)
    except ValueError:
        keika = 0
    if keika < 12:
        return ''
    return ('前回のクリーニングから1年以上経過しておりますので、'
            '現在の状況をお聴きしたくご連絡を差し上げました。')


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
        # 「その後、○○は快適に…」用。半角丸かっこ・全角丸かっこのどちらでも拾う
        '前回施工(クリーニング除く)': menu_mono(g(r, '施工メニュー（内訳）')),
        '前回施工（クリーニング除く）': menu_mono(g(r, '施工メニュー（内訳）')),
        '申込フォームURL': MOUSHIKOMI,
        '予約フォームURL': YOYAKU_FORM,
        '予約フォーム': YOYAKU_FORM,
        # 法人のお客様に「ご自宅の汚れ」と書かないための入れ替え
        'ご自宅': ('店舗・オフィス' if g(r, '法人/個人') == '法人' else 'ご自宅'),
        '電話番号': TEL_UKETSUKE,
        '本舗の電話番号': TEL_HONPO,
        # 経過が1年に満たない方には出さない（この行ごと消える）。
        # 文面が「1年以上経過しております」と言い切っているため、
        # 事実と違うことを書かないようにする（2026-09-10 オーナー判断）。
        '1年以上経過のひとこと': ichinen_ijou(r),
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


# D列「▶送る」の行き先。
#
# 直に sms:番号?body=… を書くと、スマホのスプレッドシートアプリでは
# タップしても何も起きない。HYPERLINK() が開くのは http/https/mailto だけで、
# sms: は対象外だから（2026-09-10 和真さん報告
# 「送るタップで開かないから手打ちで送るねー」）。
#
# そこで https のページを1枚はさんで、そこから sms: を開く。
SMS_PAGE = 'https://one-hitter-booking.netlify.app/s.html'


def sms_link(num, text):
    """タップするとSMSが宛先・本文入りで開く。

    ★宛先と本文は「#」より後ろ（フラグメント）に入れる。
      フラグメントはサーバーに送られないので、Netlifyのアクセス記録に
      お客様の電話番号も本文も残らない。「?」に変えないこと。
    """
    return (SMS_PAGE + '#to=' + urllib.parse.quote(num, safe='')
            + '&b=' + urllib.parse.quote(text, safe=''))


# ============================== 名義の照合（再発防止） ==============================
# 2026-09-11 の事故：送信系統=自社 の行にワンヒッター名義の文面を作り、実際は本舗名義が最新の
# お客様3名に送ってしまった。送信系統列を信じて作っていたのが原因。
# 以後、送信系統は「台帳の最新の施工の名義」と1行ずつ突き合わせ、
# 食い違う行・名義が分からない行は 送信可 にしない（tools/derive-soushin-keitou.py と同じ決まり）。
_spec2 = importlib.util.spec_from_file_location('dsk', f'{ROOT}/tools/derive-soushin-keitou.py')
dsk = importlib.util.module_from_spec(_spec2); _spec2.loader.exec_module(dsk)
MEIGI_HYOU = dsk.meigi_hyou()
print('名義の控え:', len(MEIGI_HYOU[0]), '番号／', len(MEIGI_HYOU[1]), '氏名（', dsk.CACHE_KITEI, '）')


def meigi_kuichigai(r):
    """送信系統と台帳の最新名義が食い違えば理由の文字列、合っていれば ''。"""
    keitou = g(r, '送信系統')
    m = dsk.meigi_shiraberu(MEIGI_HYOU, g(r, '元の電話番号表記') or g(r, 'TEL'), g(r, '氏名'))
    if not m:
        return '台帳に名義（One Hitter／本舗）の記録が無く、どちらの名乗りで送るか決められません'
    if m[0] != keitou:
        return f'送信系統が「{keitou}」ですが、台帳の最新の施工（{m[1]}）は{m[0]}名義です。送信系統を直してください'
    return ''


# ============================== 判定 ==============================
mizumi = set()
data = []   # (区分, 理由, 番号, 本文)
for r in rows:
    keiro, seg = g(r, '主な流入経路'), g(r, 'セグメント')
    if seg.startswith('Z_'):
        data.append(('除外', '直近3ヶ月に施工済み', '', '')); continue
    if keiro == '楽ラクーン':
        data.append(('除外', '楽ラクーン経由（フォロー連絡不可）', '', '')); continue
    # 空室クリーニングは退去後の原状回復。住んでいる人がいないので、
    # 「その後いかがですか」という声かけが成り立たない（2026-09-08 オーナー指示）
    if g(r, '施工メニュー（内訳）').split('／')[0].split('×')[0].strip() == '空室':
        data.append(('除外', '空室クリーニングのお客様（オーナー指示）', '', '')); continue
    num, err = bangou(g(r, 'TEL'))
    if not num:
        data.append(('SMS不可', err + '／公式LINEか電話で拾う', '', '')); continue
    if num in mizumi:
        data.append(('除外', '同じ電話番号が他の行にもある', num, '')); continue
    mizumi.add(num)
    # 台帳の氏名が壊れている行。「ご　さん」→「ごさま」のような送信を止める
    if re.fullmatch(r'[ぁ-んァ-ヶー]', sei(g(r, '氏名'))):
        data.append(('保留', f'氏名の表記を確認してください（台帳:{g(r, "氏名")}）',
                     num, '')); continue
    keitou = g(r, '送信系統')
    kuichigai = meigi_kuichigai(r)
    if kuichigai and not g(r, '送信済み'):
        data.append(('保留', kuichigai, num, '')); continue
    hon = honbun(r, keitou)
    if not hon:
        data.append(('保留', f'{keitou}向けの文面が未確定。'
                     f'{HINAGATA_PATH.get(keitou, "")} を埋めると送信可になります',
                     num, ''))
        continue
    # 名乗りの行が落ちた本文は送らない。
    # 「"施工時期"に"前回メニュー"を担当させていただきました、…の渡辺でございます」の行は
    # 台帳に最終施工日か施工メニューが無いと丸ごと落ちる。落ちると、
    # 誰から届いたのか分からないSMSになってしまう（2026-09-10）。
    if '渡辺でございます' not in hon:
        data.append(('保留', '最終施工日か施工メニューが台帳に無く、名乗りの行が'
                     '作れませんでした。台帳を埋めると送信可になります', num, ''))
        continue
    # 本舗のお客様に、ワンヒッターのものを出していないかを1行ずつ確かめる。
    # 「本舗顧客には本舗として営業する」（2026-09-08 オーナー指示）
    if keitou == '本舗':
        moreta = [w for w in ('ワンヒッター', 'one-hitter', 'ONE HITTER', TEL_UKETSUKE)
                  if w in hon]
        if moreta:
            data.append(('保留', 'ワンヒッターのものが本舗の文面に混ざっています:'
                         + '、'.join(moreta), num, ''))
            continue
    # 逆も見る。自社の文面には必ずワンヒッターの名乗りがあること
    if keitou == '自社' and 'ワンヒッター' not in hon:
        data.append(('保留', '自社の文面にワンヒッターの名乗りがありません', num, '')); continue
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
# 2026-09-11 和真さんの要望：E列を「送信済み」、F列を「本文」にする（横スクロールせずに結果を入れられる）
ATAMA = ['優先', '顧客名', '電話番号', '▶SMSを開く', '送信済み',
         '送信する本文', '返信メモ', '送信日の目安', '配信区分', '送らない理由',
         'セグメント', '法人/個人', '送信系統', '受注回数', '累計売上', '平均単価',
         '最終施工日', '経過(月)', '冬季施工回数', '施工メニュー（内訳）',
         '今回おすすめ', '主な流入経路', '利用年', '元の電話番号表記', '予備']

atarashii = []
RINKU = []      # D列に付けるリンク。atarashii と同じ並び
for i, r in enumerate(rows):
    kubun, riyuu, num, hon = data[i]
    link = ''
    if kubun == '送信可':
        # ★=HYPERLINK() は使わない。
        #   iPhoneのスプレッドシートアプリでは、HYPERLINK() の結果をタップしても
        #   セルが選ばれるだけでリンクが開かない（2026-09-10 和真さんのスクショで確認）。
        #   セルの文字そのものにリンクを付ける（textFormatRuns）と、
        #   リンクとして扱われてタップで開ける。付ける処理はこの下でまとめて行う。
        link = '▶ 送る'
        RINKU.append(sms_link(num, hon))
    else:
        RINKU.append('')
    atarashii.append([
        g(r, '優先'), g(r, '氏名'), ("'" + num) if num else '', link, g(r, '送信済み'),
        hon, g(r, '返信メモ'), batch.get(i, ''), kubun, riyuu,
        g(r, 'セグメント'), g(r, '法人/個人'), g(r, '送信系統'), g(r, '受注回数'), g(r, '累計売上'),
        g(r, '平均単価'), g(r, '最終施工日'), g(r, '経過(月)'), g(r, '冬季施工回数'), g(r, '施工メニュー（内訳）'),
        g(r, '今回おすすめ'), g(r, '主な流入経路'), g(r, '利用年'), g(r, 'TEL'), g(r, '送信済み'),
    ])

# 送信可を上に、そのなかは送る順。送らない人は下へ
juni = {v: k for k, v in enumerate(okuru)}
kumi = list(zip(range(len(rows)), atarashii, RINKU))
kumi.sort(key=lambda x: (0 if x[1][8] == '送信可' else 1,
                         juni.get(x[0], 9999)))
atarashii = [x[1] for x in kumi]
RINKU = [x[2] for x in kumi]        # 並べ替えたら、リンクも同じ順に並べ直す

# ============================== 実機テスト用の行 ==============================
# D列の「▶送る」がスマホで効くかどうかは、実機で試すしかない。
# 本物のお客様の行で試すと誤送信の危険があるので、いちばん上に
# 自分あて（受付番号）の行を固定で置く。
TEST_TEL = '08080438259'
TEST_HONBUN = ('【テスト】この画面が宛先と本文入りで開いていれば成功です。\n'
               'そのまま送信して、届いたらグループLINEに一言ください。')
test_gyou = ['テスト', '【実機テスト】自分あて', "'" + TEST_TEL,
             '▶ 送る',
             '', TEST_HONBUN, '', '9/9', 'テスト',
             'D列が効くかを確かめるための行。消して構いません', '', '', '',
             '', '', '', '', '', '', '', '', '', '', '', '']
atarashii.insert(0, test_gyou[:len(ATAMA)])
RINKU.insert(0, sms_link(TEST_TEL, TEST_HONBUN))

def shuukei():
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
    # SMSは全角70文字で1通。超えると分割して送られる（受け取れない端末もある）
    I_HON = ATAMA.index('送信する本文')   # 2026-09-11 にE列とF列を入れ替えたので、位置ではなく名前で引く
    naga = [len(x[I_HON]) for x in okr]
    print('本文の長さ  最短', min(naga), '／ 最長', max(naga),
          '／ 平均', sum(naga) // len(naga))
    print('  70文字超:', sum(1 for n in naga if n > 70), '件（長文SMSとして分割されます）')
    # 差し込みが空で行ごと落ちたものを数える。文面が痩せていないかの確認
    kake = [x for x in okr if '渡辺でございます' not in x[I_HON] and 'おそうじ本舗' not in x[I_HON]]
    if kake:
        print('★ 名乗りの行が落ちた本文:', len(kake),
              '件（最終施工日か施工メニューが台帳に無い方）')
    if SHIRANAI:
        print()
        print('★ ひな形に、知らない差し込みの目印がありました:',
              '、'.join(sorted(SHIRANAI)))
        print('  そのまま本文に残っています。data/sms-template.txt の説明を見てください。')
    print()
    # 本舗の文面は「前回のクリーニングから1年以上経過しております」と言い切っている。
    # 経過が1年未満の方に送ると事実と違うので、件数を必ず出す（2026-09-10）。
    i_ke = ATAMA.index('経過(月)')
    IJOU = '1年以上経過しております'
    mijikai, machigai = [], []
    for x in okr:
        if x[12] != '本舗':
            continue
        try:
            k = float(x[i_ke] or 0)
        except ValueError:
            k = 0
        if k >= 12:
            continue
        mijikai.append((x[1], k))
        if IJOU in x[I_HON]:        # ここに入ったら文面と事実が食い違っている
            machigai.append(x[1])
    if mijikai:
        print('本舗で経過1年未満の方:', len(mijikai),
              '件（「1年以上経過しております」の一文は出していません）')
        print('  例:', '、'.join(f'{na}({k}ヶ月)' for na, k in mijikai[:5]))
        print()
    if machigai:
        print('★★ 1年未満の方に「1年以上経過」と書いています:', len(machigai), '件')
        print('   送信を止めてください。', '、'.join(machigai[:5]))
        print()
    # 一文が落ちた側の文面も1件出す。落ちたあとの文のつながりを目で見るため
    for x in okr:
        if x[12] == '本舗' and IJOU not in x[I_HON]:
            print('--- 本舗・経過1年未満の例（上の一文が落ちた形）---')
            print()
            print(f'[{x[1]}]')
            print(x[I_HON])
            print()
            break
    for kt in ('自社', '本舗'):
        rei = [x for x in okr if x[12] == kt]
        if not rei:
            continue
        n2 = [len(x[I_HON]) for x in rei]
        print(f'--- {kt} の本文の例（{len(rei)}件・最長{max(n2)}文字）---')
        print()
        print(f'[{rei[0][1]}]')
        print(rei[0][I_HON])
        print()
    print('--- 本文の例（先頭3件）---')
    for x in okr[:3]:
        print(f'\n[{x[1]}]\n{x[I_HON]}')


# ============================== 書き込み ==============================
if DRY:
    shuukei()
    print('\n--dry-run のためシートには書いていません。')
    sys.exit(0)

meta = call(f'/{SS}')
sh = next(s for s in meta['sheets'] if s['properties']['title'] == TAB)
SID = sh['properties']['sheetId']
gp = sh['properties']['gridProperties']
if gp['columnCount'] < len(ATAMA):
    call(f'/{SS}:batchUpdate', 'POST', {'requests': [{'updateSheetProperties': {
        'properties': {'sheetId': SID, 'gridProperties': {'columnCount': len(ATAMA)}},
        'fields': 'gridProperties.columnCount'}}]})

YOYAKU_OK, YOYAKU_RIYUU = yoyaku_ikiteruka()
if not YOYAKU_OK:
    print('\n★★ 送信を始めてはいけません:', YOYAKU_RIYUU, '\n')

SETSUMEI = ('' if YOYAKU_OK else '【送信は保留してください】' + YOYAKU_RIYUU + ' ') + (
           'スマホでの送信作業用。D列の「▶ 送る」をタップ → 出てきたリンクを開く → '
            'SMSが宛先と本文入りで開く → 送信 → E列で「送信済み」を選ぶ。'
            '開かないときは、F列の本文をコピーして貼ってください（手打ちはしないこと）。'
            'スケジュールマッチング経由で送ってはいけない先は、E列で「対象外」にしてください。')

# いったん広めに消してから書き直す
call(f'/{SS}/values/{TAB}!A1:Y2000:clear', 'POST', {})
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
      for i, w in enumerate([48, 150, 120, 80, 100, 420, 160, 90, 80, 220])],
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
    # E列 送信済み のプルダウン
    {'setDataValidation': {
        'range': gr(5, 5 + n, 4, 5),
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
                      'values': [{'userEnteredValue': '=$E6<>""'}]},
        'format': {'backgroundColor': {'red': .88, 'green': .95, 'blue': .91}}}},
    'index': 0}})

req.append({'updateSheetProperties': {
    'properties': {'sheetId': SID, 'gridProperties': {'frozenRowCount': 5}},
    'fields': 'gridProperties.frozenRowCount'}})

call(f'/{SS}:batchUpdate', 'POST', {'requests': req})
print('書式をつけました')

# ============================== D列に本物のリンクを付ける ==============================
#
# ★ここが「▶送る」が効くかどうかの分かれ目。
#
# =HYPERLINK() で書くと、iPhoneのスプレッドシートアプリではタップしても
# セルが選ばれるだけで、リンクが開かない
# （2026-09-10 和真さんのスクリーンショットで確認。
#   タップすると「カット／コピー／ペースト」が出るだけだった）。
#
# セルの文字そのものにリンクを付ける（textFormatRuns の link）と、
# アプリ側がリンクとして扱うので、タップで開ける。
# パソコンのブラウザでは、どちらの書き方でも青い文字になって開ける。
gyou_cells = []
for u in RINKU:
    if u:
        gyou_cells.append({'values': [{
            'userEnteredValue': {'stringValue': '▶ 送る'},
            'textFormatRuns': [{'startIndex': 0, 'format': {'link': {'uri': u}}}]}]})
    else:
        gyou_cells.append({'values': [{'userEnteredValue': {'stringValue': ''}}]})
# 1回のリクエストに詰め込みすぎると通らないので、200行ずつに分ける
for hajime in range(0, len(gyou_cells), 200):
    kata = gyou_cells[hajime:hajime + 200]
    call(f'/{SS}:batchUpdate', 'POST', {'requests': [{'updateCells': {
        'range': {'sheetId': SID,
                  'startRowIndex': 5 + hajime, 'endRowIndex': 5 + hajime + len(kata),
                  'startColumnIndex': 3, 'endColumnIndex': 4},
        'rows': kata,
        'fields': 'userEnteredValue,textFormatRuns'}}]})
print('D列にリンクを付けました:', sum(1 for u in RINKU if u), '件')


shuukei()
