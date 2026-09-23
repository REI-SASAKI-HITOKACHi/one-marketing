#!/usr/bin/env python3
"""Netlify にあるのに、セーフブラウジング監視の一覧に入っていないホストを見つける。

    python3 tools/check-hosts-more.py

## 何のためのものか

2026-09-12 の事故のあと、`tools/check-safebrowsing.py` で全ホストを毎時見る仕組みを作った。
**ところがこれは「その日に存在したホスト」の一覧を手で書いたものだった。**

2026-09-19 に立った図鑑（`araidoki.netlify.app`）は、**お客様が SNS・GBP から踏む公開ページ**なのに
**5日間、一覧から漏れていた**（`docs/org/README.md` 4.10.1「新しいホストは当日中に」に反した状態）。
気づいたのは人が読み合わせたからで、**仕組みは何も検出しなかった。**

このツールは、**Netlify にあるサイトの一覧を取りにいって、`HOSTS` と突き合わせる。**
人が思い出さなくても、新しいホストが漏れたら次の毎時ルーティンで出る。

トークンは `deploy-netlify.py` と同じ読み方（環境変数 NETLIFY_TOKEN、または
NETLIFY_TOKEN_FILE、または既定のパス）。**引数にも設定ファイルにも書かない。**
"""

import json
import re
import sys
import urllib.error
import urllib.request

sys.path.insert(0, __file__.rsplit("/", 1)[0])

import importlib.util


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ROOT = __file__.rsplit("/", 2)[0]
deploy = _load("deploy_netlify", f"{ROOT}/tools/deploy-netlify.py")

API = "https://api.netlify.com/api/v1"

# 2026-09-20 に中身を見て「ワンヒッターの公開ページではない」と確認したホスト。
# ここに入れておくと毎時の出力に出ない。**新しいものが出たら必ず中身を見て判断すること。**
# 判断がつかないものは、ここに入れずに出したままにする（出しっぱなしのほうが安全）。
MITA = {
    # 別プロジェクト（ワンヒッターの資産ではない。中身を確認済み）
    "kidsmoney-crm-2014997530.netlify.app",  # 「キッズマネースクール CRM」。当社の語が0件
    "inquirycounter.netlify.app",            # 当社の語が0件
    "inquisitive-duckanoo-36090d.netlify.app",  # 「Hitokachi Buddy」（ヒトカチ社。noindex の準備中ページ）。2026-09-23 に中身を確認

    # 既定名のまま放置されている休眠サイト（2025〜2026/05 が最終配信、または未配信）
    "adorable-brioche-5ac83d.netlify.app",
    "candid-puppy-cd84cf.netlify.app",
    "capable-profiterole-987361.netlify.app",
    "curious-figolla-262114.netlify.app",
    "eclectic-profiterole-a09869.netlify.app",
    "incomparable-cobbler-5c1752.netlify.app",
    "lustrous-frangollo-9a2170.netlify.app",
    "subtle-sable-a7e919.netlify.app",
    "vermillion-peony-b32ca6.netlify.app",
}


def shiranai_hosts():
    """check-safebrowsing.py の HOSTS を、実行せずに読み取る。"""
    src = open(f"{ROOT}/tools/check-safebrowsing.py", encoding="utf-8").read()
    m = re.search(r"^HOSTS\s*=\s*\[(.*?)^\]", src, re.S | re.M)
    if not m:
        sys.exit("check-safebrowsing.py の HOSTS を読み取れませんでした")
    return set(re.findall(r"['\"]([^'\"]+)['\"]", m.group(1)))


def netlify_sites(token):
    sites, page = [], 1
    while True:
        req = urllib.request.Request(f"{API}/sites?page={page}&per_page=100")
        req.add_header("Authorization", "Bearer " + token)
        with urllib.request.urlopen(req, timeout=120) as r:
            batch = json.load(r)
        if not batch:
            break
        sites += batch
        if len(batch) < 100:
            break
        page += 1
    return sites


def main():
    token = deploy.token()
    mite_iru = shiranai_hosts()
    sites = netlify_sites(token)

    more = []
    for s in sites:
        # そのサイトが持つ全ホスト名（netlify.app と、割り当てた独自ドメイン）
        na = [s.get("default_domain"), s.get("custom_domain")]
        na += s.get("domain_aliases") or []
        for h in [x for x in na if x]:
            if h not in mite_iru and h not in MITA:
                more.append((s.get("name", "?"), h, (s.get("published_deploy") or {}).get("published_at", "")))

    print(f"Netlify のサイト {len(sites)}件 ／ 監視中 {len(mite_iru)}件 ／ 確認済みで除外 {len(MITA)}件\n")
    if not more:
        print("✅ 漏れはありません。")
        return 0

    print(f"🔴 監視の一覧に入っていないホストが {len(more)}件 あります。\n")
    for name, host, at in sorted(more, key=lambda x: x[1]):
        print(f"  {host}")
        print(f"      サイト名: {name}   最終配信: {at or '（配信なし）'}")
    print(
        "\n※ お客様が踏むページなら、tools/check-safebrowsing.py の HOSTS に**今日中に**足すこと。"
        "\n   Search Console への登録も当日中（docs/org/README.md 4.10.1）。"
        "\n   使っていないサイトなら、Netlify 側で消すほうが早い。"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
