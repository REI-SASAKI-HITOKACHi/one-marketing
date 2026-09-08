/**
 * ワンヒッター株式会社 売上/顧客情報管理シート アップグレード
 *
 * 【設計方針】
 *   1. 過去の記録は一切書き換えない。
 *      - 入力規則（プルダウン）は「現在の最終行より下」にだけ適用する
 *      - 既存タブの中身は読むだけ。壊れた集計タブも消さず、正しい版を別タブで作る
 *   2. 実行前に必ずバックアップコピーを自動作成する
 *   3. 2段階で動かす。まず shindan() で読み取りだけ行い、検出結果を確認してから jikkou()
 *
 * 【使い方】
 *   シートを開く → 拡張機能 → Apps Script → このコードを貼り付けて保存
 *   → 関数 shindan を選んで実行（初回は承認画面が出ます）
 *   → 実行ログを確認 → 問題なければ 関数 jikkou を実行
 */

// ============================== 設定 ==============================

/** プルダウンを適用する行数（最終行の下に何行ぶん用意するか） */
var YOBI_GYOU = 600;

/** ＯＨ打診の選択肢 */
var OH_SENTAKUSHI = ['未打診', '打診済', '反応あり', '成約', '対象外'];

/** フォローコールの選択肢 */
var FC_SENTAKUSHI = ['未', 'SMS送信', 'LINE送信', '電話', '返信あり', '再依頼'];

/** 流入経路に追加する選択肢（既存の選択肢は消さず、足すだけ） */
var KEIRO_TSUIKA = ['LP(アフィリエイト)', '地図検索', 'LINE/SMS再販', 'Google口コミ'];

/** メニュー別の推奨再訪サイクル（月）。前方一致で判定し、該当なしは既定値 */
var SAIHOU_CYCLE = [
  ['おそうじ定期便', 1],
  ['定期清掃', 1],
  ['トイレ', 6],
  ['洗面台', 6],
];
var SAIHOU_CYCLE_KITEI = 12;

/** 「そろそろ案内」と判定する前倒し月数 */
var SAIHOU_MAEDAOSHI = 2;

/** 月次タブの判定（1月_売上/顧客 など） */
function tsukiTabKa_(name) {
  return /^\s*\d{1,2}\s*月/.test(name) && /売上|顧客/.test(name);
}

// ============================== 診断（読み取りのみ） ==============================

function shindan() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var log = [];
  log.push('■ 診断：' + ss.getName());
  log.push('  ※ このモードは1文字も書き込みません');
  log.push('');

  var tabs = ss.getSheets().filter(function (s) { return tsukiTabKa_(s.getName()); });
  if (!tabs.length) {
    log.push('！ 月次タブが1枚も見つかりませんでした。tsukiTabKa_() の判定を調整してください。');
    Logger.log(log.join('\n'));
    return;
  }
  log.push('月次タブ ' + tabs.length + '枚：' + tabs.map(function (s) { return s.getName(); }).join(' / '));
  log.push('');

  var total = 0;
  tabs.forEach(function (sh) {
    var info = retsuKensyutsu_(sh);
    if (!info) {
      log.push('× ' + sh.getName() + ' … ヘッダー行を特定できませんでした');
      return;
    }
    total += info.kensuu;
    log.push('○ ' + sh.getName()
      + ' … ヘッダー' + info.headerRow + '行目'
      + ' / データ' + info.dataRow + '行目〜' + info.lastRow
      + ' / ' + info.kensuu + '件'
      + ' / 列ズレ' + info.offset);
    var miss = [];
    ['売上種類', '施工日付', '流入経路', '氏名', '売上', '実施メニュー', 'フォローコール', 'ＯＨ打診']
      .forEach(function (k) { if (!info.col[k]) miss.push(k); });
    if (miss.length) log.push('    ! 見つからない列：' + miss.join('、'));
  });
  log.push('');
  log.push('合計 ' + total + ' 件');
  log.push('');
  log.push('■ jikkou() で行うこと');
  log.push('  1. このファイルのバックアップコピーを作成');
  log.push('  2. 各月次タブの ' + (YOBI_GYOU) + ' 行ぶん（最終行より下）にプルダウンを設定');
  log.push('     ＯＨ打診 → ' + OH_SENTAKUSHI.join('／'));
  log.push('     フォローコール → ' + FC_SENTAKUSHI.join('／'));
  log.push('     流入経路 → 既存の選択肢 ＋ ' + KEIRO_TSUIKA.join('／'));
  log.push('  3. 「売上分析_v2」タブを新規作成（既存の売上分析タブには触れません）');
  log.push('  4. 「再販リスト」タブを新規作成');
  log.push('  ※ 既存の行は1つも書き換えません');

  Logger.log(log.join('\n'));
  SpreadsheetApp.getUi().alert(log.join('\n'));
}

/** ヘッダー行・データ開始行・列位置・列ズレを検出する */
function retsuKensyutsu_(sh) {
  var maxScan = Math.min(12, sh.getLastRow());
  if (maxScan < 2) return null;
  var head = sh.getRange(1, 1, maxScan, Math.min(30, sh.getLastColumn())).getDisplayValues();

  var headerRow = -1;
  for (var r = 0; r < head.length; r++) {
    var joined = head[r].join('|');
    if (joined.indexOf('施工日付') >= 0 && joined.indexOf('流入経路') >= 0) { headerRow = r; break; }
  }
  if (headerRow < 0) return null;

  var col = {};
  var labels = {
    '売上種類': /売上種類/, '施工日付': /施工日付/, '流入経路': /流入経路/, '氏名': /氏名/,
    'TEL': /TEL|電話/, '売上': /売上.*税込|^売上$/, '実施メニュー': /実施メニュー|メニュー/,
    'フォローコール': /^フォローコール$/, 'フォローコール日': /フォローコール日/,
    'ＯＨ打診': /[ＯO][ＨH]\s*打診/, '早期予約提案': /早期予約提案/
  };
  for (var key in labels) {
    for (var c = 0; c < head[headerRow].length; c++) {
      if (labels[key].test(String(head[headerRow][c]).replace(/\s/g, ''))) { col[key] = c + 1; break; }
    }
  }

  // データ開始行を探す：施工日付列に日付が入る最初の行
  var dataRow = -1, offset = 0;
  var lastRow = sh.getLastRow();
  var hizukeCol = col['施工日付'];
  if (!hizukeCol) return null;

  for (var off = 0; off <= 1 && dataRow < 0; off++) {
    for (var r2 = headerRow + 1; r2 < Math.min(headerRow + 8, lastRow); r2++) {
      var v = sh.getRange(r2 + 1, hizukeCol + off).getValue();
      if (v instanceof Date) { dataRow = r2 + 1; offset = off; break; }
    }
  }
  if (dataRow < 0) { dataRow = headerRow + 2; offset = 0; }

  for (var k in col) col[k] += offset;

  var kensuu = 0;
  if (lastRow >= dataRow) {
    var vals = sh.getRange(dataRow, col['施工日付'], lastRow - dataRow + 1, 1).getValues();
    vals.forEach(function (row) { if (row[0] instanceof Date) kensuu++; });
  }
  return { sheet: sh, headerRow: headerRow + 1, dataRow: dataRow, lastRow: lastRow, col: col, offset: offset, kensuu: kensuu };
}

// ============================== 実行 ==============================

function jikkou() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var ui = SpreadsheetApp.getUi();
  var kotae = ui.alert('売上台帳のアップグレード',
    'バックアップを作ってから、以下を行います。\n\n'
    + '・新しい行にだけプルダウンを設定\n'
    + '・「売上分析_v2」タブを新規作成\n'
    + '・「再販リスト」タブを新規作成\n\n'
    + '既存の行は1つも書き換えません。実行しますか？',
    ui.ButtonSet.OK_CANCEL);
  if (kotae !== ui.Button.OK) return;

  var log = [];

  // 1. バックアップ
  var stamp = Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyyMMdd-HHmm');
  var backup = DriveApp.getFileById(ss.getId()).makeCopy('【バックアップ】' + ss.getName() + ' ' + stamp);
  log.push('1. バックアップ作成： ' + backup.getName());
  log.push('   ' + backup.getUrl());

  // 2. プルダウン
  var tabs = ss.getSheets().filter(function (s) { return tsukiTabKa_(s.getName()); });
  var infos = [];
  tabs.forEach(function (sh) {
    var info = retsuKensyutsu_(sh);
    if (!info) { log.push('   ! ' + sh.getName() + ' … 列を特定できずスキップ'); return; }
    infos.push(info);
    var start = Math.max(info.lastRow + 1, info.dataRow);
    if (info.col['ＯＨ打診']) pulldownSettei_(sh, start, info.col['ＯＨ打診'], OH_SENTAKUSHI);
    if (info.col['フォローコール']) pulldownSettei_(sh, start, info.col['フォローコール'], FC_SENTAKUSHI);
    if (info.col['流入経路']) keiroPulldown_(sh, info, start);
  });
  log.push('2. プルダウン設定： ' + infos.length + 'タブ（各タブの最終行より下 ' + YOBI_GYOU + '行）');

  // 3. 売上分析_v2
  var n3 = bunsekiTabSakusei_(ss, infos);
  log.push('3. 「売上分析_v2」を作成： ' + n3 + '件を集計（既存の売上分析タブは未変更）');

  // 4. 再販リスト
  var n4 = saihanTabSakusei_(ss, infos);
  log.push('4. 「再販リスト」を作成： ' + n4 + '件');

  log.push('');
  log.push('完了しました。既存の行は1つも書き換えていません。');
  Logger.log(log.join('\n'));
  ui.alert(log.join('\n'));
}

function pulldownSettei_(sh, startRow, col, list) {
  var need = startRow + YOBI_GYOU - 1;
  if (sh.getMaxRows() < need) sh.insertRowsAfter(sh.getMaxRows(), need - sh.getMaxRows());
  var rule = SpreadsheetApp.newDataValidation()
    .requireValueInList(list, true).setAllowInvalid(true)
    .setHelpText('選択肢から選んでください（自由入力も可）').build();
  sh.getRange(startRow, col, YOBI_GYOU, 1).setDataValidation(rule);
}

/** 流入経路：既存の値を全部集めて、そこに新しい選択肢を足したプルダウンを作る */
function keiroPulldown_(sh, info, startRow) {
  var arr = [];
  if (info.lastRow >= info.dataRow) {
    sh.getRange(info.dataRow, info.col['流入経路'], info.lastRow - info.dataRow + 1, 1)
      .getDisplayValues().forEach(function (r) {
        var v = String(r[0]).trim();
        if (v && arr.indexOf(v) < 0) arr.push(v);
      });
  }
  KEIRO_TSUIKA.forEach(function (v) { if (arr.indexOf(v) < 0) arr.push(v); });
  pulldownSettei_(sh, startRow, info.col['流入経路'], arr);
}

// ============================== 売上分析_v2 ==============================

function bunsekiTabSakusei_(ss, infos) {
  var rows = zenKensakuShuushuu_(infos);

  var keiroSet = [], tsukiSet = [];
  rows.forEach(function (r) {
    if (keiroSet.indexOf(r.keiro) < 0) keiroSet.push(r.keiro);
    if (tsukiSet.indexOf(r.tsuki) < 0) tsukiSet.push(r.tsuki);
  });
  keiroSet.sort(); tsukiSet.sort(function (a, b) { return a - b; });

  var sh = tabSaisei_(ss, '売上分析_v2');
  var out = [];
  out.push(['売上分析_v2 ／ ' + Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyy-MM-dd HH:mm') + ' 自動生成']);
  out.push(['月次タブの明細から毎回そのまま集計しています。「早期予約」は「リピート」に合算していません。']);
  out.push([]);

  out.push(['■ 月別']);
  out.push(['月', '件数', '売上', '平均単価']);
  tsukiSet.forEach(function (m) {
    var f = rows.filter(function (r) { return r.tsuki === m; });
    var uri = f.reduce(function (a, r) { return a + r.uriage; }, 0);
    out.push([m + '月', f.length, uri, f.length ? Math.round(uri / f.length) : 0]);
  });
  var zenUri = rows.reduce(function (a, r) { return a + r.uriage; }, 0);
  out.push(['合計', rows.length, zenUri, rows.length ? Math.round(zenUri / rows.length) : 0]);
  out.push([]);

  out.push(['■ 流入経路別（売上の多い順）']);
  out.push(['流入経路', '件数', '売上', '平均単価', '売上構成比']);
  keiroSet.map(function (k) {
    var f = rows.filter(function (r) { return r.keiro === k; });
    var uri = f.reduce(function (a, r) { return a + r.uriage; }, 0);
    return [k, f.length, uri, f.length ? Math.round(uri / f.length) : 0, zenUri ? uri / zenUri : 0];
  }).sort(function (a, b) { return b[2] - a[2]; })
    .forEach(function (r) { out.push(r); });
  out.push([]);

  out.push(['■ 月 × 流入経路（売上）']);
  out.push([''].concat(keiroSet).concat(['月計']));
  tsukiSet.forEach(function (m) {
    var line = [m + '月'], kei = 0;
    keiroSet.forEach(function (k) {
      var v = rows.filter(function (r) { return r.tsuki === m && r.keiro === k; })
        .reduce(function (a, r) { return a + r.uriage; }, 0);
      line.push(v || ''); kei += v;
    });
    line.push(kei); out.push(line);
  });

  var width = out.reduce(function (a, r) { return Math.max(a, r.length); }, 1);
  out = out.map(function (r) { while (r.length < width) r.push(''); return r; });
  sh.getRange(1, 1, out.length, width).setValues(out);

  sh.getRange(1, 1).setFontWeight('bold').setFontSize(13);
  sh.getRange(2, 1).setFontColor('#666666');
  out.forEach(function (r, i) {
    if (String(r[0]).indexOf('■') === 0) sh.getRange(i + 1, 1, 1, width).setFontWeight('bold').setBackground('#F1EDE5');
  });
  sh.setFrozenRows(2);
  sh.autoResizeColumns(1, width);
  return rows.length;
}

// ============================== 再販リスト ==============================

function saihanTabSakusei_(ss, infos) {
  var rows = zenKensakuShuushuu_(infos);

  // 顧客ごとに最終施工をまとめる
  var kokyaku = {};
  rows.forEach(function (r) {
    if (!r.shimei) return;
    var key = r.shimei.replace(/[\s　]/g, '');
    var k = kokyaku[key];
    if (!k) { k = kokyaku[key] = { shimei: r.shimei, tel: r.tel, kaisuu: 0, gokei: 0, saishuu: null, menu: '', keiro: '' }; }
    k.kaisuu++; k.gokei += r.uriage;
    if (!k.saishuu || r.hizuke > k.saishuu) { k.saishuu = r.hizuke; k.menu = r.menu; k.keiro = r.keiro; k.tel = r.tel || k.tel; }
  });

  var kyou = new Date();
  var list = [];
  for (var key in kokyaku) {
    var k = kokyaku[key];
    if (!k.saishuu) continue;
    var cycle = SAIHOU_CYCLE_KITEI;
    for (var i = 0; i < SAIHOU_CYCLE.length; i++) {
      if (String(k.menu).indexOf(SAIHOU_CYCLE[i][0]) >= 0) { cycle = SAIHOU_CYCLE[i][1]; break; }
    }
    var osusume = new Date(k.saishuu.getTime());
    osusume.setMonth(osusume.getMonth() + cycle);
    var annai = new Date(osusume.getTime());
    annai.setMonth(annai.getMonth() - SAIHOU_MAEDAOSHI);
    var keika = Math.floor((kyou - k.saishuu) / (1000 * 60 * 60 * 24 * 30.4));
    list.push([
      annai <= kyou ? '★いま' : '',
      k.shimei, k.tel, k.kaisuu, k.gokei,
      k.saishuu, k.menu, k.keiro, cycle, keika, osusume, annai, ''
    ]);
  }
  list.sort(function (a, b) {
    if (a[0] !== b[0]) return a[0] ? -1 : 1;
    return b[9] - a[9];
  });

  var sh = tabSaisei_(ss, '再販リスト');
  var head = [
    ['再販リスト ／ ' + Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyy-MM-dd HH:mm') + ' 自動生成'],
    ['最終施工からの経過とメニュー別サイクルで、案内すべき時期が来た方に ★いま を付けています。'],
    [],
    ['案内時期', '氏名', 'TEL', '利用回数', '累計売上', '最終施工日', '最終メニュー', '最終流入経路',
      '推奨サイクル(月)', '経過(月)', '次回推奨時期', '案内開始めやす', '案内した日']
  ];
  sh.getRange(1, 1, head.length, 13).setValues(head.map(function (r) { while (r.length < 13) r.push(''); return r; }));
  if (list.length) sh.getRange(5, 1, list.length, 13).setValues(list);

  sh.getRange(1, 1).setFontWeight('bold').setFontSize(13);
  sh.getRange(2, 1).setFontColor('#666666');
  sh.getRange(4, 1, 1, 13).setFontWeight('bold').setBackground('#F1EDE5');
  sh.setFrozenRows(4);
  if (list.length) {
    sh.getRange(5, 6, list.length, 1).setNumberFormat('yyyy/MM/dd');
    sh.getRange(5, 11, list.length, 2).setNumberFormat('yyyy/MM/dd');
    sh.getRange(5, 5, list.length, 1).setNumberFormat('¥#,##0');
    sh.getRange(5, 1, list.length, 1).setFontWeight('bold').setFontColor('#D8531F');
  }
  sh.autoResizeColumns(1, 13);
  return list.length;
}

// ============================== 共通 ==============================

function zenKensakuShuushuu_(infos) {
  var rows = [];
  infos.forEach(function (info) {
    var sh = info.sheet;
    if (info.lastRow < info.dataRow) return;
    var n = info.lastRow - info.dataRow + 1;
    var lastCol = Math.max.apply(null, Object.keys(info.col).map(function (k) { return info.col[k]; }));
    var vals = sh.getRange(info.dataRow, 1, n, lastCol).getValues();
    vals.forEach(function (v) {
      var hizuke = info.col['施工日付'] ? v[info.col['施工日付'] - 1] : null;
      if (!(hizuke instanceof Date)) return;
      var uriage = info.col['売上'] ? Number(v[info.col['売上'] - 1]) : 0;
      rows.push({
        hizuke: hizuke,
        tsuki: hizuke.getMonth() + 1,
        keiro: String(info.col['流入経路'] ? v[info.col['流入経路'] - 1] : '').trim() || '(未記入)',
        shimei: String(info.col['氏名'] ? v[info.col['氏名'] - 1] : '').trim(),
        tel: String(info.col['TEL'] ? v[info.col['TEL'] - 1] : '').trim(),
        menu: String(info.col['実施メニュー'] ? v[info.col['実施メニュー'] - 1] : '').trim(),
        uriage: isNaN(uriage) ? 0 : uriage
      });
    });
  });
  return rows;
}

function tabSaisei_(ss, name) {
  var old = ss.getSheetByName(name);
  if (old) ss.deleteSheet(old);
  return ss.insertSheet(name, ss.getNumSheets());
}
