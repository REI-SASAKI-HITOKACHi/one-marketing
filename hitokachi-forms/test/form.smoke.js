/**
 * 入力画面のスモークテスト。
 *
 *   npm run smoke
 *
 * BOOT を差し込んで renderForm() まで通し、意向の折り畳みと
 * 保険種類→意向の自動反映が効いているかを実際のブラウザで確かめる。
 * 結果の画面は test/out/form.png に出る。
 *
 * npm test には入れていない。Playwright と Chromium が要るので、
 * 手元に無い環境で test が落ちないようにするため。
 *   npm install -D playwright && npx playwright install chromium
 * を一度だけ実行すれば動く。
 */
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path'), vm = require('vm');

const SRC = path.join(process.cwd(), 'src');
const ctx = { console };
vm.createContext(ctx);
for (const f of ['Fields.gs']) vm.runInContext(fs.readFileSync(path.join(SRC, f), 'utf8'), ctx, { filename: f });

const conf = {};
ctx.FIELD_DEFS.forEach(f => { conf[f.key] = f.defaultMode || 'form'; });
const BOOT = {
  allowed: true, title: 'テスト', email: 'x@example.com',
  sections: ctx.FIELD_SECTIONS,
  fields: ctx.FIELD_DEFS.filter(f => (f.defaultMode || 'form') === 'form').map(f => {
    const o = { key: f.key, label: f.label, type: f.type, section: f.section,
      required: !!f.required, unit: f.unit || '', note: f.note || '', showIf: f.showIf || '',
      mode: 'form', defaultValue: f.defaultValue == null ? '' : f.defaultValue, options: f.options || [] };
    if (f.type === 'needs') o.options = ctx.NEEDS;
    return o;
  }),
  agencies: [{ name: 'ヒトカチ株式会社', coAgents: [] }, { name: '提携代理店B', coAgents: ['熊澤 善弘'] }],
  agents: [{ name: '佐々木 嶺', agency: 'ヒトカチ株式会社' }],
  needs: ctx.NEEDS,
  productTypes: ctx.PRODUCT_TYPES.map(p => ({ key: p.key, needs: p.needs, savings: p.savings })),
  savingsYes: ctx.SAVINGS_YES,
  defaults: { contractType: '個人' }
};

let html = fs.readFileSync(path.join(SRC, 'Form.html'), 'utf8');
html = html.replace('<?!= boot ?>', JSON.stringify(BOOT));
const out = path.join(process.cwd(), 'test/out/Form.html');
fs.writeFileSync(out, html);

(async () => {
  // 環境変数で実行ファイルを指せるようにしておく（既定は Playwright が探す）。
  const b = await chromium.launch(
    process.env.CHROMIUM_PATH ? { executablePath: process.env.CHROMIUM_PATH } : {});
  const p = await b.newPage();
  const errors = [];
  p.on('pageerror', e => errors.push(e.message));
  await p.goto('file://' + out);
  await p.waitForTimeout(300);

  const check = async (name, fn, expected) => {
    const actual = await p.evaluate(fn);
    const ok = JSON.stringify(actual) === JSON.stringify(expected);
    console.log((ok ? '  ok  ' : '  NG  ') + name + (ok ? '' : `\n        期待=${JSON.stringify(expected)} 実際=${JSON.stringify(actual)}`));
  };

  console.log('\n--- 画面が組み立つ ---');
  console.log(errors.length ? '  NG  例外: ' + errors.join(' / ') : '  ok  例外なし');
  await check('保険種類がチェックになっている',
    () => document.getElementsByName('n_productType').length, 6);
  await check('共同募集の相方の欄が無い',
    () => !!document.getElementById('i_coAgent'), false);
  await check('意向は畳まれている',
    () => document.getElementById('intentBody').hidden, true);
  await check('ボタンの文言', () => document.getElementById('intentToggle').textContent, '意向を手入力する');

  console.log('\n--- 保険種類を選ぶと意向が入る ---');
  await p.evaluate(() => {
    const boxes = document.getElementsByName('n_productType');
    for (const b of boxes) if (b.value === '変額' || b.value === '終身') {
      b.checked = true; b.dispatchEvent(new Event('change'));
    }
  });
  await check('ご意向は死亡＋老後', () => STATE.values.needs, ['death', 'pension']);
  await check('貯蓄部分はある方が良い', () => STATE.values.savings, '①ある方が良い');
  await check('画面のチェックも入る',
    () => Array.from(document.getElementsByName('n_needs')).filter(b => b.checked).map(b => b.value),
    ['death', 'pension']);

  console.log('\n--- 選び直すと入れ替わる ---');
  await p.evaluate(() => {
    const boxes = document.getElementsByName('n_productType');
    for (const b of boxes) {
      const want = (b.value === '医療');
      if (b.checked !== want) { b.checked = want; b.dispatchEvent(new Event('change')); }
    }
  });
  await check('医療だけになる', () => STATE.values.needs, ['medical']);
  await check('貯蓄部分も入れ替わる', () => STATE.values.savings, '②なくても良い');

  console.log('\n--- 法人を選ぶと手入力欄が開く ---');
  await p.evaluate(() => {
    for (const b of document.getElementsByName('n_contractType')) if (b.value === '法人') {
      b.checked = true; b.dispatchEvent(new Event('change'));
    }
  });
  await check('開く', () => document.getElementById('intentBody').hidden, false);
  await check('ボタンの文言が変わる', () => document.getElementById('intentToggle').textContent, '意向の手入力を閉じる');

  await p.evaluate(() => {
    for (const b of document.getElementsByName('n_contractType')) if (b.value === '個人') {
      b.checked = true; b.dispatchEvent(new Event('change'));
    }
  });
  await check('個人に戻すと畳まれる', () => document.getElementById('intentBody').hidden, true);

  await p.screenshot({ path: 'test/out/form.png', fullPage: true });
  await b.close();
  if (errors.length) process.exit(1);
})();
