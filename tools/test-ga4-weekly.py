#!/usr/bin/env python3
"""tools/ga4-weekly.py を、偽のGA4 Data APIで動かして確かめる。

    python3 tools/test-ga4-weekly.py

**鍵は要らない。本物のGA4には一切つながらない。**

見ているのは4つ：
  1. LPのセッションが**複数ホストぶん合算**される（lp.onehitter.jp と netlify.app）
  2. 予約フォームが**3ホストぶん合算**される（足し忘れると数字が小さく出る）
  3. **公式サイト（one-hitter.jp）の数字が混ざらない**（同一プロパティの別ストリームなので）
  4. --json が落ちない（_sessions の鍵がタプルなので、一度ここで落ちた）
"""
import importlib.util, io, json, sys, urllib.request, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("w", ROOT / "tools" / "ga4-weekly.py")

w = importlib.util.module_from_spec(spec); spec.loader.exec_module(w)

CALLS = []
def fake(req, timeout=None):
    body = json.loads(req.data.decode()); CALLS.append(body)
    dims = [d["name"] for d in body.get("dimensions", [])]
    start = body["dateRanges"][0]["startDate"]
    n = 1 if start.endswith("07") else 2      # 週で数字を変える
    if dims == ["hostName", "landingPagePlusQueryString"]:
        rs = [("lp.onehitter.jp","/mizumawari/?src=qr",10*n),
              ("one-hitter-lp.netlify.app","/mizumawari/",5*n),
              ("lp.onehitter.jp","/aircon/",7*n),
              ("lp.onehitter.jp","/nenmatsu/",3*n),
              ("lp.onehitter.jp","/survey/",2*n),
              ("yoyaku.onehitter.jp","/",20*n),
              ("onehitter-yoyaku.netlify.app","/",6*n),
              ("one-hitter-booking.netlify.app","/",4*n),
              ("one-hitter.jp","/menu/",99*n)]   # 公式サイトは混ぜない
        rows=[{"dimensionValues":[{"value":a},{"value":b}],"metricValues":[{"value":str(c)}]} for a,b,c in rs]
    elif dims == ["eventName"]:
        rows=[{"dimensionValues":[{"value":k}],"metricValues":[{"value":str(v*n)}]}
              for k,v in (("generate_lead",2),("phone_click",9),("line_click",1),("page_view",100))]
    else:  # customEvent:traffic_src
        if CALLS[-1].get("_fail"): raise SystemExit(1)
        rows=[{"dimensionValues":[{"value":k}],"metricValues":[{"value":str(v*n)}]}
              for k,v in (("qr",8),("direct",5))]
    class R(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self,*a): return False
    return R(json.dumps({"rows":rows}).encode())
urllib.request.urlopen = fake
w.load_sheets_client = lambda: type("M",(),{
  "load_credentials": staticmethod(lambda: {}),
  "access_token": staticmethod(lambda i, scope=None: "t")})()

sys.argv = ["w", "--week", "2026-09-07"]
w.main()
print("\n" + "="*50)
# 検算：/mizumawari/ は2ホストぶん合算、予約は3ホスト合算、公式サイトは混ざらない
sys.argv = ["w", "--week", "2026-09-07", "--json"]
import contextlib
buf = io.StringIO()
with contextlib.redirect_stdout(buf): w.main()
d = json.loads(buf.getvalue())["今週"]
assert d["LP /mizumawari/"] == 10+5, d["LP /mizumawari/"]
assert d["予約フォーム（全ホスト合計）"] == 20+6+4, d["予約フォーム（全ホスト合計）"]
assert d["申込（generate_lead）"] == 2 and d["電話クリック（phone_click）"] == 9
assert all("menu" not in str(k) for k in d if not k.startswith("_"))
print("検算OK：/mizumawari/=15（2ホスト合算）、予約=30（3ホスト合算）、公式サイトは混ざらない")
