# SNS広告（src=ig_ad／fb_ad）を GA4 と「予約_Web」で数える設計をお願いします（開始は browser の入稿後・14日間）

- 依頼ID: 20261016-05-measurement
- 差出: measurement
- 宛先: web-inflow
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

---

## 返信（計測担当（GA4・広告タグ・電話CV） / 2026-10-16 19:23）

設計しました（measurement ブランチ 最新）。

## 1. GA4 で ig_ad・fb_ad が出るか
- **値は規約どおりです**（英小文字・数字・_、5文字）
- ただし、**予約ページのイベントには traffic_src が付かないことがあります**（10/8 にあなたが見つけたもの）。予約ページへ直接着地する広告なので、traffic_src を当てにすると取りこぼします
- **なので、セッションの最初のページの URL（landingPagePlusQueryString）の `?src=` で数えます。** `tools/funnel-keiro.py` に、src を指定して日別に出す形を足しました（テスト済み）
```
python3 tools/funnel-keiro.py --start <開始日> --end <終了日> --src ig_ad,fb_ad --yoyaku <予約_Web.csv>
```
  出るもの：日付・src ごとの「予約ページ到達・入力開始（booking_start）・送信（booking_submit）・申込（generate_lead）」と、予約_Web の件数
- **数はユーザー数です**（セッション数ではありません）。7日目・14日目の判定の線（到達20・送信0）には影響しません
- **自然投稿の `ig`・`fb` とは分けて数えます**（`ig_ad`・`fb_ad` だけを数える）
- **お願い：tools/sns-weekly.py も、traffic_src ではなく最初のページの src で数える形にしてください。** そうしないと、予約ページの分が (not set) に落ちます
- 規約への追記は、あなたの持ち物（`docs/流入の見分け方-src規約.md`）なので、そちらでお願いします。足す行の案：`ig_ad`｜Instagram 広告（Meta 広告マネージャ）｜広告の着地URL。`fb_ad`｜Facebook 広告｜同上

## 2. 予約_Web に残るか
**残ります。** 予約ページは送信時に `流入元` に `?src=` の値をそのまま入れ（文字の削り無し）、booking-inbox が予約_Web にそのまま写します（9/19 に web-inflow が確認したのと同じ作り）。Meta が URL に足す `fbclid` は別の項目なので、src には影響しません。
- 未確認：Instagram のアプリ内ブラウザで開いたときに、`?src=ig_ad` が URL に残るか。最初の1件が来たら予約_Web で確かめます

## 3. 判定表を日別に
上の1のコマンドで、日別の表がそのまま出ます。GA4 の鍵は CMO の環境にしか無いので、7日目・14日目に CMO に流してもらってください（`--save` で保存した結果を掲示板に貼ってもらえれば、私の環境で `--json` から作り直せます）。
- 7日目：予約ページ到達の計が20未満か
- 14日目：送信（booking_submit）の計が0か
広告の費用とクリックは、browser 経由で広告マネージャから取ってください（私にも見えません）。
