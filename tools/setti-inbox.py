#!/usr/bin/env python3
"""「カードを置きます」の連絡（承諾フォーム）を、進捗タブに下ろす。

なぜ要るか（2026-09-18）：
  読本の承諾フォーム（`dokuhon.onehitter.jp/setti/` ＝ Netlify の `dokuhon-setti`）は、
  施設IDの発行まで自分でやって送信してくる。**が、その結果を進捗タブに書く仕組みが無かった。**
  置いてくれた先が来ても誰も気づかず、記録にも残らない状態だった。

  CMO決定（2026-09-17）：「読本の設置のお願いだけを先に出す。置いてくれた先だけに、後から清掃の
  打診をする」。そのため **「読本を置いてくれた先」が後から数えられること** が要件になった。
  この道具が、その分母をスプレッドシートに作る。

使い方:
  python3 tools/setti-inbox.py --dry-run   # 届いているものを見るだけ（何も書かない）
  python3 tools/setti-inbox.py             # 進捗タブに下ろす

**施設名が一致しないものは、勝手に当てはめない。**「要手動照合」として出すだけにする
（カードが人づてに回って、291件のリストに無い施設から届くことがあり得るため）。
"""
import argparse
import datetime as dt
import difflib
import json
import os
import pathlib
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import sheets_client as sc  # noqa: E402

SS = "1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64"
TAB = "施設カード_進捗"
HEAD_ROW = 13
FORM_ID = "6aa3f82d0cfdb9000847ff7f"  # one-hitter-dokuhon / dokuhon-setti
TOKEN_FILE = os.path.expanduser("~/.config/one-hitter/netlify-token.txt")
STATE = ROOT / "data" / "setti-torikomi.json"
JST = ZoneInfo("Asia/Tokyo")
SCOPE = "https://www.googleapis.com/auth/spreadsheets"
NIRU = 0.82  # 施設名がこれ以上似ていれば同じ施設とみなす


def netlify(path: str):
    tok = os.environ.get("NETLIFY_TOKEN", "").strip()
    if not tok and os.path.exists(TOKEN_FILE):
        tok = open(TOKEN_FILE, encoding="utf-8").read().strip()
    if not tok:
        sys.exit("Netlify のトークンがありません（~/.config/one-hitter/netlify-token.txt）")
    req = urllib.request.Request("https://api.netlify.com/api/v1" + path)
    req.add_header("Authorization", "Bearer " + tok)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def norm(s: str) -> str:
    """施設名の突き合わせ用。全角半角・括弧・記号・空白の違いを落とす。"""
    s = unicodedata.normalize("NFKC", s or "")
    s = re.sub(r"[\[【（(].*?[\]】）)]", "", s)
    s = re.split(r"[|｜/／]", s)[0]
    s = re.sub(r"(株式会社|有限会社|合同会社|㈱|㈲)", "", s)
    return re.sub(r"[\s\-‐―ー・,、.。'\"’”]", "", s).lower()


def colletter(i: int) -> str:
    s, i = "", i + 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    subs = netlify(f"/forms/{FORM_ID}/submissions")
    done = set(json.loads(STATE.read_text(encoding="utf-8"))) if STATE.exists() else set()
    new = [s for s in subs if s.get("id") not in done]
    print(f"承諾フォームの届きぶん {len(subs)} 件（うち未取り込み {len(new)} 件）")
    if not new:
        return 0

    tok = sc.access_token(sc.load_credentials(), SCOPE)
    rng = f"{TAB}!A{HEAD_ROW}:AF1000"
    vals = sc.call(tok, f"/{SS}/values/{urllib.parse.quote(rng)}").get("values", [])
    head = vals[0]
    ci = {h: i for i, h in enumerate(head)}
    rows = [(n, r + [""] * (len(head) - len(r))) for n, r in enumerate(vals[1:], start=HEAD_ROW + 1)]
    index = {norm(r[ci["施設名"]]): (n, r) for n, r in rows if r[ci["施設名"]]}

    today = dt.datetime.now(JST).strftime("%Y-%m-%d")
    data, took, manual = [], [], []
    for s in new:
        d = s.get("data") or {}
        name = (d.get("施設名") or "").strip()
        key = norm(name)
        hit = index.get(key)
        if not hit:                      # 表記ゆれ。似ているものを探す
            cand = difflib.get_close_matches(key, list(index), n=1, cutoff=NIRU)
            hit = index.get(cand[0]) if cand else None
        if not hit:
            manual.append((name, d.get("施設ID", ""), d.get("メール", "")))
            continue
        n, r = hit
        upd = {"ステージ": "設置OK", "設置日": today, "設置場所": d.get("設置場所", ""),
               "施設ID": d.get("施設ID", ""), "カード": d.get("カード", ""),
               "先方担当者": d.get("担当者", ""), "反応": "好感触（承諾フォームから設置の連絡）",
               "次回アクション": "カードを送る", "次回予定日": today}
        for k, v in upd.items():
            if k in ci and v != "":
                data.append({"range": f"{TAB}!{colletter(ci[k])}{n}", "values": [[v]]})
        took.append((r[ci["No"]], r[ci["施設名"]], d.get("施設ID", ""), d.get("設置場所", "")))

    for no, nm, fid, place in took:
        print(f"  設置OK  No.{no} {nm[:32]}  施設ID={fid}  置き場所={place}")
    for nm, fid, mail in manual:
        print(f"  ★要手動照合  「{nm}」  施設ID={fid}  （リストに一致する施設名が無い）")

    if a.dry_run:
        print("\n--dry-run なので、何も書いていません")
        return 0
    if data:
        for k in range(0, len(data), 100):
            sc.call(tok, f"/{SS}/values:batchUpdate", method="POST",
                    payload={"valueInputOption": "USER_ENTERED", "data": data[k:k + 100]})
        print(f"\n進捗タブを更新しました（{len(took)}施設）")
    # 手動照合ぶんも「見た」ことにして二重に出さない。人が片付ける前提で、名前は上に出してある
    STATE.write_text(json.dumps(sorted(done | {s["id"] for s in new}), ensure_ascii=False), encoding="utf-8")
    if manual:
        print(f"★ {len(manual)}件は自動で当てはめていません。掲示板で cmo に上げてください")
    return 0


if __name__ == "__main__":
    sys.exit(main())
