#!/usr/bin/env python3
"""tools/nyusatsu-hikaku.py のテスト（鍵なしで動く）"""
import importlib.util
import pathlib

spec = importlib.util.spec_from_file_location("nh", pathlib.Path(__file__).with_name("nyusatsu-hikaku.py"))
nh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nh)

HEAD = ["取得日", "日付", "キャンペーン", "広告グループ", "費用", "表示回数", "クリック"]
NICHI = [HEAD,
         ["", "2026-10-01", "c", "A", 1000, 50, 4],
         ["", "2026-10-01", "c", "B", 500, 10, 1],
         ["", "2026-10-01", "c", "A", 9999, 99, 9],   # 同じ日・同じグループの2行目は無視
         ["", "2026-10-02", "c", "A", 2000, 20, 2]]
WEB = [["受信日時"] + [""] * 14,
       ["2026-10-01 10:00"] + [""] * 13 + ["gads_aircon"],
       ["2026-10-02 10:00"] + [""] * 13 + ["hp_top"]]


def check(name, cond):
    print(("PASS " if cond else "FAIL ") + name)
    assert cond


d = nh.nichiji(NICHI, "2026-10-01", "2026-10-03")
check("同じ日・グループの2行目を数えない", d["2026-10-01"] == [60, 5, 1500.0])
m = nh.moushikomi(WEB, "2026-10-01", "2026-10-03", ["2026-10-02"])
check("gads_ と追加分だけ数える", m == {"2026-10-01": 1, "2026-10-02": 1})
jiki = [("2026-10-01", "前"), ("2026-10-02", "後"), ("2099-01-01", "戻した後")]
t = nh.hyou(d, m, jiki, "2026-10-01", "2026-10-03")
check("行の無い日に印", "10/03（行なし）" in t)
check("行の無い日は日数に入れない", "| 後 | 1 |" in t)
check("まだ来ていない時期は空欄", "| 戻した後 | 0 | | |" in t)
print("すべて通りました")
