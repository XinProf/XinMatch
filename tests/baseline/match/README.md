# 参考软件 黄金基线目录（tests/baseline/match/）

本目录存放 **L3 验收用的 参考软件 黄金基线**：每个样品一行 `{sample_id}.csv`，
格式为 参考软件 4.3 导出的候选列表（分号分隔），由
`tools/match_baseline.py::load_match_csv` / `load_match_baseline_dir` 直接解析。

> **重要事实声明**：这些候选 CSV **只能由人工在 参考软件 4.x 里跑完 Search-Match
> 后导出**。本仓库的脚本（`tools/import_match_baseline.py`）只负责把人工导出的
> 原始 CSV **规范化**到本目录，绝不生成、伪造或估算任何候选数据。

## 当前已入库基线（2026-10 人工导出）

| 子目录 | 内容 | 元素限定 | 候选行数 |
|---|---|---|---|
| `jingzhun/` | 13 个样品（1-1…7-2） | 精准（必含元素，`元素限定-jingzhun.txt`） | 6,209 |
| `alloption/` | 13 个样品（1-1…7-2） | 宽松（可能性元素，超轻/轻元素全选，`元素限定-alloption.txt`） | 13,778 |

两套均为人工在 参考软件 4.x 用 **FPFM（search-match using profile fitting，
无寻峰、无峰形处理、直接原始谱图）** + 数据库 **COD-Inorg 2025.12.01**
（`参考软件安装目录\RefDB_COD`）导出，经
`tools/import_match_baseline.py` 规范化（编码嗅探/欧式小数逗号/FoM 排序），
0 行拒绝。验收时 `run_acceptance.py --baseline-dir` 需指向具体子目录
（`tests/baseline/match/jingzhun` 或 `.../alloption`）。

> 实测结论：两套基线在 参考软件 top1 排序上完全一致（XinMatch 真实 COD 对
> 两套基线的 Top-1 一致率均为 69.2%），元素限定宽窄不影响 参考软件 top1
> ——5-x 差异（Calcite/Quartz/Goethite vs Magnesite/Hematite/Kaolinite）
> 属 参考软件 独有 FoM 偏好，非元素限定所致。

---

## 1. 规范格式（本目录每个 .csv 必须长这样）

```
Candidate list of sample <sample_id>
Entry;Qual.;Formula sum;Name;P(peakpos.);P(I/I0);P(#peaks);P(#corr.);I scale fct.;FoM
96-400-1849;C;Fe Li O4 P;;n.a.;n.a.;0.0000;n.a.;0.7083;1.0000
96-400-1848;C;Fe Li O4 P;;n.a.;n.a.;0.0000;n.a.;0.7127;0.9989
...
```

- 第一行为 banner（解析器不依赖其内容，`sample_id` 取**文件名主干**）。
- 第二行为固定表头（10 列，顺序固定）。
- 数据行按 **FoM 降序**。
- FPFM（Profile Fitting）模式导出时 `P(#peaks)=0.0000`、多个 P 列为 `n.a.`
  属正常现象——L3 比较以 **FoM 排序**为准。

---

## 2. 人工操作步骤（每个样品）

1. **加载谱图**：参考软件 → `File → Import → Diffraction data`，选择样品谱图
   （推荐两列 ASCII / `.txt` / `.xy`；参考 `tests/fixtures/SAMPLE_INDEX.md`
   第 5 节的推荐加载路径）。
2. **确认仪器参数**：`Experiment` 对话框里波长设为 Cu Kα1 = 1.5406 Å
   （与 XinMatch 默认一致）。
3. **跑 Search-Match**：`Search → Search-Match`（`Ctrl+M`），参考数据库选
   COD（与 `data/cod_inorganics.db` 同源）。
   - 建议同时跑两档设置并分别导出，供宽松/精准对照：
     - **精准档**（FPFM，默认选项）→ 对应现有 `match-candidate list-jingzhun\`。
     - **宽松档**（全部候选选项）→ 对应 `match-candidate list-alloption\`。
4. **导出候选列表**：`File → Export → Candidate list (CSV)`，
   文件名存为 `{sample_id}.csv`（如 `1-1.csv`、`CPD-1a.csv`）。
5. **规范化入库**（在项目根目录 `D:\Project\XRD\XinMatch` 下执行）：

   ```powershell
   # 单个文件：
   & D:\Project\XRD\python310\python.exe tools\import_match_baseline.py "D:\path\to\导出\1-1.csv"

   # 整个导出文件夹批量入库（按基线档次分目录）：
   & D:\Project\XRD\python310\python.exe tools\import_match_baseline.py "D:\Project\XRD\test_xrd\match-candidate list-jingzhun" -o tests\baseline\match\jingzhun
   & D:\Project\XRD\python310\python.exe tools\import_match_baseline.py "D:\Project\XRD\test_xrd\match-candidate list-alloption" -o tests\baseline\match\alloption
   ```

   脚本会自动处理：UTF-8/Windows-1252 编码嗅探、欧式小数逗号（`0,7083`→`0.7083`）、
   缺列补 `n.a.`、FoM 排序、坏行（缺 Entry / FoM 不可解析）报告而不中断。
6. **自检**：脚本末尾会用生产加载器 `load_match_baseline_dir` 回读一遍，
   打印可解析样品数；也可手动：

   ```powershell
   & D:\Project\XRD\python310\python.exe -c "from pathlib import Path; from tools.match_baseline import load_match_baseline_dir; b=load_match_baseline_dir(Path('tests/baseline/match')); print({k: len(v.candidates) for k,v in b.items()})"
   ```

---

## 3. 样品清单来源（三大样品源，详见 tests/fixtures/SAMPLE_INDEX.md）

| 来源 | 路径 | 特点 |
|---|---|---|
| 精选测试集（13 个，已有 参考软件 导出） | `D:\Project\XRD\test_xrd\txt\*.txt` | 单相→7 相混合、含非晶、微量相；已有精准/宽松两套候选 CSV |
| IUCr CPD 国际标样 | `D:\Project\XRD\XRData\IUCr\` | 带 wt% 标定，定量基准；`Must do\*.txt` 为两列 ASCII |
| 用户真实样品集 | `D:\Project\XRD\XRData\csuHJW\` | 44+ 组，`.raw` 为主，部分配 `.txt/.mdi/.cif` |

---

## 4. 从 13 个扩到 20–30 个的缺口清单

**已有 13 个（test_xrd，**已入库** jingzhun + alloption 两套）**：
`1-1, 1-2, 2-1, 2-2, 3-1, 3-2, 4-1, 5-1, 5-2, 5-2b, 5-3, 7-1, 7-2`
→ 目标 20–30 个，**缺口 7–17 个**。

**建议优先补充（按覆盖度排序；duplicate 已剔除）**：

| 优先级 | 样品 | 源路径 | 覆盖目的 | 备注 |
|---|---|---|---|---|
| ★★★ | CPD-1a / 1b / 1d / 1e / 1f / 1g / 1h | `IUCr\Must do\CPD-1*.txt` | Al₂O₃/ZnO/CaF₂ 三不同比例混合 | 1c ≡ test_xrd 3-1，跳过避免重复 |
| ★★★ | CPD-4 | `IUCr\Must do\CPD-4.txt` | Al₂O₃ + 磁铁矿 + 锆石三相 | 新物相组合 |
| ★★☆ | 标准 Si | `csuHJW\data002` | 单相标样（指标化/定位校准） | 单晶相 |
| ★★☆ | 单相锐钛矿 | `csuHJW\data033` | 单相标样 | |
| ★★☆ | Y₂O₃ | `csuHJW\data038` / `IUCr\CPD-Y2O3.RAW` | 单相标样 | |
| ★★☆ | 残余奥氏体钢 | `csuHJW\data020` | 奥氏体+马氏体双相 | 复杂合金 |
| ★★☆ | ZnO+CaCO₃+SiO₂+Al₂O₃ | `csuHJW\data036` | 四相 | |
| ★☆☆ | 非晶 + SiO₂ | `csuHJW\data037` | 非晶含量 | 与 3-2 互补 |
| ★☆☆ | ZnO+CaCO₃ | `csuHJW\data041` | 两相（与 2-1 对照） | |
| ★☆☆ | NCM 811 | `csuHJW\data040` | ≡ test_xrd 1-2，不同仪器/批次 | 跨仪器稳健性 |

**已识别的重复（不要重复跑）**：
`CPD-2 ≡ 4-1`、`CPD-3 ≡ 3-2`、`Synthetic Bauxite ≡ 7-1`、`Granodiorite ≡ 7-2`、
`data001 ≡ 2-2`、`data40 ≡ 1-2`。

> 上述缺口清单只是**建议路径**；实际每个样品的 参考软件 候选 CSV 仍需人工按第 2 节
> 流程逐个导出。本目录随人工进度逐步充实，充实后 `tools/run_acceptance.py
> --baseline-dir tests/baseline/match` 即可自动读取。
