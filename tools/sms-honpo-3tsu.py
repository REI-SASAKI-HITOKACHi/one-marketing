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

UNIT = 70                          # KDDI：1通＝70文字
MAX_UNITS = 3                      # 3通案
PRICE = 11.0                       # 税込11円/通（税抜10.0の階梯）

# D列「▶ 送る」のリンク先。社内用の中継ページ（cmo の build-sms-list.py と同じ）。
# ★宛先と本文は「#」より後ろ（フラグメント）に入れる。サーバーに送られないので、
#   Netlify の記録にお客様の電話番号も本文も残らない。「?」に変えないこと。
SMS_PAGE = "https://oh-naibu-sms-k7q3x.netlify.app/s.html"

WRITE = ("--confirm" in sys.argv and "WRITE" in sys.argv)
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

    taishou = []
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
        atai = {
            "顧客名": sei(g(r, "顧客名")),
            "施工時期": itsu(g(r, "最終施工日")),
            "前回メニュー": menu_hitotsu(g(r, "施工メニュー（内訳）")),
        }
        body, shiranai = honbun(kata, atai)
        if shiranai:
            sys.exit(f"行{n}: ひな形に知らない差し込み {sorted(shiranai)} があります")
        taishou.append((n, g(r, "顧客名"), g(r, "電話番号"), body, atai))

    print(f"\n本舗・未送信の配信区分:", "／".join(f"{k}={v}" for k, v in sorted(kubun.items())))
    print(f"対象（本舗・未送信・送信可）: {len(taishou)}名")
    for k, v in nozoita.items():
        print(f"  触らない: {k} {v}件")
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

    # 書き換える前に控えを取る。
    # ★Drive のコピーはサービスアカウントに保存容量が無く 403 になる（2026-09-14 確認）。
    #   同じスプレッドシート内にタブを複製して代える。
    import datetime
    meta = sc.call(tok, f"/{SS}?fields=sheets.properties")
    gid = [s["properties"]["sheetId"] for s in meta["sheets"]
           if s["properties"]["title"] == TAB][0]
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
