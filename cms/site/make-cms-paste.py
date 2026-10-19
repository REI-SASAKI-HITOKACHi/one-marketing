# -*- coding: utf-8 -*-
"""各ページの prototype.html から、CMSの「テキスト」パーツに貼る本文だけを切り出す。

  py -X utf8 cms/site/make-cms-paste.py

切り出すのは </header> と <footer> のあいだ。
ヘッダー・フッターはCMS側のものをそのまま使うので入れない。
共通CSS（base.css）はファイル管理に置いて「外部CSS/JS」で読ませるので、ここには入らない。
ページ専用の <style> は本文の中にあるので、そのまま付いてくる。
"""
import io, os, glob

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
OUT = os.path.join(ROOT, 'cms', 'site', 'cms-paste')

# 手書きのページ（CSSが <head> にまとまっている）
TEGAKI = {'top-page', 'voice-page', 'constructed-page', 'concept-page', 'feature-page'}

HEAD = ('<!-- ===================================================================\n'
        '  %s … CMSの「テキスト」パーツにこのまま貼る\n'
        '  ・共通CSSは base.css（ファイル管理に置き、レイアウトの「外部CSS/JS」で読む）\n'
        '  ・ヘッダー／フッターはCMSのものを使うので、ここには入れていない\n'
        '  ・下のほうにある <style> はこのページだけのもの。消さないこと\n'
        '  =================================================================== -->\n')


def main():
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    rows = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'cms', '*', 'prototype.html'))):
        name = os.path.basename(os.path.dirname(f))
        if name == 'menu-price-block':
            continue  # すでに /menu/ に入っている本文ブロック
        s = io.open(f, encoding='utf-8').read().replace('\r\n', '\n')
        i = s.find('</header>')
        j = s.rfind('<footer>')
        if i < 0 or j < 0:
            print('!! 切り出せない:', name)
            continue
        body = s[i + len('</header>'):j].strip()
        # 手書きの5枚は、ページ専用のCSSが <head> の <style> にまとめて入っている
        # （build.py から作った11枚は base.css ＋ 本文中の <style> なので、そのままでよい）
        if name in TEGAKI:
            a = s.find('<style>')
            b = s.find('</style>', a)
            if a < 0 or b < 0:
                print('!! <style> が見つからない:', name)
            else:
                body = s[a:b + len('</style>')] + '\n\n' + body
        io.open(os.path.join(OUT, name + '.html'), 'w', encoding='utf-8',
                newline='\n').write(HEAD % name + body + '\n')
        rows.append((name, len(body), body.count('<style')))
    for n, l, st in rows:
        print('%-22s %7d字  ページ専用style %d' % (n, l, st))
    print('%d ページ分を cms/site/cms-paste/ に用意した' % len(rows))


if __name__ == '__main__':
    main()
