#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""アルバイト用の業務報告フォーム（社内ホスト /baito/・Netlify Forms「baito」）が送られたら、
業務連絡LINE（嶺・和真の2名）に知らせる（T062）。

  2026-10-03 第5回MTG オーナー「アルバイト用の業務報告フォームが欲しい。これも二人へ通知が必要」。

知らせる中身：現場（地域・メニュー）・終了時刻・写真の枚数・クレームの有無・今日の報告（先頭200字）。
写真は Netlify に残る（管理画面のフォーム baito／baito-shashin）。知らせた ID だけを data/baito-tsuchi.json に残す。

  python3 tools/baito-inbox.py --dry-run   # 見るだけ（毎時点検が使う）
  python3 tools/baito-inbox.py             # 知らせる
"""
import argparse
import importlib.util
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
FORM_ID = "6ac0cfcb45b99700084c25a2"   # oh-naibu-sms-k7q3x（社内用）の baito
KIROKU = ROOT / "data" / "baito-tsuchi.json"

_spec = importlib.util.spec_from_file_location("bi", ROOT / "tools" / "booking-inbox.py")
bi = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bi)


def matome(d: dict) -> str:
    gyo = [f"■ {d.get('氏名') or '（現場の記入なし）'}"]
    if d.get("クレーム") == "あり":
        gyo.insert(0, "🔴 クレームあり：" + (d.get("クレーム内容") or "").strip()[:150])
    gyo.append(f"終了 {d.get('作業終了時刻') or '—'}・写真 {d.get('写真の枚数') or 0}枚")
    hou = (d.get("迷ったこと") or "").replace("\n", " ").strip()
    if hou:
        gyo.append("報告：" + hou[:200] + ("…" if len(hou) > 200 else ""))
    if (d.get("お客様周辺情報") or "").strip():
        gyo.append("お客様のこと：" + d["お客様周辺情報"].strip()[:120])
    return "\n".join(gyo)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    subs = bi.netlify(f"/forms/{FORM_ID}/submissions")
    sumi = set(json.loads(KIROKU.read_text(encoding="utf-8"))) if KIROKU.exists() else set()
    atarashii = [s for s in subs if s["id"] not in sumi]
    print(f"未通知: {len(atarashii)}件")
    if not atarashii:
        return
    honbun = ("アルバイトの業務報告が届きました（" + str(len(atarashii)) + "件）\n\n"
              + "\n\n".join(matome(s.get("data", {})) for s in sorted(atarashii, key=lambda s: s["created_at"]))
              + "\n\n写真は Netlify の管理画面（フォーム baito）にあります。")
    if a.dry_run:
        print(honbun)
        print("\n--dry-run のため知らせていません。")
        return
    r = subprocess.run(["python3", str(ROOT / "tools" / "line_client.py"), "push", honbun, "--midoku-ok"], check=False)
    if r.returncode != 0:
        sys.exit("🔴 業務連絡LINEに知らせられませんでした（知らせ済みにはしていません）")
    KIROKU.write_text(json.dumps(sorted(sumi | {s["id"] for s in atarashii}), ensure_ascii=False) + "\n", encoding="utf-8")
    print("業務連絡LINEに知らせました")


if __name__ == "__main__":
    main()
