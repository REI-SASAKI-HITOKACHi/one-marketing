#!/usr/bin/env python3
"""無料点検の週次報告（月曜9時にオーナーへ送る1通）の本文を作る。

【なぜ】
  docs/無料点検-全体構造.md 5章：続ける／やめるの判断はオーナーがするが、
  数字は自動で出す。「点検→申込率が30%を切ったらそのメニューの単独点検を止める」の線を
  毎週、同じ形で見せる。文面の形は docs/無料点検-文面-承認シート.md ⑧。

【数字の出どころ】 tools/tenken-inbox.py と同じ送信（Netlify Forms か内蔵サンプル）。
  ファイル名にハイフンがあるので importlib で読み、yomu() を借りる。
  - 点検件数           = 現場フォーム（tenken-genba）の件数
  - 要洗浄／様子見／不要 = 現場フォームの「所見」
  - その場申込件数      = その場申込（tenken-keiyaku）の件数
  - 点検→申込率        = その場申込 ÷ 点検件数（30%線）
  - 流入元別           = 申込フォーム（tenken-moushikomi）の「流入元」
  - きっかけ別          = 現場フォームの「きっかけ」（申込があった点検／施工のついで）
  「点検→予約率」（報告書から30日以内の予約フォーム送信）は予約フォーム側の数字が要るので、ここでは出ない（未計測と書く）。

【期間】 既定は「前週の月曜〜日曜」（月曜朝に動かす前提）。--all で全期間。
  サンプルは日付が固定の架空データなので、--sample のときは自動で --all 扱い。

使い方:
  python3 tools/tenken-weekly.py                 # サンプル（トークン等が無ければ自動でこちら）
  python3 tools/tenken-weekly.py --live          # Netlify から読む（読むだけ）
  python3 tools/tenken-weekly.py --live --week-of 2026-10-19   # その日を含む週の前週
"""
import argparse
import collections
import datetime as dt
import importlib.util
import pathlib
import sys
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("tenken_inbox", ROOT / "tools" / "tenken-inbox.py")
TI = importlib.util.module_from_spec(spec)
spec.loader.exec_module(TI)
BT = TI.BT
JST = ZoneInfo("Asia/Tokyo")
OUTDIR = ROOT / "dist" / "tenken" / "weekly"

SEN = 0.30                  # 続ける／やめるの線（5章）
TENKEN_FUN = 10 + 15 + 5    # 稼働の推計：点検10分＋移動15分＋入力5分（5章の採算の目安）
TSUIDE_FUN = 10 + 5         # ついで点検は移動ゼロ


def toki(s: dict) -> dt.date:
    """送信の日付（JST）。フォームの送信時刻があればそれ、無ければ Netlify の created_at"""
    v = (s.get("data") or {}).get("送信時刻") or s.get("created_at") or ""
    try:
        return dt.datetime.fromisoformat(v.replace("Z", "+00:00")).astimezone(JST).date()
    except ValueError:
        return dt.date.min


def ritsu(a: int, b: int) -> str:
    return f"{a / b * 100:.0f}%" if b else "—"


def matome(subs: list, kikan: tuple, kikan_label: str) -> str:
    hajime, owari = kikan
    naka = [s for s in subs if hajime <= toki(s) <= owari]
    genba = [s["data"] for s in naka if s.get("form_name") == BT.FORM_GENBA]
    keiyaku = [s["data"] for s in naka if s.get("form_name") == BT.FORM_KEIYAKU]
    moushi = [s["data"] for s in naka if s.get("form_name") == BT.FORM_MOUSHIKOMI]

    n = len(genba)
    shoken = collections.Counter(d.get("所見", "") for d in genba)
    kikkake = collections.Counter(d.get("きっかけ", "") for d in genba)
    moushi_n = kikkake.get("申込があった点検", 0)
    tsuide_n = kikkake.get("施工のついで", 0)
    src = collections.Counter((d.get("流入元") or "").strip() or "（なし）" for d in moushi)
    k = len(keiyaku)
    sei = k / n if n else None
    if sei is None:
        sen = "点検0件のため判定なし"
    else:
        sen = "上回っています" if sei >= SEN else "下回っています"
    kadou = moushi_n * TENKEN_FUN + tsuide_n * TSUIDE_FUN
    src_str = "、".join(f"{s} {c}件" for s, c in src.most_common()) or "（申込なし）"

    lines = [
        f"【無料点検 週次】{kikan_label}",
        f"点検 {n}件（申込 {moushi_n}／ついで {tsuide_n}）｜要洗浄 {shoken.get('要洗浄', 0)}件（{ritsu(shoken.get('要洗浄', 0), n)}）｜"
        f"様子見 {shoken.get('様子見', 0)}件（{ritsu(shoken.get('様子見', 0), n)}）｜不要 {shoken.get('不要', 0)}件（{ritsu(shoken.get('不要', 0), n)}・公開値）",
        f"その場申込 {k}件｜点検→申込率 {ritsu(k, n)}（30%線：{sen}）",
        f"流入元：{src_str}",
        f"稼働：点検 {kadou}分（推計。申込あり{TENKEN_FUN}分・ついで{TSUIDE_FUN}分で計算）",
        "点検→予約率（報告書から30日以内の予約）：未計測（予約フォーム側の集計が要ります）",
    ]
    # メニュー別（5章：30%を切ったら「そのメニューの」単独点検を止める）
    menu_n = collections.Counter(d.get("見た場所", "") for d in genba)
    menu_k = collections.Counter(d.get("点検メニュー", "") for d in keiyaku)
    if menu_n:
        lines.append("メニュー別（点検→申込率）：" + "、".join(f"{m} {menu_n[m]}件→{menu_k.get(m, 0)}件（{ritsu(menu_k.get(m, 0), menu_n[m])}）" for m in menu_n))
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--sample", action="store_true")
    g.add_argument("--live", action="store_true")
    ap.add_argument("--all", action="store_true", help="期間で絞らない")
    ap.add_argument("--week-of", help="YYYY-MM-DD。この日を含む週の前週を集計（既定：今日）")
    ap.add_argument("--out", default=str(OUTDIR))
    a = ap.parse_args()

    subs, mode, oshirase = TI.yomu("live" if a.live else "sample")
    if oshirase:
        print("お知らせ:", oshirase)
    kyou = dt.date.fromisoformat(a.week_of) if a.week_of else dt.datetime.now(JST).date()
    if a.all or mode == "sample":
        kikan, label = (dt.date.min, dt.date.max), "全期間" + ("（サンプル）" if mode == "sample" else "")
    else:
        getsu = kyou - dt.timedelta(days=kyou.weekday())          # 今週の月曜
        hajime, owari = getsu - dt.timedelta(days=7), getsu - dt.timedelta(days=1)
        kikan, label = (hajime, owari), f"{hajime.month}/{hajime.day}〜{owari.month}/{owari.day}"

    text = matome(subs, kikan, label)
    print(text)
    out = pathlib.Path(a.out) / f"{kyou.isoformat()}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text + "\n", encoding="utf-8")
    print(f"\n書き出しました: {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}（モード {mode}）")


if __name__ == "__main__":
    main()
