#!/usr/bin/env python3
"""`tools/ads-offline-cv.py` を、偽の 予約_Web CSV で確かめる。

    python3 tools/test-ads-offline-cv.py

**このCSVは実際の広告費の最適化に使われる。** 金額や件数を取り違えると、
自動入札が間違ったほうへ学習する。**通す行と落とす行を1件ずつ検算する。**
"""
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools" / "ads-offline-cv.py"
tmp = pathlib.Path(tempfile.mkdtemp())

# 予約_Web タブを模した1本。★ は crm が台帳と紐づけた列（20260913-03-crm）
FULL = """NetlifyのID,申込日時,氏名,TEL,注文ID,gclid,★売上行への参照,★売上（税込）,★台帳の最終施工日
n001,2026/09/01 10:00,テスト太郎,08000000000,OH-20260901-mizumawari-AAAA,GCL_AAA,9月_売上!A12,"33,660",2026/09/20
n002,2026/09/02 11:00,テスト花子,08000000001,OH-20260902-aircon-BBBB,GCL_BBB,9月_売上!A13,"108,900",2026/09/22
n003,2026/09/03 12:00,自然流入,08000000002,OH-20260903-mizumawari-CCCC,,9月_売上!A14,"20,900",2026/09/21
n004,2026/06/01 09:00,むかし,08000000003,OH-20260601-mizumawari-DDDD,GCL_DDD,9月_売上!A15,"55,000",2026/09/20
n005,2026/09/04 09:00,キャンセル,08000000004,OH-20260904-nenmatsu-EEEE,GCL_EEE,,,
n006,2026/09/05 09:00,予約フォーム,08000000005,,GCL_FFF,9月_売上!A16,"44,000",2026/09/25
"""
(tmp / "yoyaku.csv").write_text(FULL, encoding="utf-8")

ok = True


def chk(label, cond, extra=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + (("  " + str(extra)) if extra else ""))
    if not cond:
        ok = False


def run(path, *extra):
    r = subprocess.run([sys.executable, str(TOOL), str(path),
                        "--kijun", "2026-09-30", *extra], capture_output=True, text=True)
    return r.stdout + r.stderr, r.returncode


# --- 1. 下見 ---
out, _ = run(tmp / "yoyaku.csv")
chk("戻せるのは3件（うち1件は予約フォーム経由）",
    "| **戻せる（CSVに入る）** | **3** |" in out, out[:500])
chk("gclid が空の行は落ちる", "| gclid が空（広告経由でない） | 1 |" in out)
chk("施工前・入金前は落ちる（異常ではない）", "| 施工前・入金前・キャンセル | 1 |" in out)
chk("90日超は落ちて、警告が出る",
    "| **クリックから90日超（戻せない）** | **1** |" in out and "OH-20260601" in out)
chk("合計金額（33,660+108,900+44,000）", "186,560円" in out, out)
chk("--out が無ければ何も書かない", "何も書いていません" in out)

# --- 2. 書き出し ---
out, _ = run(tmp / "yoyaku.csv", "--out", str(tmp / "x.csv"))
body = (tmp / "x.csv").read_text(encoding="utf-8")
chk("3件書く", "3件 書きました" in out, out[-200:])
chk("1行目がタイムゾーン", body.splitlines()[0] == "Parameters:TimeZone=Asia/Tokyo")
chk("2行目が列名",
    body.splitlines()[1] == "Google Click ID,Conversion Name,Conversion Time,"
                            "Conversion Value,Conversion Currency")
chk("予約フォーム経由（注文IDなし）も入る", "GCL_FFF" in body and "44000" in body)

# --- 3. 個人情報を1文字も出さない（いちばん大事） ---
for ng in ("テスト太郎", "テスト花子", "08000000000", "n001", "9月_売上"):
    chk(f"CSVに『{ng}』が出ない", ng not in body)

# --- 4. 広告経由の受注がまだ無いとき、0行のCSVが出る ---
(tmp / "kara.csv").write_text(
    "NetlifyのID,申込日時,注文ID,gclid,★売上（税込）,★台帳の最終施工日\n"
    "n900,2026/09/10 10:00,OH-20260910-mizumawari-XXXX,,,\n", encoding="utf-8")
out, _ = run(tmp / "kara.csv", "--out", str(tmp / "zero.csv"))
z = (tmp / "zero.csv").read_text(encoding="utf-8").splitlines()
chk("0件でも落ちない", "戻せる行はありません" in out, out[:300])
chk("0行のCSVでも見出しは出る", len(z) == 2 and z[1].startswith("Google Click ID"), z)

# --- 5. 注文IDが無くても NetlifyのID で動く ---
(tmp / "noid.csv").write_text(
    "NetlifyのID,申込日時,gclid,★売上（税込）,★台帳の最終施工日\n"
    "n801,2026/09/10 10:00,GCL_ZZZ,\"11,000\",2026/09/20\n", encoding="utf-8")
out, _ = run(tmp / "noid.csv")
chk("注文ID列が無くても動き、断り書きが出る",
    "| **戻せる（CSVに入る）** | **1** |" in out and "NetlifyのIDを鍵にしています" in out, out[:600])

# --- 6. 申込日時が無ければ、期限を見ていないと断る ---
(tmp / "nodate.csv").write_text(
    "NetlifyのID,gclid,★売上（税込）,★台帳の最終施工日\n"
    "n802,GCL_YYY,\"22,000\",2026/09/20\n", encoding="utf-8")
out, _ = run(tmp / "nodate.csv")
chk("申込日時が無ければ、期限を見ていないと断る", "90日の期限を見ていません" in out, out[:600])

# --- 7. 鍵になる列が1つも無ければ止まる ---
(tmp / "bad.csv").write_text("foo,bar\n1,2\n", encoding="utf-8")
out, rc = run(tmp / "bad.csv")
chk("鍵が無ければ、見出しを出して止まる",
    rc != 0 and ("・foo" in out or "続けられません" in out), out[:300])

print("\n" + ("すべて通りました" if ok else "失敗あり"))
sys.exit(0 if ok else 1)
