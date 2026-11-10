"""stats.py — 打印当前音集合下的还原质量统计。"""
import os

import ocarina as oc
import smf

HERE = os.path.dirname(os.path.abspath(__file__))
song = smf.load(os.path.join(HERE, "..", "midi", "windfis2.mid"))
mel = oc.quantize(oc.monophonic(song.tracks[1].notes))

cov = sorted(((oc.coverage(mel, t), t) for t in range(12)), reverse=True)
t = cov[0][1]
folded = oc.fold_phrases(mel, t)
notes, cost = oc.arrange(folded, 0)

n = len(notes)
exact = sum(1 for x in notes if x.err == 0)
errs = [abs(x.err) for x in notes]
w = sum(x.dur for x in notes)
print(f"音集合: {[o[0] for o in oc.OCARINA]}")
print(f"最优移调: {t:+d}   覆盖率: {cov[0][0]*100:.1f}%   DP 代价: {cost:.2f}")
print(f"音符数: {n}   完全命中: {exact} ({exact/n*100:.1f}%)")
print(f"平均偏差: {sum(errs)/n:.2f} 半音   按时值加权: {sum(a*x.dur for a, x in zip(errs, notes))/w:.2f}")
print("偏差分布:", {k: errs.count(k) for k in sorted(set(errs))})
print("有偏差的音:")
for i, x in enumerate(notes):
    if x.err:
        print(f"   beat {x.beat:5.2f}  {smf.note_name(mel[i].pitch):<4} -> "
              f"{x.name:<4} {x.err:+d}")
