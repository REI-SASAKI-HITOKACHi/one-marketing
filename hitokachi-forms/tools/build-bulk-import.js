#!/usr/bin/env node
/**
 * 過去の帳票から抜き出した記録を、「一括入力」シートに貼り付けられる TSV にする。
 *
 *   node tools/build-bulk-import.js
 *   node tools/build-bulk-import.js --in data/past-intent-records.json --out data/bulk-import.tsv
 *
 * 列の並びは src/Bulk.gs の bulkColumns_() から組み立てるので、シートの列と必ず一致する。
 * 項目を足したり「項目設定」を変えたりしたら、このツールを流し直せば追随する。
 *
 * 意向把握シートから回収できるのは意向まわりだけで、適合性確認シートが求める
 * 年齢・年収・金融資産・投資経験などは埋まらない。埋まらない列は空欄のまま出し、
 * 最後にどの列が未入力かを一覧で示す。担当者はそこだけ埋めればよい。
 */

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.join(__dirname, '..');
const SRC = path.join(ROOT, 'src');

const args = process.argv.slice(2);
const argOf = (name, fallback) => {
  const i = args.indexOf(name);
  return i >= 0 && args[i + 1] ? args[i + 1] : fallback;
};

const IN_FILE  = path.resolve(ROOT, argOf('--in', 'data/past-intent-records.json'));
const OUT_FILE = path.resolve(ROOT, argOf('--out', 'data/bulk-import.tsv'));

/* ---------------------------------------------------------------- *
 * src/*.gs を Node で読み込む（GAS の API は最小限のスタブ）
 * ---------------------------------------------------------------- */

function loadSources() {
  const sheets = {};
  const ctx = {
    console,
    PropertiesService: { getScriptProperties: () => ({ getProperty: () => 'offline' }) },
    SpreadsheetApp: {
      openById: () => ({
        getSheetByName: (name) => sheets[name]
          ? { getDataRange: () => ({ getValues: () => sheets[name] }) }
          : null
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

  // 「項目設定」は FIELD_DEFS の既定値から組み立てる。
  // 実運用でシートを変えている場合は、そちらに合わせて手で直すこと。
  sheets['項目設定'] = [['項目キー', '表示名', 'セクション', '扱い', '固定値', '必須', '選択肢', '備考']]
    .concat(ctx.FIELD_DEFS.map(f =>
      [f.key, f.label, f.section, ctx.MODE_LABELS[f.defaultMode || 'form'], '', !!f.required, '', '']));

  // 代理店・募集人は元データに入っている名前をそのまま出すので、
  // プルダウンの選択肢はここでは空でよい。
  sheets['代理店マスタ'] = [['代理店名', '共有フォルダID', '有効', '備考']];
  sheets['募集人マスタ'] = [['氏名', 'メールアドレス', '電話番号', '郵便番号', '住所1', '住所2', '所属代理店', 'ログイン用アドレス', '有効']];

  return ctx;
}

/* ---------------------------------------------------------------- *
 * 1 レコードを列に割り付ける
 * ---------------------------------------------------------------- */

/**
 * 抽出した記録から、列キー → 値 の対応を作る。
 * ここに書いていない列は空欄のまま（＝担当者が埋める）。
 */
function valuesFor(record) {
  const v = {};
  const put = (k, x) => { if (x !== null && x !== undefined && x !== '') v[k] = x; };

  put('customerName', record.customerName);
  put('agency', record.agency);
  put('agent', record.agent);
  put('confirmDate', record.confirmDateInitial);
  put('finalDate', record.confirmDateFinal);
  put('savings', record.savingsInitial);
  put('wishPeriod', record.wishPeriod);
  put('wishAmount', record.wishAmount);
  put('wishPremium', record.wishPremium);
  put('wishOther', record.wishOther);

  // 当初のご意向を「保障ニーズ」の列に入れる。
  // 最終のご意向は、システム側で空欄なら当初と同じ扱いになる。
  const needs = record.needsInitial || {};
  Object.keys(needs).forEach(k => { if (needs[k]) v['needs:' + k] = true; });

  // 法人のニーズだけが選ばれている記録は法人契約とみなす。
  const corporate = ['business', 'welfare', 'retire'];
  const chosen = Object.keys(needs).filter(k => needs[k]);
  if (chosen.length && chosen.every(k => corporate.indexOf(k) >= 0)) v.contractType = '法人';
  else if (chosen.length) v.contractType = '個人';

  return v;
}

/* ---------------------------------------------------------------- *
 * 実行
 * ---------------------------------------------------------------- */

function main() {
  const ctx = loadSources();
  const cols = ctx.bulkColumns_();

  const header = ['状態', 'メッセージ'].concat(cols.map(c => c.label));

  if (!fs.existsSync(IN_FILE)) {
    console.error(`入力ファイルがありません: ${IN_FILE}`);
    console.error('過去データの抽出がまだなら、見出し行だけを書き出します。');
    write([header]);
    console.log(`\n見出しだけ書き出しました（${cols.length}項目）: ${rel(OUT_FILE)}`);
    return;
  }

  const records = JSON.parse(fs.readFileSync(IN_FILE, 'utf8'));
  if (!Array.isArray(records)) throw new Error('入力ファイルの中身が配列ではありません。');

  const rows = [header];
  const filledCount = {};   // 列キー → 埋まった件数
  cols.forEach(c => { filledCount[c.key] = 0; });

  // 一括では扱えない情報を持つ記録に印を付ける。
  // 何も言わずに落とすと、当初＝最終・意向の変化なしの帳票が黙って出来上がる。
  const warned = [];
  records.forEach(r => {
    const notes = [];
    if (changed(r.needsInitial, r.needsFinal)) {
      notes.push('当初と最終でご意向が変わっています');
    }
    if ((r.changeLog || []).some(c => c && (c.date || c.text))) {
      notes.push('ご意向の変化の記録があります');
    }
    if (notes.length) warned.push({ name: r.customerName, notes });
    r.__warn = notes;
  });

  records.forEach(r => {
    const v = valuesFor(r);
    const warn = r.__warn && r.__warn.length
      ? '【一括では作成しないこと】' + r.__warn.join('・') + '。1件ずつのフォームで作成してください。'
      : '';
    const row = ['', warn + '過去の意向把握シートから取り込み。契約形態は自動推定。適合性の項目は未入力です。'];
    cols.forEach(c => {
      const has = Object.prototype.hasOwnProperty.call(v, c.key);
      if (has) filledCount[c.key]++;
      if (c.kind === 'check') row.push(has && v[c.key] ? 'TRUE' : 'FALSE');
      else row.push(has ? String(v[c.key]) : '');
    });
    rows.push(row);
  });

  write(rows);
  report(ctx, cols, filledCount, records.length, warned);
}

function write(rows) {
  fs.mkdirSync(path.dirname(OUT_FILE), { recursive: true });
  // タブ区切り。スプレッドシートに貼ると列がそのまま揃う。
  const tsv = rows.map(r => r.map(cell =>
    String(cell).replace(/[\t\r\n]/g, ' ')).join('\t')).join('\n');
  fs.writeFileSync(OUT_FILE, tsv + '\n', 'utf8');
}

/** 2つのニーズ表が違うかどうか。 */
function changed(a, b) {
  if (!a || !b) return false;
  return Object.keys(a).some(k => !!a[k] !== !!b[k]);
}

function report(ctx, cols, filledCount, total, warned) {
  const filled = cols.filter(c => filledCount[c.key] > 0);
  const empty  = cols.filter(c => filledCount[c.key] === 0);

  console.log(`\n${total} 件を書き出しました: ${rel(OUT_FILE)}`);

  console.log(`\n■ 過去データから埋まった列（${filled.length}／${cols.length}）`);
  filled.forEach(c => {
    const n = filledCount[c.key];
    const mark = n === total ? '' : `　※${total} 件中 ${n} 件のみ`;
    console.log(`   ${c.label}${mark}`);
  });

  console.log(`\n■ 担当者が埋める必要がある列（${empty.length}）`);
  const isRequired = (col) => {
    const base = col.key.indexOf(':') > 0 ? col.key.slice(0, col.key.indexOf(':')) : col.key;
    const f = ctx.fieldByKey_(base);
    return !!(f && f.required);
  };
  empty.forEach(c => {
    console.log(`   ${isRequired(c) ? '【必須】' : '　　　　'} ${c.label}`);
  });

  if (warned.length) {
    console.log(`\n■ 一括では作成できない記録（${warned.length}／${total}）`);
    console.log('   一括入力シートは「当初のご意向」と「意向の変化」を扱えません。');
    console.log('   次の顧客は、そのまま一括で作ると原本と違う帳票になります。');
    console.log('   メッセージ列に警告を入れてあるので、1件ずつのフォームで作成してください。\n');
    warned.forEach(w => console.log(`   ${w.name}　… ${w.notes.join('・')}`));
  }

  console.log(`
■ 取り込み方
   1. 設定スプレッドシートで、メニュー →「取り込みシートを準備する」
   2. ${rel(OUT_FILE)} の中身を、**見出し行を含めて** A1 から貼り付ける
   3. メニュー →「取り込みシートから流し込む」
   4. 「一括入力」シートに行が増えるので、上の【必須】の列を担当者ごとに埋める
   5. メニュー →「① 保存先を下見する」→「② 未作成の行をすべて作成する」

   列は見出しの文字列で突き合わせるので、並び順がズレていても正しく入る。
   対応する列がない見出しがあれば、何も書き込まずに中止して知らせる。`);
}

function rel(p) { return path.relative(process.cwd(), p) || p; }

main();
