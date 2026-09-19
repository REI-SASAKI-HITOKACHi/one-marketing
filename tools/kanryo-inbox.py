#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""作業完了フォームに届いたものを受け取る。

  オーナー決定（2026-09-19・MTGシート G245）
    ・施工写真 … マーケ部長が即収集してSNS投稿へ反映させる
    ・作業終了時刻 … データを蓄積・集計して施工時間計算の正確化への資産とする
    ・追加受注 … 最終金額をマーケ部長が確認して売上シートへ反映（※自動反映でもOK）
    ・クレーム有無 … 有の場合は内容をフリー入力
    ・お客様周辺情報 … マーケ部長が収集して顧客台帳へ転記する

  毎時のルーティンから呼ぶ。
    python3 tools/kanryo-inbox.py --dry-run   # 何が入るかを出すだけ
    python3 tools/kanryo-inbox.py             # 実際に書く

【売上シートの直し方】★ここは慎重に
  受注フォームが作った行だけを直す（備考に「★受注フォームから自動で入りました」がある行）。
  **直す前の金額を必ず備考に残す。** 人が手で入れた行は触らない。
  過去の実績を書き換えない、という決まり（CLAUDE.md）を、機械で守るための条件です。

【クレーム】
  クレームありは自動で何かをしません。**画面に🔴で出して、人が読むまで消えません。**
  そのまま LINE へ流すかどうかは、内容を読んでから人が決めます。
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
FORM = "kanryo"
SUMI = ROOT / "data" / "kanryo-torikomi.json"
JIKAN = ROOT / "data" / "kanryo-jikan.json"          # 実所要の蓄積（施工時間の精度を上げる資産）
SHASHIN = ROOT / "data" / "kanryo-shashin"
JIDOU = "★受注フォームから自動で入りました"
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


def daicho_wake(s):
    """「9月_売上/顧客 12行目」を ('9月_売上/顧客', 12) にする。"""
    m = re.match(r"^(.+?)\s+(\d+)\s*行目$", str(s or "").strip())
    return (m.group(1), int(m.group(2))) if m else (None, None)


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

    print(f"作業完了フォームに届いている件数: {len(subs)}件")
    if meiwaku:
        print(f"\n🔴 迷惑判定に {len(meiwaku)}件あります。**自動では取り込みません。人が見てください。**")
        for s in meiwaku:
            d = s.get("data") or {}
            print(f"   - {s['created_at'][:16]} {s['id']} 氏名={d.get('氏名','（なし）')}")
        print()

    sumi = set(json.loads(SUMI.read_text(encoding="utf-8"))) if SUMI.exists() else set()
    atarashii = [s for s in subs if s["id"] not in sumi]
    print(f"未取り込み: {len(atarashii)}件")
    if not atarashii:
        return

    tok = sc.access_token(sc.load_credentials())

    def call(p, m="GET", pay=None, q=None):
        return sc.call(tok, p, method=m, payload=pay, query=q)

    def han(rng):
        """★タブ名に「/」が入っている（例：12月_売上/顧客）ので safe='' で全部escapeすること。"""
        return f"/{SS}/values/" + urllib.parse.quote(rng, safe="")

    jikan = json.loads(JIKAN.read_text(encoding="utf-8")) if JIKAN.exists() else []
    kureemu, shuhen, mayoi, shashin_ochi, ireta = [], [], [], [], []

    for s in atarashii:
        d = s.get("data") or {}
        na = d.get("氏名", "（名前なし）")
        tab, gyo = daicho_wake(d.get("台帳", ""))
        print(f"\n── {na} さま／{d.get('施工日付','')} {d.get('開始時刻','')}〜{d.get('作業終了時刻','')}")

        # --- 写真を手元に落とす（SNSの素材にする） ---
        mai = 0
        for k, v in (s.get("data") or {}).items():
            if not k.startswith("施工写真") or not isinstance(v, dict) or not v.get("url"):
                continue
            mai += 1
            saki = SHASHIN / f"{d.get('施工日付','日付なし')}_{re.sub(r'[^0-9A-Za-zぁ-んァ-ヶ一-龥]', '', na)}_{mai}.jpg"
            if a.dry_run:
                print(f"   [予定] 写真を落とす → {saki.name}")
                continue
            saki.parent.mkdir(parents=True, exist_ok=True)
            try:
                with urllib.request.urlopen(v["url"], timeout=120) as r:
                    saki.write_bytes(r.read())
                print(f"   写真: {saki.name}  {saki.stat().st_size:,} bytes")
            except Exception as e:
                print(f"   ⚠ 写真が落とせませんでした（{k}）: {e}")
        if not mai:
            shashin_ochi.append(na)

        # --- 実所要をためる ---
        try:
            fun = int(str(d.get("実所要（分）", "")).strip() or 0)
        except ValueError:
            fun = 0
        if fun:
            jikan.append({"日": d.get("施工日付", ""), "売上種類": d.get("売上種類", ""),
                          "メニュー": d.get("実施した内容", ""), "実所要": fun,
                          "開始": d.get("開始時刻", ""), "終了": d.get("作業終了時刻", "")})
            print(f"   実所要: {fun}分")

        # --- 売上シートを直す ---
        if not tab:
            print("   ⚠ 台帳の行が分からないので、シートは直しません（手で入れてください）")
        else:
            moto = call(han(f"'{tab}'!I{gyo}")).get("values", [[""]])
            moto = str(moto[0][0]) if moto and moto[0] else ""
            biko = call(han(f"'{tab}'!N{gyo}")).get("values", [[""]])
            biko = str(biko[0][0]) if biko and biko[0] else ""
            if JIDOU not in biko:
                print(f"   ⚠ {tab} {gyo}行目は受注フォームが作った行ではありません。"
                      f"**直しません**（人が入れた行は触らない決まり）")
            else:
                saishu = str(d.get("最終金額", "")).strip()
                jissai = "／".join(x for x in [d.get("実施した内容", ""), d.get("追加受注", ""),
                                               d.get("追加受注（手入力）", "")] if x)
                tsuika_biko = "".join(x for x in [
                    f"【完了 {d.get('作業終了時刻','')}／実所要 {fun}分】" if fun else "",
                    f"受注時 {moto}円 → 最終 {saishu}円。" if saishu and saishu != re.sub(r"\D", "", moto) else "",
                    f"追加 {d.get('追加受注','')}。" if d.get("追加受注") else "",
                    f"手入力の追加「{d.get('追加受注（手入力）','')}」。" if d.get("追加受注（手入力）") else "",
                    f"やらなかった: {d.get('やらなかった内容','')}。" if d.get("やらなかった内容") else "",
                    f"🔴クレームあり：{d.get('クレーム内容','')}。" if d.get("クレーム") == "あり" else "",
                    f"アンケート依頼{d.get('アンケート依頼済み','')}／"
                    f"次回提案{d.get('次回予約提案済み','')}／"
                    f"BA確認{d.get('BeforeAfter確認済み','')}。",
                    f"お客様のこと：{d.get('お客様周辺情報','')}" if d.get("お客様周辺情報") else "",
                ])
                if a.dry_run:
                    print(f"   [予定] {tab} {gyo}行目 I列 {moto} → {saishu}／J列 ← {jissai}")
                    print(f"   [予定] 備考に足す: {tsuika_biko[:120]}…")
                else:
                    if saishu:
                        call(han(f"'{tab}'!I{gyo}"), "PUT", {"values": [[saishu]]},
                             q={"valueInputOption": "USER_ENTERED"})
                    if jissai:
                        call(han(f"'{tab}'!J{gyo}"), "PUT", {"values": [[jissai]]},
                             q={"valueInputOption": "USER_ENTERED"})
                    call(han(f"'{tab}'!N{gyo}"), "PUT", {"values": [[biko + "　" + tsuika_biko]]},
                         q={"valueInputOption": "USER_ENTERED"})
                    print(f"   直しました: {tab} {gyo}行目（I {moto} → {saishu}）")

        if d.get("クレーム") == "あり":
            kureemu.append((na, d.get("施工日付", ""), d.get("クレーム内容", "")))
        if d.get("お客様周辺情報"):
            shuhen.append((na, d.get("お客様周辺情報")))
        if d.get("迷ったこと"):
            mayoi.append((na, d.get("迷ったこと")))
        ireta.append(s["id"])

    # ---- 人が読むところ ----
    if kureemu:
        print("\n" + "=" * 56)
        print(f"🔴🔴 クレームが {len(kureemu)}件 あります。**いちばん先に読んでください。**")
        for na, hi, naka in kureemu:
            print(f"   ── {na} さま（{hi}）\n      {naka}")
        print("=" * 56)
    if shuhen:
        print(f"\n📗 顧客台帳へ移すこと（{len(shuhen)}件）")
        for na, x in shuhen:
            print(f"   - {na} さま：{x}")
    if mayoi:
        print(f"\n💭 現場で迷ったこと（{len(mayoi)}件）。仕組みで潰せないか考えること")
        for na, x in mayoi:
            print(f"   - {na} さまの現場：{x}")
    if shashin_ochi:
        print(f"\n⚠ 写真が1枚も無い受注が {len(shashin_ochi)}件: {'／'.join(shashin_ochi)}")

    if a.dry_run:
        print("\n--dry-run のため書いていません。")
        return
    JIKAN.write_text(json.dumps(jikan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SUMI.write_text(json.dumps(sorted(sumi | set(ireta)), ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    print(f"\n実所要の蓄積: {JIKAN}（{len(jikan)}件）")
    print(f"写真: {SHASHIN}　→ SNSに使うぶんは web-inflow へ渡すこと")


if __name__ == "__main__":
    main()
