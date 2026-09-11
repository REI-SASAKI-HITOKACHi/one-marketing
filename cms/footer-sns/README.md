# フッターにInstagram・Facebookのリンクを置く

作成 2026-09-11 ／ LP・サイト担当 ／ **反映はまだしない**

## 状態：**URL未着**

ネット流入施策担当（`web-inflow`）から、Instagram・FacebookのURLが届いていません。
掲示板 `20260910-01-web-inflow`「SNSアカウントの前提条件が埋まりました（誰が管理しているか）」
で管理者の確認が進んでいる段階です。

**URLが届き次第この原稿を確定します。** 以下は入れる場所と体裁だけ先に決めたものです。

## 入れる場所

フッターの `.foot-links` 相当の位置。現在ここには次が並んでいます。

```
個人情報の取扱いについて　｜　公式サイト
```

同じ行の末尾にSNSを足します。**新しいブロックは作りません**（フッターの情報量を増やすと
電話番号と住所が埋もれます）。

```html
<a href="（Instagram URL）" target="_blank" rel="noopener">Instagram</a>
<a href="（Facebook URL）" target="_blank" rel="noopener">Facebook</a>
```

## 決めておくこと（CMO宛）

1. **アイコンにするか、文字にするか。** 文字を推します。アイコンはCMSに画像を上げる手間が増え、
   公式サイトの他のリンクが全て文字なので浮きます
2. **`rel="noopener"` は必須**（付けないと開いた先から元のタブを操作できる）
3. リソース `2234`（インスタ投稿表示）が既にあります。**フッターのリンクとは別物**ですが、
   投稿表示を使うなら二重にInstagramへの導線ができます。どちらにするかCMOの判断が要ります

## 反映後の確認方法

```bash
curl -sS https://one-hitter.jp/ | grep -o 'href="https://[^"]*\(instagram\|facebook\)[^"]*"'
# Instagram と Facebook のURLが1つずつ出ること

curl -sS https://one-hitter.jp/ | grep -c 'rel="noopener"'
# SNSリンクのぶん増えていること
```
