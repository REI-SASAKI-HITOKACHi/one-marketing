#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KDDI Message Cast のデモアカウントで、オーナー宛にテスト送信する。

【なぜ要るか】
  オーナー指示（2026-09-19）「デモアカウントで僕宛にテスト送付して UX を確認してから判断しよう」。
  本舗396名へ 1,188通を送る前に、**届いたものが実機でどう見えるか**を見て決める。

  見てほしいのは3つ：
    ① 発信元に何が表示されるか（`03-5674-8758` のはず。誰も出ないFAX番号）
    ② 3通に割れたとき、境界がどこに来るか。読んで不自然でないか
    ③ 本文に書いた折り返し先（080-1344-3137）が、発信元より先に目に入るか

【いまの状態】
  **APIキーは未取得。アカウントも未発行**（利用開始は 9/25〜9/30 の見込み）。
  このツールは、キーが来たら 1コマンドで送れるように先に置いてある。
  キーが無い状態で実行すると、**送信はせず、送る予定の文面と通の割れ方だけを出す。**

【使い方】
  python3 tools/kddi-test-send.py              # 文面と通の割れ方を出すだけ（送らない）
  python3 tools/kddi-test-send.py --okuru      # 実際に送る（APIキーが要る）

  APIキーは ~/.config/one-hitter/kddi.env に置く（リポジトリには絶対に置かない）:
    KDDI_API_URL=...
    KDDI_API_KEY=...
    KDDI_SENDER=03-5674-8758
"""
import argparse
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
KITEI = os.path.expanduser("~/.config/one-hitter/kddi.env")

# オーナー本人に繋がる番号（2026-09-15 オーナー回答）。和真さんの業務用携帯とは別。
ATESAKI = "080-6817-4796"

# KDDI の数え方（2026-09-07 回答）：70文字まで1通、超過は66文字ごとに1通追加。最大660文字。
SAISHO, TSUZUKI = 70, 66


def tsu_wake(honbun: str):
    """本文を、KDDI が課金する通の単位に割る。"""
    if len(honbun) <= SAISHO:
        return [honbun]
    kire = [honbun[:SAISHO]]
    nokori = honbun[SAISHO:]
    while nokori:
        kire.append(nokori[:TSUZUKI])
        nokori = nokori[TSUZUKI:]
    return kire


def honbun_tsukuru() -> str:
    """テスト用の本文。**実際に送られるものと同じ形**にする。

    出所は `冬季見込み客_2026` の F列（crm が 9/18 に組み替えた 3通版）。
    テンプレートファイル `data/sms-template-honpo.txt` は差し込み前の長い版で、
    そのまま埋めると 7通になる。**送られるのは F列のほう**なので、そちらに合わせる。

    ★お客様には送らない。宛先はオーナー本人の番号に固定してある。
    ★名乗りは本舗。折り返し先は 080-1344-3137（本舗の受付）。
      ワンヒッターの番号 080-8043-8259 は、本舗名義の文面には絶対に入れない。
    """
    return (
        "佐々木さま\n"
        "昨年12月にお掃除機能付きエアコンのクリーニングを担当しました、おそうじ本舗の渡辺です。\n"
        "その後のお困りごとはございませんか。\n"
        "これからの時期は、エアコン・水回り・追い焚き配管のご依頼が増えます。\n"
        "このSMSへの返信・お電話は届きません。\n"
        "ご用件も、ご案内が不要な方も、下記の番号へお知らせください。\n"
        "おそうじ本舗　江戸川中央店　080-1344-3137（渡辺）"
    )


def kagi():
    if not os.path.exists(KITEI):
        return None
    d = {}
    for gyo in pathlib.Path(KITEI).read_text(encoding="utf-8").splitlines():
        gyo = gyo.strip()
        if gyo and not gyo.startswith("#") and "=" in gyo:
            k, v = gyo.split("=", 1)
            d[k.strip()] = v.strip()
    return d if d.get("KDDI_API_KEY") else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--okuru", action="store_true", help="実際に送る（APIキーが要る）")
    a = ap.parse_args()

    honbun = honbun_tsukuru()
    kire = tsu_wake(honbun)

    print(f"宛先: {ATESAKI}（オーナー本人）")
    print(f"名乗り: おそうじ本舗／折り返し先: 080-1344-3137")
    print(f"文字数: {len(honbun)}文字 → {len(kire)}通\n")
    print("─" * 46)
    for i, k in enumerate(kire, 1):
        print(f"【{i}通目 / {len(k)}文字】")
        print(k)
        print("─" * 46)

    ban = "080-1344-3137"
    ichi = honbun.find(ban)
    if ichi >= 0:
        nan_tsu = 1 if ichi < SAISHO else 2 + (ichi - SAISHO) // TSUZUKI
        print(f"\n折り返し先 {ban} は {ichi+1} 文字目＝**{nan_tsu}通目**にあります。")
        if nan_tsu > 1:
            print("　⚠ 1通目には入っていません。1通目だけ読んで発信元に折り返す方には届きません。")
    if "080-8043-8259" in honbun:
        sys.exit("\n🔴 中止：本舗名義の文面にワンヒッターの番号が入っています（2026-09-11 の事故の中身）。")

    k = kagi()
    if not a.okuru:
        print("\n（--okuru を付けていないので送っていません）")
        return
    if not k:
        sys.exit(
            f"\n🔴 送れません。APIキーがありません。\n"
            f"   {KITEI} に KDDI_API_URL / KDDI_API_KEY / KDDI_SENDER を置いてください。\n"
            f"   2026-09-19 時点では、アカウント自体が未発行です（利用開始 9/25〜9/30 の見込み）。")
    sys.exit(
        "\n🔴 送信部分は未実装です。KDDI の API 仕様書（エンドポイント・認証方式・"
        "リクエスト形式）を受け取ってから書きます。\n"
        "   推測で書くと、初回の送信でお客様に出る形が読めないため、ここで止めています。")


if __name__ == "__main__":
    main()
