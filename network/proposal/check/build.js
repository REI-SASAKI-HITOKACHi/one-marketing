// 企画書のPDF化と検査。検査に1件でも引っかかったら終了コード1
const { chromium } = require('playwright');
const path = require('path');
const DIR = path.resolve(__dirname, '..');
const OUT = path.join(DIR, '協力店ネット_企画書.pdf');
(async () => {
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
  const page = await b.newPage({ viewport: { width: 1123, height: 794 } });
  const problems = [];
  page.on('requestfailed', r => problems.push('読み込み失敗: ' + r.url().split('/').pop()));
  page.on('pageerror', e => problems.push('JSエラー: ' + e.message));
  await page.emulateMedia({ media: 'print' });
  await page.goto('file://' + path.join(DIR, 'proposal.html'), { waitUntil: 'load' });
  // 全ページで使う文字を含む字形セットを確実に読み込ませる
  await page.evaluate(async () => {
    const txt = document.body.innerText;
    await document.fonts.load('400 16px "Noto Sans JP"', txt);
    await document.fonts.load('700 16px "Noto Sans JP"', txt);
    await document.fonts.ready;
  });
  await page.waitForTimeout(500);
  const res = await page.evaluate(() => {
    const out = [];
    const loaded = [...document.fonts].filter(f => f.family.replace(/["']/g,'') === 'Noto Sans JP' && f.status === 'loaded').length;
    if (!loaded) out.push('Noto Sans JP が1つも読み込まれていない');
    const pages = [...document.querySelectorAll('.page')];
    const CONT = '.card,.panel,.step,.box,.node,.bar>div,.pros>div,.ok,.note,.band,.tl-note,.tag,.badges span,.span,.page';
    pages.forEach((pg, i) => {
      const P = pg.getBoundingClientRect();
      const n = i + 1;
      // 1) ページ外にはみ出す要素
      pg.querySelectorAll('*').forEach(el => {
        const r = el.getBoundingClientRect();
        if (!r.width || !r.height) return;
        if (r.left < P.left - 0.5 || r.right > P.right + 0.5 || r.top < P.top - 0.5 || r.bottom > P.bottom + 0.5)
          out.push(`p${n}: ページ外 ${el.tagName}.${el.className}`);
      });
      // 2) 中身が箱より大きい（スクロールが発生する）要素
      pg.querySelectorAll('*').forEach(el => {
        if (el.closest('svg')) return;
        const cs = getComputedStyle(el);
        if (cs.display === 'inline') return;
        if (el.scrollHeight > el.clientHeight + 2 && el.clientHeight > 0) out.push(`p${n}: 縦にあふれ ${el.tagName}.${el.className} (${el.scrollHeight}>${el.clientHeight}) 「${el.innerText.slice(0,20)}」`);
        if (el.scrollWidth > el.clientWidth + 2 && el.clientWidth > 0) out.push(`p${n}: 横にあふれ ${el.tagName}.${el.className} (${el.scrollWidth}>${el.clientWidth}) 「${el.innerText.slice(0,20)}」`);
      });
      // 3) 文字の1行1行が、いちばん近い枠の内側に収まっているか
      const walker = document.createTreeWalker(pg, NodeFilter.SHOW_TEXT);
      let t;
      while ((t = walker.nextNode())) {
        if (!t.textContent.trim()) continue;
        const host = t.parentElement.closest(CONT);
        const H = host.getBoundingClientRect();
        const rg = document.createRange(); rg.selectNodeContents(t);
        for (const lr of rg.getClientRects()) {
          if (lr.left < H.left - 0.5 || lr.right > H.right + 0.5 || lr.top < H.top - 0.5 || lr.bottom > H.bottom + 0.5)
            out.push(`p${n}: 枠外の文字「${t.textContent.trim().slice(0,16)}」 in ${host.className}`);
        }
      }
      // 4) 本文がフッターに重ならない
      const body = pg.querySelector('.body'), foot = pg.querySelector('.foot');
      if (body && foot) {
        const B = body.getBoundingClientRect(), F = foot.getBoundingClientRect();
        let maxBottom = 0; body.querySelectorAll('*').forEach(el => { const r = el.getBoundingClientRect(); if (r.height) maxBottom = Math.max(maxBottom, r.bottom); });
        if (maxBottom > F.top - 2) out.push(`p${n}: 本文がフッターに近すぎる/重なる`);
      }
      // 4b) 枠の中の空白：上端・子要素の間・下端のいずれかに 22mm を超える空きがあれば不合格
      const MM = 96/25.4, LIMIT = 22*MM;
      pg.querySelectorAll('.card,.panel,.step,.opt,.stage,.points,.box,.list6').forEach(box => {
        const R = box.getBoundingClientRect(), cs = getComputedStyle(box);
        const top = R.top + parseFloat(cs.paddingTop) + parseFloat(cs.borderTopWidth);
        const bottom = R.bottom - parseFloat(cs.paddingBottom) - parseFloat(cs.borderBottomWidth);
        const kids = [...box.children].map(c => c.getBoundingClientRect()).filter(r => r.height > 0).sort((a,b)=>a.top-b.top);
        if (!kids.length) return;
        const gaps = [kids[0].top - top];
        let cur = kids[0].bottom;
        for (const k of kids.slice(1)) { gaps.push(k.top - cur); cur = Math.max(cur, k.bottom); }
        gaps.push(bottom - cur);
        const g = Math.max(...gaps);
        if (g > LIMIT) out.push(`p${n}: 枠の中に空白 ${(g/MM).toFixed(0)}mm ${box.className}「${box.innerText.trim().slice(0,14)}」`);
      });
      // 5) SVGの中の文字（原則使わない）
      pg.querySelectorAll('svg text').forEach(tx => out.push(`p${n}: SVG内に文字「${tx.textContent}」`));
    });
    // 6) 禁止語
    const all = document.body.innerText;
    ['網', 'ワンヒッター', '本舗', 'ベアーズ', '競業', '石田', '木村'].forEach(w => { if (all.includes(w)) out.push('禁止語: ' + w); });
    return { out, loaded, pages: pages.length };
  });
  problems.push(...res.out);
  await page.pdf({ path: OUT, width: '297mm', height: '210mm', printBackground: true, margin: { top: 0, right: 0, bottom: 0, left: 0 }, preferCSSPageSize: true });
  console.log(`ページ数 ${res.pages} ／ Noto Sans JP 読み込み済み ${res.loaded} 面`);
  console.log(problems.length ? '問題 ' + problems.length + '件:\n' + [...new Set(problems)].join('\n') : '検査：問題なし');
  await b.close();
  process.exit(problems.length ? 1 : 0);
})();
