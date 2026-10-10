#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""11月早期予約SMSの本文を、台帳の個別情報（回数・前回の時期とメニュー・経過・次のおすすめ）で1人ずつ作る（表示のみ・シートには書かない）。

2026-10-10 オーナー（業務連絡LINE）「送付する文言がクソだから再考して。一流のマーケターとして洗練された文章にするんだよ。
あと、個別情報がせっかくあるんだから端的かつ効果的に活用して。全文へ反映させるまえに修正した内容をここで報告して。」
タカラサービス様経由（業務提携）のお客様は外す（9/22 決定）。3通（210字）以内・URL/電話が通の境目をまたがない形を自動で選ぶ。
    python3 tools/nov-sms-kobetsu.py 出力.json   # 出力に電話番号は入らない
"""
import sys,json,re,urllib.parse; sys.path.insert(0,'/home/user/one-marketing/tools')
import sheets_client as sc
T=sc.access_token(sc.load_credentials()); SS='1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64'
rs=["'11月早期予約SMS_送信'!A6:G40","'顧客管理台帳'!A16:AH3000"]
vr=[v.get('values',[]) for v in sc.call(T,f"/{SS}/values:batchGet?"+"&".join("ranges="+urllib.parse.quote(r,safe="") for r in rs))['valueRanges']]
tab,dai=vr
num=lambda x: re.sub(r"\D","",x or "")
Y="https://yoyaku.onehitter.jp/?src=sms_nov"; P="https://lp.onehitter.jp/privacy/"; TEL="080-8043-8259"
MEI={"エアコン(ロボ)":"お掃除機能付きエアコン","エアコン(ノーマル)":"エアコン","置き型業務用エアコン":"業務用エアコン","定期清掃":"定期清掃","換気扇":"換気扇","浴室乾燥機":"浴室乾燥機","浴室":"浴室","洗濯機(ノーマル)":"洗濯機","空室":"お部屋の清掃","まるごと(備考に内容)":"まるごと清掃"}
def menus(s):
    out=[]
    for part in s.split("／"):
        m=re.match(r"(.+?)×(\d+)",part)
        if not m: continue
        nm=MEI.get(m.group(1),m.group(1)); n=int(m.group(2))
        out.append((nm,n))
    return out
rows=[]
for r in tab:
    if len(r)<6: continue
    tel=num(r[2]); h=[d+['']*34 for d in dai if num((d+['']*4)[3])==tel]; h=h[0]
    sei=r[5].split("\n")[0].replace("さま","").strip()
    kai=int(num(h[6]) or 0); kei=float(h[12] or 0); last=h[11]; y,mo=last[:4],int(last[5:7])
    ms=menus(h[30]); ac=sum(n for nm,n in ms if "エアコン" in nm)
    tsugi=h[29].replace("・","や")
    if "タカラ" in h[1]+h[31] or h[15]=="業務提携":
        rows.append((r[0],r[1],"除外（タカラサービス様経由のお客様）","")); continue
    # 1行目：お礼（事実だけ・短く）
    when=(f"{mo}月" if y=="2026" else f"昨年{mo}月")
    if kai>=3: rei=f"{kai}回のご依頼、いつもありがとうございます。"
    elif kai==2: rei=f"{when}もありがとうございました。"
    else:
        m0=(ms[0][0] if ms else "ご依頼"); m0=("エアコン洗浄" if "エアコン" in m0 else m0)
        rei=f"{when}の{m0}、ありがとうございました。"
    # 2行目：その人への提案（台帳のメニュー・経過・次のおすすめ）
    if ac and kei>=9: tei=f"前回のエアコン洗浄から{int(kei)}か月、暖房前の洗いどきです。"
    elif ac: tei=f"次は{h[29]}を、年末の混雑前にいかがですか。"
    else: tei="年末の混雑前に、エアコンや水まわりはいかがですか。"
    def kumu(rei):
        head=f"{sei}様\nワンヒッターの渡辺です。{rei}\n{tei}\n11月のご予約は10%引き（1箇所）。12月は繁忙期料金です。\n"
        return [head+f"予約 {Y}\n電話 {TEL}\n個人情報 {P}\nご不要の方はご返信ください",
                head+f"電話 {TEL}\n予約 {Y}\n個人情報 {P}\nご不要の方はご返信ください",
                head+f"予約 {Y}\n個人情報 {P}\n電話 {TEL}\nご不要の方はご返信ください"]
    def warui(b):
        return len(b)>210 or any(any(b.find(kw)<k<b.find(kw)+len(kw) for k in (70,140)) for kw in (Y,P,TEL))
    kouho=kumu(rei)+kumu(f"{when}はありがとうございました。")+kumu("ありがとうございました。")
    b=next((x for x in kouho if not warui(x)), kouho[0])
    ng=[]
    if len(b)>210: ng.append(f"{len(b)}字")
    for kw in (Y,P,TEL):
        u=b.find(kw)
        if any(u<k<u+len(kw) for k in (70,140)): ng.append(kw[:10]+"が境目")
    rows.append((r[0],r[1],b,ng))
json.dump(rows,open(sys.argv[1],'w',encoding='utf-8'),ensure_ascii=False)
for x in rows: print(x[0],x[1],len(x[2]),x[3]); 
for x in rows:
    if x[3]!='' : print(x[2]); print('---')
