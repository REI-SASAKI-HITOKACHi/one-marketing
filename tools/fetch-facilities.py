#!/usr/bin/env python3
"""施設カードの設置先候補を Google Places API (New) で集める。

オーナー決定 2026-09-14：「50件送れたら停止して改善のループ。対象リストもどんどん追加が必要だよ」。
第1波（江戸川区・浦安市 291件）は送れる候補が 30 件で尽きたので、都内の区を足していく。

認証はサービスアカウント（Sheets と同じ鍵）の OAuth。Places API (New) は SA のトークンで呼べる（無料枠・課金なし）。

使い方:
  python3 tools/fetch-facilities.py --区 江東区 葛飾区 墨田区        # 集めて data/facilities-<日付>-add.json に足す
  python3 tools/fetch-facilities.py --区 江東区 --種別 ペットショップ  # 種別を絞る
  python3 tools/fetch-facilities.py --区 江東区 --dry                # 件数だけ数える（書かない）
"""
import argparse
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sheets_client as sc  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data"
CLEAN = OUT / "facilities-2026-09-clean.json"
API = "https://places.googleapis.com/v1/places:searchText"
PROJECT = "one-hitter-sheets"
FIELDS = "places.id,places.displayName,places.formattedAddress,places.nationalPhoneNumber,places.websiteUri,places.primaryType,places.types,places.businessStatus,places.userRatingCount"

# 種別ごとの検索語。第1波と同じ言葉（データの一貫性のため）
KINDS = {
    "産婦人科・産院": ["{区} 産婦人科", "{区} 産院"],
    "ペットショップ": ["{区} ペットショップ", "{区} ペットホテル"],
    "トリミング": ["{区} トリミングサロン"],
    "動物病院": ["{区} 動物病院"],
    "小児科": ["{区} 小児科"],
    "ベビー用品店": ["{区} ベビー用品"],
    "子育て支援（公的）": ["{区} 子育て支援センター"],
}
# 公的施設は送らない決まり（docs/節目チャネル-全体構造.md 9章）。集めはするが優先度Cにする
KEEP_STATUS = ("OPERATIONAL",)


def token() -> str:
    return sc.access_token(sc.load_credentials(), "https://www.googleapis.com/auth/cloud-platform")


def search(tok: str, text: str, page: str = "") -> dict:
    payload = {"textQuery": text, "languageCode": "ja", "regionCode": "JP", "maxResultCount": 20}
    if page:
        payload["pageToken"] = page
    req = urllib.request.Request(API, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json",
                                          "X-Goog-FieldMask": FIELDS + ",nextPageToken", "X-Goog-User-Project": PROJECT})
    for i in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:300]
            if e.code in (429, 500, 502, 503) and i < 3:
                time.sleep(10 * (i + 1))
                continue
            sys.exit(f"Places API {e.code}: {body}")
    return {}


def ku_of(addr: str) -> str:
    m = re.search(r"東京都(.{2,4}?[区市])", addr) or re.search(r"千葉県(.{2,4}?市)", addr) or re.search(r"神奈川県(.{2,4}?[区市])", addr)
    return m.group(1) if m else ""


def area_of(addr: str) -> str:
    return "東京都" if "東京都" in addr else ("千葉県" if "千葉県" in addr else ("神奈川県" if "神奈川県" in addr else ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--区", dest="ku", nargs="+", required=True)
    ap.add_argument("--種別", dest="kinds", nargs="+", default=list(KINDS))
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()

    known = {f["id"] for f in json.loads(CLEAN.read_text(encoding="utf-8"))}
    addf = OUT / "facilities-2026-09-add.json"
    got = {f["id"]: f for f in (json.loads(addf.read_text(encoding="utf-8")) if addf.exists() else [])}
    before = len(got)
    tok = token()
    for ku in a.ku:
        for kind in a.kinds:
            for tmpl in KINDS[kind]:
                q = tmpl.format(区=ku)
                page, n = "", 0
                while True:
                    d = search(tok, q, page)
                    for p in d.get("places", []):
                        pid = p["id"]
                        if pid in known or pid in got:
                            continue
                        if p.get("businessStatus") not in KEEP_STATUS:
                            continue
                        addr = p.get("formattedAddress", "")
                        # 検索語の区と実際の所在地が違うもの（隣接区の店が混ざる）はその区の回で拾う
                        if ku_of(addr) != ku:
                            continue
                        got[pid] = {"id": pid, "種別": kind, "検索語": q, "施設名": p.get("displayName", {}).get("text", ""),
                                    "住所": addr, "電話": p.get("nationalPhoneNumber", ""), "サイト": p.get("websiteUri", ""),
                                    "type": p.get("primaryType", ""), "types": p.get("types", []),
                                    "市区": ku, "エリア": area_of(addr), "クチコミ数": p.get("userRatingCount", 0)}
                        n += 1
                    page = d.get("nextPageToken", "")
                    if not page:
                        break
                    time.sleep(2)
                print(f"  {q}: +{n}")
    print(f"新規 {len(got) - before} 件（累計 {len(got)}）")
    if a.dry:
        return
    addf.write_text(json.dumps(list(got.values()), ensure_ascii=False, indent=1), encoding="utf-8")
    print("書き出し:", addf)


if __name__ == "__main__":
    main()
