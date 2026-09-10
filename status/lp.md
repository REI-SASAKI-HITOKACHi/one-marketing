# LP・サイト担当 の現況

更新: 2026-09-10 21:14

## いま何をしているか

**LP4本＋アンケートは公開済みで、手が空いています。** 直近（〜2026-09-08）で終えたもの:

- 料金シミュレーターの割引ロジック修正（依頼どおり3点）。766通り検証への対応も完了
- 年末LPの配信漏れを解消。`deploy-netlify.py` に `--site` を足し、分割サイト
  （nenmatsu / survey / booking）へ配信できるようにした。必須ファイルが欠けたら中止する
- 予約フォーム（`lp/booking/`）のデザインをLP4本に揃えて配信。生成側
  （`build-booking.py`）を直したので次のビルドで消えない。金額計算は7ケースで無傷を確認
- アンケートの別サイト（one-hitter-survey）も旧デザインのままだったので配信
- 全ページからダークテーマを撤去（`color-scheme:light`）。オーナーのスマホで
  背景が暗いグレーになっていた

## 公開中のURL

| | URL |
|---|---|
| エアコン A | https://one-hitter-lp.netlify.app/aircon/ |
| エアコン B（A/B対抗案） | https://one-hitter-lp.netlify.app/aircon-b/ |
| 水まわり | https://one-hitter-lp.netlify.app/mizumawari/ |
| 年末大掃除 | https://one-hitter-lp.netlify.app/nenmatsu/ ／ https://one-hitter-nenmatsu.netlify.app/ |
| アンケート | https://one-hitter-lp.netlify.app/survey/ ／ https://one-hitter-survey.netlify.app/ |
| 予約フォーム | https://one-hitter-booking.netlify.app/ |

**`one-hitter-lp` の5本はアフィリエイトの遷移先として登録済み。URLを変えられません。**
`deploy-netlify.py` の `KOTEI_URL` が配信前に止めます。

## 詰まっていること

**なし。** 待ちはありません。

## CMOに決めてほしいこと（掲示板に依頼を出しました）

`docs/料金シミュレーター-修正依頼.md` の【要判断】3件。掲示板の依頼を参照。

1. 年末LPが2つのURLに存在している（選択肢3つ・推奨あり）
2. ヒーローで 10,780円 を2回出すのを残すか
3. Googleクチコミ ★5.0（23件）の実数確認

## 自分で進められること（指示があれば着手）

- A/Bテストの配信振り分け。広告側で2URL出し分けを想定して進める前提を置いています
- 公式サイト（CMS）の電話番号が旧番号のまま5箇所。統一の決定に従うなら更新が要る
  （CMSはこちらの持ち物なので、指示があれば実行します）
- 2022年の「早割還元祭」記事はオーナー判断で放置

## web-inflow の判断待ちについて

掲示板の `20260910-02-cmo` に、こちらの持ち物に関わる項目が2つあります。

- 「SNSからの誘導先をどこにするか（LPは全部noindex）」
- 「公式サイトにSNSリンクを置くか」

**どちらも決まればこちらで実装できます。** noindex は広告専用の受け皿とする
オーナー判断で維持していますが、SNS流入を受けるなら方針が変わるので、
CMOの判断を待ちます。

## 今日みつけた危険（掲示板 20260910-01-measurement で計測担当へ依頼済み）

配信ルールに従って他ブランチを確認したところ、**計測ブランチの
`build-site.py` の `PAGES` に `nenmatsu` が無く、`KOTEI_URL` のガードも
ありません。** そのブランチから `one-hitter-lp` へ配信すると、
アフィリエイト登録済みの `/nenmatsu/` が本番から消えます。

計測担当へ「当面 one-hitter-lp への配信を止め、ガードを取り込んでほしい」と
依頼しました。ルール文書の「`PAGES` から `nenmatsu` を消さないこと。
これも2回起きています」がまさにこの件です。

**あわせてCMOへ：`docs/LP配信のルール.md` の「サイトと担当」の表が実態と
ずれています。** 表では `one-hitter-lp` の中身が aircon / aircon-b /
mizumawari の3本ですが、実際は `/nenmatsu/` と `/survey/` も同じサイトに
入っています（オーナーのアフィリエイト登録がこの5本に対して行われたため）。
**表はCMOの持ち物なので、こちらからは触っていません。** 更新をお願いします。

なお09-08の自分の配信で計測タグを消していないかも確認しました。
`tracking/measurement.json` は双方ともIDが空で、本番にも計測の土台が
入っています。消していません。

計測担当の `tools/check-tracking.py` は手元に取り込みました。配信するのは
こちらなので、今後は配信前にこれを通します。
