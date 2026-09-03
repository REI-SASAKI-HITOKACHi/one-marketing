/**
 * 保存先フォルダの解決。
 *
 * 代理店ごとの共有フォルダの直下から顧客フォルダを探す。名前の表記ゆれで
 * 顧客フォルダが二重にできる事故を防ぐため、比較は正規化した名前で行い、
 * 既存フォルダに当たった場合は必ず利用者に確認させる（勝手に保存しない）。
 */

/**
 * 人名でよく揺れる異体字。左を右に寄せてから比較する。
 * 揺れが見つかったらここに足す（左が異体字、右が寄せ先）。
 */
var NAME_VARIANTS = {
  '髙': '高', '﨑': '崎', '嵜': '崎', '濵': '浜', '濱': '浜',
  '邊': '辺', '邉': '辺', '齋': '斎', '齊': '斎', '冨': '富',
  '桒': '桑', '寶': '宝', '澤': '沢', '瀨': '瀬', '德': '徳',
  '眞': '真', '藪': '薮', '籔': '薮', '曾': '曽', '國': '国',
  '廣': '広', '惠': '恵', '晉': '晋', '槇': '槙', '嶋': '島',
  '嶌': '島', '栁': '柳', '瀧': '滝', '淸': '清', '寬': '寛'
};

/**
 * 比較用に名前を正規化する。
 * NFKC で全角英数字・記号を揃え、敬称と空白を落とし、異体字を寄せる。
 */
function normalizeName_(s) {
  var t = String(s == null ? '' : s);
  if (String.prototype.normalize) t = t.normalize('NFKC');
  t = t.replace(/[様さん殿御中]+$/, '');
  t = t.replace(/[\s　]+/g, '');
  var out = '';
  for (var i = 0; i < t.length; i++) {
    var ch = t.charAt(i);
    out += (NAME_VARIANTS[ch] || ch);
  }
  return out.toLowerCase();
}

/** Drive のフォルダ名に使えない文字を落とす。 */
function sanitizeFileName_(s) {
  return String(s == null ? '' : s).replace(/[\/\\:*?"<>|]/g, '_').replace(/^\.+/, '').trim();
}

/**
 * 代理店フォルダ直下から、顧客名に一致するフォルダを探す。
 * 戻り値は { id, name } の配列（0件＝新規作成、1件＝要確認、2件以上＝要選択）。
 */
function findCustomerFolders_(agencyFolderId, customerName) {
  var target = normalizeName_(customerName);
  if (target === '') return [];
  var parent = DriveApp.getFolderById(agencyFolderId);
  var it = parent.getFolders();
  var hits = [];
  while (it.hasNext()) {
    var f = it.next();
    if (normalizeName_(f.getName()) === target) {
      hits.push({ id: f.getId(), name: f.getName() });
    }
  }
  return hits;
}

/** 顧客フォルダを新規作成する。 */
function createCustomerFolder_(agencyFolderId, customerName) {
  var name = sanitizeFileName_(customerName);
  if (!name) throw new Error('顧客フォルダ名が空です。');
  var folder = DriveApp.getFolderById(agencyFolderId).createFolder(name);
  return { id: folder.getId(), name: folder.getName() };
}

/**
 * 保存先の候補を返す。ウェブアプリはこれを確認画面に出す。
 *   status: 'new'       … 既存なし。新規作成する
 *           'match'     … 1件ヒット。既存に保存するか新規作成するかを選ばせる
 *           'ambiguous' … 複数ヒット。どれに保存するかを選ばせる
 */
function resolveDestination_(agencyName, customerName) {
  var agency = getAgencyByName_(agencyName);
  if (!agency) throw new Error('代理店「' + agencyName + '」が代理店マスタにありません。');
  if (!agency.folderId) throw new Error('代理店「' + agencyName + '」に共有フォルダIDが設定されていません。');

  var agencyFolder;
  try {
    agencyFolder = DriveApp.getFolderById(agency.folderId);
  } catch (e) {
    throw new Error('代理店「' + agencyName + '」の共有フォルダにアクセスできません。'
      + 'フォルダIDが正しいか、あなたに編集権限があるかを確認してください。');
  }

  var hits = findCustomerFolders_(agency.folderId, customerName);
  return {
    agencyName: agency.name,
    agencyFolderId: agency.folderId,
    agencyFolderName: agencyFolder.getName(),
    customerName: customerName,
    newFolderName: sanitizeFileName_(customerName),
    candidates: hits,
    status: hits.length === 0 ? 'new' : (hits.length === 1 ? 'match' : 'ambiguous')
  };
}

/** 確認画面での選択（既存フォルダID または 'new'）を実フォルダに変換する。 */
function materializeDestination_(agencyName, customerName, choice) {
  var agency = getAgencyByName_(agencyName);
  if (!agency) throw new Error('代理店「' + agencyName + '」が代理店マスタにありません。');

  if (choice && choice !== 'new') {
    var folder = DriveApp.getFolderById(choice);
    // 選択されたフォルダが本当にこの代理店フォルダの直下かを確かめる。
    var parents = folder.getParents();
    var ok = false;
    while (parents.hasNext()) {
      if (parents.next().getId() === agency.folderId) { ok = true; break; }
    }
    if (!ok) throw new Error('選択されたフォルダは代理店「' + agencyName + '」の共有フォルダの直下にありません。');
    return { id: folder.getId(), name: folder.getName(), created: false };
  }

  var created = createCustomerFolder_(agency.folderId, customerName);
  created.created = true;
  return created;
}
