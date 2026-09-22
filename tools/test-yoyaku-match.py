#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`tools/yoyaku-match.py` の照合を、**偽データ**で検算する。シートに一切触らない。

## なぜ偽データか

`予約_Web` のデータ行は今 0 行。**確かめるためにテスト行を書くと、それ自体が汚れになる**
（CMO 2026-09-23「テスト行は書かない」）。台帳も読むだけの約束なので、
照合の中身（`daichou_hiku` / `uriage_hiku` / `awaseru` / `kensan_hani`）を
作り物の台帳・作り物の売上に対して通します。**認証も通信も要りません。**

    python3 tools/test-yoyaku-match.py

ここに出てくる氏名・電話番号は全部でたらめです（090-0000-xxxx）。実在の方ではありません。
"""

import datetime
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("ym", os.path.join(ROOT, "tools", "yoyaku-match.py"))
ym = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ym)

D = datetime.date

# ---- 作り物の台帳（顧客管理台帳のかわり）--------------------------------
# C0001 … 電話も氏名もある人
# C0002 … C0001 と同じ電話を使っている別世帯（実際に3通りある）
# C0003 … 台帳のTEL空欄（957名中152名＝15.9%）。氏名でしか引けない
# C0004 … 最終施工日が 2026/12/1。文字列で比べると 2026/9/3 に負ける
DAICHOU = {
    "tel": {
        "09000000001": [("C0001", "2026/07/01")],
        "09000000002": [("C0002", "2026/06/01")],
        "09000000004": [("C0004", "2026/9/3"), ("C0004", "2026/12/1")],
    },
    "name": {
        "検算太郎": [("C0001", "2026/07/01")],
        "検算花子": [("C0002", "2026/06/01")],
        "検算次郎": [("C0003", "2026/05/01")],
        "検算三郎": [("C0004", "2026/9/3"), ("C0004", "2026/12/1")],
        "同姓同名": [("C0005", "2026/04/01"), ("C0006", "2026/03/01")],
    },
}

# ---- 作り物の名義表（derive-soushin-keitou.py の meigi_hyou() のかわり）----
MEIGI = (
    {"09000000001": ("自社", "2026-07-01"), "09000000002": ("本舗", "2026-06-01")},
    {"検算太郎": ("自社", "2026-07-01"), "検算花子": ("本舗", "2026-06-01"),
     "検算次郎": ("本舗", "2026-05-01")},
)

# ---- 作り物の売上（◯月_売上/顧客 のかわり）------------------------------
URIAGE = [
    {"tab": "7月_売上/顧客", "no": "12", "date": D(2026, 7, 1),
     "tel": "09000000001", "name": "検算太郎", "kin": "16500"},
    {"tab": "6月_売上/顧客", "no": "34", "date": D(2026, 6, 1),
     "tel": "09000000002", "name": "検算花子", "kin": "27500"},
    {"tab": "5月_売上/顧客", "no": "56", "date": D(2026, 5, 1),
     "tel": "", "name": "検算次郎", "kin": "9900"},
]
ZOKUSEI = {"C0001": "乳幼児あり", "C0003": "犬・猫あり"}

ng = 0


def shiken(namae, deta, machi):
    global ng
    ok = deta == machi
    if not ok:
        ng += 1
    print(f"  [{'OK' if ok else 'NG'}] {namae}")
    if not ok:
        print(f"        出た値 : {deta}")
        print(f"        ほしい値: {machi}")


def yoyaku(name, tel, nozomi="", moto="", youbou="", src="", cid="", rt=""):
    return {"name": name, "tel": tel, "nozomi": nozomi, "moto": moto,
            "youbou": youbou, "src": src, "cid": cid, "rt": rt}


print("== 1. 台帳の照合（氏名＋電話の両方が一致したときだけ参照を付ける）==")
shiken("氏名も電話も一致 → 参照あり",
       ym.daichou_hiku(DAICHOU, "09000000001", "検算太郎"),
       ("C0001", "2026/07/01", "氏名＋電話一致"))
shiken("電話だけ一致（氏名が違う）→ 参照は空。手がかりだけ残る",
       ym.daichou_hiku(DAICHOU, "09000000001", "別人太郎"),
       ("", "", "電話だけ一致（C0001）＝参照は付けない"))
shiken("氏名だけ一致（台帳のTEL空欄の人）→ 参照は空",
       ym.daichou_hiku(DAICHOU, "09000000009", "検算次郎"),
       ("", "", "氏名だけ一致（C0003）＝参照は付けない"))
shiken("電話と氏名が別人を指す → どちらも参照にしない",
       ym.daichou_hiku(DAICHOU, "09000000001", "検算花子"),
       ("", "", "電話だけ一致（C0001）／氏名だけ一致（C0002）＝参照は付けない"))
shiken("同姓同名が2人 → 参照を付けず、人が確認する印",
       ym.daichou_hiku(DAICHOU, "", "同姓同名"),
       ("", "", "氏名だけ一致（C0005・C0006）＝参照は付けない"))
shiken("台帳にいない → 該当なし（新規）",
       ym.daichou_hiku(DAICHOU, "09000000099", "新顔さん"),
       ("", "", "該当なし（新規）"))
shiken("電話も氏名も空 → 該当なし（新規）。空欄どうしで当たらないこと",
       ym.daichou_hiku(DAICHOU, "", ""),
       ("", "", "該当なし（新規）"))
shiken("最終施工日は日付として新しいほうを採る（文字列比較だと 2026/9/3 が勝ってしまう）",
       ym.daichou_hiku(DAICHOU, "09000000004", "検算三郎"),
       ("C0004", "2026/12/1", "氏名＋電話一致"))

print("\n== 2. 売上との照合（ご希望日の±14日・氏名＋電話の両方）==")
shiken("両方一致・当日 → 参照と金額",
       ym.uriage_hiku(URIAGE, "09000000001", "検算太郎", D(2026, 7, 1)),
       ("7月_売上/顧客 No.12", "16500", ""))
shiken("両方一致・14日以内 → 参照と金額",
       ym.uriage_hiku(URIAGE, "09000000001", "検算太郎", D(2026, 6, 18)),
       ("7月_売上/顧客 No.12", "16500", ""))
shiken("15日離れている → 何も付けない",
       ym.uriage_hiku(URIAGE, "09000000001", "検算太郎", D(2026, 6, 16)),
       ("", "", ""))
shiken("氏名だけ一致（売上のTELが空欄）→ 参照は空。候補だけ手がかりに",
       ym.uriage_hiku(URIAGE, "09000000009", "検算次郎", D(2026, 5, 1)),
       ("", "", "売上候補 5月_売上/顧客 No.56（片方だけ一致・参照は付けない）"))
shiken("ご希望日が空 → 何もしない",
       ym.uriage_hiku(URIAGE, "09000000001", "検算太郎", None),
       ("", "", ""))

print("\n== 3. 予約1行ぶん（awaseru）==")
a = ym.awaseru(yoyaku("検算 太郎", "090-0000-0001", "2026/07/01",
                      "LP:mizumawari src=google cid=123456 OH-20260701AB"),
               DAICHOU, MEIGI, URIAGE, ZOKUSEI)
shiken("ハイフン入りの電話番号でも引ける（文字列のまま・先頭の0を落とさない）",
       (a["★台帳の顧客ID"], a["★台帳の最終施工日"]), ("C0001", "2026/07/01"))
shiken("名義・属性・売上・流入元がそろう",
       (a["★台帳の名義"], a["★属性"], a["★売上行への参照"], a["★売上（税込）"],
        a["src"], a["cid"], a["_rt"]),
       ("自社", "乳幼児あり", "7月_売上/顧客 No.12", "16500", "google", "123456", "OH-20260701AB"))

b = ym.awaseru(yoyaku("検算 次郎", "090-0000-0099", "2026/05/01"),
               DAICHOU, MEIGI, URIAGE, ZOKUSEI)
shiken("★片方だけ一致でも、名義は「本舗」と出る（取り逃すと 9/11 の事故になる）",
       b["★台帳の名義"], "本舗")
shiken("その行に参照は付かない／属性も付けない（別人かもしれないから）",
       (b["★台帳の顧客ID"], b["★売上行への参照"], b["★属性"]), ("", "", ""))
shiken("台帳の手がかりと売上の手がかりが両方残る",
       b["★照合の手がかり"],
       "氏名だけ一致（C0003）＝参照は付けない／売上候補 5月_売上/顧客 No.56（片方だけ一致・参照は付けない）")

c = ym.awaseru(yoyaku("新顔 さん", "090-0000-0099", "2026/09/25"),
               DAICHOU, MEIGI, URIAGE, ZOKUSEI)
shiken("まったくの新規 → 名義は「不明」。★不明の行にも連絡しない",
       (c["★台帳の顧客ID"], c["★台帳の名義"], c["★照合の手がかり"]),
       ("", "不明", "該当なし（新規）"))

d = ym.awaseru(yoyaku("検算 太郎", "090-0000-0001", "2026/07/01"),
               DAICHOU, None, URIAGE, ZOKUSEI)
shiken("★名義表が読めなかったら「不明」。黙って自社にしない",
       d["★台帳の名義"], "不明")

print("\n== 4. 書き込み先の検算（kensan_hani）==")
IX = {"お名前": 2, "★台帳の顧客ID": 16, "★台帳の名義": 17, "★売上行への参照": 21,
      "成果発生日": 24, "★却下判定": 26, "注文ID": 27, "gclid": 28}


def hajiku(namae, data):
    global ng
    try:
        ym.kensan_hani(data, IX)
    except RuntimeError:
        print(f"  [OK] {namae}")
        return
    ng += 1
    print(f"  [NG] {namae} … 止まらなかった")


shiken("予約_Web の機械の列だけなら通る",
       ym.kensan_hani([{"range": "予約_Web!Q2", "values": [["C0001"]]},
                       {"range": "予約_Web!AA2", "values": [["=IF(1,1,1)"]]}], IX), True)
hajiku("顧客管理台帳への書き込みは止める", [{"range": "顧客管理台帳!A2", "values": [["x"]]}])
hajiku("◯月_売上/顧客 への書き込みは止める", [{"range": "7月_売上/顧客!A4", "values": [["x"]]}])
hajiku("予約_Web でも お名前（C列）は止める", [{"range": "予約_Web!C2", "values": [["x"]]}])
hajiku("他の道具の列（注文ID・AB）は止める", [{"range": "予約_Web!AB2", "values": [["x"]]}])
hajiku("他の道具の列（gclid・AC）は止める", [{"range": "予約_Web!AC2", "values": [["x"]]}])
hajiku("人が入れる列（成果発生日・Y）は止める", [{"range": "予約_Web!Y2", "values": [["x"]]}])

print("\n== 5. 列の割り当て（a1）==")
shiken("27列目は AA（★却下判定の位置）", ym.a1(27), "AA")
shiken("28列目は AB（注文ID）", ym.a1(28), "AB")
shiken("29列目は AC（gclid）", ym.a1(29), "AC")

print()
if ng:
    print(f"★★ NG {ng}件。直すまでシートに書かないこと。")
else:
    print("すべてOK。偽データでの検算は通りました（シートには一切触っていません）。")
sys.exit(1 if ng else 0)
