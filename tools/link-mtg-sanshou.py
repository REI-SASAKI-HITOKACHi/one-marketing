#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MTGシートの中の「どこそこ」という記述を、そこへ飛べるリンクにする。

【オーナー指示（原文）】
  2026-09-19
  「同様に、ファイル内の特定箇所を指摘して議題に挙げる場合には、
    必ず該当箇所に飛べるリンクを埋め込んで。」

【どうやるか】
  セル全体を `=HYPERLINK()` にすると、1セルに1つしかリンクを張れず、本文も消える。
  そこで **textFormatRuns** を使い、**セルの中の「その文字列だけ」にリンクを張る。**
  本文はそのまま。青字＋下線にして、押せることが分かるようにする。

【何をリンクにするか】
  | 書き方の例 | 飛び先 |
  |---|---|
  | `T032`                    | TODOタブの その行 |
  | `9月_売上/顧客 19行目`       | そのタブの その行 |
  | `12月タブ 行5`              | 12月_売上/顧客 の5行目 |
  | `提携先_休眠度`              | そのタブ |
  | `docs/受注フォーム.md`       | GitHub の そのファイル |
  | `https://…`                | そのまま |

【触らないもの】
  **第1回（1〜32行）と第2回（33〜155行）は過去の打合せ記録。1文字も触らない。**

  python3 tools/link-mtg-sanshou.py            # どこに張るか出すだけ
  python3 tools/link-mtg-sanshou.py --jikkou   # 張る
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
DAI3 = 156
URL = f"https://docs.google.com/spreadsheets/d/{SS}/edit"
GH = "https://github.com/REI-SASAKI-HITOKACHi/one-marketing/blob/claude/one-hitter-cmo-strategy-5qk4ux/"
AO = {"red": 0.10, "green": 0.33, "blue": 0.65}

# TODOタブは 7行目が T001。T0nn の行 = 6 + nn
TODO_GID = 1240265810


def rd(rng):
    o = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "sheets_client.py"),
                        "read", SS, rng], capture_output=True, text=True)
    if o.returncode:
        sys.exit(o.stderr[:300])
    return json.loads(o.stdout or "[]")


def main():
    jikkou = "--jikkou" in sys.argv
    tok = sc.access_token(sc.load_credentials())
    meta = sc.call(tok, f"/{SS}", query={"fields": "sheets.properties(sheetId,title)"})
    gid = {s["properties"]["title"]: s["properties"]["sheetId"] for s in meta["sheets"]}
    sid = gid[TAB]

    def sheet_url(tab, gyo=None):
        g = gid.get(tab)
        if g is None:
            return None
        u = f"{URL}#gid={g}"
        return u + f"&range=A{gyo}" if gyo else u

    # リポジトリにある docs のファイル名を集める（実在するものだけリンクにする）
    aru = set()
    for ne, _, fs in os.walk("docs"):
        for f in fs:
            aru.add(os.path.join(ne, f).replace("\\", "/"))

    rows = rd(f"'{TAB}'!A1:I1000")
    shigoto = []          # (行, 列, [(開始, 長さ, URL, 見えている文字)])
    for gi, r in enumerate(rows, 1):
        if gi < DAI3:
            continue
        for ci, c in enumerate(r):
            s = str(c)
            if not s.strip():
                continue
            ran = []

            # 1. T0xx → TODOタブのその行
            for m in re.finditer(r"T(\d{3})", s):
                n = int(m.group(1))
                ran.append((m.start(), len(m.group(0)),
                            f"{URL}#gid={TODO_GID}&range=A{6 + n}", m.group(0)))

            # 2. 「◯月_売上/顧客 N行目」「◯月_売上/顧客 N行」
            for m in re.finditer(r"(\d{1,2}月_売上/顧客)\s*(\d{1,3})行", s):
                u = sheet_url(m.group(1), m.group(2))
                if u:
                    ran.append((m.start(), len(m.group(0)), u, m.group(0)))

            # 3. 「12月タブ 行5」の形
            for m in re.finditer(r"(\d{1,2})月タブ\s*行\s*(\d{1,3})", s):
                u = sheet_url(f"{m.group(1)}月_売上/顧客", m.group(2))
                if u:
                    ran.append((m.start(), len(m.group(0)), u, m.group(0)))

            # 4. タブ名そのもの（『』や「」で囲まれているものだけ。誤爆を避ける）
            for m in re.finditer(r"[『「]([^』」]{2,24})[』」]", s):
                u = sheet_url(m.group(1))
                if u:
                    ran.append((m.start() + 1, len(m.group(1)), u, m.group(1)))

            # 5. docs/ のファイル（実在するものだけ）
            for m in re.finditer(r"docs/[^\s。、）」』]+\.(?:md|txt)", s):
                if m.group(0) in aru:
                    ran.append((m.start(), len(m.group(0)), GH + m.group(0), m.group(0)))

            # 6. そのまま書いてある URL
            for m in re.finditer(r"https?://[^\s。、）」』]+", s):
                ran.append((m.start(), len(m.group(0)), m.group(0), m.group(0)))

            if not ran:
                continue
            # 重なりを除く（先に見つけたほうを残す）
            ran.sort()
            nokosu, owari = [], -1
            for st, ln, u, mi in ran:
                if st >= owari:
                    nokosu.append((st, ln, u, mi))
                    owari = st + ln
            shigoto.append((gi, ci, nokosu))

    kazu = sum(len(x[2]) for x in shigoto)
    print(f"リンクを張るセル: {len(shigoto)}件 ／ リンク: {kazu}本")
    for gi, ci, ran in shigoto[:14]:
        print(f"  {chr(65+ci)}{gi}: " + "／".join(m for _, _, _, m in ran))
    if len(shigoto) > 14:
        print(f"  …ほか {len(shigoto)-14}セル")

    if not jikkou:
        print("\n（--jikkou を付けていないので張っていません）")
        return

    req = []
    for gi, ci, ran in shigoto:
        s = str(rows[gi - 1][ci])
        # ★セル全体を覆うリンクは textFormatRuns では消える。
        #   Sheets が「セルの書式と同じ」とみなして正規化で落とすため（2026-09-19 実測）。
        #   その場合はセルの書式側（userEnteredFormat.textFormat.link）に入れる。
        if len(ran) == 1 and ran[0][0] == 0 and ran[0][1] == len(s):
            req.append({"repeatCell": {
                "range": {"sheetId": sid, "startRowIndex": gi - 1, "endRowIndex": gi,
                          "startColumnIndex": ci, "endColumnIndex": ci + 1},
                "cell": {"userEnteredFormat": {"textFormat": {
                    "link": {"uri": ran[0][2]}, "underline": True, "foregroundColor": AO}}},
                "fields": "userEnteredFormat.textFormat(link,underline,foregroundColor)"}})
            continue
        runs = []
        ichi = 0
        for st, ln, u, _ in ran:
            if st > ichi:
                runs.append({"startIndex": ichi, "format": {}})
            runs.append({"startIndex": st,
                         "format": {"link": {"uri": u}, "underline": True, "foregroundColor": AO}})
            ichi = st + ln
        if ichi < len(s):
            runs.append({"startIndex": ichi, "format": {}})
        if runs and runs[0]["startIndex"] != 0:
            runs.insert(0, {"startIndex": 0, "format": {}})
        req.append({"updateCells": {
            "range": {"sheetId": sid, "startRowIndex": gi - 1, "endRowIndex": gi,
                      "startColumnIndex": ci, "endColumnIndex": ci + 1},
            "rows": [{"values": [{"userEnteredValue": {"stringValue": s},
                                  "textFormatRuns": runs}]}],
            "fields": "userEnteredValue,textFormatRuns"}})

    for i in range(0, len(req), 100):
        sc.call(tok, f"/{SS}:batchUpdate", method="POST", payload={"requests": req[i:i + 100]})
    print(f"\n✅ 張りました（{len(shigoto)}セル・{kazu}本）。第1回・第2回には触っていません。")


if __name__ == "__main__":
    main()
