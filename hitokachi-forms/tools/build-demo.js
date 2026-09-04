#!/usr/bin/env node
/**
 * 触って試せるデモページを組み立てる。
 *
 *   node tools/build-demo.js
 *
 * ねらいは「デプロイ前に、実物と同じものを触って確かめられること」。
 * そのため入力画面・判定ロジック・帳票レイアウトは src/ の実物をそのまま読み込み、
 * Google のサービスを呼ぶところだけ差し替える。デモ用に作り直したものはない。
 *
 * 差し替えるのは 3 か所だけ:
 *   1. google.script.run  … サーバ呼び出しを、同じ関数のローカル実行に置き換える
 *   2. 保存先フォルダ     … Drive を見ずに、あらかじめ用意した顧客名で当たりを再現する
 *   3. PDF 化            … Google ドキュメント経由をやめ、帳票 HTML を画面に出す
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const SRC = path.join(ROOT, 'src');
const OUT = path.join(ROOT, 'demo', 'index.html');

const read = (f) => fs.readFileSync(path.join(SRC, f), 'utf8');

/** 実物のロジック。ブラウザでもそのまま動く素の JavaScript。 */
const LOGIC = ['Fields.gs', 'Config.gs', 'Judge.gs', 'Render.gs', 'Generate.gs', 'DriveUtil.gs', 'Existing.gs']
  .map(f => `/* ---- src/${f} ---- */\n${read(f)}`).join('\n\n');

/** 帳票のレイアウト。中身は触らず、文字列として持たせる。 */
const TEMPLATES = {
  SuitabilitySheet: read('SuitabilitySheet.html'),
  IntentSheet: read('IntentSheet.html')
};

/** 入力画面。CSS と処理を取り出して、そのまま使う。 */
const form = read('Form.html');
const formCss = form.match(/<style>([\s\S]*?)<\/style>/)[1];
const formJs = form.match(/<script>([\s\S]*?)<\/script>/)[1]
  .replace('var BOOT = <?!= boot ?>;', 'var BOOT = DEMO_BOOT;');

const page = `<title>適合性確認シート 作成デモ</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&display=swap">
<style>
/* ---- デモの外枠。入力画面そのものの見た目には手を入れない ---- */
:root {
  --demo-bg: #eef0f3;
  --demo-ink: #14181d;
  --demo-muted: #5a6672;
  --demo-line: #d5dae0;
  --demo-card: #ffffff;
  --demo-accent: #1a56a8;
  --demo-notice-bg: #fff8e1;
  --demo-notice-line: #e6c45a;
  --demo-notice-ink: #6b4e00;
  --demo-sheet: #ffffff;
}
:root:not([data-theme="light"]) { }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --demo-bg: #14181d;
    --demo-ink: #e6eaef;
    --demo-muted: #98a4b0;
    --demo-line: #2b323a;
    --demo-card: #1b2027;
    --demo-accent: #7aa9e8;
    --demo-notice-bg: #2c2716;
    --demo-notice-line: #6b5a1f;
    --demo-notice-ink: #e8d79a;
    --demo-sheet: #ffffff;
  }
}
:root[data-theme="dark"] {
  --demo-bg: #14181d;
  --demo-ink: #e6eaef;
  --demo-muted: #98a4b0;
  --demo-line: #2b323a;
  --demo-card: #1b2027;
  --demo-accent: #7aa9e8;
  --demo-notice-bg: #2c2716;
  --demo-notice-line: #6b5a1f;
  --demo-notice-ink: #e8d79a;
  --demo-sheet: #ffffff;
}

body {
  margin: 0;
  background: var(--demo-bg);
  color: var(--demo-ink);
  font-family: "Noto Sans JP", "Hiragino Sans", "Yu Gothic", sans-serif;
  font-size: 14px;
  line-height: 1.6;
}
.demo-shell { max-width: 1000px; margin: 0 auto; padding: 24px 16px 40px; }
.demo-head { display: flex; flex-wrap: wrap; gap: 6px 16px; align-items: baseline; margin-bottom: 14px; }
.demo-head h1 { font-size: 17px; font-weight: 700; margin: 0; letter-spacing: .02em; color: var(--demo-muted); }
.demo-head .sub { color: var(--demo-muted); font-size: 13px; }

.demo-notice {
  background: var(--demo-notice-bg);
  border: 1px solid var(--demo-notice-line);
  color: var(--demo-notice-ink);
  border-radius: 8px; padding: 12px 16px; margin-bottom: 18px; font-size: 13px;
}
.demo-notice b { font-weight: 700; }
.demo-notice ul { margin: 6px 0 0; padding-left: 20px; }

/* 入力画面は実物のまま埋め込むので、外枠の余白だけ調整する */
.demo-frame {
  background: var(--demo-card);
  border: 1px solid var(--demo-line);
  border-radius: 12px;
  overflow: hidden;
}
.demo-frame .wrap { padding-bottom: 24px; max-width: none; }
.demo-frame header h1 { font-size: 21px; }
.demo-frame .bar { position: static; border-top: 1px solid var(--demo-line); }
.demo-frame .bar.hide { display: none; }

/* 生成された帳票のプレビュー */
.sheets { margin-top: 22px; }
.sheets h2 {
  font-size: 15px; margin: 0 0 4px;
  display: flex; align-items: baseline; gap: 10px;
}
.sheets .hint { color: var(--demo-muted); font-size: 12px; font-weight: 400; }
.sheet-tabs { display: flex; gap: 8px; margin: 12px 0; flex-wrap: wrap; }
.sheet-tabs button {
  font-family: inherit; font-size: 13px; font-weight: 600; cursor: pointer;
  padding: 8px 16px; border-radius: 999px;
  border: 1px solid var(--demo-line); background: var(--demo-card); color: var(--demo-ink);
}
.sheet-tabs button[aria-pressed="true"] {
  background: var(--demo-accent); border-color: var(--demo-accent); color: #fff;
}
.sheet-paper {
  background: var(--demo-sheet); color: #1a1d21;
  border: 1px solid var(--demo-line); border-radius: 6px;
  padding: 26px 30px; overflow-x: auto;
}
.sheet-paper table { max-width: 100%; }
button:focus-visible, input:focus-visible, select:focus-visible, a:focus-visible {
  outline: 2px solid var(--demo-accent); outline-offset: 2px;
}
@media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }

/* ---- ここから src/Form.html の CSS をそのまま ---- */
${formCss}
</style>

<div class="demo-shell">
  <div class="demo-head">
    <h1>ヒトカチ 帳票作成システム</h1>
    <span class="sub">デプロイ前に、実物と同じ中身を触って確かめるページ</span>
  </div>

  <div class="demo-notice">
    <b>これは動作確認用のデモです。Google ドライブには何も保存されません。</b>
    <ul>
      <li>入力画面・適合性の判定・帳票のレイアウトは、実際に動くものと同じ中身です</li>
      <li>代理店・募集人・既存の顧客フォルダは、動きを見るための仮のデータです</li>
      <li>「PDFを作成して保存」を押すと、保存の代わりに<b>できあがる帳票をこの下に表示</b>します</li>
    </ul>
  </div>

  <div class="demo-frame">
    <div class="wrap">
      <header>
        <h1 id="title">帳票作成</h1>
        <div class="who" id="who"></div>
      </header>
      <div id="app"><p class="spin">読み込み中…</p></div>
    </div>
    <div class="bar hide" id="bar"></div>
  </div>

  <div class="sheets" id="sheets" hidden>
    <h2>できあがる帳票 <span class="hint">実際は、この内容が PDF になって顧客フォルダに保存されます</span></h2>
    <div class="sheet-tabs" id="sheetTabs"></div>
    <div class="sheet-paper" id="sheetPaper"></div>
  </div>
</div>

<script>
/* ================================================================
   1. 実物のロジック（src/*.gs をそのまま）
   ================================================================ */
${LOGIC}

/* ================================================================
   2. Google のサービスを使うところだけ、デモ用に置き換える
   ================================================================ */

/** Render.gs が使う日付整形。Apps Script の Utilities と同じ結果を返す。 */
var Utilities = {
  formatDate: function (d, tz, fmt) {
    var p = function (n) { return String(n).length < 2 ? '0' + n : String(n); };
    var y = d.getFullYear(), m = p(d.getMonth() + 1), day = p(d.getDate());
    if (fmt === 'yyyy-MM-dd') return y + '-' + m + '-' + day;
    if (fmt === 'yyyyMMdd') return '' + y + m + day;
    return y + '/' + m + '/' + day;
  }
};

var TEMPLATES = ${JSON.stringify(TEMPLATES)};

/**
 * HtmlService のテンプレート構文（<? ?> / <?= ?> / <?!= ?>）を評価する。
 * Apps Script 側と同じ書き方のまま帳票 HTML を組み立てるための、最小の実装。
 */
function renderSheet(name, model) {
  var source = TEMPLATES[name];
  var code = 'var __out = "";\\n';
  var re = /<\\?(=|!=)?([\\s\\S]*?)\\?>/g;
  var pos = 0, m;
  var esc = function (s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  };
  while ((m = re.exec(source)) !== null) {
    code += '__out += ' + JSON.stringify(source.slice(pos, m.index)) + ';\\n';
    if (m[1] === '=') code += '__out += __esc(' + m[2] + ');\\n';
    else if (m[1] === '!=') code += '__out += (' + m[2] + ');\\n';
    else code += m[2] + '\\n';
    pos = re.lastIndex;
  }
  code += '__out += ' + JSON.stringify(source.slice(pos)) + ';\\nreturn __out;';
  return new Function('m', '__esc', code)(model, esc);
}

/* ---- デモ用のマスタ。実際は設定スプレッドシートから読む ---- */

var DEMO_AGENTS = [
  { name: '佐々木 嶺', email: 'info@hitokachi.com', tel: '080-6817-4796',
    zip: '134-0081', address1: '東京都 江戸川区 北葛西',
    address2: '５－１４－１１ クオーディア西葛西５０３', agency: 'ヒトカチ株式会社' },
  { name: '髙橋 知史', email: 's-takahashi@hitokachi.com', tel: '080-2238-7592',
    zip: '134-0081', address1: '東京都 江戸川区 北葛西',
    address2: '５－１４－１１ クオーディア西葛西５０３', agency: 'ヒトカチ株式会社' }
];

/**
 * 代理店マスタの代わり。共同募集の相方はここに登録された名前から選ぶ。
 * Config.gs の getAgencies_ は設定スプレッドシートを読むので、丸ごと差し替える。
 */
var DEMO_AGENCIES = [
  { name: 'ヒトカチ株式会社', folderId: 'demo-agency', coAgents: [] },
  { name: 'クレスト保険', folderId: 'demo-agency-2',
    coAgents: ['熊澤 善弘', '小川 康之', '矢野 克臣'] }
];
getAgencies_ = function () { return DEMO_AGENCIES; };

// 設定シートは読めないので、保険種類の判定は既定のキーワードで動かす。
getSetting_ = function (key, fallback) { return fallback; };

/** 「既にこの顧客のフォルダがある」状況を再現するための仮の一覧。 */
var DEMO_EXISTING_FOLDERS = ['種田 裕貴', '石川 康幸', '三好 雄策', '田中'];

var DEMO_FIELD_CONFIG = (function () {
  var conf = {};
  FIELD_DEFS.forEach(function (f) {
    conf[f.key] = { mode: f.defaultMode || 'form', fixedValue: '' };
  });
  return conf;
})();

var DEMO_BOOT = {
  allowed: true,
  title: '適合性確認シート／意向把握シート 作成',
  email: 'info@hitokachi.com（デモ）',
  sections: FIELD_SECTIONS,
  agencies: DEMO_AGENCIES.map(function (a) { return { name: a.name, coAgents: a.coAgents }; }),
  agents: DEMO_AGENTS,
  needs: NEEDS,
  defaults: { contractType: '個人' },
  fields: FIELD_DEFS.map(function (f) {
    var o = {
      key: f.key, label: f.label, type: f.type, section: f.section,
      required: !!f.required, unit: f.unit || '', note: f.note || '',
      showIf: f.showIf || '', mode: DEMO_FIELD_CONFIG[f.key].mode,
      defaultValue: f.defaultValue == null ? '' : f.defaultValue,
      options: f.options || []
    };
    if (f.type === 'needs') o.options = NEEDS;
    return o;
  }).filter(function (f) { return f.mode === 'form'; })
};

/** 保存先の当たりを、仮の一覧から再現する。Drive は見ない。 */
function demoResolveDestination(customerName) {
  var target = normalizeName_(customerName);
  var hits = DEMO_EXISTING_FOLDERS
    .filter(function (n) { return normalizeName_(n) === target; })
    .map(function (n, i) { return { id: 'demo-folder-' + i, name: n }; });
  return {
    agencyName: 'ヒトカチ株式会社',
    agencyFolderId: 'demo-agency',
    agencyFolderName: 'ヒトカチ株式会社 共有フォルダ',
    customerName: customerName,
    newFolderName: sanitizeFileName_(customerName),
    candidates: hits,
    status: hits.length === 0 ? 'new' : (hits.length === 1 ? 'match' : 'ambiguous')
  };
}

/* ---- 入力画面から呼ばれるサーバ関数の代わり ---- */

function demoPrepare(raw) {
  var conf = DEMO_FIELD_CONFIG;
  var data = applyFieldConfig_(raw || {}, conf);
  var errors = validate_(data, conf);
  if (errors.length) return { ok: false, errors: errors };

  var answers = defaultAnswers_(data);
  return {
    ok: true,
    data: data,
    answers: answers,
    summary: summarizeAnswers_(answers),
    advice: judge_(data, conf),   // 「使わない」項目に依存する判定は参考判定を出さない
    judgeKeys: JUDGE_KEYS,
    judgeLabels: JUDGE_LABELS,
    destination: demoResolveDestination(data.customerName)
  };
}

function demoSubmit(data, choice, rawAnswers) {
  var conf = DEMO_FIELD_CONFIG;
  var checked = applyFieldConfig_(data || {}, conf);
  var errors = validate_(checked, conf);
  if (errors.length) return { ok: false, errors: errors };

  var answers = normalizeAnswers_(checked, rawAnswers);
  var summary = summarizeAnswers_(answers);
  var agent = null;
  for (var i = 0; i < DEMO_AGENTS.length; i++) {
    if (DEMO_AGENTS[i].name === checked.agent) agent = DEMO_AGENTS[i];
  }
  var model = buildModel_(checked, answers, agent || DEMO_AGENTS[0], checked.agency);
  showSheets(model, checked);

  var dest = demoResolveDestination(checked.customerName);
  var folderName = (choice && choice !== 'new' && dest.candidates.length)
    ? dest.candidates[0].name : dest.newFolderName;
  var stamp = String(checked.confirmDate || '').replace(/-/g, '');

  return {
    ok: true,
    result: {
      folderName: folderName,
      folderCreated: !(choice && choice !== 'new'),
      folderUrl: '#',
      files: [
        { name: '適合性確認シート_' + checked.customerName + '_' + stamp + '.pdf', url: '#sheets' },
        { name: '意向把握シート_' + checked.customerName + '_' + stamp + '.pdf', url: '#sheets' }
      ],
      answers: answers,
      judgment: summary
    }
  };
}

/** 入力画面のコードに手を入れず済むよう、google.script.run の形を真似る。 */
var google = { script: { run: (function () {
  var ok = null, ng = null;
  var api = {
    withSuccessHandler: function (f) { ok = f; return api; },
    withFailureHandler: function (f) { ng = f; return api; },
    prepare: function (values) {
      setTimeout(function () {
        try { ok(demoPrepare(values)); } catch (e) { if (ng) ng(e); else throw e; }
      }, 200);
    },
    submit: function (data, choice, answers) {
      setTimeout(function () {
        try { ok(demoSubmit(data, choice, answers)); } catch (e) { if (ng) ng(e); else throw e; }
      }, 500);
    }
  };
  return api;
})() } };

/* ---- できあがった帳票を画面に出す ---- */

function showSheets(model, data) {
  var sheets = [
    { key: 'SuitabilitySheet', label: '適合性確認シート' },
    { key: 'IntentSheet', label: '意向把握シート' }
  ];
  var host = document.getElementById('sheets');
  var tabs = document.getElementById('sheetTabs');
  var paper = document.getElementById('sheetPaper');

  var draw = function (i) {
    paper.innerHTML = renderSheet(sheets[i].key, model);
    Array.prototype.forEach.call(tabs.children, function (b, j) {
      b.setAttribute('aria-pressed', String(i === j));
    });
  };

  tabs.innerHTML = '';
  sheets.forEach(function (s, i) {
    var b = document.createElement('button');
    b.type = 'button';
    b.textContent = s.label;
    b.setAttribute('aria-pressed', String(i === 0));
    b.addEventListener('click', function () { draw(i); });
    tabs.appendChild(b);
  });

  host.hidden = false;
  draw(0);
  host.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/* ================================================================
   3. 入力画面（src/Form.html をそのまま）
   ================================================================ */
${formJs}
</script>
`;

fs.mkdirSync(path.dirname(OUT), { recursive: true });
fs.writeFileSync(OUT, page, 'utf8');
console.log('デモを書き出しました: ' + path.relative(process.cwd(), OUT));
console.log('  入力項目 ' + DEMO_COUNT(page) + ' 項目 / ' + (page.length / 1024).toFixed(0) + ' KB');

function DEMO_COUNT() {
  return LOGIC.split('FIELD_DEFS').length > 1 ? '（実物の定義から生成）' : '?';
}
