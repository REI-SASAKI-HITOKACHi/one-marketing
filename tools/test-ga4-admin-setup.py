#!/usr/bin/env python3
"""tools/ga4-admin-setup.py を、偽のGA4 Admin APIで動かして確かめる。

    python3 tools/test-ga4-admin-setup.py

**鍵は要らない。本物のGA4には一切つながらない。**
CMOの環境で一発勝負で走らせる道具なので、本番で試す前にここで確かめる。

見ているもの：
  1. --dry-run のときに1件も書き込まない（追加も除去も、控えのファイルも）
  2. まっさらな状態で、キーイベント4件が ONCE_PER_EVENT で作られる
  3. もう一度実行しても作り直さない（冪等）
  4. form_complete があれば外す。**外すのは足し終わったあと**
  5. **変更前の一覧を、GA4を触る前に控える**
  6. 外すと決めていないもの（teltap など）は触らない
  7. form_submit が紛れていたら警告し、範囲がEVENT以外の次元も警告する
  8. --create-dimensions で、足りない次元だけを EVENT で作る
"""
import importlib.util, io, json, sys, urllib.request, pathlib, tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("g", ROOT / "tools" / "ga4-admin-setup.py")
g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g)

STATE = {"keyEvents": [], "customDimensions": [], "log": []}
SEQ = [100]


def fake_urlopen(req, timeout=None):
    url, method = req.full_url, req.get_method()
    body = req.data.decode() if req.data else None
    if method == "POST":
        kind = "keyEvents" if url.endswith("/keyEvents") else "customDimensions"
        obj = json.loads(body)
        if kind == "keyEvents":
            SEQ[0] += 1
            obj["name"] = f"properties/381320625/keyEvents/{SEQ[0]}"
        STATE["log"].append(("POST", kind, obj))
        STATE[kind].append(obj)
        return b"{}"
    if method == "DELETE":
        name = url.split("/v1beta/")[1]
        STATE["log"].append(("DELETE", "keyEvents", name))
        STATE["keyEvents"] = [k for k in STATE["keyEvents"] if k.get("name") != name]
        return b""
    kind = "keyEvents" if "/keyEvents" in url else "customDimensions"
    items = STATE[kind]
    i = int(url.split("pageToken=")[1].split("&")[0]) if "pageToken=" in url else 0
    res = {kind: items[i:i + 1]}
    if i + 1 < len(items):
        res["nextPageToken"] = str(i + 1)
    return json.dumps(res).encode()


class R(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False


urllib.request.urlopen = lambda req, timeout=None: R(fake_urlopen(req, timeout))
g.load_sheets_client = lambda: type("M", (), {
    "load_credentials": staticmethod(lambda: {"client_email": "x"}),
    "access_token": staticmethod(lambda info, scope=None: "tok"),
})()

tmp = pathlib.Path(tempfile.mkdtemp())
ok = True


def chk(label, cond, extra=""):
    global ok
    print(("PASS " if cond else "FAIL ") + label + (("  " + str(extra)) if extra else ""))
    if not cond:
        ok = False


def run(args):
    sys.argv = ["g"] + args
    STATE["log"].clear()
    buf = io.StringIO()
    import contextlib
    with contextlib.redirect_stdout(buf):
        try:
            g.main()
        except SystemExit as e:
            if e.code:
                print("SystemExit:", e.code)
    return list(STATE["log"]), buf.getvalue()


def ke(name):
    SEQ[0] += 1
    return {"eventName": name, "countingMethod": "ONCE_PER_EVENT",
            "name": f"properties/381320625/keyEvents/{SEQ[0]}",
            "createTime": "2025-01-01T00:00:00Z"}


# --- いまの本番と同じ状態から始める（2026-09-20 ブラウザ担当の実測） ---
STATE["keyEvents"] = [ke("form_complete"), ke("purchase"), ke("teltap")]
kiroku = tmp / "before.md"

# 1. 下見
log, out = run(["--dry-run", "--kiroku", str(kiroku)])
chk("下見では1件も書き込まない", log == [], log)
chk("下見では控えのファイルも書かない", not kiroku.exists())
chk("下見で「これから外す」が出る", "form_complete" in out and "これから外す" in out, out[:400])
chk("下見で追加4件・除去1件と数える", "4 件追加・1 件除去" in out, out[-300:])

# 2. 本番
log, out = run(["--kiroku", str(kiroku)])
posts = [x[2]["eventName"] for x in log if x[0] == "POST" and x[1] == "keyEvents"]
dels = [x for x in log if x[0] == "DELETE"]
chk("キーイベント4件が作られる",
    posts == ["generate_lead", "phone_click", "line_click", "booking_start"], posts)
chk("数え方は ONCE_PER_EVENT",
    all(x[2]["countingMethod"] == "ONCE_PER_EVENT" for x in log if x[0] == "POST" and x[1] == "keyEvents"))
chk("form_complete だけが外される", len(dels) == 1, dels)
order = [x[0] for x in log if x[1] == "keyEvents"]
chk("外すのは、足し終わったあと", order == ["POST"] * 4 + ["DELETE"], order)

# 5. 変更前の控え
chk("変更前の一覧を控える", kiroku.exists())
body = kiroku.read_text(encoding="utf-8") if kiroku.exists() else ""
chk("控えに、外す前の form_complete が残っている", "`form_complete`" in body, body[:300])
chk("控えに、元に戻すときの手がかり（name）がある", "keyEvents/" in body)

# 6. 決めていないものは触らない
names = sorted(k["eventName"] for k in STATE["keyEvents"])
chk("teltap と purchase は残る（外すと決めていない）",
    "teltap" in names and "purchase" in names, names)
chk("form_complete は消えている", "form_complete" not in names, names)

# 3. 冪等
log, out = run(["--kiroku", str(tmp / "before2.md")])
chk("もう一度回しても何も変えない", [x for x in log if x[0] in ("POST", "DELETE")] == [], log)
chk("2回目は「もともと無い」と言う", "もともと無い" in out)

# 7. 紛れ込みの警告
STATE["keyEvents"].append(ke("form_submit"))
STATE["customDimensions"] += [
    {"parameterName": "lp_id", "displayName": "LP", "scope": "EVENT"},
    {"parameterName": "lp_variant", "displayName": "LPパターン", "scope": "USER"},
]
log, out = run(["--dry-run"])
chk("form_submit が紛れていたら二重計上を警告する",
    "form_submit" in out and "二重" in out, out[-600:])
chk("範囲が USER の次元を警告する", "USER" in out)

# 8. 次元
log, out = run(["--create-dimensions", "--kiroku", str(tmp / "before3.md")])
tsukutta = [x[2]["parameterName"] for x in log if x[0] == "POST" and x[1] == "customDimensions"]
chk("足りない次元だけ作る", "traffic_src" in tsukutta and "lp_id" not in tsukutta, tsukutta)
chk("作る次元は EVENT",
    all(x[2]["scope"] == "EVENT" for x in log if x[0] == "POST" and x[1] == "customDimensions"))

print("\n" + ("すべて通りました" if ok else "失敗あり"))
sys.exit(0 if ok else 1)
