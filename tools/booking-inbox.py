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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--no-line', action='store_true')
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

    atarashii = [s for s in subs if s['id'] not in sumi]
    print(f'未取り込み: {len(atarashii)}件')
    if not atarashii:
        return

    gyou, shirase, yotei = [], [], []
    for s in sorted(atarashii, key=lambda x: x['created_at']):
        d = s.get('data') or {}
        if s['_form'] != 'yoyaku':
            # LP のフォーム（name/tel/zip/menu/when/lp/src/cid/order_id）を予約フォームの列名に寄せる
            lp = d.get('lp') or s['_form'].replace('reserve-', '')
            ryuunyuu = 'LP:' + lp + ''.join(f' {k}={d[k]}' for k in ('src', 'cid') if d.get(k))
            d = {'お名前': d.get('name', ''), 'お電話番号': d.get('tel', ''),
                 'ご住所': ('〒' + d['zip']) if d.get('zip') else '',
                 'ご希望日': d.get('when', ''), 'ご希望時刻': '',
                 'ご希望の内容': d.get('menu', ''), '所要の目安（分）': '', '概算金額': '',
                 'ご要望': ('見積番号 ' + d['order_id']) if d.get('order_id') else '',
                 '流入元': ryuunyuu}
        uke = datetime.datetime.fromisoformat(
            s['created_at'].replace('Z', '+00:00')).astimezone(JST)
        gyou.append([
            uke.strftime('%Y-%m-%d %H:%M'), '未確認',
            d.get('お名前', ''), "'" + str(d.get('お電話番号', '')), d.get('ご住所', ''),
            d.get('ご希望日', ''), d.get('ご希望時刻', ''), d.get('ご希望の内容', ''),
            d.get('所要の目安（分）', ''), d.get('概算金額', ''), d.get('ご要望', ''),
            d.get('流入元', ''), '未登録', s['id'],
        ])
        # LINEには個人情報を出さない
        shirase.append(f"・{sei(d.get('お名前', ''))}さま／"
                       f"{d.get('ご希望日', '')} {d.get('ご希望時刻', '')}〜／"
                       f"{d.get('ご希望の内容', '')}")
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
        for g in gyou:
            print(' ', g[:8])
        print('\n--- カレンダーに入れるもの ---')
        print(json.dumps(yotei, ensure_ascii=False, indent=1))
        print('\n--dry-run のため何も書いていません。')
        return

    call(f'/{SS}/values/{TAB}!A1:append', 'POST', {'values': gyou},
         q={'valueInputOption': 'USER_ENTERED', 'insertDataOption': 'INSERT_ROWS'})
    print(f'{TAB} に {len(gyou)}件 追記しました')

    out = f'{ROOT}/data/calendar/booking-todo.json'
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(yotei, f, ensure_ascii=False, indent=1)
    print(f'カレンダーに入れる内容を書き出しました: {out}')

    if not a.no_line:
        honbun = ('Web予約（予約フォーム／LP）から申し込みが入りました（' + str(len(shirase)) + '件）\n\n'
                  + '\n'.join(shirase)
                  + '\n\nお名前・ご住所・お電話は、カレンダーの予定の詳細と'
                    'スプレッドシートの「予約_Web」タブに入っています。\n'
                    'まだ【仮】です。確認のお電話をして、予定のタイトルから【仮】を'
                    '外してください。')
        subprocess.run(['python3', f'{ROOT}/tools/line_client.py', 'push', honbun],
                       check=False)
        print('グループLINEに知らせました')


if __name__ == '__main__':
    main()
