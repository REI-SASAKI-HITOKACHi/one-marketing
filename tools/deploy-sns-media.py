#!/usr/bin/env python3
"""SNS投稿用の画像・動画を、公開URLの要る Graph API のために専用 Netlify サイトへ置く。

なぜ別サイトか：Instagram / Facebook の Graph API は「公開URL」からしか媒体を取り込めない。
LPサイト（one-hitter-lp）に間借りすると LP担当の持ち物を触ることになるので、
自分の持ち物として `one-hitter-sns-media` を分けた。状態は deploy/.netlify-sns-media.json に記録し、
このスクリプトはそのサイトIDにしか送らない（tools/deploy-media.py と同じ考え方）。

置き場：dist/sns-media/（gitignore 済み）。投稿する「そのままのファイル」を <投稿ID>-<連番>.jpg / .mp4 の名前で置く。
公開URL：https://one-hitter-sns-media.netlify.app/<ファイル名>
noindex（_headers の X-Robots-Tag）と robots.txt で検索には載せない。写真は投稿後に Meta 側へ複製されるので、
ここから消えても既存の投稿は壊れない。

  python3 tools/deploy-sns-media.py --create               # 初回：サイトを作る（中身は空 index のみ）
  python3 tools/deploy-sns-media.py                        # dist/sns-media/ を丸ごと配信
  python3 tools/deploy-sns-media.py --dry-run
  python3 tools/deploy-sns-media.py --test-image assets/photos/IMG_7976.jpg   # 疎通確認：1080px に縮めて配信し 200 を確かめる

他スクリプトからは publish_files([...]) を呼ぶ → {ローカルパス: 公開URL}。
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
SITE_NAME = "one-hitter-sns-media"
STATE = ROOT / "deploy" / ".netlify-sns-media.json"
SRC = ROOT / "dist" / "sns-media"
HEADERS = """/*
  X-Robots-Tag: noindex, nofollow
  X-Content-Type-Options: nosniff
  Cache-Control: public, max-age=86400
"""
ROBOTS = "User-agent: *\nDisallow: /\n"
# index は運営者情報だけの1枚（README 4.8.2：無料ドメインのホストに運営者情報が無いとフィッシングと誤判定される）
INDEX = None  # atsumeru() で media_common から組む
VERIFY = ROOT / "assets" / "site-verification" / "google1a88c31fe28c2256.html"   # Search Console の所有権確認（消さない）
EXT_OK = {".jpg", ".jpeg", ".mp4"}


def index_html() -> str:
    sys.path.insert(0, str(ROOT / "tools"))
    import media_common as C
    return (f'<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="robots" content="noindex,nofollow"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{C.esc(C.UNEI)}｜SNS用の画像置き場</title><body style="font-family:sans-serif;max-width:560px;margin:40px auto;padding:0 20px;line-height:1.8">'
            f'<h1 style="font-size:18px">SNS投稿用の画像置き場</h1><p>ここは {C.esc(C.UNEI)} が Instagram・Facebook に投稿する写真を置いている場所です。お客様向けの内容はありません。</p>'
            f'<p>{C.esc(C.UNEI)}（ハウスクリーニング）<br>{C.esc(C.UNEI_ADDR)}<br>電話 {C.esc(C.UNEI_TEL)}</p>'
            f'<p><a href="{C.PRIVACY}" rel="noopener">個人情報の取扱い</a></p></body></html>')


def gate(files: dict) -> None:
    """配信前の点検（README 4.8.2）。HTML を tools/check-public-page.py に通し、NG があれば配信しない。"""
    sys.path.insert(0, str(ROOT / "tools"))
    import importlib
    cp = importlib.import_module("check-public-page")
    for rel, b in files.items():
        if rel.endswith(".html") and rel != "/" + VERIFY.name:
            ng = cp.tenken_html(b.decode("utf-8", "ignore"))
            if ng:
                raise RuntimeError(f"配信前の点検で NG：{rel}：{'／'.join(ng)}")


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
        raise RuntimeError(f"Netlify {method} {path} が {e.code}: {e.read().decode()[:400]}") from None


def state() -> dict | None:
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else None


def base_url() -> str:
    """公開URLの土台。サイト作成前でも名前から決まるので dry-run で使える。"""
    s = state()
    return (s["url"] if s else f"https://{SITE_NAME}.netlify.app").rstrip("/")


def public_url(path) -> str:
    return base_url() + "/" + pathlib.Path(path).name


def atsumeru(only: set | None = None) -> dict:
    """dist/sns-media/ 直下の jpg/mp4 をすべて集める（サブディレクトリは見ない。名前が衝突しないように平らに置く）。

    only を渡すとその名前のファイルだけにする（疎通確認で、まだ投稿日が来ていない写真まで公開しないため）。
    Netlify のデプロイはサイト全体の写しなので、only で配信すると他のファイルはサイトから消える。
    投稿本番は only 無し（全部）で配信する。
    """
    files = {}
    if SRC.exists():
        for p in sorted(SRC.iterdir()):
            if p.is_file() and not p.name.startswith(".") and p.suffix.lower() in EXT_OK and (only is None or p.name in only):
                files["/" + p.name] = p.read_bytes()
    files["/_headers"] = HEADERS.encode()
    files["/robots.txt"] = ROBOTS.encode()
    files["/index.html"] = index_html().encode()
    files["/" + VERIFY.name] = VERIFY.read_bytes()
    gate(files)
    return files


def site_id(tok, create: bool) -> str:
    s = state()
    if s:
        return s["site_id"]
    if not create:
        sys.exit(f"{STATE} がありません。初回は --create を付けてください。")
    r = call(tok, "POST", "/sites", {"name": SITE_NAME})
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps({"site_id": r["id"], "name": r["name"], "url": r["ssl_url"]}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("サイトを作りました:", r["name"], r["ssl_url"])
    return r["id"]


def deploy(create: bool = False, quiet: bool = False, only: set | None = None) -> str:
    """dist/sns-media/ を丸ごと配信して、配信URLを返す。差分（digest）だけアップロードするので毎回軽い。"""
    files = atsumeru(only)
    tok = token()
    sid = site_id(tok, create)
    digest = {rel: hashlib.sha1(b).hexdigest() for rel, b in files.items()}
    dep = call(tok, "POST", f"/sites/{sid}/deploys", {"files": digest})
    iru = set(dep.get("required") or [])
    if not quiet:
        print(f"[sns-media] {len(files)}件（{sum(len(b) for b in files.values()):,} bytes）／アップロード {len(iru)}件／デプロイ {dep['id']}")
    for rel, b in files.items():
        if digest[rel] in iru:
            call(tok, "PUT", f"/deploys/{dep['id']}/files{rel}", raw=b, ctype="application/octet-stream")
    d = dep
    for _ in range(80):
        d = call(tok, "GET", f"/deploys/{dep['id']}")
        if d["state"] in ("ready", "error"):
            break
        time.sleep(3)
    if d["state"] != "ready":
        raise RuntimeError("配信に失敗しました: " + str(d.get("error_message")))
    url = (d.get("ssl_url") or d.get("deploy_ssl_url")).rstrip("/")
    if not quiet:
        print("URL :", url)
    return url


def verify(url: str) -> tuple[int, str]:
    """公開URLが本当に取れるか（Graph API が取りに来るのと同じ立場で）確かめる。"""
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "kenshou"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        return e.code, ""


def publish_files(paths, dry_run: bool = False, create: bool = False, only: bool = False) -> dict:
    """投稿する媒体ファイル（dist/sns-media/ 配下）を配信して {ローカルパス: 公開URL} を返す。

    dry_run のときはアップロードせず、なるはずのURLだけ返す。
    only=True なら渡したファイルだけをサイトに置く（疎通確認用。本番は False で dist/sns-media/ 全部）。
    配信後は各URLに HEAD を打って 200 でなければ例外にする（Graph API に渡す前に気づくため）。
    """
    out = {}
    for p in paths:
        p = pathlib.Path(p)
        if p.resolve().parent != SRC.resolve():
            raise ValueError(f"{p} は {SRC} 直下にありません（投稿するファイルは先にそこへ複製する）")
        if p.suffix.lower() not in EXT_OK:
            raise ValueError(f"{p}: 配信できるのは jpg / mp4 だけ")
        out[str(p)] = public_url(p)
    if dry_run or not paths:
        return out
    for p in paths:
        if not pathlib.Path(p).exists():
            raise FileNotFoundError(p)
    deploy(create=create, quiet=True, only={pathlib.Path(p).name for p in paths} if only else None)
    for p, url in out.items():
        st, ct = verify(url)
        if st != 200:
            raise RuntimeError(f"配信後の確認に失敗: {url} が {st}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--create", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--test-image", help="疎通確認用：この画像を 1080px に縮めて dist/sns-media/test-1.jpg として配信")
    a = ap.parse_args()

    if a.test_image:
        from PIL import Image
        SRC.mkdir(parents=True, exist_ok=True)
        im = Image.open(a.test_image).convert("RGB")
        im.thumbnail((1080, 1080))
        dst = SRC / "test-1.jpg"
        im.save(dst, "JPEG", quality=85, optimize=True)
        print("テスト画像:", dst, im.size)
        urls = publish_files([dst], dry_run=a.dry_run, create=a.create, only=True)
        for p, u in urls.items():
            if a.dry_run:
                print("（dry-run）", p, "→", u)
            else:
                st, ct = verify(u)
                print("公開URL:", u, "→", st, ct)
        return

    files = atsumeru()
    print(f"[sns-media] 送るファイル {len(files)}件（{sum(len(b) for b in files.values()):,} bytes）")
    if a.dry_run:
        for rel in files:
            print(" ", rel, "→", base_url() + rel)
        return
    deploy(create=a.create)


if __name__ == "__main__":
    main()
