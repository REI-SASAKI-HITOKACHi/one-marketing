#!/usr/bin/env python3
"""予約ページの控え（lp/booking/slots.json）を、本命の Apps Script API の結果から作り直す。

【なぜ要るか】
  予約ページはまず Apps Script（tools/booking-api.gs）に空き枠を聞き、落ちていたら
  同じホストの slots.json（控え）に戻る（tools/build-booking.py の loadSlots）。
  控えは以前、毎時の ■1 で「カレンダー取得 → build-slots.py → deploy-booking.py」で作っていたが、
  2026-09-24 22時に API が ok:true になってから ■1 を飛ばすことにしたため、
  **控えを作る人がいなくなり、9/24 09:44 のまま止まっていた**（2026-10-09 発見）。
  控えが古いと、API が落ちた瞬間に過去の日付や埋まった枠が出る。

【どうしたか】
  API の答えをそのまま控えにする。計算は API 側の1か所だけなので、
  build-slots.py（カレンダーの書き出しが要る）とずれる心配が無い。
  毎時点検（tools/maiji-tenken.py）が API の生存確認のついでにこれを --deploy 付きで流す。

  - 所要時間のバケツは build-slots.py の BUCKET と同じ（ページは「必要な分数以上でいちばん短いもの」を選ぶ）
  - 1つでも取れなかったら、何も書かない・配信しない（古い控えを半端な控えで上書きしない）
  - --deploy のときは、本番の控えと枠が違うか、本番の控えが MAX_AGE_H 時間より古いときだけ
    tools/deploy-booking.py --slots-only で slots.json だけを差し替える（index.html は本番のまま）

使い方:
  python3 tools/slots-from-api.py            # 手元の lp/booking/slots.json を作り直すだけ
  python3 tools/slots-from-api.py --deploy   # （2026-10-09 から不要：/slots.json は Apps Script 直結の関数が返す）
"""
import argparse
import datetime as dt
import importlib.util
import json
import pathlib
import re
import subprocess
import sys
import time
import urllib.request
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "lp" / "booking" / "slots.json"
HONBAN = "https://yoyaku.onehitter.jp/slots.json"
JST = ZoneInfo("Asia/Tokyo")
MAX_AGE_H = 5   # ページの staleHours（6）より短く。これを超えたら枠が同じでも差し替える


def bucket_list() -> list:
    """build-slots.py の BUCKET をそのまま使う（値を二重に持たない）"""
    spec = importlib.util.spec_from_file_location("build_slots", ROOT / "tools" / "build-slots.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return list(m.BUCKET)


def api_url() -> str:
    src = (ROOT / "tools" / "build-booking.py").read_text(encoding="utf-8")
    return re.search(r'^API_URL = "([^"]+)"', src, re.M).group(1)


def kiku(url: str, minutes: int) -> list:
    """1バケツぶんを聞く。Apps Script はまれに一時的な 404 を返すので、3回まで取り直す"""
    err = None
    for i in range(3):
        try:
            body = urllib.request.urlopen(
                f"{url}?action=slots&minutes={minutes}&callback=cb", timeout=60).read().decode()
            m = re.match(r"^\s*cb\((.*)\);?\s*$", body, re.S)
            d = json.loads(m.group(1) if m else body)
            if not d.get("ok"):
                raise RuntimeError(d.get("error") or "ok:false")
            slots = d.get("slots")
            if not isinstance(slots, list):
                raise RuntimeError("slots が無い")
            return slots
        except Exception as e:
            err = e
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"所要{minutes}分の取得に失敗: {err}")


def honban() -> dict:
    try:
        with urllib.request.urlopen(f"{HONBAN}?t={int(time.time())}", timeout=30) as r:
            return json.loads(r.read())
    except Exception:
        return {}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", action="store_true", help="必要なら本番の slots.json だけを差し替える")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()

    url = api_url()
    try:
        buckets = {str(m): kiku(url, m) for m in bucket_list()}
    except Exception as e:
        sys.exit(f"控えは作り直していません（API から取れない）: {e}")

    ima = dt.datetime.now(JST)
    data = {
        "generated": ima.isoformat(timespec="minutes"),
        "generatedLabel": ima.strftime("%-m月%-d日 %H:%M"),
        "staleHours": 6,
        "source": "apps-script",
        "buckets": buckets,
    }
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    sentou = (buckets.get("60") or [{}])[0].get("date", "なし")
    print(f"控えを作り直しました: {out.relative_to(ROOT)}（{data['generatedLabel']}、60分枠の先頭 {sentou}）")

    if not a.deploy:
        return
    h = honban()
    riyuu = None
    if h.get("buckets") != buckets:
        riyuu = "枠が変わった"
    else:
        try:
            keika = (ima - dt.datetime.fromisoformat(h["generated"])).total_seconds() / 3600
        except Exception:
            keika = None
        if keika is None or keika > MAX_AGE_H:
            riyuu = f"本番の控えが古い（{h.get('generatedLabel', '不明')}）"
    if not riyuu:
        print(f"本番の控えは最新（{h.get('generatedLabel')}）。差し替えなし")
        return
    print(f"本番の控えを差し替えます（{riyuu}）")
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "deploy-booking.py"), "--slots-only"],
                       capture_output=True, text=True)
    print((r.stdout + r.stderr).strip())
    if r.returncode != 0:
        sys.exit("本番の控えの差し替えに失敗しました")


if __name__ == "__main__":
    main()
