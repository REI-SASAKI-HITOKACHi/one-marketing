#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""社内フォーム（作業完了・受注）へのリンクを短くする。2026-10-26 オーナー指示（LINE 494）：
「CMO、LINEに送るURLは短縮化して送るようにして」

これまでのリンクは、お客様の名前・メニュー・未入力の一覧などを # のうしろに丸ごと入れていた
（# のうしろはサーバへ送られない設計）。一覧が長いと 5,000字を超え、LINE で切れて開けなかった（10/26）。

短縮の仕組み（中身はサーバに平文で置かない）：
  1. 元の # のうしろ（文字列）を AES-128-GCM（Node.js で）暗号化し、社内ホストの /k/<id>.json に置く
  2. LINE に送るのは  https://<社内ホスト>/kanryo/#k=<id>.<鍵>  だけ（約80字）
  3. ページの先頭の小さな読み込み役（LOADER）が /k/<id>.json を取り、# の鍵で復号して、
     元の # に置き換えて読み直す。鍵は # のうしろなのでサーバへ送られない
  - 外部の短縮サービス（bit.ly 等）は使わない：元のURL（お客様の名前・電話・住所入り）を他社に預けることになる
  - /k/ の古いファイルは 21日で消す（make() のたびに掃除）。配信は deploy-juchu.py（社内ホストまるごと）

使い方（道具から）：
  import tanshuku
  u = tanshuku.make(長いURL)        # 短いURLを返す。暗号化できないときは長いURLのまま返す
  tanshuku.haishin()                 # 新しく作った /k/ を社内ホストに配信（送る前に1回）
"""
import base64
import datetime
import json
import os
import pathlib
import secrets
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
KDIR = ROOT / "lp" / "naibu-sms" / "k"     # 社内ホストの /k/（deploy-juchu.py がルートに置くフォルダ）
HOZON_NICHI = 21
_atarashii = []

# ページ側の読み込み役。build-kanryo.py と build-juchu.py が <script> のいちばん前に入れる
LOADER = r"""<script>
/* 短縮リンク #k=<id>.<鍵> を元の # に戻して読み直す（tools/tanshuku.py） */
(function(){
  var m = /^#k=([A-Za-z0-9_-]+)\.([A-Za-z0-9_-]+)$/.exec(location.hash || '');
  if (!m || !window.crypto || !crypto.subtle) { return; }
  document.documentElement.style.visibility = 'hidden';
  function b64(s){ s = s.replace(/-/g,'+').replace(/_/g,'/'); while (s.length % 4) { s += '='; }
    var b = atob(s), u = new Uint8Array(b.length); for (var i = 0; i < b.length; i++) { u[i] = b.charCodeAt(i); } return u; }
  fetch('/k/' + m[1] + '.json', {cache: 'no-store'}).then(function(r){ if (!r.ok) { throw new Error(r.status); } return r.json(); })
    .then(function(d){ return crypto.subtle.importKey('raw', b64(m[2]), 'AES-GCM', false, ['decrypt'])
      .then(function(k){ return crypto.subtle.decrypt({name: 'AES-GCM', iv: b64(d.iv)}, k, b64(d.ct)); }); })
    .then(function(buf){ history.replaceState(null, '', location.pathname + location.search + '#' + new TextDecoder().decode(buf)); location.reload(); })
    .catch(function(){ document.documentElement.style.visibility = '';
      alert('リンクの期限が切れているか、読み込めませんでした。CMO に新しいリンクを頼んでください。'); });
})();
</script>
"""


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def souji():
    """21日より古い /k/ を消す。"""
    if not KDIR.exists():
        return
    genkai = datetime.datetime.now() - datetime.timedelta(days=HOZON_NICHI)
    for f in KDIR.glob("*.json"):
        try:
            t = datetime.datetime.fromisoformat(json.loads(f.read_text(encoding="utf-8")).get("t", ""))
        except Exception:
            t = datetime.datetime.fromtimestamp(f.stat().st_mtime)
        if t < genkai:
            f.unlink()


def make(url: str) -> str:
    """長いURL（# つき）を短いURLにする。できなければ元のまま返す（送れないよりは長くても送る）。"""
    if "#" not in url:
        return url
    moto, frag = url.split("#", 1)
    # 暗号化は Node.js（AES-128-GCM・WebCrypto と同じ形＝暗号文の後ろに16バイトの認証タグ）。
    # 2026-10-26：この環境の Python の cryptography は壊れていて（_cffi_backend なし）、例外でなく異常終了したため使わない
    js = ("const c=require('crypto');let s='';process.stdin.on('data',d=>s+=d).on('end',()=>{"
          "const k=c.randomBytes(16),iv=c.randomBytes(12),x=c.createCipheriv('aes-128-gcm',k,iv);"
          "const ct=Buffer.concat([x.update(s,'utf8'),x.final(),x.getAuthTag()]);"
          "const b=v=>v.toString('base64url');process.stdout.write(JSON.stringify({k:b(k),iv:b(iv),ct:b(ct)}))})")
    try:
        r = subprocess.run(["node", "-e", js], input=frag, capture_output=True, text=True, timeout=30)
        enc = json.loads(r.stdout)
    except Exception as e:
        print(f"  ⚠ 短縮できません（暗号化に失敗）。長いリンクのまま送ります: {e}", file=sys.stderr)
        return url
    KDIR.mkdir(parents=True, exist_ok=True)
    souji()
    while True:
        kid = _b64(secrets.token_bytes(6))           # 8文字
        f = KDIR / f"{kid}.json"
        if not f.exists():
            break
    f.write_text(json.dumps({"v": 1, "t": datetime.datetime.now().isoformat(timespec="seconds"),
                             "iv": enc["iv"], "ct": enc["ct"]}) + "\n", encoding="utf-8")
    _atarashii.append(f)
    return f"{moto}#k={kid}.{enc['k']}"


def haishin(dry: bool = False) -> bool:
    """新しく作った /k/ があれば社内ホストを配信し直す。成功したら True。"""
    if not _atarashii or dry:
        return True
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "deploy-juchu.py")], capture_output=True, text=True, timeout=400)
    if r.returncode != 0:
        print(f"  ⚠ 短縮リンクの配信に失敗: {(r.stderr or r.stdout)[-300:]}", file=sys.stderr)
        return False
    _atarashii.clear()
    return True


def kakikae(texts):
    """本文の中の社内フォームへの長いリンクを短縮して配信する。配信に失敗したら元の本文を返す。"""
    import re
    pat = re.compile(r"https://oh-naibu-sms-k7q3x\.netlify\.app/[^\s#]*#[^\s]+")
    out = [pat.sub(lambda m: make(m.group(0)), t) for t in texts]
    if out == list(texts):
        return out
    return out if haishin() else list(texts)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(make(sys.argv[1]))
        print("配信:", haishin())
