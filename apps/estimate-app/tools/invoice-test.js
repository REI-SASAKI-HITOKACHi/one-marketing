#!/usr/bin/env node
/**
 * 請求書ロジックのテスト
 *
 *   node apps/estimate-app/tools/invoice-test.js
 *
 * Invoice.gs の実関数を評価して、
 *   - 請求日・支払期限が取引先マスタの締め日／支払サイトどおりに決まるか
 *   - 駐車場代・追加作業費・値引きが請求額に正しく効くか
 *   - 保存レコードから復元しても金額が変わらないか（PDFと画面がずれない）
 * を確認する。
 */
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const srcDir = path.join(__dirname, '..', 'src');

function pad(n, len) { return String(n).padStart(len || 2, '0'); }

const sandbox = {
  console: console, JSON: JSON, Math: Math, Date: Date, Number: Number, String: String,
  Object: Object, Array: Array, isNaN: isNaN, isFinite: isFinite,

  HtmlService: {
    createHtmlOutputFromFile: function (name) {
      return { getContent: function () { return fs.readFileSync(path.join(srcDir, name + '.html'), 'utf8'); } };
    }
  },
  Utilities: {
    formatDate: function (date, tz, pattern) {
      const d = date instanceof Date ? date : new Date(date);
      return pattern
        .replace('yyyy', d.getFullYear()).replace('MM', pad(d.getMonth() + 1))
        .replace('dd', pad(d.getDate())).replace('HH', pad(d.getHours()))
        .replace('mm', pad(d.getMinutes())).replace('ss', pad(d.getSeconds()));
    }
  },
  Session: {
    getActiveUser: function () { return { getEmail: function () { return 'test@example.com'; } }; },
    getEffectiveUser: function () { return { getEmail: function () { return 'test@example.com'; } }; }
  }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(path.join(srcDir, 'code.gs'), 'utf8'), sandbox, { filename: 'code.gs' });
vm.runInContext(fs.readFileSync(path.join(srcDir, 'Invoice.gs'), 'utf8'), sandbox, { filename: 'Invoice.gs' });

/* ===================== テスト用マスタ ===================== */

const MENUS = {
  M001: { menuId: 'M001', name: 'エアコンクリーニング（ノーマルエアコン）', menuType: 'メイン', rawMenuType: 'メイン', category: 'エアコン', unitPrice: 9800, unitPriceRaw: 9800, taxType: '課税', unit: '台', busyTarget: true, busySurchargeRaw: 3300, discountTarget: true, multipleDiscountTarget: true, invoiceReusable: true, note: '', requireCheck: '' },
  O002: { menuId: 'O002', name: '室外機セット', menuType: 'オプション', rawMenuType: 'オプション', category: 'エアコン', unitPrice: 5500, unitPriceRaw: 5500, taxType: '課税', unit: '台', busyTarget: false, busySurchargeRaw: '', discountTarget: false, multipleDiscountTarget: false, invoiceReusable: true, note: '', requireCheck: '' }
};

const CTX = {
  settings: { 会社名: 'ワンヒッター株式会社', 送信元メール: 'info@one-hitter.her.jp' },
  taxRate: 0.10,
  busySurcharge: 3300,
  busySurchargeUnit: '数量ごと',
  autoDiscountEnabled: false,
  largeDiscountRatio: 0.30,
  menuMap: MENUS,
  discountRules: [],
  submitTargets: []
};

let pass = 0;
const failures = [];

function check(name, actual, expected) {
  const a = JSON.stringify(actual);
  const e = JSON.stringify(expected);
  if (a === e) { pass++; return; }
  failures.push(`${name}\n    期待: ${e}\n    実際: ${a}`);
}

function ymd(date) {
  return date.getFullYear() + '-' + pad(date.getMonth() + 1) + '-' + pad(date.getDate());
}

/* ===================== 請求日・支払期限 ===================== */

console.log('\n請求日・支払期限（取引先マスタの締め日／支払サイト）');

function terms(closingDay, paymentSite, workDate, holidayRule) {
  return sandbox.resolvePaymentTerms_(
    { closingDay: closingDay, paymentSite: paymentSite, paymentHolidayRule: holidayRule || '' },
    workDate, CTX.settings);
}

function dates(closingDay, paymentSite, workDate, holidayRule) {
  const t = terms(closingDay, paymentSite, workDate, holidayRule);
  return [ymd(t.invoiceDate), ymd(t.dueDate)];
}

check('T-1 月末締め・翌月末払い（既定）', (() => {
  const t = terms('', '', '2026-05-14');
  return [ymd(t.invoiceDate), ymd(t.dueDate)];
})(), ['2026-05-31', '2026-06-30']);

check('T-2 月末締め・翌々月末払い', (() => {
  const t = terms('月末', '翌々月末', '2026-05-14');
  return [ymd(t.invoiceDate), ymd(t.dueDate)];
})(), ['2026-05-31', '2026-07-31']);

check('T-3 20日締め・施工日が締め日前なら当月締め', (() => {
  const t = terms('20', '翌月末', '2026-05-14');
  return [ymd(t.invoiceDate), ymd(t.dueDate)];
})(), ['2026-05-20', '2026-06-30']);

check('T-4 20日締め・施工日が締め日を過ぎたら翌月締め', (() => {
  const t = terms('20', '翌月末', '2026-05-25');
  return [ymd(t.invoiceDate), ymd(t.dueDate)];
})(), ['2026-06-20', '2026-07-31']);

check('T-5 31日締めは短い月では末日に丸める（2月）', (() => {
  const t = terms('31', '翌月末', '2026-02-10');
  return [ymd(t.invoiceDate), ymd(t.dueDate)];
})(), ['2026-02-28', '2026-03-31']);

check('T-6 支払サイトが日数指定（30日）', (() => {
  const t = terms('月末', '30日', '2026-05-14');
  return [ymd(t.invoiceDate), ymd(t.dueDate)];
})(), ['2026-05-31', '2026-06-30']);

check('T-7 年跨ぎ（12月締め → 翌年1月末）', (() => {
  const t = terms('月末', '翌月末', '2026-12-10');
  return [ymd(t.invoiceDate), ymd(t.dueDate)];
})(), ['2026-12-31', '2027-01-31']);

check('T-8 当月末払い', (() => {
  const t = terms('月末', '当月末', '2026-05-14');
  return [ymd(t.invoiceDate), ymd(t.dueDate)];
})(), ['2026-05-31', '2026-05-31']);

/* --- 月＋日の指定（20日締め翌月10日払い等の実務条件） --- */

check('T-9 20日締め・翌月10日払い', dates('20', '翌月10日', '2026-05-14'), ['2026-05-20', '2026-06-10']);

check('T-10 20日締め・翌月10日払い（締め日超過で翌月締め）',
  dates('20', '翌月10日', '2026-05-25'), ['2026-06-20', '2026-07-10']);

check('T-11 月末締め・翌々月10日払い', dates('月末', '翌々月10日', '2026-05-14'), ['2026-05-31', '2026-07-10']);

check('T-12 15日締め・当月25日払い', dates('15', '当月25日', '2026-05-10'), ['2026-05-15', '2026-05-25']);

check('T-13 月＋日の指定で年を跨ぐ', dates('月末', '翌月10日', '2026-12-05'), ['2026-12-31', '2027-01-10']);

check('T-14 翌月31日払いは短い月では末日に丸める',
  dates('月末', '翌月31日', '2026-01-15'), ['2026-01-31', '2026-02-28']);

check('T-15 「翌月」だけなら翌月末とみなす', dates('月末', '翌月', '2026-05-14'), ['2026-05-31', '2026-06-30']);

/* --- 土日の調整（祝日は判定しない） --- */

// 2026-05-31 は日曜
check('T-16 支払期限が日曜・調整なしならそのまま',
  dates('月末', '当月末', '2026-05-14'), ['2026-05-31', '2026-05-31']);

check('T-17 支払期限が日曜・前営業日なら金曜へ',
  dates('月末', '当月末', '2026-05-14', '前営業日'), ['2026-05-31', '2026-05-29']);

check('T-18 支払期限が日曜・翌営業日なら月曜へ',
  dates('月末', '当月末', '2026-05-14', '翌営業日'), ['2026-05-31', '2026-06-01']);

check('T-19 平日の支払期限は調整しても動かない',
  dates('月末', '翌月10日', '2026-05-14', '前営業日'), ['2026-05-31', '2026-06-10']);

/* --- マスタ優先と既定値 --- */

check('T-20 マスタ未設定なら既定値を使い、その旨がわかる', (() => {
  const t = sandbox.resolvePaymentTerms_(null, '2026-05-14', CTX.settings);
  return [ymd(t.invoiceDate), ymd(t.dueDate), t.fromMaster];
})(), ['2026-05-31', '2026-06-30', false]);

check('T-21 マスタに設定があればそちらが優先され、根拠が出る', (() => {
  const t = terms('20', '翌月10日', '2026-05-14');
  return [t.fromMaster, t.note.indexOf('提出先マスタ') >= 0];
})(), [true, true]);

check('T-22 設定マスタの既定値も効く', (() => {
  const custom = Object.assign({}, CTX.settings, { 既定_請求締め日: '20', 既定_支払サイト: '翌月10日' });
  const t = sandbox.resolvePaymentTerms_(null, '2026-05-14', custom);
  return [ymd(t.invoiceDate), ymd(t.dueDate)];
})(), ['2026-05-20', '2026-06-10']);

/* ===================== 請求額 ===================== */

console.log('請求額の計算（駐車場代・追加作業費・値引き）');

// 見積レコードを作る：ノーマル2台 + 室外機1台
const estimatePayload = {
  projectType: '自社', customerName: 'テスト太郎', projectName: 'エアコン',
  workDate: '2026-11-20', staff: '渡辺 和真',
  details: [{ menuId: 'M001', qty: 2 }, { menuId: 'O002', qty: 1 }]
};

const estimateCalc = sandbox.calculateEstimate_(estimatePayload, CTX);
const estimateRecord = sandbox.buildEstimateRecord_(estimatePayload, CTX, estimateCalc, 'EST-20261120-0001');

check('E-0 見積額の前提（9,800×2 + 5,500 = 25,100 / 税2,510）',
  [estimateCalc.documentSubtotal, estimateCalc.tax, estimateCalc.grandTotal], [25100, 2510, 27610]);

/** 請求フォームを渡して calc だけ得る（シート読み込みを介さない経路で検証する） */
function invoiceCalc(form) {
  const adjustments = sandbox.buildInvoiceAdjustments_(estimateRecord, form);
  return sandbox.calculateEstimate_({
    projectType: estimateRecord['案件タイプ'],
    remarks: form.remarks || '',
    workDate: '2026-11-20',
    highwayFee: sandbox.toNumber_(estimateRecord['高速代']),
    busyManual: sandbox.parseBooleanLoose_(estimateRecord['繁忙期_手動設定']),
    discountManual: sandbox.parseBooleanLoose_(estimateRecord['割引_手動設定']),
    adjustments: adjustments,
    targetTotal: 0,
    details: sandbox.extractDetailsFromRecord_(estimateRecord)
  }, CTX);
}

check('I-1 追加なしなら見積と同額', invoiceCalc({}).grandTotal, 27610);

check('I-2 駐車場代（課税）2,000円', (() => {
  const c = invoiceCalc({ parkingFee: 2000, parkingTaxType: '課税' });
  return [c.documentSubtotal, c.tax, c.grandTotal];
})(), [27100, 2710, 29810]);

check('I-3 駐車場代（非課税）2,000円は消費税が変わらない', (() => {
  const c = invoiceCalc({ parkingFee: 2000, parkingTaxType: '非課税' });
  return [c.documentSubtotal, c.tax, c.grandTotal];
})(), [27100, 2510, 29610]);

check('I-4 追加作業費5,000円', invoiceCalc({ extraWorkFee: 5000 }).grandTotal, 33110);

check('I-5 値引き3,000円', invoiceCalc({ discountAmount: 3000 }).grandTotal, 24310);

check('I-6 駐車場代＋追加作業費＋値引きの複合', (() => {
  const c = invoiceCalc({ parkingFee: 1500, parkingTaxType: '課税', extraWorkFee: 4000, discountAmount: 2000 });
  return [c.documentSubtotal, c.tax, c.grandTotal];
})(), [28600, 2860, 31460]);

check('I-7 名目を変えるとPDFの行名も変わる', (() => {
  const c = invoiceCalc({ extraWorkFee: 3000, extraWorkName: '高所作業費' });
  return c.pdfRows.map(r => r.name).filter(n => n.indexOf('高所') >= 0);
})(), ['高所作業費']);

check('I-8 小計＋消費税＝合計 が常に成立する', (() => {
  const c = invoiceCalc({ parkingFee: 1500, parkingTaxType: '非課税', extraWorkFee: 4000, discountAmount: 2000 });
  return c.documentSubtotal + c.tax === c.grandTotal;
})(), true);

check('I-9 PDF明細の合計＝書類小計', (() => {
  const c = invoiceCalc({ parkingFee: 1500, parkingTaxType: '課税', extraWorkFee: 4000, discountAmount: 2000 });
  return c.pdfRows.reduce((s, r) => s + r.amount, 0) === c.documentSubtotal;
})(), true);

check('I-10 見積の端数調整は請求に持ち込まない', (() => {
  const withTarget = Object.assign({}, estimatePayload, { targetTotal: 25000 });
  const tCalc = sandbox.calculateEstimate_(withTarget, CTX);
  const tRecord = sandbox.buildEstimateRecord_(withTarget, CTX, tCalc, 'EST-20261120-0002');
  const adjustments = sandbox.buildInvoiceAdjustments_(tRecord, {});
  return [tCalc.grandTotal, adjustments.length];
})(), [25000, 0]);

/* ===================== 保存 → 復元 ===================== */

console.log('請求レコードの往復');

function invoiceRoundTrip(label, form) {
  const adjustments = sandbox.buildInvoiceAdjustments_(estimateRecord, form);
  const calcPayload = {
    projectType: estimateRecord['案件タイプ'],
    remarks: form.remarks || '',
    workDate: '2026-11-20',
    highwayFee: 0,
    busyManual: false,
    discountManual: false,
    adjustments: adjustments,
    targetTotal: 0,
    details: sandbox.extractDetailsFromRecord_(estimateRecord)
  };

  const prepared = {
    estimateRecord: estimateRecord,
    estimateRowNumber: 2,
    estimateTotal: estimateCalc.grandTotal,
    calcPayload: calcPayload,
    calc: sandbox.calculateEstimate_(calcPayload, CTX)
  };

  const payload = Object.assign({ estimateId: 'EST-20261120-0001', staff: '渡辺 和真' }, form);
  const record = sandbox.buildInvoiceRecord_(payload, CTX, prepared, 'INV-20261130-0001', '');
  const restored = sandbox.rebuildInvoiceCalc_(record, CTX);

  check(label + '：合計', restored.grandTotal, prepared.calc.grandTotal);
  check(label + '：消費税', restored.tax, prepared.calc.tax);
  check(label + '：PDF明細', restored.pdfRows, prepared.calc.pdfRows);
  check(label + '：レコードの合計金額', record['合計金額'], prepared.calc.grandTotal);

  return record;
}

invoiceRoundTrip('追加なし', {});
invoiceRoundTrip('駐車場代あり', { parkingFee: 2000, parkingTaxType: '課税' });
const complex = invoiceRoundTrip('複合', {
  parkingFee: 1500, parkingTaxType: '非課税', extraWorkFee: 4000,
  discountAmount: 2000, workCompletedDate: '2026-11-20',
  invoiceDate: '2026-11-30', dueDate: '2026-12-31', remarks: 'テスト備考'
});

check('R-1 見積IDが紐づく', complex['estimate_id'], 'EST-20261120-0001');
check('R-2 見積時の合計を記録する', complex['見積時合計金額'], 27610);
check('R-3 差額を記録する', complex['見積差額'], complex['合計金額'] - 27610);
check('R-4 駐車場代の税区分を記録する', complex['駐車場代_税区分'], '非課税');
check('R-5 支払期限が入る', sandbox.toDateInputValue_(complex['支払期限']), '2026-12-31');
check('R-6 請求ステータスの初期値', complex['請求ステータス'], '未送付');
check('R-7 未入金額＝合計金額', complex['未入金額'], complex['合計金額']);

/* ===================== ヘッダー定義 ===================== */

console.log('ヘッダー定義');

const headers = sandbox.getInvoiceHeaders_();
check('重複がない', headers.length, new Set(headers).size);
check('先頭列が従来どおり', headers.slice(0, 5),
  ['invoice_id', 'estimate_id', 'original_invoice_id', 'project_status', '請求ステータス']);
check('内部メモが追加列より前', headers.indexOf('内部メモ') < headers.indexOf('request_id'), true);

const unknown = Object.keys(complex).filter(k => headers.indexOf(k) < 0);
check('保存レコードの全キーがヘッダーに存在する', unknown, []);

const estHeaders = sandbox.getEstimateHeaders_();
check('見積ヘッダーと請求ヘッダーが別物', estHeaders[0] !== headers[0], true);

/* ===================== 差し込みセル定義 ===================== */

console.log('差し込みセル定義（本番テンプレートの実レイアウトと突き合わせ）');

const defRows = sandbox.getDefaultCellDefinitionRows_();

function defMap(docType) {
  const map = {};
  defRows.filter(r => r[0] === docType).forEach(r => { map[r[2]] = r[4]; });
  return map;
}

const estDefs = defMap('見積書');
const invDefs = defMap('請求書');

// 実テンプレート（xlsx書き出しで確認）
//   見積書 : A19=お見積金額 / C19=　円 / 備考 A39:D41 / 明細 22〜38 / 小計F39 税F40 合計F41
//   請求書 : A19=ご請求金額 / B19==F41 / C19=　円 / 備考 A39:D40 / A41=お支払い期限：
check('C-1 合計表示は B19（C19のテンプレート「円」を消さない）', [estDefs.total_amount_display, invDefs.total_amount_display], ['B19', 'B19']);
check('C-2 合計単位は C19（テンプレートの「円」の位置）', [estDefs.total_amount_unit, invDefs.total_amount_unit], ['C19', 'C19']);
check('C-3 見積書の備考は A39:D41', estDefs.remarks, 'A39:D41');
check('C-4 請求書の備考は A39:D40（41行目のお支払い期限を消さない）', invDefs.remarks, 'A39:D40');
check('C-5 請求書だけ payment_due が B41 にある', [estDefs.payment_due, invDefs.payment_due], [undefined, 'B41']);
check('C-6 明細範囲は 22〜38（テンプレートの式を空で上書きするため）',
  [estDefs.detail_name_range, estDefs.detail_qty_range, estDefs.detail_unit_price_range, estDefs.detail_amount_range],
  ['A22:C38', 'D22:D38', 'E22:E38', 'F22:F38']);
check('C-7 小計・消費税・合計の位置', [invDefs.subtotal, invDefs.tax, invDefs.grand_total], ['F39', 'F40', 'F41']);
check('C-8 帳票番号は F3', [estDefs.estimate_id, invDefs.invoice_id], ['F3', 'F3']);
check('C-9 定義キーに重複がない', defRows.length, new Set(defRows.map(r => r[0] + '::' + r[2])).size);

/* ===================== 結果 ===================== */

console.log('');
if (failures.length === 0) {
  console.log(`✅ 全 ${pass} ケース合格`);
  process.exit(0);
}

console.log(`❌ ${failures.length} 件失敗 / ${pass} 件合格\n`);
failures.forEach(f => console.log('  ✗ ' + f + '\n'));
process.exit(1);
