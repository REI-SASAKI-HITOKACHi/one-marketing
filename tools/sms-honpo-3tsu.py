#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本舗名義SMSの3通案を、全員ぶん差し込んで検算し、F列（送信する本文）を作り直す。

## なぜこれが要るか

KDDI Message Cast は **1通＝全角70文字**で、超えると自動分割して**分割後の通数で課金**される
（2026-09-13 KDDI内野氏の回答）。元の確定版は451文字＝**7通＝77円/人**だった。
オーナーが 9/14 に 3通案（210文字以内）を選んだので、
**「差し込んだあとに、本当に全員が3通に収まるか」を機械で確かめてから**シートに入れる。

ひな形は `data/sms-template-honpo.txt`。差し込みの規則は cmo の `tools/build-sms-list.py` と
**同じ関数をここに写して**ある（`sei` `itsu` `menu_hitotsu`）。食い違うと文面が変わるため。

## 使い方

    . ~/.config/one-hitter/line.env
    python3 tools/sms-honpo-3tsu.py                  # 検算だけ（既定）
    python3 tools/sms-honpo-3tsu.py --3通            # 70文字ごとの区切りを表示（オーナー提示用）
    python3 tools/sms-honpo-3tsu.py --confirm WRITE  # F列を書き換える（本舗・未送信の行だけ）

## 書き換える範囲

**`送信系統` が「本舗」で、`送信済み` が空欄の行の F列だけ。**
送信済み・返信あり・不通エラー・対象外の行は触らない。自社の行も触らない。

## 送信について

**このツールは1通も送りません。** F列（和真さんが読む控え）を作り直すだけです。
KDDI の利用開始は 9/25 ごろ。送信はそれ以降、オーナーの承認を得てから。
"""

import importlib.util
import math
import os
import re
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("sc", os.path.join(ROOT, "tools", "sheets_client.py"))
sc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sc)

SS = "1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64"
TAB = "冬季見込み客_2026"
HEAD_ROW = 5                       # 見出しの行
HINAGATA = os.path.join(ROOT, "data", "sms-template-honpo.txt")
# 文面の案を試すとき用。--ひな形 <path> で別のひな形を当てて字数と通数だけ見る。
# ★案を試すだけなので、--confirm WRITE とは一緒に使えない（下で弾く）。
if "--ひな形" in sys.argv:
    HINAGATA = sys.argv[sys.argv.index("--ひな形") + 1]

UNIT = 70                          # KDDI：1通＝70文字
MAX_UNITS = 3                      # 3通案
PRICE = 11.0                       # 税込11円/通（税抜10.0の階梯）

# ★70文字ごとに自動分割されたとき、**通の境界をまたいではいけない文字列**。
#   端末で1通に結合して表示されるかは KDDI 未回答（2026-09-17）。
#   結合されない端末では、またいだ番号は2つにちぎれて押せなくなる。
#   **確認を待たず、またがない形にする**（CMO 2026-09-18）。
MATAGANAI = ["080-1344-3137"]

# D列「▶ 送る」のリンク先。社内用の中継ページ（cmo の build-sms-list.py と同じ）。
# ★宛先と本文は「#」より後ろ（フラグメント）に入れる。サーバーに送られないので、
#   Netlify の記録にお客様の電話番号も本文も残らない。「?」に変えないこと。
SMS_PAGE = "https://oh-naibu-sms-k7q3x.netlify.app/s.html"

# 法人かどうかの見分け（CMO 2026-09-15 09:04）。
# ★「法人/個人」列は使いません。両方向にずれています（山口様は「個人」なのに株式会社、
#   逆に「法人」に個人名が混ざっている）。
HOUJIN_KAKU = ["株式会社", "有限会社", "合同会社", "(株)", "（株）", "(有)", "（有）", "㈱", "㈲"]
HANTEI_FILE = os.path.join(ROOT, "data", "sms-houjin-hantei.txt")
TEIKEI_TAB = "【毎月更新】リピート/業務提携"

import datetime
KYOU = datetime.date.today().isoformat()

WRITE = ("--confirm" in sys.argv and "WRITE" in sys.argv)
if WRITE and "--ひな形" in sys.argv:
    sys.exit("--ひな形 は案を試すためのものです。--confirm WRITE とは一緒に使えません。")
SHOW3 = "--3通" in sys.argv

# ---- 差し込みの規則（tools/build-sms-list.py と同じもの）----
IIKAE = {
    'エアコン(ノーマル)': 'エアコンクリーニング',
    'エアコン(ロボ)': 'お掃除機能付きエアコンのクリーニング',
    '天カセ': '天井カセットエアコンのクリーニング',
    'まるごと(備考に内容)': 'お住まいのクリーニング',
    'レンジフード': 'レンジフードクリーニング',
    '換気扇': '換気扇クリーニング',
    '浴室': '浴室クリーニング',
    'キッチン': 'キッチンクリーニング',
    '洗濯機': '洗濯機クリーニング',
    'トイレ': 'トイレクリーニング',
    '洗面台': '洗面台クリーニング',
    'コンロ': 'コンロクリーニング',
    '追い焚き': '追い焚き配管クリーニング',
    '床WAX': '床のワックスがけ',
    '洗濯機(ノーマル)': '洗濯機クリーニング',
    '追焚配管': '追い焚き配管クリーニング',
    '空室': '空室クリーニング',
}


def a1(col):
    s = ""
    while col:
        col, r = divmod(col - 1, 26)
        s = chr(65 + r) + s
    return s


def sei(shimei):
    na = shimei.strip()
    na = re.split(r'[（(]', na)[0].strip()
    s = re.split(r'[\s　]+', na)
    na = s[0] if s and s[0] else na
    na = re.sub(r'(様|さま|さん|殿|御中)$', '', na)
    return na or shimei.strip()


def itsu(saishu):
    m = re.match(r'(\d{4})[/-](\d{1,2})', saishu)
    if not m:
        return ''
    toshi, tsuki = int(m.group(1)), int(m.group(2))
    IMA = 2026
    if toshi == IMA:
        return f'今年{tsuki}月'
    if toshi == IMA - 1:
        return f'昨年{tsuki}月'
    return f'{toshi}年{tsuki}月'


def menu_hitotsu(uchiwake):
    if not uchiwake:
        return ''
    namae = uchiwake.split('／')[0].split('×')[0].strip()
    return IIKAE.get(namae, namae + 'のクリーニング' if namae else '')


def hantei_yomu():
    """CMOが個別に決めた答えを読む。{"送る": set, "別対応": set}"""
    out = {"送る": set(), "別対応": set()}
    ima = None
    for ln in open(HANTEI_FILE, encoding="utf-8").read().split("\n"):
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        if ln.startswith("[") and ln.endswith("]"):
            ima = ln[1:-1]
            continue
        if ima in out:
            out[ima].add(ln)
    return out


def namae_core(namae):
    """かっこの中を落とす。「古庄(株式会社エコハウス紹介)」のかっこは紹介元の注記で、
    お客様は古庄さま個人だから（CMO 2026-09-15）。"""
    return re.split(r"[（(]", namae)[0].strip()


def houjin_hantei(namae, teikei, kettei):
    """(扱い, 理由)。扱いは 送る／別対応／要判断。"""
    if namae in kettei["別対応"]:
        return "別対応", "CMO判断（お客様が会社そのもの）"
    if namae in kettei["送る"]:
        return "送る", "CMO判断（お客様は個人）"
    core = namae_core(namae)
    for w in HOUJIN_KAKU:
        if w in core:
            return "別対応", f"顧客名に「{w}」"
    if core and core in teikei:
        return "別対応", "提携先タブの会社名と一致"
    return "送る", ""


def hinagata():
    gyou = [ln for ln in open(HINAGATA, encoding="utf-8").read().split("\n")
            if not ln.lstrip().startswith("#")]
    while gyou and not gyou[0].strip():
        gyou.pop(0)
    while gyou and not gyou[-1].strip():
        gyou.pop()
    return gyou


SASHIKOMI = re.compile(r'"([^"]+)"')


def honbun(kata, atai):
    """差し込む。**値が空だった行は、その行ごと落とす。**
    「に を担当しました」のような文が出来上がるのを防ぐため（build-sms-list.py と同じ）。"""
    dekita, shiranai = [], set()
    for ln in kata:
        kara = False

        def hiku(m):
            nonlocal kara
            k = m.group(1)
            if k not in atai:
                shiranai.add(k)
                return m.group(0)
            v = atai[k]
            if not v:
                kara = True
            return v

        atarashii = SASHIKOMI.sub(hiku, ln)
        if kara:
            continue
        dekita.append(atarashii)
    return "\n".join(dekita), shiranai


def tsuu(s):
    return max(1, math.ceil(len(s) / UNIT))


def matagi(body):
    """MATAGANAI の文字列が、70文字の境界をまたいでいないか。

    またいでいる (文字列, 開始位置, またいだ境界) の一覧を返す。空なら合格。
    **1通目に収まらず2通目へ続く、という形も「またぎ」として数える。**
    """
    warui = []
    for kw in MATAGANAI:
        i = body.find(kw)
        while i >= 0:
            # 0始まりで [i, i+len) が、どの境界（UNIT の倍数）をまたぐか
            for kyoukai in range(UNIT, len(body) + UNIT, UNIT):
                if i < kyoukai < i + len(kw):
                    warui.append((kw, i + 1, kyoukai))
            i = body.find(kw, i + 1)
    return warui


def kugiri(s):
    """70文字ごとに切る。KDDI が実際に分割する位置。"""
    return [s[i:i + UNIT] for i in range(0, len(s), UNIT)] or [""]


def main():
    tok = sc.access_token(sc.load_credentials())
    rng = urllib.parse.quote(f"{TAB}!A{HEAD_ROW}:AH1200", safe="")
    v = sc.call(tok, f"/{SS}/values/{rng}").get("values", [])
    if not v:
        sys.exit(f"{TAB} を読めません")
    h = v[0]
    ix = {c: i for i, c in enumerate(h)}
    for need in ("顧客名", "送信済み", "送信する本文", "送信系統", "配信区分",
                 "最終施工日", "施工メニュー（内訳）"):
        if need not in ix:
            sys.exit(f"{TAB} に「{need}」列がありません")

    def g(r, k):
        i = ix.get(k)
        return (r[i] if i is not None and i < len(r) else "").strip()

    kata = hinagata()
    if not kata:
        sys.exit(f"{HINAGATA} に本文がありません")
    kata_moji = len("\n".join(kata))
    print(f"ひな形 {len(kata)}行／差し込み前 {kata_moji}文字")

    # 名乗りの照合（本文と宛先の両方）
    mc = importlib.util.spec_from_file_location("mc", os.path.join(ROOT, "tools", "meigi_check.py"))
    meigi = importlib.util.module_from_spec(mc)
    mc.loader.exec_module(meigi)
    hyou, riyuu = meigi.hyou_yomu()
    if hyou is None:
        sys.exit(f"台帳を読めないので名義を照合できません → {riyuu}\n"
                 "照合できないまま本文を作らないこと（2026-09-11 の事故の再発防止）。")

    # 法人の見分けに使うもの
    kettei = hantei_yomu()
    tv = sc.call(tok, f"/{SS}/values/{urllib.parse.quote(TEIKEI_TAB + '!B2:B101', safe='')}").get("values", [])
    teikei = {row[0].strip() for row in tv if row and row[0].strip()}
    print(f"法人の見分け：提携先{len(teikei)}社／CMO判断 送る{len(kettei['送る'])}名・別対応{len(kettei['別対応'])}名")

    taishou = []
    houjin = {}
    nozoita = {"送信済みなど": 0, "配信区分が送信可でない": 0}
    kubun = {}
    for n, r in enumerate(v[1:], start=HEAD_ROW + 1):
        if g(r, "送信系統") != "本舗":
            continue
        if g(r, "送信済み"):          # 送信済み・返信あり・不通エラー・対象外
            nozoita["送信済みなど"] += 1
            continue
        k = g(r, "配信区分") or "(空)"
        kubun[k] = kubun.get(k, 0) + 1
        # ★「送信可」以外は作らない。除外・SMS不可・保留の方の本文を作ると、
        #   和真さんの画面に「送れる人」として並んでしまう。
        if k != "送信可":
            nozoita["配信区分が送信可でない"] += 1
            continue
        namae = g(r, "顧客名")
        atsukai, riyuu_h = houjin_hantei(namae, teikei, kettei)
        if atsukai != "送る":
            houjin.setdefault(atsukai, []).append((n, namae, riyuu_h))
            continue
        atai = {
            "顧客名": sei(g(r, "顧客名")),
            "施工時期": itsu(g(r, "最終施工日")),
            "前回メニュー": menu_hitotsu(g(r, "施工メニュー（内訳）")),
        }
        body, shiranai = honbun(kata, atai)
        if shiranai:
            sys.exit(f"行{n}: ひな形に知らない差し込み {sorted(shiranai)} があります")
        taishou.append((n, g(r, "顧客名"), g(r, "電話番号"), body, atai))

    # ③ ①②とCMO判断で拾えず、「法人/個人」列が「法人」の行 → 本文を作らず一覧で出す
    youhandan = []
    for n, r in enumerate(v[1:], start=HEAD_ROW + 1):
        if (g(r, "送信系統") == "本舗" and not g(r, "送信済み")
                and g(r, "配信区分") == "送信可" and g(r, "法人/個人") == "法人"):
            nm = g(r, "顧客名")
            if nm not in kettei["送る"] and nm not in kettei["別対応"]:
                a, _ = houjin_hantei(nm, teikei, kettei)
                if a == "送る":
                    youhandan.append((n, nm))

    print(f"\n本舗・未送信の配信区分:", "／".join(f"{k}={v}" for k, v in sorted(kubun.items())))
    print(f"対象（本舗・未送信・送信可）: {len(taishou)}名")
    for k, vv in nozoita.items():
        print(f"  触らない: {k} {vv}件")
    for k, L in houjin.items():
        print(f"  法人の見分けで外した（{k}）: {len(L)}件")
        for n, nm, why in L:
            print(f"    行{n} {nm}  ← {why}")
    if youhandan:
        print(f"\n★★ 判断が要る行（法人/個人列は「法人」だが機械では決められない）: {len(youhandan)}件")
        print("   **この行の本文は作っています。** 外すなら data/sms-houjin-hantei.txt の [別対応] に足してください。")
        for n, nm in youhandan:
            print(f"    行{n} {nm}")
    else:
        print("\n判断が要る行（法人/個人列=法人だが機械で決められない）: 0件")
    if not taishou:
        return 0

    # ---- 検算1：名乗り ----
    ihan, tsukaeru = [], []
    for rec in taishou:
        n, name, tel, body, _ = rec
        warui = []
        ok, why = meigi.atesaki_ok(hyou, tel, name, "本舗")
        if not ok:
            warui.append(("宛先", why))
        for w in meigi.honbun_ihan("本舗", body):
            warui.append(("本文", w))
        if warui:
            ihan.append((n, warui))
        else:
            tsukaeru.append(rec)
    print(f"\n名乗り照合の違反: {len(ihan)}件 → **その行は本文を作りません**")
    for n, warui in ihan[:10]:
        for doko, why in warui:
            print(f"  行{n} [{doko}] {why}")
    if len(ihan) > 10:
        print(f"  …ほか {len(ihan)-10}件")
    taishou = tsukaeru
    if not taishou:
        print("作れる行がありません。")
        return 1

    # ---- 検算2：文字数と通数 ----
    naga = [(len(b), n, name) for n, name, _, b, _ in taishou]
    naga.sort(reverse=True)
    kazu = {}
    for ln, _, _ in naga:
        kazu[tsuu(" " * ln)] = kazu.get(tsuu(" " * ln), 0) + 1
    print(f"\n文字数：最短 {naga[-1][0]} / 中央 {naga[len(naga)//2][0]} / 最長 {naga[0][0]}")
    print("通数の内訳:", "／".join(f"{k}通={v}名" for k, v in sorted(kazu.items())))
    koeta = [x for x in naga if tsuu(" " * x[0]) > MAX_UNITS]
    if koeta:
        print(f"\n★★ {MAX_UNITS}通を超えた行: {len(koeta)}件")
        for ln, n, name in koeta[:10]:
            print(f"   行{n} {ln}文字 {sei(name)}さま")
    else:
        print(f"★ {MAX_UNITS}通を超えた行はありません（全{len(taishou)}名）")
    total = sum(tsuu(b) for _n, _na, _t, b, _a in taishou)
    print(f"費用の見込み: {total}通 × {PRICE:.0f}円 = {total*PRICE:,.0f}円"
          f"（1人あたり {total/len(taishou):.2f}通）")

    # ---- 検算3：電話番号が通の境界をまたいでいないか ----
    mataide = [(n, name, matagi(b)) for n, name, _t, b, _a in taishou if matagi(b)]
    nashi = [kw for kw in MATAGANAI
             if any(kw not in b for _n, _na, _t, b, _a in taishou)]
    if nashi:
        print(f"\n★★ 本文に見つからない必須の文字列: {nashi}")
    if mataide:
        print(f"\n★★ 電話番号が通の境界をまたぐ行: {len(mataide)}件")
        for n, name, w in mataide[:5]:
            for kw, pos, kyoukai in w:
                print(f"   行{n} {sei(name)}さま 「{kw}」が{pos}文字目から。"
                      f"{kyoukai}文字目（{kyoukai//UNIT}通目の終わり）でちぎれます")
        if len(mataide) > 5:
            print(f"   …ほか {len(mataide)-5}件")
    else:
        print(f"★ 電話番号が通の境界をまたぐ行はありません（全{len(taishou)}名）")

    # ---- 3通の区切りを見せる ----
    if SHOW3:
        ln, n, name = naga[0]
        body = next(b for m, _, _, b, _ in taishou if m == n)
        print(f"\n===== 70文字ごとの区切り（いちばん長い方・行{n}／{ln}文字）=====")
        for i, part in enumerate(kugiri(body), 1):
            print(f"\n--- {i}通目（{len(part)}文字）---")
            print(part)
        print("\n※ KDDI はこの位置で自動分割し、分割後の通数で課金します。")

    if not WRITE:
        print("\n書き込みません（検算のみ）。F列を作り直すには: --confirm WRITE")
        return 0
    if koeta:
        sys.exit(f"\n{MAX_UNITS}通を超えた行があるので書き込みません。")
    if mataide or nashi:
        sys.exit("\n電話番号が通の境界をまたぐ（または本文に無い）ので書き込みません。")

    # 書き換える前に控えを取る。
    # ★Drive のコピーはサービスアカウントに保存容量が無く 403 になる（2026-09-14 確認）。
    #   同じスプレッドシート内にタブを複製して代える。
    import datetime
    meta = sc.call(tok, f"/{SS}?fields=sheets.properties")
    gid = [s["properties"]["sheetId"] for s in meta["sheets"]
           if s["properties"]["title"] == TAB][0]
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    sc.call(tok, f"/{SS}:batchUpdate", "POST",
            {"requests": [{"duplicateSheet": {
                "sourceSheetId": gid,
                "newSheetName": f"控え_冬季見込み客_{stamp}"}}]})
    print(f"控えタブを作りました: 控え_冬季見込み客_{stamp}")

    data = [{"range": f"{TAB}!F{n}", "values": [[b]]} for n, _, _, b, _ in taishou]
    sc.call(tok, f"/{SS}/values:batchUpdate", "POST",
            {"valueInputOption": "RAW", "data": data})
    print(f"\nF列を {len(data)} 行 書き換えました（本舗・未送信のみ）。")

    # ★D列の「▶ 送る」にも本文が埋まっている。ここを直さないと、
    #   和真さんがタップしたときに**古い451文字の本文が送られる**。
    #   F列（読むための控え）だけ直しても意味がない。
    #   リンクの作り方は cmo の build-sms-list.py と同じ（フラグメントに入れる。
    #   サーバーに送られないので、Netlifyの記録に電話番号も本文も残らない）。
    meta2 = sc.call(tok, f"/{SS}?fields=sheets.properties")
    sid = [s["properties"]["sheetId"] for s in meta2["sheets"]
           if s["properties"]["title"] == TAB][0]
    reqs = []
    for n, _name, tel, body, _ in taishou:
        num = re.sub(r"\D", "", tel)
        if not num:
            continue
        uri = (SMS_PAGE + "#to=" + urllib.parse.quote(num, safe="")
               + "&b=" + urllib.parse.quote(body, safe=""))
        reqs.append({"updateCells": {
            "range": {"sheetId": sid, "startRowIndex": n - 1, "endRowIndex": n,
                      "startColumnIndex": 3, "endColumnIndex": 4},
            "rows": [{"values": [{
                "userEnteredValue": {"stringValue": "▶ 送る"},
                "textFormatRuns": [{"startIndex": 0, "format": {"link": {"uri": uri}}}]}]}],
            "fields": "userEnteredValue,textFormatRuns"}})
    for i in range(0, len(reqs), 100):   # 1回に詰め込みすぎると通らない
        sc.call(tok, f"/{SS}:batchUpdate", "POST", {"requests": reqs[i:i + 100]})
    print(f"D列（▶ 送る）のリンクを {len(reqs)} 行 貼り直しました。")

    # ---- 法人の見分けで外した行を、シートの側でも止める ----
    # 本文とリンクを消し、配信区分を「除外」にする。
    # ★消さないと、和真さんがタップしたときに住居向けの本文が法人の窓口へ飛ぶ。
    betsu = houjin.get("別対応", [])
    if betsu:
        c_ku, c_ri = a1(ix["配信区分"] + 1), a1(ix["送らない理由"] + 1)
        d2, r2 = [], []
        for n, nm, why in betsu:
            d2.append({"range": f"{TAB}!F{n}", "values": [[""]]})
            d2.append({"range": f"{TAB}!{c_ku}{n}", "values": [["除外"]]})
            d2.append({"range": f"{TAB}!{c_ri}{n}",
                       "values": [[f"法人_別対応へ（web-inflow の法人向け文面）"
                                   f"{KYOU} CMO判断：{why}"]]})
            r2.append({"updateCells": {
                "range": {"sheetId": sid, "startRowIndex": n - 1, "endRowIndex": n,
                          "startColumnIndex": 3, "endColumnIndex": 4},
                "rows": [{"values": [{"userEnteredValue": {"stringValue": ""}}]}],
                "fields": "userEnteredValue,textFormatRuns"}})
        sc.call(tok, f"/{SS}/values:batchUpdate", "POST",
                {"valueInputOption": "RAW", "data": d2})
        sc.call(tok, f"/{SS}:batchUpdate", "POST", {"requests": r2})
        print(f"法人_別対応の {len(betsu)}行：本文とリンクを消し、配信区分を「除外」にしました。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
