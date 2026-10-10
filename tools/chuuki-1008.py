#!/usr/bin/env python3
"""遠方の交通費の一文と、浴室の「標準に含まれるもの／別料金のオプション」を足す（依頼 20261007-02-lp）。

  python3 tools/chuuki-1008.py <ページ名> 元.html 出力.html     # ページ名：aircon / mizumawari-b / booking など

- 交通費：オーナー決定 10/6「通常は交通費がかかると伝える」。金額は決まっていないので書かない。
  「Web予約特典で今回は無料」は坂井様だけの例外なので書かない。
- 浴室：坂井様のキャンセル理由（10/6）「浴室乾燥機・鏡・エプロン内部まで全部入っていると思っていた」。
  申込ボタンの手前に、含まれるもの／別料金のオプションを一目で出す。オプションの金額は data/prices.json から読む。
- 旧の見た目・v2・予約ページのどれにも入るよう、文字列の置き換えで当てる。置き換えが1つも当たらなければ止める。

★公開はまだ（cmo が配信を決める）。承認まで deploy/netlify と lp/booking には入れない。
  build-site.py の CHUUKI_PAGES が空のあいだはどのLPにも入らない。確認は preview/chuuki/ で。
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

KOUTSUU = "遠方（目安：高速道路を使う地域）は、交通費をいただく場合があります。お見積りのお電話でご案内します。"
KOUTSUU_KAKKO = "遠方（目安：高速道路を使う地域）の交通費（お見積りのお電話でご案内します）"

# （置き換え前, 置き換え後）。どれもページ内の決まった言い回しで、当たった数を数えて報告する
OKIKAE = [
    ("コインパーキング代を実費でいただきます。金額は事前にお伝えします。",
     "コインパーキング代を実費でいただきます。金額は事前にお伝えします。" + KOUTSUU),
    ("コインパーキング代を実費でいただきます（金額は事前にお伝えします）。",
     "コインパーキング代を実費でいただきます（金額は事前にお伝えします）。" + KOUTSUU),
    ("コインパーキング代（実費・事前にお伝えします）と、",
     "コインパーキング代（実費・事前にお伝えします）、" + KOUTSUU_KAKKO + "と、"),
    ("別にかかる可能性があるのは、この2つだけ", "別にかかる可能性があるのは、この3つだけ"),
    ("コインパーキング等の駐車場代を実費でご請求します。",
     "コインパーキング等の駐車場代を実費でご請求します。遠方（目安：高速道路を使う地域）は、交通費をいただく場合があります（お見積りのお電話でご案内します）。"),
    # 予約ページ
    ("近くのコインパーキング代を実費でご請求いたします。あらかじめご了承ください。",
     "近くのコインパーキング代を実費でご請求いたします。あらかじめご了承ください。" + KOUTSUU),
    ("'お車を停められる場所が無い場合は、コインパーキング代が実費で加わります。' +",
     "'お車を停められる場所が無い場合は、コインパーキング代が実費で加わります。" + KOUTSUU + "' +"),
    ("<small>お車を停められる場所が無い場合は、コインパーキング代が実費で加わります。</small>",
     "<small>お車を停められる場所が無い場合は、コインパーキング代が実費で加わります。" + KOUTSUU + "</small>"),
]

YOKUSHITSU_PAGES = {"mizumawari", "mizumawari-b", "booking"}

# 含まれるもの。2026-10-10 第6回MTG（依頼 20261010-03-lp）で「落ちきらない可能性」を足した
YK_IN_MAE = "床・壁・天井・鏡・ドアの、ふだんの汚れ"
OCHIKIRANAI = "汚れの程度により、落ちきらない可能性があります。"
YK_IN = YK_IN_MAE + '<br><span class="yk-n2">' + OCHIKIRANAI + "</span>"

YOKUSHITSU_CSS = """<style>
.yk-box{border:1px solid rgba(13,59,92,.22);border-radius:10px;background:#fff;padding:14px 16px;margin:0 0 16px;font-size:14px;line-height:1.75;text-align:left;}
.yk-box .yk-h{font-weight:800;color:var(--ink,#0D3B5C);margin:0;}
.yk-box .yk-in{margin:2px 0 10px;}
.yk-box ul{list-style:none;margin:2px 0 8px;padding:0;display:grid;gap:2px;}
.yk-box li{display:flex;justify-content:space-between;gap:12px;border-bottom:1px dashed rgba(13,59,92,.15);padding:3px 0;}
.yk-box li b{white-space:nowrap;font-variant-numeric:tabular-nums;}
.yk-box .yk-n{font-size:12.5px;color:#536A78;margin:6px 0 0;}
.yk-box .yk-n2{font-size:12.5px;color:#536A78;}
</style>"""


def yen(n):
    return f"{n:,}円"


def yokushitsu_box():
    d = json.loads((ROOT / "data" / "prices.json").read_text(encoding="utf-8"))
    menu = {m["名称"]: m for m in d["本メニュー"]}
    opt = {m["名称"]: m for m in d["オプション"]}
    rows = [("浴室乾燥機の洗浄", "浴室乾燥機洗浄"),
            ("エプロン内部（浴槽の側面カバーの中）の高圧洗浄", "エプロン内部高圧洗浄"),
            ("鏡の水アカ（ウロコ）除去", "鏡の水垢除去"),
            ("浴室換気扇の洗浄", "浴室換気扇洗浄")]
    li = "".join(f"<li><span>{k}</span><b>{yen(opt[n]['価格'])}</b></li>" for k, n in rows)
    return (YOKUSHITSU_CSS +
            f'<div class="yk-box" id="yk-box"><p class="yk-h">浴室クリーニング（{yen(menu["浴室クリーニング"]["単体"])}）に含まれるもの</p>'
            f'<p class="yk-in">{YK_IN}</p>'
            '<p class="yk-h">別料金のオプション（ご希望の方のみ・税込）</p>'
            f"<ul>{li}</ul>"
            '<p class="yk-n">どこまでご希望かは、お見積りのお電話で確認してからお伺いします。</p></div>')


def apply(doc: str, page: str):
    hits = {}
    for a, b in OKIKAE:
        n = doc.count(a)
        if n and b not in doc:
            doc = doc.replace(a, b)
            hits[a[:18]] = n
    if not hits and KOUTSUU not in doc and KOUTSUU_KAKKO not in doc:
        raise SystemExit(f"{page}: 交通費の一文を足す場所が1つも見つかりません（言い回しが変わった？）")
    # すでに浴室の枠が入っているページ（10/9 配信分）には「落ちきらない可能性」だけ足す
    if 'id="yk-box"' in doc and OCHIKIRANAI not in doc:
        old = f'<p class="yk-in">{YK_IN_MAE}</p>'
        if doc.count(old) != 1:
            raise SystemExit(f"{page}: 浴室の枠の「含まれるもの」が見つかりません")
        doc = doc.replace(old, f'<p class="yk-in">{YK_IN}</p>')
        doc = doc.replace(".yk-box .yk-n{font-size:12.5px;color:#536A78;margin:6px 0 0;}",
                          ".yk-box .yk-n{font-size:12.5px;color:#536A78;margin:6px 0 0;}\n.yk-box .yk-n2{font-size:12.5px;color:#536A78;}", 1)
        hits["落ちきらない"] = 1
    if page in YOKUSHITSU_PAGES and 'id="yk-box"' not in doc:
        box = yokushitsu_box()
        if page == "booking":
            # 予約ページはお客様情報の「ご要望」欄の直後（送信ボタンの手前）
            key = '<div class="hp"><label>この欄は入力しないでください'
        else:
            key = '<button class="btn lg" type="submit">'
        i = doc.find(key)
        if i < 0:
            raise SystemExit(f"{page}: 浴室の枠を置く場所（送信ボタンの手前）が見つかりません")
        line_start = doc.rfind("\n", 0, i) + 1
        doc = doc[:line_start] + box + "\n" + doc[line_start:]
        hits["浴室の枠"] = 1
    return doc, hits


def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    page, src, dst = sys.argv[1], pathlib.Path(sys.argv[2]), pathlib.Path(sys.argv[3])
    out, hits = apply(src.read_text(encoding="utf-8"), page)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(out, encoding="utf-8")
    print(f"{page:13s} " + "／".join(f"{k}…×{v}" for k, v in hits.items()))


if __name__ == "__main__":
    main()
