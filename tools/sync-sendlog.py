#!/usr/bin/env python3
"""送信ログ用 Google フォームの回答を、売上スプシ「施設カード_送信ログ」タブへ流す。

オーナー指示 2026-09-14：「記録はアクセスなしでできる仕組みに」。
　送信ツール → フォームに HTTPS で投げる（認証なし・API の枠を使わない・失敗しない）
　このツール   → 溜まった回答をまとめてスプシに1回で書く（1日1回か、送信の区切りで）
　人が手で入れる分（電話・訪問・Instagram DM）も同じフォームから入れられる。

すでに書いた回答は data/sendlog-synced.json に控えて二重に書かない。

使い方:
  python3 tools/sync-sendlog.py          # 新しい回答をスプシに足す
  python3 tools/sync-sendlog.py --dry    # 何件あるか見るだけ
"""
import argparse
import json
import os
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sheets_client as sc  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
CFG = os.path.expanduser("~/.config/one-hitter/sendlog-form.json")
STATE = ROOT / "data" / "sendlog-synced.json"
SS = "1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64"
TAB = "施設カード_送信ログ"
FIELDS = ["日時", "波", "施設No", "施設名", "種別", "手段", "宛先／フォームURL", "文面の型", "送信者", "結果", "返信", "施設ID", "備考"]
SCOPE = "https://www.googleapis.com/auth/forms.responses.readonly https://www.googleapis.com/auth/spreadsheets"


def responses(tok: str, fid: str) -> list:
    out, page = [], ""
    while True:
        url = f"https://forms.googleapis.com/v1/forms/{fid}/responses" + (f"?pageToken={page}" if page else "")
        req = urllib.request.Request(url, headers={"Authorization": "Bearer " + tok})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                d = json.load(r)
        except urllib.error.HTTPError as e:
            sys.exit(f"Forms API {e.code}: {e.read().decode('utf-8', 'replace')[:300]}")
        out += d.get("responses", [])
        page = d.get("nextPageToken", "")
        if not page:
            break
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    cfg = json.load(open(CFG, encoding="utf-8"))
    qid = {q: name for name, q in cfg["questions"].items()}  # 設問ID → 列名
    tok = sc.access_token(sc.load_credentials(), SCOPE)
    done = set(json.loads(STATE.read_text(encoding="utf-8"))) if STATE.exists() else set()
    rows, ids = [], []
    for r in sorted(responses(tok, cfg["formId"]), key=lambda x: x.get("createTime", "")):
        rid = r.get("responseId")
        if rid in done:
            continue
        vals = {}
        for q, ans in (r.get("answers") or {}).items():
            name = qid.get(q)
            if not name:
                continue
            vals[name] = (ans.get("textAnswers", {}).get("answers") or [{}])[0].get("value", "")
        if vals.get("結果") == "テスト":
            ids.append(rid)  # 動作確認の行はスプシに書かない
            continue
        rows.append([vals.get(k, "") for k in FIELDS])
        ids.append(rid)
    print(f"新しい回答 {len(rows)} 件（控え済み {len(done)}）")
    if a.dry or not rows:
        if not a.dry and ids:
            STATE.write_text(json.dumps(sorted(done | set(ids)), ensure_ascii=False), encoding="utf-8")
        return
    sc.call(tok, f"/{SS}/values/{urllib.parse.quote(TAB + '!A1')}:append", method="POST",
            query={"valueInputOption": "USER_ENTERED", "insertDataOption": "INSERT_ROWS"}, payload={"values": rows})
    STATE.write_text(json.dumps(sorted(done | set(ids)), ensure_ascii=False), encoding="utf-8")
    print("スプシに書きました:", len(rows), "行")


if __name__ == "__main__":
    main()
