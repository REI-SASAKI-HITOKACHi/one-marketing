#!/usr/bin/env python3
"""Meta Graph API（Instagram / Facebookページ）の薄いクライアント。

トークンは ~/.config/one-hitter/meta.json（git の外）から読む。値は絶対に print しない。
  python3 tools/meta_client.py check   # 疎通確認：ページ名・IGユーザー名・フォロワー数・投稿数・最終投稿日だけ出す
"""
import json
import os
import sys
import urllib.parse
import urllib.request

CONF = os.path.expanduser("~/.config/one-hitter/meta.json")


def conf() -> dict:
    if not os.path.exists(CONF):
        sys.exit(f"{CONF} がありません（認証情報ドキュメント第11節から転記する）")
    return json.load(open(CONF, encoding="utf-8"))


def call(path: str, params: dict | None = None, method: str = "GET", data: dict | None = None, files: dict | None = None) -> dict:
    c = conf()
    base = f"https://graph.facebook.com/{c.get('api_version', 'v21.0')}/{path.lstrip('/')}"
    params = dict(params or {})
    params["access_token"] = c["access_token"]
    if method == "GET":
        url = base + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url)
    else:
        body = dict(data or {})
        body.update(params)
        req = urllib.request.Request(base, data=urllib.parse.urlencode(body).encode(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        msg = e.read().decode()[:500].replace(c["access_token"], "***")
        raise SystemExit(f"Graph API {method} {path} が {e.code}: {msg}")


def check() -> None:
    c = conf()
    acc = call("me/accounts", {"fields": "name,id"})
    names = [a.get("name") for a in acc.get("data", [])]
    print("ページ:", names)
    ig = call(c["ig_user_id"], {"fields": "username,followers_count,media_count"})
    print("Instagram:", ig.get("username"), "フォロワー", ig.get("followers_count"), "投稿", ig.get("media_count"))
    media = call(f"{c['ig_user_id']}/media", {"fields": "timestamp,media_type,permalink", "limit": 3})
    for m in media.get("data", [])[:3]:
        print("  最近の投稿:", m.get("timestamp"), m.get("media_type"), m.get("permalink"))
    page = call(c["page_id"], {"fields": "name,fan_count,followers_count"})
    print("Facebookページ:", page.get("name"), "フォロワー", page.get("followers_count"), "いいね", page.get("fan_count"))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        check()
    else:
        print(__doc__)
