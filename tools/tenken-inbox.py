#!/usr/bin/env python3
"""無料点検サイトのフォーム（Netlify Forms）に届いたものを、送るべき「物」に変える。

【なぜこの形か】
  docs/無料点検-全体構造.md 2章・6章のとおり、人がやるのは点検と現場フォームの入力だけ。
  受付メール・前日リマインド・契約書面（PDF）・報告書ページ・その送付文は、
  届いたフォームから機械的に作る。**このツールは何も送らない。**
  送る手段（LINE／SMS／メール）は別の部品なので、ここでは
  dist/tenken/outbox/ に「宛先・件名・本文・添付」を JSON で置くところまで。
  送る前に人が目を通せる形にしておくのは、文面一式のオーナー承認が終わるまでの安全弁でもある。

【入力の2つのモード】
  --sample  内蔵のサンプル（架空の申込・現場記録・その場申込）で動かす。ネットに出ない。
            トークン（~/.config/one-hitter/netlify-token.txt）かサイトID（deploy/.netlify-tenken.json）が
            無いときは、--live を付けても自動でこちらに落ちる（お知らせを出す）。
  --live    Netlify API から tenken-* フォームの送信を読む（読むだけ。書かない）。

【出力】 dist/tenken/（.gitignore 済み。お客様の氏名・住所・電話が入るのでコミットしない）
  shomen/<申込番号>.pdf              契約書面。lp/media/tenken/shomen.html を Playwright で開いて印刷
  houkoku/<受付番号>.html            報告書ページ（deploy-media.py --extra dist/tenken/houkoku:/h で /h/ に載る）
  houkoku/<受付番号>/写真N.jpg       報告書の写真（--live のときは Netlify から取り寄せる）
  outbox/<番号>.json                  送付物（to / channel / subject / body / attachments / send_on）
  processed.json                     処理済みの送信ID。2回目からは飛ばす（--redo で全部やり直し）

【フォームの項目名】 tools/build-tenken.py の hidden_form と一字一句同じでないと拾えない。
  そのため FORM_* と MENUS はここに書き写さず、build-tenken.py から importlib で読む。

【文面】 docs/無料点検-文面-承認シート.md の ``` の中を穴埋め（{お名前} など）して使う。
  シートが正（オーナー承認が1か所で済む）。シートか節が無いときだけ、ここに書いた短い既定文を使う。

【書かないこと】 報告書に「危険」「壊れる」は書かない（特商法の不実告知の禁止・8章）。
  渡辺さんの一言にその語が入っていたら伏せ字にして、警告を出す。

使い方:
  python3 tools/tenken-inbox.py                  # サンプル（トークン等が無ければ自動でこちら）
  python3 tools/tenken-inbox.py --live           # Netlify から読む（読むだけ）
  python3 tools/tenken-inbox.py --sample --redo  # 処理済みも作り直す
"""
import argparse
import base64
import datetime as dt
import importlib.util
import json
import os
import pathlib
import re
import shutil
import sys
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import media_common as C  # noqa: E402

spec = importlib.util.spec_from_file_location("build_tenken", ROOT / "tools" / "build-tenken.py")
BT = importlib.util.module_from_spec(spec)
spec.loader.exec_module(BT)

JST = ZoneInfo("Asia/Tokyo")
API = "https://api.netlify.com/api/v1"
TOKEN_KITEI = os.path.expanduser("~/.config/one-hitter/netlify-token.txt")
STATE = ROOT / "deploy" / ".netlify-tenken.json"
DIST = ROOT / "dist" / "tenken"
SHOMEN_HTML = ROOT / "lp" / "media" / "tenken" / "shomen.html"
BUNMEN = ROOT / "docs" / "無料点検-文面-承認シート.md"
SAMPLE_PHOTO = ROOT / "assets" / "photos" / "IMG_7976.jpg"
CHROMIUM_KOUHO = ["/opt/pw-browsers/chromium", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"]

TENKEN_URL = C.TENKEN_URL
HOUKOKU_URL = TENKEN_URL + "/h/{id}.html"          # deploy-media.py --extra dist/tenken/houkoku:/h
YOYAKU_URL = C.BOOKING.rstrip("/") + "/?src=tenken-{id}"
SHOUKAI_URL = TENKEN_URL + "/?src=shoukai-{id}"

NG_GO = ("危険", "壊れる")
FILE_FIELDS = [f"写真{i}" for i in range(1, 6)] + ["動画1"]

# 所見3択 → 報告書の文。「不要」だけ次回の目安を足す（MENUS の「次回」）
SHOKEN_BUN = {"要洗浄": "洗浄をおすすめします。", "様子見": "今回は様子見でよいと思います。", "不要": "今回は不要です。次回の目安は{次回}です。"}

# 契約書面の送付文（docs/無料点検-文面-承認シート.md の「契約書面の送付」があればそちらを使う）
SHOMEN_BODY_KITEI = (
    "{name} 様\n\n"
    "本日はお時間をいただき、ありがとうございました。\n"
    "お申込みいただいたクリーニングの書面を添付しました。\n"
    "施工日は明日までにSMSでご連絡して確定します。\n"
    "この書面を受け取った日を含めて8日間は、無条件でキャンセルできます（添付の赤枠をご覧ください）。\n\n"
    f"{C.UNEI} {C.UNEI_TANTOU}\n{C.UNEI_ADDR}／{C.UNEI_TEL}"
)


# ================================================================ 入力
def token() -> str:
    t = os.environ.get("NETLIFY_TOKEN", "").strip()
    if not t and os.path.exists(TOKEN_KITEI):
        t = open(TOKEN_KITEI, encoding="utf-8").read().strip()
    return t


def netlify(tok: str, path: str):
    req = urllib.request.Request(API + path)
    req.add_header("Authorization", "Bearer " + tok)
    with urllib.request.urlopen(req, timeout=60) as res:
        return json.loads(res.read())


def yomu_live():
    """Netlify から tenken-* の送信を読む。読めない理由があれば (None, 理由) を返す（落とさない）"""
    tok = token()
    if not tok:
        return None, f"Netlifyトークンがありません（{TOKEN_KITEI}）"
    if not STATE.exists():
        return None, f"{STATE.relative_to(ROOT)} がありません（無料点検サイトが未作成）"
    sid = json.loads(STATE.read_text(encoding="utf-8"))["site_id"]
    names = {BT.FORM_MOUSHIKOMI, BT.FORM_GENBA, BT.FORM_KEIYAKU}
    try:
        forms = [f for f in netlify(tok, f"/sites/{sid}/forms") if f["name"] in names]
        subs = []
        for f in forms:
            for s in netlify(tok, f"/forms/{f['id']}/submissions"):
                s.setdefault("form_name", f["name"])
                subs.append(s)
    except urllib.error.HTTPError as e:
        return None, f"Netlify API が {e.code}: {e.read().decode()[:200]}"
    return subs, ""


def sample() -> list:
    """架空のデータ。実在の氏名・住所・電話は入れない。写真は掲載可の実写を使う"""
    tid = "T20261015-AB3K"
    gid = "G20261015-Q7RZ"
    shomen = {
        "id": tid, "date": "2026年10月15日（木）", "staff": "渡辺", "name": "見本 太郎", "addr": "江戸川区北葛西0-0-0 見本マンション101",
        "tel": "09000000000", "mail": "sample@example.com", "menu": "洗濯機クリーニング", "detail": "無料点検（洗濯槽の裏側）で確認した箇所の分解洗浄",
        "opts": "洗濯機 排水溝クリーニング 3,630円", "when": "2026年10月24日（土） 午前（9〜12時）（第1希望。明日までにSMSで確定）", "dur": "120分",
        "price": "19,272円", "discount": "閑散期割引 10%（1,738円引き）を含む", "denshi": True,
    }
    return [
        {"id": "sample-moushikomi-1", "form_name": BT.FORM_MOUSHIKOMI, "created_at": "2026-10-12T01:10:00Z", "data": {
            "受付番号": tid, "点検メニュー": "洗濯槽の裏側", "洗濯機の種類": "縦型", "希望日時": "2026-10-15 12:30",
            "お名前": "見本 太郎", "お電話番号": "09000000000", "ご住所": "江戸川区北葛西0-0-0 見本マンション101", "メール": "sample@example.com",
            "気になること": "洗濯物に黒いカスが付く", "同意": "勧誘あり了解・個人情報の利用目的確認", "流入元": "instagram", "送信時刻": "2026-10-12T10:10:00+09:00"}},
        {"id": "sample-genba-1", "form_name": BT.FORM_GENBA, "created_at": "2026-10-15T04:05:00Z", "data": {
            "受付番号": tid, "お名前": "見本 太郎", "見た場所": "洗濯槽の裏側", "メニューID": "A", "きっかけ": "申込があった点検",
            "機種年数": "パナソニック 縦型 2018年ごろ", "ATP": "", "所見": "要洗浄",
            "一言": "槽の裏側の下のほうに黒いカビが帯状に付いていました。市販のクリーナーでは届かない場所です。",
            "その場の案内": "QRを出した", "送信時刻": "2026-10-15T13:05:00+09:00",
            "写真1": str(SAMPLE_PHOTO), "写真2": str(SAMPLE_PHOTO)}},
        {"id": "sample-keiyaku-1", "form_name": BT.FORM_KEIYAKU, "created_at": "2026-10-15T04:12:00Z", "data": {
            "申込番号": tid, "受付番号": tid, "お名前": "見本 太郎", "お電話番号": "09000000000", "ご住所": shomen["addr"], "メール": "sample@example.com",
            "役務": "洗濯機クリーニング", "点検メニュー": "洗濯槽の裏側", "オプション": shomen["opts"], "希望日": "2026-10-24", "時間帯": "午前（9〜12時）",
            "合計": "19272", "割引率": "0.1", "電磁的交付の承諾": "承諾", "クーリングオフ説明": "読了チェック",
            "書面": json.dumps(shomen, ensure_ascii=False), "送信時刻": "2026-10-15T13:12:00+09:00", "流入元": "点検"}},
        {"id": "sample-genba-2", "form_name": BT.FORM_GENBA, "created_at": "2026-10-16T06:40:00Z", "data": {
            "受付番号": gid, "お名前": "見本 花子", "見た場所": "追い焚き配管の中", "メニューID": "B", "きっかけ": "施工のついで",
            "機種年数": "", "ATP": "320", "所見": "不要", "一言": "循環口の周りはきれいでした。数値も低めです。",
            "その場の案内": "案内なし", "送信時刻": "2026-10-16T15:40:00+09:00", "写真1": str(SAMPLE_PHOTO)}},
    ]


def yomu(mode: str):
    """(送信のリスト, 実際のモード, お知らせ) を返す。tenken-weekly.py からも使う"""
    if mode == "live":
        subs, riyuu = yomu_live()
        if subs is not None:
            return subs, "live", ""
        return sample(), "sample", f"{riyuu}。サンプルで動かします。"
    return sample(), "sample", ""


# ================================================================ 共通
def jp_date(iso: str) -> str:
    try:
        d = dt.date.fromisoformat(iso[:10])
    except ValueError:
        return iso
    return f"{d.year}年{d.month}月{d.day}日（{'月火水木金土日'[d.weekday()]}）"


def anzen_id(s: str) -> str:
    """ファイル名に使う番号。フォームの値なので、パス区切りなどを落とす"""
    return re.sub(r"[^A-Za-z0-9_-]", "", s or "")[:40] or "noid"


def waribiki_ritsu(P: dict, tsuki: int) -> float:
    k = "1-2月" if tsuki <= 2 else "3-4月" if tsuki <= 4 else "5-7月" if tsuki <= 7 else "8-10月" if tsuki <= 10 else "11-12月"
    return float(P["raw"].get("早期予約割引", {}).get(k, 0) or 0)


def bunmen(midashi: str) -> tuple:
    """承認シート（docs/無料点検-文面-承認シート.md）から、見出しに midashi を含む節の
    (件名, [``` で囲まれた本文…]) を返す。文面はシートが正で、ここに書き写さない（承認が1か所で済むように）。
    シートか節が無ければ (None, []) を返し、呼ぶ側が既定文を使う"""
    if not BUNMEN.exists():
        return None, []
    text = BUNMEN.read_text(encoding="utf-8")
    m = re.search(rf"^#+\s*[^\n]*{re.escape(midashi)}[^\n]*\n(.*?)(?=^#+\s|\Z)", text, re.S | re.M)
    if not m:
        return None, []
    setsu = m.group(1)
    km = re.search(r"^件名：(.+)$", setsu, re.M)
    blocks = [b.strip("\n") for b in re.findall(r"```\n(.*?)```", setsu, re.S)]
    return (km.group(1).strip() if km else None), blocks


def umeru(text: str, atai: dict) -> str:
    """{お名前} のような穴を埋める。値が無い穴はそのまま残す（送る前に人が気づけるように）"""
    return re.sub(r"\{([^{}]+)\}", lambda m: str(atai.get(m.group(1), m.group(0))), text)


def joukenbun(text: str, shoken: str) -> str:
    """「（要洗浄の場合）…」「（不要の場合）…」の行は、所見に合う行だけ残して印を外す"""
    out = []
    for line in text.split("\n"):
        m = re.match(r"^（(.+?)の場合）(.*)$", line)
        if not m:
            out.append(line)
        elif m.group(1) == shoken:
            out.append(m.group(2))
    return "\n".join(out)


def kaku_json(path: pathlib.Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


# ================================================================ 契約書面 → PDF
def shomen_pdf(shomen_json: str, out: pathlib.Path, online_fonts: bool) -> None:
    """shomen.html は location.hash の base64（UTF-8のバイト列）を
    JSON.parse(decodeURIComponent(escape(atob(hash)))) で読む。だから UTF-8 のバイト列を base64 にする"""
    from playwright.sync_api import sync_playwright
    v = json.loads(shomen_json)
    b64 = base64.b64encode(json.dumps(v, ensure_ascii=False).encode("utf-8")).decode("ascii")
    url = SHOMEN_HTML.resolve().as_uri() + "#" + b64
    exe = next((p for p in CHROMIUM_KOUHO if os.path.exists(p)), None)
    out.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
        page = b.new_page()
        if not online_fonts:
            # Webフォント（Google Fonts）を待たない。ネットが無くても・遅くても同じPDFができる
            page.route("**/*", lambda r: r.continue_() if r.request.url.startswith("file:") else r.abort())
        page.goto(url, wait_until="load", timeout=30000)
        page.wait_for_selector("#shomen table", timeout=10000)
        page.emulate_media(media="print")
        page.pdf(path=str(out), format="A4", print_background=True, margin={"top": "12mm", "bottom": "12mm", "left": "10mm", "right": "10mm"})
        b.close()


def keiyaku(s: dict, dist: pathlib.Path, online_fonts: bool) -> str:
    d = s["data"]
    mid = anzen_id(d.get("申込番号") or d.get("受付番号") or s["id"])
    pdf = dist / "shomen" / f"{mid}.pdf"
    shomen_pdf(d.get("書面") or "{}", pdf, online_fonts)
    mail = (d.get("メール") or "").strip()
    v = json.loads(d.get("書面") or "{}")
    ana = {"お名前": v.get("name") or d.get("お名前") or "", "name": v.get("name") or d.get("お名前") or "", "申込番号": mid}
    kenmei, blocks = bunmen("契約書面の送付")
    body = umeru(blocks[0] if blocks else SHOMEN_BODY_KITEI, ana)
    kaku_json(dist / "outbox" / f"{mid}.json", {
        "kind": "shomen", "to": mail or "", "tel": d.get("お電話番号", ""), "channel": "mail" if mail else "sms",
        "subject": umeru(kenmei or "【ワンヒッター】クリーニングお申込みの書面（申込番号 {申込番号}）", ana),
        "body": body, "attachments": [str(pdf)], "denshi": d.get("電磁的交付の承諾", ""),
    })
    return f"書面 {mid} → {pdf.relative_to(ROOT)}（{pdf.stat().st_size:,} bytes）"


# ================================================================ 現場記録 → 報告書
def shashin_toru(d: dict, uid: str, dist: pathlib.Path, live: bool) -> list:
    """写真・動画を dist/tenken/houkoku/<id>/ に置き、(相対パス, 動画か) を返す。
    Netlify の API では、ファイル項目は URL（か {url,filename} の辞書）で来る"""
    out = []
    for f in FILE_FIELDS:
        v = d.get(f)
        if not v:
            continue
        src = v.get("url") if isinstance(v, dict) else str(v)
        if not src:
            continue
        ext = pathlib.Path(src.split("?")[0]).suffix.lower() or (".mp4" if f.startswith("動画") else ".jpg")
        dest = dist / "houkoku" / uid / f"{f}{ext}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            if src.startswith("http"):
                if not live:
                    print(f"  注意: サンプルなのに URL の写真（{f}）。取りに行きません")
                    continue
                req = urllib.request.Request(src)
                tok = token()
                if "netlify" in src and tok:
                    req.add_header("Authorization", "Bearer " + tok)
                with urllib.request.urlopen(req, timeout=60) as r:
                    dest.write_bytes(r.read())
            else:
                shutil.copyfile(src.replace("file://", ""), dest)
        except (OSError, urllib.error.URLError) as e:
            print(f"  注意: {f} を取れませんでした: {e}")
            continue
        out.append((f"./{uid}/{dest.name}", f.startswith("動画")))
    return out


def ng_fusegu(text: str) -> tuple:
    """「危険」「壊れる」を伏せる。渡辺さんの一言に入っていたときの安全弁"""
    hit = [g for g in NG_GO if g in (text or "")]
    for g in hit:
        text = text.replace(g, "〔" + "＊" * len(g) + "〕")
    return text, hit


def houkoku_html(d: dict, uid: str, media: list, P: dict, kyou: dt.date) -> str:
    menu = next((m for m in BT.MENUS if m["id"] == d.get("メニューID")), None)
    name = d.get("お名前") or ""
    basho = d.get("見た場所") or (menu["表示"] if menu else "")
    shoken = d.get("所見") or ""
    shoken_bun = SHOKEN_BUN.get(shoken, "").replace("{次回}", menu["次回"] if menu else "次の点検時期")
    hitokoto, hit = ng_fusegu(d.get("一言") or "")
    if hit:
        print(f"  警告: {uid} の一言に {hit} が入っていたので伏せました。報告書を直してから送ってください")

    photos = "".join(
        (f'<figure class="photo"><video src="{C.esc(p)}" controls playsinline style="width:100%;border-radius:10px"></video><figcaption>点検時の動画</figcaption></figure>' if v
         else f'<figure class="photo"><img src="{C.esc(p)}" alt="点検時の写真" loading="lazy"><figcaption><span class="stamp">点検時</span>{C.esc(basho)}</figcaption></figure>')
        for p, v in media)

    atp = (d.get("ATP") or "").strip()
    atp_html = f'<div class="q"><div class="head"><h2>ATPの測定値</h2></div><p class="big num">{C.esc(atp)} <small style="font-size:14px">RLU</small></p><p class="note">採水した水を測定器（ルミテスター）で測った数値です。</p></div>' if atp else ""

    kishu = (d.get("機種年数") or "").strip()
    kishu_html = f"<p class='note'>機種・年数：{C.esc(kishu)}</p>" if kishu else ""

    # 料金と予約リンクは「要洗浄」のときだけ（全体構造 2章）。「様子見」は料金の目安だけ、
    # 「不要」には出さない（承認シート「不要の方には売り込みを送らない」）
    price_html = ""
    if menu and shoken == "様子見":
        mm = P["menus"][menu["施工"]]
        price_html = f"""
  <div class="q"><div class="head"><h2>ご参考：料金</h2></div>
    <p class="note">洗浄をご希望になる場合の料金は {C.esc(menu["施工"])} <b class="num">{C.yen(mm["単体"])}</b>（税込・追加の費用はありません）です。お急ぎでなければ、次の点検の目安（{C.esc(menu["次回"])}）にまた見に伺います。<a href="{C.esc(YOYAKU_URL.format(id=uid))}">予約フォーム</a></p>
  </div>"""
    elif menu and shoken == "要洗浄":
        mm = P["menus"][menu["施工"]]
        ritsu = waribiki_ritsu(P, kyou.month)
        base = int(mm["単体"])
        rows = f'<tr><th>{C.esc(menu["施工"])}</th><td><span class="v">{C.yen(base)}</span>（税込・出張費や追加の費用はありません）</td></tr>'
        for k in BT.OPTIONS.get(menu["id"], []):
            if k in P["opts"]:
                rows += f'<tr><th>{C.esc(k)}（任意）</th><td><span class="v">{C.yen(P["opts"][k]["価格"])}</span></td></tr>'
        rows += f'<tr><th>所要</th><td>{C.esc(mm.get("所要", ""))}</td></tr>'
        if ritsu > 0:
            hiki = round(base * ritsu)
            waribiki = f'<p class="note">いまの時期（{kyou.month}月）のご予約には閑散期割引 {round(ritsu*100)}% が付きます（{C.esc(menu["施工"])} {C.yen(base)} → <b class="num">{C.yen(base - hiki)}</b>）。</p>'
        else:
            waribiki = f'<p class="note">{kyou.month}月は閑散期割引の対象月ではありません（対象：1〜4月・8〜10月）。</p>'
        price_html = f"""
  <div class="q"><div class="head"><h2>クリーニングをご希望の場合</h2><p class="why">ご依頼の有無に関係なく、この報告書は点検した全員にお送りしています。</p></div>
    <table class="tbl">{rows}</table>{waribiki}
    <a class="btn lg" href="{C.esc(YOYAKU_URL.format(id=uid))}" style="margin-top:10px">予約フォームで日程を選ぶ</a>
    <p class="note" style="margin-top:6px">お申込み後8日間は無条件でキャンセルできます。</p>
  </div>"""

    body = f"""
  <div class="intro">
    <span class="eyebrow">無料点検の報告書</span>
    <h1>{C.esc(name)} 様</h1>
    <p class="lead">本日は無料点検にお時間をいただき、ありがとうございました。見た場所と、その場でお伝えした内容をまとめました。写真と数値は、点検のときにご一緒にご覧いただいたものです。</p>
    <p class="note">受付番号 <b class="num">{C.esc(uid)}</b>／点検日 {C.esc(jp_date((d.get("送信時刻") or "")[:10]))}</p>
  </div>
  <div class="q"><div class="head"><h2>見た場所</h2></div><p>{C.esc(basho)}{("（" + C.esc(menu["道具"]) + "）") if menu else ""}</p>{kishu_html}</div>
  <div class="q"><div class="head"><h2>所見</h2></div>
    <p class="big">{C.esc(shoken)}</p><p>{C.esc(shoken_bun)}</p>
    {("<div class='meiji' style='margin-top:10px'><b>点検したスタッフより</b><br>" + C.esc(hitokoto).replace(chr(10), "<br>") + "</div>") if hitokoto else ""}
  </div>
  {("<div class='q'><div class='head'><h2>写真</h2></div><div style='display:flex;flex-direction:column;gap:10px'>" + photos + "</div></div>") if photos else ""}
  {atp_html}
  {price_html}
  <div class="q"><div class="head"><h2>ご近所・ご家族も同じ点検ができます</h2></div>
    <p class="note">閑散期の空き枠にだけ伺っています。下のリンクからお申込みいただけます。</p>
    <a class="btn ghost" href="{C.esc(SHOUKAI_URL.format(id=uid))}">無料点検を申し込む（ご紹介用）</a></div>
  <p class="note" style="margin-top:14px">この報告書は、ご依頼の有無に関係なく、点検した全員にお送りしています。ご質問は {C.UNEI_TEL}（{C.UNEI}）へ。</p>
"""
    html = C.head(f"点検の報告書 {uid}｜ワンヒッター 無料点検", "無料点検の報告書", BT.BRAND, BT.BRAND_SUB, BT.css(), home="../", unei_href="../unei.html") + body + C.foot(BT.BRAND, "この報告書は、ご依頼の有無に関係なく、点検した全員にお送りしています。", unei_href="../unei.html")
    for g in NG_GO:
        assert g not in html, f"報告書に「{g}」が入っています"
    return html


def renraku_saki(subs: list) -> dict:
    """受付番号 → (メール, 電話)。報告書の宛先は申込フォームにしか無いので、そこから引く"""
    out = {}
    for s in subs:
        if s.get("form_name") == BT.FORM_MOUSHIKOMI:
            d = s.get("data") or {}
            out[anzen_id(d.get("受付番号") or "")] = ((d.get("メール") or "").strip(), (d.get("お電話番号") or "").strip())
    return out


def genba(s: dict, dist: pathlib.Path, P: dict, live: bool, kyou: dt.date, renraku: dict = None) -> str:
    d = s["data"]
    uid = anzen_id(d.get("受付番号") or s["id"])
    mail, tel = (renraku or {}).get(uid, ("", ""))   # ついで点検（G…）は申込が無いので空。現場で聞いた連絡先を人が足す
    media = shashin_toru(d, uid, dist, live)
    out = dist / "houkoku" / f"{uid}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(houkoku_html(d, uid, media, P, kyou), encoding="utf-8")
    url = HOUKOKU_URL.format(id=uid)
    menu = next((m for m in BT.MENUS if m["id"] == d.get("メニューID")), None)
    shoken = d.get("所見") or ""
    ritsu = waribiki_ritsu(P, kyou.month)
    ana = {"お名前": d.get("お名前", ""), "点検メニュー": d.get("見た場所", ""), "報告書URL": url,
           "所見の一文": SHOKEN_BUN.get(shoken, "").replace("{次回}", menu["次回"] if menu else "次の点検時期"),
           "割引率": f"{round(ritsu * 100)}%" if ritsu else "なし", "次回": menu["次回"] if menu else "次の点検時期"}
    kenmei, blocks = bunmen("報告書の送付")
    kitei = "{お名前} 様\n本日はありがとうございました。点検の報告書をお送りします。\n{報告書URL}\n所見：{所見の一文}\nこの報告書は、ご依頼の有無に関係なく、点検した全員にお送りしています。\n" + f"{C.UNEI} {C.UNEI_TANTOU}／{C.UNEI_TEL}"
    kaku_json(dist / "outbox" / f"{uid}-houkoku.json", {
        "kind": "houkoku", "to": mail or tel, "tel": tel, "channel": "mail" if mail else "sms",
        "subject": umeru(kenmei or "【ワンヒッター】本日の無料点検の報告書（{点検メニュー}）", ana),
        "body": umeru(joukenbun(blocks[0] if blocks else kitei, shoken), ana),
        "report": str(out), "media": [p for p, _ in media], "shoken": shoken,
    })
    return f"報告書 {uid} → {out.relative_to(ROOT)}（写真{len([1 for _, v in media if not v])}枚・動画{len([1 for _, v in media if v])}本）"


# ================================================================ 申込 → 受付・前日リマインド
def moushikomi(s: dict, dist: pathlib.Path) -> str:
    d = s["data"]
    uid = anzen_id(d.get("受付番号") or s["id"])
    when = (d.get("希望日時") or "").strip()          # "2026-10-15 12:30"
    hi = when[:10]
    mail = (d.get("メール") or "").strip()
    to = mail or d.get("お電話番号", "")
    ch = "mail" if mail else "sms"
    nichiji = f"{jp_date(hi)} {when[11:]}".strip()
    ana = {"お名前": d.get("お名前", ""), "受付番号": uid, "点検メニュー": d.get("点検メニュー", ""), "希望日時": nichiji, "時刻": when[11:]}
    # 受付：承認シート①。メールがあれば1つ目（メール版）、無ければ2つ目（SMS版）
    kenmei, blocks = bunmen("受付")
    kitei = ("{お名前} 様\n\n無料点検のお申込みを受け付けました。\n\n受付番号：{受付番号}\n日時：{希望日時}\n点検する場所：{点検メニュー}\n\n"
             "点検の結果、洗浄が必要と判断した場合は、訪問時に清掃サービスのご案内をすることがあります（ご案内は1回だけ）。\n"
             f"ご都合が変わったときは {C.UNEI_TEL} へお電話ください。\n\n{C.UNEI}\n{C.UNEI_ADDR}\n電話 {C.UNEI_TEL}")
    body = blocks[0] if blocks else kitei
    if ch == "sms" and len(blocks) >= 2:
        body = blocks[1]
    kaku_json(dist / "outbox" / f"{uid}-uketsuke.json", {
        "kind": "uketsuke", "to": to, "channel": ch,
        "subject": umeru(kenmei or "【ワンヒッター】無料点検のお申込みを受け付けました（受付番号 {受付番号}）", ana),
        "body": umeru(body, ana),
    })
    # 前日リマインド：承認シート②（前日18時・SMS）。送る側は send_on / send_at を見て出す
    try:
        zenjitsu = (dt.date.fromisoformat(hi) - dt.timedelta(days=1)).isoformat()
    except ValueError:
        zenjitsu = ""
    _, blocks = bunmen("前日リマインド")
    kitei = "【ワンヒッター】明日{時刻}に無料点検で伺います（{点検メニュー}・約10〜20分）。変更は" + C.UNEI_TEL + "へ。"
    kaku_json(dist / "outbox" / f"{uid}-remind.json", {
        "kind": "remind", "send_on": zenjitsu, "send_at": "18:00", "to": to, "channel": ch,
        "subject": "【ワンヒッター】明日の無料点検のご確認", "body": umeru(blocks[0] if blocks else kitei, ana),
    })
    return f"受付 {uid} → outbox/{uid}-uketsuke.json, {uid}-remind.json（send_on {zenjitsu}）"


# ================================================================ main
def main() -> None:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--sample", action="store_true", help="内蔵サンプルで動かす（既定）")
    g.add_argument("--live", action="store_true", help="Netlify API から読む（読むだけ）")
    ap.add_argument("--redo", action="store_true", help="処理済みも作り直す")
    ap.add_argument("--dist", default=str(DIST))
    ap.add_argument("--online-fonts", action="store_true", help="PDF化のときWebフォントを取りに行く")
    a = ap.parse_args()

    subs, mode, oshirase = yomu("live" if a.live else "sample")
    if oshirase:
        print("お知らせ:", oshirase)
    dist = pathlib.Path(a.dist)
    dist.mkdir(parents=True, exist_ok=True)
    proc_path = dist / "processed.json"
    proc = json.loads(proc_path.read_text(encoding="utf-8")) if proc_path.exists() else {"ids": {}}
    P = C.prices()
    kyou = dt.datetime.now(JST).date()

    print(f"モード: {mode}／届いているもの {len(subs)}件／処理済み {len(proc['ids'])}件")
    kekka, tobashi, shippai = [], 0, []
    renraku = renraku_saki(subs)
    for s in sorted(subs, key=lambda x: x.get("created_at", "")):
        if not a.redo and s["id"] in proc["ids"]:
            tobashi += 1
            continue
        fn = s.get("form_name", "")
        try:
            if fn == BT.FORM_KEIYAKU:
                msg = keiyaku(s, dist, a.online_fonts)
            elif fn == BT.FORM_GENBA:
                msg = genba(s, dist, P, mode == "live", kyou, renraku)
            elif fn == BT.FORM_MOUSHIKOMI:
                msg = moushikomi(s, dist)
            else:
                msg = f"不明なフォーム {fn} は飛ばしました"
        except Exception as e:  # 1件の失敗で他を止めない。失敗したものは処理済みにしない
            shippai.append(f"{fn} {s['id']}: {e}")
            continue
        proc["ids"][s["id"]] = {"form": fn, "done": dt.datetime.now(JST).isoformat(timespec="minutes")}
        kekka.append(msg)

    proc_path.write_text(json.dumps(proc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n--- 作ったもの {len(kekka)}件（飛ばした {tobashi}件） ---")
    for m in kekka:
        print(" ", m)
    if shippai:
        print(f"--- 失敗 {len(shippai)}件 ---")
        for m in shippai:
            print(" ", m)
    print(f"\n★ここでは何も送っていません。送付物は {dist.relative_to(ROOT) if dist.is_relative_to(ROOT) else dist}/outbox/ にあります。")


if __name__ == "__main__":
    main()
