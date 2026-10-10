// 予約ページの空き枠（https://yoyaku.onehitter.jp/slots.json）を、本命の Apps Script から
// その場で取って返す Netlify Function。_redirects で /slots.json をここへつなぐ。
//
// 【なぜ】slots.json は以前、手元で作って配信する「控え」だった。作る工程が止まると古いまま残り、
//   2026-09-24〜10-09 の2週間、誰も気づかなかった。
//   オーナー 2026-10-09「常時自動更新されるようにリンクさせて」→ 配信をやめ、Apps Script に直結する。
// 【形】tools/slots-from-api.py と同じ JSON（generated / buckets[所要分] = [{date,label,times}]）。
//   ページ（lp/booking/index.html の loadSlots）は変えない。
// 【速さと落ちたとき】CDN に10分置き、裏で取り直す（stale-while-revalidate）。
//   Apps Script が全部取れないときは、手元の最後の写し（/slots-hikae.json）を返し、ページは「◯時点」と出す。
// BUCKETS は tools/build-slots.py の BUCKET と同じ値にすること。
const API = "https://script.google.com/macros/s/AKfycbzuuMGVICQPoLlUrFBarb1zAgi_kVdc1vDrRJoyhAJ_tvOG-eHnmTHDGWhuvix3E3_odQ/exec";
const BUCKETS = [60, 90, 120, 150, 180, 210, 240, 300, 360, 420, 480];

async function kiku(minutes) {
  let err;
  for (let i = 0; i < 2; i++) {
    try {
      const ctl = new AbortController();
      const t = setTimeout(() => ctl.abort(), 7000);
      const r = await fetch(`${API}?action=slots&minutes=${minutes}`, { redirect: "follow", signal: ctl.signal });
      clearTimeout(t);
      const body = await r.text();
      const m = body.match(/^\s*\w+\(([\s\S]*)\);?\s*$/);
      const d = JSON.parse(m ? m[1] : body);
      if (!d.ok || !Array.isArray(d.slots)) throw new Error(d.error || "ok:false");
      return d.slots;
    } catch (e) { err = e; }
  }
  throw new Error(`所要${minutes}分: ${err && err.message}`);
}

function jst() {
  const d = new Date(Date.now() + 9 * 3600 * 1000);
  const p = (n) => String(n).padStart(2, "0");
  return {
    iso: `${d.getUTCFullYear()}-${p(d.getUTCMonth() + 1)}-${p(d.getUTCDate())}T${p(d.getUTCHours())}:${p(d.getUTCMinutes())}+09:00`,
    label: `${d.getUTCMonth() + 1}月${d.getUTCDate()}日 ${p(d.getUTCHours())}:${p(d.getUTCMinutes())}`,
  };
}

exports.handler = async (event) => {
  const json = (code, obj, cache) => ({
    statusCode: code,
    // LP（lp.onehitter.jp）の「いちばん早い空き」がこの JSON を読む（2026-10-10 次のA/B・docs/LP-次のABテスト-2026-10.md）。
    // 中身は予約ページに出している空き枠と同じで、個人情報は入っていない。読めるのは自社LPのホストだけにする。
    headers: Object.assign({ "Content-Type": "application/json; charset=utf-8", "Cache-Control": "public, max-age=0, must-revalidate",
      "Access-Control-Allow-Origin": "https://lp.onehitter.jp" }, cache || {}),
    body: JSON.stringify(obj),
  });
  try {
    const kekka = await Promise.all(BUCKETS.map((m) => kiku(m)));
    const buckets = {};
    BUCKETS.forEach((m, i) => { buckets[String(m)] = kekka[i]; });
    const t = jst();
    return json(200, { generated: t.iso, generatedLabel: t.label, staleHours: 6, source: "apps-script-live", buckets },
      { "Netlify-CDN-Cache-Control": "public, durable, s-maxage=600, stale-while-revalidate=86400" });
  } catch (e) {
    // 取れないときは最後の写しを返す（CDN には置かない＝次の人でまた取り直す）
    try {
      const host = (event && event.headers && (event.headers.host || event.headers.Host)) || "yoyaku.onehitter.jp";
      const r = await fetch(`https://${host}/slots-hikae.json`);
      const d = await r.json();
      d.source = "hikae";
      return json(200, d, { "Netlify-CDN-Cache-Control": "no-store" });
    } catch (e2) {
      return json(502, { error: String(e && e.message) }, { "Netlify-CDN-Cache-Control": "no-store" });
    }
  }
};
