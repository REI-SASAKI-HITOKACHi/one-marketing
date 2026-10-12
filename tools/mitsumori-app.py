#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""見積アプリ（Apps Script のウェブアプリ）を外部APIで操作する。CMO が見積書を作り、ドライブのPDFのURLを受け取るための道具。

【なぜ】
  2026-10-12 オーナー「見積アプリで君が作成したファイルはドライブへ自動保存されるだろ？その保存先URLを提示すれば済む話じゃん」
  「君が常に見積アプリを操作できる状態にして。無駄な仕事を増やさないで。」
  → お客様の見積書はスプレッドシートの見本タブではなく、見積アプリで作る。PDF はアプリが「アプリ/見積書・請求書/見積書」に保存する。
  仕様は quotation ブランチの apps/estimate-app/docs/external-api.md。

【鍵】（リポジトリ・チャット・掲示板に値を書かない）
  QUOTE_API_TOKEN（環境変数）または ~/.config/one-hitter/quote-api-token.txt … アプリのスクリプトプロパティ API_TOKEN と同じ値
  QUOTE_API_URL（環境変数）または ~/.config/one-hitter/quote-api-url.txt   … ウェブアプリの …/exec のURL
  kagi-fukugen.py がセッション開始時に環境変数からファイルへ書き戻す。

【使い方】
  python3 tools/mitsumori-app.py ping
  python3 tools/mitsumori-app.py get 20261012-01
  python3 tools/mitsumori-app.py save payload.json      # 見積を保存（requestId が無ければ自動で付ける）→ 見積番号
  python3 tools/mitsumori-app.py build 20261012-01      # PDF を作ってドライブに保存 → PDFのURL
  payload.json は external-api.md「4a」の形（金額・単価は渡さない。menuId と qty だけ）。
"""
import json
import os
import pathlib
import sys
import urllib.request
import uuid

KAGI = pathlib.Path.home() / ".config" / "one-hitter"


def yomu(env: str, fn: str) -> str:
    v = os.environ.get(env, "").strip()
    if not v and (KAGI / fn).exists():
        v = (KAGI / fn).read_text(encoding="utf-8").strip()
    if not v:
        sys.exit(f"{env} がありません（環境変数か ~/.config/one-hitter/{fn}）。オーナーに環境変数の登録を頼む")
    return v


def call(action: str, **kw) -> dict:
    url = yomu("QUOTE_API_URL", "quote-api-url.txt")
    body = json.dumps({"token": yomu("QUOTE_API_TOKEN", "quote-api-token.txt"), "action": action, **kw}).encode()
    req = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:   # Apps Script は 302 で結果のURLへ回す。urllib は追いかける
        d = json.loads(r.read().decode("utf-8"))
    if not d.get("ok"):
        sys.exit("失敗: " + str(d.get("error")))
    return d


def main() -> None:
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    if a[0] == "ping":
        d = call("ping")
    elif a[0] == "get":
        d = call("getEstimate", estimateId=a[1])
    elif a[0] == "save":
        p = json.loads(pathlib.Path(a[1]).read_text(encoding="utf-8"))
        p.setdefault("requestId", str(uuid.uuid4()))
        d = call("saveEstimate", payload=p)
    elif a[0] == "build":
        d = call("buildEstimate", estimateId=a[1])
    else:
        sys.exit(__doc__)
    print(json.dumps(d, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
