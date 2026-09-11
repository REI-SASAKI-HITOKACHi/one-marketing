#!/usr/bin/env python3
"""
お客様が開くページを配信する前の点検（2026-09-12 セーフブラウジング事故の再発防止）。

  python3 tools/check-public-page.py <HTMLファイル or URL> ...

見るもの（1つでも欠けたら終了コード 1）：
  1. 会社名「ワンヒッター株式会社」（本舗向けページは「おそうじ本舗」）が本文にある
  2. 所在地（江戸川区）と電話番号がある
  3. 「個人情報の取扱い」または「プライバシーポリシー」へのリンクがある
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

def tenken(src):
    h = yomu(src)
    t = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', h, flags=re.S)
    text = re.sub(r'<[^>]+>', ' ', t)
    ng = []
    if not re.search(r'ワンヒッター株式会社|おそうじ本舗', text): ng.append('会社名が無い')
    if '江戸川区' not in text: ng.append('所在地（江戸川区）が無い')
    if not re.search(r'0\d{1,3}-\d{2,4}-\d{4}', text): ng.append('電話番号が無い')
    if not re.search(r'href="[^"]*(privacy|policy)[^"]*"', h) and not re.search(r'個人情報の取扱い|プライバシーポリシー', text):
        ng.append('個人情報の取扱い／プライバシーポリシーへのリンクが無い')
    if re.search(r"['\"]sms:|location\.href\s*=\s*['\"]?sms", h): ng.append('sms: を組み立てるスクリプトが同居している（送信ツールは社内用ホストへ）')
    if re.search(r'type="password"|クレジットカード|card ?number', h, re.I): ng.append('パスワード／カード番号の入力欄がある')
    return ng

if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    bad = 0
    for src in sys.argv[1:]:
        ng = tenken(src)
        print(('NG ' if ng else 'OK ') + src + ('：' + '／'.join(ng) if ng else ''))
        bad += bool(ng)
    sys.exit(1 if bad else 0)
