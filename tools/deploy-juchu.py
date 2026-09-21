#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""社内用ホスト（受注フォーム・作業完了フォーム・SMSツール）を配信する。

★ 社内用ホスト oh-naibu-sms-k7q3x にだけ送る。
  お客様用ホスト（yoyaku / lp / survey …）には**絶対に置かない**。
  2026-09-12 に、社内ツールをお客様用ホストへ同居させてセーフブラウジングに
  フィッシング判定された事故がある（docs/事故報告-2026-09-12-セーフブラウジング.md）。

  python3 tools/deploy-juchu.py --dry-run
  python3 tools/deploy-juchu.py
"""
import hashlib, json, os, pathlib, sys, time, urllib.request, urllib.error

ROOT = pathlib.Path(__file__).resolve().parent.parent
# ★社内ホストは「まるごと」配信する。1つのフォルダだけ送ると、他のページが消える。
#   2026-09-19 に実際に消した：juchu だけ送って、SMSツール（s.html・qr/・robots.txt）が404になった。
#   Netlify の配信は「送ったファイルが全部」なので、同居しているものを必ず一緒に送ること。
SRC_TACHI = [(ROOT / "lp" / "naibu-sms", ""),      # ルートに置く（既存のSMSツール）
             (ROOT / "lp" / "juchu", "/juchu"),     # /juchu/ に置く（受注フォーム）
             (ROOT / "lp" / "kanryo", "/kanryo")]   # /kanryo/ に置く（作業完了フォーム）
API = "https://api.netlify.com/api/v1"
SITE_ID = "f1b64c82-173e-4b1a-9e7f-bf24026fed0e"   # oh-naibu-sms-k7q3x（社内用）
SITE_NAME = "oh-naibu-sms-k7q3x"
TOKEN_KITEI = os.path.expanduser("~/.config/one-hitter/netlify-token.txt")


def token():
    t = os.environ.get("NETLIFY_TOKEN", "").strip()
    if not t and os.path.exists(TOKEN_KITEI):
        t = pathlib.Path(TOKEN_KITEI).read_text(encoding="utf-8").strip()
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
        with urllib.request.urlopen(req, timeout=120) as r:
            b = r.read()
            return json.loads(b) if b else {}
    except urllib.error.HTTPError as e:
        sys.exit(f"Netlify {method} {path} が {e.code}: {e.read().decode()[:400]}")


def main():
    files = {}
    for moto, saki in SRC_TACHI:
        if not moto.exists():
            sys.exit(f"{moto} がありません。")
        for p in sorted(moto.rglob("*")):
            if p.is_file() and not p.name.startswith("."):
                files[saki + "/" + p.relative_to(moto).as_posix()] = p
    if "/juchu/index.html" not in files:
        sys.exit("受注フォームがありません。先に python3 tools/build-juchu.py を実行してください。")
    if "/kanryo/index.html" not in files:
        sys.exit("作業完了フォームがありません。先に python3 tools/build-kanryo.py を実行してください。")
    if "/s.html" not in files:
        sys.exit("SMSツール（s.html）がありません。まるごと配信できないので中止します。")
    print(f"配信先: {SITE_NAME}（社内用・{SITE_ID}）")
    for rel, p in files.items():
        print(f"  {rel:<16} {p.stat().st_size:>8,} bytes")
    if "--dry-run" in sys.argv:
        print("\n--dry-run のため配信していません。")
        return

    tok = token()
    digest = {rel: hashlib.sha1(p.read_bytes()).hexdigest() for rel, p in files.items()}
    dep = call(tok, "POST", f"/sites/{SITE_ID}/deploys", {"files": digest})
    iru = set(dep.get("required") or [])
    print(f"\nデプロイ {dep['id']}／アップロードが要るファイル {len(iru)}件")
    for rel, p in files.items():
        if digest[rel] in iru:
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
    moto = d.get("ssl_url") or d.get("deploy_ssl_url")
    print("受注フォーム  :", moto + "/juchu/")
    print("作業完了フォーム:", moto + "/kanryo/")
    print("SMSツール    :", moto + "/s.html")


if __name__ == "__main__":
    main()
