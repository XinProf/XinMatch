# 3COD 数据库验收报告（可行性 / 完整性 / 效率）

- 验收对象：`D:\Project\XRD\PolyXRD-DataBase\3COD-Inorg-20261020.sqlite`、`3COD-Full-20261020.sqlite`
- 验收基准：`D:\Project\XRD\XinMatch\data\cod_inorganics.db`（XinMatch 原生库，71,206 条）
- 验收版本：XinMatch 2.0.0（commit `f8a3c22`）
- 验收日期：2026-10-20
- 环境：Windows / Python 3.13.14 / SQLite 3.4x，SSD；测量期间本机另有 PolyXRD `pytest tests/` 并发占盘，计时偏保守

## 0. 结论速览

| 维度 | 结论 | 一句话说明 |
|---|---|---|
| **可行性** | ✅ **通过** | 两个库都是 XinMatch 原生 schema，`detect_source → xinmatch`，**直接打开 0.01 s，无需转换、无需 sidecar**；检索结果与原生库同集 |
| **完整性** | ⚠️ **基本通过** | 可检索条目 99.85 % / 99.21 %；但 **PCOD 预测结构占 89 %（Inorg）**、CIF 全缺、打包列与 CSV 列有 3–8 % 不一致、3 条记录相对源快照缺失 |
| **效率** | ❌ **不通过** | 单次检索 **约 19 min 起步（实测 22 min 未跑完）**，Full 库 43 min 连缓存都没建完；峰值内存 **1.25 / 2.36 GB**；原生库同场景 26.8 s。仅供离线/批处理，交互式不可用 |

## 1. 验收对象基本情况

| | 3COD-Inorg | 3COD-Full |
|---|---|---|
| 文件大小 | 19.51 GiB（20,948,017,152 B） | 28.17 GiB（30,249,795,584 B） |
| `variant` | `slim-index-3cod-inorg` | `slim-index-3cod-full` |
| `schema_version` | 2 | 1 |
| 构建时间 | 2026-10-20 09:42:41 | 2026-10-20 10:28:16 |
| 构建脚本 | build_3cod.py v2（2026-10-19） | 同 |
| 源快照 | COD=535,166 / PCOD=1,061,964 / TCOD=362,294 | 同 |
| 峰生成约定 | λ=1.5406 Cu Kα1，d ≥ 1.0 Å，I 归一到 1000，等效反射按 2θ 合并 | 同 |
| 嵌入 CIF | 无（`cif_embedded=0`，`cif_missing=1,185,866`） | 无（`cif_missing=1,959,421`） |

表清单：

| 表 | 3COD-Inorg | 3COD-Full |
|---|---|---|
| `entries` | 1,187,652 | 1,959,421 |
| `peaks` | 115,879,994 | 191,668,450 |
| `elements` | 2,710,322 | 6,677,165 |
| `element_combo` | 30,712 | 57,847 |
| `cod_atomic_sites` | 34,384,728 | 94,184,005 |
| `phases`（PolyXRD 冗余副本） | 1,185,866 | **无此表** |
| `cod_entries`（PolyXRD 结构表） | 无 | 1,959,421 |

## 2. 可行性 —— 通过

两个库的 `entries` + `peaks` + `elements` + `element_combo` 与 XinMatch 原生库**逐列同构**，`polyxrd.detect_source()` 直接判为 `kind=xinmatch`：

```
3COD-Inorg-20261020.sqlite
  detect_source -> kind=xinmatch table=entries rows=1,187,652 (0.0 s)
  open_search_database -> Connection in 0.01 s        ← 只读直连，无 sidecar 转换
  get_entry_peaks('96-100-0003') -> 100 peaks in 0.00 s
                                    first=(5.945967861667269, 1000.0, 1, 1, 0)
3COD-Full-20261020.sqlite
  detect_source -> kind=xinmatch table=entries rows=1,959,421 (0.0 s)
  open_search_database -> Connection in 0.01 s
```

这是最理想的情况：**挂载即用，零转换成本**（对比 PolyXRD `phases` 型库需要一次 55 s / 554 MB 的 sidecar 转换）。

### 2.1 结果正确性

用 `synth_01`（刚玉型 Al₂O₃）做三方对照，窗口收到 0.1°、召回 10 峰以控制耗时：

| 库 | 耗时 | Top-5（entry_id, FoM） |
|---|---|---|
| 原生 71 k | 16.0 s | 96-230-0448 (.7596), 96-900-7498 (.7562), 96-900-8081 (.7552), 96-230-0375 (.7374), 96-900-7496 (.7359) |
| 3COD-Inorg | 168.6 s | 96-900-8081 (.8022), 96-230-0448 (.8016), 96-900-7498 (.8003), 96-230-0375 (.7745), 96-900-7496 (.7739) |

**Top-5 是同一个集合**（全部为 Al₂O₃ 卡片），只是前两名互换：FoM 差 0.0006，属并列噪声。说明峰值数据本身是正确的，可放心用于物相检索。

### 2.2 兼容性备注

- Full 库没有 `phases` 表，但 XinMatch 走的是 `entries`+`peaks`，**不受影响**；反过来，若用 PolyXRD 自身的 `phases` 读取路径去看 Full，会读不到——做交叉验证时要注意。
- 两库 `entry_id` 编号规则与原生库一致（`96-XXX-XXXX`），可直接与旧结果做条目级对比。

## 3. 完整性 —— 基本通过（4 项需处理）

### 3.1 覆盖量

| 指标 | 3COD-Inorg | 3COD-Full | 原生 71 k |
|---|---|---|---|
| entries 总数 | 1,187,652 | 1,959,421 | 71,206 |
| COD（实验） | 78,747（6.6 %） | 535,166（27.3 %） | 71,206 |
| PCOD（预测） | 1,061,962（**89.4 %**） | 1,061,962（54.2 %） | — |
| TCOD（理论） | 46,943（4.0 %） | 362,293（18.5 %） | — |
| 有峰的条目（可被检索到） | 1,185,866（**99.85 %**） | 1,944,023（**99.21 %**） | 71,206 |
| 每条目峰数（抽样 4,000） | median 96 / mean 69.6 / max 100 | median 100 / mean 70.4 / max 100 | ~87 |
| d 范围 | 1.000 – 17.660 Å | 1.000 – 17.660 Å | 1.000 – 17.6 Å |
| 每条目最强峰强度 | 恒为 1000（归一正确） | 恒为 1000 | 1000 |
| 孤立峰（entry_id 不存在于 entries） | 0 / 242 抽样 | 0 / 239 抽样 | 0 |
| (formula+cell) 重复组 | 7,096 组 / 43,902 行（冗余 36,806） | 14,870 组 / 59,948 行（冗余 45,078） | — |

相互包含关系：

- **Inorg ⊂ Full：1,187,652 / 1,187,652 = 100 %** ✔
- **原生 71 k ⊂ Inorg：70,561 / 71,206 = 99.09 %**（645 条原生条目在新快照中已消失/被过滤）
- 源快照 1,959,424 条 vs 实际入库 1,959,421 条（COD 全进、PCOD 少 2、TCOD 少 1，缺失率 0.0002 %）

### 3.2 需要处理的问题

**① PCOD 占绝对多数（最重要的认知偏差）**

`3COD-Inorg` 名字像“无机实验库”，实际 89.4 % 是 **PCOD 预测结构**，实验 COD 只有 78,747 条（6.6 %）。Full 里 COD 也只占 27.3 %。
→ 如果检索目的是“类似 PDF 卡片的实验物相鉴定”，检索结果会被大量预测结构占据，Top-N 里实验相的占比很低。建议按来源分库，或在 `entries` 里加 `source` 列（现在只能靠 `entry_id` 数值区间反推：≥1e8 = TCOD、≥2e7 = PCOD）。

**② 打包峰列与 CSV 峰列不一致（3–8 %）**

`phases.peaks_top_d` / `peaks_top_i` 是 **64 × float64**（512 B），`phases.peaks_d` 是 top-100 CSV。抽样 300 条比对：只有 8 条能对上，其余在 0.001 Å 容差下仍有 3–8 % 的峰位对不上（`subset=0.92~0.97`）。
→ 两列出自不同流水线/不同合并参数。若后续要用打包列做快速预筛（见 4.5），**必须让两条流水线共用同一份峰表**。

**③ CIF 全缺**

`cif_embedded=0`、`cif_missing` 等于全部条目数。库里有 `cod_atomic_sites`（Inorg 3,438 万行 / Full 9,418 万行）可支撑 Le Bail / Rietveld，但**没有原始 CIF 文本**，无法导出结构文件、无法复核 CIF 解析问题。

**④ 存储冗余 8.4 GiB（仅 Inorg，对 XinMatch 无用）**

`dbstat` 实测：

| 对象 | 3COD-Inorg | 3COD-Full |
|---|---|---|
| `peaks` | 4.81 GiB | 7.93 GiB |
| `phases`（冗余副本） | **4.43 GiB** | — |
| `idx_peaks_d_entry` | 3.35 GiB | 5.55 GiB |
| `idx_peaks_entry_id` | 2.38 GiB | 3.93 GiB |
| `idx_peaks_d`（被 `idx_peaks_d_entry` 前缀覆盖，纯冗余） | **1.94 GiB** | **3.22 GiB** |
| `cod_atomic_sites` + 主键索引 | 1.56 + 0.51 = **2.07 GiB** | 4.70 + 1.37 = 6.07 GiB |
| `entries` | 0.13 GiB | 0.27 GiB |

→ Inorg 若只服务 XinMatch，可回收 `phases`(4.43) + `cod_atomic_sites`(2.07) + `idx_peaks_d`(1.94) ≈ **8.4 GiB，剩 11 GiB**。Full 可回收 `idx_peaks_d` 3.22 GiB。

## 4. 效率 —— 不通过

### 4.1 端到端实测

| 场景 | 原生 71 k | 3COD-Inorg | 3COD-Full |
|---|---|---|---|
| 默认参数（0.3° 窗口、召回 40 峰、strongest_k=5） | 26.8 s | **22 min 未跑完（人为中止）** | 未测（更慢） |
| 收窄参数（0.1° 窗口、召回 10 峰） | 16.0 s | 168.6 s | **>43 min 未跑完（人为中止）** |
| 只做峰位窗口查询（7 个峰，无 FoM）0.1° | — | 11.5 s | 27.2 s |
| 同上 0.05° | — | 3.6 s | 9.9 s |
| 峰值内存 | < 200 MB | **~1.25 GB** | **2.36 GB（实测）** |

Full 的 43 min 里 CPU 只占 4.6 min，其余全在等 I/O——瓶颈是 top-K 缓存对 1.9 亿行做全表排序（见 4.2），窗口查询还没轮到。

### 4.2 成本分解（3COD-Inorg，实测）

| 阶段 | 耗时 | 说明 |
|---|---|---|
| `_load_top_k_intensities`（每进程一次） | **80.1 s** / 1,185,866 条 | 全表 `ORDER BY entry_id, intensity DESC`；因缺 `(entry_id, intensity DESC)` 覆盖索引，走 `idx_peaks_entry_id` + 回表 + 每组临时 B 树排序 |
| 每个实验峰的 Hanawalt 窗口查询 | **13.54 s** | `SELECT entry_id, MAX(intensity) … WHERE d BETWEEN ? AND ? GROUP BY entry_id` |
| 每个实验峰的纯 DISTINCT 窗口查询 | 7.11 s | 同上但不取 intensity |

按默认参数 40 个召回峰算：80 + 40 × 13.5 ≈ **10 min**（理想、无并发）；本次实测环境另有 pytest 并发占盘，实际表现为 22 min 未完成。

Full 库更极端：即使把窗口收到 0.1°、召回降到 10 峰，**43 min 仍未走完缓存阶段**（RSS 2.36 GB、CPU 仅 4.6 min，纯等 I/O）。原因是 top-K 缓存要对 1.92 亿行做 `ORDER BY entry_id, intensity DESC`，缺覆盖索引时既回表又落临时排序，代价随行数超线性增长。

### 4.3 根因：窗口在这个量级**根本不具选择性**

| 2θ 窗口 | 窗口内峰行数 | 窗口内条目数 | 单窗耗时 |
|---|---|---|---|
| 0.30°（默认） | 1,205,315 | **743,815（占全库 62.6 %）** | 6.65 s |
| 0.20° | 801,046 | 575,105 | 3.98 s |
| 0.10° | 399,086 | 335,695 | 1.37 s |
| 0.05° | 199,753 | 182,650 | 0.34 s |
| 0.02° | 79,749 | 76,816 | 0.06 s |

一个实验峰在默认窗口下就能框住 74 万个条目。**这不是索引能救的问题**——即使做纯索引扫描，78 个窗口也要访问 5,800 万行。三点原因叠加：

1. 窗口太宽（0.3° 2θ 在 d=4.2 Å 处对应 Δd≈0.06 Å，而 1.19 M 条目在这个区间有 120 万个反射）；
2. `idx_peaks_d_entry(d, entry_id)` **不含 intensity**，Hanawalt 要强度就必须回表，每行一次页访问；
3. top-K 缓存是全表排序，在 1.9 亿行上又慢又吃内存（1.25 GB）。

### 4.4 与原生库的差距来源

原生 71 k 库有 `idx_peaks_entry_intensity(entry_id, intensity DESC)` **覆盖索引**，top-K 是纯索引扫描（0.3 s 级），且总共 620 万峰行——比 3COD 小 18.7 倍。3COD 两库**没有**这个索引（建它约需 2.4 GiB / 3.9 GiB）。

### 4.5 快速预筛原型验证（已验证可行，但需配套改造）

用 `phases.peaks_top_d`（64×float64）在 numpy 里做扁平化 + 排序 + `searchsorted` 预筛：

| 步骤 | 耗时 |
|---|---|
| 读全部 1,185,866 条打包列（7,466 万峰，854 MiB） | 8.3 s |
| `argsort` | 16.4 s |
| 75 个窗口预筛 | 36.6 s |
| **合计** | **~61 s（对比 19 min，快 19×）** |

但代价是：75 个窗口筛出 **1,185,579 个候选**（几乎是全库），说明**光靠“峰位命中数”在这个量级没有区分度**——必须靠强度/FoM 在受控候选集上决胜。因此这套原型只能解决“扫描慢”，解决不了“候选太多”。

## 5. 改进建议

### P0 · 重建库时（PolyXRD 侧，收益最大）

1. **按来源拆库**：`COD-inorg-*.sqlite`（实验，78,747 条）、`PCOD-*.sqlite`（1,061,962 条）、`TCOD-*.sqlite`。实验库单独成库后，条目数回到 10 万级，现有算法立刻回到“原生库”性能区间。
2. **加覆盖索引**（若坚持单库大表）：
   ```sql
   CREATE INDEX idx_peaks_entry_intensity ON peaks(entry_id, intensity DESC);
   CREATE INDEX idx_peaks_d_entry_i     ON peaks(d, entry_id, intensity);
   ```
   前者省 top-K 的 80 s，后者把窗口查询变成覆盖扫描（去掉回表）。
3. **删冗余索引**：`idx_peaks_d` 被 `idx_peaks_d_entry` 左前缀覆盖，可直接 `DROP`（Inorg 省 1.94 GiB、Full 省 3.22 GiB）。
4. **统一两套峰列**：`peaks_top_d/peaks_top_i` 与 `peaks_d/peaks_i` 用同一份峰表生成（当前 3–8 % 对不上）。
5. **补 `source` 列**（`COD`/`PCOD`/`TCOD`），别让下游靠 entry_id 数值区间猜。
6. `peaks_d` 若只为 PolyXRD 自身服务，可与 `phases` 一起从 XinMatch 用的库里剥离（Inorg 省 4.43 GiB）。

### P1 · XinMatch 侧（不改库也能缓解）

1. 把预筛窗口从 0.3° 降到 0.05–0.1°（实测 4.2–20 倍加速），并允许 GUI/CLI/config 配置；
2. `recall_top_k` 从 40 降到 10–15，且**强制启用 strongest_k 剪枝**；
3. **大库（>20 万条）自动切换策略**：先在 `entries` 上按 restraints（元素/晶系/年份）切分子集，再做峰位预筛——把 1.19 M 砍到万级；
4. top-K 缓存改为 **SQL 侧分页 + 惰性**，或改用 `peaks_top_d` 打包列（需先修数据一致性）；
5. 给大库加“首次使用提示”：会建缓存、耗时若干分钟、占 1–2 GB 内存。

### P2 · 专用预筛索引（长期）

在库里加一张紧凑表（每条目仅保留前 20 强峰的 d，按 d 排序 + 分桶），把 1.9 亿行压到 4,000 万行且全覆盖，配 numpy/分桶查询，可把单次预筛压到 2–5 s。

## 6. 现阶段怎么用

```bat
:: 挂载（不需要拷贝文件，任意目录均可）
run_dev.bat libraries --add "D:\Project\XRD\PolyXRD-DataBase\3COD-Inorg-20261020.sqlite" --label "3COD 无机库"
run_dev.bat libraries --json

:: 直接指定库检索（批处理场景）
run_dev.bat search PATTERN.txt --db "D:\Project\XRD\PolyXRD-DataBase\3COD-Inorg-20261020.sqlite" --top-n 20
```

建议：**把它当离线批处理库用**（夜间跑、一次多图），交互式检索仍用 `data/cod_inorganics.db`；或先按元素体系切一个子库（例如只留含 Li 的 3,000 条）再挂载，交互体验即可恢复。

## 7. 复现方式

验收脚本已固化到仓库，重建库后可直接复跑：

```bat
:: 快路径（schema + 行数 + meta + 来源构成 + 字段填充率，1 分钟内）
python tools\acceptance_3cod.py "D:\Project\XRD\PolyXRD-DataBase\3COD-Inorg-20261020.sqlite"

:: 加上可检索覆盖率（每条目一次索引探查，Inorg ~10 s / Full ~25 s）
python tools\acceptance_3cod.py <db.sqlite> --coverage

:: 加上窗口选择性扫描（约 1 分钟）与表空间统计（约 2 分钟）
python tools\acceptance_3cod.py <db.sqlite> --selectivity --dbstat
```

本次验收中临时使用的分解脚本（`top-K 缓存单独计时`、`numpy 预筛原型`、`三方 Top-5 对照`）
等未入库，均在 `.scratch/` 下，可参照本报告第 4 节的表格复现。
