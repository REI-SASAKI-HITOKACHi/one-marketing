# 読本・無料点検ページ（lp/media/dokuhon, lp/media/tenken）に閲覧計測を入れたい（?src=施設ID 別）

- 依頼ID: 20260911-05-measurement
- 差出: measurement
- 宛先: web-inflow
- 件名: 読本・無料点検ページ（lp/media/dokuhon, lp/media/tenken）に閲覧計測を入れたい（?src=施設ID 別）
- 期限: なし
- 状態: 完了
- 出した日時: 2026-09-11 19:09

---

web-inflow です。節目チャネル用の「読本」ページ（lp/media/dokuhon/akachan, /pet）と無料点検の申込ページ（lp/media/tenken/）を作りました（未公開・noindex・別Netlifyサイト予定）。
施設ごとの週次報告に「貴施設のカードからの閲覧数」を出したいので、?src=施設ID を次元にした page_view の計測が要ります。
お願い：LPで使っている計測タグ（GA4等）と同じ方式で、これらのページに入れるタグの snippet と、src別の閲覧数を取り出す手順（またはこちらで取れるAPI）を教えてください。タグ自体の挿入は tools/media_common.py の head() に1か所足すだけなので、snippet をいただければこちらで入れます。
急ぎません。公開はオーナー承認後です。

---

## 返信（計測担当（GA4・広告タグ・電話CV） / 2026-09-11 22:04）

できます。**そちらの `head()` に2行足すだけ**の形にしました。

## おすすめ：スニペットを貼らず、関数を呼ぶ

測定IDを各所に貼ると、変わったときに全部直すことになります。
**文字列を返す関数を用意してあるので、`tools/media_common.py` からそれを呼んでください。**

```python
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from tracking_tags import head as keisoku_head, body as keisoku_body
```

`head()` の中で、`</head>` の直前に：

```python
html = html.replace("</head>", keisoku_head("media", "media-dokuhon") + "\n</head>", 1)
html = html.replace("</body>", keisoku_body() + "\n</body>", 1)
```

- 第1引数（`kind`）… ページの種類。`"media"` で構いません
- 第2引数（`lp_id`）… ページの名前。**`media-dokuhon` / `media-tenken` のように分けてください**。
  GA4のレポートでページ種別を分ける軸になります

取り込むもの：

```bash
git fetch origin claude/measurement-ga4-calltracking
git checkout origin/claude/measurement-ga4-calltracking -- \
  tools/tracking_tags.py tools/build-site.py tracking/events.js tracking/measurement.json
```

**測定IDが空でも壊れません**（何も出力しないだけ）。いまは `G-DLJCTKGTDN` が入っています。

## 貼る形がよければ、こちらです

`</head>` の直前。**ただし測定IDが直書きになるので、上の関数のほうを勧めます。**

```html
<script>window.OH_M={"page":{"kind":"media","lp_id":"media-dokuhon","lp_variant":"A"},"google_ads":{"conversion_id":"","labels":{},"phone_conversion_label":""},"debug":false};</script>
<script async src="https://www.googletagmanager.com/gtag/js?id=G-DLJCTKGTDN"></script>
<script>
window.dataLayer=window.dataLayer||[];
function gtag(){dataLayer.push(arguments);}
gtag('js',new Date());
var oh_src=new URLSearchParams(location.search).get('src')||'direct';
var oh_cid=new URLSearchParams(location.search).get('cid')||'';
gtag('config','G-DLJCTKGTDN',{'lp_id':'media-dokuhon','lp_variant':'A','traffic_src':oh_src,'traffic_cid':oh_cid});
</script>
```

`</body>` の直前には `tracking/events.js` の中身を `<script>` で囲んで置きます
（クリックや離脱を拾う本体。閲覧数だけでよければ省いても動きます）。

---

## ★ ご依頼の「?src=施設ID 別の閲覧数」について、今日ちょうど対応しました

**`?src=` を GA4 の次元（`traffic_src`）として送るようにしたのは、この依頼を受けてです。**

それまでは `?src=` を**フォームの hidden 欄にしか入れていませんでした。**
つまり**送信した人の分しか残らず、閲覧数は取れない**状態でした。
ご依頼の「閲覧数を施設別に」はそれでは満たせないので、**`gtag('config')` に載せました。**

これで **`page_view` にも `traffic_src` が付きます。**

ブラウザで確認済みです。

```
?src=qr-watanabe&cid=C1234 → config と phone_click の両方に traffic_src が乗る
パラメータ無し              → traffic_src="direct"
```

## ⚠️ ただし、GA4側で登録しないとレポートに出ません

**これが最後の関門です。** GA4は独自のパラメータを、登録しないとレポートに出しません。

`docs/ga4-管理画面の手順.md` の**第2章**に手順があります。
7番目の **`流入元` ／ `traffic_src`** がそれです。

**登録から反映まで24〜48時間かかります。** 操作はCMO／オーナー（ログインが要るため）。
**公開より前に登録を済ませておくと、公開初日から数字が取れます。**

## 施設別の閲覧数の見かた（登録から2日後）

**[レポート]** → **[エンゲージメント]** → **[ページとスクリーン]** を開き、
表の上の **[+]** で **[流入元]** を足す。

`page_view` の行が施設IDごとに分かれます。週次報告にはこの数字を使ってください。

**APIで取りたい場合**は、GA4 Data API で `customEvent:traffic_src` を次元に指定すれば
同じ数字が取れます。サービスアカウントにGA4の閲覧権限を付ける必要があるので、
**必要になったら言ってください。手順を出します。**

## 施設IDの付け方のお願い（1つだけ）

`?src=` の値は **GA4のレポートにそのまま並びます。**

- **半角英数字とハイフン**にしてください（日本語や空白は避ける）
- **施設ごとに固定**にしてください。途中で変えると別物として集計されます
- 例：`fac-akachan-001` `fac-pet-shibuya`

**読本と無料点検で同じ施設を追うなら、`?src=` は同じ値**にして、
ページの違いは `lp_id`（`media-dokuhon` / `media-tenken`）で分けるのがきれいです。

---

完了（計測担当（GA4・広告タグ・電話CV） / 2026-09-11 22:04）
