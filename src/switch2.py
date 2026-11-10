"""switch2.py — 生成 Switch 2 手把手按键谱。

游戏内陶笛：5 个键 + 左摇杆弯音
    L = D4   R = F4   A = A4   Y = B4   X = D5
    左摇杆：往上推 = 升高，往下推 = 降低（连续，无档位）

做法：把曲子移调到 D 小调（+3 半音，正好是陶笛的本调），
每个音取最近的按键；差 1~2 个半音就用摇杆补，差更多就标记为"近似"。
"""
from __future__ import annotations

import os
import sys

import ocarina as oc
import smf

HERE = os.path.dirname(os.path.abspath(__file__))

BUTTONS = [("L", 62), ("R", 65), ("A", 69), ("Y", 71), ("X", 74)]
BP = [p for _, p in BUTTONS]
BLOW, BHIGH = BP[0], BP[-1]
TRANS = 3                      # +3 半音 -> D 小调


def nearest(p: int, prev: int | None):
    """同一个音永远给同一个指法：先比弯音量，平手时选「往上推」。"""
    best = None
    for name, bp in BUTTONS:
        d = p - bp
        key = (abs(d), -d)
        if best is None or key < best[0]:
            best = (key, name, bp, d)
    return best[1], best[2], best[3]


def mark(d: int) -> tuple[str, bool]:
    if d == 0:
        return "", True
    if abs(d) == 1:
        return ("↑" if d > 0 else "↓"), True
    if abs(d) == 2:
        return ("↑↑" if d > 0 else "↓↓"), True
    return "≈", False


def build(mel):
    folded = oc.fold_phrases(mel, TRANS, window=(BLOW, BHIGH))
    out, prev = [], None
    for m in folded:
        name, bp, d = nearest(m.pitch, prev)
        prev = bp
        mk, ok = mark(d)
        out.append(dict(beat=m.beat, dur=m.dur, pitch=m.pitch,
                        btn=name, d=d, mk=mk, exact=ok))
    return out


def phrase_lines(seq, per_line: int = 1) -> list[str]:
    groups, g0 = [], 0
    for i, s in enumerate(seq):
        if i and s["beat"] - (seq[i - 1]["beat"] + seq[i - 1]["dur"]) >= 0.75:
            groups.append(seq[g0:i])
            g0 = i
    groups.append(seq[g0:])

    lines = []
    for g in groups:
        b0, b1 = g[0]["beat"], g[-1]["beat"] + g[-1]["dur"]
        toks = []
        for s in g:
            hold = "-" * min(6, max(0, int(round(s["dur"] * 2)) - 1))
            toks.append(f"{s['btn']}{s['mk']}{hold}")
        lines.append(f"（{b0:4.1f}-{b1:4.1f}）  " + "   ".join(toks))
    return lines


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "midi", "windfis2.mid")
    song = smf.load(src)
    mel = oc.quantize(oc.monophonic(song.tracks[1].notes))
    seq = build(mel)

    n_plain = sum(1 for s in seq if s["d"] == 0)
    n_one = sum(1 for s in seq if abs(s["d"]) == 1)
    n_two = sum(1 for s in seq if abs(s["d"]) == 2)
    n_bad = sum(1 for s in seq if not s["exact"])

    out = [f"# 45 音：纯按键 {n_plain}，±1 半音 {n_one}，±2 半音 {n_two}，够不到 {n_bad}", ""]
    out += phrase_lines(seq)
    out += ["", "## 逐音（音名 -> 按键/弯音）"]
    for s in seq:
        out.append(f"  {s['beat']:6.2f}  {smf.note_name(s['pitch']):<4} -> "
                   f"{s['btn']}{s['mk']:<2}  ({s['d']:+d})")

    text = "\n".join(out)
    print(text)
    dst = os.path.normpath(os.path.join(HERE, "..", "out", "switch2.txt"))
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    print(f"\n# 已写出 {os.path.relpath(dst, os.path.join(HERE, ".."))}")

