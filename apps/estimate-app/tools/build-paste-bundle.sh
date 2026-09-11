#!/usr/bin/env bash
# 貼り付け配布用のバンドルを作る。
#
#   bash apps/estimate-app/tools/build-paste-bundle.sh
#
# 本番GASの「既存4ファイルを上書きするだけ」で済む形に固める。
# 新規ファイルを作らせないのが目的。ファイル作成は名前の付け間違いが起きやすく、
# 実際に引継ぎ資料の style / Style の食い違いで踏みかけた。
#
#   コード      ← src/code.gs + src/Invoice.gs + src/Admin.gs を連結し、
#                 さらに src/Calc.html を CALC_ENGINE_SOURCE に埋め込む
#   Index      ← src/Index.html（そのまま）
#   Style      ← src/Style.html（そのまま）
#   JavaScript ← src/JavaScript.html（そのまま）
#
# 出力は deploy-paste/ に置き、リポジトリにコミットする。
# GitHubの画面から直接コピーできるようにするため（ローカルにcloneしなくていい）。
set -euo pipefail

cd "$(dirname "$0")/.."
OUT="deploy-paste"
mkdir -p "$OUT"

# --- Calc.html にテンプレートリテラルを壊す文字が無いか確認 ---
if grep -q '`' src/Calc.html || grep -q '\${' src/Calc.html; then
  echo "エラー: src/Calc.html にバッククォートまたは \${ が含まれています。" >&2
  echo "       テンプレートリテラルに埋め込めません。埋め込み方を見直してください。" >&2
  exit 1
fi

# --- コード：3つの.gsを連結し、計算エンジンを埋め込む ---
python3 - <<'PY'
import io, re

calc = io.open('src/Calc.html', encoding='utf-8').read()
code = io.open('src/code.gs', encoding='utf-8').read()
invoice = io.open('src/Invoice.gs', encoding='utf-8').read()
admin = io.open('src/Admin.gs', encoding='utf-8').read()

# バックスラッシュだけエスケープすればテンプレートリテラルに入る
# （バッククォートと ${ が無いことは呼び出し側で確認済み）
embedded = calc.replace('\\', '\\\\')

marker = "var CALC_ENGINE_SOURCE = '';"
assert marker in code, "CALC_ENGINE_SOURCE の宣言が見つかりません"
code = code.replace(marker, 'var CALC_ENGINE_SOURCE = `' + embedded + '`;', 1)

banner = """/**
 * 見積作成Webアプリ（サーバー側 一括版）
 *
 * これは配布用に自動生成したファイルです。直接編集しないでください。
 * 元ファイル：src/code.gs + src/Invoice.gs + src/Admin.gs + src/Calc.html
 * 生成       ：tools/build-paste-bundle.sh
 *
 * GASは全ての .gs ファイルが同じスコープを共有するため、
 * 分割しても連結しても動作は同じです。デプロイ時に作るファイル数を
 * 減らすために1つにまとめています。
 */

"""

def section(title, body):
    line = '=' * 74
    return ('\n\n/* ' + line + '\n * ' + title + '\n * ' + line + ' */\n\n') + body

out = banner + code + section('Invoice.gs', invoice) + section('Admin.gs', admin)
io.open('deploy-paste/コード.gs.txt', 'w', encoding='utf-8').write(out)
print('  コード.gs.txt        %7d文字' % len(out))
PY

cp src/Index.html      "$OUT/Index.html.txt"
cp src/Style.html      "$OUT/Style.html.txt"
cp src/JavaScript.html "$OUT/JavaScript.html.txt"

for f in Index Style JavaScript; do
  printf '  %-20s %7d文字\n' "$f.html.txt" "$(wc -m < "$OUT/$f.html.txt")"
done

# --- 検証：生成した コード が構文として通り、計算エンジンを取り出せるか ---
node --check <(sed 's|^|;|;s|^;||' "$OUT/コード.gs.txt") 2>/dev/null || {
  tmp=$(mktemp /tmp/bundle-XXXX.js); cp "$OUT/コード.gs.txt" "$tmp"
  node --check "$tmp" || { echo "エラー: 生成した コード.gs.txt が構文エラーです" >&2; exit 1; }
  rm -f "$tmp"
}

node -e '
const fs=require("fs"), vm=require("vm");
const src=fs.readFileSync("deploy-paste/コード.gs.txt","utf8");
const sandbox={console:{log(){},warn(){},error(){}},JSON,Math,Date,Number,String,Object,Array,isNaN,isFinite,RegExp};
vm.createContext(sandbox);
vm.runInContext(src,sandbox,{filename:"bundle"});
const tag=vm.runInContext("CALC_ENGINE_SOURCE",sandbox);
if(!tag||tag.indexOf("CalcEngine")<0) throw new Error("計算エンジンが埋め込まれていません");
const engine=sandbox.getCalcEngine_();
const r=engine.calculate(
  {workDate:"2026-05-20",details:[{menuId:"M1",qty:2}]},
  {taxRate:0.1,busySurcharge:3300,busySurchargeUnit:"数量ごと",autoDiscountEnabled:false,
   menuMap:{M1:{name:"テスト",menuType:"メイン",unitPrice:10000,unitPriceRaw:10000,taxType:"課税",
                busyTarget:true,busySurchargeRaw:3300,discountTarget:true,multipleDiscountTarget:false}},
   discountRules:[{ruleType:"繁忙期",target:"全体",startMonth:5,endMonth:7,value:3300,priority:10}]});
// 繁忙期加算 3,300 は税込なので課税対象には 3,000 で載る（2台ぶんで 6,000）
if(r.grandTotal!==28600) throw new Error("埋め込みエンジンの計算結果が想定と違う: "+r.grandTotal);
if(r.busyAmount!==6000) throw new Error("繁忙期加算が税抜に戻っていない: "+r.busyAmount);
console.log("  ✓ 埋め込んだ計算エンジンがサーバー側で動作（20,000+6,000+税=28,600）");
'

echo
echo "貼り付け先（すべて既存ファイルの上書き。新規作成なし）"
echo "  コード     ← deploy-paste/コード.gs.txt"
echo "  Index      ← deploy-paste/Index.html.txt"
echo "  Style      ← deploy-paste/Style.html.txt"
echo "  JavaScript ← deploy-paste/JavaScript.html.txt"
