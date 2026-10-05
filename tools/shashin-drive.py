#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""作業完了フォーム（kanryo／kanryo-shashin）の施工写真を、Google ドライブの
「施工写真_お客様別（自動）」フォルダに、お客様ごと・施工日ごとに入れる（T056・T064）。

【なぜ】
  2026-10-03 第5回MTG オーナー記入：
   「フォルダ仕訳は週一でいいので定例業務としてマーケ部長が対応して」
   「リピーターなど2回目以降のお客様に施工に入る日は当日の朝に前回施工した写真が保存されている
     ドライブURLをグループLINEへ送るようにしてほしい。作業や接客のスムーズ化に貢献できる」
  写真の元は Netlify の提出にしか無く（このリポジトリと作業環境には残さない）、お客様ごとにまとまっていなかった。

【置き方】
  施工写真_お客様別（自動）/ <お客様名（空白なし）> / <施工日>_<受注ID の先頭8字> / 01.jpg …
  お客様のフォルダの URL を data/shashin-drive.json の okyaku に残す（朝のリマインドが使う）。
  フォルダは嶺・和真・サービスアカウントが編集できる（上のフォルダから引き継ぎ）。

  python3 tools/shashin-drive.py --dry-run   # 何を入れるか見るだけ
  python3 tools/shashin-drive.py             # 入れる（週1回。急ぐときは随時）
"""
import argparse
import importlib.util
import json
import pathlib
import re
import sys
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import sheets_client as sc  # noqa: E402

OYA = "16s1Tgj0qsu2gDEj_qipZ_O9quzupH7RR"   # 施工写真_お客様別（自動）
KIROKU = ROOT / "data" / "shashin-drive.json"
SITE_ID = "f1b64c82-173e-4b1a-9e7f-bf24026fed0e"   # 社内用ホスト（作業完了フォーム）
DRIVE = "https://www.googleapis.com/drive/v3"
UP = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id&supportsAllDrives=true"

_spec = importlib.util.spec_from_file_location("bi", ROOT / "tools" / "booking-inbox.py")
bi = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bi)


KAGI = pathlib.Path.home() / ".config" / "one-hitter" / "drive.json"


def token() -> str:
    """写真を置くのはオーナーのドライブ。サービスアカウントは容量を持てない（403 storageQuota）ため、
    オーナーのアカウントで許可した鍵（~/.config/one-hitter/drive.json：client_id / client_secret / refresh_token、
    範囲 drive.file か drive）を使う。リポジトリには置かない。"""
    if not KAGI.exists():
        sys.exit(f"🔴 {KAGI} がありません。オーナーのアカウントでドライブの鍵を取ってください（docs の手順・GBP と同じ Playground）")
    k = json.loads(KAGI.read_text(encoding="utf-8"))
    d = urllib.parse.urlencode({"client_id": k["client_id"], "client_secret": k["client_secret"],
                                "refresh_token": k["refresh_token"], "grant_type": "refresh_token"}).encode()
    with urllib.request.urlopen("https://oauth2.googleapis.com/token", d, timeout=30) as r:
        return json.loads(r.read())["access_token"]


def mei(na: str) -> str:
    return re.sub(r"[\s　]", "", na or "") or "名前なし"


def drive(tok, path, method="GET", body=None, q=None):
    url = DRIVE + path + ("?" + urllib.parse.urlencode(q) if q else "")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read() or b"{}")


def folder(tok, oya, na, cache):
    key = oya + "/" + na
    if key in cache:
        return cache[key]
    q = f"'{oya}' in parents and name = '{na.replace(chr(39), '')}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    r = drive(tok, "/files", q={"q": q, "fields": "files(id)", "supportsAllDrives": "true", "includeItemsFromAllDrives": "true"})
    if r.get("files"):
        fid = r["files"][0]["id"]
    else:
        fid = drive(tok, "/files", "POST", {"name": na, "parents": [oya], "mimeType": "application/vnd.google-apps.folder"},
                    q={"fields": "id", "supportsAllDrives": "true"})["id"]
    cache[key] = fid
    return fid


def upload(tok, oya, na, data: bytes):
    b = "oh-shashin-boundary"
    meta = json.dumps({"name": na, "parents": [oya]}).encode()
    body = (f"--{b}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode() + meta
            + f"\r\n--{b}\r\nContent-Type: image/jpeg\r\n\r\n".encode() + data + f"\r\n--{b}--".encode())
    req = urllib.request.Request(UP, data=body, method="POST",
                                 headers={"Authorization": "Bearer " + tok, "Content-Type": f"multipart/related; boundary={b}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())["id"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    kiroku = json.loads(KIROKU.read_text(encoding="utf-8")) if KIROKU.exists() else {"sumi": [], "okyaku": {}}
    sumi = set(kiroku["sumi"])
    forms = {f["name"]: f["id"] for f in bi.netlify(f"/sites/{SITE_ID}/forms") if f["name"] in ("kanryo", "kanryo-shashin")}
    subs = []
    for nm, fid in forms.items():
        for s in bi.netlify(f"/forms/{fid}/submissions"):
            if s["id"] not in sumi:
                subs.append((nm, s))
    print(f"まだドライブに無い提出: {len(subs)}件")
    if not subs:
        return
    tok = None if a.dry_run else token()
    cache = {}
    for nm, s in sorted(subs, key=lambda x: x[1]["created_at"]):
        d = s.get("data") or {}
        na, hi = mei(d.get("氏名")), (d.get("施工日付") or s["created_at"][:10])
        hajime = int(re.sub(r"\D", "", str(d.get("開始番号", "1"))) or 1) if nm == "kanryo-shashin" else 1
        ran = sorted((int(re.sub(r"\D", "", k) or 0), v) for k, v in d.items()
                     if k.startswith("施工写真") and isinstance(v, dict) and v.get("url"))
        jid = (d.get("受注ID") or s["id"])[:8]
        print(f"── {na}／{hi}（{nm}）写真 {len(ran)}枚")
        if a.dry_run:
            continue
        f_okyaku = folder(tok, OYA, na, cache)
        f_hi = folder(tok, f_okyaku, f"{hi}_{jid}", cache)
        ochi = 0
        for j, (_, v) in enumerate(ran):
            try:
                with urllib.request.urlopen(v["url"], timeout=120) as r:
                    upload(tok, f_hi, f"{hajime + j:02d}.jpg", r.read())
            except Exception as e:
                ochi += 1
                print(f"   ⚠ {hajime + j}枚目を入れられませんでした: {e}")
        if ochi:
            print("   → 入れられない写真があったので、この提出は「入れ済み」にしません（次回もう一度）")
            continue
        kiroku["okyaku"][na] = {"url": f"https://drive.google.com/drive/folders/{f_okyaku}", "saigo": max(hi, kiroku["okyaku"].get(na, {}).get("saigo", ""))}
        sumi.add(s["id"])
        kiroku["sumi"] = sorted(sumi)
        KIROKU.write_text(json.dumps(kiroku, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("ドライブに入れました" if not a.dry_run else "\n--dry-run のため入れていません。")


if __name__ == "__main__":
    main()
