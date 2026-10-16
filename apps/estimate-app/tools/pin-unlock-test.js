#!/usr/bin/env node
/**
 * 暗証番号での鍵の再取得（unlockByPin）のテスト
 *
 *   node apps/estimate-app/tools/pin-unlock-test.js
 *
 * 鍵が端末から消えたとき、本人だけが知る6桁の暗証番号で鍵を取り戻す入口。
 * 鍵を持たない人が呼べる唯一の入口なので、次を確かめる。
 *   ・合っている番号の人にだけ、その人の鍵が返る
 *   ・総当たりができない（5回で60分止まる／合計15回で所有者が解除するまで止まる）
 *   ・番号そのものは保存しない／鍵を止めたら暗証番号も使えない／単純な番号は設定できない
 *   ・admin* は所有者だけ（エディタからの実行）
 */
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');
const crypto = require('crypto');

const srcDir = path.join(__dirname, '..', 'src');
const GS_FILES = fs.readdirSync(srcDir).filter(f => f.endsWith('.gs')).sort();

let pass = 0;
const failures = [];

function check(name, actual, expected) {
  const a = JSON.stringify(actual);
  const x = JSON.stringify(expected);
  if (a === x) { pass++; return; }
  failures.push(`${name}\n    期待: ${x}\n    実際: ${a}`);
}

const OWNER = 'owner@example.com';
let activeUser = OWNER;
let scriptProps = {};
let nowMs = Date.parse('2026-10-16T12:00:00Z');
let lockBusy = false;

const RealDate = Date;
class FakeDate extends RealDate {
  constructor(...a) { super(...(a.length ? a : [nowMs])); }
  static now() { return nowMs; }
}

const sandbox = {
  console: { log() {}, warn() {}, error() {} },
  JSON, Math, Date: FakeDate, Number, String, Object, Array, isNaN, isFinite, RegExp, Error,
  Session: {
    getActiveUser: () => ({ getEmail: () => activeUser }),
    getEffectiveUser: () => ({ getEmail: () => OWNER })
  },
  PropertiesService: {
    getScriptProperties: () => ({
      getProperty: k => (k in scriptProps ? scriptProps[k] : null),
      setProperty: (k, v) => { scriptProps[k] = String(v); },
      deleteProperty: k => { delete scriptProps[k]; }
    })
  },
  LockService: {
    getScriptLock: () => ({
      tryLock: () => !lockBusy,
      waitLock: () => {},
      releaseLock: () => {}
    })
  },
  ScriptApp: { getService: () => ({ getUrl: () => 'https://script.google.com/macros/s/TESTDEPLOY/exec' }) },
  Utilities: (() => {
    let n = 0;
    return {
      getUuid: () => { n++; return 'AAAAAAAA-BBBB-4CCC-8DDD-' + String(n).padStart(12, '0'); },
      formatDate: () => '20261016',
      DigestAlgorithm: { SHA_256: 'SHA_256' },
      Charset: { UTF_8: 'UTF_8' },
      // GAS は符号つきバイト列を返す
      computeDigest: (algo, text) => Array.from(crypto.createHash('sha256').update(String(text), 'utf8').digest()).map(b => (b > 127 ? b - 256 : b))
    };
  })(),
  HtmlService: {
    createHtmlOutputFromFile: name => ({ getContent: () => fs.readFileSync(path.join(srcDir, name + '.html'), 'utf8') })
  }
};

vm.createContext(sandbox);
GS_FILES.forEach(f => vm.runInContext(fs.readFileSync(path.join(srcDir, f), 'utf8'), sandbox, { filename: f }));

const EXEC = 'https://script.google.com/macros/s/KAZUMA_DEPLOY/exec';

function setup() {
  scriptProps = {};
  activeUser = OWNER;
  sandbox.adminAddUiKey('和真', EXEC);
  sandbox.adminAddUiKey('オーナー', EXEC);
  sandbox.adminSetUiPin('和真', '482915');
  sandbox.adminSetUiPin('オーナー', '730164');
  return JSON.parse(scriptProps.UI_KEYS);
}

function state() { return JSON.parse(scriptProps.UI_PIN_STATE || '{"fails":0,"totalFails":0,"lockedUntil":0}'); }

/* ===================== 取り戻せる ===================== */

console.log('\n■ 合っている暗証番号 → その人の鍵が返る');

let keys = setup();
let r = sandbox.unlockByPin('482915');
check('和真の番号 → 和真の鍵', [r.ok, r.name, r.key === keys['和真']], [true, '和真', true]);
r = sandbox.unlockByPin('730164');
check('オーナーの番号 → オーナーの鍵（人ごとに別）', [r.ok, r.name, r.key === keys['オーナー']], [true, 'オーナー', true]);
check('返った鍵で、画面の入口が通る（requireUiKey_）', sandbox.requireUiKey_(sandbox.unlockByPin('482915').key), '和真');
check('空白・改行が混ざっても通る（貼り付け・入力の癖）', sandbox.unlockByPin(' 482 915\n').ok, true);

console.log('■ 鍵を作り直しても、暗証番号はそのまま使える（鍵だけ新しくなる）');
const oldKey = keys['和真'];
sandbox.adminAddUiKey('和真', EXEC);
keys = JSON.parse(scriptProps.UI_KEYS);
r = sandbox.unlockByPin('482915');
check('作り直したあと：新しい鍵が返る', [r.ok, r.key === keys['和真'], r.key !== oldKey], [true, true, true]);

/* ===================== 間違い ===================== */

console.log('■ 違う番号・形の違う入力 → 鍵は返らない');

keys = setup();
r = sandbox.unlockByPin('000000');
check('違う番号', [r.ok, r.key], [false, undefined]);
['', 'abcdef', '12345', '1234567', null, undefined, 482915, {}, ['482915']].forEach(v => {
  const x = sandbox.unlockByPin(v);
  check('形が違う入力 ' + JSON.stringify(v) + ' は断る（鍵なし）', [x.ok, x.key], [false, undefined]);
});
check('形が違う入力は失敗として数えない（押し間違いで止めない）', state().totalFails, 1);
check('数値の 482915 は文字列ではないので通らない（型を厳密に）', sandbox.unlockByPin(482915).ok, false);

/* ===================== 総当たりの防止 ===================== */

console.log('■ 5回間違えたら60分止まる／合計15回で所有者が解除するまで止まる');

keys = setup();
nowMs = Date.parse('2026-10-16T12:00:00Z');
for (let i = 0; i < 5; i++) sandbox.unlockByPin('111112');
check('5回目で止まる状態になる', state().lockedUntil > nowMs, true);
r = sandbox.unlockByPin('482915');
check('止まっている間は、正しい番号でも通さない（総当たりで当たりを探させない）', [r.ok, r.locked, r.key], [false, true, undefined]);
check('止まっている間の案内に待ち時間が出る', /あと約\d+分/.test(r.error), true);

nowMs += 59 * 60000;
check('59分後もまだ止まっている', sandbox.unlockByPin('482915').ok, false);
nowMs += 2 * 60000;
check('61分後には解ける', sandbox.unlockByPin('482915').ok, true);
check('成功したら数えがリセットされる', state(), { fails: 0, totalFails: 0, lockedUntil: 0 });

keys = setup();
nowMs = Date.parse('2026-10-16T12:00:00Z');
for (let round = 0; round < 3; round++) {
  for (let i = 0; i < 5; i++) sandbox.unlockByPin('111112');
  nowMs += 61 * 60000;
}
check('合計15回間違えた', state().totalFails, 15);
r = sandbox.unlockByPin('482915');
check('時間が経っても、正しい番号でも通らない（所有者が解除するまで）', [r.ok, r.locked], [false, true]);
check('案内は「代表へ連絡」', /代表/.test(r.error), true);

activeUser = '';
check('匿名では解除できない（所有者だけ）', (() => { try { sandbox.adminClearPinLock(); return 'ok'; } catch (e) { return 'error'; } })(), 'error');
check('解除に失敗したので止まったまま', sandbox.unlockByPin('482915').ok, false);
activeUser = OWNER;
sandbox.adminClearPinLock();
check('所有者が解除すれば、また使える', sandbox.unlockByPin('482915').ok, true);

console.log('■ 総当たりの見込み：解除されるまでに試せるのは15回だけ');
keys = setup();
nowMs = Date.parse('2026-10-16T12:00:00Z');
let tried = 0;
for (let n = 0; n < 2000; n++) {
  const guess = String(100000 + n * 7);   // 482915 とは違う並び
  if (guess === '482915' || guess === '730164') continue;
  const x = sandbox.unlockByPin(guess);
  if (!x.locked) tried++;
  if (x.locked && /代表/.test(x.error)) break;
  if (x.locked) nowMs += 61 * 60000;
}
check('時間を進めながら試し続けても、数えられた試行は15回で打ち止め', tried, 15);

console.log('■ 状態が壊れていたら、止めたことにする（空にすると総当たりができてしまう）');
keys = setup();
scriptProps.UI_PIN_STATE = '{broken';
check('壊れた状態 → 通さない', sandbox.unlockByPin('482915').ok, false);

console.log('■ 同時に呼ばれて、ロックが取れないとき');
keys = setup();
lockBusy = true;
r = sandbox.unlockByPin('482915');
lockBusy = false;
check('ロックが取れなければ通さず、混み合っていると返す', [r.ok, /混み合って/.test(r.error)], [false, true]);

/* ===================== 保存の仕方 ===================== */

console.log('■ 暗証番号そのものは保存しない／鍵を止めたら暗証番号も使えない');

keys = setup();
check('保存した値に番号そのものが入っていない', JSON.stringify(scriptProps).indexOf('482915') < 0 && JSON.stringify(scriptProps).indexOf('730164') < 0, true);
const pins = JSON.parse(scriptProps.UI_PINS);
check('同じ番号でも人が違えば指紋が違う（名前を混ぜている）', (() => {
  sandbox.adminSetUiPin('オーナー', '482915');
  const p2 = JSON.parse(scriptProps.UI_PINS);
  return p2['オーナー'] !== p2['和真'];
})(), true);
check('番号を変えると指紋も変わる', JSON.parse(scriptProps.UI_PINS)['和真'] === pins['和真'], true);

keys = setup();
sandbox.adminRevokeUiKey('和真');
check('鍵を止めた人は、暗証番号でも入れない', sandbox.unlockByPin('482915').ok, false);
check('止めた人の暗証番号は消える', 'UI_PINS' in scriptProps && '和真' in JSON.parse(scriptProps.UI_PINS), false);
check('ほかの人の暗証番号は残る', sandbox.unlockByPin('730164').ok, true);

// 鍵だけが消えた（手でプロパティを編集した等）。暗証番号が残っていても、鍵が無い人は通さない
keys = setup();
const k2 = JSON.parse(scriptProps.UI_KEYS);
delete k2['和真'];
scriptProps.UI_KEYS = JSON.stringify(k2);
r = sandbox.unlockByPin('482915');
check('鍵が無い人は、暗証番号が残っていても通さない（鍵なしで ok を返さない）', [r.ok, r.key], [false, undefined]);
k2['和真'] = 'short';
scriptProps.UI_KEYS = JSON.stringify(k2);
check('壊れた鍵（64桁でない）は返さない', sandbox.unlockByPin('482915').ok, false);

keys = setup();
sandbox.adminRemoveUiPin('和真');
check('暗証番号を消した人は、暗証番号では入れない', sandbox.unlockByPin('482915').ok, false);

/* ===================== 設定できる番号 ===================== */

console.log('■ 単純な番号・形の違う番号は設定できない／鍵が無い人には設定できない');

keys = setup();
['000000', '111111', '999999', '123456', '234567', '654321', '987654', '12345', '1234567', 'abcdef', '', null].forEach(v => {
  check('設定できない番号 ' + JSON.stringify(v), (() => { try { sandbox.adminSetUiPin('和真', v); return 'ok'; } catch (e) { return 'error'; } })(), 'error');
});
check('拒否された番号では、前の番号がそのまま使える', sandbox.unlockByPin('482915').ok, true);
check('鍵が無い人には設定できない', (() => { try { sandbox.adminSetUiPin('いない人', '482915'); return 'ok'; } catch (e) { return 'error'; } })(), 'error');
check('設定できる番号', sandbox.adminSetUiPin('和真', '509318').indexOf('設定しました') >= 0, true);
check('一覧に暗証番号の有無が出る（番号は出ない）', (() => {
  const m = sandbox.adminListUiKeys();
  return m.indexOf('暗証番号を決めている人') >= 0 && m.indexOf('509318') < 0;
})(), true);

/* ===================== 所有者だけ ===================== */

console.log('■ 設定・解除は所有者だけ（匿名では呼べない）');

keys = setup();
activeUser = '';
['adminSetUiPin', 'adminRemoveUiPin', 'adminClearPinLock'].forEach(fn => {
  check(fn + ' は匿名では止まる', (() => { try { sandbox[fn]('和真', '509318'); return 'ok'; } catch (e) { return 'error'; } })(), 'error');
});
check('匿名で呼ばれても暗証番号は変わっていない', (() => { activeUser = OWNER; return sandbox.unlockByPin('482915').ok; })(), true);

/* ===================== 結果 ===================== */

console.log('');
if (failures.length) {
  failures.forEach(f => console.log('❌ ' + f));
  console.log('\n' + pass + ' 合格 / ' + failures.length + ' 失敗');
  process.exit(1);
}
console.log('✅ 全 ' + pass + ' ケース合格');
