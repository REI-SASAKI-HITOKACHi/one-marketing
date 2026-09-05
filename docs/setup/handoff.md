# 引き継ぎ（2026-09-05）

このドキュメントは、**画面つきの環境に移って作業を続けるため**のものです。
今日の作業はすべて GitHub に入っています。

---

## 1. まずやること

### リポジトリを開く

```
REI-SASAKI-HITOKACHi/one-marketing
ブランチ： claude/one-hitter-cmo-strategy-5qk4ux
```

**⚠️ 既定ブランチが `claude/lp-outline-presentation-8fahl3` になっています。**
そのまま開くと今日の成果物が入っていないブランチが出てきます。**必ず上のブランチに切り替えてください。**

GitHubの Settings → Branches で既定ブランチを `claude/one-hitter-cmo-strategy-5qk4ux` に
変えておくと、以後この事故が起きません（推奨）。

### 認証情報の場所

**すべてオーナーのGoogleドライブにあります。リポジトリには一切入れていません。**

| 名前 | Driveのファイル名 | 用途 |
|---|---|---|
| サービスアカウント鍵 | （オーナー保管のJSON） | Sheets / Drive / Places API |
| Netlifyトークン | `Netlify_トークン` | LP・アンケートの公開 |

環境変数に入れて使います。

```bash
export GOOGLE_SHEETS_SA_KEY="$(cat sa.json)"
export NETLIFY_TOKEN="nfp_..."
```

**サービスアカウントは一度チャットに貼られているので、いずれ作り直してください**（積み残し）。

---

## 2. 今日できたこと

| # | 内容 | 状態 |
|---|---|---|
| 1 | `.claude/settings.json` を配置 | 完了 |
| 2 | Drive API 有効化 | 完了 |
| 3 | サービスアカウントに Service Usage 管理者 | 完了・検証済み |
| 4 | Netlifyトークン発行 | 完了・疎通確認済み |
| 5 | KDDI Message Cast 申込 | 返信待ち |
| 6 | ネームギア | メール2通送付済み・返信待ち |
| 7 | LINE Messaging API | **オーナー承認待ち** |
| 8 | アンケートの公開判断 | **未** |

### 成果物

| ファイル | 内容 |
|---|---|
| `lp/survey/index.html` | 新アンケート（未公開）。次回予約割引・Google口コミ導線・紹介1,000円割引を実装 |
| `lp/survey/qr/phone-*.png` | 現場スマホ提示用のQR |
| `docs/survey-redesign.md` | アンケートの設計仕様 |
| `docs/google-reviews.md` | Googleクチコミ5件＋Place ID |
| `docs/photo-inventory.md` | 施工写真162枚の棚卸し |
| `assets/photos/` | 厳選28枚（LP・SNS用） |
| `docs/sms-provider-research.md` | SMS事業者の比較と決定理由 |
| `docs/sms-setup-steps.md` | SMS申込〜APIキー共有の手順 |
| `docs/line-api-setup.md` | LINE Messaging API の調査結果と手順 |
| `docs/namegear-dns.md` | DNSの調査結果と選択肢 |
| `docs/setup/60min-checklist.md` | オーナー作業の手順書 |

### スプレッドシート（2026年）

`1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64`

| タブ | 内容 |
|---|---|
| `目次` | 全43タブへのリンク（先頭） |
| `TODO` | T001〜T015 |
| `顧客管理台帳` | 957名。**TEL列の先頭0を復旧済み（800件）** |
| `電話番号_未登録` | 153名。渡辺さんがD列に入力するだけ |
| `冬季見込み客_2026` | 957名を優先度順に |

---

## 3. 画面つきの環境でやるべきこと（ここが本題）

**APIでは手が届かず、画面が必要な作業だけを並べます。**

### 最優先

1. **ネームギアのログイン復旧**
   - `one-hitter.jp` の**有効期限が 2026/09/30**（要注意）
   - 登録者はワンヒッター株式会社。WHOIS窓口は `as-domain@app-web.jp`（外部の代行業者）
   - リアライズとネームギアに問い合わせメールを送付済み。返信待ち
   - ログインできたら `lp` の A レコード（`118.27.125.166`）を1行追加する

2. **Googleクチコミの残り18件**
   - Places APIで5件は取得済み。**APIの上限が5件**のため残りは取れない
   - GBP管理画面 → 口コミ一覧 → Ctrl+P → PDF保存 → Driveの `Google口コミ_原本` へ

3. **LINE Messaging API の有効化**
   - 手順は `docs/line-api-setup.md`
   - **⚠️ 紐づけとプロバイダーは後から変更できません。** プロバイダー名は `ワンヒッター株式会社` で確定させること
   - 有効化の前に［応答設定］と［あいさつメッセージ］のスクショを控える

### そのあと

4. アンケートを触って公開の可否を判断（`lp/survey/index.html`）
5. 写真掲載の契約条項を確認（過去の施工写真をSNS・LPに使えるか）

---

## 4. 判断待ちの項目

| 項目 | 内容 |
|---|---|
| アンケートの公開 | 「外に出す」に該当。承認が要る |
| LINEの有効化 | 「元に戻せない」に該当。承認が要る |
| 過去写真の掲載範囲 | 密着カットは可。医療機関・店舗の内部は要許可 |
| 紹介の受付手順 | 1,000円割引の制度はあるが、誰の紹介かを記録する運用が未整備 |
| KDDIの単価 | **10円（税込）超なら NTT CPaaS に切り替え**。これが撤退ライン |

---

## 5. 引き継ぎ先で最初に投げる指示（例）

```
one-marketing の続きをやります。
ブランチは claude/one-hitter-cmo-strategy-5qk4ux。

まず docs/setup/handoff.md を読んで、状況を把握してください。
そのうえで、ブラウザが使える環境なので、
ネームギアのログイン復旧から一緒に進めたいです。
```
