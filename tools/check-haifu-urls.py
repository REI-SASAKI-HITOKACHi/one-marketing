#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""配ったURLが生きているかを確かめる（毎時のルーティン ■0 で実行）。

【なぜ】2026-09-26 に、和真さんの手元の受注フォームのリンク（9/22 に一度配った旧ホスト）が
404 になっていた。ホストを消したのに、渡した相手のブックマークは消えない。
一度渡したURLは data/haifu-urls.json に登録し、ここで毎時 200/301 を確かめる。

  python3 tools/check-haifu-urls.py          # 全件確認。死んでいれば ⚠ を出して終了コード 1
  python3 tools/check-haifu-urls.py --quiet  # 異常があるときだけ出す
"""
import json, sys, urllib.request, urllib.error, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
LIST = ROOT / "data" / "haifu-urls.json"


def tataku(url: str):
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": "one-hitter-check/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.geturl()
    except urllib.error.HTTPError as e:
        return e.code, url
    except Exception as e:  # DNS 失敗・タイムアウト
        return 0, f"{type(e).__name__}"


def main():
    quiet = "--quiet" in sys.argv
    items = json.loads(LIST.read_text(encoding="utf-8"))["urls"]
    shindeiru = []
    for it in items:
        code, final = tataku(it["url"])
        ok = 200 <= code < 400
        if not ok:
            shindeiru.append((it, code, final))
        if not quiet:
            print(("✅" if ok else "⚠ 死んでいる"), code, it["url"], "→", final if final != it["url"] else "", "｜", it["何"])
    if shindeiru:
        print(f"\n⚠ 配ったURLが {len(shindeiru)} 件、開けません。1時間以内に 301 で復旧し、渡した相手に正しいURLを送ること。")
        for it, code, final in shindeiru:
            print(f"  {code} {it['url']}（{it['何']}／渡した先：{it['渡した先']}）")
        sys.exit(1)
    if quiet:
        return
    print(f"\n✅ 配ったURL {len(items)} 件、すべて開けます。")


if __name__ == "__main__":
    main()
