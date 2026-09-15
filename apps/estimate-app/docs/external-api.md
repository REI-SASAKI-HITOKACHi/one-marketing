# 外部API（doPost）仕様

見積アプリを外のプログラムから呼ぶための入口。CMOスレッドが請求書を発行するために追加した
（掲示板 `20260915-02-quotation`）。

**画面（`doGet`）とは完全に別系統です。** 現場が使っている画面の動きは一切変えていません。

---

## 1. まだ有効になっていません

デプロイと合言葉の設定が済むまで、この入口は**全リクエストを拒否**します。

有効にするには2つ必要です。**どちらもオーナーの操作です。**

1. **合言葉を設定する** … Apps Scriptエディタで `adminSetApiToken('32文字以上の合言葉')` を1回実行
2. **ウェブアプリを公開する** … 「デプロイを管理」→ アクセスできるユーザー＝**全員**

`2` だけやって `1` を忘れても、**誰にも何もできません**（合言葉が無ければ全部拒否）。
逆に `1` だけでも外からは届きません。この順番はどちらでも構いません。

止めたいときは `adminClearApiToken()` を実行すれば、デプロイを触らずに即座に閉じます。
いま設定されているかどうかは `adminCheckApiToken()` で確認できます（値は表示しません）。

---

## 2. 呼び方

```
POST  <ウェブアプリのURL>/exec
Content-Type: application/json

{ "token": "合言葉", "action": "アクション名", ...パラメータ }
```

返りは**常にJSON**です。

```json
{ "ok": true,  ... }
{ "ok": false, "error": "理由" }
```

> **HTTPステータスは常に 200 です。** Apps Script の仕様で、失敗しても 4xx／5xx になりません。
> **必ず `ok` を見て判断してください。**

### curl の例

```bash
curl -sS -L -X POST "$GAS_URL/exec" \
  -H 'Content-Type: application/json' \
  -d '{"token":"'"$GAS_TOKEN"'","action":"ping"}'
```

`-L` が要ります。Apps Script は `script.googleusercontent.com` へリダイレクトします。

---

## 3. アクション一覧

| action | 種別 | 必須 | 任意 | すること |
|---|---|---|---|---|
| `ping` | 読み | — | — | 疎通確認。副作用なし |
| `getEstimate` | 読み | `estimateId` | — | 見積の内容を返す |
| `getInvoice` | 読み | `invoiceId` | — | 請求の内容を返す |
| `saveEstimate` | 書き | `payload` | — | 見積を保存し、見積番号を返す |
| `buildEstimate` | 書き | `estimateId` | `rowNumber` | 見積書PDFを作りDriveに保存、Gmail下書きを作る |
| `startInvoice` | 読み | `estimateId` | — | 見積から請求の下書きを組む（保存はしない） |
| `saveInvoice` | 書き | `payload` | — | 請求を保存し、請求番号を返す |
| `buildInvoice` | 書き | `invoiceId` | `rowNumber` | 請求書PDFを作りDriveに保存、Gmail下書きを作る |

`rowNumber` は `saveInvoice` の返りに入っています。渡すと行の検索を省けます（速くなるだけで、無くても動きます）。

### 典型的な流れ

**見積**

```
saveEstimate(payload)      → 見積番号（YYYYMMDD-nn）と rowNumber が返る
buildEstimate(estimateId)  → PDFのURLとファイルID、Gmail下書きのURLが返る
```

**請求**

```
startInvoice(estimateId)   → 金額と既定値を確認
saveInvoice(payload)       → 請求番号（YYYYMMDD-nn）と rowNumber が返る
buildInvoice(invoiceId)    → PDFのURLとファイルID、Gmail下書きのURLが返る
```

**採番はアプリがやります。** 呼ぶ側で番号を決めないでください。
規則は `YYYYMMDD-nn`（`docs/README.md` の「0a. 書類番号の採番」）。

**Gmailは下書きまでです。** 送信はしません。

---

## 4a. `payload` の形（`saveEstimate`）

**金額は渡しません。単価も渡しません。** メニューIDと数量だけ渡せば、
マスタの単価・繁忙期加算・割引をアプリが当てます。

| キー | 必須 | 型 | 説明 |
|---|---|---|---|
| `requestId` | ○ | 文字列 | 重複防止用。呼ぶ側でUUIDを作る |
| `details` | ○ | 配列 | 明細。`[{ "menuId": "M003", "qty": 1 }]` |
| `customerName` | ○ | 文字列 | 顧客名 |
| `projectType` | | 文字列 | 案件タイプ。既定は `自社` |
| `projectName` | | 文字列 | 案件名 |
| `siteAddress` | | 文字列 | 現場住所 |
| `workDate` | | `yyyy-MM-dd` | 作業予定日。繁忙期の判定に使う |
| `staff` | | 文字列 | 担当者 |
| `channel` | | `通常`/`WEB経由` | 受注経路。既定は `通常` |
| `highwayFee` | | 数値 | 高速代（非課税） |
| `remarks` | | 文字列 | 備考 |
| `adjustments` | | 配列 | 変則的な割引・割増 |
| `targetTotal` | | 数値 | 税込合計をこの額に合わせる |

`details` の `menuId` はメニューマスタのIDです（`M001` ノーマルエアコン、`M003` 洗濯機クリーニングなど）。
`getEstimate` で既存の見積を読めば、実際の入り方を確認できます。

**受注経路で料金が変わります。** `WEB経由` にすると同時施工価格とネット申込特典が効きます
（`docs/README.md` の「0b」）。**電話・紹介のお客様に `WEB経由` を使わないでください。**

---

## 4b. `payload` の形（`saveInvoice`）

`startInvoice` が返す `calcPayload` をそのまま加工して渡すのがいちばん確実です。
手で組むなら下記。**金額は渡しません。アプリが計算します。**

| キー | 必須 | 型 | 説明 |
|---|---|---|---|
| `estimateId` | ○ | 文字列 | 元になる見積番号 |
| `requestId` | ○ | 文字列 | 重複防止用。呼ぶ側でUUIDを作る。同じ値で2回呼んでも1件しかできない |
| `invoiceDate` | | `yyyy-MM-dd` | 請求日。既定は実行日 |
| `workCompletedDate` | | `yyyy-MM-dd` | 施工日 |
| `dueDate` | | `yyyy-MM-dd` | 支払期限。既定は提出先マスタ／設定マスタの条件から計算 |
| `parkingFee` | | 数値 | 駐車場代 |
| `parkingTaxType` | | `課税`/`非課税` | 既定は設定マスタ |
| `extraWorkFee` | | 数値 | 追加作業費 |
| `discountAmount` | | 数値 | 値引き（税抜） |
| `remarks` | | 文字列 | 備考 |
| `staff` | | 文字列 | 担当者 |

**`requestId` は必ず入れてください。** 通信が切れて再送したときに、請求書が2枚できるのを防ぎます。

---

## 5. エラー

| `error` | 意味 | 対処 |
|---|---|---|
| `認証に失敗しました。` | 合言葉が違う／未設定 | `adminCheckApiToken()` で設定状況を確認 |
| `JSONとして読めませんでした。` | 本文がJSONでない | `Content-Type` と本文を確認 |
| `知らない action です：…` | 綴り違い | 返りの `actions` に一覧が入っています |
| `請求番号がありません。` | 必須パラメータ漏れ | 上の表を確認 |

**認証失敗のときは理由を細かく返しません。** 総当たりの手がかりにしないためです。

---

## 6. 安全のために決めたこと

- **合言葉が無ければ何もしない**（fail closed）。設定し忘れた状態で公開されても素通りしない
- **合言葉はリポジトリに置かない。** スクリプトプロパティと `~/.config/one-hitter/` にだけ置く
- 照合は長さが違っても最後まで比較する（応答時間から桁数が漏れないように）
- 認証失敗は操作ログに残す（合言葉そのものは残さない）
- **Gmailは下書きまで。送信はしない**
- **過去の請求書は振り直さない。** この入口からも既存行の番号は変えられない

### 合言葉の作り方

```bash
openssl rand -base64 32
```

エディタで `adminSetApiToken('…')` に貼って1回実行し、**引数欄から必ず消してください**（履歴に残ります）。

---

## 7. まだ入っていないもの

- **見積の複製**（`apiLoadEstimateForClone` 相当）。画面からは使えます
- **過去見積の検索**（`apiSearchEstimates` 相当）。`getEstimate` で番号を指定する形だけです
- **レート制限**。GASの実行回数上限が事実上の上限です。合言葉が漏れた場合に備えるなら、
  合言葉を替える（`adminSetApiToken` を再実行）のがいちばん早い対処です

どれも要るなら足します。
