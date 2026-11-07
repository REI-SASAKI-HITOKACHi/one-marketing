#!/usr/bin/env python3
"""デザイン②「写真が主役」（C案）エアコンLPの下書きを作る・点検する（未配信）。

    python3 deploy/machi/design2/aircon-shashin/tsukuru.py          # index.html と img/ を作り、点検する
    python3 deploy/machi/design2/aircon-shashin/tsukuru.py --check  # 作らずに点検だけ

- 見た目と並べ方は _katachi.html（このフォルダ）。index.html は手で直さない（作り直すと消える）
- 計測・料金計算・フォームのスクリプトは、デザイン①の強化の下書き deploy/machi/kyouka/aircon-c/index.html から
  そのまま切り出して入れる（同じ物を二重に持たない）。①を作り直したら、これも作り直す
- 写真は下の WAKU（枠の名前 → 今入れているファイル）。差し替えは shashin-waku.md
- 変えるのは SLUG・VARIANT・LABEL の3つだけ（判定表は measurement の持ち物なので、値が決まったらここで直して作り直す）
"""
import html.parser
import json
import pathlib
import re
import shutil
import sys
import urllib.parse

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[3]
MOTO = ROOT / "deploy" / "machi" / "kyouka" / "aircon-c" / "index.html"   # デザイン①（強化の下書き）

# ---- ここだけ変える ------------------------------------------------------------
SLUG = "aircon-shashin"      # 配信するディレクトリ名（/aircon-shashin/）。フォーム名・送信先・予約ページへの lp= に使う
VARIANT = "shashin"          # GA4 の lp_variant（OH_M の1か所。gtag の config はそこを読む）
LABEL = "デザイン②写真"       # 通知メールの件名・申込内容のまとめに出る名前
# -------------------------------------------------------------------------------

# 写真の枠：枠の名前 → (書き出すファイル名, 今入れている元のファイル)。並べてよい前後の組は (mae, ato) が同じ物と確かめたものだけ
WAKU = {
    "hero":    [("hero.jpg", "assets/photos-design2/hero-ph445.jpg")],   # 仕分け表 ph-445（IMG_7716・2026-08-24・吹出口の黒カビ・施工前・縦）
    "vent-ba": [("vent-mae.jpg", "lp/nenmatsu/img/ac-vent-before.jpg"), ("vent-ato.jpg", "lp/nenmatsu/img/ac-vent-after.jpg")],
    "fin-ba":  [("fin-mae.jpg", "deploy/machi/kyouka/aircon-c/img/fin-before.jpg"), ("fin-ato.jpg", "deploy/machi/kyouka/aircon-c/img/fin-after.jpg")],
    "osui":    [("osui.jpg", "assets/photos-design2/osui-J22-01.jpg")],   # 棚 J22-01（2026-10-30・汚水）
    "sagyou":  [("sagyou.jpg", "assets/photos-design2/sagyou-J23-38.jpg")],   # 棚 J23-38（2026-10-31・洗い流した直後のルーバー）
    "og":      [("og.jpg", "deploy/machi/kyouka/aircon-c/img/og.jpg")],
    "tantou-e": [("staff.jpg", "lp/_staff/staff.jpg")],   # 担当のイラスト（置き場所は1か所）
}

KIERU = "Date.UTC(2026, 10, 30, 15, 0, 0)"


def kiridasu(s, start, end, name):
    """start から end まで（両方含む）を1つだけ切り出す。見つからない・2つ以上なら止める"""
    if s.count(start) != 1:
        sys.exit(f"[{name}] 元の下書きに {start[:60]!r} が {s.count(start)} か所（1か所のはず）。止めます")
    i = s.index(start)
    j = s.index(end, i) + len(end)
    return s[i:j]


def kaeru(s, old, new, name, count=1):
    if s.count(old) != count:
        sys.exit(f"[{name}] {old[:70]!r} が {s.count(old)} か所（{count} か所のはず）。止めます")
    return s.replace(old, new)


def bubun(moto):
    head = kiridasu(moto, "<!-- ONE HITTER 計測タグ -->", "gtag('config','AW-18450975194');\n</script>", "計測タグ")
    head = kaeru(head, '"lp_variant":"C"', f'"lp_variant":"{VARIANT}"', "計測タグ")
    # gtag の config も OH_M の値を読む（lp_variant を1か所で変えられるように）
    head = kaeru(head, "'lp_variant':'C'", "'lp_variant':window.OH_M.page.lp_variant", "計測タグ")
    nov = kiridasu(moto, "<script>\n(function(){\n  var band = document.getElementById('nov-band');", "})();\n</script>", "11月の帯")
    hero = kiridasu(moto, "<script>\n/* LP強化（tools/kyouka-1101.py）。1画面目を", "window.ohKyouka();\n</script>", "季節の見出し")
    i = moto.index("<script>\n(function(){\n  var fmt = function(n)")
    j = moto.rindex("</body>")
    hontai = moto[i:j].rstrip() + "\n"
    hontai = kaeru(hontai, "var hikitsugu = { lp: 'aircon-c',", f"var hikitsugu = {{ lp: '{SLUG}',", "引き継ぎ")
    hontai = kaeru(hontai, "-aircon-c-'", f"-{SLUG}-'", "受付番号")
    hontai = kaeru(hontai, "LABEL = 'エアコンLP（学習版C）'", f"LABEL = 'エアコンLP（{LABEL}）'", "申込内容のまとめ")
    return head, nov, hero, hontai


class Ji(html.parser.HTMLParser):
    """見出しの書体（Noto Sans JP 900）で出る字を集める"""
    KLS = {"btn", "oo", "v", "ic", "call", "go", "tot"}

    def __init__(self):
        super().__init__()
        self.st, self.ji = [], set()

    def handle_starttag(self, tag, a):
        if tag in ("br", "img", "input", "meta", "link"):
            return
        kls = set((dict(a).get("class") or "").split())
        on = tag in ("h1", "h2") or bool(kls & self.KLS) or (tag == "button" and not kls) or (bool(self.st) and self.st[-1])
        self.st.append(on)

    def handle_endtag(self, tag):
        if tag in ("br", "img", "input", "meta", "link"):
            return
        if self.st:
            self.st.pop()

    def handle_data(self, d):
        if self.st and self.st[-1]:
            self.ji.update(c for c in d if not c.isspace())


def font_url(html_text, hero_script):
    p = Ji()
    p.feed(re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html_text, flags=re.S))
    ji = set(p.ji)
    # 季節で入れ替わる見出し（JS が入れる）の字も入れる
    m = re.search(r"var C = (\{.*?\});\n", hero_script)
    for v in json.loads(m.group(1))["v"].values():
        for k in ("hero-h1",):
            ji.update(c for c in re.sub(r"<[^>]+>", "", v.get(k, "")) if not c.isspace())
    ji.update("0123456789,.%円台＋+−-／")   # 計算機の金額・工程の番号
    text = "".join(sorted(ji))
    return ("https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@900&amp;text="
            + urllib.parse.quote(text, safe="") + "&amp;display=swap"), len(text)


def tsukuru():
    moto = MOTO.read_text(encoding="utf-8")
    head, nov, hero, hontai = bubun(moto)
    h = (HERE / "_katachi.html").read_text(encoding="utf-8")
    h = h.replace("{{SLUG}}", SLUG).replace("{{LABEL}}", LABEL)
    h = h.replace("{{KEISOKU_HEAD}}", head).replace("{{NOV_SCRIPT}}", nov).replace("{{HERO_SCRIPT}}", hero)
    h = h.replace("{{HONTAI_SCRIPTS}}", hontai)
    url, n = font_url(h, hero)
    h = h.replace("{{FONT_URL}}", url)
    if "{{" in h:
        sys.exit("置き換え忘れ：" + re.search(r"\{\{[A-Z_]+\}\}", h).group(0))
    (HERE / "index.html").write_text(h, encoding="utf-8")
    img = HERE / "img"
    img.mkdir(exist_ok=True)
    for waku, fs in WAKU.items():
        for out, src in fs:
            shutil.copyfile(ROOT / src, img / out)
    print(f"書き出しました: {HERE / 'index.html'}（{len(h.encode()) // 1024}KB・見出しの字 {n} 字）")


# ---------------------------------------------------------------------------------
# 点検：①（強化の下書き）と、計測・フォームの仕組みが同じか。原稿の決まりに反していないか
# ---------------------------------------------------------------------------------
def seiki(s):
    """①と②で違ってよい所（ディレクトリ名・版・件名）をそろえてから比べる"""
    s = s.replace(SLUG, "aircon-c").replace(f'"lp_variant":"{VARIANT}"', '"lp_variant":"C"')
    s = s.replace("'lp_variant':window.OH_M.page.lp_variant", "'lp_variant':'C'")
    s = s.replace(f"エアコン（{LABEL}）", "エアコン（学習版C）").replace(f"エアコンLP（{LABEL}）", "エアコンLP（学習版C）")
    return s


def tenken():
    a = MOTO.read_text(encoding="utf-8")
    b0 = (HERE / "index.html").read_text(encoding="utf-8")
    b = seiki(b0)
    ng, kekka = [], []
    oh = lambda s: json.loads(re.search(r"window\.OH_M=(\{.*?\});</script>", s).group(1))
    if oh(a) != oh(b):
        ng.append("OH_M が lp_variant 以外でも違う")
    kekka.append(f"OH_M：lp_variant だけ違う（C → {oh(b0)['page']['lp_variant']}）")
    for pat, nm in [(r"gtag\('config'[^\n]*", "gtag の config"), (r'<input type="hidden"[^>]*>', "hidden 欄"),
                    (r'\bname="[^"]+"', "name 属性"), (r"<form [^>]*>", "form の開始タグ"),
                    (r"data-netlify=\"true\"|netlify-honeypot=\"[^\"]+\"", "Netlify Forms の属性")]:
        x, y = sorted(re.findall(pat, a)), sorted(re.findall(pat, b))
        (kekka if x == y else ng).append(f"{nm}：①{len(x)}・②{len(y)}" + ("（同じ）" if x == y else "（違う）"))
    # スクリプトの中身（計測・計算・フォーム）は①から切り出したもの。同じか
    sc = lambda s: [m for m in re.findall(r"<script[^>]*>.*?</script>", s, re.S) if "data-oh=\"shashin\"" not in m]
    x, y = sc(a), sc(b)
    kekka.append(f"script：①から切り出した {len(y)} 本が①の {len(x)} 本と中身まで同じ（②はこのほかに切り替え・no-js の2本だけ）" if sorted(x) == sorted(y) else "script：違う")
    if sorted(x) != sorted(y):
        diff = [s[:80] for s in set(x) ^ set(y)]
        ng.append("①と中身が違う script がある：" + " / ".join(diff))
    for k in ["send('generate_lead'", "send('phone_click'", "send('form_submit'", "send('form_start'", "send('cta_click'",
              "send('estimate_use'", "send('area_check'", "send('scroll_depth'", "'line_click'",
              "data-oh=\"moushikomi\"", "送信元の確認", "'cta_click', p"]:
        if a.count(k) != b.count(k):
            ng.append(f"{k} の数が違う（①{a.count(k)}・②{b.count(k)}）")
    kekka.append("send(...) の呼び出し・申込内容のまとめ・送信元の確認：数が同じ" if not any("の数が違う" in x for x in ng) else "send の数が違う")
    pl = lambda s: sorted(re.findall(r'data-yoyaku data-place="([^"]+)"', s))
    (kekka if pl(a) == pl(b) else ng).append(f"予約ボタン（data-yoyaku）の場所：①{pl(a)}・②{pl(b)}")
    body = lambda s: s[s.index("<body>"):]
    for nm, pat in [("tel: のリンク", r'href="tel:'), ("LINE のリンク", r'href="https://lin\.ee/'), ("#form へのリンク", r'href="#form"'), ("#rei へのリンク", r'href="#rei"')]:
        kekka.append(f"{nm}：①{len(re.findall(pat, body(a)))}・②{len(re.findall(pat, body(b)))}")
    for sel in ['class="sticky"', 'class="bar"', 'class="hero"', 'id="form"', 'class="calc"', "<footer"]:
        if sel not in b:
            ng.append(f"events.js の場所の判定に使う {sel} が無い")
    for i in ["total", "breakdown", "shindan", "shindan-res", "zipbtn", "zipin", "zipres", "hero-perk", "h-src", "h-cid", "h-ag",
              "soudan", "peak-now", "nov-band", "nov-link", "nov-price", "nov-rei", "hero-h1", "hero-sub", "hero-area", "simulator", "rei", "qty"]:
        if f'id="{i}"' not in b:
            ng.append(f'スクリプトが使う id="{i}" が無い')
    if b.count(KIERU) != a.count(KIERU):
        ng.append(f"12/1 に消す仕組み（{KIERU}）の数が違う（①{a.count(KIERU)}・②{b.count(KIERU)}）")
    # 原稿の決まり
    txt = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", b0, flags=re.S)
    txt = re.sub(r"<!--.*?-->", "", txt, flags=re.S)
    for w in ["98.8", "出張費無料", "一切", "完全分解", "背抜き", "ファンを外", "ファンを取り外", "今だけ", "先着", "No.1", "件の", "バケツ"]:
        if w in txt:
            ng.append(f"使わない言い方「{w}」が本文にある")
    for tel in set(re.findall(r"0\d{1,3}-\d{2,4}-\d{4}", txt)):
        if tel != "080-8043-8259":
            ng.append(f"電話番号 {tel}")
    if "98.6%" not in txt or "勧めてもよい" not in txt:
        ng.append("98.6% と「勧めてもよい」が無い")
    # 字の大きさ（CSS）：12px 未満が無いか・段階の数
    css = "".join(re.findall(r"<style>(.*?)</style>", b0, re.S))
    px = sorted({float(x) for x in re.findall(r"font-size:\s*([0-9.]+)px", css)} |
                {float(x) for x in re.findall(r"--fs-\d:\s*([0-9.]+)px", css)})
    if any(x < 12 for x in px):
        ng.append(f"12px 未満の字がある：{px}")
    kekka.append(f"CSS の字の大きさ：{[int(x) if x.is_integer() else x for x in px]}px（スマホ 13/15/17/20/24/28・PC は 24→34, 28→44。見出し1は幅 389px 未満で少し縮む）")
    # 前後の組（並べてよいのは確かめた組だけ）
    pairs = re.findall(r'<img class="mae" src="img/([^"]+)".*?<img class="ato" src="img/([^"]+)"', b0, re.S)
    ok_pairs = {("vent-mae.jpg", "vent-ato.jpg"), ("fin-mae.jpg", "fin-ato.jpg")}
    for p in pairs:
        if p not in ok_pairs:
            ng.append(f"確かめていない前後の組 {p}")
    kekka.append(f"前後の組：{pairs}")
    for p in ["fan-after", "outlet-after", "hood-after"]:
        if p in b0:
            ng.append(f"{p} が入っている（同じ物と確かめていない組の片方）")
    # 写真に EXIF が残っていないか
    try:
        from PIL import Image
        for waku, fs in WAKU.items():
            for out, _ in fs:
                im = Image.open(HERE / "img" / out)
                if len(im.getexif()):
                    ng.append(f"img/{out} に EXIF が残っている")
    except ImportError:
        kekka.append("（PIL が無いので EXIF は見ていない）")
    return kekka, ng


if __name__ == "__main__":
    if "--check" not in sys.argv:
        tsukuru()
    kekka, ng = tenken()
    for k in kekka:
        print("  ・" + k)
    for x in ng:
        print("  NG " + x)
    print("点検：" + ("NG あり" if ng else "OK"))
    sys.exit(1 if ng else 0)
