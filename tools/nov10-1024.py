#!/usr/bin/env python3
"""エアコンLP（C・E）の1画面目に「11月の作業は1台10%引き・9,702円」を出す（依頼 20261023-01-lp・20261024-01-lp・第8回MTG 8-4 No.3）。

    python3 tools/nov10-1024.py                       # deploy/machi/nov10/ に C・E・/aircon/ を作る（配信しない）
    python3 tools/nov10-1024.py --out deploy/netlify  # オーナーの「入れる」のあと、配信物に当てる

変えるのは2か所だけ（10/23 の案 docs/img/エアコンLP-11月10%の案-1024MTG.png のとおり）：
  1. 上の帯：「11月のお掃除は、今のご予約で10%お得／エアコン1台のご依頼・12月は割引なし」
            →「11月の作業は、エアコン1台10%引き／ノーマル 9,702円・お掃除機能付き 15,642円」
  2. 料金の欄：10,780円の下に「11月の作業なら 9,702円（1台のご依頼は10%引き）」を1行
金額は予約ページの計算（作業日が11月・1台のときだけ 10%）と data/prices.json に一致。
「11月のご予約」ではなく「11月の作業」と書く（予約ページは作業日の月で割引を決めるため）。
料金の欄の1行は、帯と同じく 12月1日 0:00（日本時間）に自動で隠す。
C と E に同じ変更を入れる（C対E の比べ方を崩さない）。/aircon/ は直した C から tools/furiwake-aircon.py で作り直す。
"""
import argparse
import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

BAND_OLD = '<p class="nov-in"><b>11月のお掃除は、今のご予約で10%お得</b><span class="nov-sub">エアコン1台のご依頼・12月は割引なし</span>'
BAND_NEW = '<p class="nov-in"><b>11月の作業は、エアコン1台10%引き</b><span class="nov-sub">ノーマル 9,702円・お掃除機能付き 15,642円</span>'
PRICE_OLD = '<span class="k">（税込）／60分</span>\n'
PRICE_NEW = (PRICE_OLD +
             '      <span class="nov-price" id="nov-price">11月の作業なら <b>9,702円</b>（1台のご依頼は10%引き）</span>\n'
             '      <script>if (Date.now() >= Date.UTC(2026, 10, 30, 15, 0, 0)) { document.getElementById(\'nov-price\').hidden = true; }</script>\n')
CSS_OLD = '.hero-price .s{font-size:12.5px;color:var(--steel);line-height:1.7;flex-basis:100%;}'
CSS_NEW = (CSS_OLD +
           '\n.hero-price .nov-price{flex-basis:100%;margin:2px 0 0;padding:6px 10px;border-radius:8px;background:#FCEAE4;color:#8F2408;'
           'font-size:14px;font-weight:700;line-height:1.5;}'
           '\n.hero-price .nov-price[hidden]{display:none;}'
           '\n.hero-price .nov-price b{font-family:"Oswald",sans-serif;font-size:22px;font-weight:500;margin:0 2px;}')
MARK = 'id="nov-price"'


def kaeru(s, old, new):
    n = s.count(old)
    if n != 1:
        sys.exit(f"想定と違う：{old[:60]!r} が {n} か所（1 か所のはず）。止めます")
    return s.replace(old, new)


def apply(h):
    if MARK in h:
        return h
    h = kaeru(h, BAND_OLD, BAND_NEW)
    h = kaeru(h, PRICE_OLD, PRICE_NEW)
    h = kaeru(h, CSS_OLD, CSS_NEW)
    return h


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(ROOT / "deploy" / "netlify"))
    ap.add_argument("--out", default=str(ROOT / "deploy" / "machi" / "nov10"))
    a = ap.parse_args()
    src, out = pathlib.Path(a.src), pathlib.Path(a.out)
    for v in ("aircon-c", "aircon-e"):
        h = apply((src / v / "index.html").read_text(encoding="utf-8"))
        (out / v).mkdir(parents=True, exist_ok=True)
        (out / v / "index.html").write_text(h, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("furiwake", ROOT / "tools" / "furiwake-aircon.py")
    fw = importlib.util.module_from_spec(spec); spec.loader.exec_module(fw)
    h = fw.make((out / "aircon-c" / "index.html").read_text(encoding="utf-8"))
    ng = fw.tenken(h)
    if ng:
        sys.exit("/aircon/ の作り直しで NG:\n  " + "\n  ".join(ng))
    (out / "aircon").mkdir(parents=True, exist_ok=True)
    (out / "aircon" / "index.html").write_text(h, encoding="utf-8")
    print(f"書き出しました: {out}/aircon-c・aircon-e・aircon（/aircon/ は直した C の写し）")


if __name__ == "__main__":
    main()
