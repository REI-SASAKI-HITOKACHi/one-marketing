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
      ['guardianName', '親権者氏名', '基本', '', '', false, '', '']
    ]
  });
  const conf = ctx.getFieldConfig_();
  t('打ち間違いは既定値(form)を保つ',  conf.age.mode, 'form');
  t('空欄も既定値(hidden)を保つ',      conf.guardianName.mode, 'hidden');
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

console.log('\n--- 共有フォルダIDは URL のまま貼っても通る ---');
{
  const ctx = makeContext({
    '代理店マスタ': [
      ['代理店名', '共有フォルダID', '有効', '備考'],
      ['URL貼り付け', 'https://drive.google.com/drive/folders/1QFFYl1U4MXe_Gi_D6SBfKoAIkMfHPIl9?usp=drive_link', true, ''],
      ['クエリなし', 'https://drive.google.com/drive/folders/1AnxGMvz_4nzjPnJG3cZMSDF', true, ''],
      ['IDだけ',     '1pK6ChGD2wsQehpHOOfwZ7dbgTY2lXhz6', true, ''],
      ['前後に空白',  '  1vvz_SiAb0VtFh4npYbFsSj4rVS7eUIs7  ', true, ''],
      ['旧形式',     'https://drive.google.com/open?id=10GUIYnDJtxso_xLutp7tlRlHdPe6-gIP', true, ''],
      ['空欄',       '', true, '']
    ]
  });
  const id = n => ctx.getAgencyByName_(n).folderId;
  t('URL からIDを取り出す',   id('URL貼り付け'), '1QFFYl1U4MXe_Gi_D6SBfKoAIkMfHPIl9');
  t('クエリが無くても取れる', id('クエリなし'),  '1AnxGMvz_4nzjPnJG3cZMSDF');
  t('IDだけならそのまま',     id('IDだけ'),      '1pK6ChGD2wsQehpHOOfwZ7dbgTY2lXhz6');
  t('前後の空白は落とす',     id('前後に空白'),  '1vvz_SiAb0VtFh4npYbFsSj4rVS7eUIs7');
  t('旧形式の open?id= も取れる', id('旧形式'),  '10GUIYnDJtxso_xLutp7tlRlHdPe6-gIP');
  t('空欄は空欄のまま',       id('空欄'),        '');
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

console.log('\n--- 検証実施者は作成者から決まる ---');
{
  const AGENTS_HEADER = ['氏名', 'メールアドレス', '電話番号', '郵便番号', '住所1', '住所2',
    '所属代理店', 'ログイン用アドレス', '検証者', '有効'];
  const ctx = makeContext({
    '設定': [['キー', '値', '説明'], ['既定の検証実施者', '髙橋 知史', '']],
    '募集人マスタ': [
      AGENTS_HEADER,
      ['佐々木 嶺', 'info@hitokachi.com', '', '', '', '', 'ヒトカチ株式会社', '', '', true],
      // 既定の検証実施者その人。自分を検証できないので、行に検証者を持たせる。
      ['髙橋 知史', 's-takahashi@hitokachi.com', '', '', '', '', 'ヒトカチ株式会社', '', '佐々木 嶺', true],
      ['青木 典子', '', '', '', '', '', 'ヒトカチ株式会社', '', '', true],
      // あとから足した募集人。設定は要らず、自動で既定の人が検証者になる。
      ['新人 太郎', 'shinjin@hitokachi.com', '', '', '', '', 'ヒトカチ株式会社', '', '', true],
      // 自分を検証者にしても、自己検証にはしない。
      ['自己 検証', '', '', '', '', '', 'ヒトカチ株式会社', '', '自己 検証', true]
    ]
  });
  const v = n => ctx.verifierFor_(n);
  t('髙橋以外が作成 → 髙橋',       v('佐々木 嶺'), '髙橋 知史');
  t('青木が作成 → 髙橋',           v('青木 典子'), '髙橋 知史');
  t('髙橋が作成 → 佐々木',         v('髙橋 知史'), '佐々木 嶺');
  t('あとから足した人も髙橋',      v('新人 太郎'), '髙橋 知史');
  t('自分は自分を検証できない',    v('自己 検証'), '');
  t('作成者が空なら空',            v(''), '');
  t('決まらない人を setup が拾う', ctx.agentsWithoutVerifier_(), ['自己 検証']);

  t('ログイン中の人を作成者に',
    (ctx.getAgentByEmail_('s-takahashi@hitokachi.com') || {}).name, '髙橋 知史');
  t('大文字小文字は無視',
    (ctx.getAgentByEmail_('INFO@Hitokachi.com') || {}).name, '佐々木 嶺');
  t('知らないアドレスは null', ctx.getAgentByEmail_('nobody@example.com'), null);
}

console.log('\n--- 募集人の選択肢は代理店で決まる ---');
{
  const ctx = makeContext({
    '代理店マスタ': [
      ['代理店名', '共有フォルダID', '有効', '備考'],
      ['ヒトカチ株式会社', 'F1', true, ''],
      ['提携代理店B',     'F2', true, ''],
      ['登録なし代理店',   'F3', true, '']
    ],
    '募集人マスタ': [
      ['氏名', 'メールアドレス', '電話番号', '郵便番号', '住所1', '住所2',
       '所属代理店', 'ログイン用アドレス', '検証者', '有効'],
      ['佐々木 嶺', '', '', '', '', '', 'ヒトカチ株式会社', '', '', true],
      ['髙橋 知史', '', '', '', '', '', 'ヒトカチ株式会社', '', '', true],
      ['退職 済',   '', '', '', '', '', 'ヒトカチ株式会社', '', '', false]
    ],
    '代理店募集人マスタ': [
      ['代理店名', '氏名', '有効', '備考'],
      ['提携代理店B', '熊澤 善弘', true,  ''],
      ['提携代理店B', '小川 康之', true,  ''],
      ['提携代理店B', '退職 済',   false, '']
    ]
  });
  const forAgency = n => ctx.agentNamesForAgency_(n);
  t('自社なら募集人マスタの所属者', forAgency('ヒトカチ株式会社'), ['佐々木 嶺', '髙橋 知史']);
  t('提携先なら代理店募集人マスタ', forAgency('提携代理店B'), ['熊澤 善弘', '小川 康之']);
  t('無効な人は出ない',             forAgency('ヒトカチ株式会社').indexOf('退職 済'), -1);
  t('提携先でも無効な人は出ない',   forAgency('提携代理店B').indexOf('退職 済'), -1);
  t('登録がなければ空',             forAgency('登録なし代理店'), []);
  t('代理店が未選択なら空',         forAgency(''), []);
  t('知らない代理店でも落ちない',   forAgency('そんな代理店はない'), []);
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
