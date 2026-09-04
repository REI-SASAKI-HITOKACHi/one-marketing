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
  '入力からの参考判定', '参考判定と食い違った項目',
  '保存先フォルダ名', 'フォルダ新規作成', 'フォルダURL',
  '適合性確認シートURL', '意向把握シートURL',
  '入力内容(JSON)'
];

/**
 * @param {Object} summary 帳票に印字した回答とその総合結果
 * @param {Object} advice  入力から計算した参考判定（帳票には出ない）
 */
function appendLog_(data, summary, advice, result) {
  var sh = settingsSpreadsheet_().getSheetByName(SHEET_LOG);
  // 黙って捨てると監査証跡が誰にも気づかれずに欠ける。
  if (!sh) throw new Error('「送信ログ」シートが見つかりません。setup() を再実行してください。');

  var label = { yes: 'はい', no: 'いいえ', na: '対象外', unknown: '参考判定なし' };
  var v = function (k) { return label[summary.answers[k]] || ''; };

  // 参考判定と食い違った項目を残す。あとから見直すときの手がかりになる。
  var marks = '①②③④⑤⑥';
  var diff = [];
  var reasons = JUDGE_KEYS.map(function (k, i) {
    var a = advice.items[k];
    // 'unknown' は「判定の根拠になる入力を取っていない」という意味。
    // 食い違いではないので、差分としては数えない。
    if (a.value !== 'unknown' && a.value !== summary.answers[k]) {
      diff.push(marks.charAt(i) + '（入力からは' + (label[a.value] || '') + '）');
    }
    return marks.charAt(i) + label[a.value] + '：' + a.reason;
  }).join(' / ');

  sh.appendRow([
    new Date(),
    currentUserEmail_(),
    data.agency, data.agent, data.contractType, data.customerName, data.confirmDate,
    summary.suitable ? '適合' : '不適合',
    summary.ngKeys.map(function (k) { return marks.charAt(Number(k.replace('i', '')) - 1); }).join(','),
    v('i1'), v('i2'), v('i3'), v('i4'), v('i5'), v('i6'),
    reasons,
    diff.join(' / '),
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
