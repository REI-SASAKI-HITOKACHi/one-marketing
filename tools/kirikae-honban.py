#!/usr/bin/env python3
"""本番の月の切り替えを、文字の読み戻しで確かめる（依頼 20261031-01-lp・11/1 0:00 と 12/1 0:00 の切り替え用）。

    python3 tools/kirikae-honban.py              # いまの本番を読む（表を標準出力に）
    python3 tools/kirikae-honban.py --save X.md  # 表を Markdown で保存

見るもの（実際の時刻のまま。時計は細工しない）：
  - LP（/aircon/・C・E・/kabi/・水まわり2本・年末2本）：11月の帯・「11月の作業なら 9,702円」・「いまは加算なし」の行
  - 年末LP：「作業」で書いた通常価格の線引き（古い「ご予約」の書き方が0件か）
  - 予約ページ：いちばん早い空き日、その日を選んだときの日付の画面の防カビの1行と、確認の画面の金額
  - 公式サイトの入口ページ（記事1805）：11月の1文と予約ボタン
外への計測（GA・広告・Meta）は止める。予約は送信しない（確認の画面まで）。
"""
import argparse
import datetime
import re
import urllib.request

from playwright.sync_api import sync_playwright

CHROME = "/opt/pw-browsers/chromium"
LP = "https://lp.onehitter.jp"
LPS = ["aircon", "aircon-c", "aircon-e", "kabi", "mizumawari", "mizumawari-b", "nenmatsu", "nenmatsu-b"]
YOYAKU = "https://yoyaku.onehitter.jp/?menu=ac1&src=kirikae_check"
IRIGUCHI = "https://one-hitter.jp/blog/20261028-1805/"
BLOCK = re.compile(r".*(google-analytics|googletagmanager|googleadservices|doubleclick|google\.com/(ccm|rmkt)|facebook|connect\.facebook).*")
OLD_NENMATSU = ["11月30日までのご予約", "11月30日のご予約まで", "11月までのご予約が安い", "12月のご予約だと", "申込日で判断"]


def page(b):
    ctx = b.new_context(viewport={"width": 390, "height": 844}, timezone_id="Asia/Tokyo")
    pg = ctx.new_page()
    pg.route(BLOCK, lambda r: r.abort())
    return ctx, pg


def lp_rows(b):
    rows = []
    for name in LPS:
        ctx, pg = page(b)
        pg.goto(f"{LP}/{name}/?src=kirikae_check#ab-c" if name == "aircon" else f"{LP}/{name}/?src=kirikae_check")
        pg.wait_for_timeout(2500)
        r = pg.evaluate("""(()=>{
          const vis=id=>{const e=document.getElementById(id);return e?(e.offsetParent!==null&&!e.hidden):null};
          const t=id=>{const e=document.getElementById(id);return e?e.innerText.replace(/\\s+/g,' ').trim():''};
          return {url:location.pathname, band:vis('nov-band'), bandText:t('nov-band'), price:vis('nov-price'), priceText:t('nov-price'), peak:t('peak-line')};})()""")
        html = pg.content()
        old = sum(html.count(k) for k in OLD_NENMATSU) if name.startswith("nenmatsu") else None
        rows.append((name, r, old))
        ctx.close()
    return rows


def yoyaku_row(b):
    ctx, pg = page(b)
    pg.goto(YOYAKU); pg.wait_for_timeout(4000)
    first = pg.evaluate("(()=>{const d=document.querySelector('.day .dl');return d?d.textContent.trim():''})()")
    note = tot = ""
    if first:
        pg.locator(".day .times button").first.click(); pg.wait_for_timeout(400)
        note = pg.evaluate("(()=>{const e=document.getElementById('bokabi-note');return e&&!e.hidden?e.textContent.trim():''})()")
        pg.locator("#n2").click(); pg.wait_for_timeout(400)
        pg.fill("#f-name", "見本"); pg.fill("#f-tel", "090-0000-0000"); pg.fill("#f-addr", "東京都江戸川区北葛西（見本）")
        pg.locator("#n3").click(); pg.wait_for_timeout(800)
        tot = pg.evaluate("document.getElementById('total2').innerText.replace(/\\s+/g,' ')")
    ctx.close()
    return first, note, tot


def iriguchi_row():
    h = urllib.request.urlopen(urllib.request.Request(IRIGUCHI, headers={"User-Agent": "Mozilla/5.0"}), timeout=20).read().decode("utf-8", "replace")
    t = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style)[^>]*>.*?</\1>", "", h, flags=re.S)))
    m = re.search(r"11月は、1台だけのご依頼が10%引きになります。", t)
    btn = "yoyaku.onehitter.jp/?src=blog_edogawa_aircon" in h
    return bool(m), btn


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--save")
    a = ap.parse_args()
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M JST")
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME, args=["--no-sandbox", "--disable-dev-shm-usage"])
        lps = lp_rows(b)
        first, note, tot = yoyaku_row(b)
        b.close()
    ir, btn = iriguchi_row()
    out = [f"# 本番の切り替えの読み戻し（{now}）", "", "| ページ | 11月の帯 | 9,702円の行 | 加算の行 | 年末の古い書き方 |", "|---|---|---|---|---|"]
    yn = lambda v: "—" if v is None else ("出る" if v else "出ない")
    for name, r, old in lps:
        out.append(f"| /{name}/（着地 {r['url']}） | {yn(r['band'])}：{r['bandText'][:48]} | {yn(r['price'])} | {r['peak'][-14:] or '—'} | {'—' if old is None else str(old) + '件'} |")
    out += ["", "| 予約ページ | 値 |", "|---|---|",
            f"| いちばん早い空き日 | {first or '（空き枠なし）'} |",
            f"| その日を選んだときの防カビの1行 | {note or '出ない'} |",
            f"| 確認の画面の金額 | {tot[:120]} |",
            "", "| 入口ページ（記事1805） | 値 |", "|---|---|",
            f"| 「11月は、1台だけのご依頼が10%引き」 | {'ある' if ir else '無い'} |",
            f"| 予約ボタン（?src=blog_edogawa_aircon） | {'ある' if btn else '無い'} |"]
    s = "\n".join(out)
    print(s)
    if a.save:
        open(a.save, "w", encoding="utf-8").write(s + "\n")


if __name__ == "__main__":
    main()
