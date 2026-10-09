#!/usr/bin/env python3
"""SNS（IG/FB）からの流入と申込の週別表。GA4 Data API（プロパティ 381320625）から直接取得する。

使い方: python3 tools/sns-weekly.py [開始日 YYYY-MM-DD] [終了日]
traffic_src の ig / ig_profile / fb を別行で数える。ig_profile は IG プロフィールの2本目リンク（無料点検）。
"""
import datetime as dt, json, sys, urllib.request
sys.path.insert(0, __file__.rsplit("/", 1)[0])
import sheets_client as s

PROP = "381320625"
SRCS = ["ig", "ig_profile", "fb"]
CV = ["booking_submit", "form_submit", "generate_lead"]


def run(tok, body):
    r = urllib.request.Request(
        f"https://analyticsdata.googleapis.com/v1beta/properties/{PROP}:runReport",
        data=json.dumps(body).encode(),
        headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(r)).get("rows", [])


def main():
    start = sys.argv[1] if len(sys.argv) > 1 else "2026-08-31"
    end = sys.argv[2] if len(sys.argv) > 2 else dt.date.today().isoformat()
    tok = s.access_token(s.load_credentials(), "https://www.googleapis.com/auth/analytics.readonly")
    rows = run(tok, {
        "dateRanges": [{"startDate": start, "endDate": end}],
        "dimensions": [{"name": "isoYearIsoWeek"}, {"name": "customEvent:traffic_src"}, {"name": "eventName"}],
        "metrics": [{"name": "eventCount"}],
        "dimensionFilter": {"filter": {"fieldName": "customEvent:traffic_src",
                                       "inListFilter": {"values": SRCS}}}})
    t = {}
    for r in rows:
        wk, src, ev = [d["value"] for d in r["dimensionValues"]]
        n = int(r["metricValues"][0]["value"])
        c = t.setdefault((wk, src), {"session": 0, "form_start": 0, "cv": 0})
        if ev == "session_start": c["session"] += n
        elif ev == "form_start": c["form_start"] += n
        elif ev in CV: c["cv"] += n
    print(f"期間 {start}〜{end}（GA4 実測。セッションは session_start の件数）")
    print("| 週(ISO) | traffic_src | セッション | form_start | 申込 |\n|---|---|--:|--:|--:|")
    for (wk, src), c in sorted(t.items()):
        print(f"| {wk} | {src} | {c['session']} | {c['form_start']} | {c['cv']} |")
    for src in SRCS:
        if not any(k[1] == src for k in t):
            print(f"| (期間内) | {src} | 0 | 0 | 0 |")


main()
