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
const AGENTS = [
  ['氏名', 'メールアドレス', '電話番号', '郵便番号', '住所1', '住所2', '所属代理店', 'ログイン用アドレス', '有効'],
  ['佐々木 嶺', 'info@hitokachi.com', '080-6817-4796', '134-0081', '東京都 江戸川区 北葛西', '５－１４－１１', 'ヒトカチ株式会社', '', true],
  ['髙橋 知史', 's-takahashi@hitokachi.com', '080-2238-7592', '134-0081', '東京都 江戸川区 北葛西', '５－１４－１１', 'ヒトカチ株式会社', '', true]
];

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
  const sheets = Object.assign({ '代理店マスタ': AGENCIES, '募集人マスタ': AGENTS }, extraSheets);
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
  for (const f of ['Fields.gs', 'Config.gs', 'Judge.gs', 'Render.gs', 'Generate.gs', 'DriveUtil.gs', 'Bulk.gs']) {
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
  t('原資アはチェックボックス',    byKey('sourceNotMaturity').kind, 'check');

  t('既定で使わない項目は列にならない（検証日）', byKey('verifyDate'), undefined);
  t('既定で使わない項目は列にならない（推定意向）',
    keys.filter(k => k.indexOf('estimatedNeeds') === 0).length, 0);
  t('意向の変化は一括では扱わない', byKey('changeLog'), undefined);
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
  const ctx = makeContext();
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

  const m = ctx.buildModel_(applied, j, ctx.getAgentByName_('佐々木 嶺'), 'ヒトカチ株式会社');
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
