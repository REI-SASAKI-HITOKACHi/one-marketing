#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SMSの返信を、**本文ごと残して**分類する列を用意し、分かるぶんを入れる。

## なぜこれが要るか

2026-09-16、お詫びSMSに返信してくださった3名を分類しようとして、**そもそも
「お客様が何と言ってきたか」を保存している列がどこにも無い**ことが分かった。

```
お詫びSMS_20260912： 顧客名｜電話番号｜▶SMSを開く｜送信済み｜送信する本文｜元の状態｜返信メモ
冬季見込み客_2026 ： …｜送信済み｜送信する本文｜返信メモ｜…
```

`返信メモ` は和真さんの要約（「感謝の意の返信」など）で、**本文ではない。**
実際に「返信あり」が立っているのに**メモが空欄の行があった**（お詫び行8）。
その方が何を言ってきたのかは、**和真さんの携帯の中にしか無い。**

**お詫びに返信してくださった方を取りこぼすのが、いちばんまずい二次被害**（CMO 2026-09-16）。

## 何をするか

両方のタブの**末尾に2列**足す。**既存の `返信メモ` は書き換えない。**

| 列 | 中身 |
|---|---|
| `返信内容（本文）` | お客様の文面そのまま。和真さんが貼るか、聞き取って入れる |
| `返信の分類` | 予約／断り／質問／その他／**不明・未記録** のプルダウン |

「不明・未記録」は**逃げではなく印**。**返信があったのに中身が残っていない行**を、
画面上で数えられるようにするためのもの。

## 使い方

    . ~/.config/one-hitter/line.env
    python3 tools/henshin-bunrui.py                  # 調べるだけ（既定）
    python3 tools/henshin-bunrui.py --confirm WRITE  # 列を足して、分かるぶんを入れる
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
meigi = _mod("meigi_check", "meigi_check.py")

SS = "1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64"
# (タブ名, 見出しの行)
TABS = [("お詫びSMS_20260912", 3), ("冬季見込み客_2026", 5)]
HONBUN = "返信内容（本文）"
BUNRUI = "返信の分類"
ERABU = ["予約", "断り", "質問", "その他", "不明・未記録"]

# 返信メモの書き方から分類を当てる。**当てられないものは「不明・未記録」にする。**
# ここに無い言い回しを勝手に解釈しない（推測で「予約」にすると、取りに行く判断を誤らせる）。
KIMARI = [
    ("予約", ["ご依頼予定", "依頼予定", "頼まれる予定", "予約", "お願いします", "来てほしい"]),
    # ★「断り」は**配信を止めてほしいと言われたとき**だけ。
    #   「いまは困っていない」は断りではない。断りにすると、次の案内を送らなくなる。
    ("断り", ["不要", "結構です", "停止", "配信停止", "断り", "いりません"]),
    ("質問", ["いくら", "料金", "いつ", "できますか", "？", "?"]),
    # 近況の報告・お礼。用は無いが、関係は切れていない方。
    # 2026-09-19 追加：「まめに掃除しているので問題なく過ごしています」（青木さま）
    ("その他", ["感謝", "お礼", "ありがとう",
                "問題なく", "問題あり", "問題は", "困ってい", "大丈夫"]),
]

WRITE = ("--confirm" in sys.argv and "WRITE" in sys.argv)


def a1(col):
    s = ""
    while col:
        col, r = divmod(col - 1, 26)
        s = chr(65 + r) + s
    return s


def bunrui_ateru(memo):
    """(分類, 根拠)。**当てられなければ「不明・未記録」。**"""
    m = (memo or "").strip()
    if not m:
        return "不明・未記録", "返信メモが空欄（本文がどこにも残っていない）"
    for name, kotoba in KIMARI:
        for k in kotoba:
            if k in m:
                return name, f"メモに「{k}」"
    return "不明・未記録", "メモはあるが、どの分類か機械では決められない"


def main():
    tok = sc.access_token(sc.load_credentials())
    hyou, riyuu = meigi.hyou_yomu()
    if hyou is None:
        print(f"⚠️ 台帳を読めません → {riyuu}／名義は「未確認」と出します")

    meta = sc.call(tok, f"/{SS}?fields=sheets.properties")
    gids = {s["properties"]["title"]: s["properties"]["sheetId"] for s in meta["sheets"]}

    for tab, head_row in TABS:
        v = sc.call(tok, f"/{SS}/values/{urllib.parse.quote(tab + f'!A{head_row}:BZ1200', safe='')}"
                    ).get("values", [])
        if not v:
            print(f"{tab}: 読めません")
            continue
        head = v[0]
        ix = {c: i for i, c in enumerate(head)}
        namae_col = "顧客名"
        memo_col = "返信メモ"
        if memo_col not in ix:
            print(f"{tab}: 「{memo_col}」列がありません。飛ばします")
            continue

        def g(r, k):
            i = ix.get(k)
            return str(r[i]).strip() if i is not None and i < len(r) else ""

        tsuika = [c for c in (HONBUN, BUNRUI) if c not in ix]
        print(f"\n===== {tab} =====")
        if tsuika:
            kaishi = len(head) + 1
            print(f"  末尾 {a1(kaishi)}列 から {tsuika} を足します")
            if WRITE:
                # タブの列数が足りないと「exceeds grid limits」で弾かれる。先に広げる。
                ima = [s["properties"] for s in meta["sheets"]
                       if s["properties"]["title"] == tab][0]
                aru = ima.get("gridProperties", {}).get("columnCount", 0)
                iru = kaishi + len(tsuika) - 1
                if aru < iru:
                    sc.call(tok, f"/{SS}:batchUpdate", "POST",
                            {"requests": [{"appendDimension": {
                                "sheetId": gids[tab], "dimension": "COLUMNS",
                                "length": iru - aru}}]})
                    print(f"  タブの列を {aru} → {iru} に広げました")
                sc.call(tok,
                        f"/{SS}/values/{urllib.parse.quote(tab + '!' + a1(kaishi) + str(head_row), safe='')}",
                        "PUT", {"values": [tsuika]}, query={"valueInputOption": "RAW"})
                head = head + tsuika
                ix = {c: i for i, c in enumerate(head)}
        else:
            print("  2列とも すでにあります")

        # プルダウン
        if WRITE and BUNRUI in ix:
            c = ix[BUNRUI]
            sc.call(tok, f"/{SS}:batchUpdate", "POST", {"requests": [{"setDataValidation": {
                "range": {"sheetId": gids[tab], "startRowIndex": head_row,
                          "endRowIndex": head_row + 1200,
                          "startColumnIndex": c, "endColumnIndex": c + 1},
                "rule": {
                    "condition": {"type": "ONE_OF_LIST",
                                  "values": [{"userEnteredValue": x} for x in ERABU]},
                    "showCustomUi": True, "strict": False}}}]})
            print(f"  {a1(c+1)}列にプルダウンを入れました: {'／'.join(ERABU)}")

        # 返信のある行だけ見る
        data, hyouji = [], []
        for n, r in enumerate(v[1:], start=head_row + 1):
            joutai = g(r, "送信済み")
            moto = g(r, "元の状態")
            memo = g(r, memo_col)
            if joutai != "返信あり" and moto != "返信あり" and not memo:
                continue
            bun, konkyo = bunrui_ateru(memo)
            mi = meigi.shiraberu(hyou, g(r, "電話番号"), g(r, namae_col)) if hyou else None
            ima = g(r, BUNRUI) if BUNRUI in ix else ""
            hyouji.append((n, joutai or "(空)", moto or "-", memo or "(空欄)", bun, konkyo,
                           mi[0] if mi else "未確認"))
            if WRITE and BUNRUI in ix and not ima:
                data.append({"range": f"{tab}!{a1(ix[BUNRUI]+1)}{n}", "values": [[bun]]})

        print(f"  返信のある行: {len(hyouji)}件")
        print(f"  {'行':>4} {'状態':<8} {'元':<8} {'分類':<12} {'名義':<6} メモ／根拠")
        for n, joutai, moto, memo, bun, konkyo, mg in hyouji:
            mark = "🔴" if bun in ("予約", "不明・未記録") else "  "
            print(f"  {mark}{n:>4} {joutai:<8} {moto:<8} {bun:<12} {mg:<6} {memo}  ← {konkyo}")
        if WRITE and data:
            sc.call(tok, f"/{SS}/values:batchUpdate", "POST",
                    {"valueInputOption": "RAW", "data": data})
            print(f"  分類を {len(data)}行 入れました（すでに入っている行は触りません）")

    # ---- 2つのタブで、同じお客様の記録が食い違っていないか ----
    #   お詫びタブと冬季タブに同じ方が載っている。**片方だけ更新されると気づけない。**
    #   自動では直さない。どちらが新しいかは機械には分からないため。
    print("\n===== 2つのタブの食い違い =====")
    hito = {}
    for tab, head_row in TABS:
        v = sc.call(tok, f"/{SS}/values/{urllib.parse.quote(tab + f'!A{head_row}:BZ1200', safe='')}"
                    ).get("values", [])
        if not v:
            continue
        head = v[0]
        ix = {c: i for i, c in enumerate(head)}

        def g(r, k):
            i = ix.get(k)
            return str(r[i]).strip() if i is not None and i < len(r) else ""

        for n, r in enumerate(v[1:], start=head_row + 1):
            if (g(r, "送信済み") != "返信あり" and g(r, "元の状態") != "返信あり"
                    and not g(r, memo_col) and not g(r, HONBUN) and not g(r, BUNRUI)):
                continue
            t = re.sub(r"\D", "", g(r, "電話番号"))
            if not t:
                continue
            hito.setdefault(t, {})[tab] = {
                "行": n, "メモ": g(r, memo_col), "本文": g(r, HONBUN), "分類": g(r, BUNRUI)}
    chigai = 0
    for t, d in hito.items():
        if len(d) < 2:
            continue
        (t1, a), (t2, b) = list(d.items())
        for k in ("メモ", "本文", "分類"):
            if a[k] != b[k]:
                chigai += 1
                print(f"  ★ {t1}行{a['行']} と {t2}行{b['行']} の「{k}」が違います")
                print(f"      {t1}: {a[k] or '(空)'}")
                print(f"      {t2}: {b[k] or '(空)'}")
    if chigai:
        print(f"  → {chigai}箇所。**どちらが新しいかは機械には分かりません。人が決めてください。**")
    else:
        print("  食い違いはありません。")

    if not WRITE:
        print("\n書き込みません（調べただけ）。実行するには: --confirm WRITE")
    print("\n※ `返信メモ` は1文字も書き換えていません。隣に列を足しただけです。")
    print("※ 「不明・未記録」は、**返信があったのに中身が残っていない行**の印です。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
