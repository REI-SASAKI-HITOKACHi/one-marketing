# 出来上がったPDFファイルそのものを検査する。問題があれば終了コード1
import sys, os, pymupdf
PDF = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '協力店ネット_企画書.pdf')
MM = 72/25.4
d = pymupdf.open(PDF)
issues = []
BANNED = ['網','ワンヒッター','本舗','ベアーズ','競業','石田','木村']
for pi, pg in enumerate(d):
    n = pi + 1
    R = pg.rect
    lines = []
    full = []
    for b in pg.get_text('dict')['blocks']:
        if b.get('type') != 0: continue
        bl = []
        for ln in b['lines']:
            t = ''.join(sp['text'] for sp in ln['spans']).strip()
            if t: bl.append((pymupdf.Rect(ln['bbox']), t, round(ln['spans'][0]['size'],1)))
        lines += [(r, t) for r, t, _ in bl]
        full += bl
    # 折り返しの組（ブロックをまたいで探す）：同じ左端・同じ文字サイズで、すぐ下にある行
    import re as _re
    for pr, pt, ps in full:
        h = pr.y1 - pr.y0
        nxt = [(lr, lt, ls) for lr, lt, ls in full if abs(lr.x0 - pr.x0) < 2.5 and ls == ps and pr.y1 - 1.5 <= lr.y0 <= pr.y1 + 0.9*h]
        if not nxt: continue
        lr, lt, ls = min(nxt, key=lambda x: x[0].y0)
        # 3文字以下だけの行（前の行が長いときだけ＝折り返し）
        is_last = not any(abs(r.x0 - lr.x0) < 2.5 and z == ls and lr.y1 - 1.5 <= r.y0 <= lr.y1 + 0.9*h for r, _, z in full)
        if len(pt) >= 6 and len(lt) <= 3 and is_last and pr.width > 2.5*lr.width:
            issues.append(f'p{n}: 3文字以下だけの行「{pt[-6:]}／{lt}」')
        # カタカナ語の途中での改行（例：メ／ニュー）
        if _re.search('[ァ-ヶ]$', pt) and _re.match('[ァ-ヶー]', lt):
            issues.append(f'p{n}: 語の途中で改行「{pt[-6:]}／{lt[:6]}」')
    # 禁止語
    txt = pg.get_text()
    for w in BANNED:
        if w in txt: issues.append(f'p{n}: 禁止語「{w}」')
    # ページ外
    for r, t in lines:
        if r.x0 < -0.5 or r.y0 < -0.5 or r.x1 > R.width + 0.5 or r.y1 > R.height + 0.5:
            issues.append(f'p{n}: ページ外の文字「{t[:12]}」')
    # フッターとの重なり：下端 12mm の帯に入る文字はフッターだけ
    foot_top = R.height - 9.5*MM
    feet = [r for r, t in lines if r.y0 >= foot_top]
    ftop = min((r.y0 for r in feet), default=R.height)
    for r, t in lines:
        if r.y0 < foot_top and r.y1 > ftop - 2.5*MM:
            issues.append(f'p{n}: フッターに近すぎる／重なる「{t[:14]}」')
    # 文字同士の重なり
    for i in range(len(lines)):
        for j in range(i+1, len(lines)):
            a, b = lines[i][0], lines[j][0]
            inter = a & b
            if not inter.is_empty and inter.width > 1.5 and inter.height > 1.5:
                issues.append(f'p{n}: 文字が重なる「{lines[i][1][:10]}」と「{lines[j][1][:10]}」')
    # 塗りの四角（枠）からの文字のはみ出し：行の始点を含むいちばん小さい枠に、行全体が収まっているか
    boxes = []
    for dr in pg.get_drawings():
        if dr.get('fill') is None: continue
        r = pymupdf.Rect(dr['rect'])
        if r.width < 8*MM or r.height < 5*MM: continue
        if r.width > R.width - 2 and r.height > R.height - 2: continue
        boxes.append(r)
    for r, t in lines:
        p = pymupdf.Point(r.x0 + 1, (r.y0 + r.y1) / 2)
        cands = [b for b in boxes if b.contains(p)]
        if not cands: continue
        bx = min(cands, key=lambda b: b.width * b.height)
        if r.x1 > bx.x1 + 0.8 or r.y1 > bx.y1 + 0.8 or r.y0 < bx.y0 - 0.8:
            issues.append(f'p{n}: 枠からはみ出す「{t[:14]}」')
print(f'PDF {d.page_count}ページ')
if issues:
    print(f'問題 {len(set(issues))}件'); print('\n'.join(sorted(set(issues), key=lambda x: int(x.split(":")[0][1:]))))
    sys.exit(1)
print('PDF検査：問題なし')
