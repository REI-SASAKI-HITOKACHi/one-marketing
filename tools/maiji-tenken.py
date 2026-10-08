#!/usr/bin/env python3
"""毎時点検の機械的な部分を1本にまとめたもの（2026-09-29 オーナー了承「仕様の変更はokだよ」）。

毎時の自動起動で CMO はこれを1回流すだけにし、「要対応」が0件なら1行で終える。
CMO の会話は長く、ツールを1回呼ぶたびに全体を読み直すので、呼ぶ回数を減らすのが目的
（請求の大半はその読み直し代。公式ブログ 2026-09-24）。
※ 当初は別の軽いセッションで回す案だったが、資格情報（~/.config/one-hitter/）が
  CMO の環境にしか無いので、鍵を広げない形としてこちらにした。

★このスクリプトは読むだけ。取り込み・送信・書き込みは一切しない（--dry-run だけを流す）。
  例外は1つ：毎回いちばん先に tools/kagi-fukugen.py を流し、環境変数から ~/.config/one-hitter/ の鍵ファイルを
  書き戻す（2026-10-07 オーナー指示「以後同じトラブルが絶対におこらない仕組みにしてよ」）。
  見つけたものを実際に処理するのは、起こされた CMO。

使い方:
  python3 tools/maiji-tenken.py            # 直近65分の変化を見る
  python3 tools/maiji-tenken.py --fun 180  # 見る幅を変える

最後の行は必ず「要対応: N件」。0件なら CMO を起こさない。
"""
import argparse
import datetime
import glob
import os
import re
import subprocess
import sys

KOKO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JST = datetime.timezone(datetime.timedelta(hours=9))

# 既知でオーナー判断済みのもの（新しい因果を組まない）
KICHI_KIKEN = {'oh-naibu-sms-k7q3x.netlify.app'}


def jikkou(*a, timeout=240):
    try:
        r = subprocess.run(['python3', *a], cwd=KOKO, capture_output=True,
                           text=True, timeout=timeout)
        return r.returncode, (r.stdout or '') + (r.stderr or '')
    except subprocess.TimeoutExpired:
        return 124, f'（{a[0]} が {timeout} 秒で終わらなかった）'


def safebrowsing():
    rc, out = jikkou('tools/check-safebrowsing.py', timeout=300)
    atarashii = [l.strip() for l in out.splitlines()
                 if '⚠' in l and not any(h in l for h in KICHI_KIKEN)]
    return [f'セーブブラウジング: {l}' for l in atarashii]


def hosts_more():
    rc, out = jikkou('tools/check-hosts-more.py')
    if '漏れはありません' in out:
        return []
    return ['監視漏れのホスト: ' + ' / '.join(out.strip().splitlines()[-3:])]


def haifu_urls():
    rc, out = jikkou('tools/check-haifu-urls.py', '--quiet')
    if out.strip():  # 一時的な接続失敗（状態 0）がある（9/30 22:4x）。1回だけ取り直す
        rc, out = jikkou('tools/check-haifu-urls.py', '--quiet')
    out = out.strip()
    return [f'配ったURLの異常: {out}'] if out else []


def line_midoku():
    rc, out = jikkou('tools/line_client.py', 'midoku')
    if '未確認の返信はありません' in out:
        return []
    return ['業務連絡LINEに未読あり（CMOが全文を読んで返信する）']


def torikomi():
    kekka = []
    for t, pat in (('booking-inbox', r'未取り込み: (\d+)件'),
                   ('juchu-inbox', r'未取り込み: (\d+)件'),
                   ('kanryo-inbox', r'未取り込み: (\d+)件'),
                   ('kanryo-okuru', r'送る対象: (\d+)件'),
                   ('survey-inbox', r'未通知: (\d+)件'),
                   ('baito-inbox', r'未通知: (\d+)件')):   # 2026-10-03 アルバイトの業務報告を2人に知らせる（T062）   # 2026-10-03 アンケート回答を2人に知らせる（T061）
        rc, out = jikkou(f'tools/{t}.py', '--dry-run')
        m = re.search(pat, out)
        if not m:
            kekka.append(f'{t}: 試走の結果が読めない（{out.strip().splitlines()[-1:] or "出力なし"}）')
        elif int(m.group(1)) > 0:
            kekka.append(f'{t}: {m.group(0)}')
    return kekka


def yoyaku_api():
    """予約ページがカレンダーを直接読めているか。ok:false の間だけ空き枠の作り直しが要る"""
    import urllib.request
    src = open(os.path.join(KOKO, 'tools/build-booking.py'), encoding='utf-8').read()
    url = re.search(r'^API_URL = "([^"]+)"', src, re.M).group(1)
    body, err = '', None
    for _ in range(2):  # Apps Script はまれに一時的な 404 を返す（9/30 15:4x、直後は 200）。1回だけ取り直す
        try:
            body = urllib.request.urlopen(url + '?action=slots&minutes=120&callback=cb', timeout=60).read().decode()
            err = None
            break
        except Exception as e:
            err = e
    if err:
        return [f'予約APIに届かない（2回とも）: {err}']
    return [] if '"ok":true' in body else ['予約APIが ok:false（空き枠を旧手順で作り直す。savedata 参照）']


def keijiban(fun):
    """直近 fun 分に、CMO あてに新しく来たもの・CMO の依頼に返信が付いたもの"""
    jikkou('tools/org.py', '一覧')  # 掲示板を最新に引いてくる
    kijun = datetime.datetime.now(JST).replace(tzinfo=None) - datetime.timedelta(minutes=fun)
    kekka = []
    for p in sorted(glob.glob(os.path.expanduser('~/.cache/one-hitter-org/inbox/*.md'))):
        s = open(p, encoding='utf-8').read()
        g = lambda k: (re.search(rf'^- {k}: (.*)$', s, re.M) or [None, ''])[1].strip()
        kenmei, sa, ate = g('件名'), g('差出'), g('宛先')
        hi = [datetime.datetime.strptime(d, '%Y-%m-%d %H:%M')
              for d in re.findall(r'^- 出した日時: (\d{4}-\d\d-\d\d \d\d:\d\d)', s, re.M)]
        henshin = [(who.strip(), datetime.datetime.strptime(d, '%Y-%m-%d %H:%M'))
                   for who, d in re.findall(r'^## 返信（(.*?) / (\d{4}-\d\d-\d\d \d\d:\d\d)）', s, re.M)]
        iid = os.path.basename(p)[:-3]
        if ate == 'cmo' and g('状態') == '未処理' and hi and hi[0] >= kijun:
            kekka.append(f'掲示板（新着）: {iid} {sa}→cmo「{kenmei}」')
        elif 'cmo' in (sa, ate) and any(t >= kijun and not w.startswith('CMO') for w, t in henshin):
            # 完了済みの依頼に後から返信が足されることがある（9/30 crm のお礼SMS本文で見落とした）
            kekka.append(f'掲示板（返信）: {iid}「{kenmei}」')
    return kekka


def blog_tenken():
    """公開中のブログの画像・題名（tools/check-blog-public.py）。9時台と15時台だけ（1回40秒ほどかかる）。
    2026-10-08 オーナー指摘「写真はすべて使いまわし・ピンボケ」：16本が同じ 64×48px のまま2週間気づかなかった反省"""
    if datetime.datetime.now(JST).hour not in (9, 15):
        return []
    rc, out = jikkou('tools/check-blog-public.py', '--quiet', timeout=300)
    if rc == 0:
        return []
    return ['ブログの点検: ' + (out.strip().splitlines()[-1] if out.strip() else '失敗')]


def kagi_fukugen():
    """毎回、環境変数から鍵ファイルを書き戻す（作業場が作り直されても1時間以内に戻る）。

    2026-10-04 昼に作業場が作り直されて鍵が消え、3日半 LINE・取り込み・台帳が止まった。
    鍵の置き場はクラウド環境の環境変数（オーナーが1回登録）。ファイルは毎時ここで作り直す。
    """
    r = subprocess.run(['python3', os.path.join(KOKO, 'tools/kagi-fukugen.py')],
                       capture_output=True, text=True, check=False)
    nai = [l for l in r.stdout.splitlines() if l.startswith('鍵がありません')]
    hissu = ('GOOGLE_SHEETS_SA_KEY', 'NETLIFY_TOKEN', 'LINE_CHANNEL_TOKEN', 'LINE_GROUP_ID')
    if nai and any(h in nai[0] for h in hissu):
        return ['🔴 鍵が無い（' + '、'.join(h for h in hissu if h in nai[0]) + '）。'
                'クラウド環境の環境変数に登録が要る（認証情報ドキュメントの値。オーナー作業）。'
                '登録済みなら、このセッションは古いので新しいセッションで CMO を起こす']
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fun', type=int, default=None)
    a = ap.parse_args()
    if a.fun is None:
        # 朝いちばん（7時台）は夜間ぶん（22:42〜）もまとめて見る
        a.fun = 600 if datetime.datetime.now(JST).hour == 7 else 65
    # 鍵の書き戻しをいちばん先に。無ければ先頭に🔴で出す（鍵の要らない点検＝セーフブラウジング・予約API・掲示板は続ける）
    youtaiou = kagi_fukugen()
    for f in (safebrowsing, hosts_more, haifu_urls, line_midoku, torikomi, yoyaku_api, blog_tenken):
        try:
            youtaiou += f()
        except Exception as e:  # 点検の失敗は、それ自体を要対応として CMO に渡す
            youtaiou.append(f'{f.__name__} が失敗: {e}')
    try:
        youtaiou += keijiban(a.fun)
    except Exception as e:
        youtaiou.append(f'掲示板の確認が失敗: {e}')
    for y in youtaiou:
        print('・' + y)
    if not youtaiou:
        print('変化なし')
    print(f'要対応: {len(youtaiou)}件')


if __name__ == '__main__':
    main()
