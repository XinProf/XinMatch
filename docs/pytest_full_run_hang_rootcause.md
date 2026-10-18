# 全量 pytest 单进程"挂起"根因分析与最小修复

## 结论速览

| 项 | 结果 |
|---|---|
| 全量单进程 pytest（排除 `tests/test_turn_on.py`） | **EXIT=0，100% 完成** |
| 所谓"figure_export 挂起" | **误观察** — 主线程从未在 matplotlib 内挂起 |
| 真实耗时黑洞 | `tests/refine/test_turn_on.py` 的 `scipy.optimize.least_squares`（数值雅可比，3500 点 Rietveld 图案）+ GSAS-II 子进程 + `tests/search/test_baseline_acceptance.py` 的 curve_fit |
| 最小修复 | `tests/report/conftest.py`：autouse fixture 强制 Agg 后端 + 清理残留 figure（防御性，不改运行时行为） |

## 复现命令与证据链

### 验收命令（基线）

```powershell
$env:QT_QPA_PLATFORM="offscreen"
& "D:\Project\XRD\python310\python.exe" -m pytest --ignore=tests/test_turn_on.py -p no:cacheprovider
```

### 堆栈取证方法

用 `faulthandler.dump_traceback_later(45, repeat=True)` 每 45 秒转储一次主线程堆栈到 `hang_stack.log`。

### 关键证据

1. **分块全绿（已知基线，未重复勘察）**：
   - `tests/refine` 单独：122 passed
   - `tests/report` 单独：41 passed + 1 skipped（2.63s）
   - 全量 -{refine,report}：947 passed + 1 xfailed

2. **最小复现（scipy least_squares + matplotlib Agg）**：`minimal_repro.py` 0.97s 完成，无挂起。

3. **定向实验（一个慢速 turn_on 测试 + figure_export）**：
   ```
   pytest tests/refine/test_turn_on.py::test_turn_on_strategy_completes_5_stages tests/report/test_figure_export.py
   ```
   **EXIT=0 通过**。figure_export 在 turn_on 之后正常运行。

4. **全量运行堆栈时间线**（faulthandler 转储）：
   - 51% 处：主线程在 `turn_on.py:176 least_squares`（trf/`_numdiff`）
   - 57% 处：主线程在 `tests/search/test_baseline_acceptance.py:219`（→ `tools/run_acceptance.py:796` → `curve_fit`）
   - **从未出现主线程在 `matplotlib`/`pyplot`/`savefig` 内的堆栈**

5. **最终结果**：全量运行 100% 完成，`EXIT=0`。

### 根因判定

"首个 matplotlib PNG 导出测试 CPU 持续占用 30+ 分钟不结束"是**误观察**：

- 观察者在全量运行中看到 CPU 持续占用，结合进度条停在 refine→report 交界附近，推断为 figure_export 挂起。
- 但 faulthandler 堆栈证据显示：主线程实际在 `scipy.optimize.least_squares`（turn_on 的 Rietveld 精修，数值雅可比 × 3500 点图案 × max_nfev=400）中密集计算。
- turn_on 测试跑完后，figure_export 正常通过（进度推进到 57%+，进入 search 目录）。
- 真正的耗时大头是：turn_on least_squares（每个 ~5-10 分钟，8 个测试）、GSAS-II 子进程（`subprocess.run timeout=1800`）、`test_baseline_acceptance` 的 curve_fit。

## 最小修复

### 改动文件

**新增 `tests/report/conftest.py`**（防御性 fixture）：

- autouse fixture `_matplotlib_agg_headless`：
  - 强制 `matplotlib.use("Agg")`（无头后端，不依赖 Qt/offscreen）
  - 每个测试前后清理 `plt.get_fignums()` 残留 figure
- 不改动 `test_figure_export.py` 任何断言逻辑
- 不改动 `xinmatch/core/report/figure_export.py`（该模块已在 import pyplot 前 `mpl.use("Agg")`）

### 理由

- 虽然证据表明 figure_export 并未挂起，但此 fixture 消除了"refine 测试可能泄漏后端状态/残留 figure"的潜在风险，是文件域内最小、防御性的修复。
- 不改运行时行为：`figure_export.py` 已在每个公开入口惰性调用 `mpl.use("Agg")`，此 fixture 只是在测试侧兜底。

## 验证结果

| 验证项 | 结果 |
|---|---|
| `pytest tests/report/` | 41 passed + 1 skipped（含新 conftest） |
| `ruff check tests/report/conftest.py` | All checks passed |
| 品牌词 grep（参考软件中性词约束） | 0 命中 |
| 全量单进程（排除 turn_on） | EXIT=0，100% 完成 |

### 全量运行用时说明

全量单进程运行受以下固有慢测试影响（非 figure_export）：
- `tests/refine/test_turn_on.py`：`least_squares` 数值雅可比，每测试 ~5-10 分钟
- `tests/quant/test_rietveld_quant.py` / `tests/refine/test_gsas2_project.py`：真实 GSAS-II 子进程（`timeout=1800s`）
- `tests/search/test_baseline_acceptance.py`：`run_acceptance` 管线 + curve_fit

这些测试属于算法固有耗时（数值雅可比 × 大图案），在并行任务 CPU 争用下会进一步放大。分块运行是推荐的规避方式。

## v1.7.x 更新：slow 标记已落实，默认运行不再需要手工分块

此前只有 2 个测试文件使用 `slow` 标记，`pytest` 默认会跑全部慢用例。现已：

* `tests/refine/test_turn_on.py`、`tests/search/test_baseline_acceptance.py` 加模块级
  `pytestmark = pytest.mark.slow`；
* `tests/refine/test_gsas2_project.py` 的两个真实精修用例加 `@pytest.mark.slow`；
* `pyproject.toml` 的 `addopts` 追加 `-m "not slow"`。

因此 `pytest` 现在是「快速可用」的默认入口，全量慢用例用 `pytest -m slow`（命令行
`-m` 覆盖 ini 配置）。下面的分块方案仍然适用于定位单个模块的失败。

## 分块运行方案

由于全量单进程受固有慢测试影响，推荐分块运行：

```powershell
# 快速单元测试（< 1 分钟）
pytest tests/cli tests/db tests/index tests/io tests/micro tests/model tests/peak tests/preprocess -p no:cacheprovider

# 精修模块
pytest tests/refine -p no:cacheprovider

# 报告/图表
pytest tests/report -p no:cacheprovider

# 量化（含 GSAS-II 子进程，慢）
pytest tests/quant -p no:cacheprovider

# 搜索/验收（慢，含 curve_fit 管线）
pytest tests/search -p no:cacheprovider
```

UI 测试需先设置 `$env:QT_QPA_PLATFORM="offscreen"`。
