#!/usr/bin/env node
/**
 * 画面から呼べる関数の棚卸しと、管理関数のガードのテスト
 *
 *   node apps/estimate-app/tools/admin-guard-test.js
 *
 * GAS の google.script.run は、名前が `_` で終わらない関数なら画面から何でも呼べる。
 * 見積アプリは「全員・ログイン不要」で公開しているので、公開関数はすべて
 * 「URLを知っている誰でも、所有者の権限で実行できる入口」になる。
 *
 * 2026-09-29、管理関数（admin*）15個がこの入口になっていて、
 * adminSetApiToken('…') で外部APIの合言葉を書き換えられる状態だったのを塞いだ。
 * ここでは次の3つを確かめる。
 *
 *   ① 公開関数は「決まった入口」か「ガード付きの admin*」のどちらかしかない
 *      （新しい公開関数を足してガードを忘れたら、ここで落ちる）
 *   ② ガードが本当に止める：匿名・別アカウントからは合言葉を書き換えられない
 *   ③ 画面（JavaScript.html）から admin* を呼んでいない
 */
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const srcDir = path.join(__dirname, '..', 'src');
// 固定のリストにすると、.gs を足したときに丸ごと検査から外れる。src の .gs を全部読む
const GS_FILES = fs.readdirSync(srcDir).filter(f => f.endsWith('.gs')).sort();

let pass = 0;
const failures = [];

function check(name, actual, expected) {
  const a = JSON.stringify(actual);
  const x = JSON.stringify(expected);
  if (a === x) { pass++; return; }
  failures.push(`${name}\n    期待: ${x}\n    実際: ${a}`);
}

/* ===================== ② ガードが本当に止めるか ===================== */


const OWNER = 'owner@example.com';
let activeUser = '';
let effectiveUser = OWNER;
let scriptProps = {};
let cacheCleared = 0;

function pad(n) { return String(n).padStart(2, '0'); }

const sandbox = {
  console: { log() {}, warn() {}, error() {} },
  JSON, Math, Date, Number, String, Object, Array, isNaN, isFinite, RegExp, Error,
  Session: {
    getActiveUser: () => ({ getEmail: () => activeUser }),
    getEffectiveUser: () => ({ getEmail: () => effectiveUser })
  },
  PropertiesService: {
    getScriptProperties: () => ({
      getProperty: k => (k in scriptProps ? scriptProps[k] : null),
      setProperty: (k, v) => { scriptProps[k] = v; },
      deleteProperty: k => { delete scriptProps[k]; }
    })
  },
  CacheService: {
    getScriptCache: () => ({ get: () => null, put() {}, remove() {}, removeAll() { cacheCleared++; } })
  },
  HtmlService: {
    createHtmlOutputFromFile: name => ({
      getContent: () => fs.readFileSync(path.join(srcDir, name + '.html'), 'utf8')
    })
  },
  Utilities: {
    formatDate(d) { const x = new Date(d); return x.getFullYear() + pad(x.getMonth() + 1) + pad(x.getDate()); }
  }
};

vm.createContext(sandbox);
// 読み込む前からある名前（JSON や Session などテスト側が置いたもの）を控えておく
const injected = new Set(Object.keys(sandbox));
GS_FILES.forEach(f => vm.runInContext(fs.readFileSync(path.join(srcDir, f), 'utf8'), sandbox, { filename: f }));

/* ===================== ① 公開関数の棚卸し ===================== */

console.log('\n■ 画面から呼べる関数（名前が _ で終わらない関数）の棚卸し');

/**
 * 画面から呼ばれることを前提にした入口。ここに無い公開関数は admin* でなければならず、
 * admin* は先頭で requireOwner_() を呼ばなければならない。
 *
 * api* は画面の関数。**いまは合言葉なしで呼べる**（個人情報が読める）。
 * 画面側の合言葉は別途（掲示板 20260929-02-cmo の②）。入ったらここで api* も縛る。
 *
 * 数え方：ソースを正規表現で読むのではなく、実際に読み込んだあとの関数一覧から数える。
 * 1行で書いた関数・名前とかっこの間の空白・字下げ・var 代入など、書き方の違いで
 * 棚卸しから漏れないようにするため（独立レビュー 2026-09-29 の指摘）。
 */
const UI_ENTRY_POINTS = new Set(['doGet', 'doPost', 'include', 'calcEngineTag']);
const isUiApi = name => /^api[A-Z]/.test(name);

const publicFns = Object.keys(sandbox)
  .filter(k => !injected.has(k) && typeof sandbox[k] === 'function' && !k.endsWith('_'))
  .sort();

const adminFns = publicFns.filter(n => /^admin[A-Z]/.test(n));
const unexpected = publicFns.filter(n => !UI_ENTRY_POINTS.has(n) && !isUiApi(n) && !/^admin[A-Z]/.test(n));

/** 関数本体の最初の文。引数の既定値にかっこや波かっこがあっても、本体の先頭を正しく拾う */
function firstStatement(fn) {
  const src = fn.toString();
  let depth = 0;
  let i = src.indexOf('(');
  for (; i < src.length; i++) {
    if (src[i] === '(') depth++;
    else if (src[i] === ')') { depth--; if (depth === 0) break; }
  }
  const bodyStart = src.indexOf('{', i);
  return src.slice(bodyStart + 1).replace(/^\s*(\/\/[^\n]*\n\s*|\/\*[\s\S]*?\*\/\s*)*/, '').split(/[;\n]/)[0].trim();
}

const guardMissing = adminFns.filter(n => firstStatement(sandbox[n]) !== 'requireOwner_()');

check('admin* はすべて本体の先頭で requireOwner_() を呼んでいる', guardMissing, []);
check('入口でも admin* でもない公開関数が無い（足すなら末尾に _ を付けるか、admin* にしてガードを入れる）', unexpected, []);
check('admin* が15個以上見つかっている（数え方が空振りしていない）', adminFns.length >= 15, true);
check('読み込んだ .gs が3つ以上（src の .gs を全部読んでいる）', GS_FILES.length >= 3, true);

// 数え方そのものの自己検査：書き方の違う関数を足した別の環境で、漏れずに拾えるか
(function selfTest() {
  const box = {};
  vm.createContext(box);
  const before = new Set(Object.keys(box));
  vm.runInContext([
    'function adminA() { return 1; }',
    'function adminB () {\n  return 2;\n}',
    '  function adminC(){ return 3; }',
    'var adminD = function () { return 4; };',
    'function adminE(a = f(1), b = {x: 1}) {\n  requireOwner_();\n}',
    'function privateOne_() {}'
  ].join('\n'), box);
  const found = Object.keys(box).filter(k => !before.has(k) && typeof box[k] === 'function' && !k.endsWith('_')).sort();
  check('自己検査：書き方が違っても公開関数を全部拾う', found, ['adminA', 'adminB', 'adminC', 'adminD', 'adminE']);
  check('自己検査：既定値にかっこがあっても本体の先頭を拾う', firstStatement(box.adminE), 'requireOwner_()');
  check('自己検査：ガードの無い関数は先頭が requireOwner_() にならない', firstStatement(box.adminA), 'return 1');
})();

console.log('■ ガードの動作（匿名・別アカウント・所有者）');

// シートや Drive に触る処理は、ガードを通り抜けたときだけ呼ばれる。
// 通り抜けたかどうかを数えるために、中身を空の記録係に差し替える。
let reachedBody = 0;
['getMasterSs_', 'clearContextCache_', 'readSettings_', 'getTemplateSs_'].forEach(n => {
  sandbox[n] = () => { reachedBody++; throw new Error('（テスト）本体に到達'); };
});

const TOKEN = 'x'.repeat(40);

function tryCall(fnName, args) {
  try {
    sandbox[fnName].apply(null, args || []);
    return 'ok';
  } catch (e) {
    return String(e.message || e);
  }
}

const DENIED = 'この操作は、スクリプトの所有者が Apps Script エディタから実行するものです。';

// --- 匿名（画面経由・ログインなし）---
activeUser = '';
effectiveUser = OWNER;
scriptProps = {};

check('匿名：adminSetApiToken は止まる', tryCall('adminSetApiToken', [TOKEN]), DENIED);
check('匿名：合言葉は書き込まれていない', scriptProps, {});

scriptProps = { API_TOKEN: 'original-token-value-000000000000000' };
check('匿名：adminClearApiToken は止まる', tryCall('adminClearApiToken'), DENIED);
check('匿名：既存の合言葉は消えていない', scriptProps.API_TOKEN, 'original-token-value-000000000000000');
check('匿名：adminCheckApiToken（有無を覗く）も止まる', tryCall('adminCheckApiToken'), DENIED);

// 全 admin* が、本体に一歩も入らずに止まること
reachedBody = 0;
const adminNames = Object.keys(sandbox).filter(n => /^admin[A-Z]/.test(n) && typeof sandbox[n] === 'function');
const leaked = adminNames.filter(n => tryCall(n, [TOKEN]) !== DENIED);
check('匿名：admin* はすべて止まる', leaked, []);
check('匿名：admin* の本体（シート・キャッシュ）に一度も到達していない', reachedBody, 0);

// --- 別の Google アカウント（画面経由・ログインあり）---
activeUser = 'someone-else@example.com';
effectiveUser = OWNER;
scriptProps = {};
check('別アカウント：adminSetApiToken は止まる', tryCall('adminSetApiToken', [TOKEN]), DENIED);
check('別アカウント：合言葉は書き込まれていない', scriptProps, {});

// --- 実行ユーザーが取れない（権限の持ち主も空）---
activeUser = '';
effectiveUser = '';
check('両方とも空：止まる（fail closed）', tryCall('adminSetApiToken', [TOKEN]), DENIED);

// --- 所有者（エディタから実行）---
activeUser = OWNER;
effectiveUser = OWNER;
scriptProps = {};
check('所有者：adminSetApiToken は通る', tryCall('adminSetApiToken', [TOKEN]), 'ok');
check('所有者：合言葉が設定される', scriptProps.API_TOKEN, TOKEN);
check('所有者：adminCheckApiToken は通る', tryCall('adminCheckApiToken'), 'ok');
check('所有者：adminClearApiToken は通る', tryCall('adminClearApiToken'), 'ok');
check('所有者：合言葉が消える', 'API_TOKEN' in scriptProps, false);

// 所有者のときはガードを通り抜けて本体まで行く（ガードが全部を止めてしまっていない）
reachedBody = 0;
tryCall('adminRefreshCache');
check('所有者：ガードの先の本体まで到達する', reachedBody > 0, true);

// 大文字小文字や前後の空白で一致させない（メールは Session が正規化して返す前提）
activeUser = OWNER.toUpperCase();
effectiveUser = OWNER;
check('大文字違いは別人として止める', tryCall('adminSetApiToken', [TOKEN]) === DENIED, true);

/* ===================== ③ 画面から admin* を呼んでいない ===================== */

console.log('■ 画面（src/*.html）から admin* を呼んでいない');

// JavaScript.html だけでなく、画面に配る .html を全部見る。
// run['adminX'] のような書き方も拾えるよう、呼び出しの形ではなく名前の出現で見る
const clientAdminRefs = [];
fs.readdirSync(srcDir).filter(f => f.endsWith('.html')).forEach(f => {
  const text = fs.readFileSync(path.join(srcDir, f), 'utf8');
  (text.match(/\badmin[A-Z][A-Za-z0-9]*/g) || []).forEach(m => clientAdminRefs.push(f + ':' + m));
});
check('画面のコード（src/*.html）に admin* の名前が出てこない', clientAdminRefs, []);

/* ===================== ④ リンク先は https:// だけ ===================== */

console.log('■ 画面のリンク先は https:// だけ（javascript: を踏ませない）');

// esc() は href="javascript:…" を防げない。所有者が画面を開いているときに踏まされると、
// 所有者の権限で admin* まで動いてしまうので、リンク先は safeUrl() を必ず通す。
const jsHtml = fs.readFileSync(path.join(srcDir, 'JavaScript.html'), 'utf8');
const rawHref = [];
fs.readdirSync(srcDir).filter(f => f.endsWith('.html')).forEach(f => {
  const text = fs.readFileSync(path.join(srcDir, f), 'utf8');
  (text.match(/href="' \+ (?!safeUrl\()[A-Za-z_]+\(/g) || []).forEach(m => rawHref.push(f + ':' + m));
});
check('href に埋め込むのは safeUrl() を通したものだけ', rawHref, []);

const fnSrc = (jsHtml.match(/function safeUrlRaw\([\s\S]*?\n  \}/) || [''])[0];
check('safeUrlRaw が見つかる', fnSrc.length > 0, true);
const urlBox = {};
vm.createContext(urlBox);
vm.runInContext(fnSrc, urlBox);
const su = urlBox.safeUrlRaw;
check('https:// は通す', su('https://drive.google.com/file/d/abc/view'), 'https://drive.google.com/file/d/abc/view');
check('大文字の HTTPS:// も通す', su('HTTPS://example.com'), 'HTTPS://example.com');
check('javascript: は止める', su('javascript:google.script.run.adminSetApiToken(1)'), '#');
check('前に空白を入れた javascript: も止める', su('  javascript:alert(1)'), '#');
check('大文字混じりの JavaScript: も止める', su('JaVaScRiPt:alert(1)'), '#');
check('data: は止める', su('data:text/html,<script>1</script>'), '#');
check('http:// は止める（Drive も Gmail も https）', su('http://example.com'), '#');
check('空・null は # にする', [su(''), su(null), su(undefined)], ['#', '#', '#']);

/* ===================== 結果 ===================== */

console.log('');
console.log('  公開関数 ' + publicFns.length + ' 個（うち admin* ' + adminFns.length + ' 個はガード済み）／読んだ .gs：' + GS_FILES.join(', '));
console.log('');
if (failures.length === 0) {
  console.log(`✅ 全 ${pass} ケース合格`);
  process.exit(0);
} else {
  failures.forEach(f => console.log('❌ ' + f));
  console.log(`\n${pass} 合格 / ${failures.length} 失敗`);
  process.exit(1);
}
