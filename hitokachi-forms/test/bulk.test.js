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
  ['提携代理店B', 'FOLDER_B', true, '']
];
/** 代理店ごとの共同募集の相手。1人1行。 */
const CO_AGENTS = [
  ['代理店名', '氏名', '有効', '備考'],
  ['提携代理店B', '熊澤 善弘', true, ''],
  ['提携代理店B', '小川 康之', true, ''],
  ['提携代理店B', '退職 済', false, '無効なので選択肢に出ない'],
  ['存在しない代理店', '幽霊 太郎', true, '代理店マスタに無いので無視される']
];
const AGENTS = [
  ['氏名', 'メールアドレス', '電話番号', '郵便番号', '住所1', '住所2', '所属代理店', 'ログイン用アドレス', '有効'],
  ['佐々木 嶺', 'info@hitokachi.com', '080-6817-4796', '134-0081', '東京都 江戸川区 北葛西', '５－１４－１１', 'ヒトカチ株式会社', '', true],
  ['髙橋 知史', 's-takahashi@hitokachi.com', '080-2238-7592', '134-0081', '東京都 江戸川区 北葛西', '５－１４－１１', 'ヒトカチ株式会社', '', true]
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
  t('代理店の選択肢はマスタから', byKey('agency').options, ['ヒトカチ株式会社', '提携代理店B']);
  t('募集人の選択肢もマスタから', byKey('agent').options, ['佐々木 嶺', '髙橋 知史']);
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
    agent: '佐々木 嶺',
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
    agent: '佐々木 嶺', confirmDate: '2026-08-01',
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
    agent: '佐々木 嶺', confirmDate: '2026-08-01',
    experience: [], premiumSource: [],
    riskTolerance: ctx.RISK_YES, needs: ['business'], savings: '②なくても良い'
  };
  const corpErrors = ctx.validate_(ctx.applyFieldConfig_(corp, conf), conf);
  t('年齢・年収なしでも通る', corpErrors, []);
  t('個人契約なら同じ入力は弾かれる',
    ctx.validate_(ctx.applyFieldConfig_(Object.assign({}, corp, { contractType: '個人' }), conf), conf).length > 0, true);
}

console.log('\n--- 検証：共同募集の相方 ---');
{
  const ctx = makeContext();
  const conf = ctx.getFieldConfig_();
  const base = {
    contractType: '個人', customerName: '山田 太郎', agency: '提携代理店B',
    agent: '佐々木 嶺', confirmDate: '2026-08-01',
    age: 40, occupation: '会社員', occupationClass: '左記以外',
    income: 500, assets: 100, annualPremium: 80, payYears: 10,
    experience: ['株式'], premiumSource: ['預貯金・給与'],
    sourceNotMaturity: true, sourceSpare: true, sourceNotLoan: true,
    riskTolerance: ctx.RISK_YES, needs: ['death'], savings: '①ある方が良い'
  };
  const check = (over) => ctx.validate_(ctx.applyFieldConfig_(Object.assign({}, base, over), conf), conf);

  t('空欄（単独募集）は通る', check({ coAgent: '' }), []);
  t('その代理店の募集人なら通る', check({ coAgent: '熊澤 善弘' }), []);
  t('別の代理店の募集人は弾く',
    check({ agency: 'ヒトカチ株式会社', coAgent: '熊澤 善弘' })
      .some(e => e.indexOf('登録されていません') >= 0), true);
  t('マスタにない名前は弾く',
    check({ coAgent: '存在 しない' }).some(e => e.indexOf('登録されていません') >= 0), true);
  t('募集人と同じ人は弾く',
    check({ coAgent: '佐々木 嶺' }).some(e => e.indexOf('同じ人は選べません') >= 0), true);
  t('法人契約でも組み合わせは見る',
    check({ contractType: '法人', agency: 'ヒトカチ株式会社', coAgent: '小川 康之' })
      .some(e => e.indexOf('登録されていません') >= 0), true);

  console.log('\n--- 一括入力シートの相方の選択肢 ---');
  const opts = ctx.bulkOptionsFor_(ctx.FIELD_DEFS.filter(f => f.key === 'coAgent')[0]);
  t('列としての選択肢は持たない（行ごとに作る）', opts, []);

  const co = n => (ctx.getAgencyByName_(n) || {}).coAgents;
  t('代理店ごとに相方が引ける', co('提携代理店B'), ['熊澤 善弘', '小川 康之']);
  t('無効な行は選択肢に出ない', co('提携代理店B').indexOf('退職 済'), -1);
  t('相方がいない代理店は空', co('ヒトカチ株式会社'), []);

  console.log('\n--- 連名の印字 ---');
  const solo = ctx.applyFieldConfig_(base, conf);
  const pair = ctx.applyFieldConfig_(Object.assign({}, base, { coAgent: '熊澤 善弘' }), conf);
  const agent = ctx.getAgentByName_('佐々木 嶺');
  t('単独なら自社の募集人だけ',
    ctx.buildModel_(solo, ctx.defaultAnswers_(solo), agent, '提携代理店B').agentDisplay, '佐々木 嶺');
  t('共同募集なら連名になる',
    ctx.buildModel_(pair, ctx.defaultAnswers_(pair), agent, '提携代理店B').agentDisplay,
    '佐々木 嶺 / 熊澤 善弘');
}

console.log('\n--- 代理店を選ぶと、その行の相方の選択肢が入れ替わる ---');
{
  /**
   * 一括入力シートの代役。refreshCoAgentValidation_ が触るぶんだけ。
   * grid は 1 始まりの [行][列]。validations[行] に、その行の相方セルへ
   * 張られた選択肢が入る（null なら選べない状態）。
   */
  function fakeBulkSheet(keys, rows) {
    // 1行目=列キー, 2行目=見出し, 3行目以降=データ（実物と同じ並び）。
    const grid = [null, keys.slice(), keys.map(() => '')].concat(rows.map(r => r.slice()));
    const validations = {};
    const colOf = k => keys.indexOf(k) + 1;
    const cell = (r, c) => ({
      getValues: () => [[grid[r] ? (grid[r][c - 1] === undefined ? '' : grid[r][c - 1]) : '']],
      setDataValidation(v) { if (c === colOf('coAgent')) validations[r] = v; },
      clearContent() { if (grid[r]) grid[r][c - 1] = ''; }
    });
    return {
      grid, validations,
      getName: () => '一括入力',
      getLastColumn: () => keys.length,
      getMaxRows: () => grid.length - 1,
      getRange(row, col, numRows, numCols) {
        // getRange(row, col) の 2 引数呼び出しも 1 セルとして扱う。
        if ((numRows === undefined || numRows === 1)
            && (numCols === undefined || numCols === 1)) return cell(row, col);
        const vals = [];
        for (let i = 0; i < (numRows || 1); i++) {
          const r = grid[row + i] || [];
          const line = [];
          for (let j = 0; j < (numCols || 1); j++) {
            line.push(r[col + j - 1] === undefined ? '' : r[col + j - 1]);
          }
          vals.push(line);
        }
        return { getValues: () => vals, setDataValidation() {}, clearContent() {} };
      }
    };
  }

  const ctx = makeContext();
  // 選択肢リストだけ取り出せる、最小の DataValidation ビルダー。
  ctx.SpreadsheetApp.newDataValidation = () => {
    let list = null;
    const b = {
      requireValueInList(v) { list = v.slice(); return b; },
      setAllowInvalid() { return b; },
      build: () => ({ list })
    };
    return b;
  };

  const KEYS = ['__status', '__message', 'customerName', 'agency', 'coAgent'];
  const listAt = (sh, row) => (sh.validations[row] || {}).list || null;

  const sh = fakeBulkSheet(KEYS, [
    ['', '', '山田 太郎', '提携代理店B', ''],
    ['', '', '鈴木 花子', 'ヒトカチ株式会社', ''],
    ['', '', '佐藤 次郎', '', '']
  ]);
  ctx.refreshCoAgentValidation_(sh);
  t('相方がいる代理店の行には選択肢が張られる', listAt(sh, 3), ['熊澤 善弘', '小川 康之']);
  t('相方がいない代理店の行は選べない',         listAt(sh, 4), null);
  t('代理店が未選択の行も選べない',             listAt(sh, 5), null);

  console.log('\n--- 代理店を選び直すと、前の代理店の人は消える ---');
  const sh2 = fakeBulkSheet(KEYS, [
    ['', '', '山田 太郎', 'ヒトカチ株式会社', '熊澤 善弘']  // 代理店だけ差し替えた状態
  ]);
  ctx.refreshCoAgentValidation_(sh2);
  t('他社の募集人が残らない', sh2.grid[3][4], '');
  t('選択肢も外れる',         listAt(sh2, 3), null);

  const sh3 = fakeBulkSheet(KEYS, [
    ['', '', '山田 太郎', '提携代理店B', '小川 康之']  // 同じ代理店のまま
  ]);
  ctx.refreshCoAgentValidation_(sh3);
  t('同じ代理店のままなら選択は残る', sh3.grid[3][4], '小川 康之');

  console.log('\n--- 編集された行だけ作り直す ---');
  const sh4 = fakeBulkSheet(KEYS, [
    ['', '', 'A', '提携代理店B', ''],
    ['', '', 'B', '提携代理店B', ''],
    ['', '', 'C', '提携代理店B', '']
  ]);
  ctx.refreshCoAgentValidation_(sh4, 4, 1);   // 2行目だけ
  t('指定した行だけ張られる', listAt(sh4, 4), ['熊澤 善弘', '小川 康之']);
  t('ほかの行は触らない',     [listAt(sh4, 3), listAt(sh4, 5)], [null, null]);

  console.log('\n--- 代理店か相方の列を「使わない」にしていても落ちない ---');
  const sh5 = fakeBulkSheet(['__status', '__message', 'customerName', 'agency'], [
    ['', '', '山田 太郎', '提携代理店B']
  ]);
  let threw = false;
  try { ctx.refreshCoAgentValidation_(sh5); } catch (e) { threw = true; }
  t('例外にならない', threw, false);
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
    agent: '佐々木 嶺', confirmDate: '2026-08-01',
    needs: ['death'], savings: '①ある方が良い'
  };
  const check = (over) => ctx.validate_(ctx.applyFieldConfig_(Object.assign({}, thin, over), conf), conf);

  t('医療保険なら適合性の入力を求めない', check({ productType: '医療保険' }), []);
  t('終身保険も同じ',                     check({ productType: '終身保険' }), []);
  t('変額保険なら適合性の入力を求める',    check({ productType: '変額保険' }).length > 0, true);
  t('求めるのは年齢・年収など',
    check({ productType: '変額保険' }).some(e => e.indexOf('年収') >= 0), true);
  t('保険種類が空欄なら求める側に倒す',    check({ productType: '' }).length > 0, true);

  console.log('\n--- 適合性が要らない行でも意向は必須のまま ---');
  t('ご希望の保障分野は必須',
    check({ productType: '医療保険', needs: [] }).some(e => e.indexOf('ご希望の保障分野') >= 0), true);
  t('契約者氏名も必須',
    check({ productType: '医療保険', customerName: '' }).some(e => e.indexOf('契約者氏名') >= 0), true);

  console.log('\n--- 保険種類は一括入力シートの列になる ---');
  const cols = ctx.bulkColumns_();
  t('保険種類の列がある', cols.filter(c => c.key === 'productType').length, 1);
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
