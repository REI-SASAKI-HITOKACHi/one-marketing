#!/usr/bin/env python3
"""リールに当てるBGMを、その場で合成して書き出す。

なぜ自前で作るか：**他人の曲は権利の確認が要るため使わない。**
ここで鳴っているのは合成音だけで、素材を一切借りていないので権利の問題が起きない。

## 2026-10-21 作り直し（オーナー指摘「ゲームボーイ時代のドラクエの葬式みたい」）

前の版が外した原因は4つ。同じ失敗を繰り返さないために残す。

  1. **音が全部サイン波の足し算だった** → 倍音の作りが単調で、ゲーム機の音に聞こえる
  2. **84BPMで、2小節ぶん伸びるパッドに長い残響をかけていた** → 教会・葬式の響き
  3. **打楽器が無く、拍が無かった** → 曲が浮いて、沈んだ感じになる
  4. **低いところでマイナー7thを鳴らしていた**（Am7）→ 暗い

この版の方針（上の逆をやる）:
  - **撥弦の物理モデル（Karplus-Strong）**で弾く音を作る。サイン波の足し算をやめた
  - **104BPM**。キックを1拍目と3拍目に置いて拍を作る。ハイハットで8分を刻む
  - **B♭メジャーの I - IV - V - I**（B♭ → E♭ → F → B♭）。マイナーコードを使わない
  - パッドは**高いところで小さく**。低い持続音（ドローン）を置かない
  - 残響は0.55秒まで。弾く音とパッドだけに薄くかける

使い方:
  python3 tools/make-reel-bgm.py 23.1 dist/ad-reels/bgm.wav
  python3 tools/make-reel-bgm.py --all          # data/ad-reels.json の各本の長さで作る

要るもの: pip3 install numpy
"""
import argparse
import pathlib
import sys
import wave

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
SR = 44100

# 3案。音を聴いて選べるように、作りを変えたものを並べてある。
# 既定は "a"。build(dur, style="b") のように呼び分ける。
STYLES = {
    "a": {"名": "軽快（キックあり）", "bpm": 104, "kick": 0.52, "hat": 1.0,
          "stab": 0.17, "pluck": 1.0, "pad": 0.085, "arp": "8分"},
    "b": {"名": "落ち着き（打楽器なし）", "bpm": 98, "kick": 0.0, "hat": 0.45,
          "stab": 0.13, "pluck": 1.0, "pad": 0.11, "arp": "8分"},
    "c": {"名": "きびきび（速め・刻み細かめ）", "bpm": 116, "kick": 0.50, "hat": 1.15,
          "stab": 0.20, "pluck": 0.9, "pad": 0.07, "arp": "16分混"},
    "d": {"名": "調査版D・はっきり", "研究": True},
    "e": {"名": "調査版E・やわらかめ", "研究": True, "soft": True},
}

# B♭メジャー。I - IV - V - I。マイナーコードを使わない（暗くしないため）
CHORDS = [
    {"notes": [58, 62, 65, 70], "bass": 46},   # B♭
    {"notes": [58, 63, 67, 70], "bass": 46},   # E♭/B♭（低音を動かさず明るさだけ変える）
    {"notes": [57, 60, 65, 69], "bass": 53},   # F
    {"notes": [58, 62, 65, 70], "bass": 46},   # B♭
]
ARP = [0, 2, 1, 3, 2, 0, 1, 2]                 # 1小節ぶんの8分音符。和音の何番目か


def hz(midi):
    return 440.0 * 2.0 ** ((midi - 69) / 12.0)


def place(buf, start, sig, gain=1.0):
    i = int(start * SR)
    if i < 0:
        sig = sig[-i:]
        i = 0
    j = min(len(buf), i + len(sig))
    if j > i:
        buf[i:j] += sig[: j - i] * gain


def lowpass(x, fc):
    n = len(x)
    f = np.fft.rfftfreq(n, 1.0 / SR)
    return np.fft.irfft(np.fft.rfft(x) / np.sqrt(1.0 + (f / fc) ** 2), n)


def highpass(x, fc):
    n = len(x)
    f = np.fft.rfftfreq(n, 1.0 / SR)
    h = (f / fc) / np.sqrt(1.0 + (f / fc) ** 2)
    return np.fft.irfft(np.fft.rfft(x) * h, n)


def fftconv(x, ir):
    m = 1 << (len(x) + len(ir) - 2).bit_length()
    return np.fft.irfft(np.fft.rfft(x, m) * np.fft.rfft(ir, m), m)[: len(x)]


def pluck(f, dur, amp, damp=0.4965, bright=0.5, seed=0):
    """撥弦の物理モデル（Karplus-Strong）。弦を弾いた音が出る。

    雑音を1周期ぶん詰めた輪を回し、1周ごとに隣と平均して高い成分から減らす。
    サイン波の足し算と違って倍音が自然に減るので、ゲーム機の音にならない。
    1周期ぶんをひと塊として進めればnumpyで一気に計算できる。
    """
    n = int(dur * SR)
    N = max(8, int(round(SR / f)))
    rng = np.random.default_rng(seed)
    buf = rng.standard_normal(N)
    buf = buf * (1 - bright) + np.convolve(buf, np.ones(3) / 3, mode="same") * bright
    buf -= buf.mean()
    out = np.empty(((n // N) + 2) * N)
    cur = buf
    for b in range((n // N) + 2):
        out[b * N:(b + 1) * N] = cur
        nxt = damp * (cur + np.roll(cur, 1))        # 輪を1周して隣と平均（高域が落ちる）
        cur = nxt
    y = out[:n]
    t = np.arange(n) / SR
    y = y * np.exp(-t / (dur * 0.55))               # 全体もゆるやかに消す
    y[: int(0.002 * SR)] *= np.linspace(0, 1, int(0.002 * SR))
    peak = np.abs(y).max()
    return y * (amp / peak) if peak > 0 else y


def ep_stab(freqs, dur, amp):
    """エレピ風の和音。のこぎり波をローパスで閉じて、短く切る"""
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for f in freqs:
        for det in (0.997, 1.003):
            ph = 2 * np.pi * f * det * t
            for k in range(1, 11):
                out += np.sin(k * ph) / k
    out = lowpass(out / (len(freqs) * 14), 2200)
    env = np.minimum(1.0, t / 0.008) * np.exp(-t / (dur * 0.42))
    return out * env * amp


def pad(freqs, dur, amp):
    """高いところで小さく鳴らす。低い持続音は置かない（沈んで聞こえるため）"""
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for f in freqs:
        for det, a in ((0.9988, 0.5), (1.0012, 0.5)):
            out += a * np.sin(2 * np.pi * f * det * t)
    out = lowpass(out / len(freqs), 2600)
    env = np.minimum(1.0, t / 0.55) * np.clip((dur - t) / 0.55, 0, 1)
    return out * env * amp


def bass(f, dur, amp):
    """短く弾く低音。伸ばさない"""
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.sin(2 * np.pi * f * t) + 0.22 * np.sin(2 * np.pi * f * 2 * t)
    out = np.tanh(out * 1.3)
    env = np.minimum(1.0, t / 0.012) * np.exp(-t / (dur * 0.38))
    return out * env * amp


def kick(amp):
    """1拍目と3拍目。これが無いと曲が浮いて沈んだ感じになる"""
    n = int(0.26 * SR)
    t = np.arange(n) / SR
    f = 46 + 86 * np.exp(-t / 0.028)                 # 120Hz付近から46Hzへ落とす
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.085)
    rng = np.random.default_rng(5)
    y += rng.standard_normal(n) * np.exp(-t / 0.004) * 0.25
    return np.tanh(y * 1.5) * amp


def hat(amp, seed, dur=0.045):
    n = int(dur * SR)
    t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    y = highpass(rng.standard_normal(n), 7000)
    return y * np.exp(-t / (dur * 0.3)) * amp


def reverb(x, mix, decay=0.55, seed=7):
    n = int(decay * SR)
    t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    ir = rng.standard_normal(n) * np.exp(-t / (decay / 3.0))
    ir = lowpass(ir, 4200)
    ir[0] = 1.0
    ir /= np.abs(ir).sum() ** 0.5 * 2.8
    return (1 - mix) * x + mix * fftconv(x, ir)


def build(dur, style="d"):
    if STYLES[style].get("研究"):
        return build_research(dur, soft=STYLES[style].get("soft", False))
    st = STYLES[style]
    BEAT = 60.0 / st["bpm"]
    BAR = BEAT * 4
    n = int(dur * SR) + SR
    plk = np.zeros(n)
    stab = np.zeros(n)
    pd = np.zeros(n)
    bs = np.zeros(n)
    dr = np.zeros(n)

    bar = 0
    while bar * BAR < dur + BAR:
        ch = CHORDS[(bar // 2) % len(CHORDS)]
        t0 = bar * BAR
        ns = ch["notes"]

        if bar % 2 == 0:
            place(pd, t0, pad([hz(m + 12) for m in ns], BAR * 2 + 0.4, st["pad"]))

        # 低音：1拍目と、3拍目のウラ。伸ばさない
        place(bs, t0, bass(hz(ch["bass"]), BEAT * 1.5, 0.40))
        place(bs, t0 + BEAT * 2.5, bass(hz(ch["bass"]), BEAT * 1.1, 0.30))

        # エレピの和音は2拍目と4拍目（ウラ拍）に置いて、ノリを作る
        for b in (1, 3):
            place(stab, t0 + b * BEAT, ep_stab([hz(m) for m in ns], BEAT * 0.9, st["stab"]))

        # 撥弦のアルペジオ
        for i, step in enumerate(ARP):
            t = t0 + i * BEAT / 2
            m = ns[step] + 12
            if bar % 2 == 1 and i in (3, 7):
                m += 12
            amp = (0.34 if i % 2 == 0 else 0.24) * st["pluck"]
            place(plk, t, pluck(hz(m), 1.5, amp, seed=bar * 17 + i))
            if st["arp"] == "16分混" and i in (2, 6):   # ウラに16分を1個ずつ足す
                place(plk, t + BEAT / 4, pluck(hz(ns[(step + 1) % 4] + 12), 1.1,
                                               amp * 0.55, seed=bar * 41 + i))

        # 打楽器
        if st["kick"] > 0:
            for b in (0, 2):
                place(dr, t0 + b * BEAT, kick(st["kick"]))
        for i in range(8):
            place(dr, t0 + i * BEAT / 2,
                  hat((0.055 if i % 2 == 0 else 0.034) * st["hat"], bar * 31 + i))
        bar += 1

    mix = (reverb(plk, 0.17) + reverb(stab, 0.12, seed=11)
           + reverb(pd, 0.20, seed=3) + bs + dr)
    mix = mix[: int(dur * SR)]
    mix = highpass(mix, 32)                          # 下の濁りを取る

    t = np.arange(len(mix)) / SR
    mix *= np.minimum(1.0, t / 0.25)                 # 入りは短く（すぐ始める）
    mix *= np.clip((dur - t) / 1.6, 0.0, 1.0) ** 1.2  # 終わりで消す

    mix = np.tanh(mix * 1.25) / 1.25
    peak = np.abs(mix).max()
    if peak > 0:
        mix *= 0.76 / peak

    d = int(SR * 0.008)
    left = mix.copy()
    right = np.concatenate([np.zeros(d), mix[:-d]]) * 0.94 + mix * 0.06
    return np.stack([left, right], axis=1)


# ──────────────────────────────────────────────────────────────────────
# 2026-10-21 調査版（オーナー指示「人間が気になる、離脱し辛くなるBGM」）
#
# 音楽心理学で根拠のあるものだけを設計に落とした。出典は
# docs/BGM-離脱しにくい音楽の調査-2026-10-21.md に全部書いてある。
#
#   1. テンポは120BPM
#      人が自然に刻む速さ（spontaneous motor tempo）は概ね100〜120BPM。
#      Fraisse の古典では「いちばん心地よい」間隔が500〜700ms＝86〜120BPM。
#      注意はこの周期に同期しやすい（dynamic attending theory）
#   2. 拍をはっきりさせたうえで、適度にズラす
#      Witek 2014 は「中くらいのシンコペーション」で快と動きたさが最大（逆U字）としたが、
#      Senn・Witek 2024 はこれを再現できず、「単純な型は拍の明快さで、複雑な型は面白さで
#      踊りたくさせる」と整理した。**どちらの説明でも、ズレも明快さも無い平坦な型がいちばん悪い。**
#      → 2・4拍目に手拍子（拍を明快に）＋ 低音と一部のキックをウラに置く（適度なズレ）
#   3. 低音を入れる
#      Cameron 2022（Current Biology）：聞こえない超低音を足すと、客の動きが平均11.8%増えた。
#      ただし**スマホの内蔵スピーカーは超低音を鳴らせない**ので、効くのはイヤホンの人だけ
#   4. 耳に残る旋律の作り（Jakubowski 2017）
#      耳に残る曲は「速め」「よくある山なりの輪郭（上がって下がる）」
#      「ただし途中に普通でない跳躍がある」。→ 8音の動機を山なりにして、4音目で大きく跳ばせた
#   5. 同じことを20秒続けると慣れる
#      → 4小節ごとに作りを変える。ループの変わり目で1拍だけ全部止める（次が気になる）
#   6. 終わりを解決させない
#      最後をドミナント（F）で終える。閉じないほうが引っぱられる
#   7. 頭の1秒から鳴らす（フェードインしない）

# B♭メジャー。I - V - IV - V。マイナーコードを使わない。Vで終えて解決させない
PROG_D = [
    {"notes": [58, 62, 65, 70], "bass": 46},   # B♭
    {"notes": [57, 60, 65, 69], "bass": 41},   # F
    {"notes": [58, 63, 67, 70], "bass": 39},   # E♭
    {"notes": [57, 60, 65, 69], "bass": 41},   # F
]
# 8分音符8個の動機。山なりに上がって下がる。4音目(86)で大きく跳ぶのが「普通でない跳躍」
MOTIF = [70, 74, 77, 86, 82, 79, 75, 74]


def clap(amp, seed=9):
    """2拍目と4拍目。拍を明快にする。雑音を少しずらして重ねると手拍子に聞こえる"""
    n = int(0.22 * SR)
    t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    base = rng.standard_normal(n)
    y = np.zeros(n)
    for d, a in ((0, 1.0), (0.009, 0.7), (0.017, 0.5), (0.026, 0.35)):
        i = int(d * SR)
        y[i:] += base[: n - i] * a
    y = highpass(lowpass(y, 5200), 1100)
    return y * np.exp(-t / 0.055) * amp


def sub(f, dur, amp):
    """超低音。スマホのスピーカーでは鳴らないが、イヤホンでは効く（Cameron 2022）"""
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = np.sin(2 * np.pi * f * t)
    env = np.minimum(1.0, t / 0.015) * np.exp(-t / (dur * 0.45))
    return y * env * amp


def build_research(dur, soft=False):
    """調査版。上のコメントの7項目をそのまま形にしたもの。
    soft=True は打楽器を控えめにした版（同じ設計で、耳あたりだけ変える）"""
    pz = 0.55 if soft else 1.0
    BEAT = 60.0 / 120.0
    BAR = BEAT * 4
    n = int(dur * SR) + SR
    plk = np.zeros(n); stab = np.zeros(n); pd = np.zeros(n)
    bs = np.zeros(n); sb = np.zeros(n); dr = np.zeros(n)

    bar = 0
    while bar * BAR < dur + BAR:
        ch = PROG_D[bar % 4]
        t0 = bar * BAR
        ns = ch["notes"]
        phase = (bar // 4) % 2          # 4小節ごとに作りを変える（慣れさせない）
        last = (bar * BAR + BAR) > dur  # 最後の小節

        place(pd, t0, pad([hz(m + 12) for m in ns], BAR + 0.3, 0.075 if phase else 0.055))

        # 低音：1拍目（オモテ）＋ 2拍目のウラ・3拍目のウラ（ズラす）
        for off, g in ((0.0, 1.0), (BEAT * 1.5, 0.72), (BEAT * 2.5, 0.66)):
            place(bs, t0 + off, bass(hz(ch["bass"] + 12), BEAT * 0.85, 0.34 * g))
            place(sb, t0 + off, sub(hz(ch["bass"] - 12), BEAT * 0.8, 0.30 * g))

        # 手拍子：2拍目と4拍目。これで拍が分かる
        if not last:
            for b in (1, 3):
                place(dr, t0 + b * BEAT, clap(0.30 * pz, seed=bar * 7 + b))
            # キック：1拍目（オモテ）と3拍目のウラ（ズラす）
            place(dr, t0, kick(0.50 * (0.85 if soft else 1.0)))
            place(dr, t0 + BEAT * 2.5, kick(0.42 * (0.85 if soft else 1.0)))
            for i in range(8):
                g = 0.040 if i % 2 == 0 else 0.055     # ウラを少し強く（前に進む感じ）
                place(dr, t0 + i * BEAT / 2, hat(g * (1.15 if phase else 1.0) * pz, bar * 31 + i))

        # エレピの和音は2拍目のウラと4拍目のウラ
        for off in (BEAT * 1.5, BEAT * 3.5):
            place(stab, t0 + off, ep_stab([hz(m) for m in ns], BEAT * 0.8, 0.15))

        # 動機（8分8個）。山なりで、4音目に大きな跳躍
        for i, m in enumerate(MOTIF):
            if bar % 4 == 3 and i >= 6:
                continue                                # ループの変わり目で止める（次が気になる）
            mm = m + (12 if phase and i in (3, 4) else 0)
            amp = 0.36 if i in (0, 3) else 0.25         # 頭と跳躍の音を強く
            place(plk, t0 + i * BEAT / 2, pluck(hz(mm), 1.4, amp, seed=bar * 17 + i))
        bar += 1

    mix = (reverb(plk, 0.15) + reverb(stab, 0.10, seed=11)
           + reverb(pd, 0.18, seed=3) + bs + sb + dr)
    mix = mix[: int(dur * SR)]
    mix = highpass(mix, 26)
    if soft:
        mix = lowpass(mix, 7000)     # 高域を少し落として、耳あたりを柔らかくする

    t = np.arange(len(mix)) / SR
    mix[: int(0.01 * SR)] *= np.linspace(0, 1, int(0.01 * SR))   # 頭から鳴らす
    mix *= np.clip((dur - t) / 1.1, 0.0, 1.0) ** 1.1             # 終わりは短く切る
    mix = np.tanh(mix * 1.3) / 1.3
    peak = np.abs(mix).max()
    if peak > 0:
        mix *= 0.80 / peak
    d = int(SR * 0.007)
    right = np.concatenate([np.zeros(d), mix[:-d]]) * 0.94 + mix * 0.06
    return np.stack([mix, right], axis=1)


def write_wav(path, st):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (np.clip(st, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dur", nargs="?", type=float)
    ap.add_argument("out", nargs="?")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--style", default="d", choices=list(STYLES))
    ap.add_argument("--candidates", action="store_true", help="3案の試聴用を dist/bgm-候補/ に出す")
    a = ap.parse_args()
    if a.candidates:
        out = ROOT / "dist" / "bgm-候補"
        for k, v in STYLES.items():
            p = out / f"BGM{v['名']}.wav" if v.get("研究") else out / f"BGM案{k.upper()}-{v['名']}.wav"
            write_wav(p, build(16.0, style=k))
            print(f"できた {p}")
        return
    if a.all:
        import json
        from importlib.machinery import SourceFileLoader
        reels = json.loads((ROOT / "data" / "ad-reels.json").read_text(encoding="utf-8"))["reels"]
        b = SourceFileLoader("b", str(ROOT / "tools" / "build-ad-reels.py")).load_module()
        for r in reels:
            _, total = b.timeline(r["scenes"])
            p = ROOT / "dist" / "ad-reels" / f"bgm-{r['id']}.wav"
            write_wav(p, build(total, style=a.style))
            print(f"できた {p}  {total:.1f}秒")
        return
    if a.dur is None or a.out is None:
        sys.exit("長さ（秒）と出力先を渡してください")
    write_wav(pathlib.Path(a.out), build(a.dur, style=a.style))
    print(f"できた {a.out}  {a.dur:.1f}秒")


if __name__ == "__main__":
    main()
