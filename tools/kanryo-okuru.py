#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""作業完了フォームのURLを、業務連絡グループLINEへ送る。

  オーナー決定（2026-09-19・MTGシート G245）
    「施工開始時刻の30分後にマーケ部長が業務連絡グループLINEへ作業完了フォームを送信する」

  毎時のルーティンから呼ぶ。開始から30分を過ぎた受注だけを、1件1通で送る。

  2026-10-24 オーナー決定（第8回MTG中・CMOスレッド）「アンケートについては朝まとめて送るルールへ変更しておいて」
    → 毎朝7:35 に --asa で、今日の施工ぶんを開始時刻を待たずに1通にまとめて送る（作業中に届かない問題の直し）。
      毎時の実行（引数なし）は、朝のあとに入った当日の予約だけを拾う取りこぼし防止として残す。

    python3 tools/kanryo-okuru.py --asa --dry-run   # 今日の分をまとめて見るだけ
    python3 tools/kanryo-okuru.py --asa             # 今日の分を1通にまとめて送る

    python3 tools/kanryo-okuru.py --dry-run   # 何を送るかを出すだけ
    python3 tools/kanryo-okuru.py             # 実際に送る

  2026-10-14 和真さん「作業入った30分後に送るシステムだったよね？…だから毎回手入力で作業報告してるよ！」
    → 原因：送る材料が受注フォーム経由の予約（data/kanryo-yotei.json）だけで、カレンダーにだけある予約
      （受注フォーム導入前に入った予約・和真さんが直接入れた予約）が一度も対象になっていなかった。
    → 売上表に今日の施工日付がある行（tools/kanryo_mishin.py の未入力一覧）も対象に足す。開始時刻は、
      和真さんのカレンダーの控え（~/.cache/one-hitter/kyou-yotei.json。CMO がカレンダーのコネクタで保存する）で
      お名前が説明欄か件名に入っている予定から取る。控えが無い・見つからないときは 09:00 とみなす。

  ★お客様の情報（お名前・メニュー・金額）は、URLの「#」のうしろに入れる。
    # のうしろはサーバへ送られないので、社内ホストにお客様の情報が残らない。
    材料は data/kanryo-yotei.json（tools/juchu-inbox.py が作る）。非公開リポジトリにコミットする（毎時点検はコンテナが作り直されるため。2026-09-27 CMO決定）。リンクの中身はサーバに置かない。
"""
import argparse
import base64
import datetime
import json
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

ROOT = pathlib.Path(__file__).resolve().parent.parent
YOTEI = ROOT / "data" / "kanryo-yotei.json"
SUMI = ROOT / "data" / "kanryo-okurizumi.json"
BASE = "https://oh-naibu-sms-k7q3x.netlify.app/kanryo/"
JUCHU = "https://oh-naibu-sms-k7q3x.netlify.app/juchu/"   # 次回予約用（お名前・電話・住所・メニューを入れた状態で開く）
JST = datetime.timezone(datetime.timedelta(hours=9))
SAKI_FUN = 30   # 開始から何分後に送るか
KYOU_CAL = pathlib.Path.home() / ".cache" / "one-hitter" / "kyou-yotei.json"   # 和真さんの今日の予定（コネクタの list_events の返り値そのまま）


def cal_kaishi(na, hi):
    """カレンダーの控えから、そのお客様の開始時刻（HH:MM）を探す。無ければ None。"""
    try:
        import kanryo_mishin as KMI
        ev = json.loads(KYOU_CAL.read_text(encoding="utf-8")).get("events", [])
    except Exception:
        return None
    key = KMI.seiki(na)
    for e in ev:
        st = (e.get("start") or {}).get("dateTime", "")
        if not st.startswith(hi) or not key:
            continue
        if key in KMI.seiki(e.get("description", "")) or key in KMI.seiki(e.get("summary", "")):
            return st[11:16]
    return None


def hyou_kara(yotei, sumi, kyou):
    """売上表で今日が施工日なのに、受注フォーム経由の材料に無いお客様を、送る材料の形にして返す。"""
    try:
        import kanryo_mishin as KMI
        ls = KMI.ichiran(kyou)
    except Exception as e:
        print(f"  ⚠ 売上表から今日の施工を読めませんでした（受注フォーム経由の分だけ送ります）: {e}")
        return []
    aru = {str(y.get("台帳", "")).strip() for y in yotei}
    out = []
    for x in ls:
        if x["d"] != kyou.isoformat() or x["r"] in aru:
            continue
        kid = "hyou:" + x["r"] + ":" + x["d"]
        if kid in sumi:
            continue
        t = x.get("t") or cal_kaishi(x["n"], x["d"])
        if not t:
            print(f"  ⚠ {x['n']} さまの開始時刻がカレンダーの控えに無いので 09:00 とみなします")
        out.append({"id": kid, "氏名": x["n"], "売上種類": x["s"], "施工日付": x["d"], "開始時刻": t or "09:00",
                    "メニュー": x["m"], "金額": x["k"], "台帳": x["r"]})
    return out


def kaku(d):
    b = base64.urlsafe_b64encode(json.dumps(d, ensure_ascii=False, separators=(",", ":")).encode()).decode().rstrip("=")
    return BASE + "#" + b


_JOBS = None


def gamen1_meigi(y):
    """画面1（お客様に見せる画面）の名乗り。"自社" / "本舗" / "不明"。T050・20261009-06-crm。

    tools/kanryo_meigi.py（crm）で、今日の売上種類に加えて**同じ日の本舗の行**（台帳と受注の両方）を見る
    （和真さん 9/20 の同日ルール）。台帳が読めない・道具が無いときは「不明」＝画面1にQRもクチコミも出さない。
    ★売上種類（"s"）は受注フォームが売上シートに書き戻すので変えない。画面1の判定だけ "g" で渡す。
    """
    global _JOBS
    try:
        import kanryo_meigi as KM
        if _JOBS is None:
            _JOBS = KM.daichou_jobs()
        yotei = json.loads(YOTEI.read_text(encoding="utf-8")) if YOTEI.exists() else []
        return KM.gamen1_meigi(y, yotei, _JOBS)
    except Exception as e:      # 照合できない＝出さない側に倒す
        print(f"  ⚠ 画面1の名乗りを照合できません（QRとクチコミは出しません）: {e}")
        return "不明"


def url(y, p=None):
    d = {"i": y["id"], "r": y.get("台帳", ""), "n": y.get("氏名", ""),
         "s": y.get("売上種類", ""), "d": y.get("施工日付", ""), "t": y.get("開始時刻", ""),
         "m": y.get("メニュー", []), "k": y.get("金額", ""), "g": gamen1_meigi(y)}
    if p:   # まだ完了フォームが入っていない施工の一覧（2ページ目のプルダウンになる。2026-09-26 オーナー指示）
        d["p"] = p
    return kaku(d)


def daichou_gyo(daichou):
    """「10月_売上/顧客 8行目」の行から、電話・住所を読む（次回予約の受注フォームに入れる）。読めなければ空。"""
    import re
    m = re.match(r"\s*(.+?)\s+(\d+)行目", str(daichou or ""))
    if not m:
        return {}
    try:
        import urllib.parse
        import sheets_client as sc
        tok = sc.access_token(sc.load_credentials())
        rng = f"'{m.group(1)}'!A{m.group(2)}:H{m.group(2)}"
        v = sc.call(tok, "/1TK70pwQ8lYmjxUVCfFp1E2T5qDjHOnD4XSviZzUpB64/values/" + urllib.parse.quote(rng, safe="")).get("values", [[]])
        r = (v or [[]])[0] + [""] * 8
        return {"t": str(r[5]).strip(), "a": str(r[7]).strip()}
    except Exception as e:
        print(f"  ⚠ 次回予約リンク用に台帳の電話・住所を読めませんでした（名前とメニューだけ入れます）: {e}")
        return {}


def jikai_url(y):
    """次回予約用の受注フォーム（同じお客様の情報を入れた状態）。2026-10-16 和真さんの要望・オーナー了承。

    その場で次回予約を取ったとき、受注フォームの住所などの入力でお客様を待たせてしまい、
    カレンダーに仮で入れてから後で受注フォーム、の二度手間になっていた。
    → 作業完了フォームと一緒に、お名前・電話・住所・今回のメニューが入った受注フォームのリンクを送る。
       日付と時刻だけ入れれば送れる。値は # のうしろ（サーバへ送られない）。受け側は lp/juchu の #p=。
    """
    from importlib import import_module
    g = gamen1_meigi(y)
    shurui = {"自社": "One Hitter", "本舗": "本舗"}.get(g, y.get("売上種類", ""))
    menu = "／".join(str(x).replace("(", "（").replace(")", "）") for x in (y.get("メニュー") or []))
    atai = {"s": shurui, "k": "早期予約", "n": y.get("氏名", ""), "m": menu,
            "b": f"次回予約（{y.get('施工日付', '')} の作業完了時に受注）"}
    atai.update(daichou_gyo(y.get("台帳")))
    j = json.dumps({k: v for k, v in atai.items() if v}, ensure_ascii=False, separators=(",", ":"))
    return JUCHU + "#p=" + base64.urlsafe_b64encode(j.encode("utf-8")).decode("ascii").rstrip("=")


def mishin_ichiran():
    try:
        import kanryo_mishin
        return kanryo_mishin.ichiran()
    except Exception as e:           # 一覧が作れなくても、完了フォームのリンク自体は送る
        print(f"  ⚠ 未入力の一覧が作れませんでした（プルダウン無しで送ります）: {e}")
        return []


def saisoku_honbun(p):
    """未入力のお客様をまとめて知らせる1通（python3 tools/kanryo-okuru.py --saisoku）。"""
    return "\n".join(
        ["【作業完了フォーム】まだ入っていないお客様が " + str(len(p)) + " 名います"]
        + ["・" + x["d"][5:].replace("-", "/") + " " + x["n"] + " さま" for x in p]
        + ["", "こちらから、お客様を選んで入れてください。", kaku({"p": p, "st": 1})])


def honbun(y, p=None):
    hoka = [x for x in (p or []) if x.get("r") != y.get("台帳")]
    return "\n".join([
        "【作業完了フォーム】" + y.get("氏名", "") + " さま",
        f"{y.get('施工日付','')} {y.get('開始時刻','')} 開始"
        + ("／おそうじ本舗" if y.get("売上種類") == "本舗" else "／ワンヒッター"),
        "／".join(y.get("メニュー", [])),
        "",
        "作業が終わったら、こちらから入れてください。",
        url(y, p),
        "",
        "最初の画面はお客様に見せるものです（アンケートのQR）。",
        "お客様が回答されている間に、次回のご予約をご提案ください。",
        "アンケートのあと「実はGoogle口コミが一番うれしいので、ぜひご協力をお願いします」とお伝えください（その場で投稿していただく）。",
        "下の「次へ（スタッフ用）」で入力画面に変わります。",
        "",
        "【次回のご予約が取れたら】お名前・電話・住所・今回のメニューが入った受注フォームです。日付と時刻を入れて送るだけです（メニューは変えられます）。",
        jikai_url(y),
    ] + (["", f"※ ほかに作業完了フォームが未入力のお客様が {len(hoka)} 名います（入力画面のお客様欄から選べます）："]
         + ["・" + x["d"][5:].replace("-", "/") + " " + x["n"] + " さま" for x in hoka] if hoka else []))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--all", action="store_true", help="30分の縛りを外して全部送る")
    ap.add_argument("--saisoku", action="store_true", help="未入力のお客様をまとめて1通で知らせる")
    ap.add_argument("--ichiran", action="store_true", help="未入力のお客様の一覧を出すだけ")
    ap.add_argument("--asa", action="store_true", help="今日の施工ぶんを、開始時刻を待たずに1通にまとめて送る（毎朝）")
    a = ap.parse_args()

    if a.ichiran or a.saisoku:
        p = mishin_ichiran()
        print(f"作業完了フォームが未入力：{len(p)}名")
        for x in p:
            print(f"  {x['d']} {x['n']} さま（{x['r']}）")
        if a.saisoku and p:
            txt = saisoku_honbun(p)
            if a.dry_run:
                print("\n--dry-run のため送っていません。\n" + txt)
                return
            r = subprocess.run([sys.executable, str(ROOT / "tools" / "line_client.py"), "push", txt],
                               capture_output=True, text=True)
            print("  送りました" if r.returncode == 0 else f"  🔴 送れませんでした: {r.stderr.strip()[:200]}")
        return

    if not YOTEI.exists():
        print("送る材料がありません（data/kanryo-yotei.json）。先に tools/juchu-inbox.py を動かしてください。")
        return
    yotei = json.loads(YOTEI.read_text(encoding="utf-8"))
    sumi = set(json.loads(SUMI.read_text(encoding="utf-8"))) if SUMI.exists() else set()
    ima = datetime.datetime.now(JST)
    yotei = yotei + hyou_kara(yotei, sumi, ima.date())

    # 2026-10-21 直し：受注フォームの開始時刻のまま送っていて、カレンダーで時間を動かした日に
    # 早く送ってしまった（10/18 折田様 15:00 への変更）。今日の分はカレンダーの控えを優先する。
    kyou = ima.date().isoformat()
    for y in yotei:
        if y.get("施工日付") == kyou and y["id"] not in sumi:
            t = cal_kaishi(y.get("氏名", ""), kyou)
            if t and t != str(y.get("開始時刻", ""))[:5]:
                print(f"  開始時刻をカレンダーに合わせます: {y.get('氏名')} {y.get('開始時刻')} → {t}")
                y["開始時刻"] = t

    okuru = []
    for y in yotei:
        if y["id"] in sumi:
            continue
        try:
            h, mi = (int(x) for x in str(y.get("開始時刻", "09:00"))[:5].split(":"))
            kai = datetime.datetime.fromisoformat(y["施工日付"]).replace(
                hour=h, minute=mi, tzinfo=JST)
        except Exception:
            print(f"  ⚠ 日時が読めないので飛ばします: {y['id']}")
            continue
        if a.asa:
            if y.get("施工日付") != kyou:
                continue
        elif not a.all and ima < kai + datetime.timedelta(minutes=SAKI_FUN):
            continue
        if ima > kai + datetime.timedelta(days=2):
            # 2日以上たっているものは送らない（取りこぼしを延々と送り続けないため）
            print(f"  － 古いので送りません: {y.get('氏名')} {y.get('施工日付')}")
            sumi.add(y["id"])
            continue
        okuru.append(y)

    print(f"送る対象: {len(okuru)}件（未送信 {len([y for y in yotei if y['id'] not in sumi])}件中）")
    p = mishin_ichiran() if okuru else []
    for y in okuru:
        print(f"  {y.get('施工日付')} {y.get('開始時刻')} {y.get('氏名')} → {url(y, p)[:80]}…（未入力の一覧 {len(p)}名）")
    if a.asa and okuru:
        okuru.sort(key=lambda y: str(y.get("開始時刻", "")))
        bunsho = [honbun(y, p) for y in okuru]
        midashi = f"【今日の作業完了フォーム】{len(okuru)}件（朝にまとめてお送りします）"
        kugiri = "\n\n――――――――\n\n"
        txt = midashi + "\n\n" + kugiri.join(bunsho)
        # LINE の1通は5,000字まで。超えるときだけ1件ずつに分ける
        tsuu = [txt] if len(txt) <= 4800 else [midashi + "\n\n" + b for b in bunsho]
        if a.dry_run:
            print(f"\n--dry-run のため送っていません（{len(tsuu)}通・{sum(len(x) for x in tsuu)}字）。")
            return
        ok = True
        for x in tsuu:
            r = subprocess.run([sys.executable, str(ROOT / "tools" / "line_client.py"), "push", x],
                               capture_output=True, text=True)
            if r.returncode != 0:
                print(f"  🔴 送れませんでした: {r.stderr.strip()[:200]}")
                ok = False
                break
        if ok:
            print(f"  送りました（{len(tsuu)}通）: " + "、".join(y.get("氏名", "") for y in okuru))
            sumi.update(y["id"] for y in okuru)
        SUMI.write_text(json.dumps(sorted(sumi), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return
    if a.dry_run:
        print("\n--dry-run のため送っていません。")
        return
    for y in okuru:
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "line_client.py"), "push", honbun(y, p)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            print(f"  🔴 送れませんでした: {y.get('氏名')} {r.stderr.strip()[:200]}")
            continue
        print(f"  送りました: {y.get('氏名')}")
        sumi.add(y["id"])
    SUMI.write_text(json.dumps(sorted(sumi), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
