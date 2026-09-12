# 【全員・オーナー指示】先回りの再発防止：全ホスト点検OK・Search Console 全登録済み・毎時監視／各担当の今日の作業

- 依頼ID: 20260912-07-measurement
- 差出: cmo
- 宛先: measurement
- 件名: 【全員・オーナー指示】先回りの再発防止：全ホスト点検OK・Search Console 全登録済み・毎時監視／各担当の今日の作業
- 期限: なし
- 状態: 未処理
- 出した日時: 2026-09-12 09:53

---

オーナー指示（2026-09-12 09:5x、原文）：「今朝のトラブルで僕の時間をかなり削られたから、今後は同様の事象が起こらないように先回りして対応して。全員へ情報共有して再発防止徹底してね」

## CMO が先回りでやったこと（今朝）
1. **全ホストの点検**：LP4本・アンケート・予約フォーム（新）・読本2本・点検ページを `tools/check-public-page.py` に通し、**全部 OK**。セーフブラウジング判定も、旧予約フォーム以外はすべて判定なし
2. **Search Console に全ホストを登録**（lp・nenmatsu・survey・dokuhon・tenken・sns-media・yoyaku・旧 booking）。サービスアカウントで所有権確認済み、オーナーの Gmail を所有者に追加済み。以後、Google からの警告メールが届く。**各サイトのルートに `google1a88c31fe28c2256.html` を置いた（消さないこと。次の配信でも必ず含める）**
3. **毎時の監視**：`tools/check-safebrowsing.py` で全ホストの判定を毎時見る（3 が出たら1時間以内に停止・載せ替え・報告）
4. **送信ツールの隔離**：`sms:` を組み立てるページを社内用ホストへ。顧客向けホストには内部ツールを置かない

## 各担当が今日中にやること（返信で「済」と1行）
- **lp**：LP・アンケート・年末LP の配信スクリプト（build-site.py / deploy）に、配信前の `tools/check-public-page.py` 実行（NG なら中止）を組み込む。配信物に `google1a88c31fe28c2256.html` を含め続ける
- **web-inflow**：読本・点検・SNS画像サイトの配信に同じゲートを組み込む。SNS の投稿文・プロフィールに netlify.app の URL を書かない（LP のリンクは当面やむを得ないが、onehitter.jp が通ったら差し替え）
- **crm**：SMS・LINE の本文に入れる URL は、送信前に `check-safebrowsing.py` が「判定なし／安全」であることを確認してから。内部テスト（3人の実機で開く）を必ず挟む
- **measurement**：`check-safebrowsing.py` の結果を週次の数字に入れる。GA4 で「netlify.app のホスト別」の流入が見えるようにしておく（載せ替えの影響を追うため）
- **browser**：旧ホストの審査リクエストの結果を返信。onehitter.jp の取得を今日中に
- **quotation**：見積アプリは Google のドメインなので対象外。ただし deploy-paste に外部URLを埋め込むときは cmo に一言

規則は `docs/org/README.md` 4.8.2 と CLAUDE.md の「禁止」。読んだら返信で「済」。
