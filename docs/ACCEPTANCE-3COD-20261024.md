# 三库 `.xinDB` 独立验收报告（v3.0.0 复验，2026-10-24）

> 本文是 2026-10-24 对 XinMatch **v3.0.0** 三个无机物参考库的独立复验（只读，不改库）。
> 与 [`ACCEPTANCE-3COD-20261020.md`](ACCEPTANCE-3COD-20261020.md)（建库当时的验收）互补：
> 那一份证明"库是按规范建出来的"，这一份从"发布产物"角度复核结构/记账/来源/元素索引/
> 峰载荷/端到端检索，并给出每库是否可以发布、哪些已知坏相需要登记。
> 总体代码评估见 [`CODE-REVIEW-v3.0.0-20261024.md`](CODE-REVIEW-v3.0.0-20261024.md)。

- **日期**：2026-10-24
- **验收人**：db-acceptance（独立复核，不参与建库/改码）
- **对象（只读）**：
  - `D:\Project\XRD\XinMatch-DataBase\data\COD-Inorg-20261020.xinDB`
  - `D:\Project\XRD\XinMatch-DataBase\data\PCOD-Inorg-20261020.xinDB`
  - `D:\Project\XRD\XinMatch-DataBase\data\TCOD-Inorg-20261020.xinDB`
- **纪律**：全程 `sqlite3` `mode=ro`（`PRAGMA query_only` 未用于独立脚本）只读打开；未修改任何库文件、未改源码/docs、未 commit。原始 JSON/日志在 `.scratch/review-v3/db/raw/`，脚本在 `.scratch/review-v3/db/scripts/`（`.scratch/` 不入 git；§10.2 的命令可随时重跑）。
- **环境**：`D:\Project\XRD\python310\python.exe`（Python 3.10.11，numpy 2.2.6，sqlite 3.40.1）。注意：`docs/v3.0.0-验收报告.md` 的历史耗时数字是在另一套环境（`C:\Users\Administrator\.workbuddy\...\python.exe`，Python 3.13.14 / numpy 2.5.3）测的，绝对耗时不能直接横向比。
- **代码状态**（检索路径）：主仓库 HEAD `beda021`；`reader_v3.py` sha256 `2f92f9f9…`、`search_v3.py` `1b410fae…`、`fom.py` `814a92c3…`、`model/peak.py` `25f5bfe3…`，这 4 个文件在工作树中 **clean**（其余文件被并行任务改过，但不在本次读取/检索路径上；每个 JSON 的 `code_state` 都记录了这一点）。
- **并发负载**：e2e 测量期间本机同时在跑 Lead 的全量 pytest 与另外 3 个 review 任务（多进程读同一批库）。因此**绝对耗时只作量级参考**，本报告同时给出 `time.process_time()` 的 CPU 耗时。

## 0. 结论摘要

| 库 | `validate_xindb` | 独立全量复核 | 自召回 Top-1 / Top-5 | 结论 | 可发布？ |
|---|---|---|---|---|---|
| **COD-Inorg** | 26 项，0 FAIL / 1 WARN（已知 `E1.lattice`，`96-210-4629`） | 除 1 条已知退化晶胞外，全部不变量 0 违规；**新发现 5 个坏相**（峰表只剩 d=0.7703 假峰，见 §8.1） | 38/40（95%）/ **40/40（100%）**；2 例 Top-1 失配均为**库内重复相**（见 §5.2） | **WARN** | **是**（附 8 个已知坏相登记：3 条 d=1.0 + 5 条新发现；建议引擎修好后重建） |
| **PCOD-Inorg** | 25 项，0 FAIL / 0 WARN | 全部不变量 0 违规（全量扫描，非抽样）；**新发现 7 个坏相**（同为 d=0.7703 假峰，§8.1） | **40/40（100%）/ 40/40（100%）** | **PASS** | **是**（附 7 个坏相登记；建议重建） |
| **TCOD-Inorg** | 25 项，0 FAIL / 0 WARN | 全部不变量 0 违规（全量扫描，非抽样） | **40/40（100%）/ 40/40（100%）** | **PASS** | **是** |

**一句话**：三个库作为**文件/结构/记账/元素索引**层面的发布产物是自洽的，README §1/§4 的核心数字全部复核通过；唯一的数据质量缺口是 COD 里 8 个单峰坏相（其中 5 个是本轮新发现的一类，§8.1），以及少量 README 文案口径偏差（§4）。

---

## 1. 方法与环境

### 1.1 三层验收

1. **工具层**：DB 仓库自带的 `tools/validate_xindb.py`（`S/M/C/E/P/X` 六组只读检查）。按任务要求从 DB 仓库根执行 `python -m tools.validate_xindb <db> --json <out>`（它会 `sys.path` 插入 DB 仓库根，import 自己 vendored 的 `xinmatch` 子集）。
2. **独立层**：另写 4 个不 import 任何 `xinmatch` 代码的脚本（纯 `sqlite3` + `numpy`），对**全部** entries/chunks/element_inv 做全量不变量检查（不是抽样）：
   - `check_structure.py`：文件/PRAGMA/schema/meta/计数/entry_id/peak_off 阶梯/element_inv 全量 membership/峰载荷全量（长度、有限性、d 范围、norm-1000、零填充、`top ⊆ all`）。
   - `check_provenance.py`：用共享扫描清单 `D:\Project\XRD\sync-COD\inorg_manifest.sqlite`（1,959,421 行，`id_clash=0`）做**全量** id 归属 + 40 条/库的源 CIF 存在性/formula/elements 对照 + `skipped_no_peaks` 对账。
   - `mask_consistency.py`：`entries.elem_mask` 与 `entries.elements` 逐 entry 重算比对（63 位截断口径）。
   - `peak_count_audit.py`：峰数分布 + 单峰异常相排查（PCOD/TCOD）。
3. **端到端层**：主仓库真实代码 `XinDBReader` + `search_match_v3` 做自召回（方法同 `docs/v3.0.0-验收报告.md` §8.3 / `data/_accept_3cod.py`）：从库内取某相全峰表 d/I → Bragg 反推 2θ（λ=1.5406，强度直接给 I）→ 检索回本库，看 `entry_id` 是否在 Top-1/Top-5。随机种子固定 `20261020`，每库 40 条（PCOD 任务要求≥20，这里也做 40 以对齐报告 §8.3 的 40/40 声明）。

### 1.2 库文件指纹（本次验收针对的确切字节）

| 库 | 字节 | MiB | SHA256（前 16） | mtime |
|---|---|---|---|---|
| COD | 118,710,272 | 113.211 | `328c6acb96f504df` | 2026-10-23T16:41:35 |
| PCOD | 1,776,353,280 | 1694.062 | `3eb1a35b990d611f` | 2026-10-23T12:30:27 |
| TCOD | 71,352,320 | 68.047 | `5cd6516ebb0c6d10` | 2026-10-22T23:46:08 |

（完整 SHA256 在 `raw/structure_{cod,pcod,tcod}.json` 的 `file.sha256`。）

---

## 2. `validate_xindb` 结果

命令（cwd=`D:\Project\XRD\XinMatch-DataBase`；对 COD/TCOD 加大到**全部 chunk**，PCOD 默认 8 个 chunk；seed 与报告一致）：

```powershell
python -m tools.validate_xindb data\COD-Inorg-20261020.xinDB  --sample-chunks 20 --sample-entries 1000 --seed 20261020 --json .scratch\review-v3\db\raw\validate_cod.json
python -m tools.validate_xindb data\TCOD-Inorg-20261020.xinDB --sample-chunks 12 --sample-entries 1000 --seed 20261020 --json .scratch\review-v3\db\raw\validate_tcod.json
python -m tools.validate_xindb data\PCOD-Inorg-20261020.xinDB --sample-chunks 8  --sample-entries 500  --seed 20261020 --json .scratch\review-v3\db\raw\validate_pcod.json
```

| 库 | 检查项 | PASS | FAIL | WARN | INFO | 退出码 | 工具自报耗时 | 墙钟 | 结论 |
|---|---|---|---|---|---|---|---|---|---|
| COD | 26 | 18 | 0 | 1 | 7 | 0 | 9.0 s | 9.4 s | PASSED WITH WARNINGS |
| PCOD | 25 | 19 | 0 | 0 | 6 | 0 | 10.8 s | 10.9 s | PASSED |
| TCOD | 25 | 19 | 0 | 0 | 6 | 0 | 5.5 s | 5.7 s | PASSED |

**FAIL 明细**：无。

**WARN 明细**（唯一一条，与 README §4/§6 一致）：

```
[WARN] E1.lattice  non-physical cell values: a=1, b=1, c=1, volume=1,
       alpha=1, beta=1, gamma=1 (e.g. 96-210-4629)
```

COD 比 TCOD/PCOD 多一项，是因为它的 `E3.space_group` INFO 行（127 条无空间群）——不是问题。

> 工具自检范围说明：`P1.payload` 只解码 `--sample-chunks` 个块；PCOD 默认 8/260 ≈ 3%。本报告的 §3 独立脚本对**全部** 260 块做了同样的检查（并且是全量逐 entry，而不是抽样 entry），结论一致（见 §3.6）。

---

## 3. 独立一致性复核（声明 vs 实测）

判据：`raw/structure_*.json`、`raw/provenance_*.json`、`raw/mask_consistency_*.json`。

### 3.1 容器与 PRAGMA

| 声明（README） | 实测 COD / PCOD / TCOD | 判定 |
|---|---|---|
| 单文件 SQLite，`journal_mode=DELETE` | `delete` / `delete` / `delete` | ✓ |
| 无 `-wal`/`-shm` 侧车 | 三个 `-wal/-shm/-journal` 均不存在 | ✓ |
| SQLite 头文件写/读版本 = 1（rollback journal） | `1/1`、`1/1`、`1/1` | ✓ |
| `PRAGMA integrity_check` = ok | `ok`（0.47 s / 4.25 s / 0.23 s） | ✓ |
| 可直接放只读介质（只读打开不写） | `mode=ro` 打开、校验、e2e 全程无任何写入、无侧车产生 | ✓ |
| —（附加）freelist=0、page_size=4096、UTF-8 | `0 / 4096 / UTF-8` ×3 | ✓ |

### 3.2 计数与块记账

| 声明（README §1/§3.4） | 实测 COD | 实测 PCOD | 实测 TCOD | 判定 |
|---|---|---|---|---|
| 相数 | 78,036 | 1,061,953 | 46,846 | ✓ 三项均 = `COUNT(*)` = `meta.entry_count` |
| 反射数 | 9,394,774 | 159,274,265 | 5,874,790 | ✓ `SUM(n_peaks)` = `SUM(peak_n)` = `SUM(length(all_d))/4` |
| 块数 | 20 | 260 | 12 | ✓ = `ceil(N/4096)`，`chunk_id=0..K-1` 连续 |
| `SUM(peak_chunks.n)` = 相数 | ✓ | ✓ | ✓ | ✓ |
| `peak_off` 全局阶梯连续 | 0 条违规（全量 78,036 行） | 0 条违规（1,061,953 行） | 0 条违规 | ✓ |
| `n_peaks == peak_n` | 0 违规 | 0 违规 | 0 违规 | ✓ |
| `n_peaks ≤ 150` | max 150 | max 150 | max 150 | ✓ |
| 峰/相 min/max/mean（README §3.4） | 1 / 150 / 120.39（README 120.4） | 1 / 150 / 149.9824（README “150.0”） | 3 / 150 / 125.41（README 125.4） | COD/TCOD ✓；PCOD 见 §4.1 |
| `SUM(length(top_d))/4` = N×32 | 2,497,152 ✓ | 33,982,496 ✓ | 1,499,072 ✓ | ✓（PCOD 单相峰数有例外，但 top 矩阵恒为 N×32） |

### 3.3 meta

- **必需键**：`META_KEYS` 10 个键全部非空（`schema_version / peak_convention / top_k / chunk_size / dtype / entry_count / build_time / cif_source / build_tool / library_kind`），另有 README 要求的 `data_date`；共 17 个键。
- **取值**：`schema_version=3`、`top_k=32`、`chunk_size=4096`、`dtype=f32`、`peak_convention=CuKa1-1.5406-d0.7703-30.0-merge-mult-DW-norm1000`、`library_kind=<KIND>-Inorg`、`data_date=20261020` 与文件名 `<kind>-20261020.xinDB` 全部一致；`build_tool=tools.build_cod_inorg_xindb`。
- **附加键**：`tier_default=1`、`element_mask_scheme=iupac128-v1`、`element_mask_bits=63`、`element_mask_full_bits=128`、`element_bits`（118 个符号的位表）、`element_mask_unmapped`（55 个 bit≥63 的符号）。
- **build_time** 与 README §1 注释一致：COD `2026-10-21T17:25:59+08:00`、TCOD `2026-10-22T23:29:11+08:00`、PCOD `2026-10-22T23:46:14+08:00`。
- ⚠ `meta.cif_source` 仍是**旧路径** `D:\Project\XRD\PolyXRD-DataBase\inorg_cif\<KIND>`：README 说 2026-10-23 源已迁到 `D:/Project/XRD/sync-COD`。库建于迁出之前，属 build-time provenance，不影响数据；但会误导 2026-10-23 之后的读者（见 §4.4）。

### 3.4 `entry_id` 号段与来源（跨源污染判据）

| 库 | 声明号段 | 实测 entry_id min…max | 反解原生 id | 号段内违规 | 与 manifest 对账 |
|---|---|---|---|---|---|
| COD | `[0, 20M)` | `96-100-0003` … `96-901-7926` | 1,000,003 … 9,017,926 | 0 / 78,036 | manifest(COD, is_inorg=1) 79,198 条，DB 全量 ⊆，缺失 0 |
| PCOD | `[20M, 100M)` | `96-210-00000` … `96-295-85139` | 21,000,000 … 29,585,139 | 0 / 1,061,953 | manifest 1,061,962 条，DB 全量 ⊆，缺失 0 |
| TCOD | `[100M, 1e9)` | `96-110-000001` … `96-140-354736` | 110,000,001 … 140,354,736 | 0 / 46,846 | manifest 46,943 条，DB 全量 ⊆，缺失 0 |

- 格式：`^96-\d{3}-\d+$` 违规 0；`entry_id` 唯一性 = 相数；`entries.rowid` 严格 `0..N-1`（`element_inv`/chunk 寻址前提）。
- 三个号段互不重叠，且**全量** DB id 都能在本来源的 manifest 里找到（`ids_missing_from_own_manifest = 0`；`db_ids_not_in_any_manifest_lib = 0`）——不是抽样，是 118 万条 id 全查。
- 源→库的对账（manifest `is_inorg` 文件数 = 磁盘 `*.cif` 数）：

| 库 | 源 CIF（磁盘实测） | manifest is_inorg | 入库相数 | 差 | 构建日志 `skipped_no_peaks` | 差 |
|---|---|---|---|---|---|---|
| COD | 79,198 | 79,198 | 78,036 | 1,162 | 1,162 | **0** ✓ |
| PCOD | 1,061,962 | 1,061,962 | 1,061,953 | 9 | 9 | **0** ✓ |
| TCOD | 46,943 | 46,943 | 46,846 | 97 | 97 | **0** ✓ |

- 抽样 40 条/库（seed=20261020）：源文件存在 40/40、lib 标签正确 40/40、DB `formula` 与 manifest 逐字一致 40/40、元素集合一致 40/40。`manifest.meta.id_clash = 0`。

### 3.5 元素倒排与 `elem_mask`

| 声明 | 实测 COD / PCOD / TCOD | 判定 |
|---|---|---|
| `element_inv` 元素数 = 96 / 19 / 91 | 96 / 19 / 91，且与 `entries.elements` 实际并集**完全相等**（既不缺也不多） | ✓ |
| `element_inv` ⊇ `entries.elements` 实际集合（缺失 0） | **全量 membership 逐元素相等**：每个元素的倒排数组 == 该元素在全部 entries 里的 rowid 集（不是抽样） | ✓ |
| `eids` 升序去重、值域 < N、4 字节对齐 | 全部元素均满足，0 违规 | ✓ |
| `elem_mask` 与 `elements` 一致（63 位截断口径） | 逐 entry 重算：**0 不一致**（78,036 / 46,846；PCOD 见 §3.5 注） | ✓ |
| 报告 §2：“21,650 相（27.7%）含 bit≥63 元素” | COD **21,650（27.744%）**——逐相精确复现；TCOD 12,552（26.79%） | ✓ |
| mask=0 但有元素列表的相 | COD 610、TCOD 524（全部由 bit≥63 元素构成，符合 63 位截断约定） | ✓（已知限制，非缺陷） |

注：PCOD 全量 1,061,953 相复算：**0 不一致**；含 bit≥63 元素的相 27 个（0.003%，PCOD 元素本就只有 19 种低 Z 元素，正常）。

### 3.6 峰载荷（**全部** chunk、全部 entry，非抽样）

| 检查 | COD | PCOD | TCOD |
|---|---|---|---|
| 检查范围 | 20/20 chunk，78,036 entry | 260/260 chunk，1,061,953 entry | 12/12 chunk，46,846 entry |
| `top_*` 长度 = n×32×4、`all_d`/`all_i` 等长 4 字节对齐 | 0 违规 | 0 违规 | 0 违规 |
| 非有限值（d/i） | 0 | 0 | 0 |
| d ∈ [0.7703, 30.0]（全库 min/max 见下） | 0 越界 | 0 越界 | 0 越界 |
| 强度负值 | 0 | 0 | 0 |
| norm-1000：**每个相**全峰最大值 = 1000±0.05 | 0 违规 | 0 违规 | 0 违规 |
| 全零强度相 | 0 | 0 | 0 |
| `top` 的 32 列零填充严格为 0 | 0 违规 | 0 违规 | 0 违规 |
| `top ⊆ all`（逐相、按 float32 位模式精确匹配） | 0 缺失 | 0 缺失 | 0 缺失 |
| 全库 d min / max | 0.770300 / 29.9981 | 0.770300 / 30.0000 | 0.770300 / 29.7257 |
| 全库 I max | 1000.0 | 1000.0 | 1000.0 |

> 结论：三库的所有反射载荷在“长度/有限性/d 范围/归一化/填充/两套表示一致性”上完全自洽。`check_structure.py` 全量扫描 PCOD 的 1.27 GB 峰载荷用时 26.9 s。

### 3.7 已知数据缺口（与 README §4/§6、报告 §8.5/§8.6 对照）

| 项 | 声明 | 实测 | 判定 |
|---|---|---|---|
| 退化晶胞 | COD 1 条 `96-210-4629`（a=b=c=1、volume=1） | ✓ 同一条；字段为 **NULL**（不是 1） | ✓（README 文字写“a=b=c=1”，实际 NULL，见 §4.3） |
| 无空间群 | COD 127 条（`E3` 仅提示） | 127 | ✓ |
| `crystal_system` 为 NULL | COD 11（§8.5.6）、PCOD/TCOD 0 | 11 / 0 / 0 | ✓ |
| 空元素列表 | 无 | 0 / 0 / 0 | ✓ |
| `tier` 分布 | — | 全 1（预测/理论库也标 1，见 §4.6） | 记录 |

### 3.8 与历史报告的其它数字对账

| 声明 | 实测 | 判定 |
|---|---|---|
| 构建耗时 COD 3,478.5 s（58.0 min）/ PCOD 45,852.9 s（12.7 h）/ TCOD 1,016.4 s（16.9 min） | 构建日志 `data/_build_*.log` 实测 3,478.5 / 45,852.9 / 1,016.4 s | ✓ |
| 构建速率 PCOD 1,389.6 相/min、COD 1,346.0、TCOD 2,765.3 | 日志同值 | ✓（README §3.4 的 1,590 相/min 是“单进程 COD 切片”口径，不可与全量 14 workers 直接比） |
| 三库合计 1,186,835 相 / 174,543,829 反射 / 292 块 / 1.83 GiB | 相加全部吻合（1,186,835 / 174,543,829 / 292 / 1,966,415,872 B = 1.831 GiB） | ✓ |

---

## 4. 声明 vs 实测：不一致清单（按严重度）

> 任务口径：发现不一致必须写清「声明 vs 实测」。以下按“是否影响发布判断”排序。

### 4.1 PCOD “150.0（全为上限截断）”不成立（README §3.4）

- **声明**：`PCOD-Inorg | 1,061,953 | 159,274,265 | 150.0（全为上限截断）`。
- **实测**：平均 149.9824；`n_peaks` **min=1**，且有 **581 个相（0.0547%）** 的峰数 <150（`n_peaks=1` 的有 **6 个**），并非“全部截断在 150”。
- **影响**：只是 README 文案；`meta`/载荷自洽。**不阻塞发布**，建议把“全为上限截断”改为“平均 150.0，绝大多数截断在 150，581 个相 <150”。

### 4.2 任务书/BRIEF 的 “1.69 GiB” 与 README 的 1694.1 MiB

- 任务书说 PCOD “1.69 GiB”；README §1 写 `1,776,353,280 B（1694.1 MiB）`；按 GiB 折算为 **1.654 GiB**。任务书的 1.69 GiB 是换算口径错误（把 1694 MiB 误当 GiB），README 的 MiB 数值正确。**不阻塞**。

### 4.3 README §4/§6 对退化晶胞的描述：“a=b=c=1、体积=1” vs 实测 NULL

- **声明**：`96-210-4629`：`a=b=c=1、体积=1`。
- **实测**：该行 `a,b,c,alpha,beta,gamma,volume` 全为 **NULL**（`validate_xindb` 的 `E1.lattice` 也报 NULL）。README 的“=1”来自源 CIF 的占位值语义，但**库内落的是 NULL**。
- **影响**：文字准确性问题；该相本就应剔除/重建。**不阻塞**。

### 4.4 `meta.cif_source` 是迁移前旧路径

- **声明**（README §3.2/§8 版本表）：源数据 2026-10-23 起统一在 `D:/Project/XRD/sync-COD`。
- **实测**：三库 `meta.cif_source` 仍为 `D:\Project\XRD\PolyXRD-DataBase\inorg_cif\<KIND>`（库建于 10-21/22，早于迁移）。
- **影响**：纯 provenance 文案；**不阻塞**。下次重建会自动带新路径。

### 4.5 README §5：“本机 data/ 里有三个库与 `_backup/`（两个历史副本）”

- **实测**：`XinMatch-DataBase\data\` 只有 3 个 `.xinDB`，**没有 `_backup/`**。
- **影响**：README 对本机状态的描述过期；不涉及发布产物。**不阻塞**。

### 4.6 未核实项（本机缺证据，不能算通过）

| 项 | 说明 |
|---|---|
| Release zip 的字节数（87.2 MiB / 1.35 GiB / 54.1 MiB）与 `SHA256SUMS.txt` | 本机 `XinMatch-DataBase` 下没有 zip / SHA256SUMS，也未见 `_release/`；只核对了**解压后库文件**的字节与 SHA256（见 §1.2）。 |
| `tier` 语义 | PCOD/TCOD 全库 `tier=1`（含 TCOD 理论库），若产品约定“实验=0、预测/理论=1”，则 TCOD 也标 1 属预期；未见冲突，仅记录。 |
| 构建速率 1,590 相/min（README §3.4） | 口径为“单进程 COD 切片”，未复跑，不能与全量 14 workers 的 1,346 相/min 对比。 |

### 4.7 历史报告 §8.3/§8.4 的耗时/自召回数字（见 §5、§6）

- 报告 §8.3：TCOD 自召回 40/40、中位 **372 ms**；PCOD 40/40、中位 **4,835 ms**。
- 本次实测：TCOD 40/40、中位 **0.540 s**（CPU 0.547 s）；PCOD 40/40、中位 **6.080 s**（CPU 6.046 s）。差异主要来自**环境**（报告用 Python 3.13.14/numpy 2.5.3，本任务固定 Python 3.10.11/numpy 2.2.6）与**并发负载**；命中率结论一致。§8.4 的分段耗时同理（§6 给了 CPU 耗时以便在忽略负载的情况下对照）。

---

## 5. 端到端自召回（真实读取/检索链路）

方法：每库随机 40 相（`random.Random(20261020).sample(range(N), 40)`），取该相 `fetch_peaks` 全峰表 → `2θ = 2·asin(λ/(2d))`、强度直接用 I → `search_match_v3(exp, reader, 1.5406, top_n=10)`。**先做一次冷调用**（含加载 prescreen 矩阵），再逐条计时。

### 5.1 结果

| 库 | 相数 | 完成 | Top-1 | Top-5 | 中位检索（墙钟） | 中位检索（CPU） | 冷调用（含矩阵加载） |
|---|---|---|---|---|---|---|---|
| COD | 78,036 | 40 | **38/40 = 95%** | **40/40 = 100%** | 0.623 s | 0.625 s | 0.657 s |
| PCOD | 1,061,953 | 40 | **40/40 = 100%** | **40/40 = 100%** | 6.080 s | 6.046 s | 6.221 s |
| TCOD | 46,846 | 40 | **40/40 = 100%** | **40/40 = 100%** | 0.540 s | 0.547 s | 0.533 s |

原始数据：`raw/self_recall_{cod,pcod,tcod}.json`（含逐条 `top5_ids`、`rank_of_true`、`n_prescreened=800, truncated=true`、`code_state`）；逐条 JSONL 同目录。

### 5.2 COD 的 2 例 Top-1 失配 = 库内重复相（不是检索缺陷）

| 被检索相 | Top-1 实际返回 | 证据 |
|---|---|---|
| `96-722-1944` | `96-434-4467` | 两行 `formula / space_group / a,b,c / volume / n_peaks` **完全相同**（`Ca17.4 Ce1.2 Li1.2 O48 Si12 Sr4.2`，Pn a 21，20.5411/9.34901/5.55337，1066.463 Å³，150 峰） |
| `96-900-4430` | `96-900-4429` | 同上（`C O7 Si Y2`，P -1，6.5495/6.6291/6.4395，Iimoriite-(Y)，150 峰） |

COD 库内共有 **2,002 组** `(formula, a, b, c)` 完全相同的相、共 **4,475 个 entry**（例：`O2 Si` 309 条、`Mg O` 208 条）。这些相的粉图逐位相同/近似，Top-1 落到“同结构的另一个 entry”属**数据固有歧义**，Top-5 仍 100%。若产品要求 To-1 唯一性，需要在建库期做去重/合并（`docs/COD全库优选去重库治理.md` 有相关方案），不是检索代码问题。

### 5.3 说明

- 自召回只验证“库里的相能检索回自己”，**不验证判别力**；判别力见历史报告 §3（13 个标准相 Top-1 13/13）。
- 报告 §8.3 只对 TCOD/PCOD 做了 40/40 声明；COD 的 40 条自召回是本轮新增（结果 95%/100%，失配原因已定位）。

---

## 6. 检索耗时拆分（prescreen / fetch_peaks / fetch_meta / rank）

方法同 `data/_prof_search_pipeline.py`：用同一条谱的前 40 强峰做 prescreen（tolerance=0.02、min_match=2、rank_limit=800），再 `fetch_peaks(候选)`、逐条 `fetch_meta`、`rank_candidates`；每个库取前 3 个样本各跑 3 遍取中位；同时记录 `time.process_time()` 的 CPU 耗时。

### 6.1 实测（中位，ms）

| 阶段 | COD | PCOD | TCOD | 报告 §8.4 TCOD | 报告 §8.4 PCOD |
|---|---|---|---|---|---|
| 1 prescreen（40 窗） | 238.1 | 4,062.2 | 155.1 | 106.0 | 3,010.0 |
| 2a fetch_peaks（800 候选） | 98.0 | 1,454.4 | 81.5 | 55.1 | 1,293.1 |
| 2b fetch_meta × 800 | 52.6 | 58.3 | 60.9 | 25.7 | 30.4 |
| 3 rank_candidates | 198.0 | 241.7 | 251.8 | 102.2 | 202.4 |
| 合计（热） | 584.3 | 5,900.2 | 561.0 | 289.0 | 4,535.9 |
| 冷调用（含矩阵加载） | 657 | 6,221 | 533 | 331.7 | 5,144.2 |
| 候选/命中 | 800 / 75,246（截断） | 800 / 1,057,102（截断） | 800 / 44,622（截断） | 800 | 800 |

CPU 耗时（`process_time`，排除 I/O 等待）：COD = 593.8 ms、TCOD = 562.5 ms、**PCOD = 5,875.0 ms**（prescreen 4,046.9 / fetch_peaks 1,453.1 / fetch_meta 62.5 / rank 250.0），与墙钟几乎一致——这些阶段基本是 CPU-bound。

### 6.2 解读

- **量级一致**：TCOD → PCOD 的倍率关系与报告 §8.4 的结论一致（prescreen 与库规模成正比；fetch_peaks 与 chunk 数/库体积成正比；rank 只与候选数有关）。
- **绝对值不可直接比**：报告数字用 Python 3.13/numpy 2.5、机器空闲；本次用 Python 3.10/numpy 2.2，且与 Lead 全量 pytest、另 3 个 review 任务并发。CPU 时间也系统性偏高（TCOD prescreen 156 vs 106 ms、rank 250 vs 102 ms），说明不全是负载，**Python/numpy 版本差异**是重要因素。结论：报告 §8.4 的“prescreen 占 2/3、fetch_peaks 占 28%、4.5 s 是规模代价”的**结构与量级判断成立**，绝对数值应以同一环境重测为准。
- PCOD 单条检索（`search_match_v3`）中位 **6.080 s**（CPU 6.046 s），在任务给的“单条可接受 10 s”预算内；比报告 §8.3 的 4.835 s 高约 26%，主要差在 prescreen（4,062 vs 3,010 ms，+35%）——同为环境差异 + 本机并发负载，**没有发现退化路径**。
- 另一个值得记录的观察：prescreen `min_match=2` 在 40 个测量窗上几乎不剪枝——COD 命中 75,246/78,036（96.4%）、TCOD 44,622/46,846（95.3%）、**PCOD 1,057,102/1,061,953（99.5%）**，候选上限 800 实际全靠 prescreen 的排序（`main_hit → whits → hits`）截断。自召回 40/40 说明该排序对“完全正确的谱”足够好；但 PCOD 上 prescreen 的筛选裕度很小，若换成真实实验谱（峰位/强度有偏差），候选 800 之外的相会直接丢失——这是 `min_match=2` 在密集理论库上的固有风险，不是本轮缺陷，记录供后续评估。

---

## 7. 元素筛选正确性抽查

**独立判据**：直接 `sqlite3` 读 `element_inv` 的 `eids` 解码成布尔掩码（不经过 reader），要求：

1. `reader.element_filter(group, N)` == 独立掩码的 AND；
2. `prescreen(..., elements_allowed=group, rank_limit=n_hits+1)` == 未过滤候选列表按“独立元素掩码”过滤后的**同序**结果；
3. 每个候选都确实含全部要求元素；
4. 未知元素 → 0 候选（不静默忽略）；空集合 → 等价于不过滤。

分组来源：COD 抽 6 组、TCOD 抽 4 组（从库内真实多元素相的 `elements` 组合里取，均 ≥3 元素）；PCOD 再从 19 种元素里取 3 组。

### 7.1 结果

| 库 | 元素组合（required=全部） | 库内满足相数 | 过滤后候选（命中 d 窗） | 与“未过滤候选 ∩ 倒排”同序 | mask 差异 | 越界候选 |
|---|---|---|---|---|---|---|
| COD | Mn, Sb, Yb, Zn | 7 | 7 / 76,921 | ✓ | 0 | 0 |
| COD | Ir, La, Si | 4 | 4 / 75,778 | ✓ | 0 | 0 |
| COD | Mg, Ni, O, Si | 146 | 145 / 71,206 | ✓ | 0 | 0 |
| COD | C, Fe, Mo, Pr | 1 | 1 / 75,868 | ✓ | 0 | 0 |
| COD | C, O, Si, Y | 5 | 5 / 76,818 | ✓ | 0 | 0 |
| COD | Ga, Na, O | 70 | 70 / 77,377 | ✓ | 0 | 0 |
| TCOD | B, K, O, Tm | 2 | 2 / 46,219 | ✓ | 0 | 0 |
| TCOD | Na, O, Si | 504 | 502 / 46,442 | ✓ | 0 | 0 |
| TCOD | Al, O, Y | 17 | 17 / 45,499 | ✓ | 0 | 0 |
| TCOD | Mo, O, Pr | 16 | 16 / 46,216 | ✓ | 0 | 0 |
| PCOD | O, P, V | 4,894 | 4,894 / 1,060,835 | ✓ | 0 | 0 |
| PCOD | O, Si | 954,610 | 951,803 / 1,059,106 | ✓ | 0 | 0 |
| PCOD | Be, F | 18,942 | 18,942 / 1,059,796 | ✓ | 0 | 0 |

（“过滤后候选”= 该组合全部满足相的 prescreen 结果，再做 d 窗匹配；所以可能略小于“库内满足相数”，例如 Mg,Ni,O,Si 的 146 个相里只有 145 个命中探针谱的测量窗——这正是 `expected = 未过滤候选 ∩ 元素倒排` 的口径。）PCOD 的 `O,Si` 一例有 951,803 个候选，逐条**同序**相等，因此记录 1 条 WARN（列表极大但结论不降级）。

**API 边界行为**（每库都测）：

| 测试 | 结果 |
|---|---|
| 未知元素（如 `MnQ`/`BQ`/`OQ`）→ 0 候选，不静默忽略 | ✓ 三个库均 0 |
| `elements_allowed=set()` 等价于不过滤 | ✓（合成谱无命中时平凡相等；另用真实谱复测 COD：`n_unfiltered=5`，空集结果逐位相同） |
| 返回候选必含全部要求元素（`fetch_meta` 复核） | ✓ COD `Sr+O` 过滤 Top-5（`96-100-0003` …）全部含 Sr、O |
| `element_filter` 掩码 vs 独立倒排 AND | ✓ 13/13 组 0 行差异（全库 78,036 / 46,846 / 1,061,953 行级比对） |

结论：**元素筛选在三个库上全部正确**——掩码与倒排逐行一致、`prescreen(elements_allowed=...` 与“未过滤候选 ∩ 元素倒排”逐位同序、未知元素/空集语义正确、无越界候选。唯一 WARN 是 PCOD `O,Si` 的 95 万级候选列表（真实现象：PCOD 90% 相含 O+Si）。原始数据：`raw/element_filter.json`、`raw/confirm_extra.log`。

---

## 8. 疑似缺陷与“只记录不修”项

> 发现疑似库缺陷一律用 SQL/脚本取证并给 `entry_id`；**未修改库、未修改源码**。

### 8.1 【新发现】COD 5 + PCOD 7 个相只剩一条 d=0.7703 Å（2θ=180°）假峰 —— 峰引擎边界缺陷（不是打包问题）

**证据（SQL + 用 build 时代码从源 CIF 复现）**：

| 库 | entry_id | 库内 payload（全峰表） | 剔除 180° 边界反射后的真实峰数 |
|---|---|---|---|
| COD | `96-100-8057` | `d=[0.77029997] I=[1000.0]` | 122 |
| COD | `96-151-1248` | 同上 | 228（重建后上限截断 150） |
| COD | `96-153-3251` | 同上 | 152（→150） |
| COD | `96-154-5882` | 同上 | 413（→150） |
| COD | `96-210-1175` | 同上 | 79 |
| PCOD | `96-231-03437` | 同上 | 150（截断） |
| PCOD | `96-232-31453` | 同上 | 150 |
| PCOD | `96-235-07656` | 同上 | 150 |
| PCOD | `96-254-30092` | 同上 | 150 |
| PCOD | `96-256-30724` | 同上 | 150 |
| PCOD | `96-264-40783` | 同上 | 150 |
| PCOD | `96-254-30089` | `d=[4.148173, 0.7703] I=[0.013, 1000.0]` | 150（真实峰被压到 I=0.013） |

**根因（用 DB 仓库 build 时代码 + 主仓库 HEAD 均能复现，见 `scripts/repro_lp_180.py`、`repro_single_peak_steps.py`、`env_hypothesis.py`）**：

1. `compute_pattern_from_structure` 用 `measurable = (2.0 * d) > wavelength` 剔除 180° 不可测反射；当某 hkl 的 d 恰好 = λ/2 = 0.7703 Å 时，浮点结果为 `2*0.7703000000000001 > 1.5406` **成立**，该 180° 反射被放进来（这 12 个相的源 CIF 都至少有一条晶胞轴恰好是 0.7703 的整数倍——实测 c/a/b = 7.703(×10)、10.7842(×14)、5.3921(×7)、8.4733(×11)、11.5545(×15)、13.8654(×18)……，所以真的存在 d=d_min 的 hkl；两种 Python/numpy 环境（3.10+numpy2.2 与 3.13+numpy2.5）复现结果一致）。
2. `_lorentz_polarization` 在 2θ→180°（θ→90°）时 `1/cosθ` 发散，该反射 raw I 达 1e16~1e21（实测 `96-154-5882` raw I_max ≈ 7.1e21）。
3. norm-1000 后其它真实峰相对强度 < `REL_INTENSITY_CUTOFF=1e-5` 被全部滤掉 → 只剩这条边界假峰，最终 `n_peaks=1/2`、`I=1000`。

**影响**：COD 5/78,036（0.0064%）+ PCOD 7/1,061,953（0.00066%）= 12 个相的参考谱不可用（它们只有 2θ=180° 的线，不会误增正常匹配；但“查不到自己”）。`validate_xindb` 全过（`E1` 不覆盖、`P1` 抽样也难命中），库文件本身自洽——**数据质量缺陷，不是文件损坏**。

**修复状态（重要）**：主仓库**当前工作树**里 core-audit 已经在修这块——`peak_compute.py` 新增 `_MEASURABLE_REL_EPS=1e-9`（严格化 `2*d > λ*(1+eps)` 边界）与 LP 三角因子下限；用该修复版引擎重算：COD 的 5 个相恢复 122 / 150 / 150 / 150 / 79 峰（另有 3 条 d=1.0 假峰恢复 150 / 114 峰、`96-210-4629` 判为不可计算→剔除），PCOD 的 7 个相全部恢复 150 峰。**结论：引擎修复已在工作树中，重建 COD/PCOD 库即可清掉这 12 个坏相（连同 §8.2 的 3 条）；本轮验收不修改库、不修码。**

### 8.2 已登记未修的 3 条 d=1.0 假峰（报告 §8.6）

`96-156-3735`、`96-156-3736`、`96-210-4629`：晶胞被 gemmi 读成默认 (1,1,1,90,90,90) → 单峰 d=1.0。README §4/§6 与报告 §8.6 已登记，属“只记录不修”。本轮复核：这 3 条 payload 与文档一致；主仓库**当前工作树**的 `_cell_is_usable/_recover_cell` 修复已能把前两条恢复为 150 / 114 峰，`96-210-4629` 无文本晶胞可恢复 → 判为不可计算（重建时会少 1 个相，属预期）。

> 合计：COD 库内 `n_peaks=1` 的相 **8 条** = 3 条 d=1.0（已登记）+ 5 条 d=0.7703（本轮新发现）。COD `n_peaks≤2` 的相共 12 条，其余 4 条为真实少峰相。三库合计受“峰引擎坏相”影响的相 = COD 5 + PCOD 7 = **12 个**（d=0.7703 类）+ COD 3 个（d=1.0 类）。

### 8.3 PCOD 少量相峰数 <150（README 文案不符，§4.1）与 7 个边界坏相

- `n_peaks < 150` 共 **581** 个相（0.0547%），其中 `n_peaks=1` 6 个、`n_peaks=2` 1 个（即 §8.1 的 7 个边界坏相），其余 574 个为 4–149 峰的少峰相（未逐条复核，但不属本轮 ≥4 峰异常名单；大晶胞/高对称导致可用反射少是常见原因）。
- TCOD `n_peaks < 150` 13,086 个（27.9%，README 本来就没说“全截断”，其 min=3 / max=150 / 均值 125.4 与 README §3.4 一致）；TCOD 无边界坏相（只 1 个 `n_peaks=3` 的正常相 `96-140-070332` `C4`，d=[1.408,1.219,0.862] 合理）。
- PCOD/TCOD 的 `mask` 复算均 0 不一致（见 §3.5）。

### 8.4 COD 重复相导致的 Top-1 歧义

见 §5.2：2,002 组 `(formula,a,b,c)` 相同、4,475 个 entry。自召回 Top-1 95% 的主因。**不是缺陷**，是 COD 源数据本身的多来源重复；是否去重属产品决策。

### 8.5 其它只记录项

| 项 | 说明 |
|---|---|
| `meta.cif_source` 旧路径 | §4.4，重建时自动更新 |
| README §5 `_backup/` 不存在 | §4.5，文档过期 |
| Release zip/SHA256 未核实 | §4.6，本机无发布物 |
| COD 417 条 `formula` 为 NULL | 元数据缺口（这些相的 `elements`、晶胞、峰表都正常）；不在 README 声明范围，仅记录 |
| `96-210-4629` 的 `elements` 由原子位点补出 | 报告 §2.1 已说明，本轮复核其 `element_inv` 可查（`La,Mg,Na,O,W`） |

---

## 9. 每库结论与发布判断

### COD-Inorg — **WARN（可发布，需登记已知坏相）**

- 结构/记账/元素倒置/峰载荷全部自洽，`validate_xindb` 0 FAIL（1 条已登记 WARN）；全量独立复核除 1 条退化晶胞外 0 违规。
- 数据质量：8 条单峰坏相（3 已登记 + 5 新发现，§8.1）+ 2,002 组重复相（§8.4）。
- **判断：可发布**；建议在 Release notes 的“已知缺口”里补上“5 条 d=0.7703 单峰相（entry_id 见 §8.1）”，并在峰引擎修好后重建。

### PCOD-Inorg — **PASS（可发布，建议重建以清掉 7 个边界坏相）**

- 结构/记账/元素倒置/峰载荷全量自洽，`validate_xindb` 0/0；来源对账闭合（缺 9 = `skipped_no_peaks`）；自召回 **40/40 Top-1、40/40 Top-5**（中位 6.08 s，CPU 6.05 s）。
- 数据质量：7 个 §8.1 的边界坏相（0.00066%）+ README §3.4 文案“全为上限截断”与实际 581 个 <150 相不符（§4.1）。
- **判断：可发布**；建议 Release notes 登记 7 个坏相，并在引擎修复后与 COD 一起重建。

### TCOD-Inorg — **PASS（可直接发布）**

- 全量自洽 0 违规；自召回 40/40；来源对账闭合（缺 97 = `skipped_no_peaks`）；无退化晶胞/无 NULL 空间群/晶系。

---

## 10. 复现命令与产物

### 10.1 产物

| 类型 | 路径 |
|---|---|
| 报告 | `.scratch/review-v3/db-acceptance.md` |
| validate JSON/日志 | `.scratch/review-v3/db/raw/validate_{cod,pcod,tcod}.{json,log}` |
| 结构/一致性 | `.scratch/review-v3/db/raw/structure_{cod,pcod,tcod}.json` |
| 来源对账 | `.scratch/review-v3/db/raw/provenance_{cod,pcod,tcod}.json` |
| 元素 mask | `.scratch/review-v3/db/raw/mask_consistency_{cod_tcod,pcod}.json` |
| 自召回 | `.scratch/review-v3/db/raw/self_recall_{cod,pcod,tcod}.{json,jsonl,log}` |
| 耗时拆分 | 同上 JSON 的 `breakdown_median` / `breakdown_per_entry` |
| 元素筛选 | `.scratch/review-v3/db/raw/element_filter.json` |
| 峰数/单峰异常 | `.scratch/review-v3/db/raw/peak_count_audit.json` |
| 坏相取证 | `.scratch/review-v3/db/raw/{bad_phase_compare,bad_phase_cod_fixed,confirm_extra}.log`、`env_hypothesis.py` |
| 脚本 | `.scratch/review-v3/db/scripts/*.py`、`run_validate.ps1`、`run_e2e.ps1` |

### 10.2 一键复跑（只读）

```powershell
$py = 'D:\Project\XRD\python310\python.exe'
$db = 'D:\Project\XRD\XinMatch-DataBase\data'
cd 'D:\Project\XRD\XinMatch\.scratch\review-v3\db\scripts'
& $py check_structure.py   "$db\COD-Inorg-20261020.xinDB"  COD  ..\raw\structure_cod.json
& $py check_structure.py   "$db\PCOD-Inorg-20261020.xinDB" PCOD ..\raw\structure_pcod.json
& $py check_structure.py   "$db\TCOD-Inorg-20261020.xinDB" TCOD ..\raw\structure_tcod.json
& $py check_provenance.py  COD  ..\raw\provenance_cod.json
& $py mask_consistency.py  COD,TCOD,PCOD ..\raw\mask_consistency_all.json
& $py self_recall.py       COD  40 ..\raw\self_recall_cod.json
& $py self_recall.py       PCOD 40 ..\raw\self_recall_pcod.json
& $py check_element_filter.py ..\raw\element_filter.json
& $py peak_count_audit.py  ..\raw\peak_count_audit.json
# 工具层（cwd = D:\Project\XRD\XinMatch-DataBase）
$py -m tools.validate_xindb data\COD-Inorg-20261020.xinDB --sample-chunks 20 --json ..\XinMatch\.scratch\review-v3\db\raw\validate_cod.json
```

---

## 11. 发布产物核对（Lead 补验，2026-10-24）

§4.6 曾把"release zip / SHA256SUMS 无法核实"列为未核实项；Lead 在主仓库 `dist/` 下补做了核对：

| 项 | 实测 | 结论 |
|---|---|---|
| `dist/SHA256SUMS.txt` vs 实际文件 | `XinMatch-Setup-3.0.0.exe` = `de567ddbbb8cafed…`（256,400,880 B）、`XinMatch-Internal-3.0.0.zip` = `b252249956477d16…`（356,466,971 B）、`XinMatch-Databases-COD-Inorg-3.0.0.zip` = `9c1f6f982033634f…`（91,175,782 B），三者与 `SHA256SUMS.txt` 逐位一致 | ✅ |
| `XinMatch-Databases-COD-Inorg-3.0.0.zip` 内容 | 只含 `COD-Inorg-20261020.xinDB`（118,710,272 B）；其 SHA-256 = `328c6acb96f504df…`，与 §1.2 验收的库文件**逐字节相同** | ✅ 分发包就是验收过的那份库 |
| `XinMatch-Internal-3.0.0.zip` 内容 | 含 `data/COD-Inorg-20261020.xinDB`（118,710,272 B）与 `_internal/variant.txt`，内容 = `internal` | ✅ 便携包内置默认库、变体标识正确 |
| 冻结版 `dist/xinmatch-3.0.0/XinMatch.exe` | 清空 `XINMATCH_XINDB_DIR` 后 `libraries --json` → `xindb_cod_inorg` `available=true`、`entries=78036`、路径 `<exe>/data/COD-Inorg-20261020.xinDB`，exit 0 | ✅ 冻结包开箱可检索 |

> 唯一残留风险：本机全局环境变量 `XINMATCH_XINDB_DIR` 指向已不存在的旧目录时，冻结版会把内置默认库判为 unavailable
> （本轮已作为 P1 修复 `multi_db.xindb_default_dir()` 的坏 override 回退；v3.0.0 已发布二进制仍是旧逻辑）。
