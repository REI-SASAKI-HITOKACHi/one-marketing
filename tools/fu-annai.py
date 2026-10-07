#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""施工後フォロー（次回のご提案）SMS の本文を、**名乗り照合を通してから**1人分だけ出す。

依頼 `20261004-02-crm`（長田様・初のネット受注）と、10/7 の CMO 巡回（鈴木様・坂井様の施工後）。
ひな形は `data/fu-annai.txt`。**送信はしない**（和真さんの手送り・オーナー承認のあと）。

    set -a; . ~/.config/one-hitter/line.env; set +a      # スプシの鍵（GOOGLE_SHEETS_SA_KEY）が要る
    python3 tools/fu-annai.py --tel 0901234xxxx --namae "長田 〇〇" --teian レンジフード --src fu_nagata --anketo

## 本文を出す前に機械で確かめること（どれか1つでも引っかかったら本文を出さない）

1. **名乗り**：`meigi_shiraberu()`（台帳の最新の施工の名義・同日ルールつき）が**自社**
2. **クレーム履歴**：顧客管理台帳 AG列が空（施工後のご指摘がある方には定型の案内を出さない）
3. **今後の予約**：今日より先の施工行が無い（もう予約がある方に「ご予約を」は送らない）
4. 文面：`honbun_ihan("自社", 本文)` が空

**鍵が無い・台帳が読めない ＝ 照合できない ＝ 本文を出さない。**

## 提案（--teian）

アンケートの「次に気になる所」があればそれを使い（--anketo を付けると「アンケートでお聞きした」と書く）、
無ければ台帳の「次のおすすめ」から選ぶ。
"""
import argparse
import os
import re
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import meigi_check as MC  # noqa: E402

SS = "1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64"
# 料金表どおり（税込・docs/price-master.md 2026-10-07 時点）。1箇所の単体価格
KAKAKU = {
    "レンジフード": ("レンジフード", "レンジフード18,480円（プロペラ式は10,780円）"),
    "浴室": ("浴室", "浴室18,480円"),
    "キッチン": ("キッチン", "キッチン18,480円"),
    "エアコン": ("エアコン", "エアコン10,780円（お掃除機能付き17,380円）"),
    "洗濯機": ("洗濯機", "洗濯機17,380円"),
}


def kumitate(body):
    """3通（210字）に収め、URL が 70・140 文字目をまたがない並びを選ぶ。どれもだめなら None。

    URL の前置きの言い回し3通り × 並び2通り（URL が最後／URL を配信停止の行の前に出す）を順に試す。
    """
    gyou = body.split("\n")
    url = gyou[-1]
    kouho = []
    for mae in ("ご予約はこちらから", "ご予約はこちら", "空き日時の確認・ご予約はこちらから"):
        g = gyou[:-2] + [mae, url]
        kouho += [g, g[:-4] + g[-2:] + g[-4:-2]]
    for g in kouho:
        b = "\n".join(g)
        u = b.find(url)
        if len(b) <= 210 and not any(u < k < u + len(url) for k in (70, 140)):
            return b
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tel", required=True)
    ap.add_argument("--namae", required=True, help="台帳どおりの氏名（姓と名の間に空白）")
    ap.add_argument("--teian", required=True, choices=sorted(KAKAKU))
    ap.add_argument("--src", required=True, help="予約ページの src（例：fu_nagata）")
    ap.add_argument("--anketo", action="store_true", help="アンケートで「次に気になる所」に挙げていた")
    a = ap.parse_args()

    hyou, err = MC.hyou_yomu()
    if hyou is None:
        sys.exit(f"台帳を読めません（{err}）。照合できないので本文を出しません")
    ok, riyuu = MC.atesaki_ok(hyou, a.tel, a.namae, "自社")
    if not ok:
        sys.exit(f"名乗りの照合で止めました：{riyuu}")
    dsk = MC._load()
    tok = dsk.tok_get()
    L = dsk.sc.call(tok, f"/{SS}/values/{urllib.parse.quote('顧客管理台帳!A16:AG1200', safe='')}").get("values", [])
    tel = dsk.tel_norm(a.tel)
    nm = dsk.name_norm(a.namae)
    for r in L:
        if (len(r) > 3 and dsk.tel_norm(r[3]) == tel and tel) or (len(r) > 1 and dsk.name_norm(r[1]) == nm):
            if len(r) > 32 and str(r[32]).strip():
                sys.exit("台帳にクレーム履歴（AG）があります。定型の案内は出しません")
    import datetime
    kyou = datetime.date.today()
    if any(j[0] > kyou and (j[1] == tel or j[2] == nm) for j in dsk.jobs_yomu()):
        sys.exit("今日より先の施工（予約）が入っています。案内は出しません")

    t = "\n".join(l for l in open(os.path.join(ROOT, "data", "fu-annai.txt"), encoding="utf-8").read().splitlines()
                  if not l.startswith("#")).strip()
    teian, ryoukin = KAKAKU[a.teian]
    sei = re.split(r"[\s　]", a.namae.strip())[0]
    body = (t.replace('"姓"', sei).replace('"きっかけ"', "アンケートでお聞きした" if a.anketo else "")
             .replace('"提案"', teian).replace('"料金"', ryoukin).replace('"src"', a.src))
    body = kumitate(body)
    if body is None:
        sys.exit("3通（210字）に収まらないか、URLが通の境目をまたぎます。ひな形を直してください")
    ihan = MC.honbun_ihan("自社", body)
    if ihan:
        sys.exit("文面が規則に合いません：" + "／".join(ihan))
    print(f"名乗り照合：{riyuu}\n{len(body)}文字（{-(-len(body) // 70)}通ぶん）\n" + "-" * 30)
    print(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
