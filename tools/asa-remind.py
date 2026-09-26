#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""毎朝、前日までの入力漏れを業務連絡グループLINEへ1通で知らせる。

  オーナー指示（2026-09-26・和真対応可否一覧 No.31 の F列）
    「入力漏れがあれば翌日にマーケ部長がLINEでリマインドしてほしい」（現金で受け取った売上の当日記録）
  オーナー指示（2026-09-26・MTGシート F364 の件）
    「未入力をリマインドできるようにしたい」（作業完了フォーム）

  対象（どちらも 2026-09-26 以降〜昨日の施工）
    1. 台帳（◯月_売上/顧客）で O列「入金経路」が空欄の行
    2. 作業完了フォームがまだ届いていない施工（tools/kanryo_mishin.py）
  どちらも0件なら何も送らない。

    python3 tools/asa-remind.py --dry-run
    python3 tools/asa-remind.py
"""
import argparse
import datetime
import pathlib
import subprocess
import sys
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import sheets_client as sc  # noqa: E402
import kanryo_mishin as km  # noqa: E402

JST = datetime.timezone(datetime.timedelta(hours=9))


def nyukin_mikinyu(kinou):
    tok = sc.access_token(sc.load_credentials())
    tsuki = sorted({km.KITEN.month, kinou.month}) if kinou >= km.KITEN else []
    if not tsuki:
        return []
    qs = "&".join("ranges=" + urllib.parse.quote(f"'{m}月_売上/顧客'!A4:U504", safe="") for m in range(tsuki[0], tsuki[-1] + 1))
    vr = sc.call(tok, f"/{km.SS}/values:batchGet?{qs}")["valueRanges"]
    out = []
    for m, v in zip(range(tsuki[0], tsuki[-1] + 1), vr):
        for i, r in enumerate(v.get("values", []), 4):
            r = r + [""] * 21
            if not r[1].strip() or not r[4].strip():
                continue
            try:
                d = datetime.date(*map(int, r[2].strip().split("/")))
            except Exception:
                continue
            if km.KITEN <= d <= kinou and not r[14].strip():
                out.append({"d": d, "n": r[4].strip(), "k": r[8].strip(), "r": f"{m}月_売上/顧客 {i}行目"})
    return sorted(out, key=lambda x: x["d"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    kyou = datetime.datetime.now(JST).date()
    kinou = kyou - datetime.timedelta(days=1)

    nk = nyukin_mikinyu(kinou)
    kf = [x for x in km.ichiran(kinou)]          # 昨日までの施工で完了フォーム未入力
    print(f"入金経路が空欄: {len(nk)}件／作業完了フォーム未入力: {len(kf)}件（{km.KITEN}〜{kinou}）")
    if not nk and not kf:
        print("お知らせなし")
        return
    gyo = ["【入力のお願い】昨日までの施工で、まだ入っていないものがあります"]
    if nk:
        gyo += ["", "■ 入金（現金・クレカ・請求書など）が売上シートに未記入"]
        gyo += [f"・{x['d'].month}/{x['d'].day} {x['n']} さま {x['k']}" for x in nk]
        gyo += ["→ 売上シートの「入金経路」を選んでください（現金ならその日のうちに）"]
    if kf:
        gyo += ["", "■ 作業完了フォームが未入力"]
        gyo += [f"・{x['d'][5:].replace('-', '/')} {x['n']} さま" for x in kf]
        import importlib.util
        spec = importlib.util.spec_from_file_location("ko", ROOT / "tools" / "kanryo-okuru.py")
        ko = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ko)
        gyo += ["→ こちらから、お客様を選んで入れてください", ko.kaku({"p": km.ichiran(), "st": 1})]
    txt = "\n".join(gyo)
    print(txt)
    if a.dry_run:
        print("\n--dry-run のため送っていません。")
        return
    f = ROOT / "data" / "tmp-asa-remind.txt"
    f.write_text(txt, encoding="utf-8")
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "line_client.py"), "push", "--file", str(f), "--midoku-ok"],
                       capture_output=True, text=True)
    f.unlink(missing_ok=True)
    print("送りました" if r.returncode == 0 else f"🔴 送れませんでした: {r.stderr.strip()[:200]}")


if __name__ == "__main__":
    main()
