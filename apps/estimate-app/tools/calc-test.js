#!/usr/bin/env node
/**
 * CalcEngine 固定ケーステスト（06_受入テスト.md の C / D 項目に対応）
 *
 *   node apps/estimate-app/tools/calc-test.js
 *
 * src/Calc.html をそのまま読み込んで評価するので、
 * 本番にデプロイするコードと同一のロジックを検証している。
 */
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const calcPath = path.join(__dirname, '..', 'src', 'Calc.html');
const src = fs.readFileSync(calcPath, 'utf8')
  .replace(/<script[^>]*>/gi, '')
  .replace(/<\/script>/gi, '');

const sandbox = {};
vm.createContext(sandbox);
vm.runInContext(src, sandbox, { filename: 'Calc.html' });
const CalcEngine = sandbox.CalcEngine;

/* ===================== テスト用マスタ ===================== */

const MENUS = {
  M001: { name: 'エアコンクリーニング（ノーマルエアコン）', menuType: 'メイン', rawMenuType: 'メイン', category: 'エアコン', unitPrice: 9800, unitPriceRaw: 9800, taxType: '課税', unit: '台', busyTarget: true, busySurchargeRaw: 3300, discountTarget: true, multipleDiscountTarget: true, invoiceReusable: true, note: '', requireCheck: '' },
  M002: { name: 'エアコンクリーニング（お掃除機能付きエアコン）', menuType: 'メイン', rawMenuType: 'メイン', category: 'エアコン', unitPrice: 15800, unitPriceRaw: 15800, taxType: '課税', unit: '台', busyTarget: true, busySurchargeRaw: 3300, discountTarget: true, multipleDiscountTarget: true, invoiceReusable: true, note: '', requireCheck: '' },
  M014: { name: '業務用エアコンクリーニング', menuType: 'メイン', rawMenuType: 'メイン', category: '業務用エアコン', unitPrice: 29800, unitPriceRaw: 29800, taxType: '課税', unit: '台', busyTarget: true, busySurchargeRaw: 3300, discountTarget: true, multipleDiscountTarget: true, invoiceReusable: true, note: '', requireCheck: '24,800円〜（2台以上）要確認' },
  M015: { name: '空室清掃', menuType: 'メイン', rawMenuType: 'メイン', category: '空室清掃', unitPrice: 52800, unitPriceRaw: 52800, taxType: '課税', unit: '件', busyTarget: true, busySurchargeRaw: '30%', discountTarget: true, multipleDiscountTarget: false, invoiceReusable: true, note: '', requireCheck: '' },
  O002: { name: '室外機セット', menuType: 'オプション', rawMenuType: 'オプション', category: 'エアコン', unitPrice: 5500, unitPriceRaw: 5500, taxType: '課税', unit: '台', busyTarget: false, busySurchargeRaw: '', discountTarget: false, multipleDiscountTarget: false, invoiceReusable: true, note: '', requireCheck: '' },
  O017: { name: 'カバー光沢仕上げ', menuType: 'オプション', rawMenuType: 'オプション', category: 'レンジフード', unitPrice: 0, unitPriceRaw: '', taxType: '課税', unit: '箇所', busyTarget: false, busySurchargeRaw: '', discountTarget: false, multipleDiscountTarget: false, invoiceReusable: true, note: '', requireCheck: '' }
};

const RULES = [
  { ruleType: '繁忙期', target: '全体', startMonth: 5, endMonth: 7, condition: '', value: 3300, valueType: '金額', priority: 10 },
  { ruleType: '繁忙期', target: '全体', startMonth: 12, endMonth: 12, condition: '', value: 3300, valueType: '金額', priority: 10 },
  { ruleType: '早期予約割引', target: '全体', startMonth: 1, endMonth: 2, condition: '', value: 0.15, valueType: '率', priority: 20 },
  { ruleType: '早期予約割引', target: '全体', startMonth: 3, endMonth: 4, condition: '', value: 0.10, valueType: '率', priority: 20 },
  { ruleType: '早期予約割引', target: '全体', startMonth: 8, endMonth: 10, condition: '', value: 0.10, valueType: '率', priority: 20 },
  { ruleType: '複数台割引', target: 'ノーマルエアコン', startMonth: '', endMonth: '', condition: 'totalQty:5-10', value: 500, valueType: '金額/台', priority: 30 },
  { ruleType: '複数台割引', target: 'ノーマルエアコン', startMonth: '', endMonth: '', condition: 'totalQty:11-20', value: 1000, valueType: '金額/台', priority: 30 },
  { ruleType: '複数台割引', target: 'ノーマルエアコン', startMonth: '', endMonth: '', condition: 'totalQty:21-50', value: 1500, valueType: '金額/台', priority: 30 },
  { ruleType: '複数台割引', target: 'ロボ付きエアコン', startMonth: '', endMonth: '', condition: 'totalQty:5-10', value: 1000, valueType: '金額/台', priority: 30 },
  { ruleType: '複数台割引', target: 'ロボ付きエアコン', startMonth: '', endMonth: '', condition: 'totalQty:11-20', value: 1500, valueType: '金額/台', priority: 30 },
  { ruleType: '複数台割引', target: 'ロボ付きエアコン', startMonth: '', endMonth: '', condition: 'totalQty:21-50', value: 2000, valueType: '金額/台', priority: 30 },
  { ruleType: '複数台割引', target: '業務用エアコン', startMonth: '', endMonth: '', condition: 'totalQty:2-10', value: 5000, valueType: '金額/台', priority: 30 },
  { ruleType: '複数台割引', target: '業務用エアコン', startMonth: '', endMonth: '', condition: 'totalQty:11-20', value: 6000, valueType: '金額/台', priority: 30 },
  { ruleType: '複数台割引', target: '業務用エアコン', startMonth: '', endMonth: '', condition: 'totalQty:21-50', value: 7000, valueType: '金額/台', priority: 30 }
];

function ctx(overrides) {
  return Object.assign({
    taxRate: 0.10,
    busySurcharge: 3300,
    busySurchargeUnit: '数量ごと',
    autoDiscountEnabled: false,
    largeDiscountRatio: 0.30,
    menuMap: MENUS,
    discountRules: RULES
  }, overrides || {});
}

function run(payload, ctxOverrides) {
  return CalcEngine.calculate(payload, ctx(ctxOverrides));
}

/* ===================== テストランナー ===================== */

let pass = 0;
const failures = [];

function check(name, actual, expected) {
  const a = JSON.stringify(actual);
  const e = JSON.stringify(expected);
  if (a === e) { pass++; return; }
  failures.push(`${name}\n    期待: ${e}\n    実際: ${a}`);
}

function group(title) { console.log('\n' + title); }

/* ===================== C. 繁忙期 ===================== */

group('C. 繁忙期');

check('C-1 5月メイン1台 → 3,300加算',
  run({ workDate: '2026-05-20', details: [{ menuId: 'M001', qty: 1 }] }).busyAmount, 3300);

check('C-2 7月メイン20台 → 数量20×3,300',
  run({ workDate: '2026-07-10', details: [{ menuId: 'M001', qty: 20 }] }).busyAmount, 66000);

check('C-2b PDF繁忙期行 数量20/単価3,300/金額66,000', (() => {
  const r = run({ workDate: '2026-07-10', details: [{ menuId: 'M001', qty: 20 }] });
  const row = r.pdfRows.find(x => x.name === '繁忙期加算');
  return [row.qty, row.unitPrice, row.amount];
})(), [20, 3300, 66000]);

check('C-3 12月は対象',
  run({ workDate: '2026-12-05', details: [{ menuId: 'M001', qty: 1 }] }).busyAuto, true);

check('C-4 8月は対象外',
  run({ workDate: '2026-08-05', details: [{ menuId: 'M001', qty: 1 }] }).busyAuto, false);

check('C-5 オプションのみ → 繁忙期0',
  run({ workDate: '2026-05-20', details: [{ menuId: 'O002', qty: 3 }] }).busyAmount, 0);

check('C-6 メイン+オプション → メイン数量のみ加算',
  run({ workDate: '2026-05-20', details: [{ menuId: 'M001', qty: 2 }, { menuId: 'O002', qty: 5 }] }).busyAmount, 6600);

check('C-7 法人案件で対象6台 → 割増なし',
  run({ workDate: '2026-05-20', projectType: '法人', details: [{ menuId: 'M001', qty: 6 }] }).busyAuto, false);

check('C-8 法人案件で対象5台 → 割増あり',
  run({ workDate: '2026-05-20', projectType: '法人', details: [{ menuId: 'M001', qty: 5 }] }).busyAuto, true);

check('C-9 空室清掃30% → 52,800×30%',
  run({ workDate: '2026-05-20', details: [{ menuId: 'M015', qty: 1 }] }).busyAmount, 15840);

/* ===================== D. 自動割引 ===================== */

group('D. 自動割引');

const AUTO = { autoDiscountEnabled: true };

check('D-1 1月 早期予約15%',
  run({ workDate: '2026-01-20', details: [{ menuId: 'M001', qty: 1 }] }, AUTO).autoDiscountApplied, 1470);

check('D-2 3月 早期予約10%',
  run({ workDate: '2026-03-20', details: [{ menuId: 'M001', qty: 1 }] }, AUTO).autoDiscountApplied, 980);

check('D-3 9月 早期予約10%',
  run({ workDate: '2026-09-20', details: [{ menuId: 'M001', qty: 1 }] }, AUTO).autoDiscountApplied, 980);

check('D-4 11月 早期予約なし・台数2未満 → 0',
  run({ workDate: '2026-11-20', details: [{ menuId: 'M001', qty: 1 }] }, AUTO).autoDiscountApplied, 0);

check('D-5 11月 ノーマル5台 → 500×5',
  run({ workDate: '2026-11-20', details: [{ menuId: 'M001', qty: 5 }] }, AUTO).autoDiscountApplied, 2500);

check('D-6 11月 ノーマル11台 → 1,000×11',
  run({ workDate: '2026-11-20', details: [{ menuId: 'M001', qty: 11 }] }, AUTO).autoDiscountApplied, 11000);

check('D-7 11月 ロボ5台 → 1,000×5',
  run({ workDate: '2026-11-20', details: [{ menuId: 'M002', qty: 5 }] }, AUTO).autoDiscountApplied, 5000);

check('D-8 11月 業務用2台 → 5,000×2',
  run({ workDate: '2026-11-20', details: [{ menuId: 'M014', qty: 2 }] }, AUTO).autoDiscountApplied, 10000);

check('D-9 混在6台は総台数で判定しメニューごとの単価を適用（ノーマル3+ロボ3 → 500×3+1,000×3）',
  run({ workDate: '2026-11-20', details: [{ menuId: 'M001', qty: 3 }, { menuId: 'M002', qty: 3 }] }, AUTO).autoDiscountApplied, 4500);

check('D-10 早期予約と複数台の併用時は早期予約のみ',
  run({ workDate: '2026-01-20', details: [{ menuId: 'M001', qty: 10 }] }, AUTO).autoDiscountType, '早期予約割引');

check('D-11 50台超は例外表示',
  run({ workDate: '2026-11-20', details: [{ menuId: 'M001', qty: 51 }] }, AUTO)
    .exceptionReasons.some(t => t.indexOf('50台') >= 0), true);

check('D-12 設定OFFなら自動割引は載らない',
  run({ workDate: '2026-01-20', details: [{ menuId: 'M001', qty: 1 }] }).autoDiscountApplied, 0);

check('D-13 設定OFFでも候補金額は算出して画面に出せる',
  run({ workDate: '2026-01-20', details: [{ menuId: 'M001', qty: 1 }] }).autoDiscountCandidate, 1470);

check('D-14 設定OFF＋現場が手動ON → 適用される',
  run({ workDate: '2026-01-20', discountManual: true, details: [{ menuId: 'M001', qty: 1 }] }).autoDiscountApplied, 1470);

/* ===================== 変則割引 ===================== */

group('変則割引（今回追加）');

check('X-1 定額の調整行：9,800 → 5,000引き', (() => {
  const r = run({
    workDate: '2026-11-20',
    details: [{ menuId: 'M001', qty: 1 }],
    adjustments: [{ name: '初回サービス割引', kind: 'discount', mode: 'amount', value: 5000, taxType: '課税' }]
  });
  return [r.taxableSubtotal, r.tax, r.grandTotal];
})(), [4800, 480, 5280]);

check('X-2 率の調整行：課税対象計の10%',
  run({
    workDate: '2026-11-20',
    details: [{ menuId: 'M001', qty: 10 }],
    adjustments: [{ name: 'ご紹介割引', kind: 'discount', mode: 'rate', value: 10, base: 'taxable', taxType: '課税' }]
  }).appliedAdjustments[0].amount, 9800);

check('X-3 割増もできる（追加作業費）',
  run({
    workDate: '2026-11-20',
    details: [{ menuId: 'M001', qty: 1 }],
    adjustments: [{ name: '高所作業費', kind: 'surcharge', mode: 'amount', value: 3000, taxType: '課税' }]
  }).grandTotal, 14080);

check('X-4 明細ごとの定額値引き', (() => {
  const r = run({
    workDate: '2026-11-20',
    details: [{ menuId: 'M001', qty: 2, lineDiscountMode: 'amount', lineDiscountValue: 2000 }]
  });
  return [r.lineGrossSubtotal, r.lineDiscountTotal, r.lineSubtotal, r.grandTotal];
})(), [19600, 2000, 17600, 19360]);

check('X-5 明細ごとの率値引き（10%）',
  run({
    workDate: '2026-11-20',
    details: [{ menuId: 'M001', qty: 2, lineDiscountMode: 'rate', lineDiscountValue: 10 }]
  }).lineDiscountTotal, 1960);

check('X-6 明細値引きはPDFで独立行になり単価×数量=金額が崩れない', (() => {
  const r = run({
    workDate: '2026-11-20',
    details: [{ menuId: 'M001', qty: 2, lineDiscountMode: 'amount', lineDiscountValue: 2000 }]
  });
  return r.pdfRows.map(x => [x.name, x.qty, x.unitPrice, x.amount]);
})(), [
  ['エアコンクリーニング（ノーマルエアコン）', 2, 9800, 19600],
  ['エアコンクリーニング（ノーマルエアコン） 値引き', 1, -2000, -2000]
]);

check('X-7 明細金額を超える値引きは切り詰める',
  run({
    workDate: '2026-11-20',
    details: [{ menuId: 'M001', qty: 1, lineDiscountMode: 'amount', lineDiscountValue: 99999 }]
  }).lineDiscountTotal, 9800);

check('X-8 合計を指定額ちょうどに合わせる（高速代なし）', (() => {
  const r = run({
    workDate: '2026-11-20',
    details: [{ menuId: 'M001', qty: 1 }],
    targetTotal: 10000
  });
  return [r.grandTotal, r.appliedAdjustments.length, r.appliedAdjustments[0].name];
})(), [10000, 1, '端数調整']);

check('X-9 合計指定は端数なしで一発で着地する（10台ケース）',
  run({ workDate: '2026-11-20', details: [{ menuId: 'M001', qty: 10 }], targetTotal: 100000 }).grandTotal, 100000);

check('X-10 合計指定で切り上げ（割増方向）もできる',
  run({ workDate: '2026-11-20', details: [{ menuId: 'M001', qty: 1 }], targetTotal: 12000 }).grandTotal, 12000);

check('X-11 手動値引きは例外アラートに出るが代表者確認は求めない', (() => {
  const r = run({
    workDate: '2026-11-20',
    details: [{ menuId: 'M001', qty: 1 }],
    adjustments: [{ name: '初回サービス割引', kind: 'discount', mode: 'amount', value: 1000, taxType: '課税' }]
  });
  return [r.exceptionFlag, r.reviewFlag];
})(), [true, false]);

check('X-12 単価未設定は代表者確認レベル', (() => {
  const r = run({ workDate: '2026-11-20', details: [{ menuId: 'O017', qty: 1 }] });
  return r.reviewFlag;
})(), true);

check('X-13 明細小計の30%以上の手動値引きは警告',
  run({
    workDate: '2026-11-20',
    details: [{ menuId: 'M001', qty: 1 }],
    adjustments: [{ name: '大幅値引き', kind: 'discount', mode: 'amount', value: 3000, taxType: '課税' }]
  }).exceptionReasons.some(t => t.indexOf('30%以上') >= 0), true);

check('X-14 課税値引きは課税対象を超えて引かない（消費税がマイナスにならない）', (() => {
  const r = run({
    workDate: '2026-11-20',
    details: [{ menuId: 'M001', qty: 1 }],
    adjustments: [{ name: '過大値引き', kind: 'discount', mode: 'amount', value: 50000, taxType: '課税' }]
  });
  return [r.taxableSubtotal, r.tax, r.grandTotal];
})(), [0, 0, 0]);

check('X-15 調整行が複数でPDF16行を超えるとまとめ行に畳む', (() => {
  const details = [];
  for (let i = 0; i < 14; i++) details.push({ menuId: 'M001', qty: 1 });
  const r = run({
    workDate: '2026-11-20',
    details,
    adjustments: [
      { name: '値引きA', kind: 'discount', mode: 'amount', value: 100, taxType: '課税' },
      { name: '値引きB', kind: 'discount', mode: 'amount', value: 200, taxType: '課税' },
      { name: '値引きC', kind: 'discount', mode: 'amount', value: 300, taxType: '課税' }
    ]
  });
  return [r.adjustmentsCollapsed, r.pdfRows.length, r.pdfRows[r.pdfRows.length - 1].name];
})(), [true, 15, '各種割引・調整']);

/* ===================== B. 通常見積 / 税 ===================== */

group('B. 通常見積・税');

check('B-1 メイン単価×数量',
  run({ workDate: '2026-11-20', details: [{ menuId: 'M001', qty: 3 }] }).lineSubtotal, 29400);

check('B-2 高速代は非課税で税に含めない', (() => {
  const r = run({ workDate: '2026-11-20', highwayFee: 3000, details: [{ menuId: 'M001', qty: 1 }] });
  return [r.taxableSubtotal, r.nonTaxableSubtotal, r.tax, r.grandTotal];
})(), [9800, 3000, 980, 13780]);

check('B-3 小計＋消費税＝合計 が常に成り立つ', (() => {
  const r = run({
    workDate: '2026-05-20',
    highwayFee: 2000,
    details: [
      { menuId: 'M001', qty: 3, lineDiscountMode: 'amount', lineDiscountValue: 500 },
      { menuId: 'O002', qty: 2 }
    ],
    adjustments: [{ name: 'ご紹介割引', kind: 'discount', mode: 'rate', value: 5, taxType: '課税' }]
  });
  return r.documentSubtotal + r.tax === r.grandTotal;
})(), true);

check('B-4 PDF明細の合計＝書類小計', (() => {
  const r = run({
    workDate: '2026-05-20',
    highwayFee: 2000,
    details: [
      { menuId: 'M001', qty: 3, lineDiscountMode: 'amount', lineDiscountValue: 500 },
      { menuId: 'O002', qty: 2 }
    ],
    adjustments: [{ name: 'ご紹介割引', kind: 'discount', mode: 'amount', value: 1000, taxType: '課税' }]
  });
  const sum = r.pdfRows.reduce((s, x) => s + x.amount, 0);
  return sum === r.documentSubtotal;
})(), true);

check('B-5 タイムゾーンに関係なく作業予定日の月で判定する',
  CalcEngine.monthOf('2026-05-01'), 5);

/* ===================== 保存 → 復元の往復 ===================== */

group('保存レコードからの復元（PDF・メール本文で使う）');

check('R-1 端数調整つきの見積を保存後に復元しても合計が変わらない', (() => {
  const original = run({
    workDate: '2026-11-20',
    highwayFee: 1500,
    details: [{ menuId: 'M001', qty: 2, lineDiscountMode: 'rate', lineDiscountValue: 10 }],
    adjustments: [{ name: 'ご紹介割引', kind: 'discount', mode: 'amount', value: 1000, taxType: '課税' }],
    targetTotal: 18000
  });

  // code.gs の rebuildCalcFromRecord_ と同じ復元をする：
  // 保存された調整行をそのまま渡し、targetTotal は再逆算しない。
  const restored = run({
    workDate: '2026-11-20',
    highwayFee: 1500,
    details: [{ menuId: 'M001', qty: 2, lineDiscountMode: 'amount', lineDiscountValue: original.lines[0].lineDiscount }],
    adjustments: original.appliedAdjustments,
    targetTotal: 0
  });

  return [original.grandTotal, restored.grandTotal, original.grandTotal === restored.grandTotal];
})(), [18000, 18000, true]);

check('R-2 復元してもPDF明細行が一致する', (() => {
  const payload = {
    workDate: '2026-05-20',
    details: [{ menuId: 'M001', qty: 3 }, { menuId: 'O002', qty: 1 }],
    adjustments: [{ name: '初回サービス割引', kind: 'discount', mode: 'rate', value: 5, taxType: '課税' }]
  };
  const a = run(payload);
  const b = run({ workDate: payload.workDate, details: payload.details, adjustments: a.appliedAdjustments });
  return JSON.stringify(a.pdfRows) === JSON.stringify(b.pdfRows);
})(), true);

/* ===================== 結果 ===================== */

console.log('');
if (failures.length === 0) {
  console.log(`✅ 全 ${pass} ケース合格`);
  process.exit(0);
}

console.log(`❌ ${failures.length} 件失敗 / ${pass} 件合格\n`);
failures.forEach(f => console.log('  ✗ ' + f + '\n'));
process.exit(1);
