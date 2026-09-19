#!/usr/bin/env python3
"""アンケートの回答が本当に届いているかを、Netlify の実データで数える。

同じ問いを何度も人づてでやり取りしないための道具。**誰が走らせても同じ数字が出る。**

  NETLIFY_TOKEN=nfp_xxx python3 tools/check-survey-inbox.py
  NETLIFY_TOKEN=nfp_xxx python3 tools/check-survey-inbox.py --from 2026-09-05 --to 2026-09-19

見るもの
  ・通常の受信箱（?state=ham）
  ・迷惑判定の箱（?state=spam）      ← ここを見落とすと「0件だから壊れている」と誤る
  ・アカウント内の全サイト            ← 別サイトに溜まっていないか

予約フォームで「受け口は生きているのに迷惑判定で見えていなかった」前例がある
（docs/予約フォーム-受け口は生きている-迷惑判定の穴.md）。両方数えること。
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

API = "https://api.netlify.com/api/v1"
SITE = "one-hitter-lp.netlify.app"
FORM = "survey"


def call(path: str, token: str):
    req = urllib.request.Request(API + path, headers={"Authorization": "Bearer " + token})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return {"_error": f"{e.code} {e.reason}"}
    except Exception as e:  # ネットワーク断など
        return {"_error": str(e)}


def hiduke(s: str) -> str:
    return (s or "")[:10]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="kara", default="")
    ap.add_argument("--to", dest="made", default="")
    ap.add_argument("--site", default=SITE)
    ap.add_argument("--form", default=FORM)
    a = ap.parse_args()

    token = os.environ.get("NETLIFY_TOKEN", "").strip()
    if not token:
        sys.exit("環境変数 NETLIFY_TOKEN が空です。引数にもファイルにも書かないこと。")

    forms = call(f"/sites/{a.site}/forms", token)
    if isinstance(forms, dict) and forms.get("_error"):
        sys.exit("フォーム一覧を取れません: " + forms["_error"])

    mato = [f for f in forms if f.get("name") == a.form]
    if not mato:
        print(f"× {a.site} に「{a.form}」というフォームがありません。")
        print("  名前が変わったか、配信物からフォームの記述が落ちています。")
        return 1
    form = mato[0]
    print(f"フォーム: {form['name']}  id={form['id']}  作成={form.get('created_at','')[:19]}")
    print(f"  Netlify が数えている件数: {form.get('submission_count')}")
    print()

    kikan = ""
    if a.kara or a.made:
        kikan = f"（{a.kara or '最初'} 〜 {a.made or '最後'}）"

    gokei = {}
    for state in ("ham", "spam"):
        rows = call(f"/forms/{form['id']}/submissions?state={state}&per_page=200", token)
        if isinstance(rows, dict):
            print(f"  {state}: 取得できません {rows.get('_error')}")
            continue
        if a.kara:
            rows = [r for r in rows if hiduke(r.get("created_at")) >= a.kara]
        if a.made:
            rows = [r for r in rows if hiduke(r.get("created_at")) <= a.made]
        gokei[state] = rows
        namae = "通常の受信箱" if state == "ham" else "迷惑判定の箱"
        print(f"{namae}（?state={state}）{kikan}: {len(rows)} 件")
        for r in rows:
            ua = ((r.get("data") or {}).get("user_agent") or "")[:46]
            print(f"   {r.get('created_at')}  {r.get('id')}  {ua}")
        print()

    ha = len(gokei.get("ham", []))
    sp = len(gokei.get("spam", []))
    print("=" * 56)
    print(f"通常 {ha} 件 ／ 迷惑 {sp} 件 ／ 合計 {ha + sp} 件")
    if ha + sp == 0:
        print("→ 受信そのものが0件。フォームの送信先が生きているかを疑うこと。")
        print("   確かめ方: curl -sS https://lp.onehitter.jp/survey/ | grep -o '<form[^>]*>'")
        print("   action と name が入っていなければ、回答は保存されない。")
    elif sp and not ha:
        print("→ 受信はあるが全部が迷惑判定。受け口は生きている。判定のほうを疑うこと。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
