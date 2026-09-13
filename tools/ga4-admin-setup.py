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
    ("generate_lead", "WEBフォームからの申込（本命）"),
    ("phone_click", "電話ボタンが押された"),
    ("line_click", "LINEボタンが押された"),
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
    args = ap.parse_args()

    sc = load_sheets_client()
    token = sc.access_token(sc.load_credentials(), scope=SCOPE)
    prop = args.property
    print(f"プロパティ {prop}" + ("　※下見のみ。何も変えません" if args.dry_run else ""))

    # ---------------- キーイベント ----------------
    print("\n■ キーイベント")
    have = {k.get("eventName"): k for k in list_all(token, prop, "keyEvents")}
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
        print(f"下見の結果：キーイベントは {tsuika} 件追加が要ります。"
              f"カスタムディメンションは {len(tarinai)} 件足りません。")
        print("実際に登録するには --dry-run を外してもう一度実行してください。")
    else:
        print(f"キーイベント：登録済み {len(KEY_EVENTS)} 件（今回 {tsuika} 件追加）")
        if tarinai:
            print(f"カスタムディメンション：**{len(tarinai)} 件足りません** "
                  f"→ {' / '.join(p for p, _, _ in tarinai)}")
            print("  作るなら --create-dimensions を付けて実行してください。")
        else:
            print(f"カスタムディメンション：{len(DIMENSIONS)} 件すべて登録済み")
    print("\n⏳ レポートに出るまで24〜48時間かかります。すぐ見えなくても失敗ではありません。")


if __name__ == "__main__":
    main()
