/**
 * 設定スプレッドシートの読み取りテスト。
 *
 * シート上は日本語（入力する／固定値を使う／使わない）で見せて、コードの中では
 * form / fixed / hidden として扱う。その変換と、英語表記だった頃のシートも
 * そのまま読めることを確かめる。
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const SRC = path.join(__dirname, '..', 'src');

/**
 * 見出し行つきの二次元配列を返すだけの、最小のスプレッドシート代役。
 * onRead を渡すと、シートを実際に読んだ回数を数えられる。
 */
function makeContext(sheets, onRead) {
  const ctx = {
    console,
    PropertiesService: {
      getScriptProperties: () => ({ getProperty: () => 'dummy-id' })
    },
    SpreadsheetApp: {
      openById: () => ({
        getSheetByName(name) {
          if (!sheets[name]) return null;
          return { getDataRange: () => ({ getValues: () => {
            if (onRead) onRead(name);
            return sheets[name];
          } }) };
        }
      })
    }
  };
  vm.createContext(ctx);
  for (const f of ['Fields.gs', 'Config.gs']) {
    vm.runInContext(fs.readFileSync(path.join(SRC, f), 'utf8'), ctx, { filename: f });
  }
  return ctx;
}

let pass = 0, fail = 0;
function t(name, actual, expected) {
  const ok = JSON.stringify(actual) === JSON.stringify(expected);
  ok ? pass++ : fail++;
  console.log((ok ? '  ok  ' : '  NG  ') + name +
    (ok ? '' : `\n        期待=${JSON.stringify(expected)} 実際=${JSON.stringify(actual)}`));
}

const FIELD_HEADER = ['項目キー', '表示名', 'セクション', '扱い', '固定値', '必須', '選択肢', '備考'];

console.log('\n--- 「扱い」列の日本語表記 ---');
{
  const ctx = makeContext({
    '項目設定': [
      FIELD_HEADER,
      ['age', '年齢', '適合性', '入力する', '', true, '', ''],
      ['agency', '取扱代理店', '基本', '固定値を使う', 'ヒトカチ株式会社', true, '', ''],
      ['verifyDate', '検証日', '検証欄', '使わない', '', false, '', '']
    ]
  });
  const conf = ctx.getFieldConfig_();
  t('入力する → form',      conf.age.mode, 'form');
  t('固定値を使う → fixed', conf.agency.mode, 'fixed');
  t('使わない → hidden',    conf.verifyDate.mode, 'hidden');
  t('固定値が読める',        conf.agency.fixedValue, 'ヒトカチ株式会社');
}

console.log('\n--- 英語表記の古いシートも読める ---');
{
  const ctx = makeContext({
    '項目設定': [
      ['項目キー', '表示名', 'セクション', 'モード', '固定値', '必須', '選択肢', '備考'],
      ['age', '年齢', '適合性', 'form', '', true, '', ''],
      ['agency', '取扱代理店', '基本', 'fixed', 'ヒトカチ株式会社', true, '', ''],
      ['verifyDate', '検証日', '検証欄', 'hidden', '', false, '', '']
    ]
  });
  const conf = ctx.getFieldConfig_();
  t('form',   conf.age.mode, 'form');
  t('fixed',  conf.agency.mode, 'fixed');
  t('hidden', conf.verifyDate.mode, 'hidden');
}

console.log('\n--- 未知の値や空欄は既定値のまま ---');
{
  const ctx = makeContext({
    '項目設定': [
      FIELD_HEADER,
      ['age', '年齢', '適合性', 'あいうえお', '', true, '', ''],
      ['verifyDate', '検証日', '検証欄', '', '', false, '', '']
    ]
  });
  const conf = ctx.getFieldConfig_();
  t('打ち間違いは既定値(form)を保つ',  conf.age.mode, 'form');
  t('空欄も既定値(hidden)を保つ',      conf.verifyDate.mode, 'hidden');
  t('シートにない項目も既定値が入る',  conf.customerName.mode, 'form');
}

console.log('\n--- チェックボックスだけの空行を拾わない ---');
{
  const ctx = makeContext({
    '代理店マスタ': [
      ['代理店名', '共有フォルダID', '有効', '備考'],
      ['ヒトカチ株式会社', 'FOLDER_A', true, ''],
      ['提携代理店B', 'FOLDER_B', true, ''],
      ['提携代理店C', 'FOLDER_C', false, '契約終了'],
      ['', '', false, ''],   // 先回りで入れたチェックボックスだけの行
      ['', '', false, '']
    ]
  });
  const list = ctx.getAgencies_();
  t('有効な代理店だけ返る', list.map(a => a.name), ['ヒトカチ株式会社', '提携代理店B']);
  t('フォルダIDが読める',   ctx.getAgencyByName_('提携代理店B').folderId, 'FOLDER_B');
  t('無効な代理店は返らない', ctx.getAgencyByName_('提携代理店C'), null);
}

console.log('\n--- 代理店ごとの募集人（共同募集の相手） ---');
{
  const ctx = makeContext({
    '代理店マスタ': [
      ['代理店名', '共有フォルダID', '有効', '備考'],
      ['ヒトカチ株式会社', 'FOLDER_A', true, ''],
      ['クレスト保険', 'FOLDER_B', true, ''],
      ['契約終了代理店', 'FOLDER_C', false, '']
    ],
    '代理店募集人マスタ': [
      ['代理店名', '氏名', '有効', '備考'],
      ['クレスト保険', '熊澤 善弘', true, ''],
      ['クレスト保険', '小川 康之', true, ''],
      ['クレスト保険', '矢野 克臣', true, ''],
      ['クレスト保険', '熊澤 善弘', true, '二重登録'],
      ['クレスト保険', '退職 済', false, ''],
      ['契約終了代理店', '無効 代理店の人', true, ''],
      ['', '', false, ''],              // チェックボックスだけの空行
      ['クレスト保険', '', true, '']    // 氏名が空
    ]
  });
  const byName = n => ctx.getAgencyByName_(n);
  t('1代理店に何人でもぶら下がる',
    byName('クレスト保険').coAgents, ['熊澤 善弘', '小川 康之', '矢野 克臣']);
  t('二重登録は1つにまとまる',
    byName('クレスト保険').coAgents.filter(x => x === '熊澤 善弘').length, 1);
  t('無効な人は出ない', byName('クレスト保険').coAgents.indexOf('退職 済'), -1);
  t('氏名が空の行は無視する', byName('クレスト保険').coAgents.indexOf(''), -1);
  t('登録がない代理店は空配列', byName('ヒトカチ株式会社').coAgents, []);
  t('無効な代理店は returns null のまま', byName('契約終了代理店'), null);
}

console.log('\n--- 代理店名の表記ゆれで募集人が消えない ---');
{
  const ctx = makeContext({
    '代理店マスタ': [
      ['代理店名', '共有フォルダID', '有効', '備考'],
      ['クレスト保険', 'FOLDER_B', true, '']
    ],
    '代理店募集人マスタ': [
      ['代理店名', '氏名', '有効', '備考'],
      ['クレスト保険 ', '熊澤 善弘', true, '末尾に半角スペース'],
      ['　クレスト保険', '小川 康之', true, '先頭に全角スペース'],
      ['クレスト　保険', '矢野 克臣', true, '間に全角スペース'],
      ['クレスト生命', '別会社 の人', true, '本当に別の代理店']
    ]
  });
  t('空白のゆれは吸収する',
    ctx.getAgencyByName_('クレスト保険').coAgents, ['熊澤 善弘', '小川 康之', '矢野 克臣']);
  t('別の代理店名は結び付けない',
    ctx.getAgencyByName_('クレスト保険').coAgents.indexOf('別会社 の人'), -1);

  console.log('\n--- 結び付かない行は setup() が知らせる ---');
  t('結び付かない行を拾う', ctx.orphanCoAgents_(), [{ agency: 'クレスト生命', name: '別会社 の人' }]);
}

console.log('\n--- 代理店募集人マスタが無い設定スプレッドシートでも動く ---');
{
  // シートを作る前の状態。ここで落ちると setup() 前に何も表示できなくなる。
  const ctx = makeContext({
    '代理店マスタ': [
      ['代理店名', '共有フォルダID', '有効', '備考'],
      ['ヒトカチ株式会社', 'FOLDER_A', true, '']
    ]
  });
  t('例外にならない', ctx.getAgencies_().length, 1);
  t('相方は空配列',   ctx.getAgencies_()[0].coAgents, []);
}

console.log('\n--- マスタは1回の実行で読み直さない ---');
{
  let reads = 0;
  const ctx = makeContext({
    '代理店マスタ': [
      ['代理店名', '共有フォルダID', '有効', '備考'],
      ['ヒトカチ株式会社', 'FOLDER_A', true, '']
    ]
  }, () => { reads++; });
  ctx.getAgencies_();
  const first = reads;
  ctx.getAgencies_(); ctx.getAgencyByName_('ヒトカチ株式会社');
  t('2回目からはシートを読み直さない', reads, first);
  ctx.clearMasterCache_();
  ctx.getAgencies_();
  t('キャッシュを捨てれば読み直す', reads > first, true);
}

console.log('\n--- 有効・無効の表記ゆれ ---');
{
  const ctx = makeContext({ '利用者': [] });
  const isTrue = ctx.isTrue_;
  t('チェックボックスのtrue', isTrue(true), true);
  t('文字列のTRUE',           isTrue('TRUE'), true);
  t('はい',                   isTrue('はい'), true);
  t('○',                      isTrue('○'), true);
  t('チェックボックスのfalse', isTrue(false), false);
  t('いいえ',                  isTrue('いいえ'), false);
  t('空欄',                    isTrue(''), false);
}

console.log('\n--- 利用者の許可リスト ---');
{
  const ctx = makeContext({
    '利用者': [
      ['メールアドレス', '氏名', '有効', '備考'],
      ['Info@Hitokachi.com', 'オーナー', true, ''],
      ['taro@example.com', '退職者', false, ''],
      ['', '', false, '']
    ]
  });
  t('有効なアドレスだけ・小文字化される', ctx.getAllowedEmails_(), ['info@hitokachi.com']);
}

console.log('\n--- 設定シートの単一値 ---');
{
  const ctx = makeContext({
    '設定': [
      ['キー', '値', '説明'],
      ['アクセス制限', 'はい', ''],
      ['画面タイトル', '', ''],
      ['', '', '']
    ]
  });
  t('値が読める',              ctx.getSetting_('アクセス制限', 'いいえ'), 'はい');
  t('アクセス制限が有効',       ctx.isTrue_(ctx.getSetting_('アクセス制限', 'いいえ')), true);
  t('空欄なら既定値',          ctx.getSetting_('画面タイトル', '帳票作成'), '帳票作成');
  t('キーがなければ既定値',     ctx.getSetting_('存在しないキー', '既定'), '既定');
}

console.log(`\n合計 ${pass + fail} 件 / 成功 ${pass} / 失敗 ${fail}`);
process.exit(fail ? 1 : 0);
