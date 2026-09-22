#!/usr/bin/env python3
"""ブログ原稿が `docs/blog/README.md` の形式どおりかを、出す前に機械で確かめる。

なぜ要るか（2026-09-16）：
  原稿 → cmo 査読 → LP担当の道具で投稿、という流れだが、形式のずれは人が読んでも見落とす。
  9/14〜9/15 に施設あてフォームで「機械の確認だけで済ませた」ことが原因の事故を続けて出したので、
  ブログでも「出す前に機械で確かめる」を先に用意しておく。

  LP担当の投稿ツール（20260912-05-lp / 20260912-11-lp）は、これを通ったファイルだけ受け取れば、
  front matter の欠けや料金の誤りを自分で見なくて済む。

使い方:
  python3 tools/check-blog.py                       # docs/blog/*.md を全部見る
  python3 tools/check-blog.py docs/blog/2026-09-16-*.md
  python3 tools/check-blog.py --strict               # 注意（warn）も失敗として扱う

出力は 1ファイル1ブロック。NG があれば終了コード 1。
"""
import argparse
import datetime as dt
import glob
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PRICE_MD = ROOT / "docs" / "price-master.md"
PHOTO_DIR = ROOT / "assets" / "photos"

REQUIRED = ("title", "date", "category", "eyecatch", "description")
CATEGORIES = ("事例研究", "読本", "お知らせ")
STATUSES = ("draft", "reviewed", "published")
# サイトに出さない欄。投稿ツールはここを落とす
INTERNAL_FIELDS = ("source", "notes", "status")

# docs/blog/README.md「書かないこと」＋ dokuhon_content.py の禁止語
BANNED = ["除菌", "殺菌", "抗菌", "病気", "危険", "守る", "ここからは", "お伝えします",
          "いかがでしょうか", "ぜひ", "安心", "大切な", "しっかり", "おそうじ本舗", "ビフォーアフター"]
# 満足度は 98.6% が正（CLAUDE.md）。98.8% はパンフレット・サイトの誤り
BAD_NUMBERS = ["98.8%", "98.8％"]
CTA_RE = re.compile(r"https://lp\.onehitter\.jp/(aircon|mizumawari)/\?src=(blog[A-Za-z0-9_-]*)")
SRC_RE = re.compile(r"^blog[A-Za-z0-9_-]*$")
TEL_RE = re.compile(r"0\d{1,3}-\d{2,4}-\d{4}")
PRICE_RE = re.compile(r"([1-9][0-9,]{2,7})\s*円")
IMG_RE = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)\s*$", re.M)
# 出典URL＝予約導線（lp.onehitter.jp）以外の URL。引用の例外を認める条件（cmo 決定 2026-09-22）
SHUTTEN_RE = re.compile(r"https?://(?!lp\.onehitter\.jp)\S+")


def load_prices() -> set:
    """price-master.md に出てくる金額（カンマ付き・税込）を集める。原稿の金額はこの中にしか無いはず。"""
    if not PRICE_MD.exists():
        return set()
    return {m.replace(",", "") for m in re.findall(r"¥?([0-9][0-9,]{2,7})\s*円?", PRICE_MD.read_text(encoding="utf-8"))}


def split_front(text: str):
    if not text.startswith("---"):
        return None, text
    end = text.find("\n---", 3)
    if end < 0:
        return None, text
    return text[3:end].strip("\n"), text[end + 4:]


def parse_front(raw: str) -> dict:
    """この原稿で使う範囲だけの素朴な YAML 読み。入れ子は使っていない。"""
    out = {}
    for line in raw.split("\n"):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        v = v.strip()
        if v.startswith('"') and v.endswith('"') and len(v) > 1:
            v = v[1:-1]
        out[k.strip()] = v
    return out


def honbun_len(body: str) -> int:
    """見出し・写真行・キャプション・URL・空行を除いた本文の文字数。README の数え方に合わせる。"""
    n = 0
    for line in body.split("\n"):
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("![") or s.startswith(">"):
            continue
        if s.startswith("*") and s.endswith("*"):
            continue  # キャプション
        s = re.sub(r"https?://\S+", "", s)
        n += len(re.sub(r"\s", "", s))
    return n


def check(path: pathlib.Path, prices: set) -> tuple:
    ng, warn = [], []
    text = path.read_text(encoding="utf-8")
    raw, body = split_front(text)
    if raw is None:
        return ["front matter（--- で囲む YAML）が無い"], []
    fm = parse_front(raw)

    for k in REQUIRED:
        if not fm.get(k):
            ng.append(f"front matter に {k} が無い")

    # ファイル名と date の一致
    m = re.match(r"(\d{4}-\d{2}-\d{2})-([a-z0-9-]+)\.md$", path.name)
    if not m:
        ng.append("ファイル名が YYYY-MM-DD-<半角英数とハイフン>.md になっていない")
    elif fm.get("date") and m.group(1) != fm["date"]:
        ng.append(f"ファイル名の日付 {m.group(1)} と front matter の date {fm['date']} が違う")

    if fm.get("date"):
        try:
            d = dt.date.fromisoformat(fm["date"])
            # 2026-09-22 オーナー指示で「週1本・毎週水曜」→「毎日投稿（向こう100日）」に変更。曜日は見ない
            today = dt.date.today()
            if d < today and fm.get("status", "draft") != "published":
                ng.append(f"公開予定日 {fm['date']} を過ぎているのに status が published でない")
            elif d == today and fm.get("status", "draft") != "published":
                warn.append(f"公開予定日が今日（{fm['date']}）。status は {fm.get('status', 'draft')} のまま")
        except ValueError:
            ng.append(f"date が日付として読めない: {fm['date']}")

    if fm.get("category") and fm["category"] not in CATEGORIES:
        ng.append(f"category は {'/'.join(CATEGORIES)} のどれか（いまは {fm['category']}）")
    if fm.get("status") and fm["status"] not in STATUSES:
        ng.append(f"status は {'/'.join(STATUSES)} のどれか（いまは {fm['status']}）")

    if fm.get("title") and len(fm["title"]) > 60:
        warn.append(f"title が {len(fm['title'])}字（60字程度まで）")
    if fm.get("description"):
        if len(fm["description"]) > 120:
            ng.append(f"description が {len(fm['description'])}字（120字以内）")
    for k in ("eyecatch", "ogp"):
        if fm.get(k):
            if "/" in fm[k]:
                ng.append(f"{k} はファイル名だけ（assets/photos/ 直下）")
            elif PHOTO_DIR.exists() and not (PHOTO_DIR / fm[k]).exists():
                warn.append(f"{k} の写真が assets/photos/ に無い: {fm[k]}")
    # ?src= は既定 blog。記事ごとに分けるときだけ blog_ で始める（README「記事ごとに分けたいとき」）
    if fm.get("src"):
        if not SRC_RE.match(fm["src"]):
            ng.append(f"src は blog で始まる半角英数と _ - だけ（いまは {fm['src']}）")
        elif len(fm["src"]) > 20:
            ng.append(f"src が {len(fm['src'])}字（20文字まで。LPが切り捨てる）")

    # 本文
    n = honbun_len(body)
    if not (800 <= n <= 1500):
        ng.append(f"本文 {n}字（800〜1,500字）")
    if re.search(r"^#\s", body, re.M):
        ng.append("本文に # の見出しがある（## から使う）")
    if re.search(r"^####\s", body, re.M):
        ng.append("本文に #### の見出しがある（### まで）")

    # 写真
    imgs = IMG_RE.findall(body)
    for alt, src in imgs:
        if "/" in src:
            ng.append(f"写真のパスはファイル名だけ: {src}")
        elif PHOTO_DIR.exists() and not (PHOTO_DIR / src).exists():
            warn.append(f"写真が assets/photos/ に無い: {src}")
        if re.search(r"江戸川|浦安|船堀|葛西|20\d\d年", alt):
            ng.append(f"alt に地名・日付を入れない: {alt}")
    pre = [a for a, _ in imgs if a.startswith("作業前")]
    post = [a for a, _ in imgs if a.startswith("作業後")]
    if post and not pre:
        ng.append("「作業後」の写真があるのに「作業前」が無い")
    if len(imgs) == 0:
        warn.append("写真が1枚も無い")

    # 書かないこと
    # 公的機関の案内・製品表示・お客様のクチコミの「原文引用」だけは禁止語を通す（cmo 決定 2026-09-22）。
    # 通す範囲は > の引用ブロックの中だけ。条件は、同じ記事に出典URLがあること。
    # 言い換えると根拠がずれるので、原文のまま引いて出典を添える形に寄せるための例外。
    lines = body.split("\n")
    quoted = "\n".join(l for l in lines if l.lstrip().startswith(">"))
    outside = "\n".join(l for l in lines if not l.lstrip().startswith(">"))
    has_shutten = bool(SHUTTEN_RE.search(body))
    for w in BANNED:
        if w in outside:
            ng.append(f"禁止語「{w}」が本文にある")
        elif w in quoted and not has_shutten:
            ng.append(f"禁止語「{w}」が引用の中にあるが、出典URLが記事に無い（引用の例外は出典URLが条件）")
    for w in BAD_NUMBERS:
        if w in text:
            ng.append(f"{w} は使わない（満足度は 98.6% が正）")
    if TEL_RE.search(body):
        ng.append("本文に電話番号がある（ブログには書かない。LPに任せる）")

    # 料金
    for p in {x.replace(",", "") for x in PRICE_RE.findall(body)}:
        if prices and p not in prices and int(p) >= 1000:
            ng.append(f"{int(p):,}円 が docs/price-master.md に無い")
    if re.search(r"[0-9],?[0-9]{3}\s*円", body) and "税込" not in body:
        ng.append("金額を書いているのに「税込」が本文に無い")
    # 繁忙期加算（docs/price-master.md）。書かないと 5〜7月・12月の請求額と食い違う。
    # GBP 第1束で同じ穴が出た（cmo 査読 2026-09-20）ので、ブログにも同じ門を置く
    if PRICE_RE.search(body) and not any(w in body for w in ("繁忙期", "3,300円", "3300円")):
        ng.append("金額を書いているのに繁忙期加算（5〜7月・12月／+3,300円）に触れていない")

    # 予約導線
    m_cta = CTA_RE.search(body)
    if not m_cta:
        ng.append("予約導線の URL が無い（https://lp.onehitter.jp/{aircon|mizumawari}/?src=blog）")
    else:
        want = fm.get("src") or "blog"
        if m_cta.group(2) != want:
            ng.append(f"予約導線の ?src={m_cta.group(2)} と front matter の src={want} が違う")

    # 投稿ツールに渡さない欄
    used_internal = [k for k in INTERNAL_FIELDS if k in fm]
    return ng, warn + ([f"サイトに出さない欄: {', '.join(used_internal)}（投稿ツールは落とすこと）"] if used_internal else [])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--strict", action="store_true", help="注意も失敗として扱う")
    a = ap.parse_args()
    files = [pathlib.Path(f) for f in (a.files or sorted(glob.glob(str(ROOT / "docs/blog/*.md"))))]
    files = [f for f in files if f.name not in ("README.md", "既存記事一覧.md")]
    if not files:
        print("原稿が見つかりません")
        return 1
    prices = load_prices()
    bad = 0
    for f in files:
        ng, warn = check(f, prices)
        mark = "NG" if ng else ("注意" if warn else "OK")
        try:
            shown = f.relative_to(ROOT)
        except ValueError:
            shown = f  # リポジトリの外のファイル（検証用）もそのまま見られるように
        print(f"\n[{mark}] {shown}")
        for x in ng:
            print("  ✗", x)
        for x in warn:
            print("  ・", x)
        if ng or (a.strict and warn):
            bad += 1
    print(f"\n{len(files)}本中 {bad}本に直すところがあります" if bad else f"\n{len(files)}本とも形式どおりです")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
