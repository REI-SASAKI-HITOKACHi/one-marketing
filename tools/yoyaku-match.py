#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`予約_Web` の1行ずつを、顧客管理台帳・顧客属性メモ・各月の売上と機械で突き合わせる。

設計は掲示板 `20260913-03-crm`（CMO 2026-09-14 08:5x 全面採用）。

## この道具がやること

    予約_Web の1行
      ├─ 台帳と照合   → 顧客ID・名義（自社/本舗）・最終施工日・照合の手がかり
      ├─ 属性メモ     → 乳幼児／犬・猫 などの☑を「／」でつないだもの
      ├─ 売上と照合   → ご希望日の±14日に同じ方の施工行があれば、その参照と金額
      └─ 流入元を分解 → src・cid・レントラックス注文番号（OH-…）

## やらないこと（大事）

- **顧客管理台帳を書き換えません。** 台帳は `◯月_売上/顧客` から作る派生データなので、
  手で足すと再生成で消えるか二重になります。新規のお客様は「空欄＝新規」と出るだけです。
  施工が終わって和真さんが売上に1行入れれば、次の再生成で顧客IDが付きます。
- **`◯月_売上/顧客` に予約IDを書き戻しません。** 実績データを触らないためです。
- **お客様に何も送りません。**

## ⚠️ 本舗名義のお客様の扱い

台帳の最新名義が「本舗」の方が自社のLP・予約フォームから申し込むことがあります
（台帳957名のうち **523名＝55%** が本舗名義）。

**受注は自社で構いませんが、確認連絡を SMS・LINE で送らないでください。**
施工前は台帳の最新名義がまだ本舗なので、自社名義の文面は 2026-09-11 の事故と同じことになります。
和真さんが電話で受けてください。該当行には**色が付きます**。

## 照合のしかた

電話番号だけでは足りません（台帳957名のうち **TEL空欄が152名＝15.9%**、
同じTELを2人以上が使っている例が3通り）。
`tools/derive-soushin-keitou.py` の `meigi_shiraberu()` と同じく、
**電話でも氏名でも引き、当たったうち「いちばん新しい施工」の行を採ります。**

電話番号は**文字列のまま**扱います。**数値にすると先頭の0が消えます**（過去に800件消えた事故あり）。

## 使い方

    . ~/.config/one-hitter/line.env
    python3 tools/yoyaku-match.py                  # 照合した結果を表示するだけ（既定）
    python3 tools/yoyaku-match.py --列を作る --confirm WRITE   # ★列の見出しと書式を用意する（最初の1回）
    python3 tools/yoyaku-match.py --confirm WRITE  # 照合してシートに書く（cmo の毎時ルーティンから）
"""

import datetime
import importlib.util
import os
import re
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _mod(name, path):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


sc = _mod("sc", "sheets_client.py")
meigi = _mod("meigi_check", "meigi_check.py")

SS = "1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64"
TAB = "予約_Web"
DAICHOU = "顧客管理台帳"
DAICHOU_HEAD = 15
ZOKUSEI = "顧客属性_メモ"
ZOKUSEI_HEAD = 4
HABA = 14          # 施工済と見なす日数の幅（ご希望日の ±14日）

WRITE = ("--confirm" in sys.argv and "WRITE" in sys.argv)
TSUKURU = "--列を作る" in sys.argv
SHINDAN = "--自己診断" in sys.argv   # 台帳の実在のお客様を使って、照合の道筋を確かめる

# 既存の見出し（A〜N）の右に足す列。★は機械が書く列。
TSUIKA = [
    "src", "cid",
    "★台帳の顧客ID", "★台帳の名義", "★台帳の最終施工日", "★照合の手がかり", "★属性",
    "★売上行への参照", "★売上（税込）",
    "レントラックス注文番号", "成果発生日", "入金確認日", "★却下判定",
]
# 人が手で入れる列（機械は上書きしない）
TEUCHI = {"レントラックス注文番号", "成果発生日", "入金確認日"}


def a1(col):
    s = ""
    while col:
        col, r = divmod(col - 1, 26)
        s = chr(65 + r) + s
    return s


def tel_norm(t):
    """電話番号は**文字列のまま**。数値にしない（先頭の0が消える）。"""
    return re.sub(r"\D", "", str(t or ""))


def hiduke(s):
    m = re.match(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", str(s or "").strip())
    if not m:
        return None
    try:
        return datetime.date(*(int(x) for x in m.groups()))
    except ValueError:
        return None


def yomu(tok, tab, rng):
    return sc.call(tok, f"/{SS}/values/{urllib.parse.quote(tab + '!' + rng, safe='')}").get("values", [])


def hyou_tsukuru(v, head):
    h = v[head - 1]
    ix = {c: i for i, c in enumerate(h)}

    def g(r, k):
        i = ix.get(k)
        return str(r[i]).strip() if i is not None and i < len(r) else ""

    return h, ix, g, v[head:]


def main():
    tok = sc.access_token(sc.load_credentials())

    # ---- 予約_Web ----
    v = yomu(tok, TAB, "A1:BZ500")
    if not v:
        sys.exit(f"{TAB} を読めません")
    head = v[0]
    ix = {c: i for i, c in enumerate(head)}

    # ★列の用意
    tarinai = [c for c in TSUIKA if c not in ix]
    if tarinai:
        print(f"足りない列: {tarinai}")
        if not TSUKURU:
            print("→ 先に: python3 tools/yoyaku-match.py --列を作る --confirm WRITE")
            return 1
        if not WRITE:
            print("→ --confirm WRITE を付けてください")
            return 1
        kaishi = len(head) + 1
        sc.call(tok, f"/{SS}/values/{urllib.parse.quote(TAB + '!' + a1(kaishi) + '1', safe='')}",
                "PUT", {"values": [tarinai]}, query={"valueInputOption": "RAW"})
        print(f"見出しを {a1(kaishi)}1 から {len(tarinai)}列 足しました")
        head = head + tarinai
        ix = {c: i for i, c in enumerate(head)}

    def g(r, k):
        i = ix.get(k)
        return str(r[i]).strip() if i is not None and i < len(r) else ""

    gyou = [(n, r) for n, r in enumerate(v[1:], start=2)
            if any(str(x).strip() for x in r)]
    print(f"{TAB}: {len(gyou)}行")
    if not gyou and not SHINDAN:
        print("まだ申し込みがありません。列だけ用意した状態です。")
        if TSUKURU:
            iro(tok)
        return 0

    # ---- 台帳 ----
    dv = yomu(tok, DAICHOU, f"A{DAICHOU_HEAD}:Q1200")
    _, _, dg, drows = hyou_tsukuru(dv, 1)
    by_tel, by_name = {}, {}
    for r in drows:
        cid = dg(r, "顧客ID")
        if not cid:
            continue
        rec = (cid, dg(r, "最終施工日"))
        t = tel_norm(dg(r, "TEL"))
        if t:
            by_tel.setdefault(t, []).append(rec)
        by_name.setdefault(dg(r, "顧客名").replace(" ", "").replace("　", ""), []).append(rec)

    # ---- 名義（台帳の最新施工の名義。列の値は信じない）----
    meigi_hyou, riyuu = meigi.hyou_yomu()
    if meigi_hyou is None:
        print(f"⚠️ 名義を照合できません → {riyuu}")
        print("   名義の列は「不明」にします。**この状態でお客様に連絡しないこと。**")

    # ---- 属性メモ ----
    zv = yomu(tok, ZOKUSEI, f"A{ZOKUSEI_HEAD}:Q1200")
    zh, _, zg, zrows = hyou_tsukuru(zv, 1)
    zoku_col = [c for c in zh[5:15] if c]
    zokusei = {}
    for r in zrows:
        cid = zg(r, "顧客ID")
        if not cid:
            continue
        aru = [c for c in zoku_col if zg(r, c).upper() == "TRUE"]
        memo = zg(r, zh[15]) if len(zh) > 15 else ""
        zokusei[cid] = "／".join(aru) + (f"／メモ:{memo}" if memo else "")

    # ---- 自己診断：台帳の実在のお客様を「申し込みが来た」ことにして、同じ道を通す ----
    if SHINDAN:
        erabu = []
        for r in drows:
            if len(erabu) >= 6:
                break
            cid, tel, nm = dg(r, "顧客ID"), dg(r, "TEL"), dg(r, "顧客名")
            shu = dg(r, "売上種類")
            if not cid:
                continue
            # 電話あり／電話なし × 本舗／自社 が混ざるように、組み合わせごとに2名まで拾う
            key = (bool(tel), shu)
            if sum(1 for e in erabu if e[0] == key) >= 2:
                continue
            erabu.append((key, (cid, nm, tel, dg(r, "最終施工日"))))
        gyou = []
        for i, (_, (cid, nm, tel, saishu)) in enumerate(erabu, start=900):
            r = [""] * len(head)
            r[ix["お名前"]] = nm
            r[ix["お電話番号"]] = tel
            r[ix["ご希望日"]] = saishu
            r[ix["流入元"]] = "LP:mizumawari src=google cid=123456 OH-TESTONLY"
            gyou.append((i, r))
        print(f"\n== 自己診断：台帳から {len(gyou)}名を「申し込みが来た」ことにして通します ==")
        print("   （シートには書きません。照合の道筋が通るかだけを見ます）")

    # ---- 各月の売上 ----
    uriage = []
    for m in range(1, 13):
        tab = f"{m}月_売上/顧客"
        try:
            uv = yomu(tok, tab, "A2:T520")
        except SystemExit:
            continue
        if not uv:
            continue
        _, _, ug, urows = hyou_tsukuru(uv, 1)
        for i, r in enumerate(urows, start=4):   # 見出しが2行目、データは4行目から
            d = hiduke(ug(r, "施工日付"))
            if not d:
                continue
            uriage.append({
                "tab": tab, "no": ug(r, "No.") or str(i), "date": d,
                "tel": tel_norm(ug(r, "TEL(-無し)")),
                "name": ug(r, "氏名").replace(" ", "").replace("　", ""),
                "kin": ug(r, "売上（税込）"),
            })

    # ---- 1行ずつ ----
    data, hyouji = [], []
    for n, r in gyou:
        tel = tel_norm(g(r, "お電話番号"))
        namae = g(r, "お名前").replace(" ", "").replace("　", "")
        kouho = []
        if tel and tel in by_tel:
            kouho += [(x, "電話一致") for x in by_tel[tel]]
        if namae and namae in by_name:
            kouho += [(x, "氏名一致") for x in by_name[namae]]
        if kouho:
            kouho.sort(key=lambda x: x[0][1], reverse=True)
            (cid, saishu), _ = kouho[0]
            tegakari = "両方一致" if len({k[1] for k in kouho}) > 1 else kouho[0][1]
        else:
            cid, saishu, tegakari = "", "", "該当なし（新規）"

        mg = "不明"
        if meigi_hyou is not None:
            mi = meigi.shiraberu(meigi_hyou, g(r, "お電話番号"), g(r, "お名前"))
            if mi:
                mg = mi[0]

        # 売上との照合（ご希望日の±14日）
        nozomi = hiduke(g(r, "ご希望日"))
        sanshou, kingaku = "", ""
        if nozomi:
            atari = [u for u in uriage
                     if abs((u["date"] - nozomi).days) <= HABA
                     and ((tel and u["tel"] == tel) or (namae and u["name"] == namae))]
            if atari:
                atari.sort(key=lambda u: abs((u["date"] - nozomi).days))
                sanshou = f"{atari[0]['tab']} No.{atari[0]['no']}"
                kingaku = atari[0]["kin"]

        # 流入元から src・cid・注文番号を拾う（booking-inbox.py が独立列に入れるまでの受け口）
        moto = g(r, "流入元") + " " + g(r, "ご要望")
        src = (re.search(r"src=([^\s,）)]+)", moto) or [None, g(r, "src")])[1] or ""
        cidv = (re.search(r"cid=([^\s,）)]+)", moto) or [None, g(r, "cid")])[1] or ""
        rt = (re.search(r"(OH-[A-Za-z0-9\-]+)", moto) or [None, g(r, "レントラックス注文番号")])[1] or ""

        kaku = {
            "src": src, "cid": cidv,
            "★台帳の顧客ID": cid, "★台帳の名義": mg, "★台帳の最終施工日": saishu,
            "★照合の手がかり": tegakari, "★属性": zokusei.get(cid, ""),
            "★売上行への参照": sanshou, "★売上（税込）": kingaku,
        }
        if rt and not g(r, "レントラックス注文番号"):
            kaku["レントラックス注文番号"] = rt
        for k, val in kaku.items():
            if k in TEUCHI and g(r, k):
                continue
            data.append({"range": f"{TAB}!{a1(ix[k]+1)}{n}", "values": [[val]]})
        # 却下判定（式。38日で入金未確認なら「要却下」）
        c_rt, c_hassei, c_nyuukin = (a1(ix["レントラックス注文番号"] + 1),
                                     a1(ix["成果発生日"] + 1), a1(ix["入金確認日"] + 1))
        shiki = (f'=IF(AND({c_rt}{n}<>"",{c_nyuukin}{n}="",{c_hassei}{n}<>"",'
                 f'TODAY()-{c_hassei}{n}>=38),"要却下","")')
        data.append({"range": f"{TAB}!{a1(ix['★却下判定']+1)}{n}", "values": [[shiki]]})

        hyouji.append((n, g(r, "お名前"), cid or "新規", mg, tegakari, sanshou))

    print(f"\n{'行':>3} {'お名前':<12} {'顧客ID':<8} {'名義':<4} {'手がかり':<12} 売上")
    for n, na, cid, mg, tg, sa in hyouji:
        mark = " ⚠️本舗" if mg == "本舗" else ""
        print(f"{n:>3} {na:<12} {cid:<8} {mg:<4} {tg:<12} {sa}{mark}")
    honpo = sum(1 for x in hyouji if x[3] == "本舗")
    print(f"\n本舗名義: {honpo}件（この方々には SMS・LINE で連絡しない。電話のみ）")

    if SHINDAN:
        print("\n自己診断なので書き込みません。")
        muke = [x for x in hyouji if x[2] == "新規"]
        if muke:
            print(f"★★ 台帳から採ったのに照合できなかった人がいます: {len(muke)}名")
            for x in muke:
                print("   ", x)
            return 1
        print("★ 全員が台帳と照合できました。照合の道筋は通っています。")
        return 0
    if not WRITE:
        print("\n書き込みません（表示のみ）。書くには: --confirm WRITE")
        return 0
    sc.call(tok, f"/{SS}/values:batchUpdate", "POST",
            {"valueInputOption": "USER_ENTERED", "data": data})
    print(f"\n書き込みました: {len(data)}セル")
    if TSUKURU:
        iro(tok)
    return 0


def iro(tok):
    """台帳の名義が「本舗」の行に色を付ける。SMS・LINEで連絡しないことを目で分かるように。"""
    meta = sc.call(tok, f"/{SS}?fields=sheets.properties")
    gid = [s["properties"]["sheetId"] for s in meta["sheets"]
           if s["properties"]["title"] == TAB][0]
    v = sc.call(tok, f"/{SS}/values/{urllib.parse.quote(TAB + '!A1:BZ1', safe='')}").get("values", [])
    head = v[0] if v else []
    if "★台帳の名義" not in head:
        return
    c = a1(head.index("★台帳の名義") + 1)
    sc.call(tok, f"/{SS}:batchUpdate", "POST", {"requests": [{"addConditionalFormatRule": {
        "rule": {
            "ranges": [{"sheetId": gid, "startRowIndex": 1, "endRowIndex": 500,
                        "startColumnIndex": 0, "endColumnIndex": len(head)}],
            "booleanRule": {
                "condition": {"type": "CUSTOM_FORMULA",
                              "values": [{"userEnteredValue": f'=${c}2="本舗"'}]},
                "format": {"backgroundColor": {"red": 1.0, "green": 0.90, "blue": 0.80}}}},
        "index": 0}}]})
    print("条件付き書式：台帳の名義が「本舗」の行に色を付けました（SMS・LINEで連絡しない印）")


if __name__ == "__main__":
    sys.exit(main())
