#!/usr/bin/env python3
"""deploy/netlify/ の中身を Netlify へ配信する。

トークンは環境変数 NETLIFY_TOKEN から読む。引数にも設定ファイルにも書かない
（履歴やリポジトリに残さないため）。

  NETLIFY_TOKEN=nfp_xxx python3 tools/deploy-netlify.py --create      # 初回：サイトを作って配信
  NETLIFY_TOKEN=nfp_xxx python3 tools/deploy-netlify.py               # 2回目以降：配信のみ
  NETLIFY_TOKEN=nfp_xxx python3 tools/deploy-netlify.py --notify a@b  # フォーム通知の宛先を追加

Netlify の配信は「送るファイルのSHA1を先に申告し、向こうが持っていない分だけ
アップロードする」方式なので、2回目以降は差分だけが飛ぶ。
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
SRC = ROOT / "deploy" / "netlify"
STATE = ROOT / "deploy" / ".netlify-site.json"
API = "https://api.netlify.com/api/v1"

SITE_NAME = "one-hitter-lp"


def token() -> str:
    t = os.environ.get("NETLIFY_TOKEN", "").strip()
    if not t:
        sys.exit("NETLIFY_TOKEN が設定されていません。")
    return t


def call(method: str, path: str, body=None, raw: bytes | None = None,
         content_type: str = "application/json"):
    url = path if path.startswith("http") else API + path
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer " + token())
    if data is not None:
        req.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            payload = r.read()
            return json.loads(payload) if payload else None
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:400]
        sys.exit(f"Netlify APIエラー {e.code} {method} {url}\n{detail}")


def collect() -> dict[str, tuple[pathlib.Path, str]]:
    """配信するファイルを {'/aircon/index.html': (path, sha1)} の形で集める。"""
    files = {}
    for p in sorted(SRC.rglob("*")):
        if p.is_dir():
            continue
        rel = "/" + p.relative_to(SRC).as_posix()
        files[rel] = (p, hashlib.sha1(p.read_bytes()).hexdigest())
    return files


def load_site_id() -> str | None:
    if STATE.exists():
        return json.loads(STATE.read_text())["site_id"]
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--create", action="store_true", help="サイトを新規作成する")
    ap.add_argument("--notify", action="append", default=[],
                    help="フォーム送信の通知先メールアドレス（複数可）")
    args = ap.parse_args()

    if not SRC.exists():
        sys.exit(f"{SRC} がありません。先に python3 tools/build-site.py netlify を実行してください。")

    site_id = load_site_id()
    if args.create or not site_id:
        site = call("POST", "/sites", {"name": SITE_NAME})
        site_id = site["id"]
        STATE.write_text(json.dumps({"site_id": site_id, "name": site["name"],
                                     "url": site["ssl_url"] or site["url"]}, indent=2) + "\n")
        print(f"サイトを作成： {site['ssl_url'] or site['url']}")

    files = collect()
    print(f"配信対象 {len(files)} ファイル")

    deploy = call("POST", f"/sites/{site_id}/deploys",
                  {"files": {k: v[1] for k, v in files.items()}})
    required = set(deploy.get("required", []))
    print(f"うちアップロードが必要： {len(required)} ファイル")

    for rel, (path, sha) in files.items():
        if sha not in required:
            continue
        call("PUT", f"/deploys/{deploy['id']}/files{rel}",
             raw=path.read_bytes(), content_type="application/octet-stream")
        print(f"  ↑ {rel}")

    # 配信が終わるまで待つ
    for _ in range(60):
        d = call("GET", f"/deploys/{deploy['id']}")
        if d["state"] in ("ready", "error"):
            break
        time.sleep(3)
    else:
        d = call("GET", f"/deploys/{deploy['id']}")

    print(f"状態: {d['state']}")
    if d["state"] == "error":
        sys.exit(f"配信に失敗しました: {d.get('error_message')}")

    for address in args.notify:
        call("POST", "/hooks", {
            "site_id": site_id,
            "type": "email",
            "event": "submission_created",
            "data": {"email": address},
        })
        print(f"フォーム通知を追加： {address}")

    site = call("GET", f"/sites/{site_id}")
    print("\n公開URL: " + (site["ssl_url"] or site["url"]))
    print("  案A: " + (site["ssl_url"] or site["url"]) + "/aircon/")
    print("  案B: " + (site["ssl_url"] or site["url"]) + "/mizumawari/")


if __name__ == "__main__":
    main()
