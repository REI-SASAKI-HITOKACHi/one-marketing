#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""クラウド環境の環境変数から、~/.config/one-hitter/ の鍵ファイルを作り直す。

【なぜ】
  2026-10-04 昼、CMO のコンテナが作り直されて ~/.config/one-hitter/ が丸ごと消えた。
  LINE・Netlify・スプレッドシート・GBP の道具がすべて止まった（取り込み・朝のLINE・台帳更新）。
  鍵はコンテナの中にしか無かったため。以後は、クラウド環境の設定（環境変数）に置き、
  セッションの起動時にこの道具でファイルへ書き出す（.claude/settings.json の SessionStart）。

【環境変数 → ファイル】（値はリポジトリにも掲示板にも書かない）
  GOOGLE_SHEETS_SA_KEY   → sa-key.json           （サービスアカウントの鍵 JSON そのもの）
  NETLIFY_TOKEN          → netlify-token.txt
  LINE_CHANNEL_TOKEN     → line-token.txt        （業務連絡LINE のボット）
  LINE_GROUP_ID          → line-group-id.txt
  LINE_OFFICIAL_TOKEN    → line-official-token.txt（公式LINE・お客様向け）
  LINE_MEMBERS_JSON      → line-members.json
  GBP_JSON               → gbp.json
  CMS_JSON               → cms.json
  DRIVE_JSON             → drive.json            （写真をドライブへ入れる鍵。T056）

  すでにファイルがあるときは上書きしない（--uwagaki で上書き）。権限は 600。
  何を書いたかは名前だけ出す。値は出さない。

    python3 tools/kagi-fukugen.py
"""
import os
import pathlib
import sys

KAGI = pathlib.Path.home() / ".config" / "one-hitter"
TAIOU = [
    ("GOOGLE_SHEETS_SA_KEY", "sa-key.json"),
    ("NETLIFY_TOKEN", "netlify-token.txt"),
    ("LINE_CHANNEL_TOKEN", "line-token.txt"),
    ("LINE_GROUP_ID", "line-group-id.txt"),
    ("LINE_OFFICIAL_TOKEN", "line-official-token.txt"),
    ("LINE_MEMBERS_JSON", "line-members.json"),
    ("GBP_JSON", "gbp.json"),
    ("CMS_JSON", "cms.json"),
    ("DRIVE_JSON", "drive.json"),
]


def main() -> None:
    uwagaki = "--uwagaki" in sys.argv
    KAGI.mkdir(parents=True, exist_ok=True)
    os.chmod(KAGI, 0o700)
    kaita, nai = [], []
    for env, na in TAIOU:
        v = os.environ.get(env, "").strip()
        f = KAGI / na
        if not v:
            if not f.exists():
                nai.append(env)
            continue
        if f.exists() and not uwagaki:
            continue
        f.write_text(v + ("" if na.endswith(".json") else "\n"), encoding="utf-8")
        os.chmod(f, 0o600)
        kaita.append(na)
    if kaita:
        print("鍵を置きました: " + "、".join(kaita))
    if nai:
        print("鍵がありません（クラウド環境の環境変数に登録が要る）: " + "、".join(nai))


if __name__ == "__main__":
    main()
