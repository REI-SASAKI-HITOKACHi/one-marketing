#!/usr/bin/env python3
"""予約ページに「エアコンの型番シールの写真（任意）」の欄を足す下書き（依頼 20261029-01-lp・urakata の提案 #2）。

    python3 tools/kataban-1029.py      # deploy/machi/kataban/booking/index.html を作る（配信しない）

ねらい：お掃除機能付きかどうかの申告違いを減らす（伺う前に型番で確かめる）。
- 必須にしない。エアコンを選んだときだけ、「ご連絡先」の画面のご要望の下に1つ出す
- 写真は送る前に端末の中で長辺1600px・JPEG に縮める（Netlify のフォームの保存容量を食いすぎないため）
- 写真が無いときの送り方は今までどおり（urlencoded）。写真があるときだけ FormData（multipart）で同じ "/" に送る
  （Netlify Forms はファイル項目を受け付ける。控えのフォームに同じ name の file 欄を置く）
- 標準のファイル欄は見えなくして「写真を撮る・選ぶ」のボタンにする（端末の言語で見た目が変わらないように）
- 確認の画面に「型番シールの写真：あり」の行を出す
元にするのは本番と同じ予約ページ（cmo ブランチの lp/booking/index.html。防カビ無料の入った版）。
"""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC_REF = "origin/claude/one-hitter-cmo-strategy-5qk4ux:lp/booking/index.html"
OUT = ROOT / "deploy" / "machi" / "kataban" / "booking" / "index.html"
FIELD = "エアコンの型番シール"
MARK = 'id="kataban-box"'

EDITS = [
    # 画面：ご要望の下に1つ（エアコンを選んだときだけ出す）
    ('''        <textarea id="f-note" placeholder="例）駐車場はありません／2階のエアコンです／前回と同じ場所です"></textarea>''',
     None),  # 位置の確認だけ（下の HTML_AFTER_NOTE で後ろに足す）
    # 日時→連絡先へ進むときに、エアコンを選んでいれば欄を出す
    ("    $('yk-box').hidden = !(state.qty['浴室クリーニング'] > 0);\n    go(3);",
     "    $('yk-box').hidden = !(state.qty['浴室クリーニング'] > 0);\n"
     "    $('kataban-box').hidden = !katabanAircon();\n    go(3);"),
    # 確認の画面
    ("      ['ご住所', $('f-addr').value.trim()],\n",
     "      ['ご住所', $('f-addr').value.trim()],\n"),
    ("    var note = $('f-note').value.trim();\n    if (note) { rows.push(['ご要望', note]); }\n",
     "    var note = $('f-note').value.trim();\n    if (note) { rows.push(['ご要望', note]); }\n"
     "    if (katabanFile()) { rows.push(['型番シールの写真', 'あり（1枚）']); }\n"),
    # 送信：写真があるときだけ FormData
    ("    fetch('/', {\n      method: 'POST',\n      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },\n      body: body,\n    }).then(function(r){",
     "    katabanBody(atai, body).then(function(req){ return fetch('/', req); }).then(function(r){"),
    # 控えのフォーム（Netlify が項目を見つける）
    ('  <input type="text" name="空き枠の取得時刻">',
     '  <input type="text" name="空き枠の取得時刻">\n  <input type="file" name="' + FIELD + '">'),
]

HTML_AFTER_NOTE = (
    '      <div class="field" id="kataban-box" hidden>\n'
    '        <label>エアコンの型番シールの写真（任意）</label>\n'
    '        <input id="f-kataban" type="file" accept="image/*" style="position:absolute;width:1px;height:1px;opacity:0;overflow:hidden;">\n'
    '        <label for="f-kataban" class="btn ghost sm" style="display:inline-block;cursor:pointer;">写真を撮る・選ぶ</label>\n'
    '        <span id="kataban-na" style="margin-left:8px;font-size:13px;"></span>\n'
    '        <span class="hint">室内機の横か下に貼ってあるシールです。お掃除機能付きかどうかを、伺う前に確かめるために使います。</span>\n'
    '      </div>\n')

JS = """
  /* 型番シールの写真（任意・tools/kataban-1029.py）。エアコンを選んだときだけ欄を出す */
  function katabanAircon(){
    return ['エアコンクリーニング（ノーマル）', 'エアコンクリーニング（お掃除機能付き）'].some(function(n){ return (state.qty[n] || 0) > 0; });
  }
  function katabanFile(){
    var el = $('f-kataban');
    return (el && katabanAircon() && el.files && el.files[0]) ? el.files[0] : null;
  }
  if ($('f-kataban')) {
    $('f-kataban').addEventListener('change', function(){ $('kataban-na').textContent = this.files && this.files[0] ? '選びました（1枚）' : ''; });
  }
  /* 長辺1600px・JPEG に縮める。縮められない端末では元のまま送る */
  function katabanChijimeru(f){
    return new Promise(function(res){
      try {
        var url = URL.createObjectURL(f), img = new Image();
        img.onload = function(){
          var s = Math.min(1, 1600 / Math.max(img.width, img.height));
          var c = document.createElement('canvas');
          c.width = Math.round(img.width * s); c.height = Math.round(img.height * s);
          c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
          URL.revokeObjectURL(url);
          c.toBlob(function(b){ res(b ? new File([b], 'kataban.jpg', { type: 'image/jpeg' }) : f); }, 'image/jpeg', 0.82);
        };
        img.onerror = function(){ URL.revokeObjectURL(url); res(f); };
        img.src = url;
      } catch (e) { res(f); }
    });
  }
  /* 写真が無ければ今までどおり urlencoded。あるときだけ FormData */
  function katabanBody(atai, body){
    var f = katabanFile();
    if (!f) {
      return Promise.resolve({ method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, body: body });
    }
    return katabanChijimeru(f).then(function(g){
      var fd = new FormData();
      Object.keys(atai).forEach(function(kk){ fd.append(kk, atai[kk]); });
      fd.append('""" + FIELD + """', g, 'kataban.jpg');
      return { method: 'POST', body: fd };
    });
  }
"""


def kaeru(s, old, new):
    n = s.count(old)
    if n != 1:
        sys.exit(f"想定と違う：{old[:60]!r} が {n} か所（1 か所のはず）。予約ページが変わった可能性。止めます")
    return s.replace(old, new) if new is not None else s


def make(h):
    if MARK in h:
        return h
    for a, b in EDITS:
        h = kaeru(h, a, b)
    # ご要望の field の閉じ（</div>）の後ろに欄を足す
    i = h.find('<textarea id="f-note"')
    j = h.find("      </div>\n", i) + len("      </div>\n")
    h = h[:j] + HTML_AFTER_NOTE + h[j:]
    # JS は送信の前（var okuttechuu の直前）に置く
    h = kaeru(h, "  var okuttechuu = false;\n", JS + "\n  var okuttechuu = false;\n")
    return h


def main():
    src = subprocess.run(["git", "-C", str(ROOT), "show", SRC_REF], capture_output=True, text=True, check=True).stdout
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(make(src), encoding="utf-8")
    print(f"書き出しました: {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
