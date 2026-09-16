#!/usr/bin/env python3
"""GA4に**実際に届いているイベント**を、名前とホスト別に数える。

    python3 tools/ga4-event-shirabe.py                  # 直近90日
    python3 tools/ga4-event-shirabe.py --days 28
    python3 tools/ga4-event-shirabe.py --event purchase  # 1つだけ詳しく見る

## 何のためのものか

**キーイベントの一覧を見ても、それが実際に撃たれているかは分かりません。**
GA4は「まだ一度も届いていない名前」でもキーイベントに登録できます。

2026-09-16 に、設計に無いキーイベントが3つ見つかりました。

| 名前 | 見立て |
|---|---|
| `teltap` | **公式サイト**の電話リンク（`ga('send','event','teltap',…)` の実物をHTMLで確認済み） |
| `form_complete` | 公式サイトの問い合わせフォームの完了画面と思われる（**未確認**。POST後にしか出ない） |
| `purchase` | **出どころ不明** |

**何が撃っているか分からないものを先に消してはいけません。**
このスクリプトで「どのホストから何件来ているか」を見てから決めます。

- **0件が続いている** → 誰も撃っていない。消してよい
- **公式サイトから来ている** → **消すと公式サイトの計測が止まります。** 消さない

## 動かすのに要るもの

サービスアカウントの鍵（`tools/sheets_client.py` の `load_credentials()`）。
**計測担当のブランチには鍵がありません。CMOの環境で実行してください。**
"""

import argparse
import datetime as dt
import importlib.util
import json
import pathlib
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
API = "https://analyticsdata.googleapis.com/v1beta"
SCOPE = "https://www.googleapis.com/auth/analytics.readonly"
PROPERTY = "381320625"

# 設計にあるもの。これ以外が出てきたら印を付ける。
SEKKEI = {"generate_lead", "phone_click", "line_click"}


def load_sheets_client():
    path = ROOT / "tools" / "sheets_client.py"
    if not path.exists():
        sys.exit(
            "tools/sheets_client.py がありません。\n"
            "鍵の読み込みをそこから使い回しています。CMOの環境で実行してください。"
        )
    spec = importlib.util.spec_from_file_location("sheets_client", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_report(token: str, prop: str, body: dict) -> dict:
    req = urllib.request.Request(
        f"{API}/properties/{prop}:runReport",
        data=json.dumps(body).encode(), method="POST")
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"GA4 Data API {e.code}: {e.read().decode('utf-8', 'replace')[:800]}")


def rows(res: dict) -> list:
    out = []
    for r in res.get("rows", []):
        d = tuple(v.get("value", "") for v in r.get("dimensionValues", []))
        m = tuple(int(float(v.get("value", 0) or 0)) for v in r.get("metricValues", []))
        out.append((d, m))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--property", default=PROPERTY)
    ap.add_argument("--days", type=int, default=90, help="さかのぼる日数（既定 90）")
    ap.add_argument("--event", help="この名前のイベントだけ、ホスト・ページ別に詳しく見る")
    args = ap.parse_args()

    start = (dt.date.today() - dt.timedelta(days=args.days)).isoformat()
    dr = [{"startDate": start, "endDate": "today"}]

    sc = load_sheets_client()
    token = sc.access_token(sc.load_credentials(), scope=SCOPE)

    if args.event:
        res = run_report(token, args.property, {
            "dateRanges": dr,
            "dimensions": [{"name": "hostName"}, {"name": "pagePath"}],
            "metrics": [{"name": "eventCount"}],
            "dimensionFilter": {"filter": {
                "fieldName": "eventName",
                "stringFilter": {"matchType": "EXACT", "value": args.event}}},
            "limit": "200",
        })
        got = rows(res)
        print(f"# `{args.event}` の出どころ（直近{args.days}日）\n")
        if not got:
            print(f"**0件です。** 直近{args.days}日、`{args.event}` は一度も届いていません。\n")
            print("> **誰も撃っていない名前です。** キーイベントから外して問題ありません。")
            return
        print("| ホスト | ページ | 件数 |")
        print("|---|---|---:|")
        for (host, path), (n,) in sorted(got, key=lambda x: -x[1][0]):
            print(f"| `{host}` | `{path}` | {n:,} |")
        print(f"\n> **撃たれています。** 外すと、上のページの計測が止まります。")
        return

    res = run_report(token, args.property, {
        "dateRanges": dr,
        "dimensions": [{"name": "eventName"}, {"name": "hostName"}],
        "metrics": [{"name": "eventCount"}],
        "limit": "2000",
    })
    # イベント名 → {ホスト: 件数}
    tbl = {}
    for (name, host), (n,) in rows(res):
        tbl.setdefault(name, {})[host] = tbl.setdefault(name, {}).get(host, 0) + n

    print(f"# GA4に届いているイベント（直近{args.days}日・プロパティ {args.property}）\n")
    print("| イベント | 合計 | ホスト別の内訳 |")
    print("|---|---:|---|")
    for name in sorted(tbl, key=lambda k: -sum(tbl[k].values())):
        gokei = sum(tbl[name].values())
        uchiwake = " / ".join(f"`{h}` {v:,}" for h, v in
                              sorted(tbl[name].items(), key=lambda x: -x[1]))
        shirushi = " ⭐" if name in SEKKEI else ""
        print(f"| `{name}`{shirushi} | {gokei:,} | {uchiwake} |")

    print("\n> ⭐ は設計にあるイベント（`docs/measurement-spec.md`）。")
    print("> **ここに出てこない名前は、直近で一度も届いていません。**"
          "キーイベントに登録されていても、実体はありません。")
    print("> **ホスト別の内訳が大事です。** `one-hitter.jp` から来ているものを外すと、"
          "**公式サイトの計測が止まります。**")


if __name__ == "__main__":
    main()
