#!/usr/bin/env python3
"""施設カードの設置依頼（第1波〜）を、問い合わせフォームとメールで出す。送信のたびに売上スプシへ記録する。

【決まり】（docs/節目チャネル-全体構造.md 3章・9章、オーナー決定 2026-09-13）
  - 文面は docs/節目チャネル-文面-承認シート.md（オーナー承認済みの版）から作る。ここで文を足さない
  - 送るのは公開のフォームとアドレスだけ。「営業お断り」明記のフォームは送らない。断られた施設は永久に送らない
  - 50件ずつ。1件ずつ送信ログ（施設カード_送信ログ）に書き、進捗タブのステージ・接触方法・回数・日付を更新する
  - --send を付けない限り何も送らない（フォームは入力まで行い、スクリーンショットを撮って止まる）

【入力】
  data/facilities-2026-09-clean.json     施設（Places）
  data/facilities-2026-09-contacts.json  連絡先（フォームURL・メール・営業お断り）
  売上スプシ「施設カード_進捗」          優先度・ステージ（未接触だけが対象）

使い方:
  python3 tools/shisetsu-outreach.py plan --wave 1 --n 50            # 送る50件を選んで表示（送らない）
  python3 tools/shisetsu-outreach.py form --wave 1 --n 50            # フォーム：入力してスクショ（送らない）
  python3 tools/shisetsu-outreach.py form --wave 1 --n 50 --send     # フォーム：送信してログ
  python3 tools/shisetsu-outreach.py mail --wave 1 --n 50            # メール：本文を dist/outreach/ に書き出す（送信は別）
"""
import argparse
import asyncio
import datetime as dt
import json
import pathlib
import re
import sys
import urllib.parse

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import media_common as C  # noqa: E402
import sheets_client as sc  # noqa: E402

ROOT = C.ROOT
FAC = ROOT / "data" / "facilities-2026-09-clean.json"
CON = ROOT / "data" / "facilities-2026-09-contacts.json"
OUT = ROOT / "dist" / "outreach"
SS = "1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64"
TAB_P = "施設カード_進捗"
TAB_L = "施設カード_送信ログ"
HEAD_ROW = 13  # 進捗タブのヘッダ行（1始まり）
JST = dt.timezone(dt.timedelta(hours=9))
SETTI_URL = f"{C.DOKUHON_URL}/setti/"
SENDER = "ワンヒッター株式会社 佐々木"

# ---------------- 文面（承認シート③＝フォーム用の短い版。①②はメール用）
def yomihon(kind: str) -> dict:
    if kind in ("産婦人科・産院", "小児科", "ベビー用品店", "子育て支援（公的）"):
        return {"who": "赤ちゃんを迎えるご家庭", "title": "赤ちゃんが来る前に知っておきたい、家の中の見えない汚れ", "url": f"{C.DOKUHON_URL}/akachan/",
                "min": "10分", "where": "エアコンや浴室", "src": "現場の写真と東京都の資料", "place": "待合か受付", "menu": "エアコン1台＋浴室 25,960円"}
    return {"who": "犬や猫を迎えるご家庭", "title": "新しい家族と暮らす家の、見えない汚れ", "url": f"{C.DOKUHON_URL}/pet/",
            "min": "8分", "where": "エアコンや換気扇", "src": "現場の写真と環境省・東京都の資料", "place": "レジ横か待合", "menu": "エアコン1台＋換気扇 25,960円"}


def houshuu(name: str, kind: str) -> tuple:
    """法人名で判定（docs/節目チャネル-全体構造.md 2章）。名前に法人格が無い医療機関は12%型で送り、辞退があれば報酬なし型に切り替える。"""
    if re.search(r"医療法人|社会福祉法人|学校法人|特定非営利|NPO|区立|市立|都立|県立|国立|区 |市 ", name) or kind == "子育て支援（公的）":
        return ("報酬なし型", "医療法人さま等には紹介料をお出ししていません。退院後・お迎え後のご家庭との接点を延ばす情報提供として、ご検討いただければ幸いです。")
    return ("12%型", "貴施設のカードからご利用があった場合、ご利用額の12%を月末締め・翌月末にお支払いします（雑収入として計上いただけます。支払通知を自動でお送りします）。")


def form_text(f: dict, kind: str) -> str:
    y = yomihon(kind)
    _, h = houshuu(f["施設名"], kind)
    h_short = "ご利用があった場合はご利用額の12%をお支払いしています。" if h.startswith("貴施設") else "医療法人さま等には紹介料をお出ししていません（情報提供のみ）。"
    return (f"江戸川区北葛西のハウスクリーニング店 ワンヒッター株式会社の佐々木と申します。\n"
            f"{y['who']}向けの読み物「{y['title']}」を作りました（{y['min']}・{y['url']}）。\n"
            f"{y['where']}の中の見えない汚れを、{y['src']}でお話しするものです。\n"
            f"{y['place']}にA6のカードを1枚置いていただけないでしょうか。説明も手続きも不要で、カードはPDFでお送りします。\n"
            f"{h_short}毎週、何名が読まれたかをお知らせします。\n"
            f"置いていただける場合：{SETTI_URL}（1分）\n"
            f"不要な場合は、このままご放念ください。以後お送りしません。\n"
            f"〒134-0081 東京都江戸川区北葛西5-14-11／{C.UNEI_TEL}")


def mail_text(f: dict, kind: str) -> tuple:
    y = yomihon(kind)
    _, h = houshuu(f["施設名"], kind)
    kikan = "貴院（貴施設）の利用者さま" if y["who"].startswith("赤ちゃん") else "お客さま（患者さま）"
    subj = ("赤ちゃんを迎えるご家庭向けの読み物を、待合に置いていただけませんか（江戸川区のハウスクリーニング店）" if y["who"].startswith("赤ちゃん")
            else "犬猫を迎えるご家庭向けの読み物を、レジ横に置いていただけませんか（江戸川区のハウスクリーニング店）")
    body = f"""{f['施設名']} ご担当者さま

江戸川区北葛西でハウスクリーニングをしております、ワンヒッター株式会社の佐々木と申します。

{y['who']}に向けて、「{y['title']}」という読み物を作りました。
{y['where']}の中に、目に見えないまま何が溜まっているかを、私たちが{y['src']}でお話しするものです。
売り込みの資料ではなく、{kikan}に知っておいていただきたい内容として書きました。
読み物はこちらです（{y['min']}ほどで読めます。冷蔵庫に貼れる「手入れの早見表」のPDFも付いています）：{y['url']}

お願いは1つだけです。{y['place']}に、A6のカードを1枚置いていただけないでしょうか。
カードのQRから読み物が読めます。ご説明もお手続きも不要で、カードはPDFでお送りします（普通紙で印刷していただけます。印刷したものをご希望の場合はお申し付けください）。

―― 以下は、置いていただける場合の補足です ――
・読み物の末尾に、当社のクリーニング（{y['menu']}・税込。出張費・追加作業費なし）と、エアコン・洗濯槽・追い焚き配管の無料点検のご案内を載せています
・毎週月曜に、貴施設のカードから何名が読まれたかをメールでお知らせします（個人が分かる情報は含みません）
・{h}

置いていただける場合は、下のリンクから設置場所だけお知らせください（1分）。
{SETTI_URL}

ご不要の場合は、このメールへ「不要」とご返信ください。以後お送りしません。

ワンヒッター株式会社 佐々木 嶺
〒134-0081 東京都江戸川区北葛西5-14-11／{C.UNEI_TEL}／{C.UNEI_SITE}"""
    return subj, body


# ---------------- 対象の選定
def load() -> list:
    fac = {f["id"]: f for f in json.loads(FAC.read_text(encoding="utf-8"))}
    con = {c["id"]: c for c in json.loads(CON.read_text(encoding="utf-8"))} if CON.exists() else {}
    tok = sc.access_token(sc.load_credentials())
    vals = sc.call(tok, f"/{SS}/values/{urllib.parse.quote(TAB_P + '!A' + str(HEAD_ROW) + ':AM1000')}").get("values", [])
    head = vals[0]
    col = {h: i for i, h in enumerate(head)}
    rows = []
    for r in vals[1:]:
        r = r + [""] * (len(head) - len(r))
        name = r[col["施設名"]]
        f = next((x for x in fac.values() if x["施設名"] == name), None)
        if not f:
            continue
        c = con.get(f["id"], {})
        rows.append({**f, "No": r[col["No"]], "優先度": r[col["優先度"]], "ステージ": r[col["ステージ"]], "接触回数": r[col["接触回数"]] or "0",
                     "row": None, "contact": c})
    return rows


def email_of(c: dict) -> str:
    """contacts.json の emails は {'address','kind'} の配列（文字列のこともある）。汎用アドレスを優先"""
    es = c.get("emails") or []
    addrs = [(e["address"] if isinstance(e, dict) else e) for e in es]
    addrs = [a for a in addrs if a and "@" in a]
    gen = [a for a in addrs if a.lower().startswith(("info@", "contact@", "mail@", "office@", "support@", "inquiry@"))]
    return (gen or addrs or [""])[0]


def pick(rows: list, n: int, how: str) -> list:
    out = []
    used = set()  # 同じフォーム（同一法人の複数店）には1回だけ送る
    for r in rows:
        if r["ステージ"] != "未接触" or r["優先度"] == "C":
            continue
        c = r["contact"]
        if c.get("no_sales"):
            continue
        if how == "form" and not c.get("contact_form_url"):
            continue
        if how == "mail" and not email_of(c):
            continue
        key = c.get("contact_form_url") if how == "form" else email_of(c)
        if key in used:
            continue
        used.add(key)
        out.append(r)
        if len(out) >= n:
            break
    return out


# ---------------- ログ
def log_send(tok, wave: int, f: dict, how: str, dest: str, kata: str, result: str, note: str = "") -> None:
    now = dt.datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    sc.call(tok, f"/{SS}/values/{urllib.parse.quote(TAB_L + '!A1')}:append", method="POST",
            query={"valueInputOption": "USER_ENTERED", "insertDataOption": "INSERT_ROWS"},
            payload={"values": [[now, wave, f["No"], f["施設名"], f["種別"], how, dest, kata, SENDER, result, "", "", note]]})


def update_stage(tok, f: dict, how: str) -> None:
    """進捗タブ：ステージ→接触済、接触方法、回数+1、初回/最終接触日、次回アクション（7日後の再送）"""
    vals = sc.call(tok, f"/{SS}/values/{urllib.parse.quote(TAB_P + '!A' + str(HEAD_ROW) + ':AM1000')}").get("values", [])
    head = vals[0]
    col = {h: i for i, h in enumerate(head)}
    for i, r in enumerate(vals[1:], start=HEAD_ROW + 1):
        r = r + [""] * (len(head) - len(r))
        if r[col["施設名"]] != f["施設名"]:
            continue
        today = dt.datetime.now(JST).strftime("%Y-%m-%d")
        cnt = int(r[col["接触回数"]] or 0) + 1
        nxt = (dt.datetime.now(JST) + dt.timedelta(days=7)).strftime("%Y-%m-%d")
        upd = {"ステージ": "接触済（不在・折返し）", "接触方法": {"form": "フォーム", "mail": "メール"}[how], "接触回数": cnt,
               "初回接触日": r[col["初回接触日"]] or today, "最終接触日": today, "次回アクション": "反応なしなら再送（1回だけ）", "次回予定日": nxt, "当社担当": "web-inflow"}
        data = []
        for k, v in upd.items():
            ci = col[k]
            a1 = f"{TAB_P}!{colletter(ci)}{i}"
            data.append({"range": a1, "values": [[v]]})
        sc.call(tok, f"/{SS}/values:batchUpdate", method="POST", payload={"valueInputOption": "USER_ENTERED", "data": data})
        return


def colletter(i: int) -> str:
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


# ---------------- フォーム送信（Playwright）
FIELD_HINTS = {
    "company": ["会社", "法人", "団体", "貴社", "company", "organization", "corp"],
    "name": ["お名前", "氏名", "名前", "担当者", "name"],
    "kana": ["フリガナ", "ふりがな", "カナ", "kana", "furigana"],
    "email": ["メール", "mail", "e-mail"],
    "tel": ["電話", "tel", "phone"],
    "subject": ["件名", "題名", "subject", "用件"],
    "body": ["お問い合わせ内容", "お問合せ内容", "内容", "本文", "メッセージ", "message", "inquiry", "comment", "detail", "ご質問", "ご要望"],
}
VALUES = {"company": "ワンヒッター株式会社", "name": "佐々木", "kana": "ササキ", "tel": C.UNEI_TEL}


def hint_of(label: str) -> str:
    l = label.lower()
    for key, words in FIELD_HINTS.items():
        if any(w.lower() in l for w in words):
            return key
    return ""


async def fill_form(pg, url: str, text: str, email_from: str, subject: str) -> dict:
    await pg.goto(url, timeout=30000, wait_until="domcontentloaded")
    await pg.wait_for_timeout(1500)
    html = await pg.content()
    if re.search(r"営業[^。]{0,12}(お断り|ご遠慮|禁止)|セールス[^。]{0,8}(お断り|ご遠慮)", html):
        return {"ok": False, "reason": "営業お断りの記載"}
    filled = {}
    for el in await pg.query_selector_all("input:not([type=hidden]):not([type=submit]):not([type=button]):not([type=checkbox]):not([type=radio]), textarea, select"):
        try:
            tag = await el.evaluate("e=>e.tagName.toLowerCase()")
            typ = (await el.get_attribute("type") or "").lower()
            name = (await el.get_attribute("name") or "") + " " + (await el.get_attribute("id") or "") + " " + (await el.get_attribute("placeholder") or "")
            lab = await el.evaluate("e=>{const l=e.labels&&e.labels[0]?e.labels[0].innerText:'';const p=e.closest('tr,li,p,div');return l+' '+(p?p.innerText.slice(0,60):'')}")
            key = hint_of(name + " " + lab)
            if tag == "textarea":
                key = "body"
            if typ == "email":
                key = "email"
            if typ == "tel":
                key = "tel"
            if tag == "select":
                continue
            if not key or key in filled:
                continue
            val = {"email": email_from, "subject": subject, "body": text}.get(key) or VALUES.get(key)
            if val:
                await el.fill(val)
                filled[key] = True
        except Exception:
            continue
    # 同意チェック
    for cb in await pg.query_selector_all("input[type=checkbox]"):
        try:
            lab = await cb.evaluate("e=>(e.labels&&e.labels[0]?e.labels[0].innerText:'')+' '+(e.parentElement?e.parentElement.innerText.slice(0,40):'')")
            if re.search(r"同意|確認|プライバシー|個人情報", lab):
                await cb.check()
        except Exception:
            pass
    return {"ok": "body" in filled, "filled": sorted(filled), "reason": "" if "body" in filled else "本文欄が見つからない"}


async def run_forms(targets: list, wave: int, send: bool, email_from: str) -> None:
    from playwright.async_api import async_playwright
    OUT.mkdir(parents=True, exist_ok=True)
    tok = sc.access_token(sc.load_credentials())
    async with async_playwright() as p:
        # この環境の外向き HTTPS は代理サーバー経由で、Chromium の直接の通信は途中で切られる（2026-09-13 実測：ERR_CONNECTION_RESET）。
        # そこでブラウザの全リクエストを Playwright の HTTP クライアント（代理サーバーを通れる）で取りに行き、ブラウザに返す
        b = await p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--no-sandbox"])
        ctx = await b.new_context(viewport={"width": 1200, "height": 1600}, locale="ja-JP", ignore_https_errors=True,
                                  user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36")

        async def relay(route, request):
            try:
                r = await route.fetch(max_redirects=5)
                await route.fulfill(response=r)
            except Exception:
                await route.abort()
        await ctx.route("**/*", relay)
        for f in targets:
            url = f["contact"]["contact_form_url"]
            pg = await ctx.new_page()
            text = form_text(f, f["種別"])
            subj = "利用者さま向けの読み物（A6カード）を置いていただけませんか"
            try:
                r = await fill_form(pg, url, text, email_from, subj)
                shot = OUT / f"w{wave}-{f['No']}.png"
                await pg.screenshot(path=str(shot), full_page=True)
                if not r["ok"]:
                    print("スキップ", f["No"], f["施設名"], r["reason"])
                    log_send(tok, wave, f, "フォーム", url, "③", f"未送信（{r['reason']}）")
                    continue
                if not send:
                    print("入力のみ", f["No"], f["施設名"], r["filled"], shot.name)
                    continue
                # 送信：確認画面があれば2段階
                btn = await pg.query_selector("input[type=submit], button[type=submit], button:has-text('送信'), input[value*='送信'], input[value*='確認'], button:has-text('確認')")
                if not btn:
                    log_send(tok, wave, f, "フォーム", url, "③", "未送信（送信ボタン不明）")
                    print("ボタン不明", f["No"], f["施設名"])
                    continue
                await btn.click()
                await pg.wait_for_timeout(2500)
                btn2 = await pg.query_selector("input[type=submit][value*='送信'], button:has-text('送信'), input[value*='送信する']")
                if btn2:
                    await btn2.click()
                    await pg.wait_for_timeout(2500)
                await pg.screenshot(path=str(OUT / f"w{wave}-{f['No']}-sent.png"), full_page=True)
                body = (await pg.content())
                ok = bool(re.search(r"送信(が)?完了|ありがとうござい|受け付け|受付|送信しました|thank", body, re.I))
                log_send(tok, wave, f, "フォーム", url, "③", "送信" if ok else "送信（完了表示は未確認）")
                update_stage(tok, f, "form")
                print("送信", f["No"], f["施設名"], "OK" if ok else "要確認")
            except Exception as e:
                log_send(tok, wave, f, "フォーム", url, "③", f"失敗（{type(e).__name__}）")
                print("失敗", f["No"], f["施設名"], type(e).__name__, str(e)[:120])
            finally:
                await pg.close()
        await b.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["plan", "form", "mail"])
    ap.add_argument("--wave", type=int, default=1)
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--send", action="store_true")
    ap.add_argument("--from-email", default="", help="フォームの返信先メール（CMO が決めた送信元）")
    a = ap.parse_args()
    rows = load()
    if a.mode == "plan":
        for how in ("form", "mail"):
            t = pick(rows, a.n, how)
            print(f"== {how}: {len(t)}件")
            for f in t:
                print(f" {f['No']:>4} {f['優先度']} {f['種別']:<10} {f['施設名'][:24]:<24} {f['contact'].get('contact_form_url') if how == 'form' else email_of(f['contact'])}")
        return
    if a.mode == "mail":
        OUT.mkdir(parents=True, exist_ok=True)
        t = pick(rows, a.n, "mail")
        for f in t:
            subj, body = mail_text(f, f["種別"])
            (OUT / f"w{a.wave}-{f['No']}-mail.txt").write_text(f"To: {email_of(f['contact'])}\nSubject: {subj}\n\n{body}", encoding="utf-8")
        print("メール本文を書き出し:", len(t), "件 →", OUT, "（送信は送信元が決まってから）")
        return
    if not a.from_email:
        sys.exit("--from-email（返信先）が要る。CMO が決めた送信元を指定する")
    t = pick(rows, a.n, "form")
    asyncio.run(run_forms(t, a.wave, a.send, a.from_email))


if __name__ == "__main__":
    main()
