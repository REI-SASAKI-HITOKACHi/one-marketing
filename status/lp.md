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
