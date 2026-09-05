#!/usr/bin/env node
/**
 * 旧コードと新コードで、マスタ読み込みに必要なスプレッドシートAPI呼び出し回数を数える。
 *
 *   node apps/estimate-app/tools/api-call-benchmark.js
 *
 * GASの遅さはほぼ「シートAPIの往復回数 × 1往復あたりの時間」で決まる。
 * 実行時間はネットワーク次第で揺れるが、往復回数は決定的に測れるので、
 * 改善が本物かどうかはこの数字で判断できる。
 *
 * 旧コードは docs/legacy-code.gs.txt（引継ぎ資料の current_code）を使う。
 * データは本番マスタの実データ（fixtures-live-master.json）。
 */
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const srcDir = path.join(__dirname, '..', 'src');
const docsDir = path.join(__dirname, '..', 'docs');
const fixtures = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures-live-master.json'), 'utf8'));

const MASTER_ID = '1HPtoKzOwwqnS6Yk_R0UHEy3u8Wpe43LrD7HlCvS6SLw';
const TEMPLATE_ID = '1s0iZGjz58SZLgpkrs-lO_EjGr8bQq6qUZB93lyx061c';

const SHEET_NAME_FIX = {
  '一時作業用見積書': '一時作業用/見積書',
  '一時作業用請求書': '一時作業用/請求書'
};

function pad(n) { return String(n).padStart(2, '0'); }

/** 呼び出し回数を数えるスタブ一式を作る。 */
function buildEnvironment() {
  const counts = { read: 0, write: 0, openById: 0, cells: 0 };

  function makeRange(sheet, row, col, numRows, numCols) {
    const readCells = () => {
      counts.read++;
      counts.cells += numRows * numCols;
      const out = [];
      for (let r = 0; r < numRows; r++) {
        const line = [];
        for (let c = 0; c < numCols; c++) line.push(sheet._cell(row + r, col + c));
        out.push(line);
      }
      return out;
    };

    return {
      getRow: () => row,
      getColumn: () => col,
      getNumRows: () => numRows,
      getNumColumns: () => numCols,
      getValues: readCells,
      getDisplayValues: () => readCells().map(r => r.map(v => v === null || v === undefined ? '' : String(v))),
      getDisplayValue() { counts.read++; counts.cells++; return String(sheet._cell(row, col) ?? ''); },
      getValue() { counts.read++; counts.cells++; return sheet._cell(row, col); },
      getCell: (r, c) => makeRange(sheet, row + r - 1, col + c - 1, 1, 1),
      setValue() { counts.write++; return this; },
      setValues() { counts.write++; return this; },
      clearContent() { counts.write++; return this; }
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
    ss.insertSheet = name => { sheets[name] = makeSheet(ss, name, { rows: [], maxRow: 0, maxCol: 0 }); return sheets[name]; };
    return ss;
  }

  const masterSs = makeSpreadsheet(MASTER_ID, '見積アプリ_マスタ入力テンプレート', fixtures.master);
  const templateSs = makeSpreadsheet(TEMPLATE_ID, '【アプリ】見積/請求書', fixtures.template);
  const cacheStore = {};

  const sandbox = {
    console: { log() {}, warn() {}, error() {} },
    JSON, Math, Date, Number, String, Object, Array, isNaN, isFinite, RegExp,

    SpreadsheetApp: {
      openById(id) {
        counts.openById++;
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
        return pattern.replace('yyyy', d.getFullYear()).replace('MM', pad(d.getMonth() + 1))
          .replace('dd', pad(d.getDate())).replace('HH', pad(d.getHours()))
          .replace('mm', pad(d.getMinutes())).replace('ss', pad(d.getSeconds()));
      },
      sleep() {}
    },

    Session: {
      getActiveUser: () => ({ getEmail: () => 'test@example.com' }),
      getEffectiveUser: () => ({ getEmail: () => 'test@example.com' })
    }
  };

  vm.createContext(sandbox);
  return { sandbox, counts, cacheStore };
}

function reset(counts) { counts.read = 0; counts.write = 0; counts.openById = 0; counts.cells = 0; }

function row(label, c) {
  return '  ' + label.padEnd(30)
    + String(c.read).padStart(7) + String(c.write).padStart(8)
    + String(c.read + c.write).padStart(8)
    + ('  ' + c.cells.toLocaleString('en-US')).padStart(14);
}

console.log('\n本番マスタの実データに対する、シートAPI呼び出し回数の比較');
console.log('（GASの所要時間はほぼ「往復回数 × 1往復の時間」で決まる）\n');
console.log('  ' + '処理'.padEnd(28) + '読み'.padStart(8) + '書き'.padStart(8)
  + '合計'.padStart(8) + '読んだセル数'.padStart(14));
console.log('  ' + '-'.repeat(66));

/* ===================== 旧コード ===================== */

const legacy = buildEnvironment();
vm.runInContext(fs.readFileSync(path.join(docsDir, 'legacy-code.gs.txt'), 'utf8'),
  legacy.sandbox, { filename: 'legacy-code.gs' });

reset(legacy.counts);
legacy.sandbox.getMenus_();
const legacyMenus = Object.assign({}, legacy.counts);

reset(legacy.counts);
legacy.sandbox.getDiscountRules_();
const legacyRules = Object.assign({}, legacy.counts);

reset(legacy.counts);
legacy.sandbox.getSettings_();
const legacySettings = Object.assign({}, legacy.counts);

// 旧 apiInit は setupInitialSheets() を毎回走らせていた
reset(legacy.counts);
legacy.sandbox.setupInitialSheets();
const legacySetup = Object.assign({}, legacy.counts);

const legacyInit = {
  read: legacyMenus.read + legacyRules.read + legacySettings.read + legacySetup.read,
  write: legacyMenus.write + legacyRules.write + legacySettings.write + legacySetup.write,
  cells: legacyMenus.cells + legacyRules.cells + legacySettings.cells + legacySetup.cells
};

console.log('  【旧コード】');
console.log(row('getMenus_()', legacyMenus));
console.log(row('getDiscountRules_()', legacyRules));
console.log(row('getSettings_()', legacySettings));
console.log(row('setupInitialSheets()', legacySetup));
console.log(row('→ 画面ロード1回ぶん（概算）', legacyInit));

/* ===================== 新コード ===================== */

const modern = buildEnvironment();
vm.runInContext(fs.readFileSync(path.join(srcDir, 'code.gs'), 'utf8'), modern.sandbox, { filename: 'code.gs' });
vm.runInContext(fs.readFileSync(path.join(srcDir, 'Invoice.gs'), 'utf8'), modern.sandbox, { filename: 'Invoice.gs' });

reset(modern.counts);
modern.sandbox.readMenus_(modern.sandbox.SpreadsheetApp.openById(MASTER_ID), []);
const modernMenus = Object.assign({}, modern.counts);

reset(modern.counts);
modern.sandbox.readDiscountRules_(modern.sandbox.SpreadsheetApp.openById(MASTER_ID), []);
const modernRules = Object.assign({}, modern.counts);

reset(modern.counts);
modern.sandbox.readSettings_(modern.sandbox.SpreadsheetApp.openById(MASTER_ID));
const modernSettings = Object.assign({}, modern.counts);

// 新コードは画面ロードでセットアップを走らせない
modern.sandbox.clearContextCache_();
vm.runInContext('RUNTIME.context = null; RUNTIME.headerInfo = {};', modern.sandbox);
reset(modern.counts);
modern.sandbox.loadContext_();
const modernCold = Object.assign({}, modern.counts);

vm.runInContext('RUNTIME.context = null; RUNTIME.headerInfo = {};', modern.sandbox);
reset(modern.counts);
modern.sandbox.loadContext_();
const modernWarm = Object.assign({}, modern.counts);

console.log('');
console.log('  【新コード】');
console.log(row('readMenus_()', modernMenus));
console.log(row('readDiscountRules_()', modernRules));
console.log(row('readSettings_()', modernSettings));
console.log(row('→ 画面ロード1回目（実読み）', modernCold));
console.log(row('→ 画面ロード2回目（キャッシュ）', modernWarm));

/* ===================== まとめ ===================== */

function ratio(before, after) {
  const b = before.read + before.write;
  const a = after.read + after.write;
  if (a === 0) return b + ' → 0（ゼロ）';
  return b + ' → ' + a + '（' + (b / a).toFixed(1) + '分の1）';
}

console.log('\n  ' + '-'.repeat(66));
console.log('  メニュー読み込み　　： ' + ratio(legacyMenus, modernMenus));
console.log('  画面ロード（実読み）： ' + ratio(legacyInit, modernCold));
console.log('  画面ロード（2回目）　： ' + ratio(legacyInit, modernWarm));
console.log('  入力中の再計算　　　： 旧はこれを1操作ごとにサーバーで実行、新はブラウザ内で0回');

console.log('\n  旧コードの書き込み ' + legacySetup.write + '件は setupInitialSheets() によるもの。');
console.log('  画面を開くたびにマスタへ追記していたため、割引繁忙期マスタが '
  + fixtures.master['割引繁忙期マスタ'].maxRow + '行まで増えた。');
console.log('  新コードはマスタ読み込み中に1件も書き込まない。\n');

const ok = modernMenus.read < legacyMenus.read
  && modernCold.write === 0
  && modernWarm.read === 0;

if (!ok) {
  console.log('❌ 期待した改善が確認できませんでした。');
  process.exit(1);
}

console.log('✅ メニュー読み込みの往復削減・書き込みゼロ・キャッシュ時の読み込みゼロを確認\n');
