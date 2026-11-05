#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Googleクチコミ（GBP）の返信を、週1回まわすための道具（2026-11-05 オーナー指示「丁寧に返信して。週一のルーティン業務に」）。

    python3 tools/gbp-kuchikomi.py --ichiran           # クチコミを全件読み、シート「GBP_クチコミ返信」に新しい分を足す（返信はしない）
    python3 tools/gbp-kuchikomi.py --toukou            # 確認欄が「OK」で未投稿の行だけ返信を投稿する（見るだけなら --dry-run）

流れ（README 4.8.1：返信は漏れなく・新着3日以内・★3以下は投稿前に cmo）：
  1. 鍵（~/.config/one-hitter/gbp.json：client_id・client_secret・refresh_token）がある環境で --ichiran
  2. crm が H列「返信案」を書く（名乗りはワンヒッター。本文に出てくることだけに触れ、個人の事情は書かない）
  3. cmo が J列「確認」に OK（★3以下は必ず cmo が中身を見てから）
  4. 鍵がある環境で --toukou → K列「投稿日」に記入
鍵の値は表示しない・書き出さない。シートには投稿者の表示名と本文（Google上で公開されているもの）だけを置く。
"""
import argparse
import datetime
import json
import pathlib
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sheets_client as sc  # noqa: E402

SS = "1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64"
TAB = "GBP_クチコミ返信"
LOC = "accounts/110951766689355144685/locations/15727525661440316046"  # ワンヒッター㈱（cmo-savedata 10/3）
API = "https://mybusiness.googleapis.com/v4/"
KAGI = pathlib.Path.home() / ".config" / "one-hitter" / "gbp.json"
MIDASHI = ["投稿日", "投稿者（表示名）", "★", "クチコミ本文", "返信の有無", "いまの返信", "名乗り照合（台帳）",
           "返信案（crm）", "メモ", "確認（cmo：OK）", "投稿日（返信）", "reviewId"]
HOSHI = {"ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5}


def access_token():
    if not KAGI.exists():
        sys.exit(f"{KAGI} がありません（GBP_JSON を python3 tools/kagi-fukugen.py で戻す）。この環境では動かせません")
    k = json.loads(KAGI.read_text(encoding="utf-8"))
    k = k.get("installed") or k.get("web") or k
    for need in ("client_id", "client_secret", "refresh_token"):
        if not k.get(need):
            sys.exit(f"gbp.json に {need} がありません（値は表示しません）")
    body = urllib.parse.urlencode({"client_id": k["client_id"], "client_secret": k["client_secret"],
                                   "refresh_token": k["refresh_token"], "grant_type": "refresh_token"}).encode()
    with urllib.request.urlopen(urllib.request.Request("https://oauth2.googleapis.com/token", data=body), timeout=30) as r:
        return json.loads(r.read())["access_token"]


def gbp(tok, path, method="GET", payload=None):
    req = urllib.request.Request(API + path, method=method, headers={"Authorization": "Bearer " + tok,
                                                                      "Content-Type": "application/json"},
                                 data=json.dumps(payload).encode() if payload is not None else None)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read() or b"{}")


def subete(tok):
    out, page = [], ""
    while True:
        d = gbp(tok, f"{LOC}/reviews?pageSize=50" + (f"&pageToken={page}" if page else ""))
        out += d.get("reviews", [])
        page = d.get("nextPageToken", "")
        if not page:
            return out, d.get("totalReviewCount"), d.get("averageRating")


def tab_yomu(stok):
    meta = sc.call(stok, f"/{SS}", query={"fields": "sheets.properties(title,sheetId)"})
    if TAB not in [s["properties"]["title"] for s in meta["sheets"]]:
        sc.call(stok, f"/{SS}:batchUpdate", "POST", {"requests": [{"addSheet": {"properties": {
            "title": TAB, "gridProperties": {"frozenRowCount": 1}}}}]})
        kaku(stok, "A1", [MIDASHI])
        return []
    return sc.call(stok, f"/{SS}/values/{urllib.parse.quote(TAB + '!A2:L2000', safe='')}").get("values", [])


def kaku(stok, rng, values):
    sc.call(stok, f"/{SS}/values/{urllib.parse.quote(TAB + '!' + rng, safe='')}", "PUT", {"values": values},
            query={"valueInputOption": "RAW"})


def ichiran():
    tok = access_token()
    revs, total, avg = subete(tok)
    stok = sc.access_token(sc.load_credentials())
    rows = tab_yomu(stok)
    aru = {(r + [""] * 12)[11] for r in rows}
    shin = []
    for v in sorted(revs, key=lambda v: v.get("createTime", "")):
        rid = v.get("reviewId") or v["name"].split("/")[-1]
        if rid in aru:
            continue
        rep = (v.get("reviewReply") or {}).get("comment", "")
        shin.append([v.get("createTime", "")[:10], (v.get("reviewer") or {}).get("displayName", ""),
                     str(HOSHI.get(v.get("starRating"), "")), v.get("comment", ""), "あり" if rep else "なし",
                     rep, "", "", "", "", "", rid])
    if shin:
        kaku(stok, f"A{len(rows) + 2}", shin)
    mihen = sum(1 for v in revs if not v.get("reviewReply"))
    print(f"クチコミ {len(revs)}件（Google表示 {total}件・平均 {avg}）／未返信 {mihen}件／シートに新しく足した {len(shin)}行")


def toukou(dry):
    stok = sc.access_token(sc.load_credentials())
    rows = tab_yomu(stok)
    tok = None if dry else access_token()
    n = 0
    for i, r in enumerate(rows, start=2):
        r = r + [""] * 12
        if r[9].strip().upper() != "OK" or r[10].strip() or not r[7].strip() or not r[11]:
            continue
        n += 1
        if dry:
            print(f"  投稿する予定：{i}行目（★{r[2]}・{len(r[7])}字）")
            continue
        gbp(tok, f"{LOC}/reviews/{r[11]}/reply", "PUT", {"comment": r[7].strip()})
        kaku(stok, f"K{i}", [[str(datetime.date.today())]])
        print(f"  投稿しました：{i}行目")
    print(f"{'投稿予定' if dry else '投稿'} {n}件")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ichiran", action="store_true")
    ap.add_argument("--toukou", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.ichiran:
        ichiran()
    elif a.toukou:
        toukou(a.dry_run)
    else:
        print(__doc__)
