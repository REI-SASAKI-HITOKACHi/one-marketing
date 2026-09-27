#!/usr/bin/env python3
"""GA4のキーイベントを登録し、カスタムディメンションの登録状況を一覧で見る。

    python3 tools/ga4-admin-setup.py --dry-run   # 下見（何も変えない）
    python3 tools/ga4-admin-setup.py             # 足りないキーイベントを登録する

**何度実行しても同じ結果になる。** 既にあるものは触らない。

## これは何のためのものか

GA4は「キーイベント」に指定したものしかGoogle広告へコンバージョンとして渡せない。
また「カスタムディメンション」に登録した印しかレポートで分解できない。
どちらも本来は管理画面で人が25分かけて入れる作業で、打ち間違えるとエラーも出ずに
空欄になる。**ここをAPIでやると、間違えようがなくなる。**

設計の根拠は `docs/measurement-spec.md`、画面でやる場合の手順は
`docs/ga4-管理画面の手順.md`。

## 動かすのに要るもの

- サービスアカウントの鍵。`tools/sheets_client.py` の `load_credentials()` を
  そのまま使う（環境変数 `GOOGLE_SHEETS_SA_KEY` か
  `~/.config/one-hitter/sa-key.json`）。**このファイルにも鍵は書かない。**
- そのサービスアカウントが、対象プロパティに **編集者** で入っていること
  （2026-09-12 にブラウザ担当が追加済み）
- Google Analytics Admin API が有効になっていること

## 対象

プロパティ **381320625**（公式サイトとLPは同一プロパティの別ストリーム）。
`--property` で変えられる。
"""

import argparse
import importlib.util
import json
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
API = "https://analyticsadmin.googleapis.com/v1beta"
SCOPE = "https://www.googleapis.com/auth/analytics.edit"
PROPERTY = "381320625"

# ---------------------------------------------------------------------------
# 登録したいもの。設計は docs/measurement-spec.md
# ---------------------------------------------------------------------------

# キーイベント（＝旧「コンバージョン」）。ここに入れたものだけが広告に渡せる。
#
# ⚠️ form_submit と booking_submit は**入れない**。
#    送信ボタンを押した時点と、受理された時点の二重計上になる。
#    survey_complete も入れない。アンケートの回答は広告の成果ではないので、
#    入れると自動入札が歪む。
KEY_EVENTS = [
    ("generate_lead", "申込（LPのサンクスページ／予約フォームの完了画面）"),
    ("phone_click", "電話ボタンが押された"),
    ("line_click", "LINEボタンが押された"),
    # 予約フォームの「入力を始めた」。申込ではなく関心の強さの目安。
    # CMO判断（2026-09-25 20260925-01-measurement）で足した。
    # ⚠️ 申込の件数と混ぜて読まないこと。generate_lead と足し算すると水増しになる。
    ("booking_start", "予約フォームの入力を始めた（関心の目安。申込ではない）"),
]

# キーイベントから外すもの。**ここに書いたものだけを外す。**
# 外すのは「設計に無い」からではなく、中身を確かめて理由があるものだけ。
#
# ⚠️ 外すのは、KEY_EVENTS を足し終わった**あと**。
#    先に外すと、その間キーイベントが減った状態でレポートが集計される。
REMOVE_KEY_EVENTS = [
    # 公式サイトの問い合わせ完了（/contact/complete.html）。
    # 2026-09-25 CMO実測：直近30日のキーイベント44件のうち42件がこれで、
    # PC・直接流入・/contact/ 直行のスパム（オーナーが 9/23「対応不要」と判断）。
    # 本物の問い合わせも混ざるが、スパムに埋もれて「お客様の行動」として数えられない。
    ("form_complete", "公式サイトの問い合わせ完了。直近30日の44件中42件がスパム（2026-09-25 CMO実測）"),
]

# カスタムディメンション。2026-09-12 にブラウザ担当が画面で登録済みのはずなので、
# ここでは**作らずに、あるかどうかを見るだけ**にしている。
# 足りないものがあれば --create-dimensions を付けたときだけ作る。
DIMENSIONS = [
    ("lp_id", "LP", "どの商品のLPか"),
    ("lp_variant", "LPパターン", "案Aと案B。A/Bテストの判定に要る"),
    ("page_kind", "ページの種類", "LP本体／送信完了／アンケート／予約フォーム"),
    ("link_position", "ボタンの場所", "ヘッダーか追従バーか"),
    ("area_result", "エリア判定", "対応エリア内か外か"),
    ("estimate_total", "見積り額", "申込1件あたりの概算金額"),
    ("traffic_src", "流入元", "?src= の値。QR・SMS・施設カードの別"),
    ("traffic_cid", "流入元の個別ID", "?cid= の値"),
]


# ---------------------------------------------------------------------------


def load_sheets_client():
    """鍵の読み方と署名は sheets_client.py のものを使い回す。

    2か所に同じ実装を置くと、いつか片方だけ直して壊れる。
    """
    path = ROOT / "tools" / "sheets_client.py"
    if not path.exists():
        sys.exit(
            "tools/sheets_client.py がありません。\n"
            "このスクリプトは、そこにある鍵の読み込みと署名の処理を使い回しています。\n"
            "CMOブランチには入っています。そちらの環境で実行してください。"
        )
    spec = importlib.util.spec_from_file_location("sheets_client", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def call(token: str, path: str, method: str = "GET", payload=None):
    url = f"{API}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer " + token)
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            body = r.read()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        hint = ""
        if e.code == 403:
            hint = ("\nヒント：サービスアカウントがこのプロパティに編集者で入っているか、"
                    "Google Analytics Admin API が有効になっているかを確認してください。")
        elif e.code == 404:
            hint = "\nヒント：プロパティ番号が違うかもしれません。"
        sys.exit(f"GA4 Admin API {e.code}: {detail[:1200]}{hint}")


def list_all(token: str, prop: str, kind: str) -> list:
    """ページ送りを最後までたどる。件数が増えても取りこぼさないため。"""
    out, page = [], None
    while True:
        q = "?pageSize=200" + (f"&pageToken={urllib.parse.quote(page)}" if page else "")
        res = call(token, f"/properties/{prop}/{kind}{q}")
        out += res.get(kind, [])
        page = res.get("nextPageToken")
        if not page:
            return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--property", default=PROPERTY, help=f"プロパティ番号（既定 {PROPERTY}）")
    ap.add_argument("--dry-run", action="store_true", help="何も変えずに、いまの状態と差分だけ見る")
    ap.add_argument("--create-dimensions", action="store_true",
                    help="足りないカスタムディメンションも作る（既定は見るだけ）")
    ap.add_argument("--kiroku", default=None,
                    help="変更前のキーイベント一覧を書き出す先"
                         "（既定 docs/ga4-キーイベント-変更前-<今日>.md）。下見のときは書かない")
    args = ap.parse_args()

    sc = load_sheets_client()
    token = sc.access_token(sc.load_credentials(), scope=SCOPE)
    prop = args.property
    print(f"プロパティ {prop}" + ("　※下見のみ。何も変えません" if args.dry_run else ""))

    # ---------------- キーイベント ----------------
    print("\n■ キーイベント")
    have = {k.get("eventName"): k for k in list_all(token, prop, "keyEvents")}

    # 変更前の一覧を控える。**GA4を触る前に**書く。
    # 何を外したか・元は何だったかを、あとから必ず辿れるようにするため。
    if not args.dry_run:
        import datetime as _dt
        kyou = _dt.date.today().isoformat()
        kiroku = pathlib.Path(args.kiroku) if args.kiroku else (
            ROOT / "docs" / f"ga4-キーイベント-変更前-{kyou}.md")
        kiroku.parent.mkdir(parents=True, exist_ok=True)
        gyou = ["# GA4 キーイベント：変更前の一覧",
                "",
                f"プロパティ {prop} ／ 記録 {kyou} ／ `tools/ga4-admin-setup.py` が変更の直前に書き出したもの。",
                "**元に戻すときは、ここにある名前を画面でキーイベントに付け直せば戻ります。**",
                "",
                "| イベント名 | 数え方 | 作成日時 | name |",
                "|---|---|---|---|"]
        for n in sorted(have):
            k = have[n]
            gyou.append(f"| `{n}` | {k.get('countingMethod', '')} | "
                        f"{k.get('createTime', '')} | `{k.get('name', '')}` |")
        if not have:
            gyou.append("| （なし） | | | |")
        kiroku.write_text("\n".join(gyou) + "\n", encoding="utf-8")
        print(f"  変更前の一覧を控えました → {kiroku.relative_to(ROOT) if kiroku.is_relative_to(ROOT) else kiroku}")

    tsuika = 0
    for name, why in KEY_EVENTS:
        if name in have:
            print(f"  ○ {name:<16} 既にある（{why}）")
            continue
        if args.dry_run:
            print(f"  → {name:<16} これから登録する（{why}）")
            tsuika += 1
            continue
        # countingMethod は ONCE_PER_EVENT。
        # 1回の申込で2回押された場合も2件と数える素直な数え方で、
        # 二重計上はイベント側（form_submit を入れない）で防いでいる。
        call(token, f"/properties/{prop}/keyEvents", "POST",
             {"eventName": name, "countingMethod": "ONCE_PER_EVENT"})
        print(f"  ✓ {name:<16} 登録した（{why}）")
        tsuika += 1

    # ---- 外す（足し終わったあと） ----
    hazushita = 0
    for name, why in REMOVE_KEY_EVENTS:
        k = have.get(name)
        if not k:
            print(f"  ・ {name:<16} もともと無い（{why}）")
            continue
        if args.dry_run:
            print(f"  ✕ {name:<16} これから外す（{why}）")
            hazushita += 1
            continue
        if not k.get("name"):
            sys.exit(f"{name} の識別子（name）が取れません。画面で外してください。")
        call(token, f"/{k['name']}", "DELETE")
        print(f"  ✕ {name:<16} 外した（{why}）")
        hazushita += 1
    have = {n: v for n, v in have.items()
            if n not in {r for r, _ in REMOVE_KEY_EVENTS}}

    hoka = [n for n in have if n not in {k for k, _ in KEY_EVENTS}]
    if hoka:
        print("\n  ほかにキーイベントになっているもの（設計に無いもの。意図したものか確認を）:")
        for n in sorted(hoka):
            warn = ""
            if n in ("form_submit", "booking_submit"):
                warn = "  ⚠️ generate_lead と二重に数えます"
            elif n == "survey_complete":
                warn = "  ⚠️ アンケートの回答です。広告の入札が歪みます"
            print(f"    ・{n}{warn}")

    # ---------------- カスタムディメンション ----------------
    print("\n■ カスタムディメンション")
    dims = {d.get("parameterName"): d for d in list_all(token, prop, "customDimensions")}
    tarinai = []
    for param, label, why in DIMENSIONS:
        d = dims.get(param)
        if d:
            sukoopu = d.get("scope", "?")
            ng = "" if sukoopu == "EVENT" else f"  ⚠️ 範囲が {sukoopu}。イベントにしてください"
            print(f"  ○ {param:<15} {d.get('displayName','')}{ng}")
        else:
            print(f"  × {param:<15} 未登録（{why}）")
            tarinai.append((param, label, why))

    if tarinai and args.create_dimensions and not args.dry_run:
        print()
        for param, label, why in tarinai:
            call(token, f"/properties/{prop}/customDimensions", "POST",
                 {"parameterName": param, "displayName": label,
                  "scope": "EVENT", "description": why})
            print(f"  ✓ {param:<15} 登録した")
        tarinai = []

    # ---------------- まとめ ----------------
    print("\n" + "-" * 58)
    if args.dry_run:
        print(f"下見の結果：キーイベントは {tsuika} 件追加・{hazushita} 件除去が要ります。"
              f"カスタムディメンションは {len(tarinai)} 件足りません。")
        print("実際に登録するには --dry-run を外してもう一度実行してください。")
    else:
        print(f"キーイベント：登録済み {len(KEY_EVENTS)} 件（今回 {tsuika} 件追加・{hazushita} 件除去）")
        if tarinai:
            print(f"カスタムディメンション：**{len(tarinai)} 件足りません** "
                  f"→ {' / '.join(p for p, _, _ in tarinai)}")
            print("  作るなら --create-dimensions を付けて実行してください。")
        else:
            print(f"カスタムディメンション：{len(DIMENSIONS)} 件すべて登録済み")
    print("\n⏳ レポートに出るまで24〜48時間かかります。すぐ見えなくても失敗ではありません。")


if __name__ == "__main__":
    main()
