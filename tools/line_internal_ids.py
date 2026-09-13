#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""内部テスト用の宛先（嶺さん・和真さん）のLINEユーザーIDを、台帳から取って手元に控える。

## なぜこれが要るか

お客様に届くものは、必ず内部で1回受けてから出す（2026-09-11 CMO）。
そのために送り先のユーザーIDが要る。

**公式アカウントの友だち一覧（`/v2/bot/followers/ids`）からは取れない。**
返るのはIDの羅列だけで、誰のIDかを突き合わせるには429人ぶんのプロフィールを
引くことになる。それは個人情報の取りすぎなのでやらない。

代わりに **2026年台帳の `LINE_ログ` タブ**を使う。業務連絡グループのwebhookが、
発言者のユーザーIDをD列に残している（2026-09-13 CMOの案内）。

## ⚠️ 確かめること：内部グループと公式アカウントは別チャネル

LINEのユーザーIDは**プロバイダー単位**で一意。`LINE_ログ` は内部用アカウント
（嶺・和真・CMOの3人グループ）のwebhookが書いたもので、**公式アカウントとは別チャネル**。
同じプロバイダー配下なら同じIDだが、違えば別の値になる。

**だから保存する前に、公式アカウントのトークンで `/v2/bot/profile/{userId}` を引いて
有効かどうかを確かめる。** 404 が返るなら、そのIDは公式アカウントでは使えない。

## 使い方

    . ~/.config/one-hitter/line.env
    python3 tools/line_internal_ids.py 探す     # 台帳から候補を探し、公式アカウントで検証する
    python3 tools/line_internal_ids.py 控える   # 検証に通ったものを手元に保存する
    python3 tools/line_internal_ids.py 見る     # 控えの中身（IDは末尾4文字だけ表示）

控えは `~/.config/one-hitter/line-internal-ids.json`（**gitの外**・600）。
**ユーザーIDは個人情報。画面にも掲示板にもgitにも、全体を出さない。**
"""

import importlib.util
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HIKAE = os.path.expanduser("~/.config/one-hitter/line-internal-ids.json")
SS = "1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64"  # 2026年台帳
TAB = "LINE_ログ"

# 誰の発言かを見分ける手がかり（2026-09-13 CMOの案内）。表示名が空の行があるため本文で見る。
MEJIRUSHI = {
    "和真": ["開けた", "見当たらない"],
    "嶺": ["お詫びメールは実行しよう", "それでok"],
}


def mask(uid):
    """ユーザーIDは個人情報。末尾4文字だけ見せる。"""
    return f"...{uid[-4:]}" if uid and len(uid) > 4 else "(短すぎ)"


def sheets():
    spec = importlib.util.spec_from_file_location("sc", os.path.join(ROOT, "tools", "sheets_client.py"))
    sc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sc)
    return sc, sc.access_token(sc.load_credentials())


def daichou_kara():
    """LINE_ログ から {名前: (userId, 手がかりの数)} を返す。"""
    sc, tok = sheets()
    rng = urllib.parse.quote(f"{TAB}!A1:H500", safe="")
    v = sc.call(tok, f"/{SS}/values/{rng}").get("values", [])
    if not v:
        raise SystemExit(f"{TAB} タブが読めません")
    h = v[0]
    ix = {c: i for i, c in enumerate(h)}
    if "ユーザーID" not in ix:
        raise SystemExit(f"{TAB} に「ユーザーID」列がありません。列: {h}")

    def g(r, k):
        i = ix.get(k)
        return (r[i] if i is not None and i < len(r) else "").strip()

    mitsuketa = {}
    for r in v[1:]:
        uid, body = g(r, "ユーザーID"), g(r, "本文")
        if not uid:
            continue
        for namae, kotoba in MEJIRUSHI.items():
            atari = sum(1 for k in kotoba if k in body)
            if atari:
                cur = mitsuketa.get(namae)
                if cur is None:
                    mitsuketa[namae] = [uid, atari]
                elif cur[0] == uid:
                    cur[1] += atari
                else:
                    # 同じ手がかりで違うIDが出た。見分けが効いていない
                    mitsuketa[namae] = [None, -1]
    return {k: tuple(v) for k, v in mitsuketa.items()}


def line_profile(uid):
    """公式アカウントのトークンでプロフィールを引く。(表示名, None) か (None, 理由)。"""
    tok = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    if not tok:
        return None, "環境変数 LINE_CHANNEL_ACCESS_TOKEN が未設定"
    req = urllib.request.Request(
        f"https://api.line.me/v2/bot/profile/{urllib.parse.quote(uid)}",
        headers={"Authorization": "Bearer " + tok},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode()).get("displayName", "(表示名なし)"), None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code} {e.read().decode('utf-8','replace')[:120]}"
    except Exception as e:  # noqa: BLE001
        return None, f"{type(e).__name__}: {e}"


def cmd_sagasu(hozon=False):
    mitsuketa = daichou_kara()
    if not mitsuketa:
        print(f"{TAB} から手がかりに合う行が見つかりませんでした。")
        print("MEJIRUSHI の言葉が古いかもしれません。CMOに最新の手がかりを聞いてください。")
        return 1
    print(f"== {TAB} から候補を探す ==")
    tsuuka = {}
    for namae, (uid, atari) in sorted(mitsuketa.items()):
        if uid is None:
            print(f"  [NG] {namae}: 同じ手がかりで別のIDが出ました。見分けが効いていません")
            continue
        print(f"  {namae}: {mask(uid)}（手がかり {atari}件一致）")
        hyouji, err = line_profile(uid)
        if err:
            print(f"       [NG] 公式アカウントで引けません → {err}")
            print("            内部グループと公式アカウントはチャネルが別です。")
            print("            別プロバイダーならIDも別物なので、この値は使えません。")
            continue
        print(f"       [OK] 公式アカウントで有効。表示名「{hyouji}」")
        tsuuka[namae] = {"userId": uid, "displayName": hyouji}

    if not hozon:
        print("\n控えるには: python3 tools/line_internal_ids.py 控える")
        return 0 if tsuuka else 1
    if not tsuuka:
        print("\n検証に通ったものが無いので、控えません。")
        return 1
    os.makedirs(os.path.dirname(HIKAE), exist_ok=True)
    with open(HIKAE, "w", encoding="utf-8") as f:
        json.dump(tsuuka, f, ensure_ascii=False, indent=2)
    os.chmod(HIKAE, 0o600)
    print(f"\n控えました: {HIKAE}（gitの外・600）／{len(tsuuka)}名")
    return 0


def yomu():
    if not os.path.exists(HIKAE):
        return {}
    with open(HIKAE, encoding="utf-8") as f:
        return json.load(f)


def cmd_miru():
    d = yomu()
    if not d:
        print(f"控えがありません: {HIKAE}")
        print("先に: python3 tools/line_internal_ids.py 控える")
        return 1
    print(f"控え: {HIKAE}")
    for namae, v in d.items():
        print(f"  {namae}: {mask(v['userId'])}  表示名「{v.get('displayName','')}」")
    return 0


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "探す":
        return cmd_sagasu(hozon=False)
    if cmd == "控える":
        return cmd_sagasu(hozon=True)
    if cmd == "見る":
        return cmd_miru()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
