/**
 * 見積作成Webアプリ ── サーバー側
 *
 * 設計方針（2026-09 改修）
 *   1. マスタは1リクエスト1回だけ読み、CacheServiceに載せる。画面ロードのたびに
 *      setupInitialSheets() を走らせない（マスタ増殖と遅延の原因だった）。
 *   2. 金額計算は Calc.html の CalcEngine ただ1つ。クライアントは即時表示に使い、
 *      サーバーは保存時に同じ関数で再計算して、その結果を正とする。
 *   3. シートへの読み書きはヘッダー名で位置を引く。A列から順に書かない。
 *   4. 見積作成は「保存」と「PDF/メール生成」の2フェーズ。保存が終わった時点で
 *      見積IDを画面に返し、重い処理を待たせない。
 *
 * 禁止事項（引継ぎ仕様書より）
 *   - Gmail即送信禁止。createDraft のみ。
 *   - 高速料金の自動取得禁止。
 *   - 見積の過去データを直接編集しない。複製は必ず新IDを発行する。
 *   - 例外案件でもPDF・メール下書き作成をロックしない。
 */

const APP = {
  DEFAULT_MASTER_SS_ID: '1HPtoKzOwwqnS6Yk_R0UHEy3u8Wpe43LrD7HlCvS6SLw',
  DEFAULT_TEMPLATE_SS_ID: '1s0iZGjz58SZLgpkrs-lO_EjGr8bQq6qUZB93lyx061c',
  DEFAULT_ESTIMATE_FOLDER_ID: '1jWqoPrOzvD4naIW6tjB-sqU-xsJSOqw3',
  DEFAULT_INVOICE_FOLDER_ID: '1lCcQmmIH2wSfzQDVboJS4sXknOm1OBGy',
  DEFAULT_EXECUTION_EMAIL: 'info.onehitter@gmail.com',
  TZ: 'Asia/Tokyo',
  MAX_DETAIL_ROWS: 16,
  MAX_ADJUSTMENT_SLOTS: 5,

  // マスタキャッシュの世代。マスタ構造を変えたらここを上げる。
  CACHE_VERSION: 'v3',
  CACHE_TTL_SEC: 21600, // 6時間
  // CacheServiceの1値あたり上限は100KB。日本語は1文字3バイトになり得るので
  // 文字数ベースで3万文字（最悪90KB）に抑える。
  CACHE_CHUNK_CHARS: 30000,

  SHEET_MENU: 'メニューマスタ',
  SHEET_SUBMIT_TO: '提出先マスタ',
  SHEET_MAIL_TEMPLATE: 'メールテンプレートマスタ',
  SHEET_DISCOUNT: '割引繁忙期マスタ',
  SHEET_SETTINGS: '設定マスタ',
  SHEET_STAFF: '担当者マスタ',
  SHEET_CELL_DEF: '差し込みセル定義',
  SHEET_LOG: 'ログ',

  SHEET_ESTIMATE_DATA: '見積書/データ格納',
  SHEET_INVOICE_DATA: '請求書/データ格納',

  TEMP_ESTIMATE_SHEET: '一時作業用/見積書',
  TEMP_INVOICE_SHEET: '一時作業用/請求書'
};

const SETTINGS_HEADERS = ['設定キー', '設定値', '説明', '備考_現場入力'];

const SETTING_ALIASES = {
  estimate_app_gmail_account: 'GAS実行用Gmail',
  default_sender_alias: '送信元メール',
  default_fixed_cc: '固定CC',
  representative_email: '代表者メール',
  highway_search_url: '高速料金検索URL',
  parking_note: '駐車場代注記',
  line_notice_text: 'LINE一報文言',

  master_spreadsheet_id: 'マスタスプレッドシートID',
  template_spreadsheet_id: '見積請求書テンプレートスプレッドシートID',
  pdf_template_spreadsheet_id: 'PDF生成用テンプレートスプレッドシートID',
  estimate_pdf_folder_id: '見積書PDF保存フォルダID',
  invoice_pdf_folder_id: '請求書PDF保存フォルダID',

  company_name: '会社名',
  company_zip: '会社郵便番号',
  company_address: '会社住所',
  company_tel: '会社電話番号',
  company_fax: '会社FAX',
  company_email: '会社メールアドレス',
  company_web: '会社WEB',

  tax_rate: '税率',
  busy_season_surcharge: '繁忙期加算額',
  busy_surcharge_unit: '繁忙期加算単位',
  auto_discount_enabled: '自動割引有効',
  large_discount_alert_ratio: '大幅値引き警告率',

  default_closing_day: '既定_請求締め日',
  default_payment_site: '既定_支払サイト',
  parking_tax_type: '駐車場代_税区分',
  invoice_remarks_note: '請求書備考注記',
  logo_file_id: 'ロゴファイルID',
  stamp_image_file_id: '社印画像ファイルID'
};

/* ===================== 実行単位のメモ ===================== */

// 1回のGAS実行の中で同じものを二度読まないための入れ物。
const RUNTIME = {
  context: null,
  calcEngine: null,
  spreadsheets: {},
  headerInfo: {},
  logs: []
};

/* ===================== エントリポイント ===================== */

function doGet() {
  return HtmlService
    .createTemplateFromFile('Index')
    .evaluate()
    .setTitle('見積作成Webアプリ')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}

function include(filename) {
  return HtmlService.createHtmlOutputFromFile(filename).getContent();
}

/* ===================== 計算エンジンの共有 ===================== */

/**
 * Calc.html をサーバー側でも評価して CalcEngine を得る。
 * クライアントとサーバーで計算式が二重管理にならないようにするための仕掛け。
 */
function getCalcEngine_() {
  if (RUNTIME.calcEngine) return RUNTIME.calcEngine;

  const src = HtmlService.createHtmlOutputFromFile('Calc').getContent()
    .replace(/<script[^>]*>/gi, '')
    .replace(/<\/script>/gi, '');

  RUNTIME.calcEngine = eval(src + '\nCalcEngine;');
  return RUNTIME.calcEngine;
}

function calculateEstimate_(payload, ctx) {
  return getCalcEngine_().calculate(payload, buildCalcContext_(ctx));
}

function buildCalcContext_(ctx) {
  return {
    taxRate: ctx.taxRate,
    busySurcharge: ctx.busySurcharge,
    busySurchargeUnit: ctx.busySurchargeUnit,
    autoDiscountEnabled: ctx.autoDiscountEnabled,
    largeDiscountRatio: ctx.largeDiscountRatio,
    menuMap: ctx.menuMap,
    discountRules: ctx.discountRules
  };
}

/** クライアントへ渡す版。menuMap は menus から組み立てられるので省いて転送量を半減させる。 */
function buildClientCalcContext_(ctx) {
  const client = buildCalcContext_(ctx);
  delete client.menuMap;
  return client;
}

/* ===================== API ===================== */

/**
 * 画面初期表示。マスタ一式をキャッシュから返す。
 * 旧 apiInit() と違い、セットアップ／マイグレーションは一切走らせない。
 */
function apiBootstrap() {
  return withApi_('初期表示', '', function () {
    const ctx = loadContext_();

    return {
      ok: true,
      settings: {
        高速料金検索URL: ctx.settings['高速料金検索URL'] || '',
        駐車場代注記: ctx.settings['駐車場代注記'] || '',
        LINE一報文言: ctx.settings['LINE一報文言'] || 'メール送信後、LINEで代表者へ一報を入れてください。',
        会社名: ctx.settings['会社名'] || '',
        固定CC: ctx.settings['固定CC'] || '',
        送信元メール: ctx.settings['送信元メール'] || APP.DEFAULT_EXECUTION_EMAIL
      },
      // menuMap は menus と同じ中身なので送らない。クライアント側で組み立てる。
      calcContext: buildClientCalcContext_(ctx),
      menus: ctx.menus,
      submitTargets: ctx.submitTargets,
      staff: ctx.staff,
      warnings: ctx.warnings,
      cached: ctx.fromCache,
      user: getCurrentUser_()
    };
  });
}

// 旧クライアントがキャッシュされていても動くように名前を残す。
function apiInit() {
  return apiBootstrap();
}

function apiCalculateEstimate(payload) {
  return withApi_('見積計算', '', function () {
    return { ok: true, calc: calculateEstimate_(payload, loadContext_()) };
  });
}

/**
 * フェーズ1：見積データの保存だけを行う。
 * PDFとメールは apiBuildDocuments() に分けて、現場を待たせない。
 */
function apiSaveEstimate(payload) {
  return withApi_('見積作成', '', function () {
    const ctx = loadContext_();
    const sheet = getEstimateDataSheet_(ctx);
    const calc = calculateEstimate_(payload, ctx);
    const requestId = String((payload || {}).requestId || '').trim();

    const lock = LockService.getScriptLock();
    lock.waitLock(30000);

    let estimateId = '';
    let rowNumber = 0;
    let duplicated = false;

    try {
      // 通信再送や複数端末の同時操作で同じ見積が2件できるのを防ぐ。
      // ロックの中で見るので、後から来た方は必ず既存を引き当てる。
      const seen = requestId ? readSavedRequest_(requestId) : null;

      if (seen) {
        estimateId = seen.estimateId;
        rowNumber = seen.rowNumber;
        duplicated = true;
      } else {
        estimateId = generateEstimateId_(sheet);
        const record = buildEstimateRecord_(payload, ctx, calc, estimateId);
        record.request_id = requestId;
        rowNumber = appendObject_(sheet, record);
        if (requestId) rememberSavedRequest_(requestId, estimateId, rowNumber);
      }
    } finally {
      lock.releaseLock();
    }

    queueLog_(
      duplicated ? '見積作成(再送)' : '見積作成',
      estimateId,
      duplicated
        ? '同じ操作の再送のため既存の見積を返しました。'
        : '見積データを保存しました。合計 ' + calc.grandTotal + '円',
      ''
    );

    return {
      ok: true,
      estimateId: estimateId,
      rowNumber: rowNumber,
      calc: calc,
      duplicated: duplicated,
      reviewFlag: calc.reviewFlag === true
    };
  });
}

function requestCacheKey_(requestId) {
  return 'estimate_req_' + requestId;
}

function readSavedRequest_(requestId) {
  try {
    const raw = CacheService.getScriptCache().get(requestCacheKey_(requestId));
    return raw ? JSON.parse(raw) : null;
  } catch (e) {
    return null;
  }
}

function rememberSavedRequest_(requestId, estimateId, rowNumber) {
  try {
    CacheService.getScriptCache().put(
      requestCacheKey_(requestId),
      JSON.stringify({ estimateId: estimateId, rowNumber: rowNumber }),
      1800 // 30分。再送はこの範囲で起きる
    );
  } catch (e) {
    console.warn('リクエストIDの記録に失敗しました：' + toErrorMessage_(e));
  }
}

/**
 * フェーズ2：PDF生成 → Driveへ保存 → Gmail下書き作成 → 見積データへ書き戻し。
 * PDFが失敗しても見積データは残す。メールが失敗してもPDFと本文は返す。
 */
function apiBuildDocuments(estimateId, rowNumber) {
  return withApi_('帳票生成', estimateId, function () {
    const ctx = loadContext_();
    const sheet = getEstimateDataSheet_(ctx);
    const found = findEstimateRecord_(sheet, estimateId, rowNumber);
    if (!found) throw new Error('見積IDが見つかりません：' + estimateId);

    const record = found.record;
    const calc = rebuildCalcFromRecord_(record, ctx);
    const errors = [];
    const writeback = { 更新日時: new Date() };

    let pdfFile = null;
    let pdfUrl = '';
    let pdfFileId = '';

    try {
      const pdf = generateEstimatePdf_(record, calc, ctx);
      pdfFile = pdf.file;
      pdfUrl = pdf.url;
      pdfFileId = pdf.fileId;

      writeback.PDF_URL = pdfUrl;
      writeback.PDF_FILE_ID = pdfFileId;
      record.PDF_URL = pdfUrl;
      record.PDF_FILE_ID = pdfFileId;

      queueLog_('PDF生成', estimateId, 'PDFを生成しました。', '');
    } catch (e) {
      const msg = toErrorMessage_(e);
      errors.push('PDF生成失敗：' + msg);
      queueLog_('エラー', estimateId, 'PDF生成に失敗しました。', msg);
    }

    let draftUrl = '';
    let draftId = '';
    let mailPreview = null;

    try {
      if (!pdfFile) throw new Error('PDF生成に失敗したため、PDF添付済みメール下書きは作成していません。');

      const draft = createEstimateMailDraft_(record, calc, ctx, pdfFile);
      draftUrl = draft.draftUrl;
      draftId = draft.draftId;

      writeback.メール下書きURL = draftUrl;
      writeback.メール下書きID = draftId;
      writeback.メール下書き作成日時 = new Date();

      queueLog_('メール下書き作成', estimateId, 'Gmail下書きを作成しました。', '');
    } catch (e) {
      const msg = toErrorMessage_(e);
      errors.push('メール下書き作成失敗：' + msg);
      mailPreview = buildEstimateMailPreview_(record, calc, ctx);
      queueLog_('エラー', estimateId, 'メール下書き作成に失敗しました。', msg);
    }

    // 書き戻しは1回にまとめる（旧実装は毎回シートを検索し直していた）
    updateObjectAtRow_(sheet, found.rowNumber, writeback);

    return {
      ok: true,
      estimateId: estimateId,
      pdfUrl: pdfUrl,
      pdfFileId: pdfFileId,
      draftUrl: draftUrl,
      draftId: draftId,
      errors: errors,
      mailPreview: mailPreview
    };
  });
}

/** 旧インターフェース互換。保存と帳票生成を続けて実行する。 */
function apiCreateEstimate(payload) {
  const saved = apiSaveEstimate(payload);
  if (!saved.ok) return saved;

  const built = apiBuildDocuments(saved.estimateId, saved.rowNumber);

  return {
    ok: true,
    estimateId: saved.estimateId,
    rowNumber: saved.rowNumber,
    calc: saved.calc,
    pdfUrl: built.pdfUrl || '',
    pdfFileId: built.pdfFileId || '',
    draftUrl: built.draftUrl || '',
    draftId: built.draftId || '',
    errors: built.ok ? built.errors : [built.error],
    mailPreview: built.mailPreview || null,
    representativeDraftAvailable: saved.reviewFlag === true
  };
}

function apiCreateRepresentativeDraft(estimateId) {
  return withApi_('代表者確認メール下書き作成', estimateId, function () {
    const ctx = loadContext_();
    const representativeEmail = String(ctx.settings['代表者メール'] || '').trim();
    if (!representativeEmail) {
      throw new Error('設定マスタの representative_email / 代表者メール が未設定です。');
    }

    const sheet = getEstimateDataSheet_(ctx);
    const found = findEstimateRecord_(sheet, estimateId);
    if (!found) throw new Error('見積IDが見つかりません：' + estimateId);

    const record = found.record;
    const template = ctx.mailTemplates['代表者確認依頼'] || getFallbackRepresentativeTemplate_();

    const tokens = buildTokensFromRecord_(record, ctx, {
      例外理由: record['例外理由'] || '',
      PDF_URL: record['PDF_URL'] || '',
      作成日時: formatDateTime_(record['作成日時'] || new Date())
    });

    const draft = GmailApp.createDraft(
      representativeEmail,
      renderTemplate_(template.subject, tokens),
      renderTemplate_(template.body, tokens),
      buildGmailOptions_(record['送信元メール'], '', ctx.settings)
    );

    const draftId = draft.getId();
    const draftUrl = getGmailDraftsUrl_(ctx.settings);

    updateObjectAtRow_(sheet, found.rowNumber, {
      代表者確認メール下書きURL: draftUrl,
      代表者確認メール下書きID: draftId,
      代表者確認メール作成日時: new Date(),
      更新日時: new Date()
    });

    queueLog_('代表者確認メール下書き作成', estimateId, '代表者確認メール下書きを作成しました。', '');
    return { ok: true, draftId: draftId, draftUrl: draftUrl };
  });
}

function apiSearchEstimates(criteria) {
  return withApi_('過去見積検索', '', function () {
    const ctx = loadContext_();
    const sheet = getEstimateDataSheet_(ctx);
    const c = criteria || {};

    // 検索に使う列だけ読む。203列を全部読むと遅い。
    const wanted = ['estimate_id', '作成日時', '顧客名', '案件名', '案件タイプ',
      '合計金額', 'PDF_URL', '例外フラグ', 'invoice_id'];
    const rows = readColumns_(sheet, wanted);

    const results = rows
      .filter(function (r) {
        return matchText_(r['estimate_id'], c.estimateId)
          && matchText_(r['顧客名'], c.customerName)
          && matchText_(r['案件名'], c.projectName)
          && matchText_(r['案件タイプ'], c.projectType)
          && matchDate_(r['作成日時'], c.createdDate);
      })
      .sort(function (a, b) {
        return new Date(b['作成日時']).getTime() - new Date(a['作成日時']).getTime();
      })
      .slice(0, 50)
      .map(function (r) {
        return {
          estimate_id: r['estimate_id'] || '',
          created_at: formatDateTime_(r['作成日時']),
          customer_name: r['顧客名'] || '',
          project_name: r['案件名'] || '',
          project_type: r['案件タイプ'] || '',
          total_amount: toNumber_(r['合計金額']),
          total_amount_display: formatYen_(toNumber_(r['合計金額'])),
          pdf_url: r['PDF_URL'] || '',
          invoice_id: r['invoice_id'] || '',
          exception_flag: String(r['例外フラグ'] || '') === 'TRUE'
        };
      });

    queueLog_('過去見積呼び出し', '', '検索件数：' + results.length, '');
    return { ok: true, results: results };
  });
}

/**
 * 見積プレビュー。PDFを開かずにアプリ内で中身を確認するためのもの。
 * 金額は保存レコードから計算し直すので、PDFと同じ数字になる。
 */
function apiGetEstimateDetail(estimateId) {
  return withApi_('見積プレビュー', estimateId, function () {
    const ctx = loadContext_();
    const sheet = getEstimateDataSheet_(ctx);
    const found = findEstimateRecord_(sheet, estimateId);
    if (!found) throw new Error('見積IDが見つかりません：' + estimateId);

    const r = found.record;
    const calc = rebuildCalcFromRecord_(r, ctx);

    return {
      ok: true,
      estimateId: estimateId,
      header: {
        作成日時: formatDateTime_(r['作成日時']),
        案件タイプ: r['案件タイプ'] || '',
        提出先名: r['提出先名'] || '',
        見積書宛名: (r['見積書宛名'] || '') + ' ' + (r['敬称'] || ''),
        顧客名: r['顧客名'] || '',
        案件名: r['案件名'] || '',
        現場住所: r['現場住所'] || '',
        作業予定日: toDateInputValue_(r['作業予定日']),
        担当者: r['担当者'] || r['作成者'] || '',
        宛先メール: r['宛先メール'] || '',
        固定CC: r['固定CC'] || '',
        備考: r['備考'] || '',
        例外理由: r['例外理由'] || '',
        PDF_URL: r['PDF_URL'] || '',
        メール下書きURL: r['メール下書きURL'] || '',
        invoice_id: r['invoice_id'] || '',
        project_status: r['project_status'] || ''
      },
      rows: calc.pdfRows,
      totals: {
        書類小計: calc.documentSubtotal,
        課税小計: calc.taxableSubtotal,
        非課税小計: calc.nonTaxableSubtotal,
        消費税: calc.tax,
        合計金額: calc.grandTotal,
        繁忙期加算額: calc.busyAmount,
        自動割引額: calc.autoDiscountApplied,
        明細値引き合計: calc.lineDiscountTotal,
        調整合計額: calc.adjustmentTotal
      },
      display: calc.summaryDisplay
    };
  });
}

function apiLoadEstimateForClone(estimateId) {
  return withApi_('複製編集', estimateId, function () {
    const ctx = loadContext_();
    const sheet = getEstimateDataSheet_(ctx);
    const found = findEstimateRecord_(sheet, estimateId);
    if (!found) throw new Error('見積IDが見つかりません：' + estimateId);

    const r = found.record;
    const details = [];

    for (let i = 1; i <= APP.MAX_DETAIL_ROWS; i++) {
      const p = pad2_(i);
      const name = r['明細' + p + '_品名'];
      const menuId = r['明細' + p + '_メニューID'];
      if (!name && !menuId) continue;

      details.push({
        menuId: menuId || '',
        menuName: name || '',
        menuType: r['明細' + p + '_メニュータイプ'] || '',
        qty: toNumber_(r['明細' + p + '_数量']) || 1,
        unit: r['明細' + p + '_単位'] || '',
        unitPrice: toNumber_(r['明細' + p + '_単価']),
        taxType: r['明細' + p + '_税区分'] || '',
        note: r['明細' + p + '_備考'] || '',
        lineDiscountMode: 'amount',
        lineDiscountValue: toNumber_(r['明細' + p + '_値引き額'])
      });
    }

    queueLog_('複製編集', estimateId, '見積複製用データを読み込みました。', '');

    return {
      ok: true,
      sourceEstimateId: estimateId,
      payload: {
        original_estimate_id: estimateId,
        projectType: r['案件タイプ'] || '',
        submitToName: r['提出先名'] || '',
        customerName: r['顧客名'] || '',
        projectName: r['案件名'] || '',
        siteAddress: r['現場住所'] || '',
        workDate: toDateInputValue_(r['作業予定日']),
        staff: r['担当者'] || '',
        remarks: r['備考'] || '',
        selfRecipientEmail: r['宛先メール'] || '',
        highwayFee: toNumber_(r['高速代']),
        busyManual: parseBooleanLoose_(r['繁忙期_手動設定']),
        discountManual: parseBooleanLoose_(r['割引_手動設定']),
        adjustments: parseAdjustmentsJson_(r['調整_JSON']),
        targetTotal: 0,
        details: details
      }
    };
  });
}

/* ===================== 保存レコード ===================== */

function buildEstimateRecord_(payload, ctx, calc, estimateId) {
  const p = payload || {};
  const submit = resolveSubmitTarget_(p, ctx);
  const now = new Date();

  // 端数調整で自動生成された行も含めて保存する（複製時に再現するため）
  const manualAdjustments = calc.appliedAdjustments || [];

  const record = {
    estimate_id: estimateId,
    original_estimate_id: p.original_estimate_id || '',
    invoice_id: '',
    invoice_source_flag: '見積作成',
    project_status: '見積作成済',
    作成日時: now,
    更新日時: now,
    作成者: p.staff || getCurrentUser_(),
    案件タイプ: p.projectType || '',
    提出先名: submit.submitToName || '',
    見積書宛名: submit.addresseeName || '',
    敬称: submit.addresseeSuffix || '',
    宛先メール: submit.to || '',
    固定CC: submit.cc || '',
    送信元メール: submit.from || '',
    顧客名: p.customerName || '',
    案件名: p.projectName || '',
    現場住所: p.siteAddress || '',
    作業予定日: parseDateInput_(p.workDate) || '',
    担当者: p.staff || '',
    見積日: now,
    見積番号: estimateId,
    件名: p.projectName || p.customerName || '',
    本文テンプレート種別: submit.templateType || '',
    備考: p.remarks || '',
    駐車場代注記: ctx.settings['駐車場代注記'] || '',
    高速代: calc.highwayFee,
    高速代_税区分: '非課税',
    明細小計: calc.lineSubtotal,
    割引額: calc.discountTotal,
    繁忙期加算額: calc.busyAmount,
    非課税小計: calc.nonTaxableSubtotal,
    課税小計: calc.taxableSubtotal,
    消費税: calc.tax,
    合計金額: calc.grandTotal,
    繁忙期_自動判定: boolText_(calc.busyAuto),
    繁忙期_手動設定: boolText_(calc.busyManual),
    割引_自動判定: boolText_(calc.autoDiscountAuto),
    割引_手動設定: boolText_(calc.autoDiscountOn),
    例外フラグ: boolText_(calc.exceptionFlag),
    要代表者確認: boolText_(calc.reviewFlag),
    例外理由: calc.exceptionReasons.join('\n'),
    PDF_URL: '',
    PDF_FILE_ID: '',
    メール下書きURL: '',
    メール下書きID: '',
    メール下書き作成日時: '',
    代表者確認メール下書きURL: '',
    代表者確認メール下書きID: '',
    代表者確認メール作成日時: '',
    複製元見積ID: p.original_estimate_id || '',
    内部メモ: '',
    request_id: '',

    /* --- 変則割引（今回追加） --- */
    自動割引種別: calc.autoDiscountType || '',
    自動割引額: calc.autoDiscountApplied,
    明細値引き合計: calc.lineDiscountTotal,
    調整合計額: calc.adjustmentTotal,
    合計指定額: calc.targetTotal || '',
    調整_JSON: JSON.stringify(manualAdjustments.map(function (a) {
      return {
        name: a.name, kind: a.kind, mode: a.mode, value: a.value,
        base: a.base, taxType: a.taxType, note: a.note, auto: a.auto, amount: a.amount
      };
    }))
  };

  for (let i = 1; i <= APP.MAX_ADJUSTMENT_SLOTS; i++) {
    const a = manualAdjustments[i - 1];
    record['調整' + pad2_(i) + '_名称'] = a ? a.name : '';
    record['調整' + pad2_(i) + '_金額'] = a ? (a.kind === 'surcharge' ? a.amount : -a.amount) : '';
  }

  for (let i = 1; i <= APP.MAX_DETAIL_ROWS; i++) {
    const pfx = '明細' + pad2_(i) + '_';
    const line = calc.lines[i - 1];
    record[pfx + '品名'] = line ? line.name : '';
    record[pfx + 'メニューID'] = line ? line.menuId : '';
    record[pfx + 'メニュータイプ'] = line ? line.menuType : '';
    record[pfx + '数量'] = line ? line.qty : '';
    record[pfx + '単位'] = line ? line.unit : '';
    record[pfx + '単価'] = line ? line.unitPrice : '';
    record[pfx + '金額'] = line ? line.amount : '';
    record[pfx + '税区分'] = line ? line.taxType : '';
    record[pfx + '備考'] = line ? line.note : '';
    record[pfx + '値引き額'] = line && line.lineDiscount ? line.lineDiscount : '';
  }

  return record;
}

/**
 * 保存済みレコードから計算結果を復元する。
 * PDF生成・メール本文で使うので、保存時と同じ金額になる必要がある。
 */
function rebuildCalcFromRecord_(record, ctx) {
  const details = [];

  for (let i = 1; i <= APP.MAX_DETAIL_ROWS; i++) {
    const p = pad2_(i);
    const menuId = record['明細' + p + '_メニューID'];
    if (!menuId) continue;

    details.push({
      menuId: menuId,
      qty: toNumber_(record['明細' + p + '_数量']),
      lineDiscountMode: 'amount',
      lineDiscountValue: toNumber_(record['明細' + p + '_値引き額'])
    });
  }

  return calculateEstimate_({
    projectType: record['案件タイプ'] || '',
    remarks: record['備考'] || '',
    workDate: toDateInputValue_(record['作業予定日']),
    highwayFee: toNumber_(record['高速代']),
    busyManual: parseBooleanLoose_(record['繁忙期_手動設定']),
    discountManual: parseBooleanLoose_(record['割引_手動設定']),
    adjustments: parseAdjustmentsJson_(record['調整_JSON']),
    targetTotal: 0, // 保存済みの調整行をそのまま使うので再逆算しない
    details: details
  }, ctx);
}

function parseAdjustmentsJson_(value) {
  const text = String(value || '').trim();
  if (!text) return [];

  try {
    const parsed = JSON.parse(text);
    return Array.isArray(parsed) ? parsed : [];
  } catch (e) {
    return [];
  }
}

function resolveSubmitTarget_(payload, ctx) {
  const p = payload || {};
  const projectType = String(p.projectType || '').trim();
  const target = (ctx.submitTargets || []).find(function (t) { return t.projectType === projectType; }) || null;

  if (projectType === '自社') {
    return {
      submitToName: '自社',
      addresseeName: p.customerName || '',
      addresseeSuffix: p.addresseeSuffix || '様',
      to: p.selfRecipientEmail || '',
      cc: target ? target.cc : (ctx.settings['固定CC'] || ''),
      from: target ? (target.from || ctx.settings['送信元メール']) : (ctx.settings['送信元メール'] || APP.DEFAULT_EXECUTION_EMAIL),
      templateType: target ? (target.templateType || '自社案件_見積送付') : '自社案件_見積送付'
    };
  }

  // 元請でも提出先マスタに宛先が無ければ現場の手入力を使う。
  // マスタ登録待ちでGmail下書きが作れない状態を作らないため。
  const manualTo = String(p.selfRecipientEmail || '').trim();

  if (!target) {
    return {
      submitToName: projectType,
      addresseeName: projectType,
      addresseeSuffix: '御中',
      to: manualTo,
      cc: ctx.settings['固定CC'] || '',
      from: ctx.settings['送信元メール'] || APP.DEFAULT_EXECUTION_EMAIL,
      templateType: '元請案件_見積送付'
    };
  }

  return {
    submitToName: target.submitToName || projectType,
    addresseeName: target.addresseeName || target.submitToName || projectType,
    addresseeSuffix: target.addresseeName ? '' : '御中',
    to: target.to || manualTo,
    cc: target.cc || '',
    from: target.from || ctx.settings['送信元メール'] || APP.DEFAULT_EXECUTION_EMAIL,
    templateType: target.templateType || '元請案件_見積送付'
  };
}

/* ===================== PDF ===================== */

function generateEstimatePdf_(record, calc, ctx) {
  // PDF専用の軽いテンプレートがあればそれを複製する。
  // 無ければ従来どおり帳票/DBスプレッドシートを複製する（データが増えるほど遅くなる）。
  const templateId = String(ctx.settings['PDF生成用テンプレートスプレッドシートID'] || '').trim()
    || ctx.settings['見積請求書テンプレートスプレッドシートID']
    || APP.DEFAULT_TEMPLATE_SS_ID;

  const folderId = ctx.settings['見積書PDF保存フォルダID'] || APP.DEFAULT_ESTIMATE_FOLDER_ID;

  if (!templateId) throw new Error('見積請求書テンプレートスプレッドシートIDが未設定です。');
  if (!folderId) throw new Error('見積書PDF保存フォルダIDが未設定です。');

  const folder = DriveApp.getFolderById(folderId);
  const tmpFile = DriveApp.getFileById(templateId).makeCopy('tmp_' + record.estimate_id + '_' + Date.now());
  const tmpSs = SpreadsheetApp.openById(tmpFile.getId());

  try {
    const cellDefs = getCellDefMap_('見積書', ctx);
    const targetSheetName = getTargetSheetNameFromDefs_(cellDefs, APP.TEMP_ESTIMATE_SHEET);
    const sheet = tmpSs.getSheetByName(targetSheetName);
    if (!sheet) throw new Error('対象シートが見つかりません：' + targetSheetName);

    fillEstimateSheet_(sheet, cellDefs, record, calc, ctx.settings);
    SpreadsheetApp.flush();

    const pdfBlob = exportSheetToPdfBlob_(tmpSs.getId(), sheet.getSheetId());
    pdfBlob.setName(sanitizeFileName_(
      record.estimate_id + '_見積書_' + record['顧客名'] + '_' + record['案件名'] + '.pdf'
    ));

    const savedFile = folder.createFile(pdfBlob);
    return { file: savedFile, url: savedFile.getUrl(), fileId: savedFile.getId() };
  } finally {
    tmpFile.setTrashed(true);
  }
}

function fillEstimateSheet_(sheet, defs, record, calc, settings) {
  const remarksText = [record['備考'] || '', record['駐車場代注記'] || ''].filter(String).join('\n');

  setByKeys_(sheet, defs, {
    document_date: formatDate_(record['見積日'] || new Date(), 'yyyy/MM/dd'),
    document_no_label: '見積番号：',
    estimate_id: record.estimate_id,
    title: '御  見  積  書',
    addressee_name: record['見積書宛名'] || '',
    addressee_suffix: record['敬称'] || '',
    company_name: settings['会社名'] || '',
    company_zip: settings['会社郵便番号'] || '',
    company_address: settings['会社住所'] || '',
    company_tel: settings['会社電話番号'] || '',
    company_fax: settings['会社FAX'] || '',
    project_name: record['案件名'] || record['顧客名'] || '',
    project_suffix: 'について',
    greeting: '下記の通り御見積り申し上げます。',
    total_amount_label: 'お見積金額',
    total_amount_display: calc.grandTotal,
    total_amount_unit: '円',
    detail_header_name: '品名',
    detail_header_qty: '数量',
    detail_header_unit_price: '単価',
    detail_header_amount: '金額',
    remarks: remarksText,
    subtotal_label: '小計',
    subtotal: calc.documentSubtotal,
    tax_label: '消費税',
    tax: calc.tax,
    grand_total_label: '合計',
    grand_total: calc.grandTotal
  });

  writeDetailRows_(sheet, defs, calc.pdfRows.slice(0, APP.MAX_DETAIL_ROWS));
}

/**
 * 明細をまとめて書き込む。旧実装は1セルずつ64回 setValue していた。
 * ここでは列ごとに1回の setValues にまとめる。
 */
function writeDetailRows_(sheet, defs, rows) {
  const nameDef = defs['detail_name_range'];
  const qtyDef = defs['detail_qty_range'];
  const unitDef = defs['detail_unit_price_range'];
  const amountDef = defs['detail_amount_range'];

  if (!nameDef || !qtyDef || !unitDef || !amountDef) {
    throw new Error('差し込みセル定義に明細範囲が不足しています。');
  }

  const nameRange = sheet.getRange(nameDef.a1);
  const maxRows = Math.min(APP.MAX_DETAIL_ROWS, nameRange.getNumRows());

  const columns = [
    { range: nameRange, pick: function (r) { return r.name || ''; } },
    { range: sheet.getRange(qtyDef.a1), pick: function (r) { return r.qty === undefined || r.qty === '' ? '' : r.qty; } },
    { range: sheet.getRange(unitDef.a1), pick: function (r) { return r.unitPrice === undefined || r.unitPrice === '' ? '' : r.unitPrice; } },
    { range: sheet.getRange(amountDef.a1), pick: function (r) { return r.amount === undefined || r.amount === '' ? '' : r.amount; } }
  ];

  columns.forEach(function (col) {
    const values = [];
    for (let i = 0; i < maxRows; i++) values.push([col.pick(rows[i] || {})]);
    sheet.getRange(col.range.getRow(), col.range.getColumn(), maxRows, 1).setValues(values);
  });
}

function exportSheetToPdfBlob_(spreadsheetId, gid) {
  const url = 'https://docs.google.com/spreadsheets/d/' + encodeURIComponent(spreadsheetId) + '/export'
    + '?format=pdf'
    + '&gid=' + encodeURIComponent(gid)
    + '&size=A4&portrait=true&fitw=true'
    + '&sheetnames=false&printtitle=false&pagenumbers=false&gridlines=false&fzr=false';

  const res = UrlFetchApp.fetch(url, {
    headers: { Authorization: 'Bearer ' + ScriptApp.getOAuthToken() },
    muteHttpExceptions: true
  });

  if (res.getResponseCode() !== 200) {
    throw new Error('PDFエクスポートに失敗しました。HTTP ' + res.getResponseCode()
      + ' / ' + res.getContentText().slice(0, 300));
  }

  return res.getBlob().setContentType(MimeType.PDF);
}

/* ===================== Gmail ===================== */

function createEstimateMailDraft_(record, calc, ctx, pdfFile) {
  const to = String(record['宛先メール'] || '').trim();
  if (!to) throw new Error('宛先メールが未設定です。提出先マスタか自社案件の宛先入力を確認してください。');

  const preview = buildEstimateMailPreview_(record, calc, ctx);
  const options = buildGmailOptions_(record['送信元メール'], record['固定CC'], ctx.settings);
  options.attachments = [pdfFile.getBlob()];

  const draft = GmailApp.createDraft(to, preview.subject, preview.body, options);
  return { draftId: draft.getId(), draftUrl: getGmailDraftsUrl_(ctx.settings) };
}

function buildEstimateMailPreview_(record, calc, ctx) {
  const templateType = record['本文テンプレート種別'] || '自社案件_見積送付';
  const template = ctx.mailTemplates[templateType] || getFallbackEstimateTemplate_();

  const tokens = buildTokensFromRecord_(record, ctx, {
    見積金額: formatYen_(calc.grandTotal),
    作成日: formatDate_(record['見積日'] || new Date(), 'yyyy/MM/dd'),
    PDF_URL: record['PDF_URL'] || ''
  });

  return {
    to: record['宛先メール'] || '',
    cc: record['固定CC'] || '',
    from: record['送信元メール'] || '',
    subject: renderTemplate_(template.subject, tokens),
    body: renderTemplate_(template.body, tokens)
  };
}

function buildGmailOptions_(fromEmail, cc, settings) {
  const options = {};
  if (cc) options.cc = cc;
  if (settings['会社名']) options.name = settings['会社名'];

  const requestedFrom = String(fromEmail || '').trim();
  if (requestedFrom) {
    // エイリアスが未設定なら from を指定せず実行アカウントで下書きを作る
    if (GmailApp.getAliases().indexOf(requestedFrom) >= 0) options.from = requestedFrom;
  }

  return options;
}

function getGmailDraftsUrl_(settings) {
  const account = String((settings || {})['GAS実行用Gmail'] || APP.DEFAULT_EXECUTION_EMAIL).trim();
  return 'https://mail.google.com/mail/?authuser=' + encodeURIComponent(account) + '#drafts';
}

/* ===================== マスタ読み込み（キャッシュ付き） ===================== */

function loadContext_() {
  if (RUNTIME.context) return RUNTIME.context;

  const cached = readCachedContext_();
  if (cached) {
    cached.fromCache = true;
    RUNTIME.context = cached;
    return cached;
  }

  const ctx = buildContextFromSheets_();
  ctx.fromCache = false;
  writeCachedContext_(ctx);
  RUNTIME.context = ctx;
  return ctx;
}

function buildContextFromSheets_() {
  const masterSs = getMasterSs_();
  const warnings = [];

  const settings = readSettings_(masterSs);
  const menus = readMenus_(masterSs, warnings);
  const menuMap = {};
  menus.forEach(function (m) { menuMap[m.menuId] = m; });

  return {
    settings: settings,
    taxRate: normalizeRate_(settings['税率'] || 0.10) || 0.10,
    busySurcharge: toNumber_(settings['繁忙期加算額'] || 3300),
    busySurchargeUnit: String(settings['繁忙期加算単位'] || '数量ごと').trim(),
    autoDiscountEnabled: parseBooleanLoose_(settings['自動割引有効']),
    largeDiscountRatio: normalizeRate_(settings['大幅値引き警告率'] || 0.30) || 0.30,
    menus: menus,
    menuMap: menuMap,
    submitTargets: readSubmitTargets_(masterSs, settings),
    staff: readStaff_(masterSs),
    mailTemplates: readMailTemplates_(masterSs, warnings),
    discountRules: readDiscountRules_(masterSs, warnings),
    cellDefs: readCellDefs_(masterSs),
    warnings: warnings
  };
}

function contextCacheKey_(suffix) {
  return 'estimate_ctx_' + APP.CACHE_VERSION + '_' + suffix;
}

function readCachedContext_() {
  try {
    const cache = CacheService.getScriptCache();
    const meta = cache.get(contextCacheKey_('meta'));
    if (!meta) return null;

    const chunkCount = Number(meta);
    if (!(chunkCount > 0)) return null;

    const keys = [];
    for (let i = 0; i < chunkCount; i++) keys.push(contextCacheKey_(i));

    const parts = cache.getAll(keys);
    let json = '';

    for (let i = 0; i < chunkCount; i++) {
      const part = parts[contextCacheKey_(i)];
      if (part === null || part === undefined) return null; // 一部だけ失効していたら作り直す
      json += part;
    }

    return JSON.parse(json);
  } catch (e) {
    console.warn('マスタキャッシュの読み込みに失敗しました：' + toErrorMessage_(e));
    return null;
  }
}

function writeCachedContext_(ctx) {
  try {
    const json = JSON.stringify(ctx);
    const cache = CacheService.getScriptCache();
    const entries = {};
    let chunkCount = 0;

    for (let i = 0; i < json.length; i += APP.CACHE_CHUNK_CHARS) {
      entries[contextCacheKey_(chunkCount)] = json.slice(i, i + APP.CACHE_CHUNK_CHARS);
      chunkCount++;
    }

    cache.putAll(entries, APP.CACHE_TTL_SEC);
    cache.put(contextCacheKey_('meta'), String(chunkCount), APP.CACHE_TTL_SEC);
  } catch (e) {
    // キャッシュに載らなくても動作はする。次回も実読みになるだけ。
    console.warn('マスタキャッシュの保存に失敗しました：' + toErrorMessage_(e));
  }
}

function clearContextCache_() {
  try {
    const cache = CacheService.getScriptCache();
    const meta = cache.get(contextCacheKey_('meta'));
    const keys = [contextCacheKey_('meta')];
    const count = Number(meta || 0);
    for (let i = 0; i < count; i++) keys.push(contextCacheKey_(i));
    cache.removeAll(keys);
  } catch (e) {
    console.warn(toErrorMessage_(e));
  }
  RUNTIME.context = null;
  RUNTIME.headerInfo = {};
}

/* ===================== 各マスタの読み取り ===================== */

function readSettings_(masterSs) {
  const sheet = masterSs.getSheetByName(APP.SHEET_SETTINGS);
  const settings = {};

  if (sheet) {
    readObjects_(sheet, ['設定キー', '設定値']).forEach(function (r) {
      const key = String(r['設定キー'] || r['キー'] || '').trim();
      if (!key) return;
      const value = r['設定値'] !== undefined ? r['設定値'] : r['値'];
      settings[key] = value;
      const alias = SETTING_ALIASES[key];
      if (alias) settings[alias] = value;
    });
  }

  applyDefaultSettingsValues_(settings);
  return settings;
}

function applyDefaultSettingsValues_(s) {
  if (!s['GAS実行用Gmail']) s['GAS実行用Gmail'] = APP.DEFAULT_EXECUTION_EMAIL;
  if (!s['送信元メール']) s['送信元メール'] = s['default_sender_alias'] || APP.DEFAULT_EXECUTION_EMAIL;
  if (!s['固定CC']) s['固定CC'] = '';
  if (!s['マスタスプレッドシートID']) s['マスタスプレッドシートID'] = APP.DEFAULT_MASTER_SS_ID;
  if (!s['見積請求書テンプレートスプレッドシートID']) s['見積請求書テンプレートスプレッドシートID'] = APP.DEFAULT_TEMPLATE_SS_ID;
  if (!s['見積書PDF保存フォルダID']) s['見積書PDF保存フォルダID'] = APP.DEFAULT_ESTIMATE_FOLDER_ID;
  if (!s['請求書PDF保存フォルダID']) s['請求書PDF保存フォルダID'] = APP.DEFAULT_INVOICE_FOLDER_ID;
  if (!s['税率']) s['税率'] = '0.10';
  if (!s['繁忙期加算額']) s['繁忙期加算額'] = '3300';
  if (!s['繁忙期加算単位']) s['繁忙期加算単位'] = '数量ごと';
  if (isBlank_(s['自動割引有効'])) s['自動割引有効'] = 'FALSE';
  if (!s['大幅値引き警告率']) s['大幅値引き警告率'] = '0.30';
  if (!s['既定_請求締め日']) s['既定_請求締め日'] = '月末';
  if (!s['既定_支払サイト']) s['既定_支払サイト'] = '翌月末';
  if (!s['駐車場代_税区分']) s['駐車場代_税区分'] = '課税';
}

/**
 * メニューマスタ。シート全体を1回だけ読む。
 * 旧実装はメニュー1件ごとに pickMenuActiveValue_() でシート全体を読み直しており、
 * 40メニューで80回のシート読み込みが発生していた（初期表示が遅い最大の原因）。
 */
function readMenus_(masterSs, warnings) {
  const sheet = masterSs.getSheetByName(APP.SHEET_MENU);
  if (!sheet) {
    warnings.push('メニューマスタが見つかりません。');
    return [];
  }

  const grid = readGrid_(sheet, ['メニューID', 'メニュー名']);
  if (!grid) return [];

  const headers = grid.headers;

  return grid.rows
    .map(function (row) {
      const menuId = String(pickRowValue_(headers, row, ['メニューID']) || '').trim();
      const rawMenuType = String(pickRowValue_(headers, row, ['メニュータイプ']) || '').trim();
      const busyRaw = pickRowValue_(headers, row, ['繁忙期加算対象', '繁忙期対象']);
      const discountRaw = pickRowValue_(headers, row, ['割引対象']);
      const invoiceRaw = pickRowValue_(headers, row, ['請求書流用', '請求書流用対象']);

      return {
        menuId: menuId,
        active: isActive_(pickRowValue_(headers, row, ['有効'])),
        name: String(pickRowValue_(headers, row, ['顧客表示名', 'メニュー名']) || '').trim(),
        rawMenuType: rawMenuType,
        menuType: normalizeMenuType_(menuId, rawMenuType),
        category: String(pickRowValue_(headers, row, ['カテゴリ']) || '').trim(),
        unitPriceRaw: pickRowValue_(headers, row, ['単価', '価格']),
        unitPrice: toNumber_(pickRowValue_(headers, row, ['単価', '価格'])),
        taxType: String(pickRowValue_(headers, row, ['税区分']) || '課税').trim(),
        unit: String(pickRowValue_(headers, row, ['数量単位', '単位']) || '').trim(),
        busyTarget: isBlank_(busyRaw) ? false : parseBooleanLoose_(busyRaw),
        busySurchargeRaw: pickRowValue_(headers, row, ['繁忙期加算額']) || '',
        discountTarget: isBlank_(discountRaw) ? false : parseBooleanLoose_(discountRaw),
        multipleDiscountTarget: parseBooleanLoose_(pickRowValue_(headers, row, ['複数台割引対象'])),
        invoiceReusable: isBlank_(invoiceRaw) ? true : parseBooleanLoose_(invoiceRaw),
        sortOrder: toNumber_(pickRowValue_(headers, row, ['表示順'])),
        note: String(pickRowValue_(headers, row, ['補足_現場入力', '備考']) || ''),
        requireCheck: String(pickRowValue_(headers, row, ['要確認事項']) || '')
      };
    })
    .filter(function (m) { return m.menuId && m.name && m.active; })
    .sort(function (a, b) { return (a.sortOrder || 9999) - (b.sortOrder || 9999); });
}

function normalizeMenuType_(menuId, rawMenuType) {
  if (String(menuId || '').indexOf('O') === 0) return 'オプション';
  const raw = String(rawMenuType || '');
  if (raw === 'オプション' || raw === 'セット') return 'オプション';
  return 'メイン';
}

function readSubmitTargets_(masterSs, settings) {
  const sheet = masterSs.getSheetByName(APP.SHEET_SUBMIT_TO);
  const targets = [];

  if (sheet) {
    readObjects_(sheet, ['案件タイプ', '提出先名']).forEach(function (r) {
      const projectType = String(r['案件タイプ'] || '').trim();
      if (!projectType || !isActive_(r['有効'])) return;

      targets.push({
        projectType: projectType,
        submitToName: String(r['提出先名'] || '').trim(),
        addresseeName: String(r['見積書宛名'] || '').trim(),
        to: String(r['宛先メール'] || '').trim(),
        cc: String(r['固定CC'] || '').trim(),
        from: String(r['送信元メール'] || '').trim(),
        templateType: String(r['メールテンプレート種別'] || '').trim(),
        // 請求日・支払期限は取引先ごとに条件が違うのでマスタで持つ
        closingDay: String(r['請求締め日'] || '').trim(),
        paymentSite: String(r['支払サイト'] || '').trim(),
        note: String(r['備考'] || '')
      });
    });
  }

  if (!targets.some(function (t) { return t.projectType === '自社'; })) {
    targets.unshift({
      projectType: '自社',
      submitToName: '自社',
      addresseeName: '',
      to: '',
      cc: settings['固定CC'] || '',
      from: settings['送信元メール'] || APP.DEFAULT_EXECUTION_EMAIL,
      templateType: '自社案件_見積送付',
      closingDay: '',
      paymentSite: '',
      note: '自動追加'
    });
  }

  return targets;
}

/**
 * 担当者マスタ。誰が作った見積か確実に記録するためのプルダウン用。
 * シートが無い／空の場合は空配列を返し、画面は手入力にフォールバックする（業務を止めない）。
 */
function readStaff_(masterSs) {
  const sheet = masterSs.getSheetByName(APP.SHEET_STAFF);
  if (!sheet) return [];

  return readObjects_(sheet, ['担当者名'])
    .filter(function (r) { return isActive_(r['有効']) && String(r['担当者名'] || '').trim(); })
    .map(function (r) {
      return {
        staffId: String(r['担当者ID'] || '').trim(),
        name: String(r['担当者名'] || '').trim(),
        email: String(r['メール'] || '').trim()
      };
    });
}

const MAIL_TEMPLATE_TYPES = [
  '自社案件_見積送付', '元請案件_見積送付', '代表者確認依頼',
  '自社案件_請求書送付', '元請案件_請求書送付'
];

/**
 * メールテンプレートマスタ。
 * ライブのシートは旧スキーマ（A:テンプレートID〜E:備考）と
 * 新スキーマ（F:有効〜I:本文）が混在し、初期投入行がA列から書かれていたため
 * 新ヘッダー側が空になっている。両方の並びを受け付けて読む。
 */
function readMailTemplates_(masterSs, warnings) {
  const sheet = masterSs.getSheetByName(APP.SHEET_MAIL_TEMPLATE);
  const map = {};
  if (!sheet) return map;

  const grid = readGrid_(sheet, ['テンプレート種別', '本文']);
  if (!grid) return map;

  let legacyRows = 0;

  grid.rows.forEach(function (row) {
    let active = pickRowValue_(grid.headers, row, ['有効']);
    let type = String(pickRowValue_(grid.headers, row, ['テンプレート種別']) || '').trim();
    let subject = String(pickRowValue_(grid.headers, row, ['件名']) || '');
    let body = String(pickRowValue_(grid.headers, row, ['本文']) || '');

    // 新スキーマ列が空で、A:Eに ['TRUE', 種別, 件名, 本文, 備考] が入っている行の救済
    if (!type && MAIL_TEMPLATE_TYPES.indexOf(String(row[1] || '').trim()) >= 0) {
      active = row[0];
      type = String(row[1] || '').trim();
      subject = String(row[2] || '');
      body = String(row[3] || '');
      legacyRows++;
    }

    if (!type || !isActive_(active) || !body) return;
    if (map[type]) return; // 重複行は最初の1件だけ採用する

    map[type] = { subject: subject, body: body };
  });

  if (legacyRows > 0) {
    warnings.push('メールテンプレートマスタに旧スキーマの行が' + legacyRows
      + '件あります。adminNormalizeMailTemplates() で整理してください。');
  }

  return map;
}

const DISCOUNT_RULE_TYPES = ['繁忙期', '早期予約割引', '複数台割引', '紹介料'];

/**
 * 割引繁忙期マスタ。
 * ライブのシートは旧ヘッダー（A:ルールID, B:有効, ...）のまま、
 * 初期投入行が新スキーマ順（A:有効, B:ルールID, ...）で書かれており、
 * 開始月／終了月／値が全てずれていた。その結果、
 * 繁忙期も早期予約割引も複数台割引も自動判定が常に不成立になっていた。
 * ここでは並びを判定して両方読めるようにし、重複行も畳む。
 */
function readDiscountRules_(masterSs, warnings) {
  const sheet = masterSs.getSheetByName(APP.SHEET_DISCOUNT);
  if (!sheet) {
    warnings.push('割引繁忙期マスタが見つかりません。');
    return [];
  }

  const grid = readGrid_(sheet, ['ルールID', 'ルール種別']);
  if (!grid) return [];

  const rules = [];
  const seen = {};
  let shiftedRows = 0;

  grid.rows.forEach(function (row) {
    let rule = readDiscountRowByHeader_(grid.headers, row);

    // ヘッダー読みで月も条件も取れない場合、新スキーマ順で書かれた行として読み直す
    if (!isUsableDiscountRule_(rule)) {
      const shifted = readDiscountRowByFixedOrder_(row);
      if (isUsableDiscountRule_(shifted)) {
        rule = shifted;
        shiftedRows++;
      }
    }

    if (!isUsableDiscountRule_(rule)) return;
    if (!isActive_(rule.active)) return;

    const key = [rule.ruleType, rule.target, rule.startMonth, rule.endMonth, rule.condition].join('|');
    if (seen[key]) return; // 同じルールが何度も追記されているので1件に畳む
    seen[key] = true;

    rules.push(rule);
  });

  if (shiftedRows > 0) {
    warnings.push('割引繁忙期マスタに列ずれ行が' + shiftedRows
      + '件あります。adminNormalizeDiscountRules() で整理してください。');
  }

  return rules;
}

function readDiscountRowByHeader_(headers, row) {
  return {
    active: pickRowValue_(headers, row, ['有効']),
    ruleId: String(pickRowValue_(headers, row, ['ルールID']) || '').trim(),
    ruleType: normalizeRuleType_(pickRowValue_(headers, row, ['ルール種別'])),
    target: String(pickRowValue_(headers, row, ['対象']) || '').trim(),
    startMonth: pickRowValue_(headers, row, ['開始月']),
    endMonth: pickRowValue_(headers, row, ['終了月']),
    condition: String(pickRowValue_(headers, row, ['条件']) || '').trim(),
    value: pickRowValue_(headers, row, ['値']),
    valueType: String(pickRowValue_(headers, row, ['値種別']) || '').trim(),
    priority: toNumber_(pickRowValue_(headers, row, ['優先度']) || 9999)
  };
}

// 新スキーマの並び：有効, ルールID, ルール種別, 対象, 開始月, 終了月, 条件, 値, 値種別, 優先度, 備考
function readDiscountRowByFixedOrder_(row) {
  return {
    active: row[0],
    ruleId: String(row[1] || '').trim(),
    ruleType: normalizeRuleType_(row[2]),
    target: String(row[3] || '').trim(),
    startMonth: row[4],
    endMonth: row[5],
    condition: String(row[6] || '').trim(),
    value: row[7],
    valueType: String(row[8] || '').trim(),
    priority: toNumber_(row[9] || 9999)
  };
}

function normalizeRuleType_(value) {
  const s = String(value || '').trim();
  if (!s) return '';
  if (s === '繁忙期加算') return '繁忙期';
  if (s.indexOf('複数台割引') === 0) return '複数台割引';
  return s;
}

function isUsableDiscountRule_(rule) {
  if (!rule || DISCOUNT_RULE_TYPES.indexOf(rule.ruleType) < 0) return false;
  if (!(toNumber_(rule.value) > 0)) return false;

  if (rule.ruleType === '複数台割引') {
    return /\d+\s*[-〜~]\s*\d+/.test(String(rule.condition || ''));
  }

  return toNumber_(rule.startMonth) >= 1 && toNumber_(rule.endMonth) >= 1;
}

function readCellDefs_(masterSs) {
  const sheet = masterSs.getSheetByName(APP.SHEET_CELL_DEF);
  if (!sheet) return {};

  const grid = readGrid_(sheet, ['帳票区分', '対象シート', '項目キー']);
  if (!grid) return {};

  const byDocType = {};

  grid.rows.forEach(function (row) {
    const docType = String(pickRowValue_(grid.headers, row, ['帳票区分']) || '').trim();
    const key = String(pickRowValue_(grid.headers, row, ['項目キー']) || '').trim();
    if (!docType || !key) return;

    const rawA1 = String(pickRowValue_(grid.headers, row, ['セル/範囲']) || '').trim();
    // 「項目名」が空欄で値が左にずれている行があるため、行内からA1表記を拾い直す
    const a1 = isValidA1_(rawA1) ? rawA1 : findA1InRow_(row);
    if (!a1) return;

    if (!byDocType[docType]) byDocType[docType] = {};
    if (byDocType[docType][key]) return;

    byDocType[docType][key] = {
      key: key,
      targetSheet: String(pickRowValue_(grid.headers, row, ['対象シート']) || '').trim(),
      a1: a1
    };
  });

  return byDocType;
}

function getCellDefMap_(docType, ctx) {
  const defs = (ctx.cellDefs || {})[docType];
  return defs && Object.keys(defs).length ? defs : getDefaultCellDefMap_(docType);
}

function isValidA1_(s) {
  return /^[A-Z]+\d+(?::[A-Z]+\d+)?$/i.test(String(s || '').trim());
}

function findA1InRow_(row) {
  for (let i = 0; i < row.length; i++) {
    const v = String(row[i] || '').trim();
    if (isValidA1_(v)) return v;
  }
  return '';
}

/* ===================== 見積データシート ===================== */

function getEstimateDataSheet_(ctx) {
  const ss = getTemplateSs_(ctx.settings);
  const sheet = ss.getSheetByName(APP.SHEET_ESTIMATE_DATA);
  if (!sheet) throw new Error('シートが見つかりません：' + APP.SHEET_ESTIMATE_DATA);

  ensureHeaders_(sheet, getEstimateHeaders_());
  return sheet;
}

function generateEstimateId_(sheet) {
  const prefix = 'EST-' + formatDate_(new Date(), 'yyyyMMdd') + '-';
  const info = getHeaderInfo_(sheet);
  const col = info.map['estimate_id'];
  if (!col) throw new Error('見積データシートに estimate_id ヘッダーがありません。');

  const lastRow = sheet.getLastRow();
  let maxNo = 0;

  if (lastRow > info.headerRow) {
    // ID列だけ読む。203列を全部読む必要はない。
    const ids = sheet.getRange(info.headerRow + 1, col, lastRow - info.headerRow, 1).getDisplayValues();
    ids.forEach(function (r) {
      const id = String(r[0] || '');
      if (id.indexOf(prefix) !== 0) return;
      const n = Number(id.slice(prefix.length));
      if (!isNaN(n) && n > maxNo) maxNo = n;
    });
  }

  return prefix + String(maxNo + 1).padStart(4, '0');
}

function findEstimateRecord_(sheet, estimateId, hintRowNumber) {
  const info = getHeaderInfo_(sheet);
  const col = info.map['estimate_id'];
  if (!col) throw new Error('見積データシートに estimate_id ヘッダーがありません。');

  const target = String(estimateId || '').trim();

  // 直前の保存で行番号が分かっている場合はそこだけ確認する
  if (hintRowNumber && hintRowNumber > info.headerRow) {
    const hinted = String(sheet.getRange(hintRowNumber, col).getDisplayValue()).trim();
    if (hinted === target) {
      return { rowNumber: hintRowNumber, record: readObjectAtRow_(sheet, hintRowNumber, info) };
    }
  }

  const lastRow = sheet.getLastRow();
  if (lastRow <= info.headerRow) return null;

  const ids = sheet.getRange(info.headerRow + 1, col, lastRow - info.headerRow, 1).getDisplayValues();
  for (let i = 0; i < ids.length; i++) {
    if (String(ids[i][0]).trim() === target) {
      const rowNumber = info.headerRow + 1 + i;
      return { rowNumber: rowNumber, record: readObjectAtRow_(sheet, rowNumber, info) };
    }
  }

  return null;
}

/* ===================== シートIO ===================== */

function getMasterSs_() {
  return openSpreadsheet_(APP.DEFAULT_MASTER_SS_ID,
    'マスタスプレッドシートを開けません。Excel形式のままの場合はGoogleスプレッドシート形式へ変換してください。');
}

function getTemplateSs_(settings) {
  const id = (settings && settings['見積請求書テンプレートスプレッドシートID']) || APP.DEFAULT_TEMPLATE_SS_ID;
  return openSpreadsheet_(id,
    '見積・請求書テンプレートスプレッドシートを開けません。Googleスプレッドシート形式か、権限を確認してください。');
}

function openSpreadsheet_(id, message) {
  if (RUNTIME.spreadsheets[id]) return RUNTIME.spreadsheets[id];

  try {
    const ss = SpreadsheetApp.openById(id);
    RUNTIME.spreadsheets[id] = ss;
    return ss;
  } catch (e) {
    throw new Error(message + ' 詳細：' + toErrorMessage_(e));
  }
}

/** ヘッダー行の位置と「ヘッダー名 → 列番号」を返す。実行中はメモしておく。 */
function getHeaderInfo_(sheet, requiredHeaders) {
  const key = sheet.getParent().getId() + '::' + sheet.getName();
  if (RUNTIME.headerInfo[key]) return RUNTIME.headerInfo[key];

  const lastRow = Math.min(Math.max(sheet.getLastRow(), 1), 20);
  const lastCol = Math.max(sheet.getLastColumn(), 1);
  const values = sheet.getRange(1, 1, lastRow, lastCol).getDisplayValues();

  let best = null;

  for (let r = 0; r < values.length; r++) {
    const map = {};
    values[r].forEach(function (v, idx) {
      const h = String(v || '').trim();
      if (h && !map[h]) map[h] = idx + 1;
    });

    const hit = (requiredHeaders || []).filter(function (h) { return map[h]; }).length;
    if (!best || hit > best.count) best = { headerRow: r + 1, map: map, count: hit, lastCol: lastCol };
  }

  if (!best) best = { headerRow: 1, map: {}, count: 0, lastCol: lastCol };
  RUNTIME.headerInfo[key] = best;
  return best;
}

function forgetHeaderInfo_(sheet) {
  delete RUNTIME.headerInfo[sheet.getParent().getId() + '::' + sheet.getName()];
}

/**
 * 足りないヘッダーだけを右端に1回で追加する。
 * 既存列の位置は動かさないので、稼働中のデータを壊さない。
 */
function ensureHeaders_(sheet, headers) {
  const info = getHeaderInfo_(sheet, headers.slice(0, 2));
  const missing = headers.filter(function (h) { return !info.map[h]; });
  if (missing.length === 0) return info;

  sheet.getRange(info.headerRow, sheet.getLastColumn() + 1, 1, missing.length).setValues([missing]);
  forgetHeaderInfo_(sheet);
  return getHeaderInfo_(sheet, headers.slice(0, 2));
}

/** ヘッダー行＋データ行を1回の getValues でまとめて取る。 */
function readGrid_(sheet, requiredHeaders) {
  const info = getHeaderInfo_(sheet, requiredHeaders);
  const lastRow = sheet.getLastRow();
  const lastCol = sheet.getLastColumn();
  if (lastRow <= info.headerRow || lastCol < 1) return null;

  const all = sheet.getRange(info.headerRow, 1, lastRow - info.headerRow + 1, lastCol).getValues();
  const headers = all[0].map(function (h) { return String(h || '').trim(); });

  const rows = all.slice(1).filter(function (row) {
    return row.some(function (v) { return !isBlank_(v); });
  });

  return { headers: headers, rows: rows, headerRow: info.headerRow };
}

function readObjects_(sheet, requiredHeaders) {
  const grid = readGrid_(sheet, requiredHeaders);
  if (!grid) return [];

  return grid.rows.map(function (row) {
    const obj = {};
    grid.headers.forEach(function (h, i) {
      if (h && obj[h] === undefined) obj[h] = row[i];
    });
    return obj;
  });
}

/** 指定した列だけを読む。列数の多い見積DBの検索用。 */
function readColumns_(sheet, wantedHeaders) {
  const info = getHeaderInfo_(sheet, wantedHeaders.slice(0, 2));
  const lastRow = sheet.getLastRow();
  if (lastRow <= info.headerRow) return [];

  const cols = wantedHeaders.filter(function (h) { return info.map[h]; });
  if (cols.length === 0) return [];

  const min = Math.min.apply(null, cols.map(function (h) { return info.map[h]; }));
  const max = Math.max.apply(null, cols.map(function (h) { return info.map[h]; }));

  const values = sheet.getRange(info.headerRow + 1, min, lastRow - info.headerRow, max - min + 1).getValues();

  return values
    .filter(function (row) { return row.some(function (v) { return !isBlank_(v); }); })
    .map(function (row) {
      const obj = {};
      cols.forEach(function (h) { obj[h] = row[info.map[h] - min]; });
      return obj;
    });
}

function readObjectAtRow_(sheet, rowNumber, info) {
  const row = sheet.getRange(rowNumber, 1, 1, Math.max(sheet.getLastColumn(), 1)).getValues()[0];
  const obj = {};
  Object.keys(info.map).forEach(function (h) { obj[h] = row[info.map[h] - 1]; });
  return obj;
}

/**
 * オブジェクトを1行追記する。実際のヘッダー位置に書くので、
 * シート側の列順がコードの定義と違っていてもずれない（旧 upsertRowsByKey_ の不具合）。
 * 戻り値は書き込んだ行番号。
 */
function appendObject_(sheet, obj) {
  const info = getHeaderInfo_(sheet);
  const width = Math.max(sheet.getLastColumn(), 1);
  const row = new Array(width).fill('');

  Object.keys(obj).forEach(function (key) {
    const col = info.map[key];
    if (col && col <= width) row[col - 1] = obj[key];
  });

  const rowNumber = sheet.getLastRow() + 1;
  sheet.getRange(rowNumber, 1, 1, width).setValues([row]);
  return rowNumber;
}

/** 既存行の更新。連続する列はまとめて1回の setValues にする。 */
function updateObjectAtRow_(sheet, rowNumber, fields) {
  const info = getHeaderInfo_(sheet);
  const targets = [];

  Object.keys(fields).forEach(function (key) {
    const col = info.map[key];
    if (col) targets.push({ col: col, value: fields[key] });
  });

  if (targets.length === 0) return;
  targets.sort(function (a, b) { return a.col - b.col; });

  let run = [targets[0]];

  const flush = function () {
    const start = run[0].col;
    sheet.getRange(rowNumber, start, 1, run.length)
      .setValues([run.map(function (t) { return t.value; })]);
  };

  for (let i = 1; i < targets.length; i++) {
    if (targets[i].col === run[run.length - 1].col + 1) {
      run.push(targets[i]);
    } else {
      flush();
      run = [targets[i]];
    }
  }

  flush();
}

/**
 * 差し込みセルへの書き込み。
 * 複数セル範囲は一度clearしてから左上だけに書く（金額の二重表示を防ぐため）。
 * 単一セルはclear不要なので呼び出し回数を減らす。
 */
function setByKeys_(sheet, defs, values) {
  Object.keys(values).forEach(function (key) {
    const def = defs[key];
    if (!def || !def.a1) return;

    const range = sheet.getRange(def.a1);
    if (range.getNumRows() > 1 || range.getNumColumns() > 1) range.clearContent();

    range.getCell(1, 1).setValue(values[key]);
  });
}

function getTargetSheetNameFromDefs_(defs, fallback) {
  const keys = Object.keys(defs);
  for (let i = 0; i < keys.length; i++) {
    if (defs[keys[i]].targetSheet) return defs[keys[i]].targetSheet;
  }
  return fallback;
}

function getDefaultCellDefMap_(docType) {
  const map = {};
  getDefaultCellDefinitionRows_()
    .filter(function (r) { return r[0] === docType; })
    .forEach(function (r) { map[r[2]] = { key: r[2], targetSheet: r[1], a1: r[4] }; });
  return map;
}

/* ===================== ログ ===================== */

function queueLog_(operationType, estimateId, content, errorContent, elapsedMs) {
  RUNTIME.logs.push([
    new Date(),
    getCurrentUser_(),
    operationType || '',
    estimateId || '',
    truncate_(content || '', 3000),
    truncate_(errorContent || '', 3000),
    elapsedMs === undefined ? '' : elapsedMs
  ]);
}

/** リクエスト終了時に1回だけ書き込む。旧実装は操作ごとに毎回シートを開いていた。 */
function flushLogs_() {
  if (RUNTIME.logs.length === 0) return;

  const rows = RUNTIME.logs.splice(0, RUNTIME.logs.length);

  try {
    const sheet = getMasterSs_().getSheetByName(APP.SHEET_LOG);
    if (!sheet) return;

    const info = getHeaderInfo_(sheet, getLogHeaders_());
    const order = getLogHeaders_().map(function (h) { return info.map[h] || 0; });
    const width = Math.max(sheet.getLastColumn(), getLogHeaders_().length);

    const values = rows.map(function (r) {
      const out = new Array(width).fill('');
      order.forEach(function (col, i) { if (col) out[col - 1] = r[i]; });
      return out;
    });

    sheet.getRange(sheet.getLastRow() + 1, 1, values.length, width).setValues(values);
  } catch (e) {
    console.error('ログ書き込みに失敗しました：' + toErrorMessage_(e));
  }
}

/**
 * 全APIの共通ラッパー。所要時間を測ってログに残すので、
 * 体感ではなく数字で速度を確認できる。
 */
function withApi_(operationType, estimateId, fn) {
  const started = Date.now();

  try {
    const result = fn();
    const elapsed = Date.now() - started;

    queueLog_(operationType, (result && result.estimateId) || estimateId || '',
      '完了' + (RUNTIME.context && RUNTIME.context.fromCache ? '（マスタはキャッシュ）' : '（マスタを実読み）'),
      '', elapsed);

    flushLogs_();

    if (result && typeof result === 'object') result.elapsedMs = elapsed;
    return result;
  } catch (e) {
    const msg = toErrorMessage_(e);
    queueLog_('エラー', estimateId || '', operationType + 'でエラー', msg, Date.now() - started);
    flushLogs_();
    return { ok: false, error: msg };
  }
}

/* ===================== スキーマ定義 ===================== */

function getMenuHeaders_() {
  return [
    'メニューID', '有効', '表示順', 'メニュータイプ', 'カテゴリ', 'メニュー名', '顧客表示名',
    '単価', '税区分', '数量単位', '標準時間_分', '繁忙期加算対象', '繁忙期加算額',
    '割引対象', '複数台割引対象', '既存/特殊', '見積表示', '請求書流用',
    '関連メニュー/利用可能オプション', 'PDF記載ページ', '原文価格/時間', '補足_現場入力', '要確認事項'
  ];
}

function getSubmitToHeaders_() {
  return ['有効', '案件タイプ', '提出先名', '見積書宛名', '宛先メール', '固定CC', '送信元メール',
    'メールテンプレート種別', '請求締め日', '支払サイト', '備考'];
}

function getMailTemplateHeaders_() {
  return ['有効', 'テンプレート種別', '件名', '本文', '備考'];
}

function getDiscountHeaders_() {
  return ['有効', 'ルールID', 'ルール種別', '対象', '開始月', '終了月', '条件', '値', '値種別', '優先度', '備考'];
}

function getStaffHeaders_() {
  return ['有効', '担当者ID', '担当者名', 'メール', '備考'];
}

function getCellDefHeaders_() {
  return ['帳票区分', '対象シート', '項目キー', '項目名', 'セル/範囲', '入力種別', 'データ型', '必須', '備考'];
}

function getLogHeaders_() {
  return ['日時', 'ユーザー', '操作種別', '見積ID', '内容', 'エラー内容', '所要ms'];
}

function getEstimateHeaders_() {
  const headers = [
    'estimate_id', 'original_estimate_id', 'invoice_id', 'invoice_source_flag', 'project_status',
    '作成日時', '更新日時', '作成者', '案件タイプ', '提出先名', '見積書宛名', '敬称',
    '宛先メール', '固定CC', '送信元メール', '顧客名', '案件名', '現場住所', '作業予定日',
    '担当者', '見積日', '見積番号', '件名', '本文テンプレート種別', '備考', '駐車場代注記',
    '高速代', '高速代_税区分', '明細小計', '割引額', '繁忙期加算額', '非課税小計',
    '課税小計', '消費税', '合計金額', '繁忙期_自動判定', '繁忙期_手動設定',
    '割引_自動判定', '割引_手動設定', '例外フラグ', '例外理由', 'PDF_URL', 'PDF_FILE_ID',
    'メール下書きURL', 'メール下書きID', 'メール下書き作成日時',
    '代表者確認メール下書きURL', '代表者確認メール下書きID', '代表者確認メール作成日時',
    '複製元見積ID'
  ];

  for (let i = 1; i <= APP.MAX_DETAIL_ROWS; i++) {
    const p = '明細' + pad2_(i) + '_';
    headers.push(p + '品名', p + 'メニューID', p + 'メニュータイプ', p + '数量', p + '単位',
      p + '単価', p + '金額', p + '税区分', p + '備考');
  }

  headers.push('内部メモ');

  // ここから下が2026-09改修の追加列。既存列の位置は動かさず右端に足す。
  headers.push('request_id', '要代表者確認', '自動割引種別', '自動割引額', '明細値引き合計',
    '調整合計額', '合計指定額', '調整_JSON');

  for (let i = 1; i <= APP.MAX_ADJUSTMENT_SLOTS; i++) {
    headers.push('調整' + pad2_(i) + '_名称', '調整' + pad2_(i) + '_金額');
  }

  for (let i = 1; i <= APP.MAX_DETAIL_ROWS; i++) {
    headers.push('明細' + pad2_(i) + '_値引き額');
  }

  return headers;
}

function getDefaultCellDefinitionRows_() {
  const rows = [];

  const layout = [
    ['document_date', '書類日付', 'F2', 'date'],
    ['document_no_label', '番号ラベル', 'E3', 'string'],
    ['title', '帳票タイトル', 'A5:F5', 'string'],
    ['addressee_name', '宛名', 'A8:C8', 'string'],
    ['addressee_suffix', '敬称', 'D8', 'string'],
    ['company_name', '自社名', 'E9', 'string'],
    ['company_zip', '会社郵便番号', 'E10', 'string'],
    ['company_address', '会社住所', 'E11', 'string'],
    ['company_tel', '会社電話番号', 'E12', 'string'],
    ['company_fax', '会社FAX', 'E13', 'string'],
    ['stamp_area', '社印エリア', 'F9:F13', 'image'],
    ['project_name', '案件名', 'A13:C13', 'string'],
    ['project_suffix', '案件名接尾', 'D13', 'string'],
    ['greeting', '挨拶文', 'A18:F18', 'string'],
    ['total_amount_label', '合計ラベル', 'A19', 'string'],
    ['total_amount_display', '合計表示', 'B19:C19', 'money'],
    ['total_amount_unit', '合計単位', 'D19', 'string'],
    ['detail_header_name', '明細見出し品名', 'A21:C21', 'string'],
    ['detail_header_qty', '明細見出し数量', 'D21', 'string'],
    ['detail_header_unit_price', '明細見出し単価', 'E21', 'string'],
    ['detail_header_amount', '明細見出し金額', 'F21', 'string'],
    ['detail_name_range', '明細品名範囲', 'A22:C37', 'string'],
    ['detail_qty_range', '明細数量範囲', 'D22:D37', 'number'],
    ['detail_unit_price_range', '明細単価範囲', 'E22:E37', 'money'],
    ['detail_amount_range', '明細金額範囲', 'F22:F37', 'money'],
    ['remarks', '備考', 'A39:D41', 'string'],
    ['subtotal_label', '小計ラベル', 'E39', 'string'],
    ['subtotal', '小計', 'F39', 'money'],
    ['tax_label', '消費税ラベル', 'E40', 'string'],
    ['tax', '消費税', 'F40', 'money'],
    ['grand_total_label', '合計ラベル', 'E41', 'string'],
    ['grand_total', '合計', 'F41', 'money']
  ];

  [['見積書', APP.TEMP_ESTIMATE_SHEET, 'estimate_id', '見積番号'],
   ['請求書', APP.TEMP_INVOICE_SHEET, 'invoice_id', '請求番号']].forEach(function (doc) {
    const docType = doc[0];
    const sheetName = doc[1];

    rows.push([docType, sheetName, doc[2], doc[3], 'F3', '差し込み', 'string', 'TRUE', '']);

    layout.forEach(function (l) {
      rows.push([docType, sheetName, l[0], l[1], l[2], '差し込み', l[3], 'TRUE', '']);
    });

    // 請求書だけ「お支払い期限：」の値セルがある。
    // 実テンプレートのセル位置は adminInspectTemplateLayout() で確認すること。
    if (docType === '請求書') {
      rows.push([docType, sheetName, 'payment_due', '支払期限', 'B41', '差し込み', 'date', 'FALSE',
        'テンプレートの「お支払い期限：」の右隣。要確認']);
    }
  });

  return rows;
}

/* ===================== 文面 ===================== */

function buildTokensFromRecord_(record, ctx, extra) {
  const settings = (ctx && ctx.settings) || {};
  const e = extra || {};

  return {
    顧客名: record['顧客名'] || '',
    案件名: record['案件名'] || '',
    見積金額: e['見積金額'] !== undefined ? e['見積金額'] : formatYen_(toNumber_(record['合計金額'])),
    作成日: e['作成日'] !== undefined ? e['作成日'] : formatDate_(record['作成日時'] || new Date(), 'yyyy/MM/dd'),
    担当者: record['担当者'] || record['作成者'] || '',
    提出先名: record['提出先名'] || '',
    見積ID: record.estimate_id || record['estimate_id'] || '',
    PDF_URL: e['PDF_URL'] !== undefined ? e['PDF_URL'] : (record['PDF_URL'] || ''),
    案件タイプ: record['案件タイプ'] || '',
    例外理由: e['例外理由'] !== undefined ? e['例外理由'] : (record['例外理由'] || ''),
    作成日時: e['作成日時'] !== undefined ? e['作成日時'] : formatDateTime_(record['作成日時'] || new Date()),
    会社名: settings['会社名'] || ''
  };
}

function renderTemplate_(template, tokens) {
  return String(template || '').replace(/\{([^}]+)\}/g, function (_, key) {
    return tokens[key] !== undefined ? tokens[key] : '';
  });
}

function getFallbackEstimateTemplate_() {
  return {
    subject: '【お見積書】{案件名} / {顧客名}様',
    body: '{顧客名}様\n\nお世話になっております。\nお見積書を添付にてお送りいたします。\n\n■見積ID：{見積ID}\n■見積金額：{見積金額}\n\nご確認のほど、よろしくお願いいたします。\n\n{会社名}'
  };
}

function getFallbackRepresentativeTemplate_() {
  return {
    subject: '【要確認】見積確認依頼：{見積ID}',
    body: '代表者確認をお願いします。\n\n■見積ID：{見積ID}\n■顧客名：{顧客名}\n■案件名：{案件名}\n■合計金額：{見積金額}\n■例外理由：\n{例外理由}\n\n■PDF_URL：{PDF_URL}\n■作成者：{担当者}\n■作成日時：{作成日時}'
  };
}

/* ===================== 汎用 ===================== */

function getCurrentUser_() {
  try {
    return Session.getActiveUser().getEmail() || Session.getEffectiveUser().getEmail() || '';
  } catch (e) {
    return '';
  }
}

function pickRowValue_(headers, row, candidates) {
  // 同名の重複列があるため、まず「値の入っている方」を探す
  for (let i = 0; i < candidates.length; i++) {
    for (let c = 0; c < headers.length; c++) {
      if (headers[c] === candidates[i] && !isBlank_(row[c])) return row[c];
    }
  }

  for (let i = 0; i < candidates.length; i++) {
    for (let c = 0; c < headers.length; c++) {
      if (headers[c] === candidates[i]) return row[c];
    }
  }

  return '';
}

function parseDateInput_(value) {
  if (!value) return null;
  if (Object.prototype.toString.call(value) === '[object Date]') return value;

  const s = String(value).trim();
  const m = s.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
  if (m) return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));

  const d = new Date(s);
  return isNaN(d.getTime()) ? null : d;
}

function toDateInputValue_(value) {
  const d = parseDateInput_(value);
  return d ? formatDate_(d, 'yyyy-MM-dd') : '';
}

function formatDate_(date, pattern) {
  return Utilities.formatDate(parseDateInput_(date) || new Date(), APP.TZ, pattern);
}

function formatDateTime_(date) {
  if (!date) return '';
  const d = parseDateInput_(date) || date;
  try { return Utilities.formatDate(d, APP.TZ, 'yyyy/MM/dd HH:mm:ss'); }
  catch (e) { return String(date); }
}

function toNumber_(value) {
  if (typeof value === 'number') return isFinite(value) ? value : 0;
  if (value === null || value === undefined) return 0;

  const s = String(value).replace(/[,\s円¥￥]/g, '').replace(/％/g, '%').trim();
  if (!s) return 0;
  if (s.indexOf('%') >= 0) {
    const p = Number(s.replace('%', ''));
    return isNaN(p) ? 0 : p / 100;
  }

  const n = Number(s);
  return isNaN(n) ? 0 : n;
}

function normalizeRate_(value) {
  const n = toNumber_(value);
  return n > 1 ? n / 100 : n;
}

function roundYen_(n) { return Math.round(toNumber_(n)); }

function formatYen_(n) {
  const v = roundYen_(n);
  return (v < 0 ? '-¥' : '¥') + Math.abs(v).toLocaleString('ja-JP');
}

function parseBooleanLoose_(v) {
  if (v === true) return true;
  if (v === false) return false;
  const s = String(v == null ? '' : v).trim().toLowerCase();
  return ['true', '1', 'yes', 'y', '有効', '○', '〇', 'on', '適用'].indexOf(s) >= 0;
}

function isActive_(v) {
  if (isBlank_(v)) return true;
  const s = String(v).trim().toLowerCase();
  return ['false', '0', 'no', 'n', '無効', '停止', 'off'].indexOf(s) < 0;
}

function boolText_(b) { return b ? 'TRUE' : 'FALSE'; }
function isBlank_(v) { return v === null || v === undefined || String(v).trim() === ''; }

/** 「非課税」「不課税」「対象外」以外は課税として扱う。CalcEngine と同じ判定。 */
function isTaxable_(taxType) {
  const s = String(taxType || '');
  return !(s.indexOf('非課税') >= 0 || s.indexOf('不課税') >= 0 || s.indexOf('対象外') >= 0);
}

function matchText_(value, keyword) {
  if (!keyword) return true;
  return String(value || '').toLowerCase().indexOf(String(keyword).toLowerCase()) >= 0;
}

function matchDate_(value, dateText) {
  if (!dateText) return true;
  return formatDate_(value, 'yyyy-MM-dd') === dateText;
}

function pad2_(n) { return String(n).padStart(2, '0'); }

function sanitizeFileName_(name) {
  return String(name || '').replace(/[\\/:*?"<>|\r\n]/g, '_').slice(0, 180);
}

function toErrorMessage_(e) { return !e ? '' : (e.message ? e.message : String(e)); }

function truncate_(s, max) {
  const t = String(s || '');
  return t.length > max ? t.slice(0, max) + '…' : t;
}
