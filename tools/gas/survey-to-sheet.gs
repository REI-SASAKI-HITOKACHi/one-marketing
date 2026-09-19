/**
 * アンケートの回答を「2026_売上/顧客情報管理」に1行ずつ足す。
 *
 * 経路： お客様が送信 → Netlify Forms が保存 → ここへ Webhook → スプレッドシートに追記
 *
 * 置きかたは docs/アンケート-スプレッドシート連携.md を見ること。
 * ウェブアプリとして配置し、その /exec のURLを Netlify の送信フックに入れる。
 *
 * ※ Netlify Forms 側にも回答は残る。ここが止まっても回答は失われない。
 *   スプレッドシートは「見るための写し」で、原本ではない。
 */

var SHEET_ID = '1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64';  // 2026_売上/顧客情報管理
var TAB      = 'アンケート回答';

/* 列の並び。ここに無い項目は「その他」列にまとめて入る。
   増やすときは末尾に足すこと（途中に挿すと過去の行とずれる）。 */
var COLS = [
  ['受信日時',      function (s) { return toJst(s.created_at); }],
  ['顧客ID',        'cust_id'],
  ['お名前（台帳）', 'cust_name'],
  ['メニュー',      'cust_menu'],
  ['担当',          'cust_staff'],
  ['施工日',        'cust_date'],
  ['流入元',        'src'],
  ['NPS',           'q1_nps'],
  ['NPS区分',       'nps_segment'],
  ['仕上がり',      'q2_finish'],
  ['スタッフ',      'q2_staff'],
  ['箇所',          'q3_place'],
  ['箇所の感想',    'q3_comment'],
  ['良かった点',    'q4_extra'],
  ['次に頼みたい',  'q5_next'],
  ['次の時期',      'q6_when'],
  ['割引希望',      'q6_discount'],
  ['紹介',          'q7_referral'],
  ['掲載可否',      'q8_publish'],
  ['写真掲載',      'q8_photo'],
  ['お客様の声',    'q9_message'],
  ['お名前（回答）', 'q10_name'],
  ['電話（回答）',  'q10_tel'],
  ['非公開の指摘',  'private_feedback'],
  ['IP',            'ip'],
  ['端末',          'user_agent'],
  ['参照元',        'referrer']
];

function doPost(e) {
  try {
    // 合言葉が違う POST は捨てる。URLを知られただけでは書き込めないようにする。
    var himitsu = PropertiesService.getScriptProperties().getProperty('AIKOTOBA');
    if (himitsu && (!e.parameter || e.parameter.key !== himitsu)) {
      return keka(403, 'forbidden');
    }

    var body = JSON.parse(e.postData.contents);
    // Netlify は submission そのものを送ってくる。念のため payload 包みにも対応する。
    var sub  = body.payload || body;
    var data = sub.data || {};

    var sheet = tab_();
    var row = COLS.map(function (c) {
      var key = c[1];
      var v = (typeof key === 'function') ? key(sub) : data[key];
      return (v === undefined || v === null) ? '' : String(v);
    });

    // 並びに無い項目を拾う（設問を足したのに列を足し忘れても、消えないように）
    var shitteru = {};
    COLS.forEach(function (c) { if (typeof c[1] === 'string') { shitteru[c[1]] = 1; } });
    var amari = [];
    Object.keys(data).forEach(function (k) {
      if (shitteru[k] || k.indexOf('ui_') === 0 || !data[k]) { return; }
      amari.push(k + '=' + data[k]);
    });
    row.push(amari.join(' / '));

    sheet.appendRow(row);
    return keka(200, 'ok');
  } catch (err) {
    // 失敗しても Netlify 側に原本が残るので、ここでは記録だけして 500 を返す
    console.error(err);
    return keka(500, String(err));
  }
}

/** 動作確認用。ブラウザで /exec を開くと状態が見える */
function doGet() {
  return keka(200, 'survey-to-sheet is alive. tab=' + TAB);
}

function tab_() {
  var ss = SpreadsheetApp.openById(SHEET_ID);
  var sh = ss.getSheetByName(TAB);
  if (!sh) {
    sh = ss.insertSheet(TAB);
  }
  if (sh.getLastRow() === 0) {
    var midashi = COLS.map(function (c) { return c[0]; });
    midashi.push('その他');
    sh.appendRow(midashi);
    sh.setFrozenRows(1);
    sh.getRange(1, 1, 1, midashi.length).setFontWeight('bold');
  }
  return sh;
}

function toJst(iso) {
  if (!iso) { return ''; }
  return Utilities.formatDate(new Date(iso), 'Asia/Tokyo', 'yyyy-MM-dd HH:mm:ss');
}

function keka(code, msg) {
  return ContentService
    .createTextOutput(JSON.stringify({ status: code, message: msg }))
    .setMimeType(ContentService.MimeType.JSON);
}
