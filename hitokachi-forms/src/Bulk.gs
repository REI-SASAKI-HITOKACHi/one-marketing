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
var STATUS_EXISTING    = '既存に保存';
var STATUS_NEEDS_CHECK = '要確認';
var STATUS_DONE        = '作成済';
var STATUS_ERROR       = 'エラー';

var ROW_COLORS = {};
ROW_COLORS[STATUS_PENDING]     = null;
ROW_COLORS[STATUS_READY]       = '#e8f0fe';  // 新規フォルダ
ROW_COLORS[STATUS_EXISTING]    = '#fff4d6';  // 既存フォルダ。目を通してから実行する
ROW_COLORS[STATUS_NEEDS_CHECK] = '#ffe8cc';
ROW_COLORS[STATUS_DONE]        = '#e7f4ec';
ROW_COLORS[STATUS_ERROR]       = '#fdecea';

/** 6分の実行時間制限に対する余裕。これを超えたら中断して続きを予約する。 */
var BULK_BUDGET_MS = 4.5 * 60 * 1000;
var RESUME_FUNCTION = 'resumeBulk';
var PROP_RESUME_ROWS = 'BULK_RESUME_ROWS';

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
    .addItem('取り込みシートを準備する', 'prepareImportSheet')
    .addItem('取り込みシートから流し込む', 'importFromStagingSheet')
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
          : (f.type === 'agency' || f.type === 'agent' || f.type === 'coAgent') ? 'list'
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
  if (f.type === 'coAgent') {
    // 一括では代理店ごとに選択肢を変えられないので、全代理店の相方をまとめて出す。
    var all = [];
    getAgencies_().forEach(function (a) {
      (a.coAgents || []).forEach(function (n) { if (all.indexOf(n) < 0) all.push(n); });
    });
    return all;
  }
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
  [STATUS_READY, STATUS_EXISTING, STATUS_NEEDS_CHECK, STATUS_DONE, STATUS_ERROR].forEach(function (s) {
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
    if (v && v.url) {
      // フォルダ名に " が含まれると数式が壊れる。数式内では "" が1つの " を表す。
      var text = String(v.text).replace(/"/g, '""');
      cell.setFormula('=HYPERLINK("' + v.url + '","' + text + '")');
    } else {
      cell.clearContent();
    }
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
    if (v.destination.status === 'match') {
      counts.existing++;
      counts.ready++;
      writeRow_(sh, r.row, STATUS_EXISTING, judgeSummary_(v.judgment, v.advice)
        + '／既存フォルダ「' + v.destination.candidates[0].name + '」に保存します。'
        + '同姓同名の別人でないか確かめてください。');
      return;
    }
    counts.ready++;
    writeRow_(sh, r.row, STATUS_READY, judgeSummary_(v.judgment, v.advice)
      + '／新しいフォルダ「' + v.destination.newFolderName + '」を作成します');
  });

  toast_('下見しました。作成できる ' + counts.ready + ' 件'
    + '（うち既存フォルダ ' + counts.existing + ' 件）'
    + '／要確認 ' + counts.check + ' 件／エラー ' + counts.error + ' 件'
    + '／作成済 ' + counts.done + ' 件。'
    + (counts.existing
        ? '　うち ' + counts.existing + ' 件は既存の顧客フォルダに入ります（黄色の行）。'
          + '同姓同名の別人でないか確かめてから作成してください。'
        : ''));
}

function judgeSummary_(j, advice) {
  var base = j.suitable ? '適合' : '不適合（' + j.message + '）';
  if (!advice || advice.suitable) return base;
  // 帳票は「はい」で出るが、入力内容は基準を満たしていない。気づけるように添える。
  var marks = '①②③④⑤⑥';
  var ng = advice.ngKeys.map(function (k) { return marks.charAt(Number(k.replace('i', '')) - 1); });
  return base + '　※入力からは ' + ng.join('') + ' が「いいえ」です。'
    + '帳票は「はい」で出ます。変えるなら 1 件ずつのフォームで作成してください。';
}

/** 1 行を検証・判定し、保存先を解決する。書き込みは行わない。 */
function evaluateRow_(r, conf) {
  try {
    var data = applyFieldConfig_(bulkRowToData_(r.values), conf);
    var errors = validate_(data, conf);
    if (errors.length) return { error: errors.join(' ') };
    // 一括では確認画面を出せないので、回答は既定（すべて はい）のまま。
    // 「いいえ」にしたい案件は 1 件ずつのフォームで作る。
    var answers = defaultAnswers_(data);
    return {
      data: data,
      answers: answers,
      judgment: summarizeAnswers_(answers),
      advice: judge_(data, conf),
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
  PropertiesService.getScriptProperties().deleteProperty(PROP_RESUME_ROWS);
  processBulk_(null);
}

/** シート上で選択している行だけを処理する。担当者が自分の分だけ流すときに使う。 */
function runBulkSelected() {
  var sh = bulkSheetOrThrow_();
  // getActiveRangeList はアクティブシートの選択を返す。別のシートを開いたまま
  // 実行すると、その行番号が一括入力シートの行として処理されてしまう。
  var active = SpreadsheetApp.getActiveSheet();
  if (!active || active.getSheetId() !== sh.getSheetId()) {
    return toast_('「一括入力」シートを開いて、作成したい行を選んでから実行してください。');
  }
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

/**
 * 中断した続きが自動で呼ばれる入口。
 * 「選択した行だけ」で始まった実行は、その範囲を引き継ぐ。引き継がないと
 * 担当者が保留していた他人の行まで作りにいく。
 */
function resumeBulk() {
  clearResumeTriggers_();
  var raw = PropertiesService.getScriptProperties().getProperty(PROP_RESUME_ROWS);
  var onlyRows = null;
  if (raw) {
    try { onlyRows = JSON.parse(raw); } catch (e) { onlyRows = null; }
  }
  processBulk_(onlyRows);
}

/**
 * 実行本体。
 * 6 分の制限に当たる前に切り上げ、残りがあれば 1 分後の続きを予約する。
 * 進捗は状態列そのものなので、途中で止まっても取りこぼさない。
 */
function processBulk_(onlyRows) {
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(10000)) {
    // 手動実行と再開が重なった場合。ここで諦めると残りの行が誰にも気づかれず放置される。
    scheduleResume_(onlyRows);
    return toast_('ほかの実行が動いています。1分後に自動でやり直します。');
  }

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

      // 既存フォルダへの保存は、下見で一度画面に出したものだけを通す。
      // 1件ずつのフォームなら確認画面を出せるが、一括では出せないため。
      if (v.destination.status === 'match' && r.status !== STATUS_EXISTING) {
        writeRow_(sh, r.row, STATUS_EXISTING, judgeSummary_(v.judgment, v.advice)
          + '／既存フォルダ「' + v.destination.candidates[0].name + '」に保存しようとしています。'
          + '同姓同名の別人でないか確かめて、もう一度実行してください。');
        skipped++;
        continue;
      }

      var result;
      try {
        var choice = v.destination.status === 'match' ? v.destination.candidates[0].id : 'new';
        result = generateAndSave_(v.data, choice, v.answers);
      } catch (e) {
        writeRow_(sh, r.row, STATUS_ERROR, e.message);
        failed++;
        SpreadsheetApp.flush();
        continue;
      }

      // ここまで来たら PDF は Drive にある。以降の失敗で「エラー」にすると
      // 再実行で二重に作られるため、状態は必ず「作成済」にする。
      made++;
      try {
        writeRow_(sh, r.row, STATUS_DONE,
          judgeSummary_(v.judgment, v.advice) + '／' + result.folderName
            + (result.folderCreated ? '（新規作成）' : '（既存）')
            + (result.logWarning ? '　' + result.logWarning : ''),
          [
            { url: result.folderUrl,     text: result.folderName },
            { url: result.files[0].url,  text: '適合性確認シート' },
            { url: result.files[1].url,  text: '意向把握シート' }
          ]);
      } catch (e) {
        try { sh.getRange(r.row, COL_STATUS, 1, 2).setValues([[STATUS_DONE,
          'PDFは作成済み。結果の書き込みに失敗（' + e.message + '）']]); } catch (e2) {}
      }
      SpreadsheetApp.flush();
    }

    var msg = made + ' 件作成しました。'
      + (failed ? 'エラー ' + failed + ' 件。' : '')
      + (skipped ? '要確認 ' + skipped + ' 件。' : '');
    if (remaining > 0) {
      scheduleResume_(onlyRows);
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

function scheduleResume_(onlyRows) {
  clearResumeTriggers_();
  var props = PropertiesService.getScriptProperties();
  if (onlyRows) props.setProperty(PROP_RESUME_ROWS, JSON.stringify(onlyRows));
  else props.deleteProperty(PROP_RESUME_ROWS);
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
  PropertiesService.getScriptProperties().deleteProperty(PROP_RESUME_ROWS);
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

/* ------------------------------------------------------------------ *
 * 取り込み
 *
 * 過去の帳票から起こしたデータを外から流し込む口。
 * 「一括入力」シートに直接貼らせると、列の並びがズレたときに気づけないまま
 * 別の項目へ値が入る。そこで、いったん「取り込み」シートに貼ってもらい、
 * 見出しの文字列で列を突き合わせてから流し込む。位置ではなく名前で照合するので、
 * 列の順番が違っても、余分な列があっても正しく入る。
 * ------------------------------------------------------------------ */

var SHEET_IMPORT = '取り込み';

/** 貼り付け用の空シートを用意する。 */
function prepareImportSheet() {
  var ss = settingsSpreadsheet_();
  var sh = ss.getSheetByName(SHEET_IMPORT) || ss.insertSheet(SHEET_IMPORT);
  if (sh.getLastRow() === 0) {
    sh.getRange(1, 1).setValue('ここに、見出し行を含めて貼り付けてください');
    sh.getRange(1, 1).setFontStyle('italic').setFontColor('#888888');
  }
  sh.getRange(1, 1).setNote(
    '過去データの取り込み用シートです。\n\n'
    + '1. 取り込みたい表を、見出し行を含めて A1 から貼り付ける\n'
    + '2. メニュー →「取り込みシートから流し込む」\n\n'
    + '見出しの文字列で「一括入力」シートの列と突き合わせるので、\n'
    + '列の順番が違っていても、余分な列があっても構いません。\n'
    + '対応する列がない見出しは、流し込みの前に一覧で知らせます。');
  ss.setActiveSheet(sh);
  toast_('「取り込み」シートを用意しました。見出し行を含めて A1 から貼り付けてください。');
  return sh;
}

/**
 * 「取り込み」シートの内容を「一括入力」シートの末尾に足す。
 * 見出しが一致しない列があれば、何も書かずに中止して知らせる。
 */
function importFromStagingSheet() {
  var ss = settingsSpreadsheet_();
  var src = ss.getSheetByName(SHEET_IMPORT);
  if (!src || src.getLastRow() < 2) {
    return toast_('「取り込み」シートにデータがありません。'
      + 'メニューの「取り込みシートを準備する」から、見出し行を含めて貼り付けてください。');
  }
  var dest = bulkSheetOrThrow_();

  var srcValues = src.getDataRange().getValues();
  var srcHeader = srcValues[0].map(function (h) { return normalizeHeader_(h); });

  var destLastCol = dest.getLastColumn();
  var destLabels  = dest.getRange(BULK_HEADER_ROW, 1, 1, destLastCol).getValues()[0];
  var destKeys    = dest.getRange(BULK_KEY_ROW, 1, 1, destLastCol).getValues()[0].map(String);

  // 見出しの文字列 → 一括入力シートの列番号
  var labelToCol = {};
  destLabels.forEach(function (label, i) {
    var n = normalizeHeader_(label);
    if (n) labelToCol[n] = i + 1;
  });

  var mapping = [];   // { srcCol, destCol, isCheck }
  var unknown = [];
  srcHeader.forEach(function (h, i) {
    if (!h) {
      // 見出しが空でも、その列にデータがあれば貼り付けがずれている可能性が高い。
      // 黙って捨てず、対応する列がない場合と同じく中止する。
      var hasData = srcValues.slice(1).some(function (row) {
        return String(row[i] == null ? '' : row[i]).trim() !== '';
      });
      if (hasData) unknown.push('(見出しが空の列 ' + (i + 1) + ' 列目)');
      return;
    }
    var col = labelToCol[h];
    if (!col) { unknown.push(srcValues[0][i]); return; }
    mapping.push({ srcCol: i, destCol: col, isCheck: isCheckColumn_(destKeys[col - 1]) });
  });

  if (unknown.length) {
    return alertOrToast_('取り込みを中止しました。\n\n'
      + '次の見出しに対応する列が「一括入力」シートにありません。\n\n'
      + '　' + unknown.join('\n　') + '\n\n'
      + '「一括入力シートを準備する」を実行して列を作り直すか、'
      + '取り込み側の見出しを直してから、もう一度実行してください。');
  }
  if (!mapping.length) return toast_('突き合わせられる列がありませんでした。見出し行が1行目にあるか確認してください。');

  // 既にある行の「契約者氏名＋確認日」を控えて、二重取り込みを弾く。
  // 気づかず2回流し込むと、全顧客のフォルダに同じ帳票が2セットできる。
  var existing = {};
  readBulkRows_(dest).forEach(function (row) {
    existing[importKey_(row.values)] = true;
  });

  // getLastRow() は先回りで入れたチェックボックス（値 false）まで拾って膨らむ。
  // 実データの最終行から続けないと、書式も入力規則も条件付き書式もない領域に落ちる。
  var lastDataRow = readBulkRows_(dest).reduce(function (m, row) {
    return Math.max(m, row.row);
  }, BULK_FIRST_ROW - 1);
  var startRow = lastDataRow + 1;

  var grid = [];
  var duplicates = [];

  for (var r = 1; r < srcValues.length; r++) {
    var srcRow = srcValues[r];
    if (String(srcRow.join('')).trim() === '') continue;

    var out = new Array(destLastCol).fill('');
    mapping.forEach(function (m) {
      var v = srcRow[m.srcCol];
      out[m.destCol - 1] = m.isCheck ? isTrue_(v) : v;
    });
    // 状態は必ず未処理から始める。取り込んだだけで作成済みにはしない。
    out[COL_STATUS - 1] = '';

    var pairs = {};
    destKeys.forEach(function (k, i) { pairs[k] = out[i]; });
    var key = importKey_(pairs);
    if (existing[key]) { duplicates.push(pairs.customerName); continue; }
    existing[key] = true;
    grid.push(out);
  }

  if (!grid.length) {
    return alertOrToast_('取り込める行がありませんでした。'
      + (duplicates.length ? '\n\n' + duplicates.length + ' 件は既に取り込み済みです（契約者氏名と確認日が同じ行があります）。' : ''));
  }

  dest.getRange(startRow, 1, grid.length, destLastCol).setValues(grid);

  // 追加した行にも書式・入力規則・条件付き書式を効かせる。
  var cols = bulkColumns_();
  var totalRows = startRow - BULK_FIRST_ROW + grid.length + 20;
  applyBulkColumnFormats_(dest, cols, totalRows);
  applyBulkStatusColors_(dest, destLastCol, totalRows);
  // insertCheckboxes は値を false にするので、貼り直したあとに書き戻す。
  dest.getRange(startRow, 1, grid.length, destLastCol).setValues(grid);

  // 同じシートをもう一度流し込む事故を防ぐため、取り込み元を空にする。
  src.clear();
  prepareImportSheet();

  ss.setActiveSheet(dest);
  toast_(grid.length + ' 件を「一括入力」シートの ' + startRow + ' 行目から追加しました。'
    + '　突き合わせた列は ' + mapping.length + ' 列です。'
    + (duplicates.length ? '　既に取り込み済みの ' + duplicates.length + ' 件は飛ばしました。' : '')
    + '　「① 保存先を下見する」で内容を確かめてください。');
}

/** 取り込みの重複判定に使う鍵。同じ顧客・同じ確認日なら同一とみなす。 */
function importKey_(values) {
  var d = values.confirmDate;
  var date = isDate_(d) ? Utilities.formatDate(d, 'Asia/Tokyo', 'yyyy-MM-dd')
    : String(d == null ? '' : d).trim();
  return normalizeName_(values.customerName) + '|' + date;
}

/** 見出しの表記ゆれを吸収する。全角空白や前後の空白で一致しなくなるのを防ぐ。 */
function normalizeHeader_(h) {
  var s = String(h == null ? '' : h);
  if (String.prototype.normalize) s = s.normalize('NFKC');
  return s.replace(/[\s　]+/g, '').trim();
}

function isCheckColumn_(key) {
  if (!key || key.indexOf('__') === 0) return false;
  if (key.indexOf(':') > 0) return true; // 複数選択を展開した列
  var f = fieldByKey_(key);
  return !!(f && f.type === 'check');
}

/** ダイアログが出せる場面ならダイアログ、無理ならトーストで知らせる。 */
function alertOrToast_(message) {
  try {
    SpreadsheetApp.getUi().alert(message);
  } catch (e) {
    toast_(message);
  }
}
