# ブラウザ担当スレッドの立ち上げと、最初の仕事

作成 2026-09-11（CMO）。オーナー指示：「ローカルでブラウザを使用できるスレッドを一つ立ち上げて、Claudeのブラウザ上で僕がログイン等だけをする方法で進めていく」。

## 1. 立ち上げ（オーナー。3分）

クラウドのスレッドはブラウザで外部に出られないので、**オーナーのPCで**立ち上げる（CMOからは作れない。過去の「ブラウザ実務スレッド：ロリポップIPテスト」と同じ形）。

1. PCで Claude Code（デスクトップアプリ、またはターミナル）を開き、このリポジトリ（one-marketing）で新しいセッションを始める。ブラウザ操作の拡張（Claude in Chrome）を有効にしておく
2. セッション名を **`ブラウザ担当｜管理画面の設定（SNS・GBP・LINE・ロリポップ）`** にする
3. 最初のメッセージに、下の枠の中をそのまま貼る

```
あなたはワンヒッター株式会社の「ブラウザ担当」（役割ID: browser）です。
まず docs/org/roles/browser.md と docs/org/browser-スレッド-立ち上げと最初の仕事.md を読み、
python3 tools/org.py 読む browser を実行してください。
進め方：オーナー（僕）はログイン・2段階認証だけをします。それ以外のクリックと入力は全部あなたがブラウザでやってください。
1手順ずつ、あなたのブラウザ画面を見せながら、僕にしてほしいことを1行で言ってください。
トークン・ID・パスワードは Google ドキュメント「ワンヒッター_認証情報（ここだけ）」にあなたが貼り、チャットには出さないでください。
終わったら掲示板（tools/org.py）で cmo に返信してください。最初の仕事は上の md の「2. 最初の仕事」の順です。
```

4. 立ち上がったら、そのセッションIDを CMO に一言（掲示板か LINE）。CMO が `docs/org/roles/browser.md` に追記する

## 2. 最初の仕事（優先順）

各仕事は「目的」「完了の条件」「結果の置き場」だけ書く。**画面の細かい手順は書かない**（ブラウザ担当が画面を見て進める。画面表記はサービス側で頻繁に変わる）。旧 `docs/権限移譲の手順.md`（web-inflow 作成）は背景の参考にしてよいが、**「項目ごとに Drive ファイル」の渡し方は使わない。認証情報ドキュメント1本に集約する。**

### 仕事1：Instagram と Facebookページを、APIで投稿できる状態にする（SNS運用の前提。最優先）

- 対象アカウント：Instagram `@onehitter.jp`／Facebookページ「One Hitter」（`facebook.com/people/One-Hitter/100084190801350/`）
- 目的：ネット流入施策担当（クラウド）が Instagram Graph API でフィード投稿・インサイト取得、Facebookページに投稿できること
- やること（順に）
  1. Instagram を**ビジネスアカウント**にする（クリエイターではない）。カテゴリはハウスクリーニング系。Accounts Center（accountscenter.instagram.com）はPCブラウザからも操作できる
  2. Instagram と Facebookページ「One Hitter」をリンクする
  3. Meta Business（business.facebook.com）に**ビジネスポートフォリオ**を作る（既にあればそれ）。Facebookページと Instagram アカウントをそのポートフォリオに入れる
  4. Meta for Developers でアプリを1つ作る（種類はビジネス。名前は `onehitter-sns` など。連絡先はオーナーのメール）。アプリをポートフォリオに紐づける
  5. ポートフォリオの「システムユーザー」を1人（管理者）作り、ページ・Instagram・アプリの資産を割り当て、**有効期限なし**のトークンを生成する。権限：`instagram_basic` `instagram_content_publish` `instagram_manage_insights` `pages_manage_posts` `pages_read_engagement` `pages_show_list` `business_management`
     - システムユーザーが作れない／出てこないときの代替：グラフAPIエクスプローラで長期トークン（60日）を作る。その場合は「60日で切れる」と返信に明記する
  6. 認証情報ドキュメントに見出し **`Meta（Instagram / Facebookページ）`** を作り、次を貼る：システムユーザートークン（または長期トークン＋有効期限）、アプリID、FacebookページID、InstagramビジネスアカウントID
- 完了の条件：CMO か web-inflow が、そのトークンで `GET /me/accounts` と `GET /{ig-user-id}?fields=username,followers_count` を curl で叩けて、`onehitter.jp` が返ること（ブラウザ担当は掲示板で cmo に「貼った」と返信。確認はクラウド側でやる）
- 任意：Facebookページにユーザーネーム（`onehitter.jp` など）を付けてURLを短くする

### 仕事2：Googleビジネスプロフィール（GBP）の管理者を取り戻す

- 症状：オーナーの Gmail（case.foot.kid@gmail.com）でも会社の Google アカウントでも、business.google.com のログイン後に「プロフィールを作成」の画面になる＝**どちらも管理者ではない**。以前 MEO をやっていたリアライズの Google アカウントが所有者の可能性が高い（別途リアライズにメールで移管を依頼済み）
- やること
  1. Google 検索で「ワンヒッター株式会社」を検索し、ナレッジパネルの「このビジネスのオーナーですか？」→ **アクセス権をリクエスト**の流れに入る。Google が現在の所有者のメールを一部伏せ字で表示するので、それを控える（伏せ字のままでよい。掲示板に書いてよい）
  2. リクエストを送る（所有者に通知が行く。3日で返答が無ければ Google 側の確認手順に進める）
  3. 管理者になれたら：「ユーザーとアクセス権」で `case.foot.kid@gmail.com` をオーナー、`claude-sheets@one-hitter-sheets.iam.gserviceaccount.com` を管理者に追加（サービスアカウントが弾かれたら、その旨だけ返信）
  4. ついでに直す：ビジネス説明（文案は web-inflow の `docs/gbp-audit.md`）、営業時間 8:00〜20:00、屋号「ワンヒッター株式会社」
- 完了の条件：オーナーの Gmail で business.google.com を開くと「ワンヒッター株式会社」のプロフィールが管理画面に出る

### 仕事3：LINE公式アカウントの2人のユーザーIDを控える（顧客接点担当が待っている）

- 目的：クーポンのテスト送信先（嶺さん・和真さん）のLINEユーザーIDが要る
- やること：LINE Official Account Manager（manager.line.biz）→ チャット → 嶺さん／和真さんのトークを開く → アドレスバーのURL末尾のID（`U` で始まる33文字）を、認証情報ドキュメントの見出し **`LINE ユーザーID（内部テスト用）`** に「嶺」「和真」と分けて貼る。手順の詳細は crm ブランチの `docs/LINEユーザーIDの取り方-オーナー用.md`
- 完了の条件：掲示板で `crm` に「貼りました」と返信

### 仕事4：ロリポップで info@one-hitter.her.jp を Gmail に転送する（計測担当が待っている）

- 目的：レントラックス・リアライズからのメールが info@ に届くが、クラウドのスレッドは Gmail（case.foot.kid@gmail.com）しか読めない
- やること：ロリポップのメール設定で info@ の転送先に `case.foot.kid@gmail.com` を追加。**「サーバーに残す」を必ずON**（info@ の受信箱を空にしない）
- 完了の条件：テストメールを info@ に送って Gmail に届く。掲示板で `measurement` に返信
- 手順の詳細は measurement ブランチの `docs/info@メールを全スレッドで読めるようにする.md`

### 仕事5：見積アプリ（GAS）の貼り付けとデプロイ（見積アプリ担当が締めたら）

- 目的：割引が効いていなかった不具合の修正版を本番に出す
- やること：`apps/estimate-app/deploy-paste/` の4ファイルを Apps Script エディタに貼り、「新バージョン」でデプロイ。詳細は quotation ブランチの `apps/estimate-app/docs/README.md`
- **着手は CMO が「締まった」と掲示板で言ってから**
- 完了の条件：掲示板で `quotation` に返信（デプロイURLは変わらないはず。変わったら書く）

## 3. ブラウザ担当が守ること（再掲）

- オーナーにしてもらうのはログイン・2段階認証・本人確認・支払い確認だけ
- 認証情報は認証情報ドキュメントにだけ。チャット・掲示板・md・コミットに書かない
- 有料プラン・購入・広告に触れる画面では、その場でオーナーに一言確認
- 詰まったら cmo に「何が出て、何を試したか」を返す。オーナーに長文を読ませない
