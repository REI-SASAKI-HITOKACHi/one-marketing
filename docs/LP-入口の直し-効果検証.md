# LPの入口の直し：効果検証の起点

第6回MTG（2026-10-09）6-4 のオーナー決定：
- No.2「①Realize へ原因の問い合わせを送るか ②lp.onehitter.jp/privacy/ を公開して、LP・予約ページのリンクを差し替えてよいか」→ **「どちらも実行してOK」**
- No.3「主ボタンと下部の固定バーを『空いている日を見て予約する』（予約ページ）に。交通費・浴室の範囲・クチコミ件数の固定表記外しと1便で」→ **「検証が必要だから配信後に効果検証を忘れずに行うこと。LPの改善は常に行う」**

判定は **計測担当（measurement）**。この文書は「いつ・何が変わったか」の起点の記録。

## 状態：**未配信**（2026-10-09 時点）

配信の作業は自動の権限判定で拒否され、止まっている。配信したら下の「配信日時」とデプロイIDを埋めること。
**比較期間の「配信後2週間」は、実際に配信した日時から数える。**

| サイト | 配信日時（JST） | デプロイID | 配信元 |
|---|---|---|---|
| lp.onehitter.jp（one-hitter-lp） | （未配信） | — | ブランチ `claude/lp-haishin-20261009`（73823ec3）の `deploy/netlify/` を `python3 tools/deploy-netlify.py` |
| yoyaku.onehitter.jp（onehitter-yoyaku） | （未配信） | — | CMOブランチの `lp/booking/` を `python3 tools/deploy-booking.py`（全体配信。関数 slots も一緒に送られる） |

配信の直前の本番：one-hitter-lp `6ac756236c37ab2a02dcde53`（10/8 17:36 JST）、onehitter-yoyaku `6ac8b63c31eb89dad0766499`（10/9 18:39 JST）。

## 変わるページ

### 入口の直し（予約ページへ寄せる）：4本
| ページ | ヘッダー「WEB予約」 | 最初の画面の主ボタン | 画面下の固定バー（右） | 料金計算の下 |
|---|---|---|---|---|
| /aircon/ | →予約ページ | 「空いている日を見て予約する」→予約ページ | 「空き日を見る」→予約ページ | 2択（予約ページ／フォーム） |
| /mizumawari/ | →予約ページ | 「空いている日と料金を見る」→予約ページ | 「空き日を見る」→予約ページ | 2択（予約ページ／フォーム） |
| /aircon-c/（学習版） | →予約ページ | 「空いている日を見て予約する」→予約ページ（「よくある頼み方と金額を見る」は下の文字リンクに） | 「空き日を見る」→予約ページ | 10/1 から2択（変更なし） |
| /mizumawari-b/（学習版） | →予約ページ | 同上 | 「空き日を見る」→予約ページ | 同上 |

- 予約ページへのクリックは GA4 `cta_click`（`link_target=yoyaku`、`link_position=header / hero / sticky / estimate / form`）
- 予約ページへのリンクには `lp=<ページ名>` と `src`・`cid` 等がクリックの瞬間に付く（予約_Web の流入元に残る）
- LP内のフォームはそのまま残る（2つ目の道）
- **/nenmatsu/・/nenmatsu-b/・/aircon-b/・/aircon-d/ は入口の直しの対象外**（LP担当の直し案 `docs/LP-入口の直し案-2026-10-09.md` が上の4本だけだったため）。広げるかは別途

### 交通費の一文：LP 8本＋予約ページ
aircon・aircon-b・aircon-c・aircon-d・mizumawari・mizumawari-b・nenmatsu・nenmatsu-b・予約ページ。
「遠方（目安：高速道路を使う地域）は、交通費をいただく場合があります。お見積りのお電話でご案内します。」（金額は書かない）

### 浴室の「含まれるもの／別料金のオプション」：3ページ
mizumawari・mizumawari-b・予約ページ（申込ボタンの手前）。

### Googleクチコミの件数（23件）を外す：5本
nenmatsu・aircon-c・aircon-d・mizumawari-b・nenmatsu-b。「★5.0」と時点（2026年9月時点）は残す。

### 個人情報の取扱いのリンク先：20ページ＋予約ページ
`https://lp.onehitter.jp/privacy/`（新設）へ。LP 8本の index・thanks、survey、tokushoho、予約ページ。

## 比べる指標（計測担当が判定）

| 指標 | 出どころ | 備考 |
|---|---|---|
| LPの入力開始率（LP内フォーム） | GA4（ページ別 閲覧 → フォーム入力開始） | 主な入口を予約ページにしたので、**下がっても失敗とは限らない**。予約ページへの遷移と合わせて見る |
| 予約ページへの遷移（クリック率） | GA4 `cta_click`（link_target=yoyaku）÷ LP閲覧。`link_position` 別 | `link_position` はカスタムディメンションの登録が要る（measurement） |
| 申込数 | 予約_Web（流入元の `lp=`）＋ Netlify Forms `reserve-*`・`yoyaku` | LP内フォーム経由と予約ページ経由を分けて数える |

- **比較期間**：配信前 **2026-09-28〜10-08** と、配信後 **2週間**（配信日時から）
- ページ別（aircon・mizumawari・aircon-c・mizumawari-b）に並べる。入口の直しの対象外の nenmatsu 等は対照として見る
- 同じ便で交通費・浴室・クチコミ件数も変わるので、入口の直しだけの効果とは切り分けられない（1便で出す決定のため）

## 配信前の確認（2026-10-09 済み）
- 本番 one-hitter-lp の全156ファイルが LP担当ブランチ 1953459c の `deploy/netlify/` と一致 → その上に 34387c0b（privacy）と3つの変換を当てた
- 本番との差分は「privacy のリンク差し替え＋chuuki-1008／iriguchi／bunmen-1010 の変換」だけで説明できることを機械で照合（想定外 0）
- 学習版4本は `build-site.py`（学習版を CHUUKI/BUNMEN/IRIGUCHI に足し、iriguchi を lp= の後ろへ移したもの）でビルドした結果と一致
- 全HTML（19本＋予約ページ）：check-public-page OK、98.8% なし、「23件」なし、電話 080-8043-8259 あり・080-1755-7275 なし、個人情報リンクは lp.onehitter.jp/privacy/ のみ
- check-tracking netlify OK
- スマホ幅（390px）で aircon・mizumawari・aircon-c・mizumawari-b の主ボタン・固定バーが `https://yoyaku.onehitter.jp/?lp=<ページ>&src=…` へ飛ぶことを手元で確認

## 配信後にやること
1. 上の表に配信日時・デプロイIDを書く
2. 本番を取り直して手元と一致するか（one-hitter-lp は deploy-netlify.py の kenshou、予約ページは deploy-booking.py の一致確認）
3. `https://lp.onehitter.jp/privacy/` が 200
4. スマホ幅で4本の主ボタン・固定バーが予約ページへ飛ぶこと（本番で）
5. measurement に判定を依頼（配信後2週間の日付で）
