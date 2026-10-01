/**
 * 「使い方」シートのテスト。
 *
 * ensureManualSheet_ が設定スプレッドシートに「使い方」シートを作り、
 * 必要な章がそろった本文を書き込み、タブの先頭に置くことを確かめる。
 * Apps Script のシートは、書き込まれた値と書式だけを覚える最小の偽物で代用する。
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const SRC = path.join(__dirname, '..', 'src');

/** 呼ばれた操作を記録するだけの Range。 */
function fakeRange(sheet, row, col, numRows, numCols) {
  const range = {
    setValues(values) {
      values.forEach((r, i) => {
        r.forEach((v, j) => { sheet.cells[`${row + i}:${col + j}`] = v; });
      });
      return range;
    },
    setWrap(v)              { sheet.calls.push(['setWrap', row, col, numRows, numCols, v]); return range; },
    setVerticalAlignment(v) { sheet.calls.push(['setVerticalAlignment', v]); return range; },
    setFontWeight(v)        { sheet.calls.push(['setFontWeight', row, col, numRows, numCols, v]); return range; },
    setBackground(v)        { sheet.calls.push(['setBackground', row, col, numRows, numCols, v]); return range; }
  };
  return range;
}

function fakeSheet(name) {
  const sheet = {
    name, cells: {}, calls: [], cleared: 0, frozenRows: 0, widths: {},
    getName: () => name,
    clear() { sheet.cleared++; sheet.cells = {}; return sheet; },
    getRange: (row, col, numRows, numCols) => fakeRange(sheet, row, col, numRows || 1, numCols || 1),
    setFrozenRows(n) { sheet.frozenRows = n; },
    setColumnWidth(col, w) { sheet.widths[col] = w; }
  };
  return sheet;
}

/** シートの並びと「アクティブなシート」を持つだけの偽のスプレッドシート。 */
function fakeSpreadsheet(names) {
  const sheets = names.map(fakeSheet);
  const ss = {
    sheets,
    active: null,
    getSheetByName: n => sheets.find(s => s.name === n) || null,
    insertSheet(n) { const s = fakeSheet(n); sheets.push(s); return s; },
    setActiveSheet(s) { ss.active = s; return s; },
    moveActiveSheet(pos) {
      sheets.splice(sheets.indexOf(ss.active), 1);
      sheets.splice(pos - 1, 0, ss.active);
    }
  };
  return ss;
}

function makeContext() {
  const ctx = { console };
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(path.join(SRC, 'Manual.gs'), 'utf8'), ctx, { filename: 'Manual.gs' });
  return ctx;
}

let pass = 0, fail = 0;
function t(name, actual, expected) {
  const ok = JSON.stringify(actual) === JSON.stringify(expected);
  ok ? pass++ : fail++;
  console.log((ok ? '  ok  ' : '  NG  ') + name +
    (ok ? '' : `\n        期待=${JSON.stringify(expected)} 実際=${JSON.stringify(actual)}`));
}

/** A 列の値を上から順に並べる。 */
function columnA(sheet) {
  return Object.keys(sheet.cells)
    .filter(k => k.endsWith(':1'))
    .map(k => Number(k.split(':')[0]))
    .sort((a, b) => a - b)
    .map(r => String(sheet.cells[`${r}:1`]));
}

console.log('\n--- 「使い方」シートを新しく作る ---');
{
  const ctx = makeContext();
  const ss = fakeSpreadsheet(['設定', '代理店マスタ', '送信ログ']);
  const sh = ctx.ensureManualSheet_(ss);

  t('シート名は「使い方」', sh.getName(), '使い方');
  t('タブの先頭に移動する', ss.sheets.map(s => s.name)[0], '使い方');
  t('他のシートの並びは変わらない',
    ss.sheets.map(s => s.name).slice(1), ['設定', '代理店マスタ', '送信ログ']);

  const a = columnA(sh);
  t('10 行以上書く', a.length >= 10, true);
  t('1 行目は見出し', a[0], '項目');
  t('見出しに「一括作成」を含む', a.some(v => v.indexOf('一括作成') >= 0), true);
  t('見出しに「マスタ」を含む',   a.some(v => v.indexOf('マスタ') >= 0), true);
  t('見出しに「トラブル」を含む', a.some(v => v.indexOf('トラブル') >= 0), true);
  t('説明の列も埋まっている',
    Object.keys(sh.cells).filter(k => k.endsWith(':2') && String(sh.cells[k]).trim() !== '').length >= 10, true);

  t('本文を折り返す', sh.calls.some(c => c[0] === 'setWrap' && c[5] === true), true);
  t('見出し行は太字',
    sh.calls.some(c => c[0] === 'setFontWeight' && c[1] === 1 && c[5] === 'bold'), true);
  t('見出し行に背景色',
    sh.calls.some(c => c[0] === 'setBackground' && c[1] === 1), true);
  t('章の行にも背景色（見出し以外）',
    sh.calls.filter(c => c[0] === 'setBackground' && c[1] > 1).length, ctx.MANUAL_SECTIONS_.length);
  t('見出し行を固定する', sh.frozenRows, 1);
  t('説明の列は項目の列より広い', sh.widths[2] > sh.widths[1], true);
}

console.log('\n--- 既にあれば中身を消して書き直す ---');
{
  const ctx = makeContext();
  const ss = fakeSpreadsheet(['設定', '使い方', '送信ログ']);
  const old = ss.getSheetByName('使い方');
  old.cells['50:1'] = '古い内容';

  const sh = ctx.ensureManualSheet_(ss);
  t('同じシートを使い回す', sh === old, true);
  t('いちど全部消す', sh.cleared, 1);
  t('古い内容は残らない', sh.cells['50:1'] === '古い内容', false);
  t('先頭に移動する', ss.sheets.map(s => s.name), ['使い方', '設定', '送信ログ']);
  t('シートが増えない', ss.sheets.length, 3);
}

console.log('\n--- 本文の内容 ---');
{
  const ctx = makeContext();
  const text = JSON.stringify(ctx.MANUAL_SECTIONS_);
  t('メニュー項目の名前を実物どおりに書いている',
    ['作成済みの帳票を調べ直す', '一括入力シートを準備する', '取り込みシートを準備する',
     '取り込みシートから流し込む', '① 保存先を下見する', '② 未作成の行をすべて作成する',
     '一括入力シートをリセットする', '利用者を共有フォルダに招待する', '募集人の選択肢を作り直す']
      .filter(m => text.indexOf(m) < 0), []);
  t('状態の名前を実物どおりに書いている',
    ['下見OK', '既存に保存', '要確認', '作成済', 'エラー'].filter(s => text.indexOf(s) < 0), []);
  t('画面のボタン名を実物どおりに書いている',
    ['内容を確認する', 'PDFを作成して保存', '意向を手入力する'].filter(s => text.indexOf(s) < 0), []);
  t('文体は「です・ます」（「である」を使わない）', text.indexOf('である。') < 0, true);
}

console.log(`\n合計 ${pass + fail} 件 / 成功 ${pass} / 失敗 ${fail}`);
process.exit(fail ? 1 : 0);
