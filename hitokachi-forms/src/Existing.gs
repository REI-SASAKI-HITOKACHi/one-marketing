/**
 * 作成済み帳票の索引。
 *
 * 「この顧客の帳票はもう作ってあるか」を Drive から調べて、設定スプレッドシートの
 * 「作成済み索引」シートに控える。取り込みのときはこの索引を見るので、1 行ごとに
 * Drive を叩かずに済む。
 *
 * ■ なぜ索引を作るか
 *
 * 顧客フォルダの中身を見るには、顧客ごとに 1 回ずつ Drive を呼ぶ必要がある。
 * 100 人いれば 100 回。取り込みのたびにこれをやると 6 分の実行上限に当たる。
 * 代理店ごとに一度まとめて調べて控えておき、取り込みは控えを引くだけにする。
 *
 * ■ 途中で 6 分に当たったら
 *
 * フォルダの読み出し位置（継続トークン）を控えて中断し、1 分後に自分で続きを走らせる。
 * 一括作成と同じやり方。途中まで調べた分は索引に残るので、やり直しにはならない。
 */

var SHEET_EXISTING = '作成済み索引';

var EXISTING_HEADER = [
  '代理店名', '顧客フォルダ名', '照合キー', '適合性確認シート', '意向把握シート',
  'フォルダID', '調べた日時'
];

/** 6分の実行時間制限に対する余裕。 */
var SCAN_BUDGET_MS = 4.5 * 60 * 1000;
var SCAN_RESUME_FUNCTION = 'resumeScan';
var PROP_SCAN_STATE = 'EXISTING_SCAN_STATE';

/** 帳票のファイル名の頭。saveOne_ が付ける名前と揃えておくこと。 */
var SUIT_FILE_PREFIX   = '適合性確認シート';
var INTENT_FILE_PREFIX = '意向把握シート';

/** 伏せ字に使われる記号。 */
var MASK_CHARS = /[*＊●○◯×■□]/;

/* ------------------------------------------------------------------ *
 * 索引を作る
 * ------------------------------------------------------------------ */

/** メニュー用。全代理店を調べ直す。 */
function rebuildExistingIndex() {
  PropertiesService.getScriptProperties().deleteProperty(PROP_SCAN_STATE);
  clearScanTriggers_();
  var sh = existingSheet_();
  if (sh.getLastRow() > 1) {
    sh.getRange(2, 1, sh.getLastRow() - 1, EXISTING_HEADER.length).clearContent();
  }
  scanExisting_();
}

/** 時限トリガーからの続き。 */
function resumeScan() {
  clearScanTriggers_();
  scanExisting_();
}

/** 調べている途中を打ち切る。 */
function stopScan() {
  PropertiesService.getScriptProperties().deleteProperty(PROP_SCAN_STATE);
  clearScanTriggers_();
  toast_('作成済み索引の調査を止めました。');
}

function scanExisting_() {
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(10000)) {
    scheduleScanResume_();
    return toast_('ほかの処理が動いています。1分後に自動でやり直します。');
  }

  try {
    var started = Date.now();
    var props = PropertiesService.getScriptProperties();
    var state = readScanState_(props);
    var agencies = getAgencies_().filter(function (a) { return a.folderId; });
    var sh = existingSheet_();
    var stamp = new Date();
    var rows = [];
    var scanned = 0;

    while (state.agencyIndex < agencies.length) {
      var agency = agencies[state.agencyIndex];
      var it;
      try {
        it = state.token
          ? DriveApp.continueFolderIterator(state.token)
          : DriveApp.getFolderById(agency.folderId).getFolders();
      } catch (e) {
        // フォルダIDが違う・権限がないなど。その代理店は飛ばして次へ進む。
        // ここで止めると、以降の代理店がいつまでも調べられない。
        Logger.log('代理店「' + agency.name + '」の共有フォルダを開けません: ' + e.message);
        state.agencyIndex++;
        state.token = '';
        continue;
      }

      var timedOut = false;
      while (it.hasNext()) {
        if (Date.now() - started > SCAN_BUDGET_MS) { timedOut = true; break; }
        var folder = it.next();
        var found = inspectCustomerFolder_(folder);
        rows.push([
          agency.name, folder.getName(), normalizeName_(folder.getName()),
          found.suitability, found.intent, folder.getId(), stamp
        ]);
        scanned++;
      }

      if (timedOut) {
        state.token = it.getContinuationToken();
        appendExistingRows_(sh, rows);
        writeScanState_(props, state);
        scheduleScanResume_();
        return toast_(scanned + ' 件まで調べました。1分後に自動で続きを調べます。');
      }

      state.agencyIndex++;
      state.token = '';
    }

    appendExistingRows_(sh, rows);
    props.deleteProperty(PROP_SCAN_STATE);
    toast_('作成済み索引を更新しました（' + scanned + ' 件の顧客フォルダを調べました）。');
  } finally {
    lock.releaseLock();
  }
}

/** 顧客フォルダの中に、どちらの帳票があるかを見る。 */
function inspectCustomerFolder_(folder) {
  var out = { suitability: false, intent: false };
  var it = folder.getFiles();
  while (it.hasNext()) {
    var name = String(it.next().getName());
    if (name.indexOf(SUIT_FILE_PREFIX) === 0) out.suitability = true;
    if (name.indexOf(INTENT_FILE_PREFIX) === 0) out.intent = true;
    if (out.suitability && out.intent) break;
  }
  return out;
}

function existingSheet_() {
  var ss = settingsSpreadsheet_();
  var sh = ss.getSheetByName(SHEET_EXISTING);
  if (!sh) {
    sh = ss.insertSheet(SHEET_EXISTING);
    sh.getRange(1, 1, 1, EXISTING_HEADER.length).setValues([EXISTING_HEADER])
      .setFontWeight('bold').setBackground('#efefef');
    sh.setFrozenRows(1);
    sh.getRange(1, 1).setNote(
      'メニューの「作成済みの帳票を調べ直す」で作られる控えです。\n'
      + 'Drive を1行ずつ見に行かなくて済むように、ここに結果を置いています。\n'
      + '手で書き換える必要はありません。');
  }
  return sh;
}

function appendExistingRows_(sh, rows) {
  if (!rows.length) return;
  sh.getRange(sh.getLastRow() + 1, 1, rows.length, EXISTING_HEADER.length).setValues(rows);
}

function readScanState_(props) {
  try {
    var raw = props.getProperty(PROP_SCAN_STATE);
    if (raw) {
      var o = JSON.parse(raw);
      return { agencyIndex: Number(o.agencyIndex) || 0, token: String(o.token || '') };
    }
  } catch (e) { /* 壊れていたら最初から */ }
  return { agencyIndex: 0, token: '' };
}

function writeScanState_(props, state) {
  props.setProperty(PROP_SCAN_STATE, JSON.stringify(state));
}

function scheduleScanResume_() {
  clearScanTriggers_();
  ScriptApp.newTrigger(SCAN_RESUME_FUNCTION).timeBased().after(60 * 1000).create();
}

function clearScanTriggers_() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === SCAN_RESUME_FUNCTION) ScriptApp.deleteTrigger(t);
  });
}

/* ------------------------------------------------------------------ *
 * 索引を引く
 * ------------------------------------------------------------------ */

/** 氏名が伏せ字を含むか。 */
function isMaskedName_(name) {
  return MASK_CHARS.test(String(name == null ? '' : name));
}

/**
 * 伏せ字より前の、確実に読める部分。
 * 「山＊太郎」なら「山」。照合はこの前方一致で行う。
 */
function unmaskedPrefix_(name) {
  var n = normalizeName_(name);
  var m = n.search(MASK_CHARS);
  return m < 0 ? n : n.slice(0, m);
}

/**
 * 索引を引ける形にして返す。
 * @return {Object} { byKey: {代理店名+照合キー: [entry]}, byAgency: {代理店名: [entry]} }
 */
function loadExistingIndex_() {
  var rows = readTableIfExists_(SHEET_EXISTING);
  var byKey = {};
  var byAgency = {};
  rows.forEach(function (r) {
    var entry = {
      agency: String(r['代理店名'] || '').trim(),
      folderName: String(r['顧客フォルダ名'] || '').trim(),
      key: String(r['照合キー'] || '').trim(),
      suitability: isTrue_(r['適合性確認シート']),
      intent: isTrue_(r['意向把握シート']),
      folderId: String(r['フォルダID'] || '').trim()
    };
    if (!entry.key) return;
    var k = entry.agency + '\t' + entry.key;
    if (!byKey[k]) byKey[k] = [];
    byKey[k].push(entry);
    if (!byAgency[entry.agency]) byAgency[entry.agency] = [];
    byAgency[entry.agency].push(entry);
  });
  return { byKey: byKey, byAgency: byAgency };
}

/**
 * この顧客の帳票が作ってあるかを索引から調べる。
 *
 * 伏せ字入りの氏名は、読める部分の前方一致で候補を探すだけにして、
 * 「作成済み」とも「未作成」とも決めない。前方一致で別人に当ててしまうと、
 * 作られていない帳票を作成済みと誤判定したり、年収を含む帳票を他人の
 * フォルダに保存したりする。人が確かめる。
 *
 * @return {Object} { status, entry, candidates, message }
 *   status: 'done'（要るものが揃っている）/ 'partial'（片方だけ）/
 *           'missing'（無い）/ 'ambiguous'（人が確かめる）
 */
function lookupExisting_(index, agencyName, customerName, wantSuitability) {
  var agency = String(agencyName || '').trim();

  if (isMaskedName_(customerName)) {
    var prefix = unmaskedPrefix_(customerName);
    var pool = index.byAgency[agency] || [];
    // 読める部分が1文字も無ければ、探しようがない。
    var hits = prefix === '' ? [] : pool.filter(function (e) {
      return e.key.indexOf(prefix) === 0;
    });
    return {
      status: 'ambiguous',
      entry: null,
      candidates: hits,
      message: '氏名が伏せ字（' + customerName + '）です。'
        + (hits.length
            ? '前方一致の候補: ' + hits.map(function (e) { return e.folderName; }).join('、')
            : '前方一致する顧客フォルダはありません')
        + '。正しい氏名に直してから作成してください。'
    };
  }

  var key = agency + '\t' + normalizeName_(customerName);
  var found = index.byKey[key] || [];
  if (!found.length) {
    return { status: 'missing', entry: null, candidates: [], message: '' };
  }

  // 同じ照合キーのフォルダが複数あるのは、表記違いで二重にできている状態。
  if (found.length > 1) {
    return {
      status: 'ambiguous', entry: null, candidates: found,
      message: '同じ名前とみなせる顧客フォルダが ' + found.length + ' 件あります（'
        + found.map(function (e) { return e.folderName; }).join('、') + '）。'
        + '別人の可能性があるため、1 件ずつのフォームで作成してください。'
    };
  }

  var e = found[0];
  var enough = wantSuitability ? (e.suitability && e.intent) : e.intent;
  if (enough) {
    return { status: 'done', entry: e, candidates: found, message: '作成済み' };
  }
  var lacking = [];
  if (!e.intent) lacking.push('意向把握シート');
  if (wantSuitability && !e.suitability) lacking.push('適合性確認シート');
  return {
    status: 'partial', entry: e, candidates: found,
    message: 'フォルダ「' + e.folderName + '」はありますが、' + lacking.join('と') + 'がありません。'
  };
}
