#!/usr/bin/env python3
"""予約フォーム（onehitter-yoyaku ＝ yoyaku.onehitter.jp）だけを配信する。

★ LPサイト（one-hitter-lp）には絶対に触らない。
  そちらは tools/deploy-netlify.py の担当で、LP概要プレゼンのスレッドが使っている。
  サイトIDを決め打ちにして、取り違えが起きないようにしてある。

送るもの: lp/booking/ の中身（index.html と slots.json）

  python3 tools/deploy-booking.py            # 配信
  python3 tools/deploy-booking.py --dry-run  # 送るファイルの一覧だけ出す
  python3 tools/deploy-booking.py --notify メール  # フォーム通知の宛先を足す
  python3 tools/deploy-booking.py --slots-only  # 控えの slots.json だけ差し替える（毎時点検から。下の slots_only()）
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
SRC_301 = ROOT / "lp" / "booking-redirect"   # 旧ホストへ送る301だけの中身
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
# 旧ホスト（301専用。--old でその301だけを配信する。2026-09-19 オーナーGO）
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


def seiki_sha1(raw: bytes) -> str:
    """Netlify Forms は配信時に <form ... data-netlify="true"> を <form hidden method='post' name='…'> に
    書き換える（2026-09-27 実測。違いはこの1行だけ）。form タグを除いてから比べないと、届いていても毎回不一致になる。"""
    import re
    return hashlib.sha1(re.sub(rb"<form[^>]*>", b"<form>", raw)).hexdigest()


def honban_sha1() -> str:
    """お客様が実際に受け取っているHTMLのsha1（form タグを正規化）。取れなければ空文字。"""
    try:
        with urllib.request.urlopen(KOKYAKU_URL, timeout=30) as r:
            return seiki_sha1(r.read())
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


def slots_only() -> None:
    """本番のファイルはそのまま、slots.json だけを手元のものに差し替える（2026-10-09）。

    毎時点検（tools/slots-from-api.py --deploy）から呼ばれる、空き枠データの差し替えという定常作業。
    手元の index.html は使わない（未配信の変更が手元にあっても、それを一緒に出さないため）。
    本番の各ファイルは Netlify にある sha をそのまま指定するので、送るのは slots.json の1件だけ。
    """
    p = SRC / "slots.json"
    if not p.exists():
        sys.exit("lp/booking/slots.json がありません。")
    raw = p.read_bytes()
    d = json.loads(raw)
    if not isinstance(d.get("buckets"), dict) or not d.get("generated"):
        sys.exit("slots.json の形が違います（buckets / generated が無い）。配信を中止します。")
    # ページは変えないが、念のため本番のページも点検する（NG なら差し替えない）
    import subprocess
    chk = subprocess.run([sys.executable, str(ROOT / "tools" / "check-public-page.py"), KOKYAKU_URL])
    if chk.returncode != 0:
        sys.exit("check-public-page.py が本番ページで NG。配信を中止します。")

    tok = token()
    sid = site_id(tok)
    genkou = call(tok, "GET", f"/sites/{sid}/files")
    digest = {f["path"]: f["sha"] for f in genkou if f.get("path") and f.get("sha")}
    if "/index.html" not in digest:
        sys.exit(f"本番のファイル一覧に index.html がありません（{sorted(digest)}）。配信を中止します。")
    sha = hashlib.sha1(raw).hexdigest()
    digest["/slots.json"] = sha
    dep = call(tok, "POST", f"/sites/{sid}/deploys", {"files": digest})
    iru = set(dep.get("required") or [])
    print(f"デプロイ {dep['id']}（slots.json だけ差し替え。ほか {len(digest) - 1} 件は本番のまま）")
    if iru - {sha}:
        sys.exit(f"本番にあるはずのファイルを求められました（{len(iru - {sha})}件）。配信を中止します。")
    if sha in iru:
        call(tok, "PUT", f"/deploys/{dep['id']}/files/slots.json", raw=raw,
             ctype="application/octet-stream")
    for _ in range(60):
        st = call(tok, "GET", f"/deploys/{dep['id']}")
        if st["state"] in ("ready", "error"):
            break
        time.sleep(3)
    if st["state"] != "ready":
        sys.exit("配信に失敗しました: " + str(st.get("error_message")))
    for _ in range(10):
        try:
            with urllib.request.urlopen(f"{KOKYAKU_URL}slots.json?t={int(time.time())}", timeout=30) as r:
                if hashlib.sha1(r.read()).hexdigest() == sha:
                    print(f"確認: {KOKYAKU_URL}slots.json が手元と同じになりました（{d.get('generatedLabel')}）")
                    return
        except Exception as e:
            print("  （本番の取得に失敗:", e, "）")
        time.sleep(3)
    sys.exit("配信は ready ですが、本番の slots.json が手元と一致しません。")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--notify", action="append", default=[])
    ap.add_argument("--old", action="store_true",
                    help="旧ホスト one-hitter-booking.netlify.app に301だけを配信する（送信済みSMSのリンク先を新ホストへ寄せる）")
    ap.add_argument("--slots-only", action="store_true",
                    help="本番のファイルはそのまま、slots.json だけを手元のものに差し替える（毎時点検用）")
    a = ap.parse_args()
    if a.slots_only:
        return slots_only()
    global SITE_ID, SITE_NAME, SRC
    if a.old:
        # 旧ホストには予約ページそのものを置かない。置くと、また片方だけ古くなる。
        SITE_ID, SITE_NAME, SRC = OLD_SITE_ID, OLD_SITE_NAME, SRC_301

    if not SRC.exists():
        sys.exit(f"{SRC} がありません。先に python3 tools/build-booking.py を実行してください。")
    files = atsumeru()
    if a.old:
        # 301だけのサイトなので、お客様が読むページは無い。点検の対象も無い。
        if "/_redirects" not in files:
            sys.exit("_redirects がありません。配信を中止します。")
        if "/index.html" in files:
            sys.exit("旧ホストは301専用です。index.html を置かないでください。")
        # Search Console の所有権確認ファイルは、301に食われない実ファイルとして残す
        if "/google1a88c31fe28c2256.html" not in files:
            sys.exit("google1a88c31fe28c2256.html がありません（Search Console の所有権）。配信を中止します。")
    else:
        # 2026-09-12 事故の再発防止：お客様が開くページは配信前に必ず点検する（NG なら配信しない）
        import subprocess
        chk = subprocess.run([sys.executable, str(ROOT / "tools" / "check-public-page.py"), str(SRC / "index.html")])
        if chk.returncode != 0:
            sys.exit("check-public-page.py が NG。配信を中止します。")
        if "/index.html" not in files:
            sys.exit("index.html がありません。配信を中止します。")
        if "/slots.json" not in files:
            sys.exit("slots.json がありません。先に python3 tools/build-slots.py を実行してください。")

    print(f"配信先: {SITE_NAME} → {'（301専用の旧ホスト）' if a.old else KOKYAKU_URL}")
    for rel, p in files.items():
        print(f"  {rel:<18} {p.stat().st_size:>8,} bytes")
    if a.dry_run:
        print("\n--dry-run のため配信していません。")
        return

    tok = token()
    # 旧ホストは301専用で yoyaku.onehitter.jp が付いていないので、名前引き＋ドメイン確認は現行サイトだけ
    sid = OLD_SITE_ID if a.old else site_id(tok)
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
    machi = seiki_sha1(files["/index.html"].read_bytes()) if not a.old else None
    for _ in range(10 if machi else 0):
        if honban_sha1() == machi:
            print(f"確認: {KOKYAKU_URL} が手元と同じ内容になりました。")
            break
        time.sleep(3)
    else:
        if machi:
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
