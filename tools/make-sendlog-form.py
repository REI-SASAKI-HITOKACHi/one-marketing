#!/usr/bin/env python3
"""施設カードの送信記録用 Google フォームを作る（オーナー指示 2026-09-14：「記録は Google フォームを活用して、アクセスなしでできる仕組みに」）。

仕組み：
  送信ツール（shisetsu-outreach.py）は、このフォームの formResponse に HTTPS で投げるだけ。認証も Sheets API の枠も要らない。
  フォームの回答は売上スプシに落ちる（回答先の紐づけは Forms API ではできないので、フォーム画面で1回だけ：
  回答 → スプレッドシートにリンク → 既存のスプレッドシートを選択 → 「2026_売上/顧客情報管理」。ブラウザ担当かオーナー）。

手順:
  1. GCP one-hitter-sheets で Google Forms API を有効化（1クリック。ブラウザ担当）
  2. python3 tools/make-sendlog-form.py create      # SA でフォームを作り、オーナーに編集権限を付け、設問→entry ID を ~/.config/one-hitter/sendlog-form.json に保存
  3. フォーム画面で回答先を売上スプシに紐づける
  4. python3 tools/make-sendlog-form.py test        # 1件テスト投稿（備考に「テスト」）
"""
import json
import os
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sheets_client as sc  # noqa: E402

CFG = os.path.expanduser("~/.config/one-hitter/sendlog-form.json")
FORMS = "https://forms.googleapis.com/v1/forms"
DRIVE = "https://www.googleapis.com/drive/v3/files"
SCOPE = "https://www.googleapis.com/auth/forms.body https://www.googleapis.com/auth/drive"
OWNER = "case.foot.kid@gmail.com"
TITLE = "施設カード_送信ログ（自動記録）"
# 売上スプシ「施設カード_送信ログ」タブと同じ列順
FIELDS = ["日時", "波", "施設No", "施設名", "種別", "手段", "宛先／フォームURL", "文面の型", "送信者", "結果", "返信", "施設ID", "備考"]


def call(tok, url, method="GET", payload=None):
    req = urllib.request.Request(url, data=json.dumps(payload).encode() if payload is not None else None, method=method,
                                 headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code} {url}\n{e.read().decode('utf-8', 'replace')[:800]}")


def create():
    tok = sc.access_token(sc.load_credentials(), SCOPE)
    form = call(tok, FORMS, "POST", {"info": {"title": TITLE, "documentTitle": TITLE}})
    fid = form["formId"]
    reqs = [{"createItem": {"item": {"title": name, "questionItem": {"question": {"required": name in ("日時", "施設名", "手段", "結果"), "textQuestion": {"paragraph": name in ("宛先／フォームURL", "備考", "返信")}}}},
                            "location": {"index": i}}} for i, name in enumerate(FIELDS)]
    reqs.insert(0, {"updateFormInfo": {"info": {"description": "送信ツールが自動で投稿する。人が手で入れるときは、手段に「電話」「訪問」「Instagram DM」と書く。"}, "updateMask": "description"}})
    call(tok, f"{FORMS}/{fid}:batchUpdate", "POST", {"requests": reqs})
    form = call(tok, f"{FORMS}/{fid}")
    entries = {}
    for it in form.get("items", []):
        q = it.get("questionItem", {}).get("question", {})
        if q.get("questionId"):
            entries[it["title"]] = "entry." + str(int(q["questionId"], 16))
    missing = [f for f in FIELDS if f not in entries]
    if missing:
        sys.exit(f"entry ID が取れない設問: {missing}")
    # オーナーに編集権限（回答先の紐づけと、回答の閲覧のため）
    call(tok, f"{DRIVE}/{fid}/permissions?sendNotificationEmail=false", "POST", {"role": "writer", "type": "user", "emailAddress": OWNER})
    post_url = form["responderUri"].replace("/viewform", "/formResponse")
    os.makedirs(os.path.dirname(CFG), exist_ok=True)
    json.dump({"formId": fid, "post_url": post_url, "edit_url": f"https://docs.google.com/forms/d/{fid}/edit", "entries": entries}, open(CFG, "w"), ensure_ascii=False, indent=1)
    print("作成:", TITLE)
    print("編集URL（回答先の紐づけはここで）:", f"https://docs.google.com/forms/d/{fid}/edit")
    print("投稿URL:", post_url)
    print("設定を保存:", CFG)


def post(values: dict) -> bool:
    """values: {列名: 値}。認証なしで formResponse に投げる。成功なら True"""
    cfg = json.load(open(CFG, encoding="utf-8"))
    data = {cfg["entries"][k]: str(v) for k, v in values.items() if k in cfg["entries"]}
    req = urllib.request.Request(cfg["post_url"], data=urllib.parse.urlencode(data).encode(), method="POST",
                                 headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status == 200


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "create":
        create()
    elif mode == "test":
        import datetime as dt
        ok = post({"日時": dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M"), "波": 0, "施設No": 0, "施設名": "テスト", "種別": "-", "手段": "テスト",
                   "宛先／フォームURL": "-", "文面の型": "-", "送信者": "web-inflow", "結果": "テスト", "備考": "動作確認。消してよい"})
        print("テスト投稿:", "OK" if ok else "失敗")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
