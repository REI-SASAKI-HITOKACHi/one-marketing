#!/usr/bin/env python3
"""スレッド間の掲示板。オーナーを経由せずにスレッド同士でやり取りするための道具。

【なぜこの形か】
  スレッドはそれぞれ別のブランチで作業している。
  掲示板を各自のブランチに置くと、相手には見えない。
  そこで claude/org という共有ブランチを1本だけ立てて、そこに置く。
  自分の作業ブランチは一切触らないので、作業中でも安全に読み書きできる。

  git の操作はこの中で全部やる。使う側は git を意識しなくてよい。

【使い方】
  python3 tools/org.py 名簿
  python3 tools/org.py 読む <役割ID>            # 自分あての未処理だけ出す
  python3 tools/org.py 一覧 [--全部]
  python3 tools/org.py 見る <依頼ID>
  echo "本文" | python3 tools/org.py 依頼 --from lp --to cmo --件名 "料金の確認"
  echo "本文" | python3 tools/org.py 返信 <依頼ID> --from cmo
  python3 tools/org.py 完了 <依頼ID> --from cmo
  cat status.md | python3 tools/org.py 現況 --from lp

  本文は標準入力から読む。--本文 "..." で直接渡してもよい。
"""
import argparse
import datetime
import os
import re
import subprocess
import sys

BRANCH = 'claude/org'
# 掲示板の実体はここに置く。作業中のブランチとは別のディレクトリなので、
# 自分の作業ツリーを一切汚さない
WORK = os.path.expanduser('~/.cache/one-hitter-org')

YAKUWARI = {
    'cmo':         'CMO',
    'lp':          'LP・サイト担当',
    'crm':         '顧客接点担当（SMS・公式LINE）',
    'measurement': '計測担当（GA4・広告タグ・電話CV）',
    'quotation':   '見積アプリ担当',
    'web-inflow':  'ネット流入施策担当（SNS＋メディア）',
    'browser':     'ブラウザ担当（オーナーのPCで画面操作）',
    'owner':       'オーナー（佐々木 嶺）',
}


def run(*a, **kw):
    kw.setdefault('capture_output', True)
    kw.setdefault('text', True)
    return subprocess.run(a, **kw)


def repo():
    r = run('git', 'rev-parse', '--show-toplevel')
    if r.returncode:
        sys.exit('gitリポジトリの中で実行してください。')
    return r.stdout.strip()


def origin_url():
    return run('git', '-C', repo(), 'remote', 'get-url', 'origin').stdout.strip()


def youi():
    """掲示板のブランチを手元に用意する。無ければ作る。

    ★手元のリポジトリからではなく、origin のURLから直接 clone する。
      手元のリポジトリには claude/org が「origin/claude/org」としてしか無いので、
      そこから --branch claude/org で clone すると失敗する
      （2026-09-10、顧客接点スレッドが最初に叩いたときに起きた）。"""
    url = origin_url()
    if not os.path.isdir(os.path.join(WORK, '.git')):
        os.makedirs(os.path.dirname(WORK), exist_ok=True)
        r = run('git', 'ls-remote', '--heads', url, BRANCH)
        if r.returncode == 0 and r.stdout.strip():
            c = run('git', 'clone', '--branch', BRANCH, '--single-branch', url, WORK)
            if c.returncode:
                sys.exit('掲示板を取ってこられませんでした:\n' + c.stderr)
        else:
            # 掲示板がまだ無い。空のブランチとして作る
            run('git', 'init', WORK)
            run('git', '-C', WORK, 'checkout', '--orphan', BRANCH)
            run('git', '-C', WORK, 'remote', 'add', 'origin', url)
            for d in ('inbox', 'status'):
                os.makedirs(os.path.join(WORK, d), exist_ok=True)
            open(os.path.join(WORK, 'README.md'), 'w', encoding='utf-8').write(
                'ワンヒッターのスレッド掲示板。tools/org.py が読み書きする。\n'
                '直接編集してもよいが、書式は docs/org/README.md に従うこと。\n')
            run('git', '-C', WORK, 'add', '-A')
            run('git', '-C', WORK, 'commit', '-m', '掲示板を作った')
            osu()
            return
    hiku()


def hiku():
    """最新に追いつく。ここを忘れると、古い掲示板を見て判断してしまう"""
    run('git', '-C', WORK, 'fetch', 'origin', BRANCH)
    r = run('git', '-C', WORK, 'reset', '--hard', f'origin/{BRANCH}')
    if r.returncode:
        print('※ 掲示板の取得に失敗しました。手元にあるものを使います。', file=sys.stderr)
    for d in ('inbox', 'status'):
        os.makedirs(os.path.join(WORK, d), exist_ok=True)


def osu(mes='掲示板を更新'):
    """書いたら必ず押す。押さないと相手に見えない"""
    run('git', '-C', WORK, 'add', '-A')
    r = run('git', '-C', WORK, 'commit', '-m', mes)
    if r.returncode and 'nothing to commit' in (r.stdout + r.stderr):
        return True
    for _ in range(3):
        p = run('git', '-C', WORK, 'push', 'origin', f'HEAD:{BRANCH}')
        if p.returncode == 0:
            return True
        # 他のスレッドが同時に書いた。取り込んでからもう一度
        run('git', '-C', WORK, 'fetch', 'origin', BRANCH)
        run('git', '-C', WORK, 'rebase', f'origin/{BRANCH}')
    print('★ 掲示板に押せませんでした。手元には残っています:', WORK, file=sys.stderr)
    return False


def honbun(a):
    if a.本文:
        return a.本文
    if sys.stdin.isatty():
        sys.exit('本文がありません。標準入力で渡すか --本文 を使ってください。')
    return sys.stdin.read()


def ima():
    return datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y-%m-%d %H:%M')


def michi(idd):
    return os.path.join(WORK, 'inbox', idd + '.md')


def yomu_id(idd):
    p = michi(idd)
    if not os.path.exists(p):
        sys.exit(f'{idd} という依頼はありません。「一覧」で確認してください。')
    return open(p, encoding='utf-8').read()


def midashi(text):
    """依頼ファイルの頭の項目を辞書にする"""
    d = {}
    for ln in text.split('\n'):
        m = re.match(r'^- (\S+?): (.*)$', ln)
        if m:
            d[m.group(1)] = m.group(2).strip()
        if ln.startswith('---'):
            break
    return d


def subete():
    if not os.path.isdir(os.path.join(WORK, 'inbox')):
        return []
    out = []
    for na in sorted(os.listdir(os.path.join(WORK, 'inbox'))):
        if not na.endswith('.md'):
            continue
        idd = na[:-3]
        t = open(michi(idd), encoding='utf-8').read()
        out.append((idd, midashi(t), t))
    return out


# ============================== それぞれの操作 ==============================
def op_meibo(a):
    print('役割ID       担当')
    for k, v in YAKUWARI.items():
        print(f'{k:<12} {v}')
    print()
    print('職務範囲と持ち物: docs/org/roles/<役割ID>.md')


def op_yomu(a):
    youi()
    jibun = a.役割
    if jibun not in YAKUWARI:
        sys.exit(f'知らない役割IDです: {jibun}（「名簿」で確認してください）')
    mi = [(i, h, t) for i, h, t in subete()
          if h.get('宛先') == jibun and h.get('状態') != '完了']
    if not mi:
        print(f'{YAKUWARI[jibun]} あての未処理はありません。')
        return
    print(f'★ {YAKUWARI[jibun]} あての未処理 {len(mi)}件')
    print()
    for i, h, t in mi:
        print('=' * 60)
        print(t.rstrip())
        print()
    print('=' * 60)
    print('返信:  echo "本文" | python3 tools/org.py 返信 <依頼ID> --from ' + jibun)
    print('完了:  python3 tools/org.py 完了 <依頼ID> --from ' + jibun)


def op_ichiran(a):
    youi()
    ss = subete()
    if not a.全部:
        ss = [x for x in ss if x[1].get('状態') != '完了']
    if not ss:
        print('依頼はありません。')
        return
    print(f'{"依頼ID":<28} {"差出":<12} {"宛先":<12} 状態   件名')
    for i, h, t in ss:
        print(f'{i:<28} {h.get("差出",""):<12} {h.get("宛先",""):<12} '
              f'{h.get("状態",""):<6} {h.get("件名","")}')


def op_miru(a):
    youi()
    print(yomu_id(a.依頼ID).rstrip())


def op_irai(a):
    youi()
    for k in (a.差出, a.宛先):
        if k not in YAKUWARI:
            sys.exit(f'知らない役割IDです: {k}（「名簿」で確認してください）')
    hi = datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=9))).strftime('%Y%m%d')
    n = 1
    while os.path.exists(michi(f'{hi}-{n:02d}-{a.宛先}')):
        n += 1
    idd = f'{hi}-{n:02d}-{a.宛先}'
    body = (
        f'# {a.件名}\n\n'
        f'- 依頼ID: {idd}\n'
        f'- 差出: {a.差出}\n'
        f'- 宛先: {a.宛先}\n'
        f'- 件名: {a.件名}\n'
        f'- 期限: {a.期限 or "なし"}\n'
        f'- 状態: 未処理\n'
        f'- 出した日時: {ima()}\n\n'
        f'---\n\n'
        f'{honbun(a).rstrip()}\n'
    )
    open(michi(idd), 'w', encoding='utf-8').write(body)
    osu(f'依頼 {idd}: {a.件名}（{a.差出}→{a.宛先}）')
    print('出しました:', idd)
    print(f'相手が読むコマンド: python3 tools/org.py 読む {a.宛先}')


def op_henshin(a):
    youi()
    t = yomu_id(a.依頼ID)
    t = t.rstrip() + (
        f'\n\n---\n\n## 返信（{YAKUWARI.get(a.差出, a.差出)} / {ima()}）\n\n'
        f'{honbun(a).rstrip()}\n')
    # 返信したら、球は相手に戻る
    h = midashi(t)
    if h.get('宛先') == a.差出:
        t = t.replace(f'- 宛先: {h["宛先"]}', f'- 宛先: {h.get("差出","")}', 1)
        t = t.replace(f'- 差出: {h.get("差出","")}', f'- 差出: {a.差出}', 1)
    open(michi(a.依頼ID), 'w', encoding='utf-8').write(t)
    osu(f'返信 {a.依頼ID}（{a.差出}）')
    print('返しました:', a.依頼ID)


def op_kanryou(a):
    youi()
    t = yomu_id(a.依頼ID)
    t = t.replace('- 状態: 未処理', '- 状態: 完了', 1)
    t = t.rstrip() + f'\n\n---\n\n完了（{YAKUWARI.get(a.差出, a.差出)} / {ima()}）\n'
    open(michi(a.依頼ID), 'w', encoding='utf-8').write(t)
    osu(f'完了 {a.依頼ID}')
    print('完了にしました:', a.依頼ID)


def op_genkyou(a):
    youi()
    if a.差出 not in YAKUWARI:
        sys.exit(f'知らない役割IDです: {a.差出}')
    p = os.path.join(WORK, 'status', a.差出 + '.md')
    open(p, 'w', encoding='utf-8').write(
        f'# {YAKUWARI[a.差出]} の現況\n\n更新: {ima()}\n\n{honbun(a).rstrip()}\n')
    osu(f'現況 {a.差出}')
    print('更新しました:', a.差出)


def op_genkyou_ichiran(a):
    youi()
    d = os.path.join(WORK, 'status')
    na = sorted(os.listdir(d)) if os.path.isdir(d) else []
    if not na:
        print('現況はまだ1件もありません。')
        return
    for f in na:
        if f.endswith('.md'):
            print('=' * 60)
            print(open(os.path.join(d, f), encoding='utf-8').read().rstrip())
            print()


def main():
    p = argparse.ArgumentParser(description='スレッド間の掲示板')
    s = p.add_subparsers(dest='cmd', required=True)

    s.add_parser('名簿')

    q = s.add_parser('読む'); q.add_argument('役割')
    q = s.add_parser('一覧'); q.add_argument('--全部', action='store_true')
    q = s.add_parser('見る'); q.add_argument('依頼ID')

    q = s.add_parser('依頼')
    q.add_argument('--from', dest='差出', required=True)
    q.add_argument('--to', dest='宛先', required=True)
    q.add_argument('--件名', required=True)
    q.add_argument('--期限', default='')
    q.add_argument('--本文', default='')

    q = s.add_parser('返信')
    q.add_argument('依頼ID')
    q.add_argument('--from', dest='差出', required=True)
    q.add_argument('--本文', default='')

    q = s.add_parser('完了')
    q.add_argument('依頼ID')
    q.add_argument('--from', dest='差出', default='cmo')

    q = s.add_parser('現況')
    q.add_argument('--from', dest='差出', required=True)
    q.add_argument('--本文', default='')

    s.add_parser('現況一覧')

    a = p.parse_args()
    {'名簿': op_meibo, '読む': op_yomu, '一覧': op_ichiran, '見る': op_miru,
     '依頼': op_irai, '返信': op_henshin, '完了': op_kanryou,
     '現況': op_genkyou, '現況一覧': op_genkyou_ichiran}[a.cmd](a)


if __name__ == '__main__':
    main()
