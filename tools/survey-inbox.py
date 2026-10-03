#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ご利用後アンケート（lp.onehitter.jp/survey/・Netlify Forms「survey」）に回答が届いたら、
業務連絡LINE（嶺・和真の2名）に知らせる。

【なぜ】
  2026-10-03 第5回MTG オーナー記入「アンケートの入力が完了したら和真と嶺への通知がほしい」。
  和真さん「アンケートのその後が見れるようにしてほしい」。（T061）

【知らせる中身】
  名字・メニュー・おすすめ度（0〜10）・仕上がり/対応（5段階）・次に気になる所と時期・紹介の意向・
  掲載の可否・ひとこと（先頭80字）・公開しないご意見（あれば先頭に 🔴）。
  **電話番号・住所は出さない。** 回答の全文は Netlify の管理画面にある。

【二重に知らせない】
  知らせた回答の ID だけを data/survey-tsuchi.json に残す（中身は残さない）。
  初めて動かすときは --hajime で、今ある回答を「知らせ済み」にして終える（昔の回答を一度に流さない）。

  python3 tools/survey-inbox.py --dry-run   # 何を知らせるか見るだけ（毎時点検が使う）
  python3 tools/survey-inbox.py             # 知らせる
  python3 tools/survey-inbox.py --hajime    # 今ある回答を知らせ済みにする（最初の1回だけ）
"""
import argparse
import importlib.util
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
FORM_ID = "6a9fa83ae90dd300085c81a0"   # one-hitter-lp（lp.onehitter.jp）の survey
KIROKU = ROOT / "data" / "survey-tsuchi.json"

_spec = importlib.util.spec_from_file_location("bi", ROOT / "tools" / "booking-inbox.py")
bi = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bi)


def sei(namae: str) -> str:
    n = (namae or "").replace("　", " ").strip()
    return n.split(" ")[0] if n else "（お名前なし）"


def kakunin(d: dict) -> str:
    gyo = [f"■ {sei(d.get('q10_name') or d.get('cust_name'))}さま"
           + (f"（{d.get('cust_menu') or d.get('q3_place')}）" if (d.get('cust_menu') or d.get('q3_place')) else "")]
    if (d.get("private_feedback") or "").strip():
        gyo.insert(0, "🔴 公開しないご意見あり：" + d["private_feedback"].strip()[:120])
    nps = d.get("q1_nps", "")
    gyo.append(f"おすすめ度：{nps}/10（{d.get('nps_segment', '')}）・仕上がり {d.get('q2_finish', '')}/5・対応 {d.get('q2_staff', '')}/5")
    if d.get("q5_next"):
        gyo.append(f"次に気になる所：{d['q5_next']}" + (f"（{d.get('q6_when')}" if d.get('q6_when') else "")
                   + (f"・{d.get('q6_discount')}引きの案内）" if d.get('q6_discount') else ("）" if d.get('q6_when') else "")))
    if d.get("q7_referral"):
        gyo.append(f"ご紹介：{d['q7_referral']}")
    if d.get("q8_publish"):
        gyo.append(f"掲載：{d['q8_publish']}")
    msg = (d.get("q9_message") or d.get("q3_comment") or "").replace("\n", " ").strip()
    if msg:
        gyo.append("ひとこと：" + msg[:80] + ("…" if len(msg) > 80 else ""))
    return "\n".join(gyo)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--hajime", action="store_true")
    a = ap.parse_args()

    subs = bi.netlify(f"/forms/{FORM_ID}/submissions")
    sumi = set(json.loads(KIROKU.read_text(encoding="utf-8"))) if KIROKU.exists() else set()
    if a.hajime:
        KIROKU.write_text(json.dumps(sorted({s["id"] for s in subs}), ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
        print(f"今ある {len(subs)}件を知らせ済みにしました")
        return
    atarashii = [s for s in subs if s["id"] not in sumi]
    print(f"未通知: {len(atarashii)}件")
    if not atarashii:
        return
    honbun = ("アンケートの回答が届きました（" + str(len(atarashii)) + "件）\n\n"
              + "\n\n".join(kakunin(s.get("data", {})) for s in sorted(atarashii, key=lambda s: s["created_at"]))
              + "\n\n全文は Netlify の管理画面（フォーム survey）にあります。")
    if a.dry_run:
        print(honbun)
        print("\n--dry-run のため知らせていません。")
        return
    r = subprocess.run(["python3", str(ROOT / "tools" / "line_client.py"), "push", honbun, "--midoku-ok"], check=False)
    if r.returncode != 0:
        sys.exit("🔴 業務連絡LINEに知らせられませんでした（知らせ済みにはしていません）")
    KIROKU.write_text(json.dumps(sorted(sumi | {s["id"] for s in atarashii}), ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
    print("業務連絡LINEに知らせました")


if __name__ == "__main__":
    main()
