#!/usr/bin/env python3
"""広告LPの「LP→予約ページ」の率（日別）と、C対E の人数・次の行動・早期判定の線を1枚に出す。

    python3 tools/lp-yoyaku-nichibetsu.py --start 2026-10-11 --end 2026-10-16 --save lpy.json
    python3 tools/lp-yoyaku-nichibetsu.py --json lpy.json        # 鍵の無い環境で表だけ作り直す

**読むだけです。** GA4 Data API（鍵は tools/sheets_client.py。ga4-event-shirabe.py と同じ読み方）。

## 1. 広告LPの「LP→予約ページ」（日別）
- 広告のセッション＝最初のページの URL に `src=gads_*`（カビLP の gads_kabi は除く）か gclid／gbraid／wbraid がある
- LP＝lp.onehitter.jp の page_view のユーザー、予約ページ＝yoyaku.onehitter.jp の page_view のユーザー
- `--kugiri 2026-10-16T16:50 --kugiri 2026-10-16T21:28` のように区切りを渡すと、その日を区切りの前後に分ける。
  **GA4 の時刻は1時間単位**なので、区切りを含む時間帯（16時台・21時台）は「区切りの後」に入れる（少しずれる）

## 2. C対E（起点 10/15 08:2x から）
- LP の全ユーザー（広告だけにしない。早期判定の案 (c) の数え方）
- C＝/aircon-c/、E＝/aircon-e/ を最初のページとするセッション
- 次の行動＝cta_click のユーザー、予約ページへ＝同じセッションで予約ページを開いたユーザー

## 3. 早期判定の線（docs/C対E-判定を早める案.md）
C の「予約ページへ」の人数と、各版の人数から、E を採用する線（片側フィッシャー p<0.10）を出す
"""

import argparse
import importlib.util
import json
import pathlib
import re
import sys
from math import comb

ROOT = pathlib.Path(__file__).resolve().parent.parent
PROP = "381320625"
KIGEN_CE = "2026101508"  # C対E の起点（10/15 08:2x。時間単位なので 08時台から）


def koukoku(landing):
    s = re.search(r"[?&]src=([^&#]*)", landing or "")
    s = s.group(1).lower() if s else ""
    if s.startswith("gads_kabi"):
        return False
    return s.startswith("gads") or (not s and bool(re.search(r"[?&](gclid|gbraid|wbraid)=", landing or "")))


def ban(landing):
    p = (landing or "").split("?")[0]
    if p.startswith("/aircon-c/"):
        return "C"
    if p.startswith("/aircon-e/"):
        return "E"
    return None


def kubun(date_hour, kugiri):
    """date_hour='2026101617' → 日付ラベル（区切りがあればその前後）"""
    d = date_hour[:8]
    label = f"{d[4:6]}/{d[6:8]}"
    ks = [k for k in kugiri if k[:8] == d]
    if not ks:
        return label
    h = date_hour[8:10]
    idx = sum(1 for k in sorted(ks) if h >= k[8:10])
    return label + ["（前）", "（後1）", "（後2）", "（後3）"][idx]


def fisher_one(c, n1, e, n2):
    k = c + e
    tot = comb(n1 + n2, k)
    return sum(comb(n2, x) * comb(n1, k - x) for x in range(e, min(k, n2) + 1)) / tot


def saiyou_sen(c, n_c, n_e):
    for e in range(0, n_e + 1):
        if e / max(n_e, 1) > c / max(n_c, 1) and fisher_one(c, n_c, e, n_e) < 0.10:
            return e
    return None


def shuukei(rows, kugiri):
    """rows: [(dateHour, eventName, hostName, landing, users)]"""
    nichi = {}
    ce = {"C": {"LP": 0, "次の行動": 0, "予約ページへ": 0}, "E": {"LP": 0, "次の行動": 0, "予約ページへ": 0}}
    for dh, ev, host, landing, n in rows:
        host = (host or "").lower()
        if koukoku(landing) and ev == "page_view":
            k = kubun(dh, kugiri)
            d = nichi.setdefault(k, {"LP": 0, "予約ページ": 0})
            if host.startswith("lp."):
                d["LP"] += n
            elif host.startswith("yoyaku."):
                d["予約ページ"] += n
        b = ban(landing)
        if b and dh >= KIGEN_CE:
            if ev == "page_view" and host.startswith("lp."):
                ce[b]["LP"] += n
            elif ev == "cta_click":
                ce[b]["次の行動"] += n
            elif ev == "page_view" and host.startswith("yoyaku."):
                ce[b]["予約ページへ"] += n
    return nichi, ce


def wari(a, b):
    return f"{a / b * 100:.1f}%" if b else "—"


def hyouji(nichi, ce):
    out = ["## 1. 広告LP → 予約ページ（日別・広告のセッション）", "",
           "| 日 | LP | 予約ページ | 率 |", "|---|--:|--:|--:|"]
    tl = ty = 0
    for k in sorted(nichi):
        d = nichi[k]
        tl += d["LP"]
        ty += d["予約ページ"]
        out.append(f"| {k} | {d['LP']} | {d['予約ページ']} | {wari(d['予約ページ'], d['LP'])} |")
    out.append(f"| **計** | **{tl}** | **{ty}** | **{wari(ty, tl)}** |")
    out += ["", "## 2. C対E（10/15 08時台〜・LP の全ユーザー）", "",
            "| 版 | LP | 次の行動 | 率 | 予約ページへ | 率 |", "|---|--:|--:|--:|--:|--:|"]
    for b in ("C", "E"):
        d = ce[b]
        out.append(f"| {b} | {d['LP']} | {d['次の行動']} | {wari(d['次の行動'], d['LP'])} | "
                   f"{d['予約ページへ']} | {wari(d['予約ページへ'], d['LP'])} |")
    c, e = ce["C"], ce["E"]
    out += ["", "## 3. 早期判定の線（案 c）", ""]
    if c["LP"] and e["LP"]:
        sen = saiyou_sen(c["予約ページへ"], c["LP"], e["LP"])
        p = fisher_one(c["予約ページへ"], c["LP"], e["予約ページへ"], e["LP"])
        out.append(f"- いま：C {c['予約ページへ']}/{c['LP']}、E {e['予約ページへ']}/{e['LP']}（片側 p={p:.2f}）")
        out.append(f"- **E を採用する線**：E の予約ページへが **{sen} 人以上**（いまの人数のまま）" if sen is not None
                   else "- E を採用する線：この人数では、E が全員でも p<0.10 に届かない")
        if e["予約ページへ"] / e["LP"] < c["予約ページへ"] / c["LP"]:
            out.append("- E が C を下回っている（判断はしない。オーナー決定 10/24：11/10 まで続ける）")
    else:
        out.append("- C か E の人数が0。振り分けが動いているか確かめる")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start")
    ap.add_argument("--end")
    ap.add_argument("--kugiri", action="append", default=[], metavar="YYYY-MM-DDTHH:MM")
    ap.add_argument("--json")
    ap.add_argument("--save")
    a = ap.parse_args()
    kugiri = [k.replace("-", "").replace("T", "").replace(":", "")[:10] for k in a.kugiri]
    if a.json:
        saved = json.loads(pathlib.Path(a.json).read_text(encoding="utf-8"))
        rows, start, end = [tuple(r) for r in saved["rows"]], saved["start"], saved["end"]
        kugiri = kugiri or saved.get("kugiri", [])
    else:
        if not (a.start and a.end):
            sys.exit("--start と --end を付けてください")
        start, end = a.start, a.end
        spec = importlib.util.spec_from_file_location("shirabe", ROOT / "tools" / "ga4-event-shirabe.py")
        sh = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sh)
        sc = sh.load_sheets_client()
        token = sc.access_token(sc.load_credentials(), scope=sh.SCOPE)
        body = {"dateRanges": [{"startDate": start, "endDate": end}],
                "dimensions": [{"name": "dateHour"}, {"name": "eventName"}, {"name": "hostName"},
                               {"name": "landingPagePlusQueryString"}],
                "metrics": [{"name": "totalUsers"}],
                "dimensionFilter": {"filter": {"fieldName": "eventName", "inListFilter": {
                    "values": ["page_view", "cta_click"]}}},
                "limit": 100000}
        rows = [(d[0], d[1], d[2], d[3], m[0]) for d, m in sh.rows(sh.run_report(token, PROP, body))]
        if a.save:
            pathlib.Path(a.save).write_text(json.dumps({"start": start, "end": end, "kugiri": kugiri, "rows": rows},
                                                       ensure_ascii=False), encoding="utf-8")
    nichi, ce = shuukei(rows, kugiri)
    print(f"# LP→予約ページ と C対E（{start}〜{end}）\n")
    print(hyouji(nichi, ce))
    print("\n※ 数はユーザー数（同じ人が別の日に来ると2回数える）。区切りの時間帯は1時間単位で「後」に入れている")


if __name__ == "__main__":
    main()
