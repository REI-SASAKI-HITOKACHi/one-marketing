#!/usr/bin/env python3
"""広告まわりの計測が、ブラウザで実際に動くかを確かめる。

    python3 tools/build-site.py netlify
    python3 tools/test-ads-tracking.py

見ているのは、Google広告を出す前に壊れていたら困るものだけ。

  1. `?gclid=` で来たら保存され、フォーム送信時に隠し欄へ入る
  2. `?wbraid=` `?gbraid=`（iOSなどで gclid の代わりに付くもの）でも同じ
  3. **広告から来たあと、別のページを経由してから申し込んでも gclid が残る**
     （保存していなければ、ここで落ちる）
  4. 90日を過ぎた gclid は捨てる
  5. `?src=gads&cid=...` が GA4 の設定（gtag config）に乗る
  6. 広告から来ていない人の gclid は空のまま（前の人の値が残らない）

rentracks.jp と googletagmanager.com へはこの環境から出られないので、
外部への読み込みは止めて動かしている（gclid の保存も送信も、
外部スクリプトとは無関係に動くため、それで確かめられる）。
"""
import functools
import http.server
import json
import os
import pathlib
import re
import sys
import threading

from playwright.sync_api import sync_playwright

CHROME = os.environ.get("OH_CHROME", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
ROOT = pathlib.Path(__file__).resolve().parent.parent / "deploy" / "netlify"

if not ROOT.exists():
    sys.exit(f"{ROOT} がありません。先に python3 tools/build-site.py netlify を実行してください")


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


_httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Quiet, directory=str(ROOT)))
threading.Thread(target=_httpd.serve_forever, daemon=True).start()
BASE = "http://127.0.0.1:%d" % _httpd.server_address[1]

ok = True


def chk(label, cond, extra=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + ("  " + str(extra) if extra else ""))
    if not cond:
        ok = False


def submit(pg):
    """実際には送信させず、送信イベントだけ起こす（Netlifyがここには無いため）。"""
    pg.evaluate("document.querySelector('form.form')"
                ".addEventListener('submit',function(e){e.preventDefault();},false)")
    pg.fill("#f-name", "テスト")
    pg.fill("#f-tel", "08000000000")
    pg.fill("#f-zip", "1340084")
    pg.eval_on_selector("form.form", "f => f.requestSubmit ? f.requestSubmit() : f.submit()")
    return (pg.eval_on_selector("input[name=order_id]", "e => e.value"),
            pg.eval_on_selector("input[name=gclid]", "e => e.value"))


with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=CHROME)

    def ctx():
        c = b.new_context()
        c.route(re.compile(r"^https?://(?!127\.0\.0\.1)"), lambda r: r.abort())
        return c

    # --- 1 / 2. gclid・wbraid・gbraid を拾う ---
    for param in ("gclid", "wbraid", "gbraid"):
        c = ctx()
        pg = c.new_page()
        pg.goto(f"{BASE}/mizumawari/index.html?{param}=TEST_{param.upper()}&src=gads&cid=123")
        oid, g = submit(pg)
        chk(f"?{param}= が隠し欄に入る", g == f"TEST_{param.upper()}", g)
        chk(f"?{param}= のとき注文IDも作られる", bool(oid), oid)
        c.close()

    # --- 3. 別ページを経由してから申し込んでも残る（ここが本番で起きる形） ---
    c = ctx()
    pg = c.new_page()
    pg.goto(f"{BASE}/mizumawari/index.html?gclid=KEEP_ME&src=gads")
    pg.goto(f"{BASE}/aircon/index.html")            # 広告と関係ないページを見る
    pg.goto(f"{BASE}/mizumawari/index.html")        # パラメータ無しで戻ってきて申し込む
    oid, g = submit(pg)
    chk("ページを移動しても gclid が残る（ここが肝）", g == "KEEP_ME", g)
    c.close()

    # --- 4. 90日を過ぎたら捨てる ---
    c = ctx()
    pg = c.new_page()
    pg.goto(f"{BASE}/mizumawari/index.html")
    pg.evaluate("localStorage.setItem('oh_gclid', JSON.stringify("
                "{v:'TOO_OLD', t: Date.now() - 91*24*60*60*1000}))")
    pg.goto(f"{BASE}/mizumawari/index.html")
    oid, g = submit(pg)
    chk("90日を過ぎた gclid は使わない", g == "", g)
    chk("古い gclid は消える", pg.evaluate("localStorage.getItem('oh_gclid')") is None)
    c.close()

    # --- 5. ?src=gads が GA4 の設定に乗る ---
    c = ctx()
    pg = c.new_page()
    pg.goto(f"{BASE}/mizumawari/index.html?src=gads&cid=98765")
    cfg = pg.evaluate(
        "(function(){var o=null;for(var i=0;i<(window.dataLayer||[]).length;i++){"
        "var a=window.dataLayer[i];"
        "if(a&&a[0]==='config'&&a[2]&&a[2].traffic_src!==undefined){o=a[2];}}return o;})()")
    chk("gtag config に traffic_src=gads が乗る", (cfg or {}).get("traffic_src") == "gads", cfg)
    chk("gtag config に traffic_cid が乗る", (cfg or {}).get("traffic_cid") == "98765", cfg)
    c.close()

    # --- 6. 広告から来ていない人は空のまま ---
    c = ctx()
    pg = c.new_page()
    pg.goto(f"{BASE}/mizumawari/index.html")
    oid, g = submit(pg)
    chk("広告経由でない人の gclid は空", g == "", g)
    c.close()

    b.close()

_httpd.shutdown()
print("\n" + ("すべて通りました" if ok else "失敗あり"))
sys.exit(0 if ok else 1)
