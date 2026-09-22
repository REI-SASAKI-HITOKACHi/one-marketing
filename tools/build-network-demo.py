#!/usr/bin/env python3
"""協力店ネット（仮称）のデモ画面を組み立てる。

なぜ生成するのか:
  料金を手で書き写すと data/prices.json とずれる（予約フォームと同じ考え方）。
  テンプレートは network/demo/template.html。料金と API_URL を埋めて
  network/demo/index.html に書き出す。

使い方:
  python3 tools/build-network-demo.py
  python3 tools/build-network-demo.py --api https://script.google.com/macros/s/.../exec
"""
import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PRICES = ROOT / "data" / "prices.json"
TPL = ROOT / "network" / "demo" / "template.html"
OUT = ROOT / "network" / "demo" / "index.html"


def shoyou(m):
    n = re.search(r"(\d+)", str(m.get("所要") or ""))
    return int(n.group(1)) if n else 60


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="", help="Apps Script ウェブアプリの /exec URL（空なら端末内保存だけで動く）")
    a = ap.parse_args()
    p = json.loads(PRICES.read_text(encoding="utf-8"))
    menus = [{"名称": m["名称"], "単体": m["単体"], "同時": m.get("同時施工", m["単体"]), "所要": shoyou(m)}
             for m in p["本メニュー"] if m.get("所要")]
    opts = [{"名称": o["名称"], "価格": o["価格"]} for o in p["オプション"][:5]]
    data = {"menus": menus, "options": opts,
            "busy_months": p["繁忙期加算"]["対象月"], "busy_add": p["繁忙期加算"]["金額"]}
    html = TPL.read_text(encoding="utf-8")
    if "/*__PRICES__*/" not in html or "/*__API_URL__*/" not in html:
        sys.exit("template.html に埋め込み印がありません")
    html = html.replace("/*__PRICES__*/", json.dumps(data, ensure_ascii=False))
    html = html.replace("/*__API_URL__*/", a.api)
    OUT.write_text(html, encoding="utf-8")
    print(f"書き出し: {OUT.relative_to(ROOT)}  メニュー{len(menus)}本／オプション{len(opts)}本／API_URL={'あり' if a.api else 'なし（端末内保存）'}")


if __name__ == "__main__":
    main()
