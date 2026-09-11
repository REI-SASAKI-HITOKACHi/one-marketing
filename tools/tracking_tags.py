#!/usr/bin/env python3
"""計測タグの文字列を返すだけの窓口。

`tools/build-site.py` は LP を組み立てるついでに計測タグを入れる。
予約フォームのように**別の生成スクリプトが作るページ**からも同じタグを使えるよう、
「タグの文字列を返す関数」だけをここに出しておく。

    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    from tracking_tags import head, body

    html = html.replace("</head>", head("booking", "booking") + "\\n</head>")
    html = html.replace("</body>", body() + "\\n</body>")

設定は `tracking/measurement.json` を読む。**測定IDが空なら何も出力しない**ので、
IDが用意できていない状態で呼んでも壊れない。

イベントの定義は `docs/measurement-spec.md` が正。
"""
import importlib.util
import pathlib

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("build_site", _ROOT / "tools" / "build-site.py")
_bs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_bs)


def head(kind: str, lp_id: str, variant: str = "A", tel: str = "") -> str:
    """<head> の直前に入れる分。gtag の読み込みと、このページが何かの申告。

    kind    … lp / thanks / survey / booking のいずれか
    lp_id   … レポートで並べるときの名前（予約フォームなら "booking"）
    tel     … ページに載っている電話番号。Google広告の通話計測に使う（無くてよい）
    """
    cfg = _bs.load_measurement()
    page = {"kind": kind, "lp_id": lp_id, "lp_variant": variant}
    return _bs.tracking_head(cfg, page, tel)


def body() -> str:
    """</body> の直前に入れる分。クリックや送信を拾う本体。"""
    return _bs.tracking_body()


if __name__ == "__main__":
    import sys
    kind = sys.argv[1] if len(sys.argv) > 1 else "booking"
    lp_id = sys.argv[2] if len(sys.argv) > 2 else kind
    print(head(kind, lp_id))
    print("...")
    print(body()[:200] + " …")
