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

  【作業完了フォームの写真の入れ方】2026-10-09 から（サービスアカウントは容量0で写真を置けないため）
   ① このスクリプト（サービスアカウント）が、提出ごとにお客様を特定する：
      提出の「台帳」の行（並べ替わっていたら 氏名＋施工日 で月タブを引き直す）→ その行の電話で顧客管理台帳の顧客ID。
      電話が無く名字だけ（2字以下）・行が1つに決まらない・okyaku に同名で別の顧客ID がある → 「未特定」で入れない。
   ② フォルダを作り（フォルダは容量を使わないのでサービスアカウントで作れる）、
      シート「施工写真_お客様別（自動）/_写真取り込み待ち（自動・消さない）」（MACHI）に1枚1行で載せる。
      載せた提出は data/shashin-drive.json の machi に入る。
   ③ オーナーのアカウントで動く Apps Script（tools/shashin-torikomi.gs、1時間ごと）が、写真を URL から取って保存する。
   ④ 次にこのスクリプトを流したとき、全部「済」になった提出を sumi に移し、okyaku に URL・最終施工日・顧客ID を残す。
      「失敗」の行は状態を空に戻して、Apps Script にもう一度取らせる。

  python3 tools/shashin-drive.py --dry-run   # 何を載せるか・未特定を見るだけ
  python3 tools/shashin-drive.py             # 回収（済→okyaku）と、新しい提出の追加（週1回。急ぐときは随時）

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
   4. python3 tools/shashin-drive.py            # 作業完了フォームの写真：先週載せた分の回収（済→okyaku）と今週の提出の追加
      ・「待ち」が前の週から減っていない → Apps Script が止まっている（未設置・権限切れ）。CMO からオーナーへ
        （入れ方は tools/shashin-torikomi.gs の冒頭。オーナーの操作は「setup を実行 → 許可」の1回）
      ・「未特定」が出たら、和真さんのカレンダーと月タブで確かめ、台帳の電話番号か氏名を直してから流し直す
        （推測で別のお客様のフォルダに入れない）
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
MACHI = "1-Q3F4-FvLxvkKwhYFx3W476pjYTOOF32ycUVRTCCGNY"   # 施工写真_お客様別（自動）/_写真取り込み待ち（自動・消さない）
SS = "1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64"      # 売上スプシ（月タブ・顧客管理台帳）

_spec = importlib.util.spec_from_file_location("bi", ROOT / "tools" / "booking-inbox.py")
bi = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bi)


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


def kana(x: str) -> str:
    return re.sub(r"[\s　様]", "", x or "")


def num(x: str) -> str:
    return re.sub(r"\D", "", x or "")


def daicho_yomu(tok):
    """月タブ（1〜12月）と顧客管理台帳。月タブ：C=施工日 E=氏名 F=電話。台帳：A=顧客ID B=氏名 D=電話 AF=別名。"""
    rs = [f"'{m}月_売上/顧客'!A4:T504" for m in range(1, 13)] + ["'顧客管理台帳'!A16:AG3000"]
    qs = "&".join("ranges=" + urllib.parse.quote(r, safe="") for r in rs)
    vr = [v.get("values", []) for v in sc.call(tok, f"/{SS}/values:batchGet?{qs}")["valueRanges"]]
    return [[r + [""] * 20 for r in v] for v in vr[:12]], [r + [""] * 33 for r in vr[12]]


def tokutei(tsuki, daicho, d, s):
    """提出 → (台帳の氏名, 施工日 YYYY-MM-DD, 顧客ID) か (None, 理由)。推測では当てない。
    1) 提出の「台帳」（◯月_売上/顧客 N行目）の行の氏名・施工日が提出と合うこと
       （「台帳」が空の提出は、月タブで 氏名＋提出日（前日まで）が1行だけ合うこと）
    2) その行の電話番号で顧客管理台帳の顧客ID を引く（電話が無いときは3字以上の氏名が台帳で1人だけ合うとき）"""
    na, hi = kana(d.get("氏名")), (d.get("施工日付") or "").strip()
    gyou = None
    m = re.match(r"(\d+)月_売上/顧客 (\d+)行目", d.get("台帳") or "")
    if m:
        v = tsuki[int(m[1]) - 1]
        i = int(m[2]) - 4
        if 0 <= i < len(v):
            gyou = v[i]
        if gyou is None or not na or kana(gyou[4]) != na or (hi and gyou[2].strip().replace("/", "-") != hi):
            gyou = None   # 提出のあとで行が並べ替わったときは、下の「氏名＋施工日」で引き直す
    if gyou is None:
        import datetime
        t = datetime.datetime.fromisoformat(s["created_at"].replace("Z", "+00:00")) + datetime.timedelta(hours=9)
        hi_s = {(t.date() - datetime.timedelta(days=k)).isoformat() for k in range(2)} if not hi else {hi}
        kouho = [r for v in tsuki for r in v if na and kana(r[4]) == na and r[2].strip().replace("/", "-") in hi_s]
        if len(kouho) != 1:
            return None, f"月タブで氏名と施工日の合う行が{len(kouho)}件"
        gyou = kouho[0]
    hi = gyou[2].strip().replace("/", "-")
    tel = num(gyou[5])
    hit = [x for x in daicho if tel and len(tel) >= 10 and num(x[3]) == tel]
    if not hit and not (tel and len(tel) >= 10) and len(na) >= 3:
        hit = [x for x in daicho if kana(x[1]) == na or na in [kana(y) for y in x[31].split("／")]]
    ids = {x[0].strip() for x in hit if x[0].strip()}
    if len(ids) != 1:
        return None, f"顧客管理台帳で顧客ID が{len(ids)}件"
    return (key(gyou[4]), hi, ids.pop()), ""


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
    kanryo(a.dry_run)


def kanryo(dry: bool) -> None:
    """作業完了フォームの写真。サービスアカウントは容量0で写真を置けないので、
    ここではお客様の特定・フォルダ作り・「取り込み待ち」シートへの行の追加だけを行い、
    実際のコピーはオーナーのアカウントで動く Apps Script（tools/shashin-torikomi.gs、1時間ごと）が行う。
    次の実行で、全部「済」になった提出を「入れ済み」にして okyaku に顧客IDつきで URL を残す。"""
    kiroku = json.loads(KIROKU.read_text(encoding="utf-8")) if KIROKU.exists() else {"sumi": [], "okyaku": {}}
    kiroku.setdefault("machi", {})
    sumi = set(kiroku["sumi"])
    tok = sc.access_token(sc.load_credentials(), "https://www.googleapis.com/auth/drive https://www.googleapis.com/auth/spreadsheets")

    def hozon():
        kiroku["sumi"] = sorted(sumi)
        KIROKU.write_text(json.dumps(kiroku, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    # ① 取り込み待ちシートの結果を回収
    rows = sc.call(tok, f"/{MACHI}/values/A2:G5000").get("values", [])
    jotai, sippai = {}, []
    for i, r in enumerate(rows, 2):
        r = r + [""] * 7
        jotai.setdefault(r[0], []).append(r[4])
        if r[4].startswith("失敗"):
            sippai.append(i)
    for sid, m in list(kiroku["machi"].items()):
        j = jotai.get(sid, [])
        if j and all(x == "済" for x in j):
            o = kiroku["okyaku"].setdefault(m["na"], {})
            if o.get("id") and o["id"] != m["id"]:
                print(f"⚠ {m['na']}：okyaku の顧客ID（{o['id']}）と違う（{m['id']}）。URL は書き換えません")
            else:
                o.update({"url": f"https://drive.google.com/drive/folders/{m['f_ok']}",
                          "saigo": max(m["hi"], o.get("saigo", "")), "id": m["id"]})
            sumi.add(sid)
            del kiroku["machi"][sid]
    nokori = sum(1 for sid in kiroku["machi"] for x in jotai.get(sid, []) if x != "済")
    print(f"取り込み待ち：済 {sum(x == '済' for v in jotai.values() for x in v)}枚／待ち {nokori}枚／失敗 {len(sippai)}枚")
    if sippai and not dry:   # 失敗は状態を空に戻して、次の Apps Script の回にもう一度
        sc.call(tok, f"/{MACHI}/values:batchUpdate", "POST",
                {"valueInputOption": "RAW", "data": [{"range": f"E{i}", "values": [[""]]} for i in sippai]})
    if not dry:
        hozon()

    # ② まだシートに載せていない提出を載せる
    forms = {f["name"]: f["id"] for f in bi.netlify(f"/sites/{SITE_ID}/forms") if f["name"] in ("kanryo", "kanryo-shashin")}
    subs = [(nm, s) for nm, fid in forms.items() for s in bi.netlify(f"/forms/{fid}/submissions")
            if s["id"] not in sumi and s["id"] not in kiroku["machi"]]
    print(f"まだシートに載せていない提出: {len(subs)}件")
    if not subs:
        return
    tsuki, daicho = daicho_yomu(tok)
    cache, tsuika, mitokutei, namae = {}, [], [], {}
    for nm, s in sorted(subs, key=lambda x: x[1]["created_at"]):
        d = s.get("data") or {}
        ran = sorted((int(num(k) or 0), v) for k, v in d.items()
                     if k.startswith("施工写真") and isinstance(v, dict) and v.get("url"))
        if not ran:
            continue
        t, riyu = tokutei(tsuki, daicho, d, s)
        if not t:
            mitokutei.append(f"{d.get('施工日付') or s['created_at'][:10]}（{nm}・写真{len(ran)}枚）：{riyu}")
            continue
        na, hi, cid = t
        o = kiroku["okyaku"].get(na, {})
        if o.get("id") and o["id"] != cid:
            mitokutei.append(f"{na} {hi}（{nm}）：同じ名前の別のお客様（{o['id']}）のフォルダがあるので入れない（{cid}）")
            continue
        jid = (d.get("受注ID") or "").strip()[:8] or "完了フォーム"
        hajime = int(num(str(d.get("開始番号", "1"))) or 1) if nm == "kanryo-shashin" else 1
        print(f"── {na}（{cid}）／{hi}（{nm}）写真 {len(ran)}枚")
        if dry:
            continue
        f_ok = folder(tok, OYA, na, cache)
        f_hi = folder(tok, f_ok, f"{hi}_{jid}", cache)
        for j, (_, v) in enumerate(ran):
            fn = f"{hajime + j:02d}.jpg"
            while (f_hi, fn) in namae:   # 同じ番号が重なったら別名に（取り込み側は同名を「入れ済み」と見なすため）
                fn = fn.replace(".jpg", "_b.jpg")
            namae[(f_hi, fn)] = 1
            tsuika.append([s["id"], f_hi, fn, v["url"], "", "", ""])
        kiroku["machi"][s["id"]] = {"na": na, "hi": hi, "id": cid, "f_ok": f_ok, "n": len(ran)}
    if tsuika:
        sc.call(tok, f"/{MACHI}/values/A:G:append", "POST", {"values": tsuika},
                query={"valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS"})
        hozon()
    print(f"シートに載せた：{len(tsuika)}枚" if not dry else "--dry-run のため載せていません。")
    for x in mitokutei:
        print("  未特定 " + x)


if __name__ == "__main__":
    main()
