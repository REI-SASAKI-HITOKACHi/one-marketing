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
  productType: ['変額', '終身'],
  estimatedDate: '2026-07-20', initialDate: '2026-08-05', finalDate: '2026-08-10',
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
  tel: '080-6817-4796', email: 'info@hitokachi.com',
  agency: 'ヒトカチ株式会社'   // 自社の代理店名。取扱代理店名の行に使う
};

// 推定のご意向は入力欄がなく、保険種類から自動で入る。本番と同じ形にしてから描く。
ctx.applyAutoIntent_(data, true);

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
t('確認日が西暦スラッシュ表記', i.includes('2026/08/05'));
// 推定・当初・最終の3列すべてに確認日が入る（推定の欄が空白のままだと不備になる）。
t('確認日が3列とも入っている',
  i.includes('2026/07/20') && i.includes('2026/08/05') && i.includes('2026/08/10'));
t('当初のご意向にチェックが5件', (i.match(/☑/g) || []).length >= 5);
t('未選択の項目は空チェック', i.includes('☐'));
// 推定のご意向は入力欄がないので、自動で入らないと列が丸ごと空欄になる。
t('推定のご意向も埋まっている', (i.match(/☑/g) || []).length >= 12);
t('募集人の連絡先が入っている', i.includes('080-6817-4796'));
t('個人・法人のブロックがある', i.includes('個人の') && i.includes('法人の'));

console.log('\n--- 検証結果は確定した側だけ書く ---');
// 「適 ・ 不適」を並べて片方を太字にすると、印刷では見分けが付かない。
// 判定は本文だけを見る。<style> のコメントに書いた説明まで拾ってしまうため。
const sBody = s.slice(s.indexOf('<body>'));
t('確定した結果が入っている', sBody.includes('<td class="mid">適</td>'));
t('選ばなかった側は出ない',   !sBody.includes('不適'));
t('HTMLコメントを残さない',   !sBody.includes('<!--'));

console.log('\n--- 取扱代理店名は提携先と自社の2行 ---');
{
  const rows = (d, agencyName) =>
    JSON.stringify(ctx.agencyRows_(d, agent, agencyName));
  const expect = (...pairs) =>
    JSON.stringify(pairs.map(p => ({ agency: p[0], person: p[1] })));

  t('自社の契約は1行',
    rows({}, 'ヒトカチ株式会社') === expect(['ヒトカチ株式会社', '佐々木 嶺']));

  // 提携先が先。契約を取り次いだ側から書く。取扱者名も同じ並びになる。
  t('提携先の契約は2行',
    rows({ coAgent: '熊澤 善弘' }, 'クレスト保険')
      === expect(['クレスト保険', '熊澤 善弘'], ['ヒトカチ株式会社', '佐々木 嶺']));

  t('連名の相手がいなくても提携先の行は出す',
    rows({}, 'クレスト保険')
      === expect(['クレスト保険', ''], ['ヒトカチ株式会社', '佐々木 嶺']));

  const pairData = Object.assign({}, data, { coAgent: '熊澤 善弘' });
  const pairModel = ctx.buildModel_(pairData, ctx.defaultAnswers_(pairData), agent, 'クレスト保険');
  const pairSuit = render(fs.readFileSync(path.join(SRC, 'SuitabilitySheet.html'), 'utf8'), pairModel);
  t('帳票に自社の代理店名が出る', pairSuit.includes('ヒトカチ株式会社'));
  t('帳票に提携先の代理店名も出る', pairSuit.includes('クレスト保険'));
  t('2行に分かれている', pairSuit.includes('クレスト保険<br>ヒトカチ株式会社'));
  t('取扱者も同じ並び', pairSuit.includes('熊澤 善弘<br>佐々木 嶺'));

  console.log('\n--- 意向把握シートの募集人は連名のまま ---');
  const pairIntent = render(fs.readFileSync(path.join(SRC, 'IntentSheet.html'), 'utf8'), pairModel);
  t('連名で入る', pairIntent.includes('佐々木 嶺 / 熊澤 善弘'));
  t('単独なら募集人ひとり', i.includes('佐々木 嶺') && !i.includes(' / '));
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
