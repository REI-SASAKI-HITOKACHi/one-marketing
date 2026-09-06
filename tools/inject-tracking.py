#!/usr/bin/env python3
"""完結したHTML文書に、計測タグを差し込む。

`tools/build-site.py` は LP を断片から組み立てるついでにタグを入れるが、
アンケート（`lp/survey/`）のように**それ自体が完結した文書**のページは
あちらの流れに乗らない。このツールは、そういうページ用の入口。

  python3 tools/inject-tracking.py deploy/netlify/survey/index.html --kind survey --id survey

  --kind    lp / thanks / survey     このページが何か
  --id      lp_id（レポートで並べるときの名前）
  --variant A / B                    A/Bテストをしないなら A のままでよい
  --out     書き出し先（省略すると上書き）

設定（測定IDなど）は build-site.py と同じ `tracking/measurement.json` を読む。
IDが空なら、タグは出力されない（何度実行しても壊れない）。

**同じファイルに2回実行しても、二重には入らない。** 既に入っていれば入れ替える。
"""
import argparse
import importlib.util
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

spec = importlib.util.spec_from_file_location("build_site", ROOT / "tools" / "build-site.py")
build_site = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_site)

# 既に入っている計測ブロックを見分けるための目印
HEAD_MARK = "<!-- ONE HITTER 計測タグ"
BODY_MARK = "ONE HITTER ／ LP計測スクリプト"


def strip_existing(doc: str) -> str:
    """前回入れた分を取り除く。差し込みを繰り返しても増えないようにする。"""
    # head 側：目印のコメントから </head> の手前まで
    doc = re.sub(re.escape(HEAD_MARK) + r".*?(?=</head>)", "", doc, flags=re.S)
    # body 側：目印を含む <script> ブロックまるごと。
    # 「</script> を含まない文字の並び」で挟むことで、隣のスクリプトまで
    # 巻き込まないようにしている。
    doc = re.sub(r"<script>(?:(?!</script>).)*?" + re.escape(BODY_MARK)
                 + r"(?:(?!</script>).)*?</script>\s*", "", doc, flags=re.S)
    return doc


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", help="対象のHTMLファイル")
    ap.add_argument("--kind", default="lp", choices=["lp", "thanks", "survey"])
    ap.add_argument("--id", dest="lp_id", required=True, help="lp_id（例: survey / nenmatsu）")
    ap.add_argument("--variant", default="A")
    ap.add_argument("--tel", default="", help="このページに載っている電話番号（あれば）")
    ap.add_argument("--out", default=None, help="書き出し先（省略すると上書き）")
    args = ap.parse_args()

    src = pathlib.Path(args.path)
    if not src.exists():
        sys.exit(f"{src} がありません")

    doc = src.read_text(encoding="utf-8")
    if "</head>" not in doc or "</body>" not in doc:
        sys.exit(f"{src}: </head> か </body> が見つかりません。"
                 "断片ではなく、完結したHTML文書を指定してください")

    cfg = build_site.load_measurement()
    page = {"kind": args.kind, "lp_id": args.lp_id, "lp_variant": args.variant}
    if args.kind == "thanks":
        page["lead_value"] = (cfg.get("lead_value") or {}).get(args.lp_id, 0)

    doc = strip_existing(doc)
    doc = doc.replace("</head>", build_site.tracking_head(cfg, page, args.tel) + "\n</head>", 1)
    doc = doc.replace("</body>", build_site.tracking_body() + "\n</body>", 1)

    dst = pathlib.Path(args.out) if args.out else src
    dst.write_text(doc, encoding="utf-8")

    ga4 = ((cfg.get("ga4") or {}).get("measurement_id") or "").strip()
    print(f"{dst}  kind={args.kind} lp_id={args.lp_id} variant={args.variant}  "
          f"GA4={ga4 or '未設定（タグは出力されません）'}")


if __name__ == "__main__":
    main()
