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
    3. 今日の施工のうち、2回目以降のお客様（リピーター）の前回の情報（T064）
       オーナー（2026-10-03 第5回MTG）「リピーターなど2回目以降のお客様に施工に入る日は当日の朝に
       前回施工した写真が保存されているドライブURLをグループLINEへ送るようにしてほしい」
       台帳（顧客管理台帳）と電話番号→名前の順で突き合わせ、回数・前回の日付・これまでのメニュー・クレーム履歴を出す。
       写真フォルダの URL は tools/shashin-drive.py が入れたもの（data/shashin-drive.json）があれば付ける。
       社内（嶺・和真）あての連絡なので、お客様の名乗りの照合は対象外。
  どれも0件なら何も送らない。

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


def kyou_ripi(kyou):
    """今日の施工で、台帳上2回目以降のお客様。"""
    import json
    import re
    tok = sc.access_token(sc.load_credentials())
    # 台帳の「受注回数」「最終施工日」には先の予約も入っている（例：12月の定期便）。
    # 今年の月タブを全部読み、今日より前の施工だけで「前回」を決め、先の予約の分を回数から引く。
    rs = [f"'{m}月_売上/顧客'!A4:T504" for m in range(1, 13)] + ["'顧客管理台帳'!A16:AG3000"]
    qs = "&".join("ranges=" + urllib.parse.quote(r, safe="") for r in rs)
    vr = [v.get("values", []) for v in sc.call(tok, f"/{km.SS}/values:batchGet?{qs}")["valueRanges"]]
    tsuki, daicho = vr[kyou.month - 1], vr[12]
    zenbu = [(r + [""] * 20) for v in vr[:12] for r in v]
    kyou_s = f"{kyou.year}/{kyou.month:02d}/{kyou.day:02d}"
    num = lambda x: re.sub(r"\D", "", x or "")
    mei = lambda x: re.sub(r"[\s　様]", "", x or "")
    shashin = {}
    f = ROOT / "data" / "shashin-drive.json"
    if f.exists():
        shashin = json.loads(f.read_text(encoding="utf-8")).get("okyaku", {})
    out = []
    for r in tsuki:
        r = r + [""] * 20
        if r[2].strip() != kyou_s or not r[4].strip():
            continue
        tel, na = num(r[5]), mei(r[4])
        hit = None
        for d in daicho:
            d = d + [""] * 33
            if tel and len(tel) >= 10 and num(d[3]) == tel:
                hit = d
                break
        if hit is None:
            for d in daicho:
                d = d + [""] * 33
                if na and (mei(d[1]) == na or na in [mei(x) for x in d[31].split("／")]):
                    hit = d
                    break
        if hit is None:
            continue
        onaji = [z[2].strip() for z in zenbu
                 if (tel and len(tel) >= 10 and num(z[5]) == tel) or (na and mei(z[4]) == na)]
        mae = sorted(x for x in onaji if re.fullmatch(r"\d{4}/\d{2}/\d{2}", x) and x < kyou_s)
        saki = sum(1 for x in onaji if re.fullmatch(r"\d{4}/\d{2}/\d{2}", x) and x > kyou_s)
        kai = int(num(hit[6]) or 0)
        saigo = hit[11].strip()
        konkai = (kai - saki) if saigo >= kyou_s else kai + 1   # 今日の分が台帳に入っていなければ足す
        zenkai = mae[-1] if mae else (saigo if saigo < kyou_s else "")
        if konkai < 2 or not (zenkai or hit[10].strip() < kyou_s):
            continue
        out.append({"n": r[4].strip(), "menu": r[9].strip() or r[3].strip(), "kai": konkai,
                    "shokai": hit[10].strip(), "saigo": zenkai,
                    "uchiwake": hit[30].strip(), "claim": hit[32].strip(),
                    "url": (shashin.get(na) or {}).get("url", "")})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    kyou = datetime.datetime.now(JST).date()
    kinou = kyou - datetime.timedelta(days=1)

    nk = nyukin_mikinyu(kinou)
    kf = [x for x in km.ichiran(kinou)]          # 昨日までの施工で完了フォーム未入力
    rp = kyou_ripi(kyou)
    print(f"入金経路が空欄: {len(nk)}件／作業完了フォーム未入力: {len(kf)}件（{km.KITEN}〜{kinou}）／今日のリピーター: {len(rp)}件")
    if not nk and not kf and not rp:
        print("お知らせなし")
        return
    gyo = []
    if rp:
        gyo += ["【今日のリピーターさま】前回の内容です"]
        for x in rp:
            gyo += ["", f"■ {x['n']} さま（{x['kai']}回目・今日：{x['menu']}）"]
            gyo += [f"前回 {x['saigo']}" if x["saigo"] else f"初回 {x['shokai']}"]
            if x["uchiwake"]:
                gyo += [f"これまで：{x['uchiwake'][:80]}"]
            if x["claim"]:
                gyo += [f"🔴 過去のクレーム：{x['claim'][:120]}"]
            if x["url"]:
                gyo += [f"前回までの写真：{x['url']}"]
    if nk or kf:
        gyo += ([""] if gyo else []) + ["【入力のお願い】昨日までの施工で、まだ入っていないものがあります"]
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
