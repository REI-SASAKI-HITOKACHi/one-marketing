#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""提携先さまの専用ページ（lp.onehitter.jp/partner/<鍵>/・Netlify Forms「partner」）から依頼が届いたら、
業務連絡LINE（嶺・和真の2名）に知らせる。

【なぜ】
  2026-10-10 タカラサービス様の専用ページ（/partner/takara-7q2m/）を本番に出した（オーナー「僕が操作できる状態で出して」）。
  送られた依頼は Netlify の「partner」フォームに入るが、取り込む道具が無く、誰も気づかない状態だった。
  提携先の依頼は「日時が決まりしだい貴社へ確定のご連絡」と約束しているので、毎時の点検で拾って和真さんへ回す。

【知らせる中身】
  提携先・種別（見積依頼／現調依頼）・内容・内訳・目安金額・希望日時・現場の住所（区市まで）・現場のお名前・ご担当・ご要望（先頭80字）。
  **お客様の電話は出さない**（Netlify の管理画面で見る）。テストの送信（お客様名・ご要望に「テスト」）は【テスト】と付けて知らせる。

【見積依頼は見積書まで作る】2026-10-10 オーナー「見積依頼が入ったら和真と僕へ通知＋見積書の自動作成＋メール下書きまでセットしたい」
  - 「【保存先】見積/請求/領収書」（12NMMsw…）の、提携先ごとの見本タブ（タカラ様＝『株式会社タカラサービス』）を複製して
    新しいタブに見積書を作る。見積番号は全タブの F2 の最大＋1。品名・数量・単価は送信の「明細」（ページの料金表どおり・税抜）。
    小計・消費税・合計は見本の式のまま。高速代は実費なので明細に入れず、備考に目安を書く（都内23区は0）。
  - 見積書のPDFを ~/.cache/one-hitter/mitsumori/ に置き（お客様名が入るのでリポジトリに置かない）、
    メール下書きの件名・本文を「_下書き待ち（自動・消さない）」タブに載せる。嶺さんのアカウントで動く
    tools/mitsumori-shitagaki.gs が5分ごとに PDF を付けて Gmail の下書きにする（送信は嶺さん）。
  - LINE の通知に見積書のリンクを添える。テスト送信は、タブ名の頭に「テスト_」を付ける（消してよい）。

【カレンダーの【仮】】日時が選ばれた依頼（現調依頼・日時を選んだ見積依頼）は、ほかの予約と重ならないよう
  和真さんのカレンダーに【仮】を入れる。サービスアカウントにはカレンダーの権限が無いので、材料を
  ~/.cache/one-hitter/partner-kari.json に置き、毎時点検の CMO が Google Calendar コネクタで入れる（予約ページと同じ形）。

【二重に知らせない】
  知らせた ID だけを data/partner-tsuchi.json に残す（中身は残さない）。

  python3 tools/partner-inbox.py --dry-run   # 何を知らせるか見るだけ（毎時点検が使う）
  python3 tools/partner-inbox.py             # 知らせる
"""
import argparse
import importlib.util
import json
import pathlib
import datetime
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE_ID = "dad26366-3dfb-4404-9e0c-bb6b50b893c9"   # one-hitter-lp（lp.onehitter.jp）
FORM = "partner"
KIROKU = ROOT / "data" / "partner-tsuchi.json"

MITSU_SS = "12NMMswkvumA1BjKxU1HrqMQjFgRUJNz4YMiC4m6QSu0"   # 【保存先】見積/請求/領収書
# 提携先ごとの見積書の見本タブと、メールの宛先（下書きの仮の宛先。送るのはオーナー）
MIHON = {"株式会社タカラサービス": {"tab": "株式会社タカラサービス", "ate": "info@takara-co.jp", "tantou": "深堀"}}
TEL = "080-8043-8259"
PDF_DIR = pathlib.Path(os.path.expanduser("~/.cache/one-hitter/mitsumori"))
JST = datetime.timezone(datetime.timedelta(hours=9))

sys.path.insert(0, str(ROOT / "tools"))
import sheets_client as sc  # noqa: E402

_spec = importlib.util.spec_from_file_location("ji", ROOT / "tools" / "juchu-inbox.py")
ji = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ji)


def honbun(d: dict) -> str:
    test = any("テスト" in str(d.get(k, "")) for k in ("お客様名", "ご要望", "現場のお名前"))
    g = [("【テスト】" if test else "") + f"■ 提携先からのご依頼：{d.get('提携先', '')}（{d.get('種別', '')}）"]
    for k in ("内容", "内訳", "目安金額", "高速代の目安", "希望日時", "作業時間の目安", "移動時間の目安",
              "現場の住所", "現場のお名前", "お客様名", "ご担当", "きっかけ"):
        v = str(d.get(k, "")).replace("\n", " ").strip()
        if v:
            g.append(f"{k}：{v[:120]}")
    yo = str(d.get("ご要望", "")).replace("\n", " ").strip()
    if yo:
        g.append("ご要望：" + yo[:80] + ("…" if len(yo) > 80 else ""))
    g.append("→ 日時が決まりしだい、提携先へ確定のご連絡（お客様の電話は Netlify の管理画面）")
    return "\n".join(g)


def ham(sid: str):
    """迷惑判定に入った送信を「迷惑ではない」に戻す（Netlify API PUT /submissions/{id}/ham）。"""
    t = os.environ.get("NETLIFY_TOKEN", "").strip() or pathlib.Path(os.path.expanduser("~/.config/one-hitter/netlify-token.txt")).read_text().strip()
    req = urllib.request.Request(f"https://api.netlify.com/api/v1/submissions/{sid}/ham", method="PUT",
                                 headers={"Authorization": "Bearer " + t})
    try:
        urllib.request.urlopen(req, timeout=60).read()
    except Exception as e:  # 戻せなくても、拾ったことは記録に残る
        print(f"  （迷惑判定を戻せませんでした {sid}: {e}）")


def is_test(d: dict) -> bool:
    return any("テスト" in str(d.get(k, "")) for k in ("お客様名", "ご要望", "現場のお名前"))


def mitsumorisho(d: dict, dry: bool) -> dict:
    """見積依頼から見積書のタブを作り、PDF とメール下書きの材料を返す。"""
    m = MIHON.get(d.get("提携先", ""))
    if not m:
        return {"err": f"見本タブが無い提携先：{d.get('提携先')}"}
    try:
        meisai = json.loads(d.get("明細") or "[]")
    except json.JSONDecodeError:
        meisai = []
    if not meisai:
        return {"err": "明細が無い（お見積りのみの内容）。見積書は手で作る"}
    tok = sc.access_token(sc.load_credentials())
    meta = sc.call(tok, f"/{MITSU_SS}", query={"fields": "sheets.properties(title,sheetId)"})
    tabs = {x["properties"]["title"]: x["properties"]["sheetId"] for x in meta["sheets"]}
    rs = "&".join("ranges=" + urllib.parse.quote(f"'{t}'!F2", safe="") for t in tabs)
    nums = [int(x) for v in sc.call(tok, f"/{MITSU_SS}/values:batchGet?{rs}")["valueRanges"]
            for r in v.get("values", []) for x in re.findall(r"見積番号[：:]\s*(\d{4})", str(r[0]) if r else "")]
    ban = f"{(max(nums) + 1 if nums else 1):04d}-01"
    ate_mei = (d.get("現場のお名前") or d.get("お客様名") or "").strip()
    title = ("テスト_" if is_test(d) else "") + f"タカラ_{ban}" + (f"_{ate_mei[:20]}" if ate_mei else "")
    toll = str(d.get("高速代の目安", ""))
    biko = ("［備考］\nご依頼いただきました御見積をご案内差し上げます。ご査収くださいませ。\n"
            + ("高速代は実費でご請求差し上げます（目安：" + toll + "）。\n" if toll and not toll.startswith("0円") else "")
            + "駐車場が無い場合にはコインパーキング代実費を上記に加えてご請求差し上げます。\n"
            + ("型番の分からないお掃除機能付きは最低額で計算しています（現地で型番を確かめて確定）。\n" if any(x.get("ijou") for x in meisai) else "")
            + "ご不明点やご要望等ございましたら何なりとお申し付けくださいませ。")
    kyou = datetime.datetime.now(JST)
    shoukei = sum(int(x["tanka"]) * int(x["suuryou"]) for x in meisai)
    goukei = shoukei + int(shoukei * 0.1)
    # 送り先：ページで先方が選んだもの（いつもの宛先＋追加／追加分だけ）。無ければいつもの宛先
    ate = (d.get("見積書の送り先") or "").strip() or m["ate"]
    kekka = {"ban": ban, "title": title, "shoukei": shoukei, "goukei": goukei, "ate": ate, "tantou": d.get("ご担当") or m["tantou"],
             "ate_mei": ate_mei, "meisai": meisai, "toll": toll, "kibou": d.get("希望日時", ""), "test": is_test(d)}
    if dry:
        return kekka
    src = tabs[m["tab"]]
    r = sc.call(tok, f"/{MITSU_SS}:batchUpdate", method="POST",
                payload={"requests": [{"duplicateSheet": {"sourceSheetId": src, "newSheetName": title, "insertSheetIndex": len(tabs)}}]})
    props = r["replies"][0]["duplicateSheet"]["properties"]
    gid = props["sheetId"]
    # 見本タブの35行目より下には過去の見積書の貼り付け画像が残っている。画像は Sheets API では消せないので、
    # mitsumori-shitagaki.gs（嶺さんのアカウント）が下を消し、印影（電子印影_角印.png）を重ねてから PDF にする
    # （2026-10-10 オーナー「見積書の印影も入れて」）
    q = lambda a: f"'{title}'!{a}"
    rows = [[x["hinmei"] + ("（〜）" if x.get("ijou") else ""), "", "", int(x["suuryou"]), int(x["tanka"])] for x in meisai[:12]]
    rows += [["", "", "", "", ""]] * (12 - len(rows))
    sc.call(tok, f"/{MITSU_SS}/values:batchClear", method="POST", payload={"ranges": [q("A17:E29")]})
    sc.call(tok, f"/{MITSU_SS}/values:batchUpdate", method="POST", payload={"valueInputOption": "USER_ENTERED", "data": [
        {"range": q("F1"), "values": [[kyou.strftime("%Y/%m/%d")]]},
        {"range": q("F2"), "values": [[f"見積番号：{ban}"]]},
        {"range": q("A9"), "values": [[(f"{ate_mei}　様　" if ate_mei else "") + "エアコン洗浄"]]},
        {"range": q("E11"), "values": [[f"TEL: {TEL}"]]},
        {"range": q("A17:E28"), "values": rows},
        {"range": q("A30"), "values": [[biko]]},
    ]})
    kekka["url"] = f"https://docs.google.com/spreadsheets/d/{MITSU_SS}/edit#gid={gid}"
    kekka["gid"] = gid
    machi_ni_noseru(kekka, gid)
    # PDF（A4縦・幅に合わせる）
    try:
        dtok = sc.access_token(sc.load_credentials(), "https://www.googleapis.com/auth/drive.readonly")
        u = (f"https://docs.google.com/spreadsheets/d/{MITSU_SS}/export?format=pdf&gid={gid}&size=A4&portrait=true"
             "&fitw=true&gridlines=false&printtitle=false&sheetnames=false&pagenum=UNDEFINED&r1=0&c1=0&r2=33&c2=6")
        req = urllib.request.Request(u, headers={"Authorization": "Bearer " + dtok})
        PDF_DIR.mkdir(parents=True, exist_ok=True)
        pdf = PDF_DIR / f"見積書_{ban}.pdf"
        pdf.write_bytes(urllib.request.urlopen(req, timeout=120).read())
        kekka["pdf"] = str(pdf)
    except Exception as e:  # PDF が取れなくても見積書のタブはできている
        kekka["pdf_err"] = str(e)
    return kekka


MACHI = "_下書き待ち（自動・消さない）"   # tools/mitsumori-shitagaki.gs（嶺さんのアカウント）が PDF を付けて Gmail の下書きにする


def machi_ni_noseru(k: dict, gid: int):
    """下書き待ちのタブに1行載せる（無ければ作る）。A 状態／B 日時／C gid／D 見積番号／E 宛先／F 件名／G 本文／H PDF名／I 作成日時"""
    tok = sc.access_token(sc.load_credentials())
    meta = sc.call(tok, f"/{MITSU_SS}", query={"fields": "sheets.properties(title)"})
    if MACHI not in [x["properties"]["title"] for x in meta["sheets"]]:
        sc.call(tok, f"/{MITSU_SS}:batchUpdate", method="POST", payload={"requests": [{"addSheet": {"properties": {"title": MACHI, "index": 0}}}]})
        sc.call(tok, f"/{MITSU_SS}/values/" + urllib.parse.quote(f"'{MACHI}'!A1:I1", safe=""), method="PUT",
                payload={"values": [["状態（空＝待ち）", "載せた日時", "見積書タブのgid", "見積番号", "宛先", "件名", "本文", "PDFの名前", "下書きを作った日時"]]},
                query={"valueInputOption": "RAW"})
    t = shitagaki(k).split("\n", 3)
    ate, kenmei, honbun_ = k["ate"], t[1].split("：", 1)[1], t[3]
    if k.get("test"):   # テスト送信は先方あての下書きにしない（宛先は空・件名に【テスト】）
        ate, kenmei = "", "【テスト】" + kenmei
    sc.call(tok, f"/{MITSU_SS}/values/" + urllib.parse.quote(f"'{MACHI}'!A:I", safe="") + ":append", method="POST",
            payload={"values": [["", datetime.datetime.now(JST).strftime("%Y/%m/%d %H:%M"), gid, k["ban"], ate, kenmei, honbun_, f"見積書_{k['ban']}.pdf", ""]]},
            query={"valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS"})


def shitagaki(k: dict) -> str:
    sama = f"{k['ate_mei']}様 " if k.get("ate_mei") else ""
    uti = "\n".join(f"　{x['hinmei']}　{int(x['tanka']):,}円 × {x['suuryou']}{x.get('tani', '台')}" for x in k["meisai"])
    return (f"宛先：{k['ate']}\n件名：お見積書のご送付（{sama}エアコン洗浄・見積番号{k['ban']}）\n\n"
            f"株式会社タカラサービス\n{k['tantou']} 様\n\nいつもお世話になっております。ワンヒッター株式会社の佐々木です。\n"
            f"専用ページからご依頼いただいた{sama}のエアコン洗浄について、お見積書をお送りします。\n\n{uti}\n"
            f"　小計 {k['shoukei']:,}円／消費税 {int(k['shoukei'] * 0.1):,}円／合計 {k['goukei']:,}円（税込）\n"
            + (f"　高速代：{k['toll']}\n" if k.get("toll") else "")
            + (f"　ご希望日時：{k['kibou']}\n" if k.get("kibou") else "")
            + "\n日程が決まりしだい、担当の渡辺から確定のご連絡をいたします。\nどうぞよろしくお願いいたします。\n\n"
            f"ワンヒッター株式会社\n佐々木 嶺\nTEL {TEL}")


KARI = pathlib.Path(os.path.expanduser("~/.cache/one-hitter/partner-kari.json"))   # お客様情報が入るのでリポジトリに置かない


def kari_yotei(d: dict, sid: str):
    """希望日時が選ばれていれば、和真さんのカレンダーに入れる【仮】の材料を返す（無ければ None）。
    例：「10月13日（火） 15:30〜16:30（現調60分）」「10月21日（水） 12:30〜」。"""
    m = re.search(r"(\d{1,2})月(\d{1,2})日.*?(\d{1,2}):(\d{2})", str(d.get("希望日時", "")))
    if not m:
        return None
    now = datetime.datetime.now(JST)
    mon, day, hh, mm = (int(x) for x in m.groups())
    nen = now.year + (1 if mon < now.month - 1 else 0)
    if d.get("種別") == "現調依頼":
        fun = 60
    else:
        h = re.search(r"([\d.]+)時間", str(d.get("作業時間の目安", "")))
        mi = re.search(r"(\d+)分", str(d.get("作業時間の目安", "")))
        fun = int(float(h.group(1)) * 60 if h else 0) + (int(mi.group(1)) if mi else 0) or 120
        fun = min(fun, 9 * 60)   # 1日を超える分は2日目以降を相談（ページの表示どおり）
    hajime = datetime.datetime(nen, mon, day, hh, mm, tzinfo=JST)
    mei = (d.get("現場のお名前") or d.get("お客様名") or "").strip()
    return {
        "submissionId": sid,
        "summary": ("【テスト】" if is_test(d) else "") + f"【仮】{d.get('提携先', '')}（{d.get('種別', '')}）" + (f" {mei}様" if mei else ""),
        "start": hajime.isoformat(), "end": (hajime + datetime.timedelta(minutes=fun)).isoformat(),
        "location": d.get("現場の住所", ""),
        "description": "\n".join(x for x in [
            f"提携先の専用フォームから（{d.get('種別', '')}）。確定したら提携先へ確定のご連絡・受注フォームで記録",
            f"内容：{d.get('内容', '')}", f"目安金額：{d.get('目安金額', '')}", f"高速代：{d.get('高速代の目安', '')}",
            f"お客様：{d.get('お客様名', '')}", f"お電話：{d.get('お客様の電話', '')}", f"ご要望：{d.get('ご要望', '')}",
            f"ご担当：{d.get('ご担当', '')}"] if not x.endswith("：")),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    forms = [f for f in ji.netlify(f"/sites/{SITE_ID}/forms") if f["name"] == FORM]
    subs = []
    for f in forms:
        subs += ji.netlify(f"/forms/{f['id']}/submissions")
        # 見積依頼は Netlify の迷惑判定（Akismet）に入ることがある（2026-10-10 実測：現調依頼は通り、見積依頼2件が迷惑）。
        # 鍵付き・noindex のページで、ページの送信ボタンから送ったもの（送信元の確認＝ブラウザから送信）かつ
        # 登録済みの提携先だけを本物として拾い、Netlify 側も「迷惑ではない」に戻す。
        for sp in ji.netlify(f"/forms/{f['id']}/submissions?state=spam"):
            dd = sp.get("data") or {}
            if dd.get("送信元の確認") == "ブラウザから送信" and dd.get("提携先") in MIHON:
                subs.append(sp)
                if not a.dry_run:
                    ham(sp["id"])
    sumi = set(json.loads(KIROKU.read_text(encoding="utf-8"))) if KIROKU.exists() else set()
    atarashii = [s for s in subs if s["id"] not in sumi]
    print(f"未通知: {len(atarashii)}件")
    for s in atarashii:
        print("\n" + honbun(s.get("data") or {}))
    if a.dry_run or not atarashii:
        return
    for s in atarashii:
        d = s.get("data") or {}
        msg = honbun(d)
        if d.get("種別") == "見積依頼":
            k = mitsumorisho(d, dry=False)
            if k.get("err"):
                msg += "\n見積書：" + k["err"]
                print("見積書：", k["err"])
            else:
                msg += f"\n見積書（自動作成・{k['ban']}・合計 {k['goukei']:,}円 税込）：{k['url']}\n送り先：{k['ate']}\nメールの下書き（PDF・印影付き）は嶺さんの Gmail に自動で入ります（送るのは嶺さん）"
                print(f"\n見積書を作りました：{k['title']}\n{k['url']}\nPDF：{k.get('pdf') or k.get('pdf_err')}")
                print("\n--- メール下書き（mitsumori-shitagaki.gs が PDF を付けて嶺さんの Gmail に作る）---\n" + shitagaki(k))
        ky = kari_yotei(d, s["id"])
        if ky:
            ima = json.loads(KARI.read_text(encoding="utf-8")) if KARI.exists() else []
            if s["id"] not in [x["submissionId"] for x in ima]:
                ima.append(ky)
                KARI.parent.mkdir(parents=True, exist_ok=True)
                KARI.write_text(json.dumps(ima, ensure_ascii=False, indent=1), encoding="utf-8")
            msg += "\n和真さんのカレンダーに【仮】で入れます（CMO）"
            print("\n--- カレンダーに入れる【仮】（CMO が Google Calendar コネクタで和真さんのカレンダーへ。入れたら partner-kari.json から消す）---\n"
                  + json.dumps(ky, ensure_ascii=False, indent=1))
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "line_client.py"), "push", msg],
                           capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(f"LINE に送れませんでした（{s['id']}）: {r.stdout}{r.stderr}")
        sumi.add(s["id"])
        KIROKU.write_text(json.dumps(sorted(sumi), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n知らせました: {len(atarashii)}件")


if __name__ == "__main__":
    main()
