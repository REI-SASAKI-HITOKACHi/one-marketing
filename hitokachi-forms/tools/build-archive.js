#!/usr/bin/env node
/**
 * 過去の帳票から起こした記録を、参照用の「過去帳票台帳」TSV にまとめる。
 *
 *   node tools/build-archive.js
 *
 * 入力（あるものだけ使う）:
 *   data/past-intent-records.json        … 意向把握シート.xlsx から起こした記録
 *   data/past-suitability-records.json   … 適合性確認シートの PDF/docx から起こした記録
 *
 * 出力:
 *   data/archive.tsv
 *
 * ■ この台帳は「記録」であって「再生成」ではない
 *
 * 適合性の判定①〜⑥は、システム側では入力から再計算する。しかし過去の帳票には
 * 当時の判定が既に記録されており、提出済みの書面として確定している。再計算した
 * 結果を並べると、書面と食い違う判定が残る恐れがある。
 *
 * そのためこの台帳は、帳票に書かれていた判定をそのまま転記する。年収×20% なども
 * 計算し直さず、印字されていた値を写す。元ファイルへのリンクも残し、いつでも
 * 原本に当たれるようにする。
 */

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = path.join(__dirname, '..');
const DATA = path.join(ROOT, 'data');
const OUT_FILE = path.join(DATA, 'archive.tsv');

/* ---------------------------------------------------------------- *
 * 期待する入力の形
 * ---------------------------------------------------------------- *

 past-suitability-records.json は次の形の配列。
 帳票に無い項目は null / 空配列にする。値を作らないこと。

 {
   "fileId": "1KpU9G…",
   "fileName": "【適合性】三好　雄策_単独.pdf",
   "fileUrl": "https://drive.google.com/file/d/1KpU9G…/view",
   "formGeneration": "旧様式",              // 新様式 / 旧様式 / 不明
   "customerName": "三好 雄策",
   "contractType": "個人",                  // 個人 / 法人 / null
   "confirmDate": "2024-08-13",             // YYYY-MM-DD / null
   "age": 31, "occupation": "会社員",
   "income": 500, "assets": 100,            // 万円。帳票の印字どおり
   "incomePrinted20": 100,                  // 「年収×20%」欄に印字されていた値
   "assetsPrinted30": 30,                   // 「金融資産×30%」欄に印字されていた値
   "experience": ["株式", "投資信託"], "experienceOther": "",
   "premiumSource": ["預貯金・給与"], "premiumSourceOther": "",
   "riskTolerance": "許容できる",           // 許容できる / 許容できない / null
   "needs": ["死亡時の保障"], "needsOther": "",
   "recordedJudgments": [                   // 帳票に記録されていた はい/いいえ
     { "no": "①", "answer": "はい" }        // 様式で項目数が違うので配列で持つ
   ],
   "verifyDate": null, "verifierName": null, "verifyResult": null,
   "agency": "ヒトカチ株式会社", "agent": "佐々木 嶺",
   "notes": ""
 }
 * ---------------------------------------------------------------- */

const COLUMNS = [
  '契約者氏名', '契約形態', '確認日', '募集人', '代理店', '帳票様式',
  '年齢', '職業', '年収(万円)', '金融資産(万円)',
  '年収×20%(印字)', '金融資産×30%(印字)',
  '購入経験のある金融商品', '保険料原資', 'リスク選好', 'ご意向(適合性⑧)',
  '記録された判定', '記録された総合判定',
  '検証日', '検証実施者', '検証結果',
  '保障分野(当初)', '保障分野(最終)', '貯蓄部分', 'ご意向の変化',
  '適合性確認シート(元ファイル)', '意向把握シート(元データ)', '備考'
];

function loadNormalizer() {
  const ctx = { console };
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(path.join(ROOT, 'src', 'DriveUtil.gs'), 'utf8'), ctx,
    { filename: 'DriveUtil.gs' });
  return ctx.normalizeName_;
}

function readJson(name) {
  const p = path.join(DATA, name);
  if (!fs.existsSync(p)) return null;
  const v = JSON.parse(fs.readFileSync(p, 'utf8'));
  if (!Array.isArray(v)) throw new Error(`${name} の中身が配列ではありません。`);
  return v;
}

const j = (a) => (Array.isArray(a) ? a.filter(Boolean).join('、') : (a == null ? '' : String(a)));
const s = (v) => (v == null ? '' : String(v));

/** 意向把握シート側の記録から、保障分野の日本語ラベルを組み立てる。 */
function needsLabels(map, NEEDS) {
  if (!map) return '';
  return NEEDS.filter(n => map[n.key]).map(n => n.label).join('、');
}

function judgmentsText(list) {
  if (!Array.isArray(list) || !list.length) return '';
  return list.map(x => `${s(x.no)}${s(x.answer)}`).join(' ');
}

/** 記録された判定に「いいえ」が1つでもあれば不適合。再計算はしない。 */
function overallText(list) {
  if (!Array.isArray(list) || !list.length) return '';
  const answered = list.filter(x => x.answer === 'はい' || x.answer === 'いいえ');
  if (!answered.length) return '';
  return answered.some(x => x.answer === 'いいえ') ? '不適合' : '適合';
}

function changeLogText(rows) {
  if (!Array.isArray(rows)) return '';
  return rows.filter(c => c && (c.date || c.text))
    .map(c => `${s(c.date)} ${s(c.text)}`.trim()).join(' / ');
}

/**
 * 突き合わせ用の鍵。
 *
 * 適合性確認シートは「株式会社◯◯ 代表取締役 △△」と代表者名まで書き、
 * 意向把握シートは「株式会社◯◯」だけ、という食い違いがある。法人名の後ろに
 * 続く代表者の肩書き以降を落として揃える。
 *
 * フォルダ照合（src/DriveUtil.gs）はここまで踏み込まない。あちらは別人の
 * フォルダへ保存する事故に直結するので、保守的なままにしておく。
 */
function matchKey(normalize, name) {
  let k = normalize(name);

  // 長音符の揺れを吸収する。NFKC で全角ハイフン「－」は ASCII の「-」になるが、
  // 「インタ－ハ－ト」と「インターハート」は同じ会社を指している。
  k = k.replace(/[-\u2010\u2012\u2013\u2014\u2015\u2212]/g, '\u30fc');

  // 法人名のあとに代表者の肩書きと氏名が続く書き方を落とす。
  // 適合性確認シートは「株式会社◯◯ 代表取締役 △△」、意向把握シートは
  // 「株式会社◯◯」だけ、という食い違いがあるため。
  // 法人格を含む名前にだけ適用し、個人名は触らない。
  if (/(株式会社|有限会社|合同会社|合資会社|合名会社|一般社団法人|一般財団法人|医療法人)/.test(k)) {
    k = k.replace(/(代表取締役社長|代表取締役|代表執行役|代表社員|代表理事|理事長|代表者|代表|社長|会長).*$/, '');
  }
  return k;
}


function main() {
  const normalize = loadNormalizer();
  const key = (name) => matchKey(normalize, name);
  const NEEDS = [
    { key: 'death', label: '死亡時の保障' },
    { key: 'medical', label: '病気・ケガ・介護の保障' },
    { key: 'cancer', label: 'がんなどの特定疾病に備える保障' },
    { key: 'education', label: '子供の教育資金準備' },
    { key: 'pension', label: '老後の生活資金準備' },
    { key: 'business', label: '事業保障' },
    { key: 'welfare', label: '従業員の福利厚生' },
    { key: 'retire', label: '退職金に対する備え' }
  ];

  const intents = readJson('past-intent-records.json') || [];
  const suitability = readJson('past-suitability-records.json');

  if (!suitability) {
    console.error('data/past-suitability-records.json がありません。');
    console.error('意向把握シート側の記録だけで台帳を作ります（適合性の列は空欄）。\n');
  }

  // 1 書類 1 行にする。同じ顧客で内容の食い違う適合性確認シートが複数見つかって
  // いるため、顧客単位でまとめると矛盾が隠れてしまう。監査で問題になるのはむしろ
  // その食い違いなので、書類はすべて残す。
  const intentByName = new Map();
  intents.forEach(r => intentByName.set(key(r.customerName), r));

  // 同じ顧客に何通の適合性確認シートがあるかを数える。
  const suitCount = new Map();
  (suitability || []).forEach(r => {
    const k = key(r.customerName);
    suitCount.set(k, (suitCount.get(k) || 0) + 1);
  });

  const pairs = [];
  const usedIntent = new Set();
  (suitability || []).forEach(suit => {
    const k = key(suit.customerName);
    pairs.push({ name: suit.customerName, suit: suit, intent: intentByName.get(k) || null });
    if (intentByName.has(k)) usedIntent.add(k);
  });
  // 適合性確認シートが無い顧客も、意向把握シートの記録だけで台帳に載せる。
  intents.forEach(r => {
    const k = key(r.customerName);
    if (!usedIntent.has(k)) pairs.push({ name: r.customerName, suit: null, intent: r });
  });

  const out = [COLUMNS];
  let bothSides = 0, intentOnly = 0, suitOnly = 0;

  pairs.forEach(({ name, intent, suit }) => {
    if (intent && suit) bothSides++;
    else if (intent) intentOnly++;
    else suitOnly++;

    const notes = [];
    if (suit && suit.extractionFailed) notes.push('本文を読み取れなかった');
    const dup = suit ? suitCount.get(key(suit.customerName)) : 0;
    if (dup > 1) notes.push(`この顧客の適合性確認シートは ${dup} 通ある。内容が食い違っていないか確認すること`);
    if (intent && intent.notes) notes.push(intent.notes);
    if (suit && suit.notes) notes.push(suit.notes);
    if (!suit) notes.push('適合性確認シートの記録なし');
    if (!intent) notes.push('意向把握シートの記録なし');

    out.push([
      s((suit && suit.customerName) || name),
      s(suit && suit.contractType),
      s((suit && suit.confirmDate) || (intent && intent.confirmDateInitial)),
      s((suit && suit.agent) || (intent && intent.agent)),
      s((suit && suit.agency) || (intent && intent.agency)),
      s(suit && suit.formGeneration),
      s(suit && suit.age),
      s(suit && suit.occupation),
      s(suit && suit.income),
      s(suit && suit.assets),
      s(suit && suit.incomePrinted20),
      s(suit && suit.assetsPrinted30),
      suit ? j(suit.experience) + (suit.experienceOther ? `（${suit.experienceOther}）` : '') : '',
      suit ? j(suit.premiumSource) + (suit.premiumSourceOther ? `（${suit.premiumSourceOther}）` : '') : '',
      s(suit && suit.riskTolerance),
      suit ? j(suit.needs) + (suit.needsOther ? `（${suit.needsOther}）` : '') : '',
      judgmentsText(suit && suit.recordedJudgments),
      overallText(suit && suit.recordedJudgments),
      s(suit && suit.verifyDate),
      s(suit && suit.verifierName),
      s(suit && suit.verifyResult),
      intent ? needsLabels(intent.needsInitial, NEEDS) : '',
      intent ? needsLabels(intent.needsFinal, NEEDS) : '',
      s(intent && intent.savingsInitial),
      intent ? changeLogText(intent.changeLog) : '',
      s(suit && suit.fileUrl),
      s(intent && intent.sheetName),
      notes.join(' / ')
    ]);
  });

  fs.mkdirSync(DATA, { recursive: true });
  fs.writeFileSync(OUT_FILE,
    out.map(r => r.map(c => String(c).replace(/[\t\r\n]/g, ' ')).join('\t')).join('\n') + '\n',
    'utf8');

  const rel = path.relative(process.cwd(), OUT_FILE);
  console.log(`${out.length - 1} 件の台帳を書き出しました: ${rel}\n`);
  console.log(`■ 内訳（1 書類 1 行）`);
  console.log(`   両方の記録がある            ${bothSides} 行`);
  console.log(`   意向把握シートのみ          ${intentOnly} 行`);
  console.log(`   適合性確認シートのみ        ${suitOnly} 行`);

  const multi = Array.from(suitCount.entries()).filter(([, n]) => n > 1);
  if (multi.length) {
    console.log(`\n■ 適合性確認シートが複数ある顧客（${multi.length} 名）`);
    console.log('   内容が食い違っていないか、原本に当たって確認してください。');
    multi.forEach(([k, n]) => {
      const one = (suitability || []).find(r => key(r.customerName) === k);
      console.log(`   ${one ? one.customerName : k}　… ${n} 通`);
    });
  }

  const missingSuit = out.slice(1).filter(r => r[27].indexOf('適合性確認シートの記録なし') >= 0).length;
  if (missingSuit) {
    console.log(`\n■ 適合性の列が空欄の行が ${missingSuit} 件あります`);
    console.log('   Drive にその顧客の適合性確認シートが無いか、スキャン画像で読み取れないものです。');
    console.log('   統一記録として埋めるなら、担当者が原本から転記する必要があります。');
  }

  console.log(`
■ 使い方
   1. 設定スプレッドシートに「過去帳票台帳」という名前のシートを新しく作る
   2. ${rel} の中身を、見出し行を含めて A1 から貼り付ける
   3. 参照専用として扱う。ここから帳票を再生成しないこと

   記録された判定は、当時の帳票に書かれていた はい／いいえ をそのまま写している。
   システムの再計算とは別物なので、食い違っても書き換えないこと。`);
}

main();
