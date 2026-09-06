#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LINE Messaging API のクライアント。紹介クーポンの作成・配布に使う。

認証はチャネルアクセストークン。**環境変数からしか読まない。**
  export LINE_CHANNEL_ACCESS_TOKEN="..."
リポジトリにもファイルにも書かないこと。

使い方
  python3 tools/line_client.py info
      アカウントの情報と友だち数を出す。疎通確認はこれで足りる。

  python3 tools/line_client.py coupon-create --file data/line-coupon-referral.json --dry-run
      送るJSONを表示するだけ。トークン不要。

  python3 tools/line_client.py coupon-create --file data/line-coupon-referral.json --confirm CREATE
      クーポンを作る。★作成後は修正できない（終了させて作り直しになる）。

  python3 tools/line_client.py coupon-list
  python3 tools/line_client.py coupon-get --id <couponId>

  python3 tools/line_client.py push --to <userId> --coupon <couponId> --confirm SEND
      該当者1名にクーポンメッセージを送る。

  python3 tools/line_client.py push --to <userId> --text "..." --confirm SEND

  python3 tools/line_client.py quota
      今月の無料メッセージ通数と消化数。プラン変更の判断に使う。

★確認済みの仕様（LINE Developers 公式ドキュメントで確認、2026-09-06）
  - クーポン作成: POST https://api.line.me/v2/bot/coupon
  - 固定額の割引: reward.type="discount" / reward.priceInfo.type="fixed" / fixedAmount
  - クーポンメッセージ: {"type":"coupon","couponId":"..."}
  - push / multicast / broadcast / narrowcast / reply で送信できる
  - 作成後の修正は不可。終了は PUT /v2/bot/coupon/{couponId}/close で、獲得済みの人も使えなくなる

★未確認
  リクエストボディの全プロパティ名までは公式リファレンスがJavaScriptで描画されるため取得できていない。
  data/line-coupon-referral.json は現時点の下書き。**APIがエラーを返したら、その本文をそのまま読んで直すこと。**
  推測でプロパティ名を足さないこと。
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

API = "https://api.line.me/v2/bot"
ENV = "LINE_CHANNEL_ACCESS_TOKEN"


def token():
    t = os.environ.get(ENV)
    if not t:
        raise SystemExit(
            f"環境変数 {ENV} が設定されていません。\n"
            "オーナーがDriveの限定公開ドキュメントに置いたトークンを読み込んでから実行してください。"
        )
    return t


def call(method, path, body=None, raw_url=None):
    url = raw_url or (API + path)
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": "Bearer " + token(),
            **({"Content-Type": "application/json"} if data else {}),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            text = r.read().decode("utf-8", "replace")
            return r.status, (json.loads(text) if text.strip() else {})
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(text)
        except ValueError:
            return e.code, {"raw": text}


def show(status, body):
    print(f"HTTP {status}")
    print(json.dumps(body, ensure_ascii=False, indent=2))
    return 0 if 200 <= status < 300 else 1


def cmd_info(_):
    rc = 0
    for label, path in [("botの情報", "/info"), ("友だち数（前日分）", None)]:
        if path:
            rc |= show(*call("GET", path))
    # 友だち数は insight API。日付は前日を既定にする
    import datetime as dt

    d = (dt.date.today() - dt.timedelta(days=1)).strftime("%Y%m%d")
    print(f"\n■ 友だち数（{d}）")
    rc |= show(*call("GET", f"/insight/followers?date={d}"))
    return rc


def cmd_quota(_):
    print("■ 今月の無料通数")
    rc = show(*call("GET", "/message/quota"))
    print("\n■ 今月の消化数")
    rc |= show(*call("GET", "/message/quota/consumption"))
    print(
        "\n※ コミュニケーションプランは月200通まで無料。"
        "\n※ 応答メッセージ（相手の発言への返信）は通数にカウントされない。"
    )
    return rc


def cmd_coupon_create(a):
    with open(a.file, encoding="utf-8") as f:
        body = json.load(f)
    body = {k: v for k, v in body.items() if not k.startswith("_")}
    if a.dry_run or a.confirm != "CREATE":
        print("[DRY RUN] 作成しません。送るJSONは次のとおりです。")
        print(json.dumps(body, ensure_ascii=False, indent=2))
        if not a.dry_run:
            print("\n実行するには --confirm CREATE を付けてください。")
            print("★作成したクーポンは修正できません。内容をよく確認してから実行してください。")
        return 0
    return show(*call("POST", "/coupon", body))


def cmd_coupon_list(_):
    return show(*call("GET", "/coupon"))


def cmd_coupon_get(a):
    return show(*call("GET", f"/coupon/{a.id}"))


def cmd_coupon_close(a):
    if a.confirm != "CLOSE":
        print("エラー: 終了には --confirm CLOSE が必要です。", file=sys.stderr)
        print("★終了させると、すでに獲得したお客様も使えなくなります。元に戻せません。", file=sys.stderr)
        return 2
    return show(*call("PUT", f"/coupon/{a.id}/close"))


def cmd_push(a):
    if not a.coupon and not a.text:
        print("エラー: --coupon か --text のどちらかが要ります。", file=sys.stderr)
        return 2
    msgs = []
    if a.text:
        msgs.append({"type": "text", "text": a.text})
    if a.coupon:
        msgs.append({"type": "coupon", "couponId": a.coupon})
    body = {"to": a.to, "messages": msgs}
    if a.confirm != "SEND":
        print("[DRY RUN] 送信しません。--confirm SEND を付けると送ります。")
        print(json.dumps(body, ensure_ascii=False, indent=2))
        return 0
    return show(*call("POST", "/message/push", body))


def main():
    p = argparse.ArgumentParser(description="LINE Messaging API クライアント")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("info", help="アカウント情報と友だち数").set_defaults(fn=cmd_info)
    sub.add_parser("quota", help="今月の無料通数と消化数").set_defaults(fn=cmd_quota)

    c = sub.add_parser("coupon-create", help="クーポンを作る（作成後は修正不可）")
    c.add_argument("--file", required=True)
    c.add_argument("--dry-run", action="store_true")
    c.add_argument("--confirm")
    c.set_defaults(fn=cmd_coupon_create)

    sub.add_parser("coupon-list", help="クーポンの一覧").set_defaults(fn=cmd_coupon_list)

    g = sub.add_parser("coupon-get", help="クーポンの詳細")
    g.add_argument("--id", required=True)
    g.set_defaults(fn=cmd_coupon_get)

    x = sub.add_parser("coupon-close", help="クーポンを終了する（元に戻せない）")
    x.add_argument("--id", required=True)
    x.add_argument("--confirm")
    x.set_defaults(fn=cmd_coupon_close)

    s = sub.add_parser("push", help="1名に送る")
    s.add_argument("--to", required=True, help="LINEのユーザーID")
    s.add_argument("--text")
    s.add_argument("--coupon", help="couponId")
    s.add_argument("--confirm")
    s.set_defaults(fn=cmd_push)

    a = p.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
