#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""区市ごとの「最寄りIC・船堀橋ICからの高速料金・江戸川区からの移動時間」の目安表を作る。

  python3 tools/build-kousoku-ic.py          # ドラぷらに1件ずつ聞いて data/partner-area.json を作り直す
  python3 tools/build-kousoku-ic.py --check  # 聞くだけ（書かない）

【なぜ】第6回MTG 6-4 No.4（オーナー決定）「住所を入力したら最寄りICと船堀橋IC間の高速料金を試算して表示」
  「APIの使用が有料であればリンクでもOK」。有料の経路APIは使わない。
  → NEXCO東日本のドラぷら（https://www.driveplaza.com/）の経路検索（無料・誰でも見られる結果ページ）を、
    この道具で区市ごとに1回ずつ引いて表にする。ページ（tools/build-partner.py）はこの表を持つだけで、
    開くたびに外へ問い合わせない。正確な料金は、ページからドラぷらへのリンク（出発・到着入り）で見られる。

【数字の取り方】
  出発＝船堀橋（首都高C2）・到着＝区市の最寄りIC（下の AREAS で人が決めたもの）・普通車・平日11時出発。
  ドラぷらが出す候補（最大3経路）のうち 通常時間がいちばん短い経路（同じなら ETC料金の安い方）を採る。
  （安い経路を採ると、首都高を大回りする遠回りが選ばれることがある。実際に走るのは速い経路なので速い方）
  - etc：ETC普通車・片道（円）。往復はページで×2
  - kousoku_fun：その経路の通常時間（渋滞なし）
  - idou_fun：江戸川区（船堀）から現場までの片道の目安。
      高速を使う区市 … 5分（拠点→船堀橋）＋ kousoku_fun ＋ 10分（IC→現場）を10分単位に切り上げ
      近い区市（ippan）… 高速を使わない。一般道の目安を人が決めた値（MINUTES_IPPAN）
  ドラぷらの料金は時間帯割引（深夜・休日）を含まない平日の値。首都高は距離制（上限あり）。

【使うところ】tools/build-partner.py（タカラサービス様ページの「高速代の目安」と、現調の移動時間）。
  表を作り直したら build-partner.py も流す。料金改定（首都高・NEXCO）があったら作り直すこと。
"""
import argparse
import datetime
import html
import json
import math
import pathlib
import re
import time
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "partner-area.json"
KITEN_IC = "船堀橋"
DP = "https://www.driveplaza.com/dp/SearchQuick"

# 高速を使わない近い区市の、江戸川区（船堀）からの片道の目安（分・一般道）
MINUTES_IPPAN = {"江戸川区": 15, "江東区": 25, "墨田区": 25, "葛飾区": 25, "浦安市": 20, "市川市": 25}

# (表示名, 都県, 住所の頭に来る文字列[前方一致], 最寄りIC（ドラぷらでの名前）or None=一般道, エリア外か)
# 住所は都県名を外してから前方一致で見る。いちばん長く一致したものを採る（「北区」と「横浜市港北区」を取り違えない）。
AREAS = [
    ("江戸川区", "東京都", ["江戸川区"], None, False),
    ("江東区", "東京都", ["江東区"], None, False),
    ("墨田区", "東京都", ["墨田区"], None, False),
    ("葛飾区", "東京都", ["葛飾区"], None, False),
    ("足立区", "東京都", ["足立区"], "加平", False),
    ("荒川区", "東京都", ["荒川区"], "入谷", False),
    ("台東区", "東京都", ["台東区"], "入谷", False),
    ("千代田区", "東京都", ["千代田区"], "神田橋", False),
    ("中央区", "東京都", ["中央区"], "宝町", False),
    ("港区", "東京都", ["港区"], "芝公園", False),
    ("文京区", "東京都", ["文京区"], "護国寺", False),
    ("新宿区", "東京都", ["新宿区"], "新宿", False),
    ("渋谷区", "東京都", ["渋谷区"], "渋谷", False),
    ("品川区", "東京都", ["品川区"], "戸越", False),
    ("目黒区", "東京都", ["目黒区"], "目黒", False),
    ("大田区", "東京都", ["大田区"], "平和島", False),
    ("世田谷区", "東京都", ["世田谷区"], "三軒茶屋", False),
    ("中野区", "東京都", ["中野区"], "中野長者橋", False),
    ("杉並区", "東京都", ["杉並区"], "永福", False),
    ("豊島区", "東京都", ["豊島区"], "東池袋", False),
    ("北区", "東京都", ["北区"], "王子北", False),
    ("板橋区", "東京都", ["板橋区"], "板橋本町", False),
    ("練馬区", "東京都", ["練馬区"], "中台", False),
    ("武蔵野市", "東京都", ["武蔵野市"], "永福", False),
    ("三鷹市", "東京都", ["三鷹市"], "調布", False),
    ("調布市", "東京都", ["調布市"], "調布", False),
    ("狛江市", "東京都", ["狛江市"], "調布", False),
    ("府中市", "東京都", ["府中市"], "国立府中", False),
    ("稲城市", "東京都", ["稲城市"], "稲城", False),
    ("多摩市", "東京都", ["多摩市"], "稲城", False),
    ("国分寺市", "東京都", ["国分寺市"], "国立府中", False),
    ("立川市", "東京都", ["立川市"], "国立府中", False),
    ("日野市", "東京都", ["日野市"], "国立府中", False),
    ("八王子市", "東京都", ["八王子市"], "八王子", False),
    ("町田市", "東京都", ["町田市"], "横浜町田", False),
    ("西東京市", "東京都", ["西東京市"], "大泉", False),
    ("浦安市", "千葉県", ["浦安市"], None, False),
    ("市川市", "千葉県", ["市川市"], None, False),
    ("船橋市", "千葉県", ["船橋市"], "船橋", False),
    ("習志野市", "千葉県", ["習志野市"], "湾岸習志野", False),
    ("千葉市", "千葉県", ["千葉市"], "穴川", False),
    ("八千代市", "千葉県", ["八千代市"], "千葉北", False),
    ("松戸市", "千葉県", ["松戸市"], "松戸", False),
    ("鎌ケ谷市", "千葉県", ["鎌ケ谷市", "鎌ヶ谷市"], "市川北(東京外環道)", False),
    ("柏市", "千葉県", ["柏市"], "柏", False),
    ("我孫子市", "千葉県", ["我孫子市"], "柏", False),
    ("流山市", "千葉県", ["流山市"], "流山", False),
    ("佐倉市", "千葉県", ["佐倉市"], "佐倉", False),
    ("四街道市", "千葉県", ["四街道市"], "四街道", False),
    ("市原市", "千葉県", ["市原市"], "市原", False),
    ("木更津市", "千葉県", ["木更津市"], "木更津金田", False),
    ("成田市", "千葉県", ["成田市"], "成田(東関東道)", False),
    ("川崎市 川崎区・幸区", "神奈川県", ["川崎市川崎区", "川崎市幸区", "川崎区", "幸区", "川崎市"], "大師", False),
    ("川崎市 中原区・高津区", "神奈川県", ["川崎市中原区", "川崎市高津区", "中原区", "高津区"], "京浜川崎", False),
    ("川崎市 宮前区・多摩区・麻生区", "神奈川県", ["川崎市宮前区", "川崎市多摩区", "川崎市麻生区", "宮前区", "麻生区"], "東名川崎", False),
    ("横浜市 鶴見区・神奈川区", "神奈川県", ["横浜市鶴見区", "横浜市神奈川区", "鶴見区", "神奈川区"], "子安", False),
    ("横浜市 西区・中区・南区", "神奈川県", ["横浜市西区", "横浜市中区", "横浜市南区", "横浜市"], "みなとみらい", False),
    ("横浜市 港北区・都筑区", "神奈川県", ["横浜市港北区", "横浜市都筑区", "港北区", "都筑区"], "港北", False),
    ("横浜市 青葉区・緑区", "神奈川県", ["横浜市青葉区", "横浜市緑区", "青葉区"], "横浜青葉", False),
    ("横浜市 保土ケ谷区・旭区・戸塚区", "神奈川県", ["横浜市保土ケ谷区", "横浜市保土ヶ谷区", "横浜市旭区", "横浜市戸塚区", "横浜市泉区", "横浜市瀬谷区", "保土ケ谷区", "保土ヶ谷区", "戸塚区"], "狩場", False),
    ("横浜市 磯子区・金沢区", "神奈川県", ["横浜市磯子区", "横浜市金沢区", "横浜市港南区", "横浜市栄区", "磯子区", "金沢区", "港南区"], "幸浦", False),
    ("相模原市", "神奈川県", ["相模原市"], "相模原", False),
    ("大和市", "神奈川県", ["大和市"], "横浜町田", False),
    ("厚木市", "神奈川県", ["厚木市"], "厚木", False),
    ("海老名市", "神奈川県", ["海老名市", "座間市"], "海老名", False),
    ("藤沢市", "神奈川県", ["藤沢市"], "藤沢", False),
    ("茅ヶ崎市", "神奈川県", ["茅ヶ崎市", "茅ケ崎市"], "茅ヶ崎中央", False),
    ("平塚市", "神奈川県", ["平塚市"], "平塚", False),
    ("鎌倉市", "神奈川県", ["鎌倉市"], "朝比奈", False),
    ("横須賀市", "神奈川県", ["横須賀市"], "横須賀", False),
    ("小田原市", "神奈川県", ["小田原市"], "小田原東", False),
    ("さいたま市", "埼玉県", ["さいたま市"], "外環浦和", True),
    ("川口市", "埼玉県", ["川口市"], "新井宿", True),
    ("草加市", "埼玉県", ["草加市"], "草加", True),
    ("八潮市", "埼玉県", ["八潮市"], "八潮", True),
    ("三郷市", "埼玉県", ["三郷市"], "三郷南", True),
]


def dp_url(ic: str, extra=None) -> str:
    q = {"startArrive": "true", "startPlaceKana": KITEN_IC, "arrivePlaceKana": ic}
    q.update(extra or {})
    return DP + "?" + urllib.parse.urlencode(q)


def kiku(ic: str):
    """ドラぷらの結果ページから (到着IC名, [(etc, 分, km), ...]) を取る。候補が複数あって決まらないときは None。"""
    u = dp_url(ic, {"searchHour": "11", "searchMinute": "0", "kind": "1"})
    h = urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=40).read().decode("utf-8", "replace")
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", h, flags=re.S)
    t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t)))
    title = re.search(r"(\S+?)から(\S+?)の高速料金", t)
    rs = re.findall(r"ルート \d ([\d,]+) 円 ([\d,]+) 円 ([\d,]+) 円 (\d+)時間(\d+)分 (\d+)時間(\d+)分 ([\d.]+)km", t)
    if not title or not rs:
        return None
    return title.group(2), [(int(r[1].replace(",", "")), int(r[3]) * 60 + int(r[4]), float(r[7])) for r in rs]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    out, ng = [], []
    for name, pref, match, ic, gai in AREAS:
        row = {"name": name, "pref": pref, "match": match, "eria_gai": gai}
        if ic is None:
            row.update({"ic": None, "etc": 0, "idou_fun": MINUTES_IPPAN[name], "ippan": True})
        else:
            r = kiku(ic)
            time.sleep(1.2)
            if not r:
                ng.append(f"{name}：{ic} がドラぷらで1件に決まらない")
                continue
            dest, routes = r
            etc, fun, km = sorted(routes, key=lambda x: (x[1], x[0]))[0]
            idou = int(math.ceil((5 + fun + 10) / 10.0) * 10)
            row.update({"ic": ic, "ic_hyouji": re.sub(r"\(.*?\)$", "", ic), "dp_tochaku": dest, "etc": etc,
                        "kousoku_fun": fun, "kyori_km": km, "idou_fun": idou, "ippan": False})
        out.append(row)
        print(f"{name:　<12} {row.get('ic') or '一般道':　<10} ETC片道 {row['etc']:>5}円  片道 約{row['idou_fun']}分")
    if ng:
        print("\n".join(["", "決まらなかったもの："] + ng))
    if a.check:
        return
    data = {
        "_説明": "区市ごとの最寄りIC・船堀橋ICからの高速料金（ETC普通車・片道）・江戸川区からの移動時間の目安。"
                 "tools/build-kousoku-ic.py が作る。手で直さない（AREAS を直して作り直す）。",
        "_根拠": "NEXCO東日本 ドラぷら 高速料金・ルート検索（出発＝船堀橋、到着＝表のIC、普通車、平日11時出発）。"
                 "候補経路のうち 通常時間が最も短いもの。時間帯割引は含まない。",
        "_移動時間": "高速を使う区市＝5分＋高速の通常時間＋10分を10分単位に切り上げ。近い区市（ippan）は一般道の目安を人が決めた値。渋滞は含まない。",
        "時点": datetime.date.today().isoformat(),
        "起点": {"拠点": "東京都江戸川区（船堀）", "IC": KITEN_IC + "（首都高速中央環状線）"},
        "areas": out,
    }
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("書きました:", OUT, len(out), "件")


if __name__ == "__main__":
    main()
