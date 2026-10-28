#!/usr/bin/env python3
"""広告の日別（表示・クリック・費用・CPC・申込）を、入札の時期で区切って1枚にする。読むだけ。

    python3 tools/nyusatsu-hikaku.py --start 2026-10-01 --end 2026-10-27 \
        --jiki 2026-10-01=クリック数の最大化 --jiki 2026-10-16=コンバージョン数の最大化 \
        --jiki 2026-11-01=クリック数の最大化（戻した後）

- 費用・表示・クリックは 広告_日次（Google広告のスクリプトが毎日 14:59 に書く。同じ日・広告グループが2回あれば最初の行）
- 申込は 予約_Web の src が gads_ で始まる行（キャンセルも数える）と、--tsuika で渡す行（LINE 経由など、src に出ない広告申込）
- --jiki は「その日から」の時期。日付の早い順に区切る
- 鍵の無い環境では --json（--save で保存したもの）から表だけ作り直せる
"""

import argparse
import datetime as dt
import importlib.util
import json
import pathlib
import sys
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
SHEET = "1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64"


def nichiji(rows, start, end):
    """広告_日次の行 → {日付: [表示, クリック, 費用]}"""
    d, seen = {}, set()
    for r in rows[1:]:
        if len(r) < 7 or not (start <= r[1] <= end) or (r[1], r[3]) in seen:
            continue
        seen.add((r[1], r[3]))
        x = d.setdefault(r[1], [0, 0, 0.0])
        x[0] += int(r[5])
        x[1] += int(r[6])
        x[2] += float(r[4])
    return d


def moushikomi(rows, start, end, tsuika):
    """予約_Web の行 → {日付: 件数}。src は15列目（O列）"""
    m = {}
    for r in rows[1:]:
        if len(r) < 15 or not str(r[14]).startswith("gads_"):
            continue
        hi = str(r[0])[:10]
        if start <= hi <= end:
            m[hi] = m.get(hi, 0) + 1
    for hi in tsuika:
        if start <= hi <= end:
            m[hi] = m.get(hi, 0) + 1
    return m


def jiki_of(hi, jiki):
    name = ""
    for k, v in jiki:
        if hi >= k:
            name = v
    return name


def hyou(d, m, jiki, start, end):
    out = ["| 日 | 時期 | 表示 | クリック | 費用 | CPC | 申込 |", "|---|---|--:|--:|--:|--:|--:|"]
    kei = {}
    hi = dt.date.fromisoformat(start)
    while hi.isoformat() <= end:
        s = hi.isoformat()
        x = d.get(s, [0, 0, 0.0])
        n = m.get(s, 0)
        j = jiki_of(s, jiki)
        cpc = f"¥{x[2] / x[1]:,.0f}" if x[1] else "—"
        mark = "" if s in d else "（行なし）"
        out.append(f"| {s[5:].replace('-', '/')}{mark} | {j} | {x[0]} | {x[1]} | ¥{x[2]:,.0f} | {cpc} | {n} |")
        k = kei.setdefault(j, [0, 0, 0, 0.0, 0])
        k[0] += 1 if s in d else 0  # 行の無い日（まだ入っていない日）は日数に数えない
        k[1] += x[0]
        k[2] += x[1]
        k[3] += x[2]
        k[4] += n
        hi += dt.timedelta(days=1)
    out += ["", "| 時期 | 日数 | 表示/日 | クリック/日 | 費用/日 | CPC | 申込 | 7日あたりの申込 | 申込1件あたり |",
            "|---|--:|--:|--:|--:|--:|--:|--:|--:|"]
    for _, j in jiki:
        if j not in kei or not kei[j][0]:
            out.append(f"| {j} | 0 | | | | | | | |")
            continue
        n, im, cl, hiyo, mo = kei[j]
        cpc = f"¥{hiyo / cl:,.0f}" if cl else "—"
        per = f"¥{hiyo / mo:,.0f}" if mo else "—"
        out.append(f"| {j} | {n} | {im / n:.0f} | {cl / n:.1f} | ¥{hiyo / n:,.0f} | {cpc} | {mo} | {mo / n * 7:.1f} | {per} |")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--jiki", action="append", required=True, metavar="YYYY-MM-DD=名前")
    ap.add_argument("--tsuika", action="append", default=[], metavar="YYYY-MM-DD",
                    help="src に出ない広告申込（LINE 経由など）の受付日")
    ap.add_argument("--json")
    ap.add_argument("--save")
    a = ap.parse_args()
    jiki = sorted(tuple(x.split("=", 1)) for x in a.jiki)
    if a.json:
        saved = json.loads(pathlib.Path(a.json).read_text(encoding="utf-8"))
        nichi_rows, web_rows = saved["nichiji"], saved["yoyaku"]
    else:
        spec = importlib.util.spec_from_file_location("shirabe", ROOT / "tools" / "ga4-event-shirabe.py")
        sh = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sh)
        sc = sh.load_sheets_client()
        token = sc.access_token(sc.load_credentials())
        q = {"valueRenderOption": "UNFORMATTED_VALUE", "dateTimeRenderOption": "FORMATTED_STRING"}
        yomu = lambda rng: sc.call(token, f"/{SHEET}/values/{urllib.parse.quote(rng, safe='')}", query=q).get("values", [])
        nichi_rows = yomu("広告_日次!A1:K3000")
        web_rows = yomu("予約_Web!A1:O1000")
        if a.save:
            pathlib.Path(a.save).write_text(json.dumps({"nichiji": nichi_rows, "yoyaku": web_rows},
                                                       ensure_ascii=False), encoding="utf-8")
    d = nichiji(nichi_rows, a.start, a.end)
    m = moushikomi(web_rows, a.start, a.end, a.tsuika)
    print(f"# 入札の時期別（{a.start}〜{a.end}）\n")
    print(hyou(d, m, jiki, a.start, a.end))


if __name__ == "__main__":
    main()
