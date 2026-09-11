#!/usr/bin/env python3
"""節目チャネル（型②）の「読本」ページ一式を lp/media/dokuhon/ に組み立てる。

設計は docs/節目チャネル-全体構造.md 0-1。QRの先は「読本」。全体の80〜90%が読み物で、商品は末尾。

  akachan/index.html   赤ちゃんが来る前に知っておきたい、家の中の見えない汚れ
  pet/index.html       この子が来る前に知っておきたい、家の中の見えない汚れ
  setti/index.html     施設の承諾フォーム（設置場所の連絡→施設ID・QR発行）
  unei.html            運営者情報
  photos/              assets/photos から縮小コピー（実写のみ・特定できないもの）

数字と引用は docs/読本-出典.md にある「取得ページの原文」だけを使う。ここに無い数字は書かない。
料金は data/prices.json から入れる（手で書かない）。`?src=施設ID` は末尾の予約・点検のリンクに引き継ぐ。

使い方:
  python3 tools/build-dokuhon.py
"""
import pathlib
import sys

from PIL import Image, ImageOps

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import media_common as C  # noqa: E402

OUTDIR = C.ROOT / "lp" / "media" / "dokuhon"
PHOTOS_SRC = C.ROOT / "assets" / "photos"
BRAND = "読本"
BRAND_SUB = "ワンヒッター｜家の中の見えない汚れ"
FORM_SETTI = "dokuhon-setti"
REVIEW_COUNT = 24            # Googleクチコミ件数（2026-09 CMO更新値。week-01.md と同じ）
REVIEW_ASOF = "2026年9月時点"
SURVEY = "98.6%（2023年1月〜2025年12月・209名中206名）"

# 使う写真（docs/photo-inventory.md で掲載可・お宅が特定できないもの）
PHOTOS = {
    "7963": ("IMG_7963.jpg", "エアコンの吹き出し口（作業前・2026年9月の現場）"),
    "7969": ("IMG_7969.jpg", "同じ場所（作業後）。7963と同一箇所・確認済み"),
    "7965": ("IMG_7965.jpg", "同じエアコンの熱交換器（作業前）。フィルターの奥にある部品"),
    "7976": ("IMG_7976.jpg", "このエアコン1台を洗ったあとの水"),
    "7877": ("IMG_7877.jpg", "レンジフードのシロッコファン（作業前・2026年8月の現場）"),
    "7880": ("IMG_7880.jpg", "同じファンを別の角度から"),
    "7787": ("IMG_7787.jpg", "壁掛けエアコン（作業後・2026年8月の現場）"),
    "7987": ("IMG_7987.jpg", "浴室（作業後・2026年9月の現場）"),
}

# 出典（docs/読本-出典.md と同じ。原文どおりに引用する）
SRC = {
    "tokyo9": ("東京都「健康・快適居住環境の指針」指針No.9 室内のカビ対策（平成28年度改定版）", "https://www.hokeniryo.metro.tokyo.lg.jp/documents/d/hokeniryo/web_bunya3"),
    "navi": ("東京都アレルギー情報navi.「室内環境対策」", "https://www.hokeniryo1.metro.tokyo.lg.jp/allergy/measure/indoor.html"),
    "daikin": ("ダイキン「エアコンのお手入れについて（ルームエアコン）」", "https://www.daikincc.com/faq/customer/web/knowledge2700.html"),
    "mitsubishi": ("三菱電機 FAQ「エアコン内部の洗浄について」", "https://faq01.mitsubishielectric.co.jp/faq/show/712?site_domain=default"),
    "mitsubishi2": ("三菱電機 FAQ「市販の洗浄スプレーは使用できますか？」", "https://faq01.mitsubishielectric.co.jp/faq/show/2655?site_domain=default"),
    "nite": ("NITE「エアコンの内部洗浄による事故に注意」（令和2年6月25日）", "https://www.nite.go.jp/jiko/chuikanki/press/2020fy/prs200625.html"),
    "aichi": ("愛知県 江南保健所「家庭内におけるレジオネラ対策について」", "https://www.pref.aichi.jp/soshiki/konan-hc/0000059867.html"),
}


def css():
    return """
.book h2{font-family:"Shippori Mincho B1",serif;font-size:clamp(20px,5.4vw,25px);line-height:1.45;margin:34px 0 12px;}
.book h2 small{display:block;font-family:"Barlow",sans-serif;font-size:11px;letter-spacing:.18em;color:var(--accent);margin-bottom:6px;}
.book p{font-size:15.5px;line-height:2;margin:0 0 14px;}
.book .quote{border-left:4px solid var(--accent);padding:6px 0 6px 14px;margin:14px 0;font-size:14px;line-height:1.9;color:var(--ink-soft);background:var(--surface);border-radius:0 8px 8px 0;}
.book .quote cite{display:block;font-style:normal;font-size:11.5px;color:var(--muted);margin-top:6px;}
.book .quote a{color:var(--muted);}
.book .photo{margin:14px 0 18px;}
.book .kazu{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:14px 0;}
.book .kazu div{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:12px;}
.book .kazu b{display:block;font-family:"Barlow",sans-serif;font-size:30px;line-height:1.1;color:var(--accent-deep);}
.book .kazu span{font-size:12px;color:var(--muted);line-height:1.6;display:block;margin-top:4px;}
.book ul{padding-left:1.3em;font-size:15px;line-height:1.95;margin:0 0 14px;}
.book .dekiru{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin:0 0 10px;}
.book .dekiru b{display:block;margin-bottom:4px;}
.book .dekiru.ng b{color:var(--cta-text);}
.title{padding:26px 0 8px;}
.title h1{font-family:"Shippori Mincho B1",serif;font-size:clamp(23px,6.4vw,30px);line-height:1.5;}
.title .sub{font-size:14px;color:var(--ink-soft);margin-top:10px;line-height:1.8;}
.title .who{font-size:12px;color:var(--muted);margin-top:8px;}
.toc{font-size:13.5px;line-height:1.9;color:var(--ink-soft);background:var(--surface-2);border-radius:10px;padding:12px 16px;margin:18px 0 6px;}
.toc ol{margin:0;padding-left:1.4em;}
.shouhin{border:2px solid var(--accent);border-radius:12px;padding:16px;background:var(--surface);margin:10px 0 14px;}
.shouhin h3{font-size:18px;margin-bottom:6px;}
.shouhin .ln{display:flex;justify-content:space-between;gap:10px;font-size:14px;line-height:1.8;}
.shouhin .ln.sum{font-size:20px;font-weight:900;border-top:1px solid var(--line-strong);padding-top:6px;margin-top:4px;}
.shouhin .v{font-family:"Barlow",sans-serif;white-space:nowrap;}
.shouhin .btn{width:100%;margin-top:10px;}
.tenken{border:1.5px solid var(--line-strong);border-radius:12px;padding:14px 16px;background:var(--surface-2);}
.proof{font-size:12.5px;color:var(--muted);line-height:1.8;margin-top:10px;}
.sources{font-size:11.5px;color:var(--muted);line-height:1.8;margin-top:26px;border-top:1px solid var(--line);padding-top:12px;}
.sources ol{padding-left:1.4em;margin:6px 0 0;}
.sources a{color:var(--muted);word-break:break-all;}
.ending{font-family:"Shippori Mincho B1",serif;font-size:16px;line-height:2;margin:26px 0 10px;}
.dl{display:flex;gap:8px;flex-wrap:wrap;}
"""


def photo(key: str, extra_stamp: str = "") -> str:
    fn, cap = PHOTOS[key]
    return f'<figure class="photo"><img src="../photos/{fn}" alt="{C.esc(cap)}" loading="lazy"><figcaption><span class="stamp">実際の現場写真・合成なし</span>{C.esc(cap)}{C.esc(extra_stamp)}</figcaption></figure>'


def quote(text: str, key: str) -> str:
    name, url = SRC[key]
    return f'<blockquote class="quote">「{C.esc(text)}」<cite>出典：<a href="{url}" target="_blank" rel="noopener">{C.esc(name)}</a></cite></blockquote>'


def sources_html(keys) -> str:
    items = "".join(f'<li>{C.esc(SRC[k][0])}<br><a href="{SRC[k][1]}" target="_blank" rel="noopener">{SRC[k][1]}</a></li>' for k in keys)
    return f'<div class="sources"><b>出典（すべて2026年9月11日に確認）</b><ol>{items}</ol><p>引用は原文のままです。当社の写真は、すべて当社が施工した現場で撮ったもので、合成・加工はしていません。お宅が特定できる写真は使っていません。</p></div>'


def build_book(kind: str, P: dict) -> str:
    m, o = P["menus"], P["opts"]
    baby = kind == "akachan"
    ko = "赤ちゃん" if baby else "この子"
    title = f"{ko}が来る前に知っておきたい、家の中の見えない汚れ"
    second_name = "浴室" if baby else "換気扇（レンジフード）"
    second_price = m["浴室クリーニング"]["同時施工"] if baby else m["レンジフードクリーニング"]["同時施工"]
    aircon = m["エアコンクリーニング（ノーマル）"]["単体"]
    total = aircon + second_price
    product = f"{'赤ちゃん' if baby else 'ペット'}を迎える前のエアコン＋{'浴室' if baby else '換気扇'}"
    src_key = "akachan" if baby else "pet"

    # ---- 5章（現場で見てきたこと）は種別で変える。数字は書かない
    if baby:
        ch5 = f"""
<p>出産を控えたご家庭から、私たちがよくいただくのは「生まれる前に、家をひととおりきれいにしておきたい」というご依頼です。そのとき、どこを見るか。私たちなら、まずエアコンと浴室です。</p>
<p>理由は単純で、赤ちゃんはこの2つの近くで、いちばん長い時間を過ごすからです。エアコンの風の下で寝て、浴室で毎日お湯につかる。どちらも「中」が見えない場所で、しかも上の章の東京都の調査が示すとおり、カビがいちばん生えやすい場所でもあります。</p>
<p>生まれてからは、分かります。頼みたくても、赤ちゃんを抱えたまま作業の2〜3時間を家で過ごすのは、思った以上に大変です。だから私たちは、迎える前の1〜2か月のあいだに、と申し上げています。</p>
"""
    else:
        ch5 = f"""
<p>犬や猫を迎えるご家庭から、私たちがよくいただくのは「来る前に、家をひととおりきれいにしておきたい」というご依頼です。そのとき、どこを見るか。私たちなら、まずエアコンとキッチンの換気扇です。</p>
<p>エアコンは、この子が一日じゅう過ごす部屋の空気そのものです。そして換気扇（レンジフード）は、迎えたあとに掃除がいちばん難しくなる場所です。油で覆われたファンには毛やほこりがよく付き、ここが汚れていると台所の空気が抜けません。</p>
<p>来てからは、分かります。この子がいる部屋で、分解した部品を並べて洗う2〜3時間は、お互いに落ち着きません。だから私たちは、迎える前に、と申し上げています。</p>
"""

    body = f"""
  <article class="book">
    <div class="title">
      <span class="eyebrow">読本｜読むだけ・無料</span>
      <h1>{C.esc(title)}</h1>
      <p class="sub">江戸川区のハウスクリーニング店が、実際の現場の写真と、東京都・メーカーの公表資料の数字でお話しします。</p>
      <p class="who">書いたのは、{C.UNEI}（江戸川区北葛西）の現場の者です。売り込みの資料ではありません。頼むかどうかは、読み終わってから決めてください。</p>
    </div>
    <nav class="toc"><ol>
      <li>見えないから、気にならない</li><li>どれだけ溜まるか</li><li>数字で見る</li><li>自分でできること、できないこと</li>
      <li>{C.esc(ko)}が来る家で、私たちが見てきたこと</li><li>いつ、何を</li><li>頼む場合（ここだけ商品の話です）</li></ol></nav>

    <h2><small>1</small>見えないから、気にならない</h2>
    <p>これは「フィルターはこまめに掃除している」というお宅のエアコンです。吹き出し口に、黒い点が並んでいます。</p>
    {photo("7963")}
    <p>フィルターは、エアコンの入口にある網です。そこを掃除しても、その奥にある熱交換器（アルミの薄い板が並んだ部品）と、風を送るファンには手が届きません。同じエアコンの、フィルターを外した奥がこれです。</p>
    {photo("7965")}
    <p>私たちの現場では、吹き出し口に黒い点が見えるとき、その奥のファンや熱交換器にも同じ黒い汚れが付いていることがほとんどです。見えないから、気にならない。気にならないから、そのまま何年も風が通る。それだけのことなのですが、そのままにしておく理由もありません。</p>

    <h2><small>2</small>どれだけ溜まるか</h2>
    <p>言葉で「汚れている」と言われても、ぴんと来ないと思います。私たちがいちばん分かりやすいと思っているのが、洗ったあとの水です。1章のエアコン1台を、分解して洗ったあとの水がこれです。</p>
    {photo("7976")}
    <p>これがフィルターの奥に、風の通り道として溜まっていたものです。洗う前は、外からは見えませんでした。</p>
    <p>台所の換気扇も同じです。レンジフードの中のファン（シロッコファン）は、ふだん外から見えません。外すと、こうなっています。</p>
    <div class="pair">{photo("7877")}{photo("7880")}</div>
    <p>油は、ほこりや毛を抱き込んで層になります。ここまでになると、市販の洗剤を吹きかけても落ちず、外して、つけ置きして、洗うしかありません。</p>

    <h2><small>3</small>数字で見る</h2>
    <p>ここからは、私たちの言葉ではなく、東京都が公表している調査の数字です。</p>
    <div class="kazu">
      <div><b>33.7%</b><span>過去3年間にカビが生えたことがあると回答した世帯（東京都のアンケート調査）</span></div>
      <div><b>79.7%</b><span>カビが生えた世帯のうち、発生場所が浴室だった割合（同）</span></div>
    </div>
    {quote("東京都が実施したアンケート調査では、過去3年間にカビが生えたことがあると回答した世帯は全体の33.7％（295世帯）でした。　カビが生えたことのある世帯のカビの発生場所は、浴室が79.7％と最も多く、押入れ・洗面所・寝室でも20％を超えていました。", "tokyo9")}
    <p>カビが生えやすい条件も、同じ資料にあります。</p>
    {quote("普段からカビの発生しにくい環境づくりを心掛けましょう。① 温度：20～35℃前後② 湿度：70％以上③ 栄養源等：手アカなどによる汚れ、石けんのカス、壁紙及び壁紙のノリ、結露した水、加湿器の水等", "tokyo9")}
    <p>温度20〜35℃、湿度70%以上、栄養になる汚れ。浴室と、冷房中に内部が結露するエアコンは、この3つがそろう場所です。同じ資料は、代表的なカビの生える場所として「浴室やトイレの壁・タイル目地、エアコン・加湿器・洗濯機の内部」を挙げています。</p>
    <p>健康との関係については、私たちは何も断定しません。東京都の資料に書いてある一文だけ、そのまま引きます。</p>
    {quote("室内を浮遊するカビの胞子や菌糸の断片を吸い込むと、体質によってはぜん息などを引き起こすことがあります。", "tokyo9")}
    <p>もう1つ、エアコンの内部洗浄について、製品事故を調べている国の機関（NITE）が2020年に出した注意喚起です。</p>
    {quote("エアコンの事故は2015年度から2019年度の5年間に合計263件発生し、うち火災が244件、死亡事故が6件（7名）です。", "nite")}
    {quote("今後、特に発生が心配なエアコンの事故は、誤った内部洗浄方法による火災事故です。2019年度までの5年間に20件発生しています。", "nite")}
    <p>「中を洗う」こと自体は必要でも、自分で洗浄液を入れるやり方には事故の記録がある、ということです。これは次の章につながります。</p>

    <h2><small>4</small>自分でできること、できないこと</h2>
    <p>プロに頼まなくてよいことは、たくさんあります。順にお話しします。</p>
    <div class="dekiru"><b>自分でできる：フィルターの水洗い</b>電源を切って外し、ぬるま湯で洗い、陰干しして戻す。洗剤は要りません。東京都アレルギー情報navi.は、次の目安を示しています。</div>
    {quote("目安として年に3～4回、少なくとも、冷房暖房シーズンの変わり目には実施する", "navi")}
    <div class="dekiru"><b>自分でできる：吹き出し口とルーバー（羽根）を拭く</b>固く絞った布で。黒い点が付いたら、その奥はもっと汚れているという合図です。</div>
    <div class="dekiru ng"><b>やらないでほしい：市販の洗浄スプレーを中に吹き込む</b>これは私たちの意見ではなく、メーカーの公式な案内です。</div>
    {quote("市販の洗浄スプレーは、ご使用しないでください。", "daikin")}
    {quote("市販の洗浄スプレーのご使用はお控えください。", "mitsubishi2")}
    {quote("エアコンの内部洗浄は、お客様自身で実施せずに、高い専門知識を有する業者に依頼をしてください。", "mitsubishi")}
    <p>熱交換器・送風ファン・ドレン（排水の通り道）・換気扇のシロッコファンは、外すか、分解しないと洗えません。ここから先が、私たちの仕事です。</p>

    <h2><small>5</small>{C.esc(ko)}が来る家で、私たちが見てきたこと</h2>
    {ch5}

    <h2><small>6</small>いつ、何を</h2>
    <ul>
      <li><b>時期：</b>迎える前の1〜2か月。家に人が増える前が、いちばん落ち着いて頼める時期です。</li>
      <li><b>混む時期：</b>当社では5〜7月と12月を繁忙期にしていて、この時期は予約が取りにくく、料金も繁忙期の加算があります。それ以外の月のほうが、日程も料金も選びやすいです。</li>
      <li><b>まず自分で見る：</b>エアコンの電源を切り、吹き出し口の羽根を手で下に向け、懐中電灯（スマホのライト）で奥を照らしてください。黒い点や綿ぼこりが見えたら、中も同じです。何も見えなければ、今は急ぐ必要はありません。</li>
      <li><b>{'浴室：' if baby else '換気扇：'}</b>{'天井や壁の隅、ドアのパッキン、エプロン（浴槽の側面のカバー）の内側。エプロンは外せる機種が多く、外すと中が見えます。' if baby else 'レンジフードのフィルターを外して、奥のファンを懐中電灯で。油が指に付く状態なら、ファンも同じです。'}</li>
    </ul>
    <p class="ending">ここまでが、お伝えしたかったことの全部です。<br>読んでいただいて、ありがとうございました。</p>

    <h2><small>7</small>頼む場合</h2>
    <p>ここからは商品の話です。必要な方だけお読みください。</p>
    <div class="shouhin">
      <h3>{C.esc(product)}</h3>
      <div class="ln"><span>エアコンクリーニング 1台（壁掛け・ノーマルタイプ）</span><span class="v">{C.yen(aircon)}</span></div>
      <div class="ln"><span>{C.esc(second_name)}クリーニング（同時施工の料金）</span><span class="v">{C.yen(second_price)}</span></div>
      <div class="ln sum"><span>合計（税込）</span><span class="v">{C.yen(total)}</span></div>
      <p class="note" style="margin-top:6px">出張費・駐車場代・追加作業費はいただきません。お掃除機能付きエアコンは {C.yen(m['エアコンクリーニング（お掃除機能付き）']['単体'])}。5〜7月・12月は繁忙期加算 {C.yen(P['raw']['繁忙期加算']['金額'])}。分解して部品ごとに洗い、洗ったあとの水もお見せします。</p>
      <a class="btn lg" id="btn-yoyaku" href="{C.BOOKING}">この内容で予約する</a>
      <p class="proof">ご利用後のアンケートで「他の人にすすめたい」 {SURVEY}／Googleクチコミ ★5.0（{REVIEW_COUNT}件・{REVIEW_ASOF}）／対応エリア 東京都・千葉県・神奈川県</p>
    </div>
    <div class="tenken">
      <b>まだ決めない方へ：まず無料で「中」を見てもらう</b>
      <p style="font-size:14px;line-height:1.9;margin:6px 0 10px">洗濯槽の裏側（内視鏡カメラ）と追い焚き配管（汚れの数値）を、その場で一緒に見ます。10分ほど。汚れていなければ「今回は不要」とお伝えします。閑散期限定。</p>
      <a class="btn ghost" id="btn-tenken" href="{C.TENKEN_URL}/" style="width:100%">無料点検を申し込む</a>
    </div>
    <p class="note" style="margin-top:12px">このページを置いてくださった施設には、ご利用があった場合に当社から紹介料をお支払いすることがあります（医療法人など、受け取れない施設には情報提供のみでお願いしています）。お客様の料金に上乗せはありません。</p>
    {sources_html(["tokyo9", "navi", "daikin", "mitsubishi2", "mitsubishi", "nite"])}
  </article>
<script>
(function(){{
  var src = (new URLSearchParams(location.search)).get('src') || '{src_key}';
  var y = document.getElementById('btn-yoyaku'), t = document.getElementById('btn-tenken');
  y.href = '{C.BOOKING}?src=' + encodeURIComponent('dokuhon-' + src);
  t.href = '{C.TENKEN_URL}/?src=' + encodeURIComponent('dokuhon-' + src);
}})();
</script>
"""
    return C.head(f"{title}｜ワンヒッター", "江戸川区のハウスクリーニング店が、実際の現場の写真と東京都の調査の数字で、家の中の見えない汚れをお話しします。読むだけ・無料。", BRAND, BRAND_SUB, css(), home="../", unei_href="../unei.html") + body + C.foot(BRAND, "この読み物は、当社が施工した現場の写真と、公表資料の引用だけで書いています。", unei_href="../unei.html")


def build_setti() -> str:
    body = f"""
  <div class="intro">
    <span class="eyebrow">設置のご連絡（1分）</span>
    <h1>カードを置いていただける施設の方へ</h1>
    <p class="lead" style="font-size:14.5px">ありがとうございます。設置場所だけお知らせください。折り返し、貴施設専用のQRカード（PDF）と、毎週の閲覧数のお知らせをお送りします。</p>
  </div>
  <form class="survey-form" id="f" onsubmit="return false;" novalidate>
    <div class="q">
      <div class="field"><label for="s-name">施設名</label><input id="s-name" type="text" autocomplete="organization" placeholder="例：◯◯レディースクリニック／◯◯ペットショップ"></div>
      <div class="field"><label for="s-houjin">運営法人の正式名称（分かれば）</label><input id="s-houjin" type="text" placeholder="例：医療法人社団◯◯会／株式会社◯◯／個人"><p class="hint" id="s-houjin-hint"></p></div>
      <div class="field"><label for="s-kind">施設の種別</label><select id="s-kind"><option value="">選んでください</option>
        <option>産婦人科・産院</option><option>小児科</option><option>子育て支援・保育</option><option>ベビー用品店</option>
        <option>ペットショップ</option><option>動物病院</option><option>トリミング</option><option>その他</option></select></div>
      <div class="field"><label for="s-tantou">ご担当者名</label><input id="s-tantou" type="text" autocomplete="name"></div>
      <div class="field"><label for="s-mail">メールアドレス（週次のお知らせ先）</label><input id="s-mail" type="email" inputmode="email" autocomplete="email"></div>
      <div class="field"><label for="s-addr">施設の住所</label><input id="s-addr" type="text" autocomplete="street-address"></div>
      <div class="field"><label for="s-place">カードを置く場所</label><select id="s-place"><option value="">選んでください</option><option>受付・レジ横</option><option>待合</option><option>掲示板</option><option>その他</option></select></div>
      <div class="field"><label>カードの用意</label>
        <label class="agree"><input type="radio" name="print" value="PDFを自分で印刷"><span>PDFを送ってもらい、施設で印刷する（A6・普通紙で構いません）</span></label>
        <label class="agree"><input type="radio" name="print" value="印刷して郵送"><span>印刷したカードを郵送してほしい（1〜2週間）</span></label></div>
      <label class="agree"><input type="checkbox" id="s-agree"><span>カードはいつでも撤去できること、週次のお知らせはメール1通で止められることを確認しました。</span></label>
      <input type="text" id="s-hp" name="bot-field" tabindex="-1" autocomplete="off" class="hp" aria-hidden="true">
      <p class="err" id="se"></p>
      <button type="button" class="btn lg" id="send">この内容で送る</button>
    </div>
    <section class="q done" id="done" hidden>
      <div class="head"><h2>ありがとうございます。</h2></div>
      <p class="why" style="font-size:13.5px">貴施設のID：<b id="d-id" class="num"></b><br>このIDの入ったQRカード（PDF）を、いただいたメールアドレスへ1営業日以内にお送りします。下は、貴施設専用の読本のQRです（このままスクリーンショットで使っていただいても構いません）。</p>
      <div class="qr"><div id="qrcode"></div><p class="note" id="d-url" style="word-break:break-all;text-align:center"></p></div>
      <p class="note" id="d-houshuu" style="margin-top:10px"></p>
    </section>
  </form>
<script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
<script>
(function(){{
  var $ = function(id){{ return document.getElementById(id); }};
  var Q = new URLSearchParams(location.search);
  var NASHI = ['医療法人','社会福祉法人','学校法人','特定非営利','区立','市立','都立','県立','国立'];
  function houshuuKata(h){{ for (var i=0;i<NASHI.length;i++) if (h.indexOf(NASHI[i]) >= 0) return '報酬なし型'; return '12%型'; }}
  $('s-houjin').addEventListener('input', function(){{
    $('s-houjin-hint').textContent = (houshuuKata(this.value) === '報酬なし型') ? '医療法人・社会福祉法人・学校法人・自治体などの施設には紹介料をお支払いしません（情報提供のみ）。' : '';
  }});
  function makeId(){{ var s = ''; var a = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'; for (var i=0;i<6;i++) s += a[Math.floor(Math.random()*a.length)]; return 'F' + s; }}
  var sending = false;
  $('send').addEventListener('click', function(){{
    if (sending || $('s-hp').value) return;
    var pr = document.querySelector('input[name="print"]:checked');
    if (!$('s-name').value.trim()) return $('se').textContent = '施設名を入れてください。';
    if (!$('s-kind').value) return $('se').textContent = '施設の種別を選んでください。';
    if (!$('s-mail').value.trim()) return $('se').textContent = 'メールアドレスを入れてください（QRカードの送付先です）。';
    if (!$('s-place').value) return $('se').textContent = 'カードを置く場所を選んでください。';
    if (!pr) return $('se').textContent = 'カードの用意を選んでください。';
    if (!$('s-agree').checked) return $('se').textContent = '確認にチェックをお願いします。';
    var id = Q.get('f') || makeId();
    var kind = $('s-kind').value, hen = (/産|小児|子育て|保育|ベビー/.test(kind)) ? 'akachan' : (/ペット|動物|トリミング/.test(kind)) ? 'pet' : 'akachan';
    var url = '{C.DOKUHON_URL}/' + hen + '/?src=' + id;
    var atai = {{ '施設ID': id, '施設名': $('s-name').value.trim(), '法人名': $('s-houjin').value.trim(), '報酬型': houshuuKata($('s-houjin').value), '種別': kind, '読本': hen,
      '担当者': $('s-tantou').value.trim(), 'メール': $('s-mail').value.trim(), '住所': $('s-addr').value.trim(), '設置場所': $('s-place').value, 'カード': pr.value, '読本URL': url, '送信時刻': new Date().toISOString() }};
    var fd = new FormData(); fd.append('form-name', '{FORM_SETTI}'); Object.keys(atai).forEach(function(k){{ fd.append(k, atai[k]); }});
    sending = true; $('send').disabled = true; $('send').textContent = '送信しています…';
    fetch(location.pathname, {{method:'POST', body:fd}}).then(function(r){{ if (!r.ok) throw new Error('送信できませんでした（'+r.status+'）');
      $('d-id').textContent = id; $('d-url').textContent = url; new QRCode($('qrcode'), {{text:url, width:220, height:220}});
      $('d-houshuu').textContent = (atai['報酬型'] === '12%型') ? '貴施設のカードからご利用があった場合、ご利用額の12%を月末締め・翌月末にお支払いします（支払通知を自動でお送りします）。' : '貴施設には紹介料をお支払いしない形（情報提供のみ）でお願いしています。';
      $('f').querySelector('.q').hidden = true; document.querySelector('.intro').hidden = true; $('done').hidden = false; window.scrollTo(0,0);
    }}).catch(function(e){{ sending = false; $('send').disabled = false; $('send').textContent = 'この内容で送る'; $('se').textContent = String(e.message||e); }});
  }});
}})();
</script>
<form name="{FORM_SETTI}" data-netlify="true" netlify-honeypot="bot-field" hidden>
  <input type="hidden" name="form-name" value="{FORM_SETTI}"><input type="text" name="bot-field">
  <input type="text" name="施設ID"><input type="text" name="施設名"><input type="text" name="法人名"><input type="text" name="報酬型"><input type="text" name="種別"><input type="text" name="読本">
  <input type="text" name="担当者"><input type="text" name="メール"><input type="text" name="住所"><input type="text" name="設置場所"><input type="text" name="カード"><input type="text" name="読本URL"><input type="text" name="送信時刻">
</form>
"""
    return C.head("カード設置のご連絡｜ワンヒッター 読本", "施設の方の設置連絡フォーム", BRAND, BRAND_SUB, css(), home="../", unei_href="../unei.html") + body + C.foot(BRAND, "", unei_href="../unei.html")


def build_top() -> str:
    body = f"""
  <div class="intro"><span class="eyebrow">読本</span><h1>家の中の見えない汚れ</h1>
    <p class="lead">江戸川区のハウスクリーニング店が、実際の現場の写真と公表資料の数字でお話しする読み物です。</p></div>
  <div class="q" style="display:flex;flex-direction:column;gap:10px">
    <a class="btn lg" href="./akachan/">赤ちゃんが来る前に知っておきたい、家の中の見えない汚れ</a>
    <a class="btn lg" href="./pet/">この子が来る前に知っておきたい、家の中の見えない汚れ</a>
    <a class="btn ghost" href="./setti/">施設の方：カード設置のご連絡</a>
  </div>
"""
    return C.head("読本｜ワンヒッター", "家の中の見えない汚れ", BRAND, BRAND_SUB, css()) + body + C.foot(BRAND, "")


def build_unei() -> str:
    rows = C.UNEI_ROWS_COMMON + [
        ("この読み物について", "赤ちゃん・ペットを迎えるご家庭向けに、当社が施工した現場の写真と、東京都・メーカー・NITEの公表資料の引用だけで書いています。健康への影響は断定していません。末尾に当社のクリーニングと無料点検のご案内があります。"),
        ("設置施設への紹介料", "カードを置いてくださった施設のうち、株式会社・個人事業などの施設には、ご利用額の12%を紹介料としてお支払いすることがあります。医療法人・社会福祉法人・学校法人・自治体の施設にはお支払いしません。お客様の料金に上乗せはありません。"),
    ]
    return C.unei_page(BRAND, BRAND_SUB, rows, "読本に戻る")


def copy_photos():
    dst = OUTDIR / "photos"
    dst.mkdir(parents=True, exist_ok=True)
    for fn, _ in PHOTOS.values():
        src = PHOTOS_SRC / fn
        if not src.exists():
            sys.exit(f"写真がありません: {src}")
        im = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
        im.thumbnail((1200, 1200))
        im.save(dst / fn, "JPEG", quality=82, optimize=True, progressive=True)


def main():
    P = C.prices()
    for k in ("エアコンクリーニング（ノーマル）", "浴室クリーニング", "レンジフードクリーニング", "エアコンクリーニング（お掃除機能付き）"):
        if k not in P["menus"]:
            sys.exit(f"prices.json に無いメニュー名: {k}")
    copy_photos()
    for kind in ("akachan", "pet"):
        d = OUTDIR / kind
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(build_book(kind, P), encoding="utf-8")
    (OUTDIR / "setti").mkdir(exist_ok=True)
    (OUTDIR / "setti" / "index.html").write_text(build_setti(), encoding="utf-8")
    (OUTDIR / "index.html").write_text(build_top(), encoding="utf-8")
    (OUTDIR / "unei.html").write_text(build_unei(), encoding="utf-8")
    print("書き出しました:", OUTDIR)


if __name__ == "__main__":
    main()
