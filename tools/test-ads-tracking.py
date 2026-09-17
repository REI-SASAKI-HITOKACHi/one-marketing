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
  7. **Google広告のコンバージョンが、正しい send_to で撃たれる**
  8. **LINEリンクを押すと line_click が出て、広告側にも届く**
     （LPが「LINEで無料クーポン」と誘導しているのに計上されないと、
     　LINE経由の申込が広告の成果として1件も残らない）
     （空振りすると「GA4では見えるのに広告の管理画面では0件」になる。
     　measurement.json が空のうちは、撃たないことを確かめる）

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
CFG = json.loads((pathlib.Path(__file__).resolve().parent.parent
                  / "tracking" / "measurement.json").read_text())

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

    # --- 7. Google広告のコンバージョンが、正しい send_to で撃たれるか ---
    #
    # ここが空振りすると「GA4では見えているのに広告の管理画面では0件」になる。
    # 設定が空（出稿前）のときは、撃たれないのが正しい。
    ads = CFG.get("google_ads", {})
    aw = ads.get("conversion_id", "")
    labels = ads.get("labels", {})

    def conversions(pg):
        return pg.evaluate(
            "(window.dataLayer||[]).filter(function(a){return a&&a[0]==='event'"
            "&&a[1]==='conversion';}).map(function(a){return (a[2]||{}).send_to;})")

    c = ctx()
    pg = c.new_page()
    pg.goto(f"{BASE}/mizumawari/thanks.html")
    pg.wait_for_timeout(300)
    got = conversions(pg)
    if aw and labels.get("generate_lead"):
        want = aw + "/" + labels["generate_lead"]
        chk("サンクスページ → 申込のコンバージョンが撃たれる", got == [want], got)
        chk("AW- が gtag('config') に登録されている",
            pg.evaluate("(window.dataLayer||[]).some(function(a){"
                        "return a&&a[0]==='config'&&String(a[1]).indexOf('AW-')===0;})"))
    else:
        chk("設定が空のうちは広告のコンバージョンを撃たない", got == [], got)
    c.close()

    c = ctx()
    pg = c.new_page()
    pg.goto(f"{BASE}/mizumawari/index.html")
    pg.wait_for_timeout(200)
    # tel: への遷移だけ止める。捕捉フェーズなので本体のリスナーは動く
    pg.evaluate("document.addEventListener('click',function(e){e.preventDefault();},true)")
    pg.evaluate("document.querySelector(\"a[href^='tel:']\").click()")
    pg.wait_for_timeout(300)
    got = conversions(pg)
    if aw and labels.get("phone_click"):
        want = aw + "/" + labels["phone_click"]
        chk("電話タップ → 電話のコンバージョンが撃たれる", got == [want], got)
        chk("申込と電話でラベルが違う（同じだと入札の目標に混ざる）",
            labels["phone_click"] != labels.get("generate_lead"))
    else:
        chk("設定が空のうちは電話でも撃たない", got == [], got)
    c.close()

    # --- 8. LINEタップ ---
    #
    # 両LPがファーストビューで「LINEで無料クーポン」と誘導している。
    # ここが計上されないと、LINE経由の申込が広告の成果として1件も残らず、
    # **効いている広告を止める判断をしかねない**（CMO 20260916-01-measurement）。
    for lp in ("mizumawari", "aircon"):
        c = ctx()
        pg = c.new_page()
        pg.goto(f"{BASE}/{lp}/index.html")
        pg.wait_for_timeout(200)
        pg.evaluate("document.addEventListener('click',function(e){e.preventDefault();},true)")
        n = pg.eval_on_selector_all("a[href*='lin.ee'],a[href*='line.me']", "e => e.length")
        pg.evaluate("document.querySelectorAll(\"a[href*='lin.ee'],a[href*='line.me']\")"
                    ".forEach(function(a){a.click();})")
        pg.wait_for_timeout(300)
        ev = pg.evaluate("(window.dataLayer||[]).filter(function(a){return a&&a[0]==='event'"
                         "&&a[1]==='line_click';}).length")
        got = conversions(pg)
        chk(f"{lp}: LINEリンク {n}本ぜんぶで line_click が出る", n > 0 and ev == n, ev)
        if aw and labels.get("line_click"):
            want = aw + "/" + labels["line_click"]
            chk(f"{lp}: LINEタップ → LINEのコンバージョンが撃たれる",
                got == [want] * n, got)
            chk("LINEのラベルが、申込・電話と違う（同じだと入札の目標に混ざる）",
                labels["line_click"] not in (labels.get("generate_lead"), labels.get("phone_click")))
        else:
            chk(f"{lp}: 設定が空のうちはLINEでも撃たない", got == [], got)
        c.close()

    # --- 9. アンケートのLINEボタンを、広告の成果に混ぜていないか ---
    #
    # LPのLINEボタン        … 公式アカウントを友だち追加（＝見込み客）
    # アンケートのLINEボタン … 友だちに紹介文を送る（＝本人は既存のお客様）
    #
    # 混ぜると、**広告費をかけていない既存のお客様が「広告の成果」に化ける**。
    # CPAが実態より良く見えて、出稿の判断を誤る。
    c = ctx()
    pg = c.new_page()
    pg.goto(f"{BASE}/survey/index.html")
    pg.wait_for_timeout(300)
    pg.evaluate("document.addEventListener('click',function(e){e.preventDefault();},true)")
    n = pg.eval_on_selector_all("a[href*='lin.ee'],a[href*='line.me']", "e => e.length")
    pg.evaluate("document.querySelectorAll(\"a[href*='lin.ee'],a[href*='line.me']\")"
                ".forEach(function(a){a.click();})")
    pg.wait_for_timeout(300)
    names = pg.evaluate("(window.dataLayer||[]).filter(function(a){return a&&a[0]==='event';})"
                        ".map(function(a){return a[1];})")
    chk(f"アンケートのLINEボタン {n}本は refer_share になる",
        n > 0 and names.count("refer_share") == n, names)
    chk("アンケートでは line_click を出さない（出すと既存客が広告の成果に化ける）",
        "line_click" not in names, names)
    chk("アンケートからは広告のコンバージョンを撃たない", conversions(pg) == [], conversions(pg))
    c.close()

    # --- 10. GA4 の traffic_src と、フォームの hidden 欄 src が一致するか ---
    #
    # 片方だけ生の値にしていると、**同じ訪問が GA4 と Netlify Forms で
    # 違う名前になり、突き合わせられなくなる**。
    # 規約は docs/流入の見分け方-src規約.md（英数字と _ - だけ／20文字まで）。
    from urllib.parse import quote
    for given in ("gads_mizumawari", "gads_aircon", "gads_brand",
                  "日本語", "a" * 30, "gads mizu!"):
        c = ctx()
        pg = c.new_page()
        pg.goto(f"{BASE}/mizumawari/index.html?src={quote(given)}")
        pg.wait_for_timeout(250)
        cfg = pg.evaluate(
            "(function(){var o=null,L=window.dataLayer||[];for(var i=0;i<L.length;i++){"
            "var a=L[i];if(a&&a[0]==='config'&&a[2]&&a[2].traffic_src!==undefined)o=a[2];}"
            "return o;})()")
        ga4 = (cfg or {}).get("traffic_src")
        hid = pg.evaluate(
            "(function(){var e=document.querySelector('input[name=src]');"
            "return e?e.value:null;})()")
        if hid is None:
            # このブランチの lp/ には hidden 欄がまだ無い（LP担当のブランチが正）。
            # 片側しか見られないので、GA4側が規約どおり削られているかだけ見る。
            import re as _re
            kitai = (_re.sub(r"[^A-Za-z0-9_-]", "", given)[:20]) or "direct"
            chk(f"?src={given[:16]!r} GA4側が規約どおり削られる", ga4 == kitai,
                f"GA4={ga4!r} 期待={kitai!r}")
        else:
            chk(f"?src={given[:16]!r} で GA4 とフォームが同じ値になる", ga4 == hid,
                f"GA4={ga4!r} フォーム={hid!r}")
        c.close()

    b.close()

_httpd.shutdown()
print("\n" + ("すべて通りました" if ok else "失敗あり"))
sys.exit(0 if ok else 1)
