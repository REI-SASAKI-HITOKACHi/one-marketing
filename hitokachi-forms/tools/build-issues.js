#!/usr/bin/env node
/**
 * 過去の適合性確認シートから、確認したほうがよい記録を抜き出す。
 *
 *   node tools/build-issues.js
 *
 * 入力: data/past-suitability-records.json
 * 出力: data/issues.tsv
 *
 * ■ ここでやっていること
 *
 * 帳票に書かれている内容どうしが食い違っている箇所を、機械的に拾うだけ。
 * 「正しい答え」を出すものではないので、判定を書き換えたりはしない。
 * 一覧を担当者が上から見て、原本に当たって確かめるための道具。
 *
 * 拾えるのは「帳票の中だけで完結する食い違い」に限られる。面談で何を話したかは
 * 帳票に残らないので、ここに出た＝誤り、ではない。別紙の但し書きで説明が
 * つくものもある（例: パート勤務でも世帯主の収入を確認していれば②は「はい」）。
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const DATA = path.join(ROOT, 'data');
const IN_FILE = path.join(DATA, 'past-suitability-records.json');
const OUT_FILE = path.join(DATA, 'issues.tsv');

/**
 * 「２．」の並び順は新旧の様式で共通。番号の振り方だけが違う。
 *   旧様式: ① ② ③④ ⑤ ⑥ ⑦⑧
 *   新様式: ① ② ③  ④ ⑤ ⑥
 */
const CRITERIA = [
  '単独での判断',
  '職業',
  '保険料のバランス',
  'リスクの理解',
  '保険料原資',
  'ご意向'
];

/** n 番目（0 始まり）の判定の回答と、帳票に印字されていた番号を返す。 */
function judgmentAt(rec, i) {
  const list = rec.recordedJudgments || [];
  const item = list[i];
  return { no: item ? item.no : null, answer: item ? item.answer : null };
}

const has = (arr, re) => (arr || []).some(v => re.test(String(v)));

/** 原資に解約返戻金・満期金が含まれているか。 */
function fundedByPolicy(rec) {
  // 「その他」欄に文言だけ残ってチェックが無い記録が多いので、
  // その他が実際に選ばれている場合だけ見る。
  const otherChosen = has(rec.premiumSource, /その他/);
  const otherText = String(rec.premiumSourceOther || '');
  if (otherChosen && /解約返戻金|満期金/.test(otherText)) return `その他（${otherText}）`;
  if (has(rec.premiumSource, /特定保険契約/)) return '特定保険契約（変額保険・外貨建保険等）';
  return null;
}

const NON_REGULAR = /パート|アルバイト|学生|主婦|無職|年金生活/;

/** 1 件の記録から、確認したほうがよい点を挙げる。 */
function findIssues(rec, duplicateCount) {
  const out = [];
  const add = (level, kind, detail) => out.push({ level, kind, detail });

  if (rec.extractionFailed) {
    add('中', '本文を読み取れない', 'スキャン画像とみられる。内容の確認は原本で行う');
    return out;
  }

  // 1. 原資が解約返戻金なのに「解約返戻金ではない」が「はい」
  const funded = fundedByPolicy(rec);
  const j5 = judgmentAt(rec, 4);
  if (funded && j5.answer === 'はい') {
    add('高', '原資の矛盾',
      `⑥保険料原資に「${funded}」を選びながら、` +
      `２．${j5.no}「原資が満期金または解約返戻金ではない」が「はい」`);
  }

  // 2. 職業が該当するのに「パート・学生・主婦・無職ではない」が「はい」
  const j2 = judgmentAt(rec, 1);
  if (rec.occupation && NON_REGULAR.test(rec.occupation) && j2.answer === 'はい') {
    add('中', '職業の矛盾',
      `②職業が「${rec.occupation}」でありながら、` +
      `２．${j2.no}「パート・アルバイト、学生、主婦、無職ではない」が「はい」。` +
      '世帯主等の収入を確認していれば別紙の但し書きで成立するが、その記録が帳票にない');
  }

  // 3. リスク選好が未選択なのに、意向の判定が「はい」
  const j6 = judgmentAt(rec, 5);
  if (!rec.riskTolerance && j6.answer === 'はい') {
    add('高', 'リスク選好が未記入',
      `⑦リスク選好がどちらも未選択のまま、２．${j6.no}が「はい」`);
  }

  // 4. 印字された割合が計算と合わない
  const near = (a, b) => Math.abs(a - b) <= Math.max(0.5, Math.abs(b) * 0.02);
  if (rec.income != null && rec.incomePrinted20 != null
      && !near(rec.incomePrinted20, rec.income * 0.2)) {
    add('中', '印字の計算誤り',
      `年収×20% の印字が計算と合わない（印字 ${rec.incomePrinted20} / 計算 ${rec.income * 0.2}）`);
  }
  if (rec.assets != null && rec.assetsPrinted30 != null
      && !near(rec.assetsPrinted30, rec.assets * 0.3)) {
    add('中', '印字の計算誤り',
      `金融資産×30% の印字が計算と合わない（印字 ${rec.assetsPrinted30} / 計算 ${rec.assets * 0.3}）`);
  }

  // 5. 判定が未チェックのまま
  const blanks = [];
  CRITERIA.forEach((name, i) => {
    const j = judgmentAt(rec, i);
    const corporateSkip = rec.contractType === '法人' && i <= 2;
    if (j.answer == null && !corporateSkip) blanks.push((j.no || CRITERIA[i]) + '（' + name + '）');
  });
  if (blanks.length) {
    add('中', '判定が未記入', `２．の ${blanks.join('・')} が「はい」「いいえ」どちらも未チェック`);
  }

  // 6. 投資経験なしでリスク理解が「はい」
  const j4 = judgmentAt(rec, 3);
  const noExperience = (rec.experience || []).length === 0
    || ((rec.experience || []).length === 1 && rec.experience[0] === '投資経験なし');
  if (noExperience && j4.answer === 'はい') {
    add('低', '投資経験なし',
      `⑤で投資経験なし（または未選択）のまま、２．${j4.no}「リスクを十分に理解のうえ許容いただいた」が「はい」。` +
      '別紙は「時間を確保して説明」を求めているが、その記録が帳票にない');
  }

  // 7. 未成年契約で親権者の記載がない
  if (rec.age != null && rec.age < 18 && !rec.guardianName) {
    add('高', '未成年契約',
      `①年齢が ${rec.age} 歳（職業「${rec.occupation || '記載なし'}」）だが、親権者氏名・続柄の記載がない`);
  }

  // 8. 同一顧客で複数の帳票
  if (duplicateCount > 1) {
    add('中', '同一顧客で複数',
      `この顧客の適合性確認シートが ${duplicateCount} 通ある。内容が食い違っていないか確認すること`);
  }

  // 9. 新様式なのに検証欄が空
  if (/新様式/.test(String(rec.formGeneration)) && !rec.verifyDate && !rec.verifierName) {
    add('低', '事後検証が未実施', '新様式だが検証日・検証実施者ともに未記入');
  }

  return out;
}

function main() {
  if (!fs.existsSync(IN_FILE)) {
    console.error(`${path.relative(process.cwd(), IN_FILE)} がありません。先に抽出を行ってください。`);
    process.exit(1);
  }
  const records = JSON.parse(fs.readFileSync(IN_FILE, 'utf8'));

  // 同姓同名ではなく同一顧客の重複を数える（法人名の書き方の揺れも吸収）。
  const count = new Map();
  const norm = (s) => String(s || '').replace(/[\s　]+/g, '')
    .replace(/(代表取締役社長|代表取締役|代表社員|代表)[^]*$/, '');
  records.forEach(r => {
    const k = norm(r.customerName);
    count.set(k, (count.get(k) || 0) + 1);
  });

  const LEVEL_ORDER = { '高': 0, '中': 1, '低': 2 };
  const rows = [];
  records.forEach(rec => {
    findIssues(rec, count.get(norm(rec.customerName)) || 1).forEach(issue => {
      rows.push([
        issue.level, issue.kind,
        rec.customerName || '', rec.contractType || '',
        rec.confirmDate || '', rec.agent || '',
        String(rec.formGeneration || ''),
        issue.detail,
        rec.fileUrl || '', rec.fileName || ''
      ]);
    });
  });

  rows.sort((a, b) => (LEVEL_ORDER[a[0]] - LEVEL_ORDER[b[0]])
    || a[1].localeCompare(b[1], 'ja') || String(a[4]).localeCompare(String(b[4])));

  const header = ['重要度', '種別', '契約者氏名', '契約形態', '確認日', '募集人',
    '帳票様式', '確認してほしいこと', '元ファイル', 'ファイル名'];

  fs.mkdirSync(DATA, { recursive: true });
  fs.writeFileSync(OUT_FILE,
    [header].concat(rows).map(r => r.map(c => String(c).replace(/[\t\r\n]/g, ' ')).join('\t')).join('\n') + '\n',
    'utf8');

  // 集計
  const byKind = new Map();
  const byLevel = new Map();
  const customers = new Set();
  rows.forEach(r => {
    byKind.set(r[1], (byKind.get(r[1]) || 0) + 1);
    byLevel.set(r[0], (byLevel.get(r[0]) || 0) + 1);
    customers.add(r[2]);
  });

  console.log(`${records.length} 件の帳票から ${rows.length} 件の確認事項を抜き出しました。`);
  console.log(`該当した顧客は ${customers.size} 名: ${path.relative(process.cwd(), OUT_FILE)}\n`);

  console.log('■ 重要度');
  ['高', '中', '低'].forEach(l => {
    if (byLevel.get(l)) console.log(`   ${l}  ${byLevel.get(l)} 件`);
  });

  console.log('\n■ 種別');
  Array.from(byKind.entries()).sort((a, b) => b[1] - a[1])
    .forEach(([k, n]) => console.log(`   ${String(n).padStart(3)} 件  ${k}`));

  console.log(`
■ 使い方
   設定スプレッドシートに「要確認一覧」シートを作り、見出し行を含めて貼り付ける。
   重要度の高い順に並んでいるので、上から原本に当たって確かめる。

   ここに出たものが誤りとは限らない。帳票に残らない事情で説明がつくものもある。
   確認した結果を右端に列を足して書き込めば、そのまま対応の記録になる。`);
}

main();
