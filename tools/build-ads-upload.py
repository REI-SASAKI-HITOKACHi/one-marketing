#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""検索広告 段0 の一括アップロード用CSVを作る。

読む: docs/広告-検索広告-段0.md の設計（エリア・キーワード・除外・入札・着地）
出す: data/ads/段0-一括アップロード.csv（Google広告 ツールと設定→一括操作→アップロード）

見出し・説明文の長さは Google の数え方（全角2・半角1、見出し30・説明文90）で機械検査する。
1つでも超えたら CSV を書かずに止まる。数えずに入稿すると、審査ではなく入稿で弾かれる。
"""
import csv, sys, unicodedata, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "ads" / "段0-一括アップロード.csv"

CAMPAIGN = "検索_江戸川_段0"
MAX_CPC = "500"
AIRCON = "https://lp.onehitter.jp/aircon/?src=gads&cid={campaignid}"
MIZU = "https://lp.onehitter.jp/mizumawari/?src=gads&cid={campaignid}"

# 全角は2、半角は1。Google の見出し30／説明文90／パス15 はこの単位。
def width(s):
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)

# ─────────────────────────────────────────────
# 広告グループ：キーワードと着地ページ
# ─────────────────────────────────────────────
AREAS_AIRCON = ["江戸川区", "西葛西", "葛西", "浦安", "市川", "江東区", "墨田区", "葛飾区"]
AREAS_CORE = ["江戸川区", "西葛西", "浦安", "市川", "江東区"]

def kw(head, areas):
    return [f"{head} {a}" for a in areas]

GROUPS = [
    {
        "name": "A_エアコン",
        "url": AIRCON,
        "phrase": (kw("エアコンクリーニング", AREAS_AIRCON)
                   + kw("エアコン掃除 業者", ["江戸川区", "西葛西", "浦安", "市川"])
                   + kw("エアコン洗浄", ["江戸川区", "浦安"])),
        "exact": ["エアコンクリーニング 江戸川区", "エアコンクリーニング 西葛西"],
    },
    {
        "name": "B_レンジフード",
        "url": MIZU,
        "phrase": (kw("レンジフード クリーニング", AREAS_CORE)
                   + kw("換気扇 クリーニング", ["江戸川区", "浦安", "市川"])),
        "exact": [],
    },
    {
        "name": "B_浴室",
        "url": MIZU,
        "phrase": (kw("浴室クリーニング", AREAS_CORE)
                   + kw("風呂 クリーニング 業者", ["江戸川区", "浦安", "市川"])
                   + kw("お風呂掃除 業者", ["江戸川区"])),
        "exact": [],
    },
    {
        "name": "C_ハウスクリーニング",
        "url": MIZU,
        "phrase": kw("ハウスクリーニング", AREAS_AIRCON),
        "exact": [],
    },
]

# ─────────────────────────────────────────────
# 除外キーワード（キャンペーン単位・初日から入れる）
#   docs/広告-検索広告-段0.md の一覧をそのまま
# ─────────────────────────────────────────────
NEGATIVES = ["自分で", "やり方", "方法", "DIY", "洗浄スプレー",
             "求人", "バイト", "募集", "資格", "開業", "フランチャイズ",
             "業務用", "賃貸 退去", "空室", "原状回復",
             "おそうじ本舗", "くらしのマーケット", "ユアマイスター"]

# ─────────────────────────────────────────────
# 広告文：使える事実だけ。盛らない。
#   満足度98.6%（209名中206名／2023年1月〜2025年12月）
#   Googleクチコミ★5.0（24件）／東京・千葉・神奈川／60分10,780円（税込）から
#   ※98.8% と「地域No.1」等の最上級表現は使わない（景表法）
# ─────────────────────────────────────────────
COMMON_HEADS = [
    "満足度98.6%の実績",
    "Googleクチコミ★5.0",
    "60分10,780円税込から",
    "東京・千葉・神奈川対応",
    "土日も承ります",
    "Web予約は24時間受付",
    "江戸川区の清掃業者",
]
COMMON_DESCS = [
    "アンケート209名のうち206名にご満足の回答。2023年1月〜2025年12月の実績です。",
    "Googleのクチコミは★5.0（24件）。作業の内容と料金は事前にご説明します。",
    "東京・千葉・神奈川に対応。60分10,780円（税込）から。Webから24時間受付。",
]

ADS = {
    "A_エアコン": {
        "heads": ["エアコン掃除 江戸川区", "エアコンクリーニング", "エアコン1台から"] + COMMON_HEADS,
        "descs": ["専用の機材でエアコン内部を洗浄します。西葛西・葛西・浦安はすぐ伺えます。"] + COMMON_DESCS,
        "p1": "aircon", "p2": "edogawa",
    },
    "B_レンジフード": {
        "heads": ["レンジフード清掃", "換気扇クリーニング", "油汚れを分解洗浄"] + COMMON_HEADS,
        "descs": ["取り外せる部品をお預かりして洗浄。戻したあとの動作まで確認します。"] + COMMON_DESCS,
        "p1": "rangehood", "p2": "edogawa",
    },
    "B_浴室": {
        "heads": ["浴室クリーニング", "お風呂の黒ずみに", "水まわりまとめて"] + COMMON_HEADS,
        "descs": ["浴室の床・壁・天井・鏡・ドアまで。エプロン内部の高圧洗浄は追加で承ります。"] + COMMON_DESCS,
        "p1": "bath", "p2": "edogawa",
    },
    "C_ハウスクリーニング": {
        "heads": ["ハウスクリーニング", "水まわりセット", "1か所から承ります"] + COMMON_HEADS,
        "descs": ["キッチン・浴室・トイレ・洗面をまとめて。ご予算に合わせてお選びいただけます。"] + COMMON_DESCS,
        "p1": "housecleaning", "p2": "edogawa",
    },
}

# ─────────────────────────────────────────────
# 検査
# ─────────────────────────────────────────────
def check():
    ng = []
    for g, ad in ADS.items():
        for h in ad["heads"]:
            if width(h) > 30:
                ng.append(f"見出しが長い（{width(h)}/30）[{g}] {h}")
        for d in ad["descs"]:
            if width(d) > 90:
                ng.append(f"説明文が長い（{width(d)}/90）[{g}] {d}")
        for p in (ad["p1"], ad["p2"]):
            if width(p) > 15:
                ng.append(f"パスが長い（{width(p)}/15）[{g}] {p}")
        if len(ad["heads"]) < 3:
            ng.append(f"見出しが3本未満 [{g}]")
        if len(ad["descs"]) < 2:
            ng.append(f"説明文が2本未満 [{g}]")
        if len(set(ad["heads"])) != len(ad["heads"]):
            ng.append(f"見出しに重複 [{g}]")
    # 使ってはいけない数字・表現
    for g, ad in ADS.items():
        for t in ad["heads"] + ad["descs"]:
            for bad in ("98.8", "No.1", "ナンバー1", "日本一", "地域一番"):
                if bad in t:
                    ng.append(f"使えない表現 '{bad}' [{g}] {t}")
    return ng

HEAD_N, DESC_N = 15, 4
COLS = (["Campaign", "Ad Group", "Keyword", "Criterion Type", "Max CPC", "Final URL"]
        + [f"Headline {i}" for i in range(1, HEAD_N + 1)]
        + [f"Description {i}" for i in range(1, DESC_N + 1)]
        + ["Path 1", "Path 2", "Status"])

def main():
    ng = check()
    if ng:
        print("入稿できません。直してください：", file=sys.stderr)
        for x in ng:
            print("  ✗ " + x, file=sys.stderr)
        return 1

    rows = []
    for n in NEGATIVES:
        rows.append({"Campaign": CAMPAIGN, "Keyword": n,
                     "Criterion Type": "Campaign Negative Phrase", "Status": "Enabled"})
    for g in GROUPS:
        for k in g["phrase"]:
            rows.append({"Campaign": CAMPAIGN, "Ad Group": g["name"], "Keyword": k,
                         "Criterion Type": "Phrase", "Max CPC": MAX_CPC, "Status": "Enabled"})
        for k in g["exact"]:
            rows.append({"Campaign": CAMPAIGN, "Ad Group": g["name"], "Keyword": k,
                         "Criterion Type": "Exact", "Max CPC": MAX_CPC, "Status": "Enabled"})
        ad = ADS[g["name"]]
        r = {"Campaign": CAMPAIGN, "Ad Group": g["name"], "Final URL": g["url"],
             "Path 1": ad["p1"], "Path 2": ad["p2"], "Status": "Enabled"}
        for i, h in enumerate(ad["heads"][:HEAD_N], 1):
            r[f"Headline {i}"] = h
        for i, d in enumerate(ad["descs"][:DESC_N], 1):
            r[f"Description {i}"] = d
        rows.append(r)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in COLS})

    # キャンペーンそのものを作る表（画面のウィザードが通らないときの回避策）
    camp = ROOT / "data" / "ads" / "段0-キャンペーン設定.csv"
    ccols = ["Campaign", "Campaign Type", "Campaign Subtype", "Campaign Daily Budget",
             "Bid Strategy Type", "Campaign Status", "Networks", "Languages", "Location"]
    with camp.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=ccols)
        w.writeheader()
        w.writerow({
            "Campaign": CAMPAIGN,
            "Campaign Type": "Search",
            "Campaign Subtype": "Standard",
            "Campaign Daily Budget": "1667",
            "Bid Strategy Type": "Maximize clicks",
            "Campaign Status": "Paused",
            "Networks": "Google search",
            "Languages": "Japanese",
            "Location": "Edogawa; Koto; Sumida; Katsushika; Urayasu; Ichikawa",
        })
    print(f"書きました: {camp}（画面で作れないときの回避策。1行）")

    kwn = sum(len(g["phrase"]) + len(g["exact"]) for g in GROUPS)
    print(f"書きました: {OUT}")
    print(f"  広告グループ {len(GROUPS)} ／ キーワード {kwn} ／ 除外 {len(NEGATIVES)} ／ 広告 {len(GROUPS)}")
    print("  見出し・説明文の長さは全件検査済み（全角2・半角1、見出し30・説明文90）")
    return 0

if __name__ == "__main__":
    sys.exit(main())
