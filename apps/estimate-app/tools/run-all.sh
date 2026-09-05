#!/usr/bin/env bash
# 見積アプリの全チェックをまとめて実行する。
#
#   bash apps/estimate-app/tools/run-all.sh
#
# デプロイ前と、コードを触ったあとに必ず通すこと。
set -uo pipefail

cd "$(dirname "$0")/.."

fail=0
step() {
  printf '\n\033[1m── %s\033[0m\n' "$1"
}

step "1. 構文チェック"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

for f in src/*.gs; do
  cp "$f" "$tmp/$(basename "${f%.gs}").js"
done
for f in src/Calc.html src/JavaScript.html; do
  sed -e 's|<script[^>]*>||' -e 's|</script>||' "$f" > "$tmp/$(basename "${f%.html}").js"
done

for f in "$tmp"/*.js; do
  if node --check "$f" >/dev/null 2>&1; then
    printf '  ✓ %s\n' "$(basename "$f")"
  else
    printf '  ✗ %s\n' "$(basename "$f")"
    node --check "$f"
    fail=1
  fi
done

step "2. 参照チェック（未定義の関数・孤立したハンドラ）"
if node tools/wiring-check.js; then :; else fail=1; fi

step "3. 計算エンジン"
if node tools/calc-test.js | tail -1; then :; else fail=1; fi

step "4. 見積レコードの保存→復元"
if node tools/record-roundtrip-test.js | tail -1; then :; else fail=1; fi

step "5. 請求書（請求日・請求額・セル定義）"
if node tools/invoice-test.js | tail -1; then :; else fail=1; fi

step "6. 本番マスタの実データ読み込み"
if node tools/live-master-test.js | tail -1; then :; else fail=1; fi

step "7. シートAPI呼び出し回数（旧コードとの比較）"
if node tools/api-call-benchmark.js | tail -8; then :; else fail=1; fi

step "8. マスタTSVがコードと一致しているか"
before=$(md5sum master/*.tsv 2>/dev/null | md5sum)
node tools/gen-master-tsv.js >/dev/null
after=$(md5sum master/*.tsv 2>/dev/null | md5sum)
if [ "$before" = "$after" ]; then
  printf '  ✓ master/*.tsv は最新\n'
else
  printf '  ✗ master/*.tsv がコード定義とずれていたため再生成した。差分をコミットすること\n'
  fail=1
fi

printf '\n'
if [ "$fail" -eq 0 ]; then
  printf '\033[32m✅ すべて通過\033[0m\n\n'
else
  printf '\033[31m❌ 失敗あり\033[0m\n\n'
fi
exit "$fail"
