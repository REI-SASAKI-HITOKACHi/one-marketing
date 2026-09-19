#!/usr/bin/env node
/**
 * ファイル群のハッシュを1つ出す。改行コードの違いは無視する。
 *
 *   node tools/hash-files.js deploy-paste
 *   node tools/hash-files.js master .tsv
 *
 * run-all.sh の「生成物がソースと一致しているか」の判定に使う。
 * md5sum を使っていたが、
 *   - Windows には md5sum が無いことがある
 *   - git が CRLF でチェックアウトすると、中身が同じでもハッシュが変わる
 * ので、**改行を LF に揃えてから**ハッシュを取る。
 * 改行だけの差は「同じ」と見なす（GASエディタに貼るときも改行は問題にならない）。
 */
'use strict';

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const dir = process.argv[2];
const suffix = process.argv[3] || '';

if (!dir) {
  console.error('使い方: node tools/hash-files.js <ディレクトリ> [拡張子]');
  process.exit(2);
}

let names;
try {
  names = fs.readdirSync(dir).filter(n => n.endsWith(suffix)).sort();
} catch (e) {
  console.log('(ディレクトリなし)');
  process.exit(0);
}

const h = crypto.createHash('sha256');

names.forEach(name => {
  const full = path.join(dir, name);
  if (!fs.statSync(full).isFile()) return;
  const body = fs.readFileSync(full, 'utf8').replace(/\r\n/g, '\n');
  h.update(name).update('\0').update(body).update('\0');
});

console.log(h.digest('hex'));
