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

# 増額条件（10/3）と予約ページ経由の行
(tmp / "z.csv").write_text(
    "注文ID,src,ag,lp,★売上（税込）\n"
    + "".join(f"OH-a{i},gads_aircon,222,aircon-c,\n" for i in range(5))
    + "".join(f"OH-b{i},gads_aircon,222,aircon,\n" for i in range(3))
    + "OH-y1,gads_mizumawari,,yoyaku,\n",
    encoding="utf-8")
r = subprocess.run([sys.executable, str(TOOL), str(tmp / "z.csv"), "--ag-name", "222=A_エアコン",
                    "--click", "A_エアコン:学習版=100", "--click", "A_エアコン:今の版=60",
                    "--chuki", "長田さまはgclidなし"], capture_output=True, text=True)
out = r.stdout
chk("クリック100で申込5 → 満たす", "| A_エアコン | 学習版 | aircon-c | 5 |" in out and "○ 満たす" in out, out)
chk("クリック60 → クリック不足", "クリック不足（60/100）" in out)
chk("増額は嶺さんに確認と書く", "嶺さんに確認" in out)
chk("予約ページ経由は版不明として出し、注意する", "（予約ページ・版不明）" in out and "版の比較に入れていない" in out)
chk("注記が出る", "> 長田さまはgclidなし" in out)
(tmp / "z2.csv").write_text("注文ID,src,ag,lp,★売上（税込）\n" + "".join(f"OH-a{i},gads_aircon,222,aircon-c,\n" for i in range(4)), encoding="utf-8")
r = subprocess.run([sys.executable, str(TOOL), str(tmp / "z2.csv"), "--ag-name", "222=A_エアコン",
                    "--click", "A_エアコン:学習版=100"], capture_output=True, text=True)
chk("クリック100で申込4 → 満たさない", "× 満たさない" in r.stdout, r.stdout)
r = subprocess.run([sys.executable, str(TOOL), str(tmp / "z2.csv"), "--ag-name", "222=A_エアコン",
                    "--click", "A_エアコン:学習版=150"], capture_output=True, text=True)
chk("クリック150で申込4 → 満たさない（7件要る）", "× 満たさない" in r.stdout)

(tmp / "k.csv").write_text("注文ID,src,ag,lp,★売上（税込）\nOH-n1,line,,,\"9,702\"\nOH-x,line,,,100\n", encoding="utf-8")
r = subprocess.run([sys.executable, str(TOOL), str(tmp / "k.csv"), "--kotei", "OH-n1=B_浴室:今の版:mizumawari"], capture_output=True, text=True)
chk("--kotei でLINE経由の広告客を指定の版に入れる", "| B_浴室 | 今の版 | mizumawari＊ | 1 | 1 | 9,702円 |" in r.stdout and "取り込みには入らない" in r.stdout, r.stdout)
chk("--kotei に無い line の行は数えない", "| **合計** | | | **1** |" in r.stdout)

# 10/9 判定（--kazu）
import json
(tmp / "kz.json").write_text(json.dumps({"A_エアコン:学習版": {"hiyou": 26200, "click": 100, "lp": 90, "yoyaku": 9},
                                         "A_エアコン:今の版": {"hiyou": 15000, "click": 60, "lp": 55, "yoyaku": 2}}), encoding="utf-8")
(tmp / "kz.csv").write_text("注文ID,src,ag,lp,★売上（税込）\n" + "".join(f"OH-a{i},gads_aircon,222,aircon-c,{'10780' if i == 0 else ''}\n" for i in range(5)), encoding="utf-8")
r = subprocess.run([sys.executable, str(TOOL), str(tmp / "kz.csv"), "--ag-name", "222=A_エアコン", "--kazu", str(tmp / "kz.json")], capture_output=True, text=True)
out = r.stdout
chk("判定表：学習版の行（到達率つき）", "| A_エアコン:学習版 | 26,200円 | 100 | 90（90%） | 9（10%） | 5 | 1 |" in out, out[-1500:])
chk("結論：増額を提案（嶺さんに確認）", "**増額を提案**" in out and "嶺さんに確認" in out)
chk("どこで落ちているか", "いちばん落ちている段" in out)
(tmp / "kz2.json").write_text(json.dumps({"A_エアコン:今の版": {"click": 120, "lp": 110}, "A_エアコン:学習版": {"click": 110, "lp": 100}}), encoding="utf-8")
(tmp / "kz2.csv").write_text("注文ID,src,ag,lp,★売上（税込）\nOH-1,gbp,,,\n", encoding="utf-8")
r = subprocess.run([sys.executable, str(TOOL), str(tmp / "kz2.csv"), "--kazu", str(tmp / "kz2.json")], capture_output=True, text=True)
chk("結論：クリック200以上・申込0なら止める", "**止める**" in r.stdout, r.stdout[-800:])
(tmp / "kz3.json").write_text(json.dumps({"A_エアコン:今の版": {"click": 50, "lp": 45}}), encoding="utf-8")
r = subprocess.run([sys.executable, str(TOOL), str(tmp / "kz2.csv"), "--kazu", str(tmp / "kz3.json")], capture_output=True, text=True)
chk("結論：それ以外は据え置き", "**据え置き**" in r.stdout, r.stdout[-800:])

print("\n" + ("すべて通りました" if ok else "失敗あり")); sys.exit(0 if ok else 1)
