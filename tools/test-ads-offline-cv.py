#!/usr/bin/env python3
"""`tools/ads-offline-cv.py` を、偽のCSVで確かめる。

    python3 tools/test-ads-offline-cv.py

**このCSVは実際の広告費の最適化に使われる。** 金額や件数を取り違えると、
自動入札が間違ったほうへ学習する。**通すべき行と落とすべき行を、1件ずつ検算する。**
"""
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools" / "ads-offline-cv.py"
tmp = pathlib.Path(tempfile.mkdtemp())

(tmp / "yoyaku.csv").write_text("""order_id,gclid,申込日,氏名,電話番号
OH-20260901-mizumawari-AAAA,GCL_AAA,2026/09/01 10:00,テスト太郎,08000000000
OH-20260902-aircon-BBBB,GCL_BBB,2026/09/02 11:00,テスト花子,08000000001
OH-20260903-mizumawari-CCCC,,2026/09/03 12:00,自然流入さん,08000000002
OH-20260601-mizumawari-DDDD,GCL_DDD,2026/06/01 09:00,むかしさん,08000000003
OH-20260904-nenmatsu-EEEE,GCL_EEE,2026/09/04 09:00,キャンセルさん,08000000004
""", encoding="utf-8")

(tmp / "daicho.csv").write_text("""order_id,施工日,売上,メニュー
OH-20260901-mizumawari-AAAA,2026/09/20,"33,660",浴室+キッチン
OH-20260902-aircon-BBBB,2026/09/22,"108,900",エアコン3台
OH-20260903-mizumawari-CCCC,2026/09/21,"20,900",浴室
OH-20260601-mizumawari-DDDD,2026/09/20,"55,000",水まわり
OH-20260904-nenmatsu-EEEE,2026/09/23,0,キャンセル
OH-99999999-unknown-ZZZZ,2026/09/20,"10,000",台帳にだけある
""", encoding="utf-8")

ok = True


def chk(label, cond, extra=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + (("  " + str(extra)) if extra else ""))
    if not cond:
        ok = False


def run(*extra):
    r = subprocess.run([sys.executable, str(TOOL),
                        "--yoyaku", str(tmp / "yoyaku.csv"),
                        "--daicho", str(tmp / "daicho.csv"),
                        "--kijun", "2026-09-30", *extra],
                       capture_output=True, text=True)
    return r.stdout + r.stderr


# --- 1. 下見（--out なし）は何も書かない ---
out = run()
chk("戻せるのは2件だけ", "| **戻せる（CSVに入る）** | **2** |" in out, out[:400])
chk("gclid が空の行は落ちる", "| gclid が空（広告経由でない） | 1 |" in out)
chk("売上0の行は落ちる", "| 売上が0または空 | 1 |" in out)
chk("台帳にしか無い注文IDは落ちる", "| 予約_Web に無い注文ID | 1 |" in out)
chk("90日を超えた行は落ちて、警告が出る",
    "| **クリックから90日超（戻せない）** | **1** |" in out and "OH-20260601" in out, out[-500:])
chk("合計金額が出る（33,660+108,900）", "142,560円" in out, out)
chk("--out が無ければ何も書かない", "何も書いていません" in out)
chk("下見の時点でファイルが無い", not (tmp / "x.csv").exists())

# --- 2. 書き出し ---
out = run("--out", str(tmp / "x.csv"))
chk("書いたと言う", "2件 書きました" in out, out[-300:])
body = (tmp / "x.csv").read_text(encoding="utf-8")
chk("1行目がタイムゾーン", body.splitlines()[0] == "Parameters:TimeZone=Asia/Tokyo",
    body.splitlines()[0])
chk("2行目が列名",
    body.splitlines()[1] == "Google Click ID,Conversion Name,Conversion Time,"
                            "Conversion Value,Conversion Currency", body.splitlines()[1])
chk("gclid と金額が入る", "GCL_AAA" in body and "33660" in body and "108900" in body)
chk("日時に時差が入る", "+09:00" in body)
chk("通貨は JPY", body.count("JPY") == 2)

# --- 3. 個人情報を1文字も出さない（いちばん大事） ---
for ng in ("テスト太郎", "テスト花子", "08000000000", "浴室", "エアコン3台"):
    chk(f"CSVに『{ng}』が出ない", ng not in body)

# --- 4. コンバージョン名を取り違えない ---
chk("既定の名前は『受注（オフライン）』", "受注（オフライン）" in body, body.splitlines()[2])
out = run("--out", str(tmp / "y.csv"), "--name", "べつの名前")
chk("--name で変えられる", "べつの名前" in (tmp / "y.csv").read_text(encoding="utf-8"))

# --- 5. 見出しが違うCSVでは、黙らずに止まる ---
(tmp / "bad.csv").write_text("foo,bar\n1,2\n", encoding="utf-8")
r = subprocess.run([sys.executable, str(TOOL), "--yoyaku", str(tmp / "bad.csv"),
                    "--daicho", str(tmp / "daicho.csv")], capture_output=True, text=True)
chk("見出しが読めなければ、実際の見出しを出して止まる",
    r.returncode != 0 and "・foo" in r.stderr, r.stderr[:200])

print("\n" + ("すべて通りました" if ok else "失敗あり"))
sys.exit(0 if ok else 1)
