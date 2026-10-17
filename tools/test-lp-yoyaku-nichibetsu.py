#!/usr/bin/env python3
"""tools/lp-yoyaku-nichibetsu.py を偽の GA4 結果で確かめる。"""
import json, pathlib, subprocess, sys, tempfile
TOOL = pathlib.Path(__file__).resolve().parent / "lp-yoyaku-nichibetsu.py"
tmp = pathlib.Path(tempfile.mkdtemp())
G = "/aircon-c/?src=gads_aircon&gclid=X"
GE = "/aircon-e/?src=gads_aircon&gclid=Y"
rows = [
    ["2026101110", "page_view", "lp.onehitter.jp", G, 10], ["2026101110", "page_view", "yoyaku.onehitter.jp", G, 1],
    ["2026101610", "page_view", "lp.onehitter.jp", G, 8], ["2026101610", "page_view", "yoyaku.onehitter.jp", G, 0],
    ["2026101618", "page_view", "lp.onehitter.jp", G, 4], ["2026101618", "page_view", "yoyaku.onehitter.jp", G, 1],
    ["2026101622", "page_view", "lp.onehitter.jp", GE, 2], ["2026101622", "page_view", "yoyaku.onehitter.jp", GE, 1],
    ["2026101610", "page_view", "lp.onehitter.jp", "/kabi/?src=gads_kabi", 50],   # カビは入れない
    ["2026101610", "page_view", "lp.onehitter.jp", "/aircon-c/?src=ig", 6],          # 広告でない（C対E には入る）
    ["2026101610", "cta_click", "lp.onehitter.jp", "/aircon-c/?src=ig", 2],
    ["2026101407", "page_view", "lp.onehitter.jp", "/aircon-e/?src=x", 99],          # 起点より前は C対E に入れない
]
(tmp / "g.json").write_text(json.dumps({"start": "2026-10-11", "end": "2026-10-16", "rows": rows}), encoding="utf-8")
out = subprocess.run([sys.executable, str(TOOL), "--json", str(tmp / "g.json"),
                      "--kugiri", "2026-10-16T16:50", "--kugiri", "2026-10-16T21:28"], capture_output=True, text=True)
o = out.stdout + out.stderr
ok = True
def chk(l, c):
    global ok
    print(("PASS " if c else "FAIL ") + l)
    if not c: ok = False
chk("10/11 の率", "| 10/11 | 10 | 1 | 10.0% |" in o)
chk("10/16 を区切りの前後3つに分ける", "| 10/16（前） | 8 | 0 |" in o and "| 10/16（後1） | 4 | 1 |" in o and "| 10/16（後2） | 2 | 1 |" in o)
chk("カビLP（gads_kabi）は広告LPの率に入れない", "| **計** | **24** |" in o)
chk("C対E：起点より前は入れず、全ユーザーで数える", "| C | 18 | 2 |" in o and "| E | 2 | 0 |" in o)
chk("採用の線が出る", "E を採用する線" in o)
if not ok: print(o)
print("すべて通りました" if ok else "失敗あり"); sys.exit(0 if ok else 1)
