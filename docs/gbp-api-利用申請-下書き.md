# GBP API 利用申請の下書き（送信前・未提出）

作成 2026-09-20 ／ ブラウザ担当 ／ **未提出。送信はオーナーの合図待ち**

## なぜ要るか

**これが承認されるまで、写真つきのGBP投稿を機械で出せない。**
- API は有効化済みだが **`Requests per minute = 0`**（Cloud Console の割り当て画面で実測、2026-09-20）
- 受領メールが受信箱に1通も無い（`case.foot.kid@gmail.com` を30日ぶん検索）＝**申請はまだ出ていない**
- 管理画面からの写真添付は、ブラウザ担当の実行環境では不可（ファイル選択ダイアログを操作できない／CSP／自動判定）

承認されれば、**Driveの写真＋シートの原稿から、Apps Script で写真つき投稿まで自動**にできる。

## 申請の要件（公式ページ `developers.google.com/my-business/content/prereqs` より）

| 要件 | 当社の状態 |
|---|---|
| **確認済みで有効な GBP を60日以上維持** | ✅ プロフィールは **2025-12-30 に作成**（Googleからの通知メールで確認）。クチコミは2024年から付いている |
| **GBP に掲載されたウェブサイト** | ✅ `https://one-hitter.jp` |
| 申請者のメールが GBP のオーナー／管理者 | ✅ `case.foot.kid@gmail.com` は **2026-09-13 にオーナー就任**（通知メールあり） |
| Google Cloud のプロジェクト番号 | ✅ **844550773178**（one-hitter-sheets） |

## 入力内容（このまま貼れる）

| 欄 | 入れる値 |
|---|---|
| Project Number | `844550773178` |
| Contact email | `case.foot.kid@gmail.com` |
| 会社名 | ワンヒッター株式会社 |
| ウェブサイト | `https://one-hitter.jp` |
| 申請の種類 | **Application for Basic API Access** |

### 用途（英語欄がある場合）

```
We manage a single Google Business Profile for our own company
(One Hitter Inc., a house cleaning company in Edogawa-ku, Tokyo).

We want to use the API only for our own location, to:
- publish weekly "What's new" local posts,
- upload photos of our own cleaning work,
- reply to reviews,
- read basic performance metrics.

We do not manage locations for third parties and we do not resell access.
```

### 用途（日本語欄の場合）

```
自社1拠点のビジネスプロフィール（ワンヒッター株式会社／東京都江戸川区のハウスクリーニング）に対して、
最新情報の投稿・自社の施工写真の追加・クチコミへの返信・指標の取得を行うために使用します。
第三者の店舗は扱わず、アクセスの再販も行いません。
```

## 送信について

- **送信は外部への提出**にあたるため、**オーナーの合図が要る**（ブラウザ担当の規則）
- 送信後：受領メールの有無と日付を記録し、CMO に報告する
- 承認されたら：`Requests per minute` が 0 から増えるので、Cloud Console で確認できる

## 承認までの間

`docs/gbp-更新の座組.md` の①②で回す（本文だけの予約投稿＋写真は別途）。
