"""render.py — 把结果渲染成 WAV（可试听）和 PNG（可视化对照）。"""
from __future__ import annotations

import os
import struct
import wave

import numpy as np

import ocarina as oc
import smf

SR = 44100


def _tone(freq: float, dur: float, kind: str = "ocarina") -> np.ndarray:
    n = max(1, int(dur * SR))
    t = np.arange(n) / SR
    if kind == "ocarina":
        # 陶笛：接近正弦 + 少量二次谐波，带一点气声和颤音
        vib = 1 + 0.004 * np.sin(2 * np.pi * 5.2 * t)
        w = (np.sin(2 * np.pi * freq * t * vib)
             + 0.20 * np.sin(2 * np.pi * 2 * freq * t * vib)
             + 0.07 * np.sin(2 * np.pi * 3 * freq * t * vib)
             + 0.02 * np.sin(2 * np.pi * 4 * freq * t * vib))
        w *= 1.0 + 0.02 * np.sin(2 * np.pi * 7.3 * t)
    else:
        # 原曲用「柔和长笛」音色，方便对比
        w = (np.sin(2 * np.pi * freq * t)
             + 0.35 * np.sin(2 * np.pi * 2 * freq * t)
             + 0.12 * np.sin(2 * np.pi * 3 * freq * t))
    # ADSR
    a = max(1, int(0.012 * n))
    d = max(1, int(0.05 * n))
    r = max(1, int(0.10 * n))
    env = np.ones(n)
    env[:a] = np.linspace(0, 1, a)
    env[a:a + d] *= np.linspace(1, 0.75, d)
    env[-r:] *= np.linspace(1, 0, r)
    return w * env


def write_wav(path: str, mono: np.ndarray) -> None:
    data = np.clip(mono, -1, 1)
    pcm = (data * 32767).astype("<i2")
    with wave.open(path, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SR)
        f.writeframes(pcm.tobytes())


def render(seq, bpm: float, path: str, kind: str = "ocarina",
           pad: float = 1.0) -> None:
    """seq: [(beat, dur, midi)]"""
    if not seq:
        return
    spb = 60.0 / bpm
    total = max(b + d for b, d, _ in seq) + pad
    buf = np.zeros(int(total * spb * SR) + SR)
    for beat, dur, pitch in seq:
        f = 440.0 * 2 ** ((pitch - 69) / 12)
        s = int(beat * spb * SR)
        w = _tone(f, dur * spb, kind) * 0.22
        e = min(len(buf), s + len(w))
        buf[s:e] += w[:e - s]
    # 简易软限幅，避免爆音
    buf = np.tanh(buf * 1.1)
    write_wav(path, buf)


def piano_roll(mel, notes, path: str, title: str = "") -> None:
    """左边：原曲旋律；右边：陶笛 5 音版 + 映射连线。"""
    from PIL import Image, ImageDraw, ImageFont

    W, H = 1500, 560
    L, R, T, B = 70, 30, 46, 46
    img = Image.new("RGB", (W, H), (250, 249, 246))
    d = ImageDraw.Draw(img)

    lo = min(min(m.pitch for m in mel), min(n.pitch for n in notes)) - 2
    hi = max(max(m.pitch for m in mel), max(n.pitch for n in notes)) + 2
    span = max(1, hi - lo)
    tmax = max(max(m.end for m in mel), max(n.beat + n.dur for n in notes))

    def X(beat: float) -> float:
        return L + (W - L - R) * (beat / tmax)

    def Y(p: int) -> float:
        return T + (H - T - B) * (1 - (p - lo) / span)

    # 横线（每个半音）与陶笛音高线
    for p in range(lo, hi + 1):
        y = Y(p)
        col = (232, 230, 224) if p % 12 else (206, 202, 192)
        d.line([(L, y), (W - R, y)], fill=col, width=1)
        if p in oc.PITCHES:
            d.line([(L, y), (W - R, y)], fill=(255, 196, 120), width=2)
    # 竖线（每拍）
    for b in range(0, int(tmax) + 1, 4):
        x = X(b)
        d.line([(x, T), (x, H - B)], fill=(222, 219, 212), width=1)

    # 原曲
    for m in mel:
        x0, x1 = X(m.beat), X(m.end)
        y = Y(m.pitch)
        d.rectangle([x0, y - 5, max(x1, x0 + 2), y + 5], fill=(120, 120, 132))
    # 陶笛版
    for n in notes:
        x0, x1 = X(n.beat), X(n.beat + n.dur)
        y0, y1 = Y(n.pitch), Y(n.src)
        d.line([(x0 + 3, y0), (x0 + 3, y1)], fill=(240, 170, 90), width=1)
        d.rectangle([x0, y0 - 6, max(x1, x0 + 2), y0 + 6], fill=(214, 96, 36))
    # 图例
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 16)
        small = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 14)
    except Exception:
        font = ImageFont.load_default()
        small = font
    d.text((L, 12), title or "Ballad of the Wind Fish", fill=(40, 40, 44), font=font)
    d.text((L, H - 30), "灰蓝 = 原曲旋律    橙 = 陶笛版（细线指向它替换掉的原音）",
           fill=(90, 90, 96), font=small)
    # 纵轴音名
    for p in range(lo, hi + 1):
        if p % 12 in (0, 2, 4, 5, 7, 9, 11) and p - lo > 0:
            d.text((8, Y(p) - 7), smf.note_name(p), fill=(140, 138, 132), font=small)
    img.save(path)

