#!/usr/bin/env python3
"""カビ特化LP /kabi/ を作る（T069・依頼 20261016-04-lp・第7回MTG オーナー決定）。

    python3 tools/make-kabi.py                          # preview/kabi/ に書き出す（確認用）
    python3 tools/make-kabi.py --out deploy/netlify/kabi   # 配信物に入れる（オーナーのOKのあと）

オーナー原文（F799）「即対応。最近でもエアコンが臭いとの言葉を現場で確認している。独立してカビ特化ＬＰを別途作成して
配信する。水物だから即取り掛かって。検索ワードは「エアコン　臭い」とかその周辺にして。」

- 土台は学習版の対抗案 /aircon-e/ の配信物（学習版 aircon-c ＋最初の画面の「いちばん早い空き3日」）。
  オーナー指示 10/16「学習後のクリエイティブにしてね」（依頼 20261016-06-lp）。C対E のテストとは別の独立したURL。計測は lp_id=kabi・lp_variant=A、フォーム名 reserve-kabi、予約ページへの引き継ぎは lp=kabi
- 変えるのは「検索語に合う見出し」と「季節の節」（tools/ab-aircon-kabi.py の /aircon-f/ 案と同じ文面）。
  背抜き・完全分解は今は承っていないので書かない・約束しない
- 写真は aircon-c の施工写真（送風ファン・吹き出し口の施工前後。本舗のロゴ・社名・番号の写り込み確認済み）を
  /kabi/img/ に写す（aircon-c が写真を替えても /kabi/ は変わらない）
- 料金は price-master（10/16 訂正版）。aircon-c の配信物がまだ旧いオプション価格でも tools/zei-1016.py を当てて直す
"""
import argparse
import importlib.util
import pathlib
import re
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def mod(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), ROOT / "tools" / f"{name}.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


f_ = mod("ab-aircon-kabi")   # 季節の節と CSS は /aircon-f/ 案と同じ
zei = mod("zei-1016")
fan = mod("fan-1019")   # ファンの取り外しを約束しない・付けたままとも書かない（和真さん 10/17・オーナー 10/18）
kaeru = f_.kaeru

TITLE = "エアコンが臭い・暖房にしたらカビ臭いときに｜エアコンクリーニング 10,780円｜ONE HITTER"
DESC = ("エアコンが臭い、暖房に切り替えたらカビ臭い。そのにおいは、フィルターの奥の熱交換器や送風ファンのカビかもしれません。"
        "分解して洗います。ノーマル10,780円（税込）・60分。お見積り以上の追加請求はありません。東京・千葉・神奈川。")
# 最初の画面のフック（オーナー案 10/17・依頼 20261017-02-lp）。気象の数字・「記録的」・「◯%のお宅」は書かない。現場で見ていることとして
H1 = ('<p class="nagaame-ue">毎日エアコンを洗う職人より、この秋のお知らせ</p>\n'
      '    <h1>9月の長雨で、<br>エアコンの奥に<span class="hl">カビ</span>が<br>増えています。</h1>\n'
      '    <p class="nagaame-sub">暖房をつけたら、エアコンが臭い。</p>')
SETSUMEI = ('いま伺うお宅では、送風ファンの奥に黒いカビが残っているエアコンが目立ちます。'
            '暖房をつけて臭ったら、それが合図です。')
SUB = f'<p class="hero-sub" id="hero-sub">{SETSUMEI}</p>'
NAGAAME_CSS = """
/* 最初の画面の長雨のフック（tools/make-kabi.py） */
.nagaame-ue{display:inline-block;margin:0 0 6px;padding:3px 10px;border-radius:999px;background:#FCEAE4;color:#8F2408;font-size:12.5px;font-weight:700;}
.nagaame-sub{margin:8px 0 4px;font-size:17px;font-weight:800;color:var(--ink);}
"""


HERO_SUB_GADS_OLD = "sashikae('hero-sub',  '熱交換器の奥まで分解して洗います。<b>お見積りは無料です。</b>');"
HERO_SUB_GADS_NEW = f"sashikae('hero-sub',  '{SETSUMEI}<b>お見積りは無料です。</b>');"


def make_index(h: str) -> str:
    h = kaeru(h, f"<title>{f_.TITLE_OLD}</title>", f"<title>{TITLE}</title>")
    h = kaeru(h, f'<meta property="og:title" content="{f_.TITLE_OLD}">', f'<meta property="og:title" content="{TITLE}">')
    old_desc = re.search(r'<meta name="description" content="([^"]*)">', h).group(1)
    h = kaeru(h, f'<meta name="description" content="{old_desc}">', f'<meta name="description" content="{DESC}">')
    h = kaeru(h, f'<meta property="og:description" content="{old_desc}">', f'<meta property="og:description" content="{DESC}">')
    h = kaeru(h, '<link rel="canonical" href="https://lp.onehitter.jp/aircon-e/">', '<link rel="canonical" href="https://lp.onehitter.jp/kabi/">')
    h = kaeru(h, '<meta property="og:url" content="https://lp.onehitter.jp/aircon-e/">', '<meta property="og:url" content="https://lp.onehitter.jp/kabi/">')
    h = h.replace("https://lp.onehitter.jp/aircon-c/img/", "https://lp.onehitter.jp/kabi/img/")   # og:image
    h = h.replace('="/aircon-c/img/', '="img/').replace("url(/aircon-c/img/", "url(img/")       # 写真は /kabi/img/ に写す
    h = kaeru(h, 'name="reserve-aircon-e"', 'name="reserve-kabi"')
    h = kaeru(h, 'action="/aircon-e/thanks.html"', 'action="/kabi/thanks.html"')
    h = kaeru(h, '<input type="hidden" name="form-name" value="reserve-aircon-e">',
                 '<input type="hidden" name="form-name" value="reserve-kabi">')
    h = kaeru(h, '<input type="hidden" name="lp" value="aircon-e">', '<input type="hidden" name="lp" value="kabi">')
    h = kaeru(h, "var hikitsugu = { lp: 'aircon-e',", "var hikitsugu = { lp: 'kabi',")
    h = kaeru(h, "-aircon-e-'", "-kabi-'")
    h = kaeru(h, '"lp_id":"aircon","lp_variant":"E"', '"lp_id":"kabi","lp_variant":"A"')
    h = kaeru(h, "'lp_id':'aircon','lp_variant':'E'", "'lp_id':'kabi','lp_variant':'A'")
    h = kaeru(h, f_.H1_OLD, H1)
    h = kaeru(h, f_.SUB_OLD, SUB)
    h = kaeru(h, HERO_SUB_GADS_OLD, HERO_SUB_GADS_NEW)   # 広告で来た人向けの差し替え文も、においの話に
    h = kaeru(h, '.hero-tel .num{font-size:17px;}\n', '.hero-tel .num{font-size:17px;}\n' + f_.CSS + NAGAAME_CSS)
    h = kaeru(h, '\n<section id="check">', f_.KISETSU + '\n<section id="check">')
    h = zei.apply(h)
    h = fan.apply(h)
    rest = sorted(set(re.findall(r'.{0,40}aircon-[ce](?!\.py).{0,40}', re.sub(r'/\*.*?\*/', '', h, flags=re.S))))
    if rest:
        sys.exit('aircon-c／aircon-e が残っている：\n' + '\n'.join(rest))
    return h


def make_thanks(h: str) -> str:
    h = kaeru(h, '"lp_id":"aircon","lp_variant":"E"', '"lp_id":"kabi","lp_variant":"A"')
    h = kaeru(h, "'lp_id':'aircon','lp_variant':'E'", "'lp_id':'kabi','lp_variant':'A'")
    h = kaeru(h, 'href="/aircon-e/"', 'href="/kabi/"')
    h = h.replace('="/aircon-c/img/', '="img/')
    if "aircon-c" in h or "aircon-e" in h:
        sys.exit("thanks.html に aircon-c が残っている")
    return h


def tenken(out: pathlib.Path) -> list:
    ng = []
    h = (out / "index.html").read_text(encoding="utf-8")
    text = re.sub(r'<[^>]+>', ' ', re.sub(r'<(script|style)[^>]*>.*?</\1>', '', h, flags=re.S))
    for k in ['"lp_id":"kabi","lp_variant":"A"', "'lp_id':'kabi'", 'reserve-kabi', "lp: 'kabi'",
              'action="/kabi/thanks.html"', 'https://lp.onehitter.jp/kabi/', 'G-DLJCTKGTDN', 'AW-18450975194',
              'href="https://yoyaku.onehitter.jp/" data-yoyaku data-place="hero"', 'noindex', 'id="aki"', 'slot_chip']:
        if k not in h:
            ng.append(f"index.html に {k} が無い")
    for bad in ['背抜き', '98.8', '080-1755-7275', '23件', '除菌', '100%', '他の人に勧めたい']:
        if bad in text:
            ng.append(f"使ってはいけない {bad} がある")
    ng += [f"古い金額 {x}" for x in zei.nokori(h)]
    ng += [f"ファンの書き方が古い {x}" for x in fan.nokori(h)]
    # 完全分解（ファンの取り外し）は今は承っていないので書かない（和真さん 10/17）
    if '完全分解' in text:
        ng.append("「完全分解」が出ている")
    for img in re.findall(r'src="(img/[^"]+)"', h):
        if not (out / img).exists():
            ng.append(f"写真が無い {img}")
    t = (out / "thanks.html").read_text(encoding="utf-8")
    if '"lp_id":"kabi"' not in t:
        ng.append("thanks.html の lp_id が kabi でない")
    return ng


# オーナーの指摘が来たときに、すぐ差し替えられる代案（依頼 20261017-01-lp）。--alt bunkai,koe-namae のように指定する
ALT = {
    # 「分解して洗います」が、背抜き（完全分解）を受ける意味に取られないように。
    # オーナー 10/18「分解して洗うことには変わりないからね」で、既定から外した（使わない）
    "bunkai": [
        ("分解して洗います。ノーマル10,780円", "カバーを外して、奥まで洗います。ノーマル10,780円"),
        ("フィルター掃除では届かないところを、分解して洗います。", "カバーを外して、フィルター掃除では届かない奥まで洗います。"),
        ("送風ファンのカビかもしれません。分解して洗います。<b>お見積りは無料です。</b>",
         "送風ファンのカビかもしれません。カバーを外して、奥まで洗います。<b>お見積りは無料です。</b>"),
        ("<h2>フィルターの奥を、<br>分解して洗います</h2>", "<h2>フィルターの奥まで、<br>洗います</h2>"),
    ],
    # 季節の節を、和真さんの名前で出す
    "koe-namae": [("― ワンヒッター 担当者より（2026年10月）", "― 担当 渡辺（2026年10月）")],
    # 季節の節を、人の声ではなく会社の記録として出す（名乗りの行を消す）
    "koe-nashi": [('\n      <p class="kisetsu-who">― ワンヒッター 担当者より（2026年10月）</p>', "")],
}


def alt(h: str, names) -> str:
    for n in names:
        for a, b in ALT[n]:
            if a not in h:
                continue   # 新しい説明文（10/17）で元の言い回しが無くなったものは飛ばす
            h = h.replace(a, b)
    return h


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(ROOT / "deploy" / "netlify" / "aircon-e"))
    ap.add_argument("--img", default=str(ROOT / "deploy" / "netlify" / "aircon-c" / "img"))
    ap.add_argument("--out", default=str(ROOT / "preview" / "kabi"))
    ap.add_argument("--alt", default="", help="代案：bunkai／koe-namae／koe-nashi をカンマ区切りで")
    a = ap.parse_args()
    src, out = pathlib.Path(a.src), pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    names = [x for x in a.alt.split(",") if x]
    (out / "index.html").write_text(alt(make_index((src / "index.html").read_text(encoding="utf-8")), names), encoding="utf-8")
    (out / "thanks.html").write_text(make_thanks((src / "thanks.html").read_text(encoding="utf-8")), encoding="utf-8")
    if (out / "img").exists():
        shutil.rmtree(out / "img")
    shutil.copytree(pathlib.Path(a.img), out / "img")
    ng = tenken(out)
    if ng:
        sys.exit("NG:\n  " + "\n  ".join(ng))
    print(f"書き出しました: {out}/（index.html・thanks.html・img/）点検OK")


if __name__ == "__main__":
    main()
