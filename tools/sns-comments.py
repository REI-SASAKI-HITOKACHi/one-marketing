#!/usr/bin/env python3
"""Instagram・Facebook の投稿に付いた新着コメントを、読むだけで一覧する。返信は送らない。

  python3 tools/sns-comments.py              # 新着（前回までに見ていないもの）を出す。見たコメントIDを記録する
  python3 tools/sns-comments.py --all        # 直近の全コメント（記録は更新しない）
  python3 tools/sns-comments.py --days 14    # 何日前までの投稿を見るか（既定 14）

返信は、お客様に届くため cmo の査読を通した文だけを、別の手順で送る（このツールは送らない）。
記録は data/sns-comments-seen.json（コメントID だけ。本文・氏名は入れない）。
投稿者名は画面に出すが、リポジトリには書かない。
"""
import argparse
import datetime as dt
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import meta_client as m  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
SEEN = ROOT / "data" / "sns-comments-seen.json"


def load_seen() -> set:
    return set(json.loads(SEEN.read_text(encoding="utf-8"))) if SEEN.exists() else set()


def ig_comments(ig: str, since: dt.datetime) -> list:
    out = []
    r = m.request(f"{ig}/media", {"fields": "id,permalink,timestamp,comments_count", "limit": 30})
    for p in r.get("data", []):
        ts = dt.datetime.fromisoformat(p["timestamp"].replace("Z", "+00:00"))
        if ts < since or not p.get("comments_count"):
            continue
        c = m.request(f"{p['id']}/comments", {"fields": "id,username,text,timestamp,replies{id,username,text}"})
        for x in c.get("data", []):
            out.append(("instagram", p["permalink"], x["id"], x.get("username", ""), x.get("text", ""), x.get("timestamp", ""), bool(x.get("replies", {}).get("data"))))
    return out


def fb_comments(page_id: str, since: dt.datetime) -> list:
    tok = m.page_token(page_id)
    out = []
    r = m.request(f"{page_id}/posts", {"fields": "id,permalink_url,created_time,comments.limit(50){id,from,message,created_time,comments.limit(5){from}}", "limit": 25}, token=tok)
    for p in r.get("data", []):
        ts = dt.datetime.fromisoformat(p["created_time"].replace("+0000", "+00:00"))
        if ts < since:
            continue
        for x in p.get("comments", {}).get("data", []):
            frm = x.get("from", {})
            replied = any(str(y.get("from", {}).get("id")) == str(page_id) for y in x.get("comments", {}).get("data", []))
            out.append(("facebook", p.get("permalink_url", ""), x["id"], frm.get("name", ""), x.get("message", ""), x.get("created_time", ""), replied))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--days", type=int, default=14)
    a = ap.parse_args()
    c = m.conf()
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=a.days)
    rows = ig_comments(c["ig_user_id"], since)
    try:
        rows += fb_comments(c["page_id"], since)
    except (SystemExit, m.GraphError) as e:
        print("Facebook のコメントは読めませんでした（権限 pages_read_user_content が無い）:", str(e)[:120])
    seen = load_seen()
    new = [r for r in rows if a.all or r[2] not in seen]
    print(f"対象 {len(rows)} 件／新着 {len(new)} 件（過去{a.days}日の投稿）")
    for r in new:
        print(f"- [{r[0]}] {r[5][:16]} {r[3]}：{r[4][:80]}　{'（返信済み）' if r[6] else '（未返信）'}\n    {r[1]}")
    if not a.all and new:
        SEEN.write_text(json.dumps(sorted(seen | {r[2] for r in new}), ensure_ascii=False), encoding="utf-8")


main()
