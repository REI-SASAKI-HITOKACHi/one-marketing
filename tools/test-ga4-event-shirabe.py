#!/usr/bin/env python3
"""`tools/ga4-event-shirabe.py` を、鍵なしで動かして確かめる。

    python3 tools/test-ga4-event-shirabe.py

**CMOの環境で一発勝負で走らせる道具なので、落ちないことを先に確かめておく。**
偽のAPIを相手に、①ホスト別の合算 ②日別の日付の並べ替え ③0件のときの出方 を見る。
"""
import contextlib
import importlib.util
import io
import json
import pathlib
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("sh", ROOT / "tools" / "ga4-event-shirabe.py")
sh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sh)

HOSTS = [("lp.onehitter.jp", "/survey/", 7), ("survey.onehitter.jp", "/", 5)]
DAYS = [("20260905", 3), ("20260910", 6), ("20260919", 3)]
karappo = {"rows": []}


def fake_factory(host_rows, day_rows):
    def fake(req, timeout=None):
        body = json.loads(req.data.decode())
        dims = [d["name"] for d in body.get("dimensions", [])]
        if dims == ["date"]:
            rows = [{"dimensionValues": [{"value": d}],
                     "metricValues": [{"value": str(n)}]} for d, n in day_rows]
        else:
            rows = [{"dimensionValues": [{"value": h}, {"value": p}],
                     "metricValues": [{"value": str(n)}]} for h, p, n in host_rows]

        class R:
            def read(self): return json.dumps({"rows": rows}).encode()
            def __enter__(self): return self
            def __exit__(self, *a): return False
        return R()
    return fake


sh.load_sheets_client = lambda: type("M", (), {
    "load_credentials": staticmethod(lambda: {}),
    "access_token": staticmethod(lambda i, scope=None: "t")})()

ok = True


def chk(label, cond, extra=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + (("  " + str(extra)) if extra else ""))
    if not cond:
        ok = False


def run(argv):
    sys.argv = argv
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        sh.main()
    return buf.getvalue()


# --- 1. ホスト別の合算と日別 ---
urllib.request.urlopen = fake_factory(HOSTS, DAYS)
out = run(["x", "--event", "survey_complete",
           "--start", "2026-09-05", "--end", "2026-09-19", "--daily"])
chk("合計がホスト2つの合算になる（7+5=12）", "合計 12 件" in out, out[:200])
chk("両方のホストが出る",
    "lp.onehitter.jp" in out and "survey.onehitter.jp" in out)
chk("期間が見出しに出る", "2026-09-05〜2026-09-19" in out)
chk("日別が出る", "## 日別" in out)
chk("GA4のYYYYMMDDを読める形に直す", "2026-09-10" in out and "20260910" not in out, out[-300:])

# --- 2. 0件のとき ---
urllib.request.urlopen = fake_factory([], [])
out = run(["x", "--event", "purchase", "--days", "90"])
chk("0件なら「外して問題ありません」と言う", "0件です" in out and "外して" in out, out[:200])
chk("0件のとき日別を出しにいかない", "## 日別" not in out)

# --- 3. 一覧（--event なし） ---
urllib.request.urlopen = fake_factory([("generate_lead", "lp.onehitter.jp", 4),
                                       ("teltap", "one-hitter.jp", 9)], [])
out = run(["x", "--days", "28"])
chk("設計のイベントに印が付く", "`generate_lead` ⭐" in out, out[:300])
chk("設計に無いものには印が付かない", "`teltap` ⭐" not in out)

print("\n" + ("すべて通りました" if ok else "失敗あり"))
sys.exit(0 if ok else 1)
