#!/usr/bin/env python3
"""`tools/ad-group-hyou.py` を偽の 予約_Web CSV で確かめる。

    python3 tools/test-ad-group-hyou.py

**10/9 の継続判定に使う表なので、件数と金額を1つずつ検算する。**
"""
import pathlib, subprocess, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools" / "ad-group-hyou.py"
tmp = pathlib.Path(tempfile.mkdtemp())

(tmp / "y.csv").write_text(
    "注文ID,src,ag,★売上（税込）\n"
    "OH-1,gads_mizumawari,111,\"49,170\"\n"     # 浴室：受注
    "OH-2,gads_aircon,222,\n"                   # エアコン：申込のみ
    "OH-3,gads_mizumawari,333,\n"               # レンジフード：申込のみ
    "OH-4,gads_mizumawari,111,\"33,660\"\n"     # 浴室：受注
    "OH-5,gbp,,\"20,000\"\n"                    # 広告ではない
    "OH-6,gads_aircon,,\n",                     # ag の受け側が入る前
    encoding="utf-8")

ok = True
def chk(l, c, e=""):
    global ok
    print(("PASS " if c else "FAIL ") + l + (("  " + str(e)) if e else ""))
    if not c: ok = False

def run(*a):
    r = subprocess.run([sys.executable, str(TOOL), str(tmp / "y.csv"), *a], capture_output=True, text=True)
    return r.stdout + r.stderr, r.returncode

out, _ = run("--ag-name", "111=B_浴室", "--ag-name", "222=A_エアコン", "--ag-name", "333=B_レンジフード",
             "--hiyou", "B_浴室=8048", "--hiyou", "A_エアコン=11723", "--hiyou", "B_レンジフード=3296")
chk("浴室：申込2・受注2・82,830円", "| B_浴室 | — | — | 2 | 2 | 82,830円 |" in out, out)
chk("エアコン：申込1・受注0", "| A_エアコン | — | — | 1 | 0 | 0円 |" in out)
chk("浴室の受注CPA（8048÷2）", "4,024円" in out)
chk("広告でない申込（gbp）は数えない", "20,000" not in out)
chk("lp 列が無ければ版を分けず、そう書く", "今の版と学習版を分けていません" in out)
chk("ag が空の広告申込を別に出して注意する", "（ag なし・gads_aircon）" in out and "受け側が入る前" in out)
chk("合計：申込5・受注2・82,830円", "| **合計** | | | **5** | **2** | **82,830円** |" in out, out[-600:])

out, _ = run("--zenbu")
chk("--zenbu なら広告以外も並ぶ", "gbp" in out)

(tmp / "noag.csv").write_text("注文ID,src,★売上（税込）\nOH-1,gads,100\n", encoding="utf-8")
r = subprocess.run([sys.executable, str(TOOL), str(tmp / "noag.csv")], capture_output=True, text=True)
chk("ag の列が無ければ、見出しを出して止まる", r.returncode != 0 and "ag" in r.stderr, r.stderr[:300])

# 学習版の A/B（2026-09-30）：src は同じ、lp／フォーム名で分ける
(tmp / "ab.csv").write_text(
    "注文ID,src,ag,lp,★売上（税込）\n"
    "OH-1,gads_aircon,222,aircon,\"33,660\"\n"
    "OH-2,gads_aircon,222,aircon-c,\n"
    "OH-3,gads_aircon,222,reserve-aircon-c,\"12,100\"\n"   # フォーム名の形でも読める
    "OH-4,gads_mizumawari,111,mizumawari-b,\n"
    "OH-5,gads_mizumawari,111,,\n",
    encoding="utf-8")
r = subprocess.run([sys.executable, str(TOOL), str(tmp / "ab.csv"), "--ag-name", "222=A_エアコン",
                    "--ag-name", "111=B_浴室", "--hiyou", "A_エアコン:今の版=5000",
                    "--hiyou", "A_エアコン:学習版=6000"], capture_output=True, text=True)
out = r.stdout
chk("今の版：申込1・受注1", "| A_エアコン | 今の版 | aircon | 1 | 1 | 33,660円 | 5,000円 |" in out, out)
chk("学習版：lp とフォーム名の両方の形を同じLPに寄せる", "| A_エアコン | 学習版 | aircon-c | 2 | 1 | 12,100円 | 6,000円 | 3,000円 | 6,000円 |" in out, out)
chk("水まわりの学習版", "| B_浴室 | 学習版 | mizumawari-b | 1 |" in out)
chk("lp が空の行は（不明）で出して注意する", "| B_浴室 | （不明） | — | 1 |" in out and "（不明）」の行" in out)
r = subprocess.run([sys.executable, str(TOOL), str(tmp / "ab.csv"), "--hiyou", "222=5000"], capture_output=True, text=True)
chk("費用が版に分かれていなければ、CPAを出さずにそう書く", "版ごとのCPAは出していません" in r.stdout, r.stdout[-400:])

print("\n" + ("すべて通りました" if ok else "失敗あり")); sys.exit(0 if ok else 1)
