/**
 * 作業完了フォームの施工写真を、オーナーのドライブ「施工写真_お客様別（自動）」に取り込む（T056・T064）
 *
 * 【なぜこれが要るか】
 *   写真の元は Netlify の作業完了フォームの提出にしか無い。
 *   サービスアカウントは Google の仕様でドライブの容量が0で、写真ファイルを置けない（403 storageQuota）。
 *   そこで、置き場所の決定（お客様の特定・台帳の顧客IDとの突き合わせ・フォルダ作り）は
 *   tools/shashin-drive.py（サービスアカウント）が行い、シート「_写真取り込み待ち（自動・消さない）」に
 *   1枚1行で載せる。このスクリプトはオーナーのアカウントで1時間ごとに動き、載っている写真を
 *   URL から取ってきて指定のフォルダに保存するだけ。お客様の判断は一切しない。
 *   新しい鍵をどこにも置かずに済む（tools/booking-api.gs と同じ判断）。
 *
 * 【入れ方】（オーナーのアカウントで1回だけ・約2分）
 *   1. ドライブで「施工写真_お客様別（自動）」→「_写真取り込み待ち（自動・消さない）」を開く
 *   2. 拡張機能 → Apps Script → 中身をこのファイルに置き換えて保存
 *   3. 上の関数の選択で「setup」を選んで ▶実行 →「権限を確認」→ アカウントを選ぶ →
 *      （「確認されていません」と出たら「詳細」→「…に移動」）→「許可」
 *   4. 実行ログに「取り込み：済 ◯枚」と出れば完了。以後は1時間ごとに自動で動く
 *
 * 【シートの列】A 提出ID／B フォルダID／C ファイル名／D 写真URL／E 状態（空＝待ち・済・失敗: …）／F ファイルID／G 日時
 *   E が空の行だけを処理する。同じフォルダに同じ名前のファイルがあれば、取り直さずに「済」にする（二重に入れない）。
 *   失敗の行は shashin-drive.py が次の回に空へ戻して、もう一度取らせる。
 *   写真を消す処理は持たない。
 */

var MACHI_ID = '1-Q3F4-FvLxvkKwhYFx3W476pjYTOOF32ycUVRTCCGNY';
var JIKAN_MS = 4.5 * 60 * 1000;   // 1回の実行の上限（Apps Script は6分で止まる）

function torikomi() {
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(1000)) return;
  try {
    var sh = SpreadsheetApp.openById(MACHI_ID).getSheets()[0];
    var n = sh.getLastRow();
    if (n < 2) return;
    var rows = sh.getRange(2, 1, n - 1, 7).getValues();
    var hajime = Date.now(), zumi = 0, ochi = 0, folders = {};
    for (var i = 0; i < rows.length; i++) {
      var r = rows[i];
      if (!r[0] || r[4] !== '') continue;
      if (Date.now() - hajime > JIKAN_MS) break;
      try {
        var f = folders[r[1]] || (folders[r[1]] = DriveApp.getFolderById(r[1]));
        var aru = f.getFilesByName(r[2]);
        var id;
        if (aru.hasNext()) {
          id = aru.next().getId();
        } else {
          var res = UrlFetchApp.fetch(r[3], { muteHttpExceptions: true });
          if (res.getResponseCode() !== 200) throw new Error('HTTP ' + res.getResponseCode());
          id = f.createFile(res.getBlob().setName(r[2])).getId();
        }
        sh.getRange(i + 2, 5, 1, 3).setValues([['済', id, new Date()]]);
        zumi++;
      } catch (e) {
        sh.getRange(i + 2, 5, 1, 3).setValues([['失敗: ' + String(e.message).slice(0, 200), '', new Date()]]);
        ochi++;
      }
    }
    Logger.log('取り込み：済 ' + zumi + '枚／失敗 ' + ochi + '枚');
  } finally {
    lock.releaseLock();
  }
}

/** 1回だけ実行する。1時間ごとのトリガーを入れ（重複は作らない）、その場で1回取り込む。 */
function setup() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'torikomi') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('torikomi').timeBased().everyHours(1).create();
  torikomi();
}
