#!/usr/bin/env node
/**
 * 本番マスタの実データに対する読み込みテスト
 *
 *   node apps/estimate-app/tools/live-master-test.js
 *
 * fixtures-live-master.json は本番スプレッドシートをxlsxで書き出したもの。
 * 顧客データ（データ格納）・操作ログ・提出先マスタは含めず、
 * メールアドレスは redacted@example.com に置換してある。
 *
 * 確認すること
 *   - 列ずれしたままの割引繁忙期マスタ（1000行超に増殖）から正しいルールを復元できるか
 *   - 新スキーマ列が空のメールテンプレートマスタから文面を拾えるか
 *   - メニューマスタの重複列（後半の旧列）に引きずられず単価を読めるか
 *   - 差し込みセル定義が実テンプレートのレイアウトと一致しているか
 *   - 実マスタで繁忙期・割引の自動判定が仕様どおりに動くか
 *
 * つまり「マスタを正規化する前でも正しく動く」ことの裏取り。
 */
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const srcDir = path.join(__dirname, '..', 'src');
const fixtures = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures-live-master.json'), 'utf8'));

/* ===================== SpreadsheetApp の最小スタブ ===================== */

const MASTER_ID = '1HPtoKzOwwqnS6Yk_R0UHEy3u8Wpe43LrD7HlCvS6SLw';
const TEMPLATE_ID = '1s0iZGjz58SZLgpkrs-lO_EjGr8bQq6qUZB93lyx061c';

// xlsx書き出しはシート名から「/」が落ちるので元の名前に戻す
const SHEET_NAME_FIX = {
  '一時作業用見積書': '一時作業用/見積書',
  '一時作業用請求書': '一時作業用/請求書'
};

function makeRange(sheet, row, col, numRows, numCols) {
  return {
    getRow: () => row,
    getColumn: () => col,
    getNumRows: () => numRows,
    getNumColumns: () => numCols,
    getValues() {
      const out = [];
      for (let r = 0; r < numRows; r++) {
        const line = [];
        for (let c = 0; c < numCols; c++) line.push(sheet._cell(row + r, col + c));
        out.push(line);
      }
      return out;
    },
    getDisplayValues() {
      return this.getValues().map(r => r.map(v => (v === null || v === undefined) ? '' : String(v)));
    },
    getDisplayValue() { return String(sheet._cell(row, col) ?? ''); },
    getCell: (r, c) => makeRange(sheet, row + r - 1, col + c - 1, 1, 1),
    setValue(v) { sheet._writes.push({ row, col, value: v }); return this; },
    setValues(values) {
      values.forEach((line, r) => line.forEach((v, c) =>
        sheet._writes.push({ row: row + r, col: col + c, value: v })));
      return this;
    },
    clearContent() { sheet._clears.push({ row, col, numRows, numCols }); return this; }
  };
}

function parseA1(a1) {
  const m = String(a1).toUpperCase().match(/^([A-Z]+)(\d+)(?::([A-Z]+)(\d+))?$/);
  if (!m) throw new Error('A1形式ではありません：' + a1);
  const toCol = s => s.split('').reduce((n, ch) => n * 26 + (ch.charCodeAt(0) - 64), 0);
  const c1 = toCol(m[1]), r1 = Number(m[2]);
  const c2 = m[3] ? toCol(m[3]) : c1, r2 = m[4] ? Number(m[4]) : r1;
  return { row: r1, col: c1, numRows: r2 - r1 + 1, numCols: c2 - c1 + 1 };
}

function makeSheet(parent, name, data) {
  const sheet = {
    _rows: data.rows,
    _writes: [],
    _clears: [],
    _cell(row, col) {
      const line = this._rows[row - 1];
      if (!line) return '';
      const v = line[col - 1];
      return v === undefined ? '' : v;
    },
    getName: () => name,
    getParent: () => parent,
    getSheetId: () => 0,
    getLastRow: () => data.maxRow,
    getLastColumn: () => data.maxCol,
    setFrozenRows: () => sheet,
    getRange(a, b, c, d) {
      if (typeof a === 'string') {
        const p = parseA1(a);
        return makeRange(sheet, p.row, p.col, p.numRows, p.numCols);
      }
      return makeRange(sheet, a, b, c === undefined ? 1 : c, d === undefined ? 1 : d);
    }
  };
  return sheet;
}

function makeSpreadsheet(id, title, sheetData) {
  const ss = { getId: () => id, getName: () => title, getSpreadsheetTimeZone: () => 'America/Los_Angeles' };
  const sheets = {};

  Object.keys(sheetData).forEach(raw => {
    const name = SHEET_NAME_FIX[raw] || raw;
    sheets[name] = makeSheet(ss, name, sheetData[raw]);
  });

  ss.getSheetByName = name => sheets[name] || null;
  ss.getSheets = () => Object.keys(sheets).map(k => sheets[k]);
  ss._sheets = sheets;
  return ss;
}

const masterSs = makeSpreadsheet(MASTER_ID, '見積アプリ_マスタ入力テンプレート', fixtures.master);
const templateSs = makeSpreadsheet(TEMPLATE_ID, '【アプリ】見積/請求書', fixtures.template);

function pad(n, len) { return String(n).padStart(len || 2, '0'); }

const cacheStore = {};

const sandbox = {
  console: { log() {}, warn() {}, error() {} },
  JSON, Math, Date, Number, String, Object, Array, isNaN, isFinite, RegExp,

  SpreadsheetApp: {
    openById(id) {
      if (id === MASTER_ID) return masterSs;
      if (id === TEMPLATE_ID) return templateSs;
      throw new Error('unknown spreadsheet: ' + id);
    },
    flush() {}
  },

  CacheService: {
    getScriptCache: () => ({
      get: k => (k in cacheStore ? cacheStore[k] : null),
      getAll: keys => { const o = {}; keys.forEach(k => { if (k in cacheStore) o[k] = cacheStore[k]; }); return o; },
      put: (k, v) => { cacheStore[k] = v; },
      putAll: obj => Object.assign(cacheStore, obj),
      removeAll: keys => keys.forEach(k => delete cacheStore[k])
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

/* ===================== テストランナー ===================== */

let pass = 0;
const failures = [];
const notes = [];

function check(name, actual, expected) {
  const a = JSON.stringify(actual);
  const e = JSON.stringify(expected);
  if (a === e) { pass++; return; }
  failures.push(`${name}\n    期待: ${e}\n    実際: ${a}`);
}

function note(text) { notes.push(text); }

/* ===================== 実データの状態 ===================== */

console.log('\n■ 本番マスタの現状（読み込み前）');

const discountRowCount = fixtures.master['割引繁忙期マスタ'].maxRow;
const mailRowCount = fixtures.master['メールテンプレートマスタ'].maxRow;
console.log('  割引繁忙期マスタ　　　： ' + discountRowCount + '行');
console.log('  メールテンプレートマスタ： ' + mailRowCount + '行');
console.log('  メニューマスタ　　　　： ' + fixtures.master['メニューマスタ'].maxRow + '行 × '
  + fixtures.master['メニューマスタ'].maxCol + '列');

/* ===================== マスタ読み込み ===================== */

console.log('\n■ 読み込み結果');

const warnings = [];
const settings = sandbox.readSettings_(masterSs);
const menus = sandbox.readMenus_(masterSs, warnings);
const rules = sandbox.readDiscountRules_(masterSs, warnings);
const templates = sandbox.readMailTemplates_(masterSs, warnings);
const cellDefs = sandbox.readCellDefs_(masterSs);

const byType = t => rules.filter(r => r.ruleType === t).length;

console.log('  有効メニュー　： ' + menus.length + '件（メイン '
  + menus.filter(m => m.menuType === 'メイン').length + ' / オプション '
  + menus.filter(m => m.menuType === 'オプション').length + '）');
console.log('  有効ルール　　： ' + rules.length + '件（繁忙期 ' + byType('繁忙期')
  + ' / 早期予約割引 ' + byType('早期予約割引') + ' / 複数台割引 ' + byType('複数台割引')
  + ' / 紹介料 ' + byType('紹介料') + '）');
console.log('  テンプレート　： ' + Object.keys(templates).join(', '));
console.log('  差し込み定義　： 見積書 ' + Object.keys(cellDefs['見積書'] || {}).length
  + '項目 / 請求書 ' + Object.keys(cellDefs['請求書'] || {}).length + '項目');

/* ===================== 割引繁忙期マスタ（列ずれ＋増殖） ===================== */

console.log('\n■ 割引繁忙期マスタ（列ずれしたまま・' + discountRowCount + '行）');

check('L-1 増殖した重複を畳んで15ルールに収まる', rules.length, 15);
check('L-2 繁忙期ルールを2件復元できる', byType('繁忙期'), 2);
check('L-3 早期予約割引を3件復元できる', byType('早期予約割引'), 3);
check('L-4 複数台割引を9件復元できる', byType('複数台割引'), 9);
// INTRO_OTHER は条件が「その他月」で開始月・終了月が空のため読み込み対象外。
// 紹介料はいずれにせよ計算に使っていないので実害はない。
check('L-5 紹介料は月範囲のある1件だけ読み込む', byType('紹介料'), 1);

check('L-6 繁忙期の月が数値として読めている', (() => {
  const r = rules.filter(x => x.ruleType === '繁忙期')
    .map(x => [sandbox.toNumber_(x.startMonth), sandbox.toNumber_(x.endMonth)])
    .sort((a, b) => a[0] - b[0]);
  return r;
})(), [[5, 7], [12, 12]]);

check('L-7 早期予約割引の率が読めている', (() => {
  return rules.filter(x => x.ruleType === '早期予約割引')
    .map(x => [sandbox.toNumber_(x.startMonth), sandbox.toNumber_(x.value)])
    .sort((a, b) => a[0] - b[0]);
})(), [[1, 0.15], [3, 0.1], [8, 0.1]]);

check('L-8 複数台割引の条件と単価が読めている', (() => {
  const pick = (target, cond) => {
    const r = rules.find(x => x.ruleType === '複数台割引' && x.target === target && x.condition === cond);
    return r ? sandbox.toNumber_(r.value) : null;
  };
  return [
    pick('ノーマルエアコン', 'totalQty:5-10'),
    pick('ノーマルエアコン', 'totalQty:11-20'),
    pick('ロボ付きエアコン', 'totalQty:5-10'),
    pick('業務用エアコン', 'totalQty:2-10'),
    pick('業務用エアコン', 'totalQty:21-50')
  ];
})(), [500, 1000, 1000, 5000, 7000]);

check('L-9 列ずれを検知して警告を出している',
  warnings.some(w => w.indexOf('割引繁忙期マスタ') >= 0 && w.indexOf('列ずれ') >= 0), true);

check('L-10 旧スキーマ行（SEASON_01 等）を誤って拾っていない',
  rules.some(r => String(r.ruleId).indexOf('SEASON') === 0
    || String(r.ruleId).indexOf('DISCOUNT_') === 0
    || String(r.ruleId) === 'TRUE'), false);

/* ===================== メールテンプレートマスタ ===================== */

console.log('■ メールテンプレートマスタ（新スキーマ列が空・' + mailRowCount + '行）');

check('M-1 自社案件_見積送付を復元できる', !!templates['自社案件_見積送付'], true);
check('M-2 元請案件_見積送付を復元できる', !!templates['元請案件_見積送付'], true);
check('M-3 代表者確認依頼を復元できる', !!templates['代表者確認依頼'], true);
check('M-4 件名にトークンが含まれている',
  templates['自社案件_見積送付'].subject.indexOf('{案件名}') >= 0, true);
check('M-5 本文が空でない', templates['自社案件_見積送付'].body.length > 30, true);
check('M-6 旧スキーマ行を検知して警告を出している',
  warnings.some(w => w.indexOf('メールテンプレート') >= 0), true);

/* ===================== メニューマスタ ===================== */

console.log('■ メニューマスタ（後半に重複した旧列あり・29列）');

const byId = {};
menus.forEach(m => { byId[m.menuId] = m; });

check('N-1 主要メニューの単価が0円になっていない', [
  byId['M001'] && byId['M001'].unitPrice,
  byId['M002'] && byId['M002'].unitPrice,
  byId['M003'] && byId['M003'].unitPrice
], [9800, 15800, 15800]);

check('N-2 無効メニュー（O017）が除外されている', !!byId['O017'], false);
check('N-3 メイン／オプションの振り分け', [
  byId['M001'].menuType, byId['O002'] ? byId['O002'].menuType : null
], ['メイン', 'オプション']);
check('N-4 繁忙期加算対象が読めている', byId['M001'].busyTarget, true);
check('N-5 複数台割引対象が読めている', [
  byId['M001'].multipleDiscountTarget, byId['M003'].multipleDiscountTarget
], [true, false]);
check('N-6 表示順でソートされている',
  menus.every((m, i) => i === 0 || (menus[i - 1].sortOrder || 9999) <= (m.sortOrder || 9999)), true);

const requireCheck = menus.filter(m => m.requireCheck);
note('要確認事項つきメニュー： ' + (requireCheck.length
  ? requireCheck.map(m => m.menuId + '（' + String(m.requireCheck).slice(0, 30) + '）').join(' / ')
  : 'なし'));

const priceless = menus.filter(m => sandbox.isBlank_(m.unitPriceRaw));
note('単価未設定の有効メニュー： ' + (priceless.length ? priceless.map(m => m.menuId).join(', ') : 'なし'));

const vacancy = menus.filter(m => String(m.name).indexOf('空室') >= 0 || String(m.category).indexOf('空室') >= 0);
note('空室清掃の繁忙期加算額： ' + (vacancy.length
  ? vacancy.map(m => m.menuId + '=' + m.busySurchargeRaw).join(', ') : '該当なし'));

/* ===================== 差し込みセル定義 vs 実テンプレート ===================== */

console.log('■ 差し込みセル定義と実テンプレートの突き合わせ');

const tplEst = templateSs.getSheetByName('一時作業用/見積書');
const tplInv = templateSs.getSheetByName('一時作業用/請求書');

function cellText(sheet, a1) {
  const p = parseA1(a1);
  return String(sheet._cell(p.row, p.col) ?? '').trim();
}

// 定義は正規化後の値を使う（実マスタはまだ旧定義のまま）
const defaultDefs = {};
sandbox.getDefaultCellDefinitionRows_().forEach(r => {
  if (!defaultDefs[r[0]]) defaultDefs[r[0]] = {};
  defaultDefs[r[0]][r[2]] = r[4];
});

check('D-1 見積書の合計ラベル位置にテンプレートの文字がある',
  cellText(tplEst, defaultDefs['見積書'].total_amount_label), 'お見積金額');
check('D-2 請求書の合計ラベル位置', cellText(tplInv, defaultDefs['請求書'].total_amount_label), 'ご請求金額');
check('D-3 単位セルにテンプレートの「円」がある（旧定義のD19ではない）', [
  cellText(tplEst, defaultDefs['見積書'].total_amount_unit),
  cellText(tplInv, defaultDefs['請求書'].total_amount_unit)
], ['円', '円']);
check('D-4 旧定義のD19は空（ここに書くと位置がずれる）',
  [cellText(tplEst, 'D19'), cellText(tplInv, 'D19')], ['', '']);
check('D-5 明細見出しの位置', [
  cellText(tplEst, defaultDefs['見積書'].detail_header_qty),
  cellText(tplEst, defaultDefs['見積書'].detail_header_unit_price),
  cellText(tplEst, defaultDefs['見積書'].detail_header_amount)
], ['数　量', '単　価', '金　額']);
check('D-6 小計・消費税・合計のラベル位置（見積書）', [
  cellText(tplEst, 'E39'), cellText(tplEst, 'E40'), cellText(tplEst, 'E41')
], ['小　計', '消費税', '合　計']);
check('D-7 小計・消費税・合計のラベル位置（請求書）', [
  cellText(tplInv, 'E39'), cellText(tplInv, 'E40'), cellText(tplInv, 'E41')
], ['小　計', '消費税(10%)', '合　計']);
check('D-8 請求書A41がお支払い期限の見出し', cellText(tplInv, 'A41'), 'お支払い期限：');
check('D-9 payment_due の位置が見出しの右隣で空セル',
  [defaultDefs['請求書'].payment_due, cellText(tplInv, 'B41')], ['B41', '']);
check('D-10 請求書の備考範囲が41行目を含まない',
  defaultDefs['請求書'].remarks.indexOf('41') < 0, true);
check('D-11 明細範囲の最終行がテンプレートの式の最終行と一致（請求書F38）',
  [defaultDefs['請求書'].detail_amount_range, tplInv._rows.length >= 38], ['F22:F38', true]);
check('D-12 タイトルセル', [cellText(tplEst, 'A5'), cellText(tplInv, 'A5')],
  ['御  見  積  書', '御  請  求  書']);

/* ===================== 実マスタでの自動判定 ===================== */

console.log('■ 実マスタでの自動判定（受入テストC・D相当）');

const ctx = sandbox.buildContextFromSheets_();
const engine = sandbox.getCalcEngine_();

function calcLive(payload, overrides) {
  const c = Object.assign({}, sandbox.buildCalcContext_(ctx), overrides || {});
  return engine.calculate(payload, c);
}

const AUTO = { autoDiscountEnabled: true };

check('A-1 5月メイン1台 → 繁忙期3,300',
  calcLive({ workDate: '2026-05-20', details: [{ menuId: 'M001', qty: 1 }] }).busyAmount, 3300);
check('A-2 7月メイン20台 → 66,000',
  calcLive({ workDate: '2026-07-10', details: [{ menuId: 'M001', qty: 20 }] }).busyAmount, 66000);
check('A-3 12月は繁忙期',
  calcLive({ workDate: '2026-12-05', details: [{ menuId: 'M001', qty: 1 }] }).busyAuto, true);
check('A-4 8月は繁忙期でない',
  calcLive({ workDate: '2026-08-05', details: [{ menuId: 'M001', qty: 1 }] }).busyAuto, false);
check('A-5 1月 早期予約15%',
  calcLive({ workDate: '2026-01-20', details: [{ menuId: 'M001', qty: 1 }] }, AUTO).autoDiscountApplied, 1470);
check('A-6 11月 ノーマル5台 → 2,500',
  calcLive({ workDate: '2026-11-20', details: [{ menuId: 'M001', qty: 5 }] }, AUTO).autoDiscountApplied, 2500);
check('A-7 11月 ロボ5台 → 5,000',
  calcLive({ workDate: '2026-11-20', details: [{ menuId: 'M002', qty: 5 }] }, AUTO).autoDiscountApplied, 5000);
check('A-8 納品時の既定（自動割引OFF）では0円',
  calcLive({ workDate: '2026-01-20', details: [{ menuId: 'M001', qty: 1 }] }).autoDiscountApplied, 0);
check('A-9 OFFでも候補金額は出せる',
  calcLive({ workDate: '2026-01-20', details: [{ menuId: 'M001', qty: 1 }] }).autoDiscountCandidate, 1470);

note('設定マスタの auto_discount_enabled： ' + (settings['自動割引有効'] || '(未設定)')
  + ' → ' + (ctx.autoDiscountEnabled ? '有効' : '無効'));
note('税率： ' + ctx.taxRate + ' / 繁忙期加算： ' + ctx.busySurcharge + '（' + ctx.busySurchargeUnit + '）');

/* ===================== キャッシュ ===================== */

console.log('■ マスタキャッシュ');

sandbox.clearContextCache_();
const cold = sandbox.loadContext_();
check('K-1 1回目はシートを実読みする', cold.fromCache, false);

// const 宣言は vm のグローバルオブジェクトに載らないので式として取り出す
vm.runInContext('RUNTIME.context = null;', sandbox);
const warm = sandbox.loadContext_();
check('K-2 2回目はキャッシュから返る', warm.fromCache, true);
check('K-3 キャッシュ経由でもメニュー数が一致', warm.menus.length, cold.menus.length);
check('K-4 キャッシュ経由でもルール数が一致', warm.discountRules.length, cold.discountRules.length);
check('K-5 キャッシュ経由でも金額が一致', (() => {
  const a = engine.calculate({ workDate: '2026-05-20', details: [{ menuId: 'M001', qty: 3 }] }, sandbox.buildCalcContext_(cold));
  const b = engine.calculate({ workDate: '2026-05-20', details: [{ menuId: 'M001', qty: 3 }] }, sandbox.buildCalcContext_(warm));
  return a.grandTotal === b.grandTotal && a.grandTotal > 0;
})(), true);

const chunks = Object.keys(cacheStore).filter(k => /_\d+$/.test(k)).length;
note('キャッシュ分割数： ' + chunks + 'チャンク（1チャンク上限3万文字）');

/* ===================== 読み込み中に書き込んでいないこと ===================== */

console.log('■ 副作用（画面ロードでマスタを書き換えていないこと）');

const writes = [];
Object.keys(masterSs._sheets).forEach(name => {
  const sh = masterSs._sheets[name];
  if (sh._writes.length) writes.push(name + ': ' + sh._writes.length + '件');
});

check('S-1 マスタ読み込みで1セルも書き込んでいない', writes, []);
check('S-2 マスタ読み込みでclearContentもしていない',
  Object.keys(masterSs._sheets).reduce((n, k) => n + masterSs._sheets[k]._clears.length, 0), 0);

/* ===================== 結果 ===================== */

if (notes.length) {
  console.log('\n■ 参考情報');
  notes.forEach(n => console.log('  ・' + n));
}

console.log('');
if (failures.length === 0) {
  console.log(`✅ 全 ${pass} ケース合格`);
  process.exit(0);
}

console.log(`❌ ${failures.length} 件失敗 / ${pass} 件合格\n`);
failures.forEach(f => console.log('  ✗ ' + f + '\n'));
process.exit(1);
