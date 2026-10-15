#!/usr/bin/env python3
"""11月の需要（浴室・キッチン・年末）に合わせた入口の直し（依頼 20261015-02-lp）。/aircon/ 系には触らない。

  python3 tools/nov-1015.py                       # deploy/netlify から preview/nov1015/ に書き出す（確認用）
  python3 tools/nov-1015.py --out deploy/netlify  # 配信物に当てる（オーナーのOKのあと）

1. 年末LP2本に「11月のお掃除は10%お得」の帯（1箇所だけのご依頼・12月は繁忙期）。帯の右に予約ページへのリンク
2. 年末LP2本の入口を予約ページへ（ヘッダー・固定バーの右・nenmatsu の「11月中の空き枠を確認する」・nenmatsu-b の主ボタン）
3. 水まわりLP2本の帯の「12月は割引なし」→「12月は繁忙期（1箇所+3,300円）」
"""
import argparse, importlib.util, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent

def mod(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), ROOT / "tools" / f"{name}.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

band, iri = mod("insert-band"), mod("iriguchi")
PAGES = ["mizumawari", "mizumawari-b", "nenmatsu", "nenmatsu-b"]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--src", default=str(ROOT / "deploy" / "netlify"))
    ap.add_argument("--out", default=str(ROOT / "preview" / "nov1015")); a = ap.parse_args()
    for p in PAGES:
        h = (pathlib.Path(a.src) / p / "index.html").read_text(encoding="utf-8")
        if p.startswith("nenmatsu"):
            if band.MARK not in h:
                h = band.insert(h, p)
            h = iri.apply(h, p)
        else:
            h = band.dec_dake(h, p)
        dst = pathlib.Path(a.out) / p / "index.html"; dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(h, encoding="utf-8"); print(f"{p:13s} → {dst}")

if __name__ == "__main__":
    main()
