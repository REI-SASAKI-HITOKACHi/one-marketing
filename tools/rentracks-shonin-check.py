#!/usr/bin/env python3
"""レントラックスの保留中の成果から、**もうすぐ自動承認になるもの**を洗い出す。

    python3 tools/rentracks-shonin-check.py 注文リスト.csv
    python3 tools/rentracks-shonin-check.py 注文リスト.csv --kijun 2026-10-01

## なぜ要るか

**成果の発生から45日を過ぎると、入金が確認できていなくても自動で承認になります**
（2026-09-12 先方回答）。キャンセルでも未入金でも、そのまま報酬が確定します。

当社は申込から入金まで **2〜4週間**かかるので、45日はぎりぎりです。
**見落とすと、やらなかった工事に3,000円を払います。**

**承認APIはありません（CSVの取り込みのみ）。** だから「管理画面からCSVを落とす →
これに食わせる → 出てきたものを却下する」という手作業の運用になります。

## いつ回すか

**毎週月曜。** 期限は45日ですが、**このツールの既定は38日**です。
月曜にしか見ないので、**7日の緩衝**がないと、38日の週に見落とした分は
次に見るときには45日を過ぎています。

## このツールが知らないこと

**入金が済んでいるかどうかは分かりません。** レントラックスのCSVには当社の入金情報が
入っていないからです。**出てくるのは「入金を確認すべき一覧」**で、
承認するか却下するかを決めるのは人です。

備考欄には当社の注文ID（`OH-YYYYMMDD-...`）が入っているので、それで台帳と突き合わせます。
"""

import argparse
import csv
import datetime as dt
import pathlib
import re
import sys

KIGEN = 45      # 先方の自動承認までの日数
KIJUN = 38      # こちらが却下を決める日数（7日の緩衝）

# CSVの見出しは先方の仕様で、こちらで決められない。
# 実物を見ずに1つに決め打ちすると、名前が違ったときに黙って空を返す。
# そこで候補を並べて探し、**見つからなければ見出しを表示して止める**。
COLS = {
    "hassei":  ["成果発生日", "発生日", "売上日時", "売上日", "成果日時", "成果発生日時"],
    "joutai":  ["状況", "ステータス", "承認状況", "状態"],
    "bikou":   ["備考", "備考1", "注文番号", "オーダーID", "order_id"],
    "bangou":  ["注文ID", "成果ID", "No", "NO", "番号", "注文番号"],
    "houshuu": ["報酬額", "報酬", "金額", "成果報酬"],
}
HORYU = ("保留", "未承認", "未確定")


def pick(headers, cands):
    for c in cands:
        for h in headers:
            if h and h.strip() == c:
                return h
    for c in cands:                     # 部分一致も見る（「成果発生日時」など）
        for h in headers:
            if h and c in h:
                return h
    return None


def parse_date(s: str):
    """`2026/09/15 11:16` `2026-09-15` `09/15 11:16` などを日付にする。"""
    s = (s or "").strip()
    m = re.search(r"(\d{4})[/\-年](\d{1,2})[/\-月](\d{1,2})", s)
    if m:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", help="管理画面の「注文リスト」から落としたCSV")
    ap.add_argument("--kijun", type=int, default=KIJUN,
                    help=f"何日を超えたら却下の対象にするか（既定 {KIJUN}日）")
    ap.add_argument("--hiduke", help="今日の日付をこれにする（YYYY-MM-DD。検算用）")
    args = ap.parse_args()

    path = pathlib.Path(args.csv)
    if not path.exists():
        sys.exit(f"{path} がありません。")

    kyou = dt.date.fromisoformat(args.hiduke) if args.hiduke else dt.date.today()

    # 先方のCSVは Shift_JIS のことが多い。UTF-8 も通るように両方試す。
    for enc in ("utf-8-sig", "cp932", "utf-8"):
        try:
            rows = list(csv.DictReader(path.read_text(encoding=enc).splitlines()))
            break
        except (UnicodeDecodeError, LookupError):
            continue
    else:
        sys.exit("CSVの文字コードが読めません。UTF-8 か Shift_JIS で保存し直してください。")

    if not rows:
        sys.exit("CSVに行がありません。")

    heads = list(rows[0].keys())
    col = {k: pick(heads, v) for k, v in COLS.items()}

    for need in ("hassei", "joutai"):
        if not col[need]:
            print("見出しが読み取れませんでした。CSVの見出しは次のとおりです：\n", file=sys.stderr)
            for h in heads:
                print("  ・" + str(h), file=sys.stderr)
            sys.exit(f"\n『{COLS[need][0]}』にあたる列が見つかりません。"
                     f"\nこのスクリプトの COLS に、実際の見出しを足してください。")

    taishou, horyu_kei, yomenai = [], 0, 0
    for r in rows:
        joutai = (r.get(col["joutai"]) or "").strip()
        if not any(h in joutai for h in HORYU):
            continue
        horyu_kei += 1
        hi = parse_date(r.get(col["hassei"]) or "")
        if hi is None:
            yomenai += 1
            continue
        keika = (kyou - hi).days
        if keika >= args.kijun:
            taishou.append((keika, hi, r))

    print(f"# レントラックス 承認期限の点検（{kyou}）\n")
    print(f"保留中 **{horyu_kei}件**／うち発生から **{args.kijun}日**を超えたもの "
          f"**{len(taishou)}件**\n")

    if yomenai:
        print(f"> ⚠️ **{yomenai}件は発生日が読み取れませんでした。**"
              f"（列『{col['hassei']}』）**手で見てください。**\n")

    if not taishou:
        print("**今週、却下を決めなければならないものはありません。**")
    else:
        print("| 経過 | 自動承認まで | 発生日 | 注文ID（備考） | 報酬 |")
        print("|---:|---:|---|---|---:|")
        # 経過日数だけで並べる。同じ日の成果が複数あると、
        # 3つ目の要素（行の dict）まで比べにいって落ちる
        for keika, hi, r in sorted(taishou, key=lambda x: -x[0]):
            nokori = KIGEN - keika
            bikou = (r.get(col["bikou"]) or "").strip() if col["bikou"] else ""
            hou = (r.get(col["houshuu"]) or "").strip() if col["houshuu"] else ""
            nokori_s = f"**あと{nokori}日**" if nokori > 0 else "**期限切れ**"
            print(f"| {keika}日 | {nokori_s} | {hi} | `{bikou}` | {hou} |")

        print(f"""
## やること

**上の注文IDを台帳と突き合わせ、入金が確認できないものを管理画面で却下してください。**

| 台帳の状態 | どうするか |
|---|---|
| 施工完了・入金済み | **承認** |
| キャンセル／エリア外／日程不成立／2回目以降／未入金 | **却下** |
| **まだ施工前・入金待ち** | **却下**。{KIGEN}日で自動承認になるほうが損が大きい |

> **判断がつかないものは却下してください。** 却下したあとに入金が確認できた場合、
> 先方に連絡すれば戻せます。**自動承認されたものは戻せません。**
""")

    print("\n---\n"
          f"> 自動承認は発生から **{KIGEN}日**（2026-09-12 先方回答）。"
          f"このツールの既定は **{args.kijun}日**で、差の {KIGEN - args.kijun} 日は"
          "「月曜にしか見ない」ぶんの緩衝です。\n"
          "> **入金の有無はこのツールには分かりません。** 台帳と突き合わせるのは人の仕事です。")


if __name__ == "__main__":
    main()
