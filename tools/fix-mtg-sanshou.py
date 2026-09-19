#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MTGシートの中の参照を、統合後のシートだけで追えるようにする。

【オーナー指示（原文）】
  2026-09-19
  「D179セル”T032”みたいな元のシートで参照していたような箇所が参照できないから
    新しいシートに併せて採番しなおしておいて」

【何が問題だったか】
  回ごとのタブを1枚に統合したので、**同じシートの中に「No.1」が4つある**。
    第1回（11行目〜）No.1〜21
    第2回 ■4（74行目〜）No.1〜21  ← 第1回の21項目を追っている表
    第2回 ■5（100行目〜）No.1〜25
    第3回 3-2（177行目〜）No.1〜25 ← 第2回■5の25項目を追っている表
  この状態で「前回#3」と書いてあっても、どの回のどの表の3番か決まらない。
  `T032` も、TODOタブを開かないと何のことか分からない。

【どう直すか】
  1. `前回#N` → `第1回 #N`（第1回は 2026-09-04。同じシートの11行目から）
  2. `T0xx` は本文に残したまま、**末尾に「■ 3-8 この回で出てくる T番号」の表を足す**。
     本文に注釈を差し込むとセルが長くなり、かっこが二重になって読みにくい。
     見出しは **TODOタブからそのまま引く**（言い換えるとTODO側と食い違う）

【触らないもの】
  **第1回（1〜32行）と第2回（33〜155行）は過去の打合せ記録。1文字も触らない。**
  直すのは第3回（156行目以降）だけ。

  python3 tools/fix-mtg-sanshou.py            # 何をするか出すだけ
  python3 tools/fix-mtg-sanshou.py --jikkou   # 直す
"""
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sheets_client as sc

SS = "1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64"
TAB = "MTGシート"
DAI3 = 156          # 第3回はこの行から。ここより上は過去の記録なので触らない


def rd(rng):
    o = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "sheets_client.py"),
                        "read", SS, rng], capture_output=True, text=True)
    if o.returncode:
        sys.exit(o.stderr[:300])
    return json.loads(o.stdout or "[]")


def main():
    jikkou = "--jikkou" in sys.argv

    # TODOタブの見出しを引く（言い換えずに、そのまま使う）
    todo, todo_jotai = {}, {}
    for r in rd("'TODO'!A7:E48"):
        r = list(r) + [""] * (5 - len(r))
        if str(r[0]).strip():
            todo[str(r[0]).strip()] = str(r[4]).strip()
            todo_jotai[str(r[0]).strip()] = (str(r[1]).strip(), str(r[4]).strip())
    print(f"TODOタブから {len(todo)}件の見出しを読みました")

    rows = rd(f"'{TAB}'!A1:I310")
    naosu = []
    for gi, r in enumerate(rows, 1):
        if gi < DAI3:
            continue
        for ci, c in enumerate(r):
            moto = str(c)
            s = moto
            # 1. 前回#N → 第1回 #N
            s = re.sub(r"前回#(\d+)", r"第1回 #\1", s)
            if s != moto:
                naosu.append((gi, ci, moto, s))

    print(f"\n直すセル: {len(naosu)}件")
    for gi, ci, moto, s in naosu:
        print(f"  {chr(65+ci)}{gi}")
        print(f"    前: {moto[:96]}")
        print(f"    後: {s[:96]}")

    if not jikkou:
        print("\n（--jikkou を付けていないので直していません）")
        return

    # 第3回に出てくる T番号を集めて、末尾に参照表を作る
    tsukau = sorted({t for gi, r in enumerate(rows, 1) if gi >= DAI3
                     for c in r for t in re.findall(r"T\d{3}", str(c))})
    owari = len(rows)
    hyou = [[""], ["■ 3-8　この回で出てくる T番号（TODOタブの通し番号）"],
            ["→ 本文の T005 などは、売上スプシの『TODO』タブの番号です。下が対応表です。"],
            ["T番号", "状態", "やること（TODOタブの見出しをそのまま）"]]
    for k in tsukau:
        j, y = todo_jotai.get(k, ("?", "見つかりません"))
        hyou.append([k, j, y])

    req = []
    for gi, ci, _, s in naosu:
        req.append({"updateCells": {
            "range": {"sheetId": None, "startRowIndex": gi - 1, "endRowIndex": gi,
                      "startColumnIndex": ci, "endColumnIndex": ci + 1},
            "rows": [{"values": [{"userEnteredValue": {"stringValue": s}}]}],
            "fields": "userEnteredValue"}})

    tok = sc.access_token(sc.load_credentials())
    meta = sc.call(tok, f"/{SS}", query={"fields": "sheets.properties"})
    sid = next(x["properties"]["sheetId"] for x in meta["sheets"] if x["properties"]["title"] == TAB)
    for q in req:
        q["updateCells"]["range"]["sheetId"] = sid
    sc.call(tok, f"/{SS}:batchUpdate", method="POST", payload={"requests": req})
    import pathlib as _p, tempfile
    tf = _p.Path(tempfile.gettempdir()) / "mtg-sanshou.json"
    tf.write_text(json.dumps(hyou, ensure_ascii=False), encoding="utf-8")
    o = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "sheets_client.py"),
                        "write", SS, f"'{TAB}'!A{owari+1}", str(tf)], capture_output=True, text=True)
    print(o.stdout.strip() or o.stderr[:200])
    print(f"\n✅ 直しました（本文 {len(req)}セル）。")
    print(f"   末尾に「■ 3-8 この回で出てくる T番号」を足しました（{len(tsukau)}件）。")
    print("   第1回・第2回には触っていません。")


if __name__ == "__main__":
    main()
