#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""作業完了フォームのURLを、業務連絡グループLINEへ送る。

  オーナー決定（2026-09-19・MTGシート G245）
    「施工開始時刻の30分後にマーケ部長が業務連絡グループLINEへ作業完了フォームを送信する」

  毎時のルーティンから呼ぶ。開始から30分を過ぎた受注だけを、1件1通で送る。

    python3 tools/kanryo-okuru.py --dry-run   # 何を送るかを出すだけ
    python3 tools/kanryo-okuru.py             # 実際に送る

  ★お客様の情報（お名前・メニュー・金額）は、URLの「#」のうしろに入れる。
    # のうしろはサーバへ送られないので、社内ホストにお客様の情報が残らない。
    材料は data/kanryo-yotei.json（tools/juchu-inbox.py が作る）。**手元にだけ置く。**
"""
import argparse
import base64
import datetime
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
YOTEI = ROOT / "data" / "kanryo-yotei.json"
SUMI = ROOT / "data" / "kanryo-okurizumi.json"
BASE = "https://oh-naibu-sms-k7q3x.netlify.app/kanryo/"
JST = datetime.timezone(datetime.timedelta(hours=9))
SAKI_FUN = 30   # 開始から何分後に送るか


def url(y):
    d = {"i": y["id"], "r": y.get("台帳", ""), "n": y.get("氏名", ""),
         "s": y.get("売上種類", ""), "d": y.get("施工日付", ""), "t": y.get("開始時刻", ""),
         "m": y.get("メニュー", []), "k": y.get("金額", "")}
    b = base64.urlsafe_b64encode(json.dumps(d, ensure_ascii=False).encode()).decode().rstrip("=")
    return BASE + "#" + b


def honbun(y):
    return "\n".join([
        "【作業完了フォーム】" + y.get("氏名", "") + " さま",
        f"{y.get('施工日付','')} {y.get('開始時刻','')} 開始"
        + ("／おそうじ本舗" if y.get("売上種類") == "本舗" else "／ワンヒッター"),
        "／".join(y.get("メニュー", [])),
        "",
        "作業が終わったら、こちらから入れてください。",
        url(y),
        "",
        "最初の画面はお客様に見せるものです（アンケートのQR）。",
        "お客様が回答されている間に、次回のご予約をご提案ください。",
        "下の「次へ（スタッフ用）」で入力画面に変わります。",
    ])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--all", action="store_true", help="30分の縛りを外して全部送る")
    a = ap.parse_args()

    if not YOTEI.exists():
        print("送る材料がありません（data/kanryo-yotei.json）。先に tools/juchu-inbox.py を動かしてください。")
        return
    yotei = json.loads(YOTEI.read_text(encoding="utf-8"))
    sumi = set(json.loads(SUMI.read_text(encoding="utf-8"))) if SUMI.exists() else set()
    ima = datetime.datetime.now(JST)

    okuru = []
    for y in yotei:
        if y["id"] in sumi:
            continue
        try:
            h, mi = (int(x) for x in str(y.get("開始時刻", "09:00"))[:5].split(":"))
            kai = datetime.datetime.fromisoformat(y["施工日付"]).replace(
                hour=h, minute=mi, tzinfo=JST)
        except Exception:
            print(f"  ⚠ 日時が読めないので飛ばします: {y['id']}")
            continue
        if not a.all and ima < kai + datetime.timedelta(minutes=SAKI_FUN):
            continue
        if ima > kai + datetime.timedelta(days=2):
            # 2日以上たっているものは送らない（取りこぼしを延々と送り続けないため）
            print(f"  － 古いので送りません: {y.get('氏名')} {y.get('施工日付')}")
            sumi.add(y["id"])
            continue
        okuru.append(y)

    print(f"送る対象: {len(okuru)}件（未送信 {len([y for y in yotei if y['id'] not in sumi])}件中）")
    for y in okuru:
        print(f"  {y.get('施工日付')} {y.get('開始時刻')} {y.get('氏名')} → {url(y)[:80]}…")
    if a.dry_run:
        print("\n--dry-run のため送っていません。")
        return
    for y in okuru:
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "line_client.py"), "push", honbun(y)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            print(f"  🔴 送れませんでした: {y.get('氏名')} {r.stderr.strip()[:200]}")
            continue
        print(f"  送りました: {y.get('氏名')}")
        sumi.add(y["id"])
    SUMI.write_text(json.dumps(sorted(sumi), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
