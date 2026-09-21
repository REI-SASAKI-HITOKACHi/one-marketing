#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""受注フォームに届いたものを、月次の売上タブへ入れ、カレンダーの予定を作る材料を出す。

  オーナー決定（2026-09-19・MTGシート 第3回 3-4 議題1）
    「スプシとカレンダーの双方に自動反映させる」「和真の操作工数をなるべく減らす」

  毎時のルーティンから呼ぶ。
    python3 tools/juchu-inbox.py --dry-run   # 何が入るかを出すだけ
    python3 tools/juchu-inbox.py             # 実際に書く

【カレンダーについて】
  この環境からカレンダーへ直接は書けない（サービスアカウントに権限が無い）。
  予約フォームと同じ形にする：**ここでは data/calendar/juchu-todo.json を出すところまで**。
  実際の予定づくりは、毎時のルーティンの中でマーケ部長が行う。

【郵便番号】
  2026-09-19 オーナー指示でフォームの郵便番号欄をなくした。
  住所から引いてここで入れる（tools/yubin.py）。索引は端末へ送らない。
  同じ月のタブに、人が入れた「同じ住所＋郵便番号」があれば、そちらを優先する。

【予定のタイトル】
  2026-09-04 のMTG決定「地域（区/市）/施工種類/台数」に揃える。
  **顧客名と金額はタイトルに入れない**（カレンダーを共有したときに外へ出るため）。
  顧客名・金額は説明欄、住所は場所欄。
"""
import argparse
import json
import os
import pathlib
import re
import sys
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import sheets_client as sc
import yubin

SS = "1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64"
SITE_ID = "6e568d1d-4a66-4167-8d0f-7b15ce8b0828"     # oh-genba-form-m8x2q（社内用・受注/完了フォーム専用。2026-09-22 に oh-naibu-sms から分離。旧サイトの取り込み済みIDは data/*-torikomi.json に残る）
FORM = "juchu"
SUMI = ROOT / "data" / "juchu-torikomi.json"          # 取り込み済みのID（タブを増やさない）
TEIKEI = ROOT / "data" / "teikei-saki.json"           # 提携先の選択肢（表記ゆれ防止）
TODO = ROOT / "data" / "calendar" / "juchu-todo.json"
KANRYO = ROOT / "data" / "kanryo-yotei.json"   # 作業完了フォームを送る材料（tools/kanryo-okuru.py）
TEST = ("テスト", "test", "てすと")
NETLIFY_TOKEN = os.path.expanduser("~/.config/one-hitter/netlify-token.txt")


def netlify(path):
    t = os.environ.get("NETLIFY_TOKEN", "").strip() or \
        (pathlib.Path(NETLIFY_TOKEN).read_text(encoding="utf-8").strip()
         if os.path.exists(NETLIFY_TOKEN) else "")
    if not t:
        sys.exit("Netlifyトークンがありません。")
    req = urllib.request.Request("https://api.netlify.com/api/v1" + path,
                                 headers={"Authorization": "Bearer " + t})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def chiiki(jusho):
    """住所から「江戸川区」「市川市」などを取り出す。取れなければ空。"""
    m = re.search(r"([一-龥ぁ-んァ-ヶ]{2,5}[区市町村])", str(jusho))
    return m.group(1) if m else ""


def yubin_dasu(jusho, jisseki):
    """住所から郵便番号を出す。台帳に人が入れた実績があればそれを優先する。"""
    j = re.sub(r"[\s\u3000]", "", str(jusho or ""))
    if not j:
        return "", ""
    for ban, you in jisseki.items():
        if ban and (j.startswith(you) or you.startswith(j[:8])):
            return ban, "台帳の実績から"
    y = yubin.hiku(jusho)
    return (y, "住所から自動判定") if y else ("", "")


def _owari_moji(hi, fun):
    """終了時刻。24時をまたぐときは翌日にする。"""
    import datetime
    d0 = datetime.date.fromisoformat(hi) + datetime.timedelta(days=fun // (24 * 60))
    f = fun % (24 * 60)
    return f"{d0.isoformat()}T{f//60:02d}:{f%60:02d}:00+09:00"


def taitoru(d):
    """2026-09-04 のMTG決定の形。顧客名と金額は入れない。"""
    ku = chiiki(d.get("住所", ""))
    menu = str(d.get("実施メニュー", "")).replace("クリーニング", "")
    return " / ".join(x for x in (ku, menu) if x) or "施工"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    forms = [f for f in netlify(f"/sites/{SITE_ID}/forms") if f["name"] == FORM]
    if not forms:
        sys.exit(f"{FORM} フォームが見つかりません。先に配信してください（tools/deploy-juchu.py）。")
    subs, meiwaku = [], []
    for f in forms:
        subs += netlify(f"/forms/{f['id']}/submissions")
        meiwaku += netlify(f"/forms/{f['id']}/submissions?state=spam")

    print(f"受注フォームに届いている件数: {len(subs)}件")
    if meiwaku:
        # 予約フォームと同じ。迷惑判定に入ったものは自動で取り込まず、必ず目に出す。
        print(f"\n🔴 迷惑判定に {len(meiwaku)}件あります。**自動では取り込みません。人が見てください。**")
        for s in meiwaku:
            d = s.get("data") or {}
            print(f"   - {s['created_at'][:16]} {s['id']} 氏名={d.get('氏名','（なし）')}")
        print()

    sumi = set(json.loads(SUMI.read_text(encoding="utf-8"))) if SUMI.exists() else set()
    atarashii = [s for s in subs if s["id"] not in sumi]
    tesuto = [s for s in atarashii
              if any(k in str((s.get("data") or {}).get("氏名", "")).lower() for k in TEST)]
    if tesuto:
        print(f"テスト送信 {len(tesuto)}件は取り込みません（Netlify側で削除してください）:")
        for s in tesuto:
            print("   ", s["created_at"][:16], s["id"])
    atarashii = [s for s in atarashii if s not in tesuto]
    print(f"未取り込み: {len(atarashii)}件")
    if not atarashii:
        return

    tok = sc.access_token(sc.load_credentials())

    def call(p, m="GET", pay=None, q=None):
        return sc.call(tok, p, method=m, payload=pay, query=q)

    def han(rng):
        """A1表記をURLに入る形にする。
        ★タブ名に「/」が入っている（例：12月_売上/顧客）ので、safe='' で全部escapeすること。
          safe='/...' にすると、タブ名のスラッシュがパスの区切りと解釈されて 400 になる（実測）。"""
        return f"/{SS}/values/" + urllib.parse.quote(rng, safe="")

    todo = json.loads(TODO.read_text(encoding="utf-8")) if TODO.exists() else []
    kanryo = json.loads(KANRYO.read_text(encoding="utf-8")) if KANRYO.exists() else []
    shiranai = []   # 一覧に無い提携先（台帳に足す必要がある）
    teikei = set(json.loads(TEIKEI.read_text(encoding="utf-8"))["選択肢"]) if TEIKEI.exists() else set()
    ireta = []
    for s in atarashii:
        d = s.get("data") or {}
        hi = str(d.get("施工日付", "")).strip()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", hi):
            print(f"  ⚠ 施工日付が読めないので飛ばします: {s['id']} 「{hi}」")
            continue
        tsuki = int(hi[5:7])
        tab = f"{tsuki}月_売上/顧客"

        # 空いている最初の行を探す（B列が空＝未使用）
        b = call(han(f"'{tab}'!B4:B60")).get("values", [])
        gyo = 4 + len(b)
        while gyo - 4 < len(b) and str(b[gyo - 4][0] if b[gyo - 4] else "").strip():
            gyo += 1
        # B4 から詰まっているので、値がある最後の次
        aita = 4
        for i, r in enumerate(b):
            if r and str(r[0]).strip():
                aita = 4 + i + 1
        gyo = max(aita, 4)

        # 郵便番号は住所から出す（フォームには欄が無い。2026-09-19 オーナー指示）。
        # 同じタブに人が入れた「郵便番号＋住所」があれば、そちらを先に使う。
        jisseki = {}
        for r in call(han(f"'{tab}'!G4:H60")).get("values", []):
            if len(r) >= 2 and str(r[0]).strip() and str(r[1]).strip():
                jisseki[str(r[0]).strip()] = re.sub(r"[\s\u3000]", "", str(r[1]))
        yubin_ban, yubin_moto = yubin_dasu(d.get("住所", ""), jisseki)

        hondate = [[
            d.get("売上種類", ""), hi.replace("-", "/"), d.get("流入経路", ""),
            d.get("氏名", ""), d.get("TEL", ""), yubin_ban,
            d.get("住所", ""), d.get("売上（税込）", ""), d.get("実施メニュー", ""),
        ]]
        biko = ("★受注フォームから自動で入りました（" + str(d.get("入力日時", ""))[:16] + "）。"
                + ("見込み " + str(d.get("見込み金額", "")) + "円。" if d.get("見込み金額") else "")
                + ("郵便番号は" + yubin_moto + "。" if yubin_moto else "")
                + ("【ヒアリング】" + str(d["ヒアリング"]) + "　" if d.get("ヒアリング") else "")
                + str(d.get("備考", "")))
        if a.dry_run:
            print(f"  [予定] {tab} {gyo}行目 ← {d.get('氏名')} / {d.get('実施メニュー')} / {d.get('売上（税込）')}円")
        else:
            call(han(f"'{tab}'!B{gyo}"), "PUT", {"values": hondate},
                 q={"valueInputOption": "USER_ENTERED"})
            call(han(f"'{tab}'!N{gyo}"), "PUT", {"values": [[biko]]},
                 q={"valueInputOption": "USER_ENTERED"})
            if d.get("法人名"):
                call(han(f"'{tab}'!U{gyo}"), "PUT", {"values": [[d["法人名"]]]},
                     q={"valueInputOption": "USER_ENTERED"})
        if d.get("法人名") and teikei and d["法人名"] not in teikei:
            shiranai.append((d["法人名"], f"{tab} {gyo}行目"))
            print(f"  入れました: {tab} {gyo}行目 ← {d.get('氏名')}")

        fun = int(str(d.get("所要の目安（分）", "60")) or 60)
        jikoku = str(d.get("開始時刻", "09:00"))[:5] or "09:00"
        h, mi = (int(x) for x in jikoku.split(":"))
        # 終了時刻はフォームで直せる（2026-09-19 オーナー指示）。入っていればそれを使う。
        owari_ire = str(d.get("終了時刻", "")).strip()[:5]
        if re.fullmatch(r"\d{1,2}:\d{2}", owari_ire):
            oh, omi = (int(x) for x in owari_ire.split(":"))
            owari_fun = oh * 60 + omi
            if owari_fun <= h * 60 + mi:
                owari_fun += 24 * 60
        else:
            owari_fun = h * 60 + mi + fun
        todo.append({
            "id": s["id"],
            "タイトル": taitoru(d),
            "開始": f"{hi}T{jikoku}:00+09:00",
            "終了": _owari_moji(hi, owari_fun),
            "場所": d.get("住所", ""),
            "説明": "\n".join(x for x in [
                f"{d.get('売上種類','')} {d.get('氏名','')}さま",
                f"{d.get('実施メニュー','')}",
                f"¥{d.get('売上（税込）','')}",
                f"TEL {d.get('TEL','')}" if d.get("TEL") else "",
                f"【ヒアリング】{d.get('ヒアリング','')}" if d.get("ヒアリング") else "",
                str(d.get("備考", "")),
                "※受注フォームから自動で作りました",
            ] if x),
            "台帳": f"{tab} {gyo}行目",
        })
        # 作業完了フォームを送るための材料。**お客様の情報はここ（手元）にだけ置く。**
        #   URLの # に入れて送るので、社内ホストには置かない（tools/build-kanryo.py の説明）
        kanryo.append({
            "id": s["id"],
            "氏名": d.get("氏名", ""),
            "売上種類": d.get("売上種類", ""),
            "施工日付": hi,
            "開始時刻": jikoku,
            "メニュー": [x for x in str(d.get("実施メニュー", "")).split("／") if x],
            "金額": str(d.get("売上（税込）", "")),
            "台帳": f"{tab} {gyo}行目",
        })
        ireta.append(s["id"])

    if shiranai:
        # 提携先はプルダウンから選ぶ決まり（表記ゆれ防止）。新しい名前は人が台帳へ足す。
        print(f"\n🔴 一覧に無い提携先が {len(shiranai)}件 届いています。**台帳に足してください。**")
        for na, ba in shiranai:
            print(f"   - 「{na}」（{ba}）")
        print("   足す先: スプレッドシートの『【毎月更新】リピート/業務提携』タブ B列")
        print("   足したら: python3 tools/build-teikei-list.py → build-juchu.py → deploy-juchu.py")

    if a.dry_run:
        print(f"\n--dry-run のため書いていません。カレンダーの予定 {len(todo)}件ぶんも作っていません。")
        return
    TODO.parent.mkdir(parents=True, exist_ok=True)
    TODO.write_text(json.dumps(todo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    KANRYO.write_text(json.dumps(kanryo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SUMI.write_text(json.dumps(sorted(sumi | set(ireta)), ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    print(f"\nカレンダーに作る予定: {TODO}（{len(todo)}件）")
    print("　★予定づくりは毎時のルーティンの中で行います（この環境からは直接書けないため）。")


if __name__ == "__main__":
    main()
