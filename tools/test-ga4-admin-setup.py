#!/usr/bin/env python3
"""tools/ga4-admin-setup.py を、偽のGA4 Admin APIで動かして確かめる。

    python3 tools/test-ga4-admin-setup.py

**鍵は要らない。本物のGA4には一切つながらない。**
GA4は一度キーイベントを作ると消しづらいので、本番で試す前にここで確かめる。

見ているのは5つ：
  1. --dry-run のときに1件も書き込まないこと
  2. まっさらな状態でキーイベント3件が ONCE_PER_EVENT で作られること
  3. もう一度実行しても作り直さないこと（冪等）
  4. form_submit が紛れていたら警告し、範囲がEVENT以外の次元も警告すること
  5. --create-dimensions で、足りない次元だけを EVENT で作ること
"""
import importlib.util, io, json, sys, urllib.request, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("g", ROOT / "tools" / "ga4-admin-setup.py")

g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g)

STATE = {"keyEvents": [], "customDimensions": [], "posts": []}

def fake_urlopen(req, timeout=None):
    url, method = req.full_url, req.get_method()
    body = req.data.decode() if req.data else None
    if method == "POST":
        kind = "keyEvents" if url.endswith("/keyEvents") else "customDimensions"
        STATE["posts"].append((kind, json.loads(body)))
        STATE[kind].append(json.loads(body))
        return io.BytesIO(b"{}")
    kind = "keyEvents" if "/keyEvents" in url else "customDimensions"
    # ページ送りも試す：1件ずつ返す
    items = STATE[kind]
    tok = None
    if "pageToken=" in url:
        i = int(url.split("pageToken=")[1].split("&")[0])
    else:
        i = 0
    chunk = items[i:i+1]
    if i + 1 < len(items): tok = str(i+1)
    res = {kind: chunk}
    if tok: res["nextPageToken"] = tok
    return io.BytesIO(json.dumps(res).encode())

class R(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self,*a): return False
def wrap(req, timeout=None):
    b = fake_urlopen(req, timeout); return R(b.getvalue())
urllib.request.urlopen = wrap

g.load_sheets_client = lambda: type("M", (), {
    "load_credentials": staticmethod(lambda: {"client_email":"x"}),
    "access_token": staticmethod(lambda info, scope=None: "tok"),
})()

def run(args, label):
    print("\n" + "="*64); print("### " + label)
    sys.argv = ["g"] + args
    STATE["posts"].clear()
    try: g.main()
    except SystemExit as e:
        if e.code: print("SystemExit:", e.code)
    return list(STATE["posts"])

# --- 1回目：空っぽ。下見 ---
p = run(["--dry-run"], "1回目：まっさら＋--dry-run（何も書かないはず）")
assert p == [], f"下見なのに書き込んだ: {p}"
print(">>> 書き込み0件 OK")

# --- 2回目：本番。3件作られるはず ---
p = run([], "2回目：本番（キーイベント3件が作られるはず）")
assert [x[1]["eventName"] for x in p] == ["generate_lead","phone_click","line_click"], p
assert all(x[1]["countingMethod"]=="ONCE_PER_EVENT" for x in p), p
print(">>> 3件登録 OK")

# --- 3回目：もう一度。冪等なら0件 ---
p = run([], "3回目：もう一度（冪等なら追加0件）")
assert p == [], f"2度目で作り直している: {p}"
print(">>> 冪等 OK")

# --- 4回目：余計なキーイベントと、範囲が違う次元がある状態 ---
STATE["keyEvents"].append({"eventName":"form_submit"})
STATE["customDimensions"] += [
  {"parameterName":"lp_id","displayName":"LP","scope":"EVENT"},
  {"parameterName":"lp_variant","displayName":"LPパターン","scope":"USER"},
]
p = run([], "4回目：form_submit が紛れ、lp_variant の範囲が USER の状態")
print(">>> 警告が出ていること／未登録6件と数えていることを目視")

# --- 5回目：次元も作る ---
p = run(["--create-dimensions"], "5回目：--create-dimensions で不足を作る")
tsukutta = [x[1]["parameterName"] for x in p if x[0]=="customDimensions"]
print(">>> 作った次元:", tsukutta)
assert "traffic_src" in tsukutta and "lp_id" not in tsukutta, tsukutta
assert all(x[1]["scope"]=="EVENT" for x in p if x[0]=="customDimensions")
print(">>> 不足ぶんだけ EVENT で作成 OK")
print("\nすべて通りました")
