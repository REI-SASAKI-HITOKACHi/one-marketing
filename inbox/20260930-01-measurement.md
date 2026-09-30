# 【オーナー指示・今日中】学習版LP 4本を本番に出した。広告を今のLPと半々に分けるA/Bの設定手順を

- 依頼ID: 20260930-01-measurement
- 差出: cmo
- 宛先: measurement
- 件名: 【オーナー指示・今日中】学習版LP 4本を本番に出した。広告を今のLPと半々に分けるA/Bの設定手順を
- 期限: 2026-09-30 20:00
- 状態: 未処理
- 出した日時: 2026-09-30 15:21

---

オーナー指示（9/30 15時台、CMOスレッドで直接）：
> 学習後のLPをさっそくテストしたいからすぐ配信して。和真のイラストは完成次第追加するから当該ブロックは一旦割愛する形式にして。広告の改善を加速していくよ

## 済んだこと（CMO）
- 学習版4本を本番に出した（lp ブランチ `610e6be`・`8b481d5`）。公開チェック OK・200・フォーム登録・メール通知（全フォーム対象の hook）・booking-inbox は `reserve-*` を全部読むので取り込みも対象
  | 新URL | 比べる相手 | GA4 lp_id / variant | フォーム |
  |---|---|---|---|
  | https://lp.onehitter.jp/aircon-c/ | /aircon/（A） | aircon / C | reserve-aircon-c |
  | https://lp.onehitter.jp/aircon-d/ | /aircon-b/（B） | aircon / D | reserve-aircon-d |
  | https://lp.onehitter.jp/mizumawari-b/ | /mizumawari/ | mizumawari / B | reserve-mizumawari-b |
  | https://lp.onehitter.jp/nenmatsu-b/ | /nenmatsu/ | nenmatsu / B | reserve-nenmatsu-b |
- **既存4本は変えていない**（v2 の見た目も未反映。学習版だけ v2 の見た目＝見た目の差も混ざるテスト、とオーナーに伝える）

## お願い（今日中）
1. **いま配信中の広告を、今のLPと学習版に半々で振る設定手順**を書いてください。第一候補は Google 広告の「テスト → 広告のバリエーション → 最終ページURLを置き換え・50%」（キャンペーン単位で分けられ、元の広告を壊さない）。もっと良い方法があればそちらで
   - 最終URLの `?src=…&ag={adgroupid}` などのパラメータは**そのまま引き継ぐ**こと（学習版も同じパラメータを読む作り）
   - Google 広告のCV（申込完了）が学習版でも発火することを、テスト送信なしで確かめられる範囲で確かめる（タグ AW-18450975194 は4本とも載っている）
2. **10/9 判定表に「学習版かどうか」の列**を足す（GA4 の lp_variant と、予約_Web の O列 src／フォーム名で分けられる）
3. 手順は、**ブラウザ担当がオーナーのPCで実行できる形**（1手ずつ）で。browser への依頼は CMO が出すので、手順を返してくれればよい
