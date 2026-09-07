/**
 * グループLINE 受け口（Webhook）
 *
 * 【これは何か】
 *   内部用のLINE公式アカウントを3人グループ（佐々木さん・渡辺さん・CMO）に入れ、
 *   グループでの発言をスプレッドシートのタブ「LINE_ログ」に溜めるための受け口。
 *   溜まったものをCMOが読みに行く。CMOからの発信は tools/line_client.py で行う。
 *
 * 【なぜNetlifyではなくApps Scriptか】
 *   Netlifyに置くと、シートへ書くためのサービスアカウント鍵をNetlify側にも
 *   持たせることになる。鍵の複製は増やしたくない。
 *   Apps Scriptなら佐々木さんの権限でそのままシートに書けるので、
 *   新しい鍵をどこにも置かずに済む。
 *
 * 【入れ方】
 *   スプレッドシート → 拡張機能 → Apps Script → このコードを貼り付けて保存
 *   → 右上［デプロイ］→［新しいデプロイ］
 *   → 種類の選択（歯車）→［ウェブアプリ］
 *   → 次のとおり設定してデプロイ
 *        説明          ： LINE webhook
 *        次のユーザーとして実行： 自分
 *        アクセスできるユーザー： 全員          ← ★ここが「全員」でないとLINEから届きません
 *   → 表示されたウェブアプリのURLを控える（https://script.google.com/macros/s/.../exec）
 *   → LINE Developers の［Messaging API設定］→［Webhook URL］にそのURLを貼る
 *   → ［Webhookの利用］をオンにする
 *
 * 【★正直に書いておく制約】
 *   Apps Script の doPost はリクエストヘッダーを受け取れない。
 *   そのため LINE の X-Line-Signature による署名検証ができない。
 *   代わりに次で守っている。
 *     ・ウェブアプリURLは推測できない長いランダム文字列
 *     ・SETTEI.kyokaGroupId を設定すれば、そのグループ以外のイベントは捨てる
 *   社内連絡の用途なので、この程度で釣り合うと判断している。
 *   お客様の個人情報をこの経路に流さないこと。
 */

var SETTEI = {
  /** 書き込み先のタブ名。無ければ自動で作る */
  logTab: 'LINE_ログ',

  /**
   * 受け付けるグループID。
   * 最初は空のままでよい（空なら全部受ける）。
   * グループにアカウントを招待すると join イベントが届き、
   * 下の kakunin() でグループIDが分かるので、それをここに貼る。
   */
  kyokaGroupId: '',
};

// ============================== 受け口 ==============================

function doPost(e) {
  try {
    var body = JSON.parse(e.postData.contents);
    var events = body.events || [];
    var sh = logSheet_();
    var ima = new Date();

    events.forEach(function (ev) {
      var src = ev.source || {};
      var gid = src.groupId || src.roomId || '';

      // 許可グループを決めてあるなら、それ以外は捨てる
      if (SETTEI.kyokaGroupId && gid !== SETTEI.kyokaGroupId) return;

      var honbun = '';
      if (ev.type === 'message') {
        var m = ev.message || {};
        honbun = (m.type === 'text') ? m.text : '［' + m.type + '］';
      } else if (ev.type === 'join') {
        honbun = '（このグループに参加しました）';
      } else if (ev.type === 'leave') {
        honbun = '（このグループから退出しました）';
      } else if (ev.type === 'memberJoined') {
        honbun = '（メンバーが参加しました）';
      }

      sh.appendRow([
        ima,                                   // 受信日時
        ev.type,                               // イベント種別
        gid,                                   // グループID
        src.userId || '',                      // 発言者のユーザーID
        hyoujimei_(src.userId, gid),           // 発言者の表示名
        honbun,                                // 本文
        (ev.message && ev.message.id) || '',   // メッセージID
        '',                                    // CMO確認済み（読んだら印を付ける）
        JSON.stringify(ev),                    // 生データ（後から追える）
      ]);
    });
  } catch (err) {
    logSheet_().appendRow([new Date(), 'ERROR', '', '', '', String(err), '', '', '']);
  }

  // LINEには必ず200を返す。返さないとWebhookが無効化されることがある
  return ContentService.createTextOutput(JSON.stringify({ ok: true }))
    .setMimeType(ContentService.MimeType.JSON);
}

/** ブラウザで開いたときの表示（動作確認用） */
function doGet() {
  return ContentService.createTextOutput('one-hitter line webhook: ok');
}

// ============================== 部品 ==============================

function logSheet_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(SETTEI.logTab);
  if (!sh) {
    sh = ss.insertSheet(SETTEI.logTab);
    sh.appendRow(['受信日時', '種別', 'グループID', 'ユーザーID', '表示名',
                  '本文', 'メッセージID', 'CMO確認', '生データ']);
    sh.setFrozenRows(1);
    sh.getRange(1, 1, 1, 9).setFontWeight('bold')
      .setBackground('#334455').setFontColor('#ffffff');
    sh.setColumnWidth(1, 140);
    sh.setColumnWidth(5, 110);
    sh.setColumnWidth(6, 420);
    sh.hideColumns(3, 2);   // グループIDとユーザーIDは普段見えなくてよい
    sh.hideColumns(9);      // 生データも普段は隠す
  }
  return sh;
}

/**
 * 発言者の表示名を取る。
 * スクリプトプロパティ LINE_TOKEN にチャネルアクセストークンを入れておくと使える。
 * （Apps Script の ［プロジェクトの設定］→［スクリプト プロパティ］で追加）
 * 入れていなければ空欄になるだけで、記録自体は問題なく動く。
 */
function hyoujimei_(userId, groupId) {
  if (!userId) return '';
  var tok = PropertiesService.getScriptProperties().getProperty('LINE_TOKEN');
  if (!tok) return '';
  var url = groupId
    ? 'https://api.line.me/v2/bot/group/' + groupId + '/member/' + userId
    : 'https://api.line.me/v2/bot/profile/' + userId;
  try {
    var res = UrlFetchApp.fetch(url, {
      headers: { Authorization: 'Bearer ' + tok },
      muteHttpExceptions: true,
    });
    if (res.getResponseCode() !== 200) return '';
    return JSON.parse(res.getContentText()).displayName || '';
  } catch (err) {
    return '';
  }
}

// ============================== 確認用 ==============================

/**
 * グループにアカウントを招待したあと、これを実行する。
 * ログに届いた join イベントからグループIDを拾って表示する。
 * 表示されたIDを SETTEI.kyokaGroupId に貼れば、他所からのイベントを弾けるようになる。
 */
function kakunin() {
  var sh = logSheet_();
  var last = sh.getLastRow();
  if (last < 2) { Logger.log('まだ1件も届いていません。グループで何か発言してみてください。'); return; }
  var atai = sh.getRange(2, 1, last - 1, 6).getValues();
  var ids = {};
  atai.forEach(function (r) { if (r[2]) ids[r[2]] = (ids[r[2]] || 0) + 1; });
  Logger.log('■ 届いているグループID');
  Object.keys(ids).forEach(function (k) { Logger.log('  ' + k + '  （' + ids[k] + '件）'); });
  Logger.log('');
  Logger.log('■ 直近5件');
  atai.slice(-5).forEach(function (r) {
    Logger.log('  ' + Utilities.formatDate(new Date(r[0]), 'Asia/Tokyo', 'M/d HH:mm')
               + ' [' + r[1] + '] ' + (r[4] || r[3]) + ' : ' + r[5]);
  });
}
