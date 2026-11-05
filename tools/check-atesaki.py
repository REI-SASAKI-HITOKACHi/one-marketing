#!/usr/bin/env python3
"""外部へ出すメールの宛先を、宛先台帳（data/atesaki-daichou.json）と機械で突き合わせる。

【なぜ】2026-11-05、公式サイトの制作会社への問い合わせが、同じ名前の別会社（info@realize-web.jp）に
  9/11 から4回届いていた。9月に CMO が社名だけで宛先を決め、裏付けを取らなかった。
  オーナー「このミスは重大だよ。取引先相手だったり内容が異なっていた場合は個人情報流出事故になりかねないからね。二度と起こさないで」

【使い方】Gmail の下書きを作る前に、To/CC/BCC を全部渡す。1つでも NG なら下書きを作らない。
    python3 tools/check-atesaki.py support@app-web.jp new@rentracks.co.jp
  社内（one-hitter.her.jp・オーナー・和真さん）は照合しない。
  台帳に無い宛先は、相手から届いたメールの差出人か、オーナーの原文で裏付けを取ってから台帳に足す。
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DAICHOU = ROOT / "data" / "atesaki-daichou.json"
SHANAI_DOMAIN = ("@one-hitter.her.jp",)
SHANAI = {"case.foot.kid@gmail.com", "wk09015963@gmail.com", "onehitter.her@gmail.com"}


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    d = json.loads(DAICHOU.read_text(encoding="utf-8"))
    ok = {x["宛先"].lower(): x for x in d["送ってよい"]}
    ng = {x["宛先"].lower(): x for x in d["送ってはいけない"]}
    bad = 0
    for a in argv:
        a = a.strip().strip("<>,").lower()
        if a in SHANAI or a.endswith(SHANAI_DOMAIN):
            print(f"OK  {a}（社内）")
        elif a in ng:
            bad += 1
            print(f"NG  {a}：送ってはいけない宛先＝{ng[a]['相手']}（{ng[a]['理由']}）")
        elif a in ok:
            print(f"OK  {a}：{ok[a]['相手']}／裏付け {ok[a]['裏付け']}")
        else:
            bad += 1
            print(f"NG  {a}：台帳に無い。相手から届いたメールの差出人かオーナーの原文で裏付けを取り、data/atesaki-daichou.json に足してから")
    if bad:
        print(f"\n✋ {bad}件 NG。下書きを作らないこと。")
        return 1
    print("\n✅ 全部の宛先に裏付けがあります。")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
