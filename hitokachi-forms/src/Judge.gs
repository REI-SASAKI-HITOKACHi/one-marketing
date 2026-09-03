/**
 * 適合性確認シート「２．」①〜⑥ の自動判定。
 *
 * 判定根拠は原本の【別紙】（適合性確認の基準）そのまま。入力から機械的に導けるので
 * 募集人には判定させず、ここで一括して出す。
 *
 * 戻り値の各項目:
 *   value  … 'yes' | 'no' | 'na'（法人契約で対象外のとき）
 *   reason … 画面と送信ログに出す判定理由
 */

function judge_(d) {
  var isCorp = d.contractType === '法人';
  var items = {};

  items.i1 = isCorp ? na_('法人契約のため対象外') : judgeAge_(d);
  items.i2 = isCorp ? na_('法人契約のため対象外') : judgeOccupation_(d);
  items.i3 = isCorp ? na_('法人契約のため対象外') : judgeBalance_(d);
  items.i4 = judgeExperience_(d);
  items.i5 = judgeSource_(d);
  items.i6 = judgeIntent_(d, isCorp);

  var ng = [];
  ['i1', 'i2', 'i3', 'i4', 'i5', 'i6'].forEach(function (k) {
    if (items[k].value === 'no') ng.push(k);
  });

  return {
    items: items,
    suitable: ng.length === 0,
    ngKeys: ng,
    // 別紙より: 「いいえ」が1つでもあれば変額保険は適合しない
    message: ng.length === 0
      ? '適合。変額保険の提案が可能です。'
      : '不適合。「いいえ」が ' + ng.length + ' 件あるため、変額保険はお客さまに適合しません。'
        + '他の定額保険を提案してください。'
  };
}

function yes_(reason) { return { value: 'yes', reason: reason }; }
function no_(reason)  { return { value: 'no',  reason: reason }; }
function na_(reason)  { return { value: 'na',  reason: reason }; }

/** ① お一人での判断が的確にできている（70歳以上は環境が整っている）。 */
function judgeAge_(d) {
  var age = num_(d.age);
  if (age === null) return no_('年齢が未入力');
  if (age < 70) return yes_(age + '歳（70歳未満）');
  if (d.elderlyMethod) return yes_('70歳以上だが「' + d.elderlyMethod + '」で募集');
  return no_('70歳以上だが、別紙＜１＞〜＜３＞の募集方法が選択されていない');
}

/** ② パート・アルバイト、学生、主婦、無職ではない。 */
function judgeOccupation_(d) {
  var cls = d.occupationClass || '左記以外';
  if (cls === '左記以外') return yes_('職業区分：' + cls);
  if (d.householdConfirmed) {
    return yes_(cls + 'だが、世帯主・家族等の職業を確認し継続的な支払いに問題なしと確認済み');
  }
  return no_(cls + 'であり、世帯主・家族等による支払い能力の確認がされていない');
}

/**
 * ③ 保険料の額が年収・金融資産に比べてバランスを欠く状態にない。
 *
 * 別紙より、次のいずれかを満たせば「はい」。
 *   a. 年間保険料 ≦ 年収 × 20%
 *   b. 総払込保険料（年間保険料 × 払込年数）≦ 金融資産 × 30%
 *   c. a の不足分 × 払込年数 ≦ 金融資産 × 30%（組み合わせ）
 */
function judgeBalance_(d) {
  var premium = num_(d.annualPremium);
  var years   = num_(d.payYears);
  var income  = num_(d.income);
  var assets  = num_(d.assets);
  if (premium === null || years === null || income === null || assets === null) {
    return no_('年収・金融資産・年間保険料・払込期間のいずれかが未入力');
  }

  var incomeCap = income * 0.2;
  var assetsCap = assets * 0.3;
  var f = function (n) { return Math.round(n * 10) / 10; };

  if (premium <= incomeCap) {
    return yes_('年間保険料 ' + premium + '万円 ≦ 年収の20% ' + f(incomeCap) + '万円');
  }
  if (premium * years <= assetsCap) {
    return yes_('総払込保険料 ' + f(premium * years) + '万円 ≦ 金融資産の30% ' + f(assetsCap) + '万円');
  }
  var shortfall = (premium - incomeCap) * years;
  if (shortfall <= assetsCap) {
    return yes_('年収の20%を超える不足分 ' + f(shortfall) + '万円 ≦ 金融資産の30% ' + f(assetsCap) + '万円（組み合わせ）');
  }
  return no_('年間保険料 ' + premium + '万円が年収の20%（' + f(incomeCap) + '万円）を超え、'
    + '不足分 ' + f(shortfall) + '万円も金融資産の30%（' + f(assetsCap) + '万円）を超えている');
}

/** ④ 投資性商品のリスクを説明し、十分に理解のうえ許容いただいた。 */
function judgeExperience_(d) {
  var exp = d.experience || [];
  var only = exp.length === 0 || (exp.length === 1 && exp[0] === '投資経験なし');
  if (!only) return yes_('投資経験あり：' + exp.join('、'));
  if (d.experienceExplained) {
    return yes_('投資経験なしだが、時間を確保して仕組み・リスク・諸費用・解約控除等を説明済み');
  }
  return no_('投資経験がなく、十分な説明を行った旨のチェックがない');
}

/** ⑤ 保険料原資がア〜ウをすべて満たしている。 */
function judgeSource_(d) {
  var reasons = [];
  var a = d.sourceNotMaturity || d.sourceMaturityExplained;
  if (!a) reasons.push('ア（満期金・解約返戻金が原資でない、または不利益事項を説明し了解を得た）を満たしていない');
  if (!d.sourceSpare)   reasons.push('イ（元本割れを許容できる余裕資金）を満たしていない');
  if (!d.sourceNotLoan) reasons.push('ウ（借入金を前提としていない）を満たしていない');
  if (reasons.length) return no_(reasons.join(' / '));

  var note = d.sourceNotMaturity ? 'ア〜ウをすべて満たしている'
    : 'アは満期金・解約返戻金だが不利益事項を説明し了解を得た。イ・ウは充足';
  return yes_(note);
}

/** ⑥ ⑦のリスク選好と⑧の意向が下線の項目に該当している。 */
function judgeIntent_(d, isCorp) {
  if (d.riskTolerance !== RISK_YES) {
    return no_('⑦で「関心がなくリスクを理解していない／許容できない」が選択されている');
  }
  var suitKeys = needsToSuitKeys_(d.needs || []);
  var wanted = isCorp ? ['business', 'welfare', 'retire'] : ['death', 'medical', 'savings'];
  var hit = suitKeys.filter(function (k) { return wanted.indexOf(k) >= 0; });
  if (hit.length === 0) {
    return no_((isCorp ? '法人契約の d〜f' : '個人契約の a〜c')
      + 'に該当するご意向が選択されていない（「その他」のみは「いいえ」）');
  }
  var labels = hit.map(function (k) {
    for (var i = 0; i < SUIT_NEEDS.length; i++) if (SUIT_NEEDS[i].key === k) return SUIT_NEEDS[i].label;
    return k;
  });
  return yes_('リスクを許容でき、ご意向が「' + labels.join('」「') + '」に該当');
}

function num_(v) {
  if (v === '' || v == null) return null;
  var n = Number(String(v).replace(/[^0-9.\-]/g, ''));
  return isNaN(n) ? null : n;
}

var JUDGE_LABELS = {
  i1: '1.① お客さまはお一人での判断が的確にできている。70歳以上の高齢者の場合は的確に判断できる環境が整っている。',
  i2: '1.② パート・アルバイト、学生、主婦、無職ではない。',
  i3: '1.③④ 保険料の額が、年収・金融資産に比べて、バランスを欠く状態にない。',
  i4: '1.⑤ 投資性商品のリスクについての説明をし、十分に理解のうえ、許容いただいた。',
  i5: '1.⑥ 以下、ア〜ウをすべて満たしている。'
    + 'ア.保険料の原資が定期性預貯金や他の金融商品の満期金または、解約返戻金ではない。'
    + 'イ.元本割れがある場合でも許容できる余裕資金を原資としている。'
    + 'ウ.充当される資金が借入金を前提としていない。',
  i6: '1.⑦⑧ 下線の項目に該当している。'
};
