#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SMSの送信実行。tools/sms_build.py が作った送信キュー(JSONL)を読んで送る。

★重要（ハルシネーション防止）
  KDDI Message Cast のAPI仕様（エンドポイントURL・パラメータ名・認証方式）は
  公式サイトで公開されておらず、契約後に配布されるAPI仕様書にしか書かれていない。
  そのため、このスクリプトには仕様を一切ハードコードしていない。
  仕様書が届いたら private/sms-provider.json を作って、そこに書き写すこと。
  設定が無い状態では --dry-run 以外は動かない（安全側に倒してある）。

private/sms-provider.json の形（API仕様書を見ながら埋める）
{
  "name": "KDDI Message Cast",
  "endpoint": "https://.../send",          // 仕様書の送信APIのURL
  "method": "POST",
  "auth": {"type": "bearer", "env": "SMS_API_TOKEN"},
      // type は bearer / basic / header のいずれか
      // basic のときは {"type":"basic","env_user":"SMS_API_USER","env_pass":"SMS_API_PASS"}
      // header のときは {"type":"header","name":"X-API-KEY","env":"SMS_API_TOKEN"}
  "body_format": "json",                    // json または form
  "fields": {                               // 左がAPIのパラメータ名、右がこちらの値
    "to": "$tel",
    "text": "$body",
    "from": "0801234567"
  },
  "success": {"http": [200, 201], "json_path": "status", "json_value": "OK"},
  "rate_limit_per_sec": 5
}

認証情報は環境変数から読む。ファイルにもリポジトリにも書かない。

使い方
  python3 tools/sms_send.py --queue private/queue.jsonl --dry-run
      1件も送らずに、送信内容と件数・見積額を出す。設定ファイル不要。

  python3 tools/sms_send.py --queue private/queue.jsonl --limit 1 --confirm SEND
      テスト送信（1件）。--confirm SEND を付けないと送らない。

  python3 tools/sms_send.py --queue private/queue.jsonl --confirm SEND
      本送信。★オーナーの承認を得てから実行すること。

  python3 tools/sms_send.py --result private/result.jsonl --report
      送信結果の集計（到達／不達）。
"""

import argparse
import base64
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "private", "sms-provider.json")
PRICE_PER_UNIT = 9.35


def load_queue(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_config():
    if not os.path.exists(CONFIG):
        return None
    with open(CONFIG, encoding="utf-8") as f:
        return json.load(f)


def build_request(cfg, item):
    fields = {}
    for k, v in cfg["fields"].items():
        if v == "$tel":
            fields[k] = item["tel"]  # 文字列のまま。数値化しない
        elif v == "$body":
            fields[k] = item["body"]
        else:
            fields[k] = v

    if cfg.get("body_format", "json") == "form":
        data = urllib.parse.urlencode(fields).encode()
        ctype = "application/x-www-form-urlencoded"
    else:
        data = json.dumps(fields, ensure_ascii=False).encode()
        ctype = "application/json"

    headers = {"Content-Type": ctype}
    auth = cfg.get("auth", {})
    t = auth.get("type")
    if t == "bearer":
        tok = os.environ.get(auth["env"])
        if not tok:
            raise SystemExit(f"環境変数 {auth['env']} が設定されていません")
        headers["Authorization"] = "Bearer " + tok
    elif t == "basic":
        u, p = os.environ.get(auth["env_user"]), os.environ.get(auth["env_pass"])
        if not u or not p:
            raise SystemExit(f"環境変数 {auth['env_user']} / {auth['env_pass']} が設定されていません")
        headers["Authorization"] = "Basic " + base64.b64encode(f"{u}:{p}".encode()).decode()
    elif t == "header":
        tok = os.environ.get(auth["env"])
        if not tok:
            raise SystemExit(f"環境変数 {auth['env']} が設定されていません")
        headers[auth["name"]] = tok
    return urllib.request.Request(cfg["endpoint"], data=data, headers=headers, method=cfg.get("method", "POST"))


def is_success(cfg, status, body_text):
    ok = cfg.get("success", {})
    if status not in ok.get("http", [200]):
        return False
    jp, jv = ok.get("json_path"), ok.get("json_value")
    if not jp:
        return True
    try:
        obj = json.loads(body_text)
    except ValueError:
        return False
    for part in jp.split("."):
        if not isinstance(obj, dict) or part not in obj:
            return False
        obj = obj[part]
    return str(obj) == str(jv)


def mask(tel):
    return tel[:3] + "*" * (len(tel) - 7) + tel[-4:] if len(tel) >= 7 else "***"


def cmd_dry(queue, limit):
    items = queue[:limit] if limit else queue
    units = sum(i["units"] for i in items)
    print(f"[DRY RUN] 送信しません。{len(items)}件 / {units}通分 / 約{units * PRICE_PER_UNIT:,.0f}円")
    print()
    for i in items[:5]:
        print(f"--- {mask(i['tel'])} / {i['template']} / {i['units']}通分")
        print(i["body"])
        print()
    if len(items) > 5:
        print(f"…ほか {len(items) - 5}件")
    cfg = load_config()
    print()
    print("設定ファイル: " + (CONFIG + "（あり）" if cfg else CONFIG + " が無い。API仕様書が届いたら作ること"))
    return 0


def cmd_send(args, queue):
    cfg = load_config()
    if not cfg:
        print(f"エラー: {CONFIG} がありません。API仕様書の内容を書き写してから実行してください。", file=sys.stderr)
        print("（仕様を推測して書かないこと。届いた仕様書のとおりに書くこと）", file=sys.stderr)
        return 2
    if args.confirm != "SEND":
        print("エラー: 実送信には --confirm SEND が必要です。", file=sys.stderr)
        return 2

    items = queue[: args.limit] if args.limit else queue
    out = args.result or os.path.join(ROOT, "private", f"result-{dt.datetime.now():%Y%m%d-%H%M%S}.jsonl")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    wait = 1.0 / max(1, cfg.get("rate_limit_per_sec", 5))
    ok = ng = 0
    with open(out, "w", encoding="utf-8") as f:
        for n, item in enumerate(items, 1):
            rec = {"tel": item["tel"], "template": item["template"], "units": item["units"],
                   "sent_at": dt.datetime.now().isoformat(timespec="seconds")}
            try:
                req = build_request(cfg, item)
                with urllib.request.urlopen(req, timeout=30) as r:
                    status, text = r.status, r.read().decode("utf-8", "replace")
            except urllib.error.HTTPError as e:
                status, text = e.code, e.read().decode("utf-8", "replace")
            except Exception as e:  # noqa: BLE001
                status, text = 0, str(e)
            rec["http"] = status
            rec["response"] = text[:500]
            rec["ok"] = is_success(cfg, status, text)
            ok, ng = (ok + 1, ng) if rec["ok"] else (ok, ng + 1)
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            print(f"{n}/{len(items)} {mask(item['tel'])} {'OK' if rec['ok'] else 'NG ' + str(status)}")
            time.sleep(wait)
    print(f"\n完了: 成功 {ok} / 失敗 {ng} → {out}")
    return 0 if ng == 0 else 1


def cmd_report(path):
    recs = load_queue(path)
    ok = sum(1 for r in recs if r.get("ok"))
    units = sum(r.get("units", 1) for r in recs if r.get("ok"))
    print(f"送信 {len(recs)}件 / 成功 {ok} / 失敗 {len(recs) - ok}")
    print(f"課金対象（到達課金のため成功分のみ）: {units}通分 ≒ {units * PRICE_PER_UNIT:,.0f}円")
    bad = [r for r in recs if not r.get("ok")]
    if bad:
        print("\n■ 失敗した番号（台帳の状態を『要確認』に落とすこと）")
        for r in bad:
            print(f"  {mask(r['tel'])}  HTTP{r.get('http')}  {str(r.get('response'))[:80]}")
    return 0


def main():
    p = argparse.ArgumentParser(description="SMSの送信実行（既定は送らない）")
    p.add_argument("--queue", help="tools/sms_build.py --out で作ったJSONL")
    p.add_argument("--dry-run", action="store_true", help="送らずに内容を表示する")
    p.add_argument("--confirm", help="実送信するときだけ SEND を指定する")
    p.add_argument("--limit", type=int, help="先頭N件だけ扱う（テスト送信用）")
    p.add_argument("--result", help="送信結果の書き出し先／--report のとき読み込み先")
    p.add_argument("--report", action="store_true", help="送信結果を集計する")
    a = p.parse_args()

    if a.report:
        if not a.result:
            p.error("--report には --result が必要です")
        return cmd_report(a.result)
    if not a.queue:
        p.print_help()
        return 2
    queue = load_queue(a.queue)
    if a.dry_run or not a.confirm:
        return cmd_dry(queue, a.limit)
    return cmd_send(a, queue)


if __name__ == "__main__":
    sys.exit(main())
