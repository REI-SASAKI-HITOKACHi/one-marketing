#!/usr/bin/env python3
"""レントラックスの成果タグが、ブラウザで実際に動くかを確かめる。

    python3 tools/build-site.py netlify
    python3 tools/test-rentracks-tag.py

静的なチェック（tools/check-tracking.py）は「HTMLに文字列があるか」しか見られない。
このスクリプトは本物のブラウザで動かして、**注文IDがLPからサンクスページへ実際に
渡るか**まで見る。2026-09-11 に、目印の <!-- を <script> の中に書いたせいで
タグが丸ごと死んでいたのを見つけたのがこれ。静的チェックだけでは通っていた。

rentracks.jp へはこの環境から出られないので、rt.track.js は同じ役割の偽物に
差し替えて確かめている（発火したかどうかは、それで十分わかる）。

必要なもの：playwright と Chromium。入っていなければ
    python3 -m venv .venv && .venv/bin/pip install playwright
    CHROME 変数を、この環境の Chromium の場所に合わせる
"""
from playwright.sync_api import sync_playwright
import os
import re
import sys

import functools
import http.server
import pathlib
import threading

CHROME = os.environ.get("OH_CHROME", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
ROOT = pathlib.Path(__file__).resolve().parent.parent / "deploy" / "netlify"

if not ROOT.exists():
    sys.exit(f"{ROOT} がありません。先に python3 tools/build-site.py netlify を実行してください")

# 組み立てた結果を、その場で配って見にいく。外部のサーバーは要らない。
class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):  # アクセスログは結果を見づらくするだけなので出さない
        pass


_handler = functools.partial(_Quiet, directory=str(ROOT))
_httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _handler)
threading.Thread(target=_httpd.serve_forever, daemon=True).start()
BASE = "http://127.0.0.1:%d" % _httpd.server_address[1]
ok = True
def chk(label, cond, extra=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + ("  " + str(extra) if extra else ""))
    if not cond: ok = False

with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=CHROME)
    ctx = b.new_context()
    # 外部への通信は全部止める（rentracks.jp / google は届かないので）
    # rt.track.js は本物を読みに行かせず、同じ役割の偽物を返す
    # （この環境から rentracks.jp へは出られないため）。
    STUB = ("window._rt=window._rt||{};window.__rt=window.__rt||[];"
            "window.rt_tracktag=function(){window.__rt.push("
            "JSON.parse(JSON.stringify(window._rt)));};")
    def stub(route):
        route.fulfill(status=200, content_type="application/javascript", body=STUB)
    ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1)"), lambda r: r.abort())
    ctx.route(re.compile(r"rentracks\.jp/js/itp/rt\.track\.js"), stub)
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: print("  [JSエラー]", e))

    # --- 1. LP：送信時に注文IDが作られるか ---
    pg.goto(BASE + "/mizumawari/index.html")
    # 実際の送信は止める（Netlifyは無いので）
    pg.evaluate("document.querySelector('form.form').addEventListener('submit',"
                "function(e){e.preventDefault();},false)")
    pg.fill("#f-name", "テスト")
    pg.fill("#f-tel", "08000000000")
    pg.fill("#f-zip", "1340084")
    pg.eval_on_selector("form.form", "f => f.requestSubmit ? f.requestSubmit() : f.submit()")
    hid = pg.eval_on_selector("input[name=order_id]", "e => e.value")
    ss  = pg.evaluate("sessionStorage.getItem('oh_order_id')")
    chk("注文IDが hidden 欄に入る", bool(hid), hid)
    chk("注文IDが sessionStorage に入る", ss == hid, ss)
    chk("注文IDの形が OH-日付-mizumawari-4桁",
        bool(re.fullmatch(r"OH-\d{8}-mizumawari-[A-Z2-9]{4}", hid or "")), hid)
    chk("URLエンコードで文字が増えない",
        pg.evaluate("id => encodeURIComponent(id) === id", hid))

    # --- 2. サンクス：注文IDがあるときだけ発火するか ---
    pg.goto(BASE + "/mizumawari/thanks.html")
    pg.wait_for_timeout(1200)
    fired = pg.evaluate("window.__rt || []")
    chk("サンクスで rt_tracktag が呼ばれる", len(fired) == 1, fired)
    if fired:
        v = fired[0]
        chk("sid/pid が先方指定どおり", str(v.get("sid")) == "11535" and str(v.get("pid")) == "16436", v)
        chk("price=0 / reward=-1（定額案件）", v.get("price") == 0 and v.get("reward") == -1, v)
        chk("cinfo が LP で作った注文IDと一致", v.get("cinfo") == hid, v.get("cinfo"))
        chk("氏名・電話・メールは空（社外へ出さない）",
            v.get("cname") == "" and v.get("ctel") == "" and v.get("cemail") == "", v)
    chk("使い切って sessionStorage から消える",
        pg.evaluate("sessionStorage.getItem('oh_order_id')") is None)

    # --- 3. 読み込み直しで二重に発火しないか ---
    pg.reload(); pg.wait_for_timeout(1200)
    chk("読み込み直しでは発火しない（重複防止）", pg.evaluate("(window.__rt||[]).length") == 0)

    # --- 4. サンクスを直接開いても発火しないか ---
    ctx2 = b.new_context()
    ctx2.route(re.compile(r"^https?://(?!127\.0\.0\.1)"), lambda r: r.abort())
    ctx2.route(re.compile(r"rentracks\.jp/js/itp/rt\.track\.js"), stub)
    p2 = ctx2.new_page()
    p2.goto(BASE + "/mizumawari/thanks.html"); p2.wait_for_timeout(1200)
    chk("直接開いただけでは発火しない（空の成果を立てない）", p2.evaluate("(window.__rt||[]).length") == 0)

    # --- 5. 他のLPには出ていないか ---
    for d in ("aircon", "aircon-b", "nenmatsu"):
        p3 = ctx2.new_page()
        p3.goto(f"{BASE}/{d}/thanks.html")
        has = p3.evaluate("document.documentElement.outerHTML.indexOf('rt.track.js') >= 0")
        chk(f"/{d}/ にはタグが無い（未登録の掲載先）", not has)
        p3.close()
    b.close()
_httpd.shutdown()
print("\n" + ("すべて通りました" if ok else "失敗あり"))
sys.exit(0 if ok else 1)
