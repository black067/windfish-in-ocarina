"""把 MIDI 以「时间轴 + 音名」的文本形式打印出来，方便肉眼找旋律。"""
import sys
import smf

song = smf.load(sys.argv[1])
tpq = song.tpq

print(f"# {sys.argv[1]}  fmt={song.fmt} tpq={tpq} bpm~{song.bpm:.1f} "
      f"dur={song.duration_sec:.1f}s  tempos={song.tempos[:4]}")
print(f"# time sigs={song.time_sigs}  key sigs={song.key_sigs}")
print()

for tr in song.tracks:
    if not tr.notes:
        continue
    print(f"=== track {tr.index}: {tr.name}  ch={tr.channel} prog={tr.program} "
          f"notes={len(tr.notes)}")
    line = []
    for n in tr.notes:
        b = n.start_tick / tpq
        d = n.dur_tick / tpq
        line.append(f"{b:6.2f}:{smf.note_name(n.pitch):<4}/{d:.2f}")
        if len(line) >= 10:
            print("   " + "  ".join(line))
            line = []
    if line:
        print("   " + "  ".join(line))
    print()
