#!/usr/bin/env node
/**
 * 採番と二重作成防止のテスト
 *
 *   node apps/estimate-app/tools/numbering-dedup-test.js
 *
 * 外部APIが動き出した初日に落ちるのは、だいたいこの2つです（CMO 2026-09-18）。
 *
 *   ① 採番 `YYYYMMDD-nn` … 日またぎと、同じ日にほぼ同時に来たとき
 *   ② 二重作成 … 同じ requestId の再送。**キャッシュが切れたあとも含めて**
 *
 * dopost-test.js は入口（doPost）の振り分けだけを見ています。こちらは
 * apiSaveEstimate / apiSaveInvoice を**本物のまま**動かして、シートに何行できたかを見ます。
 * シートだけメモリ上の偽物に差し替えて、時計とキャッシュはテストから動かします。
 */
'use strict';

process.env.TZ = 'Asia/Tokyo';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const srcDir = path.join(__dirname, '..', 'src');

function pad(n, len) { return String(n).padStart(len || 2, '0'); }

/* ===================== 動かせる時計 ===================== */

const RealDate = Date;
let NOW = new RealDate('2026-09-18T10:00:00+09:00');

function setNow(iso) { NOW = new RealDate(iso); }

function FakeDate(...args) {
  if (!(this instanceof FakeDate)) return new RealDate(NOW.getTime()).toString();
  return args.length === 0 ? new RealDate(NOW.getTime()) : new RealDate(...args);
}
FakeDate.prototype = RealDate.prototype;
FakeDate.now = () => NOW.getTime();
FakeDate.parse = RealDate.parse;
FakeDate.UTC = RealDate.UTC;

/* ===================== メモリ上のシート ===================== */

/**
 * getRange / setValues / getLastRow だけ本物に合わせた最小のシート。
 * 列は1始まり。値は配列の配列でそのまま持つ。
 */
function makeSheet(name, headers) {
  const grid = [headers.slice()];

  function ensure(r, c) {
    while (grid.length < r) grid.push([]);
    const row = grid[r - 1];
    while (row.length < c) row.push('');
  }

  const sheet = {
    getName: () => name,
    getParent: () => ({ getId: () => 'SS_' + name }),
    getLastRow: () => grid.length,
    getLastColumn: () => grid.reduce((m, r) => Math.max(m, r.length), 0),

    getRange(row, col, numRows, numCols) {
      const nr = numRows || 1;
      const nc = numCols || 1;
      const read = () => {
        const out = [];
        for (let r = row; r < row + nr; r++) {
          const line = [];
          for (let c = col; c < col + nc; c++) {
            const v = grid[r - 1] ? grid[r - 1][c - 1] : undefined;
            line.push(v === undefined || v === null ? '' : v);
          }
          out.push(line);
        }
        return out;
      };
      return {
        getValues: read,
        getDisplayValues: () => read().map(line => line.map(v => (v instanceof RealDate ? '' : String(v)))),
        setValues(values) {
          values.forEach((line, i) => {
            ensure(row + i, col + line.length - 1);
            line.forEach((v, j) => { grid[row + i - 1][col + j - 1] = v; });
          });
          return this;
        },
        setValue(v) { return this.setValues([[v]]); }
      };
    },

    /* テストから覗く用 */
    _grid: grid,
    _dataRows: () => grid.slice(1).filter(r => r.some(v => v !== '' && v !== undefined)),
    _column(header) {
      const c = grid[0].indexOf(header);
      return c < 0 ? [] : sheet._dataRows().map(r => r[c]);
    }
  };
  return sheet;
}

/* ===================== キャッシュ（テストから消せる） ===================== */

const cacheStore = new Map();
let cacheEnabled = true;

const CacheService = {
  getScriptCache: () => ({
    get: k => (cacheEnabled && cacheStore.has(k) ? cacheStore.get(k) : null),
    put: (k, v) => { cacheStore.set(k, v); },
    remove: k => { cacheStore.delete(k); },
    getAll: () => ({}),
    putAll: () => {}
  })
};

/** 30分たってキャッシュが消えた状態を作る */
function expireCache() { cacheStore.clear(); }

/* ===================== ロック（取得順を記録する） ===================== */

let lockHeld = false;
const lockLog = [];

const LockService = {
  getScriptLock: () => ({
    waitLock(ms) {
      if (lockHeld) throw new Error('ロックが取れませんでした（テスト側の直列化漏れ）');
      lockHeld = true;
      lockLog.push('acquire');
    },
    releaseLock() { lockHeld = false; lockLog.push('release'); },
    hasLock: () => lockHeld
  })
};

/* ===================== サンドボックス ===================== */

const sandbox = {
  console: { log() {}, warn() {}, error() {} },
  JSON, Math, Number, String, Object, Array, isNaN, isFinite, RegExp, Error,
  Date: FakeDate,
  CacheService,
  LockService,

  PropertiesService: {
    getScriptProperties: () => ({
      getProperty: () => null, setProperty: () => {}, deleteProperty: () => {}
    })
  },
  HtmlService: {
    createHtmlOutputFromFile: name => ({
      getContent: () => fs.readFileSync(path.join(srcDir, name + '.html'), 'utf8')
    })
  },
  Utilities: {
    formatDate(date, tz, pattern) {
      const d = date instanceof RealDate ? date : new RealDate(date);
      return pattern
        .replace('yyyy', d.getFullYear()).replace('MM', pad(d.getMonth() + 1))
        .replace('dd', pad(d.getDate())).replace('HH', pad(d.getHours()))
        .replace('mm', pad(d.getMinutes())).replace('ss', pad(d.getSeconds()));
    },
    getUuid: () => 'uuid-' + cacheStore.size
  },
  Session: {
    getActiveUser: () => ({ getEmail: () => 'test@example.com' }),
    getEffectiveUser: () => ({ getEmail: () => 'test@example.com' })
  }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(path.join(srcDir, 'code.gs'), 'utf8'), sandbox, { filename: 'code.gs' });
vm.runInContext(fs.readFileSync(path.join(srcDir, 'Invoice.gs'), 'utf8'), sandbox, { filename: 'Invoice.gs' });

// const で宣言されたものは sandbox のプロパティにならないので、中から取り出す
const RUNTIME = vm.runInContext('RUNTIME', sandbox);

/* ===================== マスタ（計算に必要な最小限） ===================== */

const MENUS = {
  M001: {
    menuId: 'M001', name: 'エアコンクリーニング（ノーマルエアコン）', menuType: 'メイン',
    rawMenuType: 'メイン', category: 'エアコン', unitPrice: 9800, unitPriceRaw: 9800,
    taxType: '課税', unit: '台', busyTarget: true, busySurchargeRaw: 3300,
    discountTarget: true, multipleDiscountTarget: true, invoiceReusable: true, note: '', requireCheck: ''
  }
};

const CTX = {
  settings: {},
  taxRate: 0.1,
  busySurcharge: 3300,
  busySurchargeUnit: 'メインメニュー数量',
  busySurchargeTaxIncluded: true,
  autoDiscountEnabled: false,
  autoDiscountEnabledWeb: true,
  setPricingEnabled: true,
  largeDiscountRatio: 0.3,
  netBenefit: 2200,
  menus: Object.keys(MENUS).map(k => MENUS[k]),
  menuMap: MENUS,
  discountRules: [],
  submitTos: [],
  mailTemplates: [],
  staffs: [],
  cellDefs: [],
  fromCache: false
};

/* ===================== シートを差し替える ===================== */

let estimateSheet = null;
let invoiceSheet = null;

function resetSheets() {
  estimateSheet = makeSheet('見積書/データ格納', sandbox.getEstimateHeaders_());
  invoiceSheet = makeSheet('請求書/データ格納', sandbox.getInvoiceHeaders_());
  Object.keys(RUNTIME.headerInfo).forEach(k => { delete RUNTIME.headerInfo[k]; });
  cacheStore.clear();
  cacheEnabled = true;
  lockLog.length = 0;
}

sandbox.loadContext_ = () => CTX;
sandbox.getEstimateDataSheet_ = () => estimateSheet;
sandbox.getInvoiceDataSheet_ = () => invoiceSheet;
sandbox.queueLog_ = () => {};
sandbox.flushLogs_ = () => {};

/* 採番が「ロックの中で」呼ばれていることを見張る。外に出た瞬間に同時実行で衝突する */
let numberedOutsideLock = 0;
const realGenerate = sandbox.generateDocumentId_;
sandbox.generateDocumentId_ = function (sheet, idHeader, label) {
  if (!lockHeld) numberedOutsideLock++;
  return realGenerate(sheet, idHeader, label);
};

/* ===================== テスト ===================== */

let pass = 0;
const failures = [];

function check(name, actual, expected) {
  const a = JSON.stringify(actual);
  const x = JSON.stringify(expected);
  if (a === x) { pass++; return; }
  failures.push(`${name}\n    期待: ${x}\n    実際: ${a}`);
}

function saveEstimate(requestId, extra) {
  return sandbox.apiSaveEstimate(Object.assign({
    requestId: requestId,
    案件タイプ: '自社案件',
    顧客名: 'テスト顧客',
    案件名: 'エアコンクリーニング',
    受注経路: 'normal',
    mainLines: [{ menuId: 'M001', qty: 1 }],
    optionLines: [],
    adjustments: []
  }, extra || {}));
}

function saveInvoice(requestId, estimateId, extra) {
  return sandbox.apiSaveInvoice(Object.assign({
    requestId: requestId,
    estimateId: estimateId,
    mainLines: [{ menuId: 'M001', qty: 1 }],
    optionLines: [],
    adjustments: []
  }, extra || {}));
}

console.log('\n■ 採番：同じ日');
resetSheets();
setNow('2026-09-18T10:00:00+09:00');

check('1件目は -01', saveEstimate('a1').estimateId, '20260918-01');
check('2件目は -02', saveEstimate('a2').estimateId, '20260918-02');
check('3件目は -03', saveEstimate('a3').estimateId, '20260918-03');
check('行も3行できている', estimateSheet._dataRows().length, 3);

console.log('■ 採番：日またぎ');
setNow('2026-09-18T23:59:59+09:00');
check('23:59:59 は当日の続き', saveEstimate('a4').estimateId, '20260918-04');

setNow('2026-09-19T00:00:00+09:00');
const dayAfter = saveEstimate('a5');
check('00:00:00 は翌日の -01 から', dayAfter.estimateId, '20260919-01');
check('前日の番号を作り直していない',
  estimateSheet._column('estimate_id').filter(v => v === '20260918-04').length, 1);

setNow('2026-09-19T00:00:01+09:00');
check('同じ日の2件目は -02', saveEstimate('a6').estimateId, '20260919-02');

// 日付が戻る（サマータイムや手動調整）ことは日本では起きないが、
// 戻ったとしても既存の最大値の次を採るので、既存IDを上書きしない
setNow('2026-09-18T12:00:00+09:00');
check('時計が前日に戻っても既存IDを再発行しない', saveEstimate('a7').estimateId, '20260918-05');

console.log('■ 採番：走査の対象');
resetSheets();
setNow('2026-09-18T10:00:00+09:00');

// 旧アプリの `EST-YYYYMMDD-0001` と、5桁始まりの旧請求番号が混ざっていても効かない
estimateSheet.getRange(2, 1, 3, 1).setValues([['EST-20260918-0001'], ['00116-03'], ['20260918-07']]);
estimateSheet.getRange(5, 1, 1, 1).setValues([['20260918-08-控']]);
check('旧接頭辞と旧番号と枝番を飛ばして、その次を採る',
  sandbox.generateEstimateId_(estimateSheet), '20260918-08');

resetSheets();
estimateSheet.getRange(2, 1, 1, 1).setValues([['20260918-99']]);
check('100件目は3桁になる（桁が伸びるだけで破綻しない）',
  sandbox.generateEstimateId_(estimateSheet), '20260918-100');

resetSheets();
estimateSheet.getRange(2, 1, 2, 1).setValues([['20260917-50'], ['20260919-50']]);
check('前日・翌日の番号は当日の採番に影響しない',
  sandbox.generateEstimateId_(estimateSheet), '20260918-01');

console.log('■ 採番：見積と請求がずれないこと');
resetSheets();
setNow('2026-09-18T10:00:00+09:00');

const e1 = saveEstimate('b1');
const e2 = saveEstimate('b2');
check('見積は -01 と -02', [e1.estimateId, e2.estimateId], ['20260918-01', '20260918-02']);

const i1 = saveInvoice('b3', e1.estimateId);
check('請求は自分のシートで -01 から', i1.invoiceId, '20260918-01');
check('請求2件目は -02', saveInvoice('b4', e2.estimateId).invoiceId, '20260918-02');
check('同じ generateDocumentId_ を通っている（形式が一致）',
  /^\d{8}-\d{2}$/.test(i1.invoiceId), true);

console.log('■ 採番：同時実行');
resetSheets();
setNow('2026-09-18T10:00:00+09:00');

// 直前の節でテストから直接 generateEstimateId_ を呼んでいるぶんを数えない
numberedOutsideLock = 0;

const ids = [];
for (let i = 0; i < 20; i++) ids.push(saveEstimate('c' + i).estimateId);
check('20件が全部ちがう番号', new Set(ids).size, 20);
check('連番が飛んでいない', ids[19], '20260918-20');
check('採番は必ずロックの中で行われている', numberedOutsideLock, 0);
check('ロックを取りっぱなしにしていない', lockHeld, false);
check('取得と解放の数が合っている',
  lockLog.filter(x => x === 'acquire').length === lockLog.filter(x => x === 'release').length, true);

// ロックが取れないまま採番に入ったら、番号は必ず衝突する。
// waitLock のスタブは二重取得を例外にしているので、ここが通る＝直列化されている
check('保存中に別の保存が割り込めない（ロックが効いている）', (() => {
  let overlapped = false;
  const realAppend = sandbox.appendObject_;
  sandbox.appendObject_ = function (sheet, obj) {
    // 書き込みの最中にもう1件来たとみなす。ロックが効いていれば例外になる
    try { sandbox.LockService.getScriptLock().waitLock(1); overlapped = true; } catch (e) { /* 期待どおり */ }
    return realAppend(sheet, obj);
  };
  saveEstimate('c99');
  sandbox.appendObject_ = realAppend;
  return overlapped;
})(), false);

console.log('■ 二重作成：同じ requestId の再送');
resetSheets();
setNow('2026-09-18T10:00:00+09:00');

const first = saveEstimate('same-1');
const again = saveEstimate('same-1');
check('2回目は新しい番号を作らない', again.estimateId, first.estimateId);
check('2回目は duplicated が立つ', again.duplicated, true);
check('行は1行のまま', estimateSheet._dataRows().length, 1);
check('行番号も同じ', again.rowNumber, first.rowNumber);

console.log('■ 二重作成：キャッシュが切れたあとの再送');
// 30分たつとキャッシュは消える。消えたあとに再送が来ても2件目を作らないこと。
// シートの request_id 列で拾う（findRowByRequestId_）
expireCache();
const afterExpiry = saveEstimate('same-1');
check('キャッシュが消えても新しい番号を作らない', afterExpiry.estimateId, first.estimateId);
check('キャッシュが消えても duplicated が立つ', afterExpiry.duplicated, true);
check('行はやはり1行のまま', estimateSheet._dataRows().length, 1);

// 日をまたいでからの再送でも、前日の番号を返す（新しい日付で作り直さない）
expireCache();
setNow('2026-09-19T09:00:00+09:00');
check('翌日に再送が来ても前日の番号を返す', saveEstimate('same-1').estimateId, first.estimateId);
check('翌日でも行は増えない', estimateSheet._dataRows().length, 1);

// キャッシュそのものが使えない環境でも、二重作成にはならない
resetSheets();
setNow('2026-09-18T10:00:00+09:00');
cacheEnabled = false;
const noCache1 = saveEstimate('nc-1');
const noCache2 = saveEstimate('nc-1');
check('キャッシュが全く効かなくても二重作成しない', noCache2.estimateId, noCache1.estimateId);
check('キャッシュ無しでも行は1行', estimateSheet._dataRows().length, 1);
cacheEnabled = true;

console.log('■ 二重作成：請求書');
resetSheets();
setNow('2026-09-18T10:00:00+09:00');

const est = saveEstimate('d1');
const inv1 = saveInvoice('d2', est.estimateId);
const inv2 = saveInvoice('d2', est.estimateId, { allowRecreate: true });
check('同じ requestId の請求は1通のまま', inv2.invoiceId, inv1.invoiceId);
check('請求行も1行', invoiceSheet._dataRows().length, 1);

expireCache();
const inv3 = saveInvoice('d2', est.estimateId, { allowRecreate: true });
check('キャッシュが切れても請求書を2通作らない', inv3.invoiceId, inv1.invoiceId);
check('請求行はやはり1行', invoiceSheet._dataRows().length, 1);

// requestId を付け替えたら、それは「作り直し」の意思表示。
// allowRecreate が無ければ見積側の invoice_id が二重請求を止める
check('別の requestId でも allowRecreate なしなら止まる',
  saveInvoice('d3', est.estimateId).ok, false);

console.log('■ 二重作成：見積と請求で同じ requestId を使われたとき');
// 呼ぶ側が「1件の仕事に1つの requestId」を振ると、これが起きる。
// 名前空間を分けていないと、請求番号として見積番号が返り、請求行は1行も書かれない
resetSheets();
setNow('2026-09-18T10:00:00+09:00');

const shared = 'job-777';
const sharedEst = saveEstimate(shared);
const sharedInv = saveInvoice(shared, sharedEst.estimateId);

check('請求番号が見積番号で上書きされていない',
  sharedInv.invoiceId !== sharedEst.estimateId || invoiceSheet._dataRows().length === 1, true);
check('請求行がちゃんと1行できている', invoiceSheet._dataRows().length, 1);
check('請求番号は請求シートの採番',
  invoiceSheet._column('invoice_id')[0], sharedInv.invoiceId);
check('見積行は1行のまま', estimateSheet._dataRows().length, 1);
check('見積の invoice_id に請求番号が入っている',
  estimateSheet._column('invoice_id')[0], sharedInv.invoiceId);

console.log('■ エラーの文言が、呼ぶ側にとって直せる形になっているか');

function messageOf(result) { return String(result && result.error || ''); }

// 合言葉だけは理由を出さない（総当たりの手がかりにしない）。それ以外は直せる文言に
check('見積IDが無い請求 → 何が見つからなかったか分かる', (() => {
  resetSheets();
  const m = messageOf(saveInvoice('e1', '99999999-99'));
  return [m.indexOf('見積ID') >= 0, m.indexOf('99999999-99') >= 0];
})(), [true, true]);

check('二重請求 → 既存の請求番号と、どうすれば通るかが書いてある', (() => {
  resetSheets();
  const e = saveEstimate('e2');
  const i = saveInvoice('e3', e.estimateId);
  const m = messageOf(saveInvoice('e4', e.estimateId));
  return [m.indexOf(i.invoiceId) >= 0, m.indexOf('再作成') >= 0];
})(), [true, true]);

check('requestId 忘れ → 何を入れればいいか書いてある', (() => {
  const m = String(sandbox.requirePayloadWithRequestId_({}, () => ({ ok: true })).error || '');
  return [m.indexOf('requestId') >= 0, m.indexOf('UUID') >= 0];
})(), [true, true]);

check('ID忘れ → どのIDか書いてある', (() => {
  const m = String(sandbox.requireId_('', '請求番号', () => ({ ok: true })).error || '');
  return m.indexOf('請求番号') >= 0;
})(), true);

check('エラーでも ok:false で返る（例外を投げっぱなしにしない）', (() => {
  resetSheets();
  return saveInvoice('e5', 'missing-id').ok;
})(), false);

console.log('');
if (failures.length === 0) {
  console.log(`✅ 全 ${pass} ケース合格`);
  process.exit(0);
} else {
  failures.forEach(f => console.log('❌ ' + f));
  console.log(`\n${pass} 合格 / ${failures.length} 失敗`);
  process.exit(1);
}
