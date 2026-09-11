# フッターにInstagram・Facebookのリンクを置く

作成 2026-09-11 ／ LP・サイト担当 ／ **反映はまだしない**（CMOがオーナーに一括で上げる）

依頼元：掲示板 `20260911-01-lp`（ネット流入施策担当）
背景：公式サイト4ページの外部リンクが公式LINEの1本だけで、SNSへの導線が0件だった
（`docs/sns-90日運用案.md` 1-1）。CMOが「置く」と決定（`20260910-02-cmo` 返信2）。

## 貼る内容

```html
<a href="https://www.instagram.com/onehitter.jp/" target="_blank" rel="noopener">Instagram</a>
<a href="https://www.facebook.com/people/One-Hitter/100084190801350/" target="_blank" rel="noopener">Facebook</a>
```

## 入れる場所

フッターの `.foot-links` 相当の行の末尾。現在ここには次が並んでいます。

```
個人情報の取扱いについて　｜　公式サイト
```

**新しいブロックは作りません。** フッターの情報量を増やすと電話番号と住所が埋もれます。

## 決めたこと

- **アイコンではなく文字にしました。** CMSへの画像追加が不要で、公式サイトの他のリンクが
  全て文字なので浮きません
- `target="_blank"` と `rel="noopener"` を付けます。`noopener` が無いと、
  開いた先のページから元のタブを操作できてしまいます

## URLの確認状況

| | URL | 確認 |
|---|---|---|
| Facebook | `https://www.facebook.com/people/One-Hitter/100084190801350/` | **HTTP 200** |
| Instagram | `https://www.instagram.com/onehitter.jp/` | **未確認（HTTP 429）** |

Instagram は **429（レート制限）** で確認できませんでした。404ではないのでURL自体は
妥当だと思いますが、断定はしません。**貼る前にブラウザで一度開いて確かめてください。**

## 後で差し替えが要るもの

- **FacebookのURLは `/people/…/数字ID/` 形式です。** オーナーがページにユーザーネームを
  付けたら短いURLに変わります。差し替えはネット流入担当から再度依頼が来ます
- **Googleビジネスプロフィールのリンクは未定。** 管理者の確定待ち（CMOが確認中）

## CMOへの判断依頼（1件）

リソース `2234`（インスタ投稿表示）が既にあります。投稿表示を使うなら、
フッターのリンクと合わせて**Instagramへの導線が二重**になります。どちらにしますか。

こちらの推奨は**フッターのリンクだけ**です。投稿表示はページの読み込みが重くなり、
投稿が止まると「更新されていない会社」に見えます。

## 反映後の確認方法

```bash
curl -sS https://one-hitter.jp/ | grep -o 'href="https://www\.\(instagram\|facebook\)[^"]*"'
# Instagram と Facebook のURLが1つずつ出ること

curl -sS https://one-hitter.jp/ | grep -c 'rel="noopener"'
# SNSリンクのぶん増えていること
```
