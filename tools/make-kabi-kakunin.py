#!/usr/bin/env python3
"""カビ特化LP /kabi/ のオーナー確認用の1枚（スマホ幅の画面写し＋全文＋広告の見出し案）を作る（依頼 20261016-06-lp）。

    python3 tools/make-kabi-kakunin.py      # preview/kabi/ を読んで docs/提示-カビLP-嶺さん.html を書き出す

- preview/kabi/ は tools/make-kabi.py が作ったもの。lp.onehitter.jp/kabi/ として読み込み、空き枠は本番の slots.json を使う
- GA4・広告の送信は止めて写す（数字を汚さない）
- 画像は HTML に埋め込む（右ウィンドウで1枚で開けるように）
- 広告文は measurement の docs/提示-カビ広告文-学習後.html（claude/measurement-ga4-calltracking）から読む（見出し・説明文の表と、検索結果の見え方）
"""
import base64, html, io, os, pathlib, re, subprocess, sys
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "提示-カビLP-嶺さん.html"
W, H = 390, 844


def handler_for(route):
    u = route.request.url.split("#")[0].split("?")[0].replace("https://lp.onehitter.jp/", "")
    f = (ROOT / "preview" / (u + "index.html")) if u.endswith("/") else (ROOT / "preview" / u)
    if not f.exists():
        f = ROOT / "deploy" / "netlify" / u
    route.fulfill(path=str(f)) if f.exists() else route.fulfill(status=404, body="")


def shoot():
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", proxy={"server": os.environ["HTTPS_PROXY"]},
                              args=["--no-sandbox", "--disable-dev-shm-usage", "--ssl-version-max=tls1.2", "--disable-quic"])
        c = b.new_context(viewport={"width": W, "height": H}, device_scale_factor=2)
        pg = c.new_page()
        pg.route(re.compile(r".*(google-analytics|googletagmanager|googleadservices|doubleclick|google\.com/(ccm|rmkt)).*"),
                 lambda r: r.abort())
        pg.route("https://lp.onehitter.jp/**", handler_for)
        pg.goto("https://lp.onehitter.jp/kabi/?src=gads_kabi&cid=kakunin")
        pg.wait_for_function("!document.getElementById('aki').hidden", timeout=20000)
        pg.wait_for_timeout(500)
        first = pg.screenshot()
        for el in pg.query_selector_all("img[loading=lazy]"):
            el.scroll_into_view_if_needed()
        pg.wait_for_timeout(1500)
        pg.add_style_tag(content=".sticky,[class*='sticky'],.fixbar{position:static!important}")
        pg.evaluate("window.scrollTo(0,0)")
        full = pg.screenshot(full_page=True)
        # 全文：画面に出る順に、見出しごと
        text = pg.evaluate("""() => {
          const out = []; const seen = new Set();
          document.querySelectorAll('h1,h2,h3,p,li,.v,.k,.big,.note,blockquote,figcaption,.btn,label,summary,dt,dd,td,th').forEach(e => {
            const r = e.getBoundingClientRect(); if (r.height === 0) return;
            if (e.closest('form') && !/^(H2|H3|P)$/.test(e.tagName)) return;
            const t = e.innerText.replace(/\\s+/g, ' ').trim(); if (!t || seen.has(t)) return;
            for (const s of seen) { if (s.includes(t) && t.length < 40) return; }
            seen.add(t); out.push([e.tagName, t]);
          });
          return out; }""")
        chips = pg.evaluate("[...document.querySelectorAll('.aki-chip')].map(a=>a.innerText.replace(/\\n/,' '))")
        b.close()
    return first, full, text, chips


def jpeg(img: Image.Image, width=585, q=72) -> str:
    img = img.convert("RGB")
    img = img.resize((width, int(img.height * width / img.width)))
    buf = io.BytesIO(); img.save(buf, "JPEG", quality=q, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def koukoku():
    """measurement の docs/提示-カビ広告文-学習後.html から、検索結果の見え方・見出し・説明文を読む。"""
    try:
        h = subprocess.run(["git", "-c", "core.quotepath=off", "show",
                            "origin/claude/measurement-ga4-calltracking:docs/提示-カビ広告文-学習後.html"],
                           cwd=ROOT, capture_output=True, text=True, check=True).stdout
    except subprocess.CalledProcessError:
        return [], [], []
    cards = re.findall(r'<div class="t">(.*?)</div>\s*<div class="d">(.*?)</div>', h, re.S)
    tables = re.findall(r'<table>(.*?)</table>', h, re.S)
    out = []
    for t in tables[:2]:
        out.append([[html.unescape(re.sub(r'<[^>]+>', '', c)).strip() for c in r]
                    for r in (re.findall(r'<td[^>]*>(.*?)</td>', x, re.S) for x in re.findall(r'<tr>(.*?)</tr>', t, re.S)) if r])
    while len(out) < 2:
        out.append([])
    cards = [(html.unescape(re.sub(r'<[^>]+>', '', a)).strip(), html.unescape(re.sub(r'<[^>]+>', '', b)).strip()) for a, b in cards]
    return cards, out[0], out[1]


def main():
    first, full, text, chips = shoot()
    fi = Image.open(io.BytesIO(first)); fu = Image.open(io.BytesIO(full))
    step = H * 2
    panels = [jpeg(fu.crop((0, y, fu.width, min(y + step, fu.height)))) for y in range(0, fu.height, step)]
    cards, heads, descs = koukoku()
    esc = html.escape
    body_text = "\n".join(
        (f"<h4>{esc(t)}</h4>" if tag in ("H1", "H2") else f"<p class='t-{tag.lower()}'>{esc(t)}</p>") for tag, t in text)
    tr = lambda rows: "".join("<tr>" + "".join(f"<td{' class=num' if i == len(r) - 1 else ''}>{esc(c)}</td>" for i, c in enumerate(r)) + "</tr>" for r in rows)
    serp = "".join(f'<div class="serp"><div class="u">スポンサー ・ lp.onehitter.jp/kabi/</div><div class="st">{esc(t)}</div><div class="sd">{esc(d)}</div></div>'
                   for t, d in cards)
    kensaku = [k for k in ("臭い", "臭") if any(k in r[1] for r in heads if len(r) > 1)]
    page = f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>カビ特化LP 確認用</title>
<style>
:root{{color-scheme:light;--ink:#0D3B5C;--text:#13232E;--sub:#536A78;--rule:#D7E1E7;--paper:#F6F8FA;--cta:#C0300C;}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--paper);color:var(--text);font:15px/1.8 "Noto Sans JP","Hiragino Sans",system-ui,sans-serif}}
header{{background:var(--ink);color:#fff;padding:16px 20px}} header h1{{margin:0;font-size:19px}} header p{{margin:4px 0 0;font-size:13px;opacity:.85}}
main{{max-width:1180px;margin:0 auto;padding:18px 16px 60px}}
section{{background:#fff;border:1px solid var(--rule);border-radius:10px;padding:16px 18px;margin:0 0 18px}}
h2{{font-size:17px;margin:0 0 10px;color:var(--ink)}} h4{{font-size:15px;margin:16px 0 4px;color:var(--ink)}}
.points li{{margin:2px 0}} .shots{{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:12px}}
.shots figure{{margin:0}} .shots img{{width:100%;display:block;border:1px solid var(--rule);border-radius:8px}}
.shots figcaption{{font-size:12px;color:var(--sub);text-align:center}}
table{{border-collapse:collapse;width:100%;font-size:14px}} td,th{{border-top:1px solid var(--rule);padding:6px 8px;text-align:left;vertical-align:top}}
.num{{text-align:right;font-variant-numeric:tabular-nums}} .t-li::before{{content:"・"}} .t-p,.t-li{{margin:2px 0}}
.zen{{columns:2 340px;column-gap:28px}}
.serp{{border:1px solid var(--rule);border-radius:8px;padding:10px 12px;margin:8px 0;max-width:640px}} .serp .u{{font-size:12px;color:var(--sub)}} .serp .st{{color:#1a0dab;font-size:17px;line-height:1.4}} .serp .sd{{font-size:14px}}
.note{{font-size:13px;background:#FFF8E6;border:1px solid #F0D9A0;border-radius:6px;padding:8px 10px}} .zen h4{{break-after:avoid}} .warn{{color:var(--cta);font-weight:700}}
</style></head><body>
<header><h1>カビ特化LP（/kabi/）確認用</h1><p>2026-10-16 作成・LP担当。まだ配信していません。オーナーの合格後に配信します。</p></header>
<main>
<section><h2>このLPの作り</h2><ul class="points">
<li>土台は学習後のクリエイティブ（学習版 /aircon-c/ ＋ /aircon-e/ の「いちばん早い空き3日」）。C対Eのテストとは別のURL（https://lp.onehitter.jp/kabi/）</li>
<li>見出しは検索語「エアコン 臭い」「暖房 臭い」に合わせた：<b>「暖房をつけたら、エアコンが臭い。」</b></li>
<li>季節の節「この秋、伺う現場で多いこと」＝和真さんの現場の声（長雨のあと、送風ファンや熱交換器の奥にカビが残っているエアコンが多い・暖房に切り替えた最初の日のにおい）</li>
<li>料金は10/16 訂正後（防カビコート 3,300円・室外機セット 5,500円 など）。「消えます」「除菌100%」などの言い切り、背抜き・完全分解の約束は書いていない</li>
<li>主ボタンと日付ボタンは予約ページへ直行（どのLPから来たか lp=kabi、広告の src=gads_kabi を引き継ぐ）。計測は他のLPと同じ（lp_id=kabi）</li>
<li>写しの日の空き：{esc(' ／ '.join(chips))}（本番の空き枠から自動で出る）</li>
<li class="warn">確認してほしいこと：見出しの言い方／季節の節の言い方（和真さんの言葉として出してよいか）／写真（送風ファン・熱交換器・吹き出し口の施工前後）</li>
</ul></section>
<section><h2>スマホで見た画面（上から順に）</h2><div class="shots">
<figure><img src="{jpeg(fi)}" alt="最初の画面"><figcaption>最初の画面（下の固定バーつき）</figcaption></figure>
{''.join(f'<figure><img src="{u}" alt="{i+1}画面目"><figcaption>{i+1}画面目</figcaption></figure>' for i, u in enumerate(panels))}
</div></section>
<section><h2>広告文（計測担当 作成・下書き）</h2>
<p style="font-size:13px;color:var(--sub);margin-top:0">出典：計測担当 docs/提示-カビ広告文-学習後.html（広告グループ A2_エアコン臭い）。リンク先はこの LP（/kabi/）。</p>
<h4>検索結果での見え方（例）</h4>{serp}
<p style="font-size:12px;color:var(--sub)">Google が組み合わせを自動で選ぶので、毎回この並びにはなりません。</p>
<h4>見出し（{len(heads)}本・半角30文字まで）</h4>
<table><tr><th>#</th><th>見出し</th><th>当てた学習</th><th class="num">文字数</th></tr>{tr(heads)}</table>
<h4>説明文（{len(descs)}本・半角90文字まで）</h4>
<table><tr><th>#</th><th>説明文</th><th>当てた学習</th><th class="num">文字数</th></tr>{tr(descs)}</table>
<p class="note">LP担当から一言：LP の見出しは「暖房をつけたら、エアコンが臭い。」です。見出し2の「LPの見出しと同じ言葉」は、もとになった学習版（/aircon-c/）の見出しのことです。検索語「エアコン 臭い」「暖房 臭い」をそのまま含む見出しを1本足すなら、たとえば「暖房をつけたらエアコンが臭い」（28/30）。</p>
</section>
<section><h2>全文</h2><div class="zen">{body_text}</div></section>
</main></body></html>"""
    OUT.write_text(page, encoding="utf-8")
    print(f"書き出しました: {OUT.relative_to(ROOT)}（{len(page)//1024}KB・画面 {len(panels)+1}枚）")


if __name__ == "__main__":
    main()
