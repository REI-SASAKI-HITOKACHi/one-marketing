#!/usr/bin/env python3
"""Search Console の検索語句（表示・クリック・掲載順位）を表にする。読むだけ。

    python3 tools/search-console.py --site https://one-hitter.jp/ --start 2026-09-21 --end 2026-10-20
    python3 tools/search-console.py --site sc-domain:one-hitter.jp --start ... --end ... --by page

鍵は GA4 の道具と同じ（tools/sheets_client.py の load_credentials()）。サービスアカウントが
Search Console にユーザーとして入っている必要がある（2026-10-09 時点で入っている：CMO savedata T051）。
--site は Search Console に登録した形のまま渡す（URL プレフィックスなら末尾の / まで、ドメインなら sc-domain:）。
"""

import argparse
import importlib.util
import json
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", required=True)
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--by", default="query", choices=["query", "page"])
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--save", help="結果を JSON で保存（個人情報は含まない）")
    a = ap.parse_args()

    spec = importlib.util.spec_from_file_location("shirabe", ROOT / "tools" / "ga4-event-shirabe.py")
    sh = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sh)
    sc = sh.load_sheets_client()
    token = sc.access_token(sc.load_credentials(), scope=SCOPE)

    url = ("https://searchconsole.googleapis.com/webmasters/v3/sites/"
           + urllib.parse.quote(a.site, safe="") + "/searchAnalytics/query")
    body = {"startDate": a.start, "endDate": a.end, "dimensions": [a.by], "rowLimit": a.limit}
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST")
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            res = json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"Search Console API {e.code}: {e.read().decode('utf-8', 'replace')[:600]}")

    rows = res.get("rows", [])
    if a.save:
        pathlib.Path(a.save).write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    print(f"# Search Console（{a.site}・{a.start}〜{a.end}・{a.by}）\n")
    print("| " + ("検索語句" if a.by == "query" else "ページ") + " | 表示 | クリック | クリック率 | 平均掲載順位 |")
    print("|---|--:|--:|--:|--:|")
    for r in rows:
        print(f"| {r['keys'][0]} | {int(r.get('impressions', 0))} | {int(r.get('clicks', 0))} | "
              f"{r.get('ctr', 0) * 100:.1f}% | {r.get('position', 0):.1f} |")
    if not rows:
        print("（行がありません）")


if __name__ == "__main__":
    main()
