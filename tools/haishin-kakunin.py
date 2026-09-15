#!/usr/bin/env python3
"""配信の前後にやる確認を、1コマンドでまとめて流す。

    python3 tools/haishin-kakunin.py           # 配信前（手元のビルドを見る）
    python3 tools/haishin-kakunin.py --honban  # 配信後（本番のURLを見る）
    python3 tools/haishin-kakunin.py --zenbu   # 両方

## なぜ1本にまとめたか

確認する道具が5つに分かれていて、流す順番と引数を覚えていないと使えなかった。
**承認が出てから思い出していると、その分だけ広告の開始が遅れる**（2026-09-15 CMO）。

**「通った／通らない」を1つの終了コードで返す。** 0 なら配信してよい、1 なら止める。

## 何を流すか

| | 配信前 | 配信後 |
|---|---|---|
| `check-tracking.py netlify` … 計測の土台 | ○ | — |
| `check-public-page.py` … 運営者情報（セーフブラウジング対策） | ○ | ○ |
| `docs/LP配信のルール.md` の3項目 | ○ | ○ |
| `check-darkmode.js` … お客様のページが白地か | — | ○ |
| `measure-production.py` … 本番で計測が発火するか | — | ○ |

配信前に本番は見ない（まだ古いので当たり前に落ちる）。
配信後にビルドは見ない（もう本番が正）。**--zenbu は配信をまたいで流すとき用。**
"""
import pathlib
import re
import subprocess
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEPLOY = ROOT / "deploy" / "netlify"

# docs/LP配信のルール.md の3項目。どのスレッドが配信しても守られていること。
# ★正規表現で見る。文書には "color-scheme: light" と空白つきで書いてあるが、
#   ビルドすると最小化されて "color-scheme:light" になる。
#   文字列の完全一致で見ると、正しいのに落ちる（実際に落ちた 2026-09-15）。
RULE_ARU = [
    ("ライト固定", r"color-scheme\s*:\s*light"),
    ("流入元の記録（src）", r'name\s*=\s*"src"'),
    ("流入元の記録（cid）", r'name\s*=\s*"cid"'),
]
RULE_NAI = [("ダーク配色が復活していないこと", r"prefers-color-scheme")]

PAGES = ["aircon", "aircon-b", "mizumawari", "nenmatsu", "survey"]
HONBAN = "https://lp.onehitter.jp"


def midashi(s):
    print(f"\n{'=' * 60}\n{s}\n{'=' * 60}")


def hashiru(setsumei, cmd):
    """外の道具を1つ流す。戻り値は「通ったか」"""
    print(f"\n▶ {setsumei}")
    print(f"  $ {' '.join(cmd)}")
    r = subprocess.run(cmd, cwd=ROOT)
    ok = r.returncode == 0
    print(f"  → {'OK' if ok else '★ 落ちました（終了コード %d）' % r.returncode}")
    return ok


def collect_html():
    """配信物のHTMLを {表示名: (パス, "")} で集める"""
    out = {}
    for p in sorted(DEPLOY.rglob("*.html")):
        out["/" + p.relative_to(DEPLOY).as_posix()] = (p, "")
    for p in sorted((ROOT / "lp").rglob("*.html")):
        out[p.relative_to(ROOT).as_posix()] = (p, "")
    return out


def mikakutei_check(files):
    """未確定の箱（【…】）が配信物に混ざっていないか。

    原稿が揃う前にページの形だけ作ることがある。そのとき埋めていない欄に
    【CMO確認待ち：…】と書いて残すので、**それが本番に出るのを機械で止める。**
    お客様が読むページに社内向けの文字が出るのは、間違いなく事故。
    """
    print("\n▶ 未確定の箱（【…】）が残っていないか")
    warui = []
    for rel, (path, _sha) in sorted(files.items()):
        if not rel.endswith(".html"):
            continue
        honbun = path.read_text(encoding="utf-8", errors="ignore")
        # 【…】そのものは正規の本文にも使う（例：通知メールの件名 "【LP予約】エアコン"）。
        # 社内向けの目印が入っているものだけを拾う。
        hako = re.findall(r"【[^】]{0,40}(?:確認待ち|要確認|未確定|TODO|仮置き|あとで)[^】]{0,40}】", honbun)
        if hako:
            warui.append((rel, sorted(set(hako))))
    for rel, hako in warui:
        print(f"  ★  {rel}: {' / '.join(hako)}")
    if not warui:
        print("  OK  残っていません")
    return not warui


def rule_check(yomu, doko):
    """LP配信のルールの3項目。ページごとに見る"""
    print(f"\n▶ docs/LP配信のルール.md の3項目（{doko}）")
    warui = []
    for n in PAGES:
        try:
            h = yomu(n)
        except Exception as e:
            warui.append((n, [f"取得できない: {e}"]))
            continue
        nai = [na for na, pat in RULE_ARU if not re.search(pat, h)]
        # アンケートは1ページ完結でcidを持たない。ここだけ除く
        if n == "survey":
            nai = [na for na in nai if "cid" not in na]
        aru = [na for na, pat in RULE_NAI if re.search(pat, h)]
        if nai or aru:
            warui.append((n, [f"無い: {k}" for k in nai] + [f"在ってはいけない: {k}" for k in aru]))
        else:
            print(f"  OK  {n}")
    for n, r in warui:
        print(f"  ★  {n}: {' / '.join(r)}")
    return not warui


def mae():
    midashi("配信前（手元のビルドを見る）")
    if not DEPLOY.exists():
        print("★ deploy/netlify がありません。先に build-site.py netlify を流してください。")
        return False
    ok = []
    ok.append(hashiru("計測の土台", [sys.executable, "tools/check-tracking.py", "netlify"]))
    html = [str(DEPLOY / n / "index.html") for n in PAGES if (DEPLOY / n / "index.html").exists()]
    html += [str(p) for p in sorted(DEPLOY.glob("*/thanks.html"))]
    yoyaku = ROOT / "lp" / "booking" / "index.html"
    if yoyaku.exists():
        html.append(str(yoyaku))
    ok.append(hashiru("運営者情報", [sys.executable, "tools/check-public-page.py"] + html))
    ok.append(rule_check(
        lambda n: (DEPLOY / n / "index.html").read_text(encoding="utf-8", errors="ignore"),
        "ビルド"))
    ok.append(mikakutei_check(collect_html()))
    return all(ok)


def ato():
    midashi("配信後（本番のURLを見る）")
    ok = []

    def toru(n):
        return urllib.request.urlopen(f"{HONBAN}/{n}/", timeout=40).read().decode("utf-8", "replace")

    ok.append(rule_check(toru, "本番"))
    ok.append(hashiru("運営者情報（本番）",
                      [sys.executable, "tools/check-public-page.py"]
                      + [f"{HONBAN}/{n}/" for n in PAGES]))
    # ★ここで見るのは「このスクリプトが配信するページ」だけにする。
    #   読本・点検は別スレッドの持ち物で、暗いまま残っている（2026-09-12〜）。
    #   一緒に見ると配信の可否がいつまでも○にならないので、切り離して後ろで報せる。
    ok.append(hashiru("お客様のページが白地か（配信するぶん）",
                      ["node", "tools/check-darkmode.js"]
                      + [f"{HONBAN}/{n}/" for n in PAGES]))
    ok.append(hashiru("本番で計測が発火するか", [sys.executable, "tools/measure-production.py"]))
    return all(ok)


if __name__ == "__main__":
    hiki = set(sys.argv[1:])
    shiranai = hiki - {"--honban", "--zenbu"}
    if shiranai:
        sys.exit(f"知らない引数です: {' '.join(sorted(shiranai))}\n{__doc__}")

    kekka = []
    if "--honban" not in hiki or "--zenbu" in hiki:
        kekka.append(mae())
    if hiki & {"--honban", "--zenbu"}:
        kekka.append(ato())

    midashi("まとめ")
    if hiki & {"--honban", "--zenbu"}:
        yoso = subprocess.run(
            ["node", "tools/check-darkmode.js",
             "https://one-hitter-dokuhon.netlify.app/",
             "https://one-hitter-tenken.netlify.app/"],
            cwd=ROOT, capture_output=True, text=True)
        if yoso.returncode != 0:
            print("〔参考〕読本・点検がまだ暗いままです（別スレッドの持ち物。配信の可否には含めません）")
    if all(kekka):
        print("すべて通りました。")
        sys.exit(0)
    print("★ 落ちたものがあります。上を見て直してから配信してください。")
    sys.exit(1)
