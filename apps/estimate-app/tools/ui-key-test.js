#!/usr/bin/env node
/**
 * 画面の鍵（人ごと）のテスト
 *
 *   node apps/estimate-app/tools/ui-key-test.js
 *
 * 見積アプリは「全員・ログイン不要」で公開している。画面の関数に鍵が無いと、
 * URLを知っている人は誰でも過去見積のお客様の氏名・住所・電話番号を読めた。
 * 2026-09-29、画面から呼べる関数（api*）すべてに人ごとの鍵を付けた。
 *
 * ここで確かめること
 *   ① 画面から呼べる api* は、画面が実際に使っている12個だけ（使っていない入口を残さない）
 *   ② どの入口も、先頭で requireUiKey_(key) を呼び、本体（api*_）へ引数を1つもずらさず渡す
 *   ③ 鍵が無い・違う・止めた人の鍵 → 本体に一歩も入らずに止まる。締め出しは無い
 *   ④ 正しい鍵 → 本体に届き、ログには「鍵:名前」で残る（所有者の名前で埋めない）
 *   ⑤ サーバー内部（doPost など）は入口ではなく本体を呼ぶ
 *   ⑥ 管理関数で鍵を発行・止める・一覧できる（一覧に鍵の値は出さない）
 *   ⑦ 画面：リンクから鍵を正しく拾い、すべての呼び出しで鍵を渡す
 */
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const srcDir = path.join(__dirname, '..', 'src');
const GS_FILES = fs.readdirSync(srcDir).filter(f => f.endsWith('.gs')).sort();
const clientJs = fs.readFileSync(path.join(srcDir, 'JavaScript.html'), 'utf8');

let pass = 0;
const failures = [];

function check(name, actual, expected) {
  const a = JSON.stringify(actual);
  const x = JSON.stringify(expected);
  if (a === x) { pass++; return; }
  failures.push(`${name}\n    期待: ${x}\n    実際: ${a}`);
}

/* ===================== 読み込み ===================== */

const OWNER = 'owner@example.com';
let activeUser = '';
let effectiveUser = OWNER;
let scriptProps = {};
const logs = [];
let serviceUrl = 'https://script.google.com/macros/s/TESTDEPLOY/exec';

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
      setProperty: (k, v) => { scriptProps[k] = String(v); },
      deleteProperty: k => { delete scriptProps[k]; }
    })
  },
  ScriptApp: { getService: () => ({ getUrl: () => serviceUrl }) },
  Utilities: {
    // 大文字で返る環境でも、発行した鍵が照合で弾かれないこと（小文字にそろえること）を確かめる
    getUuid: (() => { let n = 0; return () => { n++; return 'AAAAAAAA-BBBB-4CCC-8DDD-' + String(n).padStart(12, '0'); }; })(),
    formatDate: () => '20260929'
  },
  HtmlService: {
    createHtmlOutputFromFile: name => ({
      getContent: () => fs.readFileSync(path.join(srcDir, name + '.html'), 'utf8')
    })
  }
};

vm.createContext(sandbox);
const injected = new Set(Object.keys(sandbox));
GS_FILES.forEach(f => vm.runInContext(fs.readFileSync(path.join(srcDir, f), 'utf8'), sandbox, { filename: f }));
const RUNTIME = vm.runInContext('RUNTIME', sandbox);

// ログは記録だけ（シートに書かない）
sandbox.flushLogs_ = () => { logs.push.apply(logs, RUNTIME.logs.splice(0)); };

/* ===================== ① 入口の棚卸し ===================== */

console.log('\n■ 画面から呼べる api* は、画面が使っている12個だけ');

const publicApis = Object.keys(sandbox)
  .filter(k => !injected.has(k) && typeof sandbox[k] === 'function' && /^api[A-Z]/.test(k) && !k.endsWith('_'))
  .sort();

const clientApis = [...new Set([...clientJs.matchAll(/\.(api[A-Za-z]+)\(/g)].map(m => m[1]))].sort();

check('画面が呼んでいる api* は12個', clientApis.length, 12);
check('公開 api* ＝ 画面が呼んでいる api*（使っていない入口が無い）', publicApis, clientApis);
check('使っていなかった apiInit / apiCalculateEstimate / apiCreateEstimate は無い',
  ['apiInit', 'apiCalculateEstimate', 'apiCreateEstimate'].filter(n => typeof sandbox[n] === 'function'), []);
check('どの入口にも本体（api*_）がある',
  publicApis.filter(n => typeof sandbox[n + '_'] !== 'function'), []);

/* ===================== ② 入口の形 ===================== */

console.log('■ 入口は先頭で鍵を確かめ、本体へ引数をずらさず渡す');

function paramsOf(fn) {
  if (typeof fn !== 'function') return null;
  const m = fn.toString().match(/^function\s*[A-Za-z0-9_$]*\s*\(([^)]*)\)/);
  return m ? m[1].split(',').map(x => x.trim()).filter(Boolean) : null;
}

function bodyOf(fn) {
  const src = fn.toString();
  return src.slice(src.indexOf('{') + 1, src.lastIndexOf('}')).trim();
}

const shapeProblems = [];
publicApis.forEach(n => {
  const params = paramsOf(sandbox[n]);
  const implParams = paramsOf(sandbox[n + '_']);
  if (!implParams) { shapeProblems.push(n + '：本体（' + n + '_）が無い'); return; }
  if (!params || params[0] !== 'key') { shapeProblems.push(n + '：第1引数が key ではない'); return; }
  const rest = params.slice(1);
  if (JSON.stringify(rest) !== JSON.stringify(implParams)) {
    shapeProblems.push(n + '：入口の引数 ' + rest.join(',') + ' と本体の引数 ' + implParams.join(',') + ' が合わない');
  }
  const expected = 'requireUiKey_(key);\n  return ' + n + '_(' + rest.join(', ') + ');';
  if (bodyOf(sandbox[n]) !== expected) shapeProblems.push(n + '：本体が「鍵を確かめて本体を呼ぶ」だけになっていない');
});
check('12個の入口すべてが同じ形（鍵を確かめる → 本体へそのまま渡す）', shapeProblems, []);

/* ===================== ③④ 動き ===================== */

console.log('■ 鍵が無い・違う → 本体に入らない／正しい鍵 → 本体に届く');

// 本体を「呼ばれた引数を記録するだけ」に差し替える（シートや Drive に触らない）
const reached = [];
publicApis.forEach(n => {
  sandbox[n + '_'] = function () {
    reached.push({ name: n + '_', args: Array.prototype.slice.call(arguments), who: RUNTIME.uiKeyOwner || '' });
    return { ok: true };
  };
});

function callUi(name, key, args) {
  reached.length = 0;
  RUNTIME.uiKeyOwner = '';
  try {
    sandbox[name].apply(null, [key].concat(args || []));
    return 'ok';
  } catch (e) {
    return String(e.message || e);
  }
}

const KAZUMA = 'a'.repeat(64);
const OWNERKEY = 'b'.repeat(64);
const WRONG = 'c'.repeat(64);
const MARK = '[UI_KEY] ';
const NONE_MARK = '[UI_KEY_NONE] ';
/** 止まったか（鍵が合わない、または鍵が未発行） */
const stopped = r => r.indexOf(MARK) === 0 || r.indexOf(NONE_MARK) === 0;

// --- 鍵が1つも発行されていない（fail closed）---
scriptProps = {};
activeUser = '';
const leakedWhenNoKeys = publicApis.filter(n => !stopped(callUi(n, KAZUMA, ['x', 1])) || reached.length);
check('鍵が未発行：12個とも止まり、本体に入らない', leakedWhenNoKeys, []);
check('鍵が未発行のときは「未発行」の目印で返す（画面はスマホの記憶を消さない）',
  callUi('apiSearchEstimates', KAZUMA, [{}]).indexOf(NONE_MARK), 0);

// 壊れたプロパティ（JSONでない）でも開かない
scriptProps = { UI_KEYS: '{壊れた' };
check('鍵の設定が壊れていても止まる', stopped(callUi('apiSearchEstimates', KAZUMA, [{}])), true);

// --- 鍵が発行されている ---
scriptProps = { UI_KEYS: JSON.stringify({ '和真': KAZUMA, 'オーナー': OWNERKEY }) };

check('鍵なし（空）→ 止まる', callUi('apiSearchEstimates', '', [{}]).indexOf(MARK), 0);
check('鍵なし（undefined）→ 止まる', callUi('apiSearchEstimates', undefined, [{}]).indexOf(MARK), 0);
check('違う鍵 → 止まる', callUi('apiSearchEstimates', WRONG, [{}]).indexOf(MARK), 0);
check('1文字だけ違う鍵 → 止まる', callUi('apiSearchEstimates', 'a'.repeat(63) + 'c', [{}]).indexOf(MARK), 0);
check('長さが違う鍵 → 止まる', callUi('apiSearchEstimates', 'a'.repeat(65), [{}]).indexOf(MARK), 0);
check('止まったとき本体に入っていない', reached.length, 0);

// 鍵の値が空で登録されていても、空の鍵では通さない
scriptProps = { UI_KEYS: JSON.stringify({ '空': '' }) };
check('空の鍵が登録されていても、空の鍵では通らない', stopped(callUi('apiSearchEstimates', '', [{}])), true);

// 値が 64桁の英数字でないものは、照合の対象にしない（手で壊した設定から推測できる鍵が生まれない）
const weakValues = [
  ['数値', 1, '1'], ['真偽値', true, 'true'], ['オブジェクト', { a: 1 }, '[object Object]'],
  ['配列', ['x'], 'x'], ['短い文字列', '1', '1'], ['大文字', 'A'.repeat(64), 'A'.repeat(64)],
  ['null', null, 'null']
];
weakValues.forEach(([label, value, guess]) => {
  scriptProps = { UI_KEYS: JSON.stringify({ '壊れ': value }) };
  check('値が' + label + 'の鍵は照合しない（' + JSON.stringify(guess) + ' で通らない）',
    stopped(callUi('apiSearchEstimates', guess, [{}])), true);
});

// 画面から文字列以外が来ても鍵として扱わない（古い画面が payload を先頭に送ってきた場合など）
scriptProps = { UI_KEYS: JSON.stringify({ '和真': KAZUMA }) };
check('オブジェクトを鍵として渡されても通らない', stopped(callUi('apiSearchEstimates', { a: 1 }, [{}])), true);
check('配列を鍵として渡されても通らない', stopped(callUi('apiSearchEstimates', [KAZUMA], [{}])), true);

// 手で __proto__ という名前を書き込まれても、照合がおかしくならない
// （JSON.parse は自分のプロパティとして持つので、ふつうの鍵と同じに扱われる。プロトタイプは汚れない）
scriptProps = { UI_KEYS: '{"__proto__": "' + WRONG + '", "和真": "' + OWNERKEY + '"}' };
check('__proto__ という名前があっても、正規の鍵は通る', callUi('apiSearchEstimates', OWNERKEY, [{}]), 'ok');
check('__proto__ があっても、関係ない鍵では通らない', stopped(callUi('apiSearchEstimates', KAZUMA, [{}])), true);
check('プロトタイプが汚れていない', Object.prototype.hasOwnProperty.call(Object.prototype, 'aaaa') || ({}).length !== undefined, false);

scriptProps = { UI_KEYS: JSON.stringify({ '和真': KAZUMA, 'オーナー': OWNERKEY }) };

// 正しい鍵：引数がずれずに本体へ届く
const argCases = {
  apiBootstrap: [],
  apiSaveEstimate: [{ requestId: 'r1', 顧客名: 'テスト' }],
  apiBuildDocuments: ['20260929-01', 7],
  apiCreateRepresentativeDraft: ['20260929-01'],
  apiSearchEstimates: [{ customerName: '山田' }],
  apiGetEstimateDetail: ['20260929-01'],
  apiLoadEstimateForClone: ['20260929-01'],
  apiStartInvoice: ['20260929-01'],
  apiCalculateInvoice: [{ estimateId: '20260929-01' }],
  apiSaveInvoice: [{ requestId: 'r2', estimateId: '20260929-01' }],
  apiBuildInvoiceDocuments: ['20260929-01', 3],
  apiGetInvoiceDetail: ['20260929-01']
};
check('引数の見本が12個ぶんそろっている', Object.keys(argCases).sort(), publicApis);

const misrouted = [];
publicApis.forEach(n => {
  const args = argCases[n] || [];
  const r = callUi(n, KAZUMA, args);
  if (r !== 'ok' || reached.length !== 1 || reached[0].name !== n + '_'
      || JSON.stringify(reached[0].args) !== JSON.stringify(args)) {
    misrouted.push(n + ' → ' + JSON.stringify({ r, reached }));
  }
});
check('正しい鍵：12個とも本体に届き、引数がそのまま渡る（鍵は本体に渡らない）', misrouted, []);

callUi('apiSearchEstimates', OWNERKEY, [{}]);
check('鍵の持ち主が分かる（オーナーの鍵）', reached[0] && reached[0].who, 'オーナー');
callUi('apiSearchEstimates', KAZUMA, [{}]);
check('鍵の持ち主が分かる（和真さんの鍵）', reached[0] && reached[0].who, '和真');

// 締め出しは無い：何度間違えても、正しい鍵は通る
for (let i = 0; i < 50; i++) callUi('apiSearchEstimates', WRONG, [{}]);
check('50回間違えられても、正しい鍵は通る（締め出しで妨害されない）', callUi('apiSearchEstimates', KAZUMA, [{}]), 'ok');

// --- ログ：誰が操作したかを正直に書く ---
console.log('■ 操作ログの「ユーザー」欄は正直に書く');

RUNTIME.uiKeyOwner = '和真';
check('鍵で入った → 「鍵:和真」', sandbox.getLogUser_(), '鍵:和真');
RUNTIME.uiKeyOwner = '';
activeUser = '';
effectiveUser = OWNER;
check('画面経由で利用者が分からない → 所有者の名前で埋めない', sandbox.getLogUser_(), '（画面経由・利用者不明）');
activeUser = OWNER;
check('エディタから実行 → そのメール', sandbox.getLogUser_(), OWNER);
activeUser = '';
RUNTIME.apiCaller = '外部API';
check('外部API（doPost）→ 「外部API」', sandbox.getLogUser_(), '外部API');
RUNTIME.apiCaller = '';

// 鍵が合わないたびにシートへ1行書くと、鍵なしの誰でもシートを際限なく伸ばせ、
// ロックなしの追記なので正規の操作ログを上書きで消せる。失敗はシートに書かない
logs.length = 0;
RUNTIME.logs.length = 0;
for (let i = 0; i < 5; i++) callUi('apiSearchEstimates', WRONG, [{}]);
sandbox.flushLogs_();
check('鍵が合わなくても、シートのログには書かない（書き込みで妨害されない）', logs.length + RUNTIME.logs.length, 0);
scriptProps = {};
callUi('apiSearchEstimates', WRONG, [{}]);
sandbox.flushLogs_();
check('鍵が未発行でも、シートのログには書かない', logs.length + RUNTIME.logs.length, 0);
scriptProps = { UI_KEYS: JSON.stringify({ '和真': KAZUMA, 'オーナー': OWNERKEY }) };

/* ===================== ⑤ サーバー内部は本体を呼ぶ ===================== */

console.log('■ サーバー内部（doPost など）は入口ではなく本体を呼ぶ');

// 入口の定義そのもの（「function apiX(key, …) {」の行と、その中の return apiX_(…)）以外で、
// 公開 api* を呼んでいる箇所が無いこと
const internalCalls = [];
GS_FILES.forEach(f => {
  const lines = fs.readFileSync(path.join(srcDir, f), 'utf8').split('\n');
  lines.forEach((line, i) => {
    if (/^\s*(\/\/|\*|\/\*)/.test(line)) return;
    if (/^function api[A-Za-z]+\(/.test(line)) return;
    const m = line.match(/\b(api[A-Z][A-Za-z]+)\(/);
    if (m && publicApis.includes(m[1])) internalCalls.push(f + ':' + (i + 1) + '  ' + line.trim());
  });
});
check('サーバー内部から入口（鍵が要るほう）を呼んでいない', internalCalls, []);

/* ===================== ⑥ 鍵の発行・停止・一覧 ===================== */

console.log('■ 鍵の発行・停止・一覧（所有者がエディタから）');

activeUser = OWNER;
effectiveUser = OWNER;
scriptProps = {};

const EXEC = 'https://script.google.com/macros/s/KAZUMA_DEPLOY/exec';
const issued = sandbox.adminAddUiKey('和真', EXEC);
const stored1 = JSON.parse(scriptProps.UI_KEYS || '{}');
check('発行すると保存される', typeof stored1['和真'], 'string');
check('鍵は64桁の英数字（小文字にそろえる。大文字だと照合で弾かれて全員締め出される）',
  /^[0-9a-f]{64}$/.test(stored1['和真']), true);
check('専用リンクは渡したURL＋外部ブラウザで開く指定＋鍵',
  issued.indexOf(EXEC + '?openExternalBrowser=1#key=' + stored1['和真']) >= 0, true);
check('URLの形が違えば断る', (() => { try { sandbox.adminAddUiKey('和真', 'https://evil.example.com/exec'); return 'ok'; } catch (e) { return 'error'; } })(), 'error');
check('URLの形が違って断ったとき、鍵は作り直していない（前の鍵が生きている）',
  JSON.parse(scriptProps.UI_KEYS)['和真'], stored1['和真']);

// URLを渡さず、エディタから実行して /dev しか取れないとき：リンクは作らず、付け足す部分だけ出す
serviceUrl = 'https://script.google.com/macros/s/TESTDEPLOY/dev';
const devIssued = sandbox.adminAddUiKey('試し');
const devKey = JSON.parse(scriptProps.UI_KEYS)['試し'];
check('/dev しか取れないときは /dev のリンクを出さない', devIssued.indexOf('/dev') < 0, true);
check('そのときは「いつものURLに付け足す部分」を出す', devIssued.indexOf('?openExternalBrowser=1#key=' + devKey) >= 0, true);
serviceUrl = 'https://script.google.com/macros/s/TESTDEPLOY/exec';
sandbox.adminRevokeUiKey('試し');
check('案内文に「リンクをもう一度タップ」が入っている', issued.indexOf('もう一度タップ') >= 0, true);
check('発行した鍵で入口が通る', callUi('apiSearchEstimates', stored1['和真'], [{}]), 'ok');

sandbox.adminAddUiKey('和真', EXEC);
const stored2 = JSON.parse(scriptProps.UI_KEYS);
check('同じ名前でもう一度 → 鍵が作り直される', stored2['和真'] !== stored1['和真'], true);
check('作り直したら前の鍵は使えない', callUi('apiSearchEstimates', stored1['和真'], [{}]).indexOf(MARK), 0);

sandbox.adminAddUiKey('オーナー', EXEC);
const listed = sandbox.adminListUiKeys();
check('一覧に名前が出る', listed.indexOf('和真') >= 0 && listed.indexOf('オーナー') >= 0, true);
const stored3 = JSON.parse(scriptProps.UI_KEYS);
check('一覧に鍵の値は出ない', Object.values(stored3).some(v => listed.indexOf(v) >= 0), false);

sandbox.adminRevokeUiKey('和真');
check('止めた人の鍵は使えない', callUi('apiSearchEstimates', stored3['和真'], [{}]).indexOf(MARK), 0);
check('ほかの人の鍵は使える', callUi('apiSearchEstimates', stored3['オーナー'], [{}]), 'ok');

sandbox.adminRevokeUiKey('オーナー');
check('全員止めたら誰も使えない（fail closed）', stopped(callUi('apiSearchEstimates', stored3['オーナー'], [{}])), true);
check('全員止めたときは「未発行」の目印（スマホの記憶は消させない）', callUi('apiSearchEstimates', stored3['オーナー'], [{}]).indexOf(NONE_MARK), 0);

check('名前なしの発行は断る', (() => { try { sandbox.adminAddUiKey(''); return 'ok'; } catch (e) { return 'error'; } })(), 'error');
check('__proto__ という名前は断る（保存されないのに「発行した」と出てしまうため）',
  (() => { try { sandbox.adminAddUiKey('__proto__', EXEC); return 'ok'; } catch (e) { return 'error'; } })(), 'error');

// 設定が壊れているときに発行すると、空扱いにして書き戻し、ほかの人の鍵を黙って消してしまう。止めること
scriptProps = { UI_KEYS: '{壊れた' };
check('設定が壊れていたら発行は止まる', (() => { try { sandbox.adminAddUiKey('和真', EXEC); return 'ok'; } catch (e) { return 'error'; } })(), 'error');
check('壊れた設定を上書きしていない（ほかの人の鍵を消さない）', scriptProps.UI_KEYS, '{壊れた');
check('設定が壊れていたら停止も止まる', (() => { try { sandbox.adminRevokeUiKey('和真'); return 'ok'; } catch (e) { return 'error'; } })(), 'error');

scriptProps = { UI_KEYS: JSON.stringify({ '和真': KAZUMA, '壊れ': 1 }) };
check('一覧で、形の壊れた鍵を知らせる', sandbox.adminListUiKeys().indexOf('壊れ') >= 0 && sandbox.adminListUiKeys().indexOf('使えない') >= 0, true);

// 匿名では発行も一覧もできない（admin-guard-test でも全 admin* を見ているが、鍵まわりは念のためここでも）
activeUser = '';
scriptProps = {};
check('匿名：鍵を発行できない', (() => { try { sandbox.adminAddUiKey('攻撃者'); return 'ok'; } catch (e) { return 'denied'; } })(), 'denied');
check('匿名：鍵は保存されていない', scriptProps.UI_KEYS, undefined);

/* ===================== ⑦ 画面側 ===================== */

console.log('■ 画面：リンクから鍵を拾い、すべての呼び出しで鍵を渡す');

const parseSrc = (clientJs.match(/function parseUiKey\([\s\S]*?\n  \}/) || [''])[0];
check('parseUiKey が見つかる', parseSrc.length > 0, true);
const cbox = {};
vm.createContext(cbox);
vm.runInContext(parseSrc, cbox);
const parse = cbox.parseUiKey;
check('key=… を拾う', parse('key=' + KAZUMA), KAZUMA);
check('# 付きでも拾う', parse('#key=abc123'), 'abc123');
check('ほかの値と並んでいても拾う', parse('foo=1&key=abc123&bar=2'), 'abc123');
check('英数字以外は拾わない（スクリプトを混ぜさせない）', parse('key=<script>'), '');
check('空なら空', [parse(''), parse(null), parse(undefined)], ['', '', '']);
check('似た名前（monkey=…）を鍵と取り違えない', parse('monkey=abc'), '');

const callsWithoutKey = [...clientJs.matchAll(/\.(api[A-Za-z]+)\(([^)]*)/g)]
  .filter(m => !/^\s*uiKey\(/.test(m[2]))
  .map(m => m[1]);
check('画面の12個の呼び出しすべてが先頭で uiKey() を渡す', callsWithoutKey, []);

const msgSrc = (clientJs.match(/function message\(err\)[\s\S]*?\n  \}/) || [''])[0];
const noneBranch = (msgSrc.match(/UI_KEY_NONE_MARK\) >= 0\) \{[\s\S]*?\n    \}/) || [''])[0];
const wrongBranch = (msgSrc.match(/UI_KEY_MARK\) >= 0\) \{[\s\S]*?\n    \}/) || [''])[0];
check('鍵が合わないと返ってきたら、記憶を消して案内を出す',
  /forgetUiKey\(\)/.test(wrongBranch) && /showKeyRequired\('wrong'\)/.test(wrongBranch), true);
check('鍵が未発行と返ってきたら、記憶は消さずに案内だけ出す',
  !/forgetUiKey\(\)/.test(noneBranch) && /showKeyRequired\('none'\)/.test(noneBranch), true);
check('未発行の判定を、不一致の判定より先に行う（目印が似ているため）',
  msgSrc.indexOf('UI_KEY_NONE_MARK) >= 0') >= 0 && msgSrc.indexOf('UI_KEY_NONE_MARK) >= 0') < msgSrc.indexOf('UI_KEY_MARK) >= 0'), true);
check('画面とサーバーで目印の文字列が同じ（不一致）',
  (clientJs.match(/var UI_KEY_MARK = '([^']*)'/) || [])[1], vm.runInContext('UI_KEY_ERROR_MARK', sandbox));
check('画面とサーバーで目印の文字列が同じ（未発行）',
  (clientJs.match(/var UI_KEY_NONE_MARK = '([^']*)'/) || [])[1], vm.runInContext('UI_KEY_NONE_MARK', sandbox));
// 関数の中身だけを見る（ファイル全体で探すと、別の場所の同じ書き方に反応して見逃す）
const showKeySrc = (clientJs.match(/function showKeyRequired\([^)]*\) \{[\s\S]*?\n  \}/) || [''])[0];
check('showKeyRequired が見つかる', showKeySrc.length > 0, true);
check('案内を出したら画面の中身を隠す（そのまま操作させない）',
  /byId\('app'\)/.test(showKeySrc) && /classList\.add\('hidden'\)/.test(showKeySrc), true);
check('鍵を受け取ったらアドレス欄から消す（履歴に残さない）',
  /storeUiKey\(fromLink\);[\s\S]{0,120}google\.script\.history\.replace/.test(clientJs), true);

/* ===================== ⑧ 鍵の貼り付け欄（ホーム画面アイコン向けの手当て） ===================== */

console.log('■ 鍵の貼り付け欄：リンクの丸ごと／鍵だけ、どちらでも取り込める');

// ホーム画面に追加したアイコンから開く画面は Safari と記憶の置き場所が別なので、
// リンクを開き直しても鍵が届かないことがある。そのとき、LINEのリンクを丸ごと貼り付けて入れ直せる。
const textSrc = (clientJs.match(/function parseUiKeyFromText\([\s\S]*?\n  \}/) || [''])[0];
check('parseUiKeyFromText が見つかる', textSrc.length > 0, true);
const tbox = {};
vm.createContext(tbox);
vm.runInContext(textSrc, tbox);
const fromText = tbox.parseUiKeyFromText;
const K64 = 'abcdef0123456789'.repeat(4);
check('専用リンクの丸ごと', fromText('https://script.google.com/macros/s/AKfy/exec?openExternalBrowser=1#key=' + K64), K64);
check('鍵だけ', fromText(K64), K64);
check('前後の空白・改行つき', fromText('  \n' + K64 + '\n '), K64);
check('LINE が途中で折り返して改行・空白を入れても取れる',
  fromText('https://script.google.com/macros/s/AKfy/exec?openExternalBrowser=1#key=' + K64.slice(0, 30) + '\n' + K64.slice(30)), K64);
check('大文字で貼られても小文字にそろえる（サーバーは小文字だけ受け付ける）', fromText('#key=' + K64.toUpperCase()), K64);
check('途中までしか無い → 取れない', fromText('https://x/exec#key=' + K64.slice(0, 60)), '');
check('65桁以上（余計な文字が続く）→ 取れない', fromText('https://x/exec#key=' + K64 + 'a'), '');
check('key= が無いURLだけ → 取れない', fromText('https://script.google.com/macros/s/AKfy/exec'), '');
check('16進以外の文字が混じる → 取れない', fromText('#key=' + 'g'.repeat(64)), '');
check('空・null・undefined → 取れない', [fromText(''), fromText(null), fromText(undefined)], ['', '', '']);
check('64桁の別の値を鍵と取り違えない（monkey=…）', fromText('https://x/exec#monkey=' + K64), '');

const indexHtml = fs.readFileSync(path.join(srcDir, 'Index.html'), 'utf8');
check('貼り付け欄の部品が Index.html にある',
  ['keyPaste', 'keyPasteInput', 'keyPasteError'].filter(id => indexHtml.indexOf('id="' + id + '"') < 0), []);
check('「保存して開く」ボタンが save-key を呼ぶ', /data-action="save-key"/.test(indexHtml), true);
check('save-key のハンドラがある', /action === 'save-key'\) saveKeyFromPaste\(\)/.test(clientJs), true);
check('貼り付け欄は最初は隠れている',
  /<section id="keyPaste" class="card hidden"/.test(indexHtml), true);
check('貼り付け欄は #app の外にある（#app を隠しても見える）',
  indexHtml.indexOf('id="keyPaste"') < indexHtml.indexOf('id="app"'), true);

const showSrc = (clientJs.match(/function showKeyRequired\([^)]*\) \{[\s\S]*?\n  \}/) || [''])[0];
check('鍵が合わないときは貼り付け欄を出し、未発行のときは出さない',
  /kind === 'none'\) hideKeyPaste\(\); else showKeyPaste\(\)/.test(showSrc), true);

const saveSrc = (clientJs.match(/function saveKeyFromPaste\([\s\S]*?\n  \}/) || [''])[0];
check('貼り付けから読み取れなければ、保存せずに案内を出す',
  /if \(!key\)[\s\S]*?return;[\s\S]*?storeUiKey\(key\)/.test(saveSrc), true);
check('保存したら初期表示を読み直す', /onUiKeyResolved\(key\)/.test(saveSrc), true);

/* ===================== 結果 ===================== */

console.log('');
if (failures.length === 0) {
  console.log(`✅ 全 ${pass} ケース合格`);
  process.exit(0);
} else {
  failures.forEach(f => console.log('❌ ' + f));
  console.log(`\n${pass} 合格 / ${failures.length} 失敗`);
  process.exit(1);
}
