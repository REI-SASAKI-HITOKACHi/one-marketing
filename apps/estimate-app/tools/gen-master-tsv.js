#!/usr/bin/env node
/**
 * マスタ貼り付け用TSVを code.gs / Admin.gs の定義から生成する。
 *
 *   node apps/estimate-app/tools/gen-master-tsv.js
 *
 * 手書きのTSVはコードとすぐズレるので、必ずここから生成すること。
 */
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const srcDir = path.join(__dirname, '..', 'src');
const outDir = path.join(__dirname, '..', 'master');

const sandbox = { console: { log() {} }, JSON: JSON, Math: Math, Date: Date, String: String, Number: Number, Object: Object, Array: Array, isNaN: isNaN, isFinite: isFinite };
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(path.join(srcDir, 'code.gs'), 'utf8'), sandbox, { filename: 'code.gs' });

/**
 * 正規化の中身は Admin.gs が持っている。
 * ここに書き写すとすぐズレるので、Admin.gs をそのまま動かして中身を取り出す。
 * シートに触る関数は差し替えてあるので、本番には一切アクセスしない。
 */
const captured = {};

vm.runInContext(fs.readFileSync(path.join(srcDir, 'Invoice.gs'), 'utf8'), sandbox, { filename: 'Invoice.gs' });
vm.runInContext(fs.readFileSync(path.join(srcDir, 'Admin.gs'), 'utf8'), sandbox, { filename: 'Admin.gs' });

// 差し替えは全ファイルを読み込んだあとに行う（後から読むファイルの宣言に上書きされないように）
sandbox.getMasterSs_ = () => ({ getName: () => '(取り出し用ダミー)', getSheetByName: () => null });
sandbox.clearContextCache_ = () => {};
sandbox.readMailTemplates_ = () => ({});
sandbox.replaceSheetWithNormalized_ = (ss, sheetName, headers, rows) => {
  captured[sheetName] = { headers, rows };
  return '（取り出しのみ）';
};

function fromAdmin(sheetName, runner) {
  captured[sheetName] = null;
  try { runner(); } catch (e) { /* シート書き込み以外で落ちたときは下で気づける */ }
  const got = captured[sheetName];
  if (!got || !got.rows.length) {
    throw new Error('Admin.gs から「' + sheetName + '」の正規化内容を取り出せませんでした。'
      + 'replaceSheetWithNormalized_ の呼び出し方が変わっていないか確認してください。');
  }
  return got;
}

function writeTsv(name, headers, rows) {
  const lines = [headers.join('\t')].concat(rows.map(r => r.map(cell => {
    const s = cell === null || cell === undefined ? '' : String(cell);
    // TSVに改行やタブが混ざると貼り付けで列がずれるため置換する
    return s.replace(/\t/g, ' ').replace(/\r?\n/g, ' ');
  }).join('\t')));

  const file = path.join(outDir, name);
  fs.writeFileSync(file, lines.join('\n') + '\n', 'utf8');
  console.log('  ' + name + '  (' + rows.length + '行)');
}

fs.mkdirSync(outDir, { recursive: true });
console.log('生成:');

/* --- 割引繁忙期マスタ（Admin.gs の adminNormalizeDiscountRules から取得） --- */

const discount = fromAdmin('割引繁忙期マスタ', () => sandbox.adminNormalizeDiscountRules());
writeTsv('割引繁忙期マスタ_正規化.tsv', discount.headers, discount.rows);

/* --- 差し込みセル定義 --- */

writeTsv('差し込みセル定義_正規化.tsv', sandbox.getCellDefHeaders_(), sandbox.getDefaultCellDefinitionRows_());

/* --- 設定マスタ 追加分 --- */

writeTsv('設定マスタ_追加分.tsv', ['設定キー', '設定値', '説明', '備考_現場入力'], [
  ['auto_discount_enabled', 'FALSE', '早期予約割引・複数台割引の自動判定を使うか', 'TRUEにすると自動で割引が載る。現場周知後に切り替えること'],
  ['auto_discount_enabled_web', 'TRUE', 'WEB経由見積で早期予約割引・複数台割引を使うか', '予約フォームと金額を揃えるためON。通常見積は auto_discount_enabled（FALSE）が効く'],
  ['set_pricing_enabled', 'TRUE', '2箇所以上のとき同時施工価格を適用するか', '公開中の予約フォームと金額を揃えるための設定。OFFにするとフォームより高い見積が出る'],
  ['busy_surcharge_tax_included', 'TRUE', '繁忙期加算額が税込で書かれているか', 'TRUEなら課税対象に載せる前に税抜へ戻す。料金表の¥3,300は税込（オーナー確認済み）'],
  ['large_discount_alert_ratio', '0.30', '手動値引きが明細小計のこの割合以上なら警告を出す', ''],
  ['pdf_template_spreadsheet_id', '', 'PDF生成専用テンプレートのスプレッドシートID', '空なら帳票/DBを複製する。adminCreatePdfTemplate()で作成できる'],
  ['line_notice_text', 'メール送信後、LINEで代表者へ一報を入れてください。', '例外時にアプリへ出す文言', ''],
  ['default_closing_day', '月末', '請求締め日の既定値', '提出先マスタに個別指定があればそちらが優先'],
  ['default_payment_site', '翌月末', '支払サイトの既定値', '候補：当月末 / 翌月末 / 翌々月末 / 翌月10日 / 30日 など'],
  ['default_payment_holiday_rule', '', '支払期日が土日のときの調整の既定値', '空 / 前営業日 / 翌営業日。祝日は判定しない'],
  ['parking_tax_type', '課税', '駐車場代の既定の税区分', '請求書作成画面で切り替え可能'],
  ['invoice_remarks_note', '', '請求書の備考に毎回入れる定型文', '振込先はテンプレート側に記載済み']
]);

/* --- 担当者マスタ --- */

writeTsv('担当者マスタ.tsv', sandbox.getStaffHeaders_(), [
  ['TRUE', 'STAFF_01', '渡辺 和真', '', '']
]);

/* --- 提出先マスタ 追加列（請求日・支払期限用） --- */

const CLIENTS = ['自社', 'レジェンド様', '株式会社吉昇エコハウス', '株式会社クラスリフォーム',
  'カインドハウス', '株式会社プレジャー', '株式会社遼', '株式会社タカラサービス',
  '株式会社エル・アップ', '株式会社才木工業', '青山リアルティ・アドバイザーズ株式会社', '株式会社キノビト'];

writeTsv('提出先マスタ_請求条件.tsv',
  ['案件タイプ', '請求締め日', '支払サイト', '支払期日_休日調整'],
  CLIENTS.map(name => [name, '', '', '']));

/* --- 請求条件の書き方の early reference --- */

writeTsv('提出先マスタ_請求条件_記入例.tsv',
  ['請求締め日', '支払サイト', '支払期日_休日調整', '意味'],
  [
    ['月末', '翌月末', '', '月末締め・翌月末払い（空欄のときの既定）'],
    ['月末', '翌々月末', '', '月末締め・翌々月末払い'],
    ['20', '翌月10日', '', '20日締め・翌月10日払い'],
    ['15', '当月25日', '', '15日締め・当月25日払い'],
    ['月末', '翌月10日', '前営業日', '月末締め・翌月10日払い。10日が土日なら前の金曜に繰り上げ'],
    ['月末', '翌月末', '翌営業日', '末日が土日なら翌月曜に繰り下げ'],
    ['月末', '30日', '', '月末締め・請求日から30日後'],
    ['', '', '', '空欄なら設定マスタの既定値を使う']
  ]);

/* --- 設定マスタは Admin.gs 側にも同じ一覧がある。キーの取りこぼしを見張る --- */

const adminSrc = fs.readFileSync(path.join(srcDir, 'Admin.gs'), 'utf8');
const adminBlock = adminSrc.slice(adminSrc.indexOf('function upsertMissingSettings_'));
const adminKeys = (adminBlock.slice(0, adminBlock.indexOf('];')).match(/\['([a-z_]+)',/g) || [])
  .map(m => m.slice(2, -2));

const tsvKeys = fs.readFileSync(path.join(outDir, '設定マスタ_追加分.tsv'), 'utf8')
  .split('\n').slice(1).filter(Boolean).map(l => l.split('\t')[0]);

const missing = adminKeys.filter(k => tsvKeys.indexOf(k) < 0);
if (missing.length) {
  console.error('\n❌ Admin.gs にあって 設定マスタ_追加分.tsv に無い設定キー： ' + missing.join(', '));
  console.error('   gen-master-tsv.js の設定マスタ一覧に足してください。');
  process.exit(1);
}

console.log('\n完了。master/ 配下のTSVをスプレッドシートに貼り付けてください。');
