const fs = require('fs');
const vm = require('vm');
const ctx = {
  console,
  Utilities: {
    formatDate(d, tz, fmt) {
      const p = n => String(n).padStart(2, '0');
      return `${d.getFullYear()}/${p(d.getMonth() + 1)}/${p(d.getDate())}`;
    }
  }
};
vm.createContext(ctx);
for (const f of ['Fields.gs', 'Judge.gs', 'Render.gs', 'DriveUtil.gs']) {
  vm.runInContext(fs.readFileSync(require('path').join(__dirname, '..', 'src', f), 'utf8'), ctx, { filename: f });
}

let pass = 0, fail = 0;
function t(name, actual, expected) {
  const ok = JSON.stringify(actual) === JSON.stringify(expected);
  ok ? pass++ : fail++;
  console.log((ok ? '  ok  ' : '  NG  ') + name + (ok ? '' : `\n        期待=${JSON.stringify(expected)} 実際=${JSON.stringify(actual)}`));
}

console.log('\n--- 名前の正規化（フォルダ照合） ---');
const n = ctx.normalizeName_;
t('敬称を落とす',        n('種田裕貴様'), n('種田裕貴'));
t('全角スペースを落とす', n('種田　裕貴'), n('種田裕貴'));
t('半角スペースを落とす', n('種田 裕貴'),  n('種田裕貴'));
t('旧字体 髙→高',        n('髙橋知史'),   n('高橋知史'));
t('旧字体 﨑→崎',        n('尾﨑幸仙'),   n('尾崎幸仙'));
t('別人は一致しない',     n('種田裕貴') === n('種田裕樹'), false);
t('全角英数はNFKCで揃う', n('ＡＢＣ１２３'), 'abc123');
t('旧字体 邉→辺',        n('渡邉'),       n('渡辺'));
t('旧字体 齋→斎',        n('齋藤'),       n('斎藤'));
t('複合（旧字体＋空白＋敬称）', n('髙橋　知史様'), n('高橋知史'));
t('空文字は空文字',       n(''),           '');

console.log('\n--- 別人を同一視しないこと（敬称除去の回帰） ---');
t('田中 ≠ 田',            n('田中') === n('田'), false);
t('山中 ≠ 山',            n('山中') === n('山'), false);
t('野中 ≠ 野',            n('野中') === n('野'), false);
t('「中」が空にならない',   n('中'), '中');
t('「けん」が削られない',   n('けん'), 'けん');
t('株式会社田中 ≠ 株式会社田', n('株式会社田中') === n('株式会社田'), false);
t('敬称は落ちる（様）',     n('田中様'), n('田中'));
t('敬称は落ちる（さん）',   n('田中さん'), n('田中'));
t('敬称は落ちる（御中）',   n('株式会社ABC御中'), n('株式会社ABC'));
t('敬称は落ちる（殿）',     n('田中殿'), n('田中'));

console.log('\n--- 数値でない入力を0として扱わないこと ---');
t('「不明」は未入力',   ctx.num_('不明'), null);
t('「非公開」は未入力', ctx.num_('非公開'), null);
t('「―」は未入力',     ctx.num_('―'), null);
t('空欄は未入力',      ctx.num_(''), null);
t('「1,000」は1000',   ctx.num_('1,000'), 1000);
t('「500万円」は500',  ctx.num_('500万円'), 500);
t('年齢が「不明」なら判定①は いいえ', ctx.judgeAge_({ age: '不明' }).value, 'no');
t('年収が「非公開」なら判定③は いいえ',
  ctx.judgeBalance_({ income: '非公開', assets: 100, annualPremium: 80, payYears: 10 }).value, 'no');

console.log('\n--- 負の値で判定が裏返らないこと ---');
t('負の年間保険料',   ctx.judgeBalance_({ income: 500, assets: 100, annualPremium: -150, payYears: 10 }).value, 'no');
t('負の払込期間',     ctx.judgeBalance_({ income: 500, assets: 100, annualPremium: 150, payYears: -5 }).value, 'no');
t('負の年収',         ctx.judgeBalance_({ income: -500, assets: 100, annualPremium: 150, payYears: 10 }).value, 'no');
t('払込期間0年',      ctx.judgeBalance_({ income: 500, assets: 100, annualPremium: 80, payYears: 0 }).value, 'no');

console.log('\n--- 70歳以上の募集方法は別紙の組み合わせだけ ---');
t('選択肢は2つ', ctx.ELDERLY_METHODS.length, 2);
t('単独の＜２＞は選択肢にない',
  ctx.ELDERLY_METHODS.indexOf('＜２＞複数回の面談による募集'), -1);
t('どちらも2つ以上の方法を含む（単独の募集方法がない）',
  ctx.ELDERLY_METHODS.every(m => (m.match(/＜[１２３]＞/g) || []).length >= 2), true);

console.log('\n--- ニーズの集約（意向把握8項目 → 適合性⑧） ---');
t('がん＋病気は1つに集約', ctx.needsToSuitKeys_(['medical', 'cancer']), ['medical']);
t('教育＋老後は貯蓄に集約', ctx.needsToSuitKeys_(['education', 'pension']), ['savings']);
t('死亡＋がん',            ctx.needsToSuitKeys_(['death', 'cancer']), ['death', 'medical']);

console.log('\n--- 判定③ 保険料バランス（別紙の基準） ---');
const bal = (income, assets, premium, years) =>
  ctx.judgeBalance_({ income, assets, annualPremium: premium, payYears: years }).value;
t('年収500/保険料80 → 年収20%以内',        bal(500, 100, 80, 10), 'yes');
t('別紙の例: 年収500/保険料150/資産100/10年', bal(500, 100, 150, 10), 'no');
t('別紙の例: 不足分50万×1年 ≦ 資産30%',      bal(500, 100, 150, 0.6), 'yes');
t('資産潤沢: 総払込 ≦ 資産30%',             bal(0, 10000, 150, 10), 'yes');
t('原本の記入例（31歳/年収500/資産100）',     bal(500, 100, 100, 10), 'yes');
t('未入力はいいえ',                          bal('', 100, 150, 10), 'no');

console.log('\n--- 判定① 年齢 ---');
const age = (a, m) => ctx.judgeAge_({ age: a, elderlyMethod: m }).value;
t('31歳',                     age(31), 'yes');
t('70歳・募集方法なし',        age(70), 'no');
t('70歳・親族同席',           age(70, ctx.ELDERLY_METHODS[0]), 'yes');

console.log('\n--- 判定④ 投資経験 ---');
const exp = (e, ok) => ctx.judgeExperience_({ experience: e, experienceExplained: ok }).value;
t('株式・投資信託あり',        exp(['株式', '投資信託']), 'yes');
t('投資経験なし・説明なし',     exp(['投資経験なし']), 'no');
t('投資経験なし・説明済み',     exp(['投資経験なし'], true), 'yes');
t('未選択は経験なし扱い',       exp([]), 'no');

console.log('\n--- 判定⑥ 意向 ---');
const it6 = (risk, needs, corp) => ctx.judgeIntent_({ riskTolerance: risk, needs }, corp).value;
t('個人・リスク許容・死亡保障',  it6(ctx.RISK_YES, ['death'], false), 'yes');
t('個人・リスク非許容',         it6(ctx.RISK_NO, ['death'], false), 'no');
t('個人なのに法人ニーズのみ',    it6(ctx.RISK_YES, ['business'], false), 'no');
t('法人・事業保障',             it6(ctx.RISK_YES, ['business'], true), 'yes');

console.log('\n--- 総合判定（原本の記入例を再現） ---');
const genten = {
  contractType: '個人', age: 31, occupationClass: '左記以外',
  income: 500, assets: 100, annualPremium: 80, payYears: 10,
  experience: ['株式', '投資信託'],
  premiumSource: ['預貯金・給与'],
  sourceNotMaturity: true, sourceSpare: true, sourceNotLoan: true,
  riskTolerance: ctx.RISK_YES,
  needs: ['death', 'medical', 'cancer', 'education', 'pension']
};
const j = ctx.judge_(genten);
t('①〜⑥すべて はい', ['i1','i2','i3','i4','i5','i6'].map(k => j.items[k].value),
  ['yes','yes','yes','yes','yes','yes']);
t('総合＝適合', j.suitable, true);

console.log('\n--- 借入金が原資なら不適合 ---');
const ng = ctx.judge_(Object.assign({}, genten, { sourceNotLoan: false }));
t('⑤が いいえ',   ng.items.i5.value, 'no');
t('総合＝不適合', ng.suitable, false);

console.log('\n--- 法人契約は①〜③が対象外 ---');
const corp = ctx.judge_(Object.assign({}, genten, { contractType: '法人', needs: ['business'] }));
t('①②③が対象外', ['i1','i2','i3'].map(k => corp.items[k].value), ['na','na','na']);
t('総合＝適合',    corp.suitable, true);

console.log('\n--- 表示モデル（帳票への差し込み値） ---');
const m = ctx.buildModel_(
  Object.assign({}, genten, {
    customerName: '種田 裕貴', confirmDate: '2026-08-01',
    savings: '①ある方が良い', needsOther: ''
  }),
  j,
  { name: '佐々木 嶺', zip: '134-0081', address1: '東京都 江戸川区 北葛西', address2: '', tel: '080-6817-4796', email: 'info@hitokachi.com' },
  'ヒトカチ株式会社'
);
t('年収×20%の自動計算',  m.income20, '100万円');
t('金融資産×30%の自動計算', m.assets30, '30万円');
t('確認日は全角',        m.confirmDateJp, '２０２６年８月１日');
t('最終日は確認日を引き継ぐ', m.finalDateSlash, '2026/08/01');
t('⑧に病気・ケガ等がチェック', m.suitNeeds[1].mark, '■');
t('⑧の事業保障は未チェック',   m.suitNeeds[3].mark, '□');
t('意向把握8行ぶん',      m.needsRows.length, 8);
t('意向の変化は常に3行',  m.changeLog.length, 3);
t('⑤株式にチェック',      m.experience[0].mark, '■');
t('⑤公社債は未チェック',  m.experience[2].mark, '□');

console.log(`\n合計 ${pass + fail} 件 / 成功 ${pass} / 失敗 ${fail}`);
process.exit(fail ? 1 : 0);
