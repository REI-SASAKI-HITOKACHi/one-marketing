#!/usr/bin/env node
/**
 * 外部API（doPost）のテスト
 *
 *   node apps/estimate-app/tools/dopost-test.js
 *
 * いちばん確かめたいのは「合言葉が無いと何も起きないこと」。
 * /exec のURLは知っていれば誰でも叩けるので、認証が抜けた瞬間に
 * 見積・請求が外から作られる。ここが緩むと金と個人情報に直結する。
 */
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const srcDir = path.join(__dirname, '..', 'src');

function pad(n, len) { return String(n).padStart(len || 2, '0'); }

/* 呼ばれた api* を記録するだけのスタブ。実際のシートには触らない */
const calls = [];
let scriptProps = {};

const sandbox = {
  console: { log() {}, warn() {}, error() {} },
  JSON, Math, Date, Number, String, Object, Array, isNaN, isFinite, RegExp,

  PropertiesService: {
    getScriptProperties: () => ({
      getProperty: k => (k in scriptProps ? scriptProps[k] : null),
      setProperty: (k, v) => { scriptProps[k] = v; },
      deleteProperty: k => { delete scriptProps[k]; }
    })
  },
  ContentService: {
    MimeType: { JSON: 'application/json' },
    createTextOutput: text => ({
      _text: text,
      setMimeType() { return this; },
      getContent() { return this._text; }
    })
  },
  HtmlService: {
    createHtmlOutputFromFile: name => ({
      getContent: () => fs.readFileSync(path.join(srcDir, name + '.html'), 'utf8')
    })
  },
  Utilities: {
    formatDate(date, tz, pattern) {
      const d = date instanceof Date ? date : new Date(date);
      return pattern
        .replace('yyyy', d.getFullYear()).replace('MM', pad(d.getMonth() + 1))
        .replace('dd', pad(d.getDate())).replace('HH', pad(d.getHours()))
        .replace('mm', pad(d.getMinutes())).replace('ss', pad(d.getSeconds()));
    }
  },
  Session: {
    getActiveUser: () => ({ getEmail: () => 'test@example.com' }),
    getEffectiveUser: () => ({ getEmail: () => 'test@example.com' })
  }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(path.join(srcDir, 'code.gs'), 'utf8'), sandbox, { filename: 'code.gs' });
vm.runInContext(fs.readFileSync(path.join(srcDir, 'Invoice.gs'), 'utf8'), sandbox, { filename: 'Invoice.gs' });

/* 本物の api* はシートに触るので、呼ばれた事実だけ記録する版に差し替える */
['apiGetInvoiceDetail', 'apiGetEstimateDetail', 'apiStartInvoice',
 'apiSaveInvoice', 'apiBuildInvoiceDocuments',
 'apiSaveEstimate', 'apiBuildDocuments'].forEach(name => {
  sandbox[name] = function () {
    calls.push({ name, args: Array.prototype.slice.call(arguments) });
    return { ok: true, calledWith: Array.prototype.slice.call(arguments) };
  };
});
sandbox.queueLog_ = () => {};
sandbox.flushLogs_ = () => {};

const TOKEN = 'x'.repeat(40);

function post(body, raw) {
  calls.length = 0;
  const e = { postData: { contents: raw !== undefined ? raw : JSON.stringify(body) } };
  return JSON.parse(sandbox.doPost(e).getContent());
}

let pass = 0;
const failures = [];

function check(name, actual, expected) {
  const a = JSON.stringify(actual);
  const x = JSON.stringify(expected);
  if (a === x) { pass++; return; }
  failures.push(`${name}\n    期待: ${x}\n    実際: ${a}`);
}

console.log('\n■ 合言葉が未設定のとき（fail closed）');
scriptProps = {};

check('合言葉なしで ping → 拒否',
  post({ action: 'ping' }).ok, false);
check('正しそうな合言葉を送っても拒否（そもそも設定が無い）',
  post({ token: TOKEN, action: 'ping' }).ok, false);
check('書き込み系も拒否（請求）',
  post({ token: TOKEN, action: 'saveInvoice', payload: {} }).ok, false);
check('書き込み系も拒否（見積）',
  post({ token: TOKEN, action: 'saveEstimate', payload: {} }).ok, false);
check('帳票生成も拒否',
  post({ token: TOKEN, action: 'buildEstimate', estimateId: 'E1' }).ok, false);
check('拒否のとき api* を1つも呼んでいない', calls.length, 0);
check('理由を細かく返さない',
  post({ action: 'ping' }).error, '認証に失敗しました。');

console.log('■ 合言葉が設定されているとき');
scriptProps = { API_SHARED_TOKEN: TOKEN };

check('合言葉なし → 拒否', post({ action: 'ping' }).ok, false);
check('違う合言葉 → 拒否', post({ token: 'y'.repeat(40), action: 'ping' }).ok, false);
check('長さ違い → 拒否', post({ token: 'x'.repeat(39), action: 'ping' }).ok, false);
check('間違いのとき api* を呼ばない', calls.length, 0);

check('正しい合言葉で ping → 通る', post({ token: TOKEN, action: 'ping' }).ok, true);
check('ping は副作用なし', calls.length, 0);

console.log('■ action の振り分け');

check('getInvoice が apiGetInvoiceDetail を呼ぶ', (() => {
  post({ token: TOKEN, action: 'getInvoice', invoiceId: '20260915-01' });
  return [calls[0].name, calls[0].args[0]];
})(), ['apiGetInvoiceDetail', '20260915-01']);

check('getEstimate が apiGetEstimateDetail を呼ぶ', (() => {
  post({ token: TOKEN, action: 'getEstimate', estimateId: '20260915-01' });
  return calls[0].name;
})(), 'apiGetEstimateDetail');

check('startInvoice が apiStartInvoice を呼ぶ', (() => {
  post({ token: TOKEN, action: 'startInvoice', estimateId: 'E1' });
  return calls[0].name;
})(), 'apiStartInvoice');

check('saveInvoice が payload をそのまま渡す', (() => {
  post({ token: TOKEN, action: 'saveInvoice', payload: { 顧客名: 'テスト', requestId: 'r9' } });
  return [calls[0].name, calls[0].args[0]];
})(), ['apiSaveInvoice', { 顧客名: 'テスト', requestId: 'r9' }]);

check('buildInvoice が請求番号と行番号を渡す', (() => {
  post({ token: TOKEN, action: 'buildInvoice', invoiceId: '20260915-01', rowNumber: 5 });
  return [calls[0].name, calls[0].args[0], calls[0].args[1]];
})(), ['apiBuildInvoiceDocuments', '20260915-01', 5]);

check('saveEstimate が payload をそのまま渡す', (() => {
  post({ token: TOKEN, action: 'saveEstimate', payload: { 顧客名: 'テスト', requestId: 'r1' } });
  return [calls[0].name, calls[0].args[0]];
})(), ['apiSaveEstimate', { 顧客名: 'テスト', requestId: 'r1' }]);

check('buildEstimate が見積番号と行番号を渡す', (() => {
  post({ token: TOKEN, action: 'buildEstimate', estimateId: '20260915-01', rowNumber: 7 });
  return [calls[0].name, calls[0].args[0], calls[0].args[1]];
})(), ['apiBuildDocuments', '20260915-01', 7]);

// 呼ぶ側が番号を決められないこと。採番はアプリの generateDocumentId_ だけが行う
check('saveEstimate に estimate_id を混ぜても採番を奪えない', (() => {
  post({ token: TOKEN, action: 'saveEstimate',
    payload: { estimate_id: '99999999-99', 顧客名: 'テスト', requestId: 'r8' } });
  // payload はそのまま渡るが、採番するのは apiSaveEstimate 側の generateDocumentId_
  return calls[0].name;
})(), 'apiSaveEstimate');

console.log('■ 二重作成の防止（requestId 必須）');

// 外部APIは呼ぶ側が requestId を入れ忘れられる。入れ忘れたまま通信が切れて
// 再送されると請求書が2通できる。入口で止める。
check('requestId なしの saveInvoice → 拒否、api* は呼ばない', (() => {
  const r = post({ token: TOKEN, action: 'saveInvoice', payload: { 顧客名: 'テスト' } });
  return [r.ok, calls.length];
})(), [false, 0]);

check('requestId なしの saveEstimate → 拒否、api* は呼ばない', (() => {
  const r = post({ token: TOKEN, action: 'saveEstimate', payload: { 顧客名: 'テスト' } });
  return [r.ok, calls.length];
})(), [false, 0]);

check('空文字の requestId も拒否', (() => {
  const r = post({ token: TOKEN, action: 'saveInvoice', payload: { requestId: '   ' } });
  return [r.ok, calls.length];
})(), [false, 0]);

check('requestId があれば通る', (() => {
  const r = post({ token: TOKEN, action: 'saveInvoice', payload: { requestId: 'r1' } });
  return [r.ok, calls.length];
})(), [true, 1]);

// 読み取り系と帳票生成は requestId を要らない（新しい番号を作らないため）
check('buildInvoice は requestId 不要', (() => {
  const r = post({ token: TOKEN, action: 'buildInvoice', invoiceId: '20260915-01' });
  return [r.ok, calls.length];
})(), [true, 1]);

check('getInvoice は requestId 不要', (() => {
  const r = post({ token: TOKEN, action: 'getInvoice', invoiceId: '20260915-01' });
  return [r.ok, calls.length];
})(), [true, 1]);

console.log('■ 入力の不備');

check('IDなしの getInvoice → エラー、api* は呼ばない', (() => {
  const r = post({ token: TOKEN, action: 'getInvoice' });
  return [r.ok, calls.length];
})(), [false, 0]);

check('payloadなしの saveInvoice → エラー、api* は呼ばない', (() => {
  const r = post({ token: TOKEN, action: 'saveInvoice' });
  return [r.ok, calls.length];
})(), [false, 0]);

check('payloadなしの saveEstimate → エラー、api* は呼ばない', (() => {
  const r = post({ token: TOKEN, action: 'saveEstimate' });
  return [r.ok, calls.length];
})(), [false, 0]);

check('payload が配列や文字列でも拒否', (() => {
  const a1 = post({ token: TOKEN, action: 'saveInvoice', payload: 'abc' });
  const a2 = post({ token: TOKEN, action: 'saveInvoice', payload: [1, 2] });
  return [a1.ok, a2.ok, calls.length];
})(), [false, false, 0]);

check('IDなしの buildEstimate → エラー、api* は呼ばない', (() => {
  const r = post({ token: TOKEN, action: 'buildEstimate' });
  return [r.ok, calls.length];
})(), [false, 0]);

check('知らない action → 使える一覧を返す', (() => {
  const r = post({ token: TOKEN, action: 'dropTable' });
  return [r.ok, Array.isArray(r.actions)];
})(), [false, true]);

// 一覧が実装と食い違うと、呼ぶ側が存在しない action を叩く
check('返す action 一覧が実装と一致している', (() => {
  const listed = post({ token: TOKEN, action: 'zzz' }).actions.slice().sort();
  const works = listed.filter(a => {
    const r = post({ token: TOKEN, action: a });
    return !(r.error && r.error.indexOf('知らない action') === 0);
  });
  return [listed.length, works.length];
})(), [8, 8]);

check('JSONとして壊れている → エラーで落ちない',
  post(null, '{壊れた').ok, false);

check('本文が空 → 認証で止まる',
  post(null, '').ok, false);

console.log('■ doGet は変えていない');
check('doGet が残っている', typeof sandbox.doGet, 'function');
check('doPost が増えている', typeof sandbox.doPost, 'function');

console.log('');
if (failures.length === 0) {
  console.log(`✅ 全 ${pass} ケース合格`);
  process.exit(0);
}
console.log(`❌ ${failures.length} 件失敗 / ${pass} 件合格\n`);
failures.forEach(f => console.log('  ✗ ' + f + '\n'));
process.exit(1);
