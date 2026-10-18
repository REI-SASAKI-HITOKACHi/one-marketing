# -*- coding: utf-8 -*-
"""
ONE HITTER 下層ページの生成（2026-10-19 ブラウザ担当）

base.css と、このファイルの中のページ定義から、各ページの
1ファイル完結のHTMLを cms/<name>/prototype.html として書き出す。
オーナーがダブルクリックで開けるように、CSSは埋め込んでいる。

    py -X utf8 cms/site/build.py

CMSへ入れるときは base.css を外部CSSとして1本読ませ、
各ページは <body> の中身だけを入れればよい。
"""
import io, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
CSS = io.open(os.path.join(HERE, 'base.css'), encoding='utf-8').read()

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">\n'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
         '<link href="https://fonts.googleapis.com/css2?family=Shippori+Mincho:wght@400;600'
         '&family=Zen+Kaku+Gothic+New:wght@400;500;700&display=swap" rel="stylesheet">')

NAV = [('/menu/', 'メニュー'), ('/constructed/', '施工事例'), ('/voice/', 'お客様の声'),
       ('/blog/', 'ブログ'), ('/corporation/', '事業者の方')]

FOOT_NAV = [('/menu/', 'メニュー'), ('/constructed/', '施工事例'), ('/voice/', 'お客様の声'),
            ('/concept/', 'コンセプト'), ('/feature/', '特徴'), ('/blog/', 'ブログ'),
            ('/corporation/', '事業者の方'), ('/greeting/', '代表あいさつ'),
            ('/contact/', 'お問い合わせ'), ('/Other-businesses', 'その他事業'),
            ('/privacy_policy/', '個人情報の取扱い'), ('/sitemap/', 'サイトマップ')]

TEL = '080-8043-8259'
ADDR = '〒134-0081 東京都江戸川区北葛西5-14-11 クオーディア西葛西503'


def header(active, src):
    nav = '\n      '.join(
        '<a%s href="%s">%s</a>' % (' class="on"' if h == active else '', h, t)
        for h, t in NAV)
    return '''<header>
  <div class="in">
    <a class="logo" href="/"><span class="mk">ONE<br>HITTER</span>
      <span><b>ワンヒッター株式会社</b><small>HOUSE CLEANING SERVICE</small></span></a>
    <nav class="main">
      %s
    </nav>
    <a class="hbtn" href="https://yoyaku.onehitter.jp/?src=%s">空いている日を見る</a>
  </div>
</header>''' % (nav, src)


def phead(en, h1, lead, crumb, bg=None):
    bgtag = ('<div class="bg"><img alt="" src="%s"></div>' % bg) if bg else ''
    cls = 'phead' if bg else 'phead plain'
    leadp = ('\n    <p>%s</p>' % lead) if lead else ''
    return '''<div class="%s">
  %s
  <div class="in">
    <p class="crumb"><a href="/">ホーム</a>　›　%s</p>
    <span class="en">%s</span>
    <h1 class="mincho">%s</h1>%s
  </div>
</div>''' % (cls, bgtag, crumb, en, h1, leadp)


def cta(src, h2='空いている日を見て、<br>そのままご予約いただけます。',
        p='入力はおよそ1分。ご予約時のお支払いはありません。', second=('/menu/', '料金を見る')):
    return '''<section class="cta"><div class="wrap">
  <h2 class="mincho">%s</h2>
  <p>%s</p>
  <div class="acts">
    <a class="btn primary" href="https://yoyaku.onehitter.jp/?src=%s">空いている日を見る<span class="ar">→</span></a>
    <a class="btn ghost" href="%s">%s</a>
    <span class="tel">受付 8:00〜20:00<b>%s</b></span>
  </div>
</div></section>''' % (h2, p, src, second[0], second[1], TEL)


FOOTER = '''<footer><div class="in">
  <nav>%s</nav>
  <span>ワンヒッター株式会社　代表取締役 佐々木 沙樹　%s　TEL 080-8043-8259　対応エリア：東京都・千葉県・神奈川県</span>
</div></footer>''' % ('\n    '.join('<a href="%s">%s</a>' % (h, t) for h, t in FOOT_NAV), ADDR)


def page(out, title, body, note=''):
    html = '''<!doctype html>
<html lang="ja">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%s</title>
%s
<style>
%s</style>

%s
%s
%s''' % (title, FONTS, CSS, body, FOOTER, note)
    d = os.path.join(ROOT, 'cms', out)
    if not os.path.isdir(d):
        os.makedirs(d)
    p = os.path.join(d, 'prototype.html')
    io.open(p, 'w', encoding='utf-8', newline='').write(html + '\n')
    return p, len(html)


# =====================================================================
# メニュー別ページ（/feature/◯◯/）の中身
# 写真は自社の施工写真。浴室と水まわりは写真が無いのでイメージ（注記あり）
# =====================================================================
IMG = 'https://one-hitter.jp/_img/ja/article/%s/%s/800_533_2_ffffff//'
STOCK_BATH = 'https://images.unsplash.com/photo-1584622650111-993a426fbf0a?w=1400&q=80&auto=format&fit=crop'

PROOF = '''<div class="numband"><div class="in">
  <div class="c rv">
    <div class="n">98<span class="dec">.6</span><i>%</i></div>
    <div class="t">ご家族や友人に<br><b>勧めてもよい</b></div>
    <div class="sub">2023年1月〜2025年12月／回答209名中206名（自社アンケート）</div>
  </div>
  <div class="c rv">
    <div class="n"><span class="stars">★★★★★</span> 5.0</div>
    <div class="t">Googleクチコミ<br><b>25件すべてが★5</b></div>
    <div class="sub">2026年10月時点／★4以下は1件もありません</div>
  </div>
  <div class="c rv">
    <div class="n">0<i>円</i></div>
    <div class="t">お見積りのあとの<br><b>追加請求</b></div>
    <div class="sub">お出しした金額から増やしません</div>
  </div>
</div></div>'''


def ba(aid, alt_b, alt_a, cap):
    """ビフォー／アフターの2枚組（JSなし・ホバーとチェックで切替）"""
    return '''<div class="bawrap rv">
  <input type="checkbox" class="sw" id="sw%s">
  <div class="ba">
    <img src="%s" alt="%s">
    <img class="aft" src="%s" alt="%s">
    <span class="tagx"></span><label class="swlab" for="sw%s"></label>
  </div>
  <p class="cap">%s</p>
</div>''' % (aid, IMG % (aid, 'before'), alt_b, IMG % (aid, 'after'), alt_a, aid, cap)


BA_CSS = '''
.bawrap{margin:0}
.ba{position:relative;aspect-ratio:3/2;background:#e8e6e1;border-radius:3px;overflow:hidden}
.ba img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;transition:opacity .5s ease}
.ba .aft{opacity:0}
.bawrap:hover .ba .aft{opacity:1}
.ba .tagx{position:absolute;left:12px;top:12px;background:rgba(45,45,42,.82);color:#fff;
  font-size:10px;letter-spacing:.16em;padding:4px 11px;border-radius:999px;z-index:2;pointer-events:none}
.ba .tagx::after{content:"BEFORE"}
.bawrap:hover .ba .tagx{background:var(--red)}
.bawrap:hover .ba .tagx::after{content:"AFTER"}
.sw{position:absolute;opacity:0;width:0;height:0}
.ba .swlab{position:absolute;right:12px;bottom:12px;z-index:2;cursor:pointer;
  background:rgba(255,255,255,.92);border:1px solid var(--line);border-radius:999px;
  font-size:10.5px;letter-spacing:.12em;padding:6px 14px;transition:background .3s,color .3s}
.ba .swlab::after{content:"AFTERを見る"}
.ba .swlab:hover{background:var(--red);color:#fff;border-color:var(--red)}
.sw:checked + .ba .aft{opacity:1}
.sw:checked + .ba .tagx{background:var(--red)}
.sw:checked + .ba .tagx::after{content:"AFTER"}
.sw:checked + .ba .swlab::after{content:"BEFOREを見る"}
.bawrap .cap{margin:12px 0 0;font-size:12px;color:var(--mute);letter-spacing:.04em}
.price-row{display:flex;flex-wrap:wrap;align-items:baseline;gap:10px 20px;
  margin:28px 0 0;padding:20px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}
.price-row .nm{font-size:13.5px}
.price-row .yen{font-family:var(--mincho);font-size:28px;letter-spacing:.02em;white-space:nowrap}
.price-row .yen i{font-style:normal;font-size:.5em;margin-left:2px}
.price-row .mi{font-size:12px;color:var(--mute)}
.price-row .go{margin-left:auto}
@media(max-width:600px){.price-row .go{margin-left:0;width:100%}}
'''

# =====================================================================
#  ページ定義
#  本文は cms/site/bodies/<name>.html に置く（引用符の入れ子を避けるため）。
#  本文の中では次の差し込みが使える：
#     {{HEADER:<active>:<src>}}   ヘッダー
#     {{PHEAD:<en>|<h1>|<lead>|<crumb>|<bg>}}  ページの頭（bgは空でも可）
#     {{PROOF}}                   98.6%／★5.0／追加請求0円の帯
#     {{CTA:<src>}}               最後のCTA（既定の文面）
#     {{CTA:<src>|<h2>|<p>|<link>|<label>}}    文面を変える場合
#     {{BA:<記事ID>|<altB>|<altA>|<キャプション>}}  ビフォー/アフター
#     {{BACSS}}                   ビフォー/アフター用の追加CSS
# =====================================================================
import glob

TOK = re.compile(r'\{\{([A-Z]+)(?::([^}]*))?\}\}')


def expand(m):
    kind, arg = m.group(1), (m.group(2) or '')
    if kind == 'HEADER':
        a, s = (arg.split(':') + ['', ''])[:2]
        return header(a, s)
    if kind == 'PHEAD':
        parts = (arg.split('|') + ['', '', '', '', ''])[:5]
        return phead(parts[0], parts[1], parts[2], parts[3], parts[4] or None)
    if kind == 'PROOF':
        return PROOF
    if kind == 'BACSS':
        return '<style>' + BA_CSS + '</style>'
    if kind == 'BA':
        p = (arg.split('|') + ['', '', '', ''])[:4]
        return ba(p[0], p[1], p[2], p[3])
    if kind == 'CTA':
        p = arg.split('|')
        if len(p) >= 5:
            return cta(p[0], p[1], p[2], (p[3], p[4]))
        return cta(p[0])
    if kind == 'IMG':
        p = (arg.split('|') + ['before'])[:2]
        return IMG % (p[0], p[1])
    return m.group(0)


def main():
    made = []
    for f in sorted(glob.glob(os.path.join(HERE, 'bodies', '*.html'))):
        name = os.path.splitext(os.path.basename(f))[0]
        raw = io.open(f, encoding='utf-8').read()
        first = raw.split('\n', 1)
        title = first[0].strip()
        if not title.startswith('TITLE:'):
            print('!! TITLE: がありません:', f)
            continue
        title = title[len('TITLE:'):].strip()
        body = first[1]
        # IMG は入れ子（PHEAD の中）で使うので先に展開する
        body = re.sub(r'\{\{IMG:([^}|]+)\|([^}]*)\}\}', lambda m: IMG % (m.group(1), m.group(2)), body)
        body = TOK.sub(expand, body)
        p, n = page(name, title, body)
        made.append((name, n))
    for name, n in made:
        print('%-22s %7d 字' % (name, n))
    print('%d ページ書き出した' % len(made))


if __name__ == '__main__':
    main()
