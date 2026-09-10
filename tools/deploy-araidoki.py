#!/usr/bin/env python3
"""「洗いどき」（lp/media/araidoki/）だけを、専用のNetlifyサイトへ配信する。

★ LPサイト（one-hitter-lp）・予約フォーム（one-hitter-booking）・アンケート（one-hitter-survey）には
  絶対に触らない。それぞれ別スレッドの持ち物で、過去に取り違えの事故が起きている。
  このスクリプトは deploy/.netlify-araidoki.json に記録した自分のサイトIDにしか送らない。

  python3 tools/deploy-araidoki.py --create   # 初回：サイトを作って配信（サイト名 araidoki-xxxx）
  python3 tools/deploy-araidoki.py            # 2回目以降：配信のみ
  python3 tools/deploy-araidoki.py --dry-run  # 送るファイルの一覧だけ
  python3 tools/deploy-araidoki.py --notify メール  # フォーム通知の宛先を足す

トークンは環境変数 NETLIFY_TOKEN か ~/.config/one-hitter/netlify-token.txt から読む。
リポジトリには置かない。
"""
import argparse
import hashlib
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "lp" / "media" / "araidoki"
STATE = ROOT / "deploy" / ".netlify-araidoki.json"
API = "https://api.netlify.com/api/v1"
SITE_NAME = "araidoki"
TOKEN_KITEI = os.path.expanduser("~/.config/one-hitter/netlify-token.txt")

# 試作の間、検索エンジンにも他のサイトにも拾われないようにする
HEADERS = """/*
  X-Robots-Tag: noindex, nofollow
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  X-Frame-Options: SAMEORIGIN

/*.jpg
  Cache-Control: public, max-age=2592000
"""
ROBOTS = "User-agent: *\nDisallow: /\n"


def token() -> str:
    t = os.environ.get("NETLIFY_TOKEN", "").strip()
    if not t and os.path.exists(TOKEN_KITEI):
        t = open(TOKEN_KITEI, encoding="utf-8").read().strip()
    if not t:
        sys.exit(f"Netlifyトークンがありません。{TOKEN_KITEI} に置いてください。")
    return t


def call(tok, method, path, payload=None, raw=None, ctype="application/json"):
    data = raw if raw is not None else (json.dumps(payload).encode() if payload is not None else None)
    req = urllib.request.Request(API + path, data=data, method=method)
    req.add_header("Authorization", "Bearer " + tok)
    if data is not None:
        req.add_header("Content-Type", ctype)
    try:
        with urllib.request.urlopen(req, timeout=120) as res:
            body = res.read()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        sys.exit(f"Netlify {method} {path} が {e.code}: {e.read().decode()[:400]}")


def atsumeru() -> dict:
    files = {}
    for p in sorted(SRC.rglob("*")):
        if p.is_dir() or p.name.startswith("."):
            continue
        files["/" + p.relative_to(SRC).as_posix()] = p.read_bytes()
    files["/_headers"] = HEADERS.encode()
    files["/robots.txt"] = ROBOTS.encode()
    return files


def site_id(tok, create: bool) -> str:
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))["site_id"]
    if not create:
        sys.exit(f"{STATE} がありません。初回は --create を付けてください。")
    s = call(tok, "POST", "/sites", {"name": SITE_NAME})
    # 新しいサイトは ignore_html_forms が true で作られ、Netlify Forms が検出されない。
    # 手配フォームを受け取るために、ここで明示的に有効にする（2026-09-10 に実際に踏んだ）
    call(tok, "PATCH", f"/sites/{s['id']}",
         {"processing_settings": {"html": {"pretty_urls": True}, "ignore_html_forms": False}})
    STATE.write_text(json.dumps({"site_id": s["id"], "name": s["name"], "url": s["ssl_url"]},
                                ensure_ascii=False, indent=2), encoding="utf-8")
    print("サイトを作りました:", s["name"], s["ssl_url"])
    return s["id"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--create", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--notify", action="append", default=[])
    a = ap.parse_args()

    files = atsumeru()
    if "/index.html" not in files:
        sys.exit("index.html がありません。先に python3 tools/build-araidoki.py を実行してください。")
    print(f"送るファイル {len(files)}件（{sum(len(b) for b in files.values()):,} bytes）")
    if a.dry_run:
        for rel in files:
            print(" ", rel)
        return

    tok = token()
    sid = site_id(tok, a.create)
    digest = {rel: hashlib.sha1(b).hexdigest() for rel, b in files.items()}
    dep = call(tok, "POST", f"/sites/{sid}/deploys", {"files": digest})
    iru = set(dep.get("required") or [])
    print(f"デプロイ {dep['id']}／アップロード {len(iru)}件")
    for rel, b in files.items():
        if digest[rel] in iru:
            call(tok, "PUT", f"/deploys/{dep['id']}/files{rel}", raw=b, ctype="application/octet-stream")
    for _ in range(60):
        d = call(tok, "GET", f"/deploys/{dep['id']}")
        if d["state"] in ("ready", "error"):
            break
        time.sleep(3)
    print("状態:", d["state"])
    if d["state"] != "ready":
        sys.exit("配信に失敗しました: " + str(d.get("error_message")))
    url = d.get("ssl_url") or d.get("deploy_ssl_url")
    print("URL :", url)

    # 配信直後の検証：HTML が text/html で返り、noindex が入っているか
    req = urllib.request.Request(url + "/", headers={"User-Agent": "kenshou"})
    with urllib.request.urlopen(req, timeout=30) as r:
        ct = r.headers.get("Content-Type", "")
        body = r.read(4000).decode("utf-8", "replace")
        xr = r.headers.get("X-Robots-Tag", "")
    ok = ct.startswith("text/html") and "noindex" in body and "noindex" in xr
    print("検証:", "OK" if ok else "NG", f"(Content-Type={ct}, X-Robots-Tag={xr})")
    if not ok:
        sys.exit("配信後の検証に失敗しました")

    for mail in a.notify:
        call(tok, "POST", "/hooks", {"site_id": sid, "type": "email", "event": "submission_created",
                                     "data": {"email": mail}})
        print("フォーム通知の宛先を追加:", mail)


if __name__ == "__main__":
    main()
