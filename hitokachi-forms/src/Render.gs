/**
 * 帳票の描画。
 *
 * HTML を組み立てて Google ドキュメントに変換し、そこから PDF を書き出す。
 * GAS で HTML から直接 PDF にすると日本語が化けるが、Google ドキュメントを
 * 一度はさめば確実に出る。レイアウトの定義（HTML）はリポジトリ側に残るので、
 * Drive 上のテンプレートとコードがズレる事故も起きない。
 */

var A4_WIDTH_PT  = 595.28;
var A4_HEIGHT_PT = 841.89;
var MARGIN_PT    = 36; // 0.5 インチ

/**
 * 値が日付かどうか。instanceof Date は実行コンテキストをまたぐと偽になるので、
 * 型タグで見る（スプレッドシートから返る Date を取りこぼさないため）。
 */
function isDate_(v) {
  return Object.prototype.toString.call(v) === '[object Date]';
}

/** 全角数字。原本の日付表記に合わせる。 */
function toFullWidth_(s) {
  return String(s).replace(/[0-9]/g, function (c) {
    return String.fromCharCode(c.charCodeAt(0) + 0xFEE0);
  });
}

/** Date または 'YYYY-MM-DD' を「２０２６年８月１日」形式にする。 */
function formatJpDate_(v) {
  if (!v) return '';
  var d = isDate_(v) ? v : new Date(String(v).replace(/\//g, '-'));
  if (isNaN(d.getTime())) return String(v);
  return toFullWidth_(d.getFullYear()) + '年'
    + toFullWidth_(d.getMonth() + 1) + '月'
    + toFullWidth_(d.getDate()) + '日';
}

/** 意向把握シートの確認日欄は西暦スラッシュ表記。 */
function formatSlashDate_(v) {
  if (!v) return '';
  var d = isDate_(v) ? v : new Date(String(v).replace(/\//g, '-'));
  if (isNaN(d.getTime())) return String(v);
  return Utilities.formatDate(d, 'Asia/Tokyo', 'yyyy/MM/dd');
}

function chk_(on) { return on ? '■' : '□'; }
function box_(on) { return on ? '☑' : '☐'; }

function esc_(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

/**
 * HTML を Google ドキュメント経由で PDF Blob にする。
 * 中間ドキュメントは必ず削除する。
 */
function htmlToPdfBlob_(html, name) {
  var htmlBlob = Utilities.newBlob(html, 'text/html', name + '.html');
  var created = Drive.Files.create(
    { name: '__tmp__' + name, mimeType: 'application/vnd.google-apps.document' },
    htmlBlob
  );
  var docId = created.id;
  try {
    var doc = DocumentApp.openById(docId);
    var body = doc.getBody();
    body.setPageWidth(A4_WIDTH_PT).setPageHeight(A4_HEIGHT_PT);
    body.setMarginTop(MARGIN_PT).setMarginBottom(MARGIN_PT)
        .setMarginLeft(MARGIN_PT).setMarginRight(MARGIN_PT);
    doc.saveAndClose();

    var pdf = DriveApp.getFileById(docId).getAs('application/pdf');
    pdf.setName(name + '.pdf');
    // getAs は遅延評価されうるのでここでバイト列を確定させてから中間ファイルを消す。
    return Utilities.newBlob(pdf.getBytes(), 'application/pdf', name + '.pdf');
  } finally {
    try { DriveApp.getFileById(docId).setTrashed(true); } catch (e) { /* 消せなくても処理は続ける */ }
  }
}

/** テンプレートファイルにデータを渡して HTML 文字列にする。 */
function renderTemplate_(fileName, model) {
  var t = HtmlService.createTemplateFromFile(fileName);
  t.m = model;
  return t.evaluate().getContent();
}

/**
 * 入力値と判定結果から、テンプレートに渡す表示用モデルを組み立てる。
 * ここで表示の都合をすべて吸収し、テンプレート側は値を並べるだけにする。
 */
function buildModel_(d, judgment, agent, agencyName) {
  var isCorp = d.contractType === '法人';
  var income = num_(d.income);
  var assets = num_(d.assets);
  var suitKeys = needsToSuitKeys_(d.needs || []);
  if (d.needsOther) suitKeys.push('other');

  var finalNeeds   = (d.finalNeeds && d.finalNeeds.length) ? d.finalNeeds : (d.needs || []);
  var finalSavings = d.finalSavings || d.savings;

  var expOther = (d.experience || []).indexOf('その他') >= 0;
  var srcOther = (d.premiumSource || []).indexOf('その他') >= 0;

  return {
    isCorp: isCorp,
    agencyName: agencyName,
    agent: agent,

    customerName: d.customerName || '',
    guardianName: d.guardianName || '',
    guardianRelation: d.guardianRelation || '',

    confirmDateJp: formatJpDate_(d.confirmDate),
    confirmDateSlash: formatSlashDate_(d.confirmDate),
    finalDateSlash: formatSlashDate_(d.finalDate || d.confirmDate),
    verifyDateJp: formatJpDate_(d.verifyDate),
    verifierName: d.verifierName || '',
    verifyResult: d.verifyResult || '',

    age: isCorp ? '' : (d.age === '' || d.age == null ? '' : d.age + '歳'),
    occupation: isCorp ? '' : (d.occupation || ''),
    income: isCorp || income === null ? '' : income + '万円',
    assets: isCorp || assets === null ? '' : assets + '万円',
    income20: isCorp || income === null ? '' : (Math.round(income * 0.2 * 10) / 10) + '万円',
    assets30: isCorp || assets === null ? '' : (Math.round(assets * 0.3 * 10) / 10) + '万円',

    experience: EXPERIENCE_OPTIONS.map(function (o) {
      return { label: o, mark: chk_((d.experience || []).indexOf(o) >= 0) };
    }),
    experienceOther: expOther ? (d.experienceOther || '') : '',

    premiumSource: PREMIUM_SOURCE_OPTIONS.map(function (o) {
      return { label: o, mark: chk_((d.premiumSource || []).indexOf(o) >= 0) };
    }),
    premiumSourceOther: srcOther ? (d.premiumSourceOther || '') : '',

    riskYes: chk_(d.riskTolerance === RISK_YES),
    riskNo:  chk_(d.riskTolerance === RISK_NO),

    suitNeeds: SUIT_NEEDS.map(function (n) {
      return { label: n.label, mark: chk_(suitKeys.indexOf(n.key) >= 0) };
    }),
    suitNeedsOther: d.needsOther || '',

    judge: ['i1', 'i2', 'i3', 'i4', 'i5', 'i6'].map(function (k) {
      var it = judgment.items[k];
      return {
        key: k,
        label: JUDGE_LABELS[k],
        yes: it.value === 'yes' ? '■' : '□',
        no:  it.value === 'no'  ? '■' : '□',
        na:  it.value === 'na'
      };
    }),

    // 意向把握シート
    needsRows: NEEDS.map(function (n) {
      return {
        owner: n.owner,
        label: n.label,
        estimated: box_((d.estimatedNeeds || []).indexOf(n.key) >= 0),
        initial:   box_((d.needs || []).indexOf(n.key) >= 0),
        final:     box_(finalNeeds.indexOf(n.key) >= 0)
      };
    }),
    savingsRows: ['①ある方が良い', '②なくても良い'].map(function (label) {
      return {
        label: label,
        estimated: box_(d.estimatedSavings === label),
        initial:   box_(d.savings === label),
        final:     box_(finalSavings === label)
      };
    }),
    wishPeriod:  d.wishPeriod  || '',
    wishAmount:  d.wishAmount  || '',
    wishPremium: d.wishPremium || '',
    wishOther:   d.wishOther   || '',
    changeLog:   normalizeChangeLog_(d.changeLog)
  };
}

/** 意向の変化欄。常に3行出して、入力がない行は空欄にする。 */
function normalizeChangeLog_(rows) {
  var out = [];
  for (var i = 0; i < 3; i++) {
    var r = (rows && rows[i]) || {};
    out.push({ date: r.date ? formatSlashDate_(r.date) : '', text: r.text || '' });
  }
  return out;
}
