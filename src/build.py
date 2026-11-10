"""build.py — 端到端流水线：MIDI -> 单声部旋律 -> 陶笛简谱 + 试听 + 对照图。

用法:
    python build.py [input.mid] [track] [tuning] [transpose] [音名列表]
        tuning    app7（App 的 7 音，默认）
        transpose 强制音级移调 0..11；省略则自动挑覆盖率最高的
        音名列表  例如 "D4 E4 F4 G4 A4 B4 C5"，用自定义音集合覆盖 tuning
"""
from __future__ import annotations

import os
import sys

import ocarina as oc
import render
import smf

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "out"))

SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "midi", "windfis2.mid")
TRACK = int(sys.argv[2]) if len(sys.argv) > 2 else 1
TUNING = sys.argv[3] if len(sys.argv) > 3 else "app7"
FORCE_T = int(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[4] else None
CUSTOM = sys.argv[5] if len(sys.argv) > 5 else None   # 例如 "D4 E4 F4 G4 A4 B4 C5"

os.makedirs(OUT, exist_ok=True)
if CUSTOM:
    notes_list = CUSTOM.replace(",", " ").split()
    pitches = [smf.name_to_pitch(n) for n in notes_list]
    pitches.sort()
    tun = oc.use_tuning(dict(
        names=[smf.note_name(p) for p in pitches],
        pitches=pitches,
        keys=[str(i + 1) for i in range(len(pitches))],
        glyphs=[str(i + 1) for i in range(len(pitches))],
        title="自定义音集合",
    ))
    TUNING = "custom"
else:
    tun = oc.use_tuning(TUNING)
song = smf.load(SRC)
lines: list[str] = []


def p(s: str = "") -> None:
    print(s)
    lines.append(s)


p(f"# 输入: {os.path.basename(SRC)}   音集合: {TUNING}（{tun['title']}）")
p(f"# 音高: " + " ".join(f"{n}={p}" for n, p in zip(tun["names"], tun["pitches"])))
p(f"# fmt={song.fmt} tpq={song.tpq} bpm~{song.bpm:.1f} "
  f"时长={song.duration_sec:.1f}s 轨数={len(song.tracks)}")
tr = song.tracks[TRACK]
p(f"# 取轨 {TRACK}: {tr.name!r} 音符 {len(tr.notes)} program={tr.program}")

mel = oc.quantize(oc.monophonic(tr.notes))
lo, hi = min(m.pitch for m in mel), max(m.pitch for m in mel)
p(f"# 单声部化后 {len(mel)} 个音；音域 {smf.note_name(lo)}-{smf.note_name(hi)}"
  f"（{hi-lo} 半音），音集合音域 {tun['names'][0]}-{tun['names'][-1]}"
  f"（{tun['pitches'][-1]-tun['pitches'][0]} 半音）")
p()

p("## 原曲旋律（0.25 拍网格）")
for i, m in enumerate(mel):
    p(f"{i:3d}  beat {m.beat:6.2f}  dur {m.dur:4.2f}  {smf.note_name(m.pitch):<4} {m.pitch}")
p()

p("## 12 个音级移调的音级覆盖率（时值加权）")
cov = sorted(((oc.coverage(mel, t), t) for t in range(12)), reverse=True)
for c, t in cov:
    p(f"  移调 {t:+2d} 半音 -> {c*100:5.1f}%" + ("   <== 最优" if t == cov[0][1] else ""))
p()

t = FORCE_T if FORCE_T is not None else cov[0][1]
folded = oc.fold_phrases(mel, t)
notes, cost = oc.arrange(folded, 0)
# Dot5.src 记的是折叠后的音高，改回原曲音高，表格/对照图才对得上
for n, m in zip(notes, mel):
    n.src = m.pitch
p(f"## 采用音级移调 {t:+d}（覆盖率 {oc.coverage(mel, t)*100:.1f}%），"
  f"分段八度折叠，DP 代价 {cost:.2f}")
for ph in oc.split_phrases(mel):
    off = folded[mel.index(ph[0])].pitch - ph[0].pitch
    p(f"   beat {ph[0].beat:5.1f}-{ph[-1].end:5.1f}: {off:+d} 半音"
      f"   {smf.note_name(min(x.pitch for x in ph))}-{smf.note_name(max(x.pitch for x in ph))}"
      f" -> {smf.note_name(min(x.pitch for x in ph)+off)}-"
      f"{smf.note_name(max(x.pitch for x in ph)+off)}")
p()

exact = sum(1 for n in notes if n.err == 0)
errs = [abs(n.err) for n in notes]
w = sum(n.dur for n in notes) or 1
p(f"## 质量：{exact}/{len(notes)} 个音完全命中（{exact/len(notes)*100:.1f}%），"
  f"平均偏差 {sum(errs)/len(notes):.2f} 半音（按时值加权 "
  f"{sum(abs(n.err)*n.dur for n in notes)/w:.2f}）")
p()

p(oc.tab_table(notes))
p()
p(f"## 谱子（{[o[2] for o in oc.OCARINA]}；每个 '-' 延长半拍）")
p()


def phrase_tab(notes) -> list[str]:
    out = []
    groups: list[list] = []
    for n in notes:
        if not groups:
            groups.append([n])
            continue
        prev = groups[-1][-1]
        if n.beat - (prev.beat + prev.dur) >= 0.75:
            groups.append([n])
        else:
            groups[-1].append(n)
    for g in groups:
        b0, b1 = g[0].beat, g[-1].beat + g[-1].dur
        toks = []
        for n in g:
            hold = min(8, max(0, int(round(n.dur * 2)) - 1))
            toks.append(oc.OCARINA[n.idx][3] + "-" * hold)
        out.append(f"beat {b0:5.1f}-{b1:5.1f}   " + " ".join(toks))
        out.append(f"{'':19s}原音: " + " ".join(smf.note_name(n.src) for n in g))
    return out


for line in phrase_tab(notes):
    p(line)
p()

tag = "" if TUNING == "app7" else "_" + TUNING
oc.to_midi(notes, os.path.join(OUT, f"ballad{tag}.mid"), bpm=song.bpm)
render.render([(n.beat, n.dur, n.pitch) for n in notes], song.bpm,
              os.path.join(OUT, f"ocarina{tag}.wav"), "ocarina")
render.render([(m.beat, m.dur, m.pitch) for m in mel], song.bpm,
              os.path.join(OUT, "original_melody.wav"), "flute")
render.piano_roll(mel, notes, os.path.join(OUT, f"map{tag}.png"),
                  f"Ballad of the Wind Fish  ->  {tun['title']}")
p(f"# 产物: out/ballad{tag}.mid, out/ocarina{tag}.wav, out/map{tag}.png")

with open(os.path.join(OUT, f"tab{tag}.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
print(f"# 已写出 out/tab{tag}.txt")

