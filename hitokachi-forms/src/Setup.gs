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
  ensureCoAgentsSheet_(ss);
  ensureAgentsSheet_(ss);
  ensureUsersSheet_(ss);
  ensureFieldsSheet_(ss);
  ensureLogSheet_(ss);
  ensureMenuTrigger_(ss);

  clearMasterCache_();

  // 結び付かない募集人は選択肢に出ないだけで、何も言わずに消える。
  // 貼り付けで入った表記ゆれに気づけるよう、ここで知らせる。
  var orphans = orphanCoAgents_();
  if (orphans.length) {
    Logger.log('【注意】「代理店募集人マスタ」の次の行が、代理店マスタのどの代理店にも'
      + '結び付いていません。この人たちは「共同募集の相方」の選択肢に出ません。\n'
      + orphans.map(function (o) {
          return '  ・' + o.name + '（代理店名「' + o.agency + '」）';
        }).join('\n')
      + '\n代理店マスタにその代理店を追加するか、代理店名を選び直してください。');
  }

  var url = ss.getUrl();
  Logger.log('設定スプレッドシート: ' + url);
  return url;
}

/**
 * 設定スプレッドシートに仕掛けるトリガー。
 * このスクリプトはスプレッドシートに紐づいていない（スタンドアロン）ので、
 * onOpen / onEdit をそのまま書いても呼ばれない。インストール型で仕掛ける。
 *
 *   onOpenMenu … 「帳票作成」メニューを出す
 *   onEditBulk_ … 一括入力シートで代理店を選んだら、その行の
 *                 「共同募集の相方」の選択肢をその代理店の人に入れ替える
 */
function ensureMenuTrigger_(ss) {
  var existing = ScriptApp.getProjectTriggers().map(function (t) {
    return t.getHandlerFunction();
  });

  if (existing.indexOf('onOpenMenu') < 0) {
    try {
      ScriptApp.newTrigger('onOpenMenu').forSpreadsheet(ss).onOpen().create();
    } catch (e) {
      Logger.log('メニューのトリガーを作れませんでした: ' + e.message
        + '\n一括作成の各関数は、Apps Script エディタから直接実行することもできます。');
    }
  }

  if (existing.indexOf('onEditBulk_') < 0) {
    try {
      ScriptApp.newTrigger('onEditBulk_').forSpreadsheet(ss).onEdit().create();
    } catch (e) {
      Logger.log('連動プルダウンのトリガーを作れませんでした: ' + e.message
        + '\nメニューの「共同募集の相方の選択肢を作り直す」で代用できます。');
    }
  }
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
    ['アクセス制限', 'はい', '「はい」にすると、下の「利用者」シートに載っているアドレスだけが使えます'],
    ['画面タイトル', '適合性確認シート／意向把握シート 作成', 'ウェブアプリの見出し'],
    ['既定の契約形態', '個人', 'フォームを開いたときの初期値']
  ]);
  setNotes_(sh, {
    'キー': '設定の名前です。変更しないでください。',
    '値': 'ここを書き換えると動きが変わります。'
  });
  sh.autoResizeColumns(1, 3);
}

function ensureAgenciesSheet_(ss) {
  var sh = getOrCreateSheet_(ss, SHEET_AGENCIES);
  ensureHeader_(sh, ['代理店名', '共有フォルダID', '有効', '備考']);
  if (sh.getLastRow() < 2) {
    sh.getRange(2, 1, 2, 4).setValues([
      ['ヒトカチ株式会社', '', true,
       'Drive でフォルダを開いたときの URL の /folders/ 以降が共有フォルダID'],
      ['クレスト保険', '', true,
       '共同募集の相手は「代理店募集人マスタ」に1人1行で登録する']
    ]);
  }
  // 100社まで増える見込みなので、チェックボックスは多めに用意しておく。
  checkboxColumn_(sh, '有効', 120);
  setNotes_(sh, {
    '共有フォルダID': 'Drive でその代理店の共有フォルダを開いたときの URL の\n'
      + 'https://drive.google.com/drive/folders/★ここ★\nの部分を貼り付けます。\n\n'
      + '空欄のままだと、その代理店では帳票を保存できません。',
    '有効': 'チェックを外すと、入力フォームの代理店の選択肢に出なくなります。\n'
      + '取引が終わった代理店は、行を消さずにチェックを外してください\n'
      + '（過去の送信ログとの対応が保てます）。'
  });
  sh.setColumnWidth(2, 320);
  sh.setColumnWidth(4, 380);
}

/**
 * 代理店ごとの募集人（共同募集の相手）。1人1行。
 * 1代理店に何人でも登録できるので、代理店マスタの1セルに詰め込まない。
 */
function ensureCoAgentsSheet_(ss) {
  var sh = getOrCreateSheet_(ss, SHEET_CO_AGENTS);
  ensureHeader_(sh, ['代理店名', '氏名', '有効', '備考']);
  if (sh.getLastRow() < 2) {
    sh.getRange(2, 1, 3, 4).setValues([
      ['クレスト保険', '熊澤 善弘', true, ''],
      ['クレスト保険', '小川 康之', true, ''],
      ['クレスト保険', '矢野 克臣', true, '']
    ]);
  }
  // 100社 × 最大30人を見込んで、チェックボックスは 3000 行ぶん。
  checkboxColumn_(sh, '有効', 3000);
  agencyNameColumn_(sh, '代理店名', 3000);
  setNotes_(sh, {
    '代理店名': '「代理店マスタ」に登録した代理店から選びます（プルダウン）。\n'
      + '手で打つ必要はありません。代理店を先に登録してください。\n\n'
      + '同じ代理店の人は、何行に分けても構いません（並び順も自由）。',
    '氏名': '共同募集（連名）をする相手の氏名です。\n\n'
      + '入力フォームで代理店を選ぶと、その代理店の人だけが\n'
      + '「共同募集の相方」の選択肢に出ます。\n'
      + '帳票には「佐々木 嶺 / 熊澤 善弘」のように連名で入ります。\n\n'
      + '単独募集のときは、フォームで「（単独募集）」を選べばよいので\n'
      + 'ここに空行を作る必要はありません。',
    '有効': 'チェックを外すと、その人は選択肢に出なくなります。\n'
      + '退職した人は行を消さずにチェックを外してください。'
  });
  sh.setColumnWidth(1, 220);
  sh.setColumnWidth(2, 160);
  sh.setColumnWidth(4, 360);
  sh.setFrozenRows(1);
}

function ensureAgentsSheet_(ss) {
  var sh = getOrCreateSheet_(ss, SHEET_AGENTS);
  ensureHeader_(sh, [
    '氏名', 'メールアドレス', '電話番号', '郵便番号', '住所1', '住所2',
    '所属代理店', 'ログイン用アドレス', '有効'
  ]);
  if (sh.getLastRow() < 2) {
    var addr = ['134-0081', '東京都 江戸川区 北葛西', '５－１４－１１ クオーディア西葛西５０３'];
    sh.getRange(2, 1, 3, 9).setValues([
      ['佐々木 嶺', 'info@hitokachi.com', '080-6817-4796'].concat(addr)
        .concat(['ヒトカチ株式会社', '', true]),
      ['髙橋 知史', 's-takahashi@hitokachi.com', '080-2238-7592'].concat(addr)
        .concat(['ヒトカチ株式会社', '', true]),
      // 過去の帳票に登場するが連絡先が分かっていない募集人。
      // 空欄のままでも動くが、意向把握シートの連絡先欄が空白になる。
      ['青木 典子', '', '', '', '', '', 'ヒトカチ株式会社', '', true]
    ]);
  }
  checkboxColumn_(sh, '有効', 60);
  agencyNameColumn_(sh, '所属代理店', 200);
  setNotes_(sh, {
    '所属代理店': '「代理店マスタ」に登録した代理店から選びます（プルダウン）。',
    '氏名': '自社（ヒトカチ株式会社）の募集人です。\n'
      + '適合性確認シートの「取扱者名」と、意向把握シートの「募集人」に入ります。\n\n'
      + '他社の募集人は、ここではなく「代理店募集人マスタ」に登録してください。',
    '郵便番号': '意向把握シートの「所在地」に〒付きで入ります。',
    'ログイン用アドレス': '空欄でかまいません。将来ログイン者と募集人を突き合わせるための予備欄です。',
    'メールアドレス': '意向把握シートの【メール】欄に入ります。空欄なら空白で出力されます。',
    '有効': 'チェックを外すと、入力フォームの募集人の選択肢に出なくなります。'
  });
  sh.autoResizeColumns(1, 9);
}

function ensureUsersSheet_(ss) {
  var sh = getOrCreateSheet_(ss, SHEET_USERS);
  ensureHeader_(sh, ['メールアドレス', '氏名', '有効', '備考']);
  if (sh.getLastRow() < 2) {
    sh.getRange(2, 1, 1, 4).setValues([[
      Session.getEffectiveUser().getEmail(), 'オーナー', true,
      'このシステムを使えるGoogleアカウント'
    ]]);
  }
  checkboxColumn_(sh, '有効', 5);
  setNotes_(sh, {
    'メールアドレス': 'ここに載っている Google アカウントだけがこのシステムを使えます。\n'
      + '代理店の共有フォルダと、この設定スプレッドシートの編集権限も別途共有してください。',
    '有効': 'チェックを外すと、そのアカウントは使えなくなります。'
  });
  sh.autoResizeColumns(1, 4);
}

/**
 * 項目設定。FIELD_DEFS にある項目の行を用意する。
 * 既にある行のモードと固定値は保持する（運用中の設定を壊さない）。
 */
function ensureFieldsSheet_(ss) {
  var sh = getOrCreateSheet_(ss, SHEET_FIELDS);
  var header = ['項目キー', '表示名', 'セクション', '扱い', '固定値', '必須', '選択肢', '備考'];
  ensureHeader_(sh, header);

  // 既存の設定（扱いと固定値）は引き継ぐ。英語表記だった頃の値もここで日本語に直る。
  var existing = {};
  if (sh.getLastRow() >= 2) {
    sh.getRange(2, 1, sh.getLastRow() - 1, header.length).getValues().forEach(function (r) {
      if (r[0]) {
        existing[String(r[0]).trim()] = {
          mode: MODE_FROM_LABEL[String(r[3] == null ? '' : r[3]).trim()],
          fixed: r[4]
        };
      }
    });
  }

  var rows = FIELD_DEFS.map(function (f) {
    var prev = existing[f.key];
    var mode = (prev && prev.mode) ? prev.mode : (f.defaultMode || 'form');
    var options = f.options ? f.options.join(' / ')
      : (f.type === 'needs'
          ? NEEDS.map(function (n) { return n.label; }).join(' / ')
          : '');
    return [
      f.key,
      f.label,
      f.section,
      MODE_LABELS[mode],
      prev ? prev.fixed : (f.defaultValue == null ? '' : f.defaultValue),
      !!f.required,
      options,
      f.note || ''
    ];
  });

  if (sh.getLastRow() > 1) {
    sh.getRange(2, 1, sh.getLastRow() - 1, header.length).clearContent();
  }
  sh.getRange(2, 1, rows.length, header.length).setValues(rows);

  var rule = SpreadsheetApp.newDataValidation()
    .requireValueInList([MODE_LABELS.form, MODE_LABELS.fixed, MODE_LABELS.hidden], true)
    .setAllowInvalid(false).build();
  sh.getRange(2, 4, rows.length, 1).setDataValidation(rule).setHorizontalAlignment('center');
  // insertCheckboxes は値を false にするので、チェックボックス化してから必須を書き戻す。
  sh.getRange(2, 6, rows.length, 1).insertCheckboxes().setHorizontalAlignment('center');
  sh.getRange(2, 6, rows.length, 1)
    .setValues(rows.map(function (r) { return [r[5]]; }));

  setNotes_(sh, {
    '項目キー': 'システムが使う名前です。変更しないでください。',
    '扱い': 'この項目をどう扱うかを選びます。\n\n'
      + '　' + MODE_LABELS.form + '　… 入力フォームに欄を出します\n'
      + '　' + MODE_LABELS.fixed + '　… 欄を出さず、右の「固定値」を毎回そのまま使います\n'
      + '　' + MODE_LABELS.hidden + '　… この項目は使いません。帳票では空欄になります',
    '固定値': '「固定値を使う」を選んだときだけ使われます。\n\n'
      + '　チェック項目　… はい または いいえ\n'
      + '　複数選べる項目　… 読点やカンマで区切って書く（例: 株式, 投資信託）\n'
      + '　それ以外　… そのまま書く',
    '必須': '未入力だと送信できない項目です。システム側で決まっているので変更できません。',
    '選択肢': 'この項目で選べる値の一覧です（参考表示）。'
  });

  sh.setColumnWidth(2, 260);
  sh.setColumnWidth(4, 110);
  sh.setColumnWidth(7, 280);
  sh.setColumnWidth(8, 320);
}

/**
 * 代理店名の列を、代理店マスタから選ぶプルダウンにする。
 * 手で打たせると1文字の違いで結び付かなくなり、しかも黙って選択肢から
 * 消えるだけなので気づけない。打つ余地をなくすのがいちばん確実。
 *
 * @param {Sheet} sh          プルダウンを張るシート
 * @param {string} headerName 代理店名が入っている列の見出し
 * @param {number} rows       張る行数
 */
function agencyNameColumn_(sh, headerName, rows) {
  var header = sh.getRange(1, 1, 1, sh.getLastColumn()).getValues()[0];
  var col = header.indexOf(headerName);
  if (col < 0) return;

  var agencies = sh.getParent().getSheetByName(SHEET_AGENCIES);
  if (!agencies) return;

  // 代理店マスタの行が増えても張り直さなくて済むよう、広めに参照する。
  var source = agencies.getRange(2, 1, AGENCY_LIST_ROWS, 1);
  sh.getRange(2, col + 1, rows, 1).setDataValidation(
    SpreadsheetApp.newDataValidation()
      .requireValueInRange(source, true)
      .setAllowInvalid(false)
      .build());
}

/** 代理店名プルダウンが参照する、代理店マスタの行数。 */
var AGENCY_LIST_ROWS = 500;

/** 見出しセルに説明のメモを付ける。 */
function setNotes_(sh, notes) {
  var header = sh.getRange(1, 1, 1, sh.getLastColumn()).getValues()[0];
  header.forEach(function (h, i) {
    if (notes[h]) sh.getRange(1, i + 1).setNote(notes[h]);
  });
}

/**
 * 「有効」列をチェックボックスにする。
 * 既存の行に加えて数行ぶん先回りして入れておくと、行を足すときに迷わない。
 *
 * insertCheckboxes() は範囲内のセルの値をすべて false にする。そのまま呼ぶと
 * setup() を実行するたびに代理店・募集人・利用者の「有効」が全部外れ、
 * 翌日から誰もログインできなくなる。値を退避して書き戻す。
 */
function checkboxColumn_(sh, headerName, spare) {
  var header = sh.getRange(1, 1, 1, sh.getLastColumn()).getValues()[0];
  var col = header.indexOf(headerName);
  if (col < 0) return;

  var dataRows = Math.max(sh.getLastRow() - 1, 0);
  var rows = Math.max(dataRows, 1) + (spare || 0);
  var saved = dataRows > 0
    ? sh.getRange(2, col + 1, dataRows, 1).getValues().map(function (r) { return isTrue_(r[0]); })
    : [];

  sh.getRange(2, col + 1, rows, 1).insertCheckboxes().setHorizontalAlignment('center');

  if (saved.length) {
    sh.getRange(2, col + 1, saved.length, 1)
      .setValues(saved.map(function (v) { return [v]; }));
  }
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
