#!/usr/bin/env python3
"""GBP のパフォーマンス（検索・地図での表示、通話、ウェブサイトクリック、ルート検索）を週次で取る。

  python3 tools/gbp-insights.py              # 直近7日（今日を除く）と、その前の7日
  python3 tools/gbp-insights.py --days 28

月曜 08:30 の週次の数字の GBP 欄に使う。
★ 実機未確認（2026-10-01 時点で refresh_token が無い）。指標名は Business Profile Performance API の公開仕様。
"""
import argparse
import datetime
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import gbp_client as g  # noqa: E402

METRICS = [
    ("BUSINESS_IMPRESSIONS_MOBILE_SEARCH", "表示：検索（スマホ）"),
    ("BUSINESS_IMPRESSIONS_DESKTOP_SEARCH", "表示：検索（PC）"),
    ("BUSINESS_IMPRESSIONS_MOBILE_MAPS", "表示：地図（スマホ）"),
    ("BUSINESS_IMPRESSIONS_DESKTOP_MAPS", "表示：地図（PC）"),
    ("CALL_CLICKS", "通話"),
    ("WEBSITE_CLICKS", "ウェブサイトのクリック"),
    ("BUSINESS_DIRECTION_REQUESTS", "ルート検索"),
]


def fetch(loc: str, a: datetime.date, b: datetime.date) -> dict:
    q = [("dailyMetric", m) for m, _ in METRICS] + [
        ("dailyRange.startDate.year", a.year), ("dailyRange.startDate.month", a.month), ("dailyRange.startDate.day", a.day),
        ("dailyRange.endDate.year", b.year), ("dailyRange.endDate.month", b.month), ("dailyRange.endDate.day", b.day)]
    import urllib.parse
    url = f"{g.PERF}/{loc}:fetchMultiDailyMetricsTimeSeries?" + urllib.parse.urlencode(q)
    r = g.call("GET", url)
    out = {m: 0 for m, _ in METRICS}
    for blk in r.get("multiDailyMetricTimeSeries", []):
        for s in blk.get("dailyMetricTimeSeries", []):
            m = s.get("dailyMetric")
            for d in s.get("timeSeries", {}).get("datedValues", []):
                out[m] = out.get(m, 0) + int(d.get("value", 0) or 0)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    a = ap.parse_args()
    _, loc = g.account_and_location()
    end = datetime.date.today() - datetime.timedelta(days=1)
    s1 = end - datetime.timedelta(days=a.days - 1)
    e0 = s1 - datetime.timedelta(days=1)
    s0 = e0 - datetime.timedelta(days=a.days - 1)
    now, prev = fetch(loc, s1, end), fetch(loc, s0, e0)
    print(f"期間 {s1}〜{end}（前の期間 {s0}〜{e0}）")
    print("| 指標 | 今期 | 前期 |\n|---|--:|--:|")
    for m, label in METRICS:
        print(f"| {label} | {now[m]} | {prev[m]} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
