#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""住所 → 郵便番号 の索引をつくる（東京都・千葉県・神奈川県）。

  受注フォームで郵便番号欄をなくした（2026-09-19 オーナー指示）。
  「住所入力からスプシへ郵便番号を自動反映させてほしい」。

  ★引くのはサーバ側（tools/juchu-inbox.py）だけ。
    この索引をフォーム（お客様/和真さんの端末）へ送らないこと。送ると起動が重くなる。

  出所: HeartRails Geo API（https://geoapi.heartrails.com/）。町域ごとの郵便番号。
        日本郵便の KEN_ALL は、この環境からは落とせなかった（接続が切られる）。
  精度: **町域まで**。丁目ごとに郵便番号が分かれる町域は、代表の1つになる。
        台帳に人が入れた「住所と郵便番号の実績」があるときは、そちらを優先する。

    python3 tools/build-postal-index.py          # data/postal-index.json を作る
"""
import json
import pathlib
import sys
import time
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "postal-index.json"
KEN = ["東京都", "千葉県", "神奈川県"]
API = "https://geoapi.heartrails.com/api/json"


def yobu(**q):
    u = API + "?" + urllib.parse.urlencode(q)
    for i in range(4):
        try:
            with urllib.request.urlopen(u, timeout=30) as r:
                return json.loads(r.read())["response"]
        except Exception as e:
            if i == 3:
                raise
            time.sleep(2 ** i)


def main():
    sakuin = {}
    for ken in KEN:
        shi = yobu(method="getCities", prefecture=ken).get("location", [])
        print(f"{ken}: {len(shi)}市区町村")
        for s in shi:
            city = s["city"]
            r = yobu(method="getTowns", prefecture=ken, city=city)
            for t in r.get("location", []):
                yubin = str(t.get("postal", "")).strip()
                if len(yubin) != 7:
                    continue
                key = city + t["town"]
                sakuin.setdefault(key, yubin)
                sakuin.setdefault(ken + key, yubin)
            time.sleep(0.15)
        print(f"  … ここまで {len(sakuin):,}件")
    OUT.write_text(json.dumps({
        "_説明": "住所（市区町村＋町域）→ 郵便番号7桁。tools/build-postal-index.py が作る。",
        "_出所": "HeartRails Geo API。町域までの精度。",
        "_使う人": "tools/juchu-inbox.py だけ。フォームへは送らない。",
        "_作成": time.strftime("%Y-%m-%d"),
        "索引": sakuin,
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"書き出しました: {OUT}  {OUT.stat().st_size:,} bytes  {len(sakuin):,}件")


if __name__ == "__main__":
    sys.exit(main())
