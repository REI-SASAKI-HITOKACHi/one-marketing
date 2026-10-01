#!/usr/bin/env python3
"""Googleビジネスプロフィール（GBP）API の薄いクライアント。

資格情報は ~/.config/one-hitter/gbp.json（git の外）から読む。値は絶対に print しない。
  {"client_id": "...", "client_secret": "...", "refresh_token": "...",
   "account": "accounts/NNN", "location": "locations/NNN"}
  client_id / client_secret が無ければ gmail-oauth.json（同じ GCP プロジェクト 844550773178）から借りる。
  account / location は `python3 tools/gbp_client.py locations` で分かる。

  python3 tools/gbp_client.py check       # トークンが取れるか（値は出さない）
  python3 tools/gbp_client.py locations   # アカウントと店舗の名前（account / location の値を知る）

★ 2026-10-01 時点：refresh_token が未取得のため、このファイルの通信部分は**実機で未確認**。
   エンドポイントとフィールド名は Google の公開仕様に基づく。最初の実行は必ず --dry-run か一覧系で。
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

DIR = os.path.expanduser("~/.config/one-hitter")
CONF = os.path.join(DIR, "gbp.json")
FALLBACK_CLIENT = os.path.join(DIR, "gmail-oauth.json")
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/business.manage"
ACCOUNTS = "https://mybusinessaccountmanagement.googleapis.com/v1/accounts"
INFO = "https://mybusinessbusinessinformation.googleapis.com/v1"
V4 = "https://mybusiness.googleapis.com/v4"                       # 投稿・クチコミ
PERF = "https://businessprofileperformance.googleapis.com/v1"     # パフォーマンス


def mask(s: str) -> str:
    """エラー文に混じりうるトークンを消す。"""
    c = conf(strict=False)
    for k in ("client_secret", "refresh_token"):
        v = c.get(k)
        if v:
            s = s.replace(v, "***")
    return s


def conf(strict: bool = True) -> dict:
    c = {}
    if os.path.exists(FALLBACK_CLIENT):
        f = json.load(open(FALLBACK_CLIENT, encoding="utf-8"))
        c.update({k: f[k] for k in ("client_id", "client_secret") if k in f})
    if os.path.exists(CONF):
        c.update(json.load(open(CONF, encoding="utf-8")))
    if strict:
        for k in ("client_id", "client_secret", "refresh_token"):
            if not c.get(k):
                sys.exit(f"{CONF} に {k} がありません（business.manage の refresh_token を取る段取りは docs/gbp-api-自動化の段取り.md）")
    return c


_tok = None


def access_token() -> str:
    global _tok
    if _tok:
        return _tok
    c = conf()
    body = urllib.parse.urlencode({
        "client_id": c["client_id"], "client_secret": c["client_secret"],
        "refresh_token": c["refresh_token"], "grant_type": "refresh_token"}).encode()
    try:
        r = urllib.request.urlopen(urllib.request.Request(TOKEN_URL, data=body), timeout=30)
        _tok = json.load(r)["access_token"]
    except urllib.error.HTTPError as e:
        sys.exit("トークン取得に失敗：" + mask(e.read().decode("utf-8", "replace"))[:300])
    return _tok


class GbpError(Exception):
    def __init__(self, status: int, body: str):
        super().__init__(f"HTTP {status}: {mask(body)[:600]}")
        self.status = status


def call(method: str, url: str, query: dict | None = None, body: dict | None = None) -> dict:
    if query:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(query, doseq=True)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": "Bearer " + access_token(), "Content-Type": "application/json"})
    try:
        return json.load(urllib.request.urlopen(req, timeout=60)) or {}
    except urllib.error.HTTPError as e:
        raise GbpError(e.code, e.read().decode("utf-8", "replace"))


def account_and_location() -> tuple[str, str]:
    c = conf()
    if not (c.get("account") and c.get("location")):
        sys.exit("gbp.json に account / location がありません。python3 tools/gbp_client.py locations で調べて足す")
    return c["account"], c["location"]


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "check":
        access_token()
        print("OK：アクセストークンが取れました（値は出しません）")
    elif cmd == "locations":
        for a in call("GET", ACCOUNTS).get("accounts", []):
            print("アカウント:", a.get("name"), a.get("accountName"))
            r = call("GET", f"{INFO}/{a['name']}/locations", {"readMask": "name,title", "pageSize": 100})
            for loc in r.get("locations", []):
                print("  店舗:", loc.get("name"), loc.get("title"))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
