#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""作業完了フォームの「画面1（お客様に見せる画面）」を、どちらの名義で出すかを決める。

依頼 `20260925-01-crm`（CMO）。画面1 にはワンヒッターのアンケートQRがあり、その完了画面には
ワンヒッターの Google クチコミ・電話 080-8043-8259・公式LINE が出る。
**本舗名義の施工でこれを見せると、2026-09-11 の事故と同じ型になる**（本舗のお客様にワンヒッターの名乗り）。

## 決め方（名乗り照合の規則そのまま）

名乗りは「台帳の最新の施工の名義」。**画面1 を出す時点では、今日の施工が「最新の施工」**。
だから過去の履歴は関係なく、決め手は次の2つだけになる。

1. **今日の施工の売上種類**（`kanryo-yotei.json` の `売上種類`）。空・不明なら「不明」
2. **同じ日に本舗の行があれば本舗**（和真さん 2026-09-20「同じ日に自社が入ってる場合追加分で
   自社にしてる場合があるからそれは本舗受注にして」）。同じ日の行は
   - 台帳（`derive-soushin-keitou.py` の施工一覧。氏名で引く）と
   - `kanryo-yotei.json` のほかの受注（同じ氏名・同じ日）
   の両方から探す。台帳には当日の行がまだ無いことが多いので、受注の側も見る。

**「本舗 → 後日 自社」は自社**（原則どおり）。前回が本舗でも、今日が自社なら自社。

返り値は "自社" / "本舗" / "不明"。**画面1 でアンケートQR（＝クチコミ依頼）を出してよいのは "自社" のときだけ。**

    import kanryo_meigi as KM
    jobs = KM.daichou_jobs()              # 台帳の施工一覧（認証が要る。読めなければ例外）
    m = KM.gamen1_meigi(y, yotei, jobs)   # y は kanryo-yotei.json の1件
    python3 tools/kanryo_meigi.py --kensan   # 偽データの検算（シートに触らない）
"""

import datetime
import importlib.util
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URIAGE_SHU = {"One Hitter": "自社", "自社": "自社", "本舗": "本舗", "本舗(ロイ)": "本舗"}


def _dsk():
    spec = importlib.util.spec_from_file_location(
        "derive_soushin_keitou", os.path.join(ROOT, "tools", "derive-soushin-keitou.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def name_norm(n):
    return re.sub(r"\s", "", str(n or ""))


def hi(s):
    m = re.match(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", str(s or "").strip())
    return datetime.date(*(int(x) for x in m.groups())) if m else None


def daichou_jobs(cache=None):
    """台帳の施工一覧 [(日付, TEL, 氏名, 名義の生の値), ...]。**読めなければ例外**（黙って素通ししない）。"""
    return _dsk().jobs_yomu(cache)


def gamen1_meigi(y, yotei, jobs):
    """画面1 の名義。"自社" / "本舗" / "不明"。"""
    kyou = hi(y.get("施工日付"))
    nm = name_norm(y.get("氏名"))
    jibun = URIAGE_SHU.get(str(y.get("売上種類") or "").strip())
    if not kyou or not nm or not jibun:
        return "不明"
    sonohi = {jibun}
    for x in yotei or []:
        if x is y or x.get("id") == y.get("id"):
            continue
        if hi(x.get("施工日付")) == kyou and name_norm(x.get("氏名")) == nm:
            sonohi.add(URIAGE_SHU.get(str(x.get("売上種類") or "").strip(), "不明"))
    for d, _tel, jn, mg in jobs or []:
        if d == kyou and jn == nm:
            sonohi.add(URIAGE_SHU.get(mg, "本舗" if "本舗" in str(mg) else "不明"))
    if "本舗" in sonohi:
        return "本舗"
    if "不明" in sonohi:
        return "不明"
    return "自社"


def kensan():
    D = datetime.date
    jobs = [(D(2026, 9, 27), "", "検算花子", "本舗"),        # 当日の本舗行が台帳に入っている
            (D(2025, 3, 1), "", "検算太郎", "本舗")]          # 前回は本舗（今日が自社なら自社）
    yotei = [
        {"id": "a", "氏名": "検算 太郎", "施工日付": "2026-09-27", "売上種類": "One Hitter"},
        {"id": "b", "氏名": "検算 花子", "施工日付": "2026-09-27", "売上種類": "One Hitter"},
        {"id": "c", "氏名": "検算 次郎", "施工日付": "2026-09-27", "売上種類": "One Hitter"},
        {"id": "d", "氏名": "検算 次郎", "施工日付": "2026-09-27", "売上種類": "本舗"},
        {"id": "e", "氏名": "検算 三郎", "施工日付": "2026-09-27", "売上種類": ""},
        {"id": "f", "氏名": "検算 四郎", "施工日付": "2026-09-27", "売上種類": "本舗"},
        {"id": "g", "氏名": "新規 さん", "施工日付": "2026-09-27", "売上種類": "One Hitter"},
    ]
    machi = {
        "a": ("自社", "前回が本舗でも、今日が自社なら自社（本舗→後日自社の原則）"),
        "b": ("本舗", "同じ日の本舗行が台帳にある → 本舗"),
        "c": ("本舗", "同じ日の本舗の受注がほかにある → 本舗（追加分の自社行）"),
        "d": ("本舗", "今日が本舗 → 本舗"),
        "e": ("不明", "売上種類が空 → 不明（出さない）"),
        "f": ("本舗", "今日が本舗 → 本舗"),
        "g": ("自社", "台帳にいない新規でも、今日の施工が自社なら自社"),
    }
    ng = 0
    for y in yotei:
        m = gamen1_meigi(y, yotei, jobs)
        ok = m == machi[y["id"]][0]
        ng += not ok
        print(f"  [{'OK' if ok else 'NG'}] {machi[y['id']][1]} → {m}")
    print("すべてOK" if not ng else f"★★ NG {ng}件")
    return ng


if __name__ == "__main__":
    sys.exit(1 if kensan() else 0)
