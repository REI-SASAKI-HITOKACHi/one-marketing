#!/usr/bin/env python3
"""広告リールに当てるBGMを、その場で合成して書き出す。

なぜ自前で作るか：**他人の曲は権利の確認が要るため使わない。**
ここで鳴っているのは全部サイン波の足し合わせで、素材を一切借りていないので、
Instagram／Facebook に出しても権利の問題が起きない。

音の作り：F メジャー・84BPM・8小節（約22.9秒）。
  Fmaj7 → Am7 → B♭maj7 → Csus
  ベル（鉄琴寄り）のアルペジオ＋パッド＋低音＋ごく小さいシェイカー。
  打楽器は入れない（施工写真に合わせて、静かで清潔な音にする）。

使い方:
  python3 tools/make-reel-bgm.py 23.1 dist/ad-reels/bgm-23.1.wav
  python3 tools/make-reel-bgm.py --all          # data/ad-reels.json の各本の長さで作る

要るもの: pip3 install numpy
"""
import argparse
import json
import pathlib
import struct
import sys
import wave

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
SR = 44100
BPM = 84.0
BEAT = 60.0 / BPM
BAR = BEAT * 4

# F メジャー。2小節ごとに1和音
CHORDS = [
    {"pad": [53, 57, 60, 64], "bass": 41},   # Fmaj7
    {"pad": [57, 60, 64, 67], "bass": 45},   # Am7
    {"pad": [58, 62, 65, 69], "bass": 46},   # B♭maj7
    {"pad": [60, 65, 67, 72], "bass": 48},   # Csus
]
# 1小節ぶんの8分音符。数字は和音の何番目か。None は休み
ARP = [0, 1, 2, 3, None, 2, 1, 2]


def hz(midi):
    return 440.0 * 2.0 ** ((midi - 69) / 12.0)


def place(buf, start, sig):
    i = int(start * SR)
    if i < 0:
        sig = sig[-i:]
        i = 0
    j = min(len(buf), i + len(sig))
    if j > i:
        buf[i:j] += sig[: j - i]


def bell(f, dur, amp):
    """ベル／鉄琴寄りの音。倍音を足して、指数で減衰させる"""
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for k, (mult, a, dec) in enumerate([(1, 1.0, 1.9), (2, 0.34, 1.4),
                                        (3, 0.15, 1.1), (4.02, 0.07, 0.9)]):
        out += a * np.sin(2 * np.pi * f * mult * t) * np.exp(-t / dec)
    atk = np.minimum(1.0, t / 0.004)                  # 立ち上がりを丸めて、プツッと鳴らない
    return out * atk * amp / 1.56


def pad(freqs, dur, amp):
    """ゆっくり立ち上がる和音。わずかにずらして厚みを出す"""
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for f in freqs:
        for det, a in ((0.9985, 0.5), (1.0015, 0.5)):
            out += a * (np.sin(2 * np.pi * f * det * t)
                        + 0.22 * np.sin(2 * np.pi * f * 2 * det * t))
    env = np.minimum(1.0, t / 0.9) * np.minimum(1.0, (dur - t) / 0.7).clip(0)
    out = out / (len(freqs) * 1.3)
    return out * env * amp


def lowpass(x, fc):
    """一次ローパス相当。角を落として、文字の邪魔をしない音にする（FFTで一気にかける）"""
    n = len(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1.0 / SR)
    return np.fft.irfft(X / np.sqrt(1.0 + (f / fc) ** 2), n)


def fftconv(x, ir):
    n = len(x) + len(ir) - 1
    m = 1 << (n - 1).bit_length()
    y = np.fft.irfft(np.fft.rfft(x, m) * np.fft.rfft(ir, m), m)
    return y[: len(x)]


def bass(f, dur, amp):
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.sin(2 * np.pi * f * t) + 0.18 * np.sin(2 * np.pi * f * 2 * t)
    env = np.minimum(1.0, t / 0.035) * np.exp(-t / (dur * 0.75))
    return out * env * amp


def shaker(dur, amp, seed):
    n = int(dur * SR)
    rng = np.random.default_rng(seed)
    t = np.arange(n) / SR
    noise = rng.standard_normal(n)
    noise = np.diff(noise, prepend=0.0)              # 高域だけ残す簡単な差分
    return noise * np.exp(-t / 0.035) * amp


def reverb(x, mix=0.24, decay=1.3, seed=7):
    rng = np.random.default_rng(seed)
    n = int(decay * SR)
    t = np.arange(n) / SR
    ir = rng.standard_normal(n) * np.exp(-t / (decay / 3.2))
    ir = lowpass(ir, 5000)                           # 高域を落とす。残響がシャリつかないように
    ir[0] = 1.0
    ir /= np.abs(ir).sum() ** 0.5 * 2.6
    return (1 - mix) * x + mix * fftconv(x, ir)


def build(dur):
    n = int(dur * SR) + SR
    arp = np.zeros(n)
    pd = np.zeros(n)
    bs = np.zeros(n)
    sh = np.zeros(n)

    bar = 0
    while bar * BAR < dur + BAR:
        ch = CHORDS[(bar // 2) % len(CHORDS)]
        t0 = bar * BAR
        if bar % 2 == 0:                                  # 和音は2小節に1回
            place(pd, t0, pad([hz(m) for m in ch["pad"]], BAR * 2 + 0.6, 0.30))
            place(bs, t0, bass(hz(ch["bass"]), BAR * 1.7, 0.34))
            place(bs, t0 + BAR, bass(hz(ch["bass"] + 7), BAR * 0.9, 0.16))
        for i, step in enumerate(ARP):
            t = t0 + i * BEAT / 2
            if step is None:
                continue
            m = ch["pad"][step] + 12
            if bar % 2 == 1 and i in (1, 5):
                m += 12                                   # 2小節目はときどき1オクターブ上
            amp = 0.30 if i % 2 == 0 else 0.21
            place(arp, t, bell(hz(m), 2.2, amp))
            if i in (2, 6):
                place(sh, t + BEAT / 4, shaker(0.12, 0.026, bar * 13 + i))
        bar += 1

    pd = lowpass(pd, 1400)
    mix = reverb(arp, mix=0.26) + reverb(pd, mix=0.18, seed=11) + bs + reverb(sh, mix=0.3, seed=3)
    mix = mix[: int(dur * SR)]

    # 入りと終わりをならす。終わりは最後の2.2秒でゆっくり消す
    t = np.arange(len(mix)) / SR
    mix *= np.minimum(1.0, t / 0.9)
    tail = np.clip((dur - t) / 2.2, 0.0, 1.0) ** 1.4
    mix *= tail

    mix = np.tanh(mix * 1.15) / 1.15                       # 軽く頭を抑える
    peak = np.abs(mix).max()
    if peak > 0:
        mix *= 0.72 / peak

    # 左右をほんの少しずらして広げる
    d = int(SR * 0.009)
    left = mix.copy()
    right = np.concatenate([np.zeros(d), mix[:-d]]) * 0.97 + mix * 0.03
    return np.stack([left, right], axis=1)


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
    a = ap.parse_args()
    if a.all:
        reels = json.loads((ROOT / "data" / "ad-reels.json").read_text(encoding="utf-8"))["reels"]
        from importlib.machinery import SourceFileLoader
        b = SourceFileLoader("b", str(ROOT / "tools" / "build-ad-reels.py")).load_module()
        for r in reels:
            _, total = b.timeline(r["scenes"])
            p = ROOT / "dist" / "ad-reels" / f"bgm-{r['id']}.wav"
            write_wav(p, build(total))
            print(f"できた {p}  {total:.1f}秒")
        return
    if a.dur is None or a.out is None:
        sys.exit("長さ（秒）と出力先を渡してください")
    write_wav(pathlib.Path(a.out), build(a.dur))
    print(f"できた {a.out}  {a.dur:.1f}秒")


if __name__ == "__main__":
    main()
