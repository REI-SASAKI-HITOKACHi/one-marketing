#!/usr/bin/env python3
"""週次の数字（毎週月曜 08:30 JST までに cmo へ返信する分）を Graph API から集める。

【なぜ】 20260912-09-web-inflow（オーナー：「1週間ごとにサマリー報告もお願いします」）。
  形式は「表1つ＋所感3行以内」。数字はここで機械的に出し、所感だけ人（スレッド）が書く。

【出どころ】
  - 投稿数        data/sns-log.json（IG / FB それぞれ、前週に posted_at があるもの）
  - リーチ・保存   IG 各投稿の insights（reach, saved）。前週に出した投稿の合計
  - プロフィール訪問  IG アカウントの insights profile_views（period=day、前週7日の合計）
  - フォロワー      IG followers_count（今）と、前週末に控えた値（data/sns-weekly-state.json）との差
  - FB             ページの followers_count と、各投稿の post_impressions_unique（取れなければ「—」）
  - LPクリック（GA4 traffic_src）・ブログPV・GBP は計測担当・ブラウザ担当から受け取る。ここでは「—」

【期間】 既定は前週の月曜〜日曜（月曜朝に動かす前提）。--week-of YYYY-MM-DD でその日を含む週の前週。
  Graph API は読むだけ。トークンは表示しない。

使い方:
  python3 tools/sns-weekly.py            # 表（Markdown）を出す
  python3 tools/sns-weekly.py --json     # 機械向け
"""
import argparse
import datetime as dt
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import meta_client as M  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
LOG = ROOT / "data" / "sns-log.json"
STATE = ROOT / "data" / "sns-weekly-state.json"
JST = dt.timezone(dt.timedelta(hours=9))


def week_range(week_of: dt.date | None) -> tuple[dt.date, dt.date]:
    today = week_of or dt.datetime.now(JST).date()
    this_mon = today - dt.timedelta(days=today.weekday())
    start = this_mon - dt.timedelta(days=7)
    return start, start + dt.timedelta(days=6)


def posts_in(start: dt.date, end: dt.date) -> list:
    if not LOG.exists():
        return []
    out = []
    for r in json.loads(LOG.read_text(encoding="utf-8")):
        d = dt.datetime.fromisoformat(r["posted_at"]).astimezone(JST).date()
        if start <= d <= end:
            out.append(r)
    return out


def safe(path, params):
    try:
        return M.request(path, params)
    except M.GraphError as e:
        return {"_error": M.mask(str(e))[:200]}


def ig_media_insights(media_id: str, media_type: str) -> dict:
    # reach は全種で取れる。saved は画像・カルーセル・リール。動画（リール）は plays もあるが週次では出さない
    metrics = "reach,saved" if media_type != "VIDEO" else "reach,saved"
    r = safe(f"{media_id}/insights", {"metric": metrics})
    out = {}
    for m in r.get("data", []):
        v = m.get("values", [{}])[0].get("value")
        out[m["name"]] = v
    if "_error" in r:
        out["_error"] = r["_error"]
    return out


def collect(start: dt.date, end: dt.date) -> dict:
    c = M.conf()
    posts = posts_in(start, end)
    ig_posts = [p for p in posts if p["platform"] == "instagram"]
    fb_posts = [p for p in posts if p["platform"] == "facebook"]

    ig = safe(c["ig_user_id"], {"fields": "username,followers_count,media_count"})
    reach = saved = 0
    per = []
    for p in ig_posts:
        mt = safe(p["post_id"], {"fields": "media_type,permalink"}).get("media_type", "IMAGE")
        ins = ig_media_insights(p["post_id"], mt)
        reach += ins.get("reach") or 0
        saved += ins.get("saved") or 0
        per.append({"id": p["id"], "permalink": p["permalink"], **ins})

    since = int(dt.datetime.combine(start, dt.time(0, 0), JST).timestamp())
    until = int(dt.datetime.combine(end + dt.timedelta(days=1), dt.time(0, 0), JST).timestamp())
    # profile_views は metric_type=total_value でしか返らない（2026-09-12 実測。values[] ではなく total_value.value）
    pv = safe(f"{c['ig_user_id']}/insights", {"metric": "profile_views", "period": "day", "metric_type": "total_value", "since": since, "until": until})
    profile_views = None
    if "data" in pv and pv["data"]:
        profile_views = (pv["data"][0].get("total_value") or {}).get("value")

    fb = safe(c["page_id"], {"fields": "followers_count,fan_count"})
    fb_reach = 0
    fb_ok = True
    for p in fb_posts:
        r = safe(f"{p['post_id']}/insights", {"metric": "post_impressions_unique"})
        if "data" in r and r["data"]:
            fb_reach += r["data"][0].get("values", [{}])[0].get("value") or 0
        else:
            fb_ok = False

    st = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    prev = st.get("ig_followers")
    now_f = ig.get("followers_count")
    delta = (now_f - prev) if (prev is not None and now_f is not None) else None

    return {
        "week": f"{start.isoformat()}〜{end.isoformat()}",
        "ig": {"posts": len(ig_posts), "reach": reach, "saved": saved, "profile_views": profile_views,
               "followers": now_f, "followers_delta": delta, "per_post": per, "error": ig.get("_error")},
        "fb": {"posts": len(fb_posts), "reach": fb_reach if fb_ok else None, "followers": fb.get("followers_count"), "error": fb.get("_error")},
    }


def save_state(d: dict) -> None:
    STATE.write_text(json.dumps({"asof": dt.datetime.now(JST).isoformat(timespec="minutes"), "ig_followers": d["ig"]["followers"], "fb_followers": d["fb"]["followers"]},
                                ensure_ascii=False, indent=2), encoding="utf-8")


def md(d: dict) -> str:
    def v(x):
        return "—" if x is None else f"{x:,}" if isinstance(x, int) else str(x)
    ig, fb = d["ig"], d["fb"]
    dl = "" if ig["followers_delta"] is None else f"（{ig['followers_delta']:+d}）"
    return "\n".join([
        f"週次の数字｜{d['week']}",
        "",
        "| 項目 | IG | FB | 備考 |",
        "|---|---|---|---|",
        f"| 投稿数 | {v(ig['posts'])} | {v(fb['posts'])} | data/sns-log.json |",
        f"| リーチ（前週の投稿の合計） | {v(ig['reach'])} | {v(fb['reach'])} | 投稿の insights |",
        f"| 保存 | {v(ig['saved'])} | — | |",
        f"| プロフィール訪問 | {v(ig['profile_views'])} | — | アカウント insights profile_views |",
        f"| LPクリック（GA4 traffic_src） | — | — | 計測担当から |",
        f"| フォロワー | {v(ig['followers'])}{dl} | {v(fb['followers'])} | （ ）は前週末との差 |",
        f"| ブログ 公開本数／PV／上位3 | — | | 未開始（20260912-08） |",
        f"| GBP 投稿／新着クチコミ・返信済み／写真／表示・通話・ルート | — | | 管理画面のインサイト（ブラウザ担当から） |",
        f"| 読本・点検・施設カード | | | （手で1行） |",
    ])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--week-of")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-save", action="store_true", help="フォロワー数の控え（前週末の値）を更新しない")
    a = ap.parse_args()
    s, e = week_range(dt.date.fromisoformat(a.week_of) if a.week_of else None)
    d = collect(s, e)
    print(json.dumps(d, ensure_ascii=False, indent=2) if a.json else md(d))
    if not a.no_save:
        save_state(d)


if __name__ == "__main__":
    main()
