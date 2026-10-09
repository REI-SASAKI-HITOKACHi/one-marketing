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

【手持ちの写真（ドライブ「施工写真_一次格納」）の仕分け】2026-10-09 第6回MTG オーナー指示で再開
  和真さんが iPhone から 一次格納/01_これから撮る分・02_過去分 に入れた写真を、撮影日時（EXIF）で
  お客様別（自動）/ <お客様名> / <施工日>_手持ち写真 / に「ショートカット」で並べる。
  元の写真は動かさない・消さない（web-inflow のブログ割り当て表が元の場所とファイル名 IMG_xxxx を使う）。
  ショートカットは容量を使わないのでサービスアカウントで作れる（オーナーの鍵は要らない）。
  規則は data/shashin-shiwake.json の kisoku（日付・時刻の幅・お客様名・顧客ID・根拠）。
  **日付と現場が一致したものだけ**規則にする：カレンダー（和真さん wk09015963）の予定時刻と内容、
  台帳（売上スプシの月タブ）の施工日の両方が合うもの。合わないものは mitokutei に書いて当てない。
  お客様名は台帳の表記から空白と「様」を除いたもの（asa-remind の照合と同じ）。顧客ID は顧客管理台帳の A列を
  電話番号で引いたもの。asa-remind は顧客ID が合うときだけ写真の URL を出す（同名の別人に出さない）。
  もう1つの置き場「【顧客共有】施工写真/onehitter」（16z5jr1…）は和真さんが現場別に作った法人・元請向けの
  フォルダで、すでに仕分け済み。サービスアカウントは読めないので Drive コネクタで見る（前回写真を探す先）。

  ◆ 週1の定例（毎週月曜の朝、CMO が流す）
   1. python3 tools/shashin-drive.py --midasu      # 一次格納でまだ仕分けていない写真を、日付・時刻のまとまりで出す
   2. 出たまとまりごとに、和真さんのカレンダー（Google Calendar コネクタ）と月タブで現場を特定し、
      data/shashin-shiwake.json の kisoku に1行足す（分からないものは mitokutei へ）
   3. python3 tools/shashin-drive.py --shiwake --dry-run → --shiwake   # ショートカットを作り、okyaku に URL を残す
   4. python3 tools/shashin-drive.py            # 作業完了フォームの写真（オーナーの鍵がある場合）
   5. docs/sheet-changelog.md に枚数を1行。data/ の2ファイルをコミット
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


SHIWAKE = ROOT / "data" / "shashin-shiwake.json"


def key(na: str) -> str:
    """okyaku のキー。asa-remind の照合（空白と「様」を除く）と同じ形。"""
    return re.sub(r"[\s　様]", "", na or "") or "名前なし"


def sa_token() -> str:
    return sc.access_token(sc.load_credentials(), "https://www.googleapis.com/auth/drive")


def temochi_ichiran(tok):
    """一次格納の写真を全部（id・名前・撮影日時）。"""
    kisoku = json.loads(SHIWAKE.read_text(encoding="utf-8"))
    out = []
    for fid in kisoku["moto"]:
        pt = None
        while True:
            q = {"q": f"'{fid}' in parents and trashed = false and mimeType contains 'image/'",
                 "fields": "nextPageToken,files(id,name,imageMediaMetadata(time),createdTime)",
                 "pageSize": "1000", "supportsAllDrives": "true", "includeItemsFromAllDrives": "true"}
            if pt:
                q["pageToken"] = pt
            r = drive(tok, "/files", q=q)
            for f in r.get("files", []):
                t = (f.get("imageMediaMetadata") or {}).get("time", "")
                m = re.match(r"(\d{4}):(\d{2}):(\d{2}) (\d{2}):(\d{2})", t)
                out.append({"id": f["id"], "name": f["name"],
                            "hi": f"{m[1]}-{m[2]}-{m[3]}" if m else "", "ji": f"{m[4]}:{m[5]}" if m else ""})
            pt = r.get("nextPageToken")
            if not pt:
                break
    return kisoku, out


def ate(kisoku, x):
    for k in kisoku["kisoku"]:
        if x["hi"] == k["hi"] and k["kara"] <= x["ji"] <= k["made"]:
            return k
    return None


def midasu() -> None:
    kiroku = json.loads(KIROKU.read_text(encoding="utf-8")) if KIROKU.exists() else {}
    sumi = kiroku.get("temochi", {})
    kisoku, fs = temochi_ichiran(sa_token())
    nokori = sorted((x for x in fs if x["id"] not in sumi), key=lambda x: (x["hi"], x["ji"]))
    print(f"一次格納の写真 {len(fs)}枚（重複込み）／仕分け済み {len(fs) - len(nokori)}枚／残り {len(nokori)}枚")
    mae = None
    for x in nokori:
        k = ate(kisoku, x)
        s = f"→ {k['na']}（規則あり・--shiwake で入る）" if k else ("撮影日時なし" if not x["hi"] else "規則なし")
        g = (x["hi"], x["ji"][:2], s)
        if g != mae:
            print(f"  {x['hi']} {x['ji']} {x['name']} … {s}")
            mae = g


def shiwake(dry: bool) -> None:
    kiroku = json.loads(KIROKU.read_text(encoding="utf-8")) if KIROKU.exists() else {"sumi": [], "okyaku": {}}
    kiroku.setdefault("temochi", {})
    tok = sa_token()
    kisoku, fs = temochi_ichiran(tok)
    cache, namae, kazu, nashi = {}, {}, {}, 0
    for x in sorted(fs, key=lambda x: (x["hi"], x["ji"], x["name"])):
        if x["id"] in kiroku["temochi"]:
            continue
        k = ate(kisoku, x)
        if not k:
            nashi += 1
            continue
        hi_f = f"{k['hi']}_手持ち写真"
        kazu[(k["na"], hi_f)] = kazu.get((k["na"], hi_f), 0) + 1
        if dry:
            continue
        f_ok = folder(tok, OYA, k["na"], cache)
        f_hi = folder(tok, f_ok, hi_f, cache)
        nk = (f_hi, x["name"])
        if nk not in namae:   # 同じ名前の二重アップロードは1つだけ並べる
            q = f"'{f_hi}' in parents and name = '{x['name']}' and trashed = false"
            r = drive(tok, "/files", q={"q": q, "fields": "files(id)", "supportsAllDrives": "true", "includeItemsFromAllDrives": "true"})
            namae[nk] = r["files"][0]["id"] if r.get("files") else drive(
                tok, "/files", "POST", {"name": x["name"], "parents": [f_hi], "mimeType": "application/vnd.google-apps.shortcut",
                                        "shortcutDetails": {"targetId": x["id"]}}, q={"fields": "id", "supportsAllDrives": "true"})["id"]
        kiroku["temochi"][x["id"]] = namae[nk]
        o = kiroku["okyaku"].setdefault(key(k["na"]), {})
        o["url"] = f"https://drive.google.com/drive/folders/{f_ok}"
        o["saigo"] = max(k["hi"], o.get("saigo", ""))
        if k.get("id"):
            o["id"] = k["id"]
        KIROKU.write_text(json.dumps(kiroku, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for (na, hf), n in sorted(kazu.items(), key=lambda z: z[0][1]):
        print(f"  {hf} {na} {n}枚")
    print(f"{'入れる予定' if dry else '仕分けた'}: {sum(kazu.values())}枚／規則なし（未特定・未判定）: {nashi}枚")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--midasu", action="store_true", help="一次格納の未仕分けを一覧")
    ap.add_argument("--shiwake", action="store_true", help="一次格納の写真を規則どおりショートカットで仕分け")
    a = ap.parse_args()
    if a.midasu:
        return midasu()
    if a.shiwake:
        return shiwake(a.dry_run)
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
        o = kiroku["okyaku"].setdefault(key(na), {})
        o.update({"url": f"https://drive.google.com/drive/folders/{f_okyaku}", "saigo": max(hi, o.get("saigo", ""))})
        sumi.add(s["id"])
        kiroku["sumi"] = sorted(sumi)
        KIROKU.write_text(json.dumps(kiroku, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("ドライブに入れました" if not a.dry_run else "\n--dry-run のため入れていません。")


if __name__ == "__main__":
    main()
