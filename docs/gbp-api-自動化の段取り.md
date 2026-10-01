# GBP API 自動化の段取り（2026-10-01 20:00 締切の依頼 20261001-03 への回答）

作成 2026-10-01 ／ web-inflow ／ 根拠：`20261001-02`（Googleから許可済みの回答）・`20261001-03`

**状態：道具は作った。実機では1回も動かしていない。** refresh_token が無いため。
動かしていないものを「動く」とは書かない。最初の実行は一覧系と `--dry-run` から。

## 1. 作ったもの（すべて `tools/`、鍵は読むだけ・値は出さない）

| ファイル | 役割 | 送信するか |
|---|---|---|
| `gbp_client.py` | トークン更新・API呼び出し。`check`（トークンが取れるか）`locations`（account/location の値を調べる） | しない |
| `gbp-auth.py` | **オーナーが「許可」を1回押す**だけで refresh_token を `~/.config/one-hitter/gbp.json` に保存 | しない |
| `gbp-post.py` | ① 最新情報の投稿。キュー `data/gbp-queue.json` の承認済み・予定超過だけ出す | **する**（`--dry-run` 既定の運用） |
| `gbp-reviews.py` | ② クチコミの新着取得（返信なしの一覧）。返信は**査読済みの文ファイルを指定したときだけ** | 返信時のみ |
| `gbp-insights.py` | ③ 検索・地図の表示／通話／サイトクリック／ルートの週次（今期と前期） | しない |

`gbp-post.py` の門：`check-gbp.py`（字数・禁止語・本舗の語・相対表現・写真前提・時刻・繁忙期）＋承認の記録＋**ボタンURLの計測の印**（予約→`?src=gbp`、詳細→`utm_source=gbp`）。門を落とした投稿は出さない。

**予約投稿の機能は API に無い前提で作った。** 「予定」を過ぎた承認済みを、sns-post.py と同じ定期実行（平日 09:00・12:00）で出す。（Googleの公開仕様では localPosts に予約日時の項目が見当たらない。実機で確かめる）

## 2. 認証の段取り（オーナーの手は「許可」1回）

1. **クライアントは流用できる。** `~/.config/one-hitter/gmail-oauth.json` の client_id は、許可済みプロジェクト `844550773178` のものと確認した（先頭の番号が一致。値は出していない）。**ただしこの refresh_token は Gmail 用で、GBP には使えない。** business.manage で取り直す
2. ブラウザ担当が確認（CMOから依頼済みのもの＋下の2点）
   - My Business Account Management API／Business Information API／Business Profile Performance API／**My Business API（v4 の投稿・クチコミ用）**が有効か。割り当て（Requests per minute）が 0 でないか
   - **OAuth 同意画面に `business.manage` スコープを足し、case.foot.kid をテストユーザーに入れる。** 状態が「テスト」だと refresh_token は**7日で切れる**ので、公開状態にするか、毎週取り直す
   - クライアントの種類がデスクトップ型か（`gbp-auth.py` はループバック `http://127.0.0.1:8765/` を使う）。Web 型なら、この redirect URI を登録する
3. オーナーのPCで `python3 tools/gbp-auth.py` → ブラウザで「許可」→ `gbp.json` に保存
4. `python3 tools/gbp_client.py locations` で account / location の値を調べ、`gbp.json` に足す
5. 資格情報の本体は Drive「ワンヒッター_認証情報（ここだけ）」にだけ置く。掲示板・コミットに値は書かない（`.gitignore` に `gbp.json` を追加済み）

## 3. 動かす順番（届いたら即）

1. `gbp_client.py check` → `locations`
2. `gbp-insights.py`（読むだけ。月曜 08:30 の週次の GBP 欄に入る）
3. `gbp-reviews.py`（読むだけ。返信下書きは `docs/gbp-クチコミ返信の型.md` で作り、cmo 査読）
4. `gbp-post.py --dry-run` → 問題なければ定期実行に載せる（**外に出す**操作なので、最初の1本はオーナー承認を取る）

## 4. 未解決（正直に）

- **予約済み20本の本文の実物が、シートにもリポジトリにも無い。** 「GBP投稿管理」の投稿タブは G001〜G010・予約済み0のまま、ボタン列は「予約／詳細」の文字だけでURLが入っていない。`posts_min.json` を入れる依頼はブラウザ担当に出ているが未着
- API の通信部分は、公開仕様に基づく実装で**実機未確認**。エンドポイント・項目名が違えば、最初の実行で分かる
