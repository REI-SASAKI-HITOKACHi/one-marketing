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
# 既存のプロジェクトと混ざらないよう、チームを明示して作る
TEAM_SLUG = "case-foot-kid"


TOKEN_KITEI = os.path.expanduser("~/.config/one-hitter/netlify-token.txt")


# アフィリエイトに登録済みのURL。オーナーが広告側に設定しているので、
# **これらのパスは変えない。** ディレクトリ名を変える、PAGES から外す、
# 別ブランチから不足した状態で配信する — いずれもURLを死なせる。
# 配信前にここで止める。変更が必要になったときは、先にオーナーへ
# アフィリエイト設定の変更を依頼すること。
KOTEI_URL = [
    "aircon/index.html",        # エアコン パターンA
    "aircon-b/index.html",      # エアコン パターンB（A/B対抗案）
    "mizumawari/index.html",    # 水まわりセット
    "nenmatsu/index.html",      # 年末大掃除
    "survey/index.html",        # ご利用後アンケート
]


def kotei_url_check(files: dict) -> None:
    """登録済みURLが配信物から消えていないか確かめる。

    Netlifyの配信はサイト全体のファイル一覧を差し替える方式なので、
    手元のビルドに無いページは本番から消える。実際、CMO戦略ブランチと
    交互に配信していたときに年末LPが404になっていた（2026-09-06）。
    """
    nai = [u for u in KOTEI_URL if "/" + u not in files]
    if not nai:
        return
    print("\n配信を中止しました。登録済みのURLが配信物にありません。\n")
    for u in nai:
        print(f"  欠落: /{u.rsplit('/', 1)[0]}/")
    print(
        "\nこのまま配信すると、上のページが本番から消えます。\n"
        "  - ブランチが古い、または統合できていない可能性があります\n"
        "  - 意図してURLを変える場合は、先にオーナーへ\n"
        "    アフィリエイト設定の変更を依頼してから KOTEI_URL を直してください\n"
    )
    sys.exit(1)


def token() -> str:
    """トークンはこの順で読む。コマンドラインには書かない。
      1. 環境変数 NETLIFY_TOKEN
      2. 環境変数 NETLIFY_TOKEN_FILE で指定したパス
      3. ~/.config/one-hitter/netlify-token.txt
    """
    t = os.environ.get("NETLIFY_TOKEN", "").strip()
    if t:
        return t
    path = os.environ.get("NETLIFY_TOKEN_FILE", "").strip() or TOKEN_KITEI
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            t = f.read().strip()
    if not t:
        sys.exit(
            "Netlifyトークンが見つかりません。\n"
            f"  環境変数 NETLIFY_TOKEN に入れるか、{TOKEN_KITEI} に置いてください。"
        )
    return t


def kenshou(base_url: str, paths=("/",)) -> int:
    """配信後の検証。200が返るだけでは足りない。
    HTMLとして解釈される Content-Type になっているかまで見る。
    ステータスだけ見て済ませたせいで、アンケートが text/plain で配信され、
    お客様の画面にHTMLのソースがそのまま出ていた（2026-09-08）。
    """
    import urllib.error

    ng = 0
    for p in paths:
        url = base_url.rstrip("/") + p
        req = urllib.request.Request(url, method="GET",
                                     headers={"User-Agent": "one-hitter-deploy-check"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                code = r.status
                ctype = r.headers.get("Content-Type", "")
                body = r.read(200)
        except urllib.error.HTTPError as e:
            code, ctype, body = e.code, e.headers.get("Content-Type", ""), b""
        except Exception as e:
            print(f"  ！ {url} 取得できず: {e}")
            ng += 1
            continue

        ok_code = code == 200
        ok_type = "text/html" in ctype.lower()
        ok_body = body.lstrip()[:15].lower().startswith(b"<!doctype") or b"<html" in body.lower()
        mark = "OK" if (ok_code and ok_type and ok_body) else "★NG"
        print(f"  {mark} {url}")
        print(f"       status={code} content-type={ctype or '(なし)'}")
        if not ok_type:
            print("       → HTMLとして配信されていない。ブラウザにソースがそのまま出る")
        if not ok_body:
            print("       → 先頭がHTMLに見えない")
        if not (ok_code and ok_type and ok_body):
            ng += 1
    return ng


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


def save_state(site: dict) -> None:
    STATE.write_text(json.dumps({"site_id": site["id"], "name": site["name"],
                                 "url": site["ssl_url"] or site["url"]}, indent=2) + "\n")


def find_existing_site() -> dict | None:
    """チームの中から、名前が一致する既存サイトを探す。

    状態ファイル（deploy/.netlify-site.json）はリポジトリに入れていないので、
    別のパソコンや作り直した作業環境には存在しない。それを「サイトがまだ無い」と
    取り違えて新しいサイトを作ってしまうと、公開URLが変わってしまう。
    無ければ作る前に、まず名前で探す。
    """
    for site in (call("GET", f"/{TEAM_SLUG}/sites") or []):
        if site["name"] == SITE_NAME:
            return site
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--create", action="store_true", help="サイトを新規作成する")
    ap.add_argument("--notify", action="append", default=[],
                    help="フォーム送信の通知先メールアドレス（複数可）")
    args = ap.parse_args()

    if not SRC.exists():
        sys.exit(f"{SRC} がありません。先に python3 tools/build-site.py netlify を実行してください。")

    if args.create:
        existing = call("GET", f"/{TEAM_SLUG}/sites") or []
        print("チーム内の既存プロジェクト（いずれにも手を触れません）:")
        for site in existing:
            print(f"  - {site['name']}")
        if any(site["name"] == SITE_NAME for site in existing):
            sys.exit(f"{SITE_NAME} は既にあります。--create を外して実行してください。")

    site_id = load_site_id()

    if not site_id:
        # 状態ファイルが無い。作る前に、同じ名前のサイトが既にないか確かめる。
        found = find_existing_site()
        if found:
            save_state(found)
            site_id = found["id"]
            print(f"既存のプロジェクトを見つけました： {found['ssl_url'] or found['url']}")
            print("  （新しいサイトは作りません。状態ファイルを復元しました）")

    if args.create or not site_id:
        if find_existing_site():
            sys.exit(f"{SITE_NAME} は既にあります。--create を外して実行してください。")
        site = call("POST", f"/{TEAM_SLUG}/sites", {"name": SITE_NAME})
        site_id = site["id"]
        save_state(site)
        print(f"サイトを作成： {site['ssl_url'] or site['url']}")

    files = collect()
    print(f"配信対象 {len(files)} ファイル")
    kotei_url_check(files)

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
    base = site["ssl_url"] or site["url"]
    print("\n公開URL: " + base)

    # ★配信したら必ず中身を見る。200が返るだけでは足りない。
    print("\n配信後の検証")
    time.sleep(4)
    paths = sorted({"/" + str(pathlib.PurePosixPath(f).parent) + "/"
                    if str(pathlib.PurePosixPath(f).parent) != "." else "/"
                    for f in files if f.endswith(".html")})
    ng = kenshou(base, tuple(paths))
    if ng:
        sys.exit(f"\n★ {ng} 件が正しく配信されていません。上の内容を確認してください。")
    print("  すべてHTMLとして配信されています。")


if __name__ == "__main__":
    main()
