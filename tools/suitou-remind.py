#!/usr/bin/env python3
"""出納帳の手元の現金が 5万円を超えたら、和真さんに「会社の口座へ振り込んで」と業務連絡LINEで知らせる。

2026-11-05 和真さん（業務連絡LINE 654）「出納帳5万超えたら振り込むようにリマインド設定できる？」

- 出納帳タブの履歴（40行目〜）のいちばん下の「手元の現金（残高）」（H列）を読む。
- 5万円を超えていたら1通送る。**送るのは1日1回まで**（超えたままなら翌朝の点検でもう一度）。
- 和真さんが「いくら振り込みました」と送ってきたら、CMO が履歴に「出金」の行を足す → 残高が下がって止まる。

毎時点検（tools/maiji-tenken.py）が --dry-run を流し、「リマインド対象: 1件」なら CMO がこれを流して送る。

使い方:
  python3 tools/suitou-remind.py --dry-run   # 読むだけ
  python3 tools/suitou-remind.py             # 対象なら送る

★2027年1月から出納帳は新しいファイル（1UBxM_…）の『出納帳』タブ（M列が残高・3行目から）に移る。
  書き込み先を切り替える日に、下の SS・HANI・RETSU も切り替えること。
"""
import argparse
import datetime
import json
import pathlib
import subprocess
import sys
import urllib.parse

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sheets_client as sc  # noqa: E402

KOKO = pathlib.Path(__file__).resolve().parent.parent
SS = "1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64"
HANI = "'出納帳'!A40:H2003"
RETSU = 7          # H列＝手元の現金（残高）
SAKAI = 50_000     # これを超えたら知らせる
JOUTAI = pathlib.Path.home() / ".cache/one-hitter/suitou-remind.json"
JST = datetime.timezone(datetime.timedelta(hours=9))


def en(s) -> int | None:
    s = str(s).replace(",", "").replace("¥", "").replace("円", "").strip()
    try:
        return int(float(s))
    except ValueError:
        return None


def zandaka():
    tok = sc.access_token(sc.load_credentials())
    v = sc.call(tok, f"/{SS}/values/" + urllib.parse.quote(HANI, safe="")).get("values", [])
    saigo = None
    for i, r in enumerate(v):
        if len(r) > RETSU and en(r[RETSU]) is not None and any(str(c).strip() for c in r[:5]):
            saigo = (40 + i, en(r[RETSU]), r[0] if r else "")
    return saigo


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    kyou = datetime.datetime.now(JST).strftime("%Y-%m-%d")
    z = zandaka()
    if not z:
        print("⚠ 出納帳の残高が読めません")
        print("リマインド対象: 0件")
        return
    gyo, kin, hi = z
    joutai = json.loads(JOUTAI.read_text(encoding="utf-8")) if JOUTAI.exists() else {}
    print(f"手元の現金: {kin:,}円（出納帳 {gyo}行目・{hi}）／しきい値 {SAKAI:,}円")
    if kin <= SAKAI:
        print("リマインド対象: 0件")
        return
    if joutai.get("saigo_hi") == kyou:
        print(f"今日はもう知らせた（{joutai.get('zandaka', 0):,}円の時点）")
        print("リマインド対象: 0件")
        return
    print("リマインド対象: 1件")
    if a.dry_run:
        return
    honbun = (f"和真さん\n出納帳の手元の現金が {kin:,}円 になりました（5万円を超えました）。\n"
              "お手すきのときに会社の口座へ振り込みをお願いします。\n"
              "振り込んだら「〇〇円振り込みました」とここに送ってください。出納帳はCMOが付けます。")
    r = subprocess.run(["python3", "tools/line_client.py", "push", honbun], cwd=KOKO,
                       capture_output=True, text=True, timeout=120)
    print((r.stdout or "") + (r.stderr or ""))
    if r.returncode != 0:
        sys.exit(r.returncode)
    JOUTAI.parent.mkdir(parents=True, exist_ok=True)
    JOUTAI.write_text(json.dumps({"saigo_hi": kyou, "zandaka": kin, "gyo": gyo}, ensure_ascii=False) + "\n",
                      encoding="utf-8")


if __name__ == "__main__":
    main()
