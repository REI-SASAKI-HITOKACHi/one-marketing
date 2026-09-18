#!/usr/bin/env python3
"""われわれが自動で作った作業用タブだけを、控えがあることを確かめてから消す。

  python3 tools/delete-sheet-tabs.py            # 消す予定を出すだけ（既定）
  python3 tools/delete-sheet-tabs.py --jikkou   # 実際に消す

★ オーナー指示（2026-09-18）
  「君が作成したシートのみを対象にしてね。こっちが作成した（元々あった）シートは
    削除対象にしないで」

  だから、次の3つを全部満たすタブだけを消す。1つでも欠けたら、そのタブは飛ばす。

  1. 名前が `控え_` または `履歴退避_` で始まる
     （どちらも tools が機械で付ける接頭辞。人が手で付けることはない）
  2. `data/sheets/backup/<タブ名>.json.gz` に控えがある（git に入っている）
  3. その控えが空でなく、読み直せる

  2 があるので「控えを取る前の新しいタブ」は自動的に対象外になる。
  たとえば 控え_冬季見込み客_20260917-103250 は 9/16 の控えより後にできたものなので
  消さない。本舗SMS 396名ぶんの書き戻し先でもある。
"""
import gzip
import json
import os
import pathlib
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sheets_client as sc

SHEET_ID = "1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64"
BACKUP = pathlib.Path(__file__).resolve().parent.parent / "data" / "sheets" / "backup"
SETTOU = ("控え_", "履歴退避_")


def hikae_ga_aru(namae):
    """控えがあり、読み直せて、空でないなら True。"""
    p = BACKUP / f"{namae}.json.gz"
    if not p.exists():
        return False, "控えが無い"
    try:
        with gzip.open(p, "rt", encoding="utf-8") as f:
            d = json.load(f)
    except Exception as e:
        return False, f"控えが読めない（{e}）"
    gyou = d.get("values") if isinstance(d, dict) else d
    if not gyou:
        return False, "控えが空"
    return True, f"控え {len(gyou)}行"


def main():
    jikkou = "--jikkou" in sys.argv
    token = sc.access_token(sc.load_credentials())
    meta = sc.call(token, f"/{SHEET_ID}", query={"fields": "sheets.properties"})
    tabs = [s["properties"] for s in meta["sheets"]]

    kesu, nokosu = [], []
    for t in tabs:
        na = t["title"]
        if not na.startswith(SETTOU):
            continue                      # オーナーのタブ。数えもしない
        ok, riyuu = hikae_ga_aru(na)
        (kesu if ok else nokosu).append((na, t["sheetId"], riyuu))

    print(f"スプレッドシートのタブ: {len(tabs)}本")
    print(f"消す対象（接頭辞が合い、控えもある）: {len(kesu)}本")
    for na, sid, riyuu in kesu:
        print(f"  消す    {na}  [{sid}]  {riyuu}")
    if nokosu:
        print(f"\n★ 接頭辞は合うが、控えが無いので残すもの: {len(nokosu)}本")
        for na, sid, riyuu in nokosu:
            print(f"  残す    {na}  [{sid}]  ← {riyuu}")

    if not kesu:
        print("\n消すものがありません。")
        return
    if not jikkou:
        print("\n（これは予定です。実際に消すには --jikkou を付けてください）")
        return

    req = [{"deleteSheet": {"sheetId": sid}} for _, sid, _ in kesu]
    sc.call(token, f"/{SHEET_ID}:batchUpdate", method="POST", payload={"requests": req})
    print(f"\n消しました: {len(kesu)}本")


if __name__ == "__main__":
    main()
