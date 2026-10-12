/**
 * 提携先の見積依頼から自動で作った見積書を、PDF にして嶺さんの Gmail に「下書き」として作る（送信はしない）
 *
 * 【なぜこれが要るか】
 *   2026-10-10 オーナー「見積依頼が入ったら和真と僕へ通知＋見積書の自動作成＋メール下書きまでセットしたい」。
 *   通知と見積書のタブ作成は tools/partner-inbox.py（サービスアカウント）が行う。
 *   ただしサービスアカウントは嶺さんの Gmail に触れず、CMO の Gmail コネクタも PDF を添付できない。
 *   そこで partner-inbox.py が「【保存先】見積/請求/領収書」のタブ「_下書き待ち（自動・消さない）」に1件1行で載せ、
 *   このスクリプト（嶺さんのアカウントで5分ごと）が、その見積書タブを PDF にして下書きを作る。
 *   新しい鍵をどこにも置かずに済む（tools/shashin-torikomi.gs と同じ判断）。**送信は必ず嶺さんが手で行う。**
 *
 * 【入れ方】（嶺さんのアカウントで1回だけ・約2分）
 *   1. スプレッドシート「【保存先】見積/請求/領収書」を開く
 *   2. 拡張機能 → Apps Script → 中身をこのファイルに置き換えて保存
 *   3. 関数の選択で「setup」を選んで ▶実行 →「権限を確認」→ アカウントを選ぶ →
 *      （「確認されていません」と出たら「詳細」→「…に移動」）→「許可」
 *   4. 実行ログに「下書き：◯件」と出れば完了。以後は5分ごとに自動で動く
 *
 * 【印影】嶺さんのドライブの「電子印影_角印.png」を、見積書の社名・住所の右に重ねてから PDF にする（inei()）。
 *
 * 【シートの列】A 状態（空＝待ち・下書き済・失敗: …）／B 載せた日時／C 見積書タブの gid／D 見積番号／E 宛先／F 件名／G 本文／H PDFの名前／I 下書きを作った日時
 *   A が空の行だけを処理する。下書きを消す・送る処理は持たない。
 */

var MACHI = '_下書き待ち（自動・消さない）';

function shitagaki() {
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(1000)) return;
  try {
    var ss = SpreadsheetApp.getActiveSpreadsheet() || SpreadsheetApp.openById('12NMMswkvumA1BjKxU1HrqMQjFgRUJNz4YMiC4m6QSu0');
    var sh = ss.getSheetByName(MACHI);
    if (!sh || sh.getLastRow() < 2) { Logger.log('下書き：0件'); return; }
    var rows = sh.getRange(2, 1, sh.getLastRow() - 1, 9).getValues(), n = 0;
    for (var i = 0; i < rows.length; i++) {
      var r = rows[i];
      if (r[0] !== '' || !r[2]) continue;
      try {
        var sh2 = ss.getSheets().filter(function (x) { return String(x.getSheetId()) === String(r[2]); })[0];
        if (!sh2) throw new Error('見積書のタブが見つからない（gid ' + r[2] + '）');
        var nInei = inei(sh2);
        SpreadsheetApp.flush();
        var url = 'https://docs.google.com/spreadsheets/d/' + ss.getId() + '/export?format=pdf&gid=' + r[2] +
          '&size=A4&portrait=true&fitw=true&gridlines=false&printtitle=false&sheetnames=false&pagenum=UNDEFINED&r1=0&c1=0&r2=33&c2=6';
        var pdf = UrlFetchApp.fetch(url, { headers: { Authorization: 'Bearer ' + ScriptApp.getOAuthToken() } }).getBlob().setName(r[7] || ('見積書_' + r[3] + '.pdf'));
        GmailApp.createDraft(r[4], r[5], r[6], { attachments: [pdf], name: 'ワンヒッター株式会社 佐々木 嶺' });
        sh.getRange(i + 2, 1).setValue('下書き済');
        sh.getRange(i + 2, 9).setValue(new Date());
        n++;
      } catch (e) {
        sh.getRange(i + 2, 1).setValue('失敗: ' + e.message);
      }
    }
    Logger.log('下書き：' + n + '件');
  } finally {
    lock.releaseLock();
  }
}

/**
 * 印影を入れる（2026-10-10 オーナー「見積書の印影も入れて」）。
 * 印影は嶺さんのドライブ「OneHitter」フォルダの「電子印影_角印.png」（INEI_ID）。Sheets API では画像を置けないので、
 * ここで見積書の社名・住所の右（F7）に重ねる。画像を外に出さずに済む（このスクリプトは嶺さんのアカウントで動く）。
 * 見本タブを複製した見積書には、35行目より下に過去の見積書の貼り付け画像が残っているので、先に消す。PDF は1〜33行目だけ。
 */
var INEI_ID = '1lXhLKinEfH01xXX7o2wm1P7NW7guFyq6';

function inei(sh) {
  sh.getImages().forEach(function (im) { if (im.getAnchorCell().getRow() > 34) im.remove(); });
  var last = sh.getMaxRows();
  if (last > 34) sh.deleteRows(35, last - 34);
  if (sh.getImages().some(function (im) { return im.getAltTextTitle() === '印影'; })) return 0;
  var im = sh.insertImage(DriveApp.getFileById(INEI_ID).getBlob(), 6, 7, 30, 0);
  im.setWidth(76).setHeight(76).setAltTextTitle('印影');
  return 1;
}

function setup() {
  ScriptApp.getProjectTriggers().forEach(function (t) { if (t.getHandlerFunction() === 'shitagaki') ScriptApp.deleteTrigger(t); });
  ScriptApp.newTrigger('shitagaki').timeBased().everyMinutes(5).create();
  shitagaki();
}
