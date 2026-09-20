#!/usr/bin/env python3
"""その日の施工が「自社（One Hitter）」か「本舗」かを、台帳から機械で確かめる。

なぜ要るか（2026-09-20）：
  オーナー決定（2026-09-13）「**本舗の案件を混ぜないように注意してね**」。
  `docs/gbp-最新情報-運用.md` の5章に3ステップの決まりがあるのに、**私はそれを回さずに
  写真を外に出していた。** 9/4 と 9/9 の現場は台帳で「本舗」だったが、図鑑・SNSに
  ワンヒッター名義で出してしまった。人の記憶ではなく、出す前に機械で止める。

  写真の EXIF の撮影日 ＝ 施工日、という前提で照合する（棚卸しの `docs/photo-inventory*.md`
  がその前提で作られている）。同じ日に自社と本舗の両方があれば「決められない」を返す。
  **決められないものは出さない。**

使い方:
  python3 tools/check-meigi.py 2026-09-08                 # 1日
  python3 tools/check-meigi.py 2026-07-24 2026-07-30      # 複数
  python3 tools/check-meigi.py --写真棚卸し                # 棚卸しに出てくる撮影日を全部
  python3 tools/check-meigi.py --図鑑                      # data/zukan/*.json の日付を全部

自社だけなら終了コード0。1つでも本舗・決められないがあれば1。
"""
import argparse
import glob
import json
import pathlib
import re
import sys
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import sheets_client as sc  # noqa: E402

# 2026年の売上・顧客台帳。年をまたぐときはここに足す
BOOKS = {2026: "1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64",
         2025: "1cpN2tu6NNIA5FSAAC3ejCK0jNNFNfn7GCwq0ghggK3o"}
JISHA = ("One Hitter",)              # 自社名義
HONPO = ("本舗", "本舗(ロイ)")        # おそうじ本舗名義。外に出さない


def rows_of(tok: str, year: int, month: int) -> list:
    """<月>_売上/顧客 タブの行。★タブ名に / が入るので quote(safe="") が要る★"""
    ss = BOOKS.get(year)
    if not ss:
        return []
    rng = f"{month}月_売上/顧客!A1:Z300"
    try:
        v = sc.call(tok, f"/{ss}/values/{urllib.parse.quote(rng, safe='')}").get("values", [])
    except SystemExit:
        return []
    hdr = next((r for r in v if "施工日付" in r), None)
    if not hdr:
        return []
    ix = {h: i for i, h in enumerate(hdr)}
    out = []
    for r in v[v.index(hdr) + 1:]:
        def g(k):
            i = ix.get(k)
            return r[i] if i is not None and i < len(r) else ""
        if g("施工日付"):
            out.append({"日付": g("施工日付"), "名義": g("売上種類") or g("流入経路"),
                        "メニュー": g("実施メニュー"), "売上": g("売上（税込）")})
    return out


def shiraberu(tok: str, hiduke: str) -> dict:
    """1日ぶん。{判定, 行} を返す。判定は 自社／本舗／決められない／台帳に無い"""
    m = re.match(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})$", hiduke)
    if not m:
        return {"判定": "日付として読めない", "行": []}
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    want = {f"{y}/{mo}/{d}", f"{y}/{mo:02d}/{d:02d}", f"{y}-{mo:02d}-{d:02d}"}
    hit = [r for r in rows_of(tok, y, mo) if r["日付"] in want]
    if not hit:
        return {"判定": "台帳に無い", "行": []}
    meigi = {r["名義"] for r in hit}
    if meigi <= set(JISHA):
        han = "自社"
    elif meigi & set(HONPO) and not (meigi & set(JISHA)):
        han = "本舗"
    else:
        han = "決められない"        # 同じ日に自社と本舗の両方がある。写真がどちらか分からない
    return {"判定": han, "行": hit}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("日付", nargs="*")
    ap.add_argument("--写真棚卸し", action="store_true", dest="inv")
    ap.add_argument("--図鑑", action="store_true", dest="zukan")
    a = ap.parse_args()

    hi = list(a.日付)
    if a.zukan:
        hi += [json.loads(pathlib.Path(p).read_text(encoding="utf-8")).get("日付", "")
               for p in sorted(glob.glob(str(ROOT / "data/zukan/*.json")))]
    if a.inv:
        for p in sorted(glob.glob(str(ROOT / "docs/photo-inventory*.md"))):
            t = pathlib.Path(p).read_text(encoding="utf-8")
            # 「| 07/24 | 18 | …」のような棚卸しの表から撮影日を拾う
            for mm, dd in re.findall(r"^\|\s*(\d{2})/(\d{2})\s*\|", t, re.M):
                hi.append(f"2026-{mm}-{dd}")
    hi = sorted({x for x in hi if x})
    if not hi:
        print("日付を渡してください（または --写真棚卸し / --図鑑）")
        return 1

    tok = sc.access_token(sc.load_credentials(), "https://www.googleapis.com/auth/spreadsheets.readonly")
    warui = 0
    for h in hi:
        r = shiraberu(tok, h)
        mark = {"自社": "○ 出してよい", "本舗": "✗ 本舗。外に出さない",
                "決められない": "✗ 決められない。出さない", "台帳に無い": "✗ 台帳に無い。出さない"}.get(r["判定"], "✗ " + r["判定"])
        print(f"{h}  {mark}")
        for x in r["行"]:
            print(f"      名義={x['名義']:<12} {x['メニュー']:<24} {x['売上']}")
        if r["判定"] != "自社":
            warui += 1
    print(f"\n{len(hi)}日中 {warui}日は外に出せません" if warui else f"\n{len(hi)}日とも自社名義です")
    return 1 if warui else 0


if __name__ == "__main__":
    sys.exit(main())
