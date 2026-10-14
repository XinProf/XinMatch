# T6.0 验收文档 — 检索预筛策略修复 + 检索性能优化

日期：2026-10-14
范围：`search_by_d` / `search_match` 预筛链路（候选召回 → 截断 → FoM）
背景：TASK 转交 T6.0「strongest_peak_only Hanawalt 只保留最强参考峰落在实验 Top-20 强峰窗口」导致 2-1 CaCO₃ / 3-1 Al₂O₃ / 4-1 Al₂O₃ 次相卡 0 张进候选集 + `recall_max_candidates` 在 Hanawalt 模式被忽略 + 71k 库单次检索 ~9s 遗留问题（实测 15–27s）。

## 1. 确认项清单

### 1.1 缺陷根因（探针定案，`.scratch/t60_*.py` 可复现）

| 样本 | 真相相 | 旧默认（K=1/top_k=20/cap=800） | 根因 |
|---|---|---|---|
| 2-1 | CaCO₃（50% 主相之一） | 0 张进候选（K=3 全候选 rank=18,663） | ① 最强峰规则：CaCO₃ 最强线 d=2.5961 在实验谱中存在但不在**实验 Top-20 强峰窗口**（recall_top_k=20 截断中等强度峰）；② 卡峰数少时仅 1 峰落入窗口，match=1 |
| 3-1 | Al₂O₃（5.04% 微量相） | 0 张进候选 | ① 最强峰规则：Al₂O₃ 前 3 强峰均不在实验 Top-20 窗口；K≥5 才召回（96-100-0017 等，match=5–6，候选 rank 14/15/52） |
| 4-1 | Al₂O₃（21.27% 次相） | 0 张进候选 | ① 同上；K=3 时候选 rank 6/7/10 召回成功，但 FoM 层 Top-20 排名 #16–25（FoM 评分层，非预筛缺陷） |

补充缺陷：
- `recall_max_candidates` 在 Hanawalt 模式被忽略（代码路径未传入）→ 候选无上限，FoM 阶段失控（旧行为）。
- `strongest_k>1` 时相关子查询无复合索引支撑，K=3 单窗口查询 4.36s。
- 新增缺陷（本轮发现并修复）：K > 卡峰数时卡被整体排除（4 峰卡 × K=5 → 永不召回）；模块级 Top-K 缓存跨 in-memory DB 污染（pytest 多连接）。

### 1.2 修复内容（代码已写入，`git diff` 可核）

**`xinmatch/core/db/query_peaks.py`**（+128 行）
1. `search_by_d` 新增 `strongest_k: int = 0`（0=禁用；1=仅最强峰等效旧 strongest_peak_only；K=Top-K 任一命中）。
2. **Top-K 阈值缓存**（`_load_top_k_intensities`）：流式读取 `(entry_id, intensity DESC)`（走 `idx_peaks_entry_intensity`），每卡保 Top-20 强度；窗口查询改为 `GROUP BY entry_id` + `MAX(intensity)` **无相关子查询**，Python 侧与阈值比较。等价性验证：单窗口旧子查询 437 卡 vs 新 GROUP BY 437 卡，**一致=True**。
3. 缓存按**数据库文件路径**键控；in-memory 连接不缓存（避免 pytest 多连接污染）。
4. K>卡峰数时退化为「任一峰命中」（`k_eff = min(strongest_k, len(top))`）。
5. 幂等创建 `idx_peaks_entry_intensity`（try/except 保护只读挂载库；不显式 commit 避免破坏外层事务）。

**`xinmatch/core/search/search_match.py`**（+64 行）
1. 默认参数调整：`recall_top_k 20→40`、`recall_max_candidates 800→3000`、`recall_strongest_k 1→5`（T6.0 探针验证组合）。
2. `max_candidates=recall_max_candidates` 在 **Hanawalt 模式也生效**（此前被忽略）。
3. `strongest_k=recall_strongest_k if recall_strongest_peak else 0`。
4. docstring 全面更新（T6.0 语义 + 实测数据）。

**索引**（一次性迁移，`.scratch/t60_idx_build.py`，已写入用户真实 DB `data/cod_inorganics.db`）：
- `CREATE INDEX IF NOT EXISTS idx_peaks_entry_intensity ON peaks(entry_id, intensity DESC)`，3.4s 建成，幂等。
- 单窗口查询：4.36s → 2.06s（建索引后）→ 0.18s（GROUP BY 无子查询 + 缓存）。

### 1.3 效果验证

**性能（新默认 K=5/top_k=40/cap=3000，71k 库）**

| 样本 | 旧基线（K=1/top_k=20/cap=800） | 新默认 | 提升 |
|---|---|---|---|
| 2-1 | 21–23s | 10.9–12.8s | ≈45% |
| 3-1 | 15–19s | 8.5–9.3s | ≈48% |
| 4-1 | 19–24s | 9.1–9.6s | ≈55% |

**召回（真相卡进候选）**

| 样本 | 旧默认 | 新默认 |
|---|---|---|
| 2-1 CaCO₃（96-433-6389） | 0 张 | FoM 全排名 **#73**（match 由 1→2） |
| 3-1 Al₂O₃（96-100-0017/0032/0059/0914） | 0 张 | 候选 rank **#14/15/52/59**（match 5–6） |
| 4-1 Al₂O₃ | 0 张 | FoM Top-20 **#16/17/19/20**（此前 Top-20 无） |

**cap 护栏**：cap 800→3000 对 3 样本总耗时影响 ≤1s（FoM 3000 候选仅 0.8s，fetch 0.7s）——放宽 cap 的成本可忽略，收益是次相/微量相不被 match-count 截断。

**回归**

| 项 | 结果 |
|---|---|
| 合成谱验收（`tools/run_acceptance --synthetic`） | **13/13 PASS（100%）**，无退化 |
| 真实谱 Top-10 命中（`--cod-db data/cod_inorganics.db`） | **4/13**，与历史基准完全一致（无回归、无改善；FoM 排名层为本任务范围外已知长期项） |
| 相关单测（query_peaks/index_build/search_match/fom_criteria/cod_curated_search/synthetic_acceptance/smpf） | **142 passed / 0 failed** |
| ruff（query_peaks.py + search_match.py） | All checks passed |
| 全量核心回归（`--ignore=tests/db/test_pdf2_source_config.py --ignore=tests/ui`） | **1033 tests / 0 failures / 0 errors / 46 skipped**（84.5min，junit `.scratch/t60_core.xml`；历史基准 1026/0/0/46） |
| UI 冒烟（python310 + offscreen：test_app / test_search_mode） | 10 passed |

## 2. 为什么这么费时间（与前次验收同类耗时说明）

T6.0 的耗时集中在三类：

1. **真实数据探针算力时间**（大头）：每个候选组合（K=1/3/5/10/20 × top_k=20/40 × cap=800/3000/5000）都要在 71k 条目 / 626 万峰的 COD 库上跑真实 13 组谱的全链路检索，单次 9–24s；本轮累计跑探针 10+ 次 ≈ 15–20 分钟纯算力。
2. **回归验证**：相关单测 142 项 + 合成谱验收 13 组 + 真实谱验收 13 组（各 ~2–4 分钟）；全量核心回归 1026 项 ≈ 93 分钟（历史基准，本轮同样跑批）。
3. **调试成本**：K>卡峰数排除 bug、跨 DB 缓存污染两个缺陷各需「探针复现 → 定位 → 修复 → 重跑单测」一轮，每轮 5–10 分钟。

**结论**：耗时主要是「在真实规模数据上逐参数验证 + 全量回归」的固有算力成本，非流程冗余；每次验收的确认项都逐一实测、有可复现探针与 junit 证据。

## 3. 遗留与范围外

- **FoM 排名层**：次相/微量相卡即使召回，FoM 评分仍被主相密集卡压制（2-1 CaCO₃ #73、3-1 Al₂O₃ Top-500 外、4-1 Al₂O₃ #16–20）。权重扫描（此前任务）已证不可无脑调节；属长期已知面（HANDOVER 微量相检测难点），不在 T6.0 范围。
- **微量相检测（3-1 Al₂O₃ 5%、CaF₂ 1.36%）**：召回层已解决（进候选），FoM Top-10 展示需后续 FoM/展示策略任务处理。
- **真实谱 Top-10 命中率 4/13**：与 v1.5.0 基线一致，非本任务回归；提升需 FoM 层任务（T6.x 后续）。

## 4. 提交信息建议

```
T6.0 检索预筛策略修复 + 性能优化

- search_by_d: strongest_k 参数（Top-K Hanawalt 任一命中）；
  Top-K 阈值缓存（消除相关子查询，窗口查询 GROUP BY + MAX）；
  幂等创建 (entry_id, intensity) 复合索引；K>卡峰数退化任一峰命中
- search_match: 默认 recall_top_k 40 / recall_strongest_k 5 /
  recall_max_candidates 3000；max_candidates 在 Hanawalt 模式生效
- 效果：2-1 CaCO3/3-1 Al2O3/4-1 Al2O3 真相卡 0→进候选（候选 rank 14-59、
  FoM #16-20/#73）；单样本检索 15-27s → 8.5-12.8s（≈50%）
- 回归：合成谱 13/13、真实谱 4/13（与基线一致）、相关单测 142 通过
```
