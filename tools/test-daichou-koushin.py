#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`tools/daichou-koushin.py` の検算。**偽データだけ。シートに触らない・認証も要らない。**

    python3 tools/test-daichou-koushin.py

氏名・電話番号は全部でたらめ（090-0000-xxxx）。
"""
import datetime
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0]]          # --kaku などを本体に渡さない
spec = importlib.util.spec_from_file_location("dk", os.path.join(ROOT, "tools", "daichou-koushin.py"))
dk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dk)
D = datetime.date
ng = 0


def shiken(namae, deta, machi):
    global ng
    ok = deta == machi
    ng += not ok
    print(f"  [{'OK' if ok else 'NG'}] {namae}")
    if not ok:
        print(f"        出た値 : {deta}\n        ほしい値: {machi}")


def job(d, t, n, k=10000, menu="エアコン(ノーマル)", keiro="リピート", shu="One Hitter"):
    return {"d": d, "t": t, "n": n, "k": k, "menu": menu, "keiro": keiro, "shu": shu,
            "namae": n, "yuubin": "", "juusho": "", "houjin": "", "_moto": "偽"}


LED = [
    {"顧客ID": "C0001", "顧客名": "検算太郎", "TEL": "09000000001", "統合した表記": "", "受注回数": 1},
    {"顧客ID": "C0002", "顧客名": "検算花子", "TEL": "09000000002", "統合した表記": "", "受注回数": 1},
    {"顧客ID": "C0003", "顧客名": "検算次郎", "TEL": "", "統合した表記": "検算　じろう", "受注回数": 1},
    {"顧客ID": "C0004", "顧客名": "家族父", "TEL": "09000000009", "統合した表記": "", "受注回数": 1},
    {"顧客ID": "C0005", "顧客名": "家族母", "TEL": "09000000009", "統合した表記": "", "受注回数": 1},
    {"顧客ID": "C0006", "顧客名": "同姓同名", "TEL": "09000000006", "統合した表記": "", "受注回数": 1},
    {"顧客ID": "C0007", "顧客名": "同姓同名", "TEL": "09000000007", "統合した表記": "", "受注回数": 1},
]

print("== 1. 誰の施工か（電話が先・氏名は補助）==")
J = [
    job(D(2026, 9, 10), "09000000001", "別の表記"),          # 電話で C0001
    job(D(2026, 9, 11), "", "検算じろう"),                   # 統合した表記で C0003
    job(D(2026, 9, 12), "09000000009", "家族母"),            # 家族の電話 → 氏名で C0005
    job(D(2026, 9, 13), "09000000009", "知らない人"),         # 家族の電話・氏名で絞れない → 要確認
    job(D(2026, 9, 14), "", "同姓同名"),                     # 電話なし・同姓同名2人 → 要確認
    job(D(2026, 9, 15), "09000000099", "検算花子"),          # 別の電話・同じ氏名 → 別の人として新規
    job(D(2026, 9, 16), "09000000088", "新顔一郎"),          # 新規
    job(D(2026, 9, 17), "", "新顔一郎"),                     # 電話なしでも、新規の電話グループと同じ氏名ならそこへ
    job(D(2026, 9, 18), "", "まったく新しい"),               # 電話なし新規
]
wari, shinki, youkaku, chuui = dk.wariate(J, LED)
shiken("電話が1人に当たる → その人（氏名が違っても）", [j["d"].day for j in wari["C0001"]], [10])
shiken("電話なし → 統合した表記の別表記でも当たる", [j["d"].day for j in wari["C0003"]], [11])
shiken("家族で同じ電話 → 氏名で1人に絞れればその人", [j["d"].day for j in wari["C0005"]], [12])
shiken("家族で同じ電話・氏名で絞れない → 要確認", sorted(j["d"].day for j, _ in youkaku), [13, 14])
shiken("新規は3組（別の電話の同じ氏名／新顔一郎（2件）／電話なし）",
       sorted(len(g) for g in shinki), [1, 1, 2])
shiken("同姓同名は統合しない。報告に「同じ氏名の既存あり」", any("C0002" in c for c in chuui), True)

print("\n== 2. 9/5 に別の電話をまとめた人（台帳の件数が多い人）==")
J2 = [job(D(2025, 1, 1), "09000000002", "検算花子"), job(D(2025, 6, 1), "09000000077", "検算花子")]
w1, s1, _, _ = dk.wariate(J2, LED)
shiken("手がかり無しなら、別の電話の行は新規になる", (len(w1["C0002"]), len(s1)), (1, 1))
w2, s2, _, _ = dk.wariate(J2, LED, {"C0002": D(2025, 12, 31)})
shiken("台帳の件数に届かず、最終施工日以前の行なら、その人に入れる", (len(w2["C0002"]), len(s2)), (2, 0))
w3, s3, _, _ = dk.wariate([job(D(2026, 9, 1), "09000000077", "検算花子")], LED, {"C0002": D(2025, 12, 31)})
shiken("最終施工日より後の別の電話は、同姓同名の新しい人として扱う", (len(w3.get("C0002", [])), len(s3)), (0, 1))

print("\n== 3. 集計（9/5 の台帳から逆算した作り方）==")
js = [job(D(2025, 5, 1), "", "x", 10000, "エアコン(ノーマル)", "リピート", "本舗"),
      job(D(2026, 9, 3), "", "x", 20000, "浴室", "HP", "One Hitter"),
      job(D(2026, 9, 3), "", "x", 5000, "エアコン(ノーマル)", "HP", "本舗"),
      job(D(2026, 1, 2), "", "x", 3000, "", "HP", "One Hitter")]
a = dk.shuukei(js, D(2026, 9, 30))
shiken("件数・合計・平均・最高", (a["受注回数"], a["合計受注額"], a["平均単価"], a["最高単価"]), (4, 38000, 9500, 20000))
shiken("初回・最終施工日はシリアル値", (a["初回施工日"], a["最終施工日"]),
       ((D(2025, 5, 1) - dk.EPOCH).days, (D(2026, 9, 3) - dk.EPOCH).days))
shiken("★同じ日に本舗と自社 → 本舗（同日ルール）", a["売上種類"], "本舗")
shiken("主な流入経路はいちばん多いもの", a["主な流入経路"], "HP")
shiken("利用年", a["利用年"], "2025／2026")
shiken("施工メニュー（内訳）は多い順・空欄は数えない", a["施工メニュー（内訳）"], "エアコン(ノーマル)×2／浴室×1")
shiken("種目：空欄の実施メニューは「その他」", (a["エアコン(家庭用)"], a["浴室"], a["その他"]), (2, 1, 1))
shiken("次のおすすめ：換気扇→浴室→キッチン→洗濯機の未購入の先頭2つ", a["次のおすすめ"], "換気扇・キッチン")
shiken("経過(月)：(今日−最終)÷30.4", a["経過(月)"], round(27 / 30.4, 1))

print("\n== 4. 書き換えの判断 ==")
x = dict(a, **{"受注回数": 5})
shiken("台帳の件数のほうが多い → 触らない（None）", dk.sabun(x, a), None)
x = dict(a, **{"経過(月)": 0.1})
shiken("施工行が変わっていなければ 経過(月) だけ", dk.sabun(x, a), {"経過(月)": a["経過(月)"]})
x = dict(a, **{"合計受注額": 1, "施工メニュー（内訳）": "★注記あり"})
s = dk.sabun(x, a)
shiken("金額が変わったら作り直す／AE に★があれば AE は残す", ("合計受注額" in s, "施工メニュー（内訳）" in s), (True, False))

print("\n== 5. 書き込み先の検査 ==")
IX = {k: i for i, k in enumerate(["顧客ID", "顧客名", "法人/個人", "TEL", "郵便番号", "住所", "受注回数"])}
IX.update({"統合した表記": 31, "クレーム履歴（日付・内容・対応）": 32})


def hajiku(namae, rng):
    global ng
    try:
        dk.kensan_hani([{"range": rng, "values": [["x"]]}], IX)
    except RuntimeError:
        print(f"  [OK] {namae}")
        return
    ng += 1
    print(f"  [NG] {namae} … 止まらなかった")


shiken("台帳の集計列（G975）は通る", dk.kensan_hani([{"range": "顧客管理台帳!G975", "values": [[1]]}], IX), True)
hajiku("月次タブへの書き込みは止める", "9月_売上/顧客!A4")
hajiku("AG（クレーム履歴）は止める", "顧客管理台帳!AG20")
hajiku("AF（統合した表記）は止める", "顧客管理台帳!AF20")
hajiku("見出し（15行目）は止める", "顧客管理台帳!G15")
hajiku("1200行より下は止める", "顧客管理台帳!G1201")
IX["写真フォルダ"] = 33
shiken("写真フォルダ（AH）は通る", dk.kensan_hani([{"range": "顧客管理台帳!AH20", "values": [["u"]]}], IX), True)
hajiku("AH より右（AI）は止める", "顧客管理台帳!AI20")

print("\n== 6. 写真フォルダは顧客ID が一致する人だけ・消さない ==")
LED = [{"顧客ID": "C0001", "写真フォルダ": ""}, {"顧客ID": "C0002", "写真フォルダ": "https://x/old"},
       {"顧客ID": "C0003", "写真フォルダ": "https://x/keep"}, {"顧客ID": "C0004", "写真フォルダ": "https://x/same"}]
OK = {"山田": {"id": "C0001", "url": "https://x/a"}, "佐藤": {"id": "C0002", "url": "https://x/new"},
      "同名": {"url": "https://x/no-id"}, "鈴木": {"id": "C0004", "url": "https://x/same"},
      "台帳に無い": {"id": "C9999", "url": "https://x/z"}}
shiken("空欄に入れる・違えば直す・ID なし/台帳に無い/同じ値は入れない・okyaku に無い人は消さない",
       dk.shashin_sabun(LED, OK), {"C0001": "https://x/a", "C0002": "https://x/new"})

print()
print("すべてOK" if not ng else f"★★ NG {ng}件。直すまで --kaku で書かないこと")
sys.exit(1 if ng else 0)
