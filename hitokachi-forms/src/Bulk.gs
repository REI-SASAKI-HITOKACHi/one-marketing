/**
 * 一括作成。
 *
 * 設定スプレッドシートの「一括入力」シートに 1 行 1 顧客で書いて、まとめて
 * PDF を作る。適合性確認シートが求める情報（年齢・年収・投資経験など）は
 * 面談で聞くものなので成約一覧からは持ってこられない。このシートが、
 * これまで担当者の頭の中にしかなかったその情報の記録も兼ねる。
 *
 * 流れは 2 段階。
 *   1. 保存先を下見する … 検証・判定・保存先の解決だけを行う。Drive には書かない
 *   2. 作成する         … 下見の結果を見てから実行する
 *
 * 1 件ずつのフォームと違って途中で確認画面を出せないため、既存の顧客フォルダに
 * 当たる行を先に色で示して、人が目を通してから実行する形にしている。
 */

var SHEET_BULK = '一括入力';

var BULK_KEY_ROW    = 1; // 列とデータ項目の対応（非表示）
var BULK_HEADER_ROW = 2; // 人が読む見出し
var BULK_FIRST_ROW  = 3;

var COL_STATUS  = 1;
var COL_MESSAGE = 2;

var STATUS_PENDING     = '未作成';
var STATUS_READY       = '下見OK';
var STATUS_NEEDS_CHECK = '要確認';
var STATUS_DONE        = '作成済';
var STATUS_ERROR       = 'エラー';

var ROW_COLORS = {};
ROW_COLORS[STATUS_PENDING]     = null;
ROW_COLORS[STATUS_READY]       = '#e8f0fe';
ROW_COLORS[STATUS_NEEDS_CHECK] = '#ffe8cc';
ROW_COLORS[STATUS_DONE]        = '#e7f4ec';
ROW_COLORS[STATUS_ERROR]       = '#fdecea';

/** 6分の実行時間制限に対する余裕。これを超えたら中断して続きを予約する。 */
var BULK_BUDGET_MS = 4.5 * 60 * 1000;
var RESUME_FUNCTION = 'resumeBulk';

/* ------------------------------------------------------------------ *
 * メニュー
 * ------------------------------------------------------------------ */

/** 設定スプレッドシートを開いたときに呼ばれる（setup() が仕掛ける）。 */
function onOpenMenu() {
  SpreadsheetApp.getUi()
    .createMenu('帳票作成')
    .addItem('一括入力シートを準備する', 'prepareBulkSheet')
    .addSeparator()
    .addItem('① 保存先を下見する', 'dryRunBulk')
    .addItem('② 未作成の行をすべて作成する', 'runBulkAll')
    .addItem('選択した行だけ作成する', 'runBulkSelected')
    .addSeparator()
    .addItem('実行中の続きを取り消す', 'stopBulk')
    .addToUi();
}

/* ------------------------------------------------------------------ *
 * 列の組み立て
 * ------------------------------------------------------------------ */

/**
 * 一括入力シートの列定義を作る。
 * 複数選べる項目は選択肢ごとに 1 列のチェックボックスにする。打ち込むより速く、
 * 何を選んだかが一覧で見えるため。
 */
function bulkColumns_() {
  var conf = getFieldConfig_();
  var cols = [];

  var add = function (f) {
    if (conf[f.key].mode !== 'form') return;

    if (f.type === 'needs') {
      NEEDS.forEach(function (n) {
        cols.push({ key: f.key + ':' + n.key, label: 'ニーズ｜' + n.label, kind: 'check', group: f.key });
      });
      return;
    }
    if (f.type === 'multi') {
      var prefix = f.key === 'experience' ? '購入経験｜' : '保険料原資｜';
      (f.options || []).forEach(function (o) {
        cols.push({ key: f.key + ':' + o, label: prefix + o, kind: 'check', group: f.key });
      });
      return;
    }
    if (f.type === 'rows') return; // 意向の変化は1行1顧客の形に馴染まないので一括では扱わない

    cols.push({
      key: f.key,
      label: f.label + (f.unit ? '（' + f.unit + '）' : ''),
      kind: f.type === 'check' ? 'check'
          : f.type === 'date' ? 'date'
          : f.type === 'number' ? 'number'
          : (f.type === 'radio' || f.type === 'select') ? 'list'
          : (f.type === 'agency' || f.type === 'agent') ? 'list'
          : 'text',
      options: bulkOptionsFor_(f)
    });
  };

  // 契約者氏名を先頭に置く。列を固定したときにどの行か見失わないため。
  var name = fieldByKey_('customerName');
  if (name && conf[name.key].mode === 'form') add(name);
  FIELD_DEFS.forEach(function (f) { if (f.key !== 'customerName') add(f); });

  return cols;
}

function bulkOptionsFor_(f) {
  if (f.type === 'agency') return getAgencies_().map(function (a) { return a.name; });
  if (f.type === 'agent')  return getAgents_().map(function (a) { return a.name; });
  return f.options || [];
}

var BULK_RESULT_COLUMNS = ['保存先フォルダ', '適合性確認シート', '意向把握シート'];

/* ------------------------------------------------------------------ *
 * シートの準備
 * ------------------------------------------------------------------ */

/**
 * 一括入力シートを作る。既にあれば、入力済みのデータを保ったまま列を作り直す。
 * 「項目設定」を変えたあとにもう一度実行してよい。
 */
function prepareBulkSheet() {
  var ss = settingsSpreadsheet_();
  var sh = ss.getSheetByName(SHEET_BULK);
  var saved = sh ? readBulkRows_(sh) : [];

  if (!sh) sh = ss.insertSheet(SHEET_BULK);
  if (sh.getLastRow() > 0) sh.getDataRange().clearDataValidations();
  sh.clear();
  sh.clearConditionalFormatRules();
  if (sh.isRowHiddenByUser(BULK_KEY_ROW)) sh.showRows(BULK_KEY_ROW);

  var cols = bulkColumns_();
  var keys   = ['__status', '__message'].concat(cols.map(function (c) { return c.key; }))
                 .concat(BULK_RESULT_COLUMNS.map(function (c) { return '__result:' + c; }));
  var labels = ['状態', 'メッセージ'].concat(cols.map(function (c) { return c.label; }))
                 .concat(BULK_RESULT_COLUMNS);

  sh.getRange(BULK_KEY_ROW, 1, 1, keys.length).setValues([keys]);
  sh.getRange(BULK_HEADER_ROW, 1, 1, labels.length).setValues([labels])
    .setFontWeight('bold').setBackground('#efefef').setWrap(true).setVerticalAlignment('bottom');
  sh.hideRows(BULK_KEY_ROW);
  sh.setFrozenRows(BULK_HEADER_ROW);
  sh.setFrozenColumns(3); // 状態・メッセージ・契約者氏名

  var rows = saved.length + 100;
  applyBulkColumnFormats_(sh, cols, rows);
  applyBulkStatusColors_(sh, cols.length + BULK_RESULT_COLUMNS.length + 2, rows);

  if (saved.length) restoreBulkRows_(sh, cols, saved);

  sh.setColumnWidth(COL_STATUS, 76);
  sh.setColumnWidth(COL_MESSAGE, 300);
  sh.setColumnWidth(3, 130);
  sh.getRange(BULK_HEADER_ROW, 1, 1, labels.length).setNote(null);
  sh.getRange(BULK_HEADER_ROW, COL_STATUS).setNote(
    '「保存先を下見する」と「作成する」を実行すると自動で更新されます。\n直接書き換える必要はありません。');
  sh.getRange(BULK_HEADER_ROW, COL_MESSAGE).setNote(
    '判定結果やエラーの内容が入ります。エラーの行は直してから、もう一度実行してください。');

  SpreadsheetApp.getActive().toast(
    '一括入力シートを準備しました（' + cols.length + '項目）。', '帳票作成', 5);
  return sh;
}

function applyBulkColumnFormats_(sh, cols, rows) {
  cols.forEach(function (c, i) {
    var col = i + 3;
    var range = sh.getRange(BULK_FIRST_ROW, col, rows, 1);
    if (c.kind === 'check') {
      range.insertCheckboxes().setHorizontalAlignment('center');
      sh.setColumnWidth(col, 46);
    } else if (c.kind === 'date') {
      range.setNumberFormat('yyyy/MM/dd');
      sh.setColumnWidth(col, 100);
    } else if (c.kind === 'number') {
      range.setNumberFormat('#,##0');
      sh.setColumnWidth(col, 90);
    } else if (c.kind === 'list' && c.options && c.options.length) {
      range.setDataValidation(SpreadsheetApp.newDataValidation()
        .requireValueInList(c.options, true).setAllowInvalid(false).build());
      sh.setColumnWidth(col, 150);
    } else {
      sh.setColumnWidth(col, 140);
    }
  });
}

/** 状態列の値に応じて行に色を付ける。どの行が残っているか一目で分かるように。 */
function applyBulkStatusColors_(sh, totalCols, rows) {
  var range = sh.getRange(BULK_FIRST_ROW, 1, rows, totalCols);
  var rules = [];
  [STATUS_READY, STATUS_NEEDS_CHECK, STATUS_DONE, STATUS_ERROR].forEach(function (s) {
    if (!ROW_COLORS[s]) return;
    rules.push(SpreadsheetApp.newConditionalFormatRule()
      .whenFormulaSatisfied('=$A' + BULK_FIRST_ROW + '="' + s + '"')
      .setBackground(ROW_COLORS[s]).setRanges([range]).build());
  });
  sh.setConditionalFormatRules(rules);
}

/* ------------------------------------------------------------------ *
 * 読み書き
 * ------------------------------------------------------------------ */

/** シートを { row, status, values } の配列にする。 */
function readBulkRows_(sh) {
  var lastRow = sh.getLastRow();
  var lastCol = sh.getLastColumn();
  if (lastRow < BULK_FIRST_ROW || lastCol === 0) return [];

  var keys = sh.getRange(BULK_KEY_ROW, 1, 1, lastCol).getValues()[0];
  var values = sh.getRange(BULK_FIRST_ROW, 1, lastRow - BULK_FIRST_ROW + 1, lastCol).getValues();
  var out = [];

  values.forEach(function (row, i) {
    var o = {};
    var filled = false;
    keys.forEach(function (k, c) {
      k = String(k || '');
      if (!k || k.indexOf('__result:') === 0) return;
      var v = row[c];
      o[k] = v;
      if (k !== '__status' && k !== '__message' && v !== '' && v !== false && v != null) filled = true;
    });
    if (filled) out.push({ row: BULK_FIRST_ROW + i, status: String(o.__status || ''), values: o });
  });
  return out;
}

/** 列を作り直したあとに、保存しておいた値をキーで戻す。 */
function restoreBulkRows_(sh, cols, saved) {
  var lastCol = sh.getLastColumn();
  var keys = sh.getRange(BULK_KEY_ROW, 1, 1, lastCol).getValues()[0].map(String);
  var isCheck = {};
  cols.forEach(function (c) { if (c.kind === 'check') isCheck[c.key] = true; });

  var grid = saved.map(function (s) {
    return keys.map(function (k) {
      if (k === '__status')  return s.values.__status || '';
      if (k === '__message') return s.values.__message || '';
      if (k.indexOf('__result:') === 0) return '';
      var v = s.values[k];
      if (isCheck[k]) return isTrue_(v);
      return v === undefined ? '' : v;
    });
  });
  if (grid.length) sh.getRange(BULK_FIRST_ROW, 1, grid.length, lastCol).setValues(grid);
}

/** 一括入力シートの 1 行を、判定や生成に渡せる形にする。 */
function bulkRowToData_(values) {
  var data = {};
  Object.keys(values).forEach(function (k) {
    if (k.indexOf('__') === 0) return;
    var v = values[k];
    var sep = k.indexOf(':');
    if (sep < 0) {
      data[k] = isDate_(v) ? Utilities.formatDate(v, 'Asia/Tokyo', 'yyyy-MM-dd') : v;
      return;
    }
    var field = k.slice(0, sep);
    var option = k.slice(sep + 1);
    if (!data[field]) data[field] = [];
    if (isTrue_(v)) data[field].push(option);
  });
  // チェックが 1 つも入っていない複数選択項目も、空配列として持たせる。
  FIELD_DEFS.forEach(function (f) {
    if ((f.type === 'multi' || f.type === 'needs') && !data[f.key]) data[f.key] = [];
  });
  return data;
}

function writeRow_(sh, row, status, message, result) {
  sh.getRange(row, COL_STATUS, 1, 2).setValues([[status, message]]);
  if (!result) return;
  var lastCol = sh.getLastColumn();
  var keys = sh.getRange(BULK_KEY_ROW, 1, 1, lastCol).getValues()[0].map(String);
  BULK_RESULT_COLUMNS.forEach(function (name, i) {
    var col = keys.indexOf('__result:' + name);
    if (col < 0) return;
    var v = result[i];
    var cell = sh.getRange(row, col + 1);
    if (v && v.url) cell.setFormula('=HYPERLINK("' + v.url + '","' + v.text + '")');
    else cell.clearContent();
  });
}

/* ------------------------------------------------------------------ *
 * 下見
 * ------------------------------------------------------------------ */

/**
 * 検証・判定・保存先の解決までを行い、結果を書き戻す。Drive には一切書かない。
 * 既存の顧客フォルダに当たる行が色で分かるので、実行前に目視できる。
 */
function dryRunBulk() {
  var sh = bulkSheetOrThrow_();
  var rows = readBulkRows_(sh);
  if (!rows.length) return toast_('一括入力シートに行がありません。');

  var conf = getFieldConfig_();
  var counts = { ready: 0, existing: 0, check: 0, error: 0, done: 0 };

  rows.forEach(function (r) {
    if (r.status === STATUS_DONE) { counts.done++; return; }
    var v = evaluateRow_(r, conf);
    if (v.error) {
      writeRow_(sh, r.row, STATUS_ERROR, v.error);
      counts.error++;
      return;
    }
    if (v.destination.status === 'ambiguous') {
      writeRow_(sh, r.row, STATUS_NEEDS_CHECK,
        '同じ名前とみなせる顧客フォルダが ' + v.destination.candidates.length + ' 件あります。'
        + '別人の可能性があるため、この行は 1 件ずつのフォームで作成してください。');
      counts.check++;
      return;
    }
    var where = v.destination.status === 'match'
      ? '既存フォルダ「' + v.destination.candidates[0].name + '」に保存します'
      : '新しいフォルダ「' + v.destination.newFolderName + '」を作成します';
    if (v.destination.status === 'match') counts.existing++;
    counts.ready++;
    writeRow_(sh, r.row, STATUS_READY, judgeSummary_(v.judgment) + '／' + where);
  });

  toast_('下見しました。作成できる ' + counts.ready + ' 件'
    + '（うち既存フォルダ ' + counts.existing + ' 件）'
    + '／要確認 ' + counts.check + ' 件／エラー ' + counts.error + ' 件'
    + '／作成済 ' + counts.done + ' 件。'
    + (counts.existing ? '　既存フォルダに入る行に色が付いています。確認してから作成してください。' : ''));
}

function judgeSummary_(j) {
  return j.suitable ? '適合' : '不適合（' + j.message + '）';
}

/** 1 行を検証・判定し、保存先を解決する。書き込みは行わない。 */
function evaluateRow_(r, conf) {
  try {
    var data = applyFieldConfig_(bulkRowToData_(r.values), conf);
    var errors = validate_(data, conf);
    if (errors.length) return { error: errors.join(' ') };
    return {
      data: data,
      judgment: judge_(data),
      destination: resolveDestination_(data.agency, data.customerName)
    };
  } catch (e) {
    return { error: e.message };
  }
}

/* ------------------------------------------------------------------ *
 * 実行
 * ------------------------------------------------------------------ */

function runBulkAll() {
  processBulk_(null);
}

/** シート上で選択している行だけを処理する。担当者が自分の分だけ流すときに使う。 */
function runBulkSelected() {
  var sh = bulkSheetOrThrow_();
  var sel = sh.getActiveRangeList();
  if (!sel) return toast_('作成したい行を選択してから実行してください。');

  var wanted = {};
  sel.getRanges().forEach(function (range) {
    for (var i = 0; i < range.getNumRows(); i++) {
      var row = range.getRow() + i;
      if (row >= BULK_FIRST_ROW) wanted[row] = true;
    }
  });
  if (!Object.keys(wanted).length) return toast_('データ行を選択してください。');
  processBulk_(wanted);
}

/** 中断した続きが自動で呼ばれる入口。 */
function resumeBulk() {
  clearResumeTriggers_();
  processBulk_(null);
}

/**
 * 実行本体。
 * 6 分の制限に当たる前に切り上げ、残りがあれば 1 分後の続きを予約する。
 * 進捗は状態列そのものなので、途中で止まっても取りこぼさない。
 */
function processBulk_(onlyRows) {
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(10000)) return toast_('ほかの実行が動いています。終わってからもう一度実行してください。');

  try {
    var started = Date.now();
    var sh = bulkSheetOrThrow_();
    var conf = getFieldConfig_();
    var rows = readBulkRows_(sh);
    var made = 0, failed = 0, skipped = 0, remaining = 0;

    for (var i = 0; i < rows.length; i++) {
      var r = rows[i];
      if (onlyRows && !onlyRows[r.row]) continue;
      if (r.status === STATUS_DONE) continue;

      if (Date.now() - started > BULK_BUDGET_MS) {
        remaining = countPending_(rows, i, onlyRows);
        break;
      }

      var v = evaluateRow_(r, conf);
      if (v.error) {
        writeRow_(sh, r.row, STATUS_ERROR, v.error);
        failed++;
        continue;
      }
      if (v.destination.status === 'ambiguous') {
        writeRow_(sh, r.row, STATUS_NEEDS_CHECK,
          '同じ名前とみなせる顧客フォルダが ' + v.destination.candidates.length + ' 件あります。'
          + '別人の可能性があるため、この行は 1 件ずつのフォームで作成してください。');
        skipped++;
        continue;
      }

      try {
        var choice = v.destination.status === 'match' ? v.destination.candidates[0].id : 'new';
        var result = generateAndSave_(v.data, choice);
        writeRow_(sh, r.row, STATUS_DONE,
          judgeSummary_(v.judgment) + '／' + result.folderName
            + (result.folderCreated ? '（新規作成）' : '（既存）'),
          [
            { url: result.folderUrl,     text: result.folderName },
            { url: result.files[0].url,  text: '適合性確認シート' },
            { url: result.files[1].url,  text: '意向把握シート' }
          ]);
        made++;
      } catch (e) {
        writeRow_(sh, r.row, STATUS_ERROR, e.message);
        failed++;
      }
      SpreadsheetApp.flush();
    }

    var msg = made + ' 件作成しました。'
      + (failed ? 'エラー ' + failed + ' 件。' : '')
      + (skipped ? '要確認 ' + skipped + ' 件。' : '');
    if (remaining > 0) {
      scheduleResume_();
      msg += ' 残り ' + remaining + ' 件は 1 分後に自動で続きを実行します。'
           + 'このタブを閉じても構いません。';
    }
    toast_(msg);
  } finally {
    lock.releaseLock();
  }
}

function countPending_(rows, from, onlyRows) {
  var n = 0;
  for (var i = from; i < rows.length; i++) {
    if (onlyRows && !onlyRows[rows[i].row]) continue;
    if (rows[i].status !== STATUS_DONE) n++;
  }
  return n;
}

/* ------------------------------------------------------------------ *
 * 続きの予約
 * ------------------------------------------------------------------ */

function scheduleResume_() {
  clearResumeTriggers_();
  ScriptApp.newTrigger(RESUME_FUNCTION).timeBased().after(60 * 1000).create();
}

function clearResumeTriggers_() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === RESUME_FUNCTION) ScriptApp.deleteTrigger(t);
  });
}

/** 自動で続きが動くのを止める。 */
function stopBulk() {
  clearResumeTriggers_();
  toast_('予約されていた続きの実行を取り消しました。');
}

/* ------------------------------------------------------------------ *
 * 補助
 * ------------------------------------------------------------------ */

function bulkSheetOrThrow_() {
  var sh = settingsSpreadsheet_().getSheetByName(SHEET_BULK);
  if (!sh) throw new Error('「一括入力」シートがありません。メニューの「一括入力シートを準備する」を先に実行してください。');
  return sh;
}

function toast_(message) {
  try {
    SpreadsheetApp.getActive().toast(message, '帳票作成', 12);
  } catch (e) {
    Logger.log(message); // 時間主導トリガーから呼ばれたときは画面がない
  }
}
