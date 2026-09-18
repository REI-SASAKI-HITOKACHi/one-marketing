#!/usr/bin/env python3
"""週次の数字をGA4から取って、掲示板にそのまま貼れる表にする。

    python3 tools/ga4-weekly.py                # 直前の月〜日と、その前の週を比べる
    python3 tools/ga4-weekly.py --week 2026-09-07   # その週（月曜を指定）
    python3 tools/ga4-weekly.py --json         # 機械で読む用

**出てくるのは Markdown の表そのもの。** 掲示板の返信にそのまま貼れる。

## 何のためのものか

毎週月曜 08:30 JST までに、先週の数字をCMOへ返す決まりがある
（`docs/org/README.md` 4.8.1、掲示板 `20260912-04-measurement`）。
**手で管理画面を開いて数えると、毎週20分かかって、写し間違える。**

## 動かすのに要るもの

- サービスアカウントの鍵。`tools/sheets_client.py` の `load_credentials()` を使う
  （環境変数 `GOOGLE_SHEETS_SA_KEY` か `~/.config/one-hitter/sa-key.json`）
- そのサービスアカウントがプロパティに**閲覧者以上**で入っていること
- Google Analytics Data API が有効になっていること

**鍵が無い環境（計測担当のブランチなど）では動きません。** CMOの環境で実行して、
出てきた表を掲示板に貼ってください。

## 気をつけていること

- **数字が取れなかった項目は空欄にせず「未取得」と出す。** 0件と区別がつかなくなるため
- **予約フォームはホストが複数ある**（`yoyaku.onehitter.jp` / `onehitter-yoyaku.netlify.app` /
  旧 `one-hitter-booking.netlify.app`）。**全部足さないと過小になる**
- 公式サイトとLPは**同一プロパティの別ストリーム**なので、ホスト名で分ける
"""

import argparse
import datetime as dt
import importlib.util
import json
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
API = "https://analyticsdata.googleapis.com/v1beta"
SCOPE = "https://www.googleapis.com/auth/analytics.readonly"
PROPERTY = "381320625"

# 予約フォームのホスト。増えたらここに足す。
# 旧ホストを止めたら消す（止めるまでは足さないと数字が小さく出る）。
YOYAKU_HOSTS = [
    "yoyaku.onehitter.jp",
    "onehitter-yoyaku.netlify.app",
    "one-hitter-booking.netlify.app",
]


def load_sheets_client():
    path = ROOT / "tools" / "sheets_client.py"
    if not path.exists():
        sys.exit(
            "tools/sheets_client.py がありません。\n"
            "鍵の読み込みと署名をそこから使い回しています。CMOの環境で実行してください。"
        )
    spec = importlib.util.spec_from_file_location("sheets_client", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_report(token: str, prop: str, body: dict) -> dict:
    req = urllib.request.Request(
        f"{API}/properties/{prop}:runReport",
        data=json.dumps(body).encode(), method="POST")
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        hint = ""
        if e.code == 403:
            hint = ("\nヒント：サービスアカウントがこのプロパティに入っているか、"
                    "Google Analytics Data API が有効かを確認してください。")
        sys.exit(f"GA4 Data API {e.code}: {detail[:1000]}{hint}")


def rows(res: dict) -> list:
    """[(次元の値の組, 指標の数値の組)] にほぐす。"""
    out = []
    for r in res.get("rows", []):
        d = tuple(v.get("value", "") for v in r.get("dimensionValues", []))
        m = tuple(int(float(v.get("value", 0) or 0)) for v in r.get("metricValues", []))
        out.append((d, m))
    return out


def week_range(monday: dt.date):
    return monday.isoformat(), (monday + dt.timedelta(days=6)).isoformat()


def collect(token: str, prop: str, monday: dt.date) -> dict:
    """1週間ぶんの数字を集める。取れなかったものは None のままにする。"""
    start, end = week_range(monday)
    dr = [{"startDate": start, "endDate": end}]
    out = {"期間": f"{start}〜{end}"}

    # --- ホスト別・ページ別のセッション ---
    res = run_report(token, prop, {
        "dateRanges": dr,
        "dimensions": [{"name": "hostName"}, {"name": "landingPagePlusQueryString"}],
        "metrics": [{"name": "sessions"}],
        "limit": "10000",
    })
    sessions = {}
    for (host, land), (s,) in rows(res):
        sessions[(host, land.split("?")[0])] = sessions.get((host, land.split("?")[0]), 0) + s
    out["_sessions"] = sessions

    def lp(name):
        return sum(v for (h, p), v in sessions.items()
                   if h.endswith("onehitter.jp") or h.endswith("netlify.app")
                   if p.startswith(f"/{name}"))

    out["LP /mizumawari/"] = lp("mizumawari")
    out["LP /aircon/"] = lp("aircon")
    out["LP /nenmatsu/"] = lp("nenmatsu")
    out["アンケート /survey/"] = lp("survey")
    out["予約フォーム（全ホスト合計）"] = sum(
        v for (h, _), v in sessions.items() if h in YOYAKU_HOSTS)

    # --- 広告グループ別（着地URLの ?ag= から拾う） ---
    #
    # **受け側の実装がいらないのが肝。** GA4は着地URLをクエリ付きで持っているので、
    # 広告のURLに &ag={adgroupid} を足すだけで、広告グループ別のセッションが取れる。
    # LPの hidden 欄も、Netlify Forms も、台帳の列も増やさなくてよい。
    ag = {}
    for (host, land), (n,) in rows(res):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(land).query)
        v = (q.get("ag") or [""])[0]
        if v:
            ag[(v, land.split("?")[0])] = ag.get((v, land.split("?")[0]), 0) + n
    out["_ad_groups"] = ag

    # --- イベント数 ---
    res = run_report(token, prop, {
        "dateRanges": dr,
        "dimensions": [{"name": "eventName"}],
        "metrics": [{"name": "eventCount"}],
        "limit": "1000",
    })
    ev = {d[0]: m[0] for d, m in rows(res)}
    for name, label in (("generate_lead", "申込（generate_lead）"),
                        ("phone_click", "電話クリック（phone_click）"),
                        ("line_click", "LINEクリック（line_click）"),
                        ("form_start", "フォーム入力開始（form_start）")):
        out[label] = ev.get(name, 0)

    # --- traffic_src 別 ---
    # カスタムディメンションが登録されていないと 400 が返る。
    # そこで落とさず「未取得」にする。反映まで24〜48時間かかるため。
    try:
        res = run_report(token, prop, {
            "dateRanges": dr,
            "dimensions": [{"name": "customEvent:traffic_src"}],
            "metrics": [{"name": "sessions"}],
            "limit": "100",
        })
        out["_traffic_src"] = {d[0]: m[0] for d, m in rows(res)}
    except SystemExit:
        out["_traffic_src"] = None
    return out


def fmt(n):
    return "未取得" if n is None else f"{n:,}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--property", default=PROPERTY)
    ap.add_argument("--week", help="対象の週の月曜（YYYY-MM-DD）。既定は直前の月〜日")
    ap.add_argument("--json", action="store_true", help="表ではなくJSONで出す")
    args = ap.parse_args()

    if args.week:
        monday = dt.date.fromisoformat(args.week)
    else:
        today = dt.date.today()
        monday = today - dt.timedelta(days=today.weekday() + 7)
    zenshu = monday - dt.timedelta(days=7)

    sc = load_sheets_client()
    token = sc.access_token(sc.load_credentials(), scope=SCOPE)

    ima = collect(token, args.property, monday)
    mae = collect(token, args.property, zenshu)

    if args.json:
        # `_sessions` は (ホスト, パス) のタプルを鍵にしているのでJSONにできない。
        # 内訳が要るときのために "ホスト パス" の文字列へ直して出す。
        def clean(d: dict) -> dict:
            out = {k: v for k, v in d.items() if not k.startswith("_")}
            out["流入元別"] = d.get("_traffic_src")
            # (広告グループID, 着地パス) のタプル鍵はJSONにできないので文字列へ
            out["広告グループ別"] = {f"{g} {path}": v
                                     for (g, path), v in (d.get("_ad_groups") or {}).items()}
            out["ホスト別の内訳"] = {f"{h} {p}": v
                                     for (h, p), v in (d.get("_sessions") or {}).items()}
            return out
        print(json.dumps({"今週": clean(ima), "前週": clean(mae)},
                         ensure_ascii=False, indent=1))
        return

    keys = [k for k in ima if not k.startswith("_") and k != "期間"]
    print(f"# 週次の数字（{ima['期間']}）\n")
    print(f"| 項目 | 先週 {mae['期間']} | 今週 {ima['期間']} | 差 |")
    print("|---|---:|---:|---:|")
    for k in keys:
        a, b = mae.get(k), ima.get(k)
        sa = "—" if a is None or b is None else f"{b - a:+,}"
        print(f"| {k} | {fmt(a)} | {fmt(b)} | {sa} |")

    print("\n## 流入元（`?src=`）別のセッション\n")
    ts = ima.get("_traffic_src")
    if ts is None:
        print("**未取得。** `traffic_src` のカスタムディメンションがまだ反映されていません"
              "（登録から24〜48時間かかります）。")
    elif not ts:
        print("該当なし（`?src=` 付きの訪問が0件）。")
    else:
        print("| 流入元 | セッション |")
        print("|---|---:|")
        for k, v in sorted(ts.items(), key=lambda x: -x[1]):
            print(f"| {k or '(空)'} | {v:,} |")

    print("\n## 広告グループ（`?ag=`）別のセッション\n")
    ag = ima.get("_ad_groups") or {}
    if not ag:
        print("該当なし（`?ag=` 付きの着地が0件）。"
              "**広告のURLに `&ag={adgroupid}` が入っていないか、まだクリックがありません。**")
    else:
        print("| 広告グループID | 着地ページ | セッション |")
        print("|---|---|---:|")
        for (g, path), v in sorted(ag.items(), key=lambda x: -x[1]):
            print(f"| `{g}` | `{path}` | {v:,} |")
        print("\n> IDと広告グループ名の対応は Google広告の管理画面で見てください"
              "（`docs/広告-コンバージョン計測.md`）。")

    print("\n> 予約フォームは複数ホストの合計です："
          + " / ".join(f"`{h}`" for h in YOYAKU_HOSTS)
          + "。**旧ホストを止めたら `YOYAKU_HOSTS` から消してください。**")


if __name__ == "__main__":
    main()
