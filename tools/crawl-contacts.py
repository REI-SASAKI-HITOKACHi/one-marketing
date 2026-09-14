#!/usr/bin/env python3
"""施設のサイトを巡って、連絡の手段を調べる（問い合わせフォーム・公開メール・Instagram・営業お断りの記載）。

2026-09-14 第1波の反省：巡回で拾った「お問い合わせ」URL 93 件のうち 46 件は実際にはフォームが無かった
（404・店舗一覧・電話だけの案内・別会社のページ）。送信の当日に分かるので無駄が大きい。
そこでこのツールは **本文欄（textarea）があるところまで確認してから** contact_form_url に入れる。
フォームが無い施設は has_form=false のまま残し、メール・電話・DM の担当に回す。

読み取りだけ。送信は一切しない。

使い方:
  python3 tools/crawl-contacts.py data/facilities-2026-09-add.json          # 巡回して <入力>-contacts.json を書く
  python3 tools/crawl-contacts.py data/facilities-2026-09-add.json --n 100  # 先頭100件だけ
  python3 tools/crawl-contacts.py ... --同時 6                              # 同時に開く数（既定4）
"""
import argparse
import asyncio
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

# 送ってはいけない先（docs/節目チャネル-全体構造.md 9章）。shisetsu-outreach.py と同じ言葉
NO_SALES_RE = re.compile(r"(営業|セールス|勧誘|業者|取引|売り込み)[^。\n]{0,20}(お断り|ご遠慮|禁止|お控え|ご容赦)|患者(様|さま|さん)?(専用|以外|のみ)|患者様以外|営業目的[^。\n]{0,10}(禁止|お断り|ご遠慮)")
CONTACT_RE = re.compile(r"(問い?合わ?せ|問合せ|contact|inquiry|mail ?form|メールフォーム|ご相談)", re.I)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
SKIP_EXT = (".pdf", ".jpg", ".jpeg", ".png", ".gif", ".zip", ".mp4")
# 予約・採用・資料請求など、カード設置の相談に使うべきでないフォーム
WRONG_FORM_RE = re.compile(r"(予約|採用|求人|エントリー|応募|見学|里親|譲渡|資料請求|キャンセル|クレーム)", re.I)


async def one(ctx, f: dict) -> dict:
    site = (f.get("サイト") or "").strip()
    out = {"id": f["id"], "施設名": f["施設名"], "種別": f["種別"], "サイト": site, "status": "no_site",
           "contact_form_url": "", "has_form": False, "no_sales": False, "emails": [], "instagram": None, "line": None}
    if not site:
        return out
    pg = await ctx.new_page()
    try:
        await pg.goto(site, timeout=25000, wait_until="domcontentloaded")
        await pg.wait_for_timeout(1200)
        out["status"] = "ok"
        top_html = await pg.content()
        text = re.sub(r"<[^>]+>", " ", top_html)
        if NO_SALES_RE.search(text):
            out["no_sales"] = True
        for m in EMAIL_RE.finditer(text):
            a = m.group(0).lower()
            if a not in [e["address"] for e in out["emails"]]:
                out["emails"].append({"address": a, "kind": "generic" if a.split("@")[0] in ("info", "contact", "mail", "office", "support", "inquiry") else "personal"})
        ig = re.search(r"https?://(?:www\.)?instagram\.com/[A-Za-z0-9_.]+", top_html)
        out["instagram"] = ig.group(0) if ig else None
        ln = re.search(r"https?://lin\.ee/[A-Za-z0-9]+", top_html)
        out["line"] = ln.group(0) if ln else None

        # 問い合わせページの候補を集める（トップから同一ドメインのリンク）
        here = pg.url.split("/")[2] if "//" in pg.url else ""
        links = await pg.evaluate("""() => [...document.querySelectorAll('a[href]')].map(a => ({h: a.href, t: (a.innerText||'') + ' ' + a.href}))""")
        cands, seen = [], set()
        for a in links:
            h, t = a.get("h", ""), a.get("t", "")
            if not h.startswith("http") or "//" not in h or h.split("/")[2] != here:
                continue
            b = h.split("#")[0]
            if b in seen or b.lower().endswith(SKIP_EXT):
                continue
            if not CONTACT_RE.search(t):
                continue
            if WRONG_FORM_RE.search(t):
                continue
            seen.add(b)
            cands.append(b)
        cands = sorted(cands, key=lambda u: (0 if re.search(r"form|フォーム|contact", u, re.I) else 1))[:4]
        # トップ自体にフォームがあることもある
        for url in [pg.url] + cands:
            try:
                if url != pg.url:
                    await pg.goto(url, timeout=25000, wait_until="domcontentloaded")
                    await pg.wait_for_timeout(1200)
                h = await pg.content()
                t2 = re.sub(r"<[^>]+>", " ", h)
                if NO_SALES_RE.search(t2):
                    out["no_sales"] = True
                n_ta = len(await pg.query_selector_all("textarea"))
                for fr in pg.frames:
                    if fr == pg.main_frame:
                        continue
                    try:
                        n_ta += len(await fr.query_selector_all("textarea"))
                    except Exception:
                        pass
                for m in EMAIL_RE.finditer(t2):
                    a = m.group(0).lower()
                    if a not in [e["address"] for e in out["emails"]]:
                        out["emails"].append({"address": a, "kind": "generic" if a.split("@")[0] in ("info", "contact", "mail", "office", "support", "inquiry") else "personal"})
                if n_ta:
                    out["contact_form_url"] = pg.url.split("#")[0]
                    out["has_form"] = True
                    out["captcha"] = bool(re.search(r'recaptcha/api2/anchor(?![^"]*size=invisible)|hcaptcha\.com', h)) or bool(re.search(r"画像に表示|送信認証|認証コード", t2))
                    break
            except Exception:
                continue
    except Exception as e:
        out["status"] = type(e).__name__
    finally:
        await pg.close()
    return out


async def run(items: list, conc: int) -> list:
    from playwright.async_api import async_playwright
    res = []
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--no-sandbox"])
        ctx = await b.new_context(viewport={"width": 1200, "height": 900}, locale="ja-JP", ignore_https_errors=True,
                                  user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36")

        async def relay(route, request):
            # この環境の代理サーバーでは Chromium の直通が切られるので、Playwright の HTTP クライアントで中継する
            if request.resource_type in ("image", "media", "font"):
                await route.abort()
                return
            try:
                r = await route.fetch(max_redirects=5)
                await route.fulfill(response=r)
            except Exception:
                await route.abort()
        await ctx.route("**/*", relay)
        sem = asyncio.Semaphore(conc)
        done = [0]

        async def w(f):
            async with sem:
                r = await one(ctx, f)
                res.append(r)
                done[0] += 1
                if done[0] % 20 == 0:
                    print(f"  {done[0]}/{len(items)} 件（フォーム {sum(1 for x in res if x['has_form'])}／メール {sum(1 for x in res if x['emails'])}）", flush=True)
                return r
        await asyncio.gather(*[w(f) for f in items])
        await b.close()
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--n", type=int, default=0)
    ap.add_argument("--同時", dest="conc", type=int, default=4)
    a = ap.parse_args()
    src = pathlib.Path(a.src)
    items = json.loads(src.read_text(encoding="utf-8"))
    dst = src.with_name(src.stem + "-contacts.json")
    had = {c["id"]: c for c in (json.loads(dst.read_text(encoding="utf-8")) if dst.exists() else [])}
    todo = [f for f in items if f["id"] not in had]
    if a.n:
        todo = todo[:a.n]
    print(f"巡回 {len(todo)} 件（済 {len(had)}）")
    res = asyncio.run(run(todo, a.conc))
    had.update({r["id"]: r for r in res})
    dst.write_text(json.dumps(list(had.values()), ensure_ascii=False, indent=1), encoding="utf-8")
    ok = [r for r in res if r["has_form"] and not r["no_sales"]]
    print(f"書き出し: {dst}／フォームあり {sum(1 for r in res if r['has_form'])}・うち送れる {len(ok)}・メールあり {sum(1 for r in res if r['emails'])}・営業お断り {sum(1 for r in res if r['no_sales'])}")


if __name__ == "__main__":
    main()
