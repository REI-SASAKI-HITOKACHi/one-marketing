// ONE HITTER ／ LP計測スクリプト
//
// このファイルは tools/build-site.py が各LPの本文の末尾に埋め込む。
// 設定（測定IDなど）は tracking/measurement.json から window.OH_M として渡される。
//
// 設計の意図：
//   - IDが1つも設定されていなくても、エラーを出さずに黙って何もしない。
//     先にこの仕組みだけ入れておき、GA4の準備ができた時点で設定ファイルを
//     書き換えて再ビルドすれば、LPの本文には一切触れずに計測が始まる。
//   - GA4・Google広告・Metaの3つに、同じ1つの send() から配る。
//     どこに何を送っているかを1箇所で読めるようにするため。
//   - イベント名とパラメータの定義は docs/measurement-spec.md が正。
//     このファイルを直すときは、あちらも必ず直すこと。

(function () {
  var M = window.OH_M || {};
  var PAGE = M.page || {};
  var LOG = !!M.debug;

  function log() {
    if (LOG && window.console) console.log.apply(console, ['[OH計測]'].concat([].slice.call(arguments)));
  }

  // ---------------------------------------------------------------
  // 送信口。GA4 → Google広告 → Meta の順に配る。
  // ---------------------------------------------------------------

  // Google広告のコンバージョンを送るイベントと、そのラベルの対応
  var ADS_LABEL = (M.google_ads && M.google_ads.labels) || {};
  var ADS_ID = (M.google_ads && M.google_ads.conversion_id) || '';

  // Metaの標準イベント名への読み替え
  var META_MAP = { generate_lead: 'Lead', phone_click: 'Contact', line_click: 'Contact' };

  // 流入元（?src= / ?cid=）。QR・SMS・施設カードなど、どこから来たかの目印。
  // head 側の gtag('config') にも同じ値を載せてあるので page_view にも付くが、
  // 個々のイベントにも付けておくと、GA4で「この施設からの電話クリック」まで割れる。
  var Q = null;
  try { Q = new URLSearchParams(location.search); } catch (e) { Q = null; }
  var SRC = (Q && Q.get('src')) || 'direct';
  var CID = (Q && Q.get('cid')) || '';

  function send(name, params) {
    var p = params || {};
    // どのLPのどのパターンかは、全イベントに必ず付ける
    p.lp_id = PAGE.lp_id;
    p.lp_variant = PAGE.lp_variant;
    p.page_kind = PAGE.kind;
    p.traffic_src = SRC;
    if (CID) p.traffic_cid = CID;

    log(name, p);

    if (typeof window.gtag === 'function') {
      window.gtag('event', name, p);

      var label = ADS_LABEL[name];
      if (ADS_ID && label) {
        var cv = { send_to: ADS_ID + '/' + label };
        if (p.value) { cv.value = p.value; cv.currency = 'JPY'; }
        window.gtag('event', 'conversion', cv);
        log('→ Google広告のコンバージョン', cv.send_to);
      }
    }

    if (typeof window.fbq === 'function') {
      var meta = META_MAP[name];
      if (meta) window.fbq('track', meta, p.value ? { value: p.value, currency: 'JPY' } : {});
      else window.fbq('trackCustom', name, p);
    }
  }

  // ---------------------------------------------------------------
  // クリックされた場所の名前を決める。
  // 同じ「電話」でも、ヘッダーと追従バーとフォーム下では意味が違うため。
  // ---------------------------------------------------------------
  var PLACES = [
    ['.sticky', 'sticky'],       // 画面下に追従するバー
    ['.bar', 'header'],          // 上部のヘッダー
    ['.hero', 'hero'],           // ファーストビュー
    ['#form', 'form'],           // 予約フォームの節
    ['.calc', 'estimate'],       // 料金シミュレーター（案A）
    ['#builder', 'estimate'],    // 料金シミュレーター（案B）
    ['footer', 'footer']
  ];

  function placeOf(el) {
    for (var node = el; node && node !== document.body; node = node.parentElement) {
      for (var i = 0; i < PLACES.length; i++) {
        var sel = PLACES[i][0];
        var hit = sel.charAt(0) === '#' ? node.id === sel.slice(1)
                : sel.charAt(0) === '.' ? node.classList && node.classList.contains(sel.slice(1))
                : node.tagName && node.tagName.toLowerCase() === sel;
        if (hit) return PLACES[i][1];
      }
    }
    return PAGE.kind === 'thanks' ? 'thanks' : 'other';
  }

  // ---------------------------------------------------------------
  // 1. リンクのクリック（電話・LINE・フォームへの誘導）
  // ---------------------------------------------------------------
  document.addEventListener('click', function (ev) {
    var a = ev.target.closest ? ev.target.closest('a[href]') : null;
    if (!a) return;
    var href = a.getAttribute('href') || '';

    if (href.indexOf('tel:') === 0) {
      send('phone_click', { link_position: placeOf(a), phone_number: href.slice(4) });
    } else if (href.indexOf('lin.ee') > -1 || href.indexOf('line.me') > -1) {
      // アンケートのLINEリンクは「友だちに紹介文を送る」ボタンで、
      // LPの「公式アカウントを友だち追加」とは意味が違う。
      // line_click は成果（キーイベント）に指定するので、混ぜない。
      send(PAGE.kind === 'survey' ? 'refer_share' : 'line_click',
           { link_position: placeOf(a), share_to: 'line' });
    } else if (href.charAt(0) === '#' && href.length > 1) {
      send('cta_click', { link_position: placeOf(a), link_target: href });
    }
  }, true);

  // ---------------------------------------------------------------
  // 2. 料金シミュレーターを触ったか（1ページにつき1回だけ）
  // ---------------------------------------------------------------
  var estimateSent = false;
  var estimateBox = document.querySelector('.calc') || document.getElementById('builder');
  if (estimateBox) {
    estimateBox.addEventListener('change', function () {
      if (estimateSent) return;
      estimateSent = true;
      send('estimate_use', {});
    });
  }

  // 見積り合計の読み取り。「10,780円」→ 10780
  //
  // 数字を全部つなげてはいけない。予約フォームの金額欄には
  // 「（1箇所）¥10,780 ／ 概算合計（税込）¥10,780」のように複数の数字が並ぶので、
  // 素朴に非数字を落とすと 11078010780 という桁外れの値になる。実際にそうなった。
  // 合計の行（.sum）があればそこを見て、無ければ最後に出てくる金額を合計とみなす。
  function readYen(el) {
    if (!el) return 0;
    var target = el;
    if (el.querySelector) target = el.querySelector('.sum .v') || el.querySelector('.sum') || el;
    var hit = (target.textContent || '').match(/[0-9][0-9,]*/g);
    if (!hit || !hit.length) return 0;
    var n = parseInt(hit[hit.length - 1].replace(/,/g, ''), 10);
    return isNaN(n) ? 0 : n;
  }

  function estimateTotal() {
    return readYen(document.getElementById('total'));
  }

  // ---------------------------------------------------------------
  // 3. エリア判定ボタン（対応エリアかどうかの結果まで記録する）
  // ---------------------------------------------------------------
  var zipbtn = document.getElementById('zipbtn');
  if (zipbtn) {
    zipbtn.addEventListener('click', function () {
      // 判定結果はクリック直後に #zipres へ書き込まれるので、1周待ってから読む
      setTimeout(function () {
        var res = document.getElementById('zipres');
        var cls = res ? res.className : '';
        send('area_check', {
          area_result: cls === 'ok' ? 'in_area' : cls === 'ng' ? 'out_of_area' : 'invalid'
        });
      }, 0);
    });
  }

  // ---------------------------------------------------------------
  // 4. 予約フォーム（入力開始と送信）
  // ---------------------------------------------------------------
  var form = document.querySelector('form.form');
  if (form) {
    var startSent = false;
    form.addEventListener('focusin', function () {
      if (startSent) return;
      startSent = true;
      send('form_start', {});
    });

    form.addEventListener('submit', function () {
      var total = estimateTotal();
      // サンクスページで金額を使えるように渡す。読んだら消す。
      try {
        sessionStorage.setItem('oh_estimate', String(total));
        sessionStorage.setItem('oh_lp', String(PAGE.lp_id || ''));
        sessionStorage.setItem('oh_variant', String(PAGE.lp_variant || ''));
      } catch (e) { /* プライベートモード等で保存できなくても続行する */ }
      // 送信ボタンを押した時点の記録。成果として数えるのはサンクスページの
      // generate_lead のほうで、こちらは離脱の分析にだけ使う。
      send('form_submit', { estimate_total: total });
    });
  }

  // ---------------------------------------------------------------
  // 5. サンクスページ ＝ 成果（generate_lead）
  //    Netlify Forms が受理した後にしか表示されないので、
  //    ここで数えれば「送信ボタンを押しただけ」の水増しが起きない。
  // ---------------------------------------------------------------
  if (PAGE.kind === 'thanks') {
    var value = PAGE.lead_value || 0;
    var stored = 0;
    try {
      stored = parseInt(sessionStorage.getItem('oh_estimate') || '0', 10) || 0;
      if (!PAGE.lp_id) {
        PAGE.lp_id = sessionStorage.getItem('oh_lp') || PAGE.lp_id;
        PAGE.lp_variant = sessionStorage.getItem('oh_variant') || PAGE.lp_variant;
      }
      sessionStorage.removeItem('oh_estimate');
    } catch (e) { /* 読めなくても成果は数える */ }

    var lead = { estimate_total: stored };
    // 金額は「見積り額 → 設定値」の順に使う。どちらも無ければ送らない。
    if (stored > 0) { lead.value = stored; lead.currency = 'JPY'; }
    else if (value > 0) { lead.value = value; lead.currency = 'JPY'; }

    send('generate_lead', lead);
  }

  // ---------------------------------------------------------------
  // 5-b. アンケート（4問ずつ4画面のウィザード）
  //
  //   知りたいのは「QRを見た人のうち、何人が最後まで答えたか」と
  //   「どの画面で脱落したか」の2つ。ページ遷移が起きない作りなので、
  //   画面の出し入れ（hidden属性）を見張って段階を記録する。
  // ---------------------------------------------------------------
  if (PAGE.kind === 'survey') {
    var sForm = document.querySelector('form.survey-form');

    if (sForm) {
      var sStarted = false;
      sForm.addEventListener('focusin', function () {
        if (sStarted) return;
        sStarted = true;
        send('survey_start', {});
      });
      // ラジオ・チェックボックスはフォーカスを伴わない操作もあるので、変更も入口に含める
      sForm.addEventListener('change', function () {
        if (sStarted) return;
        sStarted = true;
        send('survey_start', {});
      });
    }

    // 進んだ画面の記録。戻って進み直しても二重に数えない
    var seenStep = {};
    function noteStep(n) {
      if (!n || seenStep[n]) return;
      seenStep[n] = true;
      send('survey_step', { step_number: parseInt(n, 10) });
    }

    var doneSent = false;
    function watch() {
      document.querySelectorAll('.step[data-step]').forEach(function (el) {
        if (!el.hidden) noteStep(el.getAttribute('data-step'));
      });
      var done = document.getElementById('done');
      if (done && !done.hidden && !doneSent) {
        doneSent = true;
        // ここは送信が終わってから出る画面なので、回答完了として数えてよい
        send('survey_complete', {});
      }
    }

    if (window.MutationObserver) {
      var mo = new MutationObserver(watch);
      document.querySelectorAll('.step[data-step]').forEach(function (el) {
        mo.observe(el, { attributes: true, attributeFilter: ['hidden'] });
      });
      var doneEl = document.getElementById('done');
      if (doneEl) mo.observe(doneEl, { attributes: true, attributeFilter: ['hidden'] });
    }
    watch();   // 最初の画面の分

    // 完了画面のボタン。クチコミと紹介は、ここが唯一の観測点になる
    var BUTTONS = {
      'copy-review': 'review_copy',      // クチコミ下書きをコピー
      'copy-refer': 'refer_copy',        // 紹介文をコピー
      'priv-send': 'private_send'        // 非公開のご意見を送る
    };
    Object.keys(BUTTONS).forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.addEventListener('click', function () { send(BUTTONS[id], {}); });
    });

    var glink = document.getElementById('google-link');
    if (glink) {
      glink.addEventListener('click', function () {
        // Googleのクチコミ投稿画面へ送り出した回数。実際に投稿されたかは分からない
        send('google_review_click', {});
      });
    }
  }

  // ---------------------------------------------------------------
  // 5-c. Web予約フォーム（4画面のウィザード。ページ遷移が起きない）
  //
  //   知りたいのは「SMSのリンクを開いた人のうち、何人が予約したか」。
  //   送信そのものは Netlify Forms に「流入元」として記録されているので、
  //   ここで足すのは分母（開いた人）と、どの画面で脱落したか。
  // ---------------------------------------------------------------
  if (PAGE.kind === 'booking') {
    var bStarted = false;
    function bStart() {
      if (bStarted) return;
      bStarted = true;
      send('booking_start', {});
    }
    // 入口は3つとも見る。ボタン式の選択肢は focus も change も伴わないことがある
    document.addEventListener('focusin', bStart);
    document.addEventListener('change', bStart);
    document.addEventListener('click', bStart);

    var bSeen = {};
    var bSteps = ['s1', 's2', 's3', 's4'];

    // 送信ボタンを押した時点の概算金額を控えておく。
    // 完了画面では金額の欄が隠れるので、押した瞬間に読む。
    var bTotal = 0;
    var sendBtn = document.getElementById('send');
    if (sendBtn) {
      sendBtn.addEventListener('click', function () {
        var n = readYen(document.getElementById('total'));
        if (n > 0) bTotal = n;
        send('booking_submit', { estimate_total: bTotal });
      });
    }

    var bDone = false;
    function bWatch() {
      for (var i = 0; i < bSteps.length; i++) {
        var el = document.getElementById(bSteps[i]);
        if (el && !el.hidden && !bSeen[bSteps[i]]) {
          bSeen[bSteps[i]] = true;
          send('booking_step', { step_number: i + 1 });
        }
      }
      var done = document.getElementById('done');
      if (done && !done.hidden && !bDone) {
        bDone = true;
        // ここは送信が受理されてから出る画面。予約1件として数えてよい。
        var lead = { estimate_total: bTotal };
        if (bTotal > 0) { lead.value = bTotal; lead.currency = 'JPY'; }
        send('generate_lead', lead);
      }
    }

    if (window.MutationObserver) {
      var bmo = new MutationObserver(bWatch);
      bSteps.concat(['done']).forEach(function (id) {
        var el = document.getElementById(id);
        if (el) bmo.observe(el, { attributes: true, attributeFilter: ['hidden'] });
      });
    }
    bWatch();   // 最初の画面の分
  }

  // ---------------------------------------------------------------
  // 6. どこまで読まれたか（25 / 50 / 75 / 90%）
  //    GA4の拡張計測にも90%のスクロールはあるが、あちらは1段階しかない。
  //    どの節で離脱しているかを見たいので、自前で4段階を送る。
  // ---------------------------------------------------------------
  if (PAGE.kind === 'lp') {
    var marks = [25, 50, 75, 90];
    var done = {};
    var ticking = false;

    function checkScroll() {
      ticking = false;
      var h = document.documentElement.scrollHeight - window.innerHeight;
      if (h <= 0) return;
      var pct = (window.pageYOffset / h) * 100;
      for (var i = 0; i < marks.length; i++) {
        var m = marks[i];
        if (pct >= m && !done[m]) {
          done[m] = true;
          send('scroll_depth', { percent_scrolled: m });
        }
      }
    }

    window.addEventListener('scroll', function () {
      if (ticking) return;
      ticking = true;
      window.requestAnimationFrame(checkScroll);
    }, { passive: true });
  }

  log('計測スクリプト読み込み完了', PAGE, 'gtag=' + (typeof window.gtag === 'function'));
})();
