/**
 * TODOシート → Googleカレンダー 通知（15分枠版）
 *
 * 【なぜ作り直したか】
 *   これまでは「終日予定」で登録していた。終日予定は Google カレンダーの既定では
 *   通知が飛ばない（既定の通知は「当日 午前0時」などで、実質気づけない）。
 *   時刻を指定した予定に変えると、既定のポップアップ通知が確実に鳴る。
 *
 * 【動き】
 *   毎朝6:30に自動起動 →
 *     1. TODOタブから「未着手／進行中」かつ期限が今日以前の行を拾う
 *     2. 担当者ごとに1件の予定を作る（1人1日1件。TODOが5件あっても予定は1件）
 *     3. その日の 07:00 以降で最初に空いている15分枠に置く
 *     4. 予定の説明欄に、その人のTODOを全部書く
 *     5. TODOタブの「カレンダー」列に予定へのリンクを書き戻す
 *
 * 【権限の前提 ★重要★】
 *   このスクリプトは佐々木さんのアカウントで動く。
 *   渡辺さんのカレンダー(wk09015963@gmail.com)は現在「閲覧のみ」の共有なので、
 *   そこに直接 予定を作ることはできない。
 *   そのため予定は「佐々木さんのカレンダーに作り、渡辺さんをゲストに招待する」形にしている。
 *   → 渡辺さんのカレンダーにも表示され、渡辺さん側の既定通知で鳴る。
 *   → 佐々木さんのカレンダーは「予定あり」にしない（AVAILABILITY: FREE）ので、
 *      商談枠を潰さない。
 *
 *   渡辺さんが佐々木さんに「予定の変更権限」を付けてくれれば、
 *   SETTEI.chokusetsu を true にすることで、招待ではなく直接登録に切り替えられる。
 *
 * 【入れ方】
 *   スプレッドシートを開く → 拡張機能 → Apps Script → このコードを貼り付けて保存
 *   → 関数 tesuto を実行（1文字も書き込まず、何が起きるかログに出すだけ）
 *   → 問題なければ 関数 toroku_trigger を1回だけ実行（毎朝6:30の自動起動を設定）
 *   → 手動で今すぐ流したいときは 関数 jikkou を実行
 */

// ============================== 設定 ==============================

var SETTEI = {

  /** TODOタブの名前 */
  todoTab: 'TODO',

  /** 予定を置く時間帯。この時刻以降で最初に空いている枠を使う */
  kaishiJikoku: 7,       // 7時
  saishuJikoku: 20,      // ここまでに空きがなければ、この時刻の直前に強制的に入れる
  wakuFun: 15,           // 1枠の長さ（分）

  /**
   * 担当者名 → メールアドレス
   * TODOタブのD列「担当」の表記と完全に一致させること
   */
  tantousha: {
    '佐々木': 'case.foot.kid@gmail.com',
    '渡辺':   'wk09015963@gmail.com',
  },

  /**
   * 空き枠を探すときに「予定として数えない」タイトル。
   * 渡辺さんの「バイト」は 23:00〜翌16:00 のような長時間ブロックで入っており、
   * 実際にはその時間帯に施工にも入っている（例：2026/09/02 09:00 小池様）。
   * これを予定として数えると一日中どこも空かなくなるので、除外する。
   */
  mushi: [/バイト/, /^掲示板チェック$/],

  /** 通知（分前）。0 = 開始と同時に鳴らす */
  tsuuchiFun: [0, 10],

  /** true にすると招待ではなく相手のカレンダーへ直接登録する（要 予定の変更権限） */
  chokusetsu: false,

  /** 予定タイトルの頭につける印。二重登録の判定に使うので変えないこと */
  shirushi: '【本日のTODO】',
};

// ============================== 入口 ==============================

/** 書き込みなし。何が起きるかログに出すだけ */
function tesuto() {
  honshori_(true);
}

/** 実行 */
function jikkou() {
  honshori_(false);
}

/** 毎朝6:30の自動起動を仕込む（1回だけ実行すればよい） */
function toroku_trigger() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'jikkou') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('jikkou').timeBased().atHour(6).nearMinute(30).everyDays(1).create();
  Logger.log('毎朝6:30に jikkou が自動実行されるようにしました。');
}

/** 自動起動を止める */
function kaijo_trigger() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'jikkou') ScriptApp.deleteTrigger(t);
  });
  Logger.log('自動実行を止めました。');
}

// ============================== 本体 ==============================

function honshori_(karaUchi) {
  var log = [];
  log.push(karaUchi ? '■ テスト（1文字も書き込みません）' : '■ 実行');

  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(SETTEI.todoTab);
  if (!sh) { Logger.log('！ タブ「' + SETTEI.todoTab + '」が見つかりません'); return; }

  var hyou = yomu_(sh);
  if (!hyou) { Logger.log('！ TODOタブの見出し行（ID／状態／期限／担当…）が見つかりません'); return; }
  log.push('  見出し行: ' + hyou.midashiGyou + '行目 ／ データ ' + hyou.gyou.length + '行');

  var kyou = new Date();
  kyou.setHours(0, 0, 0, 0);

  // 担当者ごとに、今日出すべきTODOをまとめる
  var matome = {};
  hyou.gyou.forEach(function (r) {
    var jotai = String(r.値[hyou.retu.状態] || '').trim();
    if (jotai !== '未着手' && jotai !== '進行中') return;

    var kigen = r.値[hyou.retu.期限];
    if (kigen instanceof Date) {
      var k = new Date(kigen); k.setHours(0, 0, 0, 0);
      if (k.getTime() > kyou.getTime()) return;   // 期限がまだ先のものは出さない
    }

    var tantou = String(r.値[hyou.retu.担当] || '').trim();
    if (!SETTEI.tantousha[tantou]) return;

    (matome[tantou] = matome[tantou] || []).push({
      gyou: r.gyou,
      id:   String(r.値[hyou.retu.ID] || ''),
      jotai: jotai,
      kigen: kigen,
      yaru: String(r.値[hyou.retu.やること] || ''),
      naze: String(r.値[hyou.retu['なぜ（効果）']] || ''),
      tejun: String(r.値[hyou.retu['手順・補足']] || ''),
    });
  });

  var mainCal = CalendarApp.getDefaultCalendar();

  Object.keys(SETTEI.tantousha).forEach(function (tantou) {
    var list = matome[tantou] || [];
    if (!list.length) { log.push('  ' + tantou + '：出すTODOなし'); return; }

    var mail = SETTEI.tantousha[tantou];
    var title = SETTEI.shirushi + tantou + 'さん（' + list.length + '件）';

    // すでに今日ぶんを作っていないか
    if (sudeniAru_(mainCal, kyou, title)) {
      log.push('  ' + tantou + '：本日ぶんは登録済みのため、そのままにしました');
      return;
    }

    var waku = akiWaku_(kyou, [mail, Session.getActiveUser().getEmail()]);
    log.push('  ' + tantou + '：' + list.length + '件 → ' + Utilities.formatDate(waku, 'Asia/Tokyo', 'M/d HH:mm') + ' から' + SETTEI.wakuFun + '分');

    var honbun = setsumei_(tantou, list);
    if (karaUchi) {
      log.push('     ---- 説明欄 ----');
      honbun.split('\n').forEach(function (l) { log.push('     ' + l.replace(/<[^>]+>/g, '')); });
      return;
    }

    var owari = new Date(waku.getTime() + SETTEI.wakuFun * 60 * 1000);
    var cal = SETTEI.chokusetsu ? CalendarApp.getCalendarById(mail) : mainCal;
    var opt = { description: honbun };
    if (!SETTEI.chokusetsu && mail !== Session.getActiveUser().getEmail()) {
      opt.guests = mail;
      opt.sendInvites = true;
    }
    var ev = cal.createEvent(title, waku, owari, opt);
    ev.setTransparency(CalendarApp.EventTransparency.TRANSPARENT); // 自分の枠は塞がない
    ev.removeAllReminders();
    SETTEI.tsuuchiFun.forEach(function (m) { ev.addPopupReminder(m); });

    var url = 'https://www.google.com/calendar/event?eid=' +
      Utilities.base64Encode(ev.getId().split('@')[0] + ' ' + cal.getId()).replace(/=+$/, '');

    // TODOタブの「カレンダー」列にリンクを書き戻す
    if (hyou.retu.カレンダー !== undefined) {
      list.forEach(function (t) {
        sh.getRange(t.gyou, hyou.retu.カレンダー + 1)
          .setFormula('=HYPERLINK("' + url + '","予定を開く")');
      });
    }
    log.push('     登録しました');
  });

  Logger.log(log.join('\n'));
}

// ============================== 部品 ==============================

/** TODOタブを読む。見出し行を自動で探す */
function yomu_(sh) {
  var atai = sh.getDataRange().getValues();
  for (var i = 0; i < Math.min(atai.length, 20); i++) {
    var gyo = atai[i].map(function (v) { return String(v).trim(); });
    if (gyo.indexOf('ID') >= 0 && gyo.indexOf('状態') >= 0 && gyo.indexOf('担当') >= 0) {
      var retu = {};
      gyo.forEach(function (n, j) { if (n) retu[n] = j; });
      var gyou = [];
      for (var k = i + 1; k < atai.length; k++) {
        if (!String(atai[k][retu.ID] || '').trim()) continue;
        gyou.push({ gyou: k + 1, 値: atai[k] });
      }
      return { midashiGyou: i + 1, retu: retu, gyou: gyou };
    }
  }
  return null;
}

/** 同じタイトルの予定がその日にすでにあるか */
function sudeniAru_(cal, hi, title) {
  var owari = new Date(hi.getTime() + 24 * 60 * 60 * 1000);
  return cal.getEvents(hi, owari).some(function (e) { return e.getTitle() === title; });
}

/**
 * その日の kaishiJikoku 以降で、渡されたカレンダー全部が空いている最初の15分枠を返す。
 * SETTEI.mushi にあたるタイトルの予定は無視する。
 */
function akiWaku_(hi, mailList) {
  var hasami = [];
  mailList.forEach(function (m) {
    var cal = null;
    try { cal = CalendarApp.getCalendarById(m); } catch (e) { return; }
    if (!cal) return;
    cal.getEvents(new Date(hi.getTime() - 24 * 3600 * 1000),
                  new Date(hi.getTime() + 48 * 3600 * 1000)).forEach(function (e) {
      if (e.isAllDayEvent()) return;
      var t = e.getTitle();
      if (SETTEI.mushi.some(function (re) { return re.test(t); })) return;
      hasami.push([e.getStartTime().getTime(), e.getEndTime().getTime()]);
    });
  });

  var ima = new Date();
  var hajime = new Date(hi); hajime.setHours(SETTEI.kaishiJikoku, 0, 0, 0);
  // 今日ぶんで、すでに開始時刻を過ぎているなら「次の15分の切りのよい時刻」から探す
  if (ima.getTime() > hajime.getTime() &&
      ima.toDateString() === hi.toDateString()) {
    hajime = new Date(Math.ceil(ima.getTime() / (SETTEI.wakuFun * 60000)) * SETTEI.wakuFun * 60000);
  }
  var owari = new Date(hi); owari.setHours(SETTEI.saishuJikoku, 0, 0, 0);
  var haba = SETTEI.wakuFun * 60 * 1000;

  for (var t = hajime.getTime(); t + haba <= owari.getTime(); t += haba) {
    var kasanari = hasami.some(function (b) { return t < b[1] && (t + haba) > b[0]; });
    if (!kasanari) return new Date(t);
  }
  return new Date(owari.getTime() - haba);   // どこも空いていなければ最後の枠
}

/** 予定の説明欄の本文 */
function setsumei_(tantou, list) {
  var s = [];
  s.push(tantou + 'さん、本日ぶんのTODOです。');
  s.push('状態のプルダウンを動かすだけで大丈夫です（完了メモは任意）。');
  s.push('');
  list.forEach(function (t, i) {
    s.push('━━━━━━━━━━━━━━');
    s.push((i + 1) + '. ' + t.yaru + '　[' + t.id + '／' + t.jotai + ']');
    if (t.kigen instanceof Date) {
      s.push('　 期限：' + Utilities.formatDate(t.kigen, 'Asia/Tokyo', 'M月d日'));
    }
    if (t.naze)  s.push('　 なぜ：' + t.naze);
    if (t.tejun) s.push('　 やり方：' + t.tejun);
  });
  s.push('━━━━━━━━━━━━━━');
  s.push('');
  s.push('TODOシート：' + SpreadsheetApp.getActiveSpreadsheet().getUrl() );
  return s.join('\n');
}
