# /aircon/ の C 対 E 振り分け（2026-10-14・未配信）

依頼 `20261014-01-lp`。Google広告の実験が編集できないため、LP 側で振り分ける（CMO 判断 10/12）。
判定表は measurement の `docs/AB-エアコンC対E-判定表.md`（GA4 のページ /aircon-c/・/aircon-e/、lp_variant C／E）。

## 動き

| 来た人 | 出るもの |
|---|---|
| 初めての人（JS あり） | 50/50 で /aircon-c/ か /aircon-e/ へ移る（location.replace）。版を localStorage と Cookie（90日）に残す |
| 2回目以降 | 残っている版へ（同じ人には同じ版） |
| 版を残せない人（プライベートブラウズ等） | 毎回 /aircon-c/ |
| JS が動かない人 | 移らない。/aircon/ に C の中身がそのまま出る（フォームは C の受け口） |

- クエリ（src・cid・ag・gclid・utm など）と `#` は**一文字も変えずに**引き継ぐ
- /aircon/ の canonical・og:url・robots は今と同じ（`https://lp.onehitter.jp/aircon/`・`noindex,follow`）
- /aircon/ では GA4・広告の config を送らない＝ /aircon/ の page_view は増えない。移り先が C／E として数える
- 確認用：URL の最後に `#ab-c`／`#ab-e` を付けるとその版に固定（以後もその版）

## 作り方・配信

```
python3 tools/furiwake-aircon.py                                          # 確認用 → preview/furiwake/aircon/
python3 tools/furiwake-aircon.py --out deploy/netlify/aircon/index.html    # 配信物に入れる（オーナーのOKのあと）
python3 tools/check-public-page.py deploy/netlify/aircon/index.html
```

- 中身は **aircon-c の配信物の写し**。aircon-c を直したら必ず作り直す
- /aircon/thanks.html（今の版のサンクス）と /aircon/img/ はそのまま残す（URL を消さない）
- 戻すとき：`git show 43249cb1:deploy/netlify/aircon/index.html > deploy/netlify/aircon/index.html`（今の版 A）

## 読み方の注意

- /aircon/ は **アフィリエイトの遷移先にも登録済み**。振り分けを入れると、アフィリエイトから来た人も C／E に分かれる（URL は変わらない）
- /aircon/ 経由の人の参照元は、移り先では lp.onehitter.jp（自サイト）になる。広告は gclid が付いて移るので google / cpc のまま。gclid の無い入口（アフィリエイト・自然検索）は (direct) に寄る
- 今の版 A（/aircon/ の旧ページ）は見えなくなる。A の数字はこの日で切れる
