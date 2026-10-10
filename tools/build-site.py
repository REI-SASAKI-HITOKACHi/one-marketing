#!/usr/bin/env python3
"""lp/<name>/index.html を、そのままサーバーに置ける HTML 文書に組み立てる。

lp/ 配下は Artifact 用に <html> や <head> を持たない断片として書いてあるので、
公開用にはここで文書として包み、フォームの送信先を PHP に繋ぎ替える。

  python3 tools/build-site.py php       →  deploy/htdocs/  （PHPでフォームを受ける）
  python3 tools/build-site.py netlify   →  deploy/netlify/ （Netlify Formsが受ける）
"""
import html
import json
import pathlib
import re
import shutil
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import moushikomi  # noqa: E402  申込フォームの「申込内容」と見積の項目（依頼 20260928-02-lp）

def strip_comments(html: str) -> str:
    """公開する文書からコメントを落とす。

    lp/ 配下のソースには、なぜその値なのかを書いた注記を残してある。
    ただし公開ページのソースに設計メモが並んでいるのは正常な状態ではないので、
    書き出すときに外す。CSSのコメントは <style> の中だけを対象にする
    （JavaScript の中の /* */ を巻き込まないため）。
    """
    html = re.sub(r"<!--.*?-->", "", html, flags=re.S)

    def _style(m):
        return m.group(1) + re.sub(r"/\*.*?\*/", "", m.group(2), flags=re.S) + m.group(3)

    html = re.sub(r"(<style[^>]*>)(.*?)(</style>)", _style, html, flags=re.S)
    # コメントを抜いた跡に残る空行を畳む
    html = re.sub(r"\n[ \t]*\n[ \t]*\n+", "\n\n", html)
    return html


ROOT = pathlib.Path(__file__).resolve().parent.parent

# 配信先ごとに、フォームの受け口と出力先が変わる
TARGETS = {
    # ロリポップなど、PHPが動くサーバー
    "php": {"out": ROOT / "deploy" / "htdocs"},
    # Netlify。フォームはNetlify Formsが受ける
    "netlify": {"out": ROOT / "deploy" / "netlify"},
}

# ★ハイフンの位置に注意。配信先は onehitter（ハイフン無し）。
#   one-hitter.jp は公式サイトで別物。lp.one-hitter.jp は存在しないホストで、
#   canonical と og:url がそこを指したまま配信されていた（2026-09-16 ブラウザ担当の指摘）。
BASE_URL = "https://lp.onehitter.jp"

# 計測の設定と、埋め込むスクリプトの置き場所
TRACKING_DIR = ROOT / "tracking"
MEASUREMENT_JSON = TRACKING_DIR / "measurement.json"
EVENTS_JS = TRACKING_DIR / "events.js"
THANKS_TEMPLATE = ROOT / "tools" / "templates" / "thanks.html"

PAGES = {
    "aircon": {
        "dir": "aircon",
        "lp_id": "aircon",
        "lp_variant": "A",
        "title": "エアコンクリーニング 10,780円／60分｜東京・千葉・神奈川｜ONE HITTER",
        "desc": "フィルター掃除では届かない、熱交換器と送風ファンの黒カビを分解洗浄。"
                "ノーマルエアコン10,780円（税込）・60分、お見積り以上の追加請求はありません。"
                "東京・千葉・神奈川、最短即日。",
        "label": "エアコン",
        "og": "aircon/img/og.jpg",
        "og_line1": "エアコン内部のカビを、分解洗浄",
        "og_line2": "ノーマル 10,780円（税込）／60分・東京 千葉 神奈川",
    },
    # パターンAに対するA/Bテスト用の対抗案。ヒーローだけが違う
    "aircon-b": {
        "dir": "aircon-b",
        # 計測上は同じ「エアコン」の商品で、ヒーローだけが違う対抗案。
        # lp_id を揃え lp_variant で分けることで、GA4で A/B を並べて比べられる。
        "lp_id": "aircon",
        "lp_variant": "B",
        "title": "エアコン分解洗浄 1台10,780円／60分 最短即日｜東京・千葉・神奈川｜ONE HITTER",
        "desc": "エアコンを分解し、熱交換器と送風ファンを専用機材で洗浄。"
                "ノーマル10,780円（税込）・60分、お掃除機能付き17,380円（税込）・120分。"
                "お見積り以上の追加請求はありません。東京・千葉・神奈川、最短即日。",
        "label": "エアコン（B）",
        "og": "aircon-b/img/og.jpg",
        "og_line1": "エアコン分解洗浄 1台 10,780円／60分",
        "og_line2": "最短即日・追加請求なし・東京 千葉 神奈川",
    },
    "mizumawari": {
        "dir": "mizumawari",
        "lp_id": "mizumawari",
        "lp_variant": "A",
        "title": "水まわりクリーニング まとめて依頼で1箇所3,300円おトク｜ONE HITTER",
        "desc": "キッチン・浴室・レンジフード・洗濯機・追い焚き配管。2箇所目からは同時施工価格。"
                "浴室＋キッチンで33,660円（税込）、半日で完了。東京・千葉・神奈川、最短即日。",
        "label": "水まわりセット",
        "og": "mizumawari/img/og.jpg",
        "og_line1": "水まわりは、まとめて頼むほど安い",
        "og_line2": "浴室＋キッチン 33,660円（税込）・東京 千葉 神奈川",
    },
    "nenmatsu": {
        "dir": "nenmatsu",
        "lp_id": "nenmatsu",
        "lp_variant": "A",
        "title": "年末大掃除 11月までなら通常価格｜レンジフード・浴室・キッチン｜ONE HITTER",
        "desc": "12月は繁忙期料金として1箇所につき3,300円が加算されます。11月30日までのご予約なら通常価格。"
                "レンジフード＋浴室で33,660円（税込）、半日で完了。東京・千葉・神奈川、自社施工。",
        "label": "年末大掃除",
        "og": "nenmatsu/img/og.jpg",
        "og_line1": "年末の大掃除は、11月までが安い",
        "og_line2": "レンジフード＋浴室 33,660円（税込）・12月から+3,300円／箇所",
    },
    # ↓ 学習版4本（2026-09-30 オーナー指示「学習後のLPをさっそくテストしたいからすぐ配信して」で DRAFTS から移動）
    "mizumawari-b": {
        "dir": "mizumawari-b",
        # 案A（mizumawari）の対抗案。lp_id を揃え lp_variant で分ける（aircon-b と同じ考え方）
        "lp_id": "mizumawari",
        "lp_variant": "B",
        "title": "水まわりクリーニング 浴室＋キッチン2箇所で33,660円｜東京・千葉・神奈川｜ONE HITTER",
        "desc": "2箇所目から同時施工価格。浴室＋キッチンで33,660円（税込）、お見積り以上の追加請求はありません。"
                "下請けに出さず、ご予約を受けた自社の職人が伺います。東京・千葉・神奈川。",
        "label": "水まわりセット（B）",
        "og": "mizumawari-b/img/og.jpg",
        "og_line1": "浴室とキッチン、2箇所で33,660円",
        "og_line2": "追加請求なし・自社の職人・東京 千葉 神奈川",
    },
    # エアコンの学習版は2本。今の案A（悩み入口）と案B（料金入口）の入口の比較を引き継ぐ
    "aircon-c": {
        "dir": "aircon-c",
        "lp_id": "aircon",
        "lp_variant": "C",
        "title": "エアコンクリーニング 10,780円／60分｜フィルター掃除で取れないカビ臭さに｜ONE HITTER",
        "desc": "フィルター掃除では届かない熱交換器と送風ファンを分解洗浄。ノーマル10,780円（税込）・60分。"
                "お見積り以上の追加請求はありません。下請けに出さず自社の職人が伺います。東京・千葉・神奈川。",
        "label": "エアコン（学習版C）",
        "og": "aircon-c/img/og.jpg",
        "og_line1": "フィルター掃除でも取れないカビ臭さに",
        "og_line2": "ノーマル 10,780円（税込）／60分・追加請求なし",
    },
    "aircon-d": {
        "dir": "aircon-d",
        "lp_id": "aircon",
        "lp_variant": "D",
        "title": "エアコン分解洗浄 1台10,780円／60分 最短即日｜東京・千葉・神奈川｜ONE HITTER",
        "desc": "送風ファンを取り外し、熱交換器の奥まで分解洗浄。ノーマル10,780円（税込）・60分、お掃除機能付き17,380円（税込）・120分。"
                "お見積り以上の追加請求はありません。東京・千葉・神奈川。",
        "label": "エアコン（学習版D）",
        "og": "aircon-d/img/og.jpg",
        "og_line1": "エアコン分解洗浄 1台 10,780円／60分",
        "og_line2": "追加請求なし・自社の職人・東京 千葉 神奈川",
    },
    "nenmatsu-b": {
        "dir": "nenmatsu-b",
        "lp_id": "nenmatsu",
        "lp_variant": "B",
        "title": "年末大掃除 レンジフード＋浴室33,660円 11月30日のご予約まで｜ONE HITTER",
        "desc": "11月30日までのご予約なら通常価格。レンジフード＋浴室で33,660円（税込）、12月は1箇所につき3,300円の繁忙期料金。"
                "お見積り以上の追加請求はありません。東京・千葉・神奈川、自社施工。",
        "label": "年末大掃除（学習版B）",
        "og": "nenmatsu-b/img/og.jpg",
        "og_line1": "レンジフード＋浴室 33,660円",
        "og_line2": "11月30日のご予約まで通常価格・12月は+3,300円／箇所",
    },
}

# 下書き（A/Bテストの候補）。PAGES と同じ形で書くが、ここに置いたものは
# 通常のビルドでは作らない＝配信物（deploy/）に入らない＝本番に出ない。
#   python3 tools/build-site.py netlify --draft mizumawari-b   → preview/netlify/mizumawari-b/
# A/Bテストを始めるときは、オーナーの許可を取ってから PAGES へ移す（1項目の移動で済む）。
DRAFTS = {
}

HEAD = """<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<!-- 広告の受け皿なので、公式サイトと検索結果で食い合わないよう検索避けにしています。
     検索にも載せたくなったら、この1行を消してください。 -->
<meta name="robots" content="noindex,follow">
<link rel="canonical" href="{base}/{dir}/">
<meta property="og:type" content="website">
<meta property="og:site_name" content="ワンヒッター株式会社">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{base}/{dir}/">
<meta property="og:image" content="{base}/{og}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:locale" content="ja_JP">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#0E7C93">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<!-- ASP・広告計測タグはこの下に貼ってください -->
</head>
<body>
"""

TAIL = """
</body>
</html>
"""

FORM_OPEN = '<form class="form" onsubmit="return false;">'

FORM_PHP = """<form class="form" action="/form/send.php" method="post">
      <input type="hidden" name="lp" value="{dir}">
      <div class="hp" aria-hidden="true">
        <label for="f-x">この欄には入力しないでください</label>
        <input id="f-x" name="x_field" type="text" tabindex="-1" autocomplete="off">
      </div>"""

# Netlify Forms は、配信されたHTMLからこの form を見つけて受け口を用意する。
# name と form-name が一致していることと、honeypot の欄名の申告が要る。
FORM_NETLIFY = """<form class="form" name="reserve-{dir}" method="post"
      action="/{dir}/thanks.html" data-netlify="true" netlify-honeypot="x_field">
      <input type="hidden" name="form-name" value="reserve-{dir}">
      <input type="hidden" name="subject" value="【LP予約】{label}">
      <input type="hidden" name="lp" value="{dir}">
      <input type="hidden" name="order_id" value="">
      <input type="hidden" name="gclid" value="">
      <div class="hp" aria-hidden="true">
        <label for="f-x">この欄には入力しないでください</label>
        <input id="f-x" name="x_field" type="text" tabindex="-1" autocomplete="off">
      </div>"""

# 計測タグの差し込み口。HEAD の中にあるこの目印を、実物のタグに置き換える。
TRACKING_SLOT = "<!-- ASP・広告計測タグはこの下に貼ってください -->"

# 差し込んだ計測タグの先頭に置く目印。inject-tracking.py が
# 「前に入れた分」を見分けて入れ替えるのに使う。社内のパスは書かない。
TRACKING_MARK = "<!-- ONE HITTER 計測タグ -->"


def load_measurement() -> dict:
    """tracking/measurement.json を読む。無ければ「全部空」として扱う。

    IDが空でもビルドは通り、タグは出力されない。計測の仕組みだけ先に入れておき、
    GA4の準備ができたら設定ファイルを書き換えて再ビルドすればよい、という作りにしている。
    """
    if not MEASUREMENT_JSON.exists():
        return {}
    data = json.loads(MEASUREMENT_JSON.read_text(encoding="utf-8"))
    # "_readme" や "_note" は人間向けのメモなので、出力には持ち込まない
    return prune_notes(data)


def prune_notes(node):
    if isinstance(node, dict):
        return {k: prune_notes(v) for k, v in node.items() if not k.startswith("_")}
    if isinstance(node, list):
        return [prune_notes(v) for v in node]
    return node


def tel_for(cfg: dict, dir_name: str) -> str:
    """このLPで表示する電話番号。コールトラッキングの発番があればそちらを使う。"""
    call = cfg.get("call_tracking") or {}
    return ((call.get("numbers") or {}).get(dir_name) or "").strip() \
        or (call.get("default_number") or DEFAULT_TEL).strip()


DEFAULT_TEL = "080-8043-8259"


def swap_tel(src: str, number: str) -> str:
    """LPに書かれている既定の番号を、計測用の発番に差し替える。

    LPのソース（lp/ 配下）には手を触れず、書き出すときだけ差し替える。
    表示用（ハイフンあり）と tel: リンク用（ハイフンなし）の両方が本文にあるので、
    どちらも置き換える。番号を戻したいときは measurement.json を空にするだけでよい。
    """
    if number == DEFAULT_TEL:
        return src
    digits = re.sub(r"[^0-9]", "", number)
    src = src.replace(DEFAULT_TEL, number)
    src = src.replace(re.sub(r"[^0-9]", "", DEFAULT_TEL), digits)
    return src


# ============================================================
# 自社アンケートの満足度。**ここ1か所だけを直せば全ページに効く。**
#
# 2026-09-21：これまで「98.6%（209名中206名／2023年1月〜2025年12月）」と書いていたが、
# 一次データ（Googleフォームの回答シート2ファイル）で再現できなかった。
# 母数が209に届かず（集計可能な最大192件）、2025年の回答が1件も無い。
# 詳細は docs/アンケート98.6%の一次集計-2026-09-21.md（CMO作成）。
# 出どころをオーナーに確認中。**確認が取れたら、この辞書を戻すだけで元に戻る。**
#
# いま入れている値は、一次データから実際に計算できたもの：
#   合算・全期間の平均 9.45／10点、N=192、2022年6月〜2024年8月
#   （CMOの指示は「9.4」だったが、§3.3 の合算・全期間の計算値は 9.45 なので
#     計算値をそのまま使う。丸めて下げるより、出せる数字を出すほうが強い）
# 2026-09-23 オーナー指示：98.6% に戻す。仕組み（この辞書1か所）は残す。
# 一次データで再現できなかった経緯は上のとおりだが、出どころの確認はオーナーが持つ。
# 9.45版に戻すときは、下の4行を差し替えるだけでよい（履歴は commit 68924c1）。
# 2026-10-10 第6回MTG 6-4 No.8 オーナー決定：206名＝「すぐにオススメしたい」＋「機会があればススメてもよい」。
#   言い回しを旧アンケートの設問どおりにした（依頼 20261010-01-lp）。学習版の数字の帯は tools/bunmen-1010.py
MANZOKU = {
    "{{MANZOKU_NUM}}":  "98.6%",
    "{{MANZOKU_UNIT}}": "",
    "{{MANZOKU_LAB}}":  "が、ご家族や友人に<br>勧めてもよいと回答<sup>※1</sup>",
    "{{MANZOKU_NOTE}}": "※1 ご利用後アンケートの設問「ご家族や知人友人の方へ『オススメしたい』と思いますか？」に、「すぐにオススメしたい」「機会があればススメてもよい」と答えた方の割合："
                        "集計期間 2023年1月〜2025年12月、回答209名中206名、自社調べ",
    "{{MANZOKU_FINE}}": "「98.6%」は、自社実施のご利用者アンケートで、ご家族や知人友人に「すぐにオススメしたい」「機会があればススメてもよい」と答えた方の割合です"
                        "（実施期間：2023年1月〜2025年12月／回答209名中206名）。",
}


def manzoku(html: str) -> str:
    """満足度の差し込み。置き換え漏れがあればビルドを止める。"""
    for k, v in MANZOKU.items():
        html = html.replace(k, v)
    if "{{MANZOKU" in html:
        raise SystemExit("満足度の差し込みに漏れがあります（{{MANZOKU…}} が残っています）")
    return html


def tracking_head(cfg: dict, page: dict, tel: str = "") -> str:
    """<head> に入れる分。gtag の読み込みと、このページが何なのかの申告。"""
    ga4 = ((cfg.get("ga4") or {}).get("measurement_id") or "").strip()
    ads = ((cfg.get("google_ads") or {}).get("conversion_id") or "").strip()
    phone_label = ((cfg.get("google_ads") or {}).get("phone_conversion_label") or "").strip()
    pixel = ((cfg.get("meta") or {}).get("pixel_id") or "").strip()

    # 設定は tracking/measurement.json、設計は docs/measurement-spec.md。
    # 内部のファイル名を公開ページのソースに出さないため、注記はここに置いてHTMLには入れない
    # （LP担当の判断。2026-09-10）。
    #
    # ただし目印そのものは要る。tools/inject-tracking.py が「前に入れた分」を
    # 見分けるのに使っており、目印が無いと二重に差し込まれる（実際にそうなった）。
    # パスを含まない1語だけの目印にして、両方の要求を満たす。
    out = [TRACKING_MARK]
    out.append("<script>window.OH_M=" + json.dumps(
        {"page": page, "google_ads": cfg.get("google_ads") or {}, "debug": bool(cfg.get("debug"))},
        ensure_ascii=False, separators=(",", ":")) + ";</script>")

    if ga4 or ads:
        # 読み込みは1本でよい。gtag('config') を並べれば両方に届く。
        first = ga4 or ads
        lines = ['<script async src="https://www.googletagmanager.com/gtag/js?id=%s"></script>' % first,
                 "<script>",
                 "window.dataLayer=window.dataLayer||[];",
                 "function gtag(){dataLayer.push(arguments);}",
                 "gtag('js',new Date());",
                 # 流入元（?src=）を、page_view を含む全イベントに付ける。
                 # config に載せるので、events.js が動く前の page_view にも乗る。
                 # これが無いと「どのQR・どの施設・どのSMSから来たか」を
                 # GA4のレポートで分解できない。フォームの hidden 欄は
                 # 送信した人の分しか残らないので、閲覧数は取れない。
                 # GA4 とフォームの隠し欄で、同じ値になるように同じ整形を通す。
                 # LP側は素性の分からない値を入れないため clean（英数と _- のみ・20文字）を
                 # かけている。GA4だけ生の値だと、**GA4と台帳で流入元が食い違う**。
                 # test-ads-tracking.py の「GA4とフォームが同じ値になる」で担保。
                 "var ohClean=function(v,n){return (v||'').replace(/[^A-Za-z0-9_-]/g,'').slice(0,n);};",
                 "var oh_src=ohClean(new URLSearchParams(location.search).get('src'),20)||'direct';",
                 "var oh_cid=ohClean(new URLSearchParams(location.search).get('cid'),20);"]
        if ga4:
            lines.append("gtag('config','%s',{'lp_id':'%s','lp_variant':'%s',"
                         "'traffic_src':oh_src,'traffic_cid':oh_cid});"
                         % (ga4, page["lp_id"], page["lp_variant"]))
        if ads:
            lines.append("gtag('config','%s');" % ads)
        if ads and phone_label and tel:
            # Google広告の「電話番号の動的挿入」。広告経由で来た人にだけ、
            # ページ上の電話番号をGoogle広告専用の転送番号に自動で差し替える。
            # 転送先は結局この番号なので、受電の仕方は変わらない。追加費用は無い。
            # ここに書く番号は、ページに表示されている番号と一致していないと差し替わらない。
            lines.append("gtag('config','%s/%s',{'phone_conversion_number':'%s'});"
                         % (ads, phone_label, tel))
        lines.append("</script>")
        out += lines
    else:
        # GA4・広告タグは未設定。tracking/measurement.json にIDを入れて再ビルドすると出力される。
        # 未設定であることを公開ページのソースに書く必要はないので、何も出さない
        pass

    if pixel:
        out += ["<script>",
                "!function(f,b,e,v,n,t,s){if(f.fbq)return;n=f.fbq=function(){n.callMethod?"
                "n.callMethod.apply(n,arguments):n.queue.push(arguments)};if(!f._fbq)f._fbq=n;"
                "n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;"
                "t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}"
                "(window,document,'script','https://connect.facebook.net/en_US/fbevents.js');",
                "fbq('init','%s');fbq('track','PageView');" % pixel,
                "</script>"]

    return "\n".join(out)


def tracking_body() -> str:
    """</body> の直前に入れる分。クリックや送信を拾う本体。"""
    js = EVENTS_JS.read_text(encoding="utf-8") if EVENTS_JS.exists() else ""
    if not js:
        return ""
    return "<script>\n" + js + "</script>"


# ---------------------------------------------------------------------------
# アフィリエイト（レントラックス）のITPトラッキングタグ
#
# 先方から受領した2本（docs/vendor/rentracks/ に原本）をそのまま使う。
#   PID16436_lp-tag.txt              … LPに置く
#   PID16436_cv-tag_ThanksPage.txt   … サンクスページに置く
#
# 先方の設置手順書（★【RENTRACKS】ITP対応トラッキングタグの設置につきまして.pdf）で
# 確認したこと：
#   - 置き場所は </body> の直前が推奨
#   - LPとサンクスページのドメインが同じなら、追加の対応は不要（手順書4ページ）
#     当社は one-hitter-lp.netlify.app/mizumawari/ と .../mizumawari/thanks で
#     ドメインが同じなので、対応不要にあたる
#   - _rt.cinfo は必須。成果を特定する識別記号を、UTF-8のURLエンコードで渡す
#     （変数のご説明.pdf。最大500文字）
#   - _rt.price は定額案件なので 0 固定、_rt.reward は -1 固定
# ---------------------------------------------------------------------------

# 先方のタグと同じ読み込み部分。LP用とCV用で中身が同じなので関数にしてある。
RT_LOADER = ("var s=document.createElement('script');s.type='text/javascript';"
             "s.src='https://www.rentracks.jp/js/itp/rt.track.js?t='+(new Date()).getTime();"
             "if(s.readyState){s.onreadystatechange=function(){"
             "if(s.readyState==='loaded'||s.readyState==='complete'){"
             "s.onreadystatechange=null;cb();}};}else{s.onload=function(){cb();};}"
             "document.getElementsByTagName('head')[0].appendChild(s);")

# 目印は <script> の**外**に置くこと。`<!--` は JavaScript では行コメントとして
# 解釈されるので、スクリプトの中に書くとその行が丸ごと死ぬ。
# （2026-09-11：中に書いてしまい、読み込み部分ごとコメントアウトされて
#  `return` が関数の外に残り、タグが一切動かなかった。ブラウザで検知）
RT_MARK = "<!-- ONE HITTER 計測タグ -->"


def rentracks_on(cfg: dict, dir_name: str) -> bool:
    """このLPにレントラックスのタグを出すかどうか。

    登録している掲載先だけに出す。登録していないLPに出しても成果にはならないし、
    出す理由が無いものを公開ページに載せない。
    """
    rt = cfg.get("rentracks") or {}
    if not (rt.get("sid") or "").strip() or not (rt.get("pid") or "").strip():
        return False
    return dir_name in (rt.get("pages") or [])


def order_id_script(dir_name: str) -> str:
    """申込1件ごとの「紐づけ情報」を用意する。**全LP共通。**

    2つある。

    ## 1. 注文ID
    送信ボタンが押された瞬間に作り、2か所に置く。
      - フォームの隠し欄 `order_id` … Netlify Forms の受信内容に残る＝当社の記録
      - sessionStorage          … サンクスページへ引き継ぐため
    アフィリエイトの成果（`_rt.cinfo`）はこのIDで特定する。

    ## 2. gclid（Google広告のクリックID）
    **これが後々いちばん効く。**

    当社は申込から受注確定まで2〜4週間かかり、電話で決まることも多い。
    サンクスページのCVだけを見ていると、**「申し込んだが成約しなかった人」も
    「電話で高額受注になった人」も同じ1件**になり、広告の自動入札が
    見当違いのほうへ最適化していく。

    gclid を申込と一緒に残しておけば、あとから
    **「この申込は実際に◯◯円で成約した」をGoogle広告へ戻せる**
    （オフラインコンバージョンのインポート）。**残していないと、後から復元できない。**

    - `?gclid=` … 通常のクリック
    - `?wbraid=` `?gbraid=` … iOSなどで gclid の代わりに付くもの。取りこぼさないため一緒に見る
    - 90日で捨てる。Google広告の取り込み期限がそれより短いため、古いものは持たない
    """
    return ("<script>(function(){"
            # --- 注文ID ---
            # OH-年月日-LP名-4桁。英数字とハイフンだけなのでURLエンコードしても増えない。
            # 紛らわしい文字（I・O・0・1）は使わない。電話で読み上げることがあるため。
            "function mkid(){var d=new Date();"
            "var p=function(n){return(n<10?'0':'')+n;};"
            "var r='';var c='ABCDEFGHJKLMNPQRSTUVWXYZ23456789';"
            "for(var i=0;i<4;i++){r+=c.charAt(Math.floor(Math.random()*c.length));}"
            "return 'OH-'+d.getFullYear()+p(d.getMonth()+1)+p(d.getDate())+'-%s-'+r;}\n"
            # --- gclid ---
            # 広告から来た「そのとき」にしか取れない。着いた瞬間に保存する。
            "var Q;try{Q=new URLSearchParams(location.search);}catch(e){Q=null;}"
            "var g=Q&&(Q.get('gclid')||Q.get('wbraid')||Q.get('gbraid'))||'';"
            "try{"
            "if(g){localStorage.setItem('oh_gclid',JSON.stringify({v:g,t:Date.now()}));}"
            "}catch(e){}\n"
            "function gclid(){try{"
            "var o=JSON.parse(localStorage.getItem('oh_gclid')||'null');"
            # 90日 = 90*24*60*60*1000
            "if(!o||!o.v)return '';"
            "if(Date.now()-o.t>7776000000){localStorage.removeItem('oh_gclid');return '';}"
            "return o.v;}catch(e){return '';}}\n"
            # --- 送信時にフォームへ入れる ---
            "var f=document.querySelector('form.form');if(!f)return;"
            # 注文IDは1ページにつき1つ。**押すたびに作り直さない。**
            #
            # 二度押しすると submit は2回起きる。作り直すと、
            #   Netlify Forms に残るのは1回目のID（先に送信が出ていくため）
            #   sessionStorage に残るのは2回目のID（後から上書きされる）
            # となり、**サンクスページのアフィリエイトタグが、当社の受信記録に
            # 無いIDを先方へ送ることになる。** 成果の突き合わせが壊れ、
            # オフラインインポートの突き合わせ鍵（order_id）も合わなくなる。
            "var id='';"
            "f.addEventListener('submit',function(){"
            "if(!id){id=mkid();}"
            "var h=f.querySelector('input[name=\"order_id\"]');if(h){h.value=id;}"
            "var gh=f.querySelector('input[name=\"gclid\"]');if(gh){gh.value=gclid();}"
            "try{sessionStorage.setItem('oh_order_id',id);}catch(e){}"
            "},true);"
            "})();</script>") % dir_name


def rentracks_lp(cfg: dict, dir_name: str) -> str:
    """LP側。トラッキングIDのCookieを置くだけで、変数は要らない。"""
    if not rentracks_on(cfg, dir_name):
        return ""
    return (RT_MARK + "<script>(function(){var cb=function(){};" + RT_LOADER + "})();</script>")


def rentracks_cv(cfg: dict, dir_name: str) -> str:
    """サンクスページ側。ここが成果の発火点。

    **注文IDがあるときだけ発火する。** 直接このURLを開かれた場合や、
    読み込み直した場合に成果を二重に立てないため。
    先方の却下条件にも「重複」が入っているので、こちらで防いでおく。
    """
    if not rentracks_on(cfg, dir_name):
        return ""
    rt = cfg["rentracks"]
    return (RT_MARK + "<script>(function(){"
            "var id='';try{id=sessionStorage.getItem('oh_order_id')||'';}catch(e){}"
            # 直接開かれたときは何もしない（空の成果を立てない）
            "if(!id){return;}"
            # 一度きり。読み込み直しでもう一度発火させない
            "try{sessionStorage.removeItem('oh_order_id');}catch(e){}"
            "var cb=function(){"
            "_rt.sid=%s;_rt.pid=%s;_rt.price=0;_rt.reward=-1;"
            # 氏名・電話・メールは渡さない。渡す必要が無く、
            # 渡せば個人情報を社外へ出すことになる（docs/レントラックス-成果計測の設計.md）
            "_rt.cname='';_rt.ctel='';_rt.cemail='';"
            "_rt.cinfo=encodeURIComponent(id);"
            "rt_tracktag();};"
            + RT_LOADER +
            "})();</script>") % (rt["sid"], rt["pid"])



def build_thanks(cfg: dict, meta: dict, out: pathlib.Path) -> None:
    """送信完了ページを組み立てる。

    ここは「Netlify Forms が受理した後にしか出ない画面」なので、成果
    （generate_lead）を数える場所として一番信用できる。
    以前は aircon と mizumawari の2枚を手で置いていたため、あとから足した
    aircon-b の分が無く、送信すると404になっていた。テンプレートから
    全ページ分を生成するように変えて、取りこぼしが起きないようにする。
    """
    # LP本体と同じく、設計のメモを公開ページに出さない。
    # 通していなかったため、テンプレートのコメントがそのまま本番に出ていた。
    tpl = strip_comments(THANKS_TEMPLATE.read_text(encoding="utf-8"))
    tel = tel_for(cfg, meta["dir"])
    page = {"kind": "thanks", "lp_id": meta["lp_id"], "lp_variant": meta["lp_variant"],
            "lead_value": (cfg.get("lead_value") or {}).get(meta["dir"], 0)}

    doc = (tpl.replace("%%DIR%%", meta["dir"])
              .replace("%%TEL_HREF%%", re.sub(r"[^0-9]", "", tel))
              .replace("%%TEL_TEXT%%", html.escape(tel))
              .replace("%%TRACKING_HEAD%%", tracking_head(cfg, page, tel))
              .replace("%%TRACKING_BODY%%",
                       tracking_body() + rentracks_cv(cfg, meta["dir"])))

    (out / meta["dir"] / "thanks.html").write_text(doc, encoding="utf-8")


HP_CSS = (
    "\n/* 自動投稿よけ。人間には見せない */\n"
    ".hp{position:absolute;left:-9999px;width:1px;height:1px;overflow:hidden;}\n"
)



JP_FONT = "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf"
LATIN_FONT = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"


def make_og(src: pathlib.Path, dst: pathlib.Path, line1: str, line2: str) -> None:
    """LINEやSNSに貼られたときのサムネイル（1200x630）をヒーロー写真から作る。"""
    from PIL import Image, ImageDraw, ImageFont

    im = Image.open(src)
    tw, th = 1200, 630
    ratio = tw / th
    if im.width / im.height > ratio:
        nw = int(im.height * ratio)
        im = im.crop(((im.width - nw) // 2, 0, (im.width - nw) // 2 + nw, im.height))
    else:
        nh = int(im.width / ratio)
        top = int((im.height - nh) * 0.35)
        im = im.crop((0, top, im.width, top + nh))
    im = im.resize((tw, th), Image.LANCZOS).convert("RGBA")

    band = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    draw = ImageDraw.Draw(band)
    draw.rectangle([0, th - 186, tw, th], fill=(13, 59, 92, 232))   # --ink
    draw.text((56, th - 160), line1, font=ImageFont.truetype(JP_FONT, 44), fill=(255, 255, 255, 255))
    draw.text((56, th - 92), line2, font=ImageFont.truetype(JP_FONT, 25), fill=(168, 194, 210, 255))  # --on-ink-2
    draw.text((56, th - 48), "ONE HITTER", font=ImageFont.truetype(LATIN_FONT, 26), fill=(111, 208, 228, 255))  # --aqua-ink

    out = Image.alpha_composite(im, band).convert("RGB")
    out.save(dst, quality=82, optimize=True, progressive=True)


# 「11月の早期予約は10%お得」の帯を入れるページ＝広告の着地LP（2026-10-05 オーナー決定）
BAND_PAGES = {"aircon", "aircon-c", "mizumawari", "mizumawari-b"}

# クチコミの件数を外す・98.6%の脚注を直すページ（承認が出るまで空。tools/bunmen-1010.py）
BUNMEN_PAGES: set = set()

# 申込の入口を予約ページに寄せるページ（承認が出るまで空。tools/iriguchi.py）
IRIGUCHI_PAGES: set = set()

# 交通費の一文・浴室の内訳を入れるページ（公開の承認が出るまで空。tools/chuuki-1008.py）
CHUUKI_PAGES: set = set()

# ギフトの入口を入れるページ（承認が出るまで空。build_page の中の説明を参照）
GIFT_PAGES: set = set()

# 担当者のイラスト（和真さん本人の確認が済んだものだけをここに置く）。
# 作り方は tools/make-staff-illust.py の冒頭を参照。写真そのものは置かない。
STAFF_IL = ROOT / "lp" / "_staff" / "staff.svg"


def build_page(name: str, meta: dict, target: str, out: pathlib.Path, cfg: dict) -> None:
    src = (ROOT / "lp" / name / "index.html").read_text(encoding="utf-8")
    src = manzoku(src)   # 満足度の差し込み（MANZOKU が唯一の出どころ）

    if FORM_OPEN not in src:
        raise SystemExit(f"{name}: フォームの開始タグが見つかりません")
    form = FORM_NETLIFY if target == "netlify" else FORM_PHP
    src = src.replace(FORM_OPEN, form.format(dir=meta["dir"], label=meta["label"]))

    # 蜂蜜罠のスタイルを、既存の .form の定義のすぐ後ろに足す
    anchor = ".form{background:var(--surface);"
    if anchor not in src:
        raise SystemExit(f"{name}: .form のスタイルが見つかりません")
    line_end = src.index("\n", src.index(anchor))
    src = src[:line_end] + HP_CSS.rstrip("\n") + src[line_end:]

    src = src.replace("</body>", "")  # 断片には無いはずだが念のため

    # 断片の先頭に Artifact 時代の <title> が残っていて、包むと <body> の中に
    # 2つ目のタイトルが入っていた。GA4は page_title を見るので、紛れの元になる。
    # 正しいタイトルは HEAD 側で付けているので、こちらは落とす。
    src = re.sub(r"^\s*<title>.*?</title>\s*", "", src, count=1, flags=re.S)
    head_meta = {k: v for k, v in meta.items()
                 if not k.startswith("og_") and k not in ("label", "lp_id", "lp_variant")}
    doc = HEAD.format(base=BASE_URL, **head_meta) + src + TAIL

    # 電話番号を計測用の発番に差し替える（設定が空なら何も起きない）
    tel = tel_for(cfg, meta["dir"])
    doc = swap_tel(doc, tel)

    dst = out / meta["dir"]
    dst.mkdir(parents=True, exist_ok=True)
    doc = strip_comments(doc)

    # 計測タグの差し込み。コメントを落としたあとに入れる
    # （strip_comments に消されないようにするため）。
    page = {"kind": "lp", "lp_id": meta["lp_id"], "lp_variant": meta["lp_variant"]}
    if TRACKING_SLOT not in doc:
        # strip_comments が目印ごと消すので、</head> を手がかりに入れる
        doc = doc.replace("</head>", tracking_head(cfg, page, tel) + "\n</head>", 1)
    else:
        doc = doc.replace(TRACKING_SLOT, tracking_head(cfg, page, tel), 1)
    # アフィリエイトのタグは </body> の直前（先方の手順書の推奨位置）。
    # 登録している掲載先のLPにだけ出る。
    doc = doc.replace("</body>", tracking_body() + order_id_script(meta["dir"])
                   + rentracks_lp(cfg, meta["dir"]) + "\n</body>", 1)

    # ギフトの「お知らせを受け取る」入口（lp/_parts/gift-oshirase.html）。
    # 掲出はオーナー承認事項（依頼 20261004-02-lp）。承認が出たら GIFT_PAGES に "nenmatsu" を足す。
    # 空のあいだはどのページにも入らない（別の用事の配信で一緒に公開されないように）。
    if meta["dir"] in GIFT_PAGES:
        import importlib.util
        spec = importlib.util.spec_from_file_location("insert_gift", ROOT / "tools" / "insert-gift.py")
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        doc = mod.insert(doc)

    # 広告の着地LPの「11月の早期予約は10%お得」の帯（依頼 20261005-01-lp）。12月1日からは帯の側で自動で隠れる
    if meta["dir"] in BAND_PAGES:
        import importlib.util
        spec = importlib.util.spec_from_file_location("insert_band", ROOT / "tools" / "insert-band.py")
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        doc = mod.insert(doc, meta["dir"])

    # 遠方の交通費の一文と浴室の「含まれるもの／オプション」（依頼 20261007-02-lp）。公開の承認が出たら CHUUKI_PAGES に足す
    if meta["dir"] in CHUUKI_PAGES:
        import importlib.util
        spec = importlib.util.spec_from_file_location("chuuki_1008", ROOT / "tools" / "chuuki-1008.py")
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        doc, _ = mod.apply(doc, meta["dir"])

    # 申込の入口を予約ページに寄せる（依頼 20261008-05-lp）。承認が出たら IRIGUCHI_PAGES に足す
    if meta["dir"] in IRIGUCHI_PAGES:
        import importlib.util
        spec = importlib.util.spec_from_file_location("iriguchi", ROOT / "tools" / "iriguchi.py")
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        doc = mod.apply(doc, meta["dir"])

    # クチコミの件数を外す・98.6%の脚注（依頼 20261008-04-lp）。承認が出たら BUNMEN_PAGES に足す
    if meta["dir"] in BUNMEN_PAGES:
        import importlib.util
        spec = importlib.util.spec_from_file_location("bunmen_1010", ROOT / "tools" / "bunmen-1010.py")
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        doc, _ = mod.apply(doc, meta["dir"])

    # 送信元の確認の隠し欄（ブラウザで送ったときだけ埋まる。依頼 20261008-01-lp）
    if target == "netlify":
        import importlib.util
        spec = importlib.util.spec_from_file_location("sousin_kakunin", ROOT / "tools" / "sousin-kakunin.py")
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        doc = mod.apply(doc)

    # 予約ページ（別ホスト）への引き継ぎに、どのLPから来たか（lp）を足す。
    # src・cid・ag・gclid は今の版と学習版で同じ値になり、A/B を区別できないため
    # （measurement 依頼 20261003-08-lp）。値はフォームの隠し欄 lp と同じ meta["dir"]。
    HIKITSUGU = "var hikitsugu = { src: src,"
    if HIKITSUGU in doc:
        doc = doc.replace(HIKITSUGU, "var hikitsugu = { lp: '" + meta["dir"] + "', src: src,", 1)

    # 申込内容のまとめと見積の隠し項目。受付番号のスクリプトより後ろに入る。
    # Netlify のフォームだけ（ほかの出し先は受け口が違う）
    if target == "netlify":
        doc = moushikomi.apply(doc, meta["dir"])

    # 担当者のイラスト。lp/_staff/staff.svg が置かれるまでは枠ごと外す
    # （空の枠や壊れた画像を本番に出さないため。置けば次の配信から4本に出る）
    if not STAFF_IL.exists():
        doc = re.sub(r'\s*<figure class="staff-il".*?</figure>', "", doc, flags=re.S)

    (dst / "index.html").write_text(doc, encoding="utf-8")
    build_thanks(cfg, meta, out)

    img_src = ROOT / "lp" / name / "img"
    img_dst = dst / "img"
    if img_dst.exists():
        shutil.rmtree(img_dst)
    shutil.copytree(img_src, img_dst)
    if STAFF_IL.exists() and 'class="staff-il"' in doc:
        shutil.copy(STAFF_IL, img_dst / "staff.svg")

    make_og(img_dst / "hero-bg.jpg", img_dst / "og.jpg", meta["og_line1"], meta["og_line2"])

    print(f"{dst.relative_to(ROOT)}/index.html  {len(doc)//1024}KB  "
          f"画像{len(list(img_dst.iterdir()))}点")


SURVEY_FORM_OPEN = '<form class="survey-form" onsubmit="return false;">'

# アンケートの回答の保存先。ここを通さないと、お客様には「ありがとうございました」が
# 出るのに回答はどこにも残らない（2026-09-19 に判明。それまで1件も保存されていなかった）。
#
# ・PAGES を通る3LPの差し替え（FORM_OPEN / FORM_NETLIFY）は
#   <form class="form" …> を見ているので、class="survey-form" のこのページには当たらない。
#   アンケートは copy_kanseihin を通るため、そちらの置換自体を通らない。
#   二重に外れていたので、誰も気づかなかった。
# ・送信は画面側の fetch（payload() が form.elements を集める）。
#   Netlify Forms は本文に form-name が要るので、隠し欄として form の中に置く。
#   payload() は name のある欄を全部拾うので、これで本文に入る。
# ・x_field は自動投稿よけ。Netlify 側で netlify-honeypot に指定する。
SURVEY_FORM_NETLIFY = (
    '<form class="survey-form" name="survey" method="post" action="/survey/"'
    ' data-netlify="true" netlify-honeypot="x_field">\n'
    '    <input type="hidden" name="form-name" value="survey">\n'
    '    <p hidden><label>この欄は入力しないでください <input name="x_field"></label></p>'
)


def survey_form(doc: str, target: str) -> str:
    """アンケートのフォームに、配信先に応じた送信先を差し込む。"""
    if SURVEY_FORM_OPEN not in doc:
        raise SystemExit(
            "lp/survey/index.html のフォーム開始タグが変わっています。"
            "差し込めないと回答が保存されないので、ここで止めます。"
        )
    if target != "netlify":
        # PHP版の送信先（/form/send.php）はアンケートの項目に対応していない。
        # 対応させるまでは、現状どおり送信先なしのままにする。
        return doc
    return doc.replace(SURVEY_FORM_OPEN, SURVEY_FORM_NETLIFY, 1)


# 完成品のうち、公開の承認待ちのもの。承認が出たらここから外す（外すまで deploy/ に出ない）。
# 確認は copy_kanseihin(ROOT / "preview" / "kansei", "preview") で preview/ に書き出す。
#   takara：タカラサービス様の確認とオーナー承認のあと（依頼 20261009-02-lp）
KANSEI_MACHI = {"takara"}


def copy_kanseihin(out: pathlib.Path, target: str) -> None:
    """完成した文書としてソースにあるページを、そのまま配信先へ写す。

    アンケート（lp/survey/）は断片ではなく <html> から始まる完成品なので
    PAGES を通らない。以前はビルドを経由せず deploy/ に直接置かれていて、
    ソースを直しても配信物に反映されず、両者がずれていた（2026-09-06）。
    """
    cfg = load_measurement()
    # tokushoho（特定商取引法に基づく表記）も同じ形の完成品。
    # PAGES に足すと lp_id や og の欄が要るが、これは商品ページではないので
    # こちら側で写す。ここに名前を足さないと、配信しても本番に出ない。
    # privacy（個人情報の取扱い）も同じ。公式サイトの 403 障害（2026-10-09）から、LP 等のリンク先はこちらが正。
    # takara（タカラサービス様の紹介カードのQRの受け皿。?src=card-t1〜t3）も同じ。依頼 20261009-02-lp
    for name in ("survey", "tokushoho", "privacy", "takara"):
        if name in KANSEI_MACHI and target != "preview":
            continue
        src = ROOT / "lp" / name / "index.html"
        if not src.exists():
            continue
        doc = strip_comments(src.read_text(encoding="utf-8"))

        # 完成品にも計測タグを入れる。ソース（lp/survey/）には手を触れず、
        # 書き出すときだけ足す。測定IDが空なら何も出ないので壊れない。
        # 入れないと「QRを見た人のうち何人が答えたか」が永久に分からない。
        page = {"kind": name, "lp_id": name, "lp_variant": "A"}
        doc = doc.replace("</head>", tracking_head(cfg, page) + "\n</head>", 1)
        doc = doc.replace("</body>", tracking_body() + "\n</body>", 1)

        if name == "survey":
            doc = survey_form(doc, target)

        dst = out / name
        dst.mkdir(parents=True, exist_ok=True)
        (dst / "index.html").write_text(doc, encoding="utf-8")

        # index.html 以外の添え物（_redirects・_headers・画像など）もそのまま写す。
        # 写さないと、ソースに置いた _redirects が配信物に入らず効かない。
        soeru = 0
        # 下のフォルダは img/ だけ写す（takara の写真）。survey/qr/ は印刷用の素材で、公開しない
        for f in sorted(list(src.parent.iterdir()) + sorted((src.parent / "img").glob("*"))):
            if f.is_file() and f != src:
                to = dst / f.relative_to(src.parent)
                to.parent.mkdir(parents=True, exist_ok=True)
                to.write_bytes(f.read_bytes())
                soeru += 1
        soe = f"＋添え物{soeru}件" if soeru else ""
        print(f"{dst.relative_to(ROOT)}/index.html  （完成品をそのまま複製＋計測タグ{soe}）")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "php"
    if target not in TARGETS:
        raise SystemExit(f"配信先は {' / '.join(TARGETS)} のいずれかです")
    out = TARGETS[target]["out"]
    cfg = load_measurement()

    # 下書きだけを preview/ に作る。deploy/ には一切書かない。
    if "--draft" in sys.argv:
        i = sys.argv.index("--draft")
        name = sys.argv[i + 1] if len(sys.argv) > i + 1 else ""
        if name not in DRAFTS:
            raise SystemExit(f"下書きは {' / '.join(DRAFTS)} のいずれかです")
        if name in PAGES:
            raise SystemExit(f"{name} は PAGES にもあります。下書きと配信対象を兼ねないでください")
        prev = ROOT / "preview" / target
        prev.mkdir(parents=True, exist_ok=True)
        build_page(name, DRAFTS[name], target, prev, cfg)
        print(f"下書き → {(prev / name).relative_to(ROOT)}/（本番には出ません）")
        raise SystemExit(0)

    out.mkdir(parents=True, exist_ok=True)

    ga4 = ((cfg.get("ga4") or {}).get("measurement_id") or "").strip() or "未設定"
    ads = ((cfg.get("google_ads") or {}).get("conversion_id") or "").strip() or "未設定"
    print(f"[{target}] → {out.relative_to(ROOT)}/")
    print(f"  計測： GA4 {ga4} ／ Google広告 {ads}")

    for name, meta in PAGES.items():
        tel = tel_for(cfg, meta["dir"])
        if tel != DEFAULT_TEL:
            print(f"  {meta['dir']}: 電話番号を {tel} に差し替え（コールトラッキング）")
        build_page(name, meta, target, out, cfg)

    copy_kanseihin(out, target)
