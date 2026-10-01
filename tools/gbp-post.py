#!/usr/bin/env python3
"""GBP「最新情報」を、キューにある予定の分だけ API で投稿する（sns-post.py の GBP 版）。

キュー：data/gbp-queue.json
  [{"id": "G011", "本文": "...", "ボタン": "予約"|"詳細"|"電話"|"なし", "予定": "2026-10-04T10:00:00+09:00",
    "承認": "cmo 2026-10-02", "状態": "承認済み", "投稿URL": null}, ...]
  「状態」が 承認済み で、「予定」を過ぎていて、まだ投稿していないものだけ出す。

出す前の門（どれか1つでも落ちたら出さない）：
  ① tools/check-gbp.py の check()（字数・禁止語・本舗の語・相対表現・写真前提・指示語・時刻・繁忙期）
  ② ボタンのURLに計測の印があること（予約→ https://yoyaku.onehitter.jp/?src=gbp ／ 詳細→ utm_source=gbp）
  ③ 承認が入っていること

使い方：
  python3 tools/gbp-post.py --dry-run     # 何も送らない。門の結果と、送る内容だけ見る
  python3 tools/gbp-post.py               # 予定を過ぎた承認済みを投稿
★ 実機未確認（2026-10-01 時点で refresh_token が無い）。最初は --dry-run。
"""
import argparse
import datetime
import importlib.util
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
QUEUE = ROOT / "data" / "gbp-queue.json"
LOG = ROOT / "data" / "gbp-log.json"
JST = datetime.timezone(datetime.timedelta(hours=9))

URL_YOYAKU = "https://yoyaku.onehitter.jp/?src=gbp"
URL_SHOUSAI = "https://one-hitter.jp/?utm_source=gbp&utm_medium=post&utm_campaign={ym}"


def _load(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def button(kind: str, ym: str):
    """(actionType, url) か None。計測の印が付いたURLだけを作る。"""
    if kind == "予約":
        return "BOOK", URL_YOYAKU
    if kind == "詳細":
        return "LEARN_MORE", URL_SHOUSAI.format(ym=ym)
    return None   # 電話・なし：CALL は電話番号が要るので、必要になったときに足す


def gates(p: dict, chk, prices) -> list:
    ng = [f"check-gbp: {x}" for x in chk.check(p["本文"], prices)]
    if not p.get("承認"):
        ng.append("承認が入っていない")
    if p.get("ボタン") in ("予約", "詳細") and not button(p["ボタン"], "202610"):
        ng.append("ボタンのURLが作れない")
    return ng


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    q = json.load(open(QUEUE, encoding="utf-8")) if QUEUE.exists() else []
    log = json.load(open(LOG, encoding="utf-8")) if LOG.exists() else []
    now = datetime.datetime.now(JST)
    chk = _load("check_gbp", ROOT / "tools" / "check-gbp.py")
    prices = chk.load_prices()
    todo = [p for p in q if p.get("状態") == "承認済み" and not p.get("投稿URL")
            and datetime.datetime.fromisoformat(p["予定"]) <= now]
    print(f"今 {now:%Y-%m-%dT%H:%M}+09:00／対象 {len(todo)}件" + ("（dry-run）" if a.dry_run else ""))
    if not todo:
        print("出すものはありません")
        return 0
    rc = 0
    if not a.dry_run:
        sys.path.insert(0, str(ROOT / "tools"))
        import gbp_client as g
        acc, loc = g.account_and_location()
    for p in todo:
        ng = gates(p, chk, prices)
        print(f"■ {p['id']} {p['予定']} ボタン={p.get('ボタン')}")
        if ng:
            print("   門で止めた：", "／".join(ng))
            rc = 1
            continue
        ym = datetime.datetime.fromisoformat(p["予定"]).strftime("%Y%m")
        body = {"languageCode": "ja", "topicType": "STANDARD", "summary": p["本文"].strip()}
        b = button(p.get("ボタン", ""), ym)
        if b:
            body["callToAction"] = {"actionType": b[0], "url": b[1]}
        print("   送る内容：", json.dumps(body, ensure_ascii=False)[:160], "…")
        if a.dry_run:
            continue
        try:
            r = g.call("POST", f"{g.V4}/{acc}/{loc}/localPosts", body=body)
        except g.GbpError as e:
            print("   失敗：", e)
            rc = 1
            continue
        p["投稿URL"] = r.get("searchUrl") or r.get("name")
        log.append({"id": p["id"], "投稿": now.isoformat(), "url": p["投稿URL"]})
        print("   OK", p["投稿URL"])
    if not a.dry_run:
        json.dump(q, open(QUEUE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        json.dump(log, open(LOG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return rc


if __name__ == "__main__":
    sys.exit(main())
