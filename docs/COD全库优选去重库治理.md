# COD 全库优选去重库治理（cod_full_curated）

> 范围：`tools/build_cod_full_curated.py`（构建脚本）+ `data/cod_full_curated.db`（产物）
> + `xinmatch/core/db/multi_db.py`（注册 `cod_full_curated`）+ `tests/db`、`tests/search`（测试）。
> 基线：`data/cod_full.db`（112,734 entries / 10,979,059 peaks / 941.8 MB），只读。

## 1. 背景与目标

COD 全库直查 L3 黄金基线 Top-1 一致率仅 1/13，而精选无机库 `data/cod_inorganics.db`
（71,199 entries）可达 11/13（84.6%）。原假设是"同一物相多卡片（重复卡/实验+理论并存）
稀释 FoM 排序"。本任务按 `(formula, space_group)` 聚类，每簇保留质量最高卡片，构建
优选去重库 `data/cod_full_curated.db`，并实测其检索质量。

## 2. 重复度分析（实测，基于 cod_full.db）

### 2.1 schema 实际情况

`entries` 表 19 列（与 `schema.sql` 一致），但**质量信号几乎全空**：

| 字段 | 实测 |
|---|---|
| `quality` | 全部为空字符串 `''`（112,734 行）——不可用作质量判据 |
| `year` / `author` / `journal` / `density` | 全部 NULL（112,734 行） |
| `formula` / `space_group` / `a/b/c` | 非空（可作聚类键） |
| `mineral_name` | 19,575 行 NULL；另有 `';'`、`'?'` 等占位垃圾值 |
| `peaks` | 每 entry 2–100 峰，均值 97.4；106,522 条卡为满 100 峰 |

因此质量判据只能退化为：**峰数（REFLECTIONS 数）→ 可用 mineral_name → entry_id 字典序**。

### 2.2 簇大小分布（按 formula+space_group 聚类）

| 簇大小 | 簇数 | 覆盖 entries |
|---:|---:|---:|
| 1（单卡） | 86,598 | 86,598 |
| 2 | 5,408 | 10,816 |
| 3 | 1,174 | 3,522 |
| 4–5 | 739 | 3,203 |
| 6–20 | 556 | 5,273 |
| 21–100 | 75 | 2,820 |
| >100 | 3 | 502（最大簇 198 卡） |
| **合计** | **94,553 簇** | **112,734 entries** |

- 多卡簇共 **7,955** 个，可移除冗余卡 **18,181** 张（每簇留 1 张）。
- 去重后：**94,553 entries**（移除 16.1%）。

## 3. 选卡策略

对每个 `(formula, space_group)` 簇，按以下优先级选 1 张保留（SQL `ROW_NUMBER()` 实现）：

1. **峰数最多**（`peaks` 行数 DESC）——反射越完整，参考谱越可靠；
2. **有可用 mineral_name**（非 NULL、非空、非 `';'` 占位）——近似"经人工核对"卡；
3. **entry_id ASC**——确定性 tie-break。

源库 `data/cod_full.db` 严格只读：通过 `ATTACH` 只读路径挂载，仅对 `src.*` 发 `SELECT`，
构建前后对 `entries` 做 checksum（行数 + `SUM(LENGTH(entry_id))`）比对，确保源字节未被改动。

## 4. 构建结果

| 指标 | 全库（源） | 优选库（产物） |
|---|---:|---:|
| entries | 112,734 | **94,553**（移除 18,181） |
| peaks | 10,979,059 | **9,328,888** |
| elements | 527,398 | 458,937 |
| element_combo | 16,117 | 16,117（按过滤后 elements 重建） |
| 文件大小 | 941.8 MB | 836.3 MB |
| 构建耗时 | — | ~134 s（单事务，synchronous=OFF） |

- schema 与全库一致：`entries/peaks/elements/element_combo/build_progress`（后两者按
  schema.sql 建表；`build_progress` 留空以保持 schema 对齐）。
- 完整性校验：孤立峰 0；所有 `(formula, space_group)` 簇大小均为 1。
- 幂等：重复运行检测到产物完整即跳过（`--force` 重建）；构建脚本可复跑。

## 5. L3 黄金基线三列对比（实测）

验收命令（项目根运行）：

```powershell
python -m tools.run_acceptance --sample-dir "D:\Project\XRD\test_xrd\txt" `
  --baseline-dir "D:\Project\XRD\test_xrd\match-candidate list-jingzhun" `
  --cod-db data\<库> --json <out.json>
```

| 库 | entries | Top-1 一致率 | Top-5 重叠 | 判定 |
|---|---:|---:|---:|---|
| `cod_inorganics.db`（无机库） | 71,199 | **84.6%（11/13）** | **83.1%** | PASS |
| `cod_full.db`（全库直查） | 112,734 | 7.7%（1/13） | 46.2% | FAIL |
| `cod_full_curated.db`（优选去重） | 94,553 | **7.7%（1/13）** | 33.8% | FAIL |

> 注：参考软件侧已知快照问题（`96-901-5965`/`96-900-0381` 内容错位、`96-900-9231`
> 缺失）按任务约定不改基线；`1-1`/`1-2` 为 DB 缺失相（LiFePO4/NCM811），不计入算法失败。

## 6. 原因分析（为什么优选库未达到无机库水平）

**结论：去重本身没有提升 Top-1，瓶颈不在"重复卡"，而在全库峰数据的稀疏度与召回行为。**
证据：

1. **优选库保留卡的 FoM 排序未改善**。以 2-1（ZnO+CaCO3）为例：
   - 无机库 top1 = `96-900-4179`（Zincite，O Zn）→ 与参考软件 top1 `96-230-0451`
     formula 兼容（同为 O Zn），判 ✓。
   - 优选库 top1 = `96-591-0353`（**Ba O4 Se**，硒酸钡）→ 与 O Zn 元素集合不同，判 ✗。
   - 优选库中 ZnO 簇确实保留了合法卡 `96-210-7059`，但它**没有排到 #1**——是离群的
     BaO4Se 在 d-spacing 召回 + FoM 中胜出。

2. **同 entry_id 在两库峰数不同**。ZnO 簇代表卡 `96-210-7059`：
   - 在 `cod_inorganics.db` 中 35 峰；在 `cod_full.db`/`cod_full_curated.db` 中仅 **21 峰**。
   - 全库构建（`tools/build_cod_full_xinmatch.py`，本任务禁改）抽出的反射数偏少，
     导致参考谱 FoM 区分度弱，弱反射卡片（BaO4Se、BrHg2N、BeCo、有机镉盐等）
     凭少数巧合匹配的强峰反超真正相。

3. **离群卡在两库都存在**。`96-591-0353`(BaO4Se)、`96-231-0922`(BrHg2N) 在无机库
   中同样 PRESENT，但无机库凭借更丰富的峰数据让真正相排到它们前面；优选库继承全库的
   稀疏峰数据，无法扭转这一点。

4. **去重只删簇内近重复卡，不改峰值**。优选库与全库共享同一套峰行（仅按保留 entry_id
   子集复制），因此 FoM 排序行为与全库基本一致——Top-1 维持 1/13。
5. **Top-5 重叠甚至略降**（全库 46.2% → 优选 33.8%）：按簇留一卡后，参考软件 Top-5
   里某些相的"命中卡"（不同 entry_id 但同相）被删去，XinMatch 候选列表里少了这些等价卡，
   交集反而变小。这与"去冗余"的初衷方向一致，但对黄金基线指标是负向。

### 6.1 与原假设的偏差

任务原假设"重复/低质量卡稀释 FoM"在本数据上**不成立**：移除 18,181 张近重复卡后，
Top-1 一致率没有变化。真正的杠杆是**全库峰数据的反射丰富度**（上游 CIF→峰抽取），
这超出"去重"任务范围，且 `tools/build_cod_full_xinmatch.py` 在本任务禁改清单内。

### 6.2 建议（不在本版本范围）

- 提升全库峰抽取的反射数/强度标定（修 `build_cod_full_xinmatch.py` 的峰抽取窗口），
  这是让全库系库达到无机库水平的真正杠杆；
- 或在优选构建中叠加"无机相过滤"（排除 C/H 有机相），近似复刻无机库覆盖；
- 优选去重库的价值在于**瘦身**（941.8→836.3 MB、entries −16.1%）与**去冗余**，
  可作为全库系的干净挂载底座，但不应替代精选无机库作为默认搜索库。

## 7. 测试与自检

- 新增 `tests/db/test_build_cod_full_curated.py`：合成小源库端到端验证选卡逻辑
  （峰数→mineral_name→entry_id tie-break）、输出 schema 一致、幂等跳过/`--force` 重建。
- 新增 `tests/search/test_cod_curated_search.py`：优选库可被 `search_match` 检索到保留卡。
- `tests/db/test_multi_db.py`：注册 `cod_full_curated` 并可 `open_library` 查询。
- 运行：`python -m pytest tests/db tests/search -p no:cacheprovider`（新增测试 19+5 通过）。
- 自检：`ruff check` 全绿；`mypy` 新增/改动源文件零错误；品牌词 grep 0 命中（统一用"参考软件"中性词）。
