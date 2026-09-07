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
  ensureAliasSheet_(ss);
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

  // 相手が決められない代理店は、黙って単独名義の帳票ができる。
  var noRep = agenciesWithoutRepresentative_();
  if (noRep.length) {
    Logger.log('【注意】次の代理店は「代理店募集人マスタ」に2人以上の登録がありますが、'
      + '「代表」に印が付いていません。このままだと連名になりません。\n'
      + noRep.map(function (n) { return '  ・' + n; }).join('\n')
      + '\n連名にする人の「代表」にチェックを入れてください。');
  }

  // 検証実施者が決まらないと、帳票の検証実施者欄が空欄で出る。
  var noVerifier = agentsWithoutVerifier_();
  if (noVerifier.length) {
    Logger.log('【注意】次の募集人は、検証実施者が決まりません。'
      + 'この人が作成した帳票は、検証実施者欄が空欄で出ます。\n'
      + noVerifier.map(function (n) { return '  ・' + n; }).join('\n')
      + '\n「募集人マスタ」のその人の行の「検証者」に、別の人を入れてください'
      + '（設定シートの「' + SETTING_DEFAULT_VERIFIER + '」その人の行が主にこれに当たります）。');
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

  // 以前は「共同募集の相方」の連動プルダウンのために onEdit も仕掛けていた。
  // 相方を代理店マスタから決めるようにして不要になったので、残っていれば外す。
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'onEditBulk_') ScriptApp.deleteTrigger(t);
  });
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
    ['既定の契約形態', '個人', 'フォームを開いたときの初期値'],
    ['一括作成の控えを残す枚数', BULK_SNAPSHOT_KEEP_DEFAULT,
     'リセットのたびに「一括作成_日付」シートを作ります。'
     + 'この枚数を超えたら古いものから消します（0 なら消しません）。'
     + '作成の記録そのものは「送信ログ」に残ります。'],
    ['適合性確認シートが必要な保険種類', SUITABILITY_KEYWORDS_DEFAULT,
     '保険種類にこの語が含まれる契約だけ、適合性確認シートを作ります'
     + '（読点かカンマで複数書けます）。それ以外は意向把握シートだけ作ります。'
     + '保険種類が空欄の行は両方作ります。'],
    [SETTING_DEFAULT_VERIFIER, '髙橋 知史',
     '適合性確認シートの「検証実施者氏名」に入る人です。作成者から決まります。'
     + 'この人以外が作成した帳票は、すべてこの人が検証実施者になります。'
     + 'この人自身が作成した帳票は、募集人マスタのこの人の行の「検証者」を使います。'],
    ['推定のご意向を自動で入れる', 'はい',
     '意向把握シートの「推定のご意向」欄を、保険種類から自動で埋めます'
     + '（当初のご意向と同じ内容）。「いいえ」にすると空欄のままになります。']
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

  // 旧レイアウト（代理店名／氏名／有効／備考）に「代表」を割り込ませる。
  // 見出しを上書きするだけだと、有効のチェックが「代表」として読まれてしまう。
  var head = sh.getLastColumn() > 0
    ? sh.getRange(1, 1, 1, sh.getLastColumn()).getValues()[0].map(String) : [];
  if (head[2] === '有効' && head.indexOf('代表') < 0) {
    sh.insertColumnBefore(3);
  }

  ensureHeader_(sh, ['代理店名', '氏名', '代表', '有効', '備考']);
  if (sh.getLastRow() < 2) {
    sh.getRange(2, 1, 3, 5).setValues([
      ['クレスト保険', '熊澤 善弘', true,  true, ''],
      ['クレスト保険', '小川 康之', false, true, ''],
      ['クレスト保険', '矢野 克臣', false, true, '']
    ]);
  }
  // 100社 × 最大30人を見込んで、チェックボックスは 3000 行ぶん。
  checkboxColumn_(sh, '代表', 3000);
  checkboxColumn_(sh, '有効', 3000);
  agencyNameColumn_(sh, '代理店名', 3000);
  setNotes_(sh, {
    '代理店名': '「代理店マスタ」に登録した代理店から選びます（プルダウン）。\n'
      + '手で打つ必要はありません。代理店を先に登録してください。\n\n'
      + '同じ代理店の人は、何行に分けても構いません（並び順も自由）。',
    '氏名': '共同募集（連名）をする相手の氏名です。\n\n'
      + '帳票には「佐々木 嶺 / 熊澤 善弘」のように連名で入ります。',
    '代表': 'その代理店と連名にする人に、1人だけチェックを入れます。\n\n'
      + 'その代理店に1人しか登録がなければ、チェックは要りません\n'
      + '（自動でその人と連名になります）。\n'
      + '2人以上いてチェックが1つも無いと、連名になりません。',
    '有効': 'チェックを外すと、その人は連名の相手に選ばれなくなります。\n'
      + '退職した人は行を消さずにチェックを外してください。'
  });
  sh.setColumnWidth(1, 220);
  sh.setColumnWidth(2, 160);
  sh.setColumnWidth(5, 360);
  sh.setFrozenRows(1);
}

function ensureAgentsSheet_(ss) {
  var sh = getOrCreateSheet_(ss, SHEET_AGENTS);

  // 旧レイアウトに「検証者」を割り込ませる。見出しを上書きするだけだと、
  // 有効のチェックが「検証者」として読まれてしまう。
  var head = sh.getLastColumn() > 0
    ? sh.getRange(1, 1, 1, sh.getLastColumn()).getValues()[0].map(String) : [];
  if (head[8] === '有効' && head.indexOf('検証者') < 0) {
    sh.insertColumnBefore(9);
  }

  ensureHeader_(sh, [
    '氏名', 'メールアドレス', '電話番号', '郵便番号', '住所1', '住所2',
    '所属代理店', 'ログイン用アドレス', '検証者', '有効'
  ]);
  if (sh.getLastRow() < 2) {
    var addr = ['134-0081', '東京都 江戸川区 北葛西', '５－１４－１１ クオーディア西葛西５０３'];
    sh.getRange(2, 1, 3, 10).setValues([
      ['佐々木 嶺', 'info@hitokachi.com', '080-6817-4796'].concat(addr)
        .concat(['ヒトカチ株式会社', '', '', true]),
      // 既定の検証実施者その人。この行だけは「検証者」を入れておく必要がある。
      ['髙橋 知史', 's-takahashi@hitokachi.com', '080-2238-7592'].concat(addr)
        .concat(['ヒトカチ株式会社', '', '佐々木 嶺', true]),
      // 過去の帳票に登場するが連絡先が分かっていない募集人。
      // 空欄のままでも動くが、意向把握シートの連絡先欄が空白になる。
      ['青木 典子', '', '', '', '', '', 'ヒトカチ株式会社', '', '', true]
    ]);
  }
  checkboxColumn_(sh, '有効', 60);
  agencyNameColumn_(sh, '所属代理店', 200);
  agentNameColumn_(sh, '検証者', 60);
  setNotes_(sh, {
    '所属代理店': '「代理店マスタ」に登録した代理店から選びます（プルダウン）。',
    '検証者': 'この人が作成した帳票を検証する人です（プルダウン）。\n\n'
      + '空欄でかまいません。空欄なら設定シートの「既定の検証実施者」が入ります。\n'
      + '既定の検証実施者その人の行だけは、ここを埋めてください。\n'
      + '空欄だと自分で自分を検証することになるので、検証実施者欄が空欄で出ます。',
    '氏名': '自社（ヒトカチ株式会社）の募集人です。\n'
      + '適合性確認シートの「取扱者名」と、意向把握シートの「募集人」に入ります。\n\n'
      + '他社の募集人は、ここではなく「代理店募集人マスタ」に登録してください。',
    '郵便番号': '意向把握シートの「所在地」に〒付きで入ります。',
    'ログイン用アドレス': '空欄でかまいません。将来ログイン者と募集人を突き合わせるための予備欄です。',
    'メールアドレス': '意向把握シートの【メール】欄に入ります。空欄なら空白で出力されます。',
    '有効': 'チェックを外すと、入力フォームの募集人の選択肢に出なくなります。'
  });
  sh.autoResizeColumns(1, 10);
}

/**
 * 成約一覧の見出しを、一括入力シートの見出しに読み替える表。
 * 成約一覧側の見出しは会社ごとに違うので、コードではなくここで足せるようにする。
 */
function ensureAliasSheet_(ss) {
  var sh = getOrCreateSheet_(ss, SHEET_ALIASES);
  ensureHeader_(sh, ['成約一覧の見出し', '一括入力シートの見出し', '備考']);
  if (sh.getLastRow() < 2) {
    var rows = IMPORT_ALIASES_DEFAULT.map(function (pair) {
      return [pair[0], pair[1], ''];
    });
    sh.getRange(2, 1, rows.length, 3).setValues(rows);
  }
  setNotes_(sh, {
    '成約一覧の見出し': '成約一覧スプレッドシートに書かれている見出しです。\n'
      + '前後の空白や全角・半角の違いは無視します。',
    '一括入力シートの見出し': '「一括入力」シートの見出しです。\n'
      + 'ここに書いた見出しへ読み替えて取り込みます。\n\n'
      + '読み替え先が「一括入力」シートに無い場合、取り込みは中止されます。',
    '備考': 'メモ欄です。空欄で構いません。'
  });
  sh.setColumnWidth(1, 200);
  sh.setColumnWidth(2, 200);
  sh.setColumnWidth(3, 300);
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

/**
 * 募集人マスタの氏名から選ぶプルダウンを張る（検証者の列に使う）。
 * 自分自身の氏名列を参照するので、募集人を足せば選択肢も増える。
 */
function agentNameColumn_(sh, headerName, rows) {
  var header = sh.getRange(1, 1, 1, sh.getLastColumn()).getValues()[0];
  var col = header.indexOf(headerName);
  if (col < 0) return;

  var source = sh.getParent().getSheetByName(SHEET_AGENTS);
  if (!source) return;

  sh.getRange(2, col + 1, rows, 1).setDataValidation(
    SpreadsheetApp.newDataValidation()
      .requireValueInRange(source.getRange(2, 1, AGENT_LIST_ROWS, 1), true)
      .setAllowInvalid(false)
      .build());
}

/** 検証者プルダウンが参照する、募集人マスタの行数。 */
var AGENT_LIST_ROWS = 200;

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
