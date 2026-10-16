#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""送信タブの宛先を、送る前日に台帳で照合し直す（表示のみ・シートは書かない）。

    python3 tools/sms-saishougou.py --tab 11月SMS2便_送信

各行について：名乗り（atesaki_ok＝台帳の最新の施工が自社）／台帳のクレーム履歴（AG）／今日より先の予約／
作成後の施工、を確かめ、変わった行の行番号と理由だけを出す（氏名・電話は出さない）。変わった行は送らない。
"""
import sys, importlib.util, json, os, re, datetime, urllib.parse, time, collections
import argparse
ap=argparse.ArgumentParser(); ap.add_argument("--tab", required=True); A=ap.parse_args(); sys.argv=[sys.argv[0]]; sys.path.insert(0,"tools")
s=importlib.util.spec_from_file_location("dk","tools/daichou-koushin.py"); dk=importlib.util.module_from_spec(s); s.loader.exec_module(dk)
import meigi_check as MC
dsk=MC._load(); o_=dsk.sc.call
def call(*a,**k):
    for i in range(8):
        try: return o_(*a,**k)
        except SystemExit as e:
            if "429" not in str(e) or i==7: raise
            time.sleep(20*(i+1))
dsk.sc.call=call
hyou=dsk.meigi_hyou(); dsk.jobs_yomu(saidoku=False)
sc=dk._sc(); tok=sc.access_token(sc.load_credentials()); SS=dk.SS
tab=dk._api(sc,tok,f"/{SS}/values/{urllib.parse.quote(A.tab+'!A6:H300',safe='')}").get("values",[])
L=dk._api(sc,tok,f"/{SS}/values/{urllib.parse.quote('顧客管理台帳!A16:AH1200',safe='')}").get("values",[])
claim={dk.tn(r[3]) for r in L if len(r)>32 and str(r[32]).strip() and len(r)>3 and dk.tn(r[3])}
jobs=dk.jobs_yomu(sc,tok); today=datetime.date.today()
c=collections.Counter(); bad=[]
for i,r in enumerate(tab, start=6):
    if len(r)<3: continue
    t=dk.tn(r[2]); n=r[1]
    ok,riyuu=MC.atesaki_ok(hyou,t,n,"自社")
    why=[]
    if not ok: why.append("名乗り："+riyuu)
    if t in claim: why.append("クレーム履歴あり")
    if any(x["d"]>today and (x["t"]==t or x["n"]==dk.nn(n)) for x in jobs): why.append("予約が入った")
    if any(x["d"]>datetime.date.today()-datetime.timedelta(days=7) and x["d"]<=today and (x["t"]==t or x["n"]==dk.nn(n)) for x in jobs): why.append("直近7日に施工")
    c["OK" if not why else "変わった"]+=1
    if why: bad.append((i, r[0][:3], "／".join(why)))
print(dict(c)); 
for b in bad: print("  行",b[0],b[1],b[2])
