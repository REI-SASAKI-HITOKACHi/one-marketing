/**
 * 初回セットアップ。
 *
 * Apps Script エディタで setup() を一度だけ実行すると、設定スプレッドシートを
 * 作って ID をスクリプトプロパティに保存する。既にある場合はシートの過不足だけ
 * 直すので、項目を追加したあとにもう一度実行して構わない。
 */

function setup() {
  var props = PropertiesService.getScriptProperties();
  var id = props.getProperty(PROP_SETTINGS_ID);
  var ss;

  if (id) {
    ss = SpreadsheetApp.openById(id);
  } else {
    ss = SpreadsheetApp.create('帳票自動作成システム 設定');
    props.setProperty(PROP_SETTINGS_ID, ss.getId());
    ss.getSheets()[0].setName(SHEET_SETTINGS);
  }

  ensureSettingsSheet_(ss);
  ensureAgenciesSheet_(ss);
  ensureAgentsSheet_(ss);
  ensureUsersSheet_(ss);
  ensureFieldsSheet_(ss);
  ensureLogSheet_(ss);

  var url = ss.getUrl();
  Logger.log('設定スプレッドシート: ' + url);
  return url;
}

function getOrCreateSheet_(ss, name) {
  return ss.getSheetByName(name) || ss.insertSheet(name);
}

/** 見出し行を書き、既存データは触らない。 */
function ensureHeader_(sh, header) {
  var current = sh.getLastColumn() > 0
    ? sh.getRange(1, 1, 1, sh.getLastColumn()).getValues()[0] : [];
  if (current.join(' ') !== header.join(' ')) {
    sh.getRange(1, 1, 1, header.length).setValues([header]);
  }
  sh.getRange(1, 1, 1, header.length).setFontWeight('bold').setBackground('#efefef');
  sh.setFrozenRows(1);
}

function ensureSettingsSheet_(ss) {
  var sh = getOrCreateSheet_(ss, SHEET_SETTINGS);
  ensureHeader_(sh, ['キー', '値', '説明']);
  seedRows_(sh, 'キー', [
    ['アクセス制限', 'true', 'true にすると「利用者」シートに載っているアドレスだけが使えます'],
    ['画面タイトル', '適合性確認シート／意向把握シート 作成', 'ウェブアプリの見出し'],
    ['既定の契約形態', '個人', 'フォームを開いたときの初期値']
  ]);
  sh.autoResizeColumns(1, 3);
}

function ensureAgenciesSheet_(ss) {
  var sh = getOrCreateSheet_(ss, SHEET_AGENCIES);
  ensureHeader_(sh, ['代理店名', '共有フォルダID', '有効', '備考']);
  if (sh.getLastRow() < 2) {
    sh.getRange(2, 1, 1, 4).setValues([[
      'ヒトカチ株式会社', '', 'TRUE',
      'Drive でフォルダを開いたときの URL の /folders/ 以降が共有フォルダID'
    ]]);
  }
  sh.setColumnWidth(2, 320);
}

function ensureAgentsSheet_(ss) {
  var sh = getOrCreateSheet_(ss, SHEET_AGENTS);
  ensureHeader_(sh, [
    '氏名', 'メールアドレス', '電話番号', '郵便番号', '住所1', '住所2',
    '所属代理店', 'ログイン用アドレス', '有効'
  ]);
  if (sh.getLastRow() < 2) {
    sh.getRange(2, 1, 2, 9).setValues([
      ['佐々木 嶺', 'info@hitokachi.com', '080-6817-4796', '134-0081',
       '東京都 江戸川区 北葛西', '５－１４－１１ クオーディア西葛西５０３',
       'ヒトカチ株式会社', '', 'TRUE'],
      ['髙橋 知史', 's-takahashi@hitokachi.com', '080-2238-7592', '134-0081',
       '東京都 江戸川区 北葛西', '５－１４－１１ クオーディア西葛西５０３',
       'ヒトカチ株式会社', '', 'TRUE']
    ]);
  }
  sh.autoResizeColumns(1, 9);
}

function ensureUsersSheet_(ss) {
  var sh = getOrCreateSheet_(ss, SHEET_USERS);
  ensureHeader_(sh, ['メールアドレス', '氏名', '有効', '備考']);
  if (sh.getLastRow() < 2) {
    sh.getRange(2, 1, 1, 4).setValues([[
      Session.getEffectiveUser().getEmail(), 'オーナー', 'TRUE',
      'このシステムを使えるGoogleアカウント'
    ]]);
  }
  sh.autoResizeColumns(1, 4);
}

/**
 * 項目設定。FIELD_DEFS にある項目の行を用意する。
 * 既にある行のモードと固定値は保持する（運用中の設定を壊さない）。
 */
function ensureFieldsSheet_(ss) {
  var sh = getOrCreateSheet_(ss, SHEET_FIELDS);
  var header = ['項目キー', '表示名', 'セクション', 'モード', '固定値', '必須', '選択肢', '備考'];
  ensureHeader_(sh, header);

  var existing = {};
  if (sh.getLastRow() >= 2) {
    sh.getRange(2, 1, sh.getLastRow() - 1, header.length).getValues().forEach(function (r) {
      if (r[0]) existing[String(r[0]).trim()] = { mode: r[3], fixed: r[4] };
    });
  }

  var rows = FIELD_DEFS.map(function (f) {
    var prev = existing[f.key];
    var options = f.options ? f.options.join(' / ')
      : (f.type === 'needs'
          ? NEEDS.map(function (n) { return n.key + '=' + n.label; }).join(' / ')
          : '');
    return [
      f.key,
      f.label,
      f.section,
      prev && prev.mode ? prev.mode : (f.defaultMode || 'form'),
      prev ? prev.fixed : (f.defaultValue == null ? '' : f.defaultValue),
      f.required ? 'TRUE' : '',
      options,
      f.note || ''
    ];
  });

  if (sh.getLastRow() > 1) {
    sh.getRange(2, 1, sh.getLastRow() - 1, header.length).clearContent();
  }
  sh.getRange(2, 1, rows.length, header.length).setValues(rows);

  var rule = SpreadsheetApp.newDataValidation()
    .requireValueInList(['form', 'fixed', 'hidden'], true)
    .setAllowInvalid(false).build();
  sh.getRange(2, 4, rows.length, 1).setDataValidation(rule);

  sh.setColumnWidth(2, 260);
  sh.setColumnWidth(7, 280);
  sh.setColumnWidth(8, 320);
}

function ensureLogSheet_(ss) {
  ensureHeader_(getOrCreateSheet_(ss, SHEET_LOG), LOG_HEADER);
}

/** キー列を見て、まだない行だけを足す。 */
function seedRows_(sh, keyHeader, rows) {
  var header = sh.getRange(1, 1, 1, sh.getLastColumn()).getValues()[0];
  var keyCol = header.indexOf(keyHeader);
  var have = {};
  if (sh.getLastRow() >= 2) {
    sh.getRange(2, keyCol + 1, sh.getLastRow() - 1, 1).getValues()
      .forEach(function (r) { have[String(r[0]).trim()] = true; });
  }
  rows.forEach(function (r) {
    if (!have[r[keyCol]]) sh.appendRow(r);
  });
}

/** 設定スプレッドシートのURLをログに出す。 */
function showSettingsUrl() {
  Logger.log(settingsSpreadsheet_().getUrl());
}
