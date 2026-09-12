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
import re
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


# 年末・アンケート・予約は、独自ドメインが通るまで別サイトに分かれている
# （docs/LP配信のルール.md）。ここから配信するときの、配信元と必須ファイル。
# 1サイトに統合できたら、この表ごと消してよい。
BUNKATSU = {
    # 年末LPの正は one-hitter-lp/nenmatsu/（アフィリエイト登録済み）。
    # この別サイトは中身を持たず、301で寄せるだけにする（オーナー承認 2026-09-11）。
    # 同じページを2サイトに置いていたため、片方だけ配信して金額が食い違った（2026-09-08）。
    "one-hitter-nenmatsu": {"src": None, "hissu": ["/_redirects"],
                            "root": "lp/nenmatsu-redirect"},
    "one-hitter-survey":   {"src": "survey",   "hissu": ["/index.html"]},
    # 予約フォームは lp/booking/ を build-booking.py が直接書き出す
    "one-hitter-booking":  {"src": None,       "hissu": ["/index.html"],
                            "root": "lp/booking"},
}

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

    # ガードがファイルの有無しか見ていなかった。中身が古い状態での上書きは
    # 止められず、実際に src/cid の記録が配信で消えた（計測担当の指摘 2026-09-10）。
    # 出ているはずの目印が配信物に無ければ、古い土台からのビルドとみなして止める。
    MEJIRUSHI = {
        "aircon/index.html":     ['id="h-src"', "color-scheme:light"],
        "aircon-b/index.html":   ['id="h-src"', "color-scheme:light"],
        "mizumawari/index.html": ['id="h-src"', "color-scheme:light", "setKakaku"],
        "nenmatsu/index.html":   ['id="h-src"', "color-scheme:light", "setKakaku"],
    }
    furui = []
    for u, mejirushi in MEJIRUSHI.items():
        ent = files.get("/" + u)
        if not ent:
            continue
        honbun = ent[0].read_text(encoding="utf-8", errors="ignore")
        kake = [m for m in mejirushi if m not in honbun]
        if kake:
            furui.append((u, kake))

    if not nai and not furui:
        return
    print("\n配信を中止しました。\n")
    for u in nai:
        print(f"  欠落: /{u.rsplit('/', 1)[0]}/")
    for u, kake in furui:
        print(f"  中身が古い: /{u.rsplit('/', 1)[0]}/  無い目印: {', '.join(kake)}")
    print(
        "\nこのまま配信すると、欠落したページは本番から消え、\n"
        "古い中身のページは本番を古い状態で上書きします。\n"
        "  - ブランチが古い、または統合できていない可能性があります\n"
        "  - 意図してURLを変える場合は、先にオーナーへ\n"
        "    アフィリエイト設定の変更を依頼してから KOTEI_URL を直してください\n"
    )
    sys.exit(1)


def shoyuken_kakunin(path: pathlib.Path) -> bool:
    """検索エンジンの所有権確認ファイルなら True。

    Search Console の `googlXXXX.html` は、中身が確認用の1行だけの
    「ページではないHTML」で、お客様が開くものではない。
    運営者情報が無いのは当たり前なので、点検の対象から外す。
    （新しいホストを作ったら当日中にSearch Consoleへ登録する決まりなので、
     これを外さないと全サイトの配信が止まる。2026-09-12 に実際に止まった）
    """
    if re.fullmatch(r"google[0-9a-f]{8,}\.html", path.name):
        return True
    honbun = path.read_text(encoding="utf-8", errors="ignore")
    return len(honbun) < 512 and "verification" in honbun.lower()


def koukai_check(files: dict) -> None:
    """お客様が開くページに、運営者情報が入っているかを配信前に見る。

    2026-09-12、予約フォームのホストが Google セーフブラウジングに
    「フィッシング」と判定され、SMSのリンクがChromeで開けなくなった。
    無料ドメイン上で個人情報を入力させるページに運営者情報が無いと誤判定される。
    判定の解除には時間がかかり、その間そのURLは配布できない。

    点検の中身は tools/check-public-page.py が持っている（docs/org/README.md 4.8.2）。
    **手で流すのを忘れても止まるように、配信の経路に直接置いてある。**
    """
    import importlib.util
    tool = ROOT / "tools" / "check-public-page.py"
    if not tool.exists():
        sys.exit("配信を中止しました。tools/check-public-page.py がありません。\n"
                 "  CMOブランチから取り込んでください（docs/org/README.md 4.8.2）。")
    spec = importlib.util.spec_from_file_location("check_public_page", tool)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    warui = []
    for rel, (path, _sha) in sorted(files.items()):
        if not rel.endswith(".html"):
            continue
        if shoyuken_kakunin(path):
            continue
        ng = mod.tenken(str(path))
        if ng:
            warui.append((rel, ng))
    if not warui:
        return
    print("\n配信を中止しました。お客様が開くページに足りないものがあります。\n")
    for rel, ng in warui:
        print(f"  {rel}")
        for x in ng:
            print(f"      - {x}")
    print("\nこのまま出すと、フィッシングと誤判定されてURLごと配布できなくなります。\n"
          "  運営者情報（会社名・所在地・電話・個人情報の取扱いへのリンク）を足してから配信してください。\n")
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


def collect(src: pathlib.Path | None = None) -> dict[str, tuple[pathlib.Path, str]]:
    """配信するファイルを {'/aircon/index.html': (path, sha1)} の形で集める。"""
    src = src or SRC
    files = {}
    for p in sorted(src.rglob("*")):
        if p.is_dir():
            continue
        rel = "/" + p.relative_to(src).as_posix()
        files[rel] = (p, hashlib.sha1(p.read_bytes()).hexdigest())
    return files


def load_site_id() -> str | None:
    if STATE.exists():
        return json.loads(STATE.read_text())["site_id"]
    return None


def save_state(site: dict) -> None:
    STATE.write_text(json.dumps({"site_id": site["id"], "name": site["name"],
                                 "url": site["ssl_url"] or site["url"]}, indent=2) + "\n")


def find_existing_site(name: str = SITE_NAME) -> dict | None:
    """チームの中から、名前が一致する既存サイトを探す。

    状態ファイル（deploy/.netlify-site.json）はリポジトリに入れていないので、
    別のパソコンや作り直した作業環境には存在しない。それを「サイトがまだ無い」と
    取り違えて新しいサイトを作ってしまうと、公開URLが変わってしまう。
    無ければ作る前に、まず名前で探す。
    """
    for site in (call("GET", f"/{TEAM_SLUG}/sites") or []):
        if site["name"] == name:
            return site
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--create", action="store_true", help="サイトを新規作成する")
    ap.add_argument("--notify", action="append", default=[],
                    help="フォーム送信の通知先メールアドレス（複数可）")
    ap.add_argument("--site", default=SITE_NAME,
                    help="配信先のNetlifyサイト名。既定は " + SITE_NAME
                         + "。分割サイト： " + " / ".join(BUNKATSU))
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

    bunkatsu = BUNKATSU.get(args.site)
    if args.site != SITE_NAME and not bunkatsu:
        sys.exit(f"知らないサイトです： {args.site}")

    if bunkatsu:
        # 分割サイトは、そのページのディレクトリをサイトの直下として配信する
        src = (ROOT / bunkatsu["root"]) if bunkatsu.get("root") else (SRC / bunkatsu["src"])
        if not src.exists():
            sys.exit(f"{src} がありません。先に build-site.py を実行してください。")
        files = collect(src)
        nai = [u for u in bunkatsu["hissu"] if u not in files]
        if nai:
            sys.exit(f"配信を中止しました。{args.site} に必要なファイルがありません： {nai}")
        site = find_existing_site(args.site)
        if not site:
            sys.exit(f"{args.site} が見つかりません。手で作られたサイトのはずです。")
        return haishin(site["id"], files, site.get("ssl_url") or site.get("url"), args)

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
    return haishin(site_id, files, None, args)


def haishin(site_id: str, files: dict, base: str | None, args) -> None:
    """集めたファイルをそのサイトへ配信し、配信後に中身まで確かめる。"""
    # 分割サイトも本サイトも必ずここを通るので、点検はこの1箇所に置く
    koukai_check(files)
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
