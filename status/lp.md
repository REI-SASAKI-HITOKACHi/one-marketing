# LP・サイト担当 の現況

更新: 2026-09-19 13:19

2026-09-19 04:xx【アンケートの保存を復旧して配信・301一本化も完了】commit a247ff1。

🔴 最大の発見：アンケートの回答は、これまで1件も保存されていなかった。
フォームに action が無く、post() が何も送らないまま完了画面を出していた。
お客様には「ありがとうございました」が出て、回答は捨てられていた。
GA4の survey_complete だけが残っていたので、件数は分かるが中身が無い。
原因は二重：(1) LPのフォーム差し替えは class="form" を見ており survey-form に当たらない
(2) アンケートは copy_kanseihin を通るのでその置換自体を通らない。
docs/survey-redesign.md に仕様はあったが実装が無かった。
CMOの「先にテスト送信して台帳に入るまで見る」という指示が無ければ気づけなかった。

【直して配信した（オーナー確認を2回取得）】
- copy_kanseihin に target を渡し Netlify Forms を差し込む。開始タグが無ければ
  ビルドを止める（黙って保存されない状態に戻らないように）
- 本番でテスト送信し保存を確認。自由記述・顧客ID（?id=）・src も通ることを手元で確認
- フォーム通知：info@one-hitter.her.jp と k-watanabe@one-hitter.her.jp（オーナー指定）
- one-hitter-survey を301専用に。netlify.app も survey.onehitter.jp も
  lp.onehitter.jp/survey/ へ。クエリ引き継ぎ確認済み。QRの刷り直し不要
- Search Console の所有権ファイルが survey.onehitter.jp で404だったのも直った
- canonical を lp.onehitter.jp/survey/ に入れ替え
- 固定URL5本すべて200

【オーナーへの依頼】本番にテスト行が2件（通常1・迷惑扱い1）。削除をお願いする。
迷惑扱いはヘッドレスで送った私の試験方法のせい。iPhone条件では通常の箱に入る。

【残り】公式サイトの G-DZF7NP8CTG は129ページ中0件で外す対象なし。計測担当の確認待ち。
【次】10月のギフトブロック（docs/gift/ はまだ私のブランチに来ていない）
