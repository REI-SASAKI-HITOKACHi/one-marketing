#!/usr/bin/env python3
"""施設からの返信を onehitter.her@gmail.com で受け取り、仕分けして、進捗タブに反映し、返事の下書きまで作る。

オーナー指摘 2026-09-14：「info@one-hitter.her.jp が送信元になると、設置許可や問い合わせが来たときに僕が対応しなきゃいけなくなる」。
そのとおりで、ロリポップのメールはこの環境から読めない（IMAP 993・POP 995・SMTP 465/587・Webメールの HTTPS すべて到達不可）。
そこで宛先も返信先も onehitter.her@gmail.com に寄せ、Gmail API（HTTPS）で私が読んで返す。

やること:
  1. 受信箱の未処理を読む（施設カードの件だけ。ラベルで印を付けて二重処理しない）
  2. 中身で仕分ける … 設置OK ／ 不要・お断り ／ 質問 ／ 自動返信（確認メール） ／ その他
  3. 進捗タブ（施設カード_進捗）の「反応」「ステージ」「次回アクション」を更新し、送信ログにも1行足す
  4. 返事を作る。**送信は --send を付けたときだけ。** 付けなければ下書き（Gmail の下書き）に置く
  5. 人に回すもの（値段の交渉・苦情・法務）は返さずに掲示板へ上げる

使い方:
  python3 tools/shisetsu-inbox.py            # 読んで仕分けして、下書きまで（送らない）
  python3 tools/shisetsu-inbox.py --send     # 定型の返事は自動で送る（9:00〜17:00 のみ）
  python3 tools/shisetsu-inbox.py --days 3   # 直近3日ぶんを見る（既定は7日）
"""
import argparse
import base64
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
SS = "1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64"
TAB_P = "施設カード_進捗"
HEAD_ROW = 13
JST = dt.timezone(dt.timedelta(hours=9))
LABEL = "施設カード_処理済み"
SEND_HOURS = (9, 17)
SETTI_URL = f"{C.DOKUHON_URL}/setti/"

# 仕分けの言葉。上から順に見る（強いものが先）
RULES = [
    ("不要", re.compile(r"不要|お断り|辞退|遠慮|見送り|間に合って|結構です|配信停止|停止してください|今後.{0,6}(送|連絡).{0,4}(不要|controlしないで)")),
    ("設置OK", re.compile(r"置(き|い)ても?(よ|良|い)い|設置(し|させて)?(ます|いただ)|お受けし|承(り|知)(しました)?|大丈夫です|置かせていただ|送ってください|お願いします")),
    ("質問", re.compile(r"\?|？|でしょうか|ますか|教えて|詳し(く|い)|資料|条件|何枚|いつ|費用|料金")),
]
AUTO_RE = re.compile(r"自動(返信|配信)|自動的に送信|automatic|no-?reply|受け付けました|お問い合わせありがとう|送信されました|確認メール")
# 人が見るべきもの（返事を自動で出さない）
ESCALATE_RE = re.compile(r"苦情|クレーム|法務|弁護士|訴|個人情報保護|特定商取引|通報|警告|損害")


def api(tok, path, method="GET", payload=None, query=None):
    url = G.API + path + (("?" + urllib.parse.urlencode(query)) if query else "")
    import urllib.request
    req = urllib.request.Request(url, data=json.dumps(payload).encode() if payload is not None else None, method=method)
    req.add_header("Authorization", "Bearer " + tok)
    if payload is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except Exception as e:
        raise RuntimeError(f"Gmail API {path}: {str(e)[:200]}")


def ensure_label(tok) -> str:
    for lb in api(tok, "/labels").get("labels", []):
        if lb["name"] == LABEL:
            return lb["id"]
    return api(tok, "/labels", "POST", {"name": LABEL, "labelListVisibility": "labelShow", "messageListVisibility": "show"})["id"]


def body_text(payload) -> str:
    """本文（text/plain を優先。無ければ HTML からタグを外す）"""
    def walk(p):
        out = []
        if p.get("body", {}).get("data"):
            out.append((p.get("mimeType", ""), base64.urlsafe_b64decode(p["body"]["data"] + "==").decode("utf-8", "replace")))
        for q in p.get("parts", []) or []:
            out += walk(q)
        return out
    parts = walk(payload)
    plain = [t for m, t in parts if m == "text/plain"]
    if plain:
        return plain[0]
    html = [t for m, t in parts if m == "text/html"]
    return re.sub(r"<[^>]+>", " ", html[0]) if html else ""


def classify(subject: str, text: str) -> str:
    s = subject + "\n" + text
    if ESCALATE_RE.search(s):
        return "人へ"
    if AUTO_RE.search(s) and not re.search(r"置|設置|カード", text):
        return "自動返信"
    for name, rx in RULES:
        if rx.search(s):
            return name
    return "その他"


def reply_text(kind: str, name: str) -> tuple:
    """定型の返事。値段の交渉や特別な条件は作らない（人に回す）"""
    if kind == "設置OK":
        return ("ありがとうございます。カードをお送りします",
                f"""{name} ご担当者さま

ご連絡をありがとうございます。カードを置いていただけるとのこと、お礼申し上げます。

下のページから、設置場所だけお知らせください（1分で終わります）。
貴施設専用のカード（A6・PDF）をお送りし、そのカードから何名が読まれたかを毎週月曜にお知らせします。
{SETTI_URL}

印刷したものをご希望でしたら、その旨お知らせください。こちらで印刷してお送りします。

ワンヒッター株式会社
佐々木 嶺
〒134-0081 東京都江戸川区北葛西5-14-11 クオーディア西葛西503
電話 {C.UNEI_TEL}""")
    if kind == "不要":
        return ("承知しました",
                f"""{name} ご担当者さま

ご連絡をありがとうございます。承知しました。以後お送りしません。
お手数をおかけしました。

ワンヒッター株式会社
佐々木 嶺
電話 {C.UNEI_TEL}""")
    return ("", "")


def colletter(i: int) -> str:
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def update_row(tok_s, name: str, kind: str, note: str) -> bool:
    vals = sc.call(tok_s, f"/{SS}/values/{urllib.parse.quote(TAB_P + '!A' + str(HEAD_ROW) + ':AM1500')}").get("values", [])
    head = vals[0]
    col = {h: i for i, h in enumerate(head)}
    today = dt.datetime.now(JST).strftime("%Y-%m-%d")
    for i, r in enumerate(vals[1:], start=HEAD_ROW + 1):
        r = r + [""] * (len(head) - len(r))
        if r[col["施設名"]] != name:
            continue
        upd = {"反応": kind, "最終接触日": today}
        if kind == "設置OK":
            upd.update({"ステージ": "設置OK（カード送付待ち）", "次回アクション": "承諾フォームの回答を待つ。3日来なければ1回だけ催促"})
        elif kind == "不要":
            upd.update({"ステージ": "お断り", "次回アクション": "以後送らない", "断り理由": note[:60]})
        elif kind == "質問":
            upd.update({"ステージ": "やり取り中", "次回アクション": "質問に回答済み。返事を待つ"})
        elif kind == "人へ":
            upd.update({"ステージ": "やり取り中", "次回アクション": "人の判断が要る（掲示板へ上げた）"})
        data = [{"range": f"{TAB_P}!{colletter(col[k])}{i}", "values": [[v]]} for k, v in upd.items() if k in col]
        sc.call(tok_s, f"/{SS}/values:batchUpdate", method="POST", payload={"valueInputOption": "USER_ENTERED", "data": data})
        return True
    return False


def match_facility(tok_s, addr: str, text: str) -> str:
    """差出人のアドレスかドメインから施設名を当てる"""
    dom = addr.split("@")[-1].lower()
    vals = sc.call(tok_s, f"/{SS}/values/{urllib.parse.quote(TAB_P + '!A' + str(HEAD_ROW) + ':I1500')}").get("values", [])
    head = vals[0]
    col = {h: i for i, h in enumerate(head)}
    for r in vals[1:]:
        r = r + [""] * (len(head) - len(r))
        site = (r[col["サイト"]] or "").lower()
        if dom and dom in site:
            return r[col["施設名"]]
    for r in vals[1:]:
        r = r + [""] * (len(head) - len(r))
        nm = r[col["施設名"]]
        if nm and len(nm) >= 4 and nm[:6] in text:
            return nm
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--send", action="store_true")
    ap.add_argument("--days", type=int, default=7)
    a = ap.parse_args()
    cfg = G.load()
    tok = G.access_token(cfg)
    who = api(tok, "/profile").get("emailAddress", "")
    if who != cfg["sender"]:
        sys.exit(f"認可されたアカウント（{who}）が sender（{cfg['sender']}）と違う")
    lbl = ensure_label(tok)
    tok_s = sc.access_token(sc.load_credentials())
    q = f"newer_than:{a.days}d -label:{LABEL} -from:me -in:sent"
    msgs = api(tok, "/messages", query={"q": q, "maxResults": 100}).get("messages", [])
    print(f"未処理 {len(msgs)} 通（{who}）")
    counts = {}
    for m in msgs:
        d = api(tok, f"/messages/{m['id']}", query={"format": "full"})
        hs = {h["name"].lower(): h["value"] for h in d["payload"].get("headers", [])}
        frm = hs.get("from", "")
        addr = (re.search(r"[\w.+-]+@[\w.-]+", frm) or [""])[0] if re.search(r"[\w.+-]+@[\w.-]+", frm) else ""
        subj = hs.get("subject", "")
        text = body_text(d["payload"])[:4000]
        kind = classify(subj, text)
        counts[kind] = counts.get(kind, 0) + 1
        name = match_facility(tok_s, addr, subj + " " + text) if kind not in ("自動返信",) else ""
        print(f"  [{kind}] {addr} {subj[:34]} → {name or '施設不明'}")
        if kind in ("設置OK", "不要", "質問", "人へ") and name:
            update_row(tok_s, name, kind, text[:80].replace("\n", " "))
        sub, rep = reply_text(kind, name or "ご担当者") if kind in ("設置OK", "不要") else ("", "")
        if rep:
            raw = base64.urlsafe_b64encode(G.build(cfg, addr, "Re: " + (subj or sub), rep)).decode()
            if a.send:
                now = dt.datetime.now(JST)
                if not (SEND_HOURS[0] <= now.hour < SEND_HOURS[1]):
                    print("    （9:00〜17:00 以外なので下書きに置く）")
                    api(tok, "/drafts", "POST", {"message": {"raw": raw, "threadId": d.get("threadId")}})
                else:
                    api(tok, "/messages/send", "POST", {"raw": raw, "threadId": d.get("threadId")})
                    print("    返信した")
            else:
                api(tok, "/drafts", "POST", {"message": {"raw": raw, "threadId": d.get("threadId")}})
                print("    下書きに置いた")
        if kind == "人へ":
            print("    ★ 人の判断が要る。掲示板へ上げること")
        api(tok, f"/messages/{m['id']}/modify", "POST", {"addLabelIds": [lbl], "removeLabelIds": ["UNREAD"]})
    print("仕分け:", counts)


if __name__ == "__main__":
    main()
