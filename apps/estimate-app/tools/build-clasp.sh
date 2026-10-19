#!/usr/bin/env bash
# clasp で本番GASへ push できる形にビルドする。
#
#   bash apps/estimate-app/tools/build-clasp.sh
#
# 本番は **5ファイル構成**（2026-10-12 に browser が実測）：
#   appsscript.json / コード.js / Index.html / JavaScript.html / Style.html
# 「コード」には code.gs + Invoice.gs + Admin.gs が連結され、計算エンジン（Calc）も埋め込まれている。
# つまり clasp で push するものは、**貼り付け用の deploy-paste/ と同じ中身**。
#
# 以前は src/ の7ファイル（Invoice.js・Admin.js・Calc.html を新規に作る形）で push する作りだった。
# 本番のコードと二重になる／関数が欠けるので壊れる。2026-10-19 にこの形をやめた。
# src/ を直接 push しないこと。
set -euo pipefail

cd "$(dirname "$0")/.."

SCRIPT_ID="1YGd7GG__SJU__fBu3TAtqbO3kp6uG3YHz2eUYSg3oU8kDwZF36zz8x4T"
OUT="clasp-build"

# 貼り付け用バンドルを最新にしてから、それを写す（src とずれた古いバンドルを push しない）
bash tools/build-paste-bundle.sh >/dev/null

rm -rf "$OUT"
mkdir -p "$OUT"

# 本番の appsscript.json（タイムゾーン・実行者・公開範囲を変えないため）。
# 本番から変わっていないかは、手順の最初に clasp pull で確かめる（下のガイド）
cp docs/production-snapshot/appsscript.json.txt "$OUT/appsscript.json"

# GASのファイル名は「拡張子を除いた部分」になる（コード.js → 「コード」、Style.html → 「Style」）
cp "deploy-paste/コード.gs.txt"      "$OUT/コード.js"
cp deploy-paste/Index.html.txt       "$OUT/Index.html"
cp deploy-paste/Style.html.txt       "$OUT/Style.html"
cp deploy-paste/JavaScript.html.txt  "$OUT/JavaScript.html"

cat > "$OUT/.clasp.json" <<JSON
{
  "scriptId": "$SCRIPT_ID",
  "rootDir": "."
}
JSON

echo "ビルド先: $(pwd)/$OUT（5ファイル。deploy-paste/ と同じ中身）"
echo
ls -1 "$OUT" | sed 's/^/  /'
echo
cat <<'GUIDE'
── 手順（嶺さんのPC。ブラウザ担当が代行してもよい）─────────────────

0. 事前確認
   - https://script.google.com/home/usersettings で「Google Apps Script API」がオン
   - info.onehitter@gmail.com でログイン済み（clasp login）

1. 現状の控えを取る（戻し先）
     mkdir /tmp/gas-backup && cd /tmp/gas-backup
     clasp clone 1YGd7GG__SJU__fBu3TAtqbO3kp6uG3YHz2eUYSg3oU8kDwZF36zz8x4T
   - 取れた5ファイルを保管する。appsscript.json が clasp-build/ のものと同じか diff する
   - `clasp deployments` で **稼働中のデプロイを全部**控える（2026-10-12 時点で5本。数えて確認）
   - 今のバージョン番号を控える（2026-10-19 時点は @9）

2. push（本番のコードが差し替わる。まだ公開中の画面は旧バージョンのまま）
     cd apps/estimate-app/clasp-build
     clasp push -f

3. 新しいバージョンを1つ作る
     clasp version "説明（コミットのハッシュを書く）"
   → 出た番号（例：10）を控える

4. **稼働中の全本数**を、その番号に差し替える（1本でも旧版に残さない）
     clasp deploy --deploymentId <ID> --versionNumber 10 --description "説明"
   を、手順1で控えた全IDについて繰り返す。**--deploymentId を付けないと新規デプロイになりURLが変わる。**
   終わったら `clasp deployments` で全本数が同じ @番号 か確認する。

5. 必要なら、エディタで管理関数（adminSetUiPin / adminRefreshCache など）を実行
   （関数のプルダウンが切り替わらないときは、嶺さんが手で選んで ▶）

── 切り戻し ──────────────────────────────────────────
  clasp deploy --deploymentId <ID> --versionNumber <手順1で控えた旧バージョン番号>
  を全本数に。**2026-09-29 のセキュリティ修正（@8）より前には戻さない。**
  （ファイルごと戻すなら、手順1で取った控えを clasp-build/ に置いて clasp push -f し、手順3〜4をやり直す）

── やってはいけないこと ─────────────────────────────
  - src/ のファイルを直接 push する（Invoice.js・Admin.js・Calc.html を新規に作り、コードが二重になる）
  - `clasp deploy` を --deploymentId なしで実行する（URLが変わる）
  - 「API 実行可能」としてデプロイする（`clasp run` 用。管理関数が画面外から呼べる設定になる。README 参照）
GUIDE
