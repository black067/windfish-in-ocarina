"""
ocarina.py — 把任意单声部旋律「压」进《时之笛》陶笛的音集合，并生成谱子。

音集合：ZELDA NOTES App 的虚拟陶笛 7 个音（自然音阶 + 高八度）。

「转换」不是移调那么简单，而是要在两个硬约束下重新配器：
    (1) 音高集合有限  -> 音阶外的音必须就近改掉
    (2) 音域有限      -> 超过音域的旋律必须「折返八度」

本模块用动态规划（DP）在每个候选音上给每个音符选址：
    * 发射代价  = 时值加权 × 绝对半音距离（离陶笛音越远越贵）
    * 转移代价  = |原曲音程 - 实际音程|（保住旋律的走向/轮廓）
再对 12 个移调（以及分段八度折叠）逐一搜索，取总代价最小的那个。
"""
from __future__ import annotations

from dataclasses import dataclass

# --------------------------------------------------------------------------- #
# 音集合定义
# --------------------------------------------------------------------------- #
APP7 = dict(
    names=["C4", "D4", "E4", "F4", "G4", "A4", "B4", "C5"],
    pitches=[60, 62, 64, 65, 67, 69, 71, 72],
    keys=["1", "2", "3", "4", "5", "6", "7", "1'"],
    glyphs=["1", "2", "3", "4", "5", "6", "7", "1'"],
    title="App 7 音（C 大调白键 + 高八度）",
)
TUNINGS = {"app7": APP7}

# 当前生效的音集合（OCARINA 每项：(音名, MIDI, 按键, 符号)）
OCARINA: list[tuple] = []
PITCHES: list[int] = []
PCS: list[int] = []


def use_tuning(name: str = "app7") -> dict:
    """切换当前音集合。"""
    global OCARINA, PITCHES, PCS
    t = TUNINGS[name] if isinstance(name, str) else name
    OCARINA = [(n, p, k, g) for n, p, k, g in
               zip(t["names"], t["pitches"], t["keys"], t["glyphs"])]
    PITCHES = list(t["pitches"])
    PCS = [p % 12 for p in PITCHES]
    return t


use_tuning("app7")


def circ_dist(a: int, b: int) -> int:
    """音级圆周距离 0..6。"""
    d = abs(a - b) % 12
    return min(d, 12 - d)


def signed_pc(a: int, b: int) -> int:
    """从 a 到 b 的最短有向音级距离，范围 -6..6。"""
    d = (b - a) % 12
    return d - 12 if d > 6 else d


# --------------------------------------------------------------------------- #
# 数据结构
# --------------------------------------------------------------------------- #
@dataclass
class Mel:
    beat: float          # 起始拍
    dur: float           # 时值（拍）
    pitch: int           # MIDI 音高

    @property
    def end(self) -> float:
        return self.beat + self.dur


@dataclass
class Note5:
    beat: float
    dur: float
    idx: int             # 0..4，对应 OCARINA
    src: int             # 原曲 MIDI 音高
    err: int             # 偏离原音级的半音数（用于质检）

    @property
    def pitch(self) -> int:
        return PITCHES[self.idx]

    @property
    def name(self) -> str:
        return OCARINA[self.idx][0]


# --------------------------------------------------------------------------- #
# 旋律抽取 / 整理
# --------------------------------------------------------------------------- #
def monophonic(notes, tol: float = 0.06) -> list[Mel]:
    """
    把一堆（可能重叠的）音符压成单声部：
      * 起点相近的音只留一个（优先长音，其次高音）
      * 时值裁到下一个音之前，避免叠在一起
    """
    from smf import Note  # noqa: F401  (仅类型提示)

    if not notes:
        return []
    items = sorted(notes, key=lambda n: (n.start_beat, -n.dur_beat, -n.pitch))
    picked: list[Mel] = []
    for n in items:
        b, d, p = n.start_beat, max(n.dur_beat, 0.05), n.pitch
        if picked and abs(b - picked[-1].beat) <= tol:
            if d > picked[-1].dur:
                picked[-1] = Mel(picked[-1].beat, d, p)
            continue
        picked.append(Mel(b, d, p))
    out: list[Mel] = []
    for i, m in enumerate(picked):
        if i + 1 < len(picked):
            gap = picked[i + 1].beat - m.beat
            m.dur = min(m.dur, max(gap * 0.95, 0.05))
        out.append(m)
    return out


def quantize(notes: list[Mel], grid: float = 0.25) -> list[Mel]:
    """把起始拍对齐到 grid，并合并同拍重复。"""
    out: list[Mel] = []
    for m in notes:
        b = round(m.beat / grid) * grid
        d = max(grid, round(m.dur / grid) * grid)
        if out and abs(b - out[-1].beat) < 1e-6:
            if m.dur > out[-1].dur:
                out[-1] = Mel(b, d, m.pitch)
            continue
        out.append(Mel(b, d, m.pitch))
    # 修掉因合并造成的重叠
    for i in range(len(out) - 1):
        span = out[i + 1].beat - out[i].beat
        out[i].dur = min(out[i].dur, max(span - 1e-3, grid))
    return out


# --------------------------------------------------------------------------- #
# 核心：5 音配器（DP）
# --------------------------------------------------------------------------- #
def _emit(i: int, j: int, mel: list[Mel], shift: int,
          long_bonus: float, out_pen: float) -> float:
    """把第 i 个音放到第 j 个陶笛音上的代价（绝对半音距离）。

    超出音域的音本来就会被压到最近的边界；额外再加一点「出界」惩罚，
    避免整段旋律为了迁就几个极值音而整体跑偏。
    """
    tgt = mel[i].pitch + shift
    w = 1.0 + long_bonus * min(mel[i].dur, 2.0)
    d = abs(tgt - PITCHES[j])
    over = max(0, PITCHES[0] - tgt, tgt - PITCHES[-1])
    return w * (d + out_pen * over)


def _trans(i: int, k: int, j: int, mel: list[Mel],
           contour: float, unison_pen: float, leap_pen: float) -> float:
    """上一音在第 k 个孔、当前音在第 j 个孔的转移代价。

    理想音程 = 原曲音程（移调不影响音程）；实际音程 = 两个陶笛音之差。
    两者差得越多越贵 —— 这就是「保住旋律轮廓」的数学表达。
    """
    ideal = mel[i].pitch - mel[i - 1].pitch
    actual = PITCHES[j] - PITCHES[k]
    # 乐句之间隔着休止，不该被上一句的尾音"拽住"
    if mel[i].beat - (mel[i - 1].beat + mel[i - 1].dur) > 0.7:
        return 0.0
    cost = contour * abs(ideal - actual)
    if ideal != 0 and PITCHES[j] == PITCHES[k]:
        cost += unison_pen          # 原曲在动，别让它卡在同一个音上
    if abs(actual) > 12:            # 陶笛上超过八度的跳进很不音乐
        cost += leap_pen * (abs(actual) - 12) / 2
    return cost


def arrange(mel: list[Mel], shift: int,
            contour: float = 0.55, long_bonus: float = 0.6,
            unison_pen: float = 0.5, out_pen: float = 0.45,
            leap_pen: float = 1.0) -> tuple[list[Note5], float]:
    """在给定移调（绝对半音）下求最优指法序列。返回 (结果, 总代价)。"""
    n = len(mel)
    if n == 0:
        return [], 0.0
    m = len(PITCHES)                     # 候选音个数（5 或 7）
    INF = float("inf")
    dp = [[INF] * m for _ in range(n)]
    back = [[0] * m for _ in range(n)]
    for j in range(m):
        dp[0][j] = _emit(0, j, mel, shift, long_bonus, out_pen)
    for i in range(1, n):
        for j in range(m):
            best, bk = INF, 0
            for k in range(m):
                v = dp[i - 1][k] + _trans(i, k, j, mel, contour, unison_pen, leap_pen)
                if v < best:
                    best, bk = v, k
            dp[i][j] = best + _emit(i, j, mel, shift, long_bonus, out_pen)
            back[i][j] = bk
    j = min(range(m), key=lambda x: dp[n - 1][x])
    total = dp[n - 1][j]
    seq = [0] * n
    for i in range(n - 1, -1, -1):
        seq[i] = j
        j = back[i][j]
    out = []
    for i, j in enumerate(seq):
        pc = (mel[i].pitch + shift) % 12
        out.append(Note5(mel[i].beat, mel[i].dur, j, mel[i].pitch,
                         signed_pc(pc, PCS[j])))
    return out, total


def best_shift(mel: list[Mel], lo: int = -36, hi: int = 12,
               **kw) -> tuple[int, list[Note5], float]:
    """扫描所有「移调 + 八度折叠」，取总代价最小的。"""
    best = None
    for s in range(lo, hi + 1):
        notes, cost = arrange(mel, s, **kw)
        if best is None or cost < best[2]:
            best = (s, notes, cost)
    return best


def split_phrases(mel: list[Mel], gap: float = 0.75) -> list[list[Mel]]:
    """按长休止把旋律切成乐句。"""
    if not mel:
        return []
    out: list[list[Mel]] = [[mel[0]]]
    for m in mel[1:]:
        if m.beat - out[-1][-1].end >= gap:
            out.append([m])
        else:
            out[-1].append(m)
    return out


def fold_phrases(mel: list[Mel], t: int, window: tuple[int, int] | None = None,
                 smooth: float = 0.6, ks=range(-4, 2)) -> list[Mel]:
    """
    「分段搬八度」：陶笛音域有限，而原曲常跨两个八度，
    所以每个乐句各自挑一个八度，把它塞进当前音集合的音域窗口。

    t      : 音级移调（0..11）
    window : 默认 = 当前音集合的最低音~最高音
    smooth : 相邻乐句换八度的平滑惩罚，避免忽高忽低
    """
    if window is None:
        window = (PITCHES[0], PITCHES[-1])
    out: list[Mel] = []
    prev_k = 0
    for ph in split_phrases(mel):
        best = None
        for k in ks:
            off = t + 12 * k
            cost = 0.0
            for m in ph:
                p = m.pitch + off
                over = max(0, window[0] - p, p - window[1])
                cost += over * over * 0.5 + over
            cost += smooth * abs(k - prev_k)
            if best is None or cost < best[0]:
                best = (cost, k)
        k = best[1]
        prev_k = k
        off = t + 12 * k
        out.extend(Mel(m.beat, m.dur, m.pitch + off) for m in ph)
    return out


def best_fold(mel: list[Mel], **kw) -> tuple[int, list[Mel], list[Note5], float]:
    """对 12 个音级移调分别做「分段折叠 + 五音 DP」，取总代价最小者。"""
    best = None
    for t in range(12):
        folded = fold_phrases(mel, t)
        notes, cost = arrange(folded, 0)
        if best is None or cost < best[3]:
            best = (t, folded, notes, cost)
    return best


def coverage(mel: list[Mel], trans: int) -> float:
    """时值加权：有多少比例的「音」落在陶笛音级上（不计八度）。"""
    tot = sum(m.dur for m in mel) or 1.0
    hit = sum(m.dur for m in mel if (m.pitch + trans) % 12 in PCS)
    return hit / tot


# --------------------------------------------------------------------------- #
# 输出
# --------------------------------------------------------------------------- #
def tab_table(notes: list[Note5]) -> str:
    """逐音表格。"""
    lines = [" 拍   时值  陶笛  按键(N64)  图谱  原音   偏差"]
    for n in notes:
        o = OCARINA[n.idx]
        d = f"{n.err:+d}" if n.err else " 0"
        lines.append(f"{n.beat:5.2f} {n.dur:5.2f}  {o[0]:<3} {o[2]:<9} {o[3]}     "
                     f"{n.pitch:3d}   {d}")
    return "\n".join(lines)


def tab_glyph(notes: list[Note5], beats_per_line: int = 16) -> str:
    """一行式按键谱：用 N64 符号，`·` 表示延音/休止的拍点。"""
    lines = []
    cur = []
    line_start = 0.0
    for n in notes:
        while n.beat - line_start >= beats_per_line:
            lines.append(" ".join(cur))
            cur, line_start = [], line_start + beats_per_line
        g = OCARINA[n.idx][3]
        # 用「-」标出长音，每个「-」代表半拍
        hold = max(0, int(round(n.dur * 2)) - 1)
        cur.append(g + "-" * hold)
    if cur:
        lines.append(" ".join(cur))
    return "\n".join(lines)


def to_midi(notes: list[Note5], path: str, bpm: float = 120.0) -> None:
    """导出 5 音版 MIDI（陶笛音色：Ocarina = GM 79）。"""
    import smf

    tpq = 480
    evs = []
    for n in notes:
        s = int(round(n.beat * tpq))
        d = int(round(n.dur * tpq))
        evs.append(smf.Note(start_tick=s, dur_tick=max(10, d), pitch=n.pitch,
                            velocity=100, channel=0, track=0))
    smf.write_midi(path, evs, bpm=bpm, program=79, name="Ballad5")


