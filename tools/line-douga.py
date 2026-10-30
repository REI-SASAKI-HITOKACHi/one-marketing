#!/usr/bin/env python3
"""業務連絡LINEに届いた動画・画像を、LINE_ログの行番号で落とす。

使い方:
  python3 tools/line-douga.py <開始行> <終了行> [保存先ディレクトリ]
  例) python3 tools/line-douga.py 367 386 ~/.cache/one-hitter/line-video/2026-10-19

LINE_ログ タブの I列（Webhook の生JSON）から message.id を取り、
https://api-data.line.me/v2/bot/message/{id}/content で実体を取る。
LINE側の保存期間は短い（数日〜）ので、届いた日のうちに落とすこと。
動画は大きい（1本で数十MB）ので、リポジトリには入れない。SNSに使うものだけ dist/ へ。
"""
import json
import os
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sheets_client as sc  # noqa: E402
import line_client as lc  # noqa: E402

SS = "1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64"
KAKUCHOSHI = {"video/mp4": ".mp4", "image/jpeg": ".jpg", "image/png": ".png"}


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    a, b = int(sys.argv[1]), int(sys.argv[2])
    out = os.path.expanduser(sys.argv[3] if len(sys.argv) > 3 else "~/.cache/one-hitter/line-media")
    os.makedirs(out, exist_ok=True)
    tok = sc.access_token(sc.load_credentials())
    rng = urllib.parse.quote(f"'LINE_ログ'!A{a}:I{b}", safe="")
    rows = sc.call(tok, f"/{SS}/values/{rng}").get("values", [])
    lt = lc.token()
    for i, row in enumerate(rows):
        n = a + i
        try:
            m = json.loads(row[8]).get("message", {})
        except Exception:
            print(n, "I列にJSONがありません")
            continue
        if m.get("type") not in ("video", "image"):
            continue
        req = urllib.request.Request(f"https://api-data.line.me/v2/bot/message/{m['id']}/content",
                                     headers={"Authorization": f"Bearer {lt}"})
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                data, ct = r.read(), r.headers.get("Content-Type", "")
        except Exception as e:
            print(n, m["id"], "取得できません", e)
            continue
        p = os.path.join(out, f"{n}_{m['id']}{KAKUCHOSHI.get(ct, '')}")
        with open(p, "wb") as f:
            f.write(data)
        sec = f"{m['duration'] / 1000:.0f}秒" if m.get("duration") else ""
        print(n, ct, f"{len(data) // 1024}KB", sec, p)


if __name__ == "__main__":
    main()
