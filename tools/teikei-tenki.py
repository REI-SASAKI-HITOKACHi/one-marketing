#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""【毎月更新】リピート/業務提携 タブへ 2026年5〜8月の業務提携売上を転記する。

## なぜこれが要るか

『【毎月更新】リピート/業務提携』タブが 2026年4月で更新が止まっている（planning 20260914-05-cmo）。
提携先ごとの実績が出ないと、週次・月次の数字も 2027 の提携目標も置けない。

## やること（この順）

  1. タブを複製して控えを作る
     （Drive のコピーはサービスアカウントに保存容量が無く 403 になるため、タブ複製で代える）
  2. 売上23〜32 の列を10組ぶん挿入する（株式会社レジェンド様が22組を使い切っているため）
  3. 新しい列の見出しと表示形式（日付／通貨）を整える
  4. 各社の行に、空いている最初の組から 日付・売上 を書き足す（**既存の値は触らない**）
  5. 合計（=F+H+…）の式を新しい列まで伸ばす
  6. 平均単価の割る数が手打ちで実態と合っていないので、日付の個数を数える式にする
  7. インテリアエージェントを新規行として足す

## 使い方

    . ~/.config/one-hitter/line.env
    python3 tools/teikei-tenki.py                  # 計画を出すだけ（既定）
    python3 tools/teikei-tenki.py --confirm WRITE  # 実際に書き込む

## 転記しなかったもの（判断が要るので保留）

  - 2026/06/13 の「加藤さんご紹介」5件（¥104,015）… 提携先ではなく個人からの紹介
  - 2026/06/17・08/02 の「山口様」2件（¥240,740）… 提携先を特定できない

出所はすべて `◯月_売上/顧客` の 流入経路=業務提携 の行。金額・日付は**そのまま写すだけで、
丸めも按分もしない。**
"""

import datetime
import importlib.util
import os
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("sc", os.path.join(ROOT, "tools", "sheets_client.py"))
sc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sc)

SS = "1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64"
TAB = "【毎月更新】リピート/業務提携"
WRITE = ("--confirm" in sys.argv and "WRITE" in sys.argv)
FORMULAS_ONLY = "--formulas-only" in sys.argv   # 5〜6（式の入れ直し）だけをやる
ADD_PAIRS = 10   # 売上23〜32
OLD_PAIRS = 22
INSERT_AT = 48   # 0始まり。AW（合計）の手前

TENKI = {
    "生活彩館かさい電器": [("2026/05/04", 49000), ("2026/05/23", 37200), ("2026/06/02", 18000),
                           ("2026/06/29", 11000), ("2026/07/03", 54000)],
    "株式会社エコハウス": [("2026/05/11", 26180), ("2026/07/30", 18480)],
    "株式会社レジェンド": [("2026/05/22", 44600), ("2026/06/24", 47440), ("2026/06/27", 15700),
                           ("2026/07/13", 26220), ("2026/07/15", 252500), ("2026/07/23", 33080),
                           ("2026/08/11", 1683000)],
    "タカラサービス":     [("2026/07/10", 75020), ("2026/08/04", 67000)],
    "才木工業":           [("2026/07/02", 46130)],
    "株式会社プレジャー": [("2026/07/20", 34800)],
}
SHINKI = ("インテリアエージェント", [("2026/06/16", 83380)])


def a1(col):
    """1始まりの列番号 → A1の列名"""
    s = ""
    while col:
        col, r = divmod(col - 1, 26)
        s = chr(65 + r) + s
    return s


def main():
    tok = sc.access_token(sc.load_credentials())

    def get(rng, mode="FORMULA"):
        return sc.call(tok, f"/{SS}/values/{urllib.parse.quote(TAB + '!' + rng, safe='')}",
                       query={"valueRenderOption": mode}).get("values", [])

    meta = sc.call(tok, f"/{SS}?fields=sheets.properties")
    gid = [s["properties"]["sheetId"] for s in meta["sheets"]
           if s["properties"]["title"] == TAB][0]
    rows = get("A1:AZ30")

    def cell(r, c):
        rr = rows[r - 1] if r - 1 < len(rows) else []
        return str(rr[c - 1]).strip() if c - 1 < len(rr) else ""

    namae2gyou = {}
    for r in range(2, 30):
        n = cell(r, 2)
        if n:
            namae2gyou[n] = r
    print("== 会社の行 ==")
    for n, r in namae2gyou.items():
        print(f"  {r:>3} {n}")

    plan = []
    for n, sales in TENKI.items():
        if n not in namae2gyou:
            sys.exit(f"行が見つからない: {n}")
        r = namae2gyou[n]
        used = [p for p in range(1, OLD_PAIRS + 1) if cell(r, 3 + 2 * p) or cell(r, 4 + 2 * p)]
        nxt = (max(used) + 1) if used else 1
        for k, (d, kin) in enumerate(sales):
            p = nxt + k
            if p > OLD_PAIRS + ADD_PAIRS:
                sys.exit(f"組が足りない: {n}")
            plan.append((r, 3 + 2 * p, d, 4 + 2 * p, kin, n, p))

    if SHINKI[0] in namae2gyou and not FORMULAS_ONLY:
        sys.exit(f"すでに「{SHINKI[0]}」の行があります（行{namae2gyou[SHINKI[0]]}）。"
                 "転記は済んでいます。二重に書かないため、ここで止めます。")
    shin_row = max(namae2gyou.values()) + 1
    print(f"\n== 書き込み計画（{len(plan)}件 ＋ 新規1社{len(SHINKI[1])}件）==")
    for r, dc, d, vc, kin, n, p in plan:
        print(f"  行{r:>2} {n:<22} 売上{p:<2} {a1(dc)}{r}={d}  {a1(vc)}{r}=¥{kin:,}")
    print(f"  行{shin_row:>2} {SHINKI[0]:<22} 新規行 E{shin_row}={SHINKI[1][0][0]} "
          f"F{shin_row}=¥{SHINKI[1][0][1]:,}")
    print(f"  転記額合計: ¥{sum(x[4] for x in plan) + SHINKI[1][0][1]:,}")

    if not WRITE:
        print("\n書き込みません（計画のみ）。実行するには: --confirm WRITE")
        return 0

    # 1. 控えタブ
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
    if not FORMULAS_ONLY:
        sc.call(tok, f"/{SS}:batchUpdate", "POST",
                {"requests": [{"duplicateSheet": {"sourceSheetId": gid,
                                                  "newSheetName": f"控え_業務提携_{stamp}"}}]})
        print(f"\n控えタブを作りました: 控え_業務提携_{stamp}")

    if not FORMULAS_ONLY:
        # 2〜3. 列を足して見出しと表示形式
        sc.call(tok, f"/{SS}:batchUpdate", "POST",
                {"requests": [{"insertDimension": {
                    "range": {"sheetId": gid, "dimension": "COLUMNS",
                              "startIndex": INSERT_AT, "endIndex": INSERT_AT + ADD_PAIRS * 2},
                    "inheritFromBefore": True}}]})
        head = []
        for p in range(OLD_PAIRS + 1, OLD_PAIRS + ADD_PAIRS + 1):
            head += ["日付", f"売上{p}"]
        sc.call(tok,
                f"/{SS}/values/{urllib.parse.quote(TAB + '!' + a1(INSERT_AT + 1) + '1', safe='')}",
                "PUT", {"values": [head]}, query={"valueInputOption": "RAW"})
        fmt = []
        for i in range(ADD_PAIRS):
            for j, pat in enumerate([("DATE", "yyyy/mm/dd"), ("CURRENCY", '"¥"#,##0')]):
                c = INSERT_AT + i * 2 + j
                fmt.append({"repeatCell": {
                    "range": {"sheetId": gid, "startRowIndex": 1, "endRowIndex": 101,
                              "startColumnIndex": c, "endColumnIndex": c + 1},
                    "cell": {"userEnteredFormat": {
                        "numberFormat": {"type": pat[0], "pattern": pat[1]}}},
                    "fields": "userEnteredFormat.numberFormat"}})
        sc.call(tok, f"/{SS}:batchUpdate", "POST", {"requests": fmt})
        print(f"売上{OLD_PAIRS + 1}〜{OLD_PAIRS + ADD_PAIRS} の列を足しました"
              f"（{a1(INSERT_AT + 1)}〜{a1(INSERT_AT + ADD_PAIRS * 2)}）")

        # 4. 明細を書き足す
        data = []
        for r, dc, d, vc, kin, n, p in plan:
            data.append({"range": f"{TAB}!{a1(dc)}{r}", "values": [[d]]})
            data.append({"range": f"{TAB}!{a1(vc)}{r}", "values": [[kin]]})
        data.append({"range": f"{TAB}!B{shin_row}:F{shin_row}",
                     "values": [[SHINKI[0], "",
                                 "2026-09-14 転記時に新規追加（planning 20260914-05-cmo）",
                                 SHINKI[1][0][0], SHINKI[1][0][1]]]})
        sc.call(tok, f"/{SS}/values:batchUpdate", "POST",
                {"valueInputOption": "USER_ENTERED", "data": data})
        print(f"明細を {len(plan) + 1} 件 書き足しました")

    # 5〜6. 合計と平均単価の式
    total_col = INSERT_AT + ADD_PAIRS * 2 + 1
    avg_col = total_col + 2
    uri_cols = [4 + 2 * p for p in range(1, OLD_PAIRS + ADD_PAIRS + 1)]
    date_cols = [3 + 2 * p for p in range(1, OLD_PAIRS + ADD_PAIRS + 1)]
    data = []
    for r in range(2, 102):   # 総合計 =SUM(BQ2:BQ101) が見ている範囲すべて
        s = "+".join(f"{a1(c)}{r}" for c in uri_cols)
        kensuu = "COUNTA(" + ",".join(f"{a1(c)}{r}" for c in date_cols) + ")"
        data.append({"range": f"{TAB}!{a1(total_col)}{r}", "values": [[f"={s}"]]})
        data.append({"range": f"{TAB}!{a1(avg_col)}{r}",
                     "values": [[f'=IF({kensuu}=0,"",{a1(total_col)}{r}/{kensuu})']]})
    sc.call(tok, f"/{SS}/values:batchUpdate", "POST",
            {"valueInputOption": "USER_ENTERED", "data": data})
    print(f"合計（{a1(total_col)}列）と平均単価（{a1(avg_col)}列）の式を入れ直しました：{len(data) // 2}行")
    print("\n完了。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
