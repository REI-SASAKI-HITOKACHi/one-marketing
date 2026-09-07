#!/usr/bin/env python3
"""
LINE Messaging API クライアント（内部用グループへの送信）

チャネルアクセストークンは、この順で読む。コマンドラインには書かない。
  1. 環境変数 LINE_CHANNEL_TOKEN
  2. 環境変数 LINE_CHANNEL_TOKEN_FILE で指定したパス
  3. ~/.config/one-hitter/line-token.txt

送り先のグループIDは、この順で読む。
  1. 引数 --to
  2. 環境変数 LINE_GROUP_ID
  3. ~/.config/one-hitter/line-group-id.txt

トークンもグループIDもリポジトリには置かないこと。

使い方:
  python3 tools/line_client.py whoami
  python3 tools/line_client.py push "本文"
  python3 tools/line_client.py push --file message.txt
  python3 tools/line_client.py push --to Cxxxxxxxx "本文"
  python3 tools/line_client.py quota
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

API = "https://api.line.me/v2/bot"

TOKEN_ENV = "LINE_CHANNEL_TOKEN"
TOKEN_FILE_ENV = "LINE_CHANNEL_TOKEN_FILE"
TOKEN_KITEI = os.path.expanduser("~/.config/one-hitter/line-token.txt")

GROUP_ENV = "LINE_GROUP_ID"
GROUP_KITEI = os.path.expanduser("~/.config/one-hitter/line-group-id.txt")

# LINEのテキストメッセージ1通あたりの上限
MOJI_JOUGEN = 5000


def _yomu(env_name: str, file_env: str, kitei: str, nani: str) -> str:
    v = os.environ.get(env_name, "").strip()
    if v:
        return v
    path = os.environ.get(file_env, "").strip() if file_env else ""
    path = path or kitei
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    sys.exit(
        f"{nani}が見つかりません。\n"
        f"  環境変数 {env_name} に入れるか、{kitei} に置いてください。\n"
        "手順は docs/グループLINE-手順書.md。"
    )


def token() -> str:
    return _yomu(TOKEN_ENV, TOKEN_FILE_ENV, TOKEN_KITEI, "チャネルアクセストークン")


def group_id() -> str:
    return _yomu(GROUP_ENV, "", GROUP_KITEI, "送信先のグループID")


def call(path: str, method: str = "GET", payload=None):
    req = urllib.request.Request(
        API + path,
        method=method,
        headers={
            "Authorization": "Bearer " + token(),
            "Content-Type": "application/json",
        },
        data=json.dumps(payload).encode() if payload is not None else None,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            body = res.read().decode()
            return json.loads(body) if body.strip() else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        sys.exit(f"LINE API エラー {e.code}: {detail}")


def wakeru(text: str):
    """5000字を超える本文を、行の切れ目で分割する"""
    if len(text) <= MOJI_JOUGEN:
        return [text]
    out, ima = [], ""
    for line in text.split("\n"):
        # 1行だけで上限を超える場合は、そのまま切る
        while len(line) > MOJI_JOUGEN:
            if ima:
                out.append(ima)
                ima = ""
            out.append(line[:MOJI_JOUGEN])
            line = line[MOJI_JOUGEN:]
        if len(ima) + len(line) + 1 > MOJI_JOUGEN:
            out.append(ima)
            ima = line
        else:
            ima = (ima + "\n" + line) if ima else line
    if ima:
        out.append(ima)
    return out


def op_whoami(a):
    info = call("/info")
    print("チャネルID:", info.get("chatMode"), "／", json.dumps(info, ensure_ascii=False))
    try:
        print("グループID:", group_id())
    except SystemExit:
        print("グループID: まだ設定されていません")


def op_quota(a):
    q = call("/message/quota")
    used = call("/message/quota/consumption")
    print("プラン:", q.get("type"), "／ 上限:", q.get("value"))
    print("今月の送信数:", used.get("totalUsage"))


def op_push(a):
    if a.file:
        with open(a.file, encoding="utf-8") as f:
            text = f.read()
    else:
        text = a.text
    if not text or not text.strip():
        sys.exit("本文が空です。")

    to = a.to or group_id()
    parts = wakeru(text)
    if len(parts) > 5:
        sys.exit(f"本文が長すぎます（{len(parts)}通に分かれます）。1回の送信は5通までです。")

    if a.dry_run:
        print(f"[確認のみ・送信しません] 宛先 {to} ／ {len(parts)}通")
        for i, p in enumerate(parts, 1):
            print(f"--- {i}通目（{len(p)}字） ---")
            print(p)
        return

    call("/message/push", "POST", {
        "to": to,
        "messages": [{"type": "text", "text": p} for p in parts],
    })
    print(f"送信しました。宛先 {to} ／ {len(parts)}通 ／ {len(text)}字")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("whoami", help="接続とグループIDの確認")
    sub.add_parser("quota", help="今月の送信数と上限")

    sp = sub.add_parser("push", help="グループにメッセージを送る")
    sp.add_argument("text", nargs="?", help="本文")
    sp.add_argument("--file", help="本文が入ったテキストファイル")
    sp.add_argument("--to", help="送信先。省略するとグループID")
    sp.add_argument("--dry-run", action="store_true", help="送らずに内容だけ表示する")

    a = p.parse_args()
    {"whoami": op_whoami, "quota": op_quota, "push": op_push}[a.cmd](a)


if __name__ == "__main__":
    main()
