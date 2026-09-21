#!/usr/bin/env python3
"""`tools/ga4-event-shirabe.py` の --param（絞り込み）を、鍵なしで確かめる。

    python3 tools/test-ga4-param.py

**CMOの環境で一発で走らせる道具なので、送っているリクエストの形まで見る。**
見た目が正しくても、絞り込みの組み立て方が違えば、黙って違う数字が返る。
"""
import contextlib, importlib.util, io, json, pathlib, sys, urllib.request
ROOT = pathlib.Path("/home/user/one-marketing")
spec = importlib.util.spec_from_file_location("sh", ROOT/"tools"/"ga4-event-shirabe.py")
sh = importlib.util.module_from_spec(spec); spec.loader.exec_module(sh)
sent = []
def mk(rs_map):
    def fake(req, timeout=None):
        body = json.loads(req.data.decode()); sent.append(body)
        dims = tuple(d["name"] for d in body.get("dimensions", []))
        rs = rs_map.get(dims, [])
        rows=[{"dimensionValues":[{"value":v} for v in r[:-1]],
               "metricValues":[{"value":str(r[-1])}]} for r in rs]
        class R:
            def read(self): return json.dumps({"rows":rows}).encode()
            def __enter__(self): return self
            def __exit__(self,*a): return False
        return R()
    return fake
sh.load_sheets_client = lambda: type("M",(),{"load_credentials":staticmethod(lambda:{}),
  "access_token":staticmethod(lambda i,scope=None:"t")})()
def run(argv):
    sys.argv=argv; buf=io.StringIO()
    with contextlib.redirect_stdout(buf): sh.main()
    return buf.getvalue()

ok=True
def chk(l,c,e=""):
    global ok
    print(("PASS " if c else "FAIL ")+l+(("  "+str(e)) if e else ""))
    if not c: ok=False

# 1. --param だけ（イベント指定なし）
sent.clear()
urllib.request.urlopen = mk({("hostName","pagePath"): [("lp.onehitter.jp","/mizumawari/",9)],
                             ("date",): [("20260918",9)]})
out = run(["x","--param","traffic_src=ig","--days","20","--daily"])
f = sent[0]["dimensionFilter"]
chk("素の名前が customEvent: に解決される",
    f["filter"]["fieldName"]=="customEvent:traffic_src", json.dumps(f,ensure_ascii=False))
chk("見出しに --param が出る", "`traffic_src=ig` の出どころ" in out, out[:80])

# 2. --event と --param の両方 → andGroup
sent.clear()
urllib.request.urlopen = mk({("hostName","pagePath"): []})
out = run(["x","--event","page_view","--param","traffic_src=fb","--days","20"])
f = sent[0]["dimensionFilter"]
names = [e["filter"]["fieldName"] for e in f["andGroup"]["expressions"]]
chk("両方指定で andGroup になる", names==["eventName","customEvent:traffic_src"], names)
chk("0件のとき、記録開始前かもしれないと注意する",
    "登録から24〜48時間" in out, out[-160:])

# 3. 標準の次元はそのまま
sent.clear()
urllib.request.urlopen = mk({("hostName","pagePath"): [("one-hitter.jp","/",3)]})
run(["x","--event","page_view","--param","country=Japan","--days","7"])
names = [e["filter"]["fieldName"] for e in sent[0]["dimensionFilter"]["andGroup"]["expressions"]]
chk("country はそのまま（customEvent: を付けない）", names[1]=="country", names)

# 4. 形が違うとき止まる
try:
    run(["x","--param","traffic_src"]); chk("名前=値 でなければ止まる", False)
except SystemExit as e:
    chk("名前=値 でなければ止まる", "名前=値" in str(e), str(e))

print("\n"+("すべて通りました" if ok else "失敗あり")); sys.exit(0 if ok else 1)
import contextlib, importlib.util, io, json, pathlib, sys, urllib.request
ROOT = pathlib.Path("/home/user/one-marketing")
spec = importlib.util.spec_from_file_location("sh", ROOT/"tools"/"ga4-event-shirabe.py")
sh = importlib.util.module_from_spec(spec); spec.loader.exec_module(sh)
sent = []
def mk(rs_map):
    def fake(req, timeout=None):
        body = json.loads(req.data.decode()); sent.append(body)
        dims = tuple(d["name"] for d in body.get("dimensions", []))
        rs = rs_map.get(dims, [])
        rows=[{"dimensionValues":[{"value":v} for v in r[:-1]],
               "metricValues":[{"value":str(r[-1])}]} for r in rs]
        class R:
            def read(self): return json.dumps({"rows":rows}).encode()
            def __enter__(self): return self
            def __exit__(self,*a): return False
        return R()
    return fake
sh.load_sheets_client = lambda: type("M",(),{"load_credentials":staticmethod(lambda:{}),
  "access_token":staticmethod(lambda i,scope=None:"t")})()
def run(argv):
    sys.argv=argv; buf=io.StringIO()
    with contextlib.redirect_stdout(buf): sh.main()
    return buf.getvalue()

ok=True
def chk(l,c,e=""):
    global ok
    print(("PASS " if c else "FAIL ")+l+(("  "+str(e)) if e else ""))
    if not c: ok=False

# 1. --param だけ（イベント指定なし）
sent.clear()
urllib.request.urlopen = mk({("hostName","pagePath"): [("lp.onehitter.jp","/mizumawari/",9)],
                             ("date",): [("20260918",9)]})
out = run(["x","--param","traffic_src=ig","--days","20","--daily"])
f = sent[0]["dimensionFilter"]
chk("素の名前が customEvent: に解決される",
    f["filter"]["fieldName"]=="customEvent:traffic_src", json.dumps(f,ensure_ascii=False))
chk("見出しに --param が出る", "`traffic_src=ig` の出どころ" in out, out[:80])

# 2. --event と --param の両方 → andGroup
sent.clear()
urllib.request.urlopen = mk({("hostName","pagePath"): []})
out = run(["x","--event","page_view","--param","traffic_src=fb","--days","20"])
f = sent[0]["dimensionFilter"]
names = [e["filter"]["fieldName"] for e in f["andGroup"]["expressions"]]
chk("両方指定で andGroup になる", names==["eventName","customEvent:traffic_src"], names)
chk("0件のとき、記録開始前かもしれないと注意する",
    "登録から24〜48時間" in out, out[-160:])

# 3. 標準の次元はそのまま
sent.clear()
urllib.request.urlopen = mk({("hostName","pagePath"): [("one-hitter.jp","/",3)]})
run(["x","--event","page_view","--param","country=Japan","--days","7"])
names = [e["filter"]["fieldName"] for e in sent[0]["dimensionFilter"]["andGroup"]["expressions"]]
chk("country はそのまま（customEvent: を付けない）", names[1]=="country", names)

# 4. 形が違うとき止まる
try:
    run(["x","--param","traffic_src"]); chk("名前=値 でなければ止まる", False)
except SystemExit as e:
    chk("名前=値 でなければ止まる", "名前=値" in str(e), str(e))

print("\n"+("すべて通りました" if ok else "失敗あり")); sys.exit(0 if ok else 1)
