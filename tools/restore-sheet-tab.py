#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""git に落としてある控えから、タブを元どおり作り直す。

【なぜ要るか】
  控えをスプレッドシートのタブとして持つと、際限なく増える（2026-09-19 に77本まで膨らんだ）。
  控えは git に置き、**戻すのが1コマンドで済む**ようにしておけば、タブに残す理由が無くなる。

【使い方】
  python3 tools/restore-sheet-tab.py                     # 戻せる控えの一覧を出す
  python3 tools/restore-sheet-tab.py <控えの名前>         # 中身を確かめるだけ（書かない）
  python3 tools/restore-sheet-tab.py <控えの名前> --jikkou # タブを作って書き戻す

  例: python3 tools/restore-sheet-tab.py 控え_冬季見込み客_20260918-025523 --jikkou

  同じ名前のタブが既にあるときは、**上書きせずに止まる**。
  消したはずのものを二重に作らないため。
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


def ichiran():
    hikae = sorted(BACKUP.glob("*.json.gz"))
    if not hikae:
        sys.exit(f"{BACKUP} に控えがありません。")
    print(f"戻せる控え: {len(hikae)}本  （{BACKUP}）\n")
    for p in hikae:
        na = p.name[: -len(".json.gz")]
        try:
            with gzip.open(p, "rt", encoding="utf-8") as f:
                d = json.load(f)
            v = d.get("values") if isinstance(d, dict) else d
            itsu = d.get("torimasu", "") if isinstance(d, dict) else ""
            print(f"  {na:<40} {len(v):>5}行  {p.stat().st_size:>8,}B  {itsu}")
        except Exception as e:
            print(f"  {na:<40} 🔴 読めません（{e}）")


def main():
    hikiwatashi = [a for a in sys.argv[1:] if not a.startswith("--")]
    jikkou = "--jikkou" in sys.argv
    if not hikiwatashi:
        ichiran()
        return

    na = hikiwatashi[0]
    p = BACKUP / f"{na}.json.gz"
    if not p.exists():
        sys.exit(f"控えがありません: {p}\n  一覧を見る: python3 tools/restore-sheet-tab.py")
    with gzip.open(p, "rt", encoding="utf-8") as f:
        d = json.load(f)
    v = d.get("values") if isinstance(d, dict) else d
    if not v:
        sys.exit("控えが空です。書き戻しません。")

    umatte = sum(1 for r in v for c in r if str(c).strip())
    retsu = max((len(r) for r in v), default=0)
    print(f"控え: {na}")
    print(f"  {len(v)}行 × {retsu}列 ／ 空でないセル {umatte:,}")
    print(f"  取った時点: {d.get('torimasu', '（記録なし）') if isinstance(d, dict) else '（記録なし）'}")
    print(f"  先頭の行: {json.dumps(v[0][:6], ensure_ascii=False)}")

    if not jikkou:
        print("\n（--jikkou を付けていないので書き戻していません）")
        return

    tok = sc.access_token(sc.load_credentials())
    meta = sc.call(tok, f"/{SHEET_ID}", query={"fields": "sheets.properties"})
    aru = {s["properties"]["title"] for s in meta["sheets"]}
    if na in aru:
        sys.exit(f"🔴 中止：同じ名前のタブが既にあります（{na}）。上書きはしません。")

    sc.call(tok, f"/{SHEET_ID}:batchUpdate", method="POST", payload={"requests": [
        {"addSheet": {"properties": {"title": na,
                                     "gridProperties": {"rowCount": max(len(v), 100),
                                                        "columnCount": max(retsu, 26)}}}}]})
    sc.call(tok, f"/{SHEET_ID}/values/{na}!A1", method="PUT",
            payload={"values": v}, query={"valueInputOption": "RAW"})
    print(f"\n✅ 書き戻しました: {na}（{len(v)}行）")


if __name__ == "__main__":
    main()
