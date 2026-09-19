#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`【毎月更新】リピート/業務提携` タブに、提携先と受注日を**追記だけ**する。

## なぜ要るか

2026-09-19、CMO から「提携タブに無い2社（楽ラクーン・クラスリフォーム）を足してほしい」と来た。
**調べると クラスリフォームは No.4 として最初から入っていた。**
そのまま足していたら、**同じ会社の行が2つ**でき、合計が二重になっていた。

> **企業名の重複を機械で止める。** これがこのツールの一番の仕事。
> 既にある会社は「新しい行」ではなく、**その会社の行に日付を追記する**のが正しい。

## 表の形（見出しは1行目）

```
A=No. B=企業名 C=業種 D=備考 | E,F=日付,売上1 | G,H=日付,売上2 | …（32組・E〜BP）
BQ=合計 BR=総合計 BS=平均単価 BT=案件発生 BU=施策
```

**日付だけ入れて売上を空にすると、平均単価（BS＝合計÷日付の個数）が一時的に下がります。**
金額が入れば自動で戻ります。**下がることを承知のうえで入れること。**

## 使い方

    . ~/.config/one-hitter/line.env
    python3 tools/teikei-tsuika.py                  # 調べるだけ（既定）
    python3 tools/teikei-tsuika.py --confirm WRITE  # 控えを取ってから追記

追記する中身は下の `TSUIKA` に書く。**既存のセルは1つも書き換えません。**
"""

import datetime
import importlib.util
import os
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _mod(name, path):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


sc = _mod("sc", "sheets_client.py")

SS = "1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64"
TAB = "【毎月更新】リピート/業務提携"
PAIR_FROM, PAIR_TO = 5, 68          # E〜BP が 日付/売上 の32組

WRITE = ("--confirm" in sys.argv and "WRITE" in sys.argv)

# ---- 今回入れるもの（2026-09-19／依頼 20260919-01-crm）----
#   日付 = [] なら「会社を登録するだけ。受注日は入れない」
TSUIKA = [
    {
        "企業名": "楽ラクーン",
        "業種": "toBマッチング",
        "日付": [],                 # ★入れない。理由は下の備考のとおり
        "備考": (
            "2026-09-19 追加（20260919-01-crm）。"
            "★受注日はこの表に入れていません。楽ラクーン経由の施工は月次タブで"
            "流入経路「楽ラクーン」として別に数えており（2026年 67件・¥1,845,833／5〜8月）、"
            "ここに日付を入れると同じ仕事が2か所で数えられます。"
            "この表に載せるのは『会社が存在する』という登録だけ。"
            "どちらで数えるかのルールが決まってから受注日を入れること。"
        ),
    },
]

# 既にある会社の行へ、受注日だけ追記するもの
HIZUKE_TSUIKA = [
    {
        "企業名": "株式会社プレジャー",
        "日付": ["2026/09/25"],
        "売上": [""],
        "備考追記": (
            "2026-09-19 追加（20260919-01-crm）：9/25 の空室清掃。"
            "住所と金額がカレンダーに無く未確認（和真さん待ち）。"
            "★金額が空のあいだ、平均単価が実際より低く出ます。"
        ),
    },
    {
        "企業名": "株式会社レジェンド",
        "日付": ["2026/09/26"],
        "売上": [""],
        "備考追記": (
            "2026-09-19 追加（20260919-01-crm）：9/26 の天カセ（カレンダーに「9時半アポ」）。"
            "住所と金額がカレンダーに無く未確認（和真さん待ち）。"
            "★金額が空のあいだ、平均単価が実際より低く出ます。"
        ),
    },
    {
        # ★提携タブでは「才木工業」、月次タブでは「株式会社才木工業」。表記が違う。
        #   企業名で引くときは、提携タブ側の書き方に合わせること。
        "企業名": "才木工業",
        "日付": ["2026/09/28"],
        "売上": ["66720"],
        "備考追記": ("2026-09-19 追加（20260919-01-crm）：9/28 東村山市栄町の天カセ"
                     "（法人担当者 カワサキ様）。月次タブでは「株式会社才木工業」表記。"),
    },
    {
        "企業名": "クラスリフォーム",
        "日付": ["2026/09/17"],
        "売上": ["57240"],
        "備考追記": "2026-09-19 追記：9/17 も別の1件として計上（月次タブ 9月20行が起きたため。9/16 と同じ現場）。",
    },
    {
        "企業名": "クラスリフォーム",
        "日付": ["2026/09/16"],
        "売上": [""],               # カレンダーに金額が無い。和真さん待ち
        "備考追記": (
            "2026-09-19 追加（20260919-01-crm）：9/16 大和市南林間7-17-18 の空室清掃。"
            "9/16・9/17 の2日間だが1案件とみて1行。金額は未確認（和真さん待ち）。"
            "★金額が空のあいだ、平均単価が実際より低く出ます。"
        ),
    },
]


# 既に入れた受注日の、空いている売上セルを埋める（金額が後から出たとき）
KINGAKU = [
    {"企業名": "クラスリフォーム", "日付": "2026/09/16", "売上": "57240"},
    {"企業名": "株式会社プレジャー", "日付": "2026/09/25", "売上": "98160"},
    {"企業名": "株式会社レジェンド", "日付": "2026/09/26", "売上": "31100"},
]


def col(n):
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def yomu(tok):
    v = sc.call(tok, f"/{SS}/values/" + urllib.parse.quote(f"{TAB}!A1:BU60", safe=""),
                query={"valueRenderOption": "FORMULA"}).get("values", [])
    return v


def kaisha_gyou(v):
    """企業名 → 行番号。前後の空白と全角空白をならして比べる。"""
    out = {}
    for n, r in enumerate(v[1:], start=2):
        if len(r) > 1 and str(r[1]).strip():
            out[str(r[1]).strip().replace("　", "")] = n
    return out


def hizuke_aru(row, hizuke):
    """その行に、同じ受注日がもう入っていないか。**二度足しを止めるため。**

    シートは日付をシリアル値で返すことがあるので、表示形と両方で見る。
    """
    import datetime as _dt
    mato = {str(hizuke).strip(), str(hizuke).replace("/", "-").strip()}
    try:
        y, m, d = [int(x) for x in str(hizuke).replace("-", "/").split("/")]
        mato.add(str((_dt.date(y, m, d) - _dt.date(1899, 12, 30)).days))
    except Exception:
        pass
    for c in range(PAIR_FROM, PAIR_TO + 1, 2):
        if c - 1 < len(row) and str(row[c - 1]).strip() in mato:
            return c
    return None


def aki_pair(row):
    """その行で最初に空いている（日付, 売上）の列番号。"""
    r = list(row) + [""] * (PAIR_TO + 2)
    for c in range(PAIR_FROM, PAIR_TO + 1, 2):
        if not str(r[c - 1]).strip() and not str(r[c]).strip():
            return c, c + 1
    return None, None


def main():
    tok = sc.access_token(sc.load_credentials())
    v = yomu(tok)
    aru = kaisha_gyou(v)
    saigo = max(aru.values())
    print(f"いまの提携先: {len(aru)}社（最終行 {saigo}）")

    data, memo = [], []

    # ---- 新しい会社 ----
    for t in TSUIKA:
        key = t["企業名"].strip().replace("　", "")
        if key in aru:
            print(f"\n🛑 「{t['企業名']}」は **すでに {aru[key]}行目にあります**。新しい行は作りません。")
            print("   （同じ会社の行が2つできると、合計が二重になります）")
            continue
        gyou = saigo + 1
        saigo = gyou
        print(f"\n＋ {gyou}行目に「{t['企業名']}」を足します（業種 {t['業種'] or '(空)'}）")
        data.append({"range": f"{TAB}!B{gyou}:D{gyou}",
                     "values": [[t["企業名"], t["業種"], t["備考"]]]})
        if not t["日付"]:
            print("   受注日は入れません（備考に理由を書いてあります）")
        for i, d in enumerate(t["日付"]):
            print(f"   受注日 {d} も入れます")

    # ---- 既にある会社への受注日の追記 ----
    for t in HIZUKE_TSUIKA:
        key = t["企業名"].strip().replace("　", "")
        if key not in aru:
            print(f"\n🛑 「{t['企業名']}」が見つかりません。追記できません。")
            continue
        n = aru[key]
        row = v[n - 1] if n - 1 < len(v) else []
        nokori = [(d, t["売上"][i]) for i, d in enumerate(t["日付"])
                  if hizuke_aru(row, d) is None]
        for d in t["日付"]:
            c = hizuke_aru(row, d)
            if c is not None:
                print(f"\n○ 「{t['企業名']}」（{n}行目）に {d} は"
                      f"**すでに {col(c)}列に入っています**。足しません")
        if not nokori:
            continue
        t = dict(t, **{"日付": [x[0] for x in nokori], "売上": [x[1] for x in nokori]})
        dc, ac = aki_pair(row)
        if dc is None:
            print(f"\n🛑 「{t['企業名']}」（{n}行目）は32組すべて埋まっています。列を増やす作業が要ります。")
            continue
        print(f"\n＋ 「{t['企業名']}」（{n}行目）の {col(dc)}/{col(ac)} に受注日を追記します")
        for i, d in enumerate(t["日付"]):
            print(f"   {col(dc)}{n} = {d} ／ {col(ac)}{n} = {t['売上'][i] or '(空欄)'}")
            data.append({"range": f"{TAB}!{col(dc)}{n}:{col(ac)}{n}",
                         "values": [[d, t["売上"][i]]]})
            dc, ac = dc + 2, ac + 2
        # 備考は「書き換え」ではなく「書き足し」
        ima = str(row[3]).strip() if len(row) > 3 else ""
        atarashii = (ima + "\n" if ima else "") + t["備考追記"]
        print(f"   D{n}（備考）に書き足します（もとの{len(ima)}文字は消しません）")
        data.append({"range": f"{TAB}!D{n}", "values": [[atarashii]]})

    # ---- 後から出た金額を、空いている売上セルに入れる ----
    for t in KINGAKU:
        key = t["企業名"].strip().replace("　", "")
        if key not in aru:
            print(f"\n🛑 「{t['企業名']}」が見つかりません。金額を入れられません。")
            continue
        n = aru[key]
        row = v[n - 1] if n - 1 < len(v) else []
        c = hizuke_aru(row, t["日付"])
        if c is None:
            print(f"\n🛑 「{t['企業名']}」（{n}行目）に {t['日付']} がありません。金額を入れられません。")
            continue
        ima = str(row[c]).strip() if c < len(row) else ""
        if ima:
            print(f"\n○ 「{t['企業名']}」{t['日付']} の売上は **すでに {ima}** です。書き換えません")
            continue
        print(f"\n＋ 「{t['企業名']}」（{n}行目）{t['日付']} の売上 {col(c+1)}{n} に {t['売上']} を入れます")
        data.append({"range": f"{TAB}!{col(c+1)}{n}", "values": [[t["売上"]]]})

    if not WRITE:
        print("\n書き込みません（調べただけ）。実行するには: --confirm WRITE")
        return 0
    if not data:
        print("\n書くものがありません。")
        return 0

    # ---- 控えを取ってから ----
    meta = sc.call(tok, f"/{SS}?fields=sheets.properties")
    gid = [s["properties"]["sheetId"] for s in meta["sheets"]
           if s["properties"]["title"] == TAB][0]
    hikae = f"控え_業務提携_{datetime.datetime.now():%Y%m%d-%H%M%S}"
    sc.call(tok, f"/{SS}:batchUpdate", "POST", {"requests": [{"duplicateSheet": {
        "sourceSheetId": gid, "newSheetName": hikae,
        "insertSheetIndex": 0}}]})
    print(f"\n控えタブを作りました: {hikae}")

    sc.call(tok, f"/{SS}/values:batchUpdate", "POST",
            {"valueInputOption": "USER_ENTERED", "data": data})
    print(f"{len(data)}か所 追記しました。**既存のセルは1つも書き換えていません。**")
    return 0


if __name__ == "__main__":
    sys.exit(main())
