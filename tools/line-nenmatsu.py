#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""公式LINE：年末の締切のお知らせを、**台帳と照合できた自社のお客様だけ**に multicast する。

依頼 `20261001-02-crm`（CMO）。**送るのはオーナー承認のあと。**

    set -a; . ~/.config/one-hitter/line.env; set +a
    python3 tools/line-nenmatsu.py               # 宛先を照合して人数だけ出す（既定・送らない）
    python3 tools/line-nenmatsu.py --kenshou     # LINE の検証API（validate/multicast）で本文を確かめる。送らない
    python3 tools/line-nenmatsu.py --okuru --shounin "オーナー 10/1 19:xx LINE で承認"   # 送る

## 宛先の決め方（名乗り照合）

LINE のユーザーIDと台帳をつなぐ列は無い。手がかりは**表示名**だけ（お客様が自由に決める）。

1. 友だち（`followers/ids`）のプロフィールの表示名から空白を除き、**台帳（顧客管理台帳）の顧客名と完全に一致**する人
2. その氏名の顧客が**台帳に1人だけ**（同姓同名がいれば外す）
3. `meigi_hyou()`（台帳の最新の施工の名義・同日ルールつき）で、その氏名が**自社**
4. **今日より先の施工行（予約）が無い**こと。もう予約がある方に「12月は加算」を送ると戸惑わせる
5. **直近30日に当社から連絡した人を外す**（オーナー 10/1「最近連絡とってる人に重複して送らないように」）。
   見るもの：冬季SMS（送信済み・返信あり）／お詫びSMSの一覧／`LINE_ログ` のその人のユーザーIDのやり取り
   ／`LINE_ログ` の業務連絡に氏名（フルネーム、または「姓＋様・さま」）が出た／`予約_Web` の申込／30日以内の施工
6. **和真さんが「送らない」と答えた人を外す**：`private/nenmatsu-nozoku.txt`（git の外）に氏名を1行ずつ。
   氏名は台帳の顧客名と空白を除いて比べる

**本文は全員同じで、名前も前回の施工も入れない。** 表示名の一致は取り違えうるので、
取り違えても害が無い文面にしてある（`data/line-nenmatsu.txt`）。

## 守ること

- ユーザーIDと表示名は**画面にも掲示板にも git にも出さない**。数だけ。手元のメモリの中だけで使う。
- `--okuru` は `--shounin`（誰がいつ承認したか）が無ければ動かない。送る直前にもう一度照合し直す。
- 送る前に `honbun_ihan("自社", 本文)` と、電話番号・番地が入っていないかを確かめる。
- 無料枠（月200通）を超えるなら送らない。
"""
import importlib.util
import json
import os
import re
import sys
import time
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import line_client as LC  # noqa: E402
import meigi_check as MC  # noqa: E402

HONBUN = os.path.join(ROOT, "data", "line-nenmatsu.txt")
SS = "1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64"


def honbun():
    t = "\n".join(l for l in open(HONBUN, encoding="utf-8").read().splitlines() if not l.startswith("#")).strip()
    ihan = MC.honbun_ihan("自社", t)
    if re.search(r"0\d{1,4}-?\d{2,4}-?\d{3,4}", t):
        ihan.append("電話番号らしきものが入っている")
    if re.search(r"\d+-\d+(-\d+)?\s*$", t, re.M) or "丁目" in t:
        ihan.append("番地らしきものが入っている")
    if ihan:
        sys.exit("本文が規則に合いません: " + "／".join(ihan))
    return t


def _retry_sc(m):
    o = m.call

    def call(*a, **k):
        for i in range(8):
            try:
                return o(*a, **k)
            except SystemExit as e:
                if "429" not in str(e) or i == 7:
                    raise
                time.sleep(20 * (i + 1))
    m.call = call


def nn(n):
    return re.sub(r"[\s　]", "", str(n or ""))


NOZOKU = os.path.join(ROOT, "private", "nenmatsu-nozoku.txt")


def saikin_kiroku(dsk, tok):
    """直近30日の連絡の記録を読む。読めなければ例外（照合できない＝送らない）。"""
    import datetime
    kyou = datetime.date.today()
    since = kyou - datetime.timedelta(days=30)

    def tab(name, rng):
        return dsk.sc.call(tok, f"/{SS}/values/{urllib.parse.quote(name + '!' + rng, safe='')}").get("values", [])

    def hi(x):
        m = re.match(r"(\d{4})/(\d{1,2})/(\d{1,2})", str(x))
        return datetime.date(*map(int, m.groups())) if m else None
    fuyu = tab("冬季見込み客_2026", "A5:AA1200")
    fh = [str(c).strip() for c in fuyu[0]]
    fuyu_n = {nn(r[fh.index("顧客名")]) for r in fuyu[1:]
              if len(r) > fh.index("送信済み") and r[fh.index("送信済み")] in ("送信済み", "返信あり")}
    ow = tab("お詫びSMS_20260912", "A1:Z300")
    ow_n = {nn(c) for r in ow for c in r[:3]}
    lg = [r for r in tab("LINE_ログ", "A2:H5000") if r and hi(r[0]) and hi(r[0]) >= since]
    lg_uid = {r[3] for r in lg if len(r) > 3}
    lg_txt = re.sub(r"[\s　]", "", " ".join(str(r[5]) for r in lg if len(r) > 5))
    yw_n = {nn(r[2]) for r in tab("予約_Web", "A2:D500") if len(r) > 2}
    sekou_n = {j[2] for j in dsk.jobs_yomu() if since <= j[0] <= kyou}
    return fuyu_n, ow_n, lg_uid, lg_txt, yw_n, sekou_n


def atesaki():
    """(送ってよい userId の並び, 内訳の数) を返す。IDは返り値の中だけ。"""
    dsk = MC._load()
    _retry_sc(dsk.sc)
    hyou = dsk.meigi_hyou()
    by_name = hyou[1]
    kyou = __import__("datetime").date.today()
    yoyaku_ari = {j[2] for j in dsk.jobs_yomu() if j[0] > kyou}   # 今日より先の施工行がある氏名
    tok = dsk.tok_get()
    v = dsk.sc.call(tok, f"/{SS}/values/{urllib.parse.quote('顧客管理台帳!B16:B1200', safe='')}").get("values", [])
    namae = {}
    for r in v:
        if r and nn(r[0]):
            namae[nn(r[0])] = namae.get(nn(r[0]), 0) + 1
    fuyu_n, ow_n, lg_uid, lg_txt, yw_n, sekou_n = saikin_kiroku(dsk, tok)
    nozoku = set()
    if os.path.exists(NOZOKU):
        nozoku = {nn(l) for l in open(NOZOKU, encoding="utf-8") if nn(l) and not l.startswith("#")}
    sei_of = {}
    for r in v:
        if r and nn(r[0]):
            sei_of[nn(r[0])] = re.split(r"[\s　]", str(r[0]).strip())[0]
    ids, start = [], None
    while True:
        st, b = LC.call("GET", "/followers/ids?limit=1000" + (f"&start={start}" if start else ""))
        if st != 200:
            sys.exit(f"友だち一覧を読めません（HTTP {st}）。照合できないので送らない")
        ids += b.get("userIds", [])
        start = b.get("next")
        if not start:
            break
    kazu = {"友だち": len(ids), "表示名が台帳の氏名と一致": 0, "同姓同名で外した": 0,
            "名義が本舗": 0, "名義が分からない": 0, "もう予約が入っている": 0,
            "最近連絡した（30日）": 0, "和真さんが送らないと答えた": 0,
            "プロフィールが取れない": 0, "送ってよい（自社）": 0}
    ok = []
    for uid in ids:
        st, p = LC.call("GET", f"/profile/{uid}")
        if st != 200:
            kazu["プロフィールが取れない"] += 1
            continue
        n = nn(p.get("displayName"))
        if n not in namae:
            continue
        kazu["表示名が台帳の氏名と一致"] += 1
        if namae[n] > 1:
            kazu["同姓同名で外した"] += 1
            continue
        mg = by_name.get(n)
        if not mg:
            kazu["名義が分からない"] += 1
        elif mg[0] != "自社":
            kazu["名義が本舗"] += 1
        elif n in yoyaku_ari:
            kazu["もう予約が入っている"] += 1   # 12月の予約の方に「12月は加算」を送ると戸惑わせる
        elif n in nozoku:
            kazu["和真さんが送らないと答えた"] += 1
        elif (n in fuyu_n or n in ow_n or uid in lg_uid or n in lg_txt or n in yw_n or n in sekou_n
              or (len(sei_of.get(n, "")) >= 2 and re.search(re.escape(sei_of[n]) + r"(様|さま)", lg_txt))):
            kazu["最近連絡した（30日）"] += 1
        else:
            ok.append(uid)
            kazu["送ってよい（自社）"] += 1
    return ok, kazu


def main():
    t = honbun()
    msgs = [{"type": "text", "text": t}]
    print(f"本文 {len(t)}文字・名乗り照合（文面）違反なし\n")
    if "--kenshou" in sys.argv:
        st, b = LC.call("POST", "/message/validate/multicast", {"messages": msgs})
        print(f"検証API（送らない）: HTTP {st} {b or ''}")
        return 0 if st == 200 else 1
    ok, kazu = atesaki()
    for k, n in kazu.items():
        print(f"  {k}: {n}")
    if "--okuru" not in sys.argv:
        print("\n送りません（既定）。")
        return 0
    if "--shounin" not in sys.argv or not sys.argv[sys.argv.index("--shounin") + 1:]:
        sys.exit("--shounin（誰がいつ承認したか）が無いので送りません")
    if not ok:
        sys.exit("送ってよい宛先が0人です")
    st, q = LC.call("GET", "/message/quota")
    st2, c = LC.call("GET", "/message/quota/consumption")
    if st == 200 and st2 == 200 and q.get("type") == "limited" and c.get("totalUsage", 0) + len(ok) > q.get("value", 0):
        sys.exit(f"今月の無料枠を超えます（使用 {c.get('totalUsage')}＋{len(ok)} > {q.get('value')}）。送りません")
    st, b = LC.call("POST", "/message/multicast", {"to": ok, "messages": msgs})
    print(f"multicast: HTTP {st} {b or ''}（{len(ok)}人・承認: {sys.argv[sys.argv.index('--shounin') + 1]}）")
    return 0 if st == 200 else 1


if __name__ == "__main__":
    sys.exit(main())
