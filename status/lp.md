# LP・サイト担当 の現況

更新: 2026-10-01 14:20

【10/1 15時 lp 現況】
済
- 予約カレンダー直行ボタン（20261001-03-lp）：学習版3本（mizumawari-b / aircon-c / nenmatsu-b）に実装（8a1875f）。料金の下を2択に＋フォーム直前にカレンダー・電話・LINE。src/cid/ag/gclid を予約ページへ引き継ぎ。cta_click に link_position（estimate/form/deadline）と link_target=yoyaku。CMOへ「配信してよい」と返信済み
- nenmatsu-b の ?ag= 修正（4e46031）、担当者イラストの枠（98dc242）
待ち
- CMOの配信 → 配信後に本番を確認する
- GA4 のカスタムディメンション link_position の登録（measurement/オーナー）
- aircon-d にもボタンを入れるか（CMO判断）
- イラストの作り方（Canva無料枠 / ココナラ外注）→ オーナー判断、和真さんの写真
- 既存4本の v2 切替は 10/9 判定後
ブランチ：claude/lp-outline-presentation-8fahl3（8a1875f）
