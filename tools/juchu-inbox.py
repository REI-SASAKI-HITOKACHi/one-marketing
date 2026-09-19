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

SS = "1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64"
SITE_ID = "f1b64c82-173e-4b1a-9e7f-bf24026fed0e"     # oh-naibu-sms-k7q3x（社内用）
FORM = "juchu"
SUMI = ROOT / "data" / "juchu-torikomi.json"          # 取り込み済みのID（タブを増やさない）
TODO = ROOT / "data" / "calendar" / "juchu-todo.json"
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

        hondate = [[
            d.get("売上種類", ""), hi.replace("-", "/"), d.get("流入経路", ""),
            d.get("氏名", ""), d.get("TEL", ""), d.get("郵便番号", ""),
            d.get("住所", ""), d.get("売上（税込）", ""), d.get("実施メニュー", ""),
        ]]
        biko = ("★受注フォームから自動で入りました（" + str(d.get("入力日時", ""))[:16] + "）。"
                + ("見込み " + str(d.get("見込み金額", "")) + "円。" if d.get("見込み金額") else "")
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
            print(f"  入れました: {tab} {gyo}行目 ← {d.get('氏名')}")

        fun = int(str(d.get("所要の目安（分）", "60")) or 60)
        jikoku = str(d.get("開始時刻", "09:00"))[:5] or "09:00"
        h, mi = (int(x) for x in jikoku.split(":"))
        owari_fun = h * 60 + mi + fun
        todo.append({
            "id": s["id"],
            "タイトル": taitoru(d),
            "開始": f"{hi}T{jikoku}:00+09:00",
            "終了": f"{hi}T{owari_fun//60:02d}:{owari_fun%60:02d}:00+09:00",
            "場所": d.get("住所", ""),
            "説明": "\n".join(x for x in [
                f"{d.get('売上種類','')} {d.get('氏名','')}さま",
                f"{d.get('実施メニュー','')}",
                f"¥{d.get('売上（税込）','')}",
                f"TEL {d.get('TEL','')}" if d.get("TEL") else "",
                str(d.get("備考", "")),
                "※受注フォームから自動で作りました",
            ] if x),
            "台帳": f"{tab} {gyo}行目",
        })
        ireta.append(s["id"])

    if a.dry_run:
        print(f"\n--dry-run のため書いていません。カレンダーの予定 {len(todo)}件ぶんも作っていません。")
        return
    TODO.parent.mkdir(parents=True, exist_ok=True)
    TODO.write_text(json.dumps(todo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SUMI.write_text(json.dumps(sorted(sumi | set(ireta)), ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    print(f"\nカレンダーに作る予定: {TODO}（{len(todo)}件）")
    print("　★予定づくりは毎時のルーティンの中で行います（この環境からは直接書けないため）。")


if __name__ == "__main__":
    main()
