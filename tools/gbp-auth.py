#!/usr/bin/env python3
"""business.manage の refresh_token を1回だけ取り、~/.config/one-hitter/gbp.json に書く。

オーナーの操作は、ブラウザに出る Google の「許可」を1回押すだけ（case.foot.kid でログイン）。
  python3 tools/gbp-auth.py            # URL を表示 → 許可 → 自動で受け取って保存
トークンの値は画面にも掲示板にも出さない。保存先は git の外。
前提：OAuth クライアントがデスクトップ型（またはループバックの redirect が許可済み）であること。
      同意画面が「テスト」のままだと refresh_token は7日で切れる（公開状態にするか、週1で取り直す）。
★ 2026-10-01 時点で未実行。
"""
import http.server
import json
import os
import sys
import urllib.parse
import urllib.request
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gbp_client as g  # noqa: E402

PORT = 8765


def main() -> None:
    c = g.conf(strict=False)
    if not (c.get("client_id") and c.get("client_secret")):
        sys.exit("client_id / client_secret がありません")
    redirect = f"http://127.0.0.1:{PORT}/"
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": c["client_id"], "redirect_uri": redirect, "response_type": "code",
        "scope": g.SCOPE, "access_type": "offline", "prompt": "consent"})
    got = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            got.update(urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query))
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("許可を受け取りました。このタブは閉じてください。".encode())

        def log_message(self, *a):
            pass

    print("次のURLをブラウザで開いて「許可」を押す：\n", url)
    try:
        webbrowser.open(url)
    except Exception:
        pass
    srv = http.server.HTTPServer(("127.0.0.1", PORT), H)
    while "code" not in got and "error" not in got:
        srv.handle_request()
    if "error" in got:
        sys.exit("許可されませんでした：" + got["error"][0])
    body = urllib.parse.urlencode({
        "code": got["code"][0], "client_id": c["client_id"], "client_secret": c["client_secret"],
        "redirect_uri": redirect, "grant_type": "authorization_code"}).encode()
    r = json.load(urllib.request.urlopen(urllib.request.Request(g.TOKEN_URL, data=body), timeout=30))
    if "refresh_token" not in r:
        sys.exit("refresh_token が返りませんでした（過去に許可済みなら、Googleアカウントのアクセス権から外して再実行）")
    cur = json.load(open(g.CONF)) if os.path.exists(g.CONF) else {}
    cur["refresh_token"] = r["refresh_token"]
    os.makedirs(g.DIR, exist_ok=True)
    fd = os.open(g.CONF, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(cur, f)
    print("保存しました（値は出しません）。次：python3 tools/gbp_client.py locations")


if __name__ == "__main__":
    main()
