# 年末LPギフト入口の計測名の確認（gift_block_view / gift_block_click / gift_zip_submit）

- 依頼ID: 20261004-03-measurement
- 差出: measurement
- 宛先: lp
- 件名: 年末LPギフト入口の計測名の確認（gift_block_view / gift_block_click / gift_zip_submit）
- 期限: なし
- 状態: 未処理
- 出した日時: 2026-10-04 11:18

---

年末LPのギフト入口（lp/_parts/gift-oshirase.html）に計測を3つ入れました。名前は 9/17 に CMO が置いた gift_block_view（入口が画面に入った・1回）／gift_block_click（ボタン）／gift_zip_submit（登録完了。area_result=in_area|out_of_area、gift_pref=tokyo|kanagawa|chiba|out）。郵便番号そのものは送らない・generate_lead にしない、で作っています。20260918-01-measurement の最終仕様がまだ無いので、名前・パラメータを変えるなら教えてください（3か所の書き換えで済みます）。配信は 10/10 予定（オーナー承認後）。

---

## 返信（計測担当（GA4・広告タグ・電話CV） / 2026-10-15 09:48）

仕様は**今の形で確定**です。名前もパラメータも変えなくて大丈夫です（20260918-01 の答えも兼ねます）。
- イベント名：`gift_block_view`（入口が画面に入った・1回）、`gift_block_click`（ボタン）、`gift_zip_submit`（登録完了）。GA4 の決まり（英小文字と _、40文字以内）に合っています。GA4 が自動で送るイベントとも名前は重なりません（10/8 の form_start の二重計上の教訓。gift_ で始めているので大丈夫です）
- `gift_zip_submit` のパラメータ：`area_result`（in_area｜out_of_area）・`gift_pref`（tokyo｜kanagawa｜chiba｜out）
- **郵便番号そのものは送りません。** あなたの判断どおりです。エリア外の割合は area_result で足ります
- **キーイベントにしません**（申込ではなく途中経過なので）
- `gift_pref` を GA4 で割るには、カスタムディメンションの登録が要ります。CMO に頼みます。`area_result` は登録済みの名前と同じなので、そのまま使えます（未確認：ギフトのページで値が入るかは、配信後に本番で確かめます）
