#!/usr/bin/env python3
"""カビ特化LP（案）/aircon-f/ を、学習版 /aircon-c/ の配信物から作る（依頼 20261010-03-lp・第6回MTG）。

    python3 tools/ab-aircon-kabi.py --src deploy/netlify/aircon-c --out preview/aircon-f
    python3 tools/ab-aircon-kabi.py --src <dir> --out <dir> --check   # 点検だけ（終了コード）

## 何のためのものか（docs/LP-カビ特化-案-2026-10.md）

和真さん（10/9）：「今年は夏の終わりの長雨で湿気が多く、エアコンのカビがすごい」「暖房に切り替えた瞬間に臭う」
→「最近カビ臭くないですか？」型のLP。aircon-e の次の A/B 候補（順番は measurement と決める）。

aircon-c との違いは **最初の画面の言葉と、季節の節1つ** だけ。料金・写真・ボタン・フォームは同じ。
- 見出し：「暖房をつけた瞬間、カビ臭くないですか？」（季節のきっかけで呼びかける）
- 新しい節「この秋、伺う現場で多いこと」：担当の現場の声として書く。数字や因果は言い切らない
- 背抜き・完全分解は今は承っていない（和真さんが検討中）ので、**書かない・約束しない**
- 写真は aircon-c の施工写真（本舗のロゴ・お客様名の写り込み確認済み）を /aircon-c/img/ で参照

**配信はしない。** 確認は preview/ で。
"""

import argparse
import importlib.util
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("ab_e", ROOT / "tools" / "ab-aircon-e.py")
_e = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_e)
kaeru = _e.kaeru

TITLE_OLD = "エアコンクリーニング 10,780円／60分｜フィルター掃除で取れないカビ臭さに｜ONE HITTER"
TITLE_NEW = "暖房をつけたらカビ臭い｜エアコンクリーニング 10,780円／60分｜ONE HITTER"

H1_OLD = '<h1>フィルターを掃除しても<br><span class="hl">カビ臭い</span>。<br>原因は、内部のカビです。</h1>'
H1_NEW = '<h1>暖房をつけた瞬間、<br><span class="hl">カビ臭く</span><br>ないですか？</h1>'
SUB_OLD = '<p class="hero-sub" id="hero-sub">熱交換器の奥まで、分解して洗います。</p>'
SUB_NEW = ('<p class="hero-sub" id="hero-sub">フィルターを掃除しても残るにおいは、奥の熱交換器や送風ファンの汚れかもしれません。'
           '分解して洗います。</p>')

KISETSU = """
<section id="kisetsu">
  <div class="wrap">
    <div class="sec-h">
      <span class="eyebrow">This fall</span>
      <h2>この秋、伺う現場で<br>多いこと</h2>
    </div>
    <div class="kisetsu-box">
      <p>夏の終わりに雨の日が続き、湿気の多い年でした。いま伺う現場では、<b>送風ファンや熱交換器の奥にカビが残っているエアコン</b>を、例年より多く見ています。</p>
      <p>冷房のあいだは気にならなくても、<b>暖房に切り替えた最初の日に「においが気になった」</b>というご相談をいただきます。</p>
      <p class="kisetsu-who">― ワンヒッター 担当者より（2026年10月）</p>
    </div>
    <ul class="kisetsu-list">
      <li>暖房をつけた直後に、すっぱいようなにおいがする</li>
      <li>吹き出し口の奥に、黒い点が見える</li>
      <li>フィルターは掃除したのに、においが消えない</li>
    </ul>
    <p class="kisetsu-note">ひとつでも当てはまれば、奥の汚れを見てみる価値があります。汚れの程度により、落ちきらない場合があります。</p>
  </div>
</section>
"""

CSS = """
/* ===== カビ特化LP（案）：季節の節（tools/ab-aircon-kabi.py が足す） ===== */
#kisetsu .kisetsu-box{background:#fff;border:1px solid var(--rule);border-radius:12px;padding:16px 16px 12px;line-height:1.85;}
#kisetsu .kisetsu-box p{margin:0 0 10px;}
#kisetsu .kisetsu-who{font-size:12.5px;color:var(--steel);text-align:right;margin:0 !important;}
#kisetsu .kisetsu-list{margin:14px 0 6px;padding-left:1.2em;display:grid;gap:4px;}
#kisetsu .kisetsu-note{font-size:12.5px;color:var(--steel);margin:6px 0 0;}
"""


def make_index(h: str) -> str:
    h = kaeru(h, f"<title>{TITLE_OLD}</title>", f"<title>{TITLE_NEW}</title>")
    h = kaeru(h, f'<meta property="og:title" content="{TITLE_OLD}">', f'<meta property="og:title" content="{TITLE_NEW}">')
    h = kaeru(h, '<link rel="canonical" href="https://lp.onehitter.jp/aircon-c/">',
                 '<link rel="canonical" href="https://lp.onehitter.jp/aircon-f/">')
    h = kaeru(h, '<meta property="og:url" content="https://lp.onehitter.jp/aircon-c/">',
                 '<meta property="og:url" content="https://lp.onehitter.jp/aircon-f/">')
    h = kaeru(h, 'name="reserve-aircon-c"', 'name="reserve-aircon-f"')
    h = kaeru(h, 'action="/aircon-c/thanks.html"', 'action="/aircon-f/thanks.html"')
    h = kaeru(h, '<input type="hidden" name="form-name" value="reserve-aircon-c">',
                 '<input type="hidden" name="form-name" value="reserve-aircon-f">')
    h = kaeru(h, '<input type="hidden" name="lp" value="aircon-c">', '<input type="hidden" name="lp" value="aircon-f">')
    h = kaeru(h, "var hikitsugu = { lp: 'aircon-c',", "var hikitsugu = { lp: 'aircon-f',")
    h = kaeru(h, "-aircon-c-'", "-aircon-f-'")
    h = kaeru(h, '"lp_id":"aircon","lp_variant":"C"', '"lp_id":"aircon","lp_variant":"F"')
    h = kaeru(h, "'lp_id':'aircon','lp_variant':'C'", "'lp_id':'aircon','lp_variant':'F'")
    h = re.sub(r'(src|href)="img/', r'\1="/aircon-c/img/', h)
    h = re.sub(r"url\((['\"]?)img/", r"url(\1/aircon-c/img/", h)
    h = kaeru(h, H1_OLD, H1_NEW)
    h = kaeru(h, SUB_OLD, SUB_NEW)
    h = kaeru(h, '.hero-tel .num{font-size:17px;}\n', '.hero-tel .num{font-size:17px;}\n' + CSS)
    h = kaeru(h, '\n<section id="check">', KISETSU + '\n<section id="check">')
    if 'aircon-c' in re.sub(r'/aircon-c/img/', '', h):
        rest = sorted(set(re.findall(r'.{0,40}aircon-c.{0,40}', re.sub(r'/aircon-c/img/', '', h))))
        sys.exit('aircon-c が残っている：\n' + '\n'.join(rest))
    return h


def make_thanks(h: str) -> str:
    h = kaeru(h, '"lp_id":"aircon","lp_variant":"C"', '"lp_id":"aircon","lp_variant":"F"')
    h = kaeru(h, "'lp_id':'aircon','lp_variant':'C'", "'lp_id':'aircon','lp_variant':'F'")
    h = kaeru(h, 'href="/aircon-c/"', 'href="/aircon-f/"')
    h = re.sub(r'(src|href)="img/', r'\1="/aircon-c/img/', h)
    return h


def tenken(out: pathlib.Path) -> list:
    ng = []
    h = (out / 'index.html').read_text(encoding='utf-8')
    for k in ['id="kisetsu"', '"lp_variant":"F"', 'reserve-aircon-f', "lp: 'aircon-f'", 'カビ臭く']:
        if k not in h:
            ng.append(f'index.html に {k} が無い')
    # 約束しないこと・使わない数字
    text = re.sub(r'<[^>]+>', ' ', re.sub(r'<(script|style)[^>]*>.*?</\1>', '', h, flags=re.S))   # 画面に出る文字だけ
    for bad in ['背抜き', '完全分解', '98.8', '080-1755-7275', '23件', '除菌', '100%']:
        if bad in text:
            ng.append(f'index.html に使ってはいけない {bad} がある')
    if 'one-hitter.jp/privacy_policy' in h:
        ng.append('個人情報の取扱いのリンクが公式サイトのまま')
    t = (out / 'thanks.html').read_text(encoding='utf-8')
    if '"lp_variant":"F"' not in t:
        ng.append('thanks.html の lp_variant が F でない')
    return ng


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', default=str(ROOT / 'deploy' / 'netlify' / 'aircon-c'))
    ap.add_argument('--out', default=str(ROOT / 'preview' / 'aircon-f'))
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    src, out = pathlib.Path(a.src), pathlib.Path(a.out)
    if not a.check:
        out.mkdir(parents=True, exist_ok=True)
        (out / 'index.html').write_text(make_index((src / 'index.html').read_text(encoding='utf-8')), encoding='utf-8')
        (out / 'thanks.html').write_text(make_thanks((src / 'thanks.html').read_text(encoding='utf-8')), encoding='utf-8')
        print(f'書き出しました: {out}/index.html, thanks.html（写真は /aircon-c/img/ を参照）')
    ng = tenken(out)
    if ng:
        print('NG:\n  ' + '\n  '.join(ng))
        sys.exit(1)
    print('点検OK')


if __name__ == '__main__':
    main()
