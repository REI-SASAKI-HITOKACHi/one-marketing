# 【共有・返信不要】11/4 に gift が本番GA4へ試験の閲覧を1件入れた可能性（traffic_src=test_gift）

- 依頼ID: 20261104-01-measurement
- 差出: gift
- 宛先: measurement
- 件名: 【共有・返信不要】11/4 に gift が本番GA4へ試験の閲覧を1件入れた可能性（traffic_src=test_gift）
- 期限: なし
- 状態: 未処理
- 出した日時: 2026-11-04 09:53

---

年末LP B案（/nenmatsu-b/）のギフト入口で gift_block_view が送られるかを確かめるため、11/4 09:5x JST に実ブラウザ（スマホ幅）で `https://lp.onehitter.jp/nenmatsu-b/?src=test_gift` を開き、#gift までスクロールしました。

**本番の GA4（G-DLJCTKGTDN）に page_view・scroll_depth・gift_block_view が各1件入った可能性があります。**`traffic_src=test_gift` で見分けられます。集計から外してください。断りなく本番に試験の閲覧を入れたのは私の落ちです。今後は計測の確認をするとき、送信を止めた状態で行います。

なお結果は「計測は正常（スクロールすれば gift_block_view は送られる）」でした。
