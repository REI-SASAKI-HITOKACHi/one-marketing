#!/usr/bin/env python3
"""11月のネット予約に「防カビコート無料（3,300円相当）」を付ける（依頼 20261024-04-lp・第8回MTG 8-4 No.4）。

    python3 tools/bokabi-1024.py          # deploy/machi/bokabi/ に予約ページと LP の下書きを作る（配信しない）

オーナー（MTG 中・業務連絡LINE 463〜465）原文「防カビ無料も入れていいんだよ」。配信は嶺さんの OK のあと。

決めたこと（確認ページで嶺さんに見せる。違えば直す）：
- 対象：予約ページから申し込み、作業日が 2026年11月、エアコンクリーニング（ノーマル／お掃除機能付き）を含むご予約
- 無料にするのは **1回のご予約につきエアコン1台分の防カビコート（3,300円）**（「台数分」にするなら KAZU を変える）
- 金額の合計は変えない。金額の欄に「防カビコート（エアコン1台分） ~~¥3,300~~ 無料」の行を足すだけ
  （防カビコートは予約ページのメニューに無く、もともと合計に入っていないため）
- 早期予約の10%引きとの併用は可（CMO：嶺さんは条件を付けていない）
- 「ご希望の内容」の末尾に「＋防カビコート無料（11月ネット予約）」を付ける（予約_Web と通知で和真さんに伝わる）
- LP の帯は、エアコンLP（C・E・/aircon/）だけ（CMO 10/25。水まわりLPは対象メニューが無いので入れない）
- 日付を選ぶ画面で11月の日付を選んだら「11月の作業なので、防カビコート…が無料になります」と1行出す
- 日付を選ぶ前にエアコンを選んでいたら、金額の下の注記に「11月の作業なら、防カビコートが無料」と出す

元にするのは本番と同じ予約ページ（cmo ブランチの lp/booking/index.html。lp ブランチのものは古い）。
"""
import argparse
import importlib.util
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC_REF = "origin/claude/one-hitter-cmo-strategy-5qk4ux:lp/booking/index.html"
KAZU = "1台分"
MARK = "S.bokabi"

CONF = ("\n  /* 11月のネット予約は防カビコート無料（tools/bokabi-1024.py・オーナー 10/24）。合計は変えず、行を出すだけ */\n"
        "  S.bokabi = {tsuki: '2026-11', gaku: 3300, kazu: '" + KAZU + "', "
        "taisho: ['エアコンクリーニング（ノーマル）', 'エアコンクリーニング（お掃除機能付き）']};\n"
        "  function bokabiAircon(){ return S.bokabi.taisho.some(function(n){ return (state.qty[n] || 0) > 0; }); }\n"
        "  function bokabiOf(){ return (state.date && state.date.slice(0, 7) === S.bokabi.tsuki && bokabiAircon()) ? S.bokabi.gaku : 0; }\n")

EDITS = [
    # 金額の計算：bokabi を返すだけ（合計 gokei は変えない）
    ("      kasan: kasan, gokei: shoukei - waribiki - netto + kasan,\n",
     "      kasan: kasan, gokei: shoukei - waribiki - netto + kasan,\n      bokabi: bokabiOf(),\n"),
    # 金額の欄：防カビの行
    ("    if (k.kasan) {\n      h.push(ln('繁忙期加算（' + k.kasho + '箇所）', '+' + yen(k.kasan), 'add'));\n    }\n",
     "    if (k.kasan) {\n      h.push(ln('繁忙期加算（' + k.kasho + '箇所）', '+' + yen(k.kasan), 'add'));\n    }\n"
     "    if (k.bokabi) {\n      h.push(ln('防カビコート（エアコン' + S.bokabi.kazu + '）', '<s>' + yen(k.bokabi) + '</s> 無料', 'off'));\n    }\n"),
    # 日付を選ぶ前の注記
    ("           (state.date ? '' : '日時をお選びいただくと、割引と加算を反映した金額になります。') + '</p>');",
     "           (state.date ? '' : '日時をお選びいただくと、割引と加算を反映した金額になります。') +\n"
     "           (!state.date && bokabiAircon() ? '11月の作業なら、防カビコート（エアコン' + S.bokabi.kazu + '・3,300円）が無料になります。' : '') + '</p>');"),
    # ご希望の内容（予約_Web・通知・確認画面）
    ("      if (q > 0) { a.push(m.n + (q > 1 ? ' ×' + q : '')); }\n    });\n    return a.join('／');",
     "      if (q > 0) { a.push(m.n + (q > 1 ? ' ×' + q : '')); }\n    });\n"
     "    return a.join('／') + (bokabiOf() ? '＋防カビコート無料（11月ネット予約・エアコン' + S.bokabi.kazu + '）' : '');"),
    # 日付を選ぶ画面：11月の日付を選んだら1行出す（金額の欄は最初の画面と確認の画面にしか無いため）
    ('        <p class="why" id="pre-note" hidden></p>\n',
     '        <p class="why" id="pre-note" hidden></p>\n        <p class="why" id="bokabi-note" hidden></p>\n'),
    ("          drawTotal();\n          $('e2').textContent = '';\n",
     "          drawTotal();\n          $('e2').textContent = '';\n"
     "          var bn = $('bokabi-note');\n"
     "          if (bn) { bn.hidden = !bokabiOf(); bn.textContent = '11月の作業なので、防カビコート（エアコン' + S.bokabi.kazu + '・3,300円）が無料になります。'; }\n"),
]


def kaeru(s, old, new):
    n = s.count(old)
    if n != 1:
        sys.exit(f"想定と違う：{old[:60]!r} が {n} か所（1 か所のはず）。予約ページが変わった可能性。止めます")
    return s.replace(old, new)


def booking(h):
    if MARK in h:
        return h
    i = h.find("  var S = {")
    j = h.find("};\n", i)
    if i < 0 or j < 0:
        sys.exit("予約ページの設定（var S）が見つかりません")
    h = h[:j + 3] + CONF + h[j + 3:]
    for a, b in EDITS:
        h = kaeru(h, a, b)
    return h


# LP の 11月の帯
AIRCON_OLD = '<p class="nov-in"><b>11月の作業は、エアコン1台10%引き</b><span class="nov-sub">ノーマル 9,702円・お掃除機能付き 15,642円</span>'
AIRCON_NEW = ('<p class="nov-in"><b>11月の作業は、エアコン1台10%引き</b>'
              '<span class="nov-sub">ネット予約なら防カビコート無料。ノーマル 9,702円・お掃除機能付き 15,642円</span>')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "deploy" / "machi" / "bokabi"))
    ap.add_argument("--src", default=str(ROOT / "deploy" / "netlify"))
    a = ap.parse_args()
    out, srcdir = pathlib.Path(a.out), pathlib.Path(a.src)
    src = subprocess.run(["git", "-C", str(ROOT), "show", SRC_REF], capture_output=True, text=True, check=True).stdout
    (out / "booking").mkdir(parents=True, exist_ok=True)
    (out / "booking" / "index.html").write_text(booking(src), encoding="utf-8")
    for d in ("aircon-c", "aircon-e"):
        h = (srcdir / d / "index.html").read_text(encoding="utf-8")
        (out / d).mkdir(parents=True, exist_ok=True)
        (out / d / "index.html").write_text(h if "ネット予約なら防カビコート無料" in h else kaeru(h, AIRCON_OLD, AIRCON_NEW), encoding="utf-8")
    # /aircon/ は直した C から作り直す（C対E の入口）
    spec = importlib.util.spec_from_file_location("furiwake", ROOT / "tools" / "furiwake-aircon.py")
    fw = importlib.util.module_from_spec(spec); spec.loader.exec_module(fw)
    h = fw.make((out / "aircon-c" / "index.html").read_text(encoding="utf-8"))
    if fw.tenken(h):
        sys.exit("/aircon/ の作り直しで NG: " + "／".join(fw.tenken(h)))
    (out / "aircon").mkdir(parents=True, exist_ok=True)
    (out / "aircon" / "index.html").write_text(h, encoding="utf-8")
    print(f"書き出しました: {out}/booking・aircon-c・aircon-e・aircon（/aircon/ は直した C の写し）")


if __name__ == "__main__":
    main()
