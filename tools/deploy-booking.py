#!/usr/bin/env python3
"""予約フォーム（one-hitter-booking）だけを配信する。

★ LPサイト（one-hitter-lp）には絶対に触らない。
  そちらは tools/deploy-netlify.py の担当で、LP概要プレゼンのスレッドが使っている。
  サイトIDを決め打ちにして、取り違えが起きないようにしてある。

送るもの: lp/booking/ の中身（index.html と slots.json）

  python3 tools/deploy-booking.py            # 配信
  python3 tools/deploy-booking.py --dry-run  # 送るファイルの一覧だけ出す
  python3 tools/deploy-booking.py --notify メール  # フォーム通知の宛先を足す
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
SRC = ROOT / "lp" / "booking"
API = "https://api.netlify.com/api/v1"

# 予約フォームのサイト。ここを書き換えないこと（LPサイトと取り違えないため）
# 2026-09-12：旧ホスト one-hitter-booking.netlify.app が Google セーフブラウジングに
# 「安全でない」と判定された（お客様から Chrome の警告の報告）ため、新ホストへ移した。
# 旧サイトにも同じ内容を配信し続ける（送信済みSMSのリンク先として残す）：--old を付ける。
SITE_ID = "39408b76-e5d0-46f4-bee8-418ef6cfb36a"
SITE_NAME = "onehitter-yoyaku"
OLD_SITE_ID = "83984fb0-5839-421b-bb99-63c8aff47fb9"
OLD_SITE_NAME = "one-hitter-booking"
TOKEN_KITEI = os.path.expanduser("~/.config/one-hitter/netlify-token.txt")


def token() -> str:
    t = os.environ.get("NETLIFY_TOKEN", "").strip()
    if t:
        return t
    if os.path.exists(TOKEN_KITEI):
        with open(TOKEN_KITEI, encoding="utf-8") as f:
            t = f.read().strip()
    if not t:
        sys.exit(f"Netlifyトークンがありません。{TOKEN_KITEI} に置いてください。")
    return t


def call(tok, method, path, payload=None, raw=None, ctype="application/json"):
    url = API + path
    data = raw if raw is not None else (
        json.dumps(payload).encode() if payload is not None else None)
    req = urllib.request.Request(url, data=data, method=method)
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
        rel = "/" + p.relative_to(SRC).as_posix()
        files[rel] = p
    return files


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--notify", action="append", default=[])
    ap.add_argument("--old", action="store_true",
                    help="旧ホスト one-hitter-booking.netlify.app にも同じ内容を配信する（送信済みSMSのリンク先）")
    a = ap.parse_args()
    global SITE_ID, SITE_NAME
    if a.old:
        SITE_ID, SITE_NAME = OLD_SITE_ID, OLD_SITE_NAME

    if not SRC.exists():
        sys.exit(f"{SRC} がありません。先に python3 tools/build-booking.py を実行してください。")
    files = atsumeru()
    if "/index.html" not in files:
        sys.exit("index.html がありません。配信を中止します。")
    if "/slots.json" not in files:
        sys.exit("slots.json がありません。先に python3 tools/build-slots.py を実行してください。")

    print(f"配信先: {SITE_NAME}（{SITE_ID}）")
    for rel, p in files.items():
        print(f"  {rel:<18} {p.stat().st_size:>8,} bytes")
    if a.dry_run:
        print("\n--dry-run のため配信していません。")
        return

    tok = token()
    digest = {rel: hashlib.sha1(p.read_bytes()).hexdigest() for rel, p in files.items()}
    dep = call(tok, "POST", f"/sites/{SITE_ID}/deploys", {"files": digest})
    iru = set(dep.get("required") or [])
    print(f"\nデプロイ {dep['id']}／アップロードが要るファイル {len(iru)}件")

    for rel, p in files.items():
        if digest[rel] not in iru:
            continue
        call(tok, "PUT", f"/deploys/{dep['id']}/files{rel}",
             raw=p.read_bytes(), ctype="application/octet-stream")
        print(f"  送信: {rel}")

    for _ in range(60):
        d = call(tok, "GET", f"/deploys/{dep['id']}")
        if d["state"] in ("ready", "error"):
            break
        time.sleep(3)
    print("状態:", d["state"])
    if d["state"] != "ready":
        sys.exit("配信に失敗しました: " + str(d.get("error_message")))
    print("URL :", d.get("ssl_url") or d.get("deploy_ssl_url"))

    for mail in a.notify:
        call(tok, "POST", f"/hooks", {
            "site_id": SITE_ID, "type": "email", "event": "submission_created",
            "data": {"email": mail},
        })
        print("フォーム通知の宛先を追加:", mail)


if __name__ == "__main__":
    main()
