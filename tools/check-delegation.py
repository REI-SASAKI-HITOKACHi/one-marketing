#!/usr/bin/env python3
"""onehitter.jp のネームサーバーがNetlify（NS1）へ切り替わったかを見る。

  python3 tools/check-delegation.py [ドメイン]

**なぜ専用の道具があるのか**

この作業環境には `dig` が無く、権威サーバへ生のUDPで直接引く方法も当てにならない
（NS1がホストしていることが確実なゾーンを対照に置いても SERVFAIL が返る）。
2026-09-12、これで「ムームー側に入れたNS値が間違っているのでは」と
誤った指摘を出しかけた。実際にはNetlify APIで見ると設定は正しかった。

**委任の確認はDNS-over-HTTPSで行うこと。** それをこの道具に閉じ込めてある。

終了コード 0＝切替済み／1＝まだ／2＝引けなかった
"""
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

KITAI = "nsone.net"          # Netlify DNS の権威サーバ
DOMAIN = "onehitter.jp"
DOH = "https://dns.google/resolve"


def hiku(name: str, typ: str = "NS") -> list[str]:
    u = f"{DOH}?name={urllib.parse.quote(name)}&type={typ}"
    r = urllib.request.Request(u, headers={"accept": "application/dns-json"})
    with urllib.request.urlopen(r, timeout=30) as f:
        d = json.loads(f.read())
    return [a["data"].rstrip(".") for a in d.get("Answer", [])]


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else DOMAIN
    try:
        ns = hiku(name)
    except urllib.error.URLError as e:
        sys.exit(f"引けませんでした: {e}")
    if not ns:
        print(f"{name} の NS が返りません（まだ登録直後かもしれません）")
        sys.exit(1)
    print(f"{name} の NS:")
    for x in sorted(ns):
        print("   ", x)
    if all(KITAI in x for x in ns):
        print(f"\n✅ 切替済みです（すべて {KITAI}）。カスタムドメインの割り当てに進めます。")
        sys.exit(0)
    print(f"\n⏳ まだです。{KITAI} 以外が返っています。")
    print("   ムームーの注記は「2〜3日かかる場合があります」。時間をおいて再実行してください。")
    sys.exit(1)
