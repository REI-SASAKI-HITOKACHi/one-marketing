# -*- coding: utf-8 -*-
"""販売管理費の式を代数で展開して、二重計上額を確定する。"""
import importlib.util, os, urllib.parse
ROOT="/home/user/one-marketing"
spec=importlib.util.spec_from_file_location("sc",os.path.join(ROOT,"tools","sheets_client.py"))
sc=importlib.util.module_from_spec(spec); spec.loader.exec_module(sc)
tok=sc.access_token(sc.load_credentials())
SS="1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64"
def get(tab,rng,mode="UNFORMATTED_VALUE"):
    return sc.call(tok,f"/{SS}/values/{urllib.parse.quote(tab+'!'+rng,safe='')}",
                   query={"valueRenderOption":mode}).get("values",[])
LAY={6:(72,80,81,78,71),7:(86,94,95,92,85)}
print(f"{'月':>3} {'SUM明細':>10} {'販管費(現)':>11} {'販管費(正)':>11} {'二重':>8} {'検算':>6}")
tot=0
for m in range(1,13):
    tab=f"{m}月_支出/成績"
    g,r,h,jin,hi = LAY.get(m,(53,61,62,59,52))
    V=get(tab,"A1:N120")
    def c(row,col):
        rr=V[row-1] if row-1<len(V) else []
        v=rr[col] if col<len(rr) else 0
        try: return float(v)
        except: return 0.0
    detail=sum(c(i,5) for i in range(2,hi+1))
    fixed=c(9,5)+c(10,5)+c(11,5)+c(12,5)
    h38=c(r,7); h10=c(r,8); jinken=c(jin,5)
    seiri = detail + h38 + h10 + fixed - jinken     # 式を展開した値
    genzai = c(h,1)                                  # シート上の販売管理費
    tadashii = seiri - fixed                         # 固定分を二重に足さない場合
    ok = "OK" if abs(seiri-genzai)<1 else f"差{seiri-genzai:,.0f}"
    tot += fixed
    print(f"{m:>3} {detail:>10,.0f} {genzai:>11,.0f} {tadashii:>11,.0f} {fixed:>8,.0f} {ok:>6}")
print(f"\n★ 二重計上の年間合計: {tot:,.0f}円")
