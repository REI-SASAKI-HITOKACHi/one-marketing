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

const sandbox = { console: console, JSON: JSON, Math: Math, Date: Date, String: String, Number: Number, Object: Object, Array: Array, isNaN: isNaN, isFinite: isFinite };
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(path.join(srcDir, 'code.gs'), 'utf8'), sandbox, { filename: 'code.gs' });

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

/* --- 割引繁忙期マスタ --- */

writeTsv('割引繁忙期マスタ_正規化.tsv', sandbox.getDiscountHeaders_(), [
  ['TRUE', 'BUSY_05_07', '繁忙期', '全体', 5, 7, '', 3300, '金額', 10, '5月〜7月。メインメニューの数量ごとに加算'],
  ['TRUE', 'BUSY_12', '繁忙期', '全体', 12, 12, '', 3300, '金額', 10, '12月。メインメニューの数量ごとに加算'],
  ['TRUE', 'EARLY_01_02', '早期予約割引', '全体', 1, 2, '', 0.15, '率', 20, '1月〜2月：15%'],
  ['TRUE', 'EARLY_03_04', '早期予約割引', '全体', 3, 4, '', 0.10, '率', 20, '3月〜4月：10%'],
  ['TRUE', 'EARLY_08_10', '早期予約割引', '全体', 8, 10, '', 0.10, '率', 20, '8月〜10月：10%'],
  ['TRUE', 'MULTI_NORMAL_05_10', '複数台割引', 'ノーマルエアコン', '', '', 'totalQty:5-10', 500, '金額/台', 30, '総台数で判定'],
  ['TRUE', 'MULTI_NORMAL_11_20', '複数台割引', 'ノーマルエアコン', '', '', 'totalQty:11-20', 1000, '金額/台', 30, '総台数で判定'],
  ['TRUE', 'MULTI_NORMAL_21_50', '複数台割引', 'ノーマルエアコン', '', '', 'totalQty:21-50', 1500, '金額/台', 30, '総台数で判定'],
  ['TRUE', 'MULTI_ROBO_05_10', '複数台割引', 'ロボ付きエアコン', '', '', 'totalQty:5-10', 1000, '金額/台', 30, '総台数で判定'],
  ['TRUE', 'MULTI_ROBO_11_20', '複数台割引', 'ロボ付きエアコン', '', '', 'totalQty:11-20', 1500, '金額/台', 30, '総台数で判定'],
  ['TRUE', 'MULTI_ROBO_21_50', '複数台割引', 'ロボ付きエアコン', '', '', 'totalQty:21-50', 2000, '金額/台', 30, '総台数で判定'],
  ['TRUE', 'MULTI_BUSINESS_02_10', '複数台割引', '業務用エアコン', '', '', 'totalQty:2-10', 5000, '金額/台', 30, '総台数で判定'],
  ['TRUE', 'MULTI_BUSINESS_11_20', '複数台割引', '業務用エアコン', '', '', 'totalQty:11-20', 6000, '金額/台', 30, '総台数で判定'],
  ['TRUE', 'MULTI_BUSINESS_21_50', '複数台割引', '業務用エアコン', '', '', 'totalQty:21-50', 7000, '金額/台', 30, '総台数で判定'],
  ['FALSE', 'INTRO_01_02', '紹介料', '全体', 1, 2, '', 0.05, '率', 90, '顧客割引か紹介元支払か未確定のため計算対象外'],
  ['FALSE', 'INTRO_OTHER', '紹介料', '全体', 3, 12, '', 0.10, '率', 90, '顧客割引か紹介元支払か未確定のため計算対象外']
]);

/* --- 差し込みセル定義 --- */

writeTsv('差し込みセル定義_正規化.tsv', sandbox.getCellDefHeaders_(), sandbox.getDefaultCellDefinitionRows_());

/* --- 設定マスタ 追加分 --- */

writeTsv('設定マスタ_追加分.tsv', ['設定キー', '設定値', '説明', '備考_現場入力'], [
  ['auto_discount_enabled', 'FALSE', '早期予約割引・複数台割引の自動判定を使うか', 'TRUEにすると自動で割引が載る。現場周知後に切り替えること'],
  ['large_discount_alert_ratio', '0.30', '手動値引きが明細小計のこの割合以上なら警告を出す', ''],
  ['pdf_template_spreadsheet_id', '', 'PDF生成専用テンプレートのスプレッドシートID', '空なら帳票/DBを複製する。adminCreatePdfTemplate()で作成できる'],
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

console.log('\n完了。master/ 配下のTSVをスプレッドシートに貼り付けてください。');
