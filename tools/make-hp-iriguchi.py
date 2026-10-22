#!/usr/bin/env python3
"""公式サイト（CMS）の入口ページ（地域×メニュー）を、原稿の Markdown から作る（依頼 20261022-01-lp）。

    python3 tools/make-hp-iriguchi.py docs/HP-入口ページ/2026-10-28-edogawa-aircon-cleaning.md

作るもの：
  cms/hp-iriguchi/<slug>/paste-into-cms.html  … CMS のブログ記事の本文欄（Jodit のソース表示）にそのまま貼るブロック
  preview/hp-iriguchi/<slug>.html             … 公式サイトの実際の記事ページの枠に本文を入れた確認用（公開しない）
そのあと、確認用ページに tools/check-public-page.py をかけ、金額・言い回しの点検もする。

決まり：
- CSS クラスを増やさない（すべてインライン style）。<style> も <script> も使わない
- 公式サイトの CSS が a の色を上書きするので、ボタンの色には !important を付ける（共有 20261010-05-lp）
- 写真は lp.onehitter.jp/blog-photos/ に既にあるものだけ（無いものは止める）
- 金額は data/prices.json の表にある数字と、予約ページの計算で出る組み合わせ（ALLOWED_YEN）だけ
"""
import html
import json
import pathlib
import re
import subprocess
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
PHOTO_DIR = ROOT / "deploy" / "netlify" / "blog-photos"
PHOTO_URL = "https://lp.onehitter.jp/blog-photos/"
TEMPLATE_URL = "https://one-hitter.jp/blog/20230130-1528/"   # 実際の記事ページ（枠だけ借りる）

INK, SUB, RULE, BG, CTA, CTA_D = "#13232E", "#3C5262", "#D7E1E7", "#FAF7F2", "#B72C0A", "#8F2408"
NG_WORDS = ["出張費", "一切", "98.8", "080-1755-7275", "完全分解", "背抜き", "付けたまま", "ファンを取り外", "ファンを外",
            "しつこい営業", "ではありません", "することはありません"]


def front_matter(md):
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", md, re.S)
    if not m:
        sys.exit("front matter がありません")
    fm, body = m.group(1), m.group(2)
    meta = {}
    for line in fm.splitlines():
        mm = re.match(r"^(\w+):\s*(.*)$", line)
        if mm and not mm.group(2).startswith("|"):
            meta[mm.group(1)] = mm.group(2).strip().strip('"')
    return meta, body


def inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", rf'<strong style="color:{INK};">\1</strong>', s)
    return s


def photo(alt, name):
    if not (PHOTO_DIR / name).exists():
        sys.exit(f"写真 {name} が lp.onehitter.jp/blog-photos/ にありません（置くには配信が要る）。止めます")
    return (f'<figure style="margin:20px 0;"><img src="{PHOTO_URL}{name}" alt="{html.escape(alt)}" '
            f'style="display:block;width:100%;height:auto;border-radius:8px;" loading="lazy">'
            f'<figcaption style="margin-top:6px;font-size:12.5px;color:{SUB};">{html.escape(alt)}</figcaption></figure>')


def button(text, url):
    return (f'<p style="margin:18px 0 8px;"><a href="{html.escape(url)}" style="display:block;box-sizing:border-box;max-width:420px;'
            f'padding:15px 14px;border-radius:9999px;background:{CTA} !important;color:#FFFFFF !important;text-decoration:none !important;text-align:center;'
            f'font-weight:700;font-size:16px;line-height:1.4;box-shadow:0 3px 0 {CTA_D};">{html.escape(text)}</a></p>')


def table(rows):
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows if not re.match(r"^\|[\s\-|]+\|$", r.strip())]
    head, body = cells[0], cells[1:]
    th = "".join(f'<th style="text-align:left;padding:8px 10px;border-bottom:2px solid {RULE};font-size:13px;color:{SUB};">{inline(c)}</th>' for c in head)
    trs = "".join("<tr>" + "".join(f'<td style="padding:9px 10px;border-bottom:1px solid {RULE};">{inline(c)}</td>' for c in r) + "</tr>" for r in body)
    return (f'<div style="overflow-x:auto;margin:14px 0;"><table style="border-collapse:collapse;width:100%;min-width:320px;font-size:15px;color:{INK};">'
            f"<thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table></div>")


def md_to_html(body):
    out, lines, i = [], body.strip().splitlines(), 0
    P = f'style="margin:0 0 14px;font-size:16px;line-height:1.9;color:{INK};"'
    while i < len(lines):
        ln = lines[i].rstrip()
        if not ln:
            i += 1; continue
        if m := re.match(r"^!\[([^\]]*)\]\(([^)]+)\)$", ln):
            out.append(photo(m.group(1), m.group(2))); i += 1; continue
        if m := re.match(r"^\[([^\]]+)\]\((https://[^)]+)\)$", ln):
            out.append(button(m.group(1), m.group(2))); i += 1; continue
        if ln.startswith("## "):
            out.append(f'<h2 style="margin:32px 0 12px;padding-left:10px;border-left:4px solid {CTA};font-size:20px;line-height:1.5;color:{INK};">{inline(ln[3:])}</h2>')
            i += 1; continue
        if ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(lines[i]); i += 1
            out.append(table(rows)); continue
        if re.match(r"^(- |\d+\. )", ln):
            tag = "ol" if re.match(r"^\d+\. ", ln) else "ul"
            items = []
            while i < len(lines) and re.match(r"^(- |\d+\. )", lines[i]):
                items.append(re.sub(r"^(- |\d+\. )", "", lines[i])); i += 1
            lis = "".join(f'<li style="margin:0 0 6px;">{inline(x)}</li>' for x in items)
            out.append(f'<{tag} style="margin:0 0 14px;padding-left:1.4em;font-size:16px;line-height:1.85;color:{INK};">{lis}</{tag}>')
            continue
        para = []
        while i < len(lines) and lines[i].strip() and not re.match(r"^(## |\||- |\d+\. |!\[|\[)", lines[i]):
            para.append(lines[i].strip()); i += 1
        out.append(f"<p {P}>{inline(''.join(para))}</p>")
    return "\n".join(out)


def allowed_yen():
    """料金表の数字と、予約ページの計算で出る数字。原稿の金額はこの中に無いと止める。"""
    d = json.load(open(ROOT / "data" / "prices.json", encoding="utf-8"))
    ok = set()
    def walk(x):
        if isinstance(x, dict):
            for v in x.values(): walk(v)
        elif isinstance(x, list):
            for v in x: walk(v)
        elif isinstance(x, (int, float)) and x >= 100:
            ok.add(int(x))
    walk(d)
    ok.add(2200)   # 予約ページのネット申込特典（S.netTokuten。prices.json には無い）
    n, o = 10780, 17380
    for v in [n * 2 - 2200, n * 3 - 2200, n + 3300, o + 3300, n - round(n * 0.1), n - round(n * 0.15),
              o - round(o * 0.1), o - round(o * 0.15), n * 2 - 2200 + 6600, 18480 + 15180]:
        ok.add(v)
    return ok


def tenken_text(block):
    t = re.sub(r"<[^>]+>", " ", block)
    ng = [f"使わない言い方「{w}」" for w in NG_WORDS if w in t]
    ok = allowed_yen()
    for y in re.findall(r"([0-9]{1,3}(?:,[0-9]{3})+)円", t):
        if int(y.replace(",", "")) not in ok:
            ng.append(f"料金表・予約ページの計算に無い金額 {y}円")
    if "080-8043-8259" not in t:
        ng.append("電話番号 080-8043-8259 が無い")
    if not re.search(r"https://yoyaku\.onehitter\.jp/\?src=(blog|hp)", block):
        ng.append("予約ページへのボタンに src が無い")
    return ng


def main():
    src = pathlib.Path(sys.argv[1])
    meta, body = front_matter(src.read_text(encoding="utf-8"))
    slug = re.sub(r"^\d{4}-\d{2}-\d{2}-", "", src.stem)
    block = md_to_html(body)
    ng = tenken_text(block)

    cms_dir = ROOT / "cms" / "hp-iriguchi" / slug
    cms_dir.mkdir(parents=True, exist_ok=True)
    head = (f"<!-- ワンヒッター：公式サイトの入口ページ「{meta.get('title','')}」の本文（{src.name} から tools/make-hp-iriguchi.py で作成）\n"
            "     ブログ記事の本文欄をソース表示（< >）にして、このコメントの下をすべて貼ってください。CSS クラスは使っていません。 -->\n")
    (cms_dir / "paste-into-cms.html").write_text(head + block + "\n", encoding="utf-8")

    tpl = urllib.request.urlopen(urllib.request.Request(TEMPLATE_URL, headers={"User-Agent": "Mozilla/5.0"}), timeout=20).read().decode("utf-8")
    a = tpl.find('<div class="-w-text -w-rich_text">'); b = tpl.find('<div class="-w-article-signature">')
    if a < 0 or b < 0:
        sys.exit("記事ページの枠が見つかりません（公式サイトのテンプレートが変わった可能性）")
    a = tpl.find(">", a) + 1
    title = html.escape(meta.get("title", ""))
    pv = tpl[:a] + "\n" + block + "\n</div>\n" + tpl[b:]
    pv = re.sub(r"<title>[^<]*</title>", f"<title>{title} | ブログ | 江戸川区のハウスクリーニングならワンヒッター株式会社</title>", pv, count=1)
    pv = re.sub(r"<h1>[^<]*</h1>", f"<h1>{title}</h1>", pv, count=1)
    pv = pv.replace('href="/', 'href="https://one-hitter.jp/').replace('src="/', 'src="https://one-hitter.jp/')
    pv_path = ROOT / "preview" / "hp-iriguchi" / f"{slug}.html"
    pv_path.parent.mkdir(parents=True, exist_ok=True)
    pv_path.write_text(pv, encoding="utf-8")

    r = subprocess.run([sys.executable, str(ROOT / "tools" / "check-public-page.py"), "--hp", str(pv_path)], capture_output=True, text=True)
    print(f"本文ブロック: {(cms_dir / 'paste-into-cms.html').relative_to(ROOT)}")
    print(f"確認用ページ: {pv_path.relative_to(ROOT)}")
    print("check-public-page:", r.stdout.strip() or r.stderr.strip())
    print("金額・言い回し:", "OK" if not ng else "NG\n  " + "\n  ".join(ng))
    sys.exit(1 if (ng or r.returncode) else 0)


if __name__ == "__main__":
    main()
