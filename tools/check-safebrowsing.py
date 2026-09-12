#!/usr/bin/env python3
"""
配信ホスト全部の Google セーフブラウジング判定を見る（毎時ルーティン用）。
  python3 tools/check-safebrowsing.py
status 3 ＝「安全でない」判定（Google のテスト用危険サイトと同じ応答）。1＝安全、4＝問題なし、6＝データなし、302/HTML＝レート制限（次回に回す）。
終了コード：3 が1つでもあれば 1。
"""
import re, sys, urllib.request
HOSTS = [
    'one-hitter-booking.netlify.app',   # 旧予約フォーム（2026-09-12 判定。解除待ち）
    'onehitter-yoyaku.netlify.app',     # 予約フォーム（現行）
    'one-hitter-lp.netlify.app',        # LP4本
    'one-hitter-nenmatsu.netlify.app',  # 年末LP（301）
    'one-hitter-survey.netlify.app',    # アンケート
    'one-hitter-dokuhon.netlify.app',   # 読本
    'one-hitter-tenken.netlify.app',    # 無料点検
    'one-hitter-sns-media.netlify.app', # SNS画像
    'one-hitter.jp',                    # 公式サイト
    'yoyaku.onehitter.jp',              # 予約フォーム（独自ドメイン。2026-09-12 割り当て）
    'dokuhon.onehitter.jp',             # 読本（独自ドメイン）
    'tenken.onehitter.jp',              # 無料点検（独自ドメイン）
]
bad = 0
# 短時間に連続で叩くと 429 になる（2026-09-12 に12ホストで発生）。ホスト間に間隔を置く。
import time
for i, h in enumerate(HOSTS):
    if i: time.sleep(4)
    try:
        raw = urllib.request.urlopen(f'https://transparencyreport.google.com/transparencyreport/api/v3/safebrowsing/status?site={h}', timeout=20).read().decode('utf-8', 'ignore')
    except urllib.error.HTTPError as e:
        print(f'{h}: HTTP {e.code}（レート制限。次回に回す）' if e.code == 429 else f'{h}: HTTP {e.code}'); continue
    except Exception as e:
        print(f'{h}: 取得失敗（{e}）'); continue
    m = re.search(r'"sb\.ssr",(\d+)', raw)
    if not m:
        print(f'{h}: レート制限（次回に回す）'); continue
    st = int(m.group(1))
    label = {1: '安全', 3: '⚠ 安全でない（判定中）', 4: '問題なし', 6: 'データなし（判定なし）'}.get(st, f'status={st}')
    print(f'{h}: {label}')
    bad += (st == 3)
sys.exit(1 if bad else 0)
