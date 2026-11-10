"""
smf.py — 纯 Python 的 Standard MIDI File (SMF) 读写器。

不依赖 mido / pretty_midi，直接按 SMF 1.0 规范解析，便于在任何 Python 环境里跑。
支持：format 0/1、running status、tempo map、track name、program change、
       note on/off（含 velocity=0 的 note off）、time signature、key signature。

作者：为 "风鱼之歌 → 时之笛陶笛" 项目编写。
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Iterable


# --------------------------------------------------------------------------- #
# 基础工具
# --------------------------------------------------------------------------- #
def read_vlq(buf: bytes, i: int) -> tuple[int, int]:
    """读取变长量（variable-length quantity）。"""
    val = 0
    while True:
        if i >= len(buf):
            raise ValueError("VLQ 截断")
        b = buf[i]
        i += 1
        val = (val << 7) | (b & 0x7F)
        if not (b & 0x80):
            return val, i


def write_vlq(value: int) -> bytes:
    """写入变长量。"""
    if value < 0:
        raise ValueError("VLQ 不能为负")
    out = bytearray([value & 0x7F])
    value >>= 7
    while value:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    return bytes(reversed(out))


NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def note_name(pitch: int) -> str:
    """MIDI 音高 -> 科学音高记号，例如 62 -> D4。"""
    return f"{NOTE_NAMES[pitch % 12]}{pitch // 12 - 1}"


def name_to_pitch(name: str) -> int:
    """'D4' / 'F#5' / 'Bb3' -> MIDI 音高。"""
    s = name.strip()
    letter = s[0].upper()
    i = 1
    acc = 0
    while i < len(s) and s[i] in "#b♯♭":
        acc += 1 if s[i] in "#♯" else -1
        i += 1
    octave = int(s[i:])
    base = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[letter]
    return (octave + 1) * 12 + base + acc


# --------------------------------------------------------------------------- #
# 事件
# --------------------------------------------------------------------------- #
@dataclass
class Note:
    """一个音符（已配对 note-on / note-off）。"""
    start_tick: int
    dur_tick: int
    pitch: int
    velocity: int = 100
    channel: int = 0
    track: int = 0
    # 下面这些在时间轴上补齐（由 Song 计算）
    start_beat: float = 0.0
    dur_beat: float = 0.0
    start_sec: float = 0.0
    dur_sec: float = 0.0

    @property
    def end_tick(self) -> int:
        return self.start_tick + self.dur_tick


@dataclass
class TrackInfo:
    index: int
    name: str = ""
    program: int = 0
    channel: int | None = None
    notes: list[Note] = field(default_factory=list)
    n_events: int = 0


@dataclass
class Song:
    fmt: int
    division: int
    tracks: list[TrackInfo]
    tempos: list[tuple[int, int]] = field(default_factory=list)  # (tick, us/qn)
    time_sigs: list[tuple[int, int, int]] = field(default_factory=list)
    key_sigs: list[tuple[int, int]] = field(default_factory=list)

    # -- 时间换算 ---------------------------------------------------------- #
    @property
    def tpq(self) -> int:
        """每四分音符的 tick 数（division 为 SMPTE 时返回近似值）。"""
        if self.division & 0x8000:
            fps = 256 - (self.division >> 8)
            ticks_per_frame = self.division & 0xFF
            return int(fps * ticks_per_frame)
        return self.division

    def _tempo_at(self, tick: int) -> int:
        us = 500_000
        for t, v in self.tempos:
            if t <= tick:
                us = v
            else:
                break
        return us

    def tick_to_sec(self, tick: float) -> float:
        """整合 tempo map，把 tick 换成秒。"""
        tpq = self.tpq
        sec = 0.0
        last_tick = 0
        us = 500_000
        for t, v in sorted(self.tempos) + [(float("inf"), us)]:
            if tick <= t:
                sec += (tick - last_tick) * (us / 1e6) / tpq
                return sec
            sec += (t - last_tick) * (us / 1e6) / tpq
            last_tick = t
            us = v
        return sec

    def tick_to_beat(self, tick: float) -> float:
        return tick / self.tpq

    def finalize(self) -> "Song":
        """给所有音符补上 beat / sec 信息，并按时间排序。"""
        for tr in self.tracks:
            for n in tr.notes:
                n.start_beat = self.tick_to_beat(n.start_tick)
                n.dur_beat = self.tick_to_beat(n.dur_tick)
                n.start_sec = self.tick_to_sec(n.start_tick)
                n.dur_sec = self.tick_to_sec(n.end_tick) - n.start_sec
            tr.notes.sort(key=lambda n: (n.start_tick, n.pitch))
        return self

    # -- 便捷视图 ---------------------------------------------------------- #
    @property
    def all_notes(self) -> list[Note]:
        out: list[Note] = []
        for tr in self.tracks:
            out.extend(tr.notes)
        out.sort(key=lambda n: (n.start_tick, n.pitch))
        return out

    @property
    def duration_sec(self) -> float:
        notes = self.all_notes
        return max((n.start_sec + n.dur_sec for n in notes), default=0.0)

    @property
    def bpm(self) -> float:
        if not self.tempos:
            return 120.0
        return 60_000_000 / self.tempos[0][1]


# --------------------------------------------------------------------------- #
# 解析
# --------------------------------------------------------------------------- #
def parse(data: bytes) -> Song:
    if data[:4] != b"MThd":
        raise ValueError("不是 MIDI 文件（缺少 MThd）")
    header_len = struct.unpack(">I", data[4:8])[0]
    fmt, ntracks, division = struct.unpack(">HHH", data[8:14])
    pos = 8 + header_len

    tracks: list[TrackInfo] = []
    tempos: list[tuple[int, int]] = []
    time_sigs: list[tuple[int, int, int]] = []
    key_sigs: list[tuple[int, int]] = []

    for ti in range(ntracks):
        if pos + 8 > len(data):
            break
        chunk_id = data[pos:pos + 4]
        chunk_len = struct.unpack(">I", data[pos + 4:pos + 8])[0]
        body = data[pos + 8:pos + 8 + chunk_len]
        pos += 8 + chunk_len
        if chunk_id != b"MTrk":
            continue

        info = TrackInfo(index=ti)
        tick = 0
        i = 0
        running: int | None = None
        open_notes: dict[tuple[int, int], list[tuple[int, int]]] = {}

        while i < len(body):
            delta, i = read_vlq(body, i)
            tick += delta
            if i >= len(body):
                break
            status = body[i]

            if status == 0xFF:                      # meta
                i += 1
                mtype = body[i]
                i += 1
                mlen, i = read_vlq(body, i)
                payload = body[i:i + mlen]
                i += mlen
                if mtype == 0x51 and mlen >= 3:
                    us = (payload[0] << 16) | (payload[1] << 8) | payload[2]
                    tempos.append((tick, us))
                elif mtype == 0x58 and mlen >= 2:
                    time_sigs.append((tick, payload[0], 2 ** payload[1]))
                elif mtype == 0x59 and mlen >= 2:
                    key_sigs.append((tick, payload[0], payload[1]))
                elif mtype == 0x03:
                    try:
                        info.name = payload.decode("utf-8", "replace").strip()
                    except Exception:
                        info.name = payload.decode("latin-1", "replace").strip()
                elif mtype == 0x2F:
                    break
                continue

            if status in (0xF0, 0xF7):              # sysex
                i += 1
                slen, i = read_vlq(body, i)
                i += slen
                continue

            if status & 0x80:                        # 有新状态字节
                i += 1
                running = status
            else:                                    # running status
                if running is None:
                    raise ValueError("running status 但没有前导状态字节")
                status = running

            hi = status & 0xF0
            ch = status & 0x0F
            if info.channel is None:
                info.channel = ch

            if hi in (0x80, 0x90, 0xA0, 0xB0, 0xE0):
                d1, d2 = body[i], body[i + 1]
                i += 2
            elif hi in (0xC0, 0xD0):
                d1 = body[i]
                d2 = 0
                i += 1
                if hi == 0xC0:
                    info.program = d1
            else:
                raise ValueError(f"未知状态字节 0x{status:02X}")

            info.n_events += 1
            if hi == 0x90 and d2 > 0:
                open_notes.setdefault((ch, d1), []).append((tick, d2))
            elif hi == 0x80 or (hi == 0x90 and d2 == 0):
                stack = open_notes.get((ch, d1))
                if stack:
                    start, vel = stack.pop(0)
                    info.notes.append(
                        Note(start_tick=start, dur_tick=max(1, tick - start),
                             pitch=d1, velocity=vel, channel=ch, track=ti)
                    )

        # 没关掉的音符：给个默认时值
        for (ch, pitch), stack in open_notes.items():
            for start, vel in stack:
                info.notes.append(
                    Note(start_tick=start, dur_tick=1, pitch=pitch,
                         velocity=vel, channel=ch, track=ti)
                )
        tracks.append(info)

    song = Song(fmt=fmt, division=division, tracks=tracks,
                tempos=sorted(tempos), time_sigs=time_sigs, key_sigs=key_sigs)
    return song.finalize()


def load(path: str) -> Song:
    with open(path, "rb") as f:
        return parse(f.read())


# --------------------------------------------------------------------------- #
# 写出（format 0，单轨）
# --------------------------------------------------------------------------- #
def write_midi(path: str, notes: Iterable[Note], bpm: float = 120.0,
               program: int = 0, name: str = "ocarina") -> None:
    """把一串 Note（用 start_tick/dur_tick 表示）写成 format 0 的 MIDI。"""
    tpq = 480
    evs: list[tuple[int, int, bytes]] = []      # (tick, order, data)
    for n in notes:
        ch = n.channel & 0x0F
        evs.append((n.start_tick, 2, bytes([0x90 | ch, n.pitch & 0x7F, n.velocity & 0x7F])))
        evs.append((n.end_tick, 1, bytes([0x80 | ch, n.pitch & 0x7F, 0])))
    evs.sort(key=lambda e: (e[0], e[1]))

    tempo_us = int(60_000_000 / bpm)
    body = bytearray()
    # meta: track name
    nm = name.encode("utf-8")[:127]
    body += write_vlq(0) + b"\xff\x03" + write_vlq(len(nm)) + nm
    body += write_vlq(0) + b"\xff\x51\x03" + tempo_us.to_bytes(3, "big")
    body += write_vlq(0) + b"\xff\x58\x04\x04\x02\x18\x08"   # 4/4
    body += write_vlq(0) + bytes([0xC0, program & 0x7F])

    last = 0
    for tick, _, data in evs:
        body += write_vlq(tick - last) + data
        last = tick
    body += write_vlq(0) + b"\xff\x2f\x00"

    hdr = b"MThd" + struct.pack(">IHHH", 6, 0, 1, tpq)
    trk = b"MTrk" + struct.pack(">I", len(body)) + bytes(body)
    with open(path, "wb") as f:
        f.write(hdr + trk)


if __name__ == "__main__":
    import sys
    song = load(sys.argv[1])
    print(f"format={song.fmt} tracks={len(song.tracks)} division={song.division} "
          f"bpm≈{song.bpm:.1f} dur={song.duration_sec:.1f}s")
    for tr in song.tracks:
        if not tr.notes:
            print(f"  [{tr.index}] {tr.name!r} (空轨, {tr.n_events} events)")
            continue
        ps = [n.pitch for n in tr.notes]
        print(f"  [{tr.index}] {tr.name!r} ch={tr.channel} prog={tr.program} "
              f"notes={len(tr.notes)} range={note_name(min(ps))}-{note_name(max(ps))}")
