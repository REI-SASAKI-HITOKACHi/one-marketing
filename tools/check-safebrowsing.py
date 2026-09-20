#!/usr/bin/env python3
"""
配信ホスト全部の Google セーフブラウジング判定を見る（毎時ルーティン用）。
  python3 tools/check-safebrowsing.py
status 3 ＝「安全でない」判定（Google のテスト用危険サイトと同じ応答）。1＝安全、4＝問題なし、6＝データなし、302/HTML＝レート制限（次回に回す）。
終了コード：3 が1つでもあれば 1。
"""
import json, re, sys, urllib.request
HOSTS = [
    # ⚠ 並び順に意味がある。**お客様が実際に踏むホストを先に置く。**
    #    後ろのホストほど 429 に当たりやすく、判定が取れないまま終わりやすい
    #    （2026-09-15、`onehitter.jp` が10番目で毎回取れていなかった）。
    #    裏側の netlify.app は「データなし」が返るだけなので後ろでよい。

    # ── お客様が踏む独自ドメイン（ここが落ちると実害が出る） ──
    'lp.onehitter.jp',                  # LP4本。★広告の遷移先。判定を受けると広告費を払いながら誰も着地できない
    'onehitter.jp',                     # apex（301 → /mizumawari/）★このホストだけ3周とも429に当たる（2026-09-15）。単独で叩けば一発で返る
    'one-hitter.jp',                    # 公式サイト
    'yoyaku.onehitter.jp',              # 予約フォーム（独自ドメイン。2026-09-12 割り当て）
    'survey.onehitter.jp',              # ご利用後アンケート。★現場のQRが飛ぶ先
    'dokuhon.onehitter.jp',             # 読本（独自ドメイン）
    'tenken.onehitter.jp',              # 無料点検（独自ドメイン）

    # ── 裏側のホスト（送信済みリンクの行き先として生かしてあるもの含む） ──
    'araidoki.netlify.app',             # 洗い時図鑑。★公開中。SNS・GBPからお客様が踏む（2026-09-20 追加。
                                        #   README 4.10.1「新しいホストは当日中に HOSTS へ」に5日間反していた）
    'oh-naibu-sms-k7q3x.netlify.app',   # 社内用（受注フォーム /juchu/・作業完了フォーム /kanryo/）。
                                        #   お客様は踏まないが、判定を受けると和真さんが現場で入力できなくなる
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
import datetime
import os
import time

# ★ 2026-09-20 追加。**並び順が固定だと、後ろのホストが毎回 429 に当たって
#    何時間も判定が取れないままになる。**「次回に回す」と書いてあっても、
#    次回も同じ順で同じところが落ちるので、次回が来ない。
#    → 前回いつ判定が取れたかを覚えておき、**古いものから先に叩く。**
#    お客様が踏むホストは、それでも常にバックエンドより先。
KIROKU = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      'data', 'safebrowsing-last.json')

# お客様が実際に踏むホスト。ここが落ちると実害が出るので、必ず先に叩く。
OKYAKU_MUKE = frozenset({
    'lp.onehitter.jp', 'onehitter.jp', 'one-hitter.jp', 'yoyaku.onehitter.jp',
    'survey.onehitter.jp', 'dokuhon.onehitter.jp', 'tenken.onehitter.jp',
    'araidoki.netlify.app',
})

# これより長く判定が取れていないホストがあれば、最後に警告を出す
FURUI_JIKAN = 6 * 3600


def kiroku_yomu():
    try:
        with open(KIROKU, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        # 記録が無い・壊れているのは、点検そのものを止める理由にならない
        return {}


def kiroku_kaku(d):
    try:
        os.makedirs(os.path.dirname(KIROKU), exist_ok=True)
        with open(KIROKU, 'w', encoding='utf-8') as f:
            json.dump(d, f, ensure_ascii=False, indent=1, sort_keys=True)
    except Exception as e:
        print(f'※ 前回時刻の記録に失敗（点検そのものには影響しません）: {e}')


def junban(hosts, mae):
    """お客様向けを先に、そのなかで「前回取れてから長いもの」を先に並べる。"""
    moto = {h: i for i, h in enumerate(hosts)}

    def key(h):
        t = (mae.get(h) or {}).get('at', '')   # 記録が無ければ '' で最優先
        return (0 if h in OKYAKU_MUKE else 1, t, moto[h])

    return sorted(hosts, key=key)


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


# 既定は1周だけ（毎時の巡回用。数分かかると巡回が時間切れになる）。
# 配信前など、全ホストの判定を必ず取りたいときは --oikake を付ける。
OIKAKE = '--oikake' in sys.argv
MACHI = (4, 15, 30) if OIKAKE else (4,)

# ★ 2026-09-20 追加。**このツール自身が「単独で叩くと取れることが多い」と
#    案内していたのに、単独で叩く手段が無かった。**
#    `python3 tools/check-safebrowsing.py lp.onehitter.jp survey.onehitter.jp`
#    のようにホスト名を並べると、そこだけを叩く（前回時刻の記録も更新される）。
SITEI = [a for a in sys.argv[1:] if not a.startswith('-')]
if SITEI:
    shiranai = [h for h in SITEI if h not in HOSTS]
    if shiranai:
        # 一覧に無いホストを黙って叩くと、監視に入れ忘れたまま
        # 「点検した」という誤った安心が残る
        sys.exit('監視の一覧に無いホストです: ' + ' '.join(shiranai) +
                 '\n  HOSTS に足してから叩いてください（docs/org/README.md 4.10.1）')
    HOSTS = SITEI

MAE = kiroku_yomu()

kekka = {}
nokori = junban(HOSTS, MAE)        # ★固定順ではなく、古いものから
for machi in MACHI:                # 追いかけるたびに間隔を広げる
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
    if nokori and machi != MACHI[-1]:
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

IMA = datetime.datetime.now(datetime.timezone.utc)
for h, r in kekka.items():
    if isinstance(r, int):         # 判定が取れたものだけ記録する
        MAE[h] = {'at': IMA.isoformat(timespec='seconds'), 'status': r}
kiroku_kaku(MAE)

# ★ 何時間も判定が取れていないホストを名指しする。
#    「今回取れなかった」より「ずっと取れていない」のほうが危ない。
furui = []
for h in HOSTS:
    at = (MAE.get(h) or {}).get('at')
    if not at:
        furui.append((h, 'まだ一度も取れていません'))
        continue
    try:
        sa = (IMA - datetime.datetime.fromisoformat(at)).total_seconds()
    except Exception:
        continue
    if sa > FURUI_JIKAN:
        furui.append((h, f'前回取れたのは {sa / 3600:.1f} 時間前'))
if furui:
    print('\n🔴 長く判定が取れていないホストがあります（今回の失敗より重い）')
    for h, riyuu in furui:
        print(f'   {h}: {riyuu}')
    print('   → 単独で叩くか、--oikake を付けて確実に取ること')

if nokori:
    print(f'\n※ {len(nokori)}件は判定が取れませんでした: {" ".join(nokori)}')
    if not OIKAKE:
        print('  --oikake を付けると、間隔を広げて3周まで追いかけます（数分かかります）')
    print('  単独で叩くには: python3 tools/check-safebrowsing.py <ホスト名> [<ホスト名>…]')
sys.exit(1 if bad else 0)
