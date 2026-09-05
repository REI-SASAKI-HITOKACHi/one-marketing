#!/usr/bin/env node
/**
 * 参照の静的チェック
 *
 *   node apps/estimate-app/tools/wiring-check.js
 *
 * GASは実行するまで未定義関数に気づけないので、デプロイ前に機械的に見る。
 *   - サーバー側で呼んでいる内部関数（末尾 _）がすべて定義されているか
 *   - 同名関数を2箇所で定義していないか（GASは全ファイルが同じスコープ）
 *   - クライアントが呼ぶ api* がサーバーに実在するか
 *   - data-action にハンドラが揃っているか
 *   - byId() が参照するidが Index.html にあるか
 */
'use strict';

const fs = require('fs');
const path = require('path');

const srcDir = path.join(__dirname, '..', 'src');
const read = f => fs.readFileSync(path.join(srcDir, f), 'utf8');

const serverFiles = fs.readdirSync(srcDir).filter(f => f.endsWith('.gs'));
const server = serverFiles.map(read).join('\n');
const client = read('JavaScript.html');
const markup = read('Index.html');

const GAS_GLOBALS = new Set(['SpreadsheetApp', 'DriveApp', 'GmailApp', 'HtmlService', 'CacheService',
  'LockService', 'Utilities', 'Session', 'ScriptApp', 'UrlFetchApp', 'MimeType', 'PropertiesService']);

const JS_KEYWORDS = new Set(['if', 'for', 'while', 'switch', 'catch', 'return', 'function', 'typeof',
  'Number', 'String', 'Boolean', 'Object', 'Array', 'Set', 'Map', 'JSON', 'Math', 'Date',
  'setTimeout', 'clearTimeout', 'parseInt', 'parseFloat', 'require', 'google', 'CalcEngine',
  'document', 'window', 'console', 'RegExp']);

// 実行時に生成されるid（請求書フォームなど）は Index.html に存在しない
const RUNTIME_IDS = new Set(['invoiceFields', 'invoiceSummary', 'invoiceSaveBtn', 'invoiceResult']);
const RUNTIME_ID_PREFIX = 'inv_';

const problems = [];
const oks = [];

function report(label, bad, formatter) {
  if (bad.length === 0) { oks.push(label); return; }
  problems.push(label + '\n' + bad.map(b => '      - ' + (formatter ? formatter(b) : b)).join('\n'));
}

/* --- サーバー側 --- */

const defined = new Set([...server.matchAll(/function\s+([A-Za-z0-9_]+)\s*\(/g)].map(m => m[1]));
const called = new Set([...server.matchAll(/\b([A-Za-z0-9_]*_)\s*\(/g)].map(m => m[1]));

// コメント中の言及を拾わないよう、コメント行を除いた本文で再確認する
const codeOnly = server.split('\n')
  .filter(l => !/^\s*(\/\/|\*|\/\*)/.test(l))
  .join('\n');
const calledInCode = new Set([...codeOnly.matchAll(/\b([A-Za-z0-9_]*_)\s*\(/g)].map(m => m[1]));

report('サーバー：未定義の内部関数を呼んでいる',
  [...calledInCode].filter(c => !defined.has(c) && !GAS_GLOBALS.has(c)).sort());

report('サーバー：同名関数を複数箇所で定義している',
  [...defined].filter(f =>
    (server.match(new RegExp('function\\s+' + f.replace(/[$.]/g, '\\$&') + '\\s*\\(', 'g')) || []).length > 1
  ).sort());

/* --- クライアント側 --- */

const clientDefined = new Set([...client.matchAll(/function\s+([A-Za-z0-9_]+)\s*\(/g)].map(m => m[1]));
const clientCalled = new Set([...client.matchAll(/(?<![.\w])([a-zA-Z_][A-Za-z0-9_]*)\s*\(/g)].map(m => m[1]));

const clientCodeOnly = client.split('\n')
  .filter(l => !/^\s*(\/\/|\*|\/\*)/.test(l))
  .join('\n');
const clientCalledInCode = new Set(
  [...clientCodeOnly.matchAll(/(?<![.\w])([a-zA-Z_][A-Za-z0-9_]*)\s*\(/g)].map(m => m[1]));

report('クライアント：未定義の関数を呼んでいる',
  [...clientCalledInCode].filter(c => !clientDefined.has(c) && !JS_KEYWORDS.has(c)).sort());

const serverApis = new Set([...client.matchAll(/\.(api[A-Za-z]+)\(/g)].map(m => m[1]));
report('クライアントが呼ぶAPIがサーバーに存在しない',
  [...serverApis].filter(a => !defined.has(a)).sort());

/* --- data-action --- */

const actionsDeclared = new Set([
  ...[...markup.matchAll(/data-action="([a-z-]+)"/g)].map(m => m[1]),
  ...[...client.matchAll(/data-action="([a-z-]+)"/g)].map(m => m[1]),
  ...[...client.matchAll(/'data-action':\s*'([a-z-]+)'/g)].map(m => m[1])
]);
const actionsHandled = new Set([...client.matchAll(/action === '([a-z-]+)'/g)].map(m => m[1]));

report('data-action にハンドラがない', [...actionsDeclared].filter(a => !actionsHandled.has(a)).sort());
report('ハンドラはあるが使われていない data-action', [...actionsHandled].filter(a => !actionsDeclared.has(a)).sort());

/* --- id --- */

const markupIds = new Set([...markup.matchAll(/id="([A-Za-z0-9_]+)"/g)].map(m => m[1]));
const usedIds = new Set([
  ...[...client.matchAll(/byId\('([A-Za-z0-9_]+)'\)/g)].map(m => m[1]),
  ...[...client.matchAll(/setVal\('([A-Za-z0-9_]+)'/g)].map(m => m[1]),
  ...[...client.matchAll(/val\('([A-Za-z0-9_]+)'\)/g)].map(m => m[1])
]);

report('存在しないidを参照している',
  [...usedIds].filter(id =>
    !markupIds.has(id) && !RUNTIME_IDS.has(id) && !id.startsWith(RUNTIME_ID_PREFIX)).sort());

/* --- Calc.html の公開API --- */

const calc = read('Calc.html');
const exposed = new Set([...calc.slice(calc.lastIndexOf('return {')).matchAll(/^\s{4}([a-zA-Z]+):/gm)].map(m => m[1]));
const calcUsed = new Set([...client.matchAll(/CalcEngine\.([a-zA-Z]+)/g)].map(m => m[1]));
report('CalcEngine の未公開メンバーを使っている', [...calcUsed].filter(m => !exposed.has(m)).sort());

/* --- 結果 --- */

oks.forEach(o => console.log('  ✓ ' + o.replace(/^(サーバー|クライアント)：/, '$1：')));

if (problems.length === 0) {
  console.log('  ✓ 参照チェック 問題なし（サーバー関数 ' + defined.size
    + ' / クライアント関数 ' + clientDefined.size + ' / API ' + serverApis.size + '）');
  process.exit(0);
}

console.log('');
problems.forEach(p => console.log('  ✗ ' + p));
process.exit(1);
