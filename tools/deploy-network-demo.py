#!/usr/bin/env python3
"""協力店ネット（仮称）のデモを、専用の Netlify サイトへ配信する。

LP（one-hitter-lp など）とは**別サイト**。ここからLPのサイトへは絶対に配信しない
（Netlify の配信はサイト全体のファイル一覧を差し替えるため、LPが消える）。

  python3 tools/build-network-demo.py           # 先に index.html を作る
  python3 tools/deploy-network-demo.py          # 無ければサイトを作って配信

トークンは環境変数 NETLIFY_TOKEN、無ければ ~/.config/one-hitter/netlify-token.txt。
リポジトリには置かない。
"""
import hashlib
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
API = "https://api.netlify.com/api/v1"
SITE_NAME = "kyoryokuten-net-demo"   # 公開URL：https://kyoryokuten-net-demo.netlify.app/
TEAM_SLUG = "case-foot-kid"
KINSHI = {"one-hitter-lp", "one-hitter-nenmatsu", "one-hitter-survey", "one-hitter-booking"}

FILES = {
    "/index.html": (ROOT / "network" / "demo" / "index.html").read_bytes(),
    # デモなので検索エンジンに載せない
    "/_headers": b"/*\n  X-Robots-Tag: noindex, nofollow\n",
}


def token() -> str:
    t = os.environ.get("NETLIFY_TOKEN", "").strip()
    if not t:
        p = pathlib.Path(os.path.expanduser("~/.config/one-hitter/netlify-token.txt"))
        t = p.read_text().strip() if p.exists() else ""
    if not t:
        sys.exit("NETLIFY_TOKEN がありません")
    return t


def call(method, path, body=None, ctype="application/json"):
    data = body if isinstance(body, (bytes, type(None))) else json.dumps(body).encode()
    req = urllib.request.Request(API + path, data=data, method=method,
                                 headers={"Authorization": "Bearer " + token(), "Content-Type": ctype})
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        sys.exit(f"{method} {path} → {e.code} {e.read().decode(errors='replace')[:300]}")


def main():
    assert SITE_NAME not in KINSHI
    html = FILES["/index.html"].decode("utf-8")
    for w in ["ワンヒッター", "本舗", "ベアーズ", "石田", "木村", "和真", "網"]:
        if w in html:
            sys.exit(f"公開版に「{w}」が入っています。止めました")
    sites = call("GET", "/sites?per_page=100&name=" + SITE_NAME)
    site = next((s for s in sites if s["name"] == SITE_NAME), None)
    if not site:
        site = call("POST", f"/{TEAM_SLUG}/sites", {"name": SITE_NAME})
        print("サイトを作成:", site["name"])
    if site["name"] in KINSHI:
        sys.exit("LPのサイトには配信しません")
    sha = {p: hashlib.sha1(b).hexdigest() for p, b in FILES.items()}
    dep = call("POST", f"/sites/{site['id']}/deploys", {"files": sha})
    need = set(dep.get("required", []))
    for p in [p for p, h in sha.items() if h in need]:
        call("PUT", f"/deploys/{dep['id']}/files{p}", FILES[p], "application/octet-stream")
        print("アップロード:", p)
    print("配信:", dep["id"])
    print("URL:", site.get("ssl_url") or site.get("url"))


if __name__ == "__main__":
    main()
