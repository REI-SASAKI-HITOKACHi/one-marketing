#!/usr/bin/env python3
"""広告グループ別に「申込・受注・受注額」を並べる（10/9 の継続判定の土台）。

    python3 tools/ad-group-hyou.py 予約_Web.csv
    python3 tools/ad-group-hyou.py 予約_Web.csv \\
        --hiyou A_エアコン=11723 --hiyou B_浴室=8048 --hiyou B_レンジフード=3296 \\
        --ag-name 1234567890=A_エアコン --ag-name 2345678901=B_浴室

**読むだけです。予約_Web も台帳も書き換えません。**

## なぜ要るのか

**Google広告の管理画面が知っているのは「申込が何件か」までです。**
当社は申込1件の金額が 33,660円から10万円超まで開き、**受注するかどうかも申込のあとで決まります。**

| | Google広告で見えるもの | この表で足すもの |
|---|---|---|
| 申込 | ○（ただし計測できたものだけ） | **当社が実際に受けた件数** |
| 受注 | × | **★売上（税込）が入った件数** |
| 受注額 | × | **★売上（税込）の合計** |

**2026-09-27 に、エアコンLPの申込が Google 広告のCVに入っていませんでした。**
**広告の数字だけで判定すると、そのグループは「申込0件」に見えます。**

## 広告グループの見分け方

**LPのURLの `?ag={adgroupid}` が、フォームの hidden 欄 `ag` に入り、予約_Web に残ります。**
`?src=` で「広告かどうか」、`ag` で「どの広告グループか」が分かります。

IDは数字なので、`--ag-name ID=名前` で名前を付けられます（Google広告の管理画面で確かめる）。
付けなければIDのまま出します。

## 予約_Web に `ag` の列が無いとき

**止まって、実際の見出しを表示します。** 黙って「全部 ag 無し」にはしません。
"""

import argparse
import csv
import pathlib
import re
import sys

COLS = {
    "src":    ["src", "流入元", "traffic_src"],
    "ag":     ["ag", "広告グループ", "adgroup"],
    "kagi":   ["注文ID", "order_id", "NetlifyのID"],
    "uriage": ["★売上（税込）", "売上（税込）", "売上"],
}


def pick(heads, cands):
    for c in cands:
        for h in heads:
            if h and h.strip() == c:
                return h
    for c in cands:
        for h in heads:
            if h and c in h:
                return h
    return None


def read_csv(path):
    for enc in ("utf-8-sig", "cp932", "utf-8"):
        try:
            return list(csv.DictReader(path.read_text(encoding=enc).splitlines()))
        except (UnicodeDecodeError, LookupError):
            continue
    sys.exit(f"{path} の文字コードが読めません。")


def yen(s):
    n = re.sub(r"[^\d]", "", s or "")
    return int(n) if n else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("yoyaku", help="予約_Web タブのCSV")
    ap.add_argument("--ag-name", action="append", default=[], metavar="ID=名前",
                    help="広告グループIDに名前を付ける（何度でも）")
    ap.add_argument("--hiyou", action="append", default=[], metavar="名前=円",
                    help="広告グループごとの費用（Google広告の管理画面から）。付けるとCPAも出す")
    ap.add_argument("--kouko-dake", action="store_true",
                    help="src が gads で始まる行だけを数える（既定。付けなくても同じ）")
    ap.add_argument("--zenbu", action="store_true", help="広告以外の申込も並べる")
    args = ap.parse_args()

    path = pathlib.Path(args.yoyaku)
    if not path.exists():
        sys.exit(f"{path} がありません。")
    rows = read_csv(path)
    if not rows:
        sys.exit(f"{path} に行がありません。")
    heads = list(rows[0].keys())
    col = {k: pick(heads, v) for k, v in COLS.items()}
    for need in ("src", "ag", "uriage"):
        if not col[need]:
            print(f"{path} の見出しは次のとおりです：\n", file=sys.stderr)
            for h in heads:
                print("  ・" + str(h), file=sys.stderr)
            sys.exit(f"\n『{COLS[need][0]}』にあたる列が見つかりません。"
                     + ("\n**予約_Web に `ag`（広告グループ）の列を足す必要があります**"
                        "（`tools/booking-inbox.py` が Netlify の送信データから写す）。"
                        if need == "ag" else ""))

    namae = {}
    for x in args.ag_name:
        i, _, n = x.partition("=")
        namae[i.strip()] = n.strip()
    hiyou = {}
    for x in args.hiyou:
        n, _, e = x.partition("=")
        hiyou[n.strip()] = yen(e)

    hyou = {}
    for r in rows:
        src = (r.get(col["src"]) or "").strip()
        if not args.zenbu and not src.startswith("gads"):
            continue
        ag = (r.get(col["ag"]) or "").strip()
        key = namae.get(ag, ag) or f"（ag なし・{src or 'src なし'}）"
        u = yen(r.get(col["uriage"]))
        h = hyou.setdefault(key, {"moushi": 0, "juchu": 0, "gaku": 0})
        h["moushi"] += 1
        if u > 0:
            h["juchu"] += 1
            h["gaku"] += u

    print("# 広告グループ別の申込・受注・受注額\n")
    if not hyou:
        print("**広告経由の申込がありません**（`src` が `gads` で始まる行が0件）。")
        return
    print("| 広告グループ | 申込 | 受注 | 受注額 | 費用 | 申込CPA | 受注CPA | 費用対受注額 |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|")
    tot = {"moushi": 0, "juchu": 0, "gaku": 0, "hiyou": 0}
    for key in sorted(hyou):
        h = hyou[key]
        hy = hiyou.get(key)
        def cpa(n):
            return f"{hy // n:,}円" if hy and n else "—"
        roas = f"{h['gaku'] / hy:.1f}倍" if hy else "—"
        print(f"| {key} | {h['moushi']} | {h['juchu']} | {h['gaku']:,}円 | "
              f"{f'{hy:,}円' if hy else '—'} | {cpa(h['moushi'])} | {cpa(h['juchu'])} | {roas} |")
        for k in ("moushi", "juchu", "gaku"):
            tot[k] += h[k]
        tot["hiyou"] += hy or 0
    th, tm, tj, tg = tot["hiyou"], tot["moushi"], tot["juchu"], tot["gaku"]
    k_hiyou = f"**{th:,}円**" if th else "—"
    k_mcpa = f"{th // tm:,}円" if th and tm else "—"
    k_jcpa = f"{th // tj:,}円" if th and tj else "—"
    k_roas = f"{tg / th:.1f}倍" if th else "—"
    print(f"| **合計** | **{tm}** | **{tj}** | **{tg:,}円** | {k_hiyou} | {k_mcpa} | {k_jcpa} | {k_roas} |")

    kakuteimae = sum(1 for k in hyou if k.startswith("（ag なし"))
    print("\n> **受注は「★売上（税込）が入った件数」です。** 施工前・入金前の申込は、まだ受注に数えていません。")
    print("> **件数が少ないうちは、1件の違いでCPAが大きく動きます。** 10/9 の判定では件数と一緒に読んでください。")
    if kakuteimae:
        print("> ⚠️ `ag` が空の広告経由の申込があります。**`?ag=` の受け側が入る前（9/28 より前）の申込**の可能性があります。")


if __name__ == "__main__":
    main()
