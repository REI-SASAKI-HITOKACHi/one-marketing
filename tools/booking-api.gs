/**
 * 既存のお客様向け Web予約の受け口（Apps Script ウェブアプリ）
 *
 * 【これは何か】
 *   お客様が lp/booking/ のページを開くと、このスクリプトに空き枠を問い合わせる。
 *   返すのは「渡辺さんのカレンダーの空き」から作った候補時刻だけで、
 *   予定の中身（誰の家か、いくらか）は一切外に出さない。
 *   お客様が枠を選んで送信すると、渡辺さんのカレンダーに【仮】予定を入れ、
 *   スプレッドシートに記録し、グループLINEへ通知する。
 *
 * 【なぜApps Scriptか】
 *   Netlifyに置くとサービスアカウント鍵をNetlify側にも持たせることになる。
 *   鍵の複製は増やしたくない（tools/line-webhook.gs と同じ判断）。
 *   Apps Scriptなら佐々木さんの権限でカレンダーとシートに触れるので、
 *   新しい鍵をどこにも置かずに済む。
 *
 * 【前提：渡辺さんのカレンダーへの権限】
 *   渡辺さんのGoogleカレンダー設定で、佐々木さん（case.foot.kid@gmail.com）に
 *   「予定の変更権限」を共有しておくこと。読み取り専用のままだと予約を書き込めない。
 *   ID/パスワードの共有は不要。渡辺さんのGmailやドライブには一切触れない。
 *   手順は docs/予約フォーム-導入手順.md。
 *
 * 【入れ方】（LINE webhookと同じスプレッドシートのApps Scriptで構わない）
 *   スプレッドシート → 拡張機能 → Apps Script → このコードを貼り付けて保存
 *   → 左メニュー［プロジェクトの設定］→ タイムゾーンが「東京」か確認する
 *      （UTCのままだと日付の区切りがずれ、空き枠が9時間ずれます）
 *   → 左メニュー［プロジェクトの設定］→［スクリプト プロパティ］に次を追加
 *        LINE_TOKEN  ： LINEのチャネルアクセストークン
 *        LINE_GROUP  ： Cdaad037f60f5bc8b2c8138ce0afffc78
 *      （LINE通知が要らなければ未設定でよい。その場合は通知だけ静かに飛ばす）
 *   → 右上［デプロイ］→［新しいデプロイ］→ 種類：ウェブアプリ
 *        次のユーザーとして実行 ： 自分
 *        アクセスできるユーザー ： 全員     ← ここが「全員」でないとお客様から使えません
 *   → 表示された /exec のURLを lp/booking/index.html の API_URL に貼る
 *
 * 【★正直に書いておく制約】
 *   ・doGet/doPost はリクエストヘッダーを読めないので、送信元の検証ができない。
 *     つまり誰でもこのURLを叩けば【仮】予定を入れられる。
 *     そのため予定は必ず【仮】で作り、確定は人が行う運用にしている。
 *     いたずらが増えたら SETTEI.gouryuJougen（同一IPではなく同一日での上限）や
 *     合言葉パラメータの導入を検討すること。
 *   ・空き枠の計算はこのスクリプトが行い、確定直前にもう一度確認する。
 *     それでも同時アクセスの完全な排他はできない。二重予約が起きたら人が調整する。
 */

var SETTEI = {
  /** 予定を入れる先。渡辺さんのカレンダー */
  calendarId: 'wk09015963@gmail.com',

  /** 記録先のスプレッドシート。空ならこのスクリプトが紐づくシート */
  sheetId: '1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64',
  yoyakuTab: '予約_Web',

  /**
   * 受付時間。2026-09-08のMTGで決定（議題#5）。
   * 「9:00-21:00 ／ 施工開始・施工終了時刻」
   */
  kaishiJikoku: 9,    // 9:00 より前には始めない
  shuuryouJikoku: 21, // 21:00 までに終わる枠だけ出す

  /** 前後に確保する移動時間（分） */
  idouFun: 60,

  /**
   * 夜勤のルール。2026-09-08のMTGで決定（前回#6の調整欄）。
   *   ・9月中は夜勤あり。Googleカレンダーに夜勤日を入れる
   *   ・夜勤明けは 13:00 以降なら受注可能
   *   ・夜勤前は 18:00 に施工完了まで受注可能
   *   ・10月以降は週休2日・1日12時間（曜日はカレンダーの予定で判断する）
   *
   * 夜勤の見分け方：時刻の入った予定のうち、yakinHanteiJi 以降に始まって
   * 翌日にまたがるもの。「バイト 21:00〜翌05:00」などが該当する。
   * タイトルでは判定しない（呼び方が変わっても壊れないようにするため）。
   */
  yakinHanteiJi: 18,      // この時刻以降に始まり日をまたぐ予定を夜勤とみなす
  yakinAkeSaihayaku: 13,  // 夜勤明けの日は13:00以降から
  yakinMaeShuuryou: 18,   // 夜勤がある日は18:00までに施工完了

  /** 何日先まで出すか。当日と翌日は出さない（準備が要るため） */
  saitanNichi: 2,
  saichouNichi: 21,

  /** タイムゾーン。空ならスクリプトの設定を使う */
  timeZone: 'Asia/Tokyo',

  /** 枠の刻み（分）。30なら 9:00, 9:30, 10:00 … */
  kizamiFun: 30,

  /** 1件の施工として受け付ける最大の長さ（分）。クライアントの値を鵜呑みにしないための上限 */
  saidaiShoyouFun: 480,
};

// ============================== 入口 ==============================

/**
 * 空き枠の問い合わせ。
 * ブラウザから直接fetchするとCORSで詰まりやすいので、JSONP（callback付き）に対応する。
 *   GET ?action=slots&minutes=180&callback=cb
 */
function doGet(e) {
  var p = (e && e.parameter) || {};
  var res;
  try {
    if (p.action === 'slots') {
      res = { ok: true, slots: akiWaku_(seisuu_(p.minutes, 120)) };
    } else if (p.action === 'ping') {
      res = { ok: true, now: new Date().toISOString() };
    } else {
      res = { ok: false, error: 'action が不明です' };
    }
  } catch (err) {
    res = { ok: false, error: String(err) };
  }
  return kaesu_(res, p.callback);
}

/**
 * 予約の確定（【仮】予定の作成）。
 * Content-Type: text/plain で送ってもらう。application/json にすると
 * ブラウザがプリフライトを飛ばし、Apps Scriptがそれに答えられないため。
 */
function doPost(e) {
  var res;
  try {
    var body = JSON.parse((e && e.postData && e.postData.contents) || '{}');
    res = yoyakuSuru_(body);
  } catch (err) {
    res = { ok: false, error: String(err) };
  }
  return kaesu_(res, null);
}

function kaesu_(obj, callback) {
  var json = JSON.stringify(obj);
  if (callback && /^[A-Za-z_$][A-Za-z0-9_$]*$/.test(callback)) {
    return ContentService.createTextOutput(callback + '(' + json + ');')
      .setMimeType(ContentService.MimeType.JAVASCRIPT);
  }
  return ContentService.createTextOutput(json)
    .setMimeType(ContentService.MimeType.JSON);
}

// ============================== 空き枠の計算 ==============================

/**
 * 所要分だけ連続して空いている開始時刻を、日付ごとにまとめて返す。
 *
 * 「空き」の判定に入れているもの
 *   ・既存の予定（時刻の入っているものだけ。終日予定＝TODOは無視する）
 *   ・既存の予定の前後 SETTEI.idouFun 分（移動時間）
 *   ・夜勤明けの日は13:00以降、夜勤に入る日は18:00までに施工完了（MTGで決定）
 */
function akiWaku_(shoyouFun) {
  var cal = CalendarApp.getCalendarById(SETTEI.calendarId);
  if (!cal) {
    throw new Error('カレンダーを開けません（' + SETTEI.calendarId +
                    '）。「予定の変更権限」の共有を確認してください。');
  }
  var tz = SETTEI.timeZone || Session.getScriptTimeZone();

  var kyou = hizukeNomi_(new Date());
  var kaishi = tasuNichi_(kyou, SETTEI.saitanNichi);
  var owari = tasuNichi_(kyou, SETTEI.saichouNichi + 1);

  // 前日の夜勤が翌朝まで伸びるので、1日前から取る
  var yotei = cal.getEvents(tasuNichi_(kaishi, -1), owari);

  var fusagi = [];
  var yakin = [];   // 夜勤（日をまたぐ勤務）の {s, e}
  yotei.forEach(function (ev) {
    // 終日予定は塞がりとして扱わない。
    // このカレンダーの終日予定はTODO（tools/todo-calendar.gs が入れるもの）で、
    // 実際の施工・バイト・通院はすべて時刻の入った予定になっている。
    // 終日予定で丸一日を塞ぐと、TODOが1件あるだけでその日が予約できなくなる。
    if (ev.isAllDayEvent()) { return; }
    var s = ev.getStartTime();
    var e = ev.getEndTime();
    fusagi.push({ s: s.getTime(), e: e.getTime() });
    // 夜勤かどうか。夕方以降に始まって、日をまたいで終わるもの
    if (s.getHours() >= SETTEI.yakinHanteiJi && !onajiHi_(s, e)) {
      yakin.push({ s: s.getTime(), e: e.getTime() });
    }
  });

  var idouMs = SETTEI.idouFun * 60000;
  var hitsuyouMs = shoyouFun * 60000;

  var out = [];
  for (var i = SETTEI.saitanNichi; i <= SETTEI.saichouNichi; i++) {
    var hi = tasuNichi_(kyou, i);
    var key = Utilities.formatDate(hi, tz, 'yyyy-MM-dd');

    var hiHajime = hi.getTime();
    var tsugiNoHi = tasuNichi_(hi, 1).getTime();

    // 夜勤明けの日か（前夜の夜勤が、この日にかかって終わる）
    var akeDa = yakin.some(function (y) {
      return y.e > hiHajime && y.e < tsugiNoHi;
    });
    // この日に夜勤に入るか
    var yakinBi = yakin.some(function (y) {
      return y.s >= hiHajime && y.s < tsugiNoHi;
    });

    var saihayaku = new Date(hi);
    saihayaku.setHours(akeDa ? SETTEI.yakinAkeSaihayaku : SETTEI.kaishiJikoku, 0, 0, 0);
    saihayaku = saihayaku.getTime();

    var shimeKiri = new Date(hi);
    shimeKiri.setHours(yakinBi ? SETTEI.yakinMaeShuuryou : SETTEI.shuuryouJikoku, 0, 0, 0);

    var kouho = [];
    var kizami = SETTEI.kizamiFun * 60000;
    // 刻みに合わせて切り上げる
    var t = Math.ceil(saihayaku / kizami) * kizami;
    for (; t + hitsuyouMs <= shimeKiri.getTime(); t += kizami) {
      if (aiteruka_(fusagi, t, t + hitsuyouMs, idouMs)) {
        kouho.push(Utilities.formatDate(new Date(t), tz, 'HH:mm'));
      }
    }
    if (kouho.length) {
      out.push({
        date: key,
        label: Utilities.formatDate(hi, tz, 'M月d日') + '（' + youbi_(hi) + '）',
        times: kouho,
      });
    }
  }
  return out;
}

/** 既存の予定と、移動時間ぶんを含めて重ならないか */
function aiteruka_(fusagi, s, e, idouMs) {
  for (var i = 0; i < fusagi.length; i++) {
    var f = fusagi[i];
    if (s < f.e + idouMs && f.s - idouMs < e) { return false; }
  }
  return true;
}

// ============================== 予約の確定 ==============================

function yoyakuSuru_(b) {
  var namae = String(b.name || '').trim();
  var tel = String(b.tel || '').trim();
  var jusho = String(b.address || '').trim();
  var date = String(b.date || '').trim();     // yyyy-MM-dd
  var time = String(b.time || '').trim();     // HH:mm
  var menu = String(b.menu || '').trim();
  var bikou = String(b.note || '').trim();
  var gaisan = kingaku_(b.amount);
  var shoyou = seisuu_(b.minutes, 120);

  if (!namae) { return { ok: false, error: 'お名前が入っていません' }; }
  if (!tel) { return { ok: false, error: 'お電話番号が入っていません' }; }
  if (!jusho) { return { ok: false, error: 'ご住所が入っていません' }; }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || !/^\d{2}:\d{2}$/.test(time)) {
    return { ok: false, error: '日時の指定が正しくありません' };
  }
  if (!menu) { return { ok: false, error: 'ご希望の内容が選ばれていません' }; }

  var tz = SETTEI.timeZone || Session.getScriptTimeZone();
  var start = new Date(date + 'T' + time + ':00' + jisaOffset_(tz, date));
  var end = new Date(start.getTime() + shoyou * 60000);

  // 送信されるまでの間に埋まっていることがあるので、作る直前にもう一度見る
  var cal = CalendarApp.getCalendarById(SETTEI.calendarId);
  if (!cal) { return { ok: false, error: 'カレンダーを開けませんでした' }; }
  var mawari = cal.getEvents(new Date(start.getTime() - 12 * 3600000),
                             new Date(end.getTime() + 12 * 3600000));
  var idouMs = SETTEI.idouFun * 60000;
  for (var i = 0; i < mawari.length; i++) {
    var ev = mawari[i];
    if (ev.isAllDayEvent()) { continue; }
    if (start.getTime() < ev.getEndTime().getTime() + idouMs &&
        ev.getStartTime().getTime() - idouMs < end.getTime()) {
      return { ok: false, error: 'うまり', message: '申し訳ありません、その枠は先に埋まってしまいました。別の時間をお選びください。' };
    }
  }

  var sei = namae.split(/[\s　]+/)[0];
  var ev2 = cal.createEvent(
    '【仮】' + sei + '様　' + menu,
    start, end,
    {
      location: jusho,
      description: [
        '■ Web予約（未確定）',
        'お名前：' + namae,
        'お電話：' + tel,
        'ご住所：' + jusho,
        'ご希望：' + menu,
        '概算：' + (gaisan ? '¥' + gaisan.toLocaleString() + '（税込）' : '—'),
        'ご要望：' + (bikou || 'なし'),
        '',
        '※ お客様がフォームから入れた仮予約です。',
        '※ お電話で確認したら、タイトルの【仮】を外してください。',
      ].join('\n'),
    }
  );

  kiroku_([
    Utilities.formatDate(new Date(), tz, 'yyyy/MM/dd HH:mm:ss'),
    date, time, shoyou, menu, gaisan, namae, tel, jusho, bikou,
    ev2.getId(), '未確認',
  ]);

  // LINEには個人情報を載せない。姓と日時と内容だけ。
  lineTsuuchi_([
    '【Web予約が入りました】',
    '',
    Utilities.formatDate(start, tz, 'M月d日（') + youbi_(start) + '） ' +
      Utilities.formatDate(start, tz, 'HH:mm') + '〜' +
      Utilities.formatDate(end, tz, 'HH:mm'),
    sei + '様 ／ ' + menu,
    gaisan ? '概算 ¥' + gaisan.toLocaleString() + '（税込）' : '',
    '',
    'カレンダーに【仮】で入れてあります。',
    'お電話で確認がとれたら【仮】を外してください。',
    'お名前・ご住所・お電話は、カレンダーの予定の詳細に入っています。',
  ].filter(String).join('\n'));

  return {
    ok: true,
    date: date, time: time,
    label: Utilities.formatDate(start, tz, 'M月d日（') + youbi_(start) + '） ' +
           Utilities.formatDate(start, tz, 'HH:mm'),
  };
}

function kiroku_(gyou) {
  var ss = SETTEI.sheetId ? SpreadsheetApp.openById(SETTEI.sheetId)
                          : SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(SETTEI.yoyakuTab);
  if (!sh) {
    sh = ss.insertSheet(SETTEI.yoyakuTab);
    sh.appendRow(['受信日時', '希望日', '希望時刻', '所要分', 'ご希望の内容',
                  '概算(税込)', 'お名前', 'お電話', 'ご住所', 'ご要望',
                  'カレンダーID', '状態']);
    sh.setFrozenRows(1);
    // 電話番号の先頭の0が消えないように、文字列として扱う
    sh.getRange('H:H').setNumberFormat('@');
  }
  sh.appendRow(gyou);
}

function lineTsuuchi_(honbun) {
  var pr = PropertiesService.getScriptProperties();
  var token = pr.getProperty('LINE_TOKEN');
  var group = pr.getProperty('LINE_GROUP');
  if (!token || !group) { return; }  // 未設定なら黙って飛ばす
  try {
    UrlFetchApp.fetch('https://api.line.me/v2/bot/message/push', {
      method: 'post',
      contentType: 'application/json',
      headers: { Authorization: 'Bearer ' + token },
      payload: JSON.stringify({ to: group, messages: [{ type: 'text', text: honbun }] }),
      muteHttpExceptions: true,
    });
  } catch (err) {
    // 通知が失敗しても予約自体は成立させる
    console.error('LINE通知に失敗: ' + err);
  }
}

// ============================== 小物 ==============================

/** 概算金額。所要時間の上限で丸めてはいけないので、別の関数にしている */
function kingaku_(v) {
  var n = parseInt(v, 10);
  if (isNaN(n) || n < 0) { return 0; }
  return Math.min(n, 9999999);
}

/** 所要分。クライアントの申告なので上限で頭を打たせる */
function seisuu_(v, kitei) {
  var n = parseInt(v, 10);
  if (isNaN(n) || n <= 0) { return kitei; }
  return Math.min(n, SETTEI.saidaiShoyouFun);
}

function hizukeNomi_(d) {
  var x = new Date(d);
  x.setHours(0, 0, 0, 0);
  return x;
}

function tasuNichi_(d, n) {
  var x = new Date(d);
  x.setDate(x.getDate() + n);
  x.setHours(0, 0, 0, 0);
  return x;
}

/** 2つの日時が同じ日か */
function onajiHi_(a, b) {
  return a.getFullYear() === b.getFullYear() &&
         a.getMonth() === b.getMonth() &&
         a.getDate() === b.getDate();
}

function youbi_(d) {
  return ['日', '月', '火', '水', '木', '金', '土'][d.getDay()];
}

/** yyyy-MM-dd の日のタイムゾーンオフセットを +09:00 の形で返す */
function jisaOffset_(tz, date) {
  var d = new Date(date + 'T12:00:00Z');
  return Utilities.formatDate(d, tz, 'XXX');
}

// ============================== 動作確認 ==============================

/**
 * エディタから実行して、権限とカレンダーの見え方を確かめる。
 * 初回は権限の承認ダイアログが出る。
 */
function kakunin() {
  var cal = CalendarApp.getCalendarById(SETTEI.calendarId);
  if (!cal) {
    Logger.log('★ カレンダーを開けません。渡辺さんからの共有設定を確認してください。');
    return;
  }
  Logger.log('カレンダー: ' + cal.getName());
  var waku = akiWaku_(120);
  Logger.log('空きのある日: ' + waku.length + '日');
  waku.slice(0, 5).forEach(function (w) {
    Logger.log('  ' + w.label + '  ' + w.times.join(' '));
  });

  // 書き込めるかどうかは、実際に作って消してみないと分からない
  try {
    var t = new Date(); t.setDate(t.getDate() + 60); t.setHours(23, 0, 0, 0);
    var ev = cal.createEvent('【テスト】削除して構いません', t,
                             new Date(t.getTime() + 600000));
    ev.deleteEvent();
    Logger.log('書き込み: できました（テスト予定は消しました）');
  } catch (err) {
    Logger.log('★ 書き込めません。共有が「予定の表示」止まりの可能性があります: ' + err);
  }
}
