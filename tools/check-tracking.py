#!/usr/bin/env python3
"""ビルド済みのページに、計測が正しく入っているかを確かめる。

  python3 tools/check-tracking.py            # deploy/netlify と deploy/htdocs の両方
  python3 tools/check-tracking.py netlify    # 片方だけ

ブラウザも外部通信も使わない。書き出されたHTMLを読んで、次を確かめるだけ。

  1. 全ページに OH_M（このページが何かの申告）が入っているか
  2. 全ページに計測スクリプトの本体が入っているか
  3. 送信完了ページが全LP分そろっているか（無いと送信後に404になる）
  4. LPと送信完了ページの lp_id / lp_variant が食い違っていないか
  5. 設定にIDを入れたなら、そのIDが実際にHTMLへ出ているか
  6. コールトラッキングの番号が、指定したLPにだけ入っているか

配信の前にこれを通すこと。落ちたら、直してから配信する。
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

# build-site.py から、ページ定義と設定の読み方をそのまま借りる
# （2か所に同じ定義を置くと、いつか必ずずれるため）
import importlib.util

spec = importlib.util.spec_from_file_location("build_site", ROOT / "tools" / "build-site.py")
build_site = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_site)

PROBLEMS: list[str] = []


def bad(msg: str) -> None:
    PROBLEMS.append(msg)


def oh_m(html: str) -> dict | None:
    m = re.search(r"window\.OH_M=(\{.*?\});</script>", html, re.S)
    return json.loads(m.group(1)) if m else None


def check_config(cfg: dict) -> None:
    """設定そのものの矛盾を見る（HTMLを見る前に）。"""
    ads = cfg.get("google_ads") or {}
    labels = ads.get("labels") or {}

    if ads.get("phone_conversion_label") and labels.get("phone_click"):
        bad("measurement.json: phone_conversion_label と labels.phone_click の両方が入っています。"
            "実際の通話と、リンクを押しただけの分を二重に数えます。どちらか一方にしてください")

    if labels.get("phone_click") or labels.get("generate_lead") or labels.get("line_click"):
        if not ads.get("conversion_id"):
            bad("measurement.json: labels を入れるなら conversion_id（AW-…）も要ります")

    if ads.get("phone_conversion_label") and not ads.get("conversion_id"):
        bad("measurement.json: phone_conversion_label を入れるなら conversion_id（AW-…）も要ります")

    # イベント名と食い違ったキーは、エラーも出ずに静かに無視されるので、ここで拾う
    known = {"generate_lead", "phone_click", "line_click", "cta_click",
             "estimate_use", "area_check", "form_start", "form_submit", "scroll_depth"}
    for key in labels:
        if key not in known:
            bad(f"measurement.json: labels の「{key}」はイベント名にありません"
                f"（送られません）。使えるのは {' / '.join(sorted(known))}")

    if cfg.get("debug"):
        bad("measurement.json: debug が true です。本番へ配信する前に false に戻してください")


def check_target(target: str, cfg: dict) -> None:
    out = build_site.TARGETS[target]["out"]
    if not out.exists():
        bad(f"{target}: {out} がありません。先に build-site.py を実行してください")
        return

    ga4 = ((cfg.get("ga4") or {}).get("measurement_id") or "").strip()
    ads = ((cfg.get("google_ads") or {}).get("conversion_id") or "").strip()
    pixel = ((cfg.get("meta") or {}).get("pixel_id") or "").strip()

    for name, meta in build_site.PAGES.items():
        d = meta["dir"]
        expect_tel = build_site.tel_for(cfg, d)

        for kind, fname in (("lp", "index.html"), ("thanks", "thanks.html")):
            path = out / d / fname
            where = f"{target}/{d}/{fname}"

            if not path.exists():
                bad(f"{where}: ページがありません"
                    + ("（フォーム送信後に404になります）" if kind == "thanks" else ""))
                continue

            html_text = path.read_text(encoding="utf-8")
            page = oh_m(html_text)

            if page is None:
                bad(f"{where}: OH_M の申告が入っていません")
                continue
            p = page.get("page", {})
            if p.get("kind") != kind:
                bad(f"{where}: kind が {p.get('kind')} になっています（{kind} のはず）")
            if p.get("lp_id") != meta["lp_id"] or p.get("lp_variant") != meta["lp_variant"]:
                bad(f"{where}: lp_id/lp_variant が {p.get('lp_id')}/{p.get('lp_variant')} "
                    f"になっています（{meta['lp_id']}/{meta['lp_variant']} のはず）")

            if "ONE HITTER ／ LP計測スクリプト" not in html_text:
                bad(f"{where}: 計測スクリプトの本体が入っていません")

            for label, value in (("GA4", ga4), ("Google広告", ads), ("Metaピクセル", pixel)):
                if value and value not in html_text:
                    bad(f"{where}: {label} の {value} がHTMLに出ていません")

            # 電話番号。表示用（ハイフンあり）と tel: 用（数字だけ）の両方を見る
            digits = re.sub(r"[^0-9]", "", expect_tel)
            if f"tel:{digits}" not in html_text:
                bad(f"{where}: 電話番号が {expect_tel} になっていません")
            stale = re.sub(r"[^0-9]", "", build_site.DEFAULT_TEL)
            if expect_tel != build_site.DEFAULT_TEL and f"tel:{stale}" in html_text:
                bad(f"{where}: 差し替え前の番号 {build_site.DEFAULT_TEL} が残っています")

    # 他のLPの計測用番号が紛れ込んでいないか（混ざると計測の意味が無くなる）
    numbers = {d: n.strip() for d, n in ((cfg.get("call_tracking") or {}).get("numbers") or {}).items() if n.strip()}
    for d, number in numbers.items():
        digits = re.sub(r"[^0-9]", "", number)
        for other in build_site.PAGES.values():
            if other["dir"] == d:
                continue
            for fname in ("index.html", "thanks.html"):
                path = out / other["dir"] / fname
                if path.exists() and digits in path.read_text(encoding="utf-8"):
                    bad(f"{target}/{other['dir']}/{fname}: {d} 用の番号 {number} が紛れ込んでいます")


def main() -> None:
    cfg = build_site.load_measurement()
    check_config(cfg)
    targets = sys.argv[1:] or list(build_site.TARGETS)
    for t in targets:
        if t not in build_site.TARGETS:
            sys.exit(f"配信先は {' / '.join(build_site.TARGETS)} のいずれかです")
        check_target(t, cfg)

    ga4 = ((cfg.get("ga4") or {}).get("measurement_id") or "").strip()
    print("GA4: " + (ga4 or "未設定（タグは出力されません）"))

    if PROBLEMS:
        print(f"\n見つかった問題 {len(PROBLEMS)}件")
        for p in PROBLEMS:
            print("  × " + p)
        sys.exit(1)
    print("すべて問題ありません。")


if __name__ == "__main__":
    main()
