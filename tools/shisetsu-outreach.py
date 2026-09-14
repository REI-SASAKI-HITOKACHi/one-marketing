#!/usr/bin/env python3
"""施設カードの設置依頼（第1波〜）を、問い合わせフォームとメールで出す。送信のたびに売上スプシへ記録する。

【決まり】（docs/節目チャネル-全体構造.md 3章・9章、オーナー決定 2026-09-13）
  - 文面は docs/節目チャネル-文面-承認シート.md（オーナー承認済みの版）から作る。ここで文を足さない
  - 送るのは公開のフォームとアドレスだけ。「営業お断り」明記のフォームは送らない。断られた施設は永久に送らない
  - 50件ずつ。1件ずつ送信ログ（施設カード_送信ログ）に書き、進捗タブのステージ・接触方法・回数・日付を更新する
  - --send を付けない限り何も送らない（フォームは入力まで行い、スクリーンショットを撮って止まる）
  - 送るのは 9:00〜17:00 JST だけ（オーナー決定 2026-09-14：「返信を除くすべてのファーストアプローチは9:00-17:00に実行」）。時間外は --send を拒む

【入力】
  data/facilities-2026-09-clean.json     施設（Places）
  data/facilities-2026-09-contacts.json  連絡先（フォームURL・メール・営業お断り）
  売上スプシ「施設カード_進捗」          優先度・ステージ（未接触だけが対象）

使い方:
  python3 tools/shisetsu-outreach.py plan --wave 1 --n 50 --exclude 産婦人科・産院   # 送る50件を選んで表示（送らない）
  python3 tools/shisetsu-outreach.py form --wave 1 --n 50            # フォーム：入力してスクショ（送らない）
  python3 tools/shisetsu-outreach.py form --wave 1 --n 50 --send     # フォーム：送信してログ
  python3 tools/shisetsu-outreach.py mail --wave 1 --n 50            # メール：本文を dist/outreach/ に書き出す（送らない）
  python3 tools/shisetsu-outreach.py mail --wave 1 --n 50 --send     # メール：Gmail API（onehitter.her@gmail.com）で送信してログ。1日50件まで
"""
import argparse
import asyncio
import os
import datetime as dt
import json
import pathlib
import re
import sys
import urllib.parse

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import media_common as C  # noqa: E402
import sheets_client as sc  # noqa: E402
import gmail_send as G  # noqa: E402

ROOT = C.ROOT
# 施設と連絡先は複数のファイルに分かれている（最初の江戸川区・浦安市＋9/14 に足した都内の区・市川市）
FAC_FILES = [ROOT / "data" / "facilities-2026-09-clean.json", ROOT / "data" / "facilities-2026-09-add.json"]
CON_FILES = [ROOT / "data" / "facilities-2026-09-contacts.json", ROOT / "data" / "facilities-2026-09-add-contacts.json"]
OUT = ROOT / "dist" / "outreach"
SS = "1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64"
TAB_P = "施設カード_進捗"
TAB_L = "施設カード_送信ログ"
HEAD_ROW = 13  # 進捗タブのヘッダ行（1始まり）
JST = dt.timezone(dt.timedelta(hours=9))
SETTI_URL = f"{C.DOKUHON_URL}/setti/"
SENDER = "ワンヒッター株式会社 佐々木"
ADDR = "〒134-0081 東京都江戸川区北葛西5-14-11 クオーディア西葛西503"  # CMO 指定（20260913-07-cmo）
REPLY_TO = G.REPLY_TO  # フォームに書く返信先メールもこれ（メールの Reply-To と同じ受信箱に集める）
MAIL_PER_DAY = 50
SEND_HOURS = (9, 17)  # JST。ファーストアプローチはこの間だけ（オーナー決定 2026-09-14）


def check_send_window() -> None:
    now = dt.datetime.now(JST)
    if not (SEND_HOURS[0] <= now.hour < SEND_HOURS[1]):
        sys.exit(f"送信は {SEND_HOURS[0]}:00〜{SEND_HOURS[1]}:00 JST だけ（いま {now:%H:%M}）。オーナー決定 2026-09-14")

# ---------------- 文面（承認シート③＝フォーム用の短い版。①②はメール用）
PLACE = {"産婦人科・産院": "待合か受付", "小児科": "待合か受付", "ベビー用品店": "レジ横か掲示板", "子育て支援（公的）": "受付か掲示板",
         "動物病院": "待合か受付", "ペットショップ": "レジ横か掲示板", "トリミング": "レジ横か待合"}  # 置き場所は種別で（オーナー指摘 9/14：ベビー用品店に待合は無い）


def yomihon(kind: str) -> dict:
    place = PLACE.get(kind, "受付かレジ横")
    if kind in ("産婦人科・産院", "小児科", "ベビー用品店", "子育て支援（公的）"):
        return {"who": "赤ちゃんを迎えるご家庭", "title": "赤ちゃんが来る前に知っておきたい、家の中の見えない汚れ", "url": f"{C.DOKUHON_URL}/akachan/",
                "min": "10分", "where": "エアコンや浴室", "src": "現場の写真と東京都の資料", "place": place, "menu": "エアコン1台＋浴室 25,960円"}
    return {"who": "犬や猫を迎えるご家庭", "title": "新しい家族と暮らす家の、見えない汚れ", "url": f"{C.DOKUHON_URL}/pet/",
            "min": "8分", "where": "エアコンや換気扇", "src": "現場の写真と環境省・東京都の資料", "place": place, "menu": "エアコン1台＋換気扇 25,960円"}


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
            f"不要な場合は、このままご放念ください。\n"
            f"\n"
            f"ワンヒッター株式会社 佐々木 嶺\n"
            f"{ADDR}\n"
            f"電話 {C.UNEI_TEL}")


def atena(name: str) -> str:
    """宛名用の施設名。Places の名前に付く説明（［犬/ねこ/エキゾ対応動物病院］、|内視鏡 胃カメラ…）を落とし、半角カナを全角にする"""
    import unicodedata
    n = unicodedata.normalize("NFKC", name)
    m = re.match(r"[『「](.+?)[』」]", n)
    if m:
        n = m.group(1)
    n = re.sub(r"[\[【（(].*?[\]】）)]", " ", n)
    n = re.split(r"[|｜]", n)[0]
    n = re.sub(r"\s+-[^-]+-\s*$", "", n)
    return re.sub(r"\s+", " ", n).strip()


def mail_text(f: dict, kind: str) -> tuple:
    y = yomihon(kind)
    _, h = houshuu(f["施設名"], kind)
    # 「知っておいていただきたい」相手の呼び方は種別で変える（トリミングサロンに「患者さま」は合わない。9/14 オーナー提示前に修正）
    kikan = {"産婦人科・産院": "貴院にお越しのご家庭", "小児科": "貴院にお越しのご家庭", "動物病院": "ご来院の飼い主さま"}.get(kind, "お客さま")
    subj = ("赤ちゃんを迎えるご家庭向けの読み物を、待合に置いていただけませんか（江戸川区のハウスクリーニング店）" if y["who"].startswith("赤ちゃん")
            else "犬猫を迎えるご家庭向けの読み物を、レジ横に置いていただけませんか（江戸川区のハウスクリーニング店）")
    body = f"""{atena(f['施設名'])} ご担当者さま

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

今後のご案内が不要でしたら、このメールにその旨ご返信ください。以後お送りしません。

ワンヒッター株式会社
佐々木 嶺
{ADDR}
電話 {C.UNEI_TEL}
{C.UNEI_SITE}"""
    return subj, body


# ---------------- Sheets API（再試行つき。9/14 08:2x に他スレッドと読み取り枠を共有して 429 が出たため。sc.call は失敗すると sys.exit するので使わない）
import time
import urllib.error
import urllib.request

FALLBACK = OUT / "sheets-fallback.jsonl"
_TOK = {"v": ""}  # 何度やっても書けなかった記録の控え（送った事実を失わないため）


def scall(tok: str, path: str, method: str = "GET", payload=None, query=None, tries: int = 6):
    tok = _TOK["v"] or tok
    url = sc.API + path + (("?" + urllib.parse.urlencode(query)) if query else "")
    data = json.dumps(payload).encode() if payload is not None else None
    for i in range(tries):
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", "Bearer " + tok)
        if data:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and i < tries - 1:
                time.sleep(15 * (i + 1))
                continue
            if e.code == 401 and i < tries - 1:  # トークン失効（1時間）。取り直して続ける
                tok = sc.access_token(sc.load_credentials())
                _TOK["v"] = tok
                continue
            raise RuntimeError(f"Sheets API {e.code}: {e.read().decode('utf-8', 'replace')[:200]}")
        except (urllib.error.URLError, TimeoutError) as e:
            if i < tries - 1:
                time.sleep(15 * (i + 1))
                continue
            raise


def safe_write(tok, what: str, fn, *args) -> None:
    """スプシへの書き込み。再試行しても駄目なら控え（FALLBACK）に残して続行する"""
    try:
        fn(tok, *args)
    except Exception as e:
        OUT.mkdir(parents=True, exist_ok=True)
        with FALLBACK.open("a", encoding="utf-8") as fp:
            fp.write(json.dumps({"時刻": dt.datetime.now(JST).isoformat(timespec="minutes"), "何": what, "引数": [a if isinstance(a, (str, int)) else a.get("施設名") for a in args], "error": str(e)[:200]}, ensure_ascii=False) + "\n")
        print("  [スプシに書けなかった→控えに記録]", what, str(e)[:80])


_PROG_CACHE = {}  # 進捗タブ：施設名→(行番号, 行)。送信中は行が動かないので最初に1回だけ読む


def progress_rows(tok, refresh: bool = False):
    if refresh or not _PROG_CACHE:
        vals = scall(tok, f"/{SS}/values/{urllib.parse.quote(TAB_P + '!A' + str(HEAD_ROW) + ':AM1000')}").get("values", [])
        head = vals[0]
        col = {h: i for i, h in enumerate(head)}
        _PROG_CACHE.clear()
        _PROG_CACHE["col"] = col
        _PROG_CACHE["rows"] = {}
        for i, r in enumerate(vals[1:], start=HEAD_ROW + 1):
            r = r + [""] * (len(head) - len(r))
            _PROG_CACHE["rows"].setdefault(r[col["施設名"]], (i, r))
    return _PROG_CACHE["col"], _PROG_CACHE["rows"]


# ---------------- 対象の選定
def load() -> list:
    fac, con = {}, {}
    for q in FAC_FILES:
        if q.exists():
            fac.update({f["id"]: f for f in json.loads(q.read_text(encoding="utf-8"))})
    for q in CON_FILES:
        if q.exists():
            con.update({c["id"]: c for c in json.loads(q.read_text(encoding="utf-8"))})
    by_name = {}
    for f in fac.values():
        by_name.setdefault(f["施設名"], f)
    tok = sc.access_token(sc.load_credentials())
    col, prows = progress_rows(tok, refresh=True)
    rows = []
    for name, (_, r) in prows.items():
        f = by_name.get(name)
        if not f:
            continue
        c = con.get(f["id"], {})
        rows.append({**f, "No": r[col["No"]], "優先度": r[col["優先度"]], "ステージ": r[col["ステージ"]], "接触回数": r[col["接触回数"]] or "0",
                     "次回アクション": r[col["次回アクション"]], "row": None, "contact": c})
    return rows


FREE_MAIL = ("gmail.com", "yahoo.co.jp", "yahoo.com", "icloud.com", "outlook.com", "hotmail.com", "ocn.ne.jp", "nifty.com", "so-net.ne.jp", "biglobe.ne.jp", "au.com", "docomo.ne.jp", "ezweb.ne.jp", "me.com", "i.softbank.jp")
PLACEHOLDER_LOCAL = ("example", "sample", "test", "yamada", "xxx", "hoge", "yourname", "mail", "abc", "user", "taro")
PLACEHOLDER_DOMAIN = ("example.com", "example.jp", "abc.ne.jp", "mail.com", "sample.com", "sample.jp", "xxx.jp", "hoge.jp", "yourdomain.com", "email.com")
DIRECTORY_HOSTS = ("mizumono.com",)  # 店舗一覧サイト。そこのフォームやメールは施設のものではない（2026-09-14 マッドマン葛西店で発見）
EMAIL_SKIP = {"info-eigo@babypark.jp": "チェーン本部の英語教室窓口で、新浦安教室の窓口ではない"}  # 個別に除く（理由つき）
GENERIC_TOK = ("com", "info", "shop", "animal", "clinic", "hospital", "salon", "tokyo", "japan", "mail", "pet", "dog", "cat")
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$")
BRANCH = {"葛西": "kasai", "江戸川": "edogawa", "小岩": "koiwa", "平井": "hirai", "浦安": "urayasu", "船堀": "funabori", "瑞江": "mizue", "篠崎": "shinozaki"}


def email_of(c: dict, name: str = "", site: str = "") -> str:
    """contacts.json の emails は {'address','kind'} の配列（文字列のこともある）。
    2026-09-14 巡回結果の点検で見つけた誤りを除く：雛形のアドレス（example@…）、タグの混入（…</p）、他店のアドレス（支店一覧の中の別支店）、
    サイトのドメインと無関係な独自ドメイン（テンプレートの残りとみられる）。フリーメールは店のものとして受け入れる。"""
    es = c.get("emails") or []
    addrs = []
    for e in es:
        a = (e["address"] if isinstance(e, dict) else e) or ""
        a = re.split(r"[<>\s\"'()]", a)[0].strip().lower()
        if not EMAIL_RE.match(a):
            continue
        local, dom = a.split("@")
        if local in PLACEHOLDER_LOCAL or dom in PLACEHOLDER_DOMAIN or a in EMAIL_SKIP:
            continue
        addrs.append(a)
    host = urllib.parse.urlparse(site or c.get("サイト") or "").netloc.lower().replace("www.", "")
    if any(host.endswith(h) for h in DIRECTORY_HOSTS):
        return ""
    def plausible(a: str) -> bool:
        dom = a.split("@")[1]
        if dom in FREE_MAIL or not host:
            return True
        toks = {t for t in re.split(r"[.-]", dom) if len(t) >= 4 and t not in GENERIC_TOK}
        return any(t in host for t in toks)
    addrs = [a for a in addrs if plausible(a)]
    if not addrs:
        return ""
    # 支店一覧（chiba@… kasai@… yokohama@…）：施設名の地名に合う局部を選ぶ。合うものが無ければ汎用アドレス
    for kanji, roma in BRANCH.items():
        if kanji in (name or ""):
            hit = [a for a in addrs if roma in a.split("@")[0]]
            if hit:
                return hit[0]
    gen = [a for a in addrs if a.startswith(("info@", "contact@", "mail@", "office@", "support@", "inquiry@"))]
    return (gen or addrs)[0]


def pick(rows: list, n: int, how: str, exclude: tuple = ()) -> list:
    """候補を上から n 件（n<=0 なら全部）。送れた数で止めるのは呼び出し側（オーナー決定 9/14：「50件送れたら停止して改善」）"""
    out = []
    used = set()  # 同じフォーム（同一法人の複数店）には1回だけ送る
    for r in rows:
        if r["ステージ"] != "未接触" or r["優先度"] == "C" or r["種別"] in exclude:
            continue
        if how == "form" and r["次回アクション"].startswith("手動"):
            continue  # 前回フォームが使えなかった（URL誤り・画像認証）。人に回してあるので機械では再挑戦しない
        if r["種別"] == "ペットショップ" and NOT_DOGCAT_RE.search(r["施設名"]):
            continue
        c = r["contact"]
        if c.get("no_sales"):
            continue
        if how == "form" and not c.get("contact_form_url"):
            continue
        if how == "form" and any(urllib.parse.urlparse(c.get("contact_form_url") or "").netloc.lower().replace("www.", "").endswith(h) for h in DIRECTORY_HOSTS):
            continue
        if how == "mail" and not email_of(c, r["施設名"], r.get("サイト", "")):
            continue
        key = c.get("contact_form_url") if how == "form" else email_of(c, r["施設名"], r.get("サイト", ""))
        if key in used:
            continue
        used.add(key)
        out.append(r)
        if n > 0 and len(out) >= n:
            break
    return out


# ---------------- ログ
def log_send(tok, wave: int, f: dict, how: str, dest: str, kata: str, result: str, note: str = "") -> None:
    now = dt.datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    # Google フォーム経由（認証も API 枠も不要。オーナー指示 2026-09-14）。フォームの設定が無い間は Sheets API に書く
    cfg = pathlib.Path(os.path.expanduser("~/.config/one-hitter/sendlog-form.json"))
    if cfg.exists():
        import importlib.util
        spec = importlib.util.spec_from_file_location("mf", pathlib.Path(__file__).with_name("make-sendlog-form.py"))
        mf = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mf)
        if mf.post({"日時": now, "波": wave, "施設No": f["No"], "施設名": f["施設名"], "種別": f["種別"], "手段": how, "宛先／フォームURL": dest,
                    "文面の型": kata, "送信者": SENDER, "結果": result, "備考": note}):
            return
        raise RuntimeError("フォームへの投稿に失敗")
    scall(tok, f"/{SS}/values/{urllib.parse.quote(TAB_L + '!A1')}:append", method="POST",
            query={"valueInputOption": "USER_ENTERED", "insertDataOption": "INSERT_ROWS"},
            payload={"values": [[now, wave, f["No"], f["施設名"], f["種別"], how, dest, kata, SENDER, result, "", "", note]]})


def mails_today(tok) -> int:
    """送信ログのうち、今日・手段=メール・結果が「送信」で始まる行の数（1日50件の上限に使う）"""
    today = dt.datetime.now(JST).strftime("%Y-%m-%d")
    vals = scall(tok, f"/{SS}/values/{urllib.parse.quote(TAB_L + '!A2:M2000')}").get("values", [])
    return sum(1 for r in vals if len(r) > 9 and r[0].startswith(today) and r[5] == "メール" and str(r[9]).startswith("送信"))


def update_stage(tok, f: dict, how: str) -> None:
    """進捗タブ：ステージ→接触済、接触方法、回数+1、初回/最終接触日、次回アクション（7日後の再送）"""
    col, prows = progress_rows(tok)
    if f["施設名"] in prows:
        i, r = prows[f["施設名"]]
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
            r[ci] = str(v)  # キャッシュも更新（同じ施設に2回目があれば回数が進む）
        scall(tok, f"/{SS}/values:batchUpdate", method="POST", payload={"valueInputOption": "USER_ENTERED", "data": data})
        return


def mark_manual(tok, f: dict, reason: str) -> None:
    """フォームが機械で送れなかった施設：進捗タブの次回アクションに「手動（理由）」と書き、以後 pick() が飛ばす。ステージは未接触のまま"""
    col, prows = progress_rows(tok)
    if f["施設名"] in prows:
        i, r = prows[f["施設名"]]
        who = "ブラウザ担当" if "認証" in reason or "CAPTCHA" in reason else "メール／電話・訪問"
        data = [{"range": f"{TAB_P}!{colletter(col['次回アクション'])}{i}", "values": [[f"手動（{reason}）→{who}"]]},
                {"range": f"{TAB_P}!{colletter(col['当社担当'])}{i}", "values": [["web-inflow"]]}]
        scall(tok, f"/{SS}/values:batchUpdate", method="POST", payload={"valueInputOption": "USER_ENTERED", "data": data})
        return


def colletter(i: int) -> str:
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


# ---------------- フォーム送信（Playwright）
# 送ってはいけないフォーム（docs/節目チャネル-全体構造.md 9章）。2026-09-13 の入力テストで「患者様以外はご遠慮」「業者様からのお問い合わせはご遠慮」を見落としたので広げた
NO_SALES_RE = re.compile(r"(営業|セールス|勧誘|業者|取引|売り込み)[^。\n]{0,20}(お断り|ご遠慮|禁止|お控え|ご容赦)|患者(様|さま|さん)?(専用|以外|のみ)|患者様以外|営業目的[^。\n]{0,10}(禁止|お断り|ご遠慮)")

FIELD_HINTS = {  # 上から順に判定（件名・会社名は「名」より先に見る）
    "subject": ["件名", "題名", "subject", "用件", "タイトル"],
    "company": ["会社", "法人", "団体", "貴社", "店名", "屋号", "company", "organization", "corp"],
    "zip": ["郵便番号", "zip", "postal", "〒"],
    "addr": ["住所", "所在地", "address"],
    "email2": ["確認のため", "メールアドレス（確認", "メール確認", "email_confirm", "email2", "mail2", "confirm"],
    "kana": ["フリガナ", "ふりがな", "カナ", "kana", "furigana"],
    "name": ["お名前", "氏名", "名前", "担当者", "name", "姓", "名"],
    "email": ["メール", "mail", "e-mail"],
    "tel": ["電話", "tel", "phone"],
    "body": ["お問い合わせ内容", "お問合せ内容", "内容", "本文", "メッセージ", "message", "inquiry", "comment", "detail", "ご質問", "ご要望"],
}
CAPTCHA_RE = re.compile(r"画像に表示|画像の文字|認証コード|送信認証|captcha|スパム対策|計算|の答え", re.I)
VALUES = {"company": "ワンヒッター株式会社", "name": "佐々木", "kana": "ササキ", "tel": C.UNEI_TEL, "zip": "134-0081", "addr": ADDR.split(" ", 1)[1]}


def hint_of(label: str) -> str:
    l = label.lower()
    for key, words in FIELD_HINTS.items():
        if any(w.lower() in l for w in words):
            return key
    return ""


CTX_JS = """e=>{
  const t=x=>(x&&x.innerText?x.innerText:'').replace(/\\s+/g,' ').trim();
  const lab=e.labels&&e.labels[0]?t(e.labels[0]):'';
  let before='',after='';
  let n=e.previousSibling; while(n&&!before){ before=(n.nodeType===3?n.textContent:t(n)).trim(); n=n.previousSibling; }
  n=e.nextSibling; while(n&&!after){ after=(n.nodeType===3?n.textContent:t(n)).trim(); n=n.nextSibling; }
  const p=e.closest('tr,li,p,dd,div');
  let head='';
  if(p){ let q=p.previousElementSibling; while(q&&!head){ head=t(q); q=q.previousElementSibling; } }
  return {lab:lab,before:before.slice(-20),after:after.slice(0,20),cont:p?t(p).slice(0,60):'',head:head.slice(0,40)};
}"""
NOT_DOGCAT_RE = re.compile(r"熱帯魚|アクア|サンマリン|ディスカス|金魚|メダカ|水族")  # ペットショップのうち観賞魚の店。犬猫の読本は合わないので送らない（2026-09-14 東京サンマリンで気づいた）


CONTACT_LINK_RE = re.compile(r"(問い?合わ?せ|問合せ|お問合わせ|contact|inquiry|mail ?form|メールフォーム)", re.I)


async def find_form_link(pg) -> str:
    """いまのページに本文欄が無いとき、同じサイト内の問い合わせページへの link を探す（2026-09-14 第1波：候補93件中46件がフォームでないURLだった）"""
    try:
        links = await pg.evaluate("""() => [...document.querySelectorAll('a[href]')].map(a => ({h: a.href, t: (a.innerText||'') + ' ' + (a.getAttribute('aria-label')||'') + ' ' + a.href}))""")
    except Exception:
        return ""
    here = pg.url.split("/")[2] if "//" in pg.url else ""
    best = ""
    for a in links:
        h, t = a.get("h", ""), a.get("t", "")
        if not h.startswith("http") or "//" not in h:
            continue
        base = h.split("#")[0]
        if h.split("/")[2] != here or base.rstrip("/") == pg.url.split("#")[0].rstrip("/"):
            continue  # 同じページ内のアンカー（#top 等）は辿らない
        if h.lower().endswith((".pdf", ".jpg", ".png", ".zip")) or "tel:" in h or "mailto:" in h:
            continue
        if CONTACT_LINK_RE.search(t):
            # 「フォーム」と明示されているものを優先
            if re.search(r"form|フォーム", base, re.I):
                return base
            best = best or base
    return best


# プルダウンで選ぶ値。上から順に探し、無ければ「選択してください」以外の最初の選択肢
OPTION_PREF = ("その他", "ご提案", "ご意見", "お問い合わせ", "お問合せ", "問い合わせ", "一般", "法人")
OPTION_NG = re.compile(r"選択|choose|select|指定|--|^$|お選び")


async def pick_option(el) -> None:
    try:
        opts = await el.evaluate("""e => [...e.options].map((o,i) => ({i: i, t: (o.text||'').trim(), v: o.value}))""")
    except Exception:
        return
    cand = [o for o in opts if o["v"] not in ("", None) and not OPTION_NG.search(o["t"] or "")]
    if not cand:
        return
    pick = None
    for w in OPTION_PREF:
        for o in cand:
            if w in o["t"]:
                pick = o
                break
        if pick:
            break
    pick = pick or cand[0]
    try:
        await el.select_option(value=pick["v"])
    except Exception:
        try:
            await el.select_option(index=pick["i"])
        except Exception:
            pass


async def fill_form(pg, url: str, text: str, email_from: str, subject: str, hop: int = 0) -> dict:
    if hop == 0:
        await pg.goto(url, timeout=30000, wait_until="domcontentloaded")
        await pg.wait_for_timeout(1500)
    html = await pg.content()
    if NO_SALES_RE.search(re.sub(r"<[^>]+>", " ", html)):
        return {"ok": False, "reason": "営業お断り・患者専用の記載"}
    # 画像認証・reCAPTCHA v2（チェック式）は機械では通せない → 人（ブラウザ担当）に回す。v3（invisible）はそのまま送れる
    if re.search(r'recaptcha/api2/anchor(?![^"]*size=invisible)', html) or re.search(r'hcaptcha\.com', html):
        return {"ok": False, "reason": "reCAPTCHA（手動送信へ）"}
    tel = C.UNEI_TEL.split("-")
    zipc = VALUES["zip"].split("-")
    parts = {"tel": tel, "zip": zipc}
    part_i = {"tel": 0, "zip": 0}
    filled = {}
    for el in await pg.query_selector_all("input:not([type=hidden]):not([type=submit]):not([type=button]):not([type=checkbox]):not([type=radio]):not([type=file]), textarea, select"):  # select も埋める（2026-09-14）
        try:
            tag = await el.evaluate("e=>e.tagName.toLowerCase()")
            if tag == "select":
                # 2026-09-14：プルダウン（店舗選択・お問い合わせ種別 等）を空のままにしていたため必須エラーで送れていなかった
                await pick_option(el)
                continue
            typ = (await el.get_attribute("type") or "").lower()
            attrs = " ".join([(await el.get_attribute(x) or "") for x in ("name", "id", "placeholder", "aria-label")])
            c = await el.evaluate(CTX_JS)
            near = f"{c['lab']} {c['before']} {c['after']} {attrs}"          # 入力欄に近い文字（姓・名・確認用 の判定）
            ctx = f"{near} {c['cont']} {c['head']}"                         # 少し広い範囲（お名前・メールアドレス 等の見出し）
            key = hint_of(near) or hint_of(ctx)
            if tag == "textarea":
                key = "body"
            if CAPTCHA_RE.search(ctx) and tag != "textarea":
                return {"ok": False, "reason": "画像認証あり（手動送信へ）"}
            if typ == "email" or key == "email":
                key = "email2" if re.search(r"確認|confirm|再入力|もう一度|2", near) else "email"
            if typ == "tel":
                key = "tel"
            if key == "name":
                # 姓・名が分かれている欄。「名」は お名前・会社名・件名 などにも含まれるので、入力欄の直近の文字だけで判定
                if re.search(r"(^|\s)姓|苗字|last|sei\b", near, re.I):
                    key = "sei"
                elif re.search(r"(^|\s)名(\s|$)|first|\bmei\b", near, re.I) and not re.search(r"お名前|氏名|名前", near):
                    key = "mei"
            if key == "kana" and re.search(r"(^|\s)セイ|(^|\s)せい", near):
                key = "kana_sei"
            elif key == "kana" and re.search(r"(^|\s)メイ|(^|\s)めい", near):
                key = "kana_mei"
            if not key:
                continue
            if key in ("tel", "zip"):
                # 3分割（080-8043-8259）・2分割（134-0081）の欄は順に埋める
                ml = await el.get_attribute("maxlength")
                if part_i[key] < len(parts[key]) and (ml and int(ml) <= 5 or re.search(r"[123]$", attrs.split()[0] if attrs.split() else "") or part_i[key] > 0):
                    await el.fill(parts[key][part_i[key]])
                    part_i[key] += 1
                    filled[key] = True
                    continue
            if key in filled:
                continue
            val = {"email": email_from, "email2": email_from, "subject": subject, "body": text, "sei": "佐々木", "mei": "嶺",
                   "kana_sei": "ササキ", "kana_mei": "レイ"}.get(key) or VALUES.get(key)
            if val:
                await el.fill(val)
                filled[key] = True
        except Exception:
            continue
    # 用件のラジオ：「その他」があればそれ、無ければ最後の選択肢
    radios = await pg.query_selector_all("input[type=radio]")
    groups = {}
    for rd in radios:
        try:
            groups.setdefault(await rd.get_attribute("name") or "", []).append(rd)
        except Exception:
            pass
    for name_, rds in groups.items():
        picked = None
        for rd in rds:
            lab = await rd.evaluate("e=>(e.labels&&e.labels[0]?e.labels[0].innerText:'')+' '+(e.parentElement?e.parentElement.innerText.slice(0,30):'')")
            if "その他" in lab:
                picked = rd
        try:
            await (picked or rds[-1]).check()
        except Exception:
            pass
    # 同意チェック
    for cb in await pg.query_selector_all("input[type=checkbox]"):
        try:
            lab = await cb.evaluate("e=>(e.labels&&e.labels[0]?e.labels[0].innerText:'')+' '+(e.parentElement?e.parentElement.innerText.slice(0,80):'')+' '+(e.closest('tr,li,p,div')?e.closest('tr,li,p,div').innerText.slice(0,80):'')")
            if re.search(r"同意|確認|プライバシー|個人情報|規約", lab):
                await cb.check(force=True)
        except Exception:
            pass
    if "body" not in filled and hop < 2:
        nxt = await find_form_link(pg)
        if nxt:
            try:
                await pg.goto(nxt, timeout=30000, wait_until="domcontentloaded")
                await pg.wait_for_timeout(1500)
                r = await fill_form(pg, nxt, text, email_from, subject, hop + 1)
                r["moved_to"] = nxt
                return r
            except Exception:
                pass
    return {"ok": "body" in filled, "filled": sorted(filled), "reason": "" if "body" in filled else "本文欄が見つからない"}


async def click(el, pg) -> None:
    """普通のクリックが通らないフォーム（要素が隠れている・別要素に覆われている）でも押せるように。
    2026-09-14 第1波：ElementHandle.click の 30 秒待ちで 8 件落ちた"""
    try:
        await el.click(timeout=8000)
        return
    except Exception:
        pass
    try:
        await el.evaluate("e => e.click()")
    except Exception:
        await el.evaluate("e => { const f = e.form || e.closest('form'); if (f) f.submit(); }")


# 完了と認めてよい文（送信後にだけ現れる言い回しに限る）。
# 2026-09-14：以前は「受付」「ありがとうござい」だけで完了としていたため、「最終受付 17:00」のような
# 営業時間の表記にも反応し、42件中27件を送れていないのに「送信」と記録した。
DONE_RE = re.compile(r"送信(が)?完了|送信を?完了|送信(いた)?しました|送信されました|受け付けました|受付けました|受付が完了|"
                     r"お問い?合わ?せ(を)?(ありがとうございました|受け付け)|ご連絡ありがとうございました|"
                     r"内容を確認の上|折り返しご連絡|thank you for|successfully sent|message sent")
FAIL_RE = re.compile(r"失敗しました|エラーが発生|記入もれ|入力(して|に)(ください|エラー)|必須項目|必須です|"
                     r"正しく入力|選択してください|もう一度お試し|error occurred")
# 「確認画面」から先に進むためのボタン（この語のときだけ2手目を押す）
SEND_BTN = "input[type=submit][value*='送信'], input[type=button][value*='送信'], button[type=submit]:has-text('送信'), button:has-text('送信する'), button:has-text('送信'), input[value='上記の内容で送信する']"


async def why_stuck(pg) -> str:
    """送れなかったとき、画面に出ている理由（必須項目の警告・ブラウザの検証メッセージ）を短く拾う。
    次の改善で何を直せばよいかを送信ログに残すため（2026-09-14）"""
    try:
        msgs = await pg.evaluate("""() => {
          const out = [];
          for (const e of document.querySelectorAll('input,select,textarea')) {
            if (e.willValidate && !e.checkValidity()) {
              const lab = (e.labels && e.labels[0] ? e.labels[0].innerText : '') || e.name || e.id || e.type;
              out.push((lab || '').replace(/\s+/g,' ').trim().slice(0,20) + ':' + (e.validationMessage||'').slice(0,20));
            }
          }
          for (const e of document.querySelectorAll('.error,.err,.is-error,[class*="error"],[class*="alert"]')) {
            const t = (e.innerText||'').replace(/\s+/g,' ').trim();
            if (t && t.length < 60) out.push(t);
          }
          return [...new Set(out)].slice(0, 4);
        }""")
        return "／".join(msgs)[:100]
    except Exception:
        return ""


async def submit(pg, wave: int, f: dict) -> dict:
    """フォームを送り、完了画面を見届ける。確認画面をまたぐ場合は3手まで進む。
    戻り値 state: done（完了を確認）／ng（完了を確認できない）"""
    seen = []
    for step in range(3):
        before_url = pg.url
        btn = await pg.query_selector("input[type=submit], button[type=submit], button:has-text('送信'), input[value*='送信'], "
                                      "input[value*='確認'], button:has-text('確認'), button:has-text('進む'), input[value*='次へ']")
        if not btn:
            await pg.screenshot(path=str(OUT / f"w{wave}-{f['No']}-sent.png"), full_page=True)
            return {"state": "ng", "reason": "送信ボタン不明" if step == 0 else "完了画面を確認できない", "proof": ""}
        await click(btn, pg)
        await pg.wait_for_timeout(3000)
        try:
            await pg.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception:
            pass
        body = re.sub(r"<[^>]+>", " ", await pg.content())
        m = DONE_RE.search(body)
        # 完了の文があっても、入力欄が残っていれば「まだ送れていない」とみなす（確認画面・エラー戻り）
        n_ta = len(await pg.query_selector_all("textarea"))
        fail = FAIL_RE.search(body)
        if m and not n_ta and not fail:
            await pg.screenshot(path=str(OUT / f"w{wave}-{f['No']}-sent.png"), full_page=True)
            return {"state": "done", "reason": "", "proof": m.group(0)}
        if fail and not m:
            await pg.screenshot(path=str(OUT / f"w{wave}-{f['No']}-sent.png"), full_page=True)
            w = await why_stuck(pg)
            return {"state": "ng", "reason": "入力エラー（" + fail.group(0) + "）" + (f"：{w}" if w else ""), "proof": ""}
        seen.append((pg.url != before_url, n_ta))
        # 確認画面らしい（入力欄が消えて「送信」ボタンがある）なら、次の手で送信を押す
        nxt = await pg.query_selector(SEND_BTN)
        if not nxt:
            await pg.screenshot(path=str(OUT / f"w{wave}-{f['No']}-sent.png"), full_page=True)
            w = await why_stuck(pg)
            return {"state": "ng", "reason": "完了画面を確認できない" + (f"：{w}" if w else ""), "proof": ""}
    await pg.screenshot(path=str(OUT / f"w{wave}-{f['No']}-sent.png"), full_page=True)
    w = await why_stuck(pg)
    return {"state": "ng", "reason": "確認画面から進めない" + (f"：{w}" if w else ""), "proof": ""}


async def run_forms(targets: list, wave: int, send: bool, email_from: str, n: int = 50) -> None:
    sent = 0
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
            if send and not (SEND_HOURS[0] <= dt.datetime.now(JST).hour < SEND_HOURS[1]):
                print(f"{SEND_HOURS[1]}:00 を過ぎたので止める（オーナー決定 2026-09-14：初動は 9:00〜17:00）")
                break
            url = f["contact"]["contact_form_url"]
            pg = await ctx.new_page()
            text = form_text(f, f["種別"])
            subj = "利用者さま向けの読み物（A6カード）を置いていただけませんか"
            try:
                r = await asyncio.wait_for(fill_form(pg, url, text, email_from, subj), timeout=90)
                shot = OUT / f"w{wave}-{f['No']}.png"
                await pg.screenshot(path=str(shot), full_page=True)
                if not r["ok"]:
                    print("スキップ", f["No"], f["施設名"], r["reason"])
                    if send:
                        safe_write(tok, "log", log_send, wave, f, "フォーム", url, "③", f"未送信（{r['reason']}）")
                        safe_write(tok, "manual", mark_manual, f, r["reason"])
                    continue
                if not send:
                    print("入力のみ", f["No"], f["施設名"], r["filled"], shot.name)
                    sent += 1
                    if sent >= n:
                        break
                    continue
                # 送信：確認画面をまたぐことがあるので、最大3手まで進めて「完了」を見届ける
                res = await asyncio.wait_for(submit(pg, wave, f), timeout=90)
                dest = r.get("moved_to") or url
                note = ("巡回で拾ったURLにフォームが無く、サイト内の問い合わせページへ移動: " + url) if r.get("moved_to") else ""
                if res["state"] != "done":
                    safe_write(tok, "log", log_send, wave, f, "フォーム", dest, "③", f"未送信（{res['reason']}）", note)
                    safe_write(tok, "manual", mark_manual, f, res["reason"])
                    print("未送信", f["No"], f["施設名"], res["reason"])
                    continue
                safe_write(tok, "log", log_send, wave, f, "フォーム", dest, "③", "送信（画面で完了を確認）",
                           (note + " / " if note else "") + res["proof"][:80])
                safe_write(tok, "stage", update_stage, f, "form")
                print("送信", f["No"], f["施設名"], res["proof"][:40])
                sent += 1
                if sent >= n:
                    print(f"{n} 件送れたので止める（オーナー決定：50件ごとに停止して改善）")
                    break
            except asyncio.TimeoutError:
                if send:
                    safe_write(tok, "log", log_send, wave, f, "フォーム", url, "③", "未送信（時間切れ）")
                    safe_write(tok, "manual", mark_manual, f, "時間切れ")
                print("時間切れ", f["No"], f["施設名"])
            except Exception as e:
                if send:
                    safe_write(tok, "log", log_send, wave, f, "フォーム", url, "③", f"失敗（{type(e).__name__}）")
                print("失敗", f["No"], f["施設名"], type(e).__name__, str(e)[:120])
            finally:
                await pg.close()
        await b.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["plan", "form", "mail"])
    ap.add_argument("--wave", type=int, default=1)
    ap.add_argument("--n", type=int, default=50, help="送れた数がこれに届いたら止める（候補は尽きるまで見る）")
    ap.add_argument("--send", action="store_true")
    ap.add_argument("--from-email", default="", help=f"フォームに書く返信先メール（既定 {G.REPLY_TO}）")
    ap.add_argument("--exclude", default="", help="送らない種別（カンマ区切り。第1波は CMO 決定で 産婦人科・産院 を除く）")
    a = ap.parse_args()
    ex = tuple(x for x in a.exclude.split(",") if x)
    rows = load()
    if a.mode == "plan":
        for how in ("form", "mail"):
            t = pick(rows, a.n, how, ex)
            print(f"== {how}: {len(t)}件")
            for f in t:
                print(f" {f['No']:>4} {f['優先度']} {f['種別']:<10} {f['施設名'][:24]:<24} {f['contact'].get('contact_form_url') if how == 'form' else email_of(f['contact'], f['施設名'], f.get('サイト', ''))}")
        return
    if a.mode == "mail":
        OUT.mkdir(parents=True, exist_ok=True)
        t = pick(rows, a.n, "mail", ex)
        for f in t:
            subj, body = mail_text(f, f["種別"])
            (OUT / f"w{a.wave}-{f['No']}-mail.txt").write_text(f"To: {email_of(f['contact'], f['施設名'], f.get('サイト', ''))}\nSubject: {subj}\n\n{body}", encoding="utf-8")
        print("メール本文を書き出し:", len(t), "件 →", OUT)
        if not a.send:
            return
        check_send_window()
        cfg = G.load()
        who = G.whoami(cfg)
        if who != cfg["sender"]:
            sys.exit(f"認可されたアカウント（{who}）が sender（{cfg['sender']}）と違う。送らない")
        tok = sc.access_token(sc.load_credentials())
        gtok = G.access_token(cfg)
        done = mails_today(tok)
        for f in t:
            if done >= MAIL_PER_DAY:
                print(f"今日の上限 {MAIL_PER_DAY} 件に達した。残りは明日")
                break
            to = email_of(f["contact"], f["施設名"], f.get("サイト", ""))
            subj, body = mail_text(f, f["種別"])
            kata = "①" if yomihon(f["種別"])["who"].startswith("赤ちゃん") else "②"
            try:
                mid = G.send(cfg, to, subj, body, token=gtok)
                safe_write(tok, "log", log_send, a.wave, f, "メール", to, kata, "送信", f"Gmail id {mid}")
                safe_write(tok, "stage", update_stage, f, "mail")
                done += 1
                print("送信", f["No"], f["施設名"], to)
            except Exception as e:
                safe_write(tok, "log", log_send, a.wave, f, "メール", to, kata, f"失敗（{type(e).__name__}）", str(e)[:100])
                print("失敗", f["No"], f["施設名"], to, str(e)[:120])
        return
    if not a.from_email:
        a.from_email = REPLY_TO
    if a.send:
        check_send_window()
    t = pick(rows, 0, "form", ex)  # 候補は全部見て、送れた数が --n に届いたら止める
    asyncio.run(run_forms(t, a.wave, a.send, a.from_email, a.n))


if __name__ == "__main__":
    main()
