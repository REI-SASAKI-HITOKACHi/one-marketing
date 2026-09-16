#!/usr/bin/env python3
"""**本番のページを取ってきて、そのままブラウザで開き、計測が発火するかを見る。**

    python3 tools/measure-production.py

## なぜ必要か

`tools/check-tracking.py` は**ビルドした結果**を見る。`tools/test-ads-tracking.py` は
**手元のビルド**をブラウザで動かす。どちらも「本番に出ているか」は見ていない。

**リポジトリに入っていても、再配信されていなければ本番では動いていない。**
2026-09-14 に、`gclid` の保存がまさにその状態（コミット済み・未配信）だった。
**出稿の前にここが食い違っていると、広告費が計測なしで流れる。**

## 何を見るか

| | |
|---|---|
| `generate_lead` | LP各本のサンクスページ、予約フォームの完了画面 |
| `phone_click` | `tel:` リンクを実際にクリックして確かめる |
| `traffic_src` / `traffic_cid` | `?src=` `?cid=` が `gtag('config')` に乗るか |
| `order_id` | 送信時に採番されて隠し欄に入るか |
| `gclid` | `?gclid=` が `localStorage` と隠し欄に入るか |
| `conversion_id` | Google広告の `AW-` が入っているか（空なら成果は記録されない） |

## 測れないもの

**GA4のサーバーが実際に受け取ったか**は、ここでは分からない。
`googletagmanager.com` へこの環境から出られないので、**`dataLayer` に積まれるところまで**を見ている。
そこから先は鍵か管理画面が要る（CMO／ブラウザ担当）。
"""

import functools
import http.server
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import threading

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.exit("playwright がありません。 pip install playwright を実行してください。")

CHROME = os.environ.get("OH_CHROME", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome")

LP_BASE = "https://lp.onehitter.jp"
LPS = ["mizumawari", "aircon", "aircon-b", "nenmatsu"]

# (保存名, URL)
PAGES = [(f"{n}", f"{LP_BASE}/{n}/") for n in LPS]
PAGES += [(f"{n}-thanks", f"{LP_BASE}/{n}/thanks.html") for n in LPS]
PAGES += [
    ("survey", f"{LP_BASE}/survey/"),
    ("yoyaku", "https://yoyaku.onehitter.jp/"),
]

ok = True


def chk(label, cond, extra=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + (("  " + str(extra)) if extra else ""))
    if not cond:
        ok = False


def fetch(dst: pathlib.Path) -> dict:
    """本番のHTMLをそのまま落とす。リダイレクトは追う（aircon-b は301）。"""
    got = {}
    for name, url in PAGES:
        out = dst / f"{name}.html"
        # 取得に失敗することがあるので3回まで試す。
        # 1回の失敗を「本番が壊れている」と読み違えないため。
        for _ in range(3):
            r = subprocess.run(
                ["curl", "-sL", "--max-time", "30", "-o", str(out), "-w", "%{http_code}", url],
                capture_output=True, text=True)
            code = r.stdout.strip()
            if code == "200":
                break
        size = out.stat().st_size if out.exists() else 0
        print(f"  {code}  {size:>7,} B  {url}")
        got[name] = (code == "200" and size > 0)
    return got


def main() -> None:
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="oh-prod-"))
    print("■ 本番から取得")
    got = fetch(tmp)
    missing = [n for n, v in got.items() if not v]
    if missing:
        chk("全ページが200で取れる", False, "取れなかった: " + " ".join(missing))

    srv = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0),
        functools.partial(type("Q", (http.server.SimpleHTTPRequestHandler,),
                               {"log_message": lambda *a: None}), directory=str(tmp)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = "http://127.0.0.1:%d" % srv.server_address[1]

    def evs(pg):
        return pg.evaluate(
            "(window.dataLayer||[]).filter(function(a){return a&&a[0]==='event';})"
            ".map(function(a){return {name:a[1], params:a[2]||{}};})")

    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=CHROME)

        def ctx():
            # 外部（GTM・レントラックス）へは出られないので止める。
            # gtag() の実体は本番HTMLに埋まった素のスニペットなので、これで測れる。
            c = b.new_context()
            c.route(re.compile(r"^https?://(?!127\.0\.0\.1)"), lambda r: r.abort())
            return c

        print("\n■ サンクスページ・完了画面の generate_lead")
        for n in LPS:
            c = ctx(); pg = c.new_page()
            pg.goto(f"{base}/{n}-thanks.html"); pg.wait_for_timeout(400)
            e = [x for x in evs(pg) if x["name"] == "generate_lead"]
            chk(f"  {n} サンクス", len(e) == 1, json.dumps(e, ensure_ascii=False)[:160])
            c.close()

        c = ctx(); pg = c.new_page()
        pg.goto(f"{base}/yoyaku.html"); pg.wait_for_timeout(400)
        before = len([x for x in evs(pg) if x["name"] == "generate_lead"])
        pg.evaluate("var d=document.getElementById('done'); if(d){d.hidden=false;}")
        pg.wait_for_timeout(400)
        after = [x for x in evs(pg) if x["name"] == "generate_lead"]
        chk("  予約フォーム：完了画面の前は発火しない", before == 0, before)
        chk("  予約フォーム：完了画面で発火", len(after) == 1,
            json.dumps(after, ensure_ascii=False)[:160])
        c.close()

        print("\n■ tel: リンクのクリック → phone_click")
        for n in LPS + ["survey", "yoyaku"]:
            c = ctx(); pg = c.new_page()
            pg.goto(f"{base}/{n}.html"); pg.wait_for_timeout(300)
            cnt = pg.eval_on_selector_all("a[href^='tel:']", "e => e.length")
            # tel: への遷移だけ止める。捕捉フェーズなので本体のリスナーは動く
            pg.evaluate("document.addEventListener('click',function(e){e.preventDefault();},true)")
            hit = pg.evaluate("(function(){var a=document.querySelector(\"a[href^='tel:']\");"
                              "if(!a)return false;a.click();return true;})()")
            pg.wait_for_timeout(300)
            e = [x for x in evs(pg) if x["name"] == "phone_click"]
            chk(f"  {n}（tel:リンク {cnt}本）", bool(hit) and len(e) == 1,
                (e[0]["params"].get("phone_number") if e else "発火なし"))
            c.close()

        print("\n■ LINEリンクのクリック → line_click")
        for n in LPS:
            c = ctx(); pg = c.new_page()
            pg.goto(f"{base}/{n}.html"); pg.wait_for_timeout(300)
            cnt = pg.eval_on_selector_all("a[href*='lin.ee'],a[href*='line.me']", "e => e.length")
            pg.evaluate("document.addEventListener('click',function(e){e.preventDefault();},true)")
            pg.evaluate("document.querySelectorAll(\"a[href*='lin.ee'],a[href*='line.me']\")"
                        ".forEach(function(a){a.click();})")
            pg.wait_for_timeout(300)
            e = [x for x in evs(pg) if x["name"] == "line_click"]
            conv = pg.evaluate("(window.dataLayer||[])"
                               ".filter(function(a){return a&&a[1]==='conversion';})"
                               ".map(function(a){return (a[2]||{}).send_to;})")
            chk(f"  {n}（LINEリンク {cnt}本）", cnt > 0 and len(e) == cnt, len(e))
            # 広告側へ届いているか。ラベルが空だと GA4 にしか残らない
            chk(f"  {n}：LINEタップが広告側にも届く", len(conv) == cnt,
                conv or "広告側へは0件（labels.line_click が空）")
            c.close()

        print("\n■ 広告まわり（gclid・order_id・traffic_src・AW-）")
        c = ctx(); pg = c.new_page()
        pg.goto(f"{base}/mizumawari.html?gclid=PROD_TEST&src=gads&cid=98765")
        pg.wait_for_timeout(400)
        chk("  ?gclid= が localStorage に入る",
            pg.evaluate("localStorage.getItem('oh_gclid')") is not None)
        chk("  フォームに gclid の隠し欄がある",
            pg.eval_on_selector_all("input[name=gclid]", "e => e.length") == 1)
        cfg = pg.evaluate(
            "(function(){var o=null,L=window.dataLayer||[];for(var i=0;i<L.length;i++){"
            "var a=L[i];if(a&&a[0]==='config'&&a[2]&&a[2].traffic_src!==undefined)o=a[2];}"
            "return o;})()")
        chk("  gtag config に traffic_src=gads", (cfg or {}).get("traffic_src") == "gads", cfg)
        chk("  gtag config に traffic_cid", (cfg or {}).get("traffic_cid") == "98765")

        # order_id は「送信した瞬間」に採番される。実際に送信イベントを起こして見る
        pg.evaluate("document.querySelector('form.form')"
                    ".addEventListener('submit',function(e){e.preventDefault();},false)")
        pg.fill("#f-name", "テスト"); pg.fill("#f-tel", "08000000000"); pg.fill("#f-zip", "1340084")
        pg.eval_on_selector("form.form", "f => f.requestSubmit ? f.requestSubmit() : f.submit()")
        pg.wait_for_timeout(300)
        oid = pg.eval_on_selector("input[name=order_id]", "e => e.value")
        chk("  送信で order_id が採番される", bool(oid), oid)
        c.close()

        c = ctx(); pg = c.new_page()
        pg.goto(f"{base}/mizumawari-thanks.html"); pg.wait_for_timeout(400)
        cid = pg.evaluate("((window.OH_M||{}).google_ads||{}).conversion_id")
        aw = pg.evaluate("(window.dataLayer||[])"
                         ".filter(function(a){return a&&a[1]==='conversion';}).length")
        chk("  Google広告の conversion_id が入っている", bool(cid),
            f"本番の値は {cid!r} ／ AW-への conversion 送信 {aw}件")
        c.close()

        b.close()

    srv.shutdown()
    print("\n⚠️ GA4のサーバーが実際に受け取ったかは、ここでは測れません"
          "（外部への通信を止めているため）。管理画面か Data API で見てください。")
    print("すべて通りました" if ok else "失敗あり（上の FAIL を見ること）")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
