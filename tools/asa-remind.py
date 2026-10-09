#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""毎朝、前日までの入力漏れを業務連絡グループLINEへ1通で知らせる。

  オーナー指示（2026-09-26・和真対応可否一覧 No.31 の F列）
    「入力漏れがあれば翌日にマーケ部長がLINEでリマインドしてほしい」（現金で受け取った売上の当日記録）
  オーナー指示（2026-09-26・MTGシート F364 の件）
    「未入力をリマインドできるようにしたい」（作業完了フォーム）

  対象（どちらも 2026-09-26 以降〜昨日の施工）
    1. 台帳（◯月_売上/顧客）で O列「入金経路」が空欄の行
    2. 作業完了フォームがまだ届いていない施工（tools/kanryo_mishin.py）
    3. 今日の施工のうち、2回目以降のお客様（リピーター）の前回の情報（T064）
       オーナー（2026-10-03 第5回MTG）「リピーターなど2回目以降のお客様に施工に入る日は当日の朝に
       前回施工した写真が保存されているドライブURLをグループLINEへ送るようにしてほしい」
       台帳（顧客管理台帳）と電話番号→名前の順で突き合わせ、回数・前回の日付・これまでのメニュー・クレーム履歴を出す。
       写真フォルダの URL は tools/shashin-drive.py が入れたもの（data/shashin-drive.json）があれば付ける。
       社内（嶺・和真）あての連絡なので、お客様の名乗りの照合は対象外。
    4. 確定の電話（T068）：13〜15日後に施工予定で、まだ【仮】の予約
       和真さん（2026-10-09 第6回MTG 6-3 No.1）「2週間前に電話をかけます。朝のラインでリマインドして」
       ・【仮】かどうかの正は**和真さんのカレンダーの題名の【仮】**（確定の電話がとれたら【仮】を外す運用。
         tools/booking-api.gs）。月タブの W列「早期予約の確定」は 2026-10-09 時点で全行空欄のため、
         「確定」と書かれた行を外す・「未確定」と書かれた行を足す、の補助に使う。
       ・サービスアカウントはカレンダーを読めない（Calendar API が無効）。巡回が Google Calendar コネクタで
         list_events（calendarId=wk09015963@gmail.com、今日+13日 0:00〜今日+16日 0:00）を呼び、
         返ってきた JSON をそのまま ~/.cache/one-hitter/kari-yotei.json に保存してから、このツールを回す。
         **今日保存した控えだけ使う**（古い控えは日付がずれるので読まない）。控えが無い日は W列「未確定」の行だけ出す。
       ・カレンダーの予定と月タブの行は、同じ日付＋名前（姓）で1件に突き合わせ、二重に出さない。
         名前・日時・メニューだけ。電話番号・住所は書かない（和真さんは台帳で番号を見る）。
       ・13〜15日後の幅は、巡回が1日抜けても取りこぼさないため（同じお客様が最大3日出る）。
  どれも0件なら何も送らない。

    python3 tools/asa-remind.py --dry-run
    python3 tools/asa-remind.py
    python3 tools/asa-remind.py --dry-run --kari-json 別の控え.json   # 控えの場所を変えるとき
"""
import argparse
import datetime
import json
import pathlib
import re
import subprocess
import sys
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import sheets_client as sc  # noqa: E402
import kanryo_mishin as km  # noqa: E402

JST = datetime.timezone(datetime.timedelta(hours=9))
KARI_JSON = pathlib.Path.home() / ".cache" / "one-hitter" / "kari-yotei.json"
KAKUNIN_MAE = (13, 14, 15)   # 何日前に「確定の電話」を出すか（和真さん「2週間前」＋前後1日）
YOUBI = "月火水木金土日"


def nyukin_mikinyu(kinou):
    tok = sc.access_token(sc.load_credentials())
    tsuki = sorted({km.KITEN.month, kinou.month}) if kinou >= km.KITEN else []
    if not tsuki:
        return []
    qs = "&".join("ranges=" + urllib.parse.quote(f"'{m}月_売上/顧客'!A4:U504", safe="") for m in range(tsuki[0], tsuki[-1] + 1))
    vr = sc.call(tok, f"/{km.SS}/values:batchGet?{qs}")["valueRanges"]
    out = []
    for m, v in zip(range(tsuki[0], tsuki[-1] + 1), vr):
        for i, r in enumerate(v.get("values", []), 4):
            r = r + [""] * 21
            if not r[1].strip() or not r[4].strip():
                continue
            try:
                d = datetime.date(*map(int, r[2].strip().split("/")))
            except Exception:
                continue
            if km.KITEN <= d <= kinou and not r[14].strip():
                out.append({"d": d, "n": r[4].strip(), "k": r[8].strip(), "r": f"{m}月_売上/顧客 {i}行目"})
    return sorted(out, key=lambda x: x["d"])


def shashin_url(o, kokyaku_id):
    """写真フォルダの URL。顧客ID が記録されていれば、台帳で当たったお客様と同じときだけ出す（同名の別人に出さない）。"""
    if not o or not o.get("url"):
        return ""
    if o.get("id") and o["id"] != kokyaku_id:
        return ""
    return o["url"]


def kyou_ripi(kyou):
    """今日の施工で、台帳上2回目以降のお客様。"""
    import json
    import re
    tok = sc.access_token(sc.load_credentials())
    # 台帳の「受注回数」「最終施工日」には先の予約も入っている（例：12月の定期便）。
    # 今年の月タブを全部読み、今日より前の施工だけで「前回」を決め、先の予約の分を回数から引く。
    rs = [f"'{m}月_売上/顧客'!A4:T504" for m in range(1, 13)] + ["'顧客管理台帳'!A16:AG3000"]
    qs = "&".join("ranges=" + urllib.parse.quote(r, safe="") for r in rs)
    vr = [v.get("values", []) for v in sc.call(tok, f"/{km.SS}/values:batchGet?{qs}")["valueRanges"]]
    tsuki, daicho = vr[kyou.month - 1], vr[12]
    zenbu = [(r + [""] * 20) for v in vr[:12] for r in v]
    kyou_s = f"{kyou.year}/{kyou.month:02d}/{kyou.day:02d}"
    num = lambda x: re.sub(r"\D", "", x or "")
    mei = lambda x: re.sub(r"[\s　様]", "", x or "")
    shashin = {}
    f = ROOT / "data" / "shashin-drive.json"
    if f.exists():
        shashin = json.loads(f.read_text(encoding="utf-8")).get("okyaku", {})
    out = []
    for r in tsuki:
        r = r + [""] * 20
        if r[2].strip() != kyou_s or not r[4].strip():
            continue
        tel, na = num(r[5]), mei(r[4])
        hit = None
        for d in daicho:
            d = d + [""] * 33
            if tel and len(tel) >= 10 and num(d[3]) == tel:
                hit = d
                break
        # 電話番号があるのに台帳の電話と合わない＝別人（新規）。名前では当てない。
        # 名字だけ（2字以下）も当てない。2026-10-09 新規の鈴木様を、別の鈴木様（3回目）と取り違えた。
        nadake = not (tel and len(tel) >= 10) and len(na) >= 3
        if hit is None and nadake:
            for d in daicho:
                d = d + [""] * 33
                if na and (mei(d[1]) == na or na in [mei(x) for x in d[31].split("／")]):
                    hit = d
                    break
        if hit is None:
            continue
        onaji = [z[2].strip() for z in zenbu
                 if (tel and len(tel) >= 10 and num(z[5]) == tel) or (nadake and mei(z[4]) == na)]
        mae = sorted(x for x in onaji if re.fullmatch(r"\d{4}/\d{2}/\d{2}", x) and x < kyou_s)
        saki = sum(1 for x in onaji if re.fullmatch(r"\d{4}/\d{2}/\d{2}", x) and x > kyou_s)
        kai = int(num(hit[6]) or 0)
        saigo = hit[11].strip()
        konkai = (kai - saki) if saigo >= kyou_s else kai + 1   # 今日の分が台帳に入っていなければ足す
        zenkai = mae[-1] if mae else (saigo if saigo < kyou_s else "")
        if konkai < 2 or not (zenkai or hit[10].strip() < kyou_s):
            continue
        out.append({"n": r[4].strip(), "menu": r[9].strip() or r[3].strip(), "kai": konkai,
                    "shokai": hit[10].strip(), "saigo": zenkai,
                    "uchiwake": hit[30].strip(), "claim": hit[32].strip(),
                    "url": shashin_url(shashin.get(na), hit[0].strip())})
    return out


def _mei(x):
    return re.sub(r"[\s　]|さま$|様$", "", x or "")


def _sei(x):
    """姓。スペースで区切れていればその前、無ければ全体（「濵田」「法龍寺」など）。"""
    t = re.split(r"[\s　]+", (x or "").strip())
    return re.sub(r"(さま|様)$", "", t[0]) if t and t[0] else ""


def kari_hikae(kyou, path):
    """カレンダーの【仮】予定の控え。今日保存されたものだけ。控えが無い・古いときは None。"""
    if not path.exists():
        return None
    if datetime.datetime.fromtimestamp(path.stat().st_mtime, JST).date() != kyou:
        print(f"（【仮】の控え {path} は今日のものではないので使いません）")
        return None
    o = json.loads(path.read_text(encoding="utf-8"))
    ev = o.get("events", []) if isinstance(o, dict) else o
    out = []
    for e in ev:
        dai = (e.get("summary") or "").strip()
        if not dai.startswith("【仮】") or e.get("status") == "cancelled":
            continue
        st = e.get("start") or {}
        dt = st.get("dateTime") or st.get("date") or ""
        try:
            d = datetime.date.fromisoformat(dt[:10])
        except ValueError:
            continue
        out.append({"d": d, "j": dt[11:16] if "T" in dt else "", "dai": dai,
                    "setsu": e.get("description") or ""})
    return out


def kari_namae(k):
    """カレンダーの予定から姓を取る（月タブと突き合わせられなかったとき用）。
    予約フォームの形「【仮】鈴木様 …」か、説明の1行目「仮予約 ワンヒッター 藤田　純子さま」。"""
    m = re.match(r"【仮】\s*([^\s/／]+?)様", k["dai"])
    if m:
        return m.group(1)
    g = (k["setsu"].splitlines() or [""])[0]
    g = re.sub(r"仮予約|ワンヒッター(株式会社)?|おそうじ本舗|Web予約（未確認）", " ", g)
    m = re.search(r"(\S+)[\s　]*\S*?(さま|様)", g)
    return _sei(m.group(1)) if m else ""


def kari_menu(dai):
    t = re.sub(r"^【仮】\s*", "", dai)
    t = re.sub(r"^[^/／]*?[区市町村]\s*[/／]\s*", "", t)   # 「江戸川区 / 」は出さない
    t = re.sub(r"^\S+?様\s*", "", t)                      # 「鈴木様 」（予約フォームの形）
    return t.strip()


def kakutei_denwa(kyou, hikae_path):
    """13〜15日後の【仮】の予約（T068）。[{d, j, n, menu}]"""
    hi = [kyou + datetime.timedelta(days=n) for n in KAKUNIN_MAE]
    kari = kari_hikae(kyou, hikae_path)
    kari = [k for k in (kari or []) if k["d"] in hi] if kari is not None else None
    # 月タブ（今年のタブしか無いので、年をまたぐ日は月タブを読まない）
    tsuki = sorted({d.month for d in hi if d.year == kyou.year})
    gyo = []
    if tsuki:
        tok = sc.access_token(sc.load_credentials())
        qs = "&".join("ranges=" + urllib.parse.quote(f"'{m}月_売上/顧客'!A2:Z504", safe="") for m in tsuki)
        for v in sc.call(tok, f"/{km.SS}/values:batchGet?{qs}")["valueRanges"]:
            rows = v.get("values", [])
            if not rows:
                continue
            hdr = rows[0]
            c_kaku = hdr.index("早期予約の確定") if "早期予約の確定" in hdr else None
            for r in rows[2:]:
                r = r + [""] * 26
                try:
                    d = datetime.date(*map(int, r[2].strip().split("/")))
                except Exception:
                    continue
                if d not in hi or not r[4].strip():
                    continue
                gyo.append({"d": d, "n": r[4].strip(), "menu": r[9].strip() or r[3].strip(),
                            "kaku": r[c_kaku].strip() if c_kaku is not None else ""})
    out, tsukatta = [], set()
    for g in gyo:
        if g["kaku"] == "確定":
            continue
        zen, sei = _mei(g["n"]), _sei(g["n"])
        hit = None
        for i, k in enumerate(kari or []):
            if i in tsukatta or k["d"] != g["d"]:
                continue
            txt = re.sub(r"[\s　]", "", k["dai"] + k["setsu"])
            if (zen and zen in txt) or (len(sei) >= 2 and sei in txt):
                hit = i
                break
        if hit is None and g["kaku"] == "未確定" and kari:
            # 名前の書き方が違う（ひらがな／漢字など）とき：その日の残りの【仮】が1件だけならそれと見なす
            nokori = [i for i, k in enumerate(kari) if i not in tsukatta and k["d"] == g["d"]]
            if len(nokori) == 1:
                hit = nokori[0]
        if hit is None and g["kaku"] != "未確定":
            continue          # カレンダーで【仮】が外れている（＝確定）か、控えが無くて分からない
        if hit is not None:
            tsukatta.add(hit)
        k = kari[hit] if hit is not None else None
        out.append({"d": g["d"], "j": k["j"] if k else "", "n": sei or g["n"],
                    "menu": (kari_menu(k["dai"]) if k else "") or g["menu"]})   # カレンダーの方が新しく細かい
    for i, k in enumerate(kari or []):
        if i not in tsukatta:   # 月タブにまだ無い【仮】（予約フォームの申込など）や、日付が台帳とずれているもの
            out.append({"d": k["d"], "j": k["j"], "n": kari_namae(k) or "（名前はカレンダーで）",
                        "menu": kari_menu(k["dai"])})
    if kari is None:
        print(f"（【仮】の控え {hikae_path} が無いため、確定の電話は W列「未確定」の行だけで判定）")
    return sorted(out, key=lambda x: (x["d"], x["j"]))


def jikoku(j):
    if not j:
        return ""
    h, m = int(j[:2]), j[3:5]
    return f" {h}時" if m == "00" else f" {h}:{m}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--kari-json", default=str(KARI_JSON), help="カレンダーの【仮】予定の控え（今日保存したもの）")
    a = ap.parse_args()
    kyou = datetime.datetime.now(JST).date()
    kinou = kyou - datetime.timedelta(days=1)

    nk = nyukin_mikinyu(kinou)
    kf = [x for x in km.ichiran(kinou)]          # 昨日までの施工で完了フォーム未入力
    rp = kyou_ripi(kyou)
    kd = kakutei_denwa(kyou, pathlib.Path(a.kari_json).expanduser())
    print(f"入金経路が空欄: {len(nk)}件／作業完了フォーム未入力: {len(kf)}件（{km.KITEN}〜{kinou}）／今日のリピーター: {len(rp)}件"
          f"／確定の電話（{KAKUNIN_MAE[0]}〜{KAKUNIN_MAE[-1]}日後の【仮】）: {len(kd)}件")
    if not nk and not kf and not rp and not kd:
        print("お知らせなし")
        return
    gyo = []
    if kd:
        gyo += ["【確定の電話】2週間後の【仮】の予約です（お電話番号は台帳で）"]
        gyo += [f"・確定の電話：{x['n']}様（{x['d'].month}/{x['d'].day}（{YOUBI[x['d'].weekday()]}）{jikoku(x['j'])}"
                f"{'・' + x['menu'][:40] if x['menu'] else ''}）あと{(x['d'] - kyou).days}日" for x in kd]
        gyo += ["→ 確定したら、カレンダーの【仮】を外し、売上シートの「早期予約の確定」を「確定」に"]
    if rp:
        gyo += ([""] if gyo else []) + ["【今日のリピーターさま】前回の内容です"]
        for x in rp:
            gyo += ["", f"■ {x['n']} さま（{x['kai']}回目・今日：{x['menu']}）"]
            gyo += [f"前回 {x['saigo']}" if x["saigo"] else f"初回 {x['shokai']}"]
            if x["uchiwake"]:
                gyo += [f"これまで：{x['uchiwake'][:80]}"]
            if x["claim"]:
                gyo += [f"🔴 過去のクレーム：{x['claim'][:120]}"]
            if x["url"]:
                gyo += [f"前回までの写真：{x['url']}"]
    if nk or kf:
        gyo += ([""] if gyo else []) + ["【入力のお願い】昨日までの施工で、まだ入っていないものがあります"]
    if nk:
        gyo += ["", "■ 入金（現金・クレカ・請求書など）が売上シートに未記入"]
        gyo += [f"・{x['d'].month}/{x['d'].day} {x['n']} さま {x['k']}" for x in nk]
        gyo += ["→ 売上シートの「入金経路」を選んでください（現金ならその日のうちに）"]
    if kf:
        gyo += ["", "■ 作業完了フォームが未入力"]
        gyo += [f"・{x['d'][5:].replace('-', '/')} {x['n']} さま" for x in kf]
        import importlib.util
        spec = importlib.util.spec_from_file_location("ko", ROOT / "tools" / "kanryo-okuru.py")
        ko = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ko)
        gyo += ["→ こちらから、お客様を選んで入れてください", ko.kaku({"p": km.ichiran(), "st": 1})]
    txt = "\n".join(gyo)
    print(txt)
    if a.dry_run:
        print("\n--dry-run のため送っていません。")
        return
    f = ROOT / "data" / "tmp-asa-remind.txt"
    f.write_text(txt, encoding="utf-8")
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "line_client.py"), "push", "--file", str(f), "--midoku-ok"],
                       capture_output=True, text=True)
    f.unlink(missing_ok=True)
    print("送りました" if r.returncode == 0 else f"🔴 送れませんでした: {r.stderr.strip()[:200]}")


if __name__ == "__main__":
    main()
