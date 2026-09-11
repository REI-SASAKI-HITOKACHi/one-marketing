#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""名乗りの照合。お客様に届くものは、必ずここを通してから出す。

## なぜあるか

2026-09-11、**本舗名義のお客様3名に、ワンヒッターの文面が届いた。**
原因は「冬季見込み客_2026」の送信系統列を信じたこと。あの列がどの規則で入ったか
記録が残っておらず、台帳の実際の名義と食い違っていた。

> **列の値を信じない。台帳の「最新の施工の名義」と機械で照合する。**
> **照合できない相手には送らない。**
> （2026-09-11 オーナー指示。決まりは CLAUDE.md と docs/org/README.md）

## 何を見るか

1. **宛先の名義** … `tools/derive-soushin-keitou.py` の `meigi_hyou()` で
   電話番号と氏名の両方から引き、いちばん新しい施工の名義を採る
2. **本文の中身** … 自社の文面に本舗のもの（店名・本舗の受付番号）が混ざっていないか。
   逆に本舗の文面にワンヒッターのもの（社名・受付番号・URL）が混ざっていないか

**1だけでは足りません。** 宛先が正しくても、文面に相手方のURLが1本混ざれば事故です。

## 使い方

    import sys, os
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import meigi_check as MC

    hyou, err = MC.hyou_yomu()            # 台帳を読む（認証が要る）
    if hyou is None:
        # ★読めない＝照合できない＝送らない。握りつぶさないこと
        ...

    ok, riyuu = MC.atesaki_ok(hyou, tel, name, "自社")
    ihan = MC.honbun_ihan("自社", body)   # 空リストなら合格

認証は環境変数 `GOOGLE_SHEETS_SA_KEY`。**リポジトリには置かない。**
控えは `~/.cache/one-hitter/meigi-cache.json`（gitの外。電話番号と氏名が入る。コミット禁止）。
"""

import importlib.util
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEIGI_TOOL = os.path.join(ROOT, "tools", "derive-soushin-keitou.py")

# 名義ごとに「必ず入っていること」と「絶対に入っていないこと」。
# 相手方のものが1つでも混ざったら、その時点で不合格。
MUST = {
    "自社": ["ワンヒッター"],
    "本舗": ["おそうじ本舗"],
}
NG = {
    # 自社の文面に、本舗のものを出さない
    "自社": [
        ("おそうじ本舗", "本舗の店名"),
        ("080-1344-3137", "本舗の受付番号"),
        ("08013443137", "本舗の受付番号"),
    ],
    # 本舗の文面に、ワンヒッターのものを出さない（社名・受付番号・URL・料金導線）
    # 2026-09-11 CMOの指定で ONE-HITTER／受付番号／netlify を追加
    "本舗": [
        ("ワンヒッター", "ワンヒッターの社名"),
        ("ONE HITTER", "ワンヒッターの社名"),
        ("ONE-HITTER", "ワンヒッターの社名"),
        ("OneHitter", "ワンヒッターの社名"),
        ("One Hitter", "ワンヒッターの社名"),
        ("080-8043-8259", "ワンヒッターの受付番号"),
        ("08080438259", "ワンヒッターの受付番号"),
        ("080-1755-7275", "ワンヒッターの代表番号"),
        ("受付番号", "ワンヒッターの受付番号への言及"),
        ("one-hitter", "ワンヒッターのURL"),
        ("lin.ee", "ワンヒッターの公式LINE"),
        ("netlify", "ワンヒッターのURL"),
    ],
}

_module = None


def _load():
    """derive-soushin-keitou.py を読み込む。読み込んだ時点で認証が走る。"""
    global _module
    if _module is None:
        spec = importlib.util.spec_from_file_location("derive_soushin_keitou", MEIGI_TOOL)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        _module = m
    return _module


def hyou_yomu(cache=None):
    """(表, None) か (None, 理由) を返す。例外は投げない。

    ★(None, 理由) が返ったら「照合できない」。そのときは送らないこと。
    「読めなかったから素通し」は、この仕組みを入れた意味がなくなる。"""
    try:
        return _load().meigi_hyou(cache), None
    except Exception as e:  # noqa: BLE001 認証切れ・通信断・台帳の形の変化、どれも「送らない」で同じ
        return None, f"{type(e).__name__}: {e}"


def shiraberu(hyou, tel, name):
    """(名義, 最新施工日) か None。電話番号と氏名の両方から引いて、新しいほうを採る。"""
    return _load().meigi_shiraberu(hyou, tel, name)


def atesaki_ok(hyou, tel, name, tsukau_meigi):
    """この宛先に、この名義で送ってよいか。(可否, 理由) を返す。"""
    if hyou is None:
        return False, "台帳を読めず照合できない"
    mi = shiraberu(hyou, tel, name)
    if mi is None:
        return False, "台帳に名義の記録がない（照合できない）"
    daichou, saishin = mi
    if daichou != tsukau_meigi:
        return False, f"名義が食い違う（台帳={daichou}／文面={tsukau_meigi}／最新施工 {saishin}）"
    return True, f"台帳={daichou}（最新施工 {saishin}）"


def honbun_ihan(meigi, body):
    """文面の違反を並べて返す。空リストなら合格。"""
    out = []
    for word in MUST.get(meigi, []):
        if word not in body:
            out.append(f"{meigi}の文面に「{word}」が入っていない")
    for word, nani in NG.get(meigi, []):
        if word in body:
            out.append(f"{meigi}の文面に{nani}「{word}」が混ざっている")
    return out


def jikoshindan():
    """自分自身の検算。名乗りの表がちゃんと相手方を弾くかを確かめる。"""
    shiken = [
        ("自社", "ワンヒッター株式会社 080-8043-8259", []),
        ("自社", "ワンヒッター株式会社 おそうじ本舗 080-8043-8259", ["本舗の店名"]),
        ("自社", "080-8043-8259 だけ", ["「ワンヒッター」が入っていない"]),
        ("本舗", "おそうじ本舗 江戸川中央店 080-1344-3137", []),
        ("本舗", "おそうじ本舗 江戸川中央店 https://lin.ee/7kD9WGN", ["公式LINE"]),
        ("本舗", "おそうじ本舗 江戸川中央店 080-8043-8259", ["受付番号"]),
        ("本舗", "おそうじ本舗 江戸川中央店 ONE-HITTER", ["社名"]),
        ("本舗", "おそうじ本舗 江戸川中央店 https://x.netlify.app/", ["URL"]),
    ]
    ng = 0
    for meigi, body, matteru in shiken:
        deta = honbun_ihan(meigi, body)
        ok = len(deta) == len(matteru) and all(any(m in d for d in deta) for m in matteru)
        if not ok:
            ng += 1
        print(f"  [{'OK' if ok else 'NG'}] {meigi}: {body[:40]} → {deta or '違反なし'}")
    return ng


if __name__ == "__main__":
    import sys

    print("== 名乗り照合の自己診断 ==")
    ng = jikoshindan()
    print(("NG %d件" % ng) if ng else "すべてOK")
    print("\n== 台帳の読み込み ==")
    hyou, err = hyou_yomu()
    if hyou is None:
        print("読めません:", err)
        print("→ この状態では照合できないので、お客様への配信をしないこと")
    else:
        by_tel, by_name = hyou
        print(f"電話番号で引ける人 {len(by_tel)}名 ／ 氏名で引ける人 {len(by_name)}名")
    sys.exit(1 if ng else 0)
