#!/usr/bin/env python3
"""バナー画像を実寸で書き出す。HTML/CSS で組んで Chromium で撮る。

【なぜこの形か】
  画像生成モデルに作らせると、文字がラスタに焼き付く。
  1文字直すのに全部作り直しになり、色も指定どおりに出ない。
  HTML で組めば、文字はベクタで正確、色は指定値そのもの、
  修正は1行の書き換えで済む。写真は実写を埋め込む。

  レントラックス提出用（300x250 / 250x250 / 200x200）。

【使い方】
  python3 tools/build-banners.py                 # 全サイズ書き出し
  python3 tools/build-banners.py --html-only     # HTMLだけ出して中身を見る

  出力先 assets/banners/
"""
import base64
import io
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PHOTOS = os.path.join(ROOT, 'assets', 'photos')
OUT = os.path.join(ROOT, 'assets', 'banners')

# ── 事実（勝手に変えないこと）─────────────────────────────
# 価格は lp/mizumawari/index.html と一致していること。
# 満足度は 98.6%（209名中206名／2023年1月〜2025年12月）。98.8% は使わない。
KAKAKU = '33,660'
MENU = '浴室＋キッチン'
SERVICE = 'クリーニング'
AREA = '東京・千葉・神奈川'
MANZOKU = '満足度 98.6%'
CTA = '詳しく見る'
BRAND = 'ONE HITTER'

# ── 色 ────────────────────────────────────────────────
NAVY = '#0D3B5C'
APRICOT = '#FFB894'
WHITE = '#FFFFFF'

# ── 写真（施工後の実写。ビフォーアフター風の生成画像は使わない）──
#
# ★お客様のご自宅なので、**私物が写っているものは使わない。**
#   シャンプー・育毛剤などの商品名が読めるカットが実際にある（IMG_7993 等）。
#   設備だけが写っているものに限る。
#
# (ファイル名, 横の寄せ 0=左 .5=中央 1=右, 縦の寄せ 0=上 .5=中央 1=下)
SHASHIN = {
    'yokushitsu': ('IMG_7987.jpg', 0.42, 0.62),   # 浴室アフター。下寄せで浴槽の縁と床を入れる
    'kitchen':    ('IMG_7985.jpg', 0.34, 0.42),   # シンクアフター。右端の水切りカゴを外す
}


def kiritori(key, w, h):
    """写真を指定の寸法へ、比率を保ったままトリミングして data URI にする"""
    from PIL import Image
    name, bx, by = SHASHIN[key]
    im = Image.open(os.path.join(PHOTOS, name)).convert('RGB')
    sw, sh = im.size
    # 収めるのではなく覆う（余白を作らない）
    scale = max(w / sw, h / sh)
    nw, nh = int(sw * scale + 0.5), int(sh * scale + 0.5)
    im = im.resize((nw, nh), Image.LANCZOS)
    left = int((nw - w) * bx + 0.5)
    top = int((nh - h) * by + 0.5)
    im = im.crop((left, top, left + w, top + h))
    buf = io.BytesIO()
    im.save(buf, 'JPEG', quality=88)
    return 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()


def shashin_ban(w, h, futatsu=True):
    """写真の帯。2枚並べると「浴室＋キッチン」のセットが絵で伝わる"""
    if futatsu:
        hw = w // 2
        a = kiritori('yokushitsu', hw, h)
        b = kiritori('kitchen', w - hw, h)
        return (
            f'<div class="ph" style="height:{h}px">'
            f'<img src="{a}" style="width:{hw}px;height:{h}px">'
            f'<img src="{b}" style="width:{w - hw}px;height:{h}px">'
            f'</div>'
        )
    a = kiritori('yokushitsu', w, h)
    return f'<div class="ph" style="height:{h}px"><img src="{a}" style="width:{w}px;height:{h}px"></div>'


KYOTSU_CSS = f"""
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{background:{NAVY}}}
body{{font-family:"IPAPGothic","IPAGothic",sans-serif;-webkit-font-smoothing:antialiased}}
.b{{position:relative;overflow:hidden;background:{NAVY}}}
.ph{{display:flex;width:100%;overflow:hidden}}
.ph img{{object-fit:cover;display:block}}
.brand{{color:{WHITE};font-weight:bold;letter-spacing:.18em;opacity:.92}}
.menu{{color:{WHITE};font-weight:bold;line-height:1.15}}
.svc{{color:{APRICOT};font-weight:bold}}
/* 数字は Liberation Sans。IPAGothic のカンマは幅が広く「33, 660」に見える */
.kakaku{{color:{APRICOT};font-weight:bold;line-height:1;
        font-family:"Liberation Sans","DejaVu Sans",sans-serif;letter-spacing:-.005em}}
.en{{color:{APRICOT};font-weight:bold}}
.zei{{color:{WHITE};opacity:.85;font-weight:bold}}
.sub{{color:{WHITE};opacity:.85}}
.cta{{background:{APRICOT};color:{NAVY};font-weight:bold;border-radius:999px;
     display:flex;align-items:center;justify-content:center;white-space:nowrap}}
"""


def banner_300x250():
    ph = shashin_ban(300, 104, futatsu=True)
    return f"""<!doctype html><meta charset="utf-8"><style>{KYOTSU_CSS}
.b{{width:300px;height:250px}}
.body{{padding:11px 14px 0}}
.brand{{font-size:10px}}
.menu{{font-size:19px;margin-top:6px}}
.svc{{font-size:13px}}
.kakaku{{font-size:38px;margin-top:5px;display:inline-block;vertical-align:-2px}}
.en{{font-size:20px}}
.zei{{font-size:11px}}
.foot{{position:absolute;left:14px;right:12px;bottom:11px;
      display:flex;align-items:center;justify-content:space-between}}
.sub{{font-size:9.5px;line-height:1.45}}
.cta{{width:104px;height:31px;font-size:13px}}
</style><div class="b">{ph}<div class="body">
<div class="brand">{BRAND}</div>
<div class="menu">{MENU}<span class="svc"> {SERVICE}</span></div>
<div><span class="kakaku">{KAKAKU}</span><span class="en">円</span><span class="zei">（税込）</span></div>
</div><div class="foot"><div class="sub">{AREA}<br>{MANZOKU}</div>
<div class="cta">{CTA}</div></div></div>"""


def banner_250x250():
    ph = shashin_ban(250, 92, futatsu=True)
    return f"""<!doctype html><meta charset="utf-8"><style>{KYOTSU_CSS}
.b{{width:250px;height:250px}}
.body{{padding:11px 14px 0;text-align:center}}
.brand{{font-size:9.5px}}
.menu{{font-size:17px;margin-top:6px}}
.svc{{font-size:12px}}
.kakaku{{font-size:36px;margin-top:4px;display:inline-block;vertical-align:-2px}}
.en{{font-size:19px}}
.zei{{font-size:10.5px}}
.foot{{position:absolute;left:14px;right:14px;bottom:12px;text-align:center}}
.sub{{font-size:9.5px;margin-bottom:7px}}
.cta{{width:150px;height:31px;font-size:13px;margin:0 auto}}
</style><div class="b">{ph}<div class="body">
<div class="brand">{BRAND}</div>
<div class="menu">{MENU}<span class="svc"> {SERVICE}</span></div>
<div><span class="kakaku">{KAKAKU}</span><span class="en">円</span><span class="zei">（税込）</span></div>
</div><div class="foot"><div class="sub">{AREA} ／ {MANZOKU}</div>
<div class="cta">{CTA}</div></div></div>"""


def banner_200x200():
    ph = shashin_ban(200, 70, futatsu=True)
    return f"""<!doctype html><meta charset="utf-8"><style>{KYOTSU_CSS}
.b{{width:200px;height:200px}}
.body{{padding:9px 11px 0;text-align:center}}
.brand{{font-size:8.5px}}
.menu{{font-size:14px;margin-top:5px}}
.svc{{font-size:10px}}
.kakaku{{font-size:29px;margin-top:3px;display:inline-block;vertical-align:-2px}}
.en{{font-size:15px}}
.zei{{font-size:9px}}
.foot{{position:absolute;left:11px;right:11px;bottom:9px;text-align:center}}
.sub{{font-size:8px;margin-bottom:5px}}
.cta{{width:122px;height:26px;font-size:11.5px;margin:0 auto}}
</style><div class="b">{ph}<div class="body">
<div class="brand">{BRAND}</div>
<div class="menu">{MENU}<span class="svc"> {SERVICE}</span></div>
<div><span class="kakaku">{KAKAKU}</span><span class="en">円</span><span class="zei">（税込）</span></div>
</div><div class="foot"><div class="sub">{AREA}<br>{MANZOKU}</div>
<div class="cta">{CTA}</div></div></div>"""


SIZES = [
    (300, 250, banner_300x250),
    (250, 250, banner_250x250),
    (200, 200, banner_200x200),
]


def main():
    os.makedirs(OUT, exist_ok=True)
    html_only = '--html-only' in sys.argv

    from playwright.sync_api import sync_playwright
    chrome = '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'

    htmls = []
    for w, h, fn in SIZES:
        p = os.path.join(OUT, f'_src-{w}x{h}.html')
        with open(p, 'w', encoding='utf-8') as f:
            f.write(fn())
        htmls.append((w, h, p))
        print(f'HTML  {w}x{h}  {p}')

    if html_only:
        return

    with sync_playwright() as pw:
        br = pw.chromium.launch(executable_path=chrome, args=['--force-device-scale-factor=1'])
        for w, h, p in htmls:
            pg = br.new_page(viewport={'width': w, 'height': h}, device_scale_factor=1)
            pg.goto('file://' + p)
            pg.wait_for_timeout(250)
            out = os.path.join(OUT, f'ONE-HITTER-{w}x{h}.png')
            pg.screenshot(path=out)
            pg.close()
            sz = os.path.getsize(out)
            print(f'PNG   {w}x{h}  {out}  {sz:,} bytes')
        br.close()

    # 実寸を機械で確かめる。目で見て終わりにしない
    print('\n--- 書き出した実寸 ---')
    from PIL import Image
    ng = 0
    for w, h, _ in SIZES:
        f = os.path.join(OUT, f'ONE-HITTER-{w}x{h}.png')
        gw, gh = Image.open(f).size
        ok = (gw, gh) == (w, h)
        if not ok:
            ng += 1
        print(f'  {os.path.basename(f)}  {gw}x{gh}  {"OK" if ok else "★寸法が違う"}')
    if ng:
        sys.exit(1)


if __name__ == '__main__':
    main()
