/**
 * 送信ログ。
 *
 * 事後検証や保険会社の監査で「誰がいつ何を確認したか」を出せるようにする。
 * 再発行もこの行を読み直せば済む。
 */

var LOG_HEADER = [
  '送信日時', '実行者', '代理店', '募集人', '契約形態', '契約者氏名', '確認日',
  '総合判定', '不適合項目',
  '判定①', '判定②', '判定③', '判定④', '判定⑤', '判定⑥',
  '判定理由',
  '保存先フォルダ名', 'フォルダ新規作成', 'フォルダURL',
  '適合性確認シートURL', '意向把握シートURL',
  '入力内容(JSON)'
];

function appendLog_(data, judgment, result) {
  var sh = settingsSpreadsheet_().getSheetByName(SHEET_LOG);
  // 黙って捨てると監査証跡が誰にも気づかれずに欠ける。
  if (!sh) throw new Error('「送信ログ」シートが見つかりません。setup() を再実行してください。');

  var v = function (k) { return judgment.items[k].value; };
  var reasons = ['i1', 'i2', 'i3', 'i4', 'i5', 'i6'].map(function (k, i) {
    return '(' + (i + 1) + ')' + judgment.items[k].reason;
  }).join(' / ');

  sh.appendRow([
    new Date(),
    currentUserEmail_(),
    data.agency, data.agent, data.contractType, data.customerName, data.confirmDate,
    judgment.suitable ? '適合' : '不適合',
    judgment.ngKeys.map(function (k) { return k.replace('i', ''); }).join(','),
    v('i1'), v('i2'), v('i3'), v('i4'), v('i5'), v('i6'),
    reasons,
    result.folderName, result.folderCreated ? '新規' : '既存', result.folderUrl,
    result.files[0].url, result.files[1].url,
    JSON.stringify(data)
  ]);
}

function currentUserEmail_() {
  try {
    return Session.getActiveUser().getEmail() || '(不明)';
  } catch (e) {
    return '(不明)';
  }
}
