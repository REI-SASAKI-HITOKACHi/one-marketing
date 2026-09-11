#!/usr/bin/env python3
"""渡辺さんのカレンダーから「空いている開始時刻」を作って lp/booking/slots.json に書く。

【なぜこうしているか】
  もともとは Apps Script（tools/booking-api.gs）が、お客様がページを開くたびに
  カレンダーを見て空き枠を返す設計だった。ただしデプロイはオーナーのGoogleアカウント
  でしかできず、コンペ期間中に手を止めてもらうわけにいかない（2026-09-08）。

  そこで「その場で計算する」のをやめて、**先に計算して静的ファイルとして置く**形にした。
  ページは同じオリジンの slots.json を読むだけなので、CORSもJSONPも要らない。
  ファイルは1時間ごとに作り直す（定期実行）。

  枠の計算ルールは booking-api.gs の akiWaku_() をそのまま移してある。
  Apps Scriptを動かせるようになったら、どちらを使ってもよい。

【入力】 data/calendar/watanabe-events.json
  Googleカレンダーの events.list の生の応答（items か events のどちらでも読む）。
  取得は Claude 側のカレンダー連携で行う（サービスアカウントには
  カレンダーAPIの権限が無いため）。

使い方:
  python3 tools/build-slots.py [--events 別のファイル] [--out 別の出力先]
"""
import argparse
import datetime as dt
import json
import pathlib
import sys
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parent.parent
EVENTS = ROOT / "data" / "calendar" / "watanabe-events.json"
OUT = ROOT / "lp" / "booking" / "slots.json"
JST = ZoneInfo("Asia/Tokyo")

# ---- booking-api.gs の SETTEI と同じ値にすること ----
KAISHI_JIKOKU = 9        # 9:00 より前には始めない
SHUURYOU_JIKOKU = 21     # 21:00 までに終わる枠だけ出す
IDOU_FUN = 60            # 前後に確保する移動時間（分）
YAKIN_HANTEI_JI = 18     # この時刻以降に始まり日をまたぐ予定を夜勤とみなす
YAKIN_AKE_SAIHAYAKU = 13  # 夜勤明けの日は13:00以降から
YAKIN_MAE_SHUURYOU = 18  # 夜勤がある日は18:00までに施工完了
SAITAN_NICHI = 2         # 当日と翌日は出さない
SAICHOU_NICHI = 21       # 3週間先まで
KIZAMI_FUN = 30          # 枠の刻み

# 所要時間ごとに枠を作っておく。ページは「必要な分数以上でいちばん短いもの」を選ぶ。
BUCKET = [60, 90, 120, 150, 180, 210, 240, 300, 360, 420, 480]

YOUBI = "月火水木金土日"


def yomu(path: pathlib.Path) -> list:
    d = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(d, list):
        return d
    return d.get("events") or d.get("items") or []


def toki(v: dict):
    """予定の start/end を (datetime, 終日か) にする"""
    if not v:
        return None, False
    if v.get("dateTime"):
        return dt.datetime.fromisoformat(v["dateTime"]).astimezone(JST), False
    if v.get("date"):
        s = v["date"][:10]
        return dt.datetime.fromisoformat(s).replace(tzinfo=JST), True
    return None, False


def fusagari(events: list):
    """(塞がっている区間, 夜勤の区間) を返す。どちらも (開始, 終了) のリスト"""
    fusagi, yakin = [], []
    for ev in events:
        if ev.get("status") == "cancelled":
            continue
        # 「予定あり/なし」の「なし」は塞がりに数えない
        if ev.get("transparency") == "transparent":
            continue
        if ev.get("availability") == "AVAILABILITY_FREE":
            continue
        s, s_zenjitsu = toki(ev.get("start"))
        e, e_zenjitsu = toki(ev.get("end"))
        if not s or not e:
            continue
        # 終日予定は塞がりとして扱わない。
        # このカレンダーの終日予定はTODOで、実際の施工・バイト・通院は
        # すべて時刻の入った予定になっている。1件のTODOで丸一日を潰さない。
        if s_zenjitsu or e_zenjitsu:
            continue
        fusagi.append((s, e))
        # 夜勤かどうか。夕方以降に始まって、日をまたいで終わるもの。
        # タイトルでは判定しない（呼び方が変わっても壊れないようにするため）
        if s.hour >= YAKIN_HANTEI_JI and s.date() != e.date():
            yakin.append((s, e))
    return fusagi, yakin


def aiteruka(fusagi, s, e, idou: dt.timedelta) -> bool:
    for fs, fe in fusagi:
        if s < fe + idou and fs - idou < e:
            return False
    return True


def aki_waku(fusagi, yakin, shoyou_fun: int, kyou: dt.date) -> list:
    idou = dt.timedelta(minutes=IDOU_FUN)
    hitsuyou = dt.timedelta(minutes=shoyou_fun)
    kizami = dt.timedelta(minutes=KIZAMI_FUN)
    out = []
    for i in range(SAITAN_NICHI, SAICHOU_NICHI + 1):
        hi = kyou + dt.timedelta(days=i)
        hi_hajime = dt.datetime.combine(hi, dt.time(0, 0), JST)
        tsugi = hi_hajime + dt.timedelta(days=1)

        # 夜勤明けの日か（前夜の夜勤が、この日にかかって終わる）
        ake = any(hi_hajime < ye < tsugi for _, ye in yakin)
        # この日に夜勤に入るか
        yakin_bi = any(hi_hajime <= ys < tsugi for ys, _ in yakin)

        saihayaku = hi_hajime.replace(
            hour=YAKIN_AKE_SAIHAYAKU if ake else KAISHI_JIKOKU)
        shimekiri = hi_hajime.replace(
            hour=YAKIN_MAE_SHUURYOU if yakin_bi else SHUURYOU_JIKOKU)

        kouho = []
        t = saihayaku
        while t + hitsuyou <= shimekiri:
            if aiteruka(fusagi, t, t + hitsuyou, idou):
                kouho.append(t.strftime("%H:%M"))
            t += kizami
        if kouho:
            out.append({
                "date": hi.isoformat(),
                "label": f"{hi.month}月{hi.day}日（{YOUBI[hi.weekday()]}）",
                "times": kouho,
            })
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", default=str(EVENTS))
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()

    path = pathlib.Path(a.events)
    if not path.exists():
        sys.exit(f"{path} がありません。先にカレンダーの予定を書き出してください。")
    events = yomu(path)
    fusagi, yakin = fusagari(events)
    ima = dt.datetime.now(JST)
    kyou = ima.date()

    buckets = {str(m): aki_waku(fusagi, yakin, m, kyou) for m in BUCKET}
    data = {
        "generated": ima.isoformat(timespec="minutes"),
        "generatedLabel": ima.strftime("%-m月%-d日 %H:%M"),
        # このファイルが古くなったらページ側で注意書きを出すための目安（時間）
        "staleHours": 6,
        "buckets": buckets,
    }
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")),
                   encoding="utf-8")

    print(f"書き出しました: {out.relative_to(ROOT)}  {out.stat().st_size:,} bytes")
    print(f"予定 {len(events)}件 → 塞がり {len(fusagi)}件 ／ 夜勤 {len(yakin)}件")
    for m in (60, 120, 240):
        hi = buckets[str(m)]
        print(f"  所要{m}分: {len(hi)}日ぶん / 枠 {sum(len(d['times']) for d in hi)}個")


if __name__ == "__main__":
    main()
