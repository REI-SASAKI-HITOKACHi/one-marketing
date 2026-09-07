# LPの配信ルール（全スレッド共通・必読）

制定 2026-09-07 ／ **同じ事故が2回起きたので明文化します。**

## 何が起きたか

`one-hitter-lp.netlify.app` に対し、**3つのスレッドがそれぞれ別のブランチから配信**していました。
各ブランチは共通の土台を持っていないため、**後から配信した側が、前の修正を消していました。**

| 日付 | 誰が | 何をして | 何が消えたか |
|---|---|---|---|
| 09/06 | CMO | ライト固定・src/cid記録・案Bの404修正を配信 | — |
| 09/06 | 計測 | GA4を入れて配信（CMOの修正が入る前の土台から） | **ライト固定・src/cid記録が消えた** |
| 09/07 | CMO | 計測のツールを取り込み、全部入りで再配信 | 復旧 |

**原因は担当分けではなく、配信の土台を決めていなかったことです。**
「どのファイルを誰が触るか」は決めましたが、「本番へ出すときに何をベースにするか」が抜けていました。

## ルール

### 1. 配信の前に、必ず他スレッドのブランチを取り込む

```bash
git fetch origin claude/one-hitter-cmo-strategy-5qk4ux
git fetch origin claude/lp-outline-presentation-8fahl3
git fetch origin claude/measurement-ga4-calltracking
```

**自分のブランチにしか無い変更で本番を上書きしないこと。**
取り込みが難しければ、配信せずに他スレッドへ回してください。

### 2. 配信後は、必ず実物を取得して確認する

ビルドが通っただけでは確認になりません。**公開URLを取得して、消えていないことを確かめます。**

```bash
python3 - <<'PY'
import urllib.request
B="https://one-hitter-lp.netlify.app"
for n in ["aircon","aircon-b","mizumawari"]:
    s=urllib.request.urlopen(f"{B}/{n}/", timeout=30).read().decode('utf-8','replace')
    print(n,
          "ライト固定", 'color-scheme: light' in s,
          "src記録", 'name="src"' in s,
          "ダーク残", 'prefers-color-scheme' in s)
PY
```

**この3つは、どのスレッドが配信しても維持されていなければなりません。**

- `color-scheme: light`：ライト固定（オーナー判断。ダーク配色は使わない）
- `name="src"` と `name="cid"`：流入元の記録（これが無いと広告の成果が測れない）
- `prefers-color-scheme` が**無い**こと：ダーク配色が復活していない証拠

### 3. `tools/build-site.py` の `PAGES` から `nenmatsu` を消さないこと

**これも2回起きています。** LPスレッドと計測スレッドの双方で、
`nenmatsu`（年末LP）のエントリが落ちた状態のビルド設定が作られました。
年末LPはCMOスレッドの管轄ですが、**ビルド設定は共通ファイル**です。
自分が担当していないページも消さないでください。

### 4. サイトと担当

| サイト | 中身 | 配信してよいスレッド |
|---|---|---|
| `one-hitter-lp.netlify.app` | aircon / aircon-b / mizumawari | LP・計測・CMO（上のルールを守ること） |
| `one-hitter-nenmatsu.netlify.app` | nenmatsu | CMO |
| `one-hitter-survey.netlify.app` | survey | CMO |

**ZIPでの配信はサイト全体を置き換えます。** 一部だけを上げると、
`robots.txt`・`favicon.ico`・`_headers`・`_redirects`・`thanks.html` が消えます。
必ず一式を含めてください。

独自ドメイン `lp.one-hitter.jp` が通った時点で、**1サイトに統合する方針**です（オーナー判断）。
統合後はこの分散も解消します。

## 現在の状態（2026-09-07 確認済み）

4本すべてで、ライト固定・src/cid記録・計測の土台が入っており、
`thanks.html` も3本とも200を返しています。
