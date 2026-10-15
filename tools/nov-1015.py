#!/usr/bin/env python3
"""11月の需要（浴室・キッチン・年末）に合わせた入口の直し（依頼 20261015-02-lp）。/aircon/ 系には触らない。

  python3 tools/nov-1015.py                       # deploy/netlify から preview/nov1015/ に書き出す（確認用）
  python3 tools/nov-1015.py --out deploy/netlify  # 配信物に当てる（オーナーのOKのあと）

1. 年末LP2本に「11月のお掃除は10%お得」の帯（1箇所だけのご依頼・12月は繁忙期）。帯の右に予約ページへのリンク
2. 年末LP2本の入口を予約ページへ（ヘッダー・固定バーの右・nenmatsu の「11月中の空き枠を確認する」・nenmatsu-b の主ボタン）
3. 水まわりLP2本の帯の「12月は割引なし」→「12月は繁忙期（1箇所+3,300円）」
4. 今の版（mizumawari・nenmatsu）は主ボタンが料金の箱と数字の帯の下＝スマホの最初の画面の外。
   主ボタンの塊を見出しの説明文の直後へ上げる（ボタンは増やさない）。nenmatsu の主ボタンは予約ページへ
"""
import re
import argparse, importlib.util, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent

def mod(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), ROOT / "tools" / f"{name}.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

band, iri = mod("insert-band"), mod("iriguchi")
PAGES = ["mizumawari", "mizumawari-b", "nenmatsu", "nenmatsu-b"]
Y = "https://yoyaku.onehitter.jp/"
UE = "<!-- nov1015-ue -->"
NEN_OLD = '<a class="btn lg" href="#builder">箇所を選んで、年末の料金を見る</a>'
NEN_NEW = (f'<a class="btn lg" href="{Y}" data-yoyaku data-place="hero">11月中の空いている日を見る</a>'
           '\n      <a class="iri-sub" href="#builder">箇所を選んで、年末の料金を見る</a>')


def ue_ni(h, p):
    """hero-in の中の hero-cta の塊を、説明文（p.sub）の直後へ移す。"""
    if UE in h:
        return h
    if p == "nenmatsu":
        if h.count(NEN_OLD) != 1:
            sys.exit("nenmatsu: 主ボタンが見つかりません")
        h = h.replace(NEN_OLD, NEN_NEW)
    m = re.search(r'\n    <div class="hero-cta">.*?\n    </div>\n', h, re.S)
    sub = re.search(r'\n    <p class="sub"[^>]*>.*?</p>\n', h, re.S)
    if not m or not sub or sub.end() > m.start():
        sys.exit(f"{p}: 主ボタンの塊か説明文が見つかりません（並びが変わった？）")
    blk = m.group(0)
    # 予約ページの主ボタンを塊の先頭に（営業時間に出る「電話で相談する」より上）
    lines = blk.split("\n")
    yo = [l for l in lines if 'data-place="hero"' in l and "yoyaku" in l]
    if len(yo) == 1:
        lines.remove(yo[0]); k = next(i for i, l in enumerate(lines) if 'class="hero-cta"' in l)
        lines.insert(k + 1, yo[0]); blk = "\n".join(lines)
    h = h[:m.start()] + "\n" + h[m.end():]
    i = sub.end()
    return h[:i] + "    " + UE + blk.lstrip("\n").replace('<div class="hero-cta">', '<div class="hero-cta" style="margin:14px 0 18px">', 1) + h[i:]

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
        if p in ("mizumawari", "nenmatsu"):
            h = ue_ni(h, p)
        dst = pathlib.Path(a.out) / p / "index.html"; dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(h, encoding="utf-8"); print(f"{p:13s} → {dst}")

if __name__ == "__main__":
    main()
