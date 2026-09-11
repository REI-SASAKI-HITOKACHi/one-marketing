#!/usr/bin/env python3
"""lp/media/ 配下の小さなサイト（無料点検・読本）を、それぞれ専用のNetlifyサイトへ配信する。

★ LPサイト（one-hitter-lp）・予約フォーム（one-hitter-booking）・アンケート（one-hitter-survey）には
  絶対に触らない。それぞれ別スレッドの持ち物。このスクリプトは deploy/.netlify-<site>.json に
  記録した自分のサイトIDにしか送らない（tools/deploy-araidoki.py と同じ考え方）。

★ 配信＝「外に出す」なのでオーナー承認が要る。承認前は --dry-run だけ。

  python3 tools/deploy-media.py --site tenken --create     # 初回：サイトを作って配信
  python3 tools/deploy-media.py --site tenken              # 2回目以降
  python3 tools/deploy-media.py --site tenken --extra dist/tenken/houkoku:/h   # 報告書ページを /h/ に同梱
  python3 tools/deploy-media.py --site dokuhon --dry-run
  python3 tools/deploy-media.py --site dokuhon --notify メール   # フォーム通知の宛先を足す

トークンは環境変数 NETLIFY_TOKEN か ~/.config/one-hitter/netlify-token.txt。リポジトリには置かない。
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
API = "https://api.netlify.com/api/v1"
TOKEN_KITEI = os.path.expanduser("~/.config/one-hitter/netlify-token.txt")
SITES = {
    "tenken": {"src": ROOT / "lp" / "media" / "tenken", "name": "one-hitter-tenken", "build": "tools/build-tenken.py"},
    "dokuhon": {"src": ROOT / "lp" / "media" / "dokuhon", "name": "one-hitter-dokuhon", "build": "tools/build-dokuhon.py"},
}
HEADERS = """/*
  X-Robots-Tag: noindex, nofollow
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  X-Frame-Options: SAMEORIGIN

/photos/*
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


def atsumeru(src: pathlib.Path, extras: list) -> dict:
    files = {}
    for p in sorted(src.rglob("*")):
        if p.is_dir() or p.name.startswith("."):
            continue
        files["/" + p.relative_to(src).as_posix()] = p.read_bytes()
    for ex in extras:
        d, _, prefix = ex.partition(":")
        d = ROOT / d
        if not d.exists():
            print("（同梱なし）", d)
            continue
        for p in sorted(d.rglob("*")):
            if p.is_file() and not p.name.startswith("."):
                files[prefix.rstrip("/") + "/" + p.relative_to(d).as_posix()] = p.read_bytes()
    files["/_headers"] = HEADERS.encode()
    files["/robots.txt"] = ROBOTS.encode()
    return files


def site_id(tok, state: pathlib.Path, name: str, create: bool) -> str:
    if state.exists():
        return json.loads(state.read_text(encoding="utf-8"))["site_id"]
    if not create:
        sys.exit(f"{state} がありません。初回は --create を付けてください。")
    s = call(tok, "POST", "/sites", {"name": name})
    # 新しいサイトは ignore_html_forms が true で作られ、Netlify Forms が検出されない（2026-09-10 に踏んだ）
    call(tok, "PATCH", f"/sites/{s['id']}", {"processing_settings": {"html": {"pretty_urls": True}, "ignore_html_forms": False}})
    state.write_text(json.dumps({"site_id": s["id"], "name": s["name"], "url": s["ssl_url"]}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("サイトを作りました:", s["name"], s["ssl_url"])
    return s["id"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", required=True, choices=sorted(SITES))
    ap.add_argument("--create", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--extra", action="append", default=[], help="同梱する外部ディレクトリ 例: dist/tenken/houkoku:/h")
    ap.add_argument("--notify", action="append", default=[])
    a = ap.parse_args()
    cfg = SITES[a.site]
    state = ROOT / "deploy" / f".netlify-{a.site}.json"

    files = atsumeru(cfg["src"], a.extra)
    if "/index.html" not in files:
        sys.exit(f"index.html がありません。先に python3 {cfg['build']} を実行してください。")
    print(f"[{a.site}] 送るファイル {len(files)}件（{sum(len(b) for b in files.values()):,} bytes）")
    if a.dry_run:
        for rel in files:
            print(" ", rel)
        return

    tok = token()
    sid = site_id(tok, state, cfg["name"], a.create)
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
        call(tok, "POST", "/hooks", {"site_id": sid, "type": "email", "event": "submission_created", "data": {"email": mail}})
        print("フォーム通知の宛先を追加:", mail)


if __name__ == "__main__":
    main()
