#!/usr/bin/env node
/**
 * code.gs の保存レコード往復テスト
 *
 *   node apps/estimate-app/tools/record-roundtrip-test.js
 *
 * 見積を保存したときの金額と、PDF・メール本文を作るときに
 * 保存レコードから復元した金額が一致することを確認する。
 * ここがずれると「画面の合計とPDFの合計が違う」という一番まずい不具合になる。
 *
 * code.gs をそのまま評価するので、テスト用の再実装はしていない。
 * Google側のAPIだけ最小限スタブする。
 */
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const srcDir = path.join(__dirname, '..', 'src');

/* ===================== Google Apps Script のスタブ ===================== */

function pad(n, len) { return String(n).padStart(len || 2, '0'); }

const sandbox = {
  console: console,
  JSON: JSON,
  Math: Math,
  Date: Date,
  Number: Number,
  String: String,
  Object: Object,
  Array: Array,
  isNaN: isNaN,
  isFinite: isFinite,

  HtmlService: {
    createHtmlOutputFromFile: function (name) {
      return {
        getContent: function () {
          return fs.readFileSync(path.join(srcDir, name + '.html'), 'utf8');
        }
      };
    }
  },

  Utilities: {
    formatDate: function (date, tz, pattern) {
      const d = date instanceof Date ? date : new Date(date);
      return pattern
        .replace('yyyy', d.getFullYear())
        .replace('MM', pad(d.getMonth() + 1))
        .replace('dd', pad(d.getDate()))
        .replace('HH', pad(d.getHours()))
        .replace('mm', pad(d.getMinutes()))
        .replace('ss', pad(d.getSeconds()));
    }
  },

  Session: {
    getActiveUser: function () { return { getEmail: function () { return 'test@example.com'; } }; },
    getEffectiveUser: function () { return { getEmail: function () { return 'test@example.com'; } }; }
  }
};

vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(path.join(srcDir, 'code.gs'), 'utf8'), sandbox, { filename: 'code.gs' });

/* ===================== テスト用コンテキスト ===================== */

const MENUS = {
  M001: { menuId: 'M001', name: 'エアコンクリーニング（ノーマルエアコン）', menuType: 'メイン', rawMenuType: 'メイン', category: 'エアコン', unitPrice: 9800, unitPriceRaw: 9800, taxType: '課税', unit: '台', busyTarget: true, busySurchargeRaw: 3300, discountTarget: true, multipleDiscountTarget: true, invoiceReusable: true, note: '', requireCheck: '' },
  M002: { menuId: 'M002', name: 'エアコンクリーニング（お掃除機能付きエアコン）', menuType: 'メイン', rawMenuType: 'メイン', category: 'エアコン', unitPrice: 15800, unitPriceRaw: 15800, taxType: '課税', unit: '台', busyTarget: true, busySurchargeRaw: 3300, discountTarget: true, multipleDiscountTarget: true, invoiceReusable: true, note: '', requireCheck: '' },
  O002: { menuId: 'O002', name: '室外機セット', menuType: 'オプション', rawMenuType: 'オプション', category: 'エアコン', unitPrice: 5500, unitPriceRaw: 5500, taxType: '課税', unit: '台', busyTarget: false, busySurchargeRaw: '', discountTarget: false, multipleDiscountTarget: false, invoiceReusable: true, note: '', requireCheck: '' }
};

const RULES = [
  { ruleType: '繁忙期', target: '全体', startMonth: 5, endMonth: 7, condition: '', value: 3300, valueType: '金額', priority: 10 },
  { ruleType: '早期予約割引', target: '全体', startMonth: 1, endMonth: 2, condition: '', value: 0.15, valueType: '率', priority: 20 },
  { ruleType: '複数台割引', target: 'ノーマルエアコン', startMonth: '', endMonth: '', condition: 'totalQty:5-10', value: 500, valueType: '金額/台', priority: 30 }
];

const CTX = {
  settings: {
    会社名: 'ワンヒッター株式会社',
    固定CC: 'info@one-hitter.her.jp',
    送信元メール: 'info@one-hitter.her.jp',
    駐車場代注記: '駐車場代が発生した場合は別途ご請求いたします。'
  },
  taxRate: 0.10,
  busySurcharge: 3300,
  busySurchargeUnit: '数量ごと',
  autoDiscountEnabled: true,
  largeDiscountRatio: 0.30,
  menuMap: MENUS,
  discountRules: RULES,
  submitTargets: [
    { projectType: '自社', submitToName: '自社', addresseeName: '', to: '', cc: 'info@one-hitter.her.jp', from: 'info@one-hitter.her.jp', templateType: '自社案件_見積送付' }
  ]
};

/* ===================== テスト ===================== */

let pass = 0;
const failures = [];

function check(name, actual, expected) {
  const a = JSON.stringify(actual);
  const e = JSON.stringify(expected);
  if (a === e) { pass++; return; }
  failures.push(`${name}\n    期待: ${e}\n    実際: ${a}`);
}

/** 保存 → 復元を1往復させ、金額とPDF明細が変わらないことを確認する。 */
function roundTrip(label, payload) {
  const saved = sandbox.calculateEstimate_(payload, CTX);
  const record = sandbox.buildEstimateRecord_(payload, CTX, saved, 'EST-20261120-0001');
  const restored = sandbox.rebuildCalcFromRecord_(record, CTX);

  check(label + '：合計金額', restored.grandTotal, saved.grandTotal);
  check(label + '：課税小計', restored.taxableSubtotal, saved.taxableSubtotal);
  check(label + '：消費税', restored.tax, saved.tax);
  check(label + '：書類小計', restored.documentSubtotal, saved.documentSubtotal);
  check(label + '：PDF明細', restored.pdfRows, saved.pdfRows);

  // 保存レコード自体の整合も見る
  check(label + '：レコードの合計金額', record['合計金額'], saved.grandTotal);

  return { saved: saved, record: record, restored: restored };
}

console.log('\n保存レコードの往復（code.gs の実関数を使用）');

roundTrip('通常見積', {
  projectType: '自社', customerName: 'テスト太郎', projectName: 'エアコン',
  workDate: '2026-11-20', staff: '和真',
  details: [{ menuId: 'M001', qty: 2 }, { menuId: 'O002', qty: 2 }]
});

roundTrip('繁忙期あり', {
  projectType: '自社', customerName: 'テスト太郎', workDate: '2026-05-20',
  details: [{ menuId: 'M001', qty: 3 }]
});

roundTrip('自動割引あり', {
  projectType: '自社', customerName: 'テスト太郎', workDate: '2026-01-20',
  details: [{ menuId: 'M001', qty: 5 }]
});

roundTrip('明細値引きあり', {
  projectType: '自社', customerName: 'テスト太郎', workDate: '2026-11-20',
  details: [
    { menuId: 'M001', qty: 3, lineDiscountMode: 'rate', lineDiscountValue: 10 },
    { menuId: 'M002', qty: 1, lineDiscountMode: 'amount', lineDiscountValue: 1500 }
  ]
});

roundTrip('調整行あり', {
  projectType: '自社', customerName: 'テスト太郎', workDate: '2026-11-20',
  highwayFee: 2500,
  details: [{ menuId: 'M001', qty: 2 }],
  adjustments: [
    { name: '初回サービス割引', kind: 'discount', mode: 'amount', value: 3000, taxType: '課税' },
    { name: '高所作業費', kind: 'surcharge', mode: 'amount', value: 5000, taxType: '課税' }
  ]
});

const target = roundTrip('合計指定あり', {
  projectType: '自社', customerName: 'テスト太郎', workDate: '2026-05-20',
  details: [{ menuId: 'M001', qty: 4 }, { menuId: 'O002', qty: 4 }],
  adjustments: [{ name: 'ご紹介割引', kind: 'discount', mode: 'rate', value: 5, taxType: '課税' }],
  targetTotal: 80000
});

check('合計指定：指定額ちょうどになる', target.saved.grandTotal, 80000);
check('合計指定：復元後も指定額のまま', target.restored.grandTotal, 80000);

/* ===================== 保存レコードの中身 ===================== */

console.log('保存レコードの列');

const sample = roundTrip('列確認用', {
  projectType: '自社', customerName: 'テスト太郎', workDate: '2026-11-20',
  details: [{ menuId: 'M001', qty: 2, lineDiscountMode: 'amount', lineDiscountValue: 800 }],
  adjustments: [{ name: '初回サービス割引', kind: 'discount', mode: 'amount', value: 1200, taxType: '課税' }]
}).record;

check('明細01_値引き額が入る', sample['明細01_値引き額'], 800);
check('明細値引き合計が入る', sample['明細値引き合計'], 800);
check('調整01_名称が入る', sample['調整01_名称'], '初回サービス割引');
check('調整01_金額はマイナス表記', sample['調整01_金額'], -1200);
check('調整合計額が入る', sample['調整合計額'], -1200);
check('要代表者確認はFALSE（手動値引きだけでは代表者確認にしない）', sample['要代表者確認'], 'FALSE');
check('例外フラグはTRUE（アラートは出す）', sample['例外フラグ'], 'TRUE');
check('調整_JSONが復元可能', JSON.parse(sample['調整_JSON']).length, 1);

/* ===================== ヘッダー定義 ===================== */

console.log('ヘッダー定義');

const headers = sandbox.getEstimateHeaders_();
check('ヘッダーに重複がない', headers.length, new Set(headers).size);
check('既存の先頭列が動いていない', headers.slice(0, 5),
  ['estimate_id', 'original_estimate_id', 'invoice_id', 'invoice_source_flag', 'project_status']);
check('内部メモの位置が従来どおり（追加列より前）',
  headers.indexOf('内部メモ') < headers.indexOf('要代表者確認'), true);

const recordKeys = Object.keys(sample);
const unknown = recordKeys.filter(k => headers.indexOf(k) < 0);
check('保存レコードの全キーがヘッダーに存在する', unknown, []);

/* ===================== 結果 ===================== */

console.log('');
if (failures.length === 0) {
  console.log(`✅ 全 ${pass} ケース合格`);
  process.exit(0);
}

console.log(`❌ ${failures.length} 件失敗 / ${pass} 件合格\n`);
failures.forEach(f => console.log('  ✗ ' + f + '\n'));
process.exit(1);
