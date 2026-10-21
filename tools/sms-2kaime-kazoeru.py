#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1・2便目で反応が無かった方への「2回目」（12月向け）の対象を数える（表示のみ・シートは書かない）。

    python3 tools/sms-2kaime-kazoeru.py

数え方（docs/SMS-2回目-12月向け-案.md）：
  1. 【1便目】【2便目】タブの各行の E列を見る
       空欄         → まだ送っていない（2回目の対象外。まず1回目を送る）
       返信あり／不通・エラー／対象外 → 外す
       送信済み     → 次へ
  2. I列（返信メモ）に何か書いてある → 外す（「不要」などの返信）
  3. 台帳で照合し直す：名乗り（atesaki_ok＝最新の施工が自社）／クレーム履歴／
     1回目の送信日より後の施工・今日より先の予約 → 外す
  4. 送れる日＝1回目の送信日＋30日。送信日は J列「送った日」（YYYY-MM-DD）。空なら A列の予定日で仮置きし「仮」と出す
出すのは件数と行番号だけ（氏名・電話は出さない）。
"""
import sys, importlib.util, os, re, datetime, urllib.parse, time, collections
sys.argv = [sys.argv[0]]
sys.path.insert(0, "tools")
s = importlib.util.spec_from_file_location("dk", "tools/daichou-koushin.py")
dk = importlib.util.module_from_spec(s)
s.loader.exec_module(dk)
import meigi_check as MC

TABS = ["【1便目】11月SMS_送信（17名・10/20）", "【2便目】11月SMS_送信（83名・10/20と10/27）"]
YOTEI = {"1便目": datetime.date(2026, 10, 20), "第1陣": datetime.date(2026, 10, 20), "第2陣": datetime.date(2026, 10, 27)}

dsk = MC._load()
o_ = dsk.sc.call


def call(*a, **k):
    for i in range(8):
        try:
            return o_(*a, **k)
        except SystemExit as e:
            if "429" not in str(e) or i == 7:
                raise
            time.sleep(20 * (i + 1))


dsk.sc.call = call
hyou = dsk.meigi_hyou()
sc = dk._sc()
tok = sc.access_token(sc.load_credentials())
SS = dk.SS
L = dk._api(sc, tok, f"/{SS}/values/{urllib.parse.quote('顧客管理台帳!A16:AH1200', safe='')}").get("values", [])
claim = {dk.tn(r[3]) for r in L if len(r) > 32 and str(r[32]).strip() and len(r) > 3 and dk.tn(r[3])}
jobs = dk.jobs_yomu(sc, tok)
today = datetime.date.today()

for T in TABS:
    rows = dk._api(sc, tok, f"/{SS}/values/{urllib.parse.quote(T + '!A6:J300', safe='')}").get("values", [])
    c = collections.Counter()
    kanou = collections.Counter()
    hazushi = []
    for i, r in enumerate(rows, start=6):
        r = r + [""] * (10 - len(r))
        if not r[2]:
            continue
        jin = r[0].split(" ")[0]
        e = r[4].strip()
        if not e:
            c["まだ送っていない（1回目が先）"] += 1
            continue
        if e != "送信済み":
            c[f"×E列「{e}」"] += 1
            continue
        if r[8].strip():
            c["×返信メモあり"] += 1
            hazushi.append((i, "返信メモ"))
            continue
        m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", r[9].strip())
        sousin, kari = (datetime.date(*map(int, m.groups())), "") if m else (YOTEI.get(jin, today), "（仮）")
        t, n = dk.tn(r[2]), dk.nn(r[1])
        ok, riyuu = MC.atesaki_ok(hyou, t, r[1], "自社")
        why = []
        if not ok:
            why.append("名乗り")
        if t in claim:
            why.append("クレーム")
        if any(x["d"] > sousin and (x["t"] == t or x["n"] == n) for x in jobs):
            why.append("送信後に施工・予約")
        if why:
            c["×" + "・".join(why)] += 1
            hazushi.append((i, "・".join(why)))
            continue
        c["○2回目の対象"] += 1
        kanou[f"{sousin + datetime.timedelta(days=30)}以降{kari}"] += 1
    print(f"== {T}")
    for k, v in sorted(c.items()):
        print(f"  {k}: {v}")
    for k, v in sorted(kanou.items()):
        print(f"    送れる日 {k}: {v}名")
    for h in hazushi:
        print(f"    外した行 {h[0]}：{h[1]}")
