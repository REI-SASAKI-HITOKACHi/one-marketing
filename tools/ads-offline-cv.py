#!/usr/bin/env python3
"""受注が確定した申込を、Google広告へ戻すためのCSVを作る（アップロードはしない）。

    python3 tools/ads-offline-cv.py --yoyaku 予約_Web.csv --daicho 9月_売上.csv
    python3 tools/ads-offline-cv.py --yoyaku … --daicho … --out data/ads-offline-2026-10.csv

**既定は下見（dry-run）です。** `--out` を付けたときだけファイルを書きます。
**アップロードはしません。** 管理画面に入る操作は、この道具の外です。

## 何のためのものか

**サンクスページのコンバージョンだけを見ていると、申込1件はどれも同じ「1」に見えます。**
当社は申込から入金まで2〜4週間かかり、**1件の金額は 33,660円から10万円超まで開きます。**

**この状態で自動入札に任せると、「申し込むだけの人」を集めるほうへ最適化していきます。**

**実際にいくらで成約したかを、あとからGoogle広告へ戻すのがオフラインインポートです。**
そのために `gclid`（広告のクリックID）をフォームに残してあります
（`docs/広告-コンバージョン計測.md` 第5章）。

## 突き合わせ方

```
予約_Web タブ            台帳（◯月_売上）
  order_id  ←──────────→  order_id
  gclid                    施工日・売上
```

**`order_id` が唯一の鍵です。** 申込のときにLPが採番して（`OH-YYYYMMDD-<LP>-XXXX`）、
Netlify Forms の受信内容に残り、予約_Web タブへ入ります。

## 出さないもの

**氏名・電話番号・住所は、1文字も出しません。**
CSVに入るのは `gclid` ／ コンバージョン名 ／ 日時 ／ 金額 ／ 通貨 の5つだけです。

## ⚠️ 最初の1回だけ、列名を突き合わせてください

**Google広告の管理画面からテンプレートCSVを落として、1行目の列名を見比べてください。**
こちらは公開されている一般的な形に合わせていますが、**画面の版で細部が変わることがあります。**
`--header` で列名を差し替えられるようにしてあります。
"""

import argparse
import csv
import datetime as dt
import pathlib
import re
import sys

# Google広告のオフラインCVインポートの列。
# **最初の1回だけ、管理画面のテンプレートと見比べること**（--header で変えられる）。
HEADER = ["Google Click ID", "Conversion Name", "Conversion Time",
          "Conversion Value", "Conversion Currency"]

# クリックから何日を過ぎるとインポートできないか。
# コンバージョンアクション側の「クリックスルー計測期間」に合わせる（当社は90日）。
KIGEN_NICHI = 90

# 列の見出しは人が付けるので揺れる。候補を並べて探し、
# 見つからなければ**実際の見出しを表示して止める**。黙って空を返さない。
COLS = {
    "order_id": ["order_id", "注文ID", "注文番号", "受付番号"],
    "gclid":    ["gclid", "Google Click ID", "クリックID"],
    "moushikomi": ["申込日", "申込日時", "受信日時", "作成日"],
    "sekou":    ["施工日", "作業日", "完了日", "施工日付"],
    "uriage":   ["売上", "売上金額", "請求額", "金額", "合計"],
}


def pick(headers, cands):
    for c in cands:
        for h in headers:
            if h and h.strip() == c:
                return h
    for c in cands:
        for h in headers:
            if h and c in h:
                return h
    return None


def read_csv(path: pathlib.Path) -> list:
    for enc in ("utf-8-sig", "cp932", "utf-8"):
        try:
            return list(csv.DictReader(path.read_text(encoding=enc).splitlines()))
        except (UnicodeDecodeError, LookupError):
            continue
    sys.exit(f"{path} の文字コードが読めません。UTF-8 か Shift_JIS で保存し直してください。")


def need(rows, path, *keys):
    """必要な列を探す。1つでも無ければ、実際の見出しを出して止める。"""
    if not rows:
        sys.exit(f"{path} に行がありません。")
    heads = list(rows[0].keys())
    col = {}
    for k in keys:
        c = pick(heads, COLS[k])
        if not c:
            print(f"{path} の見出しは次のとおりです：\n", file=sys.stderr)
            for h in heads:
                print("  ・" + str(h), file=sys.stderr)
            sys.exit(f"\n『{COLS[k][0]}』にあたる列が見つかりません。"
                     f"\nこのスクリプトの COLS に、実際の見出しを足してください。")
        col[k] = c
    return col


def parse_date(s):
    s = (s or "").strip()
    m = re.search(r"(\d{4})[/\-年](\d{1,2})[/\-月](\d{1,2})", s)
    if not m:
        return None
    d = dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    t = re.search(r"(\d{1,2}):(\d{2})", s)
    return dt.datetime(d.year, d.month, d.day,
                       int(t.group(1)) if t else 12, int(t.group(2)) if t else 0)


def parse_yen(s):
    n = re.sub(r"[^\d]", "", (s or ""))
    return int(n) if n else 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--yoyaku", required=True, help="予約_Web タブのCSV（order_id と gclid）")
    ap.add_argument("--daicho", required=True, help="台帳のCSV（order_id・施工日・売上）")
    ap.add_argument("--name", default="受注（オフライン）",
                    help="Google広告のコンバージョンアクション名。"
                         "**タグで撃っている『申込』と同じ名前にしないこと**")
    ap.add_argument("--out", help="書き出し先。付けないと下見だけで何も書かない")
    ap.add_argument("--timezone", default="Asia/Tokyo")
    ap.add_argument("--header", help="列名をカンマ区切りで差し替える（管理画面の版に合わせるとき）")
    ap.add_argument("--kijun", help="今日の日付をこれにする（YYYY-MM-DD。検算用）")
    args = ap.parse_args()

    kyou = dt.date.fromisoformat(args.kijun) if args.kijun else dt.date.today()
    header = [h.strip() for h in args.header.split(",")] if args.header else HEADER

    yp, dp = pathlib.Path(args.yoyaku), pathlib.Path(args.daicho)
    for p in (yp, dp):
        if not p.exists():
            sys.exit(f"{p} がありません。")

    yrows, drows = read_csv(yp), read_csv(dp)
    ycol = need(yrows, yp, "order_id", "gclid", "moushikomi")
    dcol = need(drows, dp, "order_id", "sekou", "uriage")

    # 予約側：order_id → (gclid, 申込日時)
    moushi = {}
    for r in yrows:
        oid = (r.get(ycol["order_id"]) or "").strip()
        if oid:
            moushi[oid] = ((r.get(ycol["gclid"]) or "").strip(),
                           parse_date(r.get(ycol["moushikomi"])))

    deta, nashi_gclid, nashi_oid, kigengire, zero = [], 0, 0, [], 0
    for r in drows:
        oid = (r.get(dcol["order_id"]) or "").strip()
        if not oid:
            continue
        if oid not in moushi:
            nashi_oid += 1
            continue
        gclid, mdt = moushi[oid]
        if not gclid:
            nashi_gclid += 1
            continue
        uriage = parse_yen(r.get(dcol["uriage"]))
        if uriage <= 0:
            zero += 1
            continue
        sekou = parse_date(r.get(dcol["sekou"]))
        if sekou is None:
            continue
        # クリックからの日数。90日を超えるとGoogle広告が受け取らない
        keika = (sekou.date() - mdt.date()).days if mdt else None
        if keika is not None and keika > KIGEN_NICHI:
            kigengire.append((oid, keika, uriage))
            continue
        deta.append({
            header[0]: gclid,
            header[1]: args.name,
            header[2]: sekou.strftime("%Y-%m-%d %H:%M:%S+09:00"),
            header[3]: str(uriage),
            header[4]: "JPY",
        })

    print(f"# オフラインCVインポート用CSV（{kyou}）\n")
    print(f"| | 件数 |")
    print(f"|---|---:|")
    print(f"| 台帳の行 | {len(drows):,} |")
    print(f"| **戻せる（CSVに入る）** | **{len(deta):,}** |")
    print(f"| 予約_Web に無い注文ID | {nashi_oid:,} |")
    print(f"| gclid が空（広告経由でない） | {nashi_gclid:,} |")
    print(f"| 売上が0または空 | {zero:,} |")
    print(f"| **クリックから{KIGEN_NICHI}日超（戻せない）** | **{len(kigengire):,}** |")

    if deta:
        gokei = sum(int(d[header[3]]) for d in deta)
        print(f"\n**戻す金額の合計 {gokei:,}円**"
              f"（1件あたり平均 {gokei // len(deta):,}円）")

    if kigengire:
        print(f"\n> ## ⚠️ {len(kigengire)}件が{KIGEN_NICHI}日を過ぎていて戻せません\n>")
        for oid, k, u in sorted(kigengire, key=lambda x: -x[1])[:10]:
            print(f"> ・`{oid}` … 申込から{k}日／{u:,}円")
        print(">\n> **インポートの間隔が空きすぎています。**"
              f"**{KIGEN_NICHI}日を超えると、いくらで成約しても戻せません。**")

    if not args.out:
        print("\n---\n**下見だけです。何も書いていません。**"
              "\n書き出すには `--out <ファイル名>` を付けてください。")
        return

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        f.write(f"Parameters:TimeZone={args.timezone}\n")
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        for d in deta:
            w.writerow(d)
    print(f"\n**{out} に {len(deta)}件 書きました。**")
    print("\n## 次にやること（人の手）\n")
    print("1. **列名を、管理画面のテンプレートと見比べる**（最初の1回だけ）")
    print(f"2. Google広告 → [目標] → [コンバージョン] → [アップロード] → このファイルを選ぶ")
    print(f"3. **必ず「プレビュー」で確かめてから適用する。**"
          "エラー行が出たら、直してからもう一度")
    print(f"4. アップロードしたら、**このファイルを `data/` に残しておく。**"
          "二重に上げないための控えになります")
    print("\n> **この道具はアップロードしません。** 管理画面に入る操作は人の手です。")


if __name__ == "__main__":
    main()
