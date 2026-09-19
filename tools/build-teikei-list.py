#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""提携先・紹介元の選択肢を、台帳から作る。

  オーナー指示（2026-09-19）
    「提携先はプルダウン選択へ（表記ゆれ防止）。新規入力欄もほしい」

  正（せい）は『【毎月更新】リピート/業務提携』タブの B列「企業名」。
  ★ここを手で書き写さないこと。書き写すと表記がずれて、同じ先が2つに割れる。

  並び順は『提携先_休眠度』タブの最終発注が新しい順（よく出る先が上に来る）。
  そこに無い先は、そのあとに台帳の並びで付ける。

    python3 tools/build-teikei-list.py           # data/teikei-saki.json を作る
    python3 tools/build-teikei-list.py --dry-run # 出すだけ
"""
import json
import pathlib
import sys
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import sheets_client as sc

SS = "1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64"
DAICHO = "【毎月更新】リピート/業務提携"
KYUMIN = "提携先_休眠度"
OUT = ROOT / "data" / "teikei-saki.json"


def main():
    tok = sc.access_token(sc.load_credentials())

    def yomu(rng):
        return sc.call(tok, "/" + SS + "/values/" + urllib.parse.quote(rng, safe="")).get("values", [])

    daicho = [str(r[0]).strip() for r in yomu(f"'{DAICHO}'!B2:B100") if r and str(r[0]).strip()]

    # 休眠度タブ（B列=提携先／F列=最終発注）で並べ替えの材料をつくる
    junjo = {}
    for r in yomu(f"'{KYUMIN}'!B1:F40"):
        r = r + [""] * (5 - len(r))
        na, saishu = str(r[0]).strip(), str(r[4]).strip()
        if na and na != "提携先":
            junjo[na] = saishu

    hai = sorted(daicho, key=lambda n: (junjo.get(n, "") == "", junjo.get(n, ""), n), reverse=True)
    hai = [n for n in hai if junjo.get(n)] + [n for n in daicho if not junjo.get(n)]

    nakami = {
        "_説明": "受注フォームの「提携先・紹介元」プルダウンの中身。表記ゆれを防ぐため台帳から作る。",
        "_正": f"『{DAICHO}』タブ B列。ここを直してから、このファイルを作り直すこと。",
        "_並び": f"『{KYUMIN}』タブの最終発注が新しい順。",
        "_作り直し": "python3 tools/build-teikei-list.py → python3 tools/build-juchu.py → python3 tools/deploy-juchu.py",
        "_新規": "フォームには「＋ 新しい先を入れる」があり、一覧に無い先も入れられる。"
                 "新しい名前で届いたら tools/juchu-inbox.py が🔴で知らせるので、台帳に足してから作り直す。",
        "選択肢": hai,
    }
    if "--dry-run" in sys.argv:
        print(json.dumps(nakami, ensure_ascii=False, indent=1))
        return
    OUT.write_text(json.dumps(nakami, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"書き出しました: {OUT}  {len(hai)}件")
    for n in hai:
        print(f"   {junjo.get(n, '（休眠度タブに無し）'):>12}  {n}")


if __name__ == "__main__":
    main()
