#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""住所から郵便番号を引く（サーバ側だけで使う）。

  受注フォームの郵便番号欄をなくした（2026-09-19 オーナー指示）。
  「住所入力からスプシへ郵便番号を自動反映させてほしい」。

  ★索引（data/postal-index.json・約850KB）をフォームへ送らないこと。
    送ると和真さんのスマホで毎回850KB読むことになる。引くのはここ（取り込み時）だけ。

  精度は**町域まで**。丁目で郵便番号が分かれる町域は代表の1つになる。
  台帳に人が入れた実績（住所と郵便番号が両方ある行）があれば、そちらを先に使うこと。
"""
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
SAKUIN = ROOT / "data" / "postal-index.json"
_idx = None


def _yomu():
    global _idx
    if _idx is None:
        _idx = json.loads(SAKUIN.read_text(encoding="utf-8"))["索引"] if SAKUIN.exists() else {}
    return _idx


def seikei(yubin):
    """7桁を 123-4567 の形にする。"""
    y = re.sub(r"\D", "", str(yubin or ""))
    return f"{y[:3]}-{y[3:]}" if len(y) == 7 else ""


def hiku(jusho):
    """住所 → 郵便番号（123-4567）。引けなければ空文字。"""
    idx = _yomu()
    s = re.sub(r"[\s　]", "", str(jusho or "")).replace("ヶ", "ケ")
    m = re.search(r"(.*?[区市町村])(.*)", s)
    if not m:
        return ""
    shi = re.sub(r"^(東京都|千葉県|神奈川県)", "", m.group(1))
    # 町域は、数字（丁目・番地）の手前まで
    cho = re.split(r"[0-9０-９\-－―ー]", m.group(2))[0]
    for n in range(len(cho), 0, -1):
        y = idx.get(shi + cho[:n])
        if y:
            return seikei(y)
    return ""


if __name__ == "__main__":
    import sys
    for a in sys.argv[1:]:
        print(f"{a}\t{hiku(a) or '（引けません）'}")
