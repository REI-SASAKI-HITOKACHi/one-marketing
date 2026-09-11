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


class GraphError(Exception):
    """Graph API がエラーを返したとき。文面からトークンは消してある。

    再試行の判断に使えるよう、HTTPステータスと Graph のエラーコード（code / error_subcode）を持つ。
    """

    def __init__(self, method: str, path: str, status: int, body: str):
        self.method, self.path, self.status = method, path, status
        self.code = self.subcode = None
        self.is_transient = False
        try:
            err = json.loads(body).get("error", {})
            self.code, self.subcode = err.get("code"), err.get("error_subcode")
            self.is_transient = bool(err.get("is_transient"))
        except Exception:
            pass
        super().__init__(f"Graph API {method} {path} が {status}: {body[:500]}")

    def retryable(self) -> bool:
        """5xx・レート制限（code 4 / 17 / 32 / 613、HTTP 429）・is_transient は待って再試行する価値がある。"""
        return self.status >= 500 or self.status == 429 or self.is_transient or self.code in (1, 2, 4, 17, 32, 613)


_MASK: list[str] = []  # 出力から消す秘密（トークン）。ページトークンも register_secret で足す


def register_secret(s: str | None) -> None:
    if s and s not in _MASK:
        _MASK.append(s)


def mask(text: str) -> str:
    """エラー文・ログに載せる前に必ず通す。トークンが混ざっていても *** になる。"""
    for s in _MASK:
        text = text.replace(s, "***")
    return text


def request(path: str, params: dict | None = None, method: str = "GET", data: dict | None = None,
            token: str | None = None, timeout: int = 60) -> dict:
    """Graph API を1回呼ぶ。失敗は GraphError（トークンは伏せ済み）で返し、呼び出し側が再試行を決める。

    token を渡すとそれを使う（Facebookページへの投稿はページトークンが要るため）。
    渡さなければ meta.json のユーザー／システムユーザートークン。
    """
    c = conf()
    register_secret(c["access_token"])
    register_secret(token)
    base = f"https://graph.facebook.com/{c.get('api_version', 'v21.0')}/{path.lstrip('/')}"
    params = dict(params or {})
    params["access_token"] = token or c["access_token"]
    if method == "GET":
        url = base + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url)
    else:
        body = dict(data or {})
        body.update(params)
        req = urllib.request.Request(base, data=urllib.parse.urlencode(body).encode(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise GraphError(method, path, e.code, mask(e.read().decode(errors="replace"))) from None
    except urllib.error.URLError as e:
        # ネットワーク断は 5xx 相当として扱い、再試行の対象にする
        raise GraphError(method, path, 599, mask(str(e.reason))) from None


def call(path: str, params: dict | None = None, method: str = "GET", data: dict | None = None, files: dict | None = None) -> dict:
    """request() の薄い皮。失敗したらその場で終了する（check など一発ものの用途）。"""
    try:
        return request(path, params, method, data)
    except GraphError as e:
        raise SystemExit(str(e))


def page_token(page_id: str | None = None, cache: str = os.path.expanduser("~/.config/one-hitter/meta-page.json")) -> str:
    """Facebookページ投稿用のページアクセストークンを /me/accounts から取る。

    リポジトリには一切書かない。~/.config/one-hitter/meta-page.json（git の外）に控えを置き、
    2回目以降はそこから読む。無効になっていたら（GraphError 190）呼び出し側が cache を消して取り直す。
    """
    c = conf()
    page_id = page_id or c["page_id"]
    if os.path.exists(cache):
        try:
            d = json.load(open(cache, encoding="utf-8"))
            if d.get("page_id") == page_id and d.get("access_token"):
                register_secret(d["access_token"])
                return d["access_token"]
        except Exception:
            pass
    acc = request("me/accounts", {"fields": "id,name,access_token"})
    for a in acc.get("data", []):
        if str(a.get("id")) == str(page_id):
            tok = a["access_token"]
            register_secret(tok)
            os.makedirs(os.path.dirname(cache), exist_ok=True)
            with open(cache, "w", encoding="utf-8") as f:
                json.dump({"page_id": page_id, "name": a.get("name"), "access_token": tok}, f, ensure_ascii=False)
            os.chmod(cache, 0o600)
            return tok
    raise GraphError("GET", "me/accounts", 404, f"page_id {page_id} が /me/accounts に見つかりません")


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
