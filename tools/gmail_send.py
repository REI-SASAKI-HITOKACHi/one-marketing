#!/usr/bin/env python3
"""Gmail API（OAuth）でメールを送る。施設カードの依頼メール用（送信元 onehitter.her@gmail.com。CMO 決定 2026-09-13 20260913-07-cmo）。

認証情報は ~/.config/one-hitter/gmail-oauth.json から読む（この環境は SMTP が出られないので HTTPS の Gmail API を使う）。
  {"client_id": "...", "client_secret": "...", "refresh_token": "...", "sender": "onehitter.her@gmail.com"}
値は認証情報ドキュメント §12 から手で写す。**git・掲示板・チャットには絶対に書かない。** トークンの値は print しない。

型（必須。CMO 決定）：From「ワンヒッター株式会社 佐々木」<onehitter.her@gmail.com>／Reply-To: info@one-hitter.her.jp／
本文末に会社名・住所・電話・「今後のご案内が不要でしたら、このメールにその旨ご返信ください」（特定電子メール法）。
1施設1通・1日50件まで（上限の管理は shisetsu-outreach.py 側）。

使い方:
  python3 tools/gmail_send.py whoami                     # 認可されたアカウントのアドレスを表示
  python3 tools/gmail_send.py test --to <自分のアドレス>   # 1通だけ試送
"""
import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid

CFG = os.path.expanduser("~/.config/one-hitter/gmail-oauth.json")
TOKEN_URL = "https://oauth2.googleapis.com/token"
API = "https://gmail.googleapis.com/gmail/v1/users/me"
FROM_NAME = "ワンヒッター株式会社 佐々木"
REPLY_TO = "info@one-hitter.her.jp"


def load() -> dict:
    if not os.path.exists(CFG):
        sys.exit(f"Gmail の認証情報がありません: {CFG}（認証情報ドキュメント §12 から client_id / client_secret / refresh_token / sender を写す）")
    cfg = json.load(open(CFG, encoding="utf-8"))
    for k in ("client_id", "client_secret", "refresh_token", "sender"):
        if not cfg.get(k):
            sys.exit(f"gmail-oauth.json に {k} がありません")
    return cfg


def access_token(cfg: dict) -> str:
    body = urllib.parse.urlencode({"client_id": cfg["client_id"], "client_secret": cfg["client_secret"],
                                   "refresh_token": cfg["refresh_token"], "grant_type": "refresh_token"}).encode()
    req = urllib.request.Request(TOKEN_URL, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)["access_token"]
    except urllib.error.HTTPError as e:
        # 秘密は出さない。エラー種別（invalid_grant 等）だけ
        detail = e.read().decode("utf-8", "replace")
        try:
            detail = json.loads(detail).get("error", "")
        except Exception:
            detail = detail[:80]
        sys.exit(f"Gmail のトークン更新に失敗: HTTP {e.code} {detail}")


def _call(token: str, path: str, method: str = "GET", payload=None):
    req = urllib.request.Request(API + path, data=json.dumps(payload).encode() if payload is not None else None, method=method)
    req.add_header("Authorization", "Bearer " + token)
    if payload is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Gmail API {e.code}: {e.read().decode('utf-8', 'replace')[:300]}")


def whoami(cfg: dict) -> str:
    return _call(access_token(cfg), "/profile").get("emailAddress", "")


def build(cfg: dict, to: str, subject: str, body: str) -> bytes:
    m = MIMEText(body, "plain", "utf-8")
    m["From"] = formataddr((str(Header(FROM_NAME, "utf-8")), cfg["sender"]))
    m["To"] = to
    m["Reply-To"] = REPLY_TO
    m["Subject"] = Header(subject, "utf-8")
    m["Date"] = formatdate(localtime=True)
    m["Message-ID"] = make_msgid(domain="one-hitter.her.jp")
    return m.as_bytes()


def send(cfg: dict, to: str, subject: str, body: str, token: str = "") -> str:
    """送って message id を返す。失敗は RuntimeError"""
    if "@" not in to:
        raise RuntimeError(f"宛先の形式がおかしい: {to}")
    raw = base64.urlsafe_b64encode(build(cfg, to, subject, body)).decode()
    r = _call(token or access_token(cfg), "/messages/send", "POST", {"raw": raw})
    return r.get("id", "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["whoami", "test"])
    ap.add_argument("--to", default="")
    a = ap.parse_args()
    cfg = load()
    if a.mode == "whoami":
        print("認可されたアカウント:", whoami(cfg))
        return
    if not a.to:
        sys.exit("--to が要る")
    mid = send(cfg, a.to, "【試送】ワンヒッター 施設カードの依頼メール（送信の型の確認）",
               "この1通は送信の型（From・Reply-To・署名）の確認です。返信は不要です。\n\n"
               "ワンヒッター株式会社\n〒134-0081 東京都江戸川区北葛西5-14-11 クオーディア西葛西503／080-8043-8259\n"
               "今後のご案内が不要でしたら、このメールにその旨ご返信ください。")
    print("送信 id:", mid)


if __name__ == "__main__":
    main()
