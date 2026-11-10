# 风鱼之歌 → 时之笛陶笛

把《塞尔达传说 织梦岛》的 **Ballad of the Wind Fish（风鱼之歌）** 搬上《时之笛》的陶笛：
找谱子 → 弄清陶笛到底能吹哪些音 → 写算法做转换 → 出谱子、试听、对照图。

目标乐器是 **Switch 2 重制版**里的陶笛，以及配套 **ZELDA NOTES App** 里那支虚拟陶笛。

---

## 结论

1. **谱子能直接拿到、能直接解析。** [VGMusic 的《织梦岛》页](https://www.vgmusic.com/music/console/nintendo/gameboy/)有 **11 个**风鱼之歌的 MIDI。主输入用最短的纯旋律版 `windfis2.mid`，再用另一个独立改编 `Zgbreve.mid` 交叉验证，两条旋律逐音一致。
2. **旋律是 B 小调**，主题就是三个音往上爬：`B–C#–D`（♩≈126，音域 F#5–G7，25 个半音，31 秒）。
3. **陶笛的音源有三层**：按键 5 个音、摇杆弯音（能滑出半音，玩家实测共 45 个音）、App 的 7 音虚拟陶笛。App 这 7 个音是完整自然音阶，正好够用。
4. **结果：45 个音里 39 个完全命中（86.7%）**，平均偏差 0.42 个半音；
   **主题段一个音都不用改**，只有高潮段因为超出音域被压缩。

---

## 1. 目录

```
zelda-windfish-ocarina/
├─ README.md
├─ switch2.md                     Switch 2 手按谱（按键 + 摇杆）
├─ .gitignore                     忽略 out/ 等脚本产物
├─ midi/                          下载的原始 MIDI（留 4 个代表）
│   ├─ windfis2.mid               893 B  · 纯旋律 45 音（★ 主输入）
│   ├─ Zgbreve.mid              1 495 B  · 同旋律低八度 + 竖琴（交叉验证）
│   ├─ Windfish4895.mid         4 605 B  · Adam Kupka 的 8 轨改编
│   └─ Windfish_Final.mid       4 969 B  · Joe Cortez 的 8 件乐器总谱
├─ src/
│   ├─ smf.py                     纯 Python 的 SMF 读写器（不依赖 mido）
│   ├─ ocarina.py                 配器核心：音集合 / 单声部化 / 移调 / 动态规划 / 折八度
│   ├─ build.py                   端到端流水线
│   ├─ render.py                  合成 WAV + 画对照图
│   ├─ switch2.py                 生成 Switch 2 按键谱
│   ├─ stats.py                   还原度统计
│   └─ dump.py                    把 MIDI 打印成「拍:音名/时值」
└─ out/                           全部由脚本生成，未纳入版本库
    ├─ tab.txt                    ★ 谱子（逐音表 + 简谱）
    ├─ ballad.mid                 导出的 7 音 MIDI
    ├─ ocarina.wav                ★ 陶笛版试听
    ├─ original_melody.wav        原曲旋律（长笛音色，A/B 对照）
    ├─ map.png                    ★ 原曲 vs 陶笛版 对照图
    └─ switch2.txt                Switch 2 手按谱（同上）
```

> `out/` 里的东西全部可以由脚本重新生成（见 §9），所以写进了 `.gitignore`。

---

## 2. 谱子

### 2.1 这首曲子

- 作品：《The Legend of Zelda: Link's Awakening》（1993 GB / 1998 DX / 2019 Switch 重制）
- 曲名：**Ballad of the Wind Fish**（日文「風魚の歌」）
- 用途：在风鱼之蛋前演奏，蛋会裂开；也是结局主题的动机
- 结构：一个 4 小节的"提问"主题（三音上行的动机），加一段展开和收尾

### 2.2 找到的来源

| 来源 | 形式 | 说明 |
|---|---|---|
| [VGMusic · Link's Awakening](https://www.vgmusic.com/music/console/nintendo/gameboy/) | **MIDI ×11** | 最实用，页内搜 "windfish" |
| [VGMusic · Ballad of the Windfish (Arranged)](https://www.vgmusic.com/file/000982006ac06a38aa0308dcf2bf9c30.html) | MIDI | 8 件乐器总谱 |
| [flat.io · Ballad of the Wind Fish](https://flat.io/score/69a60a930ccf163ab4112c51-ballad-of-the-wind-fish) | 总谱 | Cello / Horn / Bells / Harp / Marimba / Triangle / Organ / Snare，和上面 MIDI 的 8 条轨一一对应 |
| [Ultimate Guitar · 和弦谱](https://tabs.ultimate-guitar.com/tab/misc-computer-games/the-legend-of-zelda-links-awakening-ballad-of-the-wind-fish-chords-5313324) | 吉他和弦 | 核对和声走向 |
| [E-Chords · 键盘谱](https://classic.e-chords.com/keyboards/misc-computer-games/the-legend-of-zelda-links-awakening-ballad-of-the-wind-fish/key-8) | 键盘 | 同上 |
| [Zelda Dungeon · Ocarina Time #17](https://www.zeldadungeon.net/ocarina-time-17-ballad-of-the-wind-fish/) | 文章 | 有人做过"风鱼之歌 → 时之笛"，站点有 Cloudflare 验证，没读到正文 |

> ⚠️ 曲子是近藤浩治 / 任天堂的；MIDI 和总谱都是**玩家自制**，仅适合个人学习。

### 2.3 为什么选 `windfis2.mid`

| 文件 | 轨数 | 音符 | 判断 |
|---|---|---|---|
| `windfis2.mid` | 2（互为 0.25 拍延迟的齐奏） | 45 | ✅ **纯旋律** |
| `Zgbreve.mid` | 2（旋律 + 竖琴） | 70 + 141 | ✅ 低八度旋律，可交叉验证 |
| `Windfish_Final.mid` | 9 | 700+ | ❌ 旋律散在琶音里 |
| `Windfish4895.mid` | 8 | 300+ | ❌ 同上 |

### 2.4 交叉验证

`windfis2.mid` 第 1 轨与 `Zgbreve.mid` 第 1 轨（低八度、整体晚 2.5 拍）逐音比对，**45 个音的音高与相对节奏完全一致**：

```
windfis2 : B5 C#6 D6 | B5 C#6 D6 | C#6 B5 F#5 A5 B5 | ...
Zgbreve  : B5 C#6 D6 | B5 C#6 D6 | C#6 B5 F#5 A5 B5 | ...   (完全相同)
```

### 2.5 旋律转写（B 小调，4/4，♩≈126）

| 乐句 | 音（八度记号） | 时值（拍） |
|---|---|---|
| 1 | `B5 C#6 D6` | ½ ½ 2 |
| 2 | `B5 C#6 D6` | ½ ½ 2 |
| 3 | `C#6 B5 F#5 A5` → `B5` | ½ ½ ½ 1½ → 4 |
| 4 | `B5 C#6 D6` | ½ ½ 2 |
| 5 | `A5 D6 G6` | ½ ½ 2 |
| 6 | `F#6 E6 F#6` | ½ ½ 4¾ |
| 7 | `C#7 B6 F#6 F#6 G6` | 1 1 1 1½ 2¾ |
| 8 | `E7 D7 C#7 B6 F#6 E6 F#6 B6 G6 G6 A6 C6 E6 A6 F#6` | ½ ½ ½ ½ ½ ½ ½ ½ 1 ½ 2 ½ ½ ½ 2 |
| 9 | `D6 B6 A#6 G7 F#7` | ½ 4 1½ 1½ 1½ |

音域 `F#5`–`G7`，**25 个半音**，总长约 31 秒。

---

## 3. 陶笛能吹哪些音

### 3.1 按键：5 个

> "I had to create all of those memorable tunes with only five tones of the classic do-re-mi scale.
> Specifically: **re, fa, la, and ti** (and the higher-scale re)."
> —— 近藤浩治，2005《Nintendo Power》

| 音 | 音级（以 D 为主音） | 说明 |
|---|---|---|
| D4 | 1 | 主音（低） |
| F4 | ♭3 | 小三度 |
| A4 | 5 | 五度 |
| B4 | 6 | 大六度 ← 多利亚色彩 |
| D5 | 1′ | 主音（高） |

= **D 小三和弦 + 大六度**，D 多利亚，跨度 12 个半音。

### 3.2 按键映射

| 音高 | N64 | 3DS | **Switch 2** |
|---|---|---|---|
| D4 | A | L | **L** |
| F4 | C-↓ | R | **R** |
| A4 | C-→ | Y | **A** |
| B4 | C-← | X | **Y** |
| D5 | C-↑ | A | **X** |

Switch 2 的映射有三家独立攻略互相印证（[nintenderos](https://www.nintenderos.com/2026/11/todas-las-canciones-de-la-ocarina-en-zelda-ocarina-of-time-remake/)、[jeuxvideo](https://www.jeuxvideo.com/news/2113207/chants-zelda-ocarina-of-time-ou-trouver-toutes-les-melodies-a-l-ocarina.htm)、[actugaming](https://www.actugaming.net/melodies-zelda-ocarina-of-time-832931/)），
并用它们表里 12 首曲子反推验证过是自洽的（`Song of Time` = A L R = A D F 等）。
任天堂官方支持页也确认按键演奏 / 麦克风哼唱两种方式，以及 "Swap Ocarina-Playing Controls" 可以换键位。

### 3.3 摇杆：弯音（pitch bend）

- 术语就是 **Pitch Bend（弯音）**；连续滑过去叫 **glissando / portamento（滑音）**。
- 这是《时之笛》从 N64 就有、官方从没写进说明书的隐藏操作：**按住一个音，摇杆往上/往下推，音高连续升降**。Switch 2 版对应左摇杆。
- 配合 L / R，能吹出按键之外的一大批音。玩家在 [Zelda Universe 论坛](https://zeldauniverse.net/forums/index.php?thread/94823-how-to-play-real-songs-on-the-in-game-ocarina/)统计过：**一共 45 个音**——5 个键 × 摇杆上/中/下 × L/R 不用。3DS 版里十字键 ↑ 记作 ♯、↓ 记作 ♭。
- 意义：**半音是能吹的**。本曲结尾那个 `A#`（原调导音）就不必改音，推一下摇杆即可。

### 3.4 App：7 个音

[ZELDA NOTES](https://www.nintendo.com/jp/zelda/notes/ocarina/index.html)（Nintendo Switch App 里，免费、不需要 NSO）为《时之笛》开放了「オカリナ演奏」：

- 手机上**自由演奏**；
- 用"传闻任务"积分换来的**乐谱**做引导演奏 / 自动演奏；
- **自制乐谱**，生成二维码分享。

这支虚拟陶笛给的是 **7 个音**——完整自然音阶，而不是游戏内那 5 个按键音。

本项目按 **7 声音阶 + 高八度** 建模，默认 C 大调白键 `C4 D4 E4 F4 G4 A4 B4 C5`。
如果 App 里是别的调（比如 D 多利亚），换一行参数即可：

```powershell
python build.py ..\midi\windfis2.mid 1 app7 "" "D4 E4 F4 G4 A4 B4 C5"
```

---

## 4. 转换的两道约束

### 4.1 音级

原曲（B 小调）用 7 个音级。把整首移调 t 个半音，看多少时值能落在 7 个音上：

| 移调 | 覆盖率 |
|---|---|
| **+10（→ A 小调）** | **96.2%** ★ |
| +5 | 90.4% |
| +3（→ D 小调） | 81.2% |
| 其他 | ≤ 67% |

最优是 **+10**：原曲 B 小调整体上移 10 个半音 = A 小调，正好是白键上的自然小调。
剩下的 3.8% 就是结尾那个 `A#`（原调 ♯7），自然音阶里没有——那正是**弯音**该上场的地方。

### 4.2 音域

原曲跨 **25 个半音**，7 音陶笛（含高八度）只有 **12 个半音**：

```
原曲:   F#5 ────────────────────────────── G7     (25 半音)
陶笛:        C4 ────── C5                        (12 半音)
```

**必须分段折八度**。本项目按乐句挑八度（相邻乐句换八度有平滑惩罚），结果是：
前 5 句整体 **-14 半音**，后 4 句整体 **-26 半音**。

### 4.3 两者耦合

移调同时决定"音级对不对"和"这个八度合不合"。而且八度只能按 12 半音整倍挪，
所以会出现"整体高 3 个半音、降一个八度又低 5 个半音"的尴尬位置——
第 5 句 `A5 D6 G6` 就卡在这里。

---

## 5. 方法

```
MIDI ─► 选轨 ─► 单声部化 ─► 量化 0.25 拍 ─► 选移调 ─► 分段折八度 ─► 动态规划配器 ─► 谱/MIDI/WAV
```

**动态规划配器**（`ocarina.arrange`）：给每个音符在候选音里挑一个，使总代价最小

```
发射代价  E(i,j) = w_i · ( |p_i − c_j| + λ·出界量 )
            w_i = 1 + 0.6·min(时值, 2)          ← 长音更重要，别乱改
转移代价  T(i,j|k) = α·| 原曲音程 − 实际音程 |     ← 保住旋律轮廓
                   + β·[原曲在动却落回同一个音]
```

- 乐句之间隔着休止时，转移代价归零（不然上一句的尾音会把下一句"拽歪"）；
- 状态数 = 候选音个数（这里 8），`O(n·m²)`，45 个音瞬间解完。

---

## 6. 谱子

数字是**音阶级数**（简谱）：`1 2 3 4 5 6 7`，`1'` 是高八度，`-` 表示延长半拍。

默认按 C 大调白键建模，所以 `1=C 2=D 3=E 4=F 5=G 6=A 7=B`，整首在 **A 小调**（1 = A）。

```
beat   0.0-  3.0   6 7 1'---                     原音: B5  C#6 D6
beat   4.0-  7.0   6 7 1'---                     原音: B5  C#6 D6
beat   8.0- 15.0   7 6 3 5-- 6-------             原音: C#6 B5  F#5 A5  B5
beat  16.0- 19.0   6 7 1'---                     原音: B5  C#6 D6
beat  20.0- 23.0   5 1' 1'---                    原音: A5  D6  G6
beat  24.0- 29.8   3 2 3--------                 原音: F#6 E6  F#6
beat  34.0- 41.2   7- 6- 3- 3-- 4-----           原音: C#7 B6  F#6 F#6 G6
beat  42.0- 54.0   1' 1' 7 6 3 2 3 6 4- 4 5--- 1 2 5 3---
                   ↑ 原音: E7 D7 C#7 B6 F#6 E6 F#6 B6 G6 G6 A6 C6 E6 A6 F#6
beat  55.5- 65.0   1 6------- 5-- 1'-- 1'--       原音: D6  B6  A#6 G7  F#7
```

换成音名读，主题就是原曲本身：

```
主题： A B C | A B C | B A E G A | A
原曲： B C# D | B C# D | C# B F# A | B      （同一个自然音阶，整体移调）
```

逐音表格（含每个音被改了多少半音）在 `out/tab.txt`。

---

## 7. 还原度

**39/45 完全命中（86.7%）**，平均偏差 0.42 个半音（按时值加权 0.52）。

| 段落 | 结果 |
|---|---|
| 主题（第 1、2、4 句）`B C# D` | `6 7 1'` = A B C，**零改动** ✅ |
| 第 3 句 `C# B F# A B` | `7 6 3 5 6`，零改动 ✅ |
| 第 5 句 `A D G` | `5 1' 1'`：第三个音 `G` 超出音域上限，压成 `C5`（差 5 个半音） |
| 第 6 句 `F# E F#` | `3 2 3`，零改动 ✅ |
| 第 7 句 `C# B F# F# G6` | `7 6 3 3 4`，零改动 ✅ |
| 高潮（第 8 句）`E7 D7 C#7 B6` | `1' 1' 7 6`：`E7` 超出上限，压成 `C5`（差 2 个半音）；其余照原样 |
| 结尾 `A# G7 F#7` | `A#` 是变化音（差 1 个半音，可用弯音补）；`G7 F#7` 超上限，各差 5 / 4 个半音 |

**一句话**：主题、副歌、展开段都是原样还原；只有冲到 `E7`–`G7` 的那几句被压到音域上限。
瓶颈不是音级不够（96.2% 都落在音阶上），而是**音域只有 12 个半音**。

---

## 8. 想更贴近原曲，可以这么做

1. **高潮两句整体降八度重写**，而不是让算法压到上限。人耳对"整体降八度"的容忍度，远高于"所有音挤成一个"。
2. **用弯音补半音**：结尾 `A#` 推半音；长音收尾时轻轻下压做个滑音，很像真陶笛。
3. **把级进改成琶音**：时之笛自己的曲子（`Song of Time` = A–D–F）就是琶音写法，比硬塞经过音更有"陶笛味"。
4. **只在长休止处换八度**（`fold_phrases` 就是这么做的），别在半句中间跳。

---

## 9. 复现

```powershell
# 需要 Python 3.10+（核心只用标准库；render.py 用 numpy + Pillow）
# 在仓库根目录跑，out/ 会自动重建
python src/build.py                                   # 默认：windfis2 第 1 轨 + App 7 音
python src/switch2.py                                 # 生成 Switch 2 手按谱
python src/stats.py                                   # 还原度统计
python src/dump.py midi/windfis2.mid                  # 看 MIDI 内容

# 换音集合 / 强制移调
python src/build.py midi/windfis2.mid 1 app7 "" "D4 E4 F4 G4 A4 B4 C5"
```

参数：`build.py <midi> <轨道> <音集合> <强制移调> <自定义音名>`。
换别的歌只要换 MIDI；多轨的先用 `dump.py` 找出旋律在哪一轨。

---

## 10. 来源

**谱子**
- [VGMusic · Game Boy 区（Link's Awakening）](https://www.vgmusic.com/music/console/nintendo/gameboy/)
- [VGMusic · Ballad of the Windfish (Arranged)](https://www.vgmusic.com/file/000982006ac06a38aa0308dcf2bf9c30.html)
- [flat.io · Ballad of the Wind Fish 总谱](https://flat.io/score/69a60a930ccf163ab4112c51-ballad-of-the-wind-fish)
- [Ultimate Guitar · 和弦谱](https://tabs.ultimate-guitar.com/tab/misc-computer-games/the-legend-of-zelda-links-awakening-ballad-of-the-wind-fish-chords-5313324)

**陶笛**
- 近藤浩治谈五音限制（2005 Nintendo Power，转引自 [danbruno.net](https://danbruno.net/writing/ocarina/)）
- [任天堂官方支持 · 用麦克风演奏陶笛](https://en-americas-support.nintendo.com/app/answers/detail/a_id/71860/~/how-to-use-mic-input-to-play-the-ocarina-(the-legend-of-zelda:-ocarina-of-time))
- [ZELDA NOTES 官方页（オカリナ演奏 / 楽譜作成）](https://www.nintendo.com/jp/zelda/notes/ocarina/index.html)
- [nintenderos · 重制版全部曲目与按键](https://www.nintenderos.com/2026/11/todas-las-canciones-de-la-ocarina-en-zelda-ocarina-of-time-remake/)
- [jeuxvideo · 曲谱与按键（YXAYXA / ALRALR…）](https://www.jeuxvideo.com/news/2113207/chants-zelda-ocarina-of-time-ou-trouver-toutes-les-melodies-a-l-ocarina.htm)
- [actugaming · 13 首曲子与 App 虚拟陶笛](https://www.actugaming.net/melodies-zelda-ocarina-of-time-832931/)
- [Zelda Universe 论坛 · 陶笛的 45 个音（弯音 + L/R 组合）](https://zeldauniverse.net/forums/index.php?thread/94823-how-to-play-real-songs-on-the-in-game-ocarina/)

曲目版权归任天堂 / 近藤浩治所有；MIDI 为玩家自制。本目录仅作技术研究。
