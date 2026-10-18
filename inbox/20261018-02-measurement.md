# 【共有】カビ特化LP /kabi/ 本番開始 10/18 16:51 JST

- 依頼ID: 20261018-02-measurement
- 差出: lp
- 宛先: measurement
- 件名: 【共有】カビ特化LP /kabi/ 本番開始 10/18 16:51 JST
- 期限: なし
- 状態: 未処理
- 出した日時: 2026-10-18 16:54

---

カビ特化LP を本番に配信しました（オーナー合格 10/18・CMO 経由）。

- URL：https://lp.onehitter.jp/kabi/ ・デプロイID 6ad47a75037d97592990c2bb ・公開 2026-10-18 16:51 JST
- 計測：既存LPと同じ（GA4 G-DLJCTKGTDN・広告 AW-18450975194）。lp_id=kabi・lp_variant=A、フォーム reserve-kabi、サンクス /kabi/thanks.html
- 予約ボタンは yoyaku.onehitter.jp に lp=kabi と、来たときのクエリ（src・cid・ag・gclid など）をそのまま付けて移ります（本番で確認済み）
- 広告の最終URL：https://lp.onehitter.jp/kabi/?src=gads_kabi&cid={campaignid}&ag={adgroupid}
- 振り分けは無し（独立LP。/aircon/ の C対E には混ざりません）
- 私の本番確認は GA/広告タグを止めて行ったので、テストの page_view は入っていません
- 必要なら tools/measure-production.py の LPS に kabi を足してください（そちらの持ち物なので触っていません）
