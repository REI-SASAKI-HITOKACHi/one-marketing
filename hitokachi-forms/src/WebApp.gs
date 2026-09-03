/**
 * ウェブアプリの入口。
 *
 * 画面は 2 段階。
 *   1. 入力 → prepare()  … 検証・適合性判定・保存先の候補を返す
 *   2. 確認 → submit()   … PDF を作って保存する
 *
 * 既存の顧客フォルダに当たったときは prepare() が候補を返し、利用者が
 * 「既存に保存」か「新規作成」かを選ぶまで書き込みは起きない。
 */

function doGet() {
  var t = HtmlService.createTemplateFromFile('Form');
  // script タグの中に埋めるので、データ側の "<" が要素を閉じないようにしておく。
  t.boot = JSON.stringify(bootstrap_()).replace(/</g, '\\u003c');
  return t.evaluate()
    .setTitle('帳票作成')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}

/** 画面を組み立てるのに必要なものを一式返す。 */
function bootstrap_() {
  var gate = checkAccess_();
  if (!gate.allowed) return { allowed: false, message: gate.message };

  var conf = getFieldConfig_();
  var defaultContract = String(getSetting_('既定の契約形態', '個人'));
  var fields = FIELD_DEFS.map(function (f) {
    if (f.key === 'contractType') f = Object.assign({}, f, { defaultValue: defaultContract });
    var o = {
      key: f.key, label: f.label, type: f.type, section: f.section,
      required: !!f.required, unit: f.unit || '', note: f.note || '',
      showIf: f.showIf || '', mode: conf[f.key].mode,
      defaultValue: f.defaultValue == null ? '' : f.defaultValue,
      options: f.options || []
    };
    if (f.type === 'needs') o.options = NEEDS;
    return o;
  }).filter(function (f) { return f.mode === 'form'; });

  return {
    allowed: true,
    title: String(getSetting_('画面タイトル', '適合性確認シート／意向把握シート 作成')),
    email: currentUserEmail_(),
    sections: FIELD_SECTIONS,
    fields: fields,
    agencies: getAgencies_().map(function (a) { return a.name; }),
    agents: getAgents_(),
    needs: NEEDS,
    defaults: { contractType: String(getSetting_('既定の契約形態', '個人')) }
  };
}

function checkAccess_() {
  var restrict;
  try {
    restrict = isTrue_(getSetting_('アクセス制限', 'true'));
  } catch (e) {
    return { allowed: false, message: e.message };
  }
  if (!restrict) return { allowed: true };

  var email = String(currentUserEmail_()).toLowerCase();
  var allowed = getAllowedEmails_();
  if (email && allowed.indexOf(email) >= 0) return { allowed: true };
  return {
    allowed: false,
    message: 'このシステムを使う権限がありません（' + (email || 'アカウント不明') + '）。'
      + '設定スプレッドシートの「利用者」シートにアドレスを追加してください。'
  };
}

/** 手順1: 検証・判定・保存先の候補。ここでは何も書き込まない。 */
function prepare(raw) {
  var gate = checkAccess_();
  if (!gate.allowed) return { ok: false, errors: [gate.message] };

  try {
    var conf = getFieldConfig_();
    var data = applyFieldConfig_(raw || {}, conf);
    var errors = validate_(data, conf);
    if (errors.length) return { ok: false, errors: errors };

    var judgment = judge_(data);
    var dest = resolveDestination_(data.agency, data.customerName);

    return {
      ok: true,
      data: data,
      judgment: judgment,
      judgeLabels: JUDGE_LABELS,
      destination: dest
    };
  } catch (e) {
    return { ok: false, errors: [e.message] };
  }
}

/** 手順2: PDF を作って保存する。 */
function submit(data, choice) {
  var gate = checkAccess_();
  if (!gate.allowed) return { ok: false, errors: [gate.message] };

  var lock = LockService.getScriptLock();
  // 同じ顧客の同時送信でフォルダが二重にできるのを防ぐ。
  if (!lock.tryLock(30000)) {
    return { ok: false, errors: ['ほかの処理が実行中です。少し待ってからもう一度お試しください。'] };
  }
  try {
    // クライアントを経由して戻ってきた値なので、prepare() と同じ検証をやり直す。
    // 画面の不整合や将来の改修で検証が抜ける経路を塞ぐ。
    var conf = getFieldConfig_();
    var checked = applyFieldConfig_(data || {}, conf);
    var errors = validate_(checked, conf);
    if (errors.length) return { ok: false, errors: errors };

    var result = generateAndSave_(checked, choice);
    return { ok: true, result: result };
  } catch (e) {
    return { ok: false, errors: [e.message] };
  } finally {
    lock.releaseLock();
  }
}
