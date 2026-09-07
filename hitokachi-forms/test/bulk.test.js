/**
 * 一括入力シートのテスト。
 *
 * 列の組み立てと、1 行を判定・帳票に渡せる形へ戻す変換を確かめる。
 * ここが崩れると全行が静かに間違った帳票になるので、厚めに見ておく。
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const SRC = path.join(__dirname, '..', 'src');

const AGENCIES = [
  ['代理店名', '共有フォルダID', '有効', '備考'],
  ['ヒトカチ株式会社', 'FOLDER_A', true, ''],
  ['提携代理店B', 'FOLDER_B', true, ''],
  ['提携代理店C', 'FOLDER_C', true, ''],
  ['提携代理店D', 'FOLDER_D', true, '']
];
/** 代理店ごとの募集人。1人1行。入力画面の「募集人」の選択肢になる。 */
const CO_AGENTS = [
  ['代理店名', '氏名', '有効', '備考'],
  ['提携代理店B', '熊澤 善弘', true,  ''],
  ['提携代理店B', '小川 康之', true,  ''],
  ['提携代理店B', '退職 済',   false, '無効なので選択肢に出ない'],
  ['提携代理店C', '矢野 克臣', true,  ''],
  ['提携代理店D', '甲野 一郎', true,  ''],
  ['提携代理店D', '乙野 二郎', true,  ''],
  ['存在しない代理店', '幽霊 太郎', true, '代理店マスタに無いので無視される']
];
const AGENTS = [
  ['氏名', 'メールアドレス', '電話番号', '郵便番号', '住所1', '住所2', '所属代理店', 'ログイン用アドレス', '検証者', '有効'],
  ['佐々木 嶺', 'info@hitokachi.com', '080-6817-4796', '134-0081', '東京都 江戸川区 北葛西', '５－１４－１１', 'ヒトカチ株式会社', '', '', true],
  ['髙橋 知史', 's-takahashi@hitokachi.com', '080-2238-7592', '134-0081', '東京都 江戸川区 北葛西', '５－１４－１１', 'ヒトカチ株式会社', '', '佐々木 嶺', true]
];

/**
 * 帳票に印字されず、判定の参考にしか使わない項目。既定は「使わない」。
 * これらを入力する運用に戻したときの動きも見たいので、まとめて持っておく。
 */
const JUDGE_ONLY = [
  'elderlyMethod', 'occupationClass', 'householdConfirmed', 'annualPremium',
  'payYears', 'experienceExplained', 'sourceNotMaturity',
  'sourceMaturityExplained', 'sourceSpare', 'sourceNotLoan'
];
const ALL_ON = {};
JUDGE_ONLY.forEach(k => { ALL_ON[k] = 'form'; });

/** 項目設定シートを、既定の扱いから組み立てる（上書きしたい項目だけ渡す）。 */
function fieldSheet(ctx, overrides) {
  const rows = [['項目キー', '表示名', 'セクション', '扱い', '固定値', '必須', '選択肢', '備考']];
  for (const f of ctx.FIELD_DEFS) {
    const mode = (overrides && overrides[f.key]) || f.defaultMode || 'form';
    rows.push([f.key, f.label, f.section, ctx.MODE_LABELS[mode], '', !!f.required, '', '']);
  }
  return rows;
}

function makeContext(extraSheets) {
  const sheets = Object.assign(
    { '代理店マスタ': AGENCIES, '代理店募集人マスタ': CO_AGENTS, '募集人マスタ': AGENTS },
    extraSheets);
  const ctx = {
    console,
    PropertiesService: { getScriptProperties: () => ({ getProperty: () => 'dummy' }) },
    SpreadsheetApp: {
      openById: () => ({
        getSheetByName(name) {
          if (!sheets[name]) return null;
          return { getDataRange: () => ({ getValues: () => sheets[name] }) };
        }
      })
    },
    Utilities: {
      formatDate(d, tz, fmt) {
        const p = n => String(n).padStart(2, '0');
        const y = d.getFullYear(), m = p(d.getMonth() + 1), day = p(d.getDate());
        if (fmt === 'yyyy-MM-dd') return `${y}-${m}-${day}`;
        if (fmt === 'yyyyMMdd') return `${y}${m}${day}`;
        return `${y}/${m}/${day}`;
      }
    }
  };
  vm.createContext(ctx);
  for (const f of ['Fields.gs', 'Config.gs', 'Judge.gs', 'Render.gs', 'Generate.gs', 'DriveUtil.gs', 'Existing.gs', 'Bulk.gs']) {
    vm.runInContext(fs.readFileSync(path.join(SRC, f), 'utf8'), ctx, { filename: f });
  }
  // 項目設定は FIELD_DEFS を読んでから組み立てるので、あとから差し込む。
  sheets['項目設定'] = fieldSheet(ctx, extraSheets && extraSheets.__modes);
  return ctx;
}

let pass = 0, fail = 0;
function t(name, actual, expected) {
  const ok = JSON.stringify(actual) === JSON.stringify(expected);
  ok ? pass++ : fail++;
  console.log((ok ? '  ok  ' : '  NG  ') + name +
    (ok ? '' : `\n        期待=${JSON.stringify(expected)} 実際=${JSON.stringify(actual)}`));
}

console.log('\n--- 列の組み立て ---');
{
  const ctx = makeContext();
  const cols = ctx.bulkColumns_();
  const keys = cols.map(c => c.key);

  t('契約者氏名が先頭', keys[0], 'customerName');
  t('保障ニーズは8列に展開される',
    keys.filter(k => k.indexOf('needs:') === 0).length, 8);
  t('購入経験は選択肢ごとの列になる',
    keys.filter(k => k.indexOf('experience:') === 0).length, ctx.EXPERIENCE_OPTIONS.length);
  t('保険料原資も同様',
    keys.filter(k => k.indexOf('premiumSource:') === 0).length, ctx.PREMIUM_SOURCE_OPTIONS.length);
  t('列キーに重複がない', keys.length, new Set(keys).size);

  const byKey = k => cols.find(c => c.key === k);
  t('ニーズはチェックボックス',   byKey('needs:death').kind, 'check');
  t('ニーズの見出しは日本語',     byKey('needs:death').label, 'ニーズ｜死亡時の保障');
  t('代理店はプルダウン',         byKey('agency').kind, 'list');
  t('代理店の選択肢はマスタから', byKey('agency').options,
    ['ヒトカチ株式会社', '提携代理店B', '提携代理店C', '提携代理店D']);
  // 募集人は行ごとに代理店で絞るので、列全体の選択肢は持たない。
  t('募集人は列の選択肢を持たない', byKey('agent').options, []);
  t('作成者は自社の募集人から',     byKey('author').options, ['佐々木 嶺', '髙橋 知史']);
  t('年齢は数値',                 byKey('age').kind, 'number');
  t('年収の見出しに単位が付く',    byKey('income').label, '年収（万円）');
  t('確認日は日付',               byKey('confirmDate').kind, 'date');
  t('判定専用の項目は既定で列にならない',
    JUDGE_ONLY.filter(k => byKey(k) !== undefined), []);

  t('既定で使わない項目は列にならない（検証日）', byKey('verifyDate'), undefined);
  t('既定で使わない項目は列にならない（推定意向）',
    keys.filter(k => k.indexOf('estimatedNeeds') === 0).length, 0);
  t('意向の変化は一括では扱わない', byKey('changeLog'), undefined);
}

console.log('\n--- 判定専用の項目は「入力する」に戻せる ---');
{
  const ctx = makeContext({ __modes: ALL_ON });
  const cols = ctx.bulkColumns_();
  const byKey = k => cols.find(c => c.key === k);
  t('10項目すべてが列に戻る', JUDGE_ONLY.filter(k => byKey(k) === undefined), []);
  t('原資アはチェックボックス', byKey('sourceNotMaturity').kind, 'check');
  t('年間保険料は数値',         byKey('annualPremium').kind, 'number');
  t('職業区分はプルダウン',     byKey('occupationClass').kind, 'list');
}

console.log('\n--- 項目設定を変えると列も変わる ---');
{
  const ctx = makeContext({ __modes: { verifyDate: 'form', age: 'hidden', agency: 'fixed' } });
  const keys = ctx.bulkColumns_().map(c => c.key);
  t('「入力する」にすると列が生える', keys.indexOf('verifyDate') >= 0, true);
  t('「使わない」にすると列が消える', keys.indexOf('age'), -1);
  t('「固定値を使う」も列に出さない', keys.indexOf('agency'), -1);
}

console.log('\n--- 1行をデータに戻す ---');
{
  // 判定専用の項目も含めて、変換と判定が最後まで通ることを見る。
  const ctx = makeContext({ __modes: ALL_ON });
  const row = {
    __status: '未作成',
    __message: '',
    customerName: '種田 裕貴',
    agency: 'ヒトカチ株式会社',
    author: '佐々木 嶺', agent: '佐々木 嶺',
    contractType: '個人',
    confirmDate: new Date(2026, 7, 1),
    age: 31,
    occupation: '会社員（IT保守・運用）',
    occupationClass: '左記以外',
    income: 500, assets: 100, annualPremium: 80, payYears: 10,
    'experience:株式': true,
    'experience:投資信託': true,
    'experience:公社債': false,
    'experience:投資経験なし': false,
    'premiumSource:預貯金・給与': true,
    'premiumSource:株式': false,
    'needs:death': true,
    'needs:medical': true,
    'needs:cancer': true,
    'needs:education': false,
    'needs:pension': false,
    'needs:business': false,
    sourceNotMaturity: true, sourceSpare: true, sourceNotLoan: true,
    riskTolerance: ctx.RISK_YES,
    savings: '①ある方が良い'
  };
  const data = ctx.bulkRowToData_(row);

  t('管理列はデータに混ざらない', data.__status, undefined);
  t('日付は文字列になる',         data.confirmDate, '2026-08-01');
  t('チェックの入った経験だけ拾う', data.experience, ['株式', '投資信託']);
  t('保険料原資も同様',            data.premiumSource, ['預貯金・給与']);
  t('ニーズも同様',                data.needs, ['death', 'medical', 'cancer']);
  t('チェックのない複数選択は空配列', data.estimatedNeeds, []);
  t('数値はそのまま',              data.income, 500);
  t('文字列はそのまま',            data.customerName, '種田 裕貴');

  console.log('\n--- そのまま判定と帳票モデルに渡せる ---');
  const conf = ctx.getFieldConfig_();
  const applied = ctx.applyFieldConfig_(data, conf);
  t('検証で弾かれない', ctx.validate_(applied, conf), []);

  const j = ctx.judge_(applied);
  t('①〜⑥すべて はい', ['i1','i2','i3','i4','i5','i6'].map(k => j.items[k].value),
    ['yes','yes','yes','yes','yes','yes']);
  t('総合＝適合', j.suitable, true);

  const m = ctx.buildModel_(applied, ctx.defaultAnswers_(applied), ctx.getAgentByName_('佐々木 嶺'), 'ヒトカチ株式会社');
  t('年収×20%が計算される',   m.income20, '100万円');
  t('確認日が全角で入る',      m.confirmDateJp, '２０２６年８月１日');
  t('⑧に病気等が集約される',  m.suitNeeds[1].mark, '■');
  t('⑧の貯蓄は未チェック',    m.suitNeeds[2].mark, '□');
}

console.log('\n--- 入力漏れはエラーとして拾える ---');
{
  const ctx = makeContext();
  const conf = ctx.getFieldConfig_();
  const data = ctx.applyFieldConfig_(ctx.bulkRowToData_({
    customerName: '山田 太郎', agency: 'ヒトカチ株式会社'
  }), conf);
  const errors = ctx.validate_(data, conf);
  t('未入力の必須項目が挙がる', errors.length > 0, true);
  t('年収の漏れを指摘する', errors.some(e => e.indexOf('年収') >= 0), true);
  t('ニーズの漏れを指摘する', errors.some(e => e.indexOf('ご希望の保障分野') >= 0), true);
}

console.log('\n--- 検証：不正な数値を弾く ---');
{
  // 年間保険料と払込期間は既定では入力しない項目なので、入力する設定にして見る。
  const ctx = makeContext({ __modes: ALL_ON });
  const conf = ctx.getFieldConfig_();
  const base = {
    contractType: '個人', customerName: '山田 太郎', agency: 'ヒトカチ株式会社',
    author: '佐々木 嶺', agent: '佐々木 嶺', confirmDate: '2026-08-01',
    age: 40, occupation: '会社員', occupationClass: '左記以外',
    income: 500, assets: 100, annualPremium: 80, payYears: 10,
    experience: ['株式'], premiumSource: ['預貯金・給与'],
    sourceNotMaturity: true, sourceSpare: true, sourceNotLoan: true,
    riskTolerance: ctx.RISK_YES, needs: ['death'], savings: '①ある方が良い'
  };
  const check = (over) => ctx.validate_(ctx.applyFieldConfig_(Object.assign({}, base, over), conf), conf);

  t('正常な入力は通る', check({}), []);
  t('負の年間保険料を弾く',
    check({ annualPremium: -150 }).some(e => e.indexOf('負の値') >= 0), true);
  t('負の年収を弾く',
    check({ income: -500 }).some(e => e.indexOf('負の値') >= 0), true);
  t('負の金融資産を弾く',
    check({ assets: -100 }).some(e => e.indexOf('負の値') >= 0), true);
  t('負の払込期間を弾く',
    check({ payYears: -5 }).some(e => e.indexOf('1年以上') >= 0), true);
  t('払込期間0年を弾く',
    check({ payYears: 0 }).some(e => e.indexOf('1年以上') >= 0), true);
  t('「投資経験なし」と他商品の同時選択を弾く',
    check({ experience: ['株式', '投資経験なし'] }).some(e => e.indexOf('同時に選べません') >= 0), true);
  t('「投資経験なし」単独は通る', check({ experience: ['投資経験なし'] }), []);

  console.log('\n--- 検証：法人契約では個人向け項目を求めない ---');
  const corp = {
    contractType: '法人', customerName: '有限会社大原商店', agency: 'ヒトカチ株式会社',
    author: '佐々木 嶺', agent: '佐々木 嶺', confirmDate: '2026-08-01',
    experience: [], premiumSource: [],
    riskTolerance: ctx.RISK_YES, needs: ['business'], savings: '②なくても良い'
  };
  const corpErrors = ctx.validate_(ctx.applyFieldConfig_(corp, conf), conf);
  t('年齢・年収なしでも通る', corpErrors, []);
  t('個人契約なら同じ入力は弾かれる',
    ctx.validate_(ctx.applyFieldConfig_(Object.assign({}, corp, { contractType: '個人' }), conf), conf).length > 0, true);
}

console.log('\n--- 募集人は代理店に連動し、提携先なら連名になる ---');
{
  const ctx = makeContext();
  const conf = ctx.getFieldConfig_();
  const base = {
    author: '佐々木 嶺', contractType: '個人', customerName: '山田 太郎',
    confirmDate: '2026-08-01', productType: ['終身'],
    age: 40, occupation: '会社員', income: 500, assets: 100,
    experience: ['株式'], premiumSource: ['預貯金・給与'], riskTolerance: ctx.RISK_YES
  };
  const rows = (agency, agent) => {
    const d = ctx.applyFieldConfig_(Object.assign({}, base, { agency, agent }), conf);
    return ctx.buildModel_(d, ctx.defaultAnswers_(d), ctx.getAgentByName_('佐々木 嶺'), agency);
  };

  console.log('\n--- 自社の契約 ---');
  const own = rows('ヒトカチ株式会社', '髙橋 知史');
  t('取扱代理店は1行',   own.agencyRows.map(r => r.agency), ['ヒトカチ株式会社']);
  t('取扱者は選んだ募集人', own.agencyRows.map(r => r.person), ['髙橋 知史']);
  t('連名にはならない',   own.agentDisplay, '髙橋 知史');

  console.log('\n--- 提携先の契約 ---');
  const pair = rows('提携代理店B', '熊澤 善弘');
  // 提携先が上。契約を取り次いだ側から書く。自社側は作成者。
  t('取扱代理店は2行',
    pair.agencyRows.map(r => r.agency), ['提携代理店B', 'ヒトカチ株式会社']);
  t('取扱者も同じ並び',
    pair.agencyRows.map(r => r.person), ['熊澤 善弘', '佐々木 嶺']);
  t('意向把握は自社が先の連名', pair.agentDisplay, '佐々木 嶺 / 熊澤 善弘');
  t('連絡先は自社のもの', pair.agent.name, '佐々木 嶺');

  console.log('\n--- 代理店に登録されていない募集人は弾く ---');
  const check = (agency, agent) =>
    ctx.validate_(ctx.applyFieldConfig_(Object.assign({}, base, { agency, agent }), conf), conf);
  t('自社の人を提携先の契約に入れると弾く',
    check('提携代理店B', '髙橋 知史').some(e => e.indexOf('登録されていません') >= 0), true);
  t('他社の人を自社の契約に入れると弾く',
    check('ヒトカチ株式会社', '熊澤 善弘').some(e => e.indexOf('登録されていません') >= 0), true);
  t('その代理店の人なら通る', check('提携代理店B', '小川 康之'), []);
  t('自社の人も通る',         check('ヒトカチ株式会社', '佐々木 嶺'), []);

  console.log('\n--- 一括入力シートの募集人 ---');
  const cols = ctx.bulkColumns_();
  const byKey = k => cols.filter(c => c.key === k)[0];
  // 全代理店ぶんをまとめて出すと、100社×数十人で使いものにならない。
  t('列全体の選択肢は持たない', byKey('agent').options, []);
  t('作成者は自社の全員',       byKey('author').options, ['佐々木 嶺', '髙橋 知史']);
  t('相方の列は無い',           cols.filter(c => c.key === 'coAgent').length, 0);
}

console.log('\n--- 検証実施者は作成者から入る ---');
{
  const ctx = makeContext({
    '設定': [['キー', '値', '説明'], ['既定の検証実施者', '髙橋 知史', '']]
  });
  const conf = ctx.getFieldConfig_();
  const base = {
    contractType: '個人', customerName: '山田 太郎', agency: 'ヒトカチ株式会社',
    agent: '佐々木 嶺', confirmDate: '2026-08-01', productType: ['医療']
  };
  const made = (author) => ctx.applyFieldConfig_(Object.assign({}, base, { author }), conf);

  t('佐々木が作成 → 髙橋',   made('佐々木 嶺').verifierName, '髙橋 知史');
  t('髙橋が作成 → 佐々木',   made('髙橋 知史').verifierName, '佐々木 嶺');
  t('検証日は確認日と同じ',  made('佐々木 嶺').verifyDate, '2026-08-01');
  // 固定値が空欄でも、項目の既定値で補う（設定シートの入れ忘れで空白にしない）。
  t('検証結果は既定値で埋まる', made('佐々木 嶺').verifyResult, '適');

  t('作成者は入力欄がある',   ctx.FIELD_DEFS[0].key, 'author');
  t('作成者は必須',           !!ctx.FIELD_DEFS[0].required, true);
  t('検証実施者に入力欄は無い',
    ctx.getFieldConfig_().verifierName.mode, 'fixed');
  t('作成者を入れないと止まる',
    ctx.validate_(ctx.applyFieldConfig_(base, conf), conf)
      .some(e => e.indexOf('作成者') >= 0), true);
}

console.log('\n--- 意向の確認日は3つ ---');
{
  const ctx = makeContext();
  const conf = ctx.getFieldConfig_();
  const base = {
    contractType: '個人', customerName: '山田 太郎', agency: 'ヒトカチ株式会社',
    author: '佐々木 嶺', agent: '佐々木 嶺', confirmDate: '2026-08-01', productType: ['医療']
  };

  const auto = ctx.applyFieldConfig_(base, conf);
  t('推定は確認日と同じ', auto.estimatedDate, '2026-08-01');
  t('当初も確認日と同じ', auto.initialDate,   '2026-08-01');
  t('最終も確認日と同じ', auto.finalDate,     '2026-08-01');

  // 適合性の確認は提案より前に行うので、意向の確認日はあとの日付になりうる。
  const later = ctx.applyFieldConfig_(
    Object.assign({}, base, { initialDate: '2026-08-05' }), conf);
  t('当初を入れればそちら',       later.initialDate, '2026-08-05');
  t('最終は当初に合わせる',       later.finalDate,   '2026-08-05');
  t('基本情報の確認日は動かない', later.confirmDate, '2026-08-01');

  const all = ctx.applyFieldConfig_(Object.assign({}, base, {
    estimatedDate: '2026-07-20', initialDate: '2026-08-05', finalDate: '2026-08-10'
  }), conf);
  t('3つとも別の日にできる',
    [all.estimatedDate, all.initialDate, all.finalDate],
    ['2026-07-20', '2026-08-05', '2026-08-10']);

  t('一括入力シートにも3列ある',
    ctx.bulkColumns_().filter(c => /のご意向 確認日$/.test(c.label)).map(c => c.key),
    ['estimatedDate', 'initialDate', 'finalDate']);
}

console.log('\n--- 推定を自動で入れない設定 ---');
{
  const ctx = makeContext({
    '設定': [['キー', '値', '説明'], ['推定のご意向を自動で入れる', 'いいえ', '']]
  });
  const out = ctx.applyFieldConfig_({
    contractType: '個人', customerName: '山田 太郎', agency: 'ヒトカチ株式会社',
    author: '佐々木 嶺', agent: '佐々木 嶺', confirmDate: '2026-08-01', productType: ['医療']
  }, ctx.getFieldConfig_());
  // 日付だけ入って中身が空だと、推定の意向を確認したように見えてしまう。
  t('推定の意向は入らない', out.estimatedNeeds, []);
  t('推定の日付も入らない', out.estimatedDate, '');
  t('当初は入る',           out.needs, ['medical']);
  t('当初の日付も入る',     out.initialDate, '2026-08-01');
}

console.log('\n--- 法人の意向は自動で入れない ---');
{
  const ctx = makeContext();
  const conf = ctx.getFieldConfig_();
  const corp = {
    contractType: '法人', customerName: '株式会社テスト', agency: 'ヒトカチ株式会社',
    author: '佐々木 嶺', agent: '佐々木 嶺', confirmDate: '2026-08-01', productType: ['終身']
  };
  const out = ctx.applyFieldConfig_(corp, conf);
  // 同じ終身保険でも、個人なら死亡保障、法人なら事業保障や退職金準備になる。
  t('保険種類からは意向を決めない', out.needs, []);
  t('貯蓄部分も入れない',           out.savings, '');
  t('意向は入力が要る',
    ctx.validate_(out, conf).some(e => e.indexOf('ご希望の保障分野') >= 0), true);
  t('確認日は法人でも入れる',
    [out.estimatedDate, out.initialDate, out.finalDate],
    ['2026-08-01', '2026-08-01', '2026-08-01']);

  const filled = ctx.applyFieldConfig_(
    Object.assign({}, corp, { needs: ['business'], savings: ctx.SAVINGS_NO }), conf);
  t('手入力すれば通る', ctx.validate_(filled, conf), []);
  t('手入力の内容はそのまま', filled.needs, ['business']);
}

console.log('\n--- 保険種類で作る帳票が変わる ---');
{
  const ctx = makeContext({
    '設定': [['キー', '値', '説明'], ['適合性確認シートが必要な保険種類', '変額', '']]
  });
  const conf = ctx.getFieldConfig_();
  // 適合性確認シートのための入力（年齢・年収・投資経験など）を一切入れていない行。
  const thin = {
    contractType: '個人', customerName: '鈴木 花子', agency: 'ヒトカチ株式会社',
    author: '佐々木 嶺', agent: '佐々木 嶺', confirmDate: '2026-08-01',
    needs: ['death'], savings: '①ある方が良い'
  };
  const check = (over) => ctx.validate_(ctx.applyFieldConfig_(Object.assign({}, thin, over), conf), conf);

  t('医療保険なら適合性の入力を求めない', check({ productType: '医療保険' }), []);
  t('終身保険も同じ',                     check({ productType: '終身保険' }), []);
  t('変額保険なら適合性の入力を求める',    check({ productType: '変額保険' }).length > 0, true);
  t('求めるのは年齢・年収など',
    check({ productType: '変額保険' }).some(e => e.indexOf('年収') >= 0), true);
  t('保険種類が空欄なら求める側に倒す',    check({ productType: '' }).length > 0, true);

  console.log('\n--- 意向は保険種類から補う ---');
  t('保険種類があれば空欄でも通る',
    check({ productType: '医療保険', needs: [], savings: '' }), []);
  t('保険種類も空欄なら意向は必須',
    check({ productType: '', needs: [], savings: '' }).some(e => e.indexOf('ご希望の保障分野') >= 0), true);
  t('契約者氏名も必須',
    check({ productType: '医療保険', customerName: '' }).some(e => e.indexOf('契約者氏名') >= 0), true);

  console.log('\n--- 保険種類は一括入力シートの列になる ---');
  const cols = ctx.bulkColumns_();
  t('選択肢ごとに1列になる',
    cols.filter(c => c.group === 'productType').length, ctx.PRODUCT_TYPES.length);
  t('見出しは「保険種類｜変額」',
    cols.filter(c => c.key === 'productType:変額').map(c => c.label), ['保険種類｜変額']);
  t('文字列の列は残っていない', cols.filter(c => c.key === 'productType').length, 0);
  t('購入経験の見出しはそのまま',
    cols.filter(c => c.key === 'experience:株式').map(c => c.label), ['購入経験｜株式']);
}

console.log('\n--- 検証欄は固定値で印字する ---');
{
  const c = makeContext();
  const conf = c.getFieldConfig_();
  t('既定は固定値を使う',   conf.verifyResult.mode, 'fixed');
  t('検証結果の既定は「適」', c.fieldByKey_('verifyResult').defaultValue, '適');

  conf.verifierName.fixedValue = '髙橋 知史';
  conf.verifyResult.fixedValue = '適';
  const out = c.applyFieldConfig_({ confirmDate: '2026-08-01' }, conf);
  t('検証実施者が入る',     out.verifierName, '髙橋 知史');
  t('検証結果が入る',       out.verifyResult, '適');
  t('検証日は確認日と同じ', out.verifyDate, '2026-08-01');

  conf.verifyDate.fixedValue = '2026-08-05';
  t('固定値の日付があればそちら',
    c.applyFieldConfig_({ confirmDate: '2026-08-01' }, conf).verifyDate, '2026-08-05');

  const hidden = makeContext({ __modes: { verifyDate: 'hidden' } });
  t('使わないなら確認日も入れない',
    hidden.applyFieldConfig_({ confirmDate: '2026-08-01' }, hidden.getFieldConfig_()).verifyDate, '');
}

console.log('\n--- チェックボックスの表記ゆれ ---');
{
  const ctx = makeContext();
  const data = ctx.bulkRowToData_({
    'needs:death': true,       // チェックボックス
    'needs:medical': 'TRUE',   // 文字列
    'needs:cancer': '○',       // 手書き
    'needs:education': false,
    'needs:pension': ''
  });
  t('どの書き方でも拾う', data.needs, ['death', 'medical', 'cancer']);
}

console.log('\n--- 作った帳票は並び順ではなく種類で取り出す ---');
{
  // 適合性確認シートは変額保険のときだけ作る。並び順で参照すると、
  // 変額では2枚が入れ替わり、変額以外では存在しない2枚目を触って落ちる。
  const ctx = makeContext({
    '設定': [['キー', '値', '説明'], ['適合性確認シートが必要な保険種類', '変額', '']]
  });

  // Drive と PDF 化だけを差し替えて、generateAndSave_ を最後まで通す。
  const saved = [];
  ctx.saveOne_ = (folder, templateName, model, fileName, kind) => {
    saved.push({ templateName, fileName, kind });
    return { kind, id: 'id_' + kind, name: fileName + '.pdf', url: 'https://example/' + kind };
  };
  ctx.materializeDestination_ = () => ({ id: 'FOLDER', name: '山田 太郎', created: true });
  ctx.DriveApp = { getFolderById: () => ({ getId: () => 'FOLDER', getUrl: () => 'https://folder' }) };
  const logged = [];
  ctx.appendLog_ = (data, summary, advice, result) => { logged.push(result); };

  const base = {
    contractType: '個人', customerName: '山田 太郎', agency: 'ヒトカチ株式会社',
    author: '佐々木 嶺', agent: '佐々木 嶺', confirmDate: '2026-08-01',
    age: 40, occupation: '会社員', income: 500, assets: 300,
    experience: ['株式'], premiumSource: ['預貯金・給与'],
    riskTolerance: ctx.RISK_YES, needs: ['death'], savings: '①ある方が良い'
  };
  const conf = ctx.getFieldConfig_();
  const run = (productType) => {
    saved.length = 0;
    const data = ctx.applyFieldConfig_(Object.assign({}, base, { productType }), conf);
    return ctx.generateAndSave_(data, 'new', ctx.defaultAnswers_(data));
  };

  console.log('\n--- 変額保険：2枚とも作る ---');
  const both = run('変額保険');
  t('意向把握シートを先に作る', saved.map(f => f.kind), ['intent', 'suitability']);
  t('種類で正しく引ける（適合性）',
    ctx.fileUrlByKind_(both.files, 'suitability'), 'https://example/suitability');
  t('種類で正しく引ける（意向把握）',
    ctx.fileUrlByKind_(both.files, 'intent'), 'https://example/intent');
  t('添字で引くと入れ替わる（回帰の証拠）',
    both.files[0].kind === 'suitability', false);

  console.log('\n--- 医療保険：意向把握シートだけ ---');
  const one = run('医療保険');
  t('作るのは1枚だけ',       saved.map(f => f.kind), ['intent']);
  t('意向把握シートは引ける', ctx.fileUrlByKind_(one.files, 'intent'), 'https://example/intent');
  t('適合性確認シートは空欄', ctx.fileUrlByKind_(one.files, 'suitability'), '');
  t('引けなくても落ちない',   ctx.fileByKind_(one.files, 'suitability'), null);
  t('2枚目は存在しない',      one.files.length, 1);

  console.log('\n--- 送信ログにも正しい順で入る ---');
  t('医療保険でも記録される', logged.length, 2);
  t('記録に使う値が取れる',
    [ctx.fileUrlByKind_(logged[1].files, 'suitability'),
     ctx.fileUrlByKind_(logged[1].files, 'intent')],
    ['', 'https://example/intent']);
}

console.log('\n--- リセットの控えシート ---');
{
  const ctx = makeContext({
    '設定': [['キー', '値', '説明'], ['一括作成の控えを残す枚数', 3, '']]
  });
  // insertSheet / deleteSheet / getSheets だけの、最小のスプレッドシート代役。
  function fakeSpreadsheet(names) {
    const sheets = names.slice();
    return {
      sheets,
      getSheets: () => sheets.map(n => ({ getName: () => n })),
      getSheetByName: n => (sheets.indexOf(n) >= 0 ? { getName: () => n } : null),
      insertSheet(n) { sheets.push(n); return { getName: () => n }; },
      deleteSheet(sh) { sheets.splice(sheets.indexOf(sh.getName()), 1); }
    };
  }
  // 日付を固定して名前を確かめる。
  ctx.Utilities.formatDate = (d, tz, fmt) => (fmt === 'HHmmss' ? '120000' : '2026-09-04');

  const ss1 = fakeSpreadsheet([]);
  t('日付入りの名前になる', ctx.snapshotSheetName_(ss1), '一括作成_2026-09-04');

  const ss2 = fakeSpreadsheet(['一括作成_2026-09-04']);
  t('同じ日の2回目は連番', ctx.snapshotSheetName_(ss2), '一括作成_2026-09-04_2');

  const ss3 = fakeSpreadsheet(['一括作成_2026-09-04', '一括作成_2026-09-04_2']);
  t('3回目も連番',         ctx.snapshotSheetName_(ss3), '一括作成_2026-09-04_3');
  t('既存の控えを上書きしない',
    ['一括作成_2026-09-04', '一括作成_2026-09-04_2']
      .indexOf(ctx.snapshotSheetName_(ss3)), -1);

  console.log('\n--- 古い控えは枚数を超えたら消す ---');
  const many = fakeSpreadsheet([
    '設定', '一括入力', '送信ログ',
    '一括作成_2026-01-10', '一括作成_2026-02-10', '一括作成_2026-03-10',
    '一括作成_2026-04-10', '一括作成_2026-05-10'
  ]);
  const removed = ctx.pruneSnapshots_(many);
  t('古いものから消す', removed, ['一括作成_2026-01-10', '一括作成_2026-02-10']);
  t('残るのは新しい3枚',
    many.sheets.filter(n => n.indexOf('一括作成_') === 0),
    ['一括作成_2026-03-10', '一括作成_2026-04-10', '一括作成_2026-05-10']);
  t('控え以外のシートは触らない',
    many.sheets.filter(n => n.indexOf('一括作成_') !== 0),
    ['設定', '一括入力', '送信ログ']);

  console.log('\n--- 枚数の設定 ---');
  const zero = makeContext({ '設定': [['キー', '値', '説明'], ['一括作成の控えを残す枚数', 0, '']] });
  const ss4 = fakeSpreadsheet(['一括作成_2026-01-10', '一括作成_2026-02-10']);
  t('0 なら消さない', zero.pruneSnapshots_(ss4), []);

  const blank = makeContext({ '設定': [['キー', '値', '説明']] });
  const ss5 = fakeSpreadsheet(
    Array.from({ length: 30 }, (_, i) => '一括作成_2026-01-' + String(i + 1).padStart(2, '0')));
  t('未設定なら既定の24枚まで',
    ss5.sheets.length - blank.pruneSnapshots_(ss5).length, ctx.BULK_SNAPSHOT_KEEP_DEFAULT);
}

console.log('\n--- 状態と行の色 ---');
{
  const ctx = makeContext();
  t('作成済は緑', ctx.ROW_COLORS[ctx.STATUS_DONE], '#e7f4ec');
  t('エラーは赤', ctx.ROW_COLORS[ctx.STATUS_ERROR], '#fdecea');
  t('未作成は色なし', ctx.ROW_COLORS[ctx.STATUS_PENDING], null);
  t('実行時間の余裕は6分未満', ctx.BULK_BUDGET_MS < 6 * 60 * 1000, true);
}

console.log(`\n合計 ${pass + fail} 件 / 成功 ${pass} / 失敗 ${fail}`);
process.exit(fail ? 1 : 0);
