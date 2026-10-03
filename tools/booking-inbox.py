#!/usr/bin/env python3
"""予約フォームに届いた申し込みを取り込む。

Netlifyフォームに入った予約を
  1. スプレッドシートの 予約_Web タブに追記（未取り込みのものだけ）
  2. グループLINEに知らせる（★お客様の個人情報は流さない。姓と日時と内容だけ）
という形で下ろす。カレンダーへの【仮】予定は、この出力を見てClaudeが入れる
（サービスアカウントにカレンダーAPIの権限が無いため）。

  python3 tools/booking-inbox.py            # 取り込み＋LINE通知
  python3 tools/booking-inbox.py --dry-run  # 何もせず、届いているものを見るだけ
  python3 tools/booking-inbox.py --no-line  # シートだけ更新する

★LINEのグループには、氏名（姓のみ）・日時・メニューまでしか出さない。
  住所と電話番号は出さない。webhookに署名検証が無い経路のため
  （tools/line-webhook.gs の注記）。
"""
import argparse
import datetime
import importlib.util
import json
import re
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location('sc', f'{ROOT}/tools/sheets_client.py')
sc = importlib.util.module_from_spec(spec)
sys.modules['sc'] = sc
spec.loader.exec_module(sc)

SS = '1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64'
TAB = '予約_Web'
SITE_IDS = ['39408b76-e5d0-46f4-bee8-418ef6cfb36a',   # onehitter-yoyaku（2026-09-12〜）
            '83984fb0-5839-421b-bb99-63c8aff47fb9']   # one-hitter-booking（旧。送信済みSMSのリンク先）
# LP のフォーム（reserve-*）。2026-09-13 オーナー指示「LP からの予約も同じスプシへ」
LP_SITE_IDS = ['dad26366-3dfb-4404-9e0c-bb6b50b893c9',   # one-hitter-lp（lp.onehitter.jp: aircon / mizumawari / aircon-b）
               '695bb522-6f01-4bdb-8c3d-afd0ca2b265e']   # one-hitter-nenmatsu（年末LP）
TEST_KOTOBA = ('テスト', '動作確認', 'test')   # お名前にこれが入る申し込みは取り込まない（Netlify側で消す）
TOKEN_KITEI = os.path.expanduser('~/.config/one-hitter/netlify-token.txt')
JST = ZoneInfo('Asia/Tokyo')

ATAMA = ['受信日時', '状態', 'お名前', 'お電話番号', 'ご住所', 'ご希望日', 'ご希望時刻',
         'ご希望の内容', '所要(分)', '概算金額', 'ご要望', '流入元', 'カレンダー登録',
         'NetlifyのID']
# 末尾に足した2列（2026-09-22、広告のオフラインCV用。列の位置は見出し行から探す。無ければ書かない）
OSHIRI = ['src', 'cid', '注文ID', 'gclid', 'ag', 'click_type', 'lp']


def retsu(i: int) -> str:
    """0始まりの列番号を A1 の列記号に（0→A, 27→AB）"""
    out = ''
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        out = chr(65 + r) + out
    return out


def netlify_token() -> str:
    t = os.environ.get('NETLIFY_TOKEN', '').strip()
    if not t and os.path.exists(TOKEN_KITEI):
        t = open(TOKEN_KITEI, encoding='utf-8').read().strip()
    if not t:
        sys.exit('Netlifyトークンがありません。')
    return t


def netlify(path: str):
    req = urllib.request.Request('https://api.netlify.com/api/v1' + path)
    req.add_header('Authorization', 'Bearer ' + netlify_token())
    with urllib.request.urlopen(req, timeout=60) as res:
        return json.loads(res.read())


def sei(namae: str) -> str:
    return namae.split('　')[0].split(' ')[0] or namae


def eria(jusho):
    """番地を出さずに、市区町村まで（〒だけなら〒）"""
    jusho = str(jusho or '')
    m = re.match(r'^(東京都|千葉県|神奈川県|埼玉県)?(.+?[区市町村])', jusho)
    return (m.group(2) if m else jusho[:9]) or '住所なし'


# 受注フォーム（社内ホスト。data/haifu-urls.json の現行）
JUCHU_URL = 'https://oh-naibu-sms-k7q3x.netlify.app/juchu/'


def tsumeru(atai: dict) -> str:
    """受注フォームに渡す値を短く詰める（JSON → UTF-8 → base64url。空の値は落とす）。受け側は build-juchu.py"""
    import base64
    j = json.dumps({k: v for k, v in atai.items() if v}, ensure_ascii=False, separators=(',', ':'))
    return base64.urlsafe_b64encode(j.encode('utf-8')).decode('ascii').rstrip('=')


def keiro_dasu(src):
    """予約の流入元（src）を、受注フォームの「流入経路」の選択肢（data/ryunyu-keiro.json）に寄せる"""
    s = (src or '').lower()
    if 'gads' in s or 'gclid' in s or s.startswith('広告'):
        return '広告'
    if s.startswith('line'):
        return 'LINE'
    if 'gbp' in s:
        return '地図検索'
    if s.startswith('sms'):
        return 'SMS'
    if 'shokai' in s:
        return '紹介'
    if 'chirashi' in s:
        return 'チラシ(OH)'
    if 'rentrax' in s or 'aff' in s:
        return 'LP(アフィリエイト)'
    if s.startswith('site') or s.startswith('hp') or 'blog' in s:
        return 'HP'
    return '予約ページ'


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--no-line', action='store_true')
    ap.add_argument('--mou-ichido', nargs='*', default=[], help='（--dry-run と一緒に）取り込み済みの申込IDを、もう一度表示だけする')
    a = ap.parse_args()

    forms = []
    for sid in SITE_IDS:
        forms += [f for f in netlify(f'/sites/{sid}/forms') if f['name'] == 'yoyaku']
    if not forms:
        sys.exit('yoyaku フォームが見つかりません。フォームの登録を確認してください。')
    for sid in LP_SITE_IDS:
        forms += [f for f in netlify(f'/sites/{sid}/forms') if f['name'].startswith('reserve-')]
    subs = []
    meiwaku = []
    for f in forms:
        for s in netlify(f"/forms/{f['id']}/submissions"):
            s['_form'] = f['name']
            subs.append(s)
        # ★Netlify は申し込みを勝手に「迷惑」へ振り分ける。既定の一覧には出てこない。
        #   2026-09-19 に実測：テスト送信が verified 0件・spam 1件だった。
        #   お客様の本物が迷惑に入ると、黙って消える。**取り込みはしないが、必ず目に出す。**
        for s in netlify(f"/forms/{f['id']}/submissions?state=spam"):
            s['_form'] = f['name']
            meiwaku.append(s)
    print(f'Netlifyに届いている申し込み: {len(subs)}件（予約フォーム＋LP）')
    if meiwaku:
        print()
        print(f'🔴 迷惑判定に {len(meiwaku)}件あります。**自動では取り込みません。人が見てください。**')
        print('   お客様の本物が混ざっていることがあります（ヘッドレスや珍しい端末で送ると入りやすい）。')
        print('   Netlify の管理画面 → Forms → 対象フォーム → Spam で中身を確認し、')
        print('   本物なら「Mark as not spam」にすると、次回このツールが拾います。')
        for s in meiwaku:
            d = s.get('data') or {}
            na = d.get('お名前') or d.get('name') or '（氏名なし）'
            print(f"   - {s['_form']} {s['created_at'][:16]} {s['id']} 氏名={na}")
        print()
    tesuto = [s for s in subs if any(k in str((s.get('data') or {}).get('お名前', '') or (s.get('data') or {}).get('name', '')).lower() for k in TEST_KOTOBA)]
    if tesuto:
        print(f'テスト送信 {len(tesuto)}件は取り込まない（Netlify側で削除すること）:')
        for s in tesuto:
            print('   ', s['_form'], s['created_at'][:16], s['id'])
    subs = [s for s in subs if s not in tesuto]

    tok = sc.access_token(sc.load_credentials())

    def call(p, m='GET', pay=None, q=None):
        return sc.call(tok, urllib.parse.quote(p, safe='/:?&=,!'), method=m, payload=pay, query=q)

    meta = call(f'/{SS}')
    aru = {s['properties']['title'] for s in meta['sheets']}
    if TAB not in aru:
        if a.dry_run:
            print(f'（{TAB} タブがありません。本番実行時に作ります）')
        else:
            call(f'/{SS}:batchUpdate', 'POST', {'requests': [
                {'addSheet': {'properties': {'title': TAB}}}]})
            call(f'/{SS}/values/{TAB}!A1', 'PUT', {'values': [ATAMA]},
                 q={'valueInputOption': 'RAW'})
            print(f'{TAB} タブを作りました')

    sumi = set()
    if TAB in aru:
        rows = call(f'/{SS}/values/{TAB}!A2:N1000').get('values', [])
        sumi = {r[13] for r in rows if len(r) > 13 and r[13]}

    if a.dry_run and a.mou_ichido:      # 取り込み済みの申込で、知らせの見え方を確かめる
        sumi -= set(a.mou_ichido)
    atarashii = [s for s in subs if s['id'] not in sumi]
    print(f'未取り込み: {len(atarashii)}件')
    if not atarashii:
        return

    gyou, shirase, yotei, oshiri = [], [], [], []
    for s in sorted(atarashii, key=lambda x: x['created_at']):
        d = s.get('data') or {}
        # 注文ID（LPが採番 OH-…）と gclid（広告のクリックID）。どのフォームでも生の欄名から拾う
        # 予約フォーム（yoyaku）は欄名が日本語（広告のクリックID）、LPのフォームは gclid/order_id
        oshiri.append({'注文ID': str(d.get('order_id') or ''),
                       'gclid': str(d.get('gclid') or d.get('広告のクリックID') or ''),
                       # 10/9 の広告グループ別の判定に使う（measurement 20260928-01。tools/ad-group-hyou.py が読む）
                       'src': str(d.get('src') or d.get('流入元') or ''),
                       'cid': str(d.get('cid') or d.get('広告のキャンペーンID') or ''),
                       'ag': str(d.get('ag') or d.get('広告グループ') or ''),
                       'click_type': str(d.get('click_type') or d.get('クリックIDの種類') or ''),
                       'lp': str(d.get('lp') or d.get('LP') or '')})
        if s['_form'] != 'yoyaku':
            # LP のフォーム（name/tel/zip/menu/when/lp/src/cid/order_id）を予約フォームの列名に寄せる
            lp = d.get('lp') or s['_form'].replace('reserve-', '')
            ryuunyuu = 'LP:' + lp + ''.join(f' {k}={d[k]}' for k in ('src', 'cid') if d.get(k))
            # 2026-09-28〜 LP は 申込内容・見積総額・見積内訳・台数 も送る（オーナー指示「台数カウントできないの致命的」）。
            # 古い送信には無いので、あるときだけ使う
            # 申込内容はLPが作る人向けのまとめ。最初の段落（内容・台数・特典・見積総額・希望）だけ使う。
            # 後ろの段落には内訳や お名前・電話 が入るので、LINE・予約_Web の内容欄には持ち込まない
            naiyou = (str(d.get('申込内容') or '').strip().split('\n\n')[0]).replace('\n', '／') or d.get('menu', '')
            if d.get('台数') and '台' not in naiyou:
                naiyou += f"（{d['台数']}台）"
            d = {'お名前': d.get('name', ''), 'お電話番号': d.get('tel', ''),
                 'ご住所': ('〒' + d['zip']) if d.get('zip') else '',
                 'ご希望日': d.get('when', ''), 'ご希望時刻': '',
                 'ご希望の内容': naiyou, '所要の目安（分）': '',
                 '概算金額': str(d.get('見積総額') or ''),
                 'ご要望': ' '.join(x for x in [('見積番号 ' + d['order_id']) if d.get('order_id') else '',
                                              ('内訳 ' + d['見積内訳']) if d.get('見積内訳') else ''] if x),
                 '流入元': ryuunyuu}
        if d.get('紹介者'):
            # 紹介カードから（オーナー決定 2026-09-27：紹介した方は次回・紹介された方は初回、それぞれ1,000円引き）
            d = dict(d, **{'ご要望': ('【紹介者: ' + str(d['紹介者']).strip() + ' 様／初回1,000円引き】' + str(d.get('ご要望', ''))).strip()})
        uke = datetime.datetime.fromisoformat(
            s['created_at'].replace('Z', '+00:00')).astimezone(JST)
        gyou.append([
            uke.strftime('%Y-%m-%d %H:%M'), '未確認',
            d.get('お名前', ''), "'" + str(d.get('お電話番号', '')), d.get('ご住所', ''),
            d.get('ご希望日', ''), d.get('ご希望時刻', ''), d.get('ご希望の内容', ''),
            d.get('所要の目安（分）', ''), d.get('概算金額', ''), d.get('ご要望', ''),
            d.get('流入元', ''), '未登録', s['id'],
        ])
        # 2026-10-03 オーナー指示「次のアクションへの導線もどうせなら加えてほしい。電話確認が必要なら電話番号＋受注フォームURLとか。
        # 一番人間の手間を減らせるように」→ 電話番号（押せばかかる形）と、入力済みの受注フォームへのリンクを載せる。
        # 番地は本文に出さない（リンクの # のあとにだけ入れる。# 以降はサーバーに送られない）。業務連絡グループは嶺・和真の2名
        kin = str(d.get('概算金額') or '').replace(',', '')
        iriguchi = d.get('流入元', '')
        tel = re.sub(r'\D', '', str(d.get('お電話番号', '')))
        tel_h = (f'{tel[:3]}-{tel[3:7]}-{tel[7:]}' if len(tel) == 11 else
                 f'{tel[:2]}-{tel[2:6]}-{tel[6:]}' if len(tel) == 10 else tel)
        juchu = JUCHU_URL + '#p=' + tsumeru({
            's': 'One Hitter', 'k': keiro_dasu(iriguchi),
            'd': d.get('ご希望日', ''), 'j': d.get('ご希望時刻', ''),
            'n': d.get('お名前', ''), 't': tel, 'a': d.get('ご住所', ''),
            'x': kin if kin.isdigit() else '',
            'm': d.get('ご希望の内容', ''),
            'b': ('Web予約より。' + re.sub(r'\s+', ' ', str(d.get('ご要望', ''))))[:150],
        })
        if 'gads' in iriguchi:
            iriguchi = 'Google広告（' + ('エアコン' if 'aircon' in iriguchi else '水まわり' if 'mizumawari' in iriguchi else '') + 'のページ）'
        elif iriguchi.startswith('LP:'):
            iriguchi = 'LP（' + iriguchi[3:].split()[0] + '）'
        shirase.append('\n'.join(x for x in [
            f"■ {sei(d.get('お名前', ''))}さま（{eria(d.get('ご住所', ''))}）",
            f"内容：{d.get('ご希望の内容', '')}",
            f"見積：{int(kin):,}円（税込）" if kin.isdigit() else "見積：記録なし（お電話で確認）",
            f"希望：{d.get('ご希望日', '')} {d.get('ご希望時刻', '')}".rstrip(),
            f"入口：{iriguchi}" if iriguchi else '',
        ] if x) + '\n\n' + '\n'.join([
            f"① お電話で日時を確定：{tel_h}" if tel else '① お電話番号の記入なし（予約_Webタブを確認）',
            '② 確定したら受注フォームで記録（入力済み・送るだけ）：',
            juchu,
        ]))
        # カレンダーに入れる用（この出力を見てClaudeが登録する）
        yotei.append({
            'summary': f"【仮】{sei(d.get('お名前',''))}様 {d.get('ご希望の内容','')}",
            'date': d.get('ご希望日', ''), 'time': d.get('ご希望時刻', ''),
            'minutes': d.get('所要の目安（分）', '120'),
            'location': d.get('ご住所', ''),
            'description': (f"Web予約（未確認）\n"
                            f"お名前: {d.get('お名前','')}\n"
                            f"お電話: {d.get('お電話番号','')}\n"
                            f"ご住所: {d.get('ご住所','')}\n"
                            f"ご要望: {d.get('ご要望','')}\n"
                            f"概算: {d.get('概算金額','')}円\n"
                            f"流入元: {d.get('流入元','')}"),
            'submissionId': s['id'],
        })

    if a.dry_run:
        print('\n--- 追記する行 ---')
        for g, o in zip(gyou, oshiri):
            print(' ', g[:8], '末尾の列:', o)
        print('\n--- カレンダーに入れるもの ---')
        print(json.dumps(yotei, ensure_ascii=False, indent=1))
        print('\n--- LINEの知らせ（1件ぶんずつ） ---')
        print('\n\n'.join(shirase))
        print('\n--dry-run のため何も書いていません。')
        return

    res = call(f'/{SS}/values/{TAB}!A1:append', 'POST', {'values': gyou},
               q={'valueInputOption': 'USER_ENTERED', 'insertDataOption': 'INSERT_ROWS'})
    print(f'{TAB} に {len(gyou)}件 追記しました')
    # 注文ID・gclid・src・ag・click_type は末尾の列へ（見出し行にある列だけ書く。中間の列は他スレッドの持ち物なので触らない）
    midashi = call(f'/{SS}/values/{TAB}!1:1').get('values', [[]])[0]
    m = re.search(r'!A(\d+):', res.get('updates', {}).get('updatedRange', ''))
    if m:
        r0 = int(m.group(1))
        kaita = []
        for k in OSHIRI:
            if k not in midashi:
                continue
            i = midashi.index(k)
            a1 = f'{TAB}!{retsu(i)}{r0}:{retsu(i)}{r0 + len(oshiri) - 1}'
            call(f'/{SS}/values/{a1}', 'PUT', {'values': [[o[k]] for o in oshiri]}, q={'valueInputOption': 'RAW'})
            kaita.append(k)
        print('末尾の列に書きました: ' + '・'.join(kaita) if kaita else '（注文ID などの列が見出しに無いので書いていません）')

    out = f'{ROOT}/data/calendar/booking-todo.json'
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(yotei, f, ensure_ascii=False, indent=1)
    print(f'カレンダーに入れる内容を書き出しました: {out}')

    if not a.no_line:
        honbun = ('Web予約（予約フォーム／LP）から申し込みが入りました（' + str(len(shirase)) + '件）\n\n'
                  + '\n\n'.join(shirase)
                  + '\n\nカレンダーには【仮】で入っています。受注フォームで記録すると、'
                    '台帳に入り、【仮】の予定はマーケ部長が本予定に置き換えます。\n'
                    'ご住所はカレンダーの予定と「予約_Web」タブにあります。')
        # 申し込みの知らせは急ぐので、未読の返信があっても送る（2026-09-27：未読で止まり、2時間気づかれなかった）
        r = subprocess.run(['python3', f'{ROOT}/tools/line_client.py', 'push', honbun, '--midoku-ok'],
                           check=False)
        print('グループLINEに知らせました' if r.returncode == 0 else '🔴 グループLINEに知らせられませんでした（手で送ること）')


if __name__ == '__main__':
    main()
