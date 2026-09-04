/**
 * 帳票テンプレートの描画テスト。
 *
 * Apps Script にデプロイしなくても、テンプレートの構文誤りと差し込み漏れを
 * ここで見つけられるようにしている。`--write` を付けると描画結果を
 * out/ に書き出すので、ブラウザで開いてレイアウトを確認できる。
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const { render } = require('./gas-template');

const SRC = path.join(__dirname, '..', 'src');
const OUT = path.join(__dirname, 'out');

const ctx = {
  console,
  Utilities: {
    formatDate(d) {
      const p = n => String(n).padStart(2, '0');
      return `${d.getFullYear()}/${p(d.getMonth() + 1)}/${p(d.getDate())}`;
    }
  }
};
vm.createContext(ctx);
for (const f of ['Fields.gs', 'Judge.gs', 'Render.gs']) {
  vm.runInContext(fs.readFileSync(path.join(SRC, f), 'utf8'), ctx, { filename: f });
}

let pass = 0, fail = 0;
function t(name, cond) {
  cond ? pass++ : fail++;
  console.log((cond ? '  ok  ' : '  NG  ') + name);
}

const data = {
  contractType: '個人',
  customerName: '種田 裕貴',
  confirmDate: '2026-08-01',
  age: 31,
  occupation: '会社員（IT保守・運用）',
  occupationClass: '左記以外',
  income: 500, assets: 100, annualPremium: 80, payYears: 10,
  experience: ['株式', '投資信託'],
  premiumSource: ['預貯金・給与'],
  sourceNotMaturity: true, sourceSpare: true, sourceNotLoan: true,
  riskTolerance: ctx.RISK_YES,
  needs: ['death', 'medical', 'cancer', 'education', 'pension'],
  savings: '①ある方が良い',
  wishPeriod: '一生涯',
  verifyDate: '2026-08-02',
  verifierName: '髙橋 知史',
  verifyResult: '適'
};
const agent = {
  name: '佐々木 嶺', zip: '134-0081',
  address1: '東京都 江戸川区 北葛西',
  address2: '５－１４－１１ クオーディア西葛西５０３',
  tel: '080-6817-4796', email: 'info@hitokachi.com'
};

const answers = ctx.defaultAnswers_(data);
const model = ctx.buildModel_(data, answers, agent, 'ヒトカチ株式会社');

const sheets = {
  '適合性確認シート': 'SuitabilitySheet.html',
  '意向把握シート': 'IntentSheet.html'
};

console.log('\n--- テンプレートの描画 ---');
const rendered = {};
for (const [label, file] of Object.entries(sheets)) {
  let html;
  try {
    html = render(fs.readFileSync(path.join(SRC, file), 'utf8'), model);
  } catch (e) {
    fail++;
    console.log(`  NG  ${label} の描画で例外: ${e.message}`);
    continue;
  }
  rendered[file] = html;
  pass++;
  console.log(`  ok  ${label} を描画できた（${html.length} 文字）`);

  t(`${label}: 未処理のテンプレートタグが残っていない`, !/<\?/.test(html));
  t(`${label}: undefined が混ざっていない`, !/undefined/.test(html));
  t(`${label}: <td> と </td> の数が一致`,
    (html.match(/<td/g) || []).length === (html.match(/<\/td>/g) || []).length);
  t(`${label}: <tr> と </tr> の数が一致`,
    (html.match(/<tr/g) || []).length === (html.match(/<\/tr>/g) || []).length);
  t(`${label}: 契約者名が入っている`, html.includes('種田 裕貴'));
}

console.log('\n--- 適合性確認シートの中身 ---');
const s = rendered['SuitabilitySheet.html'];
t('年収×20%が計算されている', s.includes('100万円'));
t('金融資産×30%が計算されている', s.includes('30万円'));
t('確認日が全角で入っている', s.includes('２０２６年８月１日'));
t('⑤で株式にチェックが付いている', s.includes('■株式'));
t('⑤で公社債は空欄', s.includes('□公社債'));
t('判定がすべて「はい」', (s.match(/■はい/g) || []).length === 6);
t('別紙が改ページで続いている', s.includes('class="pb"'));
t('取扱代理店名が入っている', s.includes('ヒトカチ株式会社'));

console.log('\n--- 意向把握シートの中身 ---');
const i = rendered['IntentSheet.html'];
t('確認日が西暦スラッシュ表記', i.includes('2026/08/01'));
t('当初のご意向にチェックが5件', (i.match(/☑/g) || []).length >= 5);
t('未選択の項目は空チェック', i.includes('☐'));
t('募集人の連絡先が入っている', i.includes('080-6817-4796'));
t('個人・法人のブロックがある', i.includes('個人の') && i.includes('法人の'));

console.log('\n--- 共同募集（連名） ---');
{
  t('単独なら適合性シートは募集人ひとり', s.includes('佐々木 嶺') && !s.includes(' / '));
  t('単独なら意向把握シートも募集人ひとり', i.includes('佐々木 嶺') && !i.includes(' / '));

  const pairData = Object.assign({}, data, { coAgent: '熊澤 善弘' });
  const pairModel = ctx.buildModel_(pairData, ctx.defaultAnswers_(pairData), agent, 'ヒトカチ株式会社');
  const pairRendered = {};
  for (const file of Object.values(sheets)) {
    pairRendered[file] = render(fs.readFileSync(path.join(SRC, file), 'utf8'), pairModel);
  }
  t('適合性シートの取扱者名が連名になる',
    pairRendered['SuitabilitySheet.html'].includes('佐々木 嶺 / 熊澤 善弘'));
  t('意向把握シートの募集人も連名になる',
    pairRendered['IntentSheet.html'].includes('佐々木 嶺 / 熊澤 善弘'));
}

if (process.argv.includes('--write')) {
  fs.mkdirSync(OUT, { recursive: true });
  for (const [file, html] of Object.entries(rendered)) {
    fs.writeFileSync(path.join(OUT, file), html);
  }
  console.log(`\n描画結果を ${OUT} に書き出しました。ブラウザで開くとレイアウトを確認できます。`);
}

console.log(`\n合計 ${pass + fail} 件 / 成功 ${pass} / 失敗 ${fail}`);
process.exit(fail ? 1 : 0);
