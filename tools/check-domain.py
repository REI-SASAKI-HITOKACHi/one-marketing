#!/usr/bin/env python3
"""onehitter.jp の切替状況を1回ぶん確認して、進められるところまで進める。

  1. ネームサーバーが nsone（Netlify DNS）を向いたか（Google の DoH で見る）
  2. yoyaku.onehitter.jp の A が引けるか
  3. Netlify の HTTPS 証明書（無ければ発行を要求）
  4. Search Console のドメイン所有権（TXT が引けたら verify）
  5. https://yoyaku.onehitter.jp/ が 200 で返り、check-public-page が通るか

使い方: python3 tools/check-domain.py        # 何度実行しても安全（冪等）
終了コード: 0 = 全部そろった／1 = まだ
"""
import json, os, sys, urllib.request, urllib.parse, importlib.util, subprocess
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOMAIN, HOST, SITE = 'onehitter.jp', 'yoyaku.onehitter.jp', '39408b76-e5d0-46f4-bee8-418ef6cfb36a'
NS_KITAI = 'nsone.net'

def doh(name, t):
    r = json.load(urllib.request.urlopen(f'https://dns.google/resolve?name={name}&type={t}', timeout=30))
    return [a['data'] for a in r.get('Answer', []) if a.get('type') == {'NS': 2, 'A': 1, 'TXT': 16}[t]]

ok = True
ns = doh(DOMAIN, 'NS'); ns_ok = any(NS_KITAI in x for x in ns)
print('1. NS:', ns, '→', 'Netlify' if ns_ok else 'まだムームー'); ok &= ns_ok
a = doh(HOST, 'A'); print('2. A:', a); ok &= bool(a)

tok = open(os.path.expanduser('~/.config/one-hitter/netlify-token.txt')).read().strip()
def nl(path, method='GET', payload=None):
    req = urllib.request.Request('https://api.netlify.com/api/v1' + path,
                                 data=json.dumps(payload).encode() if payload is not None else None, method=method)
    req.add_header('Authorization', 'Bearer ' + tok)
    if payload is not None: req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req, timeout=60) as r: return json.load(r)
    except urllib.error.HTTPError as e:
        return {'error': e.code, 'body': e.read()[:200].decode('utf-8', 'replace')}
ssl = nl(f'/sites/{SITE}/ssl')
state = (ssl or {}).get('state')
if state != 'issued' and ns_ok and a:
    ssl = nl(f'/sites/{SITE}/ssl', 'POST', {}); state = (ssl or {}).get('state') or ssl
print('3. HTTPS:', state); ok &= state == 'issued'

# Search Console（サービスアカウントで verify。オーナーは前回と同様に owner 追加）
spec = importlib.util.spec_from_file_location('sc', f'{ROOT}/tools/sheets_client.py')
sc = importlib.util.module_from_spec(spec); sys.modules['sc'] = sc; spec.loader.exec_module(sc)
g = sc.access_token(sc.load_credentials(), 'https://www.googleapis.com/auth/siteverification')
def sv(path, method='GET', payload=None):
    req = urllib.request.Request('https://www.googleapis.com/siteVerification/v1' + path,
                                 data=json.dumps(payload).encode() if payload is not None else None, method=method)
    req.add_header('Authorization', 'Bearer ' + g); req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req, timeout=60) as r: return json.load(r)
    except urllib.error.HTTPError as e:
        return {'error': e.code, 'body': e.read()[:200].decode('utf-8', 'replace')}
txt = doh(DOMAIN, 'TXT'); print('4. TXT:', [t[:40] for t in txt])
gsc = False
if any('google-site-verification' in t for t in txt):
    r = sv('/webResource?verificationMethod=DNS_TXT', 'POST', {'site': {'type': 'INET_DOMAIN', 'identifier': DOMAIN}})
    if r.get('id'):
        gsc = True
        owners = set(r.get('owners', []))
        if 'case.foot.kid@gmail.com' not in owners:
            sv('/webResource/' + urllib.parse.quote(r['id'], safe=''), 'PUT',
               {'id': r['id'], 'site': r['site'], 'owners': sorted(owners | {'case.foot.kid@gmail.com'})})
        print('   Search Console: 所有権OK（オーナー追加済み）')
    else:
        print('   Search Console:', r)
else:
    print('   Search Console: TXT がまだ引けない')
ok &= gsc

if state == 'issued':
    try:
        with urllib.request.urlopen('https://' + HOST + '/', timeout=30) as r:
            print('5. https:', r.status)
            rc = subprocess.run([sys.executable, f'{ROOT}/tools/check-public-page.py', 'https://' + HOST + '/'], capture_output=True, text=True)
            print('   check-public-page:', 'OK' if rc.returncode == 0 else 'NG\n' + rc.stdout + rc.stderr)
            ok &= rc.returncode == 0
    except Exception as e:
        print('5. https: まだ', e); ok = False
print('\n結果:', '全部そろった' if ok else 'まだ')
sys.exit(0 if ok else 1)
