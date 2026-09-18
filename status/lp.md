# LP・サイト担当 の現況

更新: 2026-09-18 21:54

2026-09-18 13:xx【配信しました】オーナー本人の確認を直接取って実行。commit a41cd82。

ホスト one-hitter-lp ／ https://lp.onehitter.jp ／ 77ファイル中10ファイル更新
- /aircon/ /mizumawari/：?src=gads_* を受ける版（広告有効化の条件）
- LP4本：支払方法・「ご予約の時点では費用は発生しません」・フッターに特商法リンク
- /tokushoho/：新規公開
- 予約フォームは触っていない（CMOの回）

【配信前に見つけて直した重大な欠け】
lp/tokushoho/ はビルドを一度も通っておらず、deploy/ に存在していなかった。
そのまま配信したら「出した」と報告しつつ本番に1ページも増えていなかった。
copy_kanseihin の対象に tokushoho を追加して解決。

【本番で実測して確認したこと】
- ?src=gads_aircon / gads_mizumawari / gads_brand / gads の4通りで
  文言差し替えと1画面目の電話（top 312px）が出る。direct は通常のまま
- コンバージョン3ラベルとも本番のHTMLに存在
- 特商法ページ 200・24,693バイト。社名4・所在地1・電話2・支払方法4項目
- LP4本すべてのフッターから /tokushoho/ へのリンクが出ている（404の時間なし）
- 固定URL5本（one-hitter-lp.netlify.app）すべて200。1本も落ちていない
- 98.8% の混入は本番6本すべて0件

【次】アンケートのGA4（20260914-03-lp）。ただし既に直っており、残るのは
lp.onehitter.jp/survey/ → survey.onehitter.jp の301が出ていない点のみ。
計測にも検索にも実害なし。一本化を進めるかCMOの判断待ち。
