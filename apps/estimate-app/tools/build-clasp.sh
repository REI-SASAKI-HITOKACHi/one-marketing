#!/usr/bin/env bash
# clasp で本番GASへ push できる形にビルドする。
#
#   bash apps/estimate-app/tools/build-clasp.sh
#
# src/ のファイルを「本番のGASファイル名」に付け替えて clasp-build/ に並べる。
# src/ を正としてコピーするだけなので、コードが二重管理にならない。
#
# GASのファイル名は「拡張子を除いた部分」になる。
#   コード.js   → GAS上の「コード」（サーバー）
#   Style.html → GAS上の「Style」（HTML）
set -euo pipefail

cd "$(dirname "$0")/.."

SCRIPT_ID="1YGd7GG__SJU__fBu3TAtqbO3kp6uG3YHz2eUYSg3oU8kDwZF36zz8x4T"
OUT="clasp-build"

rm -rf "$OUT"
mkdir -p "$OUT"

# 本番の appsscript.json をそのまま使う（タイムゾーン・実行者・公開範囲を変えないため）
cp docs/production-snapshot/appsscript.json.txt "$OUT/appsscript.json"

# 既存ファイル（中身を差し替える）
cp src/code.gs          "$OUT/コード.js"
cp src/Index.html       "$OUT/Index.html"
cp src/Style.html       "$OUT/Style.html"
cp src/JavaScript.html  "$OUT/JavaScript.html"

# 新規ファイル
cp src/Invoice.gs       "$OUT/Invoice.js"
cp src/Admin.gs         "$OUT/Admin.js"
cp src/Calc.html        "$OUT/Calc.html"

cat > "$OUT/.clasp.json" <<JSON
{
  "scriptId": "$SCRIPT_ID",
  "rootDir": "."
}
JSON

echo "ビルド先: $(pwd)/$OUT"
echo
ls -1 "$OUT" | sed 's/^/  /'
echo
cat <<'GUIDE'
── 手順（ご自身のPCで実行）───────────────────────────────

0. 事前確認
   - https://script.google.com/home/usersettings で
     「Google Apps Script API」が オン になっていること
   - info.onehitter@gmail.com でログインしていること

1. clasp を入れてログイン
     npm install -g @google/clasp
     clasp login

2. 現状のデプロイIDを控える（URLを変えないために必須）
     cd apps/estimate-app/clasp-build
     clasp deployments
   → "- AKfycb... @12 - 説明" のような行が出る。@HEAD ではない方のIDを控える。

3. push（ソースを差し替える。まだ本番の挙動は変わらない）
     clasp push

4. Apps Scriptエディタで管理者関数を実行
     clasp open
   エディタで次の順に実行：
     adminDiagnose() → adminSetup()
     → adminNormalizeDiscountRules()
     → adminNormalizeMailTemplates()
     → adminNormalizeCellDefinitions()
     → adminDiagnose()（警告が消えたか確認）
     → adminRefreshCache()

5. 受入テストを通してから、既存デプロイを新バージョンに差し替える
     clasp deploy --deploymentId <手順2で控えたID> --description "2026-09 改修版"

   ※ --deploymentId を付けないと新しいデプロイが作られ、
     WebアプリのURLが変わって現場のブックマークが切れる。必ず付けること。

── 切り戻し ──────────────────────────────────────────

  clasp deployments        # バージョン一覧
  clasp deploy --deploymentId <ID> --versionNumber <旧バージョン番号>

  あるいは docs/production-snapshot/ の4ファイルを clasp-build/ に戻して
  clasp push し直す（Invoice.js / Admin.js / Calc.html は削除する）。
GUIDE
