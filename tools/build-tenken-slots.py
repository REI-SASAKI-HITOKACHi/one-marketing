#!/usr/bin/env python3
"""無料点検の「出してよい枠」だけを lp/media/tenken/slots.json に書く（枠制御）。

【なぜ別のツールにしたか】
  予約フォーム用の tools/build-slots.py は「空いていれば全部出す」。
  無料点検は逆で、docs/無料点検-全体構造.md 4章のとおり
  **閑散期の、施工がある日の、その施工の前後にしか出さない**。
  点検は無料なので、渡辺さんの移動時間を丸ごと使う枠を出すと採算が崩れる。
  「近くで作業がある日の空き時間だけ」を機械的に選び、
  渡辺さんに「行けますか」と聞く工程を作らない（人の稼働0）。

【ルール】（初期値。下の定数を変えればよい。オーナーが変えられる）
  - 閑散期の月だけ（1〜4月・8〜10月＝早期予約割引がある月）
  - その日に施工（時刻の入った予定）が 1〜2件ある日だけ。3件以上の日は出さない
  - 枠は30分刻みの開始時刻。所要30分＋前後の移動15分が空いていること
  - 施工の開始・終了から ±90分の範囲だけ（＝施工の「前」か「後」に寄せる）
  - 1日2枠まで、1週（ISO週）6枠まで、2〜21日先、日曜は出さない
  - area は施工の予定の location から「◯◯区／◯◯市」を取る（無ければ空）

【入力】 data/calendar/watanabe-events.json（build-slots.py と同じ。時刻だけで氏名・住所は無い想定。
  location が入っていれば区市名だけ使う）。
  空き判定の関数（toki / fusagari / aiteruka）は build-slots.py から借りる。
  ファイル名にハイフンがあるので importlib で読む。

使い方:
  python3 tools/build-tenken-slots.py
  python3 tools/build-tenken-slots.py --events 別ファイル --out 別出力 --today 2026-10-01   # テスト用
"""
import argparse
import datetime as dt
import importlib.util
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
EVENTS = ROOT / "data" / "calendar" / "watanabe-events.json"
OUT = ROOT / "lp" / "media" / "tenken" / "slots.json"

spec = importlib.util.spec_from_file_location("build_slots", ROOT / "tools" / "build-slots.py")
BS = importlib.util.module_from_spec(spec)
spec.loader.exec_module(BS)
JST = BS.JST

# ---- 枠制御の初期値（docs/無料点検-全体構造.md 4章） ----
KANSANKI_TSUKI = (1, 2, 3, 4, 8, 9, 10)   # 閑散期。5〜7月・11〜12月は枠が出ない＝自然に止まる
SEKOU_SAISHOU = 1        # その日の施工がこれ未満なら出さない（近くに作業が無い）
SEKOU_SAIDAI = 2         # これを超える日は出さない（詰まりすぎ）
TENKEN_SHOYOU_FUN = 30   # 点検の所要（現場10〜20分＋出入り）
IDOU_FUN = 15            # 施工先から点検先への移動（半径2km以内の想定）
KINSETSU_FUN = 90        # 施工の開始・終了から何分以内の開始時刻だけ出すか
HI_JOUGEN = 2            # 1日の上限
SHUU_JOUGEN = 6          # 1週（ISO週・月〜日）の上限
SAITAN_NICHI = BS.SAITAN_NICHI     # 2日先から
SAICHOU_NICHI = BS.SAICHOU_NICHI   # 21日先まで
YASUMI_YOUBI = (6,)      # 出さない曜日（0=月 … 6=日）
KIZAMI_FUN = BS.KIZAMI_FUN

# 施工とみなさない予定のタイトル。カレンダーには夜勤・私用・通院も時刻付きで入っているので、
# 「その日に作業がある」の判定からは外す。タイトルが無い予定は施工として扱う
# （実カレンダーはお客様名がタイトルのことが多いため）。
SEKOU_JOGAI_GO = ("夜勤", "私用", "通院", "バイト", "休み", "休暇", "点検")

AREA_RE = re.compile(r"(.+?[区市])")
TODOUFUKEN_RE = re.compile(r"^(〒?\s*\d{3}-?\d{4}\s*)?(東京都|北海道|(?:京都|大阪)府|.{2,3}県)?\s*")


def area_kara(location: str) -> str:
    """住所の文字列から「江戸川区」「市川市」だけを取り出す。取れなければ空。
    都道府県と郵便番号を先に落とさないと「東京都江戸川区」がそのまま返ってしまう"""
    s = TODOUFUKEN_RE.sub("", (location or "").strip(), count=1)
    m = AREA_RE.search(s)
    return m.group(1) if m else ""


def sekou_ka(ev: dict, s: dt.datetime, e: dt.datetime) -> bool:
    """「施工」とみなすか。build-slots と同じく、夜勤はタイトルでなく時刻で判定する"""
    title = ev.get("summary") or ""
    if any(g in title for g in SEKOU_JOGAI_GO):
        return False
    if s.hour >= BS.YAKIN_HANTEI_JI and s.date() != e.date():   # 夜勤
        return False
    return True


def sekou_atsumeru(events: list) -> dict:
    """日付 → その日の施工 [(開始, 終了, location)] 。読み方は build-slots.fusagari と同じ条件"""
    hi = {}
    for ev in events:
        if ev.get("status") == "cancelled" or ev.get("transparency") == "transparent":
            continue
        if ev.get("availability") == "AVAILABILITY_FREE":
            continue
        s, s_z = BS.toki(ev.get("start"))
        e, e_z = BS.toki(ev.get("end"))
        if not s or not e or s_z or e_z:
            continue
        if not sekou_ka(ev, s, e):
            continue
        hi.setdefault(s.date(), []).append((s, e, ev.get("location") or ""))
    return hi


def hi_no_waku(hi: dt.date, sekou: list, fusagi: list, yakin: list) -> list:
    """その日の候補（開始時刻の datetime）。上限は掛けずに全部返す"""
    idou = dt.timedelta(minutes=IDOU_FUN)
    shoyou = dt.timedelta(minutes=TENKEN_SHOYOU_FUN)
    kinsetsu = dt.timedelta(minutes=KINSETSU_FUN)
    hajime = dt.datetime.combine(hi, dt.time(0, 0), JST)
    tsugi = hajime + dt.timedelta(days=1)
    # 夜勤明け／夜勤前の制限は予約フォームと同じにする（渡辺さんの体を守る側の値）
    ake = any(hajime < ye < tsugi for _, ye in yakin)
    yakin_bi = any(hajime <= ys < tsugi for ys, _ in yakin)
    saihayaku = hajime.replace(hour=BS.YAKIN_AKE_SAIHAYAKU if ake else BS.KAISHI_JIKOKU)
    shimekiri = hajime.replace(hour=BS.YAKIN_MAE_SHUURYOU if yakin_bi else BS.SHUURYOU_JIKOKU)

    kouho = []
    t = saihayaku
    while t + shoyou <= shimekiri:
        if BS.aiteruka(fusagi, t, t + shoyou, idou):
            # 施工の開始か終了の ±90分に入っている開始時刻だけ
            chikai = any(abs(t - s) <= kinsetsu or abs(t - e) <= kinsetsu for s, e, _ in sekou)
            if chikai:
                kouho.append(t)
        t += dt.timedelta(minutes=KIZAMI_FUN)
    return kouho


def erabu(kouho: list, sekou: list, jougen: int) -> list:
    """1日の上限まで選ぶ。施工にいちばん近いもの（移動の無駄が少ないもの）を優先し、時刻順で返す"""
    def kyori(t):
        return min(min(abs(t - s), abs(t - e)) for s, e, _ in sekou)
    return sorted(sorted(kouho, key=kyori)[:jougen])


def tenken_waku(events: list, kyou: dt.date) -> list:
    fusagi, yakin = BS.fusagari(events)
    sekou_hi = sekou_atsumeru(events)
    shuu_kazu = {}   # ISO週 → すでに出した枠の数
    days = []
    for i in range(SAITAN_NICHI, SAICHOU_NICHI + 1):
        hi = kyou + dt.timedelta(days=i)
        if hi.month not in KANSANKI_TSUKI or hi.weekday() in YASUMI_YOUBI:
            continue
        sekou = sekou_hi.get(hi, [])
        if not (SEKOU_SAISHOU <= len(sekou) <= SEKOU_SAIDAI):
            continue
        shuu = hi.isocalendar()[:2]
        nokori = SHUU_JOUGEN - shuu_kazu.get(shuu, 0)
        if nokori <= 0:
            continue
        erabi = erabu(hi_no_waku(hi, sekou, fusagi, yakin), sekou, min(HI_JOUGEN, nokori))
        if not erabi:
            continue
        shuu_kazu[shuu] = shuu_kazu.get(shuu, 0) + len(erabi)
        area = next((area_kara(loc) for _, _, loc in sekou if area_kara(loc)), "")
        days.append({
            "date": hi.isoformat(),
            "label": f"{hi.month}月{hi.day}日（{BS.YOUBI[hi.weekday()]}）",
            "area": area,
            "times": [t.strftime("%H:%M") for t in erabi],
        })
    return days


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", default=str(EVENTS))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--today", help="テスト用。YYYY-MM-DD を「今日」として計算する")
    a = ap.parse_args()

    ima = dt.datetime.now(JST)
    kyou = dt.date.fromisoformat(a.today) if a.today else ima.date()

    path = pathlib.Path(a.events)
    if path.exists():
        events = BS.yomu(path)
        days = tenken_waku(events, kyou)
    else:
        # 予定が無いときは「枠なし」を書く。ページ側は枠なし＝LINE案内を出すので、落とさない
        print(f"注意: {path} がありません。枠なし（days=[]）で書き出します。")
        events, days = [], []

    data = {
        "generated": ima.isoformat(timespec="minutes"),
        "generatedLabel": ima.strftime("%-m月%-d日 %H:%M"),
        "days": days,
    }
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    try:
        rel = out.relative_to(ROOT)
    except ValueError:
        rel = out
    print(f"書き出しました: {rel}  {out.stat().st_size:,} bytes（今日={kyou}）")
    print(f"予定 {len(events)}件 → 点検の枠 {len(days)}日 / {sum(len(d['times']) for d in days)}枠")
    for d in days:
        print(f"  {d['label']} {d['area'] or '（エリア不明）'}: {' '.join(d['times'])}")


if __name__ == "__main__":
    main()
