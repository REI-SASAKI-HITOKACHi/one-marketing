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

/** 見出し行つきの二次元配列を返すだけの、最小のスプレッドシート代役。 */
function makeContext(sheets) {
  const ctx = {
    console,
    PropertiesService: {
      getScriptProperties: () => ({ getProperty: () => 'dummy-id' })
    },
    SpreadsheetApp: {
      openById: () => ({
        getSheetByName(name) {
          if (!sheets[name]) return null;
          return { getDataRange: () => ({ getValues: () => sheets[name] }) };
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
