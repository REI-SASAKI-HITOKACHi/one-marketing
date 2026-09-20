#!/usr/bin/env python3
"""GBP「最新情報」の本文を、出す前に機械で確かめる。

なぜ要るか（2026-09-20）：
  オーナー指示「まとめて投稿予約でいい。過去分から100投稿くらい今予約して」を受けて、
  ブラウザ担当が**予約投稿で先々まで入れる**ことになった（2027年まで指定できる）。
  本数が増えるほど、人の目では通らない。`docs/gbp-最新情報-運用.md` の6章を機械にする。

  ★予約投稿なので「先週」「先日」「今月」が使えない。★ 投稿されるのが数か月先なので、
  書いた時点の「先週」は嘘になる。日付で書く。ここを機械で止める。
  ★写真が付かない。★ ブラウザ担当の内蔵ブラウザからは写真を添付できない（2026-09-20 実測）。
  「2枚目は」「写真の」のような、写真がある前提の書き方を止める。

使い方:
  python3 tools/check-gbp.py                                  # docs/gbp-最新情報-本文のみ-*.md を全部
  python3 tools/check-gbp.py docs/gbp-最新情報-本文のみ-第1束.md

原稿は ``` で囲んだブロック1つ＝1投稿として読む。NG があれば終了コード1。
"""
import argparse
import glob
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PRICE_MD = ROOT / "docs" / "price-master.md"

MIN_JI, MAX_JI = 150, 300          # 運用の型 3章（GBPの上限1,500字は使い切らない）

# 運用 6章「書かないこと」
BANNED = ["完全除去", "必ず", "100%", "二度と", "除菌", "殺菌", "抗菌", "病気", "守る", "安心", "危険",
          "ここからは", "お伝えします", "いかがでしょうか", "ぜひ", "しっかり", "大切な"]
# 運用 5章 文言：本舗の語と番号を書かない
HONPO = ["おそうじ本舗", "本舗", "080-1344-3137"]
BAD_NUM = ["98.8%", "98.8％"]
SUPERLATIVE = ["No.1", "ナンバーワン", "日本一", "地域一番", "業界一", "最安", "一番安い", "最高品質"]
# 予約投稿で嘘になる相対表現
SOUTAI = ["先週", "先日", "今週", "今月", "昨日", "本日", "今日", "来月", "今年", "このたび", "最近"]
# 写真が付かないので、写真がある前提の書き方は使えない
# 「上の」「下の」は入れない。「扉の下のレール」のような普通の言い回しまで落ちる（2026-09-20 実測）
SHASHIN = ["枚目", "写真", "画像", "ご覧", "こちらの1枚", "ビフォーアフター"]

PRICE_RE = re.compile(r"([1-9][0-9,]{2,7})\s*円")
TEL_RE = re.compile(r"0\d{1,3}-\d{2,4}-\d{4}")
URL_RE = re.compile(r"https?://|[a-z0-9-]+\.(?:jp|com|net)\b", re.I)
BLOCK_RE = re.compile(r"```(?:text)?\n(.*?)```", re.S)


def load_prices() -> set:
    if not PRICE_MD.exists():
        return set()
    return {m.replace(",", "") for m in re.findall(r"¥?([0-9][0-9,]{2,7})\s*円?", PRICE_MD.read_text(encoding="utf-8"))}


def ji(text: str) -> int:
    """全角の字数。空白・改行は数えない（運用の型の数え方）"""
    return len(re.sub(r"\s", "", text))


def check(body: str, prices: set) -> list:
    ng = []
    n = ji(body)
    if not (MIN_JI <= n <= MAX_JI):
        ng.append(f"{n}字（{MIN_JI}〜{MAX_JI}字）")
    for w in BANNED:
        if w in body:
            ng.append(f"禁止語「{w}」")
    for w in HONPO:
        if w in body:
            ng.append(f"本舗の語・番号「{w}」（GBPはワンヒッター名義）")
    for w in BAD_NUM:
        if w in body:
            ng.append(f"{w} は使わない（満足度は 98.6% が正）")
    for w in SUPERLATIVE:
        if w in body:
            ng.append(f"最上級の表現「{w}」")
    for w in SOUTAI:
        if w in body:
            ng.append(f"予約投稿では嘘になる「{w}」（日付で書く）")
    for w in SHASHIN:
        if w in body:
            ng.append(f"写真がある前提の「{w}」（本文だけの投稿）")
    if TEL_RE.search(body):
        ng.append("本文に電話番号（GBPのプロフィール側に出る）")
    if URL_RE.search(body):
        ng.append("本文にURL（導線はボタンで出す）")
    for p in {x.replace(",", "") for x in PRICE_RE.findall(body)}:
        if prices and p not in prices and int(p) >= 1000:
            ng.append(f"{int(p):,}円 が docs/price-master.md に無い")
    if re.search(r"[0-9],?[0-9]{3}\s*円", body) and "税込" not in body:
        ng.append("金額を書いているのに「税込」が無い")
    return ng


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    a = ap.parse_args()
    files = [pathlib.Path(f) for f in (a.files or sorted(glob.glob(str(ROOT / "docs/gbp-最新情報-本文のみ-*.md"))))]
    if not files:
        print("原稿が見つかりません")
        return 1
    prices = load_prices()
    bad = total = 0
    for f in files:
        blocks = BLOCK_RE.findall(f.read_text(encoding="utf-8"))
        print(f"\n■ {f.name}（{len(blocks)}本）")
        for i, b in enumerate(blocks, 1):
            total += 1
            ng = check(b.strip(), prices)
            print(f"  [{'NG' if ng else 'OK'}] {i:>3}本目  {ji(b)}字  {b.strip().splitlines()[0][:28]}")
            for x in ng:
                print("        ✗", x)
            if ng:
                bad += 1
    print(f"\n{total}本中 {bad}本に直すところがあります" if bad else f"\n{total}本とも形式どおりです")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
