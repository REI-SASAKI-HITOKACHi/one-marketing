#!/usr/bin/env python3
"""2027年の月次計画（売上〜経常利益）を計算する。

【なぜこの形か】
  和真さん向けの説明資料と、来年度のスプレッドシートと、docs/2027-数値目標.md が
  同じ数字を使う必要がある。手で3回書くと必ずズレるので、計算はここ1箇所に置く。

  係数はすべて 2026年の実績から取っている（出典は KEISU の各コメント）。
  推定を入れた箇所には「仮置き」と書いてある。

【使い方】
  python3 tools/plan2027.py            # 中立（正式目標）の月次表を出す
  python3 tools/plan2027.py --案 保守
  python3 tools/plan2027.py --案 攻め
  python3 tools/plan2027.py --全案      # 3案の年計サマリー
  python3 tools/plan2027.py --json      # 機械可読（スプレッドシート生成用）
"""
import argparse
import json
import sys

TSUKI = list(range(1, 13))

# ---------------------------------------------------------------
# 2026年の実績から取った係数
# ---------------------------------------------------------------
KEISU = {
    # 資材費。2026年の原価内訳 エアコン69,015＋換気扇1,936＋浴室1,639＝72,590円 ÷ 323件
    '資材費_円per件': 225,
    # 協力業者へ回す案件の平均売価。
    # ⚠ おそうじ本舗の案件は外注できない（オーナー 2026-09-14）。だから協力業者に回せるのは
    #   自社案件のあふれ分だけで、売価はマッチングPFの単価帯ではなく全体平均に近くなる。
    '外注_売価_円per件': 40000,
    # 案A（売価の65%を支払う）。3案の比較は docs/2027-数値目標.md §6
    '外注_支払率': 0.65,
    # 販管費のうち毎月固定で出る分。2026年9月_支出/成績（当月は固定費のみ計上）の経費小計 F54
    '固定経費_円per月': 159708,
    # ロイヤリティの固定分。備考が「本舗固定」の4行の合計
    # （固定ロイ22,000／HITOWA HPC利用料22,000／HITOWAサイト保守4,400／HITOWAサポート1,650）
    'ロイヤリティ固定_円per月': 50050,
    # 本舗売上に連動するロイヤリティの実効率。
    # 2026年1〜8月の F62 ロイヤリティ実績 1,754,635 −固定 50,050×8 ＝1,354,235 ÷ 本舗売上 3,476,143
    # 内訳は 入札38%／チラシ・自店受け10%／toB・楽ラクーンは個別ロイ（率ではなく実額）の合計。
    # ⚠ CLAUDE.md の「27.6%」は2024年実績。2026年は個別ロイ案件が増えて実効率が上がっている
    'ロイヤリティ率_本舗売上': 0.39,
    # 融資返済。毎月同額
    '融資返済_円per月': 38059,
    # 変動経費（ガソリン・コインパーキング・紹介料・消耗品ほか）。
    # 2026年1〜8月の販管費 3,821,745 −固定経費×8 −ロイヤリティ実績 の残差 ÷ 売上
    'その他変動費率': 0.068,
    # 新規正社員の社会保険料（会社負担）。仮置き
    '社保率': 0.15,
}

# 新規正社員（オーナー決定 2026-09-13）
#   3月入社。試用期間6か月（3〜8月）は月30万。9月から35万。入社1年後（2028年3月）に40万を目指す。
SHINJIN = {
    '入社月': 3,
    '試用_月給_円': 300000,
    '試用_終了月': 8,
    '本採用_月給_円': 350000,
    '昇給目標_月給_円': 400000,   # 2028年3月から
    '採用費_装備_円': 500000,     # 1月20万・2月30万で計上
}

# 和真さんの報酬（2026年9月分から新制度）
#   固定給40万＋プール10万（3か月ごとに払い出し）。損益上は毎月50万で積む。
WATANABE_EN_PER_TSUKI = 500000

# おそうじ本舗経由の売上（2026-09-14 オーナー決定）
#   「本舗は伸ばさない。自然流入のみ＝今年度と同じ数字にするよ」
#   → 3案とも 2026年の着地見込みと同額で固定する。売上が伸びてもロイヤリティは増えない。
#   2026年着地見込み 17,000,000円（オーナー 2026-09-14）× 本舗比率 31.7%（1〜8月実績）
HONPO_URIAGE_NEN_EN = 5_390_000

# ---------------------------------------------------------------
# 3案。売上・件数の月配分は 2026年1〜8月実績＋2025年9〜12月実績の季節性から置き、
# 2026年8月の大型案件（1,841,740円）は再現前提にしないので季節性から外した。
# ---------------------------------------------------------------
AN = {
    '保守': {
        '売上_万': [130, 115, 160, 180, 225, 240, 210, 120, 135, 165, 175, 145],
        '件数':    [34,  30,  42,  47,  55,  59,  52,  32,  35,  43,  46,  38],
        '広告費_万': [5, 5, 2, 2, 3, 3, 3, 0, 0, 1, 1, 0],
        '外注件数': [0, 0, 3, 4, 7, 9, 6, 3, 3, 5, 6, 4],
        '補助人件費_万': [1, 1, 1, 2, 2, 2, 2, 1, 1, 2, 2, 2],
    },
    '中立': {
        '売上_万': [144, 128, 185, 226, 289, 340, 274, 160, 180, 232, 248, 194],
        '件数':    [37,  32,  46,  57,  70,  82,  68,  42,  46,  60,  64,  45],
        '広告費_万': [5, 5, 6, 6, 12, 12, 12, 3, 3, 7, 7, 2],
        '外注件数': [0, 0, 5, 8, 14, 18, 12, 5, 5, 10, 12, 11],
        '補助人件費_万': [2, 2, 2, 3, 4, 4, 4, 2, 2, 3, 4, 4],
    },
    '攻め': {
        '売上_万': [155, 140, 210, 270, 350, 410, 330, 200, 230, 290, 320, 295],
        '件数':    [40,  36,  52,  66,  83,  97,  79,  49,  56,  70,  77,  69],
        '広告費_万': [5, 5, 8, 8, 15, 15, 15, 4, 4, 10, 10, 1],
        '外注件数': [0, 0, 8, 14, 25, 32, 22, 10, 10, 20, 22, 17],
        '補助人件費_万': [2, 2, 3, 4, 5, 5, 5, 3, 3, 5, 5, 6],
    },
}

MAN = 10000  # 万円→円

# ---------------------------------------------------------------
# 2026年の着地見込み（オーナー 2026-09-14：売上 17,000,000円）
#   2027年と同じ係数で計算して、比べられる形にする。
#   和真さんの報酬だけは旧制度（経常利益×45%）なので別建てで引く。
# ---------------------------------------------------------------
KIJUN_2026 = {
    '売上': 17_000_000,
    '件数': 469,               # 1〜8月実績283件＋9〜12月186件（2025年同期の単価28,777円で換算）
    '本舗売上': HONPO_URIAGE_NEN_EN,
    '原価_人件費外注費': 1_057_635,   # 2026年1〜8月の実績（8月の876,135は外注費。オーナー 2026-09-14）
    '和真_配分率': 0.45,       # 旧制度
}


def kijun2026():
    k = KIJUN_2026
    shizai = k['件数'] * KEISU['資材費_円per件']
    genka = shizai + k['原価_人件費外注費']
    hankan = (KEISU['固定経費_円per月'] * 12
              + KEISU['ロイヤリティ固定_円per月'] * 12
              + round(k['本舗売上'] * KEISU['ロイヤリティ率_本舗売上'])
              + round(k['売上'] * KEISU['その他変動費率']))
    eigyou = k['売上'] - genka - hankan
    keijou = eigyou - KEISU['融資返済_円per月'] * 12
    watanabe = round(keijou * k['和真_配分率'])
    return {'売上': k['売上'], '件数': k['件数'], '原価': genka, '販管費': hankan,
            '営業利益': eigyou, '経常利益': keijou, '和真報酬': watanabe,
            '会社に残る': keijou - watanabe}


def bunki():
    """損益分岐点と、2026年並みの利益を残すライン（中立の費用構造で計算）。"""
    g = goukei(keisan('中立'))
    u = g['売上']
    kotei = (KEISU['固定経費_円per月'] * 12 + KEISU['ロイヤリティ固定_円per月'] * 12
             + g['販管_ロイヤリティ'] + g['販管_広告費'] + g['販管_人件費_和真']
             + g['販管_人件費_新人'] + g['販管_採用費装備'] + g['融資返済'])
    hendo = (g['原価_計'] + g['販管_その他変動費']) / u
    zanzon = 1 - hendo
    k26 = kijun2026()
    return {'固定費': kotei, '変動費率': hendo, '限界残存率': zanzon,
            '損益分岐点': round(kotei / zanzon),
            '2026年並み': round((kotei + k26['会社に残る']) / zanzon)}


def shinjin_kyuuyo_en(tsuki):
    """新規正社員の月給（円）。社会保険料は含まない。"""
    if tsuki < SHINJIN['入社月']:
        return 0
    if tsuki <= SHINJIN['試用_終了月']:
        return SHINJIN['試用_月給_円']
    return SHINJIN['本採用_月給_円']


def saiyouhi_en(tsuki):
    """採用費・装備。1月20万・2月30万。"""
    return {1: 200000, 2: 300000}.get(tsuki, 0)


def keisan(an_mei):
    a = AN[an_mei]
    gyou = []
    for i, t in enumerate(TSUKI):
        uriage = a['売上_万'][i] * MAN
        kensuu = a['件数'][i]
        # 本舗売上は年額で固定。月には、その案の売上の月構成比で割り振る
        honpo_uriage = round(HONPO_URIAGE_NEN_EN * a['売上_万'][i] / sum(a['売上_万']))

        # --- 原価 ---
        shizai = kensuu * KEISU['資材費_円per件']
        gaichu = round(a['外注件数'][i] * KEISU['外注_売価_円per件'] * KEISU['外注_支払率'])
        hojo = a['補助人件費_万'][i] * MAN
        genka = shizai + gaichu + hojo

        # --- 販売管理費 ---
        kotei = KEISU['固定経費_円per月']
        kotei_roi = KEISU['ロイヤリティ固定_円per月']
        royalty = round(honpo_uriage * KEISU['ロイヤリティ率_本舗売上'])
        koukoku = a['広告費_万'][i] * MAN
        watanabe = WATANABE_EN_PER_TSUKI
        sk = shinjin_kyuuyo_en(t)
        shinjin = round(sk * (1 + KEISU['社保率']))
        saiyou = saiyouhi_en(t)
        sonota = round(uriage * KEISU['その他変動費率'])
        hankan = kotei + kotei_roi + royalty + koukoku + watanabe + shinjin + saiyou + sonota

        eigyou = uriage - genka - hankan
        hensai = KEISU['融資返済_円per月']
        keijou = eigyou - hensai

        gyou.append({
            '月': t, '売上': uriage, '件数': kensuu, '平均単価': round(uriage / kensuu) if kensuu else 0,
            '本舗売上': honpo_uriage,
            '原価_資材費': shizai, '原価_外注費': gaichu, '原価_補助人件費': hojo, '原価_計': genka,
            '売上総利益': uriage - genka,
            '販管_固定経費': kotei, '販管_ロイヤリティ固定': kotei_roi, '販管_ロイヤリティ': royalty,
            '販管_広告費': koukoku, '販管_人件費_和真': watanabe, '販管_人件費_新人': shinjin,
            '販管_採用費装備': saiyou, '販管_その他変動費': sonota, '販管_計': hankan,
            '営業利益': eigyou, '融資返済': hensai, '経常利益': keijou,
            '外注件数': a['外注件数'][i],
        })
    return gyou


def goukei(gyou):
    g = {}
    for k in gyou[0]:
        if k in ('月', '平均単価'):
            continue
        g[k] = sum(r[k] for r in gyou)
    g['平均単価'] = round(g['売上'] / g['件数']) if g['件数'] else 0
    return g


def en(v):
    return f"{v:,}"


def hyou(an_mei):
    gyou = keisan(an_mei)
    g = goukei(gyou)
    shihanki = {1: (1, 3), 2: (4, 6), 3: (7, 9), 4: (10, 12)}

    print(f"# 2027年 月次計画（{an_mei}）  単位：円\n")
    midashi = ['月', '売上', '件数', '単価', '原価計', '販管費計', '営業利益', '経常利益', '累計経常']
    print('| ' + ' | '.join(midashi) + ' |')
    print('|' + '---|' * len(midashi))
    ruikei = 0
    for r in gyou:
        ruikei += r['経常利益']
        shime = ' ■四半期末' if r['月'] in (3, 6, 9, 12) else ''
        print(f"| {r['月']}月{shime} | {en(r['売上'])} | {r['件数']} | {en(r['平均単価'])} | "
              f"{en(r['原価_計'])} | {en(r['販管_計'])} | {en(r['営業利益'])} | {en(r['経常利益'])} | {en(ruikei)} |")
    print(f"| **年計** | **{en(g['売上'])}** | **{g['件数']}** | **{en(g['平均単価'])}** | "
          f"**{en(g['原価_計'])}** | **{en(g['販管_計'])}** | **{en(g['営業利益'])}** | **{en(g['経常利益'])}** | |")

    print("\n## 四半期")
    print('| 四半期 | 売上 | 件数 | 営業利益 | 経常利益 |')
    print('|---|---|---|---|---|')
    for q, (a, b) in shihanki.items():
        rs = [r for r in gyou if a <= r['月'] <= b]
        print(f"| Q{q}（{a}〜{b}月） | {en(sum(r['売上'] for r in rs))} | {sum(r['件数'] for r in rs)} | "
              f"{en(sum(r['営業利益'] for r in rs))} | {en(sum(r['経常利益'] for r in rs))} |")

    print("\n## 費目の年計")
    for k in ['原価_資材費', '原価_外注費', '原価_補助人件費', '販管_固定経費', '販管_ロイヤリティ固定',
              '販管_ロイヤリティ', '販管_広告費', '販管_人件費_和真', '販管_人件費_新人',
              '販管_採用費装備', '販管_その他変動費', '融資返済']:
        print(f"- {k}: {en(g[k])}")
    akaji = [r['月'] for r in gyou if r['経常利益'] < 0]
    print(f"\n赤字の月: {akaji if akaji else 'なし'}")


def zenan():
    print('| 案 | 売上 | 件数 | 平均単価 | 原価 | 販管費 | 営業利益 | 経常利益 | 赤字の月 |')
    print('|---|---|---|---|---|---|---|---|---|')
    for a in ['保守', '中立', '攻め']:
        gyou = keisan(a)
        g = goukei(gyou)
        akaji = [f"{r['月']}月" for r in gyou if r['経常利益'] < 0]
        print(f"| {a} | {en(g['売上'])} | {g['件数']} | {en(g['平均単価'])} | {en(g['原価_計'])} | "
              f"{en(g['販管_計'])} | {en(g['営業利益'])} | {en(g['経常利益'])} | {'・'.join(akaji) or 'なし'} |")


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--案', default='中立', choices=list(AN))
    p.add_argument('--全案', action='store_true')
    p.add_argument('--json', action='store_true')
    a = p.parse_args()
    if a.json:
        json.dump({k: {'月次': keisan(k), '年計': goukei(keisan(k))} for k in AN},
                  sys.stdout, ensure_ascii=False, indent=1)
        return
    if getattr(a, '全案'):
        zenan()
        return
    hyou(getattr(a, '案'))


if __name__ == '__main__':
    main()


# ---------------------------------------------------------------
# HTML 断片の書き出し（和真さん向け資料・スプレッドシート生成が同じ数字を使うため）
# ---------------------------------------------------------------
def html_hyou(an_mei):
    """月次P/Lの詳細表（HTML）。四半期末の行に class="q" が付く。"""
    gyou = keisan(an_mei)
    g = goukei(gyou)
    retsu = [
        ('売上', '売上'), ('件数', '件数'), ('平均単価', '単価'),
        ('原価_資材費', '資材費'), ('原価_外注費', '外注費'), ('原価_補助人件費', '補助人件費'),
        ('原価_計', '原価計'), ('売上総利益', '売上総利益'),
        ('販管_人件費_和真', '人件費(和真)'), ('販管_人件費_新人', '人件費(新人)'),
        ('販管_採用費装備', '採用・装備'), ('販管_広告費', '広告費'),
        ('販管_ロイヤリティ', 'ロイヤリティ(変動)'), ('販管_ロイヤリティ固定', 'ロイヤリティ(固定)'),
        ('販管_固定経費', '固定経費'), ('販管_その他変動費', '変動経費'),
        ('販管_計', '販管費計'), ('営業利益', '営業利益'), ('融資返済', '融資返済'),
        ('経常利益', '経常利益'),
    ]
    out = ['<table class="pl"><thead><tr><th class="k">項目</th>']
    for r in gyou:
        cls = ' class="q"' if r['月'] in (3, 6, 9, 12) else ''
        out.append(f'<th{cls}>{r["月"]}月</th>')
    out.append('<th class="t">年計</th></tr></thead><tbody>')
    for key, mei in retsu:
        futoji = key in ('売上', '原価_計', '販管_計', '営業利益', '経常利益')
        tr = ' class="b"' if futoji else ''
        out.append(f'<tr{tr}><th class="k">{mei}</th>')
        for r in gyou:
            v = r[key]
            cls = []
            if r['月'] in (3, 6, 9, 12):
                cls.append('q')
            if v < 0:
                cls.append('neg')
            c = f' class="{" ".join(cls)}"' if cls else ''
            out.append(f'<td{c}>{v:,}</td>')
        tv = g[key] if key != '平均単価' else g['平均単価']
        out.append(f'<td class="t{" neg" if tv < 0 else ""}">{tv:,}</td></tr>')
    out.append('</tbody></table>')
    return '\n'.join(out)


def html_shihanki(an_mei):
    gyou = keisan(an_mei)
    out = ['<table class="sum"><thead><tr><th>四半期</th><th>売上</th><th>件数</th>'
           '<th>営業利益</th><th>経常利益</th><th>累計 経常利益</th></tr></thead><tbody>']
    ruikei = 0
    for q, (a, b) in {1: (1, 3), 2: (4, 6), 3: (7, 9), 4: (10, 12)}.items():
        rs = [r for r in gyou if a <= r['月'] <= b]
        kj = sum(r['経常利益'] for r in rs)
        ruikei += kj
        out.append(f'<tr><th>Q{q}　{a}〜{b}月</th><td>{sum(r["売上"] for r in rs):,}</td>'
                   f'<td>{sum(r["件数"] for r in rs)}</td>'
                   f'<td>{sum(r["営業利益"] for r in rs):,}</td>'
                   f'<td class="{"neg" if kj < 0 else ""}">{kj:,}</td><td>{ruikei:,}</td></tr>')
    out.append('</tbody></table>')
    return '\n'.join(out)
