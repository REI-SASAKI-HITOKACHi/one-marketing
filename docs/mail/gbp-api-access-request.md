# Google Business Profile API アクセス申請（下書き）

作成：2026-09-14 ブラウザ担当／指示：cmo
**送信はしない。オーナーがログインした回に、貼って送信ボタンを押してもらう。**

> この文書は、ブラウザ担当（オーナーのPC上で動くスレッド）が作成したものを、
> CMO が代理でコミットした。ブラウザ担当は GitHub への push が 403 で通らないため
> （`docs/cmo-savedata.md` の「ブラウザ担当との連絡経路」を参照）。

## 前提（2026-09-14 時点で確認済み）

- プロジェクト `one-hitter-sheets` で **My Business Business Information API** と **My Business Account Management API** は**有効化済み**。
- ただし **Requests per minute の割り当てが 0**。API の説明文にあるとおり、この状態では1回も呼び出せず、アクセス申請の承認が要る。（承認されると 300 QPM になる。承認の確認は同じ割り当て画面で行う）
- 受付メール・審査結果メールは onehitter.her / case.foot.kid のどちらの Gmail にも無く、**過去に申請された形跡は無い**。

## 申請の入口

1. https://developers.google.com/my-business/content/prereqs#request-access
2. そこからリンクされている **GBP API お問い合わせフォーム** https://support.google.com/business/contact/api_default
3. 「どのようなことでお困りですか？」で **「基本の API アクセスの申請」** を選ぶ（他の選択肢は「API に関する一般的な質問」「割り当ての引き上げリクエスト」）
4. 選ぶと申請フォームが展開される。**フォーム本体は埋め込みで、項目名は画面で確認すること**（2026-09-14 に内蔵ブラウザから開いたが、埋め込み部分が描画されず項目名を取れなかった）

**重要：ビジネス プロフィールのオーナーまたは管理者になっている Google アカウントでログインした状態で開くこと。** onehitter.her@gmail.com（メインのオーナー）か case.foot.kid@gmail.com（2026-09-13 にオーナー承諾済み）のどちらでもよい。

## Google が示している申請の条件

- 認証済みで **60日以上** 稼働しているビジネス プロフィールを管理していること → ワンヒッター㈱ は2022年から運用しており、条件を満たす
- プロフィールに、そのビジネスを表すウェブサイトが登録されていること → https://one-hitter.jp/ を登録済み

## 入力する内容

| 項目 | 入力する値 |
|---|---|
| 会社名 | ワンヒッター株式会社（ONE HITTER Inc.） |
| 所在地 | 〒134-0081 東京都江戸川区北葛西5-14-11 クオーディア西葛西503 |
| ウェブサイト | https://one-hitter.jp/ |
| 連絡先メールアドレス | info@one-hitter.her.jp |
| 申請者（ログインするアカウント） | GBP のオーナー権限を持つ Google アカウント |
| Google Cloud プロジェクト ID | one-hitter-sheets |
| Google Cloud プロジェクト番号 | 844550773178 |
| 管理するロケーション数 | **1**（自社1拠点のみ） |
| ビジネス プロフィール名 | ワンヒッター㈱ |
| 使用する API | My Business Business Information API／My Business Account Management API |
| 第三者への提供 | **なし**（自社利用のみ。代理店・SaaS としての提供はしない） |

## 用途の説明（そのまま貼る）

当社は東京都江戸川区に拠点を置くハウスクリーニング事業者です。
自社が管理する1つのビジネス プロフィール（ワンヒッター株式会社）についてのみ、次の運用を自動化するために API の利用を申請します。

1. 最新情報（投稿）の作成と公開
2. 施工後の写真の追加
3. お客様からのクチコミへの返信
4. 表示回数・通話・ルート検索などの掲載結果の取得

現在はすべて管理画面から手作業で行っており、投稿や返信が滞りがちです。社内の業務システムから直接更新できるようにすることで、更新の頻度と速さを改善したいと考えています。

対象は**自社が所有する1ロケーションのみ**です。**他社のビジネス プロフィールを代理で操作することはありません。** 取得したデータを第三者に提供したり、SaaS や代理店サービスとして再提供したりすることもありません。

## 英語版（フォームが英語で表示された場合）

We are a house cleaning company based in Edogawa-ku, Tokyo, Japan. We are requesting API access for **a single Business Profile that we own and operate** (ONE HITTER Inc.).

We plan to use the API to:
1. Create and publish local posts (updates)
2. Upload photos taken after each job
3. Reply to customer reviews
4. Retrieve performance metrics (views, calls, direction requests)

All of this is done manually through the web interface today, which makes our updates infrequent and slow. We want to update the profile directly from our internal system.

This is for **one location that we own**. We will **not** manage Business Profiles on behalf of any third party, and we will not resell or redistribute the data as an agency or SaaS offering.

## 送信したあと

- 受付メールが info@one-hitter.her.jp（または申請したアカウント）に届くはず。**申請日と受付メールの有無を控えて cmo に報告する。**
- 承認の確認は、Cloud コンソールの `APIとサービス → My Business Business Information API → 割り当てとシステム上限` で **Requests per minute が 0 から 300 に変わっているか**を見る。
- 承認されるまでは、GBP の投稿・写真・クチコミ返信は管理画面からの手作業を続ける。

## やらないこと

- **このフォームをブラウザ担当が送信しない。** 社外への送信のため、リアライズ・レントラックス宛のメールと同じ扱いにする（cmo 決定 2026-09-14）。
- 資格情報（クライアントID・シークレット・トークン・パスワード）はこの文書に書かない。
