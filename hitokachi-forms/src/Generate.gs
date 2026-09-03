/**
 * 2 帳票の生成と保存。
 */

/**
 * PDF を作って保存先フォルダに置く。
 * @param {Object} data      フォームからの入力（固定値の反映済み）
 * @param {string} choice    保存先フォルダID、または 'new'
 * @return {Object}          保存結果
 */
function generateAndSave_(data, choice) {
  var judgment = judge_(data);
  var agent = getAgentByName_(data.agent);
  if (!agent) throw new Error('募集人「' + data.agent + '」が募集人マスタにありません。');

  var dest = materializeDestination_(data.agency, data.customerName, choice);
  var folder = DriveApp.getFolderById(dest.id);

  var model = buildModel_(data, judgment, agent, data.agency);
  var stamp = Utilities.formatDate(
    data.confirmDate ? new Date(String(data.confirmDate).replace(/\//g, '-')) : new Date(),
    'Asia/Tokyo', 'yyyyMMdd');
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
    judgment: judgment
  };

  appendLog_(data, judgment, result);
  return result;
}

function saveOne_(folder, templateName, model, fileName) {
  var html = renderTemplate_(templateName, model);
  var pdf = htmlToPdfBlob_(html, fileName);
  var file = folder.createFile(pdf);
  return { id: file.getId(), name: file.getName(), url: file.getUrl() };
}

/**
 * 入力値の検証。表示中（form）かつ必須の項目が埋まっているかを見る。
 * 帳票そのものの妥当性（適合性の判定）は judge_ の仕事なのでここでは見ない。
 */
function validate_(data, fieldConfig) {
  var errors = [];
  FIELD_DEFS.forEach(function (f) {
    if (!f.required) return;
    var mode = fieldConfig[f.key].mode;
    if (mode === 'hidden') return;
    var v = data[f.key];
    var empty = (v == null || v === '' || (Array.isArray(v) && v.length === 0));
    if (empty) errors.push(f.label + 'を入力してください。');
  });

  var age = num_(data.age);
  if (age !== null && (age < 0 || age > 120)) errors.push('年齢の値が不正です。');
  if (num_(data.payYears) === 0) errors.push('保険料払込期間は1年以上で入力してください。');
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
  if (field.type === 'date' && raw instanceof Date) return formatSlashDate_(raw);
  return raw == null ? '' : raw;
}
