#!/usr/bin/env python3
"""
お客様が開くページを配信する前の点検（2026-09-12 セーフブラウジング事故の再発防止）。

  python3 tools/check-public-page.py <HTMLファイル or URL> ...
  python3 tools/check-public-page.py --hp <公式サイトに載るページ> ...   # 公式サイト自身の /privacy_policy/ へのリンクを、開けることを確かめて認める

見るもの（1つでも欠けたら終了コード 1）：
  1. 会社名「ワンヒッター株式会社」（本舗向けページは「おそうじ本舗」）が本文にある
  2. 所在地（江戸川区）と電話番号がある
  3. 「個人情報の取扱い」または「プライバシーポリシー」へのリンクがある（公式サイトの privacy_policy を指していたらNG。2026-10-09〜）
  4. sms: を組み立てるスクリプト（送信ツール）を同居させていない
  5. パスワード・クレジットカード番号の入力欄が無い
理由：無料ドメイン上で個人情報を入力させるページは、運営者情報が無いとフィッシングと誤判定される。
      送信ツール（sms: を開くページ）を同じホストに置くと、スミッシングの道具に見える。
"""
import re, sys, urllib.request

def yomu(src):
    if src.startswith('http'):
        return urllib.request.urlopen(src, timeout=20).read().decode('utf-8', 'ignore')
    return open(src, encoding='utf-8', errors='ignore').read()

def tenken(src, hp=False):
    h = yomu(src)
    t = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', h, flags=re.S)
    text = re.sub(r'<[^>]+>', ' ', t)
    ng = []
    if not re.search(r'ワンヒッター株式会社|おそうじ本舗', text): ng.append('会社名が無い')
    if '江戸川区' not in text: ng.append('所在地（江戸川区）が無い')
    if not re.search(r'0\d{1,3}-\d{2,4}-\d{4}', text): ng.append('電話番号が無い')
    if not re.search(r'href="[^"]*(privacy|policy)[^"]*"', h) and not re.search(r'個人情報の取扱い|プライバシーポリシー', text):
        ng.append('個人情報の取扱い／プライバシーポリシーへのリンクが無い')
    # 公式サイトは 2026-10-09 に全ページ 403 になった。リンク先は自社LPホストの /privacy/ を正にする（依頼 20261009-01-lp）
    # --hp：公式サイト（one-hitter.jp）そのものに載るページ。共通フッターの自サイトの /privacy_policy/ は正しいリンクなので、
    #       そのページが今開ける（200）ことを確かめたうえで、この1項目だけ外す（依頼 20261022-01-lp）
    if hp and re.search(r'href="https?://(www\.)?one-hitter\.jp/privacy_policy', h):
        try:
            if urllib.request.urlopen('https://one-hitter.jp/privacy_policy/', timeout=20).status != 200:
                ng.append('公式サイトの /privacy_policy/ が開けない')
        except Exception as e:
            ng.append(f'公式サイトの /privacy_policy/ が開けない（{type(e).__name__}）')
    elif re.search(r'href="https?://(www\.)?one-hitter\.jp/privacy_policy', h):
        ng.append('個人情報の取扱いのリンク先が公式サイト（one-hitter.jp/privacy_policy/）のまま。https://lp.onehitter.jp/privacy/ へ')
    if re.search(r"['\"]sms:|location\.href\s*=\s*['\"]?sms", h): ng.append('sms: を組み立てるスクリプトが同居している（送信ツールは社内用ホストへ）')
    # ★見るのは「入力欄があるか」。語が出てくるだけでNGにしない。
    #   特商法の表記は支払方法として「クレジットカード」に触れる必要があり、
    #   語で弾くと、載せなければならないページが配信できない（2026-09-17 実際に弾かれた）。
    if re.search(r'type="password"', h, re.I) \
       or re.search(r'<input[^>]*(card[_-]?number|カード番号|セキュリティコード|cvv|cvc)', h, re.I) \
       or re.search(r'(name|id|placeholder)\s*=\s*["\'][^"\']*(card[_-]?number|カード番号)', h, re.I):
        ng.append('パスワード／カード番号の入力欄がある')
    if re.search(r'prefers-color-scheme\s*:\s*dark|data-theme="dark"', h): ng.append('ダークモード対応が入っている（お客様のページは常に白地。2026-09-12 オーナー指示）')
    return ng

if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    bad = 0
    hp = '--hp' in sys.argv[1:]
    for src in [a for a in sys.argv[1:] if a != '--hp']:
        ng = tenken(src, hp)
        print(('NG ' if ng else 'OK ') + src + ('：' + '／'.join(ng) if ng else ''))
        bad += bool(ng)
    sys.exit(1 if bad else 0)
