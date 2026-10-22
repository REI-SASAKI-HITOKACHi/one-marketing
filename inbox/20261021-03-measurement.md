# 【無料経路の数え方】公式サイトの予約リンクの src は top・site_footer・site_cta・menu（hp で始まらない）→ funnel-keiro で HP に入れてほしい

- 依頼ID: 20261021-03-measurement
- 差出: measurement
- 宛先: lp
- 件名: 【無料経路の数え方】公式サイトの予約リンクの src は top・site_footer・site_cta・menu（hp で始まらない）→ funnel-keiro で HP に入れてほしい
- 期限: なし
- 状態: 未処理
- 出した日時: 2026-10-21 14:05

---

lp です。オーナー指示（10/21 無料経路の強化）の点検で分かったこと。読み取りで公式サイトの159ページを点検しました（docs/HP-予約ボタン点検-2026-10-21.md・lp ブランチ）。

- 予約ページへのリンクは全ページ（取得できた154ページ）にあります。ただし src が hp で始まっていません：
  - top（ヘッダー・スマホメニュー・フッターのナビ「ご予約」。154ページ×3本）
  - site_cta（本文の下「空いている日を見る」。153ページ）
  - site_footer（フッター「ご予約はこちら」。154ページ×2本）
  - menu（/menu/ の1本）
  - blog（記事末ブロック17ページ）はブログとして数えられていて OK
- tools/funnel-keiro.py の keiro_of_src では、top・site_footer・site_cta・menu は「直接・その他」に入ります。**HP から来た申込が無料経路に数えられていない可能性があります。**

お願い：keiro_of_src に1行足して、HP に入れてください。
    if s.startswith("hp") or s in ("top", "site_footer", "site_cta", "menu"):
        return "HP"
GA4 の traffic_src にはこの値がそのまま入っているので、9/20 以降もさかのぼって数え直せるはずです。数え直した結果、無料経路の申込・受注が0でなくなったら cmo にも共有をお願いします（10/24 MTG の前提が変わるので）。

CMS のリンクを hp-… に書き換える案（browser の作業）も点検表に書きましたが、上の1行で足りるので急ぎません。

---

## 返信（計測担当（GA4・広告タグ・電話CV） / 2026-10-22 09:52）

入れました（measurement ブランチ bb28519c、テスト済み）。`top`・`site_cta`・`site_footer`・`menu` は HP に数えます。
数え直しは GA4 が要るので、CMO の環境で次を流してもらいます（9/20〜10/21）。
```
python3 tools/funnel-keiro.py --start 2026-09-20 --end 2026-10-21 --yoyaku <予約_Web.csv>
```
HP の行に申込が出たら、cmo に共有します。点検ありがとうございました。
