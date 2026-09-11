#!/usr/bin/env node
/**
 * 予約フォームと見積アプリの金額突き合わせ
 *
 *   node apps/estimate-app/tools/booking-form-parity-test.js
 *
 * お客様が予約フォーム（https://one-hitter-booking.netlify.app/）で見た概算と、
 * あとから現場が出す正式見積の金額がズレると、そのまま信用の問題になる。
 * ズレる条件を機械的に洗い出して、CMOと共有するための道具。
 *
 * 予約フォーム側のロジックは fixtures-booking-form.json に写してある
 * （公開ページから読み取ったもの。仕様変更があれば取り直すこと）。
 * 見積アプリ側は本物の CalcEngine と本番メニューマスタを使う。
 *
 * 2026-09-11、CMO判断（掲示板 20260910-06-cmo）により見積アプリ側を揃えた。
 * 以降このテストは**一致を要求する**。ズレたら失敗する。
 *
 *   Q1 繁忙期加算 ¥3,300 は税込（10%を重ねない）
 *   Q2 同時施工価格を予約フォームと同じ解釈で見積アプリにも入れる
 *   Q3 ネット申込特典 −¥2,200 はページ限定。見積では任意の割引行として足す
 *
 * 見積アプリ側は **WEB経由見積タブ**（channel: 'web'）で計算する。
 * 通常見積タブは改修前の料金のままなので、ここでは比較しない
 * （通常見積が変わっていないことは calc-test.js の C / D / S-0 群で見ている）。
 *
 * 自動割引はONにして比較する。予約フォームは常に早期予約割引を出すため。
 * 参考として、納品時の既定（auto_discount_enabled = FALSE）の金額も併記する。
 * ネット申込特典はWEB経由タブで自動適用されるので、こちら側で足す必要はない。
 */
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const srcDir = path.join(__dirname, '..', 'src');
const master = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures-live-master.json'), 'utf8'));
const form = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures-booking-form.json'), 'utf8'));

/* ===================== 予約フォーム側の計算（写し） ===================== */

function formPrice(basket, month) {
  const items = [];
  basket.forEach(b => {
    const m = form.menus.find(x => x.n === b.name);
    if (!m) throw new Error('予約フォームに無いメニュー：' + b.name);
    for (let i = 0; i < b.qty; i++) items.push(m);
  });

  const n = items.length;
  if (!n) return null;

  const hasKitchen = basket.some(b => b.name === 'キッチンクリーニング' && b.qty > 0);
  const setPrice = m => (m.n === 'コンロクリーニング' && !hasKitchen) ? m.t : m.d;

  const tanpin = items.reduce((s, m) => s + m.t, 0);

  let shoukei;
  if (n === 1) {
    shoukei = items[0].t;
  } else {
    const sorted = items.slice().sort((a, b) => (a.t - setPrice(a)) - (b.t - setPrice(b)));
    shoukei = sorted[0].t;
    for (let i = 1; i < sorted.length; i++) shoukei += setPrice(sorted[i]);
  }

  const setBiki = tanpin - shoukei;
  const ritsu = (n === 1 && month) ? (form.souki[String(month)] || 0) : 0;
  const waribiki = Math.round(shoukei * ritsu);
  const netto = (n >= 2 && setBiki === 0) ? form.netTokuten : 0;
  const kasan = (month && form.hanbouki.tsuki.indexOf(month) >= 0) ? form.hanbouki.gaku * n : 0;

  return {
    kasho: n, tanpin, shoukei, setBiki, waribiki, netto, kasan,
    total: shoukei - waribiki - netto + kasan   // 税込
  };
}

/* ===================== 見積アプリ側（本物のエンジン＋本番マスタ） ===================== */

function pad(x) { return String(x).padStart(2, '0'); }

const sandbox = {
  console: { log() {}, warn() {}, error() {} },
  JSON, Math, Date, Number, String, Object, Array, isNaN, isFinite, RegExp,
  HtmlService: {
    createHtmlOutputFromFile: name => ({
      getContent: () => fs.readFileSync(path.join(srcDir, name + '.html'), 'utf8')
    })
  },
  Utilities: {
    formatDate(d, tz, p) {
      const x = d instanceof Date ? d : new Date(d);
      return p.replace('yyyy', x.getFullYear()).replace('MM', pad(x.getMonth() + 1))
        .replace('dd', pad(x.getDate())).replace('HH', pad(x.getHours()))
        .replace('mm', pad(x.getMinutes())).replace('ss', pad(x.getSeconds()));
    }
  },
  Session: {
    getActiveUser: () => ({ getEmail: () => 't@example.com' }),
    getEffectiveUser: () => ({ getEmail: () => 't@example.com' })
  }
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(path.join(srcDir, 'code.gs'), 'utf8'), sandbox, { filename: 'code.gs' });

const engine = sandbox.getCalcEngine_();

/** 本番メニューマスタから menuMap を組む */
const menuRows = master.master['メニューマスタ'].rows;
const headers = menuRows[0].map(h => String(h || '').trim());
const col = name => headers.indexOf(name);

const menuMap = {};
const byName = {};
menuRows.slice(1).forEach(r => {
  const id = String(r[col('メニューID')] || '').trim();
  if (!id) return;
  const active = String(r[col('有効')] || '').trim().toUpperCase() !== 'FALSE';
  if (!active) return;

  const name = String(r[col('メニュー名')] || '').trim();
  const m = {
    menuId: id,
    name: String(r[col('顧客表示名')] || name).trim(),
    menuType: id.indexOf('O') === 0 ? 'オプション' : 'メイン',
    rawMenuType: String(r[col('メニュータイプ')] || '').trim(),
    category: String(r[col('カテゴリ')] || '').trim(),
    unitPrice: sandbox.toNumber_(r[col('単価')]),
    unitPriceRaw: r[col('単価')],
    taxType: String(r[col('税区分')] || '課税').trim(),
    unit: String(r[col('数量単位')] || '').trim(),
    busyTarget: String(r[col('繁忙期加算対象')] || '').trim().toUpperCase() === 'TRUE',
    busySurchargeRaw: r[col('繁忙期加算額')] || '',
    discountTarget: String(r[col('割引対象')] || '').trim().toUpperCase() === 'TRUE',
    multipleDiscountTarget: String(r[col('複数台割引対象')] || '').trim().toUpperCase() === 'TRUE',
    note: '', requireCheck: ''
  };
  menuMap[id] = m;
  byName[name] = m;
});

/**
 * 割引繁忙期マスタの正規化後の内容（Admin.gs の adminNormalizeDiscountRules と同じ値）。
 * ここを直したら Admin.gs も直すこと。ズレていないかは下の整合チェックで見ている。
 */
const rules = [
  { ruleType: '繁忙期', target: '全体', startMonth: 5, endMonth: 7, value: 3300, priority: 10 },
  { ruleType: '繁忙期', target: '全体', startMonth: 12, endMonth: 12, value: 3300, priority: 10 },
  { ruleType: '早期予約割引', target: '全体', startMonth: 1, endMonth: 2, value: 0.15, priority: 20 },
  { ruleType: '早期予約割引', target: '全体', startMonth: 3, endMonth: 4, value: 0.10, priority: 20 },
  { ruleType: '早期予約割引', target: '全体', startMonth: 8, endMonth: 10, value: 0.10, priority: 20 },

  { ruleType: '同時施工価格', target: 'M004', condition: '', value: 13800, priority: 40 },
  { ruleType: '同時施工価格', target: 'M006', condition: '', value: 13800, priority: 40 },
  { ruleType: '同時施工価格', target: 'M007', condition: '', value: 13800, priority: 40 },
  { ruleType: '同時施工価格', target: 'M008', condition: '', value: 15100, priority: 40 },
  { ruleType: '同時施工価格', target: 'M009', condition: 'M006', value: 5500, priority: 40 },
  { ruleType: '同時施工価格', target: 'M010', condition: '', value: 6800, priority: 40 },

  { ruleType: 'ネット申込特典', target: 'ネット申込特典', condition: '', value: 2200, priority: 50 }
];

const NET_BENEFIT = { name: 'ネット申込特典', amount: 2200, note: 'このページからのお申し込み特典' };

function appCtx(autoDiscount) {
  return {
    taxRate: 0.10, busySurcharge: 3300, busySurchargeUnit: '数量ごと',
    busySurchargeTaxIncluded: true,
    autoDiscountEnabled: autoDiscount, setPricingEnabled: true,
    largeDiscountRatio: 0.30, netBenefit: NET_BENEFIT,
    menuMap, discountRules: rules
  };
}

function appPrice(basket, month, autoDiscount) {
  const details = basket.map(b => {
    const m = byName[b.appMenu];
    if (!m) throw new Error('メニューマスタに無い：' + b.appMenu);
    return { menuId: m.menuId, qty: b.qty };
  });
  const workDate = '2026-' + pad(month) + '-15';
  return engine.calculate({ channel: 'web', workDate, details }, appCtx(autoDiscount));
}

/** 通常見積タブ（改修前の料金）。変わっていないことの確認用 */
function normalPrice(basket, month) {
  const details = basket.map(b => {
    const m = byName[b.appMenu];
    if (!m) throw new Error('メニューマスタに無い：' + b.appMenu);
    return { menuId: m.menuId, qty: b.qty };
  });
  const workDate = '2026-' + pad(month) + '-15';
  return engine.calculate({ workDate, details }, appCtx(false));
}

/* ===================== 比較 ===================== */

// 予約フォームの名前 → メニューマスタの「メニュー名」
const NAME_MAP = {
  'エアコンクリーニング（ノーマル）': 'ノーマルエアコン',
  'エアコンクリーニング（お掃除機能付き）': 'お掃除機能付きエアコン',
  '洗濯機クリーニング': '洗濯機クリーニング',
  'レンジフードクリーニング': 'レンジフードクリーニング',
  'キッチンクリーニング': 'キッチンクリーニング',
  '浴室クリーニング': '浴室クリーニング',
  'トイレクリーニング': 'トイレクリーニング',
  '洗面台クリーニング': '洗面台クリーニング',
  'コンロクリーニング': 'コンロクリーニング'
};

const CASES = [
  { label: '浴室1（9月・単品）', month: 9, basket: [{ name: '浴室クリーニング', qty: 1 }] },
  { label: '浴室1＋キッチン1（9月）', month: 9, basket: [{ name: '浴室クリーニング', qty: 1 }, { name: 'キッチンクリーニング', qty: 1 }] },
  { label: 'エアコン1（1月・単品）', month: 1, basket: [{ name: 'エアコンクリーニング（ノーマル）', qty: 1 }] },
  { label: 'エアコン2（1月）', month: 1, basket: [{ name: 'エアコンクリーニング（ノーマル）', qty: 2 }] },
  { label: 'エアコン1（6月・繁忙期）', month: 6, basket: [{ name: 'エアコンクリーニング（ノーマル）', qty: 1 }] },
  { label: 'エアコン2（6月・繁忙期）', month: 6, basket: [{ name: 'エアコンクリーニング（ノーマル）', qty: 2 }] },
  { label: '浴室1＋トイレ1（11月）', month: 11, basket: [{ name: '浴室クリーニング', qty: 1 }, { name: 'トイレクリーニング', qty: 1 }] },
  { label: 'キッチン1＋コンロ1（11月）', month: 11, basket: [{ name: 'キッチンクリーニング', qty: 1 }, { name: 'コンロクリーニング', qty: 1 }] },
  { label: '洗濯機1＋トイレ1（11月）', month: 11, basket: [{ name: '洗濯機クリーニング', qty: 1 }, { name: 'トイレクリーニング', qty: 1 }] }
];

const yen = n => '¥' + Math.round(n).toLocaleString('en-US');

/* --- Admin.gs の正規化テーブルとズレていないか --- */

const adminSrc = fs.readFileSync(path.join(srcDir, 'Admin.gs'), 'utf8');
const adminSet = {};
adminSrc.replace(/\['TRUE', 'SET_(\w+)', '同時施工価格', '(\w+)', '', '', '(\w*)', (\d+)/g,
  (_, id, target, cond, value) => { adminSet[target] = { cond, value: Number(value) }; });

const adminNet = /'ネット申込特典', 'ネット申込特典', '', '', '', (\d+)/.exec(adminSrc);

const mismatches = [];
rules.filter(r => r.ruleType === '同時施工価格').forEach(r => {
  const a = adminSet[r.target];
  if (!a) return mismatches.push(r.target + ' が Admin.gs に無い');
  if (a.value !== r.value) mismatches.push(r.target + ' の単価が違う（Admin.gs ' + a.value + ' / このテスト ' + r.value + '）');
  if (a.cond !== (r.condition || '')) mismatches.push(r.target + ' の条件が違う');
});
if (Object.keys(adminSet).length !== rules.filter(r => r.ruleType === '同時施工価格').length) {
  mismatches.push('同時施工価格ルールの件数が Admin.gs と違う（Admin.gs ' + Object.keys(adminSet).length + '件）');
}
if (!adminNet || Number(adminNet[1]) !== NET_BENEFIT.amount) {
  mismatches.push('ネット申込特典の金額が Admin.gs と違う');
}

/* --- 突き合わせ --- */

console.log('\n予約フォーム vs 見積アプリ WEB経由見積タブ（すべて税込で比較）');
console.log('「WEB経由」＝自動割引ONの場合。「通常見積」は改修前の料金のまま\n');
console.log('  ' + 'ケース'.padEnd(26) + 'フォーム'.padStart(11) + 'WEB経由'.padStart(11)
  + '差額'.padStart(9) + '  通常見積'.padStart(12) + '  内訳');
console.log('  ' + '-'.repeat(104));

const gaps = [];

CASES.forEach(c => {
  const basket = c.basket.map(b => Object.assign({}, b, { appMenu: NAME_MAP[b.name] }));

  let f, same, normal;
  try {
    f = formPrice(basket, c.month);
    same = appPrice(basket, c.month, true);
    normal = normalPrice(basket, c.month);
  } catch (e) {
    console.log('  ' + c.label.padEnd(26) + '  スキップ：' + e.message);
    gaps.push({ label: c.label, diff: NaN });
    return;
  }

  const diff = same.grandTotal - f.total;
  const why = [];
  if (f.setBiki) why.push('同時施工 -' + yen(f.setBiki));
  if (f.waribiki) why.push('早期予約 -' + yen(f.waribiki));
  if (f.netto) why.push('ネット特典 -' + yen(f.netto));
  if (f.kasan) why.push('繁忙期 +' + yen(f.kasan));

  console.log('  ' + c.label.padEnd(26) + yen(f.total).padStart(11) + yen(same.grandTotal).padStart(11)
    + (diff === 0 ? '一致' : (diff > 0 ? '+' : '') + yen(diff)).padStart(9)
    + yen(normal.grandTotal).padStart(12)
    + '  ' + why.join(' / '));

  if (diff !== 0) gaps.push({ label: c.label, diff, form: f, app: same });
});

console.log('\n' + '='.repeat(104));

if (mismatches.length) {
  console.log('■ Admin.gs の正規化テーブルとの不一致');
  mismatches.forEach(m => console.log('  ✗ ' + m));
  console.log('');
}

if (gaps.length === 0 && mismatches.length === 0) {
  console.log('■ 揃っていること');
  console.log(`
  ・繁忙期加算 ¥3,300 は税込。課税対象には ¥3,000 で載せ、消費税を足して ¥3,300 になる。
  ・2箇所以上は同時施工価格。割引額がいちばん小さい1箇所だけ単品価格、残りは同時施工単価。
    コンロはキッチンと同時のときだけ ¥5,500（税抜）。
  ・早期予約割引は1箇所のみのご依頼に限る。2箇所以上は同時施工価格を優先。
  ・ネット申込特典 −¥2,200（税込）は、2箇所以上で同時施工割引が付かないときだけ自動で付く。
    1箇所のみのご依頼には付けない。

  ■ 通常見積タブとの差
  右端の「通常見積」列は改修前の料金そのまま。ここは今回一切変えていない。
  受注経路は見積レコードの「受注経路」列に残るので、あとから区別できる。

  ■ 納品時の既定との差
  自動割引は auto_discount_enabled = FALSE で納品するため、WEB経由タブでも
  1箇所のみのご依頼はフォームより高く出る（早期予約割引が載らないため）。
  2箇所以上は同時施工価格とネット申込特典が既定でONなので、既定のままでも一致する。
`);
  console.log(`✅ 全 ${CASES.length} 通り一致\n`);
  process.exit(0);
}

console.log('■ 一致しませんでした');
gaps.forEach(g => console.log('  ✗ ' + g.label + '：' + (isNaN(g.diff) ? 'スキップ' : yen(g.diff))));
console.log(`\n❌ ${gaps.length} / ${CASES.length} 通りがズレています。`);
console.log('   料金の決めごとを変えたのであれば掲示板で共有し、このテストも直すこと。\n');
process.exit(1);
