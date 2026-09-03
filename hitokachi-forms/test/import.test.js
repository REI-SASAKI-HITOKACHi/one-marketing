/**
 * 過去データ取り込みの往復テスト。
 *
 * tools/build-bulk-import.js が出した TSV を「取り込み」シートに貼り、
 * メニューから「一括入力」シートへ流し込み、そこから帳票データに戻すまでを通す。
 * 列がズレて別の項目に値が入る事故が一番怖いので、ここを厚く見る。
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const { execFileSync } = require('child_process');

const ROOT = path.join(__dirname, '..');
const SRC = path.join(ROOT, 'src');
const TMP = path.join(__dirname, '.tmp');

/* ---------- スプレッドシートの最小実装 ---------- */

class FakeSheet {
  constructor(name, grid) {
    this.name = name;
    this.grid = grid || [];
    this.notes = {};
    this.width = this.grid.reduce((w, r) => Math.max(w, r.length), 0);
  }
  _ensure(rows, cols) {
    while (this.grid.length < rows) this.grid.push([]);
    this.width = Math.max(this.width, cols);
    this.grid.forEach(r => { while (r.length < this.width) r.push(''); });
  }
  getLastRow() {
    for (let i = this.grid.length - 1; i >= 0; i--) {
      if (this.grid[i].some(c => c !== '' && c !== null && c !== undefined)) return i + 1;
    }
    return 0;
  }
  getLastColumn() { return this.width; }
  getRange(row, col, numRows = 1, numCols = 1) {
    const sheet = this;
    return {
      getValues() {
        sheet._ensure(row + numRows - 1, col + numCols - 1);
        const out = [];
        for (let r = 0; r < numRows; r++) {
          const line = [];
          for (let c = 0; c < numCols; c++) {
            const v = sheet.grid[row - 1 + r][col - 1 + c];
            line.push(v === undefined ? '' : v);
          }
          out.push(line);
        }
        return out;
      },
      setValues(values) {
        sheet._ensure(row + values.length - 1, col + values[0].length - 1);
        values.forEach((line, r) => line.forEach((v, c) => {
          sheet.grid[row - 1 + r][col - 1 + c] = v;
        }));
        return this;
      },
      setValue(v) { return this.setValues([[v]]); },
      setNote(n) { sheet.notes[`${row},${col}`] = n; return this; },
      // 実APIの insertCheckboxes は「範囲内のセルの値をすべて false にする」。
      // ここを忠実に真似ておかないと、値が消える不具合をテストが見逃す。
      insertCheckboxes() {
        sheet._ensure(row + numRows - 1, col + numCols - 1);
        for (let r = 0; r < numRows; r++) {
          for (let c = 0; c < numCols; c++) sheet.grid[row - 1 + r][col - 1 + c] = false;
        }
        return this;
      },
      clearContent() {
        sheet._ensure(row + numRows - 1, col + numCols - 1);
        for (let r = 0; r < numRows; r++) {
          for (let c = 0; c < numCols; c++) sheet.grid[row - 1 + r][col - 1 + c] = '';
        }
        return this;
      },
      setFormula(f) { return this.setValues([[f]]); },
      setDataValidation() { return this; },
      setNumberFormat() { return this; },
      setHorizontalAlignment() { return this; },
      setVerticalAlignment() { return this; },
      setFontStyle() { return this; },
      setFontColor() { return this; },
      setFontWeight() { return this; },
      setBackground() { return this; },
      setWrap() { return this; }
    };
  }
  getDataRange() { return this.getRange(1, 1, Math.max(this.getLastRow(), 1), Math.max(this.width, 1)); }
  getSheetId() { return this.name; }
  setColumnWidth() { return this; }
  setFrozenRows() { return this; }
  setFrozenColumns() { return this; }
  hideRows() { return this; }
  showRows() { return this; }
  isRowHiddenByUser() { return false; }
  clearConditionalFormatRules() { return this; }
  setConditionalFormatRules() { return this; }
  clear() { this.grid = []; this.width = 0; return this; }
}

function makeContext(sheets) {
  const alerts = [];
  const toasts = [];
  const ctx = {
    console, alerts, toasts,
    PropertiesService: { getScriptProperties: () => ({ getProperty: () => 'id' }) },
    SpreadsheetApp: {
      openById: () => ({
        getSheetByName: name => sheets[name] || null,
        insertSheet: name => (sheets[name] = new FakeSheet(name, [])),
        setActiveSheet: () => {}
      }),
      getActive: () => ({ toast: (m) => toasts.push(m) }),
      getUi: () => ({ alert: (m) => alerts.push(m) }),
      newDataValidation: () => ({
        requireValueInList() { return this; }, setAllowInvalid() { return this; },
        build() { return {}; }
      }),
      newConditionalFormatRule: () => {
        const b = {
          whenFormulaSatisfied() { return b; }, setBackground() { return b; },
          setRanges() { return b; }, build() { return {}; }
        };
        return b;
      }
    },
    Utilities: {
      formatDate(d, tz, fmt) {
        const p = n => String(n).padStart(2, '0');
        const y = d.getFullYear(), m = p(d.getMonth() + 1), day = p(d.getDate());
        if (fmt === 'yyyy-MM-dd') return `${y}-${m}-${day}`;
        if (fmt === 'yyyyMMdd') return `${y}${m}${day}`;
        return `${y}/${m}/${day}`;
      }
    }
  };
  vm.createContext(ctx);
  for (const f of ['Fields.gs', 'Config.gs', 'Judge.gs', 'Render.gs', 'Generate.gs', 'DriveUtil.gs', 'Bulk.gs']) {
    vm.runInContext(fs.readFileSync(path.join(SRC, f), 'utf8'), ctx, { filename: f });
  }
  sheets['項目設定'] = new FakeSheet('項目設定',
    [['項目キー', '表示名', 'セクション', '扱い', '固定値', '必須', '選択肢', '備考']].concat(
      ctx.FIELD_DEFS.map(f => [f.key, f.label, f.section, ctx.MODE_LABELS[f.defaultMode || 'form'], '', !!f.required, '', ''])));
  sheets['代理店マスタ'] = new FakeSheet('代理店マスタ', [['代理店名', '共有フォルダID', '有効', '備考']]);
  sheets['募集人マスタ'] = new FakeSheet('募集人マスタ',
    [['氏名', 'メールアドレス', '電話番号', '郵便番号', '住所1', '住所2', '所属代理店', 'ログイン用アドレス', '有効']]);
  return ctx;
}

/** bulkColumns_ から「一括入力」シートの空の器を作る（prepareBulkSheet の書式抜き版）。 */
function makeBulkSheet(ctx) {
  const cols = ctx.bulkColumns_();
  const keys = ['__status', '__message'].concat(cols.map(c => c.key))
    .concat(ctx.BULK_RESULT_COLUMNS.map(c => '__result:' + c));
  const labels = ['状態', 'メッセージ'].concat(cols.map(c => c.label))
    .concat(ctx.BULK_RESULT_COLUMNS);
  return { sheet: new FakeSheet('一括入力', [keys, labels]), cols, labels };
}

let pass = 0, fail = 0;
function t(name, actual, expected) {
  const ok = JSON.stringify(actual) === JSON.stringify(expected);
  ok ? pass++ : fail++;
  console.log((ok ? '  ok  ' : '  NG  ') + name +
    (ok ? '' : `\n        期待=${JSON.stringify(expected)} 実際=${JSON.stringify(actual)}`));
}

/* ---------- 実データ相当の記録を1件用意する ---------- */

const RECORD = {
  sheetName: '加藤学様',
  customerName: '加藤学',
  confirmDateInitial: '2023-12-05',
  confirmDateFinal: '2023-12-07',
  needsInitial: { death: true, medical: true, cancer: false, education: false,
                  pension: false, business: false, welfare: false, retire: false },
  savingsInitial: '①ある方が良い',
  wishPeriod: '一生涯',
  wishAmount: '', wishPremium: '', wishOther: '',
  agency: 'ヒトカチ株式会社',
  agent: '髙橋 知史'
};

console.log('\n--- 変換ツールが TSV を出せる ---');
fs.mkdirSync(TMP, { recursive: true });
const inFile = path.join(TMP, 'records.json');
const outFile = path.join(TMP, 'import.tsv');
fs.writeFileSync(inFile, JSON.stringify([RECORD], null, 2));
execFileSync('node', [path.join(ROOT, 'tools', 'build-bulk-import.js'),
  '--in', inFile, '--out', outFile], { cwd: ROOT, stdio: 'pipe' });

const tsv = fs.readFileSync(outFile, 'utf8').trim().split('\n').map(l => l.split('\t'));
t('見出し行とデータ行が出る', tsv.length, 2);
t('先頭は状態列', tsv[0][0], '状態');
t('契約者氏名が入っている', tsv[1][2], '加藤学');

console.log('\n--- 取り込み：見出しで列を突き合わせる ---');
{
  const store = {};
  const ctx = makeContext(store);
  const { sheet: bulk } = makeBulkSheet(ctx);
  store['一括入力'] = bulk;
  store['取り込み'] = new FakeSheet('取り込み', tsv.map(r => r.slice()));

  ctx.importFromStagingSheet();

  t('中止されていない', ctx.alerts.length, 0);
  const rows = ctx.readBulkRows_(bulk);
  t('1件だけ追加された', rows.length, 1);

  const data = ctx.bulkRowToData_(rows[0].values);
  t('契約者氏名', data.customerName, '加藤学');
  t('代理店',     data.agency, 'ヒトカチ株式会社');
  t('募集人',     data.agent, '髙橋 知史');
  t('確認日',     data.confirmDate, '2023-12-05');
  t('最終確認日', data.finalDate, '2023-12-07');
  t('契約形態は個人ニーズから推定', data.contractType, '個人');
  t('ニーズが正しく戻る', data.needs, ['death', 'medical']);
  t('貯蓄部分',   data.savings, '①ある方が良い');
  t('保険期間',   data.wishPeriod, '一生涯');
  t('適合性の項目は空のまま', data.income, '');
  t('状態は未処理から始まる', rows[0].status, '');
}

console.log('\n--- 列の順番が違っても正しく入る ---');
{
  const store = {};
  const ctx = makeContext(store);
  const { sheet: bulk } = makeBulkSheet(ctx);
  store['一括入力'] = bulk;

  // 見出しごと並べ替える（実運用で列を入れ替えて貼られる状況）
  const order = tsv[0].map((_, i) => i).reverse();
  const shuffled = tsv.map(row => order.map(i => row[i]));
  store['取り込み'] = new FakeSheet('取り込み', shuffled);

  ctx.importFromStagingSheet();
  const rows = ctx.readBulkRows_(bulk);
  const data = ctx.bulkRowToData_(rows[0].values);
  t('並べ替えても契約者氏名は正しい', data.customerName, '加藤学');
  t('並べ替えてもニーズは正しい',     data.needs, ['death', 'medical']);
  t('並べ替えても確認日は正しい',     data.confirmDate, '2023-12-05');
}

console.log('\n--- 知らない見出しがあれば何も書かずに中止する ---');
{
  const store = {};
  const ctx = makeContext(store);
  const { sheet: bulk } = makeBulkSheet(ctx);
  store['一括入力'] = bulk;

  const broken = tsv.map(r => r.slice());
  broken[0][3] = '存在しない見出し';
  store['取り込み'] = new FakeSheet('取り込み', broken);

  const before = bulk.getLastRow();
  ctx.importFromStagingSheet();
  t('中止を知らせる',         ctx.alerts.length, 1);
  t('知らない見出しを名指しする', ctx.alerts[0].indexOf('存在しない見出し') >= 0, true);
  t('1行も書き込まれていない', bulk.getLastRow(), before);
}

console.log('\n--- 見出しの表記ゆれは吸収する ---');
{
  const store = {};
  const ctx = makeContext(store);
  const { sheet: bulk } = makeBulkSheet(ctx);
  store['一括入力'] = bulk;

  const spaced = tsv.map(r => r.slice());
  spaced[0] = spaced[0].map(h => '　' + h + ' '); // 前後に全角・半角の空白
  store['取り込み'] = new FakeSheet('取り込み', spaced);

  ctx.importFromStagingSheet();
  t('中止されない', ctx.alerts.length, 0);
  t('1件取り込まれる', ctx.readBulkRows_(bulk).length, 1);
}

console.log('\n--- 追記であって上書きではない ---');
{
  const store = {};
  const ctx = makeContext(store);
  const { sheet: bulk } = makeBulkSheet(ctx);
  store['一括入力'] = bulk;

  // 既に手入力された行があるとする
  const cols = ctx.bulkColumns_();
  const existing = new Array(2 + cols.length + ctx.BULK_RESULT_COLUMNS.length).fill('');
  existing[0] = '作成済';
  existing[2] = '既存 花子';
  bulk.getRange(ctx.BULK_FIRST_ROW, 1, 1, existing.length).setValues([existing]);

  store['取り込み'] = new FakeSheet('取り込み', tsv.map(r => r.slice()));
  ctx.importFromStagingSheet();

  const rows = ctx.readBulkRows_(bulk);
  t('既存の行が残っている',     rows.length, 2);
  t('既存の行は先頭のまま',     rows[0].values.customerName, '既存 花子');
  t('既存の状態も保たれる',     rows[0].status, '作成済');
  t('取り込んだ行が後ろに付く', rows[1].values.customerName, '加藤学');
}

console.log('\n--- 同じ表を2回流し込んでも二重にならない ---');
{
  const store = {};
  const ctx = makeContext(store);
  const { sheet: bulk } = makeBulkSheet(ctx);
  store['一括入力'] = bulk;

  store['取り込み'] = new FakeSheet('取り込み', tsv.map(r => r.slice()));
  ctx.importFromStagingSheet();
  t('1回目で1件入る', ctx.readBulkRows_(bulk).length, 1);

  // 取り込みシートは流し込み後に空になっているので、貼り直した状況を作る
  store['取り込み'] = new FakeSheet('取り込み', tsv.map(r => r.slice()));
  ctx.importFromStagingSheet();
  t('2回目は増えない', ctx.readBulkRows_(bulk).length, 1);
  t('飛ばしたことを知らせる',
    ctx.alerts.concat(ctx.toasts).some(m => String(m).indexOf('取り込み済み') >= 0), true);

  // 別の顧客なら入る
  const other = tsv.map(r => r.slice());
  other[1][2] = '別人 太郎';
  store['取り込み'] = new FakeSheet('取り込み', other);
  ctx.importFromStagingSheet();
  t('別の顧客は追加される', ctx.readBulkRows_(bulk).length, 2);
}

console.log('\n--- 流し込み後は取り込みシートが空になる ---');
{
  const store = {};
  const ctx = makeContext(store);
  const { sheet: bulk } = makeBulkSheet(ctx);
  store['一括入力'] = bulk;
  store['取り込み'] = new FakeSheet('取り込み', tsv.map(r => r.slice()));
  ctx.importFromStagingSheet();
  const staging = store['取り込み'];
  const rows = staging.getRange(2, 1, Math.max(staging.getLastRow() - 1, 1), 5).getValues();
  t('データ行が残っていない', rows.every(r => r.every(c => c === '' || c === undefined)), true);
}

console.log('\n--- 見出しが空の列にデータがあれば中止する ---');
{
  const store = {};
  const ctx = makeContext(store);
  const { sheet: bulk } = makeBulkSheet(ctx);
  store['一括入力'] = bulk;

  const shifted = tsv.map(r => r.slice());
  shifted[0].push('');          // 見出しだけ空
  shifted[1].push('取り残された値');
  store['取り込み'] = new FakeSheet('取り込み', shifted);

  ctx.importFromStagingSheet();
  t('中止する', ctx.alerts.length, 1);
  t('1行も書き込まれていない', ctx.readBulkRows_(bulk).length, 0);
}

fs.rmSync(TMP, { recursive: true, force: true });
console.log(`\n合計 ${pass + fail} 件 / 成功 ${pass} / 失敗 ${fail}`);
process.exit(fail ? 1 : 0);
