#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""作業完了フォームが「まだ入っていない」施工の一覧を作る。

  オーナー指示（2026-09-26・MTGシート F364 とチャット）
    「QRの次のページ（２ページ目）の顧客名入力欄は当日のスケジュールからプルダウンで顧客名を表示、
      選択可能な状態にしたい。表記ゆれ等防止のため。」
    「顧客名の選択肢は今日以降の未作成者全員を出して、未入力をリマインドできるようにしたい」

  対象 … 台帳（◯月_売上/顧客）の施工日付が KITEN（2026-09-26）〜今日 の行
  除く … 作業完了フォームがもう届いている行（台帳の行、または 氏名＋施工日付 で突き合わせ）
         お名前に「テスト」を含む提出は、届いたものとして数えない

  この一覧は LINE で送るリンクの # のうしろにだけ入れる（tools/kanryo-okuru.py）。サーバには置かない。

    python3 tools/kanryo_mishin.py        # 一覧を出す
"""
import datetime
import json
import pathlib
import re
import sys
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import sheets_client as sc  # noqa: E402

SS = "1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64"
KITEN = datetime.date(2026, 9, 26)          # オーナー指示の日＝「今日以降」の起点
JST = datetime.timezone(datetime.timedelta(hours=9))
YOTEI = ROOT / "data" / "kanryo-yotei.json"
SAIDAI = 30                                 # リンクが長くなりすぎないよう、古い順に30件まで


def seiki(na):
    return re.sub(r"[\s　]|様|さま|さん", "", str(na or ""))


def teishutsu_zumi():
    """作業完了フォームに届いたもの（Netlify）から、済みの印を作る。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location("kanryo_inbox", ROOT / "tools" / "kanryo-inbox.py")
    ki = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ki)
    rows, pairs = set(), set()
    for f in [f for f in ki.netlify(f"/sites/{ki.SITE_ID}/forms") if f["name"] == ki.FORM]:
        for s in ki.netlify(f"/forms/{f['id']}/submissions"):
            d = s.get("data") or {}
            if "テスト" in str(d.get("氏名", "")):
                continue
            if d.get("台帳"):
                rows.add(str(d["台帳"]).strip())
            pairs.add((seiki(d.get("氏名")), str(d.get("施工日付", "")).replace("/", "-")))
    return rows, pairs


def ichiran(kyou=None):
    kyou = kyou or datetime.datetime.now(JST).date()
    if kyou < KITEN:
        return []
    tok = sc.access_token(sc.load_credentials())
    tsuki = []
    y, m = KITEN.year, KITEN.month
    while (y, m) <= (kyou.year, kyou.month):
        if y == 2026:                       # 2026年シートだけ（2027年は別シートになったら足す）
            tsuki.append(m)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    qs = "&".join("ranges=" + urllib.parse.quote(f"'{mm}月_売上/顧客'!A4:U504", safe="") for mm in tsuki)
    vr = sc.call(tok, f"/{SS}/values:batchGet?{qs}&valueRenderOption=FORMATTED_VALUE")["valueRanges"]
    yotei = json.loads(YOTEI.read_text(encoding="utf-8")) if YOTEI.exists() else []
    by_row = {str(x.get("台帳", "")).strip(): x for x in yotei}
    zumi_rows, zumi_pairs = teishutsu_zumi()
    out = []
    for mm, v in zip(tsuki, vr):
        for i, r in enumerate(v.get("values", []), 4):
            r = r + [""] * 21
            shurui, hi, na = r[1].strip(), r[2].strip(), r[4].strip()
            if not shurui or not na or not re.match(r"^\d{4}/\d{1,2}/\d{1,2}$", hi):
                continue
            d = datetime.date(*map(int, hi.split("/")))
            if not (KITEN <= d <= kyou):
                continue
            ref = f"{mm}月_売上/顧客 {i}行目"
            if ref in zumi_rows or (seiki(na), d.isoformat()) in zumi_pairs:
                continue
            y0 = by_row.get(ref, {})
            kin = re.sub(r"[^\d]", "", r[8])
            out.append({"i": y0.get("id", ""), "r": ref, "n": na,
                        "s": "本舗" if shurui == "本舗" else "One Hitter",
                        "d": d.isoformat(), "t": y0.get("開始時刻", ""),
                        "m": y0.get("メニュー") or ([r[9]] if r[9] else []), "k": y0.get("金額") or kin})
    out.sort(key=lambda x: (x["d"], x["t"] or "99"))
    return out[:SAIDAI]


if __name__ == "__main__":
    ls = ichiran()
    print(f"作業完了フォームが未入力：{len(ls)}名（{KITEN.isoformat()} 以降〜今日）")
    for x in ls:
        print(f"  {x['d']} {x['t'] or '     '} {x['n']} さま（{'・'.join(x['m'])}）{x['r']}")
