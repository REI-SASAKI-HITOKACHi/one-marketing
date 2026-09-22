#!/usr/bin/env python3
"""SNSカード（画像に焼き込む文字）を、投稿の前に機械で確かめる。

なぜ要るか（2026-09-22）：
  キャプションは `check-gbp.py` の考え方で見ていたが、**画像の中の文字は誰も見ていなかった。**
  w02-1・w02-2 で実際にこうなっていた：

    承認済みキャプション … 機材に触れない「差し替え版」（`data/sns-queue.json` の note の条件分岐どおり）
    カード画像          … 旧版のまま「内視鏡カメラで槽の裏側を、その場で一緒に見ます」
                          「配管から出てくる水の汚れを数値で測る点検を、無料でやっています」

  **内視鏡カメラとATP測定器が手元にあるかが未確定**のまま、約束だけが画像に載っていた。
  投稿の直前に目で見て気づいたが、目で見なければ出ていた。ここを機械にする（cmo 承認 2026-09-22）。

見るもの:
  1. `check-gbp.py` と同じ門のうち、カードに当てはまるもの
     （禁止語・本舗の語と番号・98.8%・最上級・電話番号・料金がマスターにあるか・「税込」）
  2. **裏の取れていない約束**（内視鏡カメラ・ATP・ルミテスター・「無料で」）。
     機材の有無が確定したら `MIKAKUTEI` から外す
  3. ★**カードの約束が、承認済みキャプションに無い**★ ← 今回の本質。
     画像とキャプションが食い違っていたら、画像のほうが強い（人はまず画像を見る）

使い方:
  python3 tools/check-cards.py              # data/sns-cards/*.json を全部
  python3 tools/check-cards.py w02-1 w03-1

NG があれば終了コード1。
"""
import argparse
import glob
import importlib.util
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SPECS = ROOT / "data" / "sns-cards"
QUEUE = ROOT / "data" / "sns-queue.json"

# check-gbp.py の語彙をそのまま使う（二重管理にしない）
_spec = importlib.util.spec_from_file_location("cg", ROOT / "tools" / "check-gbp.py")
cg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cg)

# 裏が取れるまでカードに書けない約束。確定したらここから外す
MIKAKUTEI = {
    "内視鏡": "内視鏡カメラが手元にあるか未確定（2026-09-19 に質問・未回答）",
    "ATP": "ATP測定器が手元にあるか未確定（同上）",
    "ルミテスター": "ATP測定器が手元にあるか未確定（同上）",
    "数値で測る": "ATP測定器が手元にあるか未確定（同上）",
}
# キャプションに無いのにカードにあると事故になる語（約束・条件・金額に関わるもの）
YAKUSOKU = ["無料", "内視鏡", "ATP", "ルミテスター", "数値で測る", "その場で", "点検", "限定", "円"]


def card_text(d: dict) -> str:
    """画像に出る文字を全部つなぐ"""
    parts = [d.get("headline", ""), d.get("credit", "")]
    parts += d.get("lines", [])
    parts.append(d.get("footnote", ""))
    return "\n".join(p for p in parts if p)


def approved_caption(cid: str) -> str:
    """同じ id のキューのキャプション。approved か posted（出す前／出した後）を照合の相手にする。
    draft は承認前なので相手にしない。無ければ空"""
    if not QUEUE.exists():
        return ""
    for it in json.loads(QUEUE.read_text(encoding="utf-8")):
        if it.get("id") == cid and it.get("status") in ("approved", "posted"):
            return it.get("caption") or it.get("本文") or ""
    return ""


def bunsetsu(text: str) -> list:
    """。で切って、空でない文を返す"""
    return [s.strip() for s in re.split(r"[。\n]", text) if s.strip()]


def check(cid: str, d: dict, prices: set) -> list:
    ng = []
    t = card_text(d)

    for w in cg.BANNED:
        if w in t:
            ng.append(f"禁止語「{w}」")
    for w in cg.HONPO:
        if w in t:
            ng.append(f"本舗の語・番号「{w}」")
    for w in cg.BAD_NUM:
        if w in t:
            ng.append(f"{w} は使わない（満足度は 98.6% が正）")
    for w in cg.SUPERLATIVE:
        if w in t:
            ng.append(f"最上級の表現「{w}」")
    if cg.TEL_RE.search(t):
        ng.append("カードに電話番号（プロフィール側に出る）")
    for p in {x.replace(",", "") for x in cg.PRICE_RE.findall(t)}:
        if prices and p not in prices and int(p) >= 1000:
            ng.append(f"{int(p):,}円 が docs/price-master.md に無い")
    if re.search(r"[0-9],?[0-9]{3}\s*円", t) and "税込" not in t:
        ng.append("金額を書いているのに「税込」が無い")

    for w, riyuu in MIKAKUTEI.items():
        if w in t:
            ng.append(f"裏の取れていない約束「{w}」… {riyuu}")

    # ★カードとキャプションの食い違い（2026-09-22 の事故そのもの）
    cap = approved_caption(cid)
    if cap:
        for s in bunsetsu(t):
            hit = [w for w in YAKUSOKU if w in s]
            if hit and s not in cap.replace("\n", ""):
                # キャプションに同じ文が無い＝画像だけが約束している
                miss = [w for w in hit if w not in cap]
                if miss:
                    ng.append(f"カードにあってキャプションに無い約束「{'／'.join(miss)}」: {s[:34]}")
    elif QUEUE.exists():
        # 照合の相手が無いのは、まだ承認前（draft のみ）のとき。事故ではないので注意どまり
        print(f"      ・ {cid}: キューに approved/posted が無い（まだ査読前）。照合はスキップ")
    return ng


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*")
    a = ap.parse_args()
    files = sorted(glob.glob(str(SPECS / "*.json")))
    if a.ids:
        files = [f for f in files if pathlib.Path(f).stem in a.ids]
    if not files:
        print("カード原稿が見つかりません")
        return 1
    prices = cg.load_prices()
    bad = 0
    for f in files:
        d = json.loads(pathlib.Path(f).read_text(encoding="utf-8"))
        cid = d.get("id", pathlib.Path(f).stem)
        ng = check(cid, d, prices)
        print(f"[{'NG' if ng else 'OK'}] {cid}  {card_text(d).splitlines()[0][:34]}")
        for x in ng:
            print("      ✗", x)
        if ng:
            bad += 1
    print(f"\n{len(files)}枚中 {bad}枚に直すところがあります" if bad else f"\n{len(files)}枚とも出せます")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
