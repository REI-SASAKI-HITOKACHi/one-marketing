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
const GS_FILES = ['code.gs', 'Invoice.gs', 'Admin.gs'];

let pass = 0;
const failures = [];

function check(name, actual, expected) {
  const a = JSON.stringify(actual);
  const x = JSON.stringify(expected);
  if (a === x) { pass++; return; }
  failures.push(`${name}\n    期待: ${x}\n    実際: ${a}`);
}

/* ===================== ① 公開関数の棚卸し ===================== */

console.log('\n■ 画面から呼べる関数（名前が _ で終わらない関数）の棚卸し');

/**
 * 画面から呼ばれることを前提にした入口。ここに無い公開関数は admin* でなければならず、
 * admin* は先頭で requireOwner_() を呼ばなければならない。
 *
 * api* は画面の関数。**いまは合言葉なしで呼べる**（個人情報が読める）。
 * 画面側の合言葉は別途（掲示板 20260929-02-cmo の②）。入ったらここで api* も縛る。
 */
const UI_ENTRY_POINTS = new Set(['doGet', 'doPost', 'include', 'calcEngineTag']);
const isUiApi = name => /^api[A-Z]/.test(name);

const publicFns = [];
const guardMissing = [];
const unexpected = [];

GS_FILES.forEach(file => {
  const src = fs.readFileSync(path.join(srcDir, file), 'utf8');
  const re = /^function ([A-Za-z0-9_]+)\([^)]*\)\s*\{\s*\n([^\n]*)/gm;
  let m;
  while ((m = re.exec(src))) {
    const name = m[1];
    const firstLine = m[2].trim();
    if (name.endsWith('_')) continue; // 非公開。画面から呼べない
    publicFns.push(file + ':' + name);

    if (UI_ENTRY_POINTS.has(name) || isUiApi(name)) continue;

    if (/^admin[A-Z]/.test(name)) {
      if (firstLine !== 'requireOwner_();') guardMissing.push(file + ':' + name);
      continue;
    }
    unexpected.push(file + ':' + name);
  }
});

check('admin* はすべて先頭で requireOwner_() を呼んでいる', guardMissing, []);
check('入口でも admin* でもない公開関数が無い（足すなら末尾に _ を付けるか、ガードを入れる）', unexpected, []);
check('admin* が1つ以上見つかっている（正規表現が空振りしていない）',
  publicFns.filter(f => /:admin[A-Z]/.test(f)).length >= 15, true);

/* ===================== ② ガードが本当に止めるか ===================== */

console.log('■ ガードの動作（匿名・別アカウント・所有者）');

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
GS_FILES.forEach(f => vm.runInContext(fs.readFileSync(path.join(srcDir, f), 'utf8'), sandbox, { filename: f }));

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

console.log('■ 画面（JavaScript.html）から admin* を呼んでいない');

const clientJs = fs.readFileSync(path.join(srcDir, 'JavaScript.html'), 'utf8');
const clientAdminCalls = (clientJs.match(/\badmin[A-Z][A-Za-z0-9]*\s*\(/g) || []);
check('画面のコードに admin* の呼び出しが無い', clientAdminCalls, []);

/* ===================== 結果 ===================== */

console.log('');
console.log('  公開関数 ' + publicFns.length + ' 個（うち admin* ' + adminNames.length + ' 個はガード済み）');
console.log('');
if (failures.length === 0) {
  console.log(`✅ 全 ${pass} ケース合格`);
  process.exit(0);
} else {
  failures.forEach(f => console.log('❌ ' + f));
  console.log(`\n${pass} 合格 / ${failures.length} 失敗`);
  process.exit(1);
}
