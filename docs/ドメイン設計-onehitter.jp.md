# LP用ドメイン `onehitter.jp` のホスト名設計

作成 2026-09-12 ／ LP・サイト担当 ／ 依頼 `20260912-04-lp`（オーナー決定：ドメインは取得する）

> **公式サイト `one-hitter.jp` はこの設計に含みません。** リアライズ管理のまま、一切触りません。
> `lp.one-hitter.jp` は**リアライズがCNAME追加に対応不可**と回答したため白紙になりました。

## 大前提：既存のURLは全部残す。301もしない

| | |
|---|---|
| `one-hitter-lp.netlify.app/aircon/` ほか5本 | **アフィリエイトの遷移先として登録済み** |
| `/survey/` | **現場のQRコードに刷り込み済み** |
| `one-hitter-nenmatsu.netlify.app` | SMSに記載済み（いまは301で `/nenmatsu/` へ） |

**新ドメインは「増やす」だけで、古いURLは生かしたままにします。**
Netlifyはカスタムドメインを足しても `.netlify.app` のURLを止めないので、両方が並びます。
ここを301にすると広告が死ぬので、やりません。

## ホスト名の割り当て（案）

| ホスト名 | 向き先 | 中身 |
|---|---|---|
| `onehitter.jp` | one-hitter-lp | LPの入口。**当面は `/mizumawari/` へ301** |
| `lp.onehitter.jp` | one-hitter-lp | LP4本（aircon / aircon-b / mizumawari / nenmatsu） |
| `yoyaku.onehitter.jp` | one-hitter-booking | 予約フォーム |
| `nenmatsu.onehitter.jp` | one-hitter-nenmatsu | 年末LP（いまは301だけのサイト） |
| `survey.onehitter.jp` | one-hitter-survey | ご利用後アンケート |
| `media.onehitter.jp` | （未作成） | 読本・点検。作るときに足す |

CMOの案のとおりです。1点だけ補足します。

> **`nenmatsu.onehitter.jp` は、いまのところ中身がありません。**
> `one-hitter-nenmatsu` は301専用のサイトにしてあるので、このホスト名を当てると
> `onehitter.jp` 配下から `one-hitter-lp.netlify.app/nenmatsu/` へ飛ぶ形になり、
> **新ドメインから旧ドメインへ出ていく**ことになります。
> 年末LPを `lp.onehitter.jp/nenmatsu/` で見せるなら、このホスト名は不要です。
> **どちらにするかCMOに決めてほしい**（推奨：不要。1本に寄せるほうが混乱しません）

## 切り替えの順番

1. ブラウザ担当がムームードメインで `onehitter.jp` を取得
2. **LP担当がNetlifyでDNSゾーンを作り、ネームサーバー4つを掲示板に返す** ← いまここ（下記参照）
3. ブラウザ担当がムームー側にネームサーバーを設定
4. 浸透を確認（`dig NS onehitter.jp`）
5. **各サイトにカスタムドメインを割り当て、HTTPS証明書を発行** ←「外に出す」。CMOに一言入れてから
6. 計測担当と、新ドメインでもGA4の参照元と `?src=` が取れることを確認
7. `docs/LP配信のルール.md` を更新

## 手順1〜3の実績（2026-09-12 確認）

**ドメインは取得済み、ゾーンも作成済み、ネームサーバーの設定も完了しています**
（ブラウザ担当が実施）。契約は 2027/09/30 まで・自動更新ON。
付随して `onehitter.online` と `onehitter.site` も契約済み（未使用）。

| | 値 |
|---|---|
| Netlify DNSゾーンID | `6aa436fdd51fa8a46f46eba5` |
| ネームサーバー | `dns1` 〜 `dns4.p06.nsone.net` |

**ムームー側の設定値とNetlify側の割り当ては一致しています**（Netlify APIで確認）。

### 委任はまだ反映されていません（2026-09-12 時点）

レジストリはまだ `dns01/dns02.muumuu-domain.com` を返します（DNS-over-HTTPSで確認）。
ムームーの注記は「2〜3日かかる場合があります」。**反映されるまでHTTPSは発行できません。**

> この環境には `dig` が無く、権威サーバへ直接引く方法も当てになりません
> （既知のゾーンを対照に置いても SERVFAIL が返るため）。
> **委任状況の確認はDNS-over-HTTPS（`https://dns.google/resolve`）で行うこと。**

### ゾーンに入っているレコード

| 種別 | ホスト名 | 向き先 |
|---|---|---|
| NETLIFY | `dokuhon.onehitter.jp` | `one-hitter-dokuhon` |
| NETLIFY | `tenken.onehitter.jp` | `one-hitter-tenken` |
| NETLIFY | `yoyaku.onehitter.jp` | **`onehitter-yoyaku`** ← 下記参照 |
| TXT | `onehitter.jp` | Google site verification |

**まだ当てていないのは `onehitter.jp`（apex）・`lp.onehitter.jp`・`survey.onehitter.jp` です。**
これがLP担当の担当ぶんで、委任が反映され次第の作業になります。

## 🚨 予約フォームのサイトが2つあります（要対応・LP担当の持ち物ではない）

| サイト | カスタムドメイン | 中身 |
|---|---|---|
| `one-hitter-booking.netlify.app` | なし | 予約フォーム |
| `onehitter-yoyaku.netlify.app` | **`yoyaku.onehitter.jp`** | 予約フォーム |

**2026-09-12 時点で中身は1バイトも違いません**（どちらも 63,073 バイト）。
ですが **`tools/deploy-netlify.py` の `BUNKATSU` は `one-hitter-booking` しか知りません。**

> **次に予約フォームを配信すると、更新されるのは `one-hitter-booking` だけです。**
> **お客様に見えている `yoyaku.onehitter.jp`（＝`onehitter-yoyaku`）は古いまま残ります。**
> これは年末LPで起きた事故（同じページが2サイトにあり、片方だけ配信して金額が食い違った）
> と同じ形です。**中身が同じいまのうちに、1つに寄せてください。**

予約フォームはLP担当の持ち物ではないので、こちらでは直しません。掲示板で回しています。
寄せ方は2通りで、どちらでも構いません。

1. `yoyaku.onehitter.jp` を `one-hitter-booking` に付け替え、`onehitter-yoyaku` を削除する
2. `onehitter-yoyaku` を正とし、`deploy-netlify.py` の `BUNKATSU` の向き先を差し替える

## ⛔ 以前あった問題（解消済み）

**ゾーン作成はブラウザ担当が実施したので、この問題は解消しました。**
（当時：Netlify APIでのDNSゾーン作成が、このスレッドの実行環境で拒否された。
理由名「DNS / Domain / Cert Changes」。なお**読み取りのAPIは通ります**ので、
ゾーンの確認・レコードの確認・サイト一覧の取得はこちらでできます。）

**残るのは手順5（カスタムドメインの割り当てとHTTPS発行）で、これも同じ制約に
当たる可能性があります。** 当たったらまた掲示板で回します。

そもそも `CLAUDE.md` でも**ドメイン設定の変更は「元に戻せない」に分類**されていて、
オーナー確認が要る区分です。ゾーンを作るだけなら実害はありませんが、
**この環境からは実行できません。**

**手順2は、CMOかブラウザ担当の側で実施してください。** やることは1つだけです。

- Netlify（チーム `case-foot-kid`）で `onehitter.jp` のDNSゾーンを作る
- 表示される**ネームサーバー4つ**（`dns1〜dns4.p0x.nsone.net` の形）を掲示板に貼る

ネームサーバーの値さえ掲示板に出れば、**手順4以降はこちらで進められます**
（浸透確認・カスタムドメイン割り当ての準備・計測の確認・文書更新）。
手順5の実行だけは、また同じ制約に当たる可能性があります。

## 決めていないこと

- `media.onehitter.jp` の中身と時期
- `nenmatsu.onehitter.jp` を作るかどうか（上記）
- `onehitter.jp` の301先を `/mizumawari/` でよいか
  （いま成果タグが入っているのは水まわりLPだけなので、これが妥当だと考えています）
