/**
 * 協力店ネット（仮称）デモの保存先（Apps Script ウェブアプリ）
 *
 * 【これは何か】
 *   network/demo/index.html は、そのままだと開いた端末の中（localStorage）にだけ
 *   データを持つ。9/26 に「和真さんのスマホで手を挙げる → オーナーのスマホで決める」
 *   のように 2台で見せたいときは、この受け口を入れると同じデータを共有できる。
 *
 * 【入れ方】（予約フォームの booking-api.gs と同じ手順）
 *   1. 任意のスプレッドシート（新規でよい）→ 拡張機能 → Apps Script → このコードを貼る
 *   2. 右上［デプロイ］→［新しいデプロイ］→ 種類：ウェブアプリ
 *        次のユーザーとして実行 ： 自分
 *        アクセスできるユーザー ： 全員
 *   3. /exec のURLを控えて  python3 tools/build-network-demo.py --api <URL>
 *
 * 【★正直に書いておく制約】
 *   ・doGet/doPost は送信元を検証できない。URLを知っていれば誰でも書ける。
 *     デモ用途（架空データ）に限る。本番はここに載せない。
 *   ・保存は「状態のJSONを丸ごと1セルに置く」だけ。同時に2人が操作すると後勝ち。
 *     デモでは問題にならないが、本番の設計ではない。
 */

var SETTEI = {
  sheetId: '',          // 空ならこのスクリプトが紐づくシート
  tab: 'network_demo',  // 状態を置くタブ。無ければ作る
};

function sheet_() {
  var ss = SETTEI.sheetId ? SpreadsheetApp.openById(SETTEI.sheetId) : SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(SETTEI.tab);
  if (!sh) {
    sh = ss.insertSheet(SETTEI.tab);
    sh.getRange('A1').setValue('state_json');
    sh.getRange('B1').setValue('updated_at');
  }
  return sh;
}

function out_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

function doGet(e) {
  var action = (e && e.parameter && e.parameter.action) || 'load';
  if (action !== 'load') return out_({ ok: false, error: 'unknown action' });
  var sh = sheet_();
  var raw = sh.getRange('A2').getValue();
  var state = null;
  if (raw) { try { state = JSON.parse(raw); } catch (err) { state = null; } }
  return out_({ ok: true, state: state, updated_at: String(sh.getRange('B2').getValue() || '') });
}

function doPost(e) {
  var body = {};
  try { body = JSON.parse(e.postData.contents || '{}'); } catch (err) { return out_({ ok: false, error: 'bad json' }); }
  if (body.action !== 'save' || !body.state) return out_({ ok: false, error: 'unknown action' });
  var json = JSON.stringify(body.state);
  if (json.length > 45000) return out_({ ok: false, error: 'too large' }); // 1セルの上限（5万文字）の手前で止める
  var sh = sheet_();
  sh.getRange('A2').setValue(json);
  sh.getRange('B2').setValue(new Date());
  return out_({ ok: true });
}
