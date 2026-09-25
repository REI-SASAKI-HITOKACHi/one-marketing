#!/usr/bin/env python3
"""予約フォーム（onehitter-yoyaku ＝ yoyaku.onehitter.jp）だけを配信する。

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

# 予約フォームのサイト。
#
# ⚠ 2026-09-23 の事故：ここが "one-hitter-booking"（ID 83984fb0-…）だったため、
#   配信は成功したのに**お客様には1文字も届いていなかった。**
#   お客様が見る https://yoyaku.onehitter.jp/ を配信しているのは onehitter-yoyaku で、
#   one-hitter-booking のほうは yoyaku.onehitter.jp へ301するだけの抜け殻。
#   （経緯は docs/ドメイン設計-onehitter.jp.md「予約フォームのサイトが2つあります」）
#
# サイトIDは決め打ちにせず、名前から引く。引いたあとで
# カスタムドメインが KOKYAKU_HOST であることを必ず確かめる（取り違え防止）。
SITE_NAME = "onehitter-yoyaku"
KOKYAKU_HOST = "yoyaku.onehitter.jp"
KOKYAKU_URL = "https://yoyaku.onehitter.jp/"
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


def site_id(tok: str) -> str:
    """名前からサイトIDを引き、お客様のドメインが付いていることを確かめる。"""
    s = call(tok, "GET", f"/sites/{SITE_NAME}.netlify.app")
    domains = [s.get("custom_domain")] + list(s.get("domain_aliases") or [])
    if KOKYAKU_HOST not in domains:
        sys.exit(
            f"{SITE_NAME} に {KOKYAKU_HOST} が付いていません（付いているのは {domains}）。\n"
            "お客様が見ているサイトが変わった可能性があります。配信を中止します。"
        )
    return s["id"]


def honban_sha1() -> str:
    """お客様が実際に受け取っているHTMLのsha1。取れなければ空文字。"""
    try:
        with urllib.request.urlopen(KOKYAKU_URL, timeout=30) as r:
            return hashlib.sha1(r.read()).hexdigest()
    except Exception as e:  # 確認に失敗しても配信の成否は変えない
        print("  （本番の取得に失敗:", e, "）")
        return ""


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
    a = ap.parse_args()

    if not SRC.exists():
        sys.exit(f"{SRC} がありません。先に python3 tools/build-booking.py を実行してください。")
    files = atsumeru()
    if "/index.html" not in files:
        sys.exit("index.html がありません。配信を中止します。")
    if "/slots.json" not in files:
        sys.exit("slots.json がありません。先に python3 tools/build-slots.py を実行してください。")

    print(f"配信先: {SITE_NAME} → {KOKYAKU_URL}")
    for rel, p in files.items():
        print(f"  {rel:<18} {p.stat().st_size:>8,} bytes")
    if a.dry_run:
        print("\n--dry-run のため配信していません。")
        return

    tok = token()
    sid = site_id(tok)
    print(f"サイトID: {sid}")
    digest = {rel: hashlib.sha1(p.read_bytes()).hexdigest() for rel, p in files.items()}
    dep = call(tok, "POST", f"/sites/{sid}/deploys", {"files": digest})
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

    # ★ 配信できたか、ではなく「お客様に届いたか」を確かめる。
    #   9/23 はここが無かったので、届いていないのに「配信済み」と報告してしまった。
    machi = hashlib.sha1(files["/index.html"].read_bytes()).hexdigest()
    for _ in range(10):
        if honban_sha1() == machi:
            print(f"確認: {KOKYAKU_URL} が手元と同じ内容になりました。")
            break
        time.sleep(3)
    else:
        sys.exit(
            f"配信は ready ですが、{KOKYAKU_URL} の内容が手元と一致しません。\n"
            "お客様には届いていない可能性があります。配信先を確かめてください。"
        )

    for mail in a.notify:
        call(tok, "POST", f"/hooks", {
            "site_id": sid, "type": "email", "event": "submission_created",
            "data": {"email": mail},
        })
        print("フォーム通知の宛先を追加:", mail)


if __name__ == "__main__":
    main()
