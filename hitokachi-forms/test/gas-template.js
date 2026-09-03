/**
 * Apps Script の HtmlService テンプレート（<? ?> / <?= ?> / <?!= ?>）を
 * Node 上で評価する最小実装。テンプレートの構文誤りを手元で見つけるために使う。
 */
const vm = require('vm');

function escapeHtml(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function render(source, model) {
  let code = 'var __out = "";\n';
  let pos = 0;
  const re = /<\?(=|!=)?([\s\S]*?)\?>/g;
  let match;
  while ((match = re.exec(source)) !== null) {
    code += '__out += ' + JSON.stringify(source.slice(pos, match.index)) + ';\n';
    const body = match[2];
    if (match[1] === '=') code += '__out += __esc(' + body + ');\n';
    else if (match[1] === '!=') code += '__out += (' + body + ');\n';
    else code += body + '\n';
    pos = re.lastIndex;
  }
  code += '__out += ' + JSON.stringify(source.slice(pos)) + ';\n__out;';

  const ctx = { m: model, __esc: escapeHtml };
  vm.createContext(ctx);
  return vm.runInContext(code, ctx);
}

module.exports = { render };
