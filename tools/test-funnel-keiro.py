#!/usr/bin/env python3
"""tools/funnel-keiro.py を偽の GA4 結果で確かめる。  python3 tools/test-funnel-keiro.py"""
import json, pathlib, subprocess, sys, tempfile
ROOT = pathlib.Path(__file__).resolve().parent.parent
TOOL = ROOT / "tools" / "funnel-keiro.py"
tmp = pathlib.Path(tempfile.mkdtemp())
rows = [
    ["page_view", "lp.onehitter.jp", "/aircon-c/?src=gads_aircon&ag=1&gclid=X", 80],
    ["page_view", "yoyaku.onehitter.jp", "/aircon-c/?src=gads_aircon&ag=1&gclid=X", 10],
    ["booking_start", "yoyaku.onehitter.jp", "/aircon-c/?src=gads_aircon&ag=1&gclid=X", 4],
    ["generate_lead", "yoyaku.onehitter.jp", "/aircon-c/?src=gads_aircon&ag=1&gclid=X", 1],
    ["page_view", "lp.onehitter.jp", "/mizumawari/?gclid=Y", 20],          # src 無しでも gclid で広告
    ["page_view", "yoyaku.onehitter.jp", "/?src=sms_nov", 30],
    ["booking_start", "yoyaku.onehitter.jp", "/?src=sms_nov", 3],
    ["page_view", "lp.onehitter.jp", "/aircon/?src=ig", 5],
    ["page_view", "lp.onehitter.jp", "/", 7],
    ["scroll", "lp.onehitter.jp", "/", 99],                                 # 数えない
]
(tmp / "g.json").write_text(json.dumps({"start": "2026-10-01", "end": "2026-10-14", "rows": rows}), encoding="utf-8")
(tmp / "y.csv").write_text("注文ID,src,受信日時,状態の区分\nA,gads_aircon,2026-10-06 10:37,受注済\nB,sms_nov,2026-10-12 9:00,\nC,direct,2026-10-08 4:24,空送信\nD,gads_aircon,2026-09-27 18:41,受注済\n", encoding="utf-8")
ok = True
def chk(l, c, e=""):
    global ok
    print(("PASS " if c else "FAIL ") + l + (("\n" + str(e)) if (e and not c) else ""))
    if not c: ok = False
out = subprocess.run([sys.executable, str(TOOL), "--json", str(tmp / "g.json"), "--yoyaku", str(tmp / "y.csv")], capture_output=True, text=True).stdout
chk("広告：LP100（gclid のみの行も広告）・予約ページ10・入力開始4・申込1", "| 広告 | 100 | 10（10%） | 4（40%） | 1（25%） | 1 | 1 |" in out, out)
chk("SMS：LPを経ずに予約ページへ", "| SMS | 0 | 30（—） | 3（10%） | 0（0%） | 1 | 0 |" in out, out)
chk("Instagram（ig）は無料経路の行", "| Instagram | 5 |" in out)
chk("src 無し・gclid 無しは直接・その他", "| 直接・その他 | 7 |" in out)
chk("予約_Web：期間外と空送信は数えない", "| 直接・その他 | 7 | 0（0%） | 0（0%） | 0（—） | 0 | 0 |" in out, out)
chk("いちばん落ちている所＝広告の LP→予約ページ", "**広告 の「LP表示→予約ページ表示」**" in out, out)
# SNS広告の日別（--src）
rows2 = [
    ["20261017", "page_view", "yoyaku.onehitter.jp", "/?src=ig_ad&fbclid=abc", 6],
    ["20261017", "booking_start", "yoyaku.onehitter.jp", "/?src=ig_ad&fbclid=abc", 2],
    ["20261017", "booking_submit", "yoyaku.onehitter.jp", "/?src=ig_ad&fbclid=abc", 1],
    ["20261017", "generate_lead", "yoyaku.onehitter.jp", "/?src=ig_ad&fbclid=abc", 1],
    ["20261018", "page_view", "yoyaku.onehitter.jp", "/?src=fb_ad", 3],
    ["20261018", "page_view", "yoyaku.onehitter.jp", "/?src=ig", 9],          # 自然投稿は入れない
]
(tmp / "g2.json").write_text(json.dumps({"start": "2026-10-17", "end": "2026-10-30", "rows": rows2}), encoding="utf-8")
(tmp / "y2.csv").write_text("注文ID,src,受信日時,状態の区分\nA,ig_ad,2026-10-17 20:00,\nB,ig,2026-10-18 9:00,\n", encoding="utf-8")
out = subprocess.run([sys.executable, str(TOOL), "--json", str(tmp / "g2.json"), "--src", "ig_ad,fb_ad", "--yoyaku", str(tmp / "y2.csv")], capture_output=True, text=True).stdout
chk("ig_ad の日別（到達6・入力開始2・送信1・申込1）", "| 2026-10-17 | ig_ad | 6 | 2 | 1 | 1 |" in out, out)
chk("fb_ad の日別", "| 2026-10-18 | fb_ad | 3 | 0 | 0 | 0 |" in out, out)
chk("自然投稿の ig は入れない", "| ig |" not in out)
chk("予約_Web の件数（ig_ad 1・fb_ad 0）", "ig_ad 1件、fb_ad 0件" in out, out)

rows3 = [["page_view", "lp.onehitter.jp", "/kabi/?src=gads_kabi&ag=9&gclid=Z", 12],
         ["page_view", "yoyaku.onehitter.jp", "/kabi/?src=gads_kabi&ag=9&gclid=Z", 3],
         ["page_view", "lp.onehitter.jp", "/aircon-c/?src=gads_aircon&gclid=X", 5]]
(tmp / "g3.json").write_text(json.dumps({"start": "2026-10-20", "end": "2026-10-30", "rows": rows3}), encoding="utf-8")
out = subprocess.run([sys.executable, str(TOOL), "--json", str(tmp / "g3.json")], capture_output=True, text=True).stdout
chk("gads_kabi はカビLPとして別の行（広告の行に混ざらない）", "| 広告（カビLP） | 12 | 3（25%） |" in out and "| 広告 | 5 |" in out, out)

rows4 = [["page_view", "yoyaku.onehitter.jp", "/?src=ig_ad", 4], ["page_view", "yoyaku.onehitter.jp", "/?src=hp_menu", 3],
         ["page_view", "yoyaku.onehitter.jp", "/?src=gbp_book", 2]]
(tmp / "g4.json").write_text(json.dumps({"start": "2026-10-01", "end": "2026-10-20", "rows": rows4}), encoding="utf-8")
(tmp / "y4.csv").write_text("注文ID,src,受信日時,状態の区分\nA,hp_menu,2026-10-05 9:00,受注済\n", encoding="utf-8")
out = subprocess.run([sys.executable, str(TOOL), "--json", str(tmp / "g4.json"), "--yoyaku", str(tmp / "y4.csv")], capture_output=True, text=True).stdout
chk("ig_ad は SNS広告（無料経路に入れない）", "| SNS広告 | 0 | 4（—） |" in out and "| Instagram | 0 | 0" in out, out)
chk("HP の申込・受注", "| HP | 0 | 3（—） | 0（0%） | 0（—） | 1 | 1 |" in out, out)
chk("無料経路の計（HP 3＋GBP 2 の予約ページ到達・申込1・受注1）", "| **無料経路の計**（HP・Instagram・Facebook・ブログ・GBP） | 0 | 5 | 0 | 0 | 1 | 1 |" in out, out)

print("\n" + ("すべて通りました" if ok else "失敗あり")); sys.exit(0 if ok else 1)
