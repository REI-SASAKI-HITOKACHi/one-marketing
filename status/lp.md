# LP・サイト担当 の現況

更新: 2026-09-15 02:06

2026-09-15 未明。広告まわりは「反映すれば終わる」状態。配信は承認待ちで止めている。

**手元で完了（すべて実行まで検証済み・未配信）**
- Google広告のコンバージョン：AW-18450975194／generate_lead／phone_click。
  ブラウザで実際に発火し send_to にラベルが載ることまで確認。
  phone_conversion_label は二重計上を避けるため空のまま。
- gclid / wbraid / gbraid の保存（localStorage 90日→隠し欄）。LP4本＋予約フォーム。22項目通過。
- 広告の着地ページ：?src=gads の初見向け文言、電話を1画面目（追従バーの裏に隠れる問題を実測で修正）。
- アンケート：GA4と最新版、netlify.app→survey.onehitter.jp の301、canonical。

**配信待ち（許可が出たら2サイトへ1回で）**
one-hitter-lp ／ one-hitter-survey

**判断待ち**
- アンケートの一本化の形（凍結URLは301にできないので canonical で寄せた）
- 写真：6520/6521はFV不可（清潔感の方針に反する）・6598→6616は画角違いで組にならない
- 読本・点検のダークモード：ソースがこちらに無い。持ち主スレッドを教えてほしい

**引き継ぎ**
- docs/広告-コンバージョン計測.md はどのブランチにも無い。
  measure-production.py の判定条件を仕様として実装した。
- copy_kanseihin が index.html しか複製していなかった（_redirects が配信物に入らない）。修正済み。
