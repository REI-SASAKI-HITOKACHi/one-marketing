# hitokachi-forms の切り出し（2026-09-05）

`hitokachi-forms/` は **ヒトカチ株式会社**の帳票自動作成システムで、
ワンヒッター株式会社のマーケティング資産とは**別会社・別プロジェクト**。
one-marketing リポジトリに同居していたため、専用リポジトリへ移す。

## このフォルダにあるもの

`hitokachi-forms.bundle` — `git subtree split` で切り出した完全な履歴（246KB）

| | |
|---|---|
| 元ブランチ | `claude/auto-form-generation-system-uwv3mf` |
| 切り出したパス | `hitokachi-forms/` |
| コミット数 | **21**（履歴は保たれている） |
| ファイル数 | 33 |
| ブランチ名 | `hitokachi-forms-split` |
| ワンヒッターのファイル | **混入なし**（検証済み） |

バンドルから復元できることは検証済み。

---

## 移設の手順

### ステップ1：オーナーが空のリポジトリを作る

**CMO側では作成できない**（GitHub連携にリポジトリ作成権限がなく、403で弾かれる）。

1. https://github.com/new を開く
2. Repository name：**`hitokachi-forms`**
3. Description：`帳票自動作成システム（ヒトカチ株式会社）`
4. **Private** を選ぶ
5. **「Add a README file」などのチェックは全部外す**（空のまま作る。中身を入れると後で衝突する）
6. 「Create repository」

### ステップ2：中身を入れる

**方法A：CMO側でやる（推奨）**

新リポジトリができたら「作ったよ」と伝えてください。
セッションにリポジトリを追加して、バンドルから push します。

**方法B：オーナーのPCでやる**

`hitokachi-forms.bundle` をダウンロードして、次を実行。

```bash
git clone -b hitokachi-forms-split hitokachi-forms.bundle hitokachi-forms
cd hitokachi-forms
git branch -m hitokachi-forms-split main
git remote remove origin
git remote add origin https://github.com/REI-SASAKI-HITOKACHi/hitokachi-forms.git
git push -u origin main
```

### ステップ3：帳票スレッドを新リポジトリに向ける

**セッションのリポジトリは後から差し替えられない。** 新しいスレッドを
`hitokachi-forms` リポジトリで始めて、引き継ぐこと。

引き継ぎ時に伝えるとよいこと：
- GASのデプロイが `clasp login`（ブラウザ認証）待ちで止まっていること
- `docs/pending-decisions.md` に判断待ちの項目があること

### ステップ4：one-marketing から削除する

**⚠️ 新リポジトリで動くことを確認してからにすること。**

`claude/auto-form-generation-system-uwv3mf` ブランチから `hitokachi-forms/` を削除する。
削除しても、履歴はバンドルと新リポジトリの両方に残る。

---

## なぜ分けるのか

one-marketing の `CLAUDE.md` は、そのリポジトリで作業する**全セッションが読み込む**。
つまり帳票（ヒトカチ）のスレッドが、ワンヒッターの売上・顧客数・報酬まで読んでいた。

いまは同じオーナーなので情報漏洩ではないが、

1. 帳票プロジェクトを将来ヒトカチ側の人に渡すと、ワンヒッターの数字も一緒に渡る
2. 帳票スレッドが無関係な文脈を読み込んで消費する
3. 別会社の資産が混在している状態そのものが望ましくない

## 移設が終わるまでの措置

`CLAUDE.md` に境界線を明記した。`hitokachi-forms/` は別会社のプロジェクトであり、
ワンヒッターの情報と混ぜないこと、CMOセーブデータはマーケティング作業のときだけ読めばよいこと。
