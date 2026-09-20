#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""**1回でも楽ラクーン経由の施工がある方**を、SMSの送信対象から外す。

## なぜ要るか（2026-09-20・実害1名）

和真さん：「SMS送信リスト内に楽ラクーン経由のお客様が入ってたんだけど楽ラクーンは
SMS送信対象外だからリストから排除して！」

`tools/build-sms-list.py` の除外は **顧客管理台帳の「主な流入経路」1列**しか見ていなかった。
**「主な」＝いちばん回数の多い経路**なので、楽ラクーンが1回でも、ほかが2回以上あればすり抜ける。
大場 正博さまは5回中1回が楽ラクーンで、残りがリピート → 「主な流入経路＝リピート」→ **送信済み**。

> **9/11 の事故と同じ型。「集計後の1列を信じる」と落ちる。**
> だから**月次タブの生の行を1件ずつ見る。**

## 見る列は「流入経路」だけ。★行のどこでもよい、にしてはいけない

CMO から「2023はB列、2024〜2026はD列」と注意があったので、**列の位置ではなく見出しで引く**。

> ### 🚨 最初「行のどのセルでも楽ラクーンがあれば該当」にして、盛大に外した（2026-09-20）
>
> **`カウント用`（T列）は、売上種類のプルダウンの選択肢が置いてあるだけの列。**
> どの月次タブでも **3〜6行目に `One Hitter` / `本舗` / `楽ラクーン` / `下請`** が並んでいる。
> **その行に居るお客様とは何の関係もない。**
>
> これを拾ったせいで「送信済み5名・155行目以降に2名」という**誤った結果**が出て、
> あやうく和真さんの送信を止めさせるところだった。**正しくは送信済み1名・155行目以降0名。**
>
> **「どこかに書いてあれば」は照合ではない。どの列の意味なのかまで見ること。**

`備考(お客様の声)` の「楽ラクーン」は**弱い根拠だが、根拠ではある**（「楽ラクーンロボ2台 回収¥24,453-」など、
明らかに楽ラクーンの施工を指している）。**除外には使うが、出力で別立てにして、人が目で見られるようにする。**
`カウント用` のような**選択肢が並んでいるだけの列とは違う**ので、そこは分けて考える。

## 2022年は判定できない

**2022年の台帳には流入経路の列そのものが無い。**
「調べれば分かる」ではなく「**データが存在しない**」。**追わないと決めた**（CMO 2026-09-20）。
2022年に施工があるだけの方は、楽ラクーン経由かどうか**永久に分からない**。

## 使い方

    . ~/.config/one-hitter/line.env
    python3 tools/rakuraccoon-jogai.py                  # 調べるだけ（既定）
    python3 tools/rakuraccoon-jogai.py --confirm WRITE  # 配信区分を「除外」にする
"""

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
hikae = _mod("hikae", "hikae.py")

BOOKS = {"2022": "1-NNZCK6LtyTxvecHOgAHnHRJ6FP_4in_6ht-92a_YME",
         "2023": "1mOGaxy5viO4peUUQqgJYQ9gp0tuev2c_Y8DrdDy-y3M",
         "2024": "1Q-dJ0Rh2AeYGhNYUyqoKOkG_Kgq4e1M0KcwkhMFb0J4",
         "2025": "1cpN2tu6NNIA5FSAAC3ejCK0jNNFNfn7GCwq0ghggK3o",
         "2026": "1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64"}
SS = BOOKS["2026"]
TAB = "冬季見込み客_2026"
HEAD_ROW = 5
KEYWORD = "楽ラクーン"
RIYUU = "楽ラクーン経由（フォロー連絡不可）／1回でも該当"

WRITE = ("--confirm" in sys.argv and "WRITE" in sys.argv)


def tel_norm(t):
    return re.sub(r"\D", "", str(t or ""))


def name_norm(n):
    return re.sub(r"[\s　]", "", str(n or ""))


# 見てよい列。**ここに無い列で「楽ラクーン」を見つけても、除外の根拠にしない。**
MIRU = ("流入経路",)
# 人が目で見るために出すだけの列（除外には使わない）
SANKOU = ("備考(お客様の声)", "備考")


def atari_wo_atsumeru(tok):
    """全年の月次タブから、楽ラクーン経由の（氏名, 電話）を集める。

    **見るのは `流入経路` 列だけ**（見出しで引く。列の位置は年で違う）。
    """
    tel_set, na_set, meisai, retsu, sankou = set(), set(), [], {}, []
    bikou_tel, bikou_na = set(), set()
    for y, ss in BOOKS.items():
        meta = sc.call(tok, f"/{ss}", query={"fields": "sheets.properties.title"})
        tabs = [s["properties"]["title"] for s in meta["sheets"]
                if re.match(r"^\d{1,2}月_売上", s["properties"]["title"])]
        atta = 0
        for tab in tabs:
            v = sc.call(tok, f"/{ss}/values/"
                        + urllib.parse.quote(f"{tab}!A1:T500", safe="")).get("values", [])
            hi = next((i for i, r in enumerate(v)
                       if "氏名" in r or "施工日付" in r or "日付" in r), None)
            if hi is None:
                continue
            h = v[hi]
            ix = {c: i for i, c in enumerate(h)}

            def g(r, k):
                i = ix.get(k)
                return str(r[i]).strip() if i is not None and i < len(r) else ""

            if not any(k in ix for k in MIRU):
                continue                      # 2022年など、流入経路の列が無い年
            for r in v[hi + 1:]:
                na, tel = name_norm(g(r, "氏名")), tel_norm(g(r, "TEL(-無し)") or g(r, "TEL"))
                if any(g(r, k) == KEYWORD for k in MIRU):
                    atta += 1
                    for k in MIRU:
                        if g(r, k) == KEYWORD:
                            retsu[f"{y}／{k}"] = retsu.get(f"{y}／{k}", 0) + 1
                    if tel:
                        tel_set.add(tel)
                    if na:
                        na_set.add(na)
                    meisai.append((y, tab, na, tel))
                elif any(KEYWORD in g(r, k) for k in SANKOU if k in ix):
                    # 備考にだけ書かれている。**弱い根拠だが、除外には使う**（別立てで出す）
                    if tel:
                        tel_set.add(tel)
                    if na:
                        na_set.add(na)
                        bikou_na.add(na)
                    if tel:
                        bikou_tel.add(tel)
                    sankou.append((y, tab, g(r, "氏名"),
                                   next(g(r, k) for k in SANKOU if k in ix and KEYWORD in g(r, k))[:60]))
        print(f"  {y}年 … 月次{len(tabs)}タブ／流入経路が楽ラクーンの行 {atta}件")
    print(f"\n当たった列（年／見出し）: {retsu}")
    if sankou:
        print(f"\n★ 備考にだけ「楽ラクーン」と書かれている行 {len(sankou)}件"
              f"（弱い根拠だが除外には使う。★目で見ること）")
        for x in sankou:
            print(f"   {x[0]}年 {x[1]} {x[2]}  「{x[3]}」")
    return tel_set, na_set, meisai, bikou_tel, bikou_na


def main():
    tok = sc.access_token(sc.load_credentials())
    print("=== 全年の月次タブから「楽ラクーン」を拾う ===")
    tel_set, na_set, meisai, bikou_tel, bikou_na = atari_wo_atsumeru(tok)
    print(f"\n楽ラクーン経由の実人数（電話で数えて）: {len(tel_set)}／氏名で数えて: {len(na_set)}")
    print("※ 2022年は流入経路の列そのものが無いので判定できません（追わないと決めた）")

    v = sc.call(tok, f"/{SS}/values/"
                + urllib.parse.quote(f"{TAB}!A{HEAD_ROW}:AA1200", safe="")).get("values", [])
    h = v[0]
    ix = {c: i for i, c in enumerate(h)}
    atari = []
    for n, r in enumerate(v[1:], start=HEAD_ROW + 1):
        def g(k):
            i = ix.get(k)
            return str(r[i]).strip() if i is not None and i < len(r) else ""
        na, tel = name_norm(g("顧客名")), tel_norm(g("電話番号"))
        if not na and not tel:
            continue
        de = "電話" if (tel and tel in tel_set) else ("氏名" if (na and na in na_set) else None)
        if not de:
            continue
        konkyo = "備考のみ" if (tel in bikou_tel or na in bikou_na) else "流入経路"
        atari.append({"行": n, "名": g("顧客名"), "tel": tel, "照合": de, "根拠": konkyo,
                      "区分": g("配信区分"), "状態": g("送信済み"), "理由": g("送らない理由"),
                      "本文あり": bool(g("送信する本文"))})

    sumi = [a for a in atari if a["状態"] in ("送信済み", "返信あり", "不通・エラー")]
    mada = [a for a in atari if a not in sumi]
    kaeru = [a for a in mada if a["区分"] != "除外"]
    print(f"\n===== SMSリストの中の楽ラクーン経由 =====")
    print(f"  当たった行: {len(atari)}名")
    print(f"  🔴 すでに送ってしまった: {len(sumi)}名")
    for a in sumi:
        print(f"     行{a['行']} {a['名']}（{a['照合']}一致・状態 {a['状態']}）")
    print(f"  未送信: {len(mada)}名（うち **いま除外に変わるのは {len(kaeru)}名**）")
    for a in kaeru:
        print(f"     行{a['行']} {a['名']}（{a['照合']}一致／根拠 {a['根拠']}・いまの区分 "
              f"{a['区分'] or '(空)'}・本文{'あり' if a['本文あり'] else 'なし'}）")

    # ★和真さんがいま送っている範囲に居ないか
    ima = [a for a in kaeru if a["行"] >= 155 and a["本文あり"]]
    print(f"\n★★ 155行目以降で、まだ送っていない楽ラクーン経由: {len(ima)}名")
    for a in ima:
        print(f"     行{a['行']} {a['名']}  ← **和真さんの手を止めること**")
    if not ima:
        print("     いません。和真さんの手は止めなくてよい")

    if not WRITE:
        print("\n書き込みません（調べただけ）。除外にするには: --confirm WRITE")
        return 0
    if not kaeru:
        print("\n変えるものがありません。")
        return 0

    hikae.git_ni_toru(tok, TAB)
    c_ku, c_ri = ix["配信区分"], ix["送らない理由"]

    def a1(col):
        s = ""
        while col:
            col, r = divmod(col - 1, 26)
            s = chr(65 + r) + s
        return s

    data = []
    for a in kaeru:
        # ★理由は書き足し。もとの理由（照合不能など）を消さない
        riyuu = f"{RIYUU}（根拠: {a['根拠']}）"
        moto = a["理由"]
        data.append({"range": f"{TAB}!{a1(c_ku+1)}{a['行']}", "values": [["除外"]]})
        data.append({"range": f"{TAB}!{a1(c_ri+1)}{a['行']}",
                     "values": [[(moto + " ／ " if moto else "") + riyuu]]})
    sc.call(tok, f"/{SS}/values:batchUpdate", "POST",
            {"valueInputOption": "RAW", "data": data})
    print(f"\n{len(kaeru)}行を「除外」にしました。")
    print("★ 本文とリンクはこのツールでは消していません。"
          "送れてしまう行が残っていないか、下の確認を見ること。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
