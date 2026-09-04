/**
 * 設定スプレッドシートの読み書き。
 *
 * 運用者がコードを触らずに変えられるものは、すべてここを経由して読む。
 *   設定       … 全体設定（キー・値）
 *   代理店マスタ … 代理店名 → 共有フォルダID
 *   募集人マスタ … 募集人の氏名・連絡先・所属代理店
 *   項目設定   … 各入力項目を form / fixed / hidden のどれで扱うか
 *   利用者     … このウェブアプリを使えるGoogleアカウント
 */

var PROP_SETTINGS_ID = 'SETTINGS_SPREADSHEET_ID';

/**
 * 「項目設定」シートの扱い列。シート上は日本語で見せ、コードの中では
 * form / fixed / hidden で扱う。英語表記の古いシートもそのまま読める。
 */
var MODE_LABELS = {
  form:   '入力する',
  fixed:  '固定値を使う',
  hidden: '使わない'
};

var MODE_FROM_LABEL = {
  '入力する': 'form', '固定値を使う': 'fixed', '使わない': 'hidden',
  'form': 'form', 'fixed': 'fixed', 'hidden': 'hidden'
};

var SHEET_SETTINGS = '設定';
var SHEET_AGENCIES = '代理店マスタ';
var SHEET_AGENTS   = '募集人マスタ';
var SHEET_FIELDS   = '項目設定';
var SHEET_USERS    = '利用者';
var SHEET_LOG      = '送信ログ';

function settingsSpreadsheet_() {
  var id = PropertiesService.getScriptProperties().getProperty(PROP_SETTINGS_ID);
  if (!id) {
    throw new Error(
      'セットアップが済んでいません。Apps Script エディタで setup() を一度実行してください。');
  }
  return SpreadsheetApp.openById(id);
}

function sheetOrThrow_(name) {
  var sh = settingsSpreadsheet_().getSheetByName(name);
  if (!sh) throw new Error('設定スプレッドシートに「' + name + '」シートがありません。setup() を再実行してください。');
  return sh;
}

/** 見出し行つきシートをオブジェクト配列で読む。 */
function readTable_(name) {
  var values = sheetOrThrow_(name).getDataRange().getValues();
  if (values.length < 2) return [];
  var header = values[0];
  var rows = [];
  for (var r = 1; r < values.length; r++) {
    var row = values[r];
    // どのシートも1列目がキー。空ならまだ書かれていない行なので飛ばす
    // （チェックボックスだけ入った行を拾わないため）。
    if (String(row[0] == null ? '' : row[0]).trim() === '') continue;
    var o = {};
    for (var c = 0; c < header.length; c++) {
      if (header[c] !== '') o[String(header[c])] = row[c];
    }
    rows.push(o);
  }
  return rows;
}

function isTrue_(v) {
  if (v === true) return true;
  var s = String(v == null ? '' : v).trim().toLowerCase();
  return s === 'true' || s === '1' || s === 'はい' || s === '有効' || s === 'yes' || s === '○';
}

/** 「設定」シートの単一値。 */
function getSetting_(key, fallback) {
  var rows = readTable_(SHEET_SETTINGS);
  for (var i = 0; i < rows.length; i++) {
    if (String(rows[i]['キー']).trim() === key) {
      var v = rows[i]['値'];
      return (v === '' || v == null) ? fallback : v;
    }
  }
  return fallback;
}

function getAgencies_() {
  return readTable_(SHEET_AGENCIES)
    .filter(function (r) { return isTrue_(r['有効']) && String(r['代理店名']).trim() !== ''; })
    .map(function (r) {
      return {
        name: String(r['代理店名']).trim(),
        folderId: String(r['共有フォルダID']).trim(),
        // 共同募集の相方。その代理店側の募集人を読点・カンマ区切りで並べる。
        // 空欄なら単独募集だけの代理店。
        coAgents: String(r['代理店側の募集人'] || '').split(/[,、\n]/)
          .map(function (x) { return x.trim(); })
          .filter(function (x) { return x !== ''; })
      };
    });
}

function getAgencyByName_(name) {
  var list = getAgencies_();
  for (var i = 0; i < list.length; i++) if (list[i].name === name) return list[i];
  return null;
}

function getAgents_() {
  return readTable_(SHEET_AGENTS)
    .filter(function (r) { return isTrue_(r['有効']) && String(r['氏名']).trim() !== ''; })
    .map(function (r) {
      return {
        name:     String(r['氏名']).trim(),
        email:    String(r['メールアドレス'] || '').trim(),
        tel:      String(r['電話番号'] || '').trim(),
        zip:      String(r['郵便番号'] || '').trim(),
        address1: String(r['住所1'] || '').trim(),
        address2: String(r['住所2'] || '').trim(),
        agency:   String(r['所属代理店'] || '').trim(),
        loginEmail: String(r['ログイン用アドレス'] || '').trim()
      };
    });
}

function getAgentByName_(name) {
  var list = getAgents_();
  for (var i = 0; i < list.length; i++) if (list[i].name === name) return list[i];
  return null;
}

/**
 * 項目設定を { key: {mode, fixedValue} } で返す。
 * シートに行がない項目は FIELD_DEFS の defaultMode を使う。
 */
function getFieldConfig_() {
  var conf = {};
  FIELD_DEFS.forEach(function (f) {
    conf[f.key] = { mode: f.defaultMode || 'form', fixedValue: '' };
  });
  readTable_(SHEET_FIELDS).forEach(function (r) {
    var key = String(r['項目キー']).trim();
    if (!conf[key]) return;
    // 見出しは「扱い」。英語表記だった頃の「モード」列も読めるようにしておく。
    var raw = r['扱い'] != null && r['扱い'] !== '' ? r['扱い'] : r['モード'];
    var mode = MODE_FROM_LABEL[String(raw == null ? '' : raw).trim()];
    if (mode) conf[key].mode = mode;
    conf[key].fixedValue = r['固定値'] == null ? '' : r['固定値'];
  });
  return conf;
}

/** 利用を許可されたメールアドレス（小文字）の配列。 */
function getAllowedEmails_() {
  return readTable_(SHEET_USERS)
    .filter(function (r) { return isTrue_(r['有効']); })
    .map(function (r) { return String(r['メールアドレス']).trim().toLowerCase(); })
    .filter(function (e) { return e !== ''; });
}
