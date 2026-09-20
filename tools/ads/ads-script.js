/**
 * Google広告 → スプレッドシート（毎日1回）
 * ──────────────────────────────────────────────────────────────
 * ★これは「Google広告スクリプト」です。Apps Script でも Node でもありません。
 *   Google広告の画面： ツールと設定 → 一括操作 → スクリプト → ＋
 *   に**そのまま貼って**、承認して、実行頻度を「毎日」にします。
 *
 * ## なぜこれを作ったか
 *
 * Google広告の管理画面に入れるのはブラウザ担当だけで、
 * そのブラウザ担当は**オーナーのPC上でしか動かない**。
 * つまり**オーナーがPCを立ち上げた回にしか、検索語句レポートが読めなかった。**
 * オーナー指示（2026-09-20）「僕が都度見るのは面倒だからやめて」。
 *
 * Google広告APIを使うにはデベロッパートークンの審査が要るが、
 * **広告スクリプトなら審査も外部トークンも要らない。**貼って承認するだけ。
 *
 * ## 何をするか
 *
 * 1. 広告グループ別の数字を `広告_日次` タブへ追記する（上書きしない）
 * 2. **検索語句を `広告_検索語句` タブへ追記する**（ここが人依存の核心だった）
 * 3. `広告_除外語_指示` タブを読んで、**キャンペーンの除外キーワードを足す**
 *    （足すだけ。消さない・止めない・予算を触らない）
 *
 * ## やらないこと（意図的に）
 *
 * - **予算の変更**（お金を使う＝オーナーの判断）
 * - **広告やキャンペーンの停止・再開**（同上）
 * - **除外語の削除**（消すと、なぜ消えたのか誰にも分からなくなる）
 * - **キーワードの追加**（広い語が入ると日予算が溶ける。人が決める）
 */

// ── 設定 ───────────────────────────────────────────────────────
var SS_URL = 'https://docs.google.com/spreadsheets/d/1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64/edit';

var TAB_NISSHI   = '広告_日次';
var TAB_GOKU     = '広告_検索語句';
var TAB_SHIJI    = '広告_除外語_指示';
var TAB_LOG      = '広告_スクリプト記録';

/** 1回の実行で足せる除外語の上限。暴走の保険 */
var JOGAI_JOUGEN = 20;

// ── 本体 ───────────────────────────────────────────────────────
function main() {
  var ss = SpreadsheetApp.openByUrl(SS_URL);
  var kyou = Utilities.formatDate(new Date(), AdsApp.currentAccount().getTimeZone(), 'yyyy-MM-dd');
  var log = [];

  try {
    var n1 = kakiNisshi_(ss, kyou);
    log.push('日次 ' + n1 + '行');
  } catch (e) { log.push('🔴 日次で失敗: ' + e); }

  try {
    var n2 = kakiGoku_(ss, kyou);
    log.push('検索語句 ' + n2 + '行');
  } catch (e) { log.push('🔴 検索語句で失敗: ' + e); }

  try {
    var n3 = tsukauShiji_(ss, kyou);
    log.push('除外語を足した ' + n3 + '件');
  } catch (e) { log.push('🔴 除外語で失敗: ' + e); }

  nokosu_(ss, kyou, log.join(' ／ '));
  Logger.log(log.join('\n'));
}

/** 広告グループ別の数字を追記 */
function kakiNisshi_(ss, kyou) {
  var sh = tab_(ss, TAB_NISSHI,
    ['取得日', '日付', 'キャンペーン', '広告グループ', '費用', '表示回数',
     'クリック', 'CTR', '平均CPC', 'コンバージョン', 'コンバージョン単価']);
  var rows = [];
  var it = AdsApp.report(
    'SELECT campaign.name, ad_group.name, segments.date, ' +
    '       metrics.cost_micros, metrics.impressions, metrics.clicks, ' +
    '       metrics.ctr, metrics.average_cpc, metrics.conversions, ' +
    '       metrics.cost_per_conversion ' +
    'FROM ad_group ' +
    'WHERE segments.date DURING YESTERDAY').rows();
  while (it.hasNext()) {
    var r = it.next();
    rows.push([kyou, r['segments.date'], r['campaign.name'], r['ad_group.name'],
               en_(r['metrics.cost_micros']), r['metrics.impressions'], r['metrics.clicks'],
               r['metrics.ctr'], en_(r['metrics.average_cpc']),
               r['metrics.conversions'], en_(r['metrics.cost_per_conversion'])]);
  }
  if (rows.length) sh.getRange(sh.getLastRow() + 1, 1, rows.length, rows[0].length).setValues(rows);
  return rows.length;
}

/**
 * 検索語句を追記。
 * ★ここが本命。「どんな言葉で来ているか」は、これまで人が画面を見ないと分からなかった。
 */
function kakiGoku_(ss, kyou) {
  var sh = tab_(ss, TAB_GOKU,
    ['取得日', '日付', 'キャンペーン', '広告グループ', '検索語句',
     '表示回数', 'クリック', '費用', 'コンバージョン', '判定']);
  var rows = [];
  var it = AdsApp.report(
    'SELECT campaign.name, ad_group.name, search_term_view.search_term, segments.date, ' +
    '       metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions ' +
    'FROM search_term_view ' +
    'WHERE segments.date DURING YESTERDAY').rows();
  while (it.hasNext()) {
    var r = it.next();
    rows.push([kyou, r['segments.date'], r['campaign.name'], r['ad_group.name'],
               r['search_term_view.search_term'], r['metrics.impressions'],
               r['metrics.clicks'], en_(r['metrics.cost_micros']), r['metrics.conversions'], '']);
  }
  if (rows.length) sh.getRange(sh.getLastRow() + 1, 1, rows.length, rows[0].length).setValues(rows);
  return rows.length;
}

/**
 * 指示タブを読んで、キャンペーンの除外キーワードを足す。
 * A列=除外語／B列=一致タイプ（完全/フレーズ/部分。空ならフレーズ）／C列=結果（機械が書く）
 * ★C列が空の行だけを処理する。処理したら結果を書くので、二度と足さない。
 */
function tsukauShiji_(ss, kyou) {
  var sh = ss.getSheetByName(TAB_SHIJI);
  if (!sh) { tab_(ss, TAB_SHIJI, ['除外語', '一致タイプ', '結果', '実施日']); return 0; }
  var last = sh.getLastRow();
  if (last < 2) return 0;

  var vals = sh.getRange(2, 1, last - 1, 4).getValues();
  var camp = AdsApp.campaigns().get();
  if (!camp.hasNext()) throw new Error('キャンペーンが1つも見つかりません');

  var n = 0;
  for (var i = 0; i < vals.length; i++) {
    if (n >= JOGAI_JOUGEN) break;
    var go = String(vals[i][0]).trim();
    var kata = String(vals[i][1]).trim();
    var kekka = String(vals[i][2]).trim();
    if (!go || kekka) continue;               // 空行・処理済みは飛ばす

    var hyouki = (kata === '完全') ? '[' + go + ']'
               : (kata === '部分') ? go
               : '"' + go + '"';              // 既定はフレーズ一致
    try {
      var it = AdsApp.campaigns().get();
      while (it.hasNext()) it.next().createNegativeKeyword(hyouki);
      sh.getRange(i + 2, 3).setValue('足しました ' + hyouki);
      sh.getRange(i + 2, 4).setValue(kyou);
      n++;
    } catch (e) {
      sh.getRange(i + 2, 3).setValue('🔴 失敗: ' + e);
      sh.getRange(i + 2, 4).setValue(kyou);
    }
  }
  return n;
}

// ── 小道具 ─────────────────────────────────────────────────────

/** micros（100万分の1）を円に直す */
function en_(v) {
  var x = Number(v);
  if (!isFinite(x)) return 0;
  return Math.round(x / 1000000);
}

/** タブが無ければ見出し付きで作る */
function tab_(ss, na, midashi) {
  var sh = ss.getSheetByName(na);
  if (!sh) {
    sh = ss.insertSheet(na);
    sh.getRange(1, 1, 1, midashi.length).setValues([midashi]).setFontWeight('bold');
    sh.setFrozenRows(1);
  }
  return sh;
}

/** 実行の記録。★失敗しても静かに終わらないために、必ず1行残す */
function nokosu_(ss, kyou, honbun) {
  var sh = tab_(ss, TAB_LOG, ['実行日時', '結果']);
  sh.appendRow([Utilities.formatDate(new Date(), AdsApp.currentAccount().getTimeZone(),
                                     'yyyy-MM-dd HH:mm'), honbun]);
}
