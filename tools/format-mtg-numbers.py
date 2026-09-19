#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MTGシートの数値に表示書式（￥・％・3桁区切り）を当てる。値は1つも書き換えない。

【オーナー指示（原文）】
  2026-09-19
  「MTG数値に入力してある数値の単位とカンマ（3桁区切り）を付けて。￥とか％とか」

【使い方】
  python3 tools/format-mtg-numbers.py            # 当てる対象を一覧で出すだけ
  python3 tools/format-mtg-numbers.py --jikkou   # 当てる（当てたあと値を突き合わせて確認する）

【いちばん大事なこと】
  セルの値は1つも書き換えない。repeatCell の userEnteredFormat.numberFormat だけを当てる。
  fields をそこに限定しているので、format-mtg-sheet.py が当てた
  背景色・折り返し・太字・結合・プルダウンは壊れない。

【どうやって振り分けているか】
  値だけを見ると 0.945 が「割合」なのか「0.9件」なのか分からない。
  そこで **表の見出し行（列の見出し）を機械で見つけて、その列の意味で振り分けている。**
    1. 「全部が文字」「2つ以上に中身がある」「次の中身のある行に数値がある」行を見出し行とみなす
    2. 見出し行の直後から、空行・区切り（━ ■ → ★ ※ 【）まで下をデータ行とみなす
    3. 列の見出しの文字で 金額／割合／件数 に振り分ける
    4. どれにも当てはまらない列の数値は **触らない**（例：「No.」列の連番）

  見出しが分からない列を触らないのは、間違った書式を当てるより素のままのほうがましだから。
  （このシートの「No.」列は 1〜25 の連番で、3桁区切りを当てても見た目が変わらない）

【注意】
  第1回（7行目〜）・第2回（35行目〜）は過去の打合せ記録。値は絶対に書き換えない。書式だけ当てる。
  第3回の一部のセルは頭に ' を付けた **文字** として入っている（'9/08 '28,160 '80.2% など）。
  文字のセルに数値書式は効かない。効かないだけで害は無いので、無理に数値へ戻さない。
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sheets_client as sc

SS = "1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64"
TAB = "MTGシート"
HANI = f"'{TAB}'!A1:I300"

# ---------------------------------------------------------------- 書式の3種類
SHOSHIKI = {
    "金額": {"type": "CURRENCY", "pattern": '"¥"#,##0'},   # ¥1,120,607
    "割合": {"type": "PERCENT", "pattern": "0.0%"},        # 94.5%
    "件数": {"type": "NUMBER", "pattern": "#,##0"},        # 1,005
}

# ---------------------------------------------------------- 列の見出しの振り分け
# ① まず「この見出しはこれ」と名指しで決める。
#    キーワードでは拾えない（拾うと他の列まで巻き込む）見出しをここに書く。
MIDASHI_MEIJI = {
    "うち早期予約（現場での次回予約）": "金額",  # 「予約」なので金額の語が入っていない。中身は受注額
    "今朝の台帳": "金額",                       # 9/19 時点の受注額
    "補った後": "金額",                         # 台帳に入れ直したあとの受注額
    "対象月数": "件数",                         # 何か月分かの月数。金額ではない
    "件数": "件数",
    "数量": "件数",
}

# ② 名指しに無ければ、見出しに含まれる語で決める。
#    「割合」を先に見る（達成率・前年比が金額の語とぶつからないよう、語は絞ってある）。
WARIAI_GO = ("達成率", "割合", "率", "比")
KINGAKU_GO = ("売上", "金額", "予算", "実績", "受注", "利益", "給与", "報酬",
              "単価", "差", "累計", "販売管理費", "経費")
KENSU_GO = ("件数", "日数", "月数", "回数", "通数", "人数", "台数", "文字数", "数量")

KUGIRI_ATAMA = ("━", "■", "→", "★", "※", "【")


def hanbetsu(midashi: str):
    """列の見出しから 金額／割合／件数 を決める。決められなければ None（＝触らない）。"""
    m = midashi.strip()
    if not m:
        return None
    if m in MIDASHI_MEIJI:
        return MIDASHI_MEIJI[m]
    if any(g in m for g in WARIAI_GO):
        return "割合"
    if any(g in m for g in KENSU_GO):
        return "件数"
    if any(g in m for g in KINGAKU_GO):
        return "金額"
    return None


def suuji(c):
    """セルが数値かどうか。真偽値は数値として扱わない。"""
    return isinstance(c, (int, float)) and not isinstance(c, bool)


def kara(r):
    return not any(str(c).strip() for c in r)


def kugiri(r):
    a = str(r[0]).strip() if r else ""
    return kara(r) or a.startswith(KUGIRI_ATAMA)


def retsu(j):
    return chr(ord("A") + j)


def midashi_gyo(rows, i):
    """i行目（0起点）が表の見出し行かどうか。"""
    r = rows[i]
    if kugiri(r):
        return False
    if any(suuji(c) for c in r):
        return False
    if len([c for c in r if str(c).strip()]) < 2:
        return False
    # 次の「中身のある行」に数値があるなら、この行は数値表の見出しとみなす
    for k in range(i + 1, min(i + 4, len(rows))):
        if kara(rows[k]):
            continue
        return any(suuji(c) for c in rows[k])
    return False


def main():
    jikkou = "--jikkou" in sys.argv
    tok = sc.access_token(sc.load_credentials())
    meta = sc.call(tok, f"/{SS}", query={"fields": "sheets.properties"})
    sid = next((s["properties"]["sheetId"] for s in meta["sheets"]
                if s["properties"]["title"] == TAB), None)
    if sid is None:
        sys.exit(f"{TAB} タブがありません。")

    rows = yomu()
    n = len(rows)

    ateru = []      # (行0起点, 列0起点, 種類, 値, 見出し)
    minogashi = []  # 触らなかった数値セル（行0起点, 列, 値, 理由）

    i = 0
    while i < n:
        if not midashi_gyo(rows, i):
            i += 1
            continue
        midashi = [str(c).strip() for c in rows[i]]
        shurui = [hanbetsu(m) for m in midashi]
        j = i + 1
        while j < n and not kugiri(rows[j]) and not midashi_gyo(rows, j):
            for k, c in enumerate(rows[j]):
                if not suuji(c):
                    continue
                s = shurui[k] if k < len(shurui) else None
                mi = midashi[k] if k < len(midashi) else ""
                if s is None:
                    minogashi.append((j, k, c, f"列の見出し「{mi or '（空）'}」からは種類を決められない"))
                    continue
                # 値での安全弁：見出しと中身が食い違うときは触らない
                if s == "割合" and not (0 <= c <= 1):
                    minogashi.append((j, k, c, f"「{mi}」列だが 0〜1 の小数ではない"))
                    continue
                if s in ("金額", "件数") and 0 < abs(c) < 1:
                    minogashi.append((j, k, c, f"「{mi}」列だが 0〜1 の小数。割合の可能性があり判断できない"))
                    continue
                ateru.append((j, k, s, c, mi))
            j += 1
        i = j

    # ---- 当てる内容を出す（--jikkou が無ければここで終わり）
    print(f"対象: {TAB}（{n}行 読み込み）")
    print(f"\n■ 当てるセル {len(ateru)}件")
    for gyo, ret, s, v, mi in ateru:
        print(f"  {retsu(ret)}{gyo + 1:<4} {s}  {v!r:<22} 列の見出し:{mi}")
    uchiwake = {k: sum(1 for a in ateru if a[2] == k) for k in SHOSHIKI}
    print("  内訳: " + " / ".join(f"{k} {v}件" for k, v in uchiwake.items()))

    print(f"\n■ 触らない数値セル {len(minogashi)}件")
    matome = {}
    for gyo, ret, v, riyuu in minogashi:
        matome.setdefault(riyuu, []).append(f"{retsu(ret)}{gyo + 1}")
    for riyuu, cells in matome.items():
        print(f"  {riyuu}: {len(cells)}件  {' '.join(cells[:30])}"
              + (" …" if len(cells) > 30 else ""))

    if not ateru:
        print("\n当てるものがありません。")
        return

    # ---- リクエストを作る（同じ列の連続する行はまとめる）
    req = []
    ateru.sort(key=lambda a: (a[1], a[2], a[0]))
    hajime = None
    for idx, a in enumerate(ateru):
        tsugi = ateru[idx + 1] if idx + 1 < len(ateru) else None
        if hajime is None:
            hajime = a
        tsuzuki = (tsugi and tsugi[1] == a[1] and tsugi[2] == a[2] and tsugi[0] == a[0] + 1)
        if not tsuzuki:
            req.append({"repeatCell": {
                "range": {"sheetId": sid,
                          "startRowIndex": hajime[0], "endRowIndex": a[0] + 1,
                          "startColumnIndex": a[1], "endColumnIndex": a[1] + 1},
                "cell": {"userEnteredFormat": {"numberFormat": SHOSHIKI[a[2]]}},
                # ★ここを numberFormat に限定しているので、色・折り返し・結合は壊れない
                "fields": "userEnteredFormat.numberFormat"}})
            hajime = None
    print(f"\n■ リクエスト数: {len(req)}")

    if not jikkou:
        print("\n（--jikkou を付けていないので当てていません）")
        return

    sc.call(tok, f"/{SS}:batchUpdate", method="POST", payload={"requests": req})
    print("\n✅ 当てました。")

    # ---- 当てたあと、値が1つも変わっていないことを突き合わせる
    ato = yomu()
    chigai = []
    for gyo in range(max(len(rows), len(ato))):
        a = rows[gyo] if gyo < len(rows) else []
        b = ato[gyo] if gyo < len(ato) else []
        for ret in range(max(len(a), len(b))):
            x = a[ret] if ret < len(a) else ""
            y = b[ret] if ret < len(b) else ""
            if x != y:
                chigai.append(f"{retsu(ret)}{gyo + 1}: {x!r} → {y!r}")
    if chigai:
        print(f"\n🔴 値が変わったセルがあります（{len(chigai)}件）。確認してください。")
        for c in chigai[:50]:
            print("   " + c)
    else:
        print("✅ 突き合わせ完了：値は1つも変わっていません"
              f"（{sum(len(r) for r in rows)}セルを比較）。")


def yomu():
    """UNFORMATTED_VALUE で読む。数値は数値、文字は文字のまま返ってくる。"""
    o = subprocess.run([sys.executable,
                        os.path.join(os.path.dirname(os.path.abspath(__file__)), "sheets_client.py"),
                        "read", SS, HANI], capture_output=True, text=True)
    if o.returncode:
        sys.exit(o.stderr[:400])
    return json.loads(o.stdout or "[]")


if __name__ == "__main__":
    main()
