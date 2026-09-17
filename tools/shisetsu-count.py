#!/usr/bin/env python3
"""施設カードの数を、誰が数えても同じになる形で出す。

なぜ要るか（2026-09-18）：
  CMO決定（2026-09-17）で、291件への接触は **①読本の設置のお願い → ②置いてくれた先にだけ清掃の打診**
  の2段に分かれた。②の分母は「読本を置いてくれた先」なので、**それが後から数えられる必要がある。**

  数え方を口頭で決めると、次に数えたときに違う数が出る。ここに固定する。

数え方（このとおりにしか数えない）:
  接触した          ステージが「未接触」でない（対象外も含む。一度でも出したもの）
  生きている接触    ステージが「未接触」でも「対象外…」でもない
  返事があった      反応 が空でない
  設置OK            ステージ が「設置OK」または「稼働中（読取あり）」  ← **②清掃打診の分母**
  読取あり          ステージ が「稼働中（読取あり）」
  対象外            ステージ が「対象外」で始まる（不達・断り）

使い方:
  python3 tools/shisetsu-count.py           # 全体
  python3 tools/shisetsu-count.py --種別    # 種別ごとの内訳も出す
  python3 tools/shisetsu-count.py --設置先  # 設置OKの施設を一覧で出す（②の打診先）
"""
import argparse
import collections
import pathlib
import sys
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import sheets_client as sc  # noqa: E402

SS = "1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64"
RNG = "施設カード_進捗!A13:AF1000"
OK_STAGES = ("設置OK", "稼働中（読取あり）")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--種別", action="store_true", dest="by_kind")
    ap.add_argument("--設置先", action="store_true", dest="list_ok")
    a = ap.parse_args()

    tok = sc.access_token(sc.load_credentials(), "https://www.googleapis.com/auth/spreadsheets.readonly")
    v = sc.call(tok, f"/{SS}/values/{urllib.parse.quote(RNG)}").get("values", [])
    head = v[0]
    ci = {h: i for i, h in enumerate(head)}
    rows = [r + [""] * (len(head) - len(r)) for r in v[1:] if (r + [""])[ci["施設名"]]]

    def stage(r):
        return r[ci["ステージ"]]

    total = len(rows)
    taigai = [r for r in rows if stage(r).startswith("対象外")]
    sesshoku = [r for r in rows if stage(r) != "未接触"]
    ikiteru = [r for r in sesshoku if not stage(r).startswith("対象外")]
    henji = [r for r in ikiteru if r[ci["反応"]].strip()]
    ok = [r for r in rows if stage(r) in OK_STAGES]
    yomi = [r for r in rows if stage(r) == "稼働中（読取あり）"]

    def pct(n, d):
        return f"{n / d * 100:.1f}%" if d else "—"

    # 送信ログと突き合わせて、「機械が送信を確認できた」ぶんを別に数える。
    # 9/14 の「要再確認（完了画面を確認できず）」のように、進捗は接触済でも送信を確認できていない行がある
    log = sc.call(tok, f"/{SS}/values/{urllib.parse.quote('施設カード_送信ログ!A1:M2000')}").get("values", [])
    kakunin = {(r + [""] * 13)[2] for r in log[1:] if len(r) > 9 and str(r[9]).startswith("送信")}
    ik_kakunin = [r for r in ikiteru if r[ci["No"]] in kakunin]

    print(f"リスト全体            {total:>5}")
    print(f"接触した              {len(sesshoku):>5}   （うち対象外 {len(taigai)}：不達・断り）")
    print(f"生きている接触        {len(ikiteru):>5}   ← ①読本の設置のお願いが生きている先")
    print(f"  うち送信を確認済み  {len(ik_kakunin):>5}   （送信ログで「送信」と確認できたもの）")
    print(f"  うち確認できず      {len(ikiteru) - len(ik_kakunin):>5}   ← 届いたか分からない。再送すると二重になる")
    print(f"返事があった          {len(henji):>5}   {pct(len(henji), len(ikiteru))}（生きている接触に対して）")
    print(f"**設置OK**            {len(ok):>5}   {pct(len(ok), len(ikiteru))}   ← **②清掃打診の分母**")
    print(f"読取あり              {len(yomi):>5}   {pct(len(yomi), len(ok))}（設置OKに対して）")

    if a.by_kind:
        print("\n種別ごと")
        print(f"  {'種別':<16}{'全体':>6}{'接触':>6}{'生きて':>7}{'返事':>6}{'設置OK':>8}")
        k_all = collections.Counter(r[ci["種別"]] for r in rows)
        k_se = collections.Counter(r[ci["種別"]] for r in sesshoku)
        k_ik = collections.Counter(r[ci["種別"]] for r in ikiteru)
        k_he = collections.Counter(r[ci["種別"]] for r in henji)
        k_ok = collections.Counter(r[ci["種別"]] for r in ok)
        for k, n in k_all.most_common():
            print(f"  {k:<16}{n:>6}{k_se[k]:>6}{k_ik[k]:>7}{k_he[k]:>6}{k_ok[k]:>8}")

    if a.list_ok:
        print(f"\n設置OK の施設（②清掃の打診先）{len(ok)}件")
        if not ok:
            print("  まだありません")
        for r in ok:
            print(f"  No.{r[ci['No']]:>4}  {r[ci['施設名']][:34]:<36} 種別={r[ci['種別']]:<10} "
                  f"設置日={r[ci['設置日']]:<12} 施設ID={r[ci['施設ID']]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
