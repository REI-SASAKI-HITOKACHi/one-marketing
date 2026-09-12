// お客様が開くページが、端末のダークモードでも白地のままかを実測する。
//
//   node tools/check-darkmode.js [URL ...]      引数なしなら既定の一覧を全部見る
//
// なぜ grep ではなく実測なのか（2026-09-12）：
//   オーナーから「スマホで開くと背景がグレー」と指摘が出て、掲示板では
//   lp/survey/index.html が原因だと共有された。しかし実際に測ると survey は白地で、
//   暗かったのは読本（dokuhon）と無料点検（tenken）だった。
//   HTMLを grep すると「どのブランチの版を見ているか」で結論が変わる。
//   本番のURLをダークモードのブラウザで開いて算出値を見るのが確実。
//
// 決まり：お客様が開くページにダークモード対応を入れない。常に白地（README 4.8.2）。
//
// 終了コード 0＝全部白地／1＝暗いページがある／2＝1本も取得できなかった

let chromium;
for (const p of ['playwright', '/tmp/claude-0/node_modules/playwright',
                 '/opt/node22/lib/node_modules/playwright']) {
  try { ({ chromium } = require(p)); break; } catch (e) { /* 次を試す */ }
}
if (!chromium) {
  console.error('playwright が見つかりません。npm i playwright するか、パスを足してください。');
  process.exit(2);
}

const KITEI = [
  ['survey',     'https://one-hitter-lp.netlify.app/survey/'],
  ['aircon',     'https://one-hitter-lp.netlify.app/aircon/'],
  ['aircon-b',   'https://one-hitter-lp.netlify.app/aircon-b/'],
  ['mizumawari', 'https://one-hitter-lp.netlify.app/mizumawari/'],
  ['nenmatsu',   'https://one-hitter-lp.netlify.app/nenmatsu/'],
  ['yoyaku',     'https://yoyaku.onehitter.jp/'],
  ['dokuhon',    'https://one-hitter-dokuhon.netlify.app/'],
  ['tenken',     'https://one-hitter-tenken.netlify.app/'],
];

const args = process.argv.slice(2);
const TARGETS = args.length
  ? args.map(u => [new URL(u).hostname.split('.')[0], u])
  : KITEI;

(async () => {
  const b = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium', headless: true,
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--ssl-version-max=tls1.2', '--disable-quic'],
    proxy: process.env.HTTPS_PROXY ? { server: process.env.HTTPS_PROXY } : undefined,
  });
  // 端末のダークモードON・スマホ幅。オーナーが見ているのと同じ条件
  const ctx = await b.newContext({ colorScheme: 'dark', viewport: { width: 390, height: 844 } });
  const p = await ctx.newPage();
  p.setDefaultTimeout(60000);

  let kurai = 0, toreta = 0;
  console.log('端末のダークモードON・幅390pxで実測\n');
  console.log('page        body背景                 文字色                  判定');
  for (const [name, u] of TARGETS) {
    try {
      await p.goto(u, { waitUntil: 'load' });
      await p.waitForTimeout(1200);
      const r = await p.evaluate(() => {
        const cs = getComputedStyle(document.body);
        const html = getComputedStyle(document.documentElement);
        const bg = cs.backgroundColor !== 'rgba(0, 0, 0, 0)' ? cs.backgroundColor : html.backgroundColor;
        return { bg, fg: cs.color };
      });
      toreta++;
      const m = (r.bg.match(/\d+/g) || [255, 255, 255]).map(Number);
      // 明度（ITU-R BT.601）。200より明るければ白地とみなす
      const akarui = (m[0] * 0.299 + m[1] * 0.587 + m[2] * 0.114) > 200;
      if (!akarui) kurai++;
      console.log(`${name.padEnd(11)} ${r.bg.padEnd(24)} ${r.fg.padEnd(23)} ${akarui ? '白地 ✅' : '★暗い ⚠'}`);
    } catch (e) {
      console.log(`${name.padEnd(11)} 取得失敗 ${e.message.slice(0, 60)}`);
    }
  }
  await b.close();
  if (!toreta) { console.log('\n1本も取得できませんでした。'); process.exit(2); }
  if (kurai) {
    console.log(`\n★ ${kurai}本が暗いままです。`);
    console.log('  @media (prefers-color-scheme: dark) と [data-theme="dark"] のブロックを消し、');
    console.log('  :root に color-scheme:light を入れてください。');
    process.exit(1);
  }
  console.log('\nすべて白地です。');
})();
