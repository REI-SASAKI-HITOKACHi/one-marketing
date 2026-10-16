#!/usr/bin/env python3
"""提携先へ「今月の空き枠」を知らせる文面を作る（T052）。

【なぜ】
  第6回MTG（10/9）の議事録より、オーナーの言葉「タカラサービス様は、こちらから定期的に連絡すれば案件が出る」。
  6-8 の T052 についたオーナーのメモは「着手して和真は対応しない」。
  → 和真さんの手を使わず、予約ページと同じ空き枠（和真さんのカレンダーから作る控え）から
    月1回の連絡文を作る。

【材料】
  lp/booking/slots-hikae.json（毎時点検が3時間ごとに作り直す。所要時間ごとの空き枠・約3週間先まで）

【出すもの】
  件名と本文を標準出力に出す。送るのは嶺さん（初回は嶺さんが確認、2回目からは毎月1日の朝に CMO が下書きを作る）。
  お客様向けのページではないので check-public-page の対象外。宛先は提携先の担当者（会社あて）だけ。

【使い方】
  python3 tools/teikei-akiwaku.py                 # タカラサービス様（既定）
  python3 tools/teikei-akiwaku.py --json          # 件名・本文を JSON で（Gmail 下書きを作るとき）
"""
import argparse
import datetime
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
HIKAE = ROOT / "lp" / "booking" / "slots-hikae.json"
YOUBI = "月火水木金土日"

# 提携先ごとの宛名とご依頼の入口。先方の専用フォームがある会社だけ URL を入れる。
TEIKEI = {
    "takara": {
        "atena": "株式会社タカラサービス\n深堀様",
        "form": "https://lp.onehitter.jp/partner/takara-7q2m/",
    },
}

ZENJITSU = "480"   # 8時間＝終日
HANNICHI = "240"   # 4時間＝半日
OSOI = "16:00"     # これより遅い開始は法人の現場には向かないので出さない
ASA = "10:00"      # 「終日」と書くのは、この時刻までに入れる日だけ（12時半から8時間は終日とは言えない）


def hi(d):
    x = datetime.date.fromisoformat(d)
    return f"{x.month}/{x.day}（{YOUBI[x.weekday()]}）"


def waku(buckets, key, kyou, made=OSOI):
    out = []
    for x in buckets.get(key, []):
        if x["date"] <= kyou.isoformat():
            continue
        t = [s for s in x["times"] if s <= made]
        if t:
            out.append((x["date"], t[0]))
    return out


def bunmen(teikei, hikae, kyou):
    b = hikae["buckets"]
    zen = waku(b, ZENJITSU, kyou, made=ASA)
    zen_hi = {d for d, _ in zen}
    han = [(d, t) for d, t in waku(b, HANNICHI, kyou) if d not in zen_hi]
    owari = max([x["date"] for v in b.values() for x in v] or [kyou.isoformat()])
    t = TEIKEI[teikei]
    gyo = [
        t["atena"], "",
        "いつもお世話になっております。",
        "ワンヒッター株式会社の佐々木です。", "",
        f"直近（{hi(owari)}まで）の作業の空き状況をお知らせいたします。", "",
    ]
    if zen:
        gyo.append("■ 終日お伺いできる日")
        gyo += [f"・{hi(d)} {s}〜" for d, s in zen]
        gyo.append("")
    if han:
        gyo.append("■ 半日（4時間ほど）お伺いできる日")
        gyo += [f"・{hi(d)} {s}〜" for d, s in han]
        gyo.append("")
    if not zen and not han:
        gyo += ["この期間は空きが少なくなっております。日程はご相談のうえ調整いたします。", ""]
    gyo += [
        "お見積り・現地調査のご依頼は、貴社専用のフォームから承っております。",
        t["form"],
        "空き状況は日々変わりますので、ご依頼の順に調整させていただきます。", "",
        "引き続きどうぞよろしくお願いいたします。", "",
        "ワンヒッター株式会社",
        "佐々木",
    ]
    kenmei = f"【ワンヒッター】{hi(owari)}までの作業の空き状況のご案内"
    return kenmei, "\n".join(gyo), len(zen), len(han)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--teikei", default="takara", choices=sorted(TEIKEI))
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    hikae = json.loads(HIKAE.read_text(encoding="utf-8"))
    kyou = datetime.date.today()
    kenmei, honbun, nz, nh = bunmen(a.teikei, hikae, kyou)
    if a.json:
        print(json.dumps({"subject": kenmei, "body": honbun, "zenjitsu": nz, "hannichi": nh,
                          "hikae": hikae.get("generated")}, ensure_ascii=False))
    else:
        print(f"件名：{kenmei}\n（空き枠の控え {hikae.get('generated')}・終日 {nz}日／半日 {nh}日）\n")
        print(honbun)


if __name__ == "__main__":
    main()
