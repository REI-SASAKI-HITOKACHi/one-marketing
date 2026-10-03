#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""紹介割引の残高タブ・利用記録タブと、早期予約の確定フラグ列を作る（2026年スプシ）。

依頼 `20261003-02-crm`（第5回MTG 10/3 のオーナー決定・期限 10/8）。

    set -a; . ~/.config/one-hitter/line.env; set +a
    python3 tools/shoukai-zandaka-tab.py          # 何を作るかを出すだけ（既定）
    python3 tools/shoukai-zandaka-tab.py --kaku   # 作る（あるものは作り直さない）

## 紹介割引の決まり（オーナー 10/3）

①繰り越す ②分けて使える ③チラシ特典とは併用しない ④有効期限なし
⑤紹介先の**施工完了**で、紹介した方に**1人1,000円**・人数の上限なし

## 作るもの

- **`紹介割引_残高`**（式だけ。人は書かない）
  紹介者（顧客ID）ごとに：完了した紹介の人数 ×1,000円 − 使った額 ＝ 残り
  - 紹介者は `10〜12月_売上/顧客` の V列「紹介者（顧客ID）」から自動で拾う
  - 「完了」＝施工日付が今日以前で、売上（税込）が0より大きい行
  - **1人1,000円**：同じ方が2回施工しても1人と数える（氏名で重複を除く）
- **`紹介割引_利用`**（人が1行ずつ書く記録）
  記録日／使った人（顧客ID）／使った額／使った施工（例：11月 No.12）／チラシ特典を使っていない☑／記録者／判定（式）
  - 判定の式が「同じ施工で二重」「チラシ特典の確認なし」「残高を超えた」を赤で出す（**二重に引かない**）
- **10〜12月_売上/顧客 の W列「早期予約の確定」**（確定／未確定 のプルダウン）
  流入経路が「早期予約」で、まだ「確定」でない行に色が付く（和真さんの確定の電話の一覧になる）
  **値は入れない。** 確定したかどうかは台帳から読めないので、電話で確かめた人が選ぶ

## 守ること

- 過去の実績の値は1つも変えない（列の追加・入力規則・条件付き書式・新しいタブだけ）
- 2027年に広げるときは、`紹介割引_残高` の式の `{…}` に 2027 の範囲を足す
"""
import importlib.util
import os
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("sc", os.path.join(ROOT, "tools", "sheets_client.py"))
sc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sc)
SS = "1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64"
KAKU = "--kaku" in sys.argv
TSUKI = ["10月_売上/顧客", "11月_売上/顧客", "12月_売上/顧客"]
ZAN, RIYOU = "紹介割引_残高", "紹介割引_利用"


def stack(col):
    return "{" + ";".join(f"'{t}'!{col}4:{col}504" for t in TSUKI) + "}"


V, C, I, E = stack("V"), stack("C"), stack("I"), stack("E")
ZAN_ROWS = [
    ["紹介割引の残高（自動・人は書かない）"],
    ["紹介先の施工完了（施工日が今日以前・売上あり）で、紹介した方に1人1,000円。繰越・分けて使える・有効期限なし・チラシ特典と併用不可（オーナー 10/3）。"
     "使ったら『紹介割引_利用』に1行書く。"],
    [""],
    ["紹介者（顧客ID）", "顧客名", "完了した紹介（人）", "獲得額", "使った額", "残り", "まだ完了していない紹介（人）"],
    [f'=IFERROR(SORT(UNIQUE(FILTER({V},{V}<>""))),"")',
     f"=MAP(A5:A200,LAMBDA(id,IF(id=\"\",\"\",IFERROR(VLOOKUP(id,'顧客管理台帳'!A16:B1200,2,FALSE),\"（台帳に無い・未照合）\"))))",
     f"=MAP(A5:A200,LAMBDA(id,IF(id=\"\",\"\",IFERROR(ROWS(UNIQUE(FILTER({E},{V}=id,{C}<=TODAY(),{I}>0))),0))))",
     "=MAP(C5:C200,LAMBDA(n,IF(n=\"\",\"\",n*1000)))",
     f"=MAP(A5:A200,LAMBDA(id,IF(id=\"\",\"\",SUMIF('{RIYOU}'!B5:B2000,id,'{RIYOU}'!C5:C2000))))",
     "=MAP(D5:D200,E5:E200,LAMBDA(g,u,IF(g=\"\",\"\",g-u)))",
     f"=MAP(A5:A200,LAMBDA(id,IF(id=\"\",\"\",IFERROR(ROWS(UNIQUE(FILTER({E},{V}=id,{C}>TODAY()))),0))))"],
]
RIYOU_ROWS = [
    ["紹介割引の利用記録（使ったら1行書く・消さない）"],
    ["使った額は分けてよい（例：500円だけ）。チラシ特典と同じ施工では使わない。判定が赤なら、引く前に止まること。"],
    [""],
    ["記録日", "使った人（顧客ID）", "使った額", "使った施工（例：11月 No.12）", "チラシ特典を使っていない", "記録者", "判定（自動）"],
]
HANTEI = (f"=MAP(B5:B2000,C5:C2000,D5:D2000,E5:E2000,LAMBDA(id,gaku,sekou,chirashi,"
          f"IF(id=\"\",\"\",IF(COUNTIFS(B5:B2000,id,D5:D2000,sekou)>1,\"⚠ 同じ施工で二重\","
          f"IF(chirashi<>TRUE,\"⚠ チラシ特典の確認なし\","
          f"IF(IFERROR(VLOOKUP(id,'{ZAN}'!A5:F200,6,FALSE),-1)<0,\"⚠ 残高を超えた／残高に無い人\",\"OK\"))))))")


def main():
    tok = sc.access_token(sc.load_credentials())
    meta = sc.call(tok, f"/{SS}", query={"fields": "sheets.properties(title,sheetId)"})
    gid = {s["properties"]["title"]: s["properties"]["sheetId"] for s in meta["sheets"]}
    yaru = [t for t in (ZAN, RIYOU) if t not in gid]
    w_hitsuyou = []
    for t in TSUKI:
        h = sc.call(tok, f"/{SS}/values/{urllib.parse.quote(t + '!A2:X2', safe='')}").get("values", [[]])[0]
        if len(h) < 22 or h[21].strip() != "紹介者（顧客ID）":
            sys.exit(f"{t} の V2 が「紹介者（顧客ID）」ではありません。列がずれた可能性。止めます")
        if len(h) > 22 and h[22].strip():
            if h[22].strip() != "早期予約の確定":
                sys.exit(f"{t} の W2 にすでに「{h[22]}」があります。止めます")
        else:
            w_hitsuyou.append(t)
    print("新しく作るタブ:", yaru or "なし")
    print("W列「早期予約の確定」を足すタブ:", w_hitsuyou or "なし")
    if not KAKU:
        print("作りません（既定）。作るには --kaku")
        return 0
    reqs = [{"addSheet": {"properties": {"title": t, "gridProperties": {"rowCount": 2000 if t == RIYOU else 200,
                                                                        "columnCount": 8}}}} for t in yaru]
    if reqs:
        r = sc.call(tok, f"/{SS}:batchUpdate", "POST", {"requests": reqs})
        for x in r.get("replies", []):
            p = x["addSheet"]["properties"]
            gid[p["title"]] = p["sheetId"]
    if ZAN in yaru:
        sc.call(tok, f"/{SS}/values/{urllib.parse.quote(ZAN + '!A1', safe='')}", "PUT",
                {"values": ZAN_ROWS}, query={"valueInputOption": "USER_ENTERED"})
    if RIYOU in yaru:
        sc.call(tok, f"/{SS}/values/{urllib.parse.quote(RIYOU + '!A1', safe='')}", "PUT",
                {"values": RIYOU_ROWS + [[""] * 6 + [HANTEI]]}, query={"valueInputOption": "USER_ENTERED"})
        g = gid[RIYOU]
        reqs = [
            {"setDataValidation": {"range": {"sheetId": g, "startRowIndex": 4, "endRowIndex": 2000, "startColumnIndex": 4, "endColumnIndex": 5},
                                   "rule": {"condition": {"type": "BOOLEAN"}}}},
            {"setDataValidation": {"range": {"sheetId": g, "startRowIndex": 4, "endRowIndex": 2000, "startColumnIndex": 1, "endColumnIndex": 2},
                                   "rule": {"condition": {"type": "CUSTOM_FORMULA", "values": [{"userEnteredValue": '=REGEXMATCH(B5,"^C\\d{4}$")'}]},
                                            "strict": True, "inputMessage": "顧客ID（C0123 の形）"}}},
            {"setDataValidation": {"range": {"sheetId": g, "startRowIndex": 4, "endRowIndex": 2000, "startColumnIndex": 2, "endColumnIndex": 3},
                                   "rule": {"condition": {"type": "NUMBER_GREATER", "values": [{"userEnteredValue": "0"}]}, "strict": True}}},
            {"setDataValidation": {"range": {"sheetId": g, "startRowIndex": 4, "endRowIndex": 2000, "startColumnIndex": 0, "endColumnIndex": 1},
                                   "rule": {"condition": {"type": "DATE_IS_VALID"}, "strict": True}}},
            {"addConditionalFormatRule": {"index": 0, "rule": {
                "ranges": [{"sheetId": g, "startRowIndex": 4, "endRowIndex": 2000, "startColumnIndex": 0, "endColumnIndex": 7}],
                "booleanRule": {"condition": {"type": "CUSTOM_FORMULA", "values": [{"userEnteredValue": '=LEFT($G5,1)="⚠"'}]},
                                "format": {"backgroundColor": {"red": 1, "green": 0.8, "blue": 0.8}}}}}},
        ]
        sc.call(tok, f"/{SS}:batchUpdate", "POST", {"requests": reqs})
    for t in w_hitsuyou:
        g = gid[t]
        sc.call(tok, f"/{SS}:batchUpdate", "POST", {"requests": [
            {"copyPaste": {"source": {"sheetId": g, "startRowIndex": 1, "endRowIndex": 2, "startColumnIndex": 21, "endColumnIndex": 22},
                           "destination": {"sheetId": g, "startRowIndex": 1, "endRowIndex": 2, "startColumnIndex": 22, "endColumnIndex": 23},
                           "pasteType": "PASTE_FORMAT"}},
            {"setDataValidation": {"range": {"sheetId": g, "startRowIndex": 3, "endRowIndex": 504, "startColumnIndex": 22, "endColumnIndex": 23},
                                   "rule": {"condition": {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": "確定"}, {"userEnteredValue": "未確定"}]},
                                            "strict": True, "showCustomUi": True}}},
            {"addConditionalFormatRule": {"index": 0, "rule": {
                "ranges": [{"sheetId": g, "startRowIndex": 3, "endRowIndex": 504, "startColumnIndex": 22, "endColumnIndex": 23}],
                "booleanRule": {"condition": {"type": "CUSTOM_FORMULA", "values": [{"userEnteredValue": '=AND($D4="早期予約",$W4<>"確定")'}]},
                                "format": {"backgroundColor": {"red": 1, "green": 0.95, "blue": 0.6}}}}}},
        ]})
        sc.call(tok, f"/{SS}/values/{urllib.parse.quote(t + '!W2', safe='')}", "PUT",
                {"values": [["早期予約の確定"]]}, query={"valueInputOption": "RAW"})
    # 確かめ：式がエラーを出していないか
    for t in (ZAN, RIYOU):
        v = sc.call(tok, f"/{SS}/values/{urllib.parse.quote(t + '!A1:G6', safe='')}").get("values", [])
        err = [c for r in v for c in r if str(c).startswith("#")]
        print(t, "式のエラー:", err or "なし")
    print("作りました")
    return 0


if __name__ == "__main__":
    sys.exit(main())
