#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`顧客管理台帳` を、月次タブ（2023〜2026年の `◯月_売上/顧客`）から機械で増やし・更新する。

依頼 `20260930-02-crm`（CMO・オーナー 9/30「顧客台帳の製作って進んでる？」）。
台帳は 2026-09-05 に貼った**値のまま**で、月次タブから自動では増えていなかった。

    set -a; . ~/.config/one-hitter/line.env; set +a
    python3 tools/daichou-koushin.py            # 何が変わるかを出すだけ（既定・書かない）
    python3 tools/daichou-koushin.py --kaku     # 書く（控えを git に取ってから）
    python3 tools/test-daichou-koushin.py       # 偽データの検算（シートに触らない）

## 作り方は 9/5 の台帳から逆算して、検算してある

9/5 に台帳を作った道具はリポジトリに無い。そこで「件数と金額が今の台帳と一致した928名」で、
各列の作り方を当てて確かめた（2026-09-30）。

| 列 | 作り方 | 一致 |
|---|---|---|
| 平均単価・最高単価・初回/最終施工日・最終月・利用年 | 素直な集計 | 926〜928 / 928 |
| 売上種類 | **いちばん新しい施工の売上種類。同じ日に本舗があれば本舗**（和真さん 9/20 の同日ルール） | 906 / 928 |
| 主な流入経路 | いちばん多い流入経路 | 915 / 928 |
| 施工メニュー（内訳） | 実施メニューの回数を多い順に「X×n」で「／」区切り | 904 / 928（違いは同数の並び順だけ） |
| 種目の12列 | 実施メニューを下の CAT で振り分けた回数（空欄は「その他」） | 926〜928 / 928 |
| 次のおすすめ | 換気扇→浴室→キッチン→洗濯機 のうち未購入の先頭2つ | 927 / 928 |
| 経過(月) | （今日−最終施工日）÷30.4 を小数1桁。**毎回今日で計算し直す** | 基準日の違いで±0.1 |

## 誰の施工かの決め方（電話番号が先、氏名は補助）

1. 電話番号が台帳の1人にだけ当たる → その人
2. 電話番号が台帳の2人以上に当たる → **要確認（どちらにも入れない）**
3. 電話番号はあるが台帳に無い：
   - 氏名が台帳の1人に当たり、その人の電話が空欄 → その人
   - 氏名が台帳の人に当たるが、その人には**別の電話**がある → **別の人として新しく足す**
     （同姓同名は統合しない。CMO 9/30：C0389 と C0959 の例）。報告に「同じ氏名の既存あり」と出す
   - 氏名も当たらない → 新しいお客様
4. 電話番号が無い：氏名が1人に当たる → その人／2人以上 → 要確認／0人 → 新しいお客様

氏名は空白を除いて比べる。台帳の「統合した表記」（AF列）に並んでいる別表記も、その人の氏名として使う。

## 書かないもの（大事）

- **月次タブ（過去の実績）には1文字も書かない。** 読むだけ。
- 既存のお客様の **顧客ID・顧客名・法人/個人・TEL・郵便番号・住所（A〜F）は書き換えない。**
- **AF（統合した表記）・AG（クレーム履歴）は人が書く欄。触らない。**
- **AE（施工メニュー（内訳））に「★」が入っていたら、その人の AE は書き換えない**（注記を残す）。
- **台帳の件数のほうが多い人は触らない。** 9/5 に複数の電話・表記を1人にまとめた人（例：C0089 は台帳21件・電話で引くと3件）。
  減らす方向に書き換えると、その人の履歴が消える。報告に出すだけ。
- 書く前に `kensan_hani()` が全セルの宛先を検査する。台帳の許された列以外なら例外で止まる。

電話番号・郵便番号は**文字列のまま**書く（RAW）。数値にすると先頭の0が消える（過去に800件消えた事故）。
"""

import collections
import datetime
import importlib.util
import json
import os
import re
import sys
import time
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOOKS = {"2023": "1mOGaxy5viO4peUUQqgJYQ9gp0tuev2c_Y8DrdDy-y3M",
         "2024": "1Q-dJ0Rh2AeYGhNYUyqoKOkG_Kgq4e1M0KcwkhMFb0J4",
         "2025": "1cpN2tu6NNIA5FSAAC3ejCK0jNNFNfn7GCwq0ghggK3o",
         "2026": "1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64"}
SS = BOOKS["2026"]
TAB = "顧客管理台帳"
HEAD = 15               # 見出し行。データは16行目から
SAIGO = 1200            # ダッシュボードの式が見ている最後の行（$A$16:$A$1200）
EPOCH = datetime.date(1899, 12, 30)
OOSUGI = 30             # 1回で新しく足すお客様がこれより多ければ止める（読み違いの疑い）

KAKU = "--kaku" in sys.argv
OOI_OK = "--ooi-ok" in sys.argv

CAT = [("エアコン(家庭用)", r"^エアコン"), ("業務用エアコン", r"天カセ|業務用"), ("浴室", r"浴室"),
       ("換気扇", r"換気扇"), ("キッチン", r"キッチン"), ("洗濯機", r"洗濯機"),
       ("トイレ・洗面台", r"トイレ|洗面"), ("追焚配管", r"追焚|追い焚"), ("まるごと", r"まるごと"),
       ("空室", r"空室"), ("定期清掃・定期便", r"定期")]
CAT_NAMES = [c for c, _ in CAT] + ["その他"]
OSUSUME = ["換気扇", "浴室", "キッチン", "洗濯機"]
HOUJIN_KW = (r"株式会社|有限会社|合同会社|（株）|\(株\)|㈱|法人|組合|学校|病院|協会|会社|事務所|"
             r"教習所|センター|施設|マンション|不動産|工業|建設|商事|管理")

# 集計で書く列（既存のお客様）。A〜F・AF・AG は書かない。
SHUUKEI = ["受注回数", "合計受注額", "平均単価", "最高単価", "初回施工日", "最終施工日", "経過(月)",
           "最終月", "利用年", "主な流入経路", "売上種類"] + CAT_NAMES + ["次のおすすめ", "施工メニュー（内訳）"]
SHINKI_DAKE = ["顧客ID", "顧客名", "法人/個人", "TEL", "郵便番号", "住所"]
KAKENAI = {"統合した表記", "クレーム履歴（日付・内容・対応）"}


def tn(t):
    """電話番号は**文字列のまま**。数字だけ残す。"""
    return re.sub(r"\D", "", str(t or ""))


def nn(n):
    return re.sub(r"[\s　]", "", str(n or ""))


def hi(s):
    m = re.match(r"(\d{4})/(\d{1,2})/(\d{1,2})", str(s or "").strip())
    if not m:
        return None
    try:
        return datetime.date(*map(int, m.groups()))
    except ValueError:
        return None


def yen(x):
    return int(re.sub(r"[^\d]", "", str(x)) or 0)


def serial(d):
    return (d - EPOCH).days


def cat(v):
    for c, p in CAT:
        if re.search(p, v):
            return c
    return "その他"


def a1(col):
    s = ""
    while col:
        col, r = divmod(col - 1, 26)
        s = chr(65 + r) + s
    return s


# ---------------------------------------------------------------- 集計（純粋な関数）
def shuukei(js, kyou):
    """1人ぶんの施工行から、台帳の集計列を作る。js は dict(d, k, menu, keiro, shu) の並び。"""
    n = len(js)
    s = sum(j["k"] for j in js)
    saigo = max(j["d"] for j in js)
    sonohi = {j["shu"] for j in js if j["d"] == saigo and j["shu"]}
    shu = "本舗" if "本舗" in sonohi else (sorted(sonohi)[0] if sonohi else "")
    keiro = collections.Counter(j["keiro"] for j in js if j["keiro"])
    menu = collections.Counter(j["menu"] for j in js if j["menu"])
    cats = collections.Counter(cat(j["menu"]) if j["menu"] else "その他" for j in js)
    out = {
        "受注回数": n, "合計受注額": s, "平均単価": round(s / n), "最高単価": max(j["k"] for j in js),
        "初回施工日": serial(min(j["d"] for j in js)), "最終施工日": serial(saigo),
        "経過(月)": round((kyou - saigo).days / 30.4, 1), "最終月": saigo.month,
        "利用年": "／".join(sorted({str(j["d"].year) for j in js})),
        "主な流入経路": keiro.most_common(1)[0][0] if keiro else "",
        "売上種類": shu,
        "施工メニュー（内訳）": "／".join(f"{k}×{v}" for k, v in sorted(menu.items(), key=lambda kv: -kv[1])),
    }
    for c in CAT_NAMES:
        out[c] = cats.get(c, 0)
    out["次のおすすめ"] = "・".join([o for o in OSUSUME if out[o] == 0][:2])
    return out


def wariate(jobs, led, tarinai=None):
    """施工行を台帳のお客様に割り当てる。

    返り値 (割当 {顧客ID: [job]}, 新規 [[job]], 要確認 [(job, 理由)], 注意 [str])
    led は [{顧客ID, 顧客名, TEL, 統合した表記}]。
    tarinai は {顧客ID: 最終施工日(date)}：電話と氏名だけでは台帳の件数に届かない人（9/5 に別の電話をまとめた人）。
    """
    tarinai = tarinai or {}
    by_tel, by_name, tel_of = collections.defaultdict(set), collections.defaultdict(set), {}
    for x in led:
        cid = x["顧客ID"]
        t = tn(x.get("TEL"))
        tel_of[cid] = t
        if t:
            by_tel[t].add(cid)
        for nm in [x.get("顧客名")] + str(x.get("統合した表記") or "").split("／"):
            if nn(nm):
                by_name[nn(nm)].add(cid)
    wari, shinki, youkaku, chuui = collections.defaultdict(list), [], [], []
    for j in jobs:
        t, n = j["t"], j["n"]
        if t and t in by_tel:
            ids = by_tel[t]
            if len(ids) == 1:
                wari[next(iter(ids))].append(j)
                continue
            # 家族で1つの電話を使っている（台帳では氏名で分けてある）。氏名で1人に絞れればその人
            shibori = ids & by_name.get(n, set())
            if len(shibori) == 1:
                wari[next(iter(shibori))].append(j)
            else:
                youkaku.append((j, "電話番号が台帳の%d人に当たり、氏名で絞れない（%s）" % (len(ids), "・".join(sorted(ids)))))
            continue
        ids = by_name.get(n, set())
        if t:
            sora = [c for c in ids if not tel_of.get(c)]
            # 9/5 の台帳で「別の電話の施工」もまとめて数えてある人の、その施工。
            # 台帳の件数のほうが多く、この施工がその人の最終施工日以前なら、9/5 と同じくその人に入れる。
            matome = [c for c in ids if c in tarinai and j["d"] <= tarinai[c]]
            if len(ids) == 1 and sora:
                wari[sora[0]].append(j)
            elif len(ids) == 1 and matome:
                wari[matome[0]].append(j)
            else:
                if ids:
                    j = dict(j, _chuui="同じ氏名の既存あり（%s・電話が違う）→ 別の人として追加" % "・".join(sorted(ids)))
                shinki.append(j)
            continue
        if len(ids) == 1:
            wari[next(iter(ids))].append(j)
        elif len(ids) > 1:
            youkaku.append((j, "氏名が台帳の%d人に当たり、電話が無い（%s）" % (len(ids), "・".join(sorted(ids)))))
        else:
            shinki.append(j)
    # 新しいお客様をまとめる：電話があれば電話で、無ければ氏名で。
    # 電話の無い行は、氏名が1つの電話グループにだけ当たればそこへ入れる。
    g_tel, g_name = collections.OrderedDict(), collections.OrderedDict()
    for j in shinki:
        if j["t"]:
            g_tel.setdefault(j["t"], []).append(j)
    for j in shinki:
        if not j["t"]:
            atari = [t for t, js in g_tel.items() if any(x["n"] == j["n"] for x in js)]
            if len(atari) == 1:
                g_tel[atari[0]].append(j)
            else:
                g_name.setdefault(j["n"], []).append(j)
    groups = list(g_tel.values()) + list(g_name.values())
    for g in groups:
        for j in g:
            if j.get("_chuui"):
                chuui.append(j["_chuui"])
                break
    return wari, groups, youkaku, chuui


def sabun(x, atarashii):
    """既存の1人の、書き換える列と値。台帳の件数のほうが多ければ None（触らない）。"""
    if atarashii["受注回数"] < int(float(x.get("受注回数") or 0)):
        return None
    # 件数・金額・初回/最終施工日が同じなら、施工行は増えも変わりもしていない。
    # そのときは 経過(月) だけ直す。同数の並び順などの小さな違いで 9/5 の値を書き換えないため。
    kawatta = any(_num(x.get(k)) != _num(atarashii[k])
                  for k in ("受注回数", "合計受注額", "初回施工日", "最終施工日"))
    out = {}
    for k in (SHUUKEI if kawatta else ["経過(月)"]):
        if k == "施工メニュー（内訳）" and "★" in str(x.get(k) or ""):
            continue
        a, b = atarashii[k], x.get(k, "")
        same = (str(a) == str(b)) or (isinstance(a, (int, float)) and str(b).strip() != ""
                                      and _num(b) is not None and abs(a - _num(b)) < 1e-9)
        if not same:
            out[k] = a
    return out


def _num(b):
    try:
        return float(b)
    except (TypeError, ValueError):
        return None


def kensan_hani(data, ix):
    """書き込み先の検査。**台帳の、書いてよい列以外に1セルでも向いていたら止める。**"""
    yoi = {a1(ix[c] + 1) for c in ix if c in set(SHUUKEI) | set(SHINKI_DAKE)}
    warui = []
    for d in data:
        rng = d["range"]
        if not rng.startswith(TAB + "!"):
            warui.append(rng)
            continue
        m = re.match(r"^([A-Z]+)(\d+)$", rng.split("!", 1)[1])
        if not m or m.group(1) not in yoi or not (HEAD < int(m.group(2)) <= SAIGO):
            warui.append(rng)
    if warui:
        raise RuntimeError("書き込み先がおかしい（止めました）: " + "・".join(warui[:10]))
    return True


# ---------------------------------------------------------------- シートを読む
def _sc():
    spec = importlib.util.spec_from_file_location("sc", os.path.join(ROOT, "tools", "sheets_client.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _api(sc, *a, **k):
    """読みすぎ（429）のときだけ待って繰り返す。sheets_client は失敗すると sys.exit する。"""
    for i in range(8):
        try:
            return sc.call(*a, **k)
        except SystemExit as e:
            if "429" not in str(e) or i == 7:
                raise
            time.sleep(20 * (i + 1))


def jobs_yomu(sc, tok):
    """2023〜2026年の月次タブの施工行。**読むだけ。**見出しは strip（2023の ' 売上（税込） ' 対策）。"""
    jobs = []
    for y, ss in BOOKS.items():
        meta = _api(sc, tok, f"/{ss}", query={"fields": "sheets.properties.title"})
        tabs = [s["properties"]["title"] for s in meta["sheets"]
                if re.match(r"^\d{1,2}月_売上", s["properties"]["title"])]
        res = _api(sc, tok, f"/{ss}/values:batchGet",
                   query=[("ranges", t + "!A1:V520") for t in tabs]
                   + [("valueRenderOption", "UNFORMATTED_VALUE"), ("dateTimeRenderOption", "FORMATTED_STRING")])
        for t, vr in zip(tabs, res.get("valueRanges", [])):
            v = vr.get("values", [])
            h_i = next((i for i, r in enumerate(v[:5]) if any(str(c).strip() == "施工日付" for c in r)), None)
            if h_i is None:
                continue
            h = [str(c).strip() for c in v[h_i]]
            ix = {c: i for i, c in enumerate(h) if c}

            def g(r, k):
                i = ix.get(k)
                return str(r[i]).strip() if i is not None and i < len(r) else ""
            for n, r in enumerate(v[h_i + 1:], start=h_i + 2):
                d, nm = hi(g(r, "施工日付")), nn(g(r, "氏名"))
                if not d or not nm:
                    continue
                jobs.append({"d": d, "t": tn(g(r, "TEL(-無し)")), "n": nm, "k": yen(g(r, "売上（税込）")),
                             "menu": g(r, "実施メニュー"), "keiro": g(r, "流入経路"),
                             "shu": g(r, "売上種類"), "namae": g(r, "氏名"),
                             "yuubin": tn(g(r, "郵便番号(-無し)")), "juusho": g(r, "住所"),
                             "houjin": g(r, "法人名"), "_moto": f"{y}:{t} {n}行"})
    return jobs


def main():
    sc = _sc()
    tok = sc.access_token(sc.load_credentials())
    kyou = datetime.date.today()
    L = _api(sc, tok, f"/{SS}/values/{urllib.parse.quote(f'{TAB}!A{HEAD}:AH{SAIGO}', safe='')}",
             query={"valueRenderOption": "UNFORMATTED_VALUE"}).get("values", [])
    h = [str(c).strip() for c in L[0]]
    ix = {c: i for i, c in enumerate(h)}
    for need in SHUUKEI + SHINKI_DAKE + list(KAKENAI):
        if need not in ix:
            sys.exit(f"台帳に「{need}」列がありません。列の並びが変わった可能性。止めます")
    led, gyou = [], {}
    for n, r in enumerate(L[1:], start=HEAD + 1):
        if r and str(r[0]).strip():
            x = {k: (r[i] if i < len(r) else "") for k, i in ix.items()}
            led.append(x)
            gyou[x["顧客ID"]] = n
    saigo_gyou = max(gyou.values())
    print(f"台帳: {len(led)}名（最後の行 {saigo_gyou}）")

    jobs = jobs_yomu(sc, tok)
    print(f"月次タブの施工行: {len(jobs)}件（2023〜2026）")
    # 1回目で「台帳の件数に届かない人」を見つけ、2回目でその人の別の電話の施工を拾う
    wari, _, _, _ = wariate(jobs, led)
    tarinai = {x["顧客ID"]: EPOCH + datetime.timedelta(days=int(float(x["最終施工日"])))
               for x in led if str(x.get("最終施工日")).strip()
               and len(wari.get(x["顧客ID"], [])) < int(float(x.get("受注回数") or 0))}
    wari, shinki, youkaku, chuui = wariate(jobs, led, tarinai)

    data, koushin, fureru_nai = [], [], []
    for x in led:
        js = wari.get(x["顧客ID"])
        if not js:
            continue
        s = sabun(x, shuukei(js, kyou))
        if s is None:
            fureru_nai.append((x["顧客ID"], int(float(x["受注回数"] or 0)), len(js)))
            continue
        if s:
            keika_dake = set(s) <= {"経過(月)"}
            koushin.append((x["顧客ID"], s, keika_dake))
            for k, val in s.items():
                data.append({"range": f"{TAB}!{a1(ix[k] + 1)}{gyou[x['顧客ID']]}", "values": [[val]]})

    saidai = max(int(x["顧客ID"][1:]) for x in led if re.fullmatch(r"C\d+", str(x["顧客ID"])))
    atarashii_gyou = []
    for i, g in enumerate(shinki):
        cid = f"C{saidai + 1 + i:04d}"
        n = saigo_gyou + 1 + i
        a = shuukei(g, kyou)
        g2 = sorted(g, key=lambda j: j["d"])
        saishin = g2[-1]
        namae = saishin["namae"]
        houjin = "法人" if (any(j["houjin"] for j in g) or re.search(HOUJIN_KW, namae)) else "個人"
        rec = dict(a, **{"顧客ID": cid, "顧客名": namae, "法人/個人": houjin,
                         "TEL": next((j["t"] for j in reversed(g2) if j["t"]), ""),
                         "郵便番号": next((j["yuubin"] for j in reversed(g2) if j["yuubin"]), ""),
                         "住所": next((j["juusho"] for j in reversed(g2) if j["juusho"]), "")})
        atarashii_gyou.append((cid, n, rec, g))
        for k in SHINKI_DAKE + SHUUKEI:
            data.append({"range": f"{TAB}!{a1(ix[k] + 1)}{n}", "values": [[rec[k]]]})

    # ---- 表示（氏名・電話は出さない。顧客IDと件数だけ）----
    honmono = [c for c in koushin if not c[2]]
    print(f"\n既存のお客様で中身が変わる人: {len(honmono)}名（ほかに 経過(月) だけ変わる人 {len(koushin) - len(honmono)}名）")
    for cid, s, _ in honmono[:40]:
        print(f"  {cid}: " + "・".join(f"{k}" for k in s if k != "経過(月)"))
    print(f"\n新しく足すお客様: {len(atarashii_gyou)}名（{a1(1)}{saigo_gyou + 1} から）")
    for cid, n, rec, g in atarashii_gyou:
        print(f"  {cid}（{n}行目）: {rec['受注回数']}件 最終 {max(j['d'] for j in g)} 売上種類={rec['売上種類'] or '空'} 法人/個人={rec['法人/個人']}（推定）")
    for c in chuui:
        print("  ⚠", c)
    print(f"\n触らない人（台帳の件数のほうが多い＝9/5 に表記をまとめた人）: {len(fureru_nai)}名")
    for cid, a, b in fureru_nai[:20]:
        print(f"  {cid}: 台帳 {a}件／月次から引けたのは {b}件")
    print(f"\n要確認（どの人にも入れていない施工行）: {len(youkaku)}件")
    for j, why in youkaku[:20]:
        print(f"  {j['_moto']} {j['d']}: {why}")

    if not data:
        print("\n変わるものはありません。")
        return 0
    if not KAKU:
        print(f"\n書きません（既定）。書く予定 {len(data)}セル。書くには --kaku")
        return 0
    if len(atarashii_gyou) > OOSUGI and not OOI_OK:
        sys.exit(f"新しく足すお客様が {len(atarashii_gyou)}名（>{OOSUGI}）。読み違いの疑い。確かめてから --ooi-ok を付けて")
    if saigo_gyou + len(atarashii_gyou) > SAIGO:
        sys.exit(f"{SAIGO}行を超えます。ダッシュボードの式の範囲を広げてから")
    kensan_hani(data, ix)
    hikae = _hikae()
    hikae.git_ni_toru(tok, TAB, f"A1:AH{SAIGO}")    # 控えが取れなければ例外。書かない
    if atarashii_gyou:
        # 新しい行に、いちばん下の行の書式を写す（日付・金額の表示をそろえる）
        meta = _api(sc, tok, f"/{SS}", query={"fields": "sheets.properties(title,sheetId)"})
        gid = [s["properties"]["sheetId"] for s in meta["sheets"] if s["properties"]["title"] == TAB][0]
        _api(sc, tok, f"/{SS}:batchUpdate", "POST", {"requests": [{"copyPaste": {
            "source": {"sheetId": gid, "startRowIndex": saigo_gyou - 1, "endRowIndex": saigo_gyou,
                       "startColumnIndex": 0, "endColumnIndex": len(h)},
            "destination": {"sheetId": gid, "startRowIndex": saigo_gyou,
                            "endRowIndex": saigo_gyou + len(atarashii_gyou),
                            "startColumnIndex": 0, "endColumnIndex": len(h)},
            "pasteType": "PASTE_FORMAT"}}]})
    # ★RAW：電話番号・郵便番号を文字列のまま入れる（数値にすると先頭の0が消える）
    for i in range(0, len(data), 500):
        _api(sc, tok, f"/{SS}/values:batchUpdate", "POST",
             {"valueInputOption": "RAW", "data": data[i:i + 500]})
    print(f"\n書きました: {len(data)}セル（既存 {len(koushin)}名・新規 {len(atarashii_gyou)}名）")
    print("★控えのコミットを忘れないこと（data/sheets/backup/）")
    return 0


def _hikae():
    spec = importlib.util.spec_from_file_location("hikae", os.path.join(ROOT, "tools", "hikae.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


if __name__ == "__main__":
    sys.exit(main())
