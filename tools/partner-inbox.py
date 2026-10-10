#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""提携先さまの専用ページ（lp.onehitter.jp/partner/<鍵>/・Netlify Forms「partner」）から依頼が届いたら、
業務連絡LINE（嶺・和真の2名）に知らせる。

【なぜ】
  2026-10-10 タカラサービス様の専用ページ（/partner/takara-7q2m/）を本番に出した（オーナー「僕が操作できる状態で出して」）。
  送られた依頼は Netlify の「partner」フォームに入るが、取り込む道具が無く、誰も気づかない状態だった。
  提携先の依頼は「日時が決まりしだい御社へ確定のご連絡」と約束しているので、毎時の点検で拾って和真さんへ回す。

【知らせる中身】
  提携先・種別（見積依頼／現調依頼）・内容・内訳・目安金額・希望日時・現場の住所（区市まで）・現場のお名前・ご担当・ご要望（先頭80字）。
  **お客様の電話は出さない**（Netlify の管理画面で見る）。テストの送信（お客様名・ご要望に「テスト」）は【テスト】と付けて知らせる。

【二重に知らせない】
  知らせた ID だけを data/partner-tsuchi.json に残す（中身は残さない）。

  python3 tools/partner-inbox.py --dry-run   # 何を知らせるか見るだけ（毎時点検が使う）
  python3 tools/partner-inbox.py             # 知らせる
"""
import argparse
import importlib.util
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE_ID = "dad26366-3dfb-4404-9e0c-bb6b50b893c9"   # one-hitter-lp（lp.onehitter.jp）
FORM = "partner"
KIROKU = ROOT / "data" / "partner-tsuchi.json"

_spec = importlib.util.spec_from_file_location("ji", ROOT / "tools" / "juchu-inbox.py")
ji = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ji)


def honbun(d: dict) -> str:
    test = any("テスト" in str(d.get(k, "")) for k in ("お客様名", "ご要望", "現場のお名前"))
    g = [("【テスト】" if test else "") + f"■ 提携先からのご依頼：{d.get('提携先', '')}（{d.get('種別', '')}）"]
    for k in ("内容", "内訳", "目安金額", "高速代の目安", "希望日時", "作業時間の目安", "移動時間の目安",
              "現場の住所", "現場のお名前", "お客様名", "ご担当", "きっかけ"):
        v = str(d.get(k, "")).replace("\n", " ").strip()
        if v:
            g.append(f"{k}：{v[:120]}")
    yo = str(d.get("ご要望", "")).replace("\n", " ").strip()
    if yo:
        g.append("ご要望：" + yo[:80] + ("…" if len(yo) > 80 else ""))
    g.append("→ 日時が決まりしだい、提携先へ確定のご連絡（お客様の電話は Netlify の管理画面）")
    return "\n".join(g)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    forms = [f for f in ji.netlify(f"/sites/{SITE_ID}/forms") if f["name"] == FORM]
    subs = []
    for f in forms:
        subs += ji.netlify(f"/forms/{f['id']}/submissions")
    sumi = set(json.loads(KIROKU.read_text(encoding="utf-8"))) if KIROKU.exists() else set()
    atarashii = [s for s in subs if s["id"] not in sumi]
    print(f"未通知: {len(atarashii)}件")
    for s in atarashii:
        print("\n" + honbun(s.get("data") or {}))
    if a.dry_run or not atarashii:
        return
    for s in atarashii:
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "line_client.py"), "push", honbun(s.get("data") or {})],
                           capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(f"LINE に送れませんでした（{s['id']}）: {r.stdout}{r.stderr}")
        sumi.add(s["id"])
        KIROKU.write_text(json.dumps(sorted(sumi), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n知らせました: {len(atarashii)}件")


if __name__ == "__main__":
    main()
