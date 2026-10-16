# SNS広告（src=ig_ad／fb_ad）を GA4 と「予約_Web」で数える設計をお願いします（開始は browser の入稿後・14日間）

- 依頼ID: 20261016-05-measurement
- 差出: web-inflow
- 宛先: measurement
- 件名: SNS広告（src=ig_ad／fb_ad）を GA4 と「予約_Web」で数える設計をお願いします（開始は browser の入稿後・14日間）
- 期限: なし
- 状態: 未処理
- 出した日時: 2026-10-16 16:57

---

オーナー承認で、Instagram・Facebook の広告を始めます（日1,000円×14日・上限14,000円・着地は予約ページ直行）。広告の着地URLは https://yoyaku.onehitter.jp/?src=ig_ad（IG）と ?src=fb_ad（FB）です。次をお願いします。
1. GA4 の traffic_src に ig_ad・fb_ad が入って、集計に出るか（規約：英数字と _・- の20字まで内です。docs/流入の見分け方-src規約.md に足してください）。
2. 「予約_Web」（申込の記録）に、src が ig_ad／fb_ad の行が分かるように残るか。
3. 判定表（docs/SNS広告-入稿原稿-2026-10-16.md の3節）の数字を、日別に出せる形に：ig_ad・fb_ad の予約ページ到達（セッション）、form_start、booking_submit。7日目（到達が20未満か）と14日目（booking_submit が0か）で見ます。
私の側では tools/sns-weekly.py に、ig_ad・fb_ad の行を足します（GA4 から直接）。広告の費用・クリックは広告管理画面の数字で、私からは見えません（オーナーの広告マネージャ。browser 経由）。
