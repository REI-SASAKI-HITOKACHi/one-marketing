#!/usr/bin/env python3
"""
配信ホスト全部の Google セーフブラウジング判定を見る（毎時ルーティン用）。
  python3 tools/check-safebrowsing.py
status 3 ＝「安全でない」判定（Google のテスト用危険サイトと同じ応答）。1＝安全、4＝問題なし、6＝データなし、302/HTML＝レート制限（次回に回す）。
終了コード：3 が1つでもあれば 1。
"""
import re, sys, urllib.request
HOSTS = [
    # ⚠ 並び順に意味がある。**お客様が実際に踏むホストを先に置く。**
    #    後ろのホストほど 429 に当たりやすく、判定が取れないまま終わりやすい
    #    （2026-09-15、`onehitter.jp` が10番目で毎回取れていなかった）。
    #    裏側の netlify.app は「データなし」が返るだけなので後ろでよい。

    # ── お客様が踏む独自ドメイン（ここが落ちると実害が出る） ──
    'lp.onehitter.jp',                  # LP4本。★広告の遷移先。判定を受けると広告費を払いながら誰も着地できない
    'onehitter.jp',                     # apex（301 → /mizumawari/）。※このホストは単独でも取れにくい
    'one-hitter.jp',                    # 公式サイト
    'yoyaku.onehitter.jp',              # 予約フォーム（独自ドメイン。2026-09-12 割り当て）
    'survey.onehitter.jp',              # ご利用後アンケート。★現場のQRが飛ぶ先
    'dokuhon.onehitter.jp',             # 読本（独自ドメイン）
    'tenken.onehitter.jp',              # 無料点検（独自ドメイン）

    # ── 裏側のホスト（送信済みリンクの行き先として生かしてあるもの含む） ──
    'one-hitter-booking.netlify.app',   # 旧予約フォーム（2026-09-12 に判定 → 2026-09-15 解除を確認）
    'onehitter-yoyaku.netlify.app',     # 予約フォーム（現行）
    'one-hitter-lp.netlify.app',        # LP4本
    'one-hitter-nenmatsu.netlify.app',  # 年末LP（301）
    'one-hitter-survey.netlify.app',    # アンケート
    'one-hitter-dokuhon.netlify.app',   # 読本
    'one-hitter-tenken.netlify.app',    # 無料点検
    'one-hitter-sns-media.netlify.app', # SNS画像
]
LABEL = {1: '安全', 3: '⚠ 安全でない（判定中）', 4: '問題なし', 6: 'データなし（判定なし）'}
URL = 'https://transparencyreport.google.com/transparencyreport/api/v3/safebrowsing/status?site='

# 短時間に連続で叩くと 429 になる（2026-09-12 に12ホストで発生）。ホスト間に間隔を置く。
# ⚠ 一覧の後ろのほうのホストは毎回 429 に当たりやすく、「次回に回す」を続けると
#    永久に判定が取れない（2026-09-15、onehitter.jp が10番目で毎回取れていなかった）。
#    取れなかったぶんは、間隔を空けて追いかける。
import time


def hantei(h):
    """安全判定を返す。取れなければ None。"""
    try:
        raw = urllib.request.urlopen(URL + h, timeout=20).read().decode('utf-8', 'ignore')
    except urllib.error.HTTPError as e:
        # 429 以外の HTTP エラーは、追いかけても同じ結果なのでそのまま返す
        return None if e.code == 429 else f'HTTP {e.code}'
    except Exception:
        # 接続リセット等の一時的な失敗も追いかける（2026-09-15、lp.onehitter.jp で
        # Connection reset by peer に当たり、1周目で諦めて判定が取れなかった）
        return None
    m = re.search(r'"sb\.ssr",(\d+)', raw)
    return int(m.group(1)) if m else None


kekka = {}
nokori = list(HOSTS)
for machi in (4, 15, 30):          # 追いかけるたびに間隔を広げる
    if not nokori:
        break
    tsugi = []
    for i, h in enumerate(nokori):
        if i:
            time.sleep(machi)
        r = hantei(h)
        if r is None:
            tsugi.append(h)        # レート制限。次の周で追いかける
        else:
            kekka[h] = r
    nokori = tsugi
    if nokori:
        print(f'（レート制限 {len(nokori)}件。{machi * 3}秒あけて追いかけます）')
        time.sleep(machi * 3)

bad = 0
for h in HOSTS:
    r = kekka.get(h)
    if r is None:
        print(f'{h}: 判定が取れませんでした（レート制限が続いた）')
        continue
    if isinstance(r, str):
        print(f'{h}: {r}')
        continue
    print(f'{h}: {LABEL.get(r, f"status={r}")}')
    bad += (r == 3)

if nokori:
    print(f'\n※ {len(nokori)}件は判定が取れませんでした: {" ".join(nokori)}')
    print('  単独で叩くと取れることが多い（一覧の後ろのホストほど 429 に当たりやすい）')
sys.exit(1 if bad else 0)
