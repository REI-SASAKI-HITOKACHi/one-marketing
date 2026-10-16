#!/usr/bin/env node
/**
 * 画面側（src/JavaScript.html）の「鍵」の動きのテスト
 *
 *   node apps/estimate-app/tools/ui-key-client-test.js
 *
 * ui-key-test.js は画面のソースを文字列で見るだけだったので、書き換えられても気づけなかった
 * （独立レビュー 2026-10-16）。ここでは画面のスクリプトを実際に動かし、偽の google.script・
 * 偽の画面部品・偽の localStorage を使って、次の筋書きを確かめる。
 *   ・リンク（アイコン）の ?k= の鍵で開く／通ったらアドレス欄にも鍵を書く
 *   ・リンクの鍵が古いときは、スマホに残っている鍵で開き直す（ちょうど2回で止まる）
 *   ・どの鍵も合わないときは、暗証番号の欄を出す
 *   ・暗証番号：二度押しでもサーバーは1回しか呼ばれない／合えば鍵を保存して開く
 *   ・localStorage が例外を投げても動く／旧い #key= のリンクも読める
 */
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const srcDir = path.join(__dirname, '..', 'src');
const html = fs.readFileSync(path.join(srcDir, 'JavaScript.html'), 'utf8');
const script = html.replace(/^[\s\S]*?<script>/, '').replace(/<\/script>[\s\S]*$/, '');

let pass = 0;
const failures = [];
function check(name, actual, expected) {
  const a = JSON.stringify(actual);
  const x = JSON.stringify(expected);
  if (a === x) { pass++; return; }
  failures.push(`${name}\n    期待: ${x}\n    実際: ${a}`);
}

const K_OLD = 'a'.repeat(64);
const K_NEW = 'b'.repeat(64);
const K_PIN = 'c'.repeat(64);
const MARK = '[UI_KEY] ';
const NONE = '[UI_KEY_NONE] ';

/** 画面部品の偽物。知らない関数は何もしない関数として扱う */
function makeEl(id) {
  const classes = new Set(id === 'keyPaste' || id === 'fatalError' || id === 'app' ? ['hidden'] : []);
  const base = {
    id, value: '', checked: false, textContent: '', innerHTML: '', disabled: false, hidden: false,
    style: {}, dataset: {},
    classList: {
      add: c => classes.add(c), remove: c => classes.delete(c),
      toggle: c => (classes.has(c) ? classes.delete(c) : classes.add(c)), contains: c => classes.has(c)
    },
    getAttribute: n => (n === 'data-action' && id === '__unlock' ? 'unlock-pin' : null),
    addEventListener() {}, appendChild() {}, setAttribute() {}, focus() {}, querySelectorAll: () => [],
    querySelector: () => null, closest: () => null,
    _classes: classes
  };
  return new Proxy(base, { get: (t, p) => (p in t ? t[p] : function () {}), set: (t, p, v) => { t[p] = v; return true; } });
}

/**
 * 1つの筋書きを動かす。
 * opts.loc … getLocation が返す値  opts.stored … localStorage の初期値  opts.storageThrows
 * opts.accept … 通す鍵の一覧  opts.noneMode … 鍵が1つも無い応答にする
 * opts.pinReply … unlockByPin の返事  opts.holdPin … 返事をすぐ返さず、あとで返す
 */
function run(opts) {
  const els = {};
  const getEl = id => (els[id] = els[id] || makeEl(id));
  const unlockBtn = makeEl('__unlock');
  const log = { bootstrap: [], pin: [], replace: [], store: {}, handlers: {}, toasts: [] };
  let storage = opts.stored ? { estimateAppUiKey: opts.stored } : {};
  const held = [];

  const documentStub = {
    getElementById: getEl,
    createElement: () => makeEl('x'),
    querySelector: sel => (sel === '[data-action="unlock-pin"]' ? unlockBtn : makeEl('q')),
    querySelectorAll: () => [],
    addEventListener: (type, fn) => { log.handlers[type] = fn; },
    body: makeEl('body')
  };

  function runner() {
    let ok = () => {}; let ng = () => {};
    const api = {
      withSuccessHandler(f) { ok = f; return api; },
      withFailureHandler(f) { ng = f; return api; },
      apiBootstrap(key) {
        log.bootstrap.push(key);
        if (opts.noneMode) return ng({ message: NONE + 'いま見積アプリは準備中です。' });
        if ((opts.accept || []).indexOf(key) >= 0) return ok({ ok: false, error: 'stop-after-key' });
        return ng({ message: MARK + 'このスマホでは、まだ見積アプリを使えません。' });
      },
      unlockByPin(pin) {
        log.pin.push(pin);
        const reply = opts.pinReply || { ok: false, error: '暗証番号が違います。' };
        if (opts.holdPin) { held.push(() => ok(reply)); return; }
        ok(reply);
      }
    };
    return api;
  }

  const windowStub = {
    addEventListener: (type, fn) => { log.handlers['window:' + type] = fn; },
    localStorage: {
      getItem: k => { if (opts.storageThrows) throw new Error('blocked'); return k in storage ? storage[k] : null; },
      setItem: (k, v) => { if (opts.storageThrows) throw new Error('blocked'); storage[k] = v; log.store[k] = v; },
      removeItem: k => { if (opts.storageThrows) throw new Error('blocked'); delete storage[k]; }
    },
    crypto: undefined
  };

  const sandbox = {
    window: windowStub, document: documentStub, console: { log() {}, warn() {}, error() {} },
    google: {
      script: {
        run: new Proxy({}, { get: (t, p) => runner()[p] || (() => runner()) }),
        url: { getLocation: cb => cb(opts.loc || { parameter: {}, hash: '' }) },
        history: { replace: (s, params, hash) => log.replace.push({ params, hash }) }
      }
    },
    CalcEngine: new Proxy({}, { get: () => function () { return ''; } }),
    setTimeout: () => 0, clearTimeout() {}, Date, JSON, Math, Number, String, Object, Array, RegExp, Error, isNaN, isFinite
  };
  // google.script.run は呼ぶたびに新しい呼び出しの入れ物を返す
  Object.defineProperty(sandbox.google.script, 'run', { get: () => runner() });

  vm.createContext(sandbox);
  vm.runInContext(script, sandbox, { filename: 'JavaScript.html' });
  log.handlers['window:load']();

  return {
    log, els, getEl, storage: () => storage,
    clickUnlock() {
      getEl('pinInput').value = opts.pinInput !== undefined ? opts.pinInput : '482915';
      const target = { closest: () => ({ getAttribute: n => (n === 'data-action' ? 'unlock-pin' : null) }) };
      log.handlers.click({ target, preventDefault() {} });
    },
    release() { while (held.length) held.shift()(); },
    panelShown: () => !getEl('keyPaste')._classes.has('hidden'),
    unlockBtn
  };
}

const keyOf = k => ({ parameter: { k }, hash: '' });

/* ===================== リンク（アイコン）の鍵 ===================== */

console.log('\n■ リンクの ?k= の鍵で開く');

let r = run({ loc: keyOf(K_NEW), accept: [K_NEW] });
check('サーバーを1回だけ呼び、リンクの鍵を渡す', r.log.bootstrap, [K_NEW]);
check('通ったら、鍵をアドレス欄にも書く（アイコンに残る）', r.log.replace, [{ params: { k: K_NEW }, hash: '' }]);
check('通ったら、スマホにも覚えさせる', r.storage().estimateAppUiKey, K_NEW);
check('鍵の案内は出さない', r.panelShown(), false);

console.log('■ 旧い #key= のリンクも読める → ?k= に置き換わる');
r = run({ loc: { parameter: {}, hash: '#key=' + K_NEW }, accept: [K_NEW] });
check('旧リンクの鍵で開く', r.log.bootstrap, [K_NEW]);
check('アドレス欄は ?k= に置き換わる（# 以下は消える）', r.log.replace, [{ params: { k: K_NEW }, hash: '' }]);

console.log('■ 配列で来た parameter.k（同じ名前が複数）も読める');
r = run({ loc: { parameter: { k: [K_NEW, 'x'] }, hash: '' }, accept: [K_NEW] });
check('最初の値を使う', r.log.bootstrap, [K_NEW]);

console.log('■ 形の違う k は無視する（スマホの鍵があればそれで開く）');
r = run({ loc: keyOf('not-a-key'), stored: K_NEW, accept: [K_NEW] });
check('スマホの鍵で開く', r.log.bootstrap, [K_NEW]);

/* ===================== スマホの記憶（予備） ===================== */

console.log('■ アドレス欄に鍵が無い → スマホの鍵で開き、アドレス欄に鍵を書き戻す');
r = run({ stored: K_NEW, accept: [K_NEW] });
check('スマホの鍵で1回だけ呼ぶ', r.log.bootstrap, [K_NEW]);
check('アドレス欄に鍵を書く（ここから「ホーム画面に追加」すれば鍵が残る）', r.log.replace, [{ params: { k: K_NEW }, hash: '' }]);

console.log('■ リンクの鍵が古い（鍵を作り直した）→ スマホに残っている新しい鍵で開き直す');
r = run({ loc: keyOf(K_OLD), stored: K_NEW, accept: [K_NEW] });
check('古い鍵 → 新しい鍵の順に、ちょうど2回', r.log.bootstrap, [K_OLD, K_NEW]);
check('新しい鍵が通ったのでアドレス欄は新しい鍵になる', r.log.replace, [{ params: { k: K_NEW }, hash: '' }]);
check('案内は出さない', r.panelShown(), false);

console.log('■ どの鍵も合わない → 2回で止まり、暗証番号の欄を出す（無限に呼ばない）');
r = run({ loc: keyOf(K_OLD), stored: K_NEW, accept: [] });
check('サーバーを呼ぶのは2回まで', r.log.bootstrap, [K_OLD, K_NEW]);
check('暗証番号の欄が出る', r.panelShown(), true);
check('合わなかったスマホの鍵は捨てる', r.storage().estimateAppUiKey, undefined);

r = run({ loc: keyOf(K_OLD), accept: [] });
check('予備が無いときは1回で止まる', r.log.bootstrap, [K_OLD]);
check('そのときも暗証番号の欄が出る', r.panelShown(), true);

r = run({ loc: keyOf(K_OLD), stored: K_OLD, accept: [] });
check('リンクとスマホが同じ鍵なら、同じ鍵を2回呼ばない', r.log.bootstrap, [K_OLD]);

console.log('■ 鍵がどこにも無い → サーバーを呼ばずに暗証番号の欄を出す');
r = run({});
check('サーバーを呼ばない', r.log.bootstrap, []);
check('暗証番号の欄が出る', r.panelShown(), true);

console.log('■ 鍵が1つも発行されていない（準備中）→ 入力欄は出さず、スマホの鍵は消さない');
r = run({ loc: keyOf(K_NEW), stored: K_NEW, noneMode: true });
check('入力欄を出さない', r.panelShown(), false);
check('スマホの鍵は残す（発行し直されたら、そのまま使える）', r.storage().estimateAppUiKey, K_NEW);

console.log('■ localStorage が使えなくても、リンクの鍵で開ける');
r = run({ loc: keyOf(K_NEW), accept: [K_NEW], storageThrows: true });
check('開ける', r.log.bootstrap, [K_NEW]);
r = run({ storageThrows: true });
check('記憶も読めず鍵も無いときは、暗証番号の欄を出す', [r.log.bootstrap, r.panelShown()], [[], true]);

/* ===================== 暗証番号 ===================== */

console.log('■ 暗証番号：合えば鍵を保存して開く');
r = run({ pinReply: { ok: true, name: '和真', key: K_PIN }, accept: [K_PIN] });
r.clickUnlock();
check('サーバーの unlockByPin を1回呼ぶ', r.log.pin, ['482915']);
check('返ってきた鍵で開く', r.log.bootstrap, [K_PIN]);
check('鍵をスマホに保存する', r.storage().estimateAppUiKey, K_PIN);
check('アドレス欄にも鍵を書く', r.log.replace.some(x => x.params.k === K_PIN), true);
check('案内の欄は閉じる', r.panelShown(), false);

console.log('■ 暗証番号：違えば鍵は保存せず、理由を出す。ボタンは押せる状態に戻る');
r = run({ pinReply: { ok: false, error: '暗証番号が違います。' } });
r.clickUnlock();
check('鍵を保存しない', r.storage().estimateAppUiKey, undefined);
check('理由を出す', r.getEl('pinError').textContent, '暗証番号が違います。');
check('ボタンは押せる状態に戻る', r.unlockBtn.disabled, false);
check('サーバーで開こうとしない', r.log.bootstrap, []);

console.log('■ 暗証番号：返事を待っている間の二度押しは、サーバーを1回しか呼ばない');
r = run({ pinReply: { ok: false, error: '暗証番号が違います。' }, holdPin: true });
r.clickUnlock();
check('押している間はボタンが押せない', r.unlockBtn.disabled, true);
r.clickUnlock();
r.clickUnlock();
check('3回押してもサーバーを呼ぶのは1回', r.log.pin.length, 1);
r.release();
check('返事が来たらボタンが戻る', r.unlockBtn.disabled, false);

console.log('■ 暗証番号：6桁の数字でなければ、サーバーを呼ばない');
['12345', 'abcdef', '', '１２３４５６'].forEach(v => {
  r = run({ pinInput: v });
  r.clickUnlock();
  check('入力 ' + JSON.stringify(v) + ' はサーバーを呼ばず、案内を出す', [r.log.pin, r.getEl('pinError').textContent], [[], '暗証番号は6桁の数字です。']);
});
r = run({ pinInput: '482 915', pinReply: { ok: false, error: 'x' } });
r.clickUnlock();
check('途中に空白が入っていても、詰めて送る', r.log.pin, ['482915']);

/* ===================== 結果 ===================== */

console.log('');
if (failures.length) {
  failures.forEach(f => console.log('❌ ' + f));
  console.log('\n' + pass + ' 合格 / ' + failures.length + ' 失敗');
  process.exit(1);
}
console.log('✅ 全 ' + pass + ' ケース合格');
