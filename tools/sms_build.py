#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
冬季SMSの宛先リストと本文を組み立てる。送信はしない（送信は tools/sms_send.py）。

やること
  1. 「冬季見込み客_2026」タブのCSVを読む
  2. 電話番号を正規化し、送れない行をはじく（理由つき）
  3. セグメントごとにテンプレートを選び、差し込みを埋める
  4. 課金通数を見積もり、合計金額を出す
  5. 送信キューを JSONL で書き出す（既定は private/ 配下。gitignore 済み）

使い方
  python3 tools/sms_build.py --check
      テンプレートの検算だけ（CSVなし）。文字数・必須要素・料金の整合をみる。

  python3 tools/sms_build.py --csv private/冬季見込み客.csv
      サマリーを表示。ファイルは書かない。

  python3 tools/sms_build.py --csv private/冬季見込み客.csv --out private/queue.jsonl
      送信キューを書き出す。

  python3 tools/sms_build.py --csv ... --priority 1,2 --route 自社
      優先度・送信系統でしぼる。

CSVに必要な列（「冬季見込み客_2026」タブのヘッダーそのまま）
  優先 / セグメント / 送信系統 / 氏名 / TEL / 最終施工日 / 経過(月) / 今回おすすめ

★電話番号は文字列として扱う。数値に変換しない（先頭の0が消える）。
"""

import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES = os.path.join(ROOT, "data", "sms-templates.json")
PRICES = os.path.join(ROOT, "data", "prices.json")

# KDDI Message Cast の課金は「文字数に応じて課金通数が異なる」とだけ公表されており、
# 換算表は非公開（2026-09-06 時点、公式サイトで確認）。
# ここでは国内SMSの慣行である「全角70文字ごとに1通」を仮置きしている。
# ★契約時にKDDIから正式な換算表をもらったら UNIT_CHARS と PRICE_PER_UNIT を直すこと。
UNIT_CHARS = 70
PRICE_PER_UNIT = 9.35  # 円・税込。公表値は「9.35円〜」なので下限。提示額が出たら差し替える
PRICE_IS_PROVISIONAL = True
WITHDRAW_LINE = 10.0  # 税込10円を超えたら NTT CPaaS に切り替える（撤退ライン）

MAX_CHARS = 660  # docomo基準。全キャリア宛はこれを上限にする


def count_chars(text: str) -> int:
    """KDDIの数え方に合わせる。半角も全角も1文字、改行は2文字、絵文字は2文字。"""
    n = 0
    for ch in text:
        if ch == "\n":
            n += 2
        elif unicodedata.east_asian_width(ch) == "W" and ord(ch) > 0x1F000:
            n += 2  # 絵文字
        else:
            n += 1
    return n


def count_units(text: str) -> int:
    c = count_chars(text)
    return max(1, -(-c // UNIT_CHARS))


PHONE_NG = {
    "空欄": "電話番号が入っていない",
    "桁数": "桁数が携帯番号として不正",
    "固定": "固定電話（SMSが届かない）",
    "重複": "同じ番号が既に送信対象に入っている",
}


def normalize_phone(raw: str):
    """(正規化後の番号 or None, 理由) を返す。数値化はしない。"""
    if raw is None:
        return None, "空欄"
    s = unicodedata.normalize("NFKC", str(raw)).strip()
    s = re.sub(r"[^\d+]", "", s)
    if not s:
        return None, "空欄"
    if s.startswith("+81"):
        s = "0" + s[3:]
    elif s.startswith("81") and len(s) == 12:
        s = "0" + s[2:]
    if not s.startswith("0"):
        return None, "桁数"
    if re.fullmatch(r"0[789]0\d{8}", s):
        return s, ""
    if re.fullmatch(r"0\d{8,9}", s):
        return None, "固定"
    return None, "桁数"


def surname(full: str) -> str:
    """差し込み用に姓へ丸める。法人名・注記つきの名前はそのまま使わず短くする。"""
    s = unicodedata.normalize("NFKC", (full or "").strip())
    s = re.sub(r"\s*(様|さま|さん|先生)\s*$", "", s)
    # 「竹内さま 加藤さんご紹介」のような注記を落とす
    s = re.split(r"[（(]", s)[0].strip()
    if re.search(r"(株式会社|有限会社|合同会社|\(株\)|㈱)", s):
        return s  # 法人はフルネームのまま
    parts = re.split(r"[\s　]+", s)
    if len(parts) >= 2 and len(parts[0]) <= 5:
        return parts[0]
    return parts[0] if parts else s


def months_elapsed(row) -> str:
    v = (row.get("経過(月)") or "").strip()
    try:
        return str(int(round(float(v))))
    except ValueError:
        pass
    d = (row.get("最終施工日") or "").strip().replace("-", "/")
    m = re.match(r"(\d{4})/(\d{1,2})/(\d{1,2})", d)
    if not m:
        return ""
    last = dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    today = dt.date.today()
    return str(max(0, round((today - last).days / 30.4)))


def load_templates():
    with open(TEMPLATES, encoding="utf-8") as f:
        data = json.load(f)
    return data, {t["id"]: t for t in data["テンプレート"]}


def pick_template(row) -> str:
    pr = (row.get("優先") or "").strip()
    route = (row.get("送信系統") or "").strip()
    honpo = "本舗" in route
    if pr in ("1", "2"):
        return "B1" if honpo else "A1"
    if pr == "3":
        return "B3" if honpo else "A3"
    return ""


def render(body: str, row) -> str:
    return (
        body.replace("{name}", surname(row.get("氏名", "")))
        .replace("{osusume}", (row.get("今回おすすめ") or "").strip())
        .replace("{months}", months_elapsed(row))
    )


# ---------------------------------------------------------------- check mode

REQUIRED_TOKENS = [
    ("名乗り", lambda b: b.lstrip().startswith("【")),
    ("配信停止の記載", lambda b: "停止" in b),
]


def cmd_check() -> int:
    data, by_id = load_templates()
    with open(PRICES, encoding="utf-8") as f:
        prices = json.load(f)
    peak = prices["繁忙期加算"]["金額"]
    same_day = prices["同時施工割引"]["標準"]

    ng = 0
    print("== テンプレートの検算 ==")
    print(f"（{UNIT_CHARS}文字＝1通 / {PRICE_PER_UNIT}円・税込 で計算）\n")
    sample = {
        "氏名": "末武　俊康",
        "今回おすすめ": "換気扇・浴室",
        "経過(月)": "8.2",
        "最終施工日": "2025/12/29",
    }
    for t in data["テンプレート"]:
        body = render(t["本文"], sample).replace("{survey_url}", "https://one-hitter-survey.netlify.app/?src=sms&id=C0032")
        c, u = count_chars(body), count_units(body)
        flags = []
        for label, fn in REQUIRED_TOKENS:
            if not fn(body):
                flags.append(f"NG:{label}")
                ng += 1
        if c > MAX_CHARS:
            flags.append(f"NG:{MAX_CHARS}文字超")
            ng += 1
        # 料金の数字がテンプレに直書きされている場合は正データと突き合わせる
        for num in re.findall(r"([0-9,]{3,})円", body):
            n = int(num.replace(",", ""))
            if n not in (peak, same_day, 1000):
                flags.append(f"NG:料金{n}円が prices.json と合わない")
                ng += 1
        print(f"[{t['id']}] {t['対象']}")
        print(f"     {c}文字 / {u}通分 / {u * PRICE_PER_UNIT:.2f}円  {' '.join(flags) or 'OK'}")
    print()
    if PRICE_IS_PROVISIONAL:
        print(f"※ 単価{PRICE_PER_UNIT}円は公表下限。KDDIの提示が{WITHDRAW_LINE}円(税込)を超えたら NTT CPaaS に切り替える。")
        print("※ 課金の文字数換算はKDDI非公開。契約時にもらう換算表で UNIT_CHARS を直すこと。")
    print(("NG が %d 件あります" % ng) if ng else "\nすべてOK")
    return 1 if ng else 0


# ---------------------------------------------------------------- build mode


def cmd_build(args) -> int:
    data, by_id = load_templates()
    want_pr = set(x.strip() for x in args.priority.split(",")) if args.priority else None
    with open(args.csv, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    queue, skipped, seen = [], [], set()
    for row in rows:
        pr = (row.get("優先") or "").strip()
        route = (row.get("送信系統") or "").strip()
        if want_pr and pr not in want_pr:
            continue
        if args.route and args.route not in route:
            continue
        tid = pick_template(row)
        if not tid:
            skipped.append((row, f"優先{pr} は対象外"))
            continue
        tel, reason = normalize_phone(row.get("TEL"))
        if tel is None:
            skipped.append((row, PHONE_NG[reason]))
            continue
        if tel in seen:
            skipped.append((row, PHONE_NG["重複"]))
            continue
        seen.add(tel)
        body = render(by_id[tid]["本文"], row)
        queue.append(
            {
                "tel": tel,  # 文字列。数値化しないこと
                "template": tid,
                "priority": pr,
                "segment": (row.get("セグメント") or "").strip(),
                "route": route,
                "name": surname(row.get("氏名", "")),
                "chars": count_chars(body),
                "units": count_units(body),
                "body": body,
            }
        )

    total_units = sum(q["units"] for q in queue)
    print(f"CSV {len(rows)}行 → 送信可 {len(queue)}件 / 除外 {len(skipped)}件")
    print()
    print("■ 内訳")
    agg = {}
    for q in queue:
        k = (q["priority"], q["route"], q["template"])
        a = agg.setdefault(k, [0, 0])
        a[0] += 1
        a[1] += q["units"]
    for k in sorted(agg):
        n, u = agg[k]
        print(f"  優先{k[0]} / {k[1]:<4} / {k[2]}  {n:>4}件  {u:>4}通分  {u * PRICE_PER_UNIT:>9,.0f}円")
    print(f"  {'合計':<18} {len(queue):>4}件  {total_units:>4}通分  {total_units * PRICE_PER_UNIT:>9,.0f}円")
    print()
    print("■ 除外の理由")
    rc = {}
    for _, why in skipped:
        rc[why] = rc.get(why, 0) + 1
    for why, n in sorted(rc.items(), key=lambda x: -x[1]):
        print(f"  {why}: {n}件")
    print()
    print(f"■ 無料トライアル枠(2か月・3,000通)に対して {total_units}通分 … " + ("収まる" if total_units <= 3000 else "★超える"))

    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            for q in queue:
                f.write(json.dumps(q, ensure_ascii=False) + "\n")
        print(f"\n書き出し: {args.out}（個人情報を含む。コミットしないこと）")
    if args.sample:
        print("\n■ 本文サンプル")
        shown = set()
        for q in queue:
            if q["template"] in shown:
                continue
            shown.add(q["template"])
            print(f"\n--- {q['template']} / {q['chars']}文字 / {q['units']}通分 ---")
            print(q["body"])
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="冬季SMSの宛先リストと本文を組み立てる")
    p.add_argument("--check", action="store_true", help="テンプレートの検算だけ行う")
    p.add_argument("--csv", help="冬季見込み客_2026 タブのCSV")
    p.add_argument("--out", help="送信キューの書き出し先（JSONL）")
    p.add_argument("--priority", help="優先度でしぼる（例: 1,2）")
    p.add_argument("--route", help="送信系統でしぼる（自社 / 本舗）")
    p.add_argument("--sample", action="store_true", help="テンプレートごとに本文を1件表示")
    a = p.parse_args()
    if a.check:
        return cmd_check()
    if not a.csv:
        p.print_help()
        return 2
    return cmd_build(a)


if __name__ == "__main__":
    sys.exit(main())
