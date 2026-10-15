#!/usr/bin/env python3
"""経路別に「LP表示 → 予約ページ表示 → 入力開始 → 申込」の4段を1表にする（11月ネット10件の作戦用）。

    python3 tools/funnel-keiro.py --start 2026-10-01 --end 2026-10-14
    python3 tools/funnel-keiro.py --start 2026-10-01 --end 2026-10-14 --yoyaku 予約_Web.csv
    python3 tools/funnel-keiro.py --json 保存したGA4の結果.json      # 鍵の無い環境で表だけ作り直す

**読むだけです。** GA4 Data API（鍵は tools/sheets_client.py）と、任意で予約_Web の CSV を読む。

## 経路の見分け方

GA4 のセッションの最初のページの URL（`landingPagePlusQueryString`）から `?src=` を取り出して分ける。
予約ページのイベントには `traffic_src` が付かないことがある（web-inflow 10/8 の指摘）が、
**同じセッションの最初のページの src は予約ページのイベントにも付いて回る**ので、こちらで分ける。
src が無いセッションは、広告のクリックID（gclid 等）が URL にあれば「広告」、無ければ「直接・その他」。

| 経路 | src |
|---|---|
| 広告 | `gads_*`（または URL に gclid／gbraid／wbraid） |
| SNS | `fb*`・`ig*` |
| ブログ | `blog*` |
| SMS | `sms*` |
| GBP | `gbp*` |
| 直接・その他 | それ以外（`direct`、src 無し、qr、teikei_* など） |

## 4段の定義

| 段 | GA4 |
|---|---|
| LP表示 | `page_view`（lp.onehitter.jp） |
| 予約ページ表示 | `page_view`（yoyaku.onehitter.jp） |
| 入力開始 | `booking_start`（予約ページで最初に触った）＋ `form_start`（LP内フォーム） |
| 申込 | `generate_lead`（LPの完了ページ・予約ページの完了画面） |

- 数はイベントのユーザー数を、最初のページごとに足したもの（同じ人が別のセッションで来ると2回数える。少し多めに出る）
- **form_start は 10/9 14時まで2倍に数えていた**（GA4 の「フォームの操作」との重複）。10/9 より前を含む期間では入力開始が多めに出る
- `--yoyaku` を付けると、申込の段に予約_Web の件数（src 列で同じ経路に分けたもの）も並べる。**判定には予約_Web の方を使う**（GA4 はブロッカー等で取りこぼす）
"""

import argparse
import csv
import datetime
import importlib.util
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PROP = "381320625"

KEIRO = ["広告", "SNS", "ブログ", "SMS", "GBP", "直接・その他"]
DAN = ["LP表示", "予約ページ表示", "入力開始", "申込"]


def keiro_of_src(src, url=""):
    s = (src or "").lower()
    if s.startswith("gads") or (not s and re.search(r"[?&](gclid|gbraid|wbraid)=", url or "")):
        return "広告"
    if s.startswith(("fb", "ig")):
        return "SNS"
    if s.startswith("blog"):
        return "ブログ"
    if s.startswith("sms"):
        return "SMS"
    if s.startswith("gbp"):
        return "GBP"
    return "直接・その他"


def src_of_url(url):
    m = re.search(r"[?&]src=([^&#]*)", url or "")
    return m.group(1) if m else ""


def dan_of(event, host):
    host = (host or "").lower()
    if event == "page_view" and host.startswith("lp."):
        return "LP表示"
    if event == "page_view" and host.startswith("yoyaku."):
        return "予約ページ表示"
    if event in ("booking_start", "form_start"):
        return "入力開始"
    if event == "generate_lead":
        return "申込"
    return None


def shuukei(ga4_rows):
    """ga4_rows: [(eventName, hostName, landingPagePlusQueryString, users)]"""
    hyou = {k: {d: 0 for d in DAN} for k in KEIRO}
    for ev, host, landing, n in ga4_rows:
        d = dan_of(ev, host)
        if not d:
            continue
        k = keiro_of_src(src_of_url(landing), landing)
        hyou[k][d] += n
    return hyou


def yoyaku_web(path, start, end):
    out = {k: 0 for k in KEIRO}
    text = None
    for enc in ("utf-8-sig", "cp932", "utf-8"):
        try:
            text = pathlib.Path(path).read_text(encoding=enc)
            break
        except UnicodeDecodeError:
            continue
    for r in csv.DictReader(text.splitlines()):
        src = (r.get("src") or r.get("流入元") or "").strip()
        when = (r.get("受信日時") or "").strip()[:10]
        if when and not (start <= when <= end):
            continue
        kubun = (r.get("状態の区分") or "").strip()
        if kubun in ("空送信",):
            continue
        out[keiro_of_src(src)] += 1
    return out


def wari(a, b):
    return f"{a / b * 100:.0f}%" if b else "—"


def hyouji(hyou, yw=None):
    lines = ["| 経路 | LP表示 | 予約ページ表示 | 入力開始 | 申込（GA4） |" + (" 申込（予約_Web） |" if yw else ""),
             "|---|--:|--:|--:|--:|" + ("--:|" if yw else "")]
    for k in KEIRO:
        h = hyou[k]
        mae = h["LP表示"]
        yy = h["予約ページ表示"]
        row = (f"| {k} | {h['LP表示']} | {yy}（{wari(yy, mae)}） | "
               f"{h['入力開始']}（{wari(h['入力開始'], yy or mae)}） | {h['申込']}（{wari(h['申込'], h['入力開始'])}） |")
        if yw:
            row += f" {yw[k]} |"
        lines.append(row)
    lines.append("")
    lines.append("（ ）内は、ひとつ前の段からの通過率。入力開始は予約ページ表示に対して（予約ページ表示が0なら LP表示に対して）")
    return "\n".join(lines)


def ochi(hyou):
    """いちばん大きく落ちている（経路, 段, 通過率, 母数）。母数10未満は除く。"""
    kouho = []
    for k in KEIRO:
        h = hyou[k]
        steps = [("LP表示→予約ページ表示", h["LP表示"], h["予約ページ表示"]),
                 ("予約ページ表示→入力開始", h["予約ページ表示"], h["入力開始"]),
                 ("入力開始→申込", h["入力開始"], h["申込"])]
        for name, a, b in steps:
            if a >= 10:
                kouho.append((a - b, k, name, b / a, a))
    if not kouho:
        return None
    kouho.sort(reverse=True)
    lost, k, name, r, a = kouho[0]
    return k, name, r, a, lost


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start")
    ap.add_argument("--end")
    ap.add_argument("--yoyaku", help="予約_Web の CSV（src・受信日時・状態の区分 の列）")
    ap.add_argument("--json", help="GA4 の結果を保存したもの（--save で作る）。鍵の無い環境用")
    ap.add_argument("--save", help="GA4 の結果をこのファイルに保存する（個人情報は含まない）")
    args = ap.parse_args()

    if args.json:
        saved = json.loads(pathlib.Path(args.json).read_text(encoding="utf-8"))
        rows_ = [tuple(r) for r in saved["rows"]]
        start, end = saved["start"], saved["end"]
    else:
        if not (args.start and args.end):
            sys.exit("--start と --end を付けてください（例 2026-10-01 2026-10-14）")
        start, end = args.start, args.end
        spec = importlib.util.spec_from_file_location("shirabe", ROOT / "tools" / "ga4-event-shirabe.py")
        sh = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(sh)
        sc = sh.load_sheets_client()
        token = sc.access_token(sc.load_credentials(), scope=sh.SCOPE)
        body = {
            "dateRanges": [{"startDate": start, "endDate": end}],
            "dimensions": [{"name": "eventName"}, {"name": "hostName"}, {"name": "landingPagePlusQueryString"}],
            "metrics": [{"name": "totalUsers"}],
            "dimensionFilter": {"filter": {"fieldName": "eventName", "inListFilter": {
                "values": ["page_view", "booking_start", "form_start", "generate_lead"]}}},
            "limit": 100000,
        }
        res = sh.run_report(token, PROP, body)
        rows_ = [(d[0], d[1], d[2], m[0]) for d, m in sh.rows(res)]
        if args.save:
            pathlib.Path(args.save).write_text(json.dumps({"start": start, "end": end, "rows": rows_},
                                                          ensure_ascii=False), encoding="utf-8")

    hyou = shuukei(rows_)
    yw = yoyaku_web(args.yoyaku, start, end) if args.yoyaku else None
    print(f"# 経路別の4段（{start}〜{end}）\n")
    print(hyouji(hyou, yw))
    o = ochi(hyou)
    print("\n## いちばん大きく落ちている所\n")
    if o:
        k, name, r, a, lost = o
        print(f"**{k} の「{name}」**：{a} 人のうち通過 {r * 100:.0f}%（{lost} 人がここで離れている）")
    else:
        print("母数が10人以上の段がありません。")


if __name__ == "__main__":
    main()
