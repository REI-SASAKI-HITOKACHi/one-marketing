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
 * このテストは「一致すること」を主張しない。
 * **ズレの一覧を出す**のが目的。どう揃えるかは料金の決めごとなのでオーナー判断。
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

const rules = [
  { ruleType: '繁忙期', target: '全体', startMonth: 5, endMonth: 7, value: 3300, priority: 10 },
  { ruleType: '繁忙期', target: '全体', startMonth: 12, endMonth: 12, value: 3300, priority: 10 },
  { ruleType: '早期予約割引', target: '全体', startMonth: 1, endMonth: 2, value: 0.15, priority: 20 },
  { ruleType: '早期予約割引', target: '全体', startMonth: 3, endMonth: 4, value: 0.10, priority: 20 },
  { ruleType: '早期予約割引', target: '全体', startMonth: 8, endMonth: 10, value: 0.10, priority: 20 }
];

function appCtx(autoDiscount) {
  return {
    taxRate: 0.10, busySurcharge: 3300, busySurchargeUnit: '数量ごと',
    autoDiscountEnabled: autoDiscount, largeDiscountRatio: 0.30,
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
  return engine.calculate({ workDate, details }, appCtx(autoDiscount));
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

console.log('\n予約フォーム vs 見積アプリ（すべて税込で比較）');
console.log('見積アプリは納品時の既定（自動割引OFF）で計算\n');
console.log('  ' + 'ケース'.padEnd(26) + 'フォーム'.padStart(11) + 'アプリ'.padStart(11)
  + '差額'.padStart(11) + '  内訳');
console.log('  ' + '-'.repeat(88));

const gaps = [];

CASES.forEach(c => {
  const basket = c.basket.map(b => Object.assign({}, b, { appMenu: NAME_MAP[b.name] }));

  let f, a;
  try {
    f = formPrice(basket, c.month);
    a = appPrice(basket, c.month, false);
  } catch (e) {
    console.log('  ' + c.label.padEnd(26) + '  スキップ：' + e.message);
    return;
  }

  const diff = a.grandTotal - f.total;
  const why = [];
  if (f.setBiki) why.push('同時施工割引 -' + yen(f.setBiki));
  if (f.waribiki) why.push('早期予約 -' + yen(f.waribiki));
  if (f.netto) why.push('ネット特典 -' + yen(f.netto));
  if (f.kasan) why.push('繁忙期 +' + yen(f.kasan) + '（フォーム）');
  if (a.busyAmount) why.push('繁忙期 +' + yen(a.busyAmount) + '（アプリ・税抜）');

  console.log('  ' + c.label.padEnd(26) + yen(f.total).padStart(11) + yen(a.grandTotal).padStart(11)
    + (diff === 0 ? '一致' : (diff > 0 ? '+' : '') + yen(diff)).padStart(11)
    + '  ' + why.join(' / '));

  if (diff !== 0) gaps.push({ label: c.label, diff, form: f, app: a });
});

console.log('\n' + '='.repeat(92));
console.log('■ ズレの原因（コードから読み取れたもの）');
console.log('='.repeat(92));

console.log(`
1. 同時施工割引（セット価格）
   予約フォーム : メニューごとに単品価格 t と同時施工価格 d を持ち、2箇所以上のとき
                 「割引額がいちばん小さい1箇所」だけ単品、残りは同時施工価格。
   見積アプリ   : 同時施工価格という概念が無い。常に単価1本。
   → 2箇所以上のご依頼で、フォームのほうが安く出る。

2. ネット申込特典 ¥2,200
   予約フォーム : 2箇所以上でセット割引が付かない組み合わせのときだけ −¥2,200。
   見積アプリ   : 無し。

3. 早期予約割引の条件
   予約フォーム : 1箇所のときだけ（複数箇所は同時施工割引を優先）。
                 率は 1-2月15% / 3-4月10% / 8-10月10%。
   見積アプリ   : 箇所数の条件が無い。かわりにエアコンの複数台割引を持つ。
                 いまは auto_discount_enabled=FALSE なので、そもそも割引が載らない。

4. 繁忙期加算の数え方
   予約フォーム : 選んだ箇所数 × ¥3,300（税込表示）。
   見積アプリ   : 繁忙期加算対象のメインメニューの数量 × ¥3,300（税抜に加算し、後で課税）。
   → 本メニューだけなら対象は一致するが、税の扱いが違うため税込額は一致しない。
     アプリはオプション（室外機セット等）を対象外にしており、フォームには
     オプションが無いので、いまのところ表面化していない。
`);

console.log('='.repeat(92));
console.log('■ 判断が要ること（料金の決めごとなのでオーナー判断）');
console.log('='.repeat(92));
console.log(`
  ・同時施工価格を見積アプリにも入れるか
    docs/price-master.md では、この解釈自体が [要確認] のまま。
    「オプション欄の価格は2箇所目以降の同時施工価格」という読みで
    予約フォームは実装されている。合っているかの確認が要る。

  ・ネット申込特典 ¥2,200 を正式見積にも反映するか
    フォーム限定の特典なら、見積が高く出るのは正しい。
    その場合はお客様への説明文言が要る。

  ・早期予約割引を「1箇所のみ」に揃えるか
    見積アプリ側は現在 auto_discount_enabled=FALSE で無効。
    有効化するときに条件を合わせないと、同じ月・同じ内容で金額が変わる。
`);

console.log(`ズレたケース: ${gaps.length} / ${CASES.length}`);
console.log('※ このテストは一致を要求しない（失敗させない）。ズレの可視化が目的。\n');
