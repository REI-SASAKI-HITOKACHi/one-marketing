# one-marketing

ワンヒッター株式会社（ONE HITTER）のマーケティング資産を管理するリポジトリ。

## オーナーの希望（進め方）

- **質問がまとまって出るときは、テキストで並べずカード形式（AskUserQuestion）で聞くこと。**
  1〜2件の自由記述だけなら通常の文章で構わない。
- 作業は並行して進めてよい。必要に応じて子エージェントを使う。

## 構成

| パス | 内容 |
|---|---|
| `lp/aircon/` | LP案A：エアコンクリーニング単品訴求 |
| `lp/mizumawari/` | LP案B：水まわりセット訴求 |
| `docs/lp-proposal.md` | LP構成案と、決定済み/未決定の論点一覧 |
| `docs/price-master.md` | 料金マスター（パンフレットPDFが正） |
| `docs/site-audit.md` | 公式サイトとパンフレットの差分監査 |
| `docs/tracking-setup.md` | ユニークコール（電話CV計測）の導入手順 |
| `docs/measurement-audit.md` | 計測の棚卸し。いま何が測れていて何が測れていないか |
| `docs/measurement-spec.md` | **計測設計書。イベントとコンバージョンの定義はこれが正** |
| `docs/measurement-owner-steps.md` | オーナーの作業手順（GA4・広告・電話計測） |
| `docs/calltracking-vendors.md` | コールトラッキング事業者の比較（出典URL付き） |
| `tracking/` | 計測の設定と埋め込みスクリプト。`measurement.json` にIDを入れて再ビルドする |
| `docs/sns-operation-memo.md` | SNS運用（着手前のメモ） |

## 前提

- **料金はパンフレットPDFが正。** 公式サイトの料金表には誤りがあり、修正が必要（`docs/site-audit.md`）。
- 対応エリアは東京都・千葉県・神奈川県。
- アンケート実績は **98.6%**（209名中206名／2023年1月〜2025年12月）。
  パンフレットとサイトの「98.8%」は根拠と一致しないため使わない。
- 成果地点は作業完了ベース／成果単価3,000円。事業者の選定とやり取りはオーナーが担当する。

## 禁止

- CMSの認証情報など、資格情報を一切コミットしないこと。
  （`tracking/measurement.json` に入れてよいのは、公開ページのHTMLに出る測定IDだけ。
  APIキー・トークンの類は入れない）
- 計測を確かめずに配信しないこと。**配信の前に必ず `python3 tools/check-tracking.py` を通す。**
