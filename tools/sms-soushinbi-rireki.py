#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SMS送信タブの E列「送信済み」が付いた日を、スプレッドシートの変更履歴（Drive API revisions）から出す（表示のみ）。

    SP=<作業用フォルダ> python3 tools/sms-soushinbi-rireki.py

現場に「送った日」を書かせないためのもの（オーナー 10/24）。各版を ODS で取り出し、タブごとに E列が空→「送信済み」に
変わった最初の版の時刻を出す。版は数時間ぶんをまとめるので、人ごとの時刻ではなく「印が付いた日」になる。
ODS ではタブ名の「/」が消えるので、TABS は「/」を抜いた名前で書く。結果は $SP/rev/hist.json。
"""
import sys,json,urllib.request,zipfile,io,os
import xml.etree.ElementTree as ET
sys.path.insert(0,"tools"); import sheets_client as sc
FID="1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64"
t=sc.access_token(sc.load_credentials(),"https://www.googleapis.com/auth/drive.readonly")
H={"Authorization":"Bearer "+t}
rv=json.loads(urllib.request.urlopen(urllib.request.Request(f"https://www.googleapis.com/drive/v3/files/{FID}/revisions?pageSize=1000&fields=revisions(id,modifiedTime,exportLinks,lastModifyingUser/displayName)",headers=H)).read())["revisions"]
rv=[x for x in rv if x["modifiedTime"]>=os.environ.get("SINCE","2026-10-20T00:00")]
TABS=["【1便目】11月SMS_送信（17名・1020）","【2便目】11月SMS_送信（83名・1020と1027）"]
NS={"table":"urn:oasis:names:tc:opendocument:xmlns:table:1.0","text":"urn:oasis:names:tc:opendocument:xmlns:text:1.0"}
T="{%s}"%NS["table"]
def cells(row):
    out=[]
    for c in row:
        if c.tag not in (T+"table-cell",T+"covered-table-cell"): continue
        n=int(c.get(T+"number-columns-repeated","1"))
        txt="\n".join("".join(p.itertext()) for p in c.findall("text:p",NS))
        out+= [txt]*min(n,12)
        if len(out)>=12: break
    return out
def read(rid,link):
    p=f"{os.environ['SP']}/rev/{rid}.ods"
    if not os.path.exists(p):
        open(p,"wb").write(urllib.request.urlopen(urllib.request.Request(link,headers=H),timeout=300).read())
    z=zipfile.ZipFile(p); res={}
    for ev,el in ET.iterparse(z.open("content.xml"),events=("end",)):
        if el.tag==T+"table":
            nm=el.get(T+"name")
            if nm in TABS:
                rows=[];
                for r in el.iter(T+"table-row"):
                    n=int(r.get(T+"number-rows-repeated","1")); cs=cells(r)
                    rows+=[cs]*min(n,5)
                res[nm]=rows
            el.clear()
    return res
hist={}
for x in rv:
    try: res=read(x["id"],x["exportLinks"]["application/x-vnd.oasis.opendocument.spreadsheet"])
    except Exception as e: print("NG",x["id"],str(e)[:100]); continue
    for nm,rows in res.items():
        for i,r in enumerate(rows,1):
            if i<6 or len(r)<5: continue
            hist.setdefault((nm,i),[]).append((x["modifiedTime"],r[4],x.get("lastModifyingUser",{}).get("displayName")))
    print("版",x["id"],x["modifiedTime"],{k[:6]:sum(1 for r in v[5:] if len(r)>4 and r[4]) for k,v in res.items()},flush=True)
json.dump({f"{k[0]}|{k[1]}":v for k,v in hist.items()},open(f"{os.environ['SP']}/rev/hist.json","w"),ensure_ascii=False)

for k,v in sorted(json.load(open(f"{os.environ['SP']}/rev/hist.json")).items()):
    first=next((t for t,e,u in v if e=="送信済み"),None)
    if first: print(k.split("|")[0][:6], "行", k.split("|")[1], "送信済みが付いた最初の版", first)
