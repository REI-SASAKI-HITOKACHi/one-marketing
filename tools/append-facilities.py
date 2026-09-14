#!/usr/bin/env python3
"""新しく集めた施設を、売上スプシ「施設カード_進捗」に足す。

オーナー決定 2026-09-14：「対象リストもどんどん追加が必要だよ」。
足すのは **連絡が取れる見込みのあるものだけ**（検証済みのフォームがある／公開メールがある）。
連絡手段が無いものはスプシを膨らませるだけなので data/ のファイルに残し、電話・訪問の候補として置いておく。

優先度：A＝犬猫・赤ちゃんの節目に近い業種で、フォームがあるもの／B＝メールだけ／C＝公的・営業お断り
既存の行は一切触らない（過去の実績は書き換えない）。No は最後の続きから振る。

使い方:
  python3 tools/append-facilities.py --dry     # 何件足すか数えるだけ
  python3 tools/append-facilities.py
"""
import argparse
import json
import pathlib
import re
import sys
import urllib.parse

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sheets_client as sc  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
ADD = ROOT / "data" / "facilities-2026-09-add.json"
CON = ROOT / "data" / "facilities-2026-09-add-contacts.json"
SS = "1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64"
TAB = "施設カード_進捗"
HEAD_ROW = 13
DOKUHON = {"産婦人科・産院": "赤ちゃん版", "小児科": "赤ちゃん版", "ベビー用品店": "赤ちゃん版", "子育て支援（公的）": "赤ちゃん版"}
NOT_DOGCAT_RE = re.compile(r"熱帯魚|アクア|サンマリン|ディスカス|金魚|メダカ|水族")
HOUJIN_RE = re.compile(r"医療法人|社会福祉法人|学校法人|特定非営利|NPO|区立|市立|都立|県立|国立")


def priority(f: dict, c: dict) -> str:
    if f["種別"] == "子育て支援（公的）" or c.get("no_sales"):
        return "C"
    if c.get("has_form") and not c.get("captcha"):
        return "A"
    return "B"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    fac = {f["id"]: f for f in json.loads(ADD.read_text(encoding="utf-8"))}
    con = {c["id"]: c for c in json.loads(CON.read_text(encoding="utf-8"))}

    tok = sc.access_token(sc.load_credentials())
    head = sc.call(tok, f"/{SS}/values/{urllib.parse.quote(TAB + '!A' + str(HEAD_ROW) + ':AM' + str(HEAD_ROW))}").get("values", [[]])[0]
    vals = sc.call(tok, f"/{SS}/values/{urllib.parse.quote(TAB + '!A' + str(HEAD_ROW) + ':D1500')}").get("values", [])
    have = {r[3] for r in vals[1:] if len(r) > 3}
    last_no = max((int(r[0]) for r in vals[1:] if r and r[0].isdigit()), default=0)
    start_row = HEAD_ROW + len(vals)

    rows = []
    no = last_no
    for fid, f in fac.items():
        c = con.get(fid)
        if not c or f["施設名"] in have:
            continue
        if not (c.get("has_form") or c.get("emails")):
            continue  # 連絡手段が無いものは足さない
        if f["種別"] == "ペットショップ" and NOT_DOGCAT_RE.search(f["施設名"]):
            continue  # 観賞魚の店は犬猫の読本が合わない
        no += 1
        r = [""] * len(head)
        col = {h: i for i, h in enumerate(head)}
        r[col["No"]] = no
        r[col["優先度"]] = priority(f, c)
        r[col["種別"]] = f["種別"]
        r[col["施設名"]] = f["施設名"]
        r[col["市区"]] = f.get("市区", "")
        r[col["エリア"]] = f.get("エリア", "")
        r[col["住所"]] = f.get("住所", "")
        r[col["電話"]] = f.get("電話", "")
        r[col["サイト"]] = f.get("サイト", "")
        r[col["読本"]] = DOKUHON.get(f["種別"], "ペット版")
        r[col["報酬型（仮）"]] = "報酬なし型" if (HOUJIN_RE.search(f["施設名"]) or f["種別"] == "子育て支援（公的）") else "12%型"
        r[col["ステージ"]] = "未接触"
        r[col["接触回数"]] = 0
        r[col["次回アクション"]] = "第2波で送信" if c.get("has_form") and not c.get("captcha") else ("手動（画像認証）→ブラウザ担当" if c.get("captcha") else "メールで送信")
        r[col["Googleクチコミ数"]] = f.get("クチコミ数", 0)
        r[col["当社担当"]] = "web-inflow"
        r[col["メモ"]] = f"2026-09-14 追加（{f.get('検索語','')}）"
        rows.append(r)

    import collections
    print(f"足す {len(rows)} 件（No {last_no + 1}〜{no}）", collections.Counter(r[1] for r in rows), collections.Counter(r[2] for r in rows))
    if a.dry or not rows:
        return
    rng = f"{TAB}!A{start_row}"
    sc.call(tok, f"/{SS}/values/{urllib.parse.quote(rng)}:append", method="POST",
            query={"valueInputOption": "USER_ENTERED", "insertDataOption": "INSERT_ROWS"}, payload={"values": rows})
    print("追記しました:", rng)


if __name__ == "__main__":
    main()
