#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""月次タブの「法人名」列（U列）を、氏名から機械で埋める。

【なぜ要るか】2026-09-19 に判明
  流入経路が「業務提携」の47件のうち、**45件で法人名（U列）が空**だった。
  提携先が誰かは、氏名の自由入力からしか読めない状態になっている。しかも表記が割れている。

    「株式会社レジェンド」「レジェンド様」「レジェンド様　湘南エミネンス寮」
    「チクブパッケージ　レジェンド様案件」「野田 レジェンド様案件」

  このままだと、提携先ごとの売上を数えるたびに人が目で寄せることになる。
  実際、顧客管理台帳では「タカラサービス」と「江戸前ハーブ　タカラサービス」が
  **別のお客様として2行に割れていた**（提携タブの17件とも数が合わない）。

【やること】
  `data/teikei-saki.json`（正＝『【毎月更新】リピート/業務提携』B列）の社名が
  氏名に含まれていたら、U列にその**正式名称**を入れる。

【絶対に守ること】
  ・**空のU列にだけ書く。**すでに入っている値は上書きしない
  ・**氏名・日付・金額・メニューには一切触らない**（過去の実績データを書き換えない）
  ・**推測で埋めない。**一覧に無い名前（個人の紹介者など）は空のまま残して、画面に出す
  ・実行前に控えを取る

    python3 tools/fill-teikei-houjin.py --dry-run   # 何を書くかを出すだけ
    python3 tools/fill-teikei-houjin.py            # 実際に書く
"""
import argparse
import datetime
import gzip
import json
import pathlib
import re
import sys
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import sheets_client as sc

SS = "1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64"
TEIKEI = ROOT / "data" / "teikei-saki.json"
HIKAE = ROOT / "data" / "sheets" / "backup"
# 列（B列を0とした相対位置）
C_HI, C_KEIRO, C_NA, C_KIN, C_HOUJIN = 1, 2, 3, 7, 19


def sagasu(shimei, saki_tachi):
    """氏名の中に提携先の社名が入っていたら、その正式名称を返す。
       いちばん長く一致したものを採る（『レジェンド』より『株式会社レジェンド』）。"""
    s = re.sub(r"[\s　]", "", str(shimei))
    atari = []
    for seishiki in saki_tachi:
        # 「株式会社」「合同会社」を外した芯でも見る（氏名側は略されていることが多い）
        shin = re.sub(r"(株式会社|合同会社|有限会社|様|さま)", "", seishiki)
        shin = re.sub(r"[\s　]", "", shin)
        if not shin:
            continue
        if shin in s:
            atari.append((len(shin), seishiki))
    if not atari:
        return ""
    return sorted(atari)[-1][1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    _t = json.loads(TEIKEI.read_text(encoding="utf-8"))
    saki = _t["選択肢"]
    # 別名（略称）。一覧の中で1社しか当たらないものだけを持つ。data/teikei-saki.json 参照
    BETSUMEI = {k: v for k, v in (_t.get("別名") or {}).items() if not k.startswith("_")}
    for _ryaku, _sei in BETSUMEI.items():
        _atari = [x for x in saki if _ryaku in x]
        if len(_atari) != 1:
            sys.exit(f"★別名「{_ryaku}」が一覧の{len(_atari)}社に当たります。"
                     f"一意でない別名は使えません。data/teikei-saki.json を直してください。")
    tok = sc.access_token(sc.load_credentials())

    def han(rng):
        """★タブ名に「/」が入っている（例：12月_売上/顧客）ので safe='' で全部escapeすること。"""
        return f"/{SS}/values/" + urllib.parse.quote(rng, safe="")

    rngs = [f"'{m}月_売上/顧客'!B4:U200" for m in range(1, 13)]
    q = [("ranges", r) for r in rngs]
    r = sc.call(tok, f"/{SS}/values:batchGet?" + urllib.parse.urlencode(q))

    kaku, nokori, hikae = [], [], {}
    for vr in r["valueRanges"]:
        tab = vr["range"].split("!")[0].strip("'")
        vals = vr.get("values", [])
        hikae[tab] = vals
        for i, row in enumerate(vals, start=4):
            row = list(row) + [""] * (20 - len(row))
            if str(row[C_KEIRO]).strip() != "業務提携":
                continue
            if str(row[C_HOUJIN]).strip():
                continue                      # すでに入っている。触らない
            seishiki = sagasu(row[C_NA], saki)
            if not seishiki:
                _s = re.sub(r"[\s\u3000]", "", str(row[C_NA]))
                for _ryaku, _sei in BETSUMEI.items():
                    if _ryaku in _s:
                        seishiki = _sei
                        break
            if seishiki:
                kaku.append((tab, i, str(row[C_NA]).strip(), seishiki, str(row[C_KIN]).strip()))
            else:
                nokori.append((tab, i, str(row[C_NA]).strip(), str(row[C_KIN]).strip()))

    print(f"法人名を入れられる行: {len(kaku)}件")
    for tab, i, na, se, kin in kaku:
        print(f"  {tab:14s} {i:3d}行  {na[:26]:28s} → {se}　{kin}")
    print(f"\n一覧に無いので**空のまま残す**行: {len(nokori)}件（推測で埋めません）")
    for tab, i, na, kin in nokori:
        print(f"  {tab:14s} {i:3d}行  {na[:26]:28s} {kin}")

    if a.dry_run:
        print("\n--dry-run のため書いていません。")
        return
    if not kaku:
        return

    HIKAE.mkdir(parents=True, exist_ok=True)
    p = HIKAE / f"月次タブ-法人名を入れる前-{datetime.datetime.now():%Y%m%d-%H%M%S}.json.gz"
    with gzip.open(p, "wt", encoding="utf-8") as f:
        json.dump({"取得": datetime.datetime.now().isoformat(), "values": hikae},
                  f, ensure_ascii=False)
    print(f"\n控え: {p.name}  {p.stat().st_size:,} bytes")

    data = [{"range": f"{tab}!U{i}", "values": [[se]]} for tab, i, _, se, _ in kaku]
    sc.call(tok, f"/{SS}/values:batchUpdate", method="POST",
            payload={"valueInputOption": "USER_ENTERED", "data": data})
    print(f"{len(kaku)}件の法人名を入れました。氏名・日付・金額は1文字も触っていません。")


if __name__ == "__main__":
    main()
