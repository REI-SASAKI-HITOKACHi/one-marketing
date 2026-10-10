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
  // 2026-10-11：所要の長い枠（480分など）は Apps Script が14秒ほどかかり、7秒×2回の待ちでは毎回あきらめて
  // 控え（10/9 18時のまま）を返していた。関数の持ち時間（約10秒）に収まるよう、1回だけ9秒まで待つ。
  // 取れなかった所要時間だけ控えで埋める（下の handler）。
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), 9000);
  try {
    const r = await fetch(`${API}?action=slots&minutes=${minutes}`, { redirect: "follow", signal: ctl.signal });
    const body = await r.text();
    const m = body.match(/^\s*\w+\(([\s\S]*)\);?\s*$/);
    const d = JSON.parse(m ? m[1] : body);
    if (!d.ok || !Array.isArray(d.slots)) throw new Error(d.error || "ok:false");
    return d.slots;
  } finally {
    clearTimeout(t);
  }
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
  const host = (event && event.headers && (event.headers.host || event.headers.Host)) || "yoyaku.onehitter.jp";
  const kekka = await Promise.allSettled(BUCKETS.map((m) => kiku(m)));
  const ok = kekka.filter((k) => k.status === "fulfilled").length;
  const t = jst();
  if (ok === BUCKETS.length) {
    const buckets = {};
    BUCKETS.forEach((m, i) => { buckets[String(m)] = kekka[i].value; });
    return json(200, { generated: t.iso, generatedLabel: t.label, staleHours: 6, source: "apps-script-live", buckets },
      { "Netlify-CDN-Cache-Control": "public, durable, s-maxage=600, stale-while-revalidate=86400" });
  }
  // 一部だけ取れなかった：取れた所要時間は今の答え、取れなかった所要時間だけ控えで埋める（CDN には短く置く）
  try {
    const r = await fetch(`https://${host}/slots-hikae.json`);
    const d = await r.json();
    if (ok === 0) {
      d.source = "hikae";
      return json(200, d, { "Netlify-CDN-Cache-Control": "no-store" });
    }
    const buckets = {}, kake = [];
    BUCKETS.forEach((m, i) => {
      if (kekka[i].status === "fulfilled") { buckets[String(m)] = kekka[i].value; }
      else { buckets[String(m)] = (d.buckets || {})[String(m)] || []; kake.push(m); }
    });
    return json(200, { generated: t.iso, generatedLabel: t.label, staleHours: 6, source: "apps-script-partial", hikaeBuckets: kake,
      hikaeGenerated: d.generated, buckets }, { "Netlify-CDN-Cache-Control": "public, durable, s-maxage=120, stale-while-revalidate=600" });
  } catch (e2) {
    return json(502, { error: String(e2 && e2.message) }, { "Netlify-CDN-Cache-Control": "no-store" });
  }
};
