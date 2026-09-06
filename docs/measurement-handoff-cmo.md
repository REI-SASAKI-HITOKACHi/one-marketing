# CMOスレッドへの引き継ぎ：アンケートと年末LPに計測を入れる

作成 2026-09-06 ／ 計測担当スレッド（ブランチ `claude/measurement-ga4-calltracking`）

---

## これは何か

アンケート（`lp/survey/`）と年末LP（`lp/nenmatsu/`）は **CMOスレッドの持ち物**なので、
こちらのブランチには入っていません。**ファイルを勝手に持ってきて二重管理にはしません。**

代わりに、**そちらで1コマンド実行すれば入る形**にしてあります。
このファイルは、その手順です。

> **オーナーの判断（2026-09-06）：アンケートには入れる。年末LPは各スレッドの判断でよい。**

---

## 前提：ブランチを合流させる

計測の仕組みは `claude/measurement-ga4-calltracking` にあります。まずこれを取り込んでください。

```bash
git fetch origin claude/measurement-ga4-calltracking
git merge origin/claude/measurement-ga4-calltracking
```

### ⚠️ `tools/build-site.py` は競合します

両ブランチで同じファイルを変えているためです。**中身が違うので、どちらかを捨ててはいけません。**

| どちらの変更か | 内容 | どうするか |
|---|---|---|
| CMO側 | `nenmatsu` の追加、`STATIC_PAGES`（アンケート）、`build_static_page()` | **残す** |
| 計測側 | `tracking_head()` / `tracking_body()` / `swap_tel()` / `build_thanks()`、`PAGES` への `lp_id`・`lp_variant`、`load_measurement()` | **残す** |

**どちらも足し算なので、両方を残せば通ります。** 合流したら、必ず動作を確かめてください。

```bash
python3 tools/build-site.py netlify
python3 tools/check-tracking.py netlify
```

`check-tracking.py` は `PAGES` に載っているLPしか見ないので、
`nenmatsu` を `PAGES` に足してあれば、そちらも自動で確認対象に入ります。
**`lp_id` と `lp_variant` の2つを書き足すのを忘れないでください**（無いとビルドが落ちます）。

---

## アンケートに入れる（1コマンド）

アンケートは断片ではなく**完結したHTML文書**なので、LPの組み立てには乗りません。
専用の差し込みツールを用意しました。

```bash
python3 tools/build-site.py netlify          # いつもどおり書き出す
python3 tools/inject-tracking.py deploy/netlify/survey/index.html --kind survey --id survey
```

これを `tools/build-site.py` の後ろに置くだけです。

- **何度実行しても二重には入りません。** 既に入っていれば入れ替えます
- `tracking/measurement.json` の測定IDが空なら、タグは出力されません（壊れません）
- **アンケートのソース（`lp/survey/index.html`）は1文字も変わりません**

### 入るイベント

| イベント名 | いつ |
|---|---|
| `survey_start` | 最初の設問に触れたとき |
| `survey_step` | 各画面が表示されたとき（`step_number` 1〜4） |
| **`survey_complete`** | **回答が送信され、完了画面が出たとき** |
| `review_copy` / `google_review_click` | クチコミの下書きコピー／Googleの投稿画面へ |
| `refer_copy` / `refer_share` | 紹介文のコピー／LINEで送る |
| `private_send` | 非公開のご意見を送る |

**回答率 ＝ `survey_complete` ÷ `page_view`。**
`survey_step` を並べれば、4画面のどこで抜けているかが分かります。

### 動作確認は済んでいます

**公開中のアンケートページ（`one-hitter-survey.netlify.app`）を実際に取得して差し込み、
Chromiumで1画面目から完了画面まで通しで操作**して、次を確認しました。

- `survey_step` 1 → 2 → 3 → 4、`survey_start`、`survey_complete` が正しく1回ずつ送られる
- 完了画面の各ボタン（クチコミ・紹介・非公開意見・Googleリンク）が拾える
- **アンケート本来の動作（設問の分岐、下書き生成、LINEの共有URL）は壊れていない**
- JSエラーなし

---

## GA4の測定IDについて（重要）

アンケートは **`one-hitter-survey.netlify.app` という別サイト**です。
LPとは別サイトですが、**同じGA4プロパティに入れて構いません。**
`page_kind`（`survey` / `lp` / `thanks`）で切り分けられるようにしてあります。

分けたい場合は、そちらで別の `measurement.json` を用意する形になります。
**まずは1つにまとめることを勧めます。** 小規模なので、分けても手間が増えるだけです。

---

## 年末LP（`lp/nenmatsu/`）に入れる場合

年末LPは断片なので、**`tools/build-site.py` の `PAGES` に足すだけ**です。

```python
"nenmatsu": {
    "dir": "nenmatsu",
    "lp_id": "nenmatsu",      # ← この2行を足す
    "lp_variant": "A",
    ...
},
```

これだけで、計測タグ・送信完了ページ・電話番号の差し替えが自動で付きます。

**ただし、年末LPは未公開なので急ぎません。** 公開の直前で間に合います。

---

## 触っていないもの

- `lp/survey/index.html` `lp/nenmatsu/index.html` の**中身**（デザイン・コピー・価格）
- `data/prices.json`
- QR関連（`lp/survey/qr/`、`tools/make-survey-qr.py`）

計測担当が変更したのは、LP 3本（`aircon` / `aircon-b` / `mizumawari`）の
**書き出し処理と、計測の設定ファイルだけ**です。

---

## 参照

| | |
|---|---|
| `docs/measurement-audit.md` | 計測の棚卸し（何が測れていて、何が測れていないか） |
| `docs/measurement-spec.md` | **イベントとコンバージョンの定義。これが正** |
| `docs/measurement-owner-steps.md` | オーナーの作業手順（GA4・広告・電話計測） |
| `docs/calltracking-vendors.md` | コールトラッキング事業者の比較 |
