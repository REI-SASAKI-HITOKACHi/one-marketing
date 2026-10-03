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

## 学習版かどうか（2026-09-30 追加）

**9/30 に学習版LP 4本を出し、広告を今のLPと半々に分けて比べます。**
**`src` は両方とも同じ（例：どちらも `gads_aircon`）なので、`src` では分けられません。**
分けるのは、フォームの hidden 欄 `lp`（例：`aircon-c`）か、フォーム名（例：`reserve-aircon-c`）です。
予約_Web にどちらかの列があれば、広告グループごとに「今の版／学習版」の2行に分けて出します。
**どちらも無ければ分けずに出し、そのことを表の下に書きます。**

費用は、Google広告のテスト画面に「元の広告」と「バリエーション」に分けて出ます。
`--hiyou A_エアコン:今の版=5000 --hiyou A_エアコン:学習版=5200` のように、版ごとに渡してください。

## 増額の条件（2026-10-03 オーナー承認の条件。実行は嶺さんに確認してから）

**版ごとに「クリック100回で申込5件」**。`--click A_エアコン:学習版=120` のように版ごとのクリック数を渡すと、
「増額条件」の列に ○／×／クリック不足 を出す。
100回を超えたら、同じ確からしさ（送信率の片側80%下限が 2.73% 以上）で必要件数を数え直す（150回なら7件）。

## 予約ページ（予約カレンダー）経由の申込

`src=gads_*` で予約ページに着いた申込も数える（`src` で広告と分かるため）。
**ただし 10/3 時点の予約ページは、`ag` と「どのLPから来たか」を受け取っていない。** その行は
広告グループが「（ag なし）」、版が「（予約ページ・版不明）」で出る。直るまでは、版の比較に入れられない。

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
    "lp":     ["lp", "LP", "フォーム名", "form-name", "form_name"],
}

# 学習版LP（2026-09-30 本番公開）。それ以外の LP は「今の版」
GAKUSHU = {"aircon-c", "aircon-d", "mizumawari-b", "nenmatsu-b"}


HIKKAKU_CPA = 9600      # 増額の許容CPA（planning）
HIKKAKU_CPC = 262       # 9/20〜27 の平均クリック単価
SAITEI_CLICK = 100


def kagen(k, n, conf=0.8):
    """送信率の片側 conf 下限（Clopper-Pearson）。"""
    from math import comb
    if k == 0:
        return 0.0
    lo, hi = 0.0, 1.0
    for _ in range(60):
        m = (lo + hi) / 2
        ue = sum(comb(n, i) * m ** i * (1 - m) ** (n - i) for i in range(k, n + 1))
        if ue > 1 - conf:
            hi = m
        else:
            lo = m
    return lo


def zouka_hantei(moushi, click):
    """増額条件（版ごとにクリック100で申込5件）の当否。"""
    if click is None:
        return "—"
    if click < SAITEI_CLICK:
        return f"クリック不足（{click}/{SAITEI_CLICK}）"
    return "○ 満たす" if kagen(moushi, click) >= HIKKAKU_CPC / HIKKAKU_CPA else "× 満たさない"


def ban(lp_value):
    """lp 欄またはフォーム名から (版, LP名) を返す。読めなければ ('', '')。"""
    v = (lp_value or "").strip()
    if v.startswith("reserve-"):
        v = v[len("reserve-"):]
    if not v:
        return "", ""
    if v == "yoyaku":
        return "（予約ページ・版不明）", "yoyaku"
    return ("学習版" if v in GAKUSHU else "今の版"), v


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
    ap.add_argument("--click", action="append", default=[], metavar="名前:版=回",
                    help="版ごとのクリック数（Google広告のテスト画面から）。付けると増額条件の当否を出す")
    ap.add_argument("--kotei", action="append", default=[], metavar="注文ID=名前:版:LP",
                    help="経路を人が判断した申込を、指定の広告グループ・版に入れる（例：LINE経由で予約した広告客）")
    ap.add_argument("--chuki", action="append", default=[], metavar="文",
                    help="表の下に足す注記（何度でも）")
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
    click = {}
    for x in args.click:
        n, _, e = x.partition("=")
        click[n.strip()] = yen(e)
    hiyou = {}
    for x in args.hiyou:
        n, _, e = x.partition("=")
        hiyou[n.strip()] = yen(e)

    kotei = {}
    for x in args.kotei:
        i, _, rest = x.partition("=")
        kotei[i.strip()] = tuple((rest.split(":") + ["", "", ""])[:3])

    hyou = {}
    for r in rows:
        src = (r.get(col["src"]) or "").strip()
        kid = (r.get(col["kagi"]) or "").strip() if col["kagi"] else ""
        if kid in kotei:
            n, b, lpname = kotei[kid]
            key = (n, b or "—", (lpname or "—") + "＊")
            u = yen(r.get(col["uriage"]))
            h = hyou.setdefault(key, {"moushi": 0, "juchu": 0, "gaku": 0})
            h["moushi"] += 1
            if u > 0:
                h["juchu"] += 1
                h["gaku"] += u
            continue
        if not args.zenbu and not src.startswith("gads"):
            continue
        ag = (r.get(col["ag"]) or "").strip()
        key = namae.get(ag, ag) or f"（ag なし・{src or 'src なし'}）"
        b, lpname = ban(r.get(col["lp"])) if col["lp"] else ("", "")
        if col["lp"]:
            key = (key, b or "（不明）", lpname or "—")
        else:
            key = (key, "—", "—")
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
    print("| 広告グループ | 版 | LP | 申込 | 受注 | 受注額 | 費用 | 申込CPA | 受注CPA | 費用対受注額 | 増額条件 |")
    print("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|")
    tot = {"moushi": 0, "juchu": 0, "gaku": 0, "hiyou": 0}
    for key in sorted(hyou):
        h = hyou[key]
        ag_, b, lpname = key
        hy = hiyou.get(f"{ag_}:{b}") if col["lp"] else hiyou.get(ag_)
        def cpa(n):
            return f"{hy // n:,}円" if hy and n else "—"
        roas = f"{h['gaku'] / hy:.1f}倍" if hy else "—"
        print(f"| {ag_} | {b} | {lpname} | {h['moushi']} | {h['juchu']} | {h['gaku']:,}円 | "
              f"{f'{hy:,}円' if hy else '—'} | {cpa(h['moushi'])} | {cpa(h['juchu'])} | {roas} | "
              f"{zouka_hantei(h['moushi'], click.get(f'{ag_}:{b}'))} |")
        for k in ("moushi", "juchu", "gaku"):
            tot[k] += h[k]
        tot["hiyou"] += hy or 0
    th, tm, tj, tg = tot["hiyou"], tot["moushi"], tot["juchu"], tot["gaku"]
    k_hiyou = f"**{th:,}円**" if th else "—"
    k_mcpa = f"{th // tm:,}円" if th and tm else "—"
    k_jcpa = f"{th // tj:,}円" if th and tj else "—"
    k_roas = f"{tg / th:.1f}倍" if th else "—"
    print(f"| **合計** | | | **{tm}** | **{tj}** | **{tg:,}円** | {k_hiyou} | {k_mcpa} | {k_jcpa} | {k_roas} | |")

    if click:
        print("> **増額条件**：版ごとにクリック100回で申込5件（10/3 オーナー承認の条件）。"
              "**満たしても、増額の前に嶺さんに確認する**（10/3 第5回MTGの決定）。")
    if any(k[1] == "（予約ページ・版不明）" for k in hyou):
        print("> ⚠️ 予約ページ経由の申込は、どの版のLPから来たかが分からないため、版の比較に入れていない。")
    if kotei:
        print("> ＊ の行は、経路を人が判断して入れた申込（`--kotei`）。広告のクリックIDが無いので、オフラインCVの取り込みには入らない。")
    for c in args.chuki:
        print("> " + c)
    kakuteimae = sum(1 for k in hyou if k[0].startswith("（ag なし"))
    print("\n> **受注は「★売上（税込）が入った件数」です。** 施工前・入金前の申込は、まだ受注に数えていません。")
    print("> **件数が少ないうちは、1件の違いでCPAが大きく動きます。** 10/9 の判定では件数と一緒に読んでください。")
    if not col["lp"]:
        print("> ⚠️ 予約_Web に `lp` もフォーム名の列も無いため、**今の版と学習版を分けていません。**"
              "（`src` は両方同じなので、`src` では分けられません）")
    elif any(k[1] == "（不明）" for k in hyou):
        print("> ⚠️ 版が「（不明）」の行は、`lp`／フォーム名の欄が空です。")
    if col["lp"] and args.hiyou and not any(":" in x.split("=")[0] for x in args.hiyou):
        print("> ⚠️ 費用が広告グループ単位で渡されたため、版ごとのCPAは出していません。"
              "`--hiyou 名前:今の版=円 --hiyou 名前:学習版=円` で渡してください。")
    if kakuteimae:
        print("> ⚠️ `ag` が空の広告経由の申込があります。**`?ag=` の受け側が入る前（9/28 より前）の申込**の可能性があります。")


if __name__ == "__main__":
    main()
