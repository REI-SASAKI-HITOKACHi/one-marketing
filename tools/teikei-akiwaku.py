#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""提携先ごとに「空き日のお知らせ」メールの下書きを作る（TODO T052／和真対応可否 No.35）。

【なぜ】提携経由は平均LTV 186,272円・リピート率45%で、いちばん高い入口。
  ところが月1回の接触すら回っていない。営業に回せる人がいないので、
  「相手が使える情報（空いている日）を、人の手をほとんど使わずに送る」形にする
  （docs/提携先-月1回の空き枠連絡.md）。

【何をするか】
  1. 空き枠を予約ページと同じ Apps Script（和真さんのカレンダーをその場で見る）から取る。
     半日＝240分の枠、1日＝480分の枠が入る日だけを拾う。
     ★API が返すのは「翌日〜21日先」まで（booking-api.gs の saitanNichi／saichouNichi）。
       1か月先までは取れない。だから毎月25日に作ると「26日〜翌月中旬」の空きになる。
  2. 提携先の一覧は売上スプシ『提携先_休眠度』タブ（読み取りのみ）。
     J列「今後の方針」が 切る／放置／積極的に活性化しない／受動的対応 の先は出さない。
  3. 名乗りの照合（CLAUDE.md の禁止事項）：tools/derive-soushin-keitou.py の meigi_hyou() で、
     台帳の氏名にその社名が入っている施工を集め、**いちばん新しい施工の名義**が「自社」の先だけ出す。
     本舗名義の先・台帳で照合できない先は出さない（出力の末尾に理由つきで並べる）。
  4. 宛名・担当者・宛先メールは data/teikei-renrakusaki.json（台帳に列が無いため）。
     専用ご依頼ページ（tools/build-partner.py の COMPANIES）がある先だけ URL 行を入れ、
     そのURLが公開されているか（HTTP 200）もその場で確かめる。
  5. 出力：data/teikei-akiwaku/<YYYY-MM>.md（下書き。**送信はしない**）

【文面の決まり】あいさつ1行／空いている日（既定で最大8日。終日の日を優先して選び、日付順に並べる。
  あふれたぶんは「ほか◯日」の1行。隠さない）／専用ページのURL／署名。説明のための説明は書かない。
  空き日が1日も無い月は下書きを作らない（終了コード1。「今月は送らない」が正しい）。

【毎月の回し方】
  毎月25日の毎時点検（朝の巡回）の中で：
    python3 tools/teikei-akiwaku.py                 # 25日以降は翌月分として data/teikei-akiwaku/<翌月>.md を作る
  → cmo が下書きを読んで、掲示板で「今月の空き日のお知らせ、◯社に送ってよいか」をオーナーに上げる（外に出すもの）
  → オーナーOKなら、宛先が登録済みの先だけ Gmail の下書きにする（Claude の Gmail 連携 create_draft。送信ボタンはオーナー）
  → 送った日・送った先・返信・その後の受注を記録する（docs/提携先-月1回の空き枠連絡.md「測ること」）

【使い方】
  python3 tools/teikei-akiwaku.py                  # 下書きを作る（今日が20日以降なら翌月分、それより前は今月分のファイル名）
  python3 tools/teikei-akiwaku.py --tsuki 2026-11  # ファイル名の月を指定
  python3 tools/teikei-akiwaku.py --saidai 6       # 並べる日数の上限（既定8）
  python3 tools/teikei-akiwaku.py --dry-run        # 画面に出すだけ（ファイルを書かない）

  旧 tools/build-teikei-akiwaku.py（静的な slots.json から1通ぶんの本文を出す）は、この道具に置き換えた。
"""
import argparse
import datetime as dt
import importlib.util
import json
import pathlib
import re
import sys
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "teikei-akiwaku"
RENRAKU = ROOT / "data" / "teikei-renrakusaki.json"
TEIKEI_SAKI = ROOT / "data" / "teikei-saki.json"

SS = "1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64"
KYUMIN = "提携先_休眠度"
API = ("https://script.google.com/macros/s/AKfycbzuuMGVICQPoLlUrFBarb1zAgi_kVdc1vDrRJoyhAJ_tvOG-eHnmTHDGWhuvix3E3_odQ/exec")
PAGE_URL = "https://lp.onehitter.jp/partner/{key}/"

HANNICHI, ICHINICHI = 240, 480   # 半日・1日の枠（分）
JOGAI_HOUSHIN = ("切る", "放置", "活性化しない", "受動的")   # 『提携先_休眠度』J列。この語を含む先には送らない

# 名乗りの照合に使う略称（data/teikei-saki.json の「別名」に足して使う）。台帳の氏名で実際に使われていて、
# 1社にしか当たらないものだけ。青山は台帳に「青山リアルティ様」「青山リアルティ・アドバイザーズ株式会社」の表記があり、
# 正式名の長音「ー」の有無で割れる（2026-10-08 の照合で4名義とも自社と確認したもの）。
SHOUGOU_BETSUMEI = {"青山リアルティ": "青山リアルティー・アドバイザーズ"}

SHOMEI = "ワンヒッター株式会社\n佐々木 嶺\nTEL 080-8043-8259"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ---------------- 空き枠 ----------------

def slots(minutes):
    """API の応答 slots（[{date, label, times}]）。callback を付けなければ素の JSON が返る。"""
    url = API + "?" + urllib.parse.urlencode({"action": "slots", "minutes": minutes})
    with urllib.request.urlopen(url, timeout=60) as r:
        d = json.loads(r.read().decode("utf-8"))
    if not d.get("ok"):
        sys.exit(f"空き枠APIがエラーを返しました: {d.get('error')}")
    return d["slots"]


def akibi():
    """[(date, label, 区分)]。区分＝終日／半日（午前）／半日（午後）／半日（午前か午後）"""
    ichi = {x["date"] for x in slots(ICHINICHI)}
    out = []
    for x in slots(HANNICHI):
        if x["date"] in ichi:
            k = "終日"
        else:
            am = any(t < "12:00" for t in x["times"])
            pm = any(t >= "12:00" for t in x["times"])
            k = "半日（午前か午後）" if am and pm else ("半日（午前）" if am else "半日（午後）")
        out.append((x["date"], x["label"], k))
    return sorted(out)


def erabu(hi, saidai):
    """終日の日を優先して saidai 日まで選び、日付順に戻す。残りの日数も返す。"""
    yuusen = sorted(hi, key=lambda x: (x[2] != "終日", x[0]))[:saidai]
    return sorted(yuusen), len(hi) - len(yuusen)


# ---------------- 提携先 ----------------

def core(n):
    return re.sub(r"株式会社|合同会社|有限会社|（株）|\(株\)|様|\s", "", str(n))


def teikei_ichiran():
    """『提携先_休眠度』の [(社名, 状態, 最終発注, 今後の方針)]"""
    sc = load("sc", ROOT / "tools" / "sheets_client.py")
    tok = sc.access_token(sc.load_credentials())
    v = sc.call(tok, f"/{SS}/values/" + urllib.parse.quote(f"'{KYUMIN}'!B1:J60", safe="")).get("values", [])
    hi = next(i for i, r in enumerate(v) if r and str(r[0]).strip() == "提携先")
    out = []
    for r in v[hi + 1:]:
        r = [str(c).strip() for c in r] + [""] * 9
        if not r[0]:
            break
        out.append((r[0], r[2], r[4], r[8]))
    return out


def meigi_teikei(hyou, sha, betsumei):
    """(名義, 最新施工日, 照合した氏名の数) か None。
    台帳の氏名にその社名（株式会社などを除いた部分）が入っている施工をすべて集め、いちばん新しい施工の名義を採る。
    同じ日に自社と本舗があれば本舗（saishin() と同じ考え）。
    社名が3文字以下（ドア・はるか など）は、氏名が社名そのもののときだけ当てる（「伊藤はるか」を拾わないため）。"""
    _, by_name = hyou
    c = core(sha)
    kagi = {c} | {core(k) for k, v in betsumei.items() if v == sha}
    hit = []
    for name, (meigi, hiduke) in by_name.items():
        n = core(name)
        if any((n == k) if len(k) <= 3 else (k in n) for k in kagi):
            hit.append((hiduke, meigi))
    if not hit:
        return None
    saishin = max(h for h, _ in hit)
    sonohi = {m for h, m in hit if h == saishin}
    return ("本舗" if "本舗" in sonohi else sonohi.pop()), saishin, len(hit)


def senyou_pages():
    """{社名の core: (鍵, COMPANIES の中身)}"""
    bp = load("bp", ROOT / "tools" / "build-partner.py")
    return {core(c["kaisha"]): (k, c) for k, c in bp.COMPANIES.items()}


def page_for(sha, pages):
    c = core(sha)
    for k, v in pages.items():
        if c and (c in k or k in c):
            return v
    return None


def koukai_sumi(url):
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status == 200
    except Exception:
        return False


# ---------------- 文面 ----------------

def hiduke_jp(iso):
    d = dt.date.fromisoformat(iso)
    return f"{d.month}月{d.day}日"


def honbun(atena, tantou, hani, narabi, amari, url, kyumin=False):
    aisatsu = "ご無沙汰しております" if kyumin else "いつもお世話になっております"   # 1年以上発注の無い先（🔴）は「ご無沙汰」
    L = [atena, f"{tantou} 様" if tantou else "ご担当者 様", "",
         f"{aisatsu}。ワンヒッター株式会社の佐々木です。{hani}の空き日をお知らせします。", ""]
    L += [f"　{label}　{k}" for _, label, k in narabi]
    if amari > 0:
        L.append(f"　ほか{amari}日、空きがあります。")
    L.append("")
    if url:
        L += ["ご依頼は御社専用のページから、空いている時間を選んでそのまま仮押さえできます。", url]
    else:
        L += ["ご依頼はお電話か、このメールへのご返信で承ります。"]
    L += ["", SHOMEI]
    return "\n".join(L)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tsuki", help="ファイル名の月 YYYY-MM（既定：20日以降は翌月、それより前は今月）")
    p.add_argument("--saidai", type=int, default=8, help="並べる日数の上限（既定8）")
    p.add_argument("--dry-run", action="store_true", help="画面に出すだけ")
    a = p.parse_args()

    kyou = dt.date.today()
    if a.tsuki:
        tsuki = a.tsuki
    else:
        t = (kyou.replace(day=1) + dt.timedelta(days=32)) if kyou.day >= 20 else kyou
        tsuki = f"{t.year}-{t.month:02d}"

    hi = akibi()
    if not hi:
        print("★ 半日・1日の空きが1日もありません。今月は送らない、が正しい判断です。", file=sys.stderr)
        sys.exit(1)
    narabi, amari = erabu(hi, a.saidai)
    hani = f"{hiduke_jp(hi[0][0])}〜{hiduke_jp(hi[-1][0])}"
    kenmei = f"{hani}の空き日のお知らせ（ワンヒッター）"

    meigi = load("meigi", ROOT / "tools" / "derive-soushin-keitou.py")
    hyou = meigi.meigi_hyou()
    betsumei = {k: v for k, v in json.loads(TEIKEI_SAKI.read_text(encoding="utf-8")).get("別名", {}).items()
                if not k.startswith("_")}
    betsumei.update(SHOUGOU_BETSUMEI)
    renraku = {k: v for k, v in json.loads(RENRAKU.read_text(encoding="utf-8")).items() if not k.startswith("_")}
    pages = senyou_pages()
    koukai = {}

    dasu, houshin_gai, shougou_gai, page_nashi = [], [], [], []
    for sha, joutai, saishu, houshin in teikei_ichiran():
        if any(w in houshin for w in JOGAI_HOUSHIN):
            houshin_gai.append((sha, houshin))
            continue
        m = meigi_teikei(hyou, sha, betsumei)
        if m is None:
            shougou_gai.append((sha, "台帳の氏名に社名が見つからない（照合できない）"))
            continue
        if m[0] != "自社":
            shougou_gai.append((sha, f"最新の施工（{m[1]}）が{m[0]}名義"))
            continue
        r = renraku.get(sha, {})
        pg = page_for(sha, pages)
        url, tantou = None, r.get("tantou", "")
        if pg:
            url = PAGE_URL.format(key=pg[0])
            tantou = pg[1].get("tantou") or tantou
            if url not in koukai:
                koukai[url] = koukai_sumi(url)
        else:
            page_nashi.append(sha)
        dasu.append({"sha": sha, "joutai": joutai, "saishu": saishu, "meigi": m, "mail": r.get("mail", ""),
                     "url": url, "body": honbun(r.get("atena") or sha, tantou, hani, narabi, amari, url, kyumin="🔴" in joutai)})

    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    md = [f"# 提携先への空き日のお知らせ　{tsuki}（下書き・未送信）", "",
          f"作成 {now}　`python3 tools/teikei-akiwaku.py`。**送信はしない。送るのはオーナー（外に出すもの）。**", "",
          f"- 空き枠：予約ページと同じ Apps Script から取得（{hani}。API は翌日〜21日先まで）。"
          f"半日以上空いている日 {len(hi)}日（うち終日 {sum(1 for x in hi if x[2] == '終日')}日）、"
          f"文面には {len(narabi)}日を掲載" + (f"、ほか{amari}日は1行に畳んだ" if amari > 0 else ""),
          f"- 名乗り：`meigi_hyou()` で照合し、最新の施工が「自社」名義の先だけ出した（{len(dasu)}社）",
          f"- 件名（全社共通）：**{kenmei}**", ""]
    mikoukai = [u for u, ok in koukai.items() if not ok]
    if mikoukai:
        md += ["> ⚠ **専用ページがまだ公開されていません**（HTTP 200 が返らない）："] + \
              [f"> - {u}" for u in mikoukai] + \
              ["> 公開（オーナー承認・`check-public-page.py`）してから送るか、その先だけURL行を外して送る。", ""]
    md += ["---", ""]
    for x in dasu:
        md += [f"## {x['sha']}", "",
               f"- 宛先：{x['mail'] or '**未登録**（data/teikei-renrakusaki.json に入れる）'}",
               f"- 名乗りの照合：{x['meigi'][0]}（最新の施工 {x['meigi'][1]}・氏名{x['meigi'][2]}件で照合）／休眠度：{x['joutai']}（最終発注 {x['saishu']}）",
               f"- 専用ページ：{x['url'] + ('' if koukai.get(x['url']) else '（⚠ 未公開）') if x['url'] else 'なし'}",
               "", "```", f"件名：{kenmei}", "", x["body"], "```", ""]
    md += ["---", "", "## 出さなかった先", "", "| 提携先 | 理由 |", "|---|---|"]
    md += [f"| {s} | 名乗りの照合：{why} |" for s, why in shougou_gai]
    md += [f"| {s} | 今後の方針「{h}」（『{KYUMIN}』J列） |" for s, h in houshin_gai]
    md += ["", "## 専用ページを作れば載る先", "",
           "下の先は URL 行なし（「お電話か、このメールへのご返信で」）で作った。"
           "`tools/build-partner.py` の COMPANIES に足せば、次の回から専用ページのURLが入る。", ""]
    md += [f"- {s}" for s in page_nashi] or ["- （なし）"]
    md.append("")
    text = "\n".join(md)

    if a.dry_run:
        print(text)
        return
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{tsuki}.md"
    out.write_text(text, encoding="utf-8")
    print(f"書きました: {out.relative_to(ROOT)}（{len(dasu)}社・掲載{len(narabi)}日／空き{len(hi)}日）")
    print(f"出さなかった先: 照合 {len(shougou_gai)}社・方針 {len(houshin_gai)}社／専用ページなし {len(page_nashi)}社"
          + (f"／⚠ 未公開の専用ページ {len(mikoukai)}件" if mikoukai else ""))


if __name__ == "__main__":
    main()
