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
# Google が提示した正表記をそのまま使う。市区名だけ（「江戸川区」等）は無効（2026-09-15 実測）
LOCATIONS = ("Edogawa City,Tokyo,Japan;Koto City,Tokyo,Japan;Sumida City,Tokyo,Japan;"
             "Katsushika City,Tokyo,Japan;Urayasu,Chiba,Japan;Ichikawa,Chiba,Japan")
# src は広告グループの着地ごとに分ける（?src= 規約）。LP は区切りの前だけ見るので
# gads / gads_aircon のどちらでも文言は切り替わるが、GA4 へは切り落とす前の値が渡る。
# 全部 gads にすると、同じ /mizumawari/ に着く3グループが GA4 側で見分けられない。
AIRCON = "https://lp.onehitter.jp/aircon/?src=gads_aircon&cid={campaignid}"
MIZU = "https://lp.onehitter.jp/mizumawari/?src=gads_mizumawari&cid={campaignid}"

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


# ⚠ 2026-09-15 実測：区名を付けた語は 41語中22語が「検索ボリュームが少ない」で配信されない。
#    B群は8〜9語中7〜8語が該当し、そのままでは在庫がほぼ無い。
#    → **地域語を外した語**をフレーズ一致で足し、エリアはキャンペーンの地域設定で担保する。
#    区名付きの語は残す（配信されないだけで害は無く、検索が増えたときに精度が効く）。

GROUPS = [
    {
        "name": "A_エアコン",
        "bare": ["エアコンクリーニング", "エアコン掃除 業者"],
        "url": AIRCON,
        "phrase": (kw("エアコンクリーニング", AREAS_AIRCON)
                   + kw("エアコン掃除 業者", ["江戸川区", "西葛西", "浦安", "市川"])
                   + kw("エアコン洗浄", ["江戸川区", "浦安"])),
        "exact": ["エアコンクリーニング 江戸川区", "エアコンクリーニング 西葛西"],
    },
    {
        "name": "B_レンジフード",
        "bare": ["レンジフード クリーニング", "レンジフード 掃除 業者", "換気扇 クリーニング"],
        "url": MIZU,
        "phrase": (kw("レンジフード クリーニング", AREAS_CORE)
                   + kw("換気扇 クリーニング", ["江戸川区", "浦安", "市川"])),
        "exact": [],
    },
    {
        "name": "B_浴室",
        "bare": ["浴室クリーニング", "風呂 クリーニング 業者", "お風呂掃除 業者"],
        "url": MIZU,
        "phrase": (kw("浴室クリーニング", AREAS_CORE)
                   + kw("風呂 クリーニング 業者", ["江戸川区", "浦安", "市川"])
                   + kw("お風呂掃除 業者", ["江戸川区"])),
        "exact": [],
    },
    {
        "name": "C_ハウスクリーニング",
        "bare": ["ハウスクリーニング"],
        "cpc": "300",
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
    "Googleクチコミ評価5.0",
    "60分10,780円税込から",
    "東京・千葉・神奈川対応",
    "土日も承ります",
    "Web予約は24時間受付",
    "江戸川区の清掃業者",
]
COMMON_DESCS = [
    "アンケート209名のうち206名にご満足の回答。2023年1月〜2025年12月の実績です。",
    "Googleのクチコミ評価は5.0（24件）。作業の内容と料金は事前にご説明します。",
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
            for bad in ("98.8", "No.1", "ナンバー1", "日本一", "地域一番",
                        "最安", "絶対", "必ず", "完全除去", "100%", "永久"):
                if bad in t:
                    ng.append(f"使えない表現 '{bad}' [{g}] {t}")
            # Google に「記号や句読点の不適切な使用」で弾かれる文字（2026-09-15 実測）
            for bad in ("★", "☆", "♪", "♡", "→", "◎", "※", "！！"):
                if bad in t:
                    ng.append(f"Googleが弾く記号 '{bad}' [{g}] {t}")
    return ng

HEAD_N, DESC_N = 15, 4
# 一括アップロードに実際に入るのは 広告グループ と キーワード だけ（2026-09-15 実測）。
# 広告文・除外キーワードの列は入れない。入れてもエラーになるか、黙って捨てられる。
COLS = ["Campaign", "Ad Group", "Keyword", "Criterion Type", "Max CPC", "Status"]

def main():
    ng = check()
    if ng:
        print("入稿できません。直してください：", file=sys.stderr)
        for x in ng:
            print("  ✗ " + x, file=sys.stderr)
        return 1

    rows = []
    # ⚠ 除外キーワードは一括アップロードでは入らない（Campaign Negative Phrase / Negative Phrase とも
    #    「値が無効です」。2026-09-15 実測）。管理画面から手で入れるため、別ファイルに出す。
    neg = ROOT / "data" / "ads" / "段0-除外キーワード.txt"
    neg.write_text("\n".join(NEGATIVES) + "\n", encoding="utf-8")
    # ⚠ レスポンシブ検索広告も一括アップロードでは作れない（最小構成でも「エラーが発生しました」）。
    #    管理画面に手で入れるため、貼り付け用の文面を別ファイルに出す。
    admd = ROOT / "data" / "ads" / "段0-広告文.md"
    with admd.open("w", encoding="utf-8") as f:
        f.write("# 段0 レスポンシブ検索広告（管理画面に手で入れる）\n\n")
        f.write("一括アップロードでは作れないため、ここから貼る。"
                "見出しは全角1文字＝2カウントで30まで、説明文は90まで。\n")
        for g in GROUPS:
            ad = ADS[g["name"]]
            f.write(f"\n## {g['name']}\n\n")
            f.write(f"- 最終ページURL：`{g['url']}`\n")
            f.write(f"- 表示パス：`{ad['p1']}` / `{ad['p2']}`\n\n### 見出し\n\n")
            for h in ad["heads"]:
                f.write(f"- {h}\n")
            f.write("\n### 説明文\n\n")
            for d in ad["descs"]:
                f.write(f"- {d}\n")
    for g in GROUPS:
        # ⚠ 広告グループはキーワード行からは自動生成されない。作る行を先に置く（2026-09-15 実測）
        rows.append({"Campaign": CAMPAIGN, "Ad Group": g["name"],
                     "Max CPC": g.get("cpc", MAX_CPC), "Status": "Enabled"})
        for k in g["bare"] + g["phrase"]:
            rows.append({"Campaign": CAMPAIGN, "Ad Group": g["name"], "Keyword": k,
                         "Criterion Type": "Phrase", "Max CPC": g.get("cpc", MAX_CPC),
                         "Status": "Enabled"})
        for k in g["exact"]:
            rows.append({"Campaign": CAMPAIGN, "Ad Group": g["name"], "Keyword": k,
                         "Criterion Type": "Exact", "Max CPC": g.get("cpc", MAX_CPC),
                         "Status": "Enabled"})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in COLS})

    # キャンペーンそのものを作る表（画面のウィザードが通らないときの回避策）
    camp = ROOT / "data" / "ads" / "段0-キャンペーン設定.csv"
    # ⚠ 予算の列名は "Budget"。"Campaign Daily Budget" はエラーも出さずに無視される（2026-09-15 実測）
    # ⚠ 地域は市区名だけだと無効。Google が提示する正表記をそのまま使う
    ccols = ["Campaign", "Campaign Type", "Campaign Subtype", "Budget",
             "Bid Strategy Type", "Campaign Status", "Networks", "Languages", "Location"]
    with camp.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=ccols)
        w.writeheader()
        w.writerow({
            "Campaign": CAMPAIGN,
            "Campaign Type": "Search",
            "Campaign Subtype": "Standard",
            "Budget": "1667",
            "Bid Strategy Type": "Maximize clicks",
            "Campaign Status": "Paused",
            "Networks": "Google search",
            "Languages": "Japanese",
            "Location": LOCATIONS,
        })
    print(f"書きました: {camp}（画面で作れないときの回避策。1行）")

    add = ROOT / "data" / "ads" / "段0-追加キーワード（地域語なし）.txt"
    with add.open("w", encoding="utf-8") as f:
        for g in GROUPS:
            f.write(f"# {g['name']}（上限CPC {g.get('cpc', MAX_CPC)}円・フレーズ一致）\n")
            for k in g["bare"]:
                f.write(k + "\n")
            f.write("\n")
    print(f"  書きました: {add}")

    kwn = sum(len(g["bare"]) + len(g["phrase"]) + len(g["exact"]) for g in GROUPS)
    print(f"書きました: {OUT}")
    print(f"  広告グループ {len(GROUPS)} ／ キーワード {kwn}（除外18語と広告4本は一括では入らないので別ファイル）")
    print(f"  書きました: {neg}")
    print(f"  書きました: {admd}")
    print("  見出し・説明文の長さは全件検査済み（全角2・半角1、見出し30・説明文90）")
    return 0

if __name__ == "__main__":
    sys.exit(main())
