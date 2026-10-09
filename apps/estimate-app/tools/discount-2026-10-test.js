#!/usr/bin/env node
/**
 * 2026-10 の割引追加（早期予約11月10%／チラシ特典／紹介割引）のテスト
 *
 *   node apps/estimate-app/tools/discount-2026-10-test.js
 *
 * 一番大事なのは「新しい項目を使っていない見積は、これまでと1円も変わらない」こと。
 * （オーナー指示 2026-09-16：通常見積は従来どおり）
 * code.gs / Invoice.gs / Admin.gs の実関数を評価する。Google側のAPIだけ最小限スタブする。
 */
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const srcDir = path.join(__dirname, '..', 'src');

function pad(n, len) { return String(n).padStart(len || 2, '0'); }

const sandbox = {
  console: { log: function () {}, warn: function () {}, error: console.error },
  JSON: JSON, Math: Math, Date: Date, Number: Number, String: String,
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
    getActiveUser: function () { return { getEmail: function () { return 'owner@example.com'; } }; },
    getEffectiveUser: function () { return { getEmail: function () { return 'owner@example.com'; } }; }
  },
  LockService: { getScriptLock: function () { return { waitLock: function () {}, releaseLock: function () {} }; } },
  CacheService: { getScriptCache: function () { return { get: function () { return null; }, removeAll: function () {}, put: function () {} }; } }
};

vm.createContext(sandbox);
['code.gs', 'Invoice.gs', 'Admin.gs'].forEach(function (f) {
  vm.runInContext(fs.readFileSync(path.join(srcDir, f), 'utf8'), sandbox, { filename: f });
});

/* ===================== テスト用マスタ ===================== */

const MENUS = {
  M001: { menuId: 'M001', name: 'エアコンクリーニング（ノーマルエアコン）', menuType: 'メイン', rawMenuType: 'メイン', category: 'エアコン', unitPrice: 9800, unitPriceRaw: 9800, taxType: '課税', unit: '台', busyTarget: true, busySurchargeRaw: 3300, discountTarget: true, multipleDiscountTarget: true, invoiceReusable: true, note: '', requireCheck: '' },
  O002: { menuId: 'O002', name: '室外機セット', menuType: 'オプション', rawMenuType: 'オプション', category: 'エアコン', unitPrice: 5500, unitPriceRaw: 5500, taxType: '課税', unit: '台', busyTarget: false, busySurchargeRaw: '', discountTarget: false, multipleDiscountTarget: false, invoiceReusable: true, note: '', requireCheck: '' }
};

const RULES = [
  { ruleType: '繁忙期', target: '全体', startMonth: 5, endMonth: 7, condition: '', value: 3300, valueType: '金額', priority: 10 },
  { ruleType: '早期予約割引', target: '全体', startMonth: 8, endMonth: 11, condition: '', value: 0.10, valueType: '率', priority: 20 },
  { ruleType: '早期予約割引', target: '全体', startMonth: 1, endMonth: 2, condition: '', value: 0.15, valueType: '率', priority: 20 },
  { ruleType: '複数台割引', target: 'ノーマルエアコン', startMonth: '', endMonth: '', condition: 'totalQty:5-10', value: 500, valueType: '金額/台', priority: 30 }
];

const BASE_CTX = {
  settings: { 会社名: 'ワンヒッター株式会社', 送信元メール: 'info@one-hitter.her.jp' },
  taxRate: 0.10,
  busySurcharge: 3300,
  busySurchargeUnit: '数量ごと',
  autoDiscountEnabled: false, // 本番の通常見積と同じ
  busySurchargeTaxIncluded: true,
  setPricingEnabled: true,
  largeDiscountRatio: 0.30,
  netBenefit: { name: 'ネット申込特典', amount: 2200, note: '' },
  menuMap: MENUS,
  discountRules: RULES,
  submitTargets: []
};
const CTX_OLD = BASE_CTX; // チラシ特典の行が無いマスタ（これまで）
const CTX = Object.assign({}, BASE_CTX, { flyerBenefit: { name: 'チラシ特典', amount: 500, note: '' } });

/* ===================== テスト部品 ===================== */

let pass = 0;
const failures = [];

function check(name, actual, expected) {
  const a = JSON.stringify(actual);
  const e = JSON.stringify(expected);
  if (a === e) { pass++; return; }
  failures.push(`${name}\n    期待: ${e}\n    実際: ${a}`);
}

const ONE = [{ menuId: 'M001', qty: 1 }];

function pl(extra) {
  return Object.assign({ projectType: '自社', customerName: 'テスト太郎', workDate: '2026-09-10', details: ONE }, extra || {});
}
function calc(extra, ctx) { return sandbox.calculateEstimate_(pl(extra), ctx || CTX); }
function names(c) { return c.pdfRows.map(r => r.name); }
function exTexts(c) { return (c.exceptions || []).map(e => (e.level || '') + ':' + (e.message || e.text || JSON.stringify(e))); }
function sumRows(c) { return c.pdfRows.reduce((s, r) => s + r.amount, 0); }

/** 金額まわりの結果だけ取り出す（新しい項目は含めない＝従来と比べるため） */
function core(c) {
  return {
    grandTotal: c.grandTotal, tax: c.tax, taxable: c.taxableSubtotal, doc: c.documentSubtotal,
    pdf: c.pdfRows, exceptions: c.exceptions
  };
}

/* ===================== 1. 通常見積は変わらない ===================== */

console.log('\n新項目を使わない見積は従来と同じ');

const PLAIN_CASES = [
  ['9月・1台', { workDate: '2026-09-10' }],
  ['5月繁忙期・3台', { workDate: '2026-05-20', details: [{ menuId: 'M001', qty: 3 }] }],
  ['1月・5台・自動割引ON', { workDate: '2026-01-20', discountManual: true, details: [{ menuId: 'M001', qty: 5 }] }],
  ['11月・室外機あり', { workDate: '2026-11-20', details: [{ menuId: 'M001', qty: 2 }, { menuId: 'O002', qty: 2 }] }],
  ['WEB経由', { channel: 'web', workDate: '2026-09-10' }],
  ['調整行あり', { workDate: '2026-12-10', adjustments: [{ name: '値引き', kind: 'discount', mode: 'amount', value: 1000, taxType: '課税' }] }]
];

PLAIN_CASES.forEach(function (c) {
  const unused = [
    ['未指定', {}],
    ['false', { flyerManual: false, referralAmount: 0, referralBalance: '' }],
    ['null', { flyerManual: null, referralAmount: null, referralBalance: null }],
    ['空文字', { flyerManual: '', referralAmount: '', referralBalance: '' }],
    ['"false"', { flyerManual: 'false', referralAmount: '0' }]
  ];
  const old = core(calc(c[1], CTX_OLD));
  unused.forEach(function (u) {
    check(c[0] + '（' + u[0] + '）：チラシ特典の行があるマスタでも、行が無いマスタと同じ',
      core(calc(Object.assign({}, c[1], u[1]), CTX)), old);
  });
});

// 保存・復元の往復でも変わらない（古いレコード＝新しい列が無い、を含む）
(function () {
  PLAIN_CASES.forEach(function (c) {
    const payload = pl(c[1]);
    const saved = sandbox.calculateEstimate_(payload, CTX);
    const record = sandbox.buildEstimateRecord_(payload, CTX, saved, 'EST-20260910-0001');
    const restored = sandbox.rebuildCalcFromRecord_(record, CTX);
    check(c[0] + '：往復で合計が同じ', restored.grandTotal, saved.grandTotal);
    check(c[0] + '：往復でPDF明細が同じ', restored.pdfRows, saved.pdfRows);

    const legacy = Object.assign({}, record);
    ['チラシ特典_手動設定', 'チラシ特典額', 'チラシ特典_税込額', '紹介割引_入力額', '紹介割引額', '紹介割引_適用額', '紹介割引_残り確認']
      .forEach(function (k) { delete legacy[k]; });
    check(c[0] + '：新しい列が無い古いレコードでも同じ', sandbox.rebuildCalcFromRecord_(legacy, CTX).grandTotal, saved.grandTotal);

    ['チラシ特典_手動設定', 'チラシ特典額', 'チラシ特典_税込額', '紹介割引_入力額', '紹介割引額', '紹介割引_適用額', '紹介割引_残り確認']
      .forEach(function (k) {
        check(c[0] + '：未使用なら ' + k + ' は空欄', record[k] === '' || record[k] === false || record[k] === 0 || record[k] === undefined, true);
      });
  });
})();

/* ===================== 2. 早期予約（11月も10%） ===================== */

console.log('11月の早期予約10%');

(function () {
  const sep = calc({ workDate: '2026-09-10', discountManual: true });
  const nov = calc({ workDate: '2026-11-10', discountManual: true });
  const dec = calc({ workDate: '2026-12-10', discountManual: true });
  const jan = calc({ workDate: '2027-01-10', discountManual: true });
  check('9月：10%（980円）', sep.autoDiscountApplied, 980);
  check('11月：10%（980円）', nov.autoDiscountApplied, 980);
  check('12月：なし', dec.autoDiscountApplied, 0);
  check('1月：15%（1,470円）', jan.autoDiscountApplied, 1470);
  check('11月の合計', nov.grandTotal, 9702);
  check('12月は割引なしの合計', dec.grandTotal, 10780);

  // WEB経由は早期予約を「1箇所のみ」に限る（予約フォームと同じ）。ネット申込特典は外して、早期予約だけを見る
  const webCtx = Object.assign({}, CTX, { autoDiscountEnabledWeb: true, netBenefit: null });
  const web = calc({ workDate: '2026-11-10', channel: 'web' }, webCtx);
  const webSep = calc({ workDate: '2026-09-10', channel: 'web' }, webCtx);
  const webDec = calc({ workDate: '2026-12-10', channel: 'web' }, webCtx);
  check('WEB経由・1箇所・11月：9月と同じ割引（980円）', [web.autoDiscountApplied, webSep.autoDiscountApplied], [980, 980]);
  check('WEB経由・12月：付かない', webDec.autoDiscountApplied, 0);
  const web2 = calc({ workDate: '2026-11-10', channel: 'web', details: [{ menuId: 'M001', qty: 2 }] }, webCtx);
  check('WEB経由・2箇所以上は早期予約にならない（従来どおり）', web2.autoDiscountType === '早期予約割引', false);
})();

/* ===================== 3. チラシ特典 ===================== */

console.log('チラシ特典');

(function () {
  const plain = calc({});
  const f = calc({ flyerManual: true });
  check('チラシ特典のみ：合計', f.grandTotal, 10280);
  check('チラシ特典のみ：500円下がる', plain.grandTotal - f.grandTotal, 500);
  check('チラシ特典のみ：適用額（税抜）', f.flyerApplied, 455);
  check('チラシ特典のみ：行名に税込500円引き', names(f).some(n => n.indexOf('チラシ特典') >= 0 && n.indexOf('500') >= 0), true);
  check('チラシ特典のみ：PDF明細の合計＝書類小計', sumRows(f), f.documentSubtotal);
  check('チラシ特典のみ：使っただけでは確認事項を出さない', f.exceptions.filter(e => e.level === 'review').length, 0);

  // 既定OFF：チェックしなければ付かない
  check('チェックなしなら付かない', calc({}).flyerApplied || 0, 0);

  // マスタに額が無いのにチェックされた
  const noMaster = calc({ flyerManual: true }, CTX_OLD);
  check('マスタに行が無い：金額は変わらない', noMaster.grandTotal, plain.grandTotal);
  check('マスタに行が無い：アラートが出る', exTexts(noMaster).length > 0, true);

  // 他の割引との関係（併用不可＝大きいほう）
  const lost = calc({ flyerManual: true, discountManual: true });
  check('早期予約980円のほうが大きい：チラシは付かない', lost.flyerApplied || 0, 0);
  check('早期予約980円のほうが大きい：合計は早期予約のみ', lost.grandTotal, 9702);
  check('早期予約980円のほうが大きい：権利が残るとわかる文言が出る', exTexts(lost).some(t => t.indexOf('権利は残ります') >= 0), true);

  // 同額は他の割引を優先（チラシ特典を使い切らせない）
  const tieCtx = Object.assign({}, CTX, { flyerBenefit: { name: 'チラシ特典', amount: 1078, note: '' } });
  const tie = calc({ flyerManual: true, discountManual: true }, tieCtx);
  check('同額なら他の割引を優先する', tie.flyerApplied || 0, 0);

  // 手入力の値引きと併用すると確認事項
  const withManual = calc({ flyerManual: true, adjustments: [{ name: 'お詫び', kind: 'discount', mode: 'amount', value: 300, taxType: '課税' }] });
  check('手入力の値引き＋チラシ：確認が出る', exTexts(withManual).length > 0, true);
})();

/* ===================== 4. 紹介割引 ===================== */

console.log('紹介割引');

(function () {
  const r = calc({ referralAmount: 1000 });
  check('紹介割引1,000円：合計', r.grandTotal, 9780);
  check('紹介割引1,000円：行名', names(r).some(n => n.indexOf('紹介割引') >= 0), true);
  check('紹介割引1,000円：PDF明細の合計＝書類小計', sumRows(r), r.documentSubtotal);
  check('紹介割引1,000円：適用額（税抜）', r.referralApplied, 909);

  const over = calc({ referralAmount: 1000, referralBalance: 500 });
  check('残りを超える：確認事項（review）が出る', over.exceptions.some(e => e.level === 'review'), true);

  const ok = calc({ referralAmount: 1000, referralBalance: 3000 });
  check('残りに収まる：確認事項は出ない', ok.exceptions.filter(e => e.level === 'review').length, 0);

  const blank = calc({ referralAmount: 1000, referralBalance: '' });
  check('残りが空欄：確認事項は出ない（未入力は0円ではない）', blank.exceptions.filter(e => e.level === 'review').length, 0);

  const zero = calc({ referralAmount: 1000, referralBalance: 0 });
  check('残りが0円で使おうとした：確認事項が出る', zero.exceptions.some(e => e.level === 'review'), true);

  // 上限：課税対象額を超えない
  const capped = calc({ referralAmount: 10000, details: [{ menuId: 'O002', qty: 1 }] });
  check('上限：引く額は課税対象額（5,500円）まで', capped.referralApplied, 5500);
  check('上限：課税小計・合計は0円（マイナスにならない）', [capped.taxableSubtotal, capped.grandTotal], [0, 0]);
  check('上限：PDF明細の合計＝書類小計', sumRows(capped), capped.documentSubtotal);
  check('上限：確認事項が出る', capped.exceptions.some(e => e.level === 'review'), true);

  // 他の割引とは併用できる
  const combo = calc({ referralAmount: 1000, discountManual: true });
  check('紹介割引＋早期予約：両方引かれた合計', combo.grandTotal, 8702);
  check('紹介割引＋早期予約：どちらも適用される', [combo.autoDiscountApplied > 0, combo.referralApplied > 0], [true, true]);

  // チラシ特典と併用できない
  const withFlyer = calc({ flyerManual: true, referralAmount: 300 });
  check('チラシ500円と紹介300円：大きいチラシが適用され、紹介は付かない', [withFlyer.flyerApplied > 0, withFlyer.referralApplied || 0], [true, 0]);
  const refWins = calc({ flyerManual: true, referralAmount: 1000 });
  check('チラシ500円と紹介1,000円：紹介のみ', [refWins.flyerApplied || 0, refWins.referralApplied > 0], [0, true]);
})();

/* ===================== 5. 端数 ===================== */

console.log('端数（税込額を税抜に戻す）');

(function () {
  // 課税小計の1の位ごとに、チラシ500円・紹介1,000円が合計を何円下げるか
  const priced = function (price) {
    const menus = Object.assign({}, MENUS, { MX: Object.assign({}, MENUS.O002, { menuId: 'MX', unitPrice: price, unitPriceRaw: price }) });
    return Object.assign({}, CTX, { menuMap: menus });
  };
  const flyerDiffs = {};
  const refDiffs = {};
  for (let price = 5000; price < 5010; price++) {
    const ctx = priced(price);
    const base = calc({ details: [{ menuId: 'MX', qty: 1 }, { menuId: 'M001', qty: 1 }] }, ctx);
    const withF = calc({ flyerManual: true, details: [{ menuId: 'MX', qty: 1 }, { menuId: 'M001', qty: 1 }] }, ctx);
    const withR = calc({ referralAmount: 1000, details: [{ menuId: 'MX', qty: 1 }, { menuId: 'M001', qty: 1 }] }, ctx);
    flyerDiffs[base.taxableSubtotal % 10] = base.grandTotal - withF.grandTotal;
    refDiffs[base.taxableSubtotal % 10] = base.grandTotal - withR.grandTotal;
    check('端数：チラシ特典は常に500〜501円下がる（価格' + price + '）', [499, 500, 501].indexOf(base.grandTotal - withF.grandTotal) >= 0 && base.grandTotal - withF.grandTotal >= 500, true);
    check('端数：紹介割引は999〜1,000円下がる（価格' + price + '）', [999, 1000, 1001].indexOf(base.grandTotal - withR.grandTotal) >= 0, true);
  }
  // 1の位ごとの結果を固定する（変わったら金額の見え方が変わるので気づけるように）
  check('端数：チラシ500円の下がり幅（課税小計の1の位 0〜9）', flyerDiffs,
    { 0: 500, 1: 500, 2: 500, 3: 500, 4: 500, 5: 501, 6: 501, 7: 501, 8: 501, 9: 501 });
  check('端数：紹介1,000円の下がり幅（課税小計の1の位 0〜9）', refDiffs,
    { 0: 1000, 1: 1000, 2: 1000, 3: 1000, 4: 999, 5: 1000, 6: 1000, 7: 1000, 8: 1000, 9: 1000 });
})();

/* ===================== 6. 保存済みの額の固定 ===================== */

console.log('保存済みの見積・請求はマスタの額を変えても動かない');

(function () {
  const payload = pl({ flyerManual: true });
  const saved = sandbox.calculateEstimate_(payload, CTX);
  const record = sandbox.buildEstimateRecord_(payload, CTX, saved, 'EST-20260910-0002');

  check('レコード：チラシ特典_手動設定', sandbox.parseBooleanLoose_(record['チラシ特典_手動設定']), true);
  check('レコード：チラシ特典_税込額', record['チラシ特典_税込額'], 500);
  check('レコード：チラシ特典額（税抜）', record['チラシ特典額'], 455);

  const changed = Object.assign({}, CTX, { flyerBenefit: { name: 'チラシ特典', amount: 1000, note: '' } });
  check('マスタを500→1,000円に変えても復元の合計は同じ', sandbox.rebuildCalcFromRecord_(record, changed).grandTotal, saved.grandTotal);
  check('マスタを消しても復元の合計は同じ', sandbox.rebuildCalcFromRecord_(record, CTX_OLD).grandTotal, saved.grandTotal);

  // payload からは額を指定できない
  const sneaky = calc({ flyerManual: true, flyerGross: 99999, flyerAmount: 99999, flyerBenefit: { amount: 99999 } });
  check('画面・API の入力で額は変えられない', sneaky.grandTotal, 10280);

  // 紹介割引の記録
  const rp = pl({ referralAmount: 1000, referralBalance: 3000 });
  const rc = sandbox.calculateEstimate_(rp, CTX);
  const rr = sandbox.buildEstimateRecord_(rp, CTX, rc, 'EST-20260910-0003');
  check('レコード：紹介割引_入力額', rr['紹介割引_入力額'], 1000);
  check('レコード：紹介割引_残り確認', rr['紹介割引_残り確認'], 3000);
  check('紹介割引の往復', sandbox.rebuildCalcFromRecord_(rr, CTX).grandTotal, rc.grandTotal);

  const blankRp = pl({ referralAmount: 1000, referralBalance: '' });
  const blankC = sandbox.calculateEstimate_(blankRp, CTX);
  const blankRec = sandbox.buildEstimateRecord_(blankRp, CTX, blankC, 'EST-20260910-0004');
  const blankBack = sandbox.rebuildCalcFromRecord_(blankRec, CTX);
  check('残り空欄のまま往復しても「確認事項」が増えない',
    blankBack.exceptions.filter(e => e.level === 'review').length, blankC.exceptions.filter(e => e.level === 'review').length);
})();

/* ===================== 7. 請求書 ===================== */

console.log('請求書への引き継ぎ');

(function () {
  const payload = pl({ flyerManual: true, referralAmount: 0 });
  const eCalc = sandbox.calculateEstimate_(payload, CTX);
  const eRec = sandbox.buildEstimateRecord_(payload, CTX, eCalc, 'EST-20260910-0005');

  const flags = sandbox.calcFlagsFromRecord_(eRec);
  const calcPayload = Object.assign({
    projectType: eRec['案件タイプ'], remarks: '', workDate: '2026-09-10', highwayFee: 0,
    adjustments: sandbox.buildInvoiceAdjustments_(eRec, {}), targetTotal: 0,
    details: sandbox.extractDetailsFromRecord_(eRec)
  }, flags);
  const prepared = {
    estimateRecord: eRec, estimateRowNumber: 2, estimateTotal: eCalc.grandTotal,
    calcPayload: calcPayload, calc: sandbox.calculateEstimate_(calcPayload, sandbox.ctxForRecord_(CTX, eRec))
  };
  check('請求：見積と同じ合計（チラシ特典）', prepared.calc.grandTotal, eCalc.grandTotal);

  const invRec = sandbox.buildInvoiceRecord_({ estimateId: 'EST-20260910-0005', staff: '和真' }, CTX, prepared, 'INV-20260930-0001', '');
  check('請求レコード：チラシ特典_手動設定', sandbox.parseBooleanLoose_(invRec['チラシ特典_手動設定']), true);
  check('請求レコード：チラシ特典_税込額', invRec['チラシ特典_税込額'], 500);
  const back = sandbox.rebuildInvoiceCalc_(invRec, Object.assign({}, CTX, { flyerBenefit: { name: 'チラシ特典', amount: 1000, note: '' } }));
  check('請求の再現：マスタの額を変えても同じ合計', back.grandTotal, prepared.calc.grandTotal);
  check('請求の再現：PDF明細が同じ', back.pdfRows, prepared.calc.pdfRows);

  // 紹介割引つきの見積から請求へ
  const rp = pl({ referralAmount: 1000, referralBalance: 2000 });
  const rCalc = sandbox.calculateEstimate_(rp, CTX);
  const rRec = sandbox.buildEstimateRecord_(rp, CTX, rCalc, 'EST-20260910-0006');
  const rFlags = sandbox.calcFlagsFromRecord_(rRec);
  check('請求へ引き継ぐフラグ：紹介割引の入力額', rFlags.referralAmount, 1000);
  check('請求へ引き継ぐフラグ：残り確認', rFlags.referralBalance, 2000);
  const rInvPayload = Object.assign({
    projectType: rRec['案件タイプ'], remarks: '', workDate: '2026-09-10', highwayFee: 0,
    adjustments: [], targetTotal: 0, details: sandbox.extractDetailsFromRecord_(rRec)
  }, rFlags);
  check('請求：紹介割引つきでも見積と同じ合計', sandbox.calculateEstimate_(rInvPayload, CTX).grandTotal, rCalc.grandTotal);
})();

/* ===================== 8. 複製 ===================== */

console.log('複製（二重使用の防止）');

(function () {
  const payload = pl({ flyerManual: true });
  const c = sandbox.calculateEstimate_(payload, CTX);
  const rec = sandbox.buildEstimateRecord_(payload, CTX, c, 'EST-20260910-0007');
  const flags = sandbox.calcFlagsFromRecord_(rec);
  check('保存レコードから取り出すフラグに、チラシ特典が入る', flags.flyerManual, true);

  // 複製の入口（シート読み込みを差し替える）
  const origLoad = sandbox.loadContext_;
  const origSheet = sandbox.getEstimateDataSheet_;
  const origFind = sandbox.findEstimateRecord_;
  const origWithApi = sandbox.withApi_;
  sandbox.loadContext_ = function () { return CTX; };
  sandbox.getEstimateDataSheet_ = function () { return {}; };
  sandbox.findEstimateRecord_ = function () { return { record: Object.assign({}, rec, { '紹介割引_入力額': 1000 }) }; };
  sandbox.withApi_ = function (name, id, fn) { return fn(); };
  sandbox.queueLog_ = function () {};
  let res;
  try {
    res = sandbox.apiLoadEstimateForClone_('EST-20260910-0007');
  } finally {
    sandbox.loadContext_ = origLoad;
    sandbox.getEstimateDataSheet_ = origSheet;
    sandbox.findEstimateRecord_ = origFind;
    sandbox.withApi_ = origWithApi;
  }
  check('複製：チラシ特典は引き継がない', res.payload.flyerManual, false);
  check('複製：紹介割引は引き継がない', [res.payload.referralAmount, res.payload.referralBalance], [0, '']);
  check('複製：引き継がなかった項目を知らせる', res.droppedBenefits, ['チラシ特典', '紹介割引']);
})();

/* ===================== 9. PDF明細のまとめ ===================== */

console.log('PDF明細（16行の上限）');

(function () {
  // 明細14行＋調整2行＝ちょうど16行。ここにチラシ特典・紹介割引の行が足されると16行を超える
  const details = [];
  for (let i = 0; i < 14; i++) details.push({ menuId: i % 2 ? 'O002' : 'M001', qty: 1 });
  const adj = [
    { name: '高所作業費', kind: 'surcharge', mode: 'amount', value: 3000, taxType: '課税' },
    { name: 'お詫び', kind: 'discount', mode: 'amount', value: 300, taxType: '課税' }
  ];
  const none = calc({ details: details, adjustments: adj });
  check('前提：新項目なしで16行ちょうど', none.pdfRows.length, 16);

  [
    ['チラシ特典', { flyerManual: true }],
    ['紹介割引', { referralAmount: 1000 }],
    ['繁忙期＋紹介割引', { referralAmount: 1000, workDate: '2026-05-10' }]
  ].forEach(function (t) {
    const c = calc(Object.assign({ details: details, adjustments: adj }, t[1]));
    check(t[0] + '：16行以内にまとめる', c.pdfRows.length <= 16, true);
    check(t[0] + '：まとめても合計が一致', sumRows(c), c.documentSubtotal);
    check(t[0] + '：まとめても小計＋消費税＝合計', c.documentSubtotal + c.tax, c.grandTotal);
  });
})();

/* ===================== 10. マスタへの追記（adminEnsureDiscountRules） ===================== */

console.log('割引繁忙期マスタへの追記');

(function () {
  const headers = sandbox.getDiscountHeaders_();
  function makeSheet(rows) {
    const grid = [headers.slice()].concat(rows.map(r => r.slice()));
    return {
      grid: grid,
      getLastRow: function () { return grid.length; },
      getRange: function (row, col, numRows, numCols) {
        return {
          getDisplayValues: function () { return grid.slice(row - 1, row - 1 + numRows).map(r => r.slice(col - 1, col - 1 + numCols).map(v => String(v == null ? '' : v))); },
          getValues: function () { return grid.slice(row - 1, row - 1 + numRows).map(r => r.slice(col - 1, col - 1 + numCols)); },
          setValues: function (vals) {
            vals.forEach(function (v, i) { grid[row - 1 + i] = v.slice(); });
          }
        };
      }
    };
  }

  const existing = sandbox.getDefaultDiscountRuleRows_().filter(r => ['EARLY_11', 'FLYER_BENEFIT'].indexOf(r[1]) < 0);
  const sheet = makeSheet(existing);
  let cleared = 0;
  sandbox.getMasterSs_ = function () { return { getSheetByName: function () { return sheet; } }; };
  sandbox.forgetHeaderInfo_ = function () {};
  sandbox.clearContextCache_ = function () { cleared++; };

  const before = sheet.grid.length;
  const msg1 = sandbox.adminEnsureDiscountRules();
  check('追記：2行増える', sheet.grid.length - before, 2);
  check('追記：EARLY_11 と FLYER_BENEFIT が入る', sheet.grid.slice(before).map(r => r[1]).sort(), ['EARLY_11', 'FLYER_BENEFIT']);
  check('追記：キャッシュを消す', cleared, 1);
  check('追記：メッセージに追加が出る', msg1.indexOf('追加') >= 0, true);

  const snapshot = JSON.stringify(sheet.grid);
  const msg2 = sandbox.adminEnsureDiscountRules();
  check('2回目：何も増えない（冪等）', JSON.stringify(sheet.grid), snapshot);
  check('2回目：追加なしと出る', msg2.indexOf('追加なし') >= 0, true);

  // IDが違っても中身が同じなら足さない
  const dupRow = sandbox.getDefaultDiscountRuleRows_().find(r => r[1] === 'EARLY_11').slice();
  dupRow[1] = 'MY_EARLY_NOV';
  const sheet2 = makeSheet(existing.concat([dupRow]));
  sandbox.getMasterSs_ = function () { return { getSheetByName: function () { return sheet2; } }; };
  const b2 = sheet2.grid.length;
  sandbox.adminEnsureDiscountRules();
  check('中身が同じ行が別IDであれば、二重に足さない', sheet2.grid.slice(b2).map(r => r[1]), ['FLYER_BENEFIT']);

  // オーナーが EARLY_08_10 を 8〜11月に直した本番の形（2026-10-07）。EARLY_11 を重ねて足さない
  const widened = existing.map(r => r.slice());
  widened.forEach(r => { if (r[1] === 'EARLY_08_10') { r[5] = 11; r[10] = '8月〜11月：10%'; } });
  const sheet3 = makeSheet(widened);
  sandbox.getMasterSs_ = function () { return { getSheetByName: function () { return sheet3; } }; };
  const b3 = sheet3.grid.length;
  const msg3 = sandbox.adminEnsureDiscountRules();
  check('11月を含む早期予約が既にある：EARLY_11 は足さない（チラシ特典だけ足す）', sheet3.grid.slice(b3).map(r => r[1]), ['FLYER_BENEFIT']);
  check('11月を含む早期予約が既にある：理由がメッセージに出る', msg3.indexOf('11月を含む') >= 0, true);
  const early11 = sheet3.grid.filter(r => r[2] === '早期予約割引' && Number(r[4]) <= 11 && 11 <= Number(r[5]));
  check('11月に効く早期予約の行は1本だけ', early11.length, 1);
  // 無効（FALSE）の行は数えない
  const disabled = existing.map(r => r.slice());
  disabled.forEach(r => { if (r[1] === 'EARLY_08_10') { r[0] = 'FALSE'; r[5] = 11; } });
  const sheet4 = makeSheet(disabled);
  sandbox.getMasterSs_ = function () { return { getSheetByName: function () { return sheet4; } }; };
  const b4 = sheet4.grid.length;
  sandbox.adminEnsureDiscountRules();
  check('11月を含む行が無効なら EARLY_11 を足す', sheet4.grid.slice(b4).map(r => r[1]).sort(), ['EARLY_11', 'FLYER_BENEFIT']);

  // 見出しが想定と違うシートには書かない
  const bad = makeSheet(existing);
  bad.grid[0][3] = '対象外';
  sandbox.getMasterSs_ = function () { return { getSheetByName: function () { return bad; } }; };
  const bl = bad.grid.length;
  let err = '';
  try { sandbox.adminEnsureDiscountRules(); } catch (e) { err = String(e.message); }
  check('見出しが違う：書かずに止まる', [bad.grid.length === bl, err.indexOf('列の並び') >= 0], [true, true]);

  // シートが無い
  sandbox.getMasterSs_ = function () { return { getSheetByName: function () { return null; } }; };
  let err2 = '';
  try { sandbox.adminEnsureDiscountRules(); } catch (e) { err2 = String(e.message); }
  check('シートが無い：案内つきで止まる', err2.indexOf('adminNormalizeDiscountRules') >= 0, true);

  // 追記した行の内容：EARLY_11は8–11月ではなく「11月」の10%
  const e11 = sandbox.getDefaultDiscountRuleRows_().find(r => r[1] === 'EARLY_11');
  check('EARLY_11 の中身（早期予約割引・全体・11月〜11月・10%）', [e11[2], e11[3], e11[4], e11[5], e11[7], e11[8]], ['早期予約割引', '全体', 11, 11, 0.1, '率']);
  const fb = sandbox.getDefaultDiscountRuleRows_().find(r => r[1] === 'FLYER_BENEFIT');
  check('FLYER_BENEFIT の中身（チラシ特典・500円）', [fb[2], fb[7], fb[8]], ['チラシ特典', 500, '金額(税込)']);
})();

/* ===================== 11. 独立レビュー（2026-10-03）で指摘された点 ===================== */

console.log('レビュー指摘の固定（文言・上限・請求の通り道）');

(function () {
  const texts = c => exTexts(c).join(' / ');

  // 行名の額は、実際に引いた額（入力額ではない）
  const ok = calc({ referralAmount: 1000 });
  check('行名：上限に当たらないときは入力額', names(ok).filter(n => n.indexOf('紹介割引') >= 0), ['紹介割引（税込1,000円引き）']);
  check('紹介割引の適用額（税込）が保存される', calc({ referralAmount: 1000 }).referralAppliedGross, 1000);

  const capped = calc({ discountManual: true, referralAmount: 20000 });
  check('上限：他の割引（980円）を引いたあとの残りまでしか引かない', capped.referralApplied, 8820);
  check('上限：合計0円', capped.grandTotal, 0);
  check('上限：行名は実際に引いた額（入力の20,000円ではない）',
    names(capped).filter(n => n.indexOf('紹介割引') >= 0), ['紹介割引（税込' + (9702).toLocaleString('en-US') + '円引き）']);
  check('上限：確認事項の文言', texts(capped).indexOf('課税対象を超える') >= 0, true);
  check('上限：保存される適用額は実額', (() => {
    const pay = pl({ discountManual: true, referralAmount: 20000 });
    const rec = sandbox.buildEstimateRecord_(pay, CTX, sandbox.calculateEstimate_(pay, CTX), 'EST-20260910-0010');
    return [rec['紹介割引_入力額'], rec['紹介割引額'], rec['紹介割引_適用額']];
  })(), [20000, 8820, 9702]);

  // 上限超過の確認事項は「合計0円」の確認事項とは別に出る
  const over = calc({ referralAmount: 1000, referralBalance: 500 });
  check('残り超過：確認事項の文言', over.exceptions.some(e => e.level === 'review' && e.text.indexOf('残り') >= 0), true);

  // 警告（止めない）
  const noBal = calc({ referralAmount: 1000 });
  check('残り未入力：警告が出る', texts(noBal).indexOf('「残り」が未入力') >= 0, true);
  check('残り未入力：止めない（review ではない）', noBal.exceptions.filter(e => e.level === 'review').length, 0);
  check('残りを入れれば未入力の警告は出ない', texts(calc({ referralAmount: 1000, referralBalance: 3000 })).indexOf('未入力') >= 0, false);
  check('1,000円単位でない額：警告が出る', texts(calc({ referralAmount: 1234, referralBalance: 5000 })).indexOf('1,000円単位ではありません') >= 0, true);
  check('1,000円単位なら出ない', texts(calc({ referralAmount: 3000, referralBalance: 5000 })).indexOf('1,000円単位') >= 0, false);
  check('大きな紹介割引（明細小計の30%以上）：警告が出る', texts(calc({ referralAmount: 9000, referralBalance: 9000 })).indexOf('30%以上') >= 0, true);
  check('小さい紹介割引では出ない', texts(calc({ referralAmount: 1000, referralBalance: 9000 })).indexOf('30%以上') >= 0, false);

  // チラシ特典の警告の文言
  const withManual = calc({ flyerManual: true, adjustments: [{ name: 'お詫び', kind: 'discount', mode: 'amount', value: 300, taxType: '課税' }] });
  check('チラシ＋手入力値引き：併用の警告の文言', texts(withManual).indexOf('チラシ特典は他の割引と併用できません。手入力の値引き') >= 0, true);
  const suppress = calc({ flyerManual: true, referralAmount: 300, referralBalance: 300 });
  check('チラシが勝つと、止めた割引を知らせる', texts(suppress).indexOf('併用できないため、紹介割引は適用していません') >= 0, true);
  check('チラシが勝っても紹介割引の保存は0', suppress.referralApplied || 0, 0);

  // 大きな数・非数
  ['Infinity', '1e400', 'NaN', '-5', '１０００'].forEach(function (v) {
    const c = calc({ referralAmount: v });
    check('異常な入力 ' + v + '：金額は変わらない（9,780または10,780）', [10780, 9780].indexOf(c.grandTotal) >= 0, true);
    check('異常な入力 ' + v + '：適用額が有限の数', isFinite(c.referralApplied) && isFinite(c.referralGross), true);
  });
  check('Infinity は0円扱い（引かない）', calc({ referralAmount: 'Infinity' }).grandTotal, 10780);
  check('残りが Infinity なら未入力扱い', calc({ referralAmount: 1000, referralBalance: 'Infinity' }).referralHasBalance, false);

  // 請求：prepareInvoiceCalc_ / buildInvoiceRecord_ を通す
  const origSheet = sandbox.getEstimateDataSheet_;
  const origFind = sandbox.findEstimateRecord_;
  try {
    const flyerRecord = (() => {
      const pay = pl({ flyerManual: true });
      return sandbox.buildEstimateRecord_(pay, CTX, sandbox.calculateEstimate_(pay, CTX), 'EST-20260910-0011');
    })();
    const refRecord = (() => {
      const pay = pl({ referralAmount: 1000, referralBalance: 2000 });
      return sandbox.buildEstimateRecord_(pay, CTX, sandbox.calculateEstimate_(pay, CTX), 'EST-20260910-0012');
    })();

    [['チラシ特典', flyerRecord, 10280, 1000], ['紹介割引', refRecord, 9780, 1000]].forEach(function (t) {
      sandbox.getEstimateDataSheet_ = function () { return {}; };
      sandbox.findEstimateRecord_ = function () { return { record: t[1], rowNumber: 2 }; };
      // マスタのチラシ特典を1,000円に変えたあとでも、請求は保存時の額で作る
      const changed = Object.assign({}, CTX, { flyerBenefit: { name: 'チラシ特典', amount: t[3], note: '' } });
      const prepared = sandbox.prepareInvoiceCalc_({ estimateId: 'x' }, changed);
      check('請求（prepareInvoiceCalc_）' + t[0] + '：見積と同じ合計', prepared.calc.grandTotal, t[2]);
      const rec = sandbox.buildInvoiceRecord_({ estimateId: 'x', staff: '和真' }, changed, prepared, 'INV-20260930-0009', '');
      check('請求レコード' + t[0] + '：合計', rec['合計金額'], t[2]);
      check('請求の作り直し' + t[0] + '：合計', sandbox.rebuildInvoiceCalc_(rec, changed).grandTotal, t[2]);
    });
    sandbox.findEstimateRecord_ = function () { return { record: refRecord, rowNumber: 2 }; };
    const pr = sandbox.prepareInvoiceCalc_({ estimateId: 'x' }, CTX);
    const refInv = sandbox.buildInvoiceRecord_({ estimateId: 'x', staff: '和真' }, CTX, pr, 'INV-20260930-0010', '');
    check('請求レコード：紹介割引_入力額・適用額・残り確認',
      [refInv['紹介割引_入力額'], refInv['紹介割引_適用額'], refInv['紹介割引_残り確認']], [1000, 1000, 2000]);
  } finally {
    sandbox.getEstimateDataSheet_ = origSheet;
    sandbox.findEstimateRecord_ = origFind;
  }
})();

/* ===================== 12. 流入経路「チラシ(OH)」で自動適用（オーナー決定 10/9） ===================== */

console.log('流入経路 チラシ(OH) の自動適用');

(function () {
  const plain = calc({});
  ['チラシ(OH)', 'チラシ（OH）', ' チラシ(oh) ', 'チラシOH'].forEach(function (v) {
    const c = calc({ inflowRoute: v });
    check('流入経路 ' + JSON.stringify(v) + '：チラシ特典が自動で付く', [c.flyerApplied, c.grandTotal], [455, 10280]);
  });
  check('チェックを明示的に外していれば付かない', calc({ inflowRoute: 'チラシ(OH)', flyerManual: false }).grandTotal, plain.grandTotal);
  check('チェックが明示されていれば付く（経路なし）', calc({ flyerManual: true }).grandTotal, 10280);
  ['', null, undefined, 'WEB', 'チラシ', 'Googleマップ', 'チラシ(OH)2'].forEach(function (v) {
    check('流入経路 ' + JSON.stringify(v) + '：何も変わらない', core(calc({ inflowRoute: v })), core(plain));
  });
  check('マスタにチラシ特典が無ければ付かず、警告が出る', (() => {
    const c = calc({ inflowRoute: 'チラシ(OH)' }, CTX_OLD);
    return [c.grandTotal, exTexts(c).length > 0];
  })(), [10780, true]);

  // 他の割引との関係は手動チェックと同じ（大きいほう）
  check('流入経路チラシ＋早期予約980円：早期予約のほうが大きいので、チラシは使わない',
    [calc({ inflowRoute: 'チラシ(OH)', discountManual: true }).flyerApplied || 0, calc({ inflowRoute: 'チラシ(OH)', discountManual: true }).grandTotal], [0, 9702]);

  // 保存→復元（チェックの印が残り、あとでマスタが変わっても同じ）
  const pay = pl({ inflowRoute: 'チラシ(OH)' });
  const saved = sandbox.calculateEstimate_(pay, CTX);
  const rec = sandbox.buildEstimateRecord_(pay, CTX, saved, 'EST-20260910-0020');
  check('保存：流入経路が残る', rec['流入経路'], 'チラシ(OH)');
  check('保存：チラシ特典の印と税込額', [sandbox.parseBooleanLoose_(rec['チラシ特典_手動設定']), rec['チラシ特典_税込額']], [true, 500]);
  check('復元：同じ合計（マスタを1,000円に変えても）',
    sandbox.rebuildCalcFromRecord_(rec, Object.assign({}, CTX, { flyerBenefit: { name: 'チラシ特典', amount: 1000, note: '' } })).grandTotal, saved.grandTotal);
  const none = sandbox.buildEstimateRecord_(pl({}), CTX, sandbox.calculateEstimate_(pl({}), CTX), 'EST-20260910-0021');
  check('経路を使わない見積：流入経路は空欄', none['流入経路'], '');
  check('見積の列に 流入経路 がある', sandbox.getEstimateHeaders_().indexOf('流入経路') >= 0, true);
})();

/* ===================== 結果 ===================== */

console.log('');
if (failures.length) {
  console.error('失敗 ' + failures.length + ' 件 / 成功 ' + pass + ' 件');
  failures.forEach(f => console.error('  × ' + f));
  process.exit(1);
}
console.log('discount-2026-10-test: ' + pass + ' 件すべて通過');
