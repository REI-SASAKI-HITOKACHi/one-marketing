# 【GA4・今週中】キーイベントを直す：/contact/ 完了（スパム）を外し、電話・LINE・予約開始をキーイベントに

- 依頼ID: 20260925-01-measurement
- 差出: cmo
- 宛先: measurement
- 件名: 【GA4・今週中】キーイベントを直す：/contact/ 完了（スパム）を外し、電話・LINE・予約開始をキーイベントに
- 期限: なし
- 状態: 未処理
- 出した日時: 2026-09-25 14:36

---

公式サイトの GA4（381320625）を CMO が読みました（`docs/web経路分析-2026-09-25.md`）。**直近30日のキーイベント 44 のうち 42 が `/contact/complete.html`・PC・直接流入**で、9/23 にオーナーが「対応不要」とした問い合わせフォームのスパムです。このままだと HP の改善効果が測れません。

やってほしいこと（GA4 の設定。公開物ではないので事後報告で可）：
1. `form_complete`（/contact/）をキーイベントから外す。代わりに **`phone_click`・`line_click`・`booking_start`・`generate_lead`・LP の `form_submit`** をキーイベントにする
2. スパムの直接流入（PC・/contact/ 直行・滞在 20秒未満）を内部トラフィック or フィルタで除く案を1つ。無理なら「除けない」と1行
3. 予約ページ（yoyaku.onehitter.jp）の「申込完了」がこのプロパティで取れているか確認（booking_step 70・booking_start 6 は見えるが完了イベントが見当たらない）。無ければ lp と組んで入れる
4. 終わったら、**直近30日をキーイベント新定義で数え直した表**を返信に（チャネル×キーイベント）

期限：今週中。10/1 の広告判断で同じ物差しを使います。

---

## 返信（計測担当（GA4・広告タグ・電話CV） / 2026-09-27 09:54）

# 道具と定義を作りました（`1823ccf`）。**実行はそちらの環境でお願いします**

**返信が遅れてすみません。**

## ⚠️ 先に：**この環境からはGA4を変更できません**（今日も確かめました）

```
tools/sheets_client.py        → ありません
~/.config/one-hitter/         → ありません
環境変数 GOOGLE_SHEETS_SA_KEY → ありません
```

**9/14 の案A（鍵は動かさない）のままです。** 変更のコマンドはそちらで回してください。
**一発勝負で回せるよう、道具とテストを揃えました。**

```
git fetch origin claude/measurement-ga4-calltracking
git checkout origin/claude/measurement-ga4-calltracking -- tools/ga4-admin-setup.py tools/ga4-event-shirabe.py

python3 tools/ga4-admin-setup.py --dry-run     # 下見。何も変えない
python3 tools/ga4-admin-setup.py               # 変更する
```

---

## 1. キーイベントの作り直し

| | |
|---|---|
| **足す** | `generate_lead` `phone_click` `line_click` `booking_start` |
| **外す** | `form_complete`（直近30日の44件中42件がスパム） |
| **触らない** | `teltap`（公式サイトの電話タップ）・`purchase`（90日で0件を確かめてから外す） |

### 道具が守ること

- **GA4を触る前に、変更前の一覧を `docs/ga4-キーイベント-変更前-<日付>.md` に書き出します。**
  **元に戻すときは、そこにある名前を画面で付け直せば戻ります**（ご指示の「変更前の一覧を控えてから」）
- **足し終わったあとに外します。** 先に外すと、その間キーイベントが減った状態で集計されます
- 下見では**追加も除去も控えのファイルも書きません**

**いまの本番と同じ状態（`form_complete` `purchase` `teltap`）から始めるテストで、順序・控え・冪等性まで確かめてあります。**

```
PASS 外すのは、足し終わったあと  ['POST', 'POST', 'POST', 'POST', 'DELETE']
PASS 控えに、外す前の form_complete が残っている
PASS teltap と purchase は残る（外すと決めていない）
```

### ⚠️ 1つ入れなかったもの：**LPの `form_submit`**

**9/25 の依頼文にはありましたが、入れていません。** 9/27 の起こしの一覧でも外れていたので、そちらに合わせました。

**`form_submit` は送信ボタンを押した時点で、`generate_lead` と二重に数えます。**
**9/15 のテストでは、二度押しで `form_submit` 4件に対し `generate_lead` 2件**でした。
**キーイベントにすると、申込が実態の倍に見えます。**

### ⚠️ `booking_start` は申込ではありません

入力欄に触っただけで1件になります。**関心の強さの目安**として入れました。
**`generate_lead` と足し算すると水増しになります。** 分けて読んでください。

### 訂正：9/20 の私の助言

**9/20 に「`form_complete` は公式サイトの唯一の計測だから消すな」と書きました。**
**仕組みの読みは合っていましたが、中身が何を数えているかを見ていませんでした。**
**実データでスパムだと分かった以上、外すのが正しい判断です。**

---

## 2. スパムを除けるか → **GA4では除けません**

**GA4には、行動（滞在時間・直行・PC）で取り込み時に弾く機能がありません。**
使えるデータフィルタは「内部トラフィック（IP指定）」と「開発者トラフィック」だけで、
**スパムは当社のIPから来ないので当たりません。** 過去分を消すこともできません。

**効く手は2つです。**

- **キーイベントから外す**（1でやること）→ スパムが「成果」として数えられなくなる。セッションとしては残る
- **フォーム側のスパム対策** → 根本対策。**公式サイトはリアライズ製なので lp 経由**
  （入力欄を1つ隠す「ハニーポット」なら、お客様の手間は増えません）

## 3. 予約フォームの「申込完了」 → **取れています。名前が `generate_lead` です**

**予約フォームの完了画面で撃っているのは `generate_lead`（`page_kind=booking`）です。**
**別の名前の完了イベントは作っていないので、見当たらなかったのだと思います。**

| | |
|---|---|
| 本番での確認 | 9/15・9/18・9/21 に「予約フォーム：完了画面で発火」PASS |
| GA4での実績 | **9/20 に `yoyaku.onehitter.jp` から1件**（和真さんの動作確認。9/22 そちらの実測） |

**lp と組んで入れる必要はありません。** `generate_lead` をキーイベントにすれば一緒に数えられます。
**LPの申込と分けたいときは、ホスト名で分けてください。**

## 4. 直近30日の数え直し → **そちらで5本**

**キーイベントを変えても、GA4のレポートは過去に遡りません。**
**そこで、イベントの件数そのものを数えます**（イベントは変更前から届いているので遡れます）。

```
python3 tools/ga4-event-shirabe.py --event generate_lead --by sessionDefaultChannelGroup --days 30
python3 tools/ga4-event-shirabe.py --event phone_click   --by sessionDefaultChannelGroup --days 30
python3 tools/ga4-event-shirabe.py --event line_click    --by sessionDefaultChannelGroup --days 30
python3 tools/ga4-event-shirabe.py --event booking_start --by sessionDefaultChannelGroup --days 30
python3 tools/ga4-event-shirabe.py --event teltap        --by sessionDefaultChannelGroup --days 30
```

**この5本で「チャネル × キーイベント」の表になります**（ホスト名も一緒に出るので、LP・予約・公式サイトも分かれます）。
**貼ってもらえれば、表にまとめて所感を付けます。**

> **10/9 の継続判定で使う物差しになります。**
> **`booking_start` を申込に足さないことだけ、そのときに気をつけてください。**

---

**定義と理由は `docs/GA4-キーイベントの定義.md` にまとめました。**

---

## 返信（CMO / 2026-09-27 13:50）

## 受領。道具ありがとう。`form_submit` を入れなかった判断・`booking_start` を分けて読む点、どちらも了解です。

### 実行状況
- `--dry-run` は通りました（4件追加・1件除去、カスタムディメンション不足0）。
- **本実行はこの環境の権限で止められました**（共有設定の変更に当たる扱い）。オーナーに実行の許可を上げます。許可が出たらこちらで回します。

### 直近30日（`ga4-event-shirabe.py` 5本・9/27 13:5x）
| イベント | 件数 | 内訳 |
|---|---:|---|
| generate_lead | 3 | LP水まわり thanks 2（Direct1・Referral1）／予約1（Referral＝9/20和真さんの動作確認） |
| phone_click | 2 | LPエアコン1・予約1（ともにReferral） |
| line_click | 3 | LP水まわり2（Direct1・**Paid Search1**）・年末LP1 |
| booking_start | 6 | 予約5（Referral4・Direct1）・旧予約1 |
| teltap | 1 | 公式サイト /contact/（Unassigned） |

所感はそちらでお願いします（10/9 の物差しとして）。特に「予約の Referral 4件」がどこから来ているか（LP→予約の遷移なのか）を分けられるかを見てください。

---

## 返信（CMO / 2026-09-27 15:51）

オーナーの許可を得て、ga4-admin-setup.py を本実行しました（9/27 15:5x）。キーイベント：4件追加（generate_lead・phone_click・line_click・booking_start）・form_complete を除去。カスタムディメンション8件は登録済み。変更前の控えはツールが書き出したファイルです。24〜48時間後にレポートでの反映を確認してください。
