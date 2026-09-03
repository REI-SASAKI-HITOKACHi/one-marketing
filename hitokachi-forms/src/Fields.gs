/**
 * 入力項目の定義。
 *
 * ここが唯一の項目マスタで、入力フォーム・設定シート・帳票差し込み・ログの
 * すべてがこの定義から組み立てられる。項目を足したいときはここに 1 行足す。
 *
 * mode（表示するか固定するか）は設定スプレッドシートの「項目設定」シートで
 * 上書きできる。defaultMode は初回セットアップ時の初期値。
 *   form   … 入力フォームに表示する
 *   fixed  … フォームには出さず、設定シートの固定値を使う
 *   hidden … 使わない（帳票では空欄になる）
 */

/** 保障ニーズ。意向把握シートの 8 項目が入力の粒度で、適合性⑧へは集約して流す。 */
var NEEDS = [
  { key: 'death',     label: '死亡時の保障',                   owner: '個人', suit: 'death'    },
  { key: 'medical',   label: '病気・ケガ・介護の保障',          owner: '個人', suit: 'medical'  },
  { key: 'cancer',    label: 'がんなどの特定疾病に備える保障',  owner: '個人', suit: 'medical'  },
  { key: 'education', label: '子供の教育資金準備',              owner: '個人', suit: 'savings'  },
  { key: 'pension',   label: '老後の生活資金準備',              owner: '個人', suit: 'savings'  },
  { key: 'business',  label: '事業保障',                        owner: '法人', suit: 'business' },
  { key: 'welfare',   label: '従業員の福利厚生',                owner: '法人', suit: 'welfare'  },
  { key: 'retire',    label: '退職金に対する備え',              owner: '法人', suit: 'retire'   }
];

/** 適合性確認シート⑧の選択肢。NEEDS の suit がこのキーに対応する。 */
var SUIT_NEEDS = [
  { key: 'death',    label: '死亡時の保障',                          owner: '個人' },
  { key: 'medical',  label: '病気・ケガ・がん・特定疾病・介護の保障', owner: '個人' },
  { key: 'savings',  label: '貯蓄（教育資金・老後生活資金準備等）',   owner: '個人' },
  { key: 'business', label: '事業保障・事業継承（役員の保障）',       owner: '法人' },
  { key: 'welfare',  label: '福利厚生（従業員の保障）',               owner: '法人' },
  { key: 'retire',   label: '退職金（生存・死亡）準備',               owner: '法人' },
  { key: 'other',    label: 'その他',                                 owner: '共通' }
];

var EXPERIENCE_OPTIONS = [
  '株式', '投資信託', '公社債', '特定保険契約（変額保険・外貨建保険等）',
  '外貨預金', 'その他', '投資経験なし'
];

var PREMIUM_SOURCE_OPTIONS = [
  '預貯金・給与', '株式', '投資信託', '公社債',
  '特定保険契約（変額保険・外貨建保険等）', '外貨預金', 'その他'
];

var RISK_YES = '株式や為替相場に関心がありリスクを理解し（または理解いただくことができ）、許容することができる';
var RISK_NO  = '株式や為替相場に関心がなくリスクを理解していない（または理解いただくことができず）、許容することができない';

var ELDERLY_METHODS = [
  '＜１＞70歳未満の親族の同席をともなった募集',
  '＜２＞複数回の面談による募集',
  '＜２＞複数回の面談＋＜３＞70歳未満の親族への説明'
];

var OCCUPATION_CLASSES = ['左記以外', 'パート・アルバイト', '学生', '主婦', '無職'];

var FIELD_DEFS = [
  // ---- 基本（両帳票に効く） ----
  { key: 'agency',       label: '取扱代理店',   type: 'agency', section: '基本', required: true,  defaultMode: 'form' },
  { key: 'agent',        label: '募集人',       type: 'agent',  section: '基本', required: true,  defaultMode: 'form' },
  { key: 'contractType', label: '契約形態',     type: 'radio',  section: '基本', required: true,  defaultMode: 'form',
    options: ['個人', '法人'], defaultValue: '個人',
    note: '法人を選ぶと適合性確認シートの①〜④および2.①〜③が対象外になる' },
  { key: 'customerName', label: '契約者氏名',   type: 'text',   section: '基本', required: true,  defaultMode: 'form',
    note: '保存先の顧客フォルダ名にも使う' },
  { key: 'confirmDate',  label: '確認日',       type: 'date',   section: '基本', required: true,  defaultMode: 'form',
    note: '適合性の確認日／意向把握シートの「当初のご意向」確認日' },
  { key: 'guardianName',     label: '親権者氏名',        type: 'text', section: '基本', defaultMode: 'hidden',
    note: '契約者が未成年の場合のみ' },
  { key: 'guardianRelation', label: '契約者からみた続柄', type: 'text', section: '基本', defaultMode: 'hidden' },

  // ---- 適合性確認シート ----
  { key: 'age',    label: '年齢',   type: 'number', unit: '歳', section: '適合性', required: true, defaultMode: 'form' },
  { key: 'elderlyMethod', label: '70歳以上の場合の募集方法', type: 'select', section: '適合性', defaultMode: 'form',
    options: ELDERLY_METHODS, showIf: 'elderly',
    note: '70歳以上のときだけ表示。未選択だと判定①が「いいえ」になる' },
  { key: 'occupation',      label: '職業',     type: 'text',  section: '適合性', required: true, defaultMode: 'form' },
  { key: 'occupationClass', label: '職業区分', type: 'radio', section: '適合性', required: true, defaultMode: 'form',
    options: OCCUPATION_CLASSES, defaultValue: '左記以外',
    note: '判定②に使う。帳票には出力しない' },
  { key: 'householdConfirmed',
    label: '世帯主・家族等の職業を確認し、保険料の継続的な支払いに問題がないことを確認した',
    type: 'check', section: '適合性', defaultMode: 'form', showIf: 'nonRegularOccupation' },
  { key: 'income',        label: '年収',             type: 'number', unit: '万円', section: '適合性', required: true, defaultMode: 'form' },
  { key: 'assets',        label: '金融資産',         type: 'number', unit: '万円', section: '適合性', required: true, defaultMode: 'form' },
  { key: 'annualPremium', label: '年間保険料',       type: 'number', unit: '万円', section: '適合性', required: true, defaultMode: 'form',
    note: '判定③（年収の20%／金融資産の30%）に使う。帳票には出力しない' },
  { key: 'payYears',      label: '保険料払込期間',   type: 'number', unit: '年',   section: '適合性', required: true, defaultMode: 'form',
    note: '判定③に使う。帳票には出力しない' },
  { key: 'experience',    label: 'これまでご購入されたことのある金融商品', type: 'multi', section: '適合性', defaultMode: 'form',
    options: EXPERIENCE_OPTIONS },
  { key: 'experienceOther', label: '金融商品「その他」の内容', type: 'text', section: '適合性', defaultMode: 'form' },
  { key: 'experienceExplained',
    label: '投資経験がないため、変額保険の仕組み・特徴・投資リスク・諸費用・解約控除等を十分に理解いただく時間を確保して説明した',
    type: 'check', section: '適合性', defaultMode: 'form', showIf: 'noExperience' },
  { key: 'premiumSource',      label: '保険料原資',                 type: 'multi', section: '適合性', defaultMode: 'form',
    options: PREMIUM_SOURCE_OPTIONS },
  { key: 'premiumSourceOther', label: '保険料原資「その他」の内容', type: 'text',  section: '適合性', defaultMode: 'form' },
  { key: 'sourceNotMaturity',
    label: 'ア．保険料の原資が定期性預貯金や他の金融商品の満期金または解約返戻金ではない',
    type: 'check', section: '適合性', defaultMode: 'form', defaultValue: true },
  { key: 'sourceMaturityExplained',
    label: '（満期金・解約返戻金が原資の場合）商品特性等や解約による不利益事項を十分に説明し、了解を得た',
    type: 'check', section: '適合性', defaultMode: 'form', showIf: 'maturitySource' },
  { key: 'sourceSpare',
    label: 'イ．元本割れがある場合でも許容できる余裕資金を原資としている',
    type: 'check', section: '適合性', defaultMode: 'form', defaultValue: true },
  { key: 'sourceNotLoan',
    label: 'ウ．充当される資金が借入金を前提としていない',
    type: 'check', section: '適合性', defaultMode: 'form', defaultValue: true },
  { key: 'riskTolerance', label: '株式や為替相場に関する興味やリスク選好度合', type: 'radio', section: '適合性',
    required: true, defaultMode: 'form', options: [RISK_YES, RISK_NO] },

  // ---- 意向把握シート ----
  { key: 'needs',      label: 'ご希望の保障分野・目的', type: 'needs', section: '意向', required: true, defaultMode: 'form',
    note: '意向把握シート「当初のご意向」。適合性⑧へは自動で集約する' },
  { key: 'needsOther', label: '適合性⑧「その他」の内容', type: 'text', section: '意向', defaultMode: 'form' },
  { key: 'savings',    label: '貯蓄部分を必要とされますか', type: 'radio', section: '意向', required: true, defaultMode: 'form',
    options: ['①ある方が良い', '②なくても良い'] },
  { key: 'wishPeriod',  label: '保険期間のご希望',   type: 'text', section: '意向', defaultMode: 'form' },
  { key: 'wishAmount',  label: '保険金額のご希望',   type: 'text', section: '意向', defaultMode: 'form' },
  { key: 'wishPremium', label: '保険料のご希望',     type: 'text', section: '意向', defaultMode: 'form' },
  { key: 'wishOther',   label: 'その他のご希望',     type: 'text', section: '意向', defaultMode: 'form' },
  { key: 'finalDate',   label: '最終のご意向 確認日', type: 'date', section: '意向', defaultMode: 'form',
    note: '空欄なら確認日と同じ日付を入れる' },

  // ---- 既定では非表示。設定シートで form にすれば使える ----
  { key: 'estimatedNeeds',   label: '推定のご意向（保障分野）',   type: 'needs', section: '任意', defaultMode: 'hidden',
    note: '募集人の推定に基づいて提案する場合のみ記入する欄' },
  { key: 'estimatedSavings', label: '推定のご意向（貯蓄部分）',   type: 'radio', section: '任意', defaultMode: 'hidden',
    options: ['①ある方が良い', '②なくても良い'] },
  { key: 'finalNeeds',       label: '最終のご意向（保障分野）',   type: 'needs', section: '任意', defaultMode: 'hidden',
    note: '空欄なら「当初のご意向」と同じ内容を入れる' },
  { key: 'finalSavings',     label: '最終のご意向（貯蓄部分）',   type: 'radio', section: '任意', defaultMode: 'hidden',
    options: ['①ある方が良い', '②なくても良い'] },
  { key: 'changeLog',        label: 'ご意向の変化の内容等',       type: 'rows',  section: '任意', defaultMode: 'hidden',
    note: '日付と内容の組を最大3行まで' },

  // ---- 検証欄。募集後に別タイミングで入れるため既定では非表示 ----
  { key: 'verifyDate',   label: '検証日',           type: 'date',  section: '検証欄', defaultMode: 'hidden' },
  { key: 'verifierName', label: '検証実施者氏名',   type: 'text',  section: '検証欄', defaultMode: 'hidden' },
  { key: 'verifyResult', label: '検証結果',         type: 'radio', section: '検証欄', defaultMode: 'hidden',
    options: ['適', '不適'] }
];

var FIELD_SECTIONS = ['基本', '適合性', '意向', '任意', '検証欄'];

function fieldByKey_(key) {
  for (var i = 0; i < FIELD_DEFS.length; i++) {
    if (FIELD_DEFS[i].key === key) return FIELD_DEFS[i];
  }
  return null;
}

/** NEEDS のキー配列を適合性⑧のキー配列に集約する。 */
function needsToSuitKeys_(needKeys) {
  var seen = {};
  var out = [];
  (needKeys || []).forEach(function (k) {
    for (var i = 0; i < NEEDS.length; i++) {
      if (NEEDS[i].key === k && !seen[NEEDS[i].suit]) {
        seen[NEEDS[i].suit] = true;
        out.push(NEEDS[i].suit);
      }
    }
  });
  return out;
}
