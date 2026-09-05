/**
 * 管理者専用の処理。Webアプリからは一切呼ばれない。
 * Apps Scriptエディタで関数を選んで実行する。
 *
 * 旧実装は setupInitialSheets() を apiInit() から呼んでいたため、
 * 画面を開くたびにマスタへ初期行が追記され、割引繁忙期マスタが150行超まで増殖していた。
 * セットアップとマイグレーションはここに隔離する。
 *
 * 実行順の目安（初回デプロイ時）
 *   1. adminBackup()                  … 本番2ファイルを複製して退避
 *   2. adminDiagnose()                … 現状を確認（読むだけ・変更しない）
 *   3. adminSetup()                   … 不足シート／不足ヘッダーだけを補う
 *   4. adminNormalizeDiscountRules()  … 割引繁忙期マスタを正規化
 *   5. adminNormalizeMailTemplates()  … メールテンプレートマスタを正規化
 *   6. adminNormalizeCellDefinitions()… 差し込みセル定義の列ずれを修復
 *   7. adminCreatePdfTemplate()       … PDF生成専用の軽いテンプレートを作る（任意）
 *   8. adminSetMasterTimezone()       … マスタのタイムゾーンを Asia/Tokyo に統一（任意）
 *   9. adminRefreshCache()            … マスタキャッシュを破棄
 */

/* ===================== バックアップ ===================== */

function adminBackup() {
  const stamp = Utilities.formatDate(new Date(), APP.TZ, 'yyyyMMdd_HHmm');
  const out = [];

  [
    { id: APP.DEFAULT_MASTER_SS_ID, label: 'マスタ' },
    { id: APP.DEFAULT_TEMPLATE_SS_ID, label: '帳票DB' }
  ].forEach(function (t) {
    const file = DriveApp.getFileById(t.id);
    const copy = file.makeCopy('[BACKUP ' + stamp + '] ' + file.getName());
    out.push(t.label + '：' + copy.getName() + ' / ' + copy.getUrl());
  });

  const message = out.join('\n');
  console.log(message);
  return message;
}

/* ===================== セットアップ ===================== */

/**
 * 不足しているシートとヘッダーだけを補う。
 * 既存の列位置は動かさない。初期データの投入もしない（増殖の原因になるため）。
 */
function adminSetup() {
  const masterSs = getMasterSs_();
  const settings = readSettings_(masterSs);
  const templateSs = getTemplateSs_(settings);
  const report = [];

  const ensure = function (ss, name, headers) {
    let sheet = ss.getSheetByName(name);

    if (!sheet) {
      sheet = ss.insertSheet(name);
      sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
      sheet.setFrozenRows(1);
      report.push('作成：' + ss.getName() + ' / ' + name);
      return;
    }

    if (sheet.getLastRow() === 0 || sheet.getLastColumn() === 0) {
      sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
      sheet.setFrozenRows(1);
      report.push('ヘッダー投入：' + name);
      return;
    }

    forgetHeaderInfo_(sheet);
    const before = getHeaderInfo_(sheet, headers.slice(0, 2));
    const missing = headers.filter(function (h) { return !before.map[h]; });

    if (missing.length === 0) {
      report.push('変更なし：' + name);
      return;
    }

    sheet.getRange(before.headerRow, sheet.getLastColumn() + 1, 1, missing.length).setValues([missing]);
    forgetHeaderInfo_(sheet);
    report.push('列追加：' + name + ' → ' + missing.join(', '));
  };

  ensure(masterSs, APP.SHEET_SETTINGS, SETTINGS_HEADERS);
  ensure(masterSs, APP.SHEET_MENU, getMenuHeaders_());
  ensure(masterSs, APP.SHEET_SUBMIT_TO, getSubmitToHeaders_());
  ensure(masterSs, APP.SHEET_MAIL_TEMPLATE, getMailTemplateHeaders_());
  ensure(masterSs, APP.SHEET_DISCOUNT, getDiscountHeaders_());
  ensure(masterSs, APP.SHEET_STAFF, getStaffHeaders_());
  ensure(masterSs, APP.SHEET_CELL_DEF, getCellDefHeaders_());
  ensure(masterSs, APP.SHEET_LOG, getLogHeaders_());

  ensure(templateSs, APP.SHEET_ESTIMATE_DATA, getEstimateHeaders_());
  ensure(templateSs, APP.SHEET_INVOICE_DATA, getInvoiceHeaders_());

  report.push(upsertMissingSettings_(masterSs));
  report.push(seedStaffIfEmpty_(masterSs));

  clearContextCache_();

  const message = report.join('\n');
  console.log(message);
  return message;
}

/** 設定マスタに「キーが存在しない設定」だけを追記する。既存値は上書きしない。 */
function upsertMissingSettings_(masterSs) {
  const sheet = masterSs.getSheetByName(APP.SHEET_SETTINGS);
  if (!sheet) return '設定マスタが見つかりません。';

  const defaults = [
    ['auto_discount_enabled', 'FALSE', '早期予約割引・複数台割引の自動判定を使うか', 'TRUEにすると自動で割引が載る。現場周知後に切り替えること'],
    ['large_discount_alert_ratio', '0.30', '手動値引きが明細小計のこの割合以上なら警告', ''],
    ['pdf_template_spreadsheet_id', '', 'PDF生成専用テンプレートのID', '空なら帳票/DBスプレッドシートを複製する。adminCreatePdfTemplate()で作成'],
    ['line_notice_text', 'メール送信後、LINEで代表者へ一報を入れてください。', '例外時のアプリ表示文言', ''],
    ['default_closing_day', '月末', '請求締め日の既定値', '提出先マスタに個別指定があればそちらが優先'],
    ['default_payment_site', '翌月末', '支払サイトの既定値', '候補：当月末 / 翌月末 / 翌々月末 / 30日 など'],
    ['parking_tax_type', '課税', '駐車場代の既定の税区分', '請求書作成画面で切り替え可能'],
    ['invoice_remarks_note', '', '請求書の備考に毎回入れる定型文', '振込先はテンプレート側に記載済み']
  ];

  forgetHeaderInfo_(sheet);
  const info = getHeaderInfo_(sheet, ['設定キー', '設定値']);
  const keyCol = info.map['設定キー'];
  if (!keyCol) return '設定マスタに「設定キー」列がありません。';

  const existing = {};
  const lastRow = sheet.getLastRow();

  if (lastRow > info.headerRow) {
    sheet.getRange(info.headerRow + 1, keyCol, lastRow - info.headerRow, 1)
      .getDisplayValues()
      .forEach(function (r) { existing[String(r[0] || '').trim()] = true; });
  }

  const toAdd = defaults.filter(function (d) { return !existing[d[0]]; });
  if (toAdd.length === 0) return '設定マスタ：追加なし';

  const width = Math.max(sheet.getLastColumn(), SETTINGS_HEADERS.length);
  const rows = toAdd.map(function (d) {
    const row = new Array(width).fill('');
    SETTINGS_HEADERS.forEach(function (h, i) {
      const col = info.map[h];
      if (col) row[col - 1] = d[i];
    });
    return row;
  });

  sheet.getRange(sheet.getLastRow() + 1, 1, rows.length, width).setValues(rows);
  return '設定マスタ：' + toAdd.map(function (d) { return d[0]; }).join(', ') + ' を追加';
}

/**
 * 担当者マスタが空のときだけ初期メンバーを入れる。
 * 既に行があれば何もしない（増殖させない）。
 */
function seedStaffIfEmpty_(masterSs) {
  const sheet = masterSs.getSheetByName(APP.SHEET_STAFF);
  if (!sheet) return '担当者マスタ：シートがありません';

  forgetHeaderInfo_(sheet);
  const info = getHeaderInfo_(sheet, getStaffHeaders_());
  if (sheet.getLastRow() > info.headerRow) return '担当者マスタ：既存行があるため変更なし';

  const seed = [['TRUE', 'STAFF_01', '渡辺 和真', '', '']];
  const width = Math.max(sheet.getLastColumn(), getStaffHeaders_().length);

  const rows = seed.map(function (d) {
    const row = new Array(width).fill('');
    getStaffHeaders_().forEach(function (h, i) {
      const col = info.map[h];
      if (col) row[col - 1] = d[i];
    });
    return row;
  });

  sheet.getRange(info.headerRow + 1, 1, rows.length, width).setValues(rows);
  return '担当者マスタ：渡辺 和真 を登録';
}

function adminRefreshCache() {
  clearContextCache_();
  console.log('マスタキャッシュを破棄しました。次のアクセスで読み直します。');
  return 'ok';
}

/* ===================== 正規化（マイグレーション） ===================== */

/**
 * 元シートを「_旧_日時」にリネームして退避し、正規化した新シートを作る。
 * 破壊的な書き換えをしないので、問題があればシート名を戻すだけで復旧できる。
 */
function replaceSheetWithNormalized_(ss, sheetName, headers, rows) {
  const stamp = Utilities.formatDate(new Date(), APP.TZ, 'yyyyMMdd_HHmm');
  const old = ss.getSheetByName(sheetName);
  const backupName = sheetName + '_旧_' + stamp;

  if (old) old.setName(backupName);

  const sheet = ss.insertSheet(sheetName);
  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  sheet.setFrozenRows(1);

  if (rows.length > 0) {
    sheet.getRange(2, 1, rows.length, headers.length).setValues(rows);
  }

  sheet.autoResizeColumns(1, Math.min(headers.length, 12));
  forgetHeaderInfo_(sheet);

  return sheetName + ' を正規化しました（' + rows.length + '行）。旧シートは「' + backupName + '」に退避しています。';
}

/**
 * 割引繁忙期マスタの正規化。
 *
 * 現状の問題：旧ヘッダー（A:ルールID, B:有効…）のまま、初期投入行が
 * 新スキーマ順（A:有効, B:ルールID…）で書かれていたため開始月・終了月・値が全てずれ、
 * 繁忙期／早期予約割引／複数台割引の自動判定が常に不成立になっていた。
 * さらに画面を開くたびに16行が追記され、150行超まで重複していた。
 */
function adminNormalizeDiscountRules() {
  const masterSs = getMasterSs_();

  const rows = [
    ['TRUE', 'BUSY_05_07', '繁忙期', '全体', 5, 7, '', 3300, '金額', 10, '5月〜7月。メインメニューの数量ごとに加算'],
    ['TRUE', 'BUSY_12', '繁忙期', '全体', 12, 12, '', 3300, '金額', 10, '12月。メインメニューの数量ごとに加算'],

    ['TRUE', 'EARLY_01_02', '早期予約割引', '全体', 1, 2, '', 0.15, '率', 20, '1月〜2月：15%'],
    ['TRUE', 'EARLY_03_04', '早期予約割引', '全体', 3, 4, '', 0.10, '率', 20, '3月〜4月：10%'],
    ['TRUE', 'EARLY_08_10', '早期予約割引', '全体', 8, 10, '', 0.10, '率', 20, '8月〜10月：10%'],

    ['TRUE', 'MULTI_NORMAL_05_10', '複数台割引', 'ノーマルエアコン', '', '', 'totalQty:5-10', 500, '金額/台', 30, '総台数で判定'],
    ['TRUE', 'MULTI_NORMAL_11_20', '複数台割引', 'ノーマルエアコン', '', '', 'totalQty:11-20', 1000, '金額/台', 30, '総台数で判定'],
    ['TRUE', 'MULTI_NORMAL_21_50', '複数台割引', 'ノーマルエアコン', '', '', 'totalQty:21-50', 1500, '金額/台', 30, '総台数で判定'],
    ['TRUE', 'MULTI_ROBO_05_10', '複数台割引', 'ロボ付きエアコン', '', '', 'totalQty:5-10', 1000, '金額/台', 30, '総台数で判定'],
    ['TRUE', 'MULTI_ROBO_11_20', '複数台割引', 'ロボ付きエアコン', '', '', 'totalQty:11-20', 1500, '金額/台', 30, '総台数で判定'],
    ['TRUE', 'MULTI_ROBO_21_50', '複数台割引', 'ロボ付きエアコン', '', '', 'totalQty:21-50', 2000, '金額/台', 30, '総台数で判定'],
    ['TRUE', 'MULTI_BUSINESS_02_10', '複数台割引', '業務用エアコン', '', '', 'totalQty:2-10', 5000, '金額/台', 30, '総台数で判定'],
    ['TRUE', 'MULTI_BUSINESS_11_20', '複数台割引', '業務用エアコン', '', '', 'totalQty:11-20', 6000, '金額/台', 30, '総台数で判定'],
    ['TRUE', 'MULTI_BUSINESS_21_50', '複数台割引', '業務用エアコン', '', '', 'totalQty:21-50', 7000, '金額/台', 30, '総台数で判定'],

    ['FALSE', 'INTRO_01_02', '紹介料', '全体', 1, 2, '', 0.05, '率', 90, '顧客割引か紹介元支払か未確定のため計算対象外'],
    ['FALSE', 'INTRO_OTHER', '紹介料', '全体', 3, 12, '', 0.10, '率', 90, '顧客割引か紹介元支払か未確定のため計算対象外']
  ];

  const message = replaceSheetWithNormalized_(masterSs, APP.SHEET_DISCOUNT, getDiscountHeaders_(), rows);
  clearContextCache_();

  const note = message + '\n'
    + '※ 空室清掃の繁忙期30%はメニューマスタ M015 の「繁忙期加算額」欄（30%）で管理しています。\n'
    + '※ 早期予約割引と複数台割引は併用しません（早期予約が優先）。この併用ルールはコード側に実装済みです。\n'
    + '※ 自動割引を実際に効かせるには、設定マスタの auto_discount_enabled を TRUE にしてください。';

  console.log(note);
  return note;
}

/**
 * メールテンプレートマスタの正規化。
 * 旧列（テンプレートID / 用途 / 件名テンプレート / 本文テンプレート）と
 * 新列（有効 / テンプレート種別 / 件名 / 本文 / 備考）が混在し、
 * 初期投入行がA列から書かれていたため新列側が空で、実質コードのfallback文面が使われていた。
 */
function adminNormalizeMailTemplates() {
  const masterSs = getMasterSs_();

  // 既存シートから拾えた文面を優先して引き継ぐ
  const existing = readMailTemplates_(masterSs, []);

  const defaults = {
    '自社案件_見積送付': {
      subject: '【お見積書】{案件名} / {顧客名}様',
      body: '{顧客名}様\n\nお世話になっております。\nワンヒッター株式会社です。\n\nご依頼いただきましたお見積書を添付にてお送りいたします。\n\n■案件名：{案件名}\n■お見積金額：{見積金額}\n■見積番号：{見積ID}\n\nご不明点やご要望等ございましたら、何なりとお申し付けくださいませ。\nご検討のほど、よろしくお願いいたします。\n\n{会社名}',
      note: '自社顧客向け'
    },
    '元請案件_見積送付': {
      subject: '【お見積書】{顧客名}様 / {案件名} / {見積ID}',
      body: '{提出先名} ご担当者様\n\nお世話になっております。\nワンヒッター株式会社です。\n\n下記案件のお見積書を添付にてお送りいたします。\n\n■顧客名：{顧客名}\n■案件名：{案件名}\n■お見積金額：{見積金額}\n■見積番号：{見積ID}\n\nご査収のほど、よろしくお願いいたします。\n\n{会社名}',
      note: '元請向け'
    },
    '代表者確認依頼': {
      subject: '【要確認】見積確認依頼：{見積ID} / {顧客名} / {案件名}',
      body: '代表者確認をお願いします。\n\n■見積ID：{見積ID}\n■顧客名：{顧客名}\n■案件名：{案件名}\n■案件タイプ：{案件タイプ}\n■合計金額：{見積金額}\n■担当者：{担当者}\n■作成日時：{作成日時}\n\n■例外理由：\n{例外理由}\n\n■PDF：{PDF_URL}',
      note: '例外時のみ使用。メール送信後にLINEで一報'
    },
    '自社案件_請求書送付': {
      subject: '【ご請求書】{案件名} / {顧客名}様',
      body: '{顧客名}様\n\nお世話になっております。\nワンヒッター株式会社です。\n\nご請求書を添付にてお送りいたします。\n\n■案件名：{案件名}\n■ご請求金額：{見積金額}\n\nご確認のほど、よろしくお願いいたします。\n\n{会社名}',
      note: '請求書フェーズ用。文面は要確定'
    },
    '元請案件_請求書送付': {
      subject: '【ご請求書】{顧客名}様 / {案件名}',
      body: '{提出先名} ご担当者様\n\nお世話になっております。\nワンヒッター株式会社です。\n\n下記案件のご請求書を添付にてお送りいたします。\n\n■顧客名：{顧客名}\n■案件名：{案件名}\n■ご請求金額：{見積金額}\n\nご査収のほど、よろしくお願いいたします。\n\n{会社名}',
      note: '請求書フェーズ用。文面は要確定'
    }
  };

  const rows = MAIL_TEMPLATE_TYPES.map(function (type) {
    const kept = existing[type];
    const def = defaults[type];
    return [
      'TRUE',
      type,
      (kept && kept.subject) || def.subject,
      (kept && kept.body) || def.body,
      def.note + ((kept && kept.body) ? '（既存文面を引き継ぎ）' : '（初期文面）')
    ];
  });

  const message = replaceSheetWithNormalized_(masterSs, APP.SHEET_MAIL_TEMPLATE, getMailTemplateHeaders_(), rows);
  clearContextCache_();

  console.log(message);
  return message;
}

/** 差し込みセル定義の列ずれ（項目名が空で値が左に寄っている行）を9列の正規形に直す。 */
function adminNormalizeCellDefinitions() {
  const masterSs = getMasterSs_();
  const message = replaceSheetWithNormalized_(
    masterSs, APP.SHEET_CELL_DEF, getCellDefHeaders_(), getDefaultCellDefinitionRows_());

  clearContextCache_();
  console.log(message);
  return message;
}

/* ===================== PDF専用テンプレート ===================== */

/**
 * PDF生成のたびに帳票/DBスプレッドシートを丸ごと複製するのをやめるため、
 * 差し込み用の2シートだけを持つ軽いスプレッドシートを作る。
 * 見積データが増えても複製時間が伸びなくなる。
 */
function adminCreatePdfTemplate() {
  const settings = readSettings_(getMasterSs_());
  const sourceSs = getTemplateSs_(settings);
  const stamp = Utilities.formatDate(new Date(), APP.TZ, 'yyyyMMdd_HHmm');

  const target = SpreadsheetApp.create('【アプリ】PDF生成用テンプレート ' + stamp);
  target.setSpreadsheetTimeZone(APP.TZ);

  [APP.TEMP_ESTIMATE_SHEET, APP.TEMP_INVOICE_SHEET].forEach(function (name) {
    const src = sourceSs.getSheetByName(name);
    if (!src) throw new Error('コピー元シートが見つかりません：' + name);
    // copyTo は書式・結合・列幅・印刷設定をそのまま引き継ぐ
    target.setActiveSheet(src.copyTo(target)).setName(name);
  });

  const leftovers = target.getSheets().filter(function (s) {
    return [APP.TEMP_ESTIMATE_SHEET, APP.TEMP_INVOICE_SHEET].indexOf(s.getName()) < 0;
  });
  leftovers.forEach(function (s) { target.deleteSheet(s); });

  const message = 'PDF生成用テンプレートを作成しました。\n'
    + 'ID: ' + target.getId() + '\n'
    + 'URL: ' + target.getUrl() + '\n\n'
    + '設定マスタの pdf_template_spreadsheet_id にこのIDを入れてから adminRefreshCache() を実行してください。\n'
    + '※ 帳票レイアウトを変更したら、このテンプレートも作り直してください。';

  console.log(message);
  return message;
}

/* ===================== タイムゾーン ===================== */

function adminSetMasterTimezone() {
  const masterSs = getMasterSs_();
  const before = masterSs.getSpreadsheetTimeZone();
  masterSs.setSpreadsheetTimeZone(APP.TZ);

  const message = 'マスタのタイムゾーンを ' + before + ' → ' + masterSs.getSpreadsheetTimeZone() + ' に変更しました。';
  console.log(message);
  return message;
}

/* ===================== 診断 ===================== */

/** 読むだけ。何も書き換えない。デプロイ前後の健康診断に使う。 */
function adminDiagnose() {
  const out = [];
  const add = function (line) { out.push(line); };

  const masterSs = getMasterSs_();
  const settings = readSettings_(masterSs);

  add('■ スプレッドシート');
  add('  マスタ　　： ' + masterSs.getName() + ' / TZ=' + masterSs.getSpreadsheetTimeZone());

  let templateSs = null;
  try {
    templateSs = getTemplateSs_(settings);
    add('  帳票/DB　： ' + templateSs.getName() + ' / TZ=' + templateSs.getSpreadsheetTimeZone());
  } catch (e) {
    add('  帳票/DB　： 開けません → ' + toErrorMessage_(e));
  }

  if (masterSs.getSpreadsheetTimeZone() !== APP.TZ) {
    add('  ⚠ マスタのタイムゾーンが ' + APP.TZ + ' ではありません。adminSetMasterTimezone() を検討してください。');
  }

  add('');
  add('■ マスタの行数');
  [APP.SHEET_MENU, APP.SHEET_SUBMIT_TO, APP.SHEET_MAIL_TEMPLATE,
   APP.SHEET_DISCOUNT, APP.SHEET_SETTINGS, APP.SHEET_CELL_DEF, APP.SHEET_LOG].forEach(function (name) {
    const sheet = masterSs.getSheetByName(name);
    add('  ' + name + '： ' + (sheet ? (sheet.getLastRow() + '行 / ' + sheet.getLastColumn() + '列') : '見つかりません'));
  });

  add('');
  add('■ マスタ読み取り結果');
  const warnings = [];
  const menus = readMenus_(masterSs, warnings);
  const rules = readDiscountRules_(masterSs, warnings);
  const templates = readMailTemplates_(masterSs, warnings);
  const targets = readSubmitTargets_(masterSs, settings);

  add('  有効メニュー： ' + menus.length + '件（メイン ' +
    menus.filter(function (m) { return m.menuType === 'メイン'; }).length + ' / オプション ' +
    menus.filter(function (m) { return m.menuType === 'オプション'; }).length + '）');
  add('  有効ルール　： ' + rules.length + '件（' + ['繁忙期', '早期予約割引', '複数台割引', '紹介料'].map(function (t) {
    return t + ' ' + rules.filter(function (r) { return r.ruleType === t; }).length;
  }).join(' / ') + '）');
  add('  テンプレート： ' + Object.keys(templates).join(', '));
  add('  案件タイプ　： ' + targets.length + '件');

  const priceless = menus.filter(function (m) { return isBlank_(m.unitPriceRaw); });
  if (priceless.length) add('  ⚠ 単価未設定の有効メニュー： ' + priceless.map(function (m) { return m.menuId; }).join(', '));

  const noMail = targets.filter(function (t) { return t.projectType !== '自社' && !t.to; });
  if (noMail.length) {
    add('  ⚠ 宛先メール未設定の提出先（PDFは作れるがGmail下書きが作れません）：');
    noMail.forEach(function (t) { add('      - ' + t.projectType); });
  }

  MAIL_TEMPLATE_TYPES.slice(0, 3).forEach(function (t) {
    if (!templates[t]) add('  ⚠ メールテンプレート未登録： ' + t + '（コード内のfallback文面が使われます）');
  });

  add('');
  add('■ 自動割引の設定');
  add('  auto_discount_enabled： ' + (parseBooleanLoose_(settings['自動割引有効']) ? 'TRUE（自動で割引が載ります）' : 'FALSE（自動割引は載りません）'));
  add('  税率　　　　　　　　： ' + normalizeRate_(settings['税率']));
  add('  繁忙期加算　　　　　： ' + settings['繁忙期加算額'] + ' / ' + settings['繁忙期加算単位']);

  add('');
  add('■ 自動判定の動作確認（マスタの実データで計算）');
  const engine = getCalcEngine_();
  const ctx = buildCalcContext_(buildContextFromSheets_());
  const probeMenu = menus.filter(function (m) { return m.menuType === 'メイン' && m.multipleDiscountTarget; })[0];

  if (!probeMenu) {
    add('  複数台割引対象のメインメニューが無いため確認をスキップしました。');
  } else {
    const probe = function (label, workDate, qty) {
      const calc = engine.calculate({
        workDate: workDate,
        details: [{ menuId: probeMenu.menuId, qty: qty }]
      }, Object.assign({}, ctx, { autoDiscountEnabled: true }));

      add('  ' + label + '： 繁忙期 ' + (calc.busyAuto ? 'あり ' + calc.busyAmount + '円' : 'なし')
        + ' / 割引候補 ' + (calc.autoDiscountCandidate || 0) + '円'
        + (calc.autoDiscountType ? '（' + calc.autoDiscountType + '）' : ''));
    };

    add('  対象メニュー： ' + probeMenu.menuId + ' ' + probeMenu.name);
    probe('  1月 1台 ', '2026-01-15', 1);
    probe('  5月 1台 ', '2026-05-15', 1);
    probe('  7月20台', '2026-07-15', 20);
    probe('  8月 1台 ', '2026-08-15', 1);
    probe(' 11月 5台 ', '2026-11-15', 5);
    probe(' 12月 1台 ', '2026-12-15', 1);
  }

  add('');
  add('■ Drive / Gmail');
  [
    ['見積書PDF保存フォルダ', settings['見積書PDF保存フォルダID']],
    ['請求書PDF保存フォルダ', settings['請求書PDF保存フォルダID']]
  ].forEach(function (t) {
    try {
      add('  ' + t[0] + '： ' + DriveApp.getFolderById(t[1]).getName());
    } catch (e) {
      add('  ⚠ ' + t[0] + '： 開けません（' + t[1] + '）');
    }
  });

  const pdfTemplateId = String(settings['PDF生成用テンプレートスプレッドシートID'] || '').trim();
  if (pdfTemplateId) {
    try {
      add('  PDF生成用テンプレート： ' + SpreadsheetApp.openById(pdfTemplateId).getName());
    } catch (e) {
      add('  ⚠ PDF生成用テンプレートを開けません（' + pdfTemplateId + '）');
    }
  } else {
    add('  PDF生成用テンプレート： 未設定（帳票/DBスプレッドシートを複製します）');
  }

  const aliases = GmailApp.getAliases();
  const wantAlias = String(settings['送信元メール'] || '').trim();
  add('  Gmailエイリアス： ' + (aliases.length ? aliases.join(', ') : 'なし'));
  add('  送信元メール　： ' + wantAlias + (aliases.indexOf(wantAlias) >= 0 ? '（利用可）' : '（未設定のため実行アカウントで下書きされます）'));

  add('');
  add('■ 見積データ');
  if (templateSs) {
    const sheet = templateSs.getSheetByName(APP.SHEET_ESTIMATE_DATA);
    if (sheet) {
      forgetHeaderInfo_(sheet);
      const info = getHeaderInfo_(sheet, ['estimate_id']);
      const missing = getEstimateHeaders_().filter(function (h) { return !info.map[h]; });
      add('  ' + APP.SHEET_ESTIMATE_DATA + '： ' + Math.max(0, sheet.getLastRow() - info.headerRow) + '件 / ' + sheet.getLastColumn() + '列');
      add(missing.length
        ? '  ⚠ 不足列 ' + missing.length + '件： ' + missing.slice(0, 12).join(', ') + (missing.length > 12 ? ' …' : '') + '  → adminSetup() を実行してください'
        : '  列定義： 最新');
    }
  }

  if (warnings.length) {
    add('');
    add('■ 警告');
    warnings.forEach(function (w) { add('  ⚠ ' + w); });
  }

  const message = out.join('\n');
  console.log(message);
  return message;
}

/**
 * 帳票テンプレートの実レイアウトを書き出す。
 * 差し込みセル定義が実テンプレートと合っているかを目視確認するためのもの。
 *
 * 特に請求書の「お支払い期限：」の値セルは資料から確定できなかったため、
 * 請求書を初めて発行する前に必ず一度実行して、payment_due の行を実際の位置に直すこと。
 */
function adminInspectTemplateLayout() {
  const settings = readSettings_(getMasterSs_());
  const ss = getTemplateSs_(settings);
  const out = [];

  [APP.TEMP_ESTIMATE_SHEET, APP.TEMP_INVOICE_SHEET].forEach(function (name) {
    const sheet = ss.getSheetByName(name);
    out.push('');
    out.push('■ ' + name);

    if (!sheet) {
      out.push('  シートが見つかりません。');
      return;
    }

    const lastRow = Math.min(sheet.getLastRow(), 50);
    const lastCol = Math.min(Math.max(sheet.getLastColumn(), 1), 8);
    const values = sheet.getRange(1, 1, lastRow, lastCol).getDisplayValues();

    values.forEach(function (row, r) {
      const filled = [];
      row.forEach(function (v, c) {
        const text = String(v || '').trim();
        if (text) filled.push(columnLetter_(c + 1) + (r + 1) + '=' + truncate_(text, 40));
      });
      if (filled.length) out.push('  ' + filled.join('  |  '));
    });
  });

  out.push('');
  out.push('■ 差し込みセル定義との突き合わせ');

  const ctx = buildContextFromSheets_();
  ['見積書', '請求書'].forEach(function (docType) {
    const defs = getCellDefMap_(docType, ctx);
    out.push('  ' + docType + '： ' + Object.keys(defs).length + '項目');
    ['detail_name_range', 'subtotal', 'tax', 'grand_total', 'payment_due'].forEach(function (key) {
      const def = defs[key];
      out.push('    ' + key + '： ' + (def ? def.a1 : '未定義'));
    });
  });

  const message = out.join('\n');
  console.log(message);
  return message;
}

function columnLetter_(col) {
  let letter = '';
  let n = col;
  while (n > 0) {
    const rem = (n - 1) % 26;
    letter = String.fromCharCode(65 + rem) + letter;
    n = Math.floor((n - 1) / 26);
  }
  return letter;
}

/** マスタ読み込みにかかる時間を実測する。改善前後の比較用。 */
function adminBenchmark() {
  clearContextCache_();

  const t0 = Date.now();
  const ctx = buildContextFromSheets_();
  const cold = Date.now() - t0;

  writeCachedContext_(ctx);
  RUNTIME.context = null;

  const t1 = Date.now();
  loadContext_();
  const warm = Date.now() - t1;

  const message = 'マスタ読み込み（キャッシュなし）： ' + cold + 'ms\n'
    + 'マスタ読み込み（キャッシュあり）： ' + warm + 'ms';

  console.log(message);
  return message;
}
