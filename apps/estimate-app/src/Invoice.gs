/**
 * 請求書機能
 *
 * 見積検索 → プレビュー → 請求書作成 → PDF → Gmail下書き → 見積へ書き戻し。
 *
 * 設計上の要点
 *   - 見積レコードは絶対に上書きしない。invoice_id と project_status だけ更新する。
 *   - 請求データは 請求書/データ格納 へ別レコードとして保存する。
 *   - 金額計算は見積と同じ CalcEngine を使う。駐車場代・追加作業費・値引き額は
 *     「調整行」に変換して渡すので、計算式を二重に持たない。
 *   - 見積に invoice_id があれば通常の作成は出さず「請求書確認」にする（二重請求防止）。
 *     作り直しは明示的な再作成フラグを立てたときだけ。
 *   - Gmailは下書きのみ。即送信しない。
 */

/* ===================== API ===================== */

/**
 * 請求書作成の入口。見積を読み、請求フォームの初期値を組み立てて返す。
 * 既に請求済みなら existingInvoiceId を立てて、画面側で「確認」に切り替えさせる。
 */
function apiStartInvoice(estimateId) {
  return withApi_('請求書作成準備', estimateId, function () {
    const ctx = loadContext_();
    const estimateSheet = getEstimateDataSheet_(ctx);
    const found = findEstimateRecord_(estimateSheet, estimateId);
    if (!found) throw new Error('見積IDが見つかりません：' + estimateId);

    const r = found.record;
    const existingInvoiceId = String(r['invoice_id'] || '').trim();
    const estimateCalc = rebuildCalcFromRecord_(r, ctx);
    const target = (ctx.submitTargets || []).find(function (t) {
      return t.projectType === String(r['案件タイプ'] || '').trim();
    }) || null;

    const workDate = toDateInputValue_(r['作業予定日']);
    const terms = resolvePaymentTerms_(target, workDate, ctx.settings);

    return {
      ok: true,
      estimateId: estimateId,
      existingInvoiceId: existingInvoiceId,
      estimateTotal: estimateCalc.grandTotal,
      estimateTotalDisplay: formatYen_(estimateCalc.grandTotal),
      customerName: r['顧客名'] || '',
      projectName: r['案件名'] || '',
      projectType: r['案件タイプ'] || '',
      submitToName: r['提出先名'] || '',
      addresseeName: r['見積書宛名'] || '',
      to: r['宛先メール'] || '',
      cc: r['固定CC'] || '',
      rows: estimateCalc.pdfRows,
      form: {
        workCompletedDate: workDate,
        invoiceDate: toDateInputValue_(terms.invoiceDate),
        dueDate: toDateInputValue_(terms.dueDate),
        parkingFee: '',
        parkingTaxType: String(ctx.settings['駐車場代_税区分'] || '課税'),
        extraWorkName: '追加作業費',
        extraWorkFee: '',
        discountName: '値引き',
        discountAmount: '',
        remarks: '',
        staff: r['担当者'] || r['作成者'] || ''
      },
      termsNote: terms.note
    };
  });
}

/** 請求フォームの内容で金額だけ計算して返す（保存はしない）。 */
function apiCalculateInvoice(payload) {
  return withApi_('請求額計算', (payload || {}).estimateId || '', function () {
    const ctx = loadContext_();
    const prepared = prepareInvoiceCalc_(payload, ctx);

    return {
      ok: true,
      calc: prepared.calc,
      estimateTotal: prepared.estimateTotal,
      diff: prepared.calc.grandTotal - prepared.estimateTotal
    };
  });
}

/**
 * 請求データを保存する。フェーズ1（見積と同じ2フェーズ構成）。
 * 見積側は invoice_id と project_status だけ更新する。
 */
function apiSaveInvoice(payload) {
  return withApi_('請求書作成', (payload || {}).estimateId || '', function () {
    const p = payload || {};
    const ctx = loadContext_();
    const estimateSheet = getEstimateDataSheet_(ctx);
    const found = findEstimateRecord_(estimateSheet, p.estimateId);
    if (!found) throw new Error('見積IDが見つかりません：' + p.estimateId);

    const existing = String(found.record['invoice_id'] || '').trim();
    if (existing && p.allowRecreate !== true) {
      throw new Error('この見積には既に請求書 ' + existing + ' が作成されています。'
        + '作り直す場合は再作成を明示してください。');
    }

    const invoiceSheet = getInvoiceDataSheet_(ctx);
    const prepared = prepareInvoiceCalc_(p, ctx);
    const requestId = String(p.requestId || '').trim();

    const lock = LockService.getScriptLock();
    lock.waitLock(30000);

    let invoiceId = '';
    let rowNumber = 0;
    let duplicated = false;

    try {
      const seen = requestId ? readSavedRequest_(requestId) : null;

      if (seen) {
        invoiceId = seen.estimateId; // 同じキャッシュ構造を使い回している
        rowNumber = seen.rowNumber;
        duplicated = true;
      } else {
        invoiceId = generateInvoiceId_(invoiceSheet);
        const record = buildInvoiceRecord_(p, ctx, prepared, invoiceId, existing);
        record.request_id = requestId;
        rowNumber = appendObject_(invoiceSheet, record);
        if (requestId) rememberSavedRequest_(requestId, invoiceId, rowNumber);
      }
    } finally {
      lock.releaseLock();
    }

    if (!duplicated) {
      // 見積レコードは上書きしない。紐付けと進捗だけ更新する。
      updateObjectAtRow_(estimateSheet, found.rowNumber, {
        invoice_id: invoiceId,
        project_status: '請求書作成済',
        更新日時: new Date()
      });
    }

    queueLog_(duplicated ? '請求書作成(再送)' : '請求書作成', p.estimateId,
      '請求ID ' + invoiceId + ' / 請求額 ' + prepared.calc.grandTotal
      + '円 / 見積額 ' + prepared.estimateTotal + '円', '');

    return {
      ok: true,
      invoiceId: invoiceId,
      rowNumber: rowNumber,
      estimateId: p.estimateId,
      duplicated: duplicated,
      calc: prepared.calc,
      estimateTotal: prepared.estimateTotal,
      diff: prepared.calc.grandTotal - prepared.estimateTotal
    };
  });
}

/** フェーズ2：請求書PDFとGmail下書きを作る。 */
function apiBuildInvoiceDocuments(invoiceId, rowNumber) {
  return withApi_('請求書帳票生成', invoiceId, function () {
    const ctx = loadContext_();
    const sheet = getInvoiceDataSheet_(ctx);
    const found = findInvoiceRecord_(sheet, invoiceId, rowNumber);
    if (!found) throw new Error('請求IDが見つかりません：' + invoiceId);

    const record = found.record;
    const calc = rebuildInvoiceCalc_(record, ctx);
    const errors = [];
    const writeback = { 更新日時: new Date() };

    let pdfFile = null;
    let pdfUrl = '';
    let pdfFileId = '';

    try {
      const pdf = generateInvoicePdf_(record, calc, ctx);
      pdfFile = pdf.file;
      pdfUrl = pdf.url;
      pdfFileId = pdf.fileId;

      writeback.PDF_URL = pdfUrl;
      writeback.PDF_FILE_ID = pdfFileId;
      record.PDF_URL = pdfUrl;

      queueLog_('請求書PDF生成', invoiceId, '請求書PDFを生成しました。', '');
    } catch (e) {
      const msg = toErrorMessage_(e);
      errors.push('PDF生成失敗：' + msg);
      queueLog_('エラー', invoiceId, '請求書PDF生成に失敗しました。', msg);
    }

    let draftUrl = '';
    let draftId = '';
    let mailPreview = null;

    try {
      if (!pdfFile) throw new Error('PDF生成に失敗したため、PDF添付済みメール下書きは作成していません。');

      const draft = createInvoiceMailDraft_(record, calc, ctx, pdfFile);
      draftUrl = draft.draftUrl;
      draftId = draft.draftId;

      writeback.メール下書きURL = draftUrl;
      writeback.メール下書きID = draftId;
      writeback.メール下書き作成日時 = new Date();

      queueLog_('請求書メール下書き作成', invoiceId, 'Gmail下書きを作成しました。', '');
    } catch (e) {
      const msg = toErrorMessage_(e);
      errors.push('メール下書き作成失敗：' + msg);
      mailPreview = buildInvoiceMailPreview_(record, calc, ctx);
      queueLog_('エラー', invoiceId, '請求書メール下書き作成に失敗しました。', msg);
    }

    updateObjectAtRow_(sheet, found.rowNumber, writeback);

    return {
      ok: true,
      invoiceId: invoiceId,
      pdfUrl: pdfUrl,
      pdfFileId: pdfFileId,
      draftUrl: draftUrl,
      draftId: draftId,
      errors: errors,
      mailPreview: mailPreview
    };
  });
}

/** 作成済み請求書の確認用。 */
function apiGetInvoiceDetail(invoiceId) {
  return withApi_('請求書確認', invoiceId, function () {
    const ctx = loadContext_();
    const sheet = getInvoiceDataSheet_(ctx);
    const found = findInvoiceRecord_(sheet, invoiceId);
    if (!found) throw new Error('請求IDが見つかりません：' + invoiceId);

    const r = found.record;
    const calc = rebuildInvoiceCalc_(r, ctx);

    return {
      ok: true,
      invoiceId: invoiceId,
      header: {
        estimate_id: r['estimate_id'] || '',
        作成日時: formatDateTime_(r['作成日時']),
        案件タイプ: r['案件タイプ'] || '',
        提出先名: r['提出先名'] || '',
        請求書宛名: (r['請求書宛名'] || '') + ' ' + (r['敬称'] || ''),
        顧客名: r['顧客名'] || '',
        案件名: r['案件名'] || '',
        施工日: toDateInputValue_(r['施工日']),
        請求日: toDateInputValue_(r['請求日']),
        支払期限: toDateInputValue_(r['支払期限']),
        担当者: r['担当者'] || '',
        宛先メール: r['宛先メール'] || '',
        固定CC: r['固定CC'] || '',
        備考: r['備考'] || '',
        PDF_URL: r['PDF_URL'] || '',
        メール下書きURL: r['メール下書きURL'] || ''
      },
      rows: calc.pdfRows,
      display: calc.summaryDisplay,
      estimateTotal: toNumber_(r['見積時合計金額']),
      diff: calc.grandTotal - toNumber_(r['見積時合計金額'])
    };
  });
}

/* ===================== 請求日・支払期限 ===================== */

/**
 * 取引先ごとの締め日・支払サイトから請求日と支払期限を決める。
 * マスタが空なら「月末締め・翌月末払い」を既定にする。
 * 画面で上書きできるので、ここはあくまで初期値。
 */
function resolvePaymentTerms_(target, workDateInput, settings) {
  const workDate = parseDateInput_(workDateInput) || new Date();
  const closing = String((target && target.closingDay) || settings['既定_請求締め日'] || '月末').trim();
  const site = String((target && target.paymentSite) || settings['既定_支払サイト'] || '翌月末').trim();

  const invoiceDate = calcClosingDate_(workDate, closing);
  const dueDate = calcDueDate_(invoiceDate, site);

  return {
    invoiceDate: invoiceDate,
    dueDate: dueDate,
    note: '締め日：' + closing + ' / 支払サイト：' + site
      + (target && (target.closingDay || target.paymentSite) ? '（提出先マスタ）' : '（既定値）')
  };
}

function lastDayOfMonth_(year, monthIndex) {
  return new Date(year, monthIndex + 1, 0);
}

function clampToMonth_(year, monthIndex, day) {
  const last = lastDayOfMonth_(year, monthIndex).getDate();
  return new Date(year, monthIndex, Math.min(day, last));
}

/** 施工日が締め日を過ぎていれば翌月締めにする。 */
function calcClosingDate_(workDate, closing) {
  const y = workDate.getFullYear();
  const m = workDate.getMonth();
  const text = String(closing || '').trim();

  if (!text || text === '月末' || text === '末日' || text === '末') return lastDayOfMonth_(y, m);

  const day = toNumber_(text);
  if (!(day >= 1 && day <= 31)) return lastDayOfMonth_(y, m);

  const thisMonth = clampToMonth_(y, m, day);
  return workDate.getDate() <= thisMonth.getDate() ? thisMonth : clampToMonth_(y, m + 1, day);
}

function calcDueDate_(invoiceDate, site) {
  const y = invoiceDate.getFullYear();
  const m = invoiceDate.getMonth();
  const text = String(site || '').trim();

  if (text === '当月末') return lastDayOfMonth_(y, m);
  if (text === '翌月末') return lastDayOfMonth_(y, m + 1);
  if (text === '翌々月末') return lastDayOfMonth_(y, m + 2);

  const days = toNumber_(text.replace(/日/g, ''));
  if (days > 0) {
    const d = new Date(invoiceDate.getTime());
    d.setDate(d.getDate() + days);
    return d;
  }

  return lastDayOfMonth_(y, m + 1);
}

/* ===================== 請求額の計算 ===================== */

/**
 * 見積の明細をそのまま引き継ぎ、請求時の追加項目を「調整行」に変換して
 * 見積と同じ CalcEngine で計算する。計算式を二重に持たないための構成。
 */
function prepareInvoiceCalc_(payload, ctx) {
  const p = payload || {};
  const estimateSheet = getEstimateDataSheet_(ctx);
  const found = findEstimateRecord_(estimateSheet, p.estimateId);
  if (!found) throw new Error('見積IDが見つかりません：' + p.estimateId);

  const r = found.record;
  const estimateCalc = rebuildCalcFromRecord_(r, ctx);

  const calcPayload = {
    projectType: r['案件タイプ'] || '',
    remarks: p.remarks || '',
    workDate: toDateInputValue_(r['作業予定日']),
    highwayFee: toNumber_(r['高速代']),
    busyManual: parseBooleanLoose_(r['繁忙期_手動設定']),
    discountManual: parseBooleanLoose_(r['割引_手動設定']),
    adjustments: buildInvoiceAdjustments_(r, p),
    targetTotal: 0,
    details: extractDetailsFromRecord_(r)
  };

  return {
    estimateRecord: r,
    estimateRowNumber: found.rowNumber,
    estimateTotal: estimateCalc.grandTotal,
    calcPayload: calcPayload,
    calc: calculateEstimate_(calcPayload, ctx)
  };
}

function extractDetailsFromRecord_(record) {
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

  return details;
}

/** 請求時の追加項目を調整行に変換する。見積側の調整行はそのまま引き継ぐ。 */
function buildInvoiceAdjustments_(estimateRecord, form) {
  const out = parseAdjustmentsJson_(estimateRecord['調整_JSON']).filter(function (a) {
    // 見積の端数調整は台数も金額も変わり得るので請求には持ち込まない
    return a && !a.auto;
  });

  const parking = toNumber_(form.parkingFee);
  if (parking > 0) {
    out.push({
      name: '駐車場代', kind: 'surcharge', mode: 'amount', value: parking,
      base: 'taxable',
      taxType: isTaxable_(form.parkingTaxType) ? '課税' : '非課税',
      note: '請求時入力', auto: false
    });
  }

  const extra = toNumber_(form.extraWorkFee);
  if (extra > 0) {
    out.push({
      name: String(form.extraWorkName || '').trim() || '追加作業費',
      kind: 'surcharge', mode: 'amount', value: extra,
      base: 'taxable', taxType: '課税', note: '請求時入力', auto: false
    });
  }

  const discount = toNumber_(form.discountAmount);
  if (discount > 0) {
    out.push({
      name: String(form.discountName || '').trim() || '値引き',
      kind: 'discount', mode: 'amount', value: discount,
      base: 'taxable', taxType: '課税', note: '請求時入力', auto: false
    });
  }

  return out;
}

/** 保存済み請求レコードから計算し直す（PDF・メール本文用）。 */
function rebuildInvoiceCalc_(record, ctx) {
  return calculateEstimate_({
    projectType: record['案件タイプ'] || '',
    remarks: record['備考'] || '',
    workDate: toDateInputValue_(record['施工日']),
    highwayFee: toNumber_(record['高速代']),
    busyManual: parseBooleanLoose_(record['繁忙期_手動設定']),
    discountManual: parseBooleanLoose_(record['割引_手動設定']),
    adjustments: parseAdjustmentsJson_(record['調整_JSON']),
    targetTotal: 0,
    details: extractDetailsFromRecord_(record)
  }, ctx);
}

/* ===================== 保存レコード ===================== */

function buildInvoiceRecord_(payload, ctx, prepared, invoiceId, previousInvoiceId) {
  const p = payload || {};
  const r = prepared.estimateRecord;
  const calc = prepared.calc;
  const now = new Date();

  const record = {
    invoice_id: invoiceId,
    estimate_id: r['estimate_id'] || '',
    original_invoice_id: previousInvoiceId || '',
    project_status: '請求書作成済',
    請求ステータス: '未送付',
    作成日時: now,
    更新日時: now,
    作成者: p.staff || getCurrentUser_(),
    案件タイプ: r['案件タイプ'] || '',
    提出先名: r['提出先名'] || '',
    請求書宛名: r['見積書宛名'] || '',
    敬称: r['敬称'] || '',
    宛先メール: r['宛先メール'] || '',
    固定CC: r['固定CC'] || '',
    送信元メール: r['送信元メール'] || '',
    顧客名: r['顧客名'] || '',
    案件名: r['案件名'] || '',
    現場住所: r['現場住所'] || '',
    施工日: parseDateInput_(p.workCompletedDate) || '',
    請求日: parseDateInput_(p.invoiceDate) || now,
    支払期限: parseDateInput_(p.dueDate) || '',
    担当者: p.staff || '',
    請求番号: invoiceId,
    件名: r['案件名'] || r['顧客名'] || '',
    本文テンプレート種別: resolveInvoiceTemplateType_(r),
    備考: p.remarks || '',
    駐車場代: toNumber_(p.parkingFee),
    駐車場代_税区分: isTaxable_(p.parkingTaxType) ? '課税' : '非課税',
    高速代: toNumber_(r['高速代']),
    高速代_税区分: '非課税',
    追加作業費: toNumber_(p.extraWorkFee),
    値引き額: toNumber_(p.discountAmount),
    明細小計: calc.lineSubtotal,
    非課税小計: calc.nonTaxableSubtotal,
    課税小計: calc.taxableSubtotal,
    消費税: calc.tax,
    合計金額: calc.grandTotal,
    入金予定日: parseDateInput_(p.dueDate) || '',
    入金日: '',
    入金額: '',
    入金方法: '',
    未入金額: calc.grandTotal,
    PDF_URL: '',
    PDF_FILE_ID: '',
    メール下書きURL: '',
    メール下書きID: '',
    メール下書き作成日時: '',
    送付日: '',
    複製元請求書ID: previousInvoiceId || '',
    内部メモ: '',

    request_id: '',
    見積時合計金額: prepared.estimateTotal,
    見積差額: calc.grandTotal - prepared.estimateTotal,
    繁忙期_手動設定: boolText_(calc.busyManual),
    割引_手動設定: boolText_(calc.autoDiscountOn),
    調整合計額: calc.adjustmentTotal,
    調整_JSON: JSON.stringify((calc.appliedAdjustments || []).map(function (a) {
      return {
        name: a.name, kind: a.kind, mode: a.mode, value: a.value,
        base: a.base, taxType: a.taxType, note: a.note, auto: a.auto, amount: a.amount
      };
    }))
  };

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

function resolveInvoiceTemplateType_(estimateRecord) {
  return String(estimateRecord['案件タイプ'] || '').trim() === '自社'
    ? '自社案件_請求書送付'
    : '元請案件_請求書送付';
}

/* ===================== シート ===================== */

function getInvoiceDataSheet_(ctx) {
  const ss = getTemplateSs_(ctx.settings);
  const sheet = ss.getSheetByName(APP.SHEET_INVOICE_DATA);
  if (!sheet) throw new Error('シートが見つかりません：' + APP.SHEET_INVOICE_DATA);

  ensureHeaders_(sheet, getInvoiceHeaders_());
  return sheet;
}

function generateInvoiceId_(sheet) {
  const prefix = 'INV-' + formatDate_(new Date(), 'yyyyMMdd') + '-';
  const info = getHeaderInfo_(sheet);
  const col = info.map['invoice_id'];
  if (!col) throw new Error('請求データシートに invoice_id ヘッダーがありません。');

  const lastRow = sheet.getLastRow();
  let maxNo = 0;

  if (lastRow > info.headerRow) {
    const ids = sheet.getRange(info.headerRow + 1, col, lastRow - info.headerRow, 1).getDisplayValues();
    ids.forEach(function (row) {
      const id = String(row[0] || '');
      if (id.indexOf(prefix) !== 0) return;
      const n = Number(id.slice(prefix.length));
      if (!isNaN(n) && n > maxNo) maxNo = n;
    });
  }

  return prefix + String(maxNo + 1).padStart(4, '0');
}

function findInvoiceRecord_(sheet, invoiceId, hintRowNumber) {
  const info = getHeaderInfo_(sheet);
  const col = info.map['invoice_id'];
  if (!col) throw new Error('請求データシートに invoice_id ヘッダーがありません。');

  const target = String(invoiceId || '').trim();

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

/* ===================== PDF ===================== */

function generateInvoicePdf_(record, calc, ctx) {
  const templateId = String(ctx.settings['PDF生成用テンプレートスプレッドシートID'] || '').trim()
    || ctx.settings['見積請求書テンプレートスプレッドシートID']
    || APP.DEFAULT_TEMPLATE_SS_ID;

  const folderId = ctx.settings['請求書PDF保存フォルダID'] || APP.DEFAULT_INVOICE_FOLDER_ID;
  if (!folderId) throw new Error('請求書PDF保存フォルダIDが未設定です。');

  const folder = DriveApp.getFolderById(folderId);
  const tmpFile = DriveApp.getFileById(templateId).makeCopy('tmp_' + record.invoice_id + '_' + Date.now());
  const tmpSs = SpreadsheetApp.openById(tmpFile.getId());

  try {
    const cellDefs = getCellDefMap_('請求書', ctx);
    const targetSheetName = getTargetSheetNameFromDefs_(cellDefs, APP.TEMP_INVOICE_SHEET);
    const sheet = tmpSs.getSheetByName(targetSheetName);
    if (!sheet) throw new Error('対象シートが見つかりません：' + targetSheetName);

    fillInvoiceSheet_(sheet, cellDefs, record, calc, ctx.settings);
    SpreadsheetApp.flush();

    const pdfBlob = exportSheetToPdfBlob_(tmpSs.getId(), sheet.getSheetId());
    pdfBlob.setName(sanitizeFileName_(
      record.invoice_id + '_請求書_' + record['顧客名'] + '_' + record['案件名'] + '.pdf'
    ));

    const savedFile = folder.createFile(pdfBlob);
    return { file: savedFile, url: savedFile.getUrl(), fileId: savedFile.getId() };
  } finally {
    tmpFile.setTrashed(true);
  }
}

function fillInvoiceSheet_(sheet, defs, record, calc, settings) {
  const remarksText = [record['備考'] || '', settings['請求書備考注記'] || ''].filter(String).join('\n');

  setByKeys_(sheet, defs, {
    document_date: formatDate_(record['請求日'] || new Date(), 'yyyy/MM/dd'),
    document_no_label: '請求番号：',
    invoice_id: record.invoice_id,
    title: '御  請  求  書',
    addressee_name: record['請求書宛名'] || '',
    addressee_suffix: record['敬称'] || '',
    company_name: settings['会社名'] || '',
    company_zip: settings['会社郵便番号'] || '',
    company_address: settings['会社住所'] || '',
    company_tel: settings['会社電話番号'] || '',
    company_fax: settings['会社FAX'] || '',
    project_name: record['案件名'] || record['顧客名'] || '',
    project_suffix: 'について',
    greeting: '下記の通り御請求申し上げます。',
    total_amount_label: 'ご請求金額',
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
    grand_total: calc.grandTotal,
    // 差し込みセル定義に payment_due が無ければ書かずに素通りする
    payment_due: record['支払期限'] ? formatDate_(record['支払期限'], 'yyyy/MM/dd') : ''
  });

  writeDetailRows_(sheet, defs, calc.pdfRows.slice(0, APP.MAX_DETAIL_ROWS));
}

/* ===================== Gmail ===================== */

function createInvoiceMailDraft_(record, calc, ctx, pdfFile) {
  const to = String(record['宛先メール'] || '').trim();
  if (!to) throw new Error('宛先メールが未設定です。提出先マスタを確認してください。');

  const preview = buildInvoiceMailPreview_(record, calc, ctx);
  const options = buildGmailOptions_(record['送信元メール'], record['固定CC'], ctx.settings);
  options.attachments = [pdfFile.getBlob()];

  const draft = GmailApp.createDraft(to, preview.subject, preview.body, options);
  return { draftId: draft.getId(), draftUrl: getGmailDraftsUrl_(ctx.settings) };
}

function buildInvoiceMailPreview_(record, calc, ctx) {
  const templateType = record['本文テンプレート種別'] || '自社案件_請求書送付';
  const template = ctx.mailTemplates[templateType] || getFallbackInvoiceTemplate_();

  const tokens = buildTokensFromRecord_(record, ctx, {
    見積金額: formatYen_(calc.grandTotal),
    作成日: formatDate_(record['請求日'] || new Date(), 'yyyy/MM/dd'),
    PDF_URL: record['PDF_URL'] || ''
  });

  tokens['請求金額'] = formatYen_(calc.grandTotal);
  tokens['請求ID'] = record.invoice_id || '';
  tokens['請求日'] = formatDate_(record['請求日'] || new Date(), 'yyyy/MM/dd');
  tokens['支払期限'] = record['支払期限'] ? formatDate_(record['支払期限'], 'yyyy/MM/dd') : '';
  tokens['施工日'] = record['施工日'] ? formatDate_(record['施工日'], 'yyyy/MM/dd') : '';

  return {
    to: record['宛先メール'] || '',
    cc: record['固定CC'] || '',
    from: record['送信元メール'] || '',
    subject: renderTemplate_(template.subject, tokens),
    body: renderTemplate_(template.body, tokens)
  };
}

function getFallbackInvoiceTemplate_() {
  return {
    subject: '【ご請求書】{案件名} / {顧客名}様',
    body: '{顧客名}様\n\nお世話になっております。\nご請求書を添付にてお送りいたします。\n\n■案件名：{案件名}\n■ご請求金額：{請求金額}\n■請求番号：{請求ID}\n■お支払期限：{支払期限}\n\nご確認のほど、よろしくお願いいたします。\n\n{会社名}'
  };
}

/* ===================== スキーマ ===================== */

function getInvoiceHeaders_() {
  const headers = [
    'invoice_id', 'estimate_id', 'original_invoice_id', 'project_status', '請求ステータス',
    '作成日時', '更新日時', '作成者', '案件タイプ', '提出先名', '請求書宛名', '敬称',
    '宛先メール', '固定CC', '送信元メール', '顧客名', '案件名', '現場住所', '施工日',
    '請求日', '支払期限', '担当者', '請求番号', '件名', '本文テンプレート種別', '備考',
    '駐車場代', '駐車場代_税区分', '高速代', '高速代_税区分', '追加作業費', '値引き額',
    '明細小計', '非課税小計', '課税小計', '消費税', '合計金額', '入金予定日', '入金日',
    '入金額', '入金方法', '未入金額', 'PDF_URL', 'PDF_FILE_ID', 'メール下書きURL',
    'メール下書きID', 'メール下書き作成日時', '送付日', '複製元請求書ID'
  ];

  for (let i = 1; i <= APP.MAX_DETAIL_ROWS; i++) {
    const p = '明細' + pad2_(i) + '_';
    headers.push(p + '品名', p + 'メニューID', p + 'メニュータイプ', p + '数量', p + '単位',
      p + '単価', p + '金額', p + '税区分', p + '備考');
  }

  headers.push('内部メモ');

  // 2026-09改修の追加列。既存列の位置は動かさず右端に足す。
  headers.push('request_id', '見積時合計金額', '見積差額',
    '繁忙期_手動設定', '割引_手動設定', '調整合計額', '調整_JSON');

  for (let i = 1; i <= APP.MAX_DETAIL_ROWS; i++) {
    headers.push('明細' + pad2_(i) + '_値引き額');
  }

  return headers;
}
