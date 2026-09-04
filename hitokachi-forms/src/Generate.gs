/**
 * 2 帳票の生成と保存。
 */

/**
 * PDF を作って保存先フォルダに置く。
 * @param {Object} data      フォームからの入力（固定値の反映済み）
 * @param {string} choice    保存先フォルダID、または 'new'
 * @param {Object} rawAnswers 確認画面で確定した「２．」の回答。省略時は既定（すべて はい）
 * @return {Object}          保存結果
 */
function generateAndSave_(data, choice, rawAnswers) {
  var answers = normalizeAnswers_(data, rawAnswers);
  var summary = summarizeAnswers_(answers);
  // 帳票には出さない。ログに残す参考値。入力を取っていない項目に依存する判定は
  // 'unknown' になるので、使っていない入力を根拠にした食い違いはログに載らない。
  var advice = judge_(data, getFieldConfig_());
  var agent = getAgentByName_(data.agent);
  if (!agent) throw new Error('募集人「' + data.agent + '」が募集人マスタにありません。');

  var dest = materializeDestination_(data.agency, data.customerName, choice);
  var folder = DriveApp.getFolderById(dest.id);

  var model = buildModel_(data, answers, agent, data.agency);
  var stamp = Utilities.formatDate(confirmDateAsDate_(data.confirmDate), 'Asia/Tokyo', 'yyyyMMdd');
  var base = sanitizeFileName_(data.customerName) + '_' + stamp;

  var files = [];
  files.push(saveOne_(folder, 'SuitabilitySheet', model, '適合性確認シート_' + base));
  files.push(saveOne_(folder, 'IntentSheet',      model, '意向把握シート_' + base));

  var result = {
    folderId: dest.id,
    folderName: dest.name,
    folderCreated: dest.created,
    folderUrl: folder.getUrl(),
    files: files,
    answers: answers,
    judgment: summary,
    advice: advice,
    logWarning: ''
  };

  // ここから先で投げると、PDF は既に Drive にあるのに失敗扱いになり、
  // 再実行で同じフォルダに同じ帳票が二重にできる。ログの失敗は警告に留める。
  try {
    appendLog_(data, summary, advice, result);
  } catch (e) {
    result.logWarning = '送信ログに記録できませんでした（' + e.message + '）。'
      + '監査証跡が欠けるので、設定スプレッドシートの「送信ログ」シートを確認してください。';
  }
  return result;
}

/** 確認日を Date にする。文字列でも Date でも受ける。不正なら今日。 */
function confirmDateAsDate_(v) {
  if (isDate_(v)) return v;
  var d = new Date(String(v == null ? '' : v).replace(/\//g, '-'));
  return isNaN(d.getTime()) ? new Date() : d;
}

function saveOne_(folder, templateName, model, fileName) {
  var html = renderTemplate_(templateName, model);
  var pdf = htmlToPdfBlob_(html, fileName, folder.getId());
  var file = folder.createFile(pdf);
  return { id: file.getId(), name: file.getName(), url: file.getUrl() };
}

/**
 * 入力値の検証。表示中（form）かつ必須の項目が埋まっているかを見る。
 * 帳票そのものの妥当性（適合性の判定）は judge_ の仕事なのでここでは見ない。
 */
/** 法人契約では使わない項目。帳票にもログにも出ないので入力を求めない。 */
var INDIVIDUAL_ONLY_FIELDS = [
  'age', 'elderlyMethod', 'occupation', 'occupationClass', 'householdConfirmed',
  'income', 'assets', 'annualPremium', 'payYears'
];

function validate_(data, fieldConfig) {
  var errors = [];
  var isCorp = data.contractType === '法人';

  FIELD_DEFS.forEach(function (f) {
    if (!f.required) return;
    if (fieldConfig[f.key].mode === 'hidden') return;
    if (isCorp && INDIVIDUAL_ONLY_FIELDS.indexOf(f.key) >= 0) return;
    var v = data[f.key];
    var empty = (v == null || v === '' || (Array.isArray(v) && v.length === 0));
    if (empty) errors.push(f.label + 'を入力してください。');
  });

  // 共同募集の相方は、その代理店に登録されている募集人だけ。一括入力シートの
  // 選択肢は全代理店の相方をまとめて出すので、ここで組み合わせを見ておく。
  // 誤ると帳票に無関係な代理店の募集人名が連名で印字される。
  if (data.coAgent) {
    var ag = getAgencyByName_(data.agency);
    var coList = (ag && ag.coAgents) || [];
    if (coList.indexOf(String(data.coAgent).trim()) < 0) {
      errors.push('共同募集の相方「' + data.coAgent + '」は代理店「' + data.agency
        + '」の募集人として登録されていません。代理店マスタの「代理店側の募集人」を確認してください。');
    }
    if (String(data.coAgent).trim() === String(data.agent).trim()) {
      errors.push('共同募集の相方に、募集人と同じ人は選べません。');
    }
  }

  if (isCorp) return errors;

  // 数値の妥当性。負の値を通すと判定③が静かに「はい」になり、しかも年間保険料と
  // 払込期間は帳票に出ないので、出来上がったPDFを見ても誤りに気づけない。
  var age = num_(data.age);
  if (age !== null && (age < 0 || age > 120)) errors.push('年齢の値が不正です。');

  [['income', '年収'], ['assets', '金融資産'], ['annualPremium', '年間保険料']]
    .forEach(function (pair) {
      var n = num_(data[pair[0]]);
      if (n !== null && n < 0) errors.push(pair[1] + 'に負の値は入力できません。');
    });

  var years = num_(data.payYears);
  if (years !== null && years <= 0) errors.push('保険料払込期間は1年以上で入力してください。');

  // 「投資経験なし」と他の商品を同時に選ぶのは矛盾。判定④が甘くなる。
  var exp = data.experience || [];
  if (exp.length > 1 && exp.indexOf('投資経験なし') >= 0) {
    errors.push('「投資経験なし」は他の金融商品と同時に選べません。');
  }
  return errors;
}

/**
 * 設定シートで fixed になっている項目の値を、入力データに流し込む。
 * hidden の項目は帳票側で空欄になるよう明示的に落とす。
 */
function applyFieldConfig_(data, fieldConfig) {
  var out = {};
  FIELD_DEFS.forEach(function (f) {
    var c = fieldConfig[f.key];
    if (c.mode === 'hidden') {
      out[f.key] = (f.type === 'multi' || f.type === 'needs' || f.type === 'rows') ? [] : '';
    } else if (c.mode === 'fixed') {
      out[f.key] = coerceFixed_(f, c.fixedValue);
    } else {
      out[f.key] = data[f.key];
    }
  });
  return out;
}

/** 設定シートの固定値（文字列）を、項目の型に合わせて解釈する。 */
function coerceFixed_(field, raw) {
  if (field.type === 'multi' || field.type === 'needs') {
    return String(raw == null ? '' : raw).split(/[,、\n]/)
      .map(function (s) { return s.trim(); })
      .filter(function (s) { return s !== ''; });
  }
  if (field.type === 'check') return isTrue_(raw);
  if (field.type === 'rows') return [];
  if (field.type === 'date' && isDate_(raw)) return formatSlashDate_(raw);
  return raw == null ? '' : raw;
}
