/**
 * 設定スプレッドシートの読み書き。
 *
 * 運用者がコードを触らずに変えられるものは、すべてここを経由して読む。
 *   設定       … 全体設定（キー・値）
 *   代理店マスタ … 代理店名 → 共有フォルダID
 *   代理店募集人マスタ … 代理店ごとの、共同募集の相手になる募集人（1代理店に何人でも）
 *   募集人マスタ … 自社の募集人の氏名・連絡先・所属代理店
 *   項目設定   … 各入力項目を form / fixed / hidden のどれで扱うか
 *   利用者     … このウェブアプリを使えるGoogleアカウント
 */

var PROP_SETTINGS_ID = 'SETTINGS_SPREADSHEET_ID';

/**
 * 「項目設定」シートの扱い列。シート上は日本語で見せ、コードの中では
 * form / fixed / hidden で扱う。英語表記の古いシートもそのまま読める。
 */
var MODE_LABELS = {
  form:   '入力する',
  fixed:  '固定値を使う',
  hidden: '使わない'
};

var MODE_FROM_LABEL = {
  '入力する': 'form', '固定値を使う': 'fixed', '使わない': 'hidden',
  'form': 'form', 'fixed': 'fixed', 'hidden': 'hidden'
};

var SHEET_SETTINGS = '設定';
var SHEET_AGENCIES = '代理店マスタ';
var SHEET_CO_AGENTS = '代理店募集人マスタ';

/** 設定シートのキー名。コードと Setup.gs で同じ文字列を使うため。 */
var SETTING_DEFAULT_VERIFIER = '既定の検証実施者';
var SHEET_AGENTS   = '募集人マスタ';
var SHEET_FIELDS   = '項目設定';
var SHEET_USERS    = '利用者';
var SHEET_LOG      = '送信ログ';

function settingsSpreadsheet_() {
  var id = PropertiesService.getScriptProperties().getProperty(PROP_SETTINGS_ID);
  if (!id) {
    throw new Error(
      'セットアップが済んでいません。Apps Script エディタで setup() を一度実行してください。');
  }
  return SpreadsheetApp.openById(id);
}

function sheetOrThrow_(name) {
  var sh = settingsSpreadsheet_().getSheetByName(name);
  if (!sh) throw new Error('設定スプレッドシートに「' + name + '」シートがありません。setup() を再実行してください。');
  return sh;
}

/** 見出し行つきシートをオブジェクト配列で読む。 */
function readTable_(name) {
  return readSheetTable_(sheetOrThrow_(name));
}

/** 同上。ただしシートが無ければ空配列を返す（旧い設定スプレッドシート対策）。 */
function readTableIfExists_(name) {
  var sh = settingsSpreadsheet_().getSheetByName(name);
  return sh ? readSheetTable_(sh) : [];
}

function readSheetTable_(sh) {
  var values = sh.getDataRange().getValues();
  if (values.length < 2) return [];
  var header = values[0];
  var rows = [];
  for (var r = 1; r < values.length; r++) {
    var row = values[r];
    // どのシートも1列目がキー。空ならまだ書かれていない行なので飛ばす
    // （チェックボックスだけ入った行を拾わないため）。
    if (String(row[0] == null ? '' : row[0]).trim() === '') continue;
    var o = {};
    for (var c = 0; c < header.length; c++) {
      if (header[c] !== '') o[String(header[c])] = row[c];
    }
    rows.push(o);
  }
  return rows;
}

function isTrue_(v) {
  if (v === true) return true;
  var s = String(v == null ? '' : v).trim().toLowerCase();
  return s === 'true' || s === '1' || s === 'はい' || s === '有効' || s === 'yes' || s === '○';
}

/** 「設定」シートの単一値。 */
function getSetting_(key, fallback) {
  var rows = readTable_(SHEET_SETTINGS);
  for (var i = 0; i < rows.length; i++) {
    if (String(rows[i]['キー']).trim() === key) {
      var v = rows[i]['値'];
      return (v === '' || v == null) ? fallback : v;
    }
  }
  return fallback;
}

/**
 * マスタの読み込み結果を1回の実行の中だけ覚えておく。
 * 一括作成は1行ごとに代理店・募集人を引くので、100代理店 × 数百行になると
 * シートの読み直しだけで実行時間を使い切ってしまう。setup() は書き換えたあとに
 * clearMasterCache_() を呼ぶこと。
 */
var MASTER_CACHE_ = {};

function clearMasterCache_() { MASTER_CACHE_ = {}; }

/**
 * 共有フォルダIDの欄から、フォルダIDを取り出す。
 *
 * Drive のアドレスバーからコピーすると URL 全体が入る。
 *   https://drive.google.com/drive/folders/XXXX?usp=drive_link
 * ID だけを貼るより URL を貼るほうが自然なので、どちらでも通るようにする。
 * 直さないと DriveApp.getFolderById() が URL を ID として扱って失敗する。
 */
function folderIdFromInput_(v) {
  var s = String(v == null ? '' : v).trim();
  if (s === '') return '';

  var m = s.match(/\/folders\/([^\/?#]+)/);      // .../drive/folders/ID?usp=...
  if (m) return m[1];
  m = s.match(/[?&]id=([^&#]+)/);                // 旧形式 ...open?id=ID
  if (m) return m[1];
  m = s.match(/\/d\/([^\/?#]+)/);                // 念のため .../d/ID/...
  if (m) return m[1];

  return s.replace(/[?#].*$/, '');               // ID がそのまま入っている
}

/**
 * 代理店名を突き合わせるためのキー。
 * 「代理店募集人マスタ」の代理店名は設定シート上ではプルダウンから選ぶが、
 * 貼り付けで入った値には前後の空白や全角空白が混じる。表記のゆれだけで
 * 募集人が黙って選択肢から消えるのを防ぐ。
 */
function agencyKey_(name) {
  var t = String(name == null ? '' : name);
  if (String.prototype.normalize) t = t.normalize('NFKC');
  return t.replace(/[\s　]+/g, '');
}

/**
 * 代理店の一覧。
 *
 *   coAgents … 「代理店募集人マスタ」に登録された、その代理店側の募集人
 *   coAgent  … そのうち連名に使う1人（下記）
 *
 * ■ 連名の相手を選ばせない理由
 *
 * 代理店を選べば連名の相手は決まる、という運用にしている。入力欄を1つ減らすため。
 * 相手は「その代理店に1人しかいなければその人」、複数いるなら「代表」に印が
 * 付いている人。どちらでも決まらないときは連名にしない。誰と連名にするか
 * 決められないまま適当な1人を選ぶと、募集していない人の名前が帳票に載る。
 */
function getAgencies_() {
  if (MASTER_CACHE_.agencies) return MASTER_CACHE_.agencies;

  var byAgency = {};
  var repByAgency = {};
  readTableIfExists_(SHEET_CO_AGENTS).forEach(function (r) {
    if (!isTrue_(r['有効'])) return;
    var key = agencyKey_(r['代理店名']);
    var person = String(r['氏名'] || '').trim();
    if (key === '' || person === '') return;
    if (!byAgency[key]) byAgency[key] = [];
    // 同じ人を二度書いても選択肢は1つ。
    if (byAgency[key].indexOf(person) < 0) byAgency[key].push(person);
    // 代表が複数行に付いていたら、先に書いてあるほうを使う。
    if (isTrue_(r['代表']) && !repByAgency[key]) repByAgency[key] = person;
  });

  MASTER_CACHE_.agencies = readTable_(SHEET_AGENCIES)
    .filter(function (r) { return isTrue_(r['有効']) && String(r['代理店名']).trim() !== ''; })
    .map(function (r) {
      var name = String(r['代理店名']).trim();
      var key = agencyKey_(name);
      var list = byAgency[key] || [];
      return {
        name: name,
        folderId: folderIdFromInput_(r['共有フォルダID']),
        coAgents: list,
        coAgent: repByAgency[key] || (list.length === 1 ? list[0] : '')
      };
    });
  return MASTER_CACHE_.agencies;
}

/**
 * この代理店と連名にする募集人の氏名。決まらなければ空文字（単独名義）。
 * マスタが読めない場面（テストなど）でも落とさない。
 */
function coAgentFor_(agencyName) {
  try {
    var a = getAgencyByName_(String(agencyName || '').trim());
    return (a && a.coAgent) || '';
  } catch (e) {
    return '';
  }
}

/**
 * 募集人が複数いるのに「代表」が決まっていない代理店。
 * この状態だと連名にならないまま帳票ができるので、setup() が知らせる。
 */
function agenciesWithoutRepresentative_() {
  return getAgencies_()
    .filter(function (a) { return a.coAgents.length > 1 && !a.coAgent; })
    .map(function (a) { return a.name; });
}

/**
 * 「代理店募集人マスタ」にあるのに、代理店マスタのどの代理店にも結び付かない行。
 * 結び付かない募集人は選択肢に出ないだけで、何も言わずに消える。
 * setup() がこれを見て知らせる。
 */
function orphanCoAgents_() {
  var known = {};
  readTable_(SHEET_AGENCIES).forEach(function (r) {
    var k = agencyKey_(r['代理店名']);
    if (k) known[k] = true;
  });

  var out = [];
  readTableIfExists_(SHEET_CO_AGENTS).forEach(function (r) {
    var raw = String(r['代理店名'] || '').trim();
    var person = String(r['氏名'] || '').trim();
    if (raw === '' || person === '') return;
    if (!known[agencyKey_(raw)]) out.push({ agency: raw, name: person });
  });
  return out;
}

function getAgencyByName_(name) {
  var list = getAgencies_();
  for (var i = 0; i < list.length; i++) if (list[i].name === name) return list[i];
  return null;
}

function getAgents_() {
  if (MASTER_CACHE_.agents) return MASTER_CACHE_.agents;
  MASTER_CACHE_.agents = readTable_(SHEET_AGENTS)
    .filter(function (r) { return isTrue_(r['有効']) && String(r['氏名']).trim() !== ''; })
    .map(function (r) {
      return {
        name:     String(r['氏名']).trim(),
        email:    String(r['メールアドレス'] || '').trim(),
        tel:      String(r['電話番号'] || '').trim(),
        zip:      String(r['郵便番号'] || '').trim(),
        address1: String(r['住所1'] || '').trim(),
        address2: String(r['住所2'] || '').trim(),
        agency:   String(r['所属代理店'] || '').trim(),
        loginEmail: String(r['ログイン用アドレス'] || '').trim(),
        verifier: String(r['検証者'] || '').trim()
      };
    });
  return MASTER_CACHE_.agents;
}

function getAgentByName_(name) {
  var list = getAgents_();
  for (var i = 0; i < list.length; i++) if (list[i].name === name) return list[i];
  return null;
}

/** ログイン中のアドレスに一致する募集人。作成者の初期値に使う。 */
function getAgentByEmail_(email) {
  var e = String(email || '').trim().toLowerCase();
  if (e === '') return null;
  var list = getAgents_();
  for (var i = 0; i < list.length; i++) {
    if (String(list[i].loginEmail).toLowerCase() === e) return list[i];
    if (String(list[i].email).toLowerCase() === e) return list[i];
  }
  return null;
}

/**
 * 適合性確認シートの検証実施者。作成者から決める。
 *
 *   1. 募集人マスタのその人の「検証者」列
 *   2. 空欄なら設定シートの「既定の検証実施者」
 *
 * 作成者自身になってしまう場合は空にする。自分の募集を自分で検証した記録は
 * 検証になっていない。既定の検証実施者その人が作成したときは、その人の行に
 * 「検証者」を入れておけば 1. で拾われる。
 *
 * 募集人を1人足したときも、その人の検証者は既定の人になるので設定は要らない。
 */
function verifierFor_(authorName) {
  var author = String(authorName || '').trim();
  if (author === '') return '';

  var v = '';
  try {
    var a = getAgentByName_(author);
    if (a && a.verifier) v = a.verifier;
    if (v === '') v = String(getSetting_(SETTING_DEFAULT_VERIFIER, '')).trim();
  } catch (e) {
    return '';
  }
  return v === author ? '' : v;
}

/**
 * 検証実施者が決まらない募集人。setup() が知らせる。
 * 既定の検証実施者その人だけは、自分の行の「検証者」で決める必要がある。
 */
function agentsWithoutVerifier_() {
  return getAgents_()
    .filter(function (a) { return verifierFor_(a.name) === ''; })
    .map(function (a) { return a.name; });
}

/**
 * 項目設定を { key: {mode, fixedValue} } で返す。
 * シートに行がない項目は FIELD_DEFS の defaultMode を使う。
 */
function getFieldConfig_() {
  var conf = {};
  FIELD_DEFS.forEach(function (f) {
    conf[f.key] = { mode: f.defaultMode || 'form', fixedValue: '' };
  });
  readTable_(SHEET_FIELDS).forEach(function (r) {
    var key = String(r['項目キー']).trim();
    if (!conf[key]) return;
    // 見出しは「扱い」。英語表記だった頃の「モード」列も読めるようにしておく。
    var raw = r['扱い'] != null && r['扱い'] !== '' ? r['扱い'] : r['モード'];
    var mode = MODE_FROM_LABEL[String(raw == null ? '' : raw).trim()];
    if (mode) conf[key].mode = mode;
    conf[key].fixedValue = r['固定値'] == null ? '' : r['固定値'];
  });
  return conf;
}

/** 利用を許可されたメールアドレス（小文字）の配列。 */
function getAllowedEmails_() {
  return readTable_(SHEET_USERS)
    .filter(function (r) { return isTrue_(r['有効']); })
    .map(function (r) { return String(r['メールアドレス']).trim().toLowerCase(); })
    .filter(function (e) { return e !== ''; });
}
