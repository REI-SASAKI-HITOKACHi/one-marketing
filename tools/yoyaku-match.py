#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`予約_Web` の★列を、台帳・属性メモ・各月の売上と機械で突き合わせて埋める。

設計は掲示板 `20260913-03-crm`（案A・CMO 2026-09-14 採用）。
道具化と照合の厳しさは `20260923-01-crm`（CMO 2026-09-23）。

## この道具がやること

    予約_Web の1行
      ├─ 台帳と照合   → 顧客ID・名義（自社/本舗）・最終施工日・照合の手がかり
      ├─ 属性メモ     → 乳幼児／犬・猫 などの☑を「／」でつないだもの
      ├─ 売上と照合   → ご希望日の±14日に同じ方の施工行があれば、その参照と金額
      └─ 流入元を分解 → src・cid・レントラックス注文番号（OH-…）

広告のオフラインCV（計測担当 `tools/ads-offline-cv.py`・月初）が
`★売上行への参照`・`★売上（税込）`・`★台帳の最終施工日` を読む。
**ここが埋まっていないと、戻せる行が0になる。**

## ★照合の規則（2026-09-23 CMO指定）

> **氏名＋電話の両方が同じ1人を指したときだけ「参照あり」。**
> 片方だけ一致は `★照合の手がかり` に書いて、参照は空のまま。

片方だけの一致で参照を付けると、**別人の売上を広告のCVとして送ることになる**。
実際 2026-09-17 に姓だけの一致で別人（C0724 と C0057）を同じ人と見かけた。

- **この結果、台帳でTEL空欄のお客様（957名中152名＝15.9%）には構造的に参照が付かない。**
  それでよい。付かない行は `★照合の手がかり` に「氏名だけ一致」と残るので、後から人が見て判断できる。
- **名義（`★台帳の名義`）だけは片方一致でも採る。** ここだけは規則が逆向きに見えるが、
  **取り逃すと本舗のお客様に自社名義で連絡してしまう**（2026-09-11 の事故）。
  厳しくするほど安全な列と、緩くするほど安全な列は別。`meigi_shiraberu()` のまま。

## やらないこと（大事）

- **顧客管理台帳・◯月_売上/顧客を1文字も書きません。** 読むだけ。
  台帳は `◯月_売上/顧客` から作る派生データなので、手で足すと再生成で消えるか二重になります。
  新規のお客様は「空欄＝新規」と出るだけ。施工が終わって和真さんが売上に1行入れれば、
  次の再生成で顧客IDが付きます。
- **人が手で入れる列（レントラックス注文番号・成果発生日・入金確認日）を上書きしません。**
- **他の道具・フォームの列（注文ID・gclid・NetlifyのID・受信日時…）に触りません。**
- **お客様に何も送りません。**

## ⚠️ 本舗名義のお客様の扱い

台帳の最新名義が「本舗」の方が自社のLP・予約フォームから申し込むことがあります
（台帳957名のうち **523名＝55%** が本舗名義）。

**受注は自社で構いませんが、確認連絡を SMS・LINE で送らないでください。**
施工前は台帳の最新名義がまだ本舗なので、自社名義の文面は 2026-09-11 の事故と同じことになります。
和真さんが電話で受けてください。該当行には**色が付きます**（`--列を作る` のときに条件付き書式を入れる）。

名義が「不明」の行も同じです。**照合できない相手には送らない。**

## 照合の土台

`tools/derive-soushin-keitou.py` をそのまま使います（2026-09-15 の名義照合と同じ土台）。
電話番号の正規化・氏名の正規化・見出しの `strip()`（2023年の `' 売上（税込） '` で踏んだ）を
**この道具で書き直さない**ためです。

電話番号は**文字列のまま**扱います。**数値にすると先頭の0が消えます**（過去に800件消えた事故あり）。

## 使い方

    set -a; . ~/.config/one-hitter/line.env; set +a
    python3 tools/yoyaku-match.py                 # 照合した結果を表示するだけ（既定・書かない）
    python3 tools/yoyaku-match.py --kaku          # シートに書く（週次ルーティンから）
    python3 tools/yoyaku-match.py --列を作る --kaku  # ★列の見出しと書式を用意する（最初の1回）
    python3 tools/yoyaku-match.py --自己診断      # 台帳の実在のお客様で照合の道筋を確かめる（書かない）
    python3 tools/test-yoyaku-match.py            # 偽データの検算（シートに触らない）
"""

import datetime
import importlib.util
import os
import re
import sys
import time
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _mod(name, path):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "tools", path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


sc = _mod("sc", "sheets_client.py")
meigi = _mod("meigi_check", "meigi_check.py")
dsk = _mod("derive_soushin_keitou", "derive-soushin-keitou.py")   # import しただけでは認証しない
hikae = _mod("hikae", "hikae.py")

SS = "1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64"
TAB = "予約_Web"
DAICHOU = "顧客管理台帳"
DAICHOU_HEAD = 15
ZOKUSEI = "顧客属性_メモ"
ZOKUSEI_HEAD = 4
HABA = 14          # 施工済と見なす日数の幅（ご希望日の ±14日）

# ★書くのは --kaku があるときだけ。既定は表示のみ（20260923-01-crm）
KAKU = ("--kaku" in sys.argv or "--書く" in sys.argv)
TSUKURU = "--列を作る" in sys.argv
SHINDAN = "--自己診断" in sys.argv   # 台帳の実在のお客様を使って、照合の道筋を確かめる

# 既存の見出し（A〜N）の右に足す列。★は機械が書く列。
TSUIKA = [
    "src", "cid",
    "★台帳の顧客ID", "★台帳の名義", "★台帳の最終施工日", "★照合の手がかり", "★属性",
    "★売上行への参照", "★売上（税込）",
    "レントラックス注文番号", "成果発生日", "入金確認日", "★却下判定",
]
# この道具が書いてよい列は、これだけ。ここに無い列に書こうとしたら止める（kensan_hani）。
KIKAI = {"src", "cid",
         "★台帳の顧客ID", "★台帳の名義", "★台帳の最終施工日", "★照合の手がかり", "★属性",
         "★売上行への参照", "★売上（税込）", "★却下判定",
         "レントラックス注文番号"}   # ←空のときだけ入れる
# 人が手で入れる列（空のときしか触らない）
TEUCHI = {"レントラックス注文番号", "成果発生日", "入金確認日"}


def a1(col):
    s = ""
    while col:
        col, r = divmod(col - 1, 26)
        s = chr(65 + r) + s
    return s


def hiduke(s):
    m = re.match(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", str(s or "").strip())
    if not m:
        return None
    try:
        return datetime.date(*(int(x) for x in m.groups()))
    except ValueError:
        return None


def hi_key(s):
    """日付の新しさを比べるための鍵。文字列の大小で比べると 2026/9/3 > 2026/12/1 になる。"""
    d = hiduke(s)
    return (1, d.toordinal()) if d else (0, 0)


def _api(tok, path, method="GET", payload=None, query=None, kai=4):
    """読みすぎ（429）のときだけ待って繰り返す。それ以外の失敗はそのまま上へ投げる。

    ★`sheets_client.call` は失敗すると `sys.exit()` する。`except Exception` では捕れない
    （2026-09-20 に backup-sheet-tabs.py で踏んだ）。SystemExit を見ること。
    ★**429 を「そのタブが無い」と同じ扱いにしないこと。** 黙って売上を読み飛ばすと、
    参照が付かない行が出て、広告のオフラインCVがその分だけ静かに減る。
    """
    for i in range(kai):
        try:
            return sc.call(tok, path, method, payload, query)
        except SystemExit as e:
            if "429" not in str(e) or i == kai - 1:
                raise
            time.sleep(5 * (2 ** i))


def yomu(tok, tab, rng):
    return _api(tok, f"/{SS}/values/{urllib.parse.quote(tab + '!' + rng, safe='')}").get("values", [])


def hyou_tsukuru(v, head):
    """見出し行から (見出し, 位置, 取り出す関数, データ行) を作る。見出しは strip する。"""
    h = [str(c).strip() for c in v[head - 1]]
    ix = {c: i for i, c in enumerate(h)}

    def g(r, k):
        i = ix.get(k)
        return str(r[i]).strip() if i is not None and i < len(r) else ""

    return h, ix, g, v[head:]


# ---------------------------------------------------------------- 照合（純粋な関数）
# ここから下の4つはシートに触りません。偽データで検算できます（tools/test-yoyaku-match.py）。

def daichou_hiku(daichou, tel, namae):
    """台帳から引く。**氏名と電話の両方が同じ1人を指したときだけ**参照を返す。

    返り値 (顧客ID, 最終施工日, 手がかり)。参照を付けないときは顧客IDも最終施工日も空。
    """
    t = daichou["tel"].get(tel, []) if tel else []       # [(顧客ID, 最終施工日), ...]
    n = daichou["name"].get(namae, []) if namae else []
    tc = {c for c, _ in t}
    nc = {c for c, _ in n}
    ryou = tc & nc
    if len(ryou) == 1:
        cid = next(iter(ryou))
        saishu = max((s for c, s in list(t) + list(n) if c == cid), key=hi_key, default="")
        return cid, saishu, "氏名＋電話一致"
    if len(ryou) > 1:
        return "", "", "氏名＋電話一致が複数（%s）★人が確認" % "・".join(sorted(ryou))
    katahou = []
    if tc:
        katahou.append("電話だけ一致（%s）" % "・".join(sorted(tc)))
    if nc:
        katahou.append("氏名だけ一致（%s）" % "・".join(sorted(nc)))
    if katahou:
        return "", "", "／".join(katahou) + "＝参照は付けない"
    return "", "", "該当なし（新規）"


def uriage_hiku(uriage, tel, namae, nozomi):
    """ご希望日の±14日で売上行を探す。**氏名と電話の両方が一致したときだけ**参照を返す。

    返り値 (参照, 売上（税込）, 手がかりに足す一言)。
    """
    if not nozomi:
        return "", "", ""
    chikai = [u for u in uriage if abs((u["date"] - nozomi).days) <= HABA]
    ryou = [u for u in chikai if tel and namae and u["tel"] == tel and u["name"] == namae]
    if ryou:
        ryou.sort(key=lambda u: abs((u["date"] - nozomi).days))
        return f"{ryou[0]['tab']} No.{ryou[0]['no']}", ryou[0]["kin"], ""
    katahou = [u for u in chikai
               if (tel and u["tel"] == tel) or (namae and u["name"] == namae)]
    if katahou:
        katahou.sort(key=lambda u: abs((u["date"] - nozomi).days))
        return "", "", "売上候補 %s No.%s（片方だけ一致・参照は付けない）" % (
            katahou[0]["tab"], katahou[0]["no"])
    return "", "", ""


def nagare(moto, ima_src, ima_cid, ima_rt):
    """流入元の文字列から src・cid・レントラックス注文番号（OH-…）を拾う。
    もう列に入っていればそれを優先（booking-inbox.py が独立列に入れるまでの受け口）。"""
    src = (re.search(r"src=([^\s,）)]+)", moto) or [None, ima_src])[1] or ""
    cid = (re.search(r"cid=([^\s,）)]+)", moto) or [None, ima_cid])[1] or ""
    rt = (re.search(r"(OH-[A-Za-z0-9\-]+)", moto) or [None, ima_rt])[1] or ""
    return src, cid, rt


def awaseru(rec, daichou, meigi_hyou, uriage, zokusei):
    """予約1行分の★列の値を作る。シートには触らない。

    rec = {"name", "tel", "nozomi"(文字列), "moto", "src", "cid", "rt"}
    """
    tel = dsk.tel_norm(rec.get("tel"))
    namae = dsk.name_norm(rec.get("name"))
    cid, saishu, tegakari = daichou_hiku(daichou, tel, namae)

    # 名義だけは片方一致でも採る（本舗を取り逃さないため。上の説明を参照）
    mg = "不明"
    if meigi_hyou is not None:
        mi = dsk.meigi_shiraberu(meigi_hyou, rec.get("tel"), rec.get("name"))
        if mi:
            mg = mi[0]

    sanshou, kingaku, u_te = uriage_hiku(uriage, tel, namae, hiduke(rec.get("nozomi")))
    if u_te:
        tegakari = (tegakari + "／" + u_te) if tegakari else u_te
    src, cidv, rt = nagare((rec.get("moto") or "") + " " + (rec.get("youbou") or ""),
                           rec.get("src"), rec.get("cid"), rec.get("rt"))
    return {
        "src": src, "cid": cidv,
        "★台帳の顧客ID": cid, "★台帳の名義": mg, "★台帳の最終施工日": saishu,
        "★照合の手がかり": tegakari, "★属性": zokusei.get(cid, "") if cid else "",
        "★売上行への参照": sanshou, "★売上（税込）": kingaku,
        "_rt": rt,
    }


def kensan_hani(data, ix):
    """書き込む前の検算。**予約_Web の、機械が書いてよい列以外に1セルでも向いていたら止める。**

    台帳や ◯月_売上/顧客 に1文字も書かないことを、目視ではなく機械で担保する。
    """
    retsu = {a1(ix[c] + 1): c for c in ix if c in KIKAI}
    warui = []
    for d in data:
        rng = d["range"]
        if not rng.startswith(TAB + "!"):
            warui.append(rng)
            continue
        m = re.match(r"^[A-Z]+", rng.split("!", 1)[1])
        if not m or m.group(0) not in retsu:
            warui.append(rng)
    if warui:
        raise RuntimeError("書き込み先がおかしい（止めました）: " + "・".join(warui[:10]))
    return True


# ---------------------------------------------------------------- シートを読む
def daichou_yomu(tok):
    """顧客管理台帳を読んで、電話と氏名の索引を作る。**読むだけ。**"""
    dv = yomu(tok, DAICHOU, f"A{DAICHOU_HEAD}:Q1200")
    _, _, dg, drows = hyou_tsukuru(dv, 1)
    d = {"tel": {}, "name": {}}
    for r in drows:
        cid = dg(r, "顧客ID")
        if not cid:
            continue
        rec = (cid, dg(r, "最終施工日"))
        t = dsk.tel_norm(dg(r, "TEL"))
        if t:
            d["tel"].setdefault(t, []).append(rec)
        nm = dsk.name_norm(dg(r, "顧客名"))
        if nm:
            d["name"].setdefault(nm, []).append(rec)
    return d, drows, dg


def zokusei_yomu(tok):
    zv = yomu(tok, ZOKUSEI, f"A{ZOKUSEI_HEAD}:Q1200")
    zh, _, zg, zrows = hyou_tsukuru(zv, 1)
    zoku_col = [c for c in zh[5:15] if c]
    out = {}
    for r in zrows:
        cid = zg(r, "顧客ID")
        if not cid:
            continue
        aru = [c for c in zoku_col if zg(r, c).upper() == "TRUE"]
        memo = zg(r, zh[15]) if len(zh) > 15 else ""
        out[cid] = "／".join(aru) + (f"／メモ:{memo}" if memo else "")
    return out


def uriage_yomu(tok):
    """今年の ◯月_売上/顧客 を読む。**読むだけ。**見出しは strip 済み（hyou_tsukuru）。

    実在するタブを先に調べてから、**batchGet で1回にまとめて読む**。
    月ごとに12回読むと 60回/分の上限に当たって落ちる（2026-09-23 に実際に当たった）。
    """
    meta = _api(tok, f"/{SS}", query={"fields": "sheets.properties.title"})
    tabs = [s["properties"]["title"] for s in meta["sheets"]
            if re.match(r"^\d{1,2}月_売上", s["properties"]["title"])]
    if not tabs:
        return []
    res = _api(tok, f"/{SS}/values:batchGet",
               query=[("ranges", t + "!A2:T520") for t in tabs]
                     + [("majorDimension", "ROWS")])
    uriage = []
    for tab, vr in zip(tabs, res.get("valueRanges", [])):
        uv = vr.get("values", [])
        if not uv:
            continue
        _, _, ug, urows = hyou_tsukuru(uv, 1)
        for i, r in enumerate(urows, start=4):   # 見出しが2行目、データは4行目から
            d = hiduke(ug(r, "施工日付"))
            if not d:
                continue
            uriage.append({
                "tab": tab, "no": ug(r, "No.") or str(i), "date": d,
                "tel": dsk.tel_norm(ug(r, "TEL(-無し)")),
                "name": dsk.name_norm(ug(r, "氏名")),
                "kin": ug(r, "売上（税込）"),
            })
    return uriage


# ---------------------------------------------------------------- 本体
def main():
    tok = sc.access_token(sc.load_credentials())

    # ---- 予約_Web ----
    v = yomu(tok, TAB, "A1:BZ500")
    if not v:
        sys.exit(f"{TAB} を読めません")
    head = [str(c).strip() for c in v[0]]
    ix = {c: i for i, c in enumerate(head)}

    # ★列の用意
    tarinai = [c for c in TSUIKA if c not in ix]
    if tarinai:
        print(f"足りない列: {tarinai}")
        if not TSUKURU:
            print("→ 先に: python3 tools/yoyaku-match.py --列を作る --kaku")
            return 1
        if not KAKU:
            print("→ --kaku を付けてください（既定は書きません）")
            return 1
        kaishi = len(head) + 1
        sc.call(tok, f"/{SS}/values/{urllib.parse.quote(TAB + '!' + a1(kaishi) + '1', safe='')}",
                "PUT", {"values": [tarinai]}, query={"valueInputOption": "RAW"})
        print(f"見出しを {a1(kaishi)}1 から {len(tarinai)}列 足しました")
        head = head + tarinai
        ix = {c: i for i, c in enumerate(head)}

    def g(r, k):
        i = ix.get(k)
        return str(r[i]).strip() if i is not None and i < len(r) else ""

    gyou = [(n, r) for n, r in enumerate(v[1:], start=2)
            if any(str(x).strip() for x in r)]
    print(f"{TAB}: {len(gyou)}行")
    if not gyou and not SHINDAN:
        print("まだ申し込みがありません。列だけ用意した状態です。")
        print("（データ行が0なので、確かめは偽データで: python3 tools/test-yoyaku-match.py）")
        if TSUKURU and KAKU:
            iro(tok)
        return 0

    daichou, drows, dg = daichou_yomu(tok)
    meigi_hyou, riyuu = meigi.hyou_yomu()
    if meigi_hyou is None:
        print(f"⚠️ 名義を照合できません → {riyuu}")
        print("   名義の列は「不明」にします。**この状態でお客様に連絡しないこと。**")
    zokusei = zokusei_yomu(tok)

    # ---- 自己診断：台帳の実在のお客様を「申し込みが来た」ことにして、同じ道を通す ----
    if SHINDAN:
        erabu = []
        for r in drows:
            if len(erabu) >= 6:
                break
            cid, tel, nm = dg(r, "顧客ID"), dg(r, "TEL"), dg(r, "顧客名")
            shu = dg(r, "売上種類")
            if not cid:
                continue
            # 電話あり／電話なし × 本舗／自社 が混ざるように、組み合わせごとに2名まで拾う
            key = (bool(tel), shu)
            if sum(1 for e in erabu if e[0] == key) >= 2:
                continue
            erabu.append((key, (cid, nm, tel, dg(r, "最終施工日"))))
        gyou = []
        for i, (_, (cid, nm, tel, saishu)) in enumerate(erabu, start=900):
            r = [""] * len(head)
            r[ix["お名前"]] = nm
            r[ix["お電話番号"]] = tel
            r[ix["ご希望日"]] = saishu
            r[ix["流入元"]] = "LP:mizumawari src=google cid=123456 OH-TESTONLY"
            gyou.append((i, r))
        print(f"\n== 自己診断：台帳から {len(gyou)}名を「申し込みが来た」ことにして通します ==")
        print("   （シートには書きません。照合の道筋が通るかだけを見ます）")

    uriage = uriage_yomu(tok)

    # ---- 1行ずつ ----
    data, hyouji = [], []
    for n, r in gyou:
        kaku = awaseru({
            "name": g(r, "お名前"), "tel": g(r, "お電話番号"), "nozomi": g(r, "ご希望日"),
            "moto": g(r, "流入元"), "youbou": g(r, "ご要望"),
            "src": g(r, "src"), "cid": g(r, "cid"), "rt": g(r, "レントラックス注文番号"),
        }, daichou, meigi_hyou, uriage, zokusei)
        rt = kaku.pop("_rt")
        if rt and not g(r, "レントラックス注文番号"):
            kaku["レントラックス注文番号"] = rt
        for k, val in kaku.items():
            if k not in ix:
                continue
            if k in TEUCHI and g(r, k):
                continue
            data.append({"range": f"{TAB}!{a1(ix[k]+1)}{n}", "values": [[val]]})
        # 却下判定（式。38日で入金未確認なら「要却下」）
        c_rt, c_hassei, c_nyuukin = (a1(ix["レントラックス注文番号"] + 1),
                                     a1(ix["成果発生日"] + 1), a1(ix["入金確認日"] + 1))
        shiki = (f'=IF(AND({c_rt}{n}<>"",{c_nyuukin}{n}="",{c_hassei}{n}<>"",'
                 f'TODAY()-{c_hassei}{n}>=38),"要却下","")')
        data.append({"range": f"{TAB}!{a1(ix['★却下判定']+1)}{n}", "values": [[shiki]]})

        hyouji.append((n, g(r, "お名前"), kaku["★台帳の顧客ID"] or "新規", kaku["★台帳の名義"],
                       kaku["★照合の手がかり"], kaku["★売上行への参照"]))

    print(f"\n{'行':>3} {'お名前':<12} {'顧客ID':<8} {'名義':<4} {'手がかり':<12} 売上")
    for n, na, cid, mg, tg, sa in hyouji:
        mark = " ⚠️本舗" if mg == "本舗" else ("  ⚠️名義不明" if mg == "不明" else "")
        print(f"{n:>3} {na:<12} {cid:<8} {mg:<4} {tg:<12} {sa}{mark}")
    honpo = sum(1 for x in hyouji if x[3] == "本舗")
    fumei = sum(1 for x in hyouji if x[3] == "不明")
    sanshou = sum(1 for x in hyouji if x[5])
    print(f"\n本舗名義: {honpo}件／名義不明: {fumei}件"
          f"（この方々には SMS・LINE で連絡しない。電話のみ）")
    print(f"売上行への参照が付いた行: {sanshou}/{len(hyouji)}件"
          f"（氏名＋電話の両方が一致した行だけ）")

    if SHINDAN:
        print("\n自己診断なので書き込みません。")
        muke = [x for x in hyouji if x[2] == "新規" and "電話だけ" not in x[4] and "氏名だけ" not in x[4]]
        if muke:
            print(f"★★ 台帳から採ったのに、手がかりすら出なかった人がいます: {len(muke)}名")
            for x in muke:
                print("   ", x)
            return 1
        katahou = [x for x in hyouji if x[2] == "新規"]
        print(f"★ 照合の道筋は通っています（うち片方だけ一致で参照を付けなかった人 {len(katahou)}名）。")
        return 0
    if not KAKU:
        print(f"\n書き込みません（既定は表示のみ）。書くには: --kaku  ／ 書く予定 {len(data)}セル")
        return 0

    kensan_hani(data, ix)          # ★予約_Web の機械の列以外に向いていたら、ここで止まる
    hikae.git_ni_toru(tok, TAB)    # 控えが取れなかったら例外。書かない
    sc.call(tok, f"/{SS}/values:batchUpdate", "POST",
            {"valueInputOption": "USER_ENTERED", "data": data})
    print(f"\n書き込みました: {len(data)}セル")
    if TSUKURU:
        iro(tok)
    return 0


def iro(tok):
    """台帳の名義が「本舗」の行に色を付ける。SMS・LINEで連絡しないことを目で分かるように。"""
    meta = sc.call(tok, f"/{SS}?fields=sheets.properties")
    gid = [s["properties"]["sheetId"] for s in meta["sheets"]
           if s["properties"]["title"] == TAB][0]
    v = sc.call(tok, f"/{SS}/values/{urllib.parse.quote(TAB + '!A1:BZ1', safe='')}").get("values", [])
    head = [str(c).strip() for c in (v[0] if v else [])]
    if "★台帳の名義" not in head:
        return
    c = a1(head.index("★台帳の名義") + 1)
    # ★条件付き書式は「先に当たった規則が勝つ」。index 0 に入れる（2026-09-19 に踏んだ）
    sc.call(tok, f"/{SS}:batchUpdate", "POST", {"requests": [{"addConditionalFormatRule": {
        "rule": {
            "ranges": [{"sheetId": gid, "startRowIndex": 1, "endRowIndex": 500,
                        "startColumnIndex": 0, "endColumnIndex": len(head)}],
            "booleanRule": {
                "condition": {"type": "CUSTOM_FORMULA",
                              "values": [{"userEnteredValue": f'=OR(${c}2="本舗",${c}2="不明")'}]},
                "format": {"backgroundColor": {"red": 1.0, "green": 0.90, "blue": 0.80}}}},
        "index": 0}}]})
    print("条件付き書式：名義が「本舗」「不明」の行に色を付けました（SMS・LINEで連絡しない印）")


if __name__ == "__main__":
    sys.exit(main())
