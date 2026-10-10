#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""11月の早期予約SMS（拡大案19名）の「ワンタップ送信シート」を作る。前回（9月の冬季SMS）と同じ仕様。

依頼 `20261010-01-crm`（第6回MTG No.6 オーナー決定「送るのは和真…ワンタップで送信できるように、前回と同じ仕様」）。
**送信はしない。** 和真さんがスマホで「▶ 送る」をタップ → 社内ページ s.html が開く → SMS アプリに宛先と本文が入る。

    python3 tools/nov-sms-sheet.py --taishou ~/.cache/one-hitter/nov-kakudai.json            # 表示のみ
    python3 tools/nov-sms-sheet.py --taishou ... --kaku                                       # タブを作る
    python3 tools/nov-sms-sheet.py --taishou ... --kaku --privacy https://lp.onehitter.jp/privacy/   # 公開後に差し替え

## 1行ずつ、書く前に機械で確かめること（1つでも外れたらその行は作らない）
- 名乗り：`meigi_shiraberu()`（台帳の最新の施工＝同日ルールつき）が**自社**
- 本文：`honbun_ihan("自社", 本文)` が空／210字（3通）以内／URL・電話番号が 70・140 字目をまたがない
- 個人情報の取扱いの URL が **200 を返す**（公開前の URL は使わない）

対象の JSON は `[{full, t, sei, last}, …]`（git の外。電話番号が入る）。シートのタブにも電話番号は入るので、
**送り終えたらタブは消してよい**（消すのは CMO の判断）。
"""
import argparse
import datetime
import json
import os
import sys
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import meigi_check as MC  # noqa: E402

SS = "1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64"
TAB = "11月早期予約SMS_送信"
S_HTML = "https://oh-naibu-sms-k7q3x.netlify.app/s.html"
YOYAKU = "https://yoyaku.onehitter.jp/?src=sms_nov"
TEL_OH = "080-8043-8259"
HINAGATA = """"姓"さま
"年月"にお伺いしたワンヒッター渡辺です。
11月の作業は今のご予約で10%引き（1箇所の場合。12月は割引なし・繁忙期加算）。
ご予約 {Y}
電話 {T}
不要な方はご返信ください。
個人情報の取扱い {P}
ワンヒッター株式会社"""


def ikiteru(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method="GET"), timeout=20) as r:
            return r.status == 200
    except Exception:
        return False


def honbun(sei, nengetsu, privacy):
    b = HINAGATA.replace('"姓"', sei).replace('"年月"', nengetsu).format(Y=YOYAKU, T=TEL_OH, P=privacy)
    ng = MC.honbun_ihan("自社", b)
    if len(b) > 210:
        ng.append(f"{len(b)}字（3通を超える）")
    for kw in (YOYAKU, privacy, TEL_OH):
        u = b.find(kw)
        if any(u < k < u + len(kw) for k in (70, 140)):
            ng.append(f"{kw[:12]}…が通の境目をまたぐ")
    return b, ng


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--taishou", required=True)
    ap.add_argument("--privacy", default="https://one-hitter.jp/privacy_policy/")
    ap.add_argument("--kaku", action="store_true")
    ap.add_argument("--tsukurinaoshi", action="store_true",
                    help="この道具が作った同名のタブ（A1 の見出しで確かめる）を消してから作り直す")
    a = ap.parse_args()
    if not ikiteru(a.privacy):
        sys.exit(f"個人情報の取扱いの URL が開けません（{a.privacy}）。公開前の URL は使いません")
    hyou, err = MC.hyou_yomu()
    if hyou is None:
        sys.exit(f"台帳を読めません（{err}）。照合できないので作りません")
    dsk = MC._load()
    taishou = json.load(open(os.path.expanduser(a.taishou), encoding="utf-8"))
    rows, tometa = [], []
    for o in sorted(taishou, key=lambda o: o["last"], reverse=True):
        ok, riyuu = MC.atesaki_ok(hyou, o["t"], o["full"], "自社")
        d = datetime.date.fromisoformat(o["last"])
        b, ng = honbun(o["sei"], f"{d.year}年{d.month}月", a.privacy)
        if not ok or ng:
            tometa.append((o["last"], riyuu if not ok else "／".join(ng)))
            continue
        link = S_HTML + "#to=" + dsk.tel_norm(o["t"]) + "&b=" + urllib.parse.quote(b, safe="")
        rows.append((o, b, link))
    print(f"対象 {len(taishou)}名 → シートに載せる {len(rows)}名／止めた {len(tometa)}名")
    for x in tometa:
        print("  止めた:", x)
    if not a.kaku:
        print("書きません（既定）。作るには --kaku")
        return 0
    tok = dsk.tok_get()
    sc = dsk.sc
    meta = sc.call(tok, f"/{SS}", query={"fields": "sheets.properties(title,sheetId)"})
    gid = {s["properties"]["title"]: s["properties"]["sheetId"] for s in meta["sheets"]}
    if TAB in gid:
        if not a.tsukurinaoshi:
            sys.exit(f"「{TAB}」タブがもうあります。作り直すなら --tsukurinaoshi（上書きはしない）")
        a1 = sc.call(tok, f"/{SS}/values/{urllib.parse.quote(TAB + '!A1:A1', safe='')}").get("values", [[""]])[0][0]
        if not str(a1).startswith("11月の早期予約SMS（ワンヒッター名義）／ワンタップ送信シート"):
            sys.exit("同名のタブの見出しが、この道具の作ったものと違います。消さずに止めます")
        e = sc.call(tok, f"/{SS}/values/{urllib.parse.quote(TAB + '!E6:E100', safe='')}").get("values", [])
        if any(str(c).strip() for r in e for c in r):
            sys.exit("前のタブの E列（送信済み）に記録があります。送信の記録を消さないよう、作り直しを止めます")
        sc.call(tok, f"/{SS}:batchUpdate", "POST", {"requests": [{"deleteSheet": {"sheetId": gid[TAB]}}]})
        print(f"前のタブ（この道具が作ったもの・送信の記録なし）を消しました")
    r = sc.call(tok, f"/{SS}:batchUpdate", "POST", {"requests": [{"addSheet": {"properties": {
        "title": TAB, "gridProperties": {"rowCount": len(rows) + 10, "columnCount": 7, "frozenRowCount": 5}}}}]})
    g = r["replies"][0]["addSheet"]["properties"]["sheetId"]
    sw = {"stringValue": ""}

    def cell(v, link=None):
        c = {"userEnteredValue": {"stringValue": str(v)}}
        if link:
            c["userEnteredFormat"] = {"textFormat": {"link": {"uri": link}, "bold": True}}
        return c
    head = [
        [cell("11月の早期予約SMS（ワンヒッター名義）／ワンタップ送信シート")],
        [cell("スマホでの送信作業用。D列の「▶ 送る」をタップ → 出てきたリンクを開く → SMSが宛先と本文入りで開く → 送信 → E列で「送信済み」を選ぶ。"
              "開かないときは、F列の本文をコピーして貼ってください（手打ちはしないこと）。送る日：10/14（火）12時（オーナー承認後）")],
        [cell(f"作成 {datetime.date.today()} 顧客接点担当（20261010-01-crm）。名乗りは台帳と照合済み（全員 自社）。送り終えたらこのタブは消してよい（電話番号を含む）")],
        [cell("")],
        [cell(x) for x in ("優先", "顧客名", "電話番号", "▶SMSを開く", "送信済み", "送信する本文", "前回の施工")],
    ]
    body_rows = [[cell(i), cell(o["full"]), cell(o["t"]), cell("▶ 送る", link), cell(""), cell(b), cell(o["last"])]
                 for i, (o, b, link) in enumerate(rows, 1)]
    sc.call(tok, f"/{SS}:batchUpdate", "POST", {"requests": [
        {"updateCells": {"start": {"sheetId": g, "rowIndex": 0, "columnIndex": 0},
                         "rows": [{"values": r_} for r_ in head + body_rows],
                         "fields": "userEnteredValue,userEnteredFormat.textFormat"}},
        {"setDataValidation": {"range": {"sheetId": g, "startRowIndex": 5, "endRowIndex": 5 + len(rows),
                                         "startColumnIndex": 4, "endColumnIndex": 5},
                               "rule": {"condition": {"type": "ONE_OF_LIST", "values": [
                                   {"userEnteredValue": v} for v in ("送信済み", "返信あり", "不通・エラー", "対象外")]},
                                   "showCustomUi": True}}},
        {"repeatCell": {"range": {"sheetId": g, "startColumnIndex": 5, "endColumnIndex": 6},
                        "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP"}}, "fields": "userEnteredFormat.wrapStrategy"}},
    ]})
    # 読み直して確かめる：電話番号の先頭0・リンクの宛先
    v = sc.call(tok, f"/{SS}", query={"ranges": f"{TAB}!C6:D{5 + len(rows)}", "includeGridData": "true",
                                      "fields": "sheets.data.rowData.values(formattedValue,hyperlink)"})
    rd = v["sheets"][0]["data"][0].get("rowData", [])
    zero = sum(1 for x in rd if x["values"][0].get("formattedValue", "").startswith("0"))
    linkok = sum(1 for x in rd if ("#to=" + x["values"][0].get("formattedValue", "")) in x["values"][1].get("hyperlink", ""))
    print(f"タブ「{TAB}」を作りました：{len(rd)}行／電話番号の先頭0 {zero}/{len(rd)}／リンクの宛先一致 {linkok}/{len(rd)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
