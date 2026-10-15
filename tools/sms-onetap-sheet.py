#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本文を作り終えた SMS の宛先一覧から、ワンタップ送信タブを作る（冬季SMS・11月SMSと同じ仕様）。

    python3 tools/sms-onetap-sheet.py --taishou ~/.cache/one-hitter/bin2.json --tab 11月SMS2便_送信 \\
        --url https://yoyaku.onehitter.jp/?src=sms_nov2 --midashi "11月SMS 2便目" [--kaku] [--tsukurinaoshi]

対象 JSON：[{full, t, body, last, kubun, fuyu}, …]（git の外。電話番号が入る）。
**送信はしない。** 和真さんが D列「▶ 送る」をタップ → 社内ページ s.html → SMS アプリに宛先と本文入り。

## 1行ずつ、書く前に機械で確かめること（1つでも外れたらその行は作らない）
- 名乗り：`atesaki_ok()`（台帳の最新の施工＝同日ルールつき）が **自社**
- 本文：`honbun_ihan("自社")` が空／210字（3通）以内／予約URL・個人情報URL・当社の電話が 70・140 字目をまたがない
- 予約URL・個人情報URL・s.html が 200 を返す

## 陣（送る日）
`fuyu`（9月に冬季SMSを送った方）が真なら第2陣（10/27 以降）、偽なら第1陣（10/20）。
オーナー 10/1「最近連絡とってる人に重複して送らないように」（30日）に合わせるため。
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
S_HTML = "https://oh-naibu-sms-k7q3x.netlify.app/s.html"
PRIVACY = "https://lp.onehitter.jp/privacy/"
TEL_OH = "080-8043-8259"
JIN = {False: ("第1陣", "10/20（火）12時"), True: ("第2陣", "10/27（火）12時以降")}


def ikiteru(url):
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            return r.status == 200
    except Exception:
        return False


def kensa(b, url, jougen=210, privacy_hissu=True):
    """本文の検査。jougen が 210（KDDI の3通）以下のときだけ、URL・電話が 70 字ごとの境目をまたがないかも見る。
    和真さんの手送り（1通に結合される）の型（山口様の型・約270〜290字）は --jougen 300 --privacy-nashi で通す。"""
    ng = MC.honbun_ihan("自社", b)
    if len(b) > jougen:
        ng.append(f"{len(b)}字（上限{jougen}）")
    for kw in (url, PRIVACY, TEL_OH):
        u = b.find(kw)
        if u < 0 and (kw == url or (kw == PRIVACY and privacy_hissu)):
            ng.append(f"{kw[:20]}が本文に無い")
        if u >= 0 and jougen <= 210 and any(u < k < u + len(kw) for k in (70, 140)):
            ng.append(f"{kw[:12]}…が通の境目")
    return ng


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--taishou", required=True)
    ap.add_argument("--tab", required=True)
    ap.add_argument("--url", required=True)
    ap.add_argument("--midashi", required=True)
    ap.add_argument("--kaku", action="store_true")
    ap.add_argument("--tsukurinaoshi", action="store_true")
    ap.add_argument("--jougen", type=int, default=210, help="本文の上限字数（手送りの山口様の型は 300）")
    ap.add_argument("--privacy-nashi", action="store_true", help="個人情報URLを必須にしない（山口様の型）")
    a = ap.parse_args()
    for u in (a.url, PRIVACY, S_HTML):
        if not ikiteru(u):
            sys.exit(f"{u} が開けません。作りません")
    hyou, err = MC.hyou_yomu()
    if hyou is None:
        sys.exit(f"台帳を読めません（{err}）。照合できないので作りません")
    dsk = MC._load()
    taishou = json.load(open(os.path.expanduser(a.taishou), encoding="utf-8"))
    rows, tometa = [], []
    for o in sorted(taishou, key=lambda o: (bool(o.get("fuyu")), o.get("kubun", ""), o["last"])):
        ok, riyuu = MC.atesaki_ok(hyou, o["t"], o["full"], "自社")
        if o.get("ng"):
            tometa.append((o.get("kubun"), o["ng"]))
            continue
        ng = kensa(o["body"], a.url, a.jougen, not a.privacy_nashi)
        if not ok or ng:
            tometa.append((o.get("kubun"), riyuu if not ok else "／".join(ng)))
            continue
        link = S_HTML + "#to=" + dsk.tel_norm(o["t"]) + "&b=" + urllib.parse.quote(o["body"], safe="")
        rows.append((o, link))
    jin = {k: sum(1 for o, _ in rows if bool(o.get("fuyu")) == k) for k in (False, True)}
    print(f"対象 {len(taishou)}名 → 載せる {len(rows)}名（第1陣 {jin[False]}・第2陣 {jin[True]}）／止めた {len(tometa)}名")
    for x in tometa:
        print("  止めた:", x)
    if not a.kaku:
        print("書きません（既定）。作るには --kaku")
        return 0
    tok = dsk.tok_get()
    sc = dsk.sc
    meta = sc.call(tok, f"/{SS}", query={"fields": "sheets.properties(title,sheetId)"})
    gid = {s["properties"]["title"]: s["properties"]["sheetId"] for s in meta["sheets"]}
    if a.tab in gid:
        if not a.tsukurinaoshi:
            sys.exit(f"「{a.tab}」タブがもうあります。作り直すなら --tsukurinaoshi")
        e = sc.call(tok, f"/{SS}/values/{urllib.parse.quote(a.tab + '!E6:E300', safe='')}").get("values", [])
        if any(str(c).strip() for r in e for c in r):
            sys.exit("前のタブの E列（送信済み）に記録があります。消さずに止めます")
        sc.call(tok, f"/{SS}:batchUpdate", "POST", {"requests": [{"deleteSheet": {"sheetId": gid[a.tab]}}]})
    r = sc.call(tok, f"/{SS}:batchUpdate", "POST", {"requests": [{"addSheet": {"properties": {
        "title": a.tab, "gridProperties": {"rowCount": len(rows) + 10, "columnCount": 9, "frozenRowCount": 5}}}}]})
    g = r["replies"][0]["addSheet"]["properties"]["sheetId"]

    def cell(v, link=None):
        c = {"userEnteredValue": {"stringValue": str(v)}}
        if link:
            c["userEnteredFormat"] = {"textFormat": {"link": {"uri": link}, "bold": True}}
        return c
    head = [
        [cell(f"{a.midashi}（ワンヒッター名義）／ワンタップ送信シート")],
        [cell("スマホでの送信作業用。D列の「▶ 送る」をタップ → 出てきたリンクを開く → SMSが宛先と本文入りで開く → 送信 → E列で「送信済み」を選ぶ。"
              "開かないときは F列の本文をコピー（手打ちはしない）。**A列の送る日より前には送らない**（第2陣は9月に冬季SMSを受け取った方）。")],
        [cell(f"作成 {datetime.date.today()} 顧客接点担当。名乗りは台帳と照合済み（全員 自社）。電話番号を含むので、送り終えたらこのタブは消してよい")],
        [cell("")],
        [cell(x) for x in ("陣・送る日", "顧客名", "電話番号", "▶SMSを開く", "送信済み", "送信する本文", "前回の施工", "区分", "返信メモ")],
    ]
    body = [[cell(f"{JIN[bool(o.get('fuyu'))][0]} {JIN[bool(o.get('fuyu'))][1]}"), cell(o["full"]), cell(o["t"]),
             cell("▶ 送る", link), cell(""), cell(o["body"]), cell(o["last"]), cell(o.get("kubun", "")), cell("")]
            for o, link in rows]
    sc.call(tok, f"/{SS}:batchUpdate", "POST", {"requests": [
        {"updateCells": {"start": {"sheetId": g, "rowIndex": 0, "columnIndex": 0},
                         "rows": [{"values": x} for x in head + body],
                         "fields": "userEnteredValue,userEnteredFormat.textFormat"}},
        {"setDataValidation": {"range": {"sheetId": g, "startRowIndex": 5, "endRowIndex": 5 + len(rows),
                                         "startColumnIndex": 4, "endColumnIndex": 5},
                               "rule": {"condition": {"type": "ONE_OF_LIST", "values": [
                                   {"userEnteredValue": v} for v in ("送信済み", "返信あり", "不通・エラー", "対象外")]},
                                   "showCustomUi": True}}},
        {"repeatCell": {"range": {"sheetId": g, "startColumnIndex": 5, "endColumnIndex": 6},
                        "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP"}}, "fields": "userEnteredFormat.wrapStrategy"}},
    ]})
    v = sc.call(tok, f"/{SS}", query={"ranges": f"{a.tab}!C6:D{5 + len(rows)}", "includeGridData": "true",
                                      "fields": "sheets.data.rowData.values(formattedValue,hyperlink)"})
    rd = v["sheets"][0]["data"][0].get("rowData", [])
    zero = sum(1 for x in rd if x["values"][0].get("formattedValue", "").startswith("0"))
    linkok = sum(1 for x in rd if ("#to=" + x["values"][0].get("formattedValue", "")) in x["values"][1].get("hyperlink", ""))
    print(f"タブ「{a.tab}」（gid={g}）を作りました：{len(rd)}行／電話番号の先頭0 {zero}/{len(rd)}／リンクの宛先一致 {linkok}/{len(rd)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
