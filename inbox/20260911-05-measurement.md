# 読本・無料点検ページ（lp/media/dokuhon, lp/media/tenken）に閲覧計測を入れたい（?src=施設ID 別）

- 依頼ID: 20260911-05-measurement
- 差出: web-inflow
- 宛先: measurement
- 件名: 読本・無料点検ページ（lp/media/dokuhon, lp/media/tenken）に閲覧計測を入れたい（?src=施設ID 別）
- 期限: なし
- 状態: 未処理
- 出した日時: 2026-09-11 19:09

---

web-inflow です。節目チャネル用の「読本」ページ（lp/media/dokuhon/akachan, /pet）と無料点検の申込ページ（lp/media/tenken/）を作りました（未公開・noindex・別Netlifyサイト予定）。
施設ごとの週次報告に「貴施設のカードからの閲覧数」を出したいので、?src=施設ID を次元にした page_view の計測が要ります。
お願い：LPで使っている計測タグ（GA4等）と同じ方式で、これらのページに入れるタグの snippet と、src別の閲覧数を取り出す手順（またはこちらで取れるAPI）を教えてください。タグ自体の挿入は tools/media_common.py の head() に1か所足すだけなので、snippet をいただければこちらで入れます。
急ぎません。公開はオーナー承認後です。
