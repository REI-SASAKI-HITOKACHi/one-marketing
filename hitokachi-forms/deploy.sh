#!/usr/bin/env bash
#
# Apps Script プロジェクトを作って、コードを上げて、ウェブアプリとして公開する。
#
#   bash deploy.sh
#
# 事前に 1 回だけ必要:
#   npm install -g @google/clasp
#   clasp login          ← ブラウザで Google アカウントを承認する
#
# このスクリプトが終わったら、あと 2 つだけ手作業が残る。
#   1. エディタで Drive API（v3）を追加する
#   2. エディタで setup() を実行して権限を承認する
# 最後に案内を出すので、そのとおりに進めればよい。

set -euo pipefail
cd "$(dirname "$0")"

TITLE="${1:-帳票自動作成システム}"

say() { printf '\n\033[1m%s\033[0m\n' "$*"; }
die() { printf '\n\033[31m%s\033[0m\n' "$*" >&2; exit 1; }

# ---- 事前確認 ----

command -v clasp >/dev/null 2>&1 \
  || die 'clasp が見つかりません。先に  npm install -g @google/clasp  を実行してください。'

# clasp 3.x は show-authorized-user、2.x は login --status。どちらでも通るようにする。
clasp show-authorized-user >/dev/null 2>&1 || clasp login --status >/dev/null 2>&1 \
  || die 'Google アカウントにログインしていません。先に  clasp login  を実行してください。'

[ -f src/appsscript.json ] || die 'src/appsscript.json がありません。リポジトリのルートで実行してください。'

# ---- プロジェクトを作る（すでにあれば作らない） ----

if [ -f .clasp.json ]; then
  say "既存の .clasp.json を使います。"
else
  say "Apps Script プロジェクトを作ります: ${TITLE}"
  clasp create --type webapp --title "${TITLE}" --rootDir src
fi

# clasp 3.x は scriptExtensions / htmlExtensions を自分で書くので、拡張子の設定は要らない。
# 2.x で作られた古い .clasp.json のために rootDir だけ念のため揃える。
node -e '
  const fs = require("fs");
  const c = JSON.parse(fs.readFileSync(".clasp.json", "utf8"));
  c.rootDir = "src";
  if (!c.scriptExtensions) c.fileExtension = "gs";   // 2.x 向け
  fs.writeFileSync(".clasp.json", JSON.stringify(c, null, 2) + "\n");
  console.log("scriptId:", c.scriptId);
'

# ---- コードを上げる ----

say "コードを上げています…"
clasp push --force

# ---- ウェブアプリとして公開する ----
#
# 実行するユーザー・アクセスできるユーザーは src/appsscript.json の webapp 設定に従う。
#   executeAs: USER_ACCESSING   … 誰が作成したかをログに残すため
#   access:    ANYONE           … URL だけでは入れない。利用者シートで絞る

say "ウェブアプリとして公開しています…"
clasp deploy --description "初回デプロイ" >/dev/null

SCRIPT_ID=$(node -e 'console.log(JSON.parse(require("fs").readFileSync(".clasp.json","utf8")).scriptId)')

cat <<EOS

────────────────────────────────────────────────
 ここまで完了しました
────────────────────────────────────────────────

  エディタ: https://script.google.com/d/${SCRIPT_ID}/edit

 残りは 2 つだけです。

 1. Drive API を追加する
      エディタ左の「サービス」の ＋ → 「Drive API」→ バージョン v3 → 追加
      ※ これを忘れると PDF が作れません

 2. setup() を実行する
      上の関数の一覧から setup を選んで実行
      初回は権限の承認が出ます。自作スクリプトなので
      「詳細」→「安全ではないページに移動」で進んで構いません

      実行ログに出た URL が設定スプレッドシートです

 そのあと「デプロイ」→「デプロイを管理」からウェブアプリの URL を確認できます。
 URL を知っているだけでは入れません。設定スプレッドシートの「利用者」シートに
 載っているアドレスだけが使えます。

 コードを直したときは  clasp push --force  だけで反映されます。
 シートの構成を変えたときは、あわせて setup() をもう一度実行してください
 （入力済みのデータは壊しません）。

EOS
