#!/usr/bin/env python3
"""GBP のクチコミを取り、返信がまだのものを出す。返信は、承認済みの文を明示したときだけ送る。

  python3 tools/gbp-reviews.py                 # 新着（返信なし）を一覧。送信はしない
  python3 tools/gbp-reviews.py --all           # 返信済みも含めて全件
  python3 tools/gbp-reviews.py --reply <reviewId> --file <返信文.txt>   # 返信を送る（文は事前に cmo 査読）

返信の型：docs/gbp-クチコミ返信の型.md。★ 返信文は自動で作らない（お客様に届くため）。
投稿者名は画面に出すが、リポジトリには書かない。
★ 実機未確認（2026-10-01 時点で refresh_token が無い）。
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import gbp_client as g  # noqa: E402

STAR = {"ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5}


def all_reviews(acc: str, loc: str) -> list:
    out, tok = [], None
    while True:
        q = {"pageSize": 50, "orderBy": "updateTime desc"}
        if tok:
            q["pageToken"] = tok
        r = g.call("GET", f"{g.V4}/{acc}/{loc}/reviews", q)
        out += r.get("reviews", [])
        tok = r.get("nextPageToken")
        if not tok:
            return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--reply")
    ap.add_argument("--file")
    a = ap.parse_args()
    acc, loc = g.account_and_location()
    if a.reply:
        if not a.file:
            sys.exit("--reply には --file（査読済みの返信文）が要ります")
        text = pathlib.Path(a.file).read_text(encoding="utf-8").strip()
        g.call("PUT", f"{g.V4}/{acc}/{loc}/reviews/{a.reply}/reply", body={"comment": text})
        print("返信しました:", a.reply)
        return 0
    rv = all_reviews(acc, loc)
    new = [r for r in rv if "reviewReply" not in r]
    print(f"クチコミ {len(rv)}件（返信なし {len(new)}件）")
    for r in (rv if a.all else new):
        s = STAR.get(r.get("starRating"), "?")
        print(f"- {r['reviewId']}  ★{s}  {r.get('updateTime', '')[:10]}  {(r.get('comment') or '（コメントなし）')[:60]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
