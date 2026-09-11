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

    # 注文IDの欄と、それを埋めるスクリプトが対になっているか。
    # 片方だけだと、受注と申込を結ぶ鍵が空のまま溜まる。
    for meta in build_site.PAGES.values():
        path = out / meta["dir"] / "index.html"
        if not path.exists():
            continue
        doc = path.read_text(encoding="utf-8")
        has_field = 'name="order_id"' in doc
        has_maker = "sessionStorage.setItem('oh_order_id'" in doc
        if has_field != has_maker:
            bad(f"{target}/{meta['dir']}/index.html: 注文IDの"
                + ("欄はあるのに、作るスクリプトがありません" if has_field
                   else "スクリプトはあるのに、入れる欄がありません"))

    check_rentracks(target, cfg, out)


def check_rentracks(target: str, cfg: dict, out) -> None:
    """アフィリエイト（レントラックス）のタグを見る。

    ここで落としたい事故は3つ。
      1. 登録していない掲載先にタグが出ている（＝出す理由が無いものを公開している）
      2. 目印の `<!--` が <script> の中に入って、タグが丸ごと死んでいる
         （2026-09-11 に実際に起きた。JavaScriptでは `<!--` が行コメントになる）
      3. 氏名・電話・メールを先方へ渡してしまっている
    """
    rt = cfg.get("rentracks") or {}
    sid, pid = (rt.get("sid") or "").strip(), (rt.get("pid") or "").strip()
    pages = rt.get("pages") or []
    if not sid or not pid:
        if pages:
            bad("measurement.json: rentracks.pages が入っているのに sid / pid が空です")
        return

    for meta in build_site.PAGES.values():
        d = meta["dir"]
        want = d in pages
        for fname in ("index.html", "thanks.html"):
            path = out / d / fname
            if not path.exists():
                continue
            doc = path.read_text(encoding="utf-8")
            has = "rentracks.jp/js/itp/rt.track.js" in doc
            where = f"{target}/{d}/{fname}"
            if has and not want:
                bad(f"{where}: レントラックスのタグが出ています。"
                    f"掲載先として登録しているのは {' / '.join(pages) or '（なし）'} だけです")
            if want and not has:
                bad(f"{where}: レントラックスのタグがありません")
            if not has:
                continue
            if doc.count("rentracks.jp/js/itp/rt.track.js") != 1:
                bad(f"{where}: レントラックスのタグが2つ以上あります（成果を二重に数えます）")
            # `<!--` が <script> の中にあると、その行が丸ごとコメントになって死ぬ
            for block in re.findall(r"<script>(.*?)</script>", doc, re.S):
                if "rt.track.js" in block and "<!--" in block:
                    bad(f"{where}: レントラックスのタグの中に <!-- があります。"
                        "JavaScriptでは行コメントになり、タグが動きません")
            if fname == "thanks.html":
                if f"_rt.sid={sid};_rt.pid={pid};" not in doc:
                    bad(f"{where}: _rt.sid / _rt.pid が measurement.json と違います")
                if "_rt.price=0;_rt.reward=-1;" not in doc:
                    bad(f"{where}: 定額案件なので _rt.price は 0、_rt.reward は -1 です")
                if "_rt.cinfo=encodeURIComponent(" not in doc:
                    bad(f"{where}: _rt.cinfo（成果の識別記号）が入っていません。先方指定の必須項目です")
                if "_rt.cname='';_rt.ctel='';_rt.cemail='';" not in doc:
                    bad(f"{where}: 氏名・電話・メールが空になっていません。"
                        "これらを入れると、お客様の個人情報を社外へ渡すことになります")


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
