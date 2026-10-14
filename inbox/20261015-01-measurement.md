# 【共有】C対E 振り分けを配信：判定表の起点は 10/15 08:2x JST

- 依頼ID: 20261015-01-measurement
- 差出: lp
- 宛先: measurement
- 件名: 【共有】C対E 振り分けを配信：判定表の起点は 10/15 08:2x JST
- 期限: なし
- 状態: 未処理
- 出した日時: 2026-10-15 08:28

---

/aircon/ の C 対 E 50/50 振り分けを配信しました。**判定表の起点：2026-10-15 08:2x JST**（オーナーOK 10/14、CMO 依頼 20261015-01-lp）。

- /aircon/ に来た人は初回だけ 50/50 で /aircon-c/ か /aircon-e/ へ（同じ人には同じ版、残せない人は C）。クエリはそのまま引き継ぐ
- /aircon/ では GA4・広告の config を送らない＝ /aircon/ の page_view は増えません。数えるのは今までどおり /aircon-c/・/aircon-e/（lp_variant C／E）
- 参照元の注意：/aircon/ 経由の人は移り先で参照元が自サイトになる。広告は gclid が付いて移るので google / cpc のまま。gclid の無い入口（アフィリエイト・自然検索）は (direct) に寄ります
- tools/measure-production.py の見るページを /aircon/ → /aircon-c/・/aircon-e/ に変えました（lp ブランチ）
- 仕様：docs/LP-エアコンC対E-振り分け.md（lp ブランチ）
