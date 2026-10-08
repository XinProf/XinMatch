# XinMatch 项目转交记录

> **撰写时间**：2026-10-08
> **当前 HEAD**：`8f81947 docs(ROADMAP_v3): clarify refinement architecture`
> **状态**：核心计算内核基本完成（P1–P12），GUI 骨架已起（T13.0–T13.2），精修生产闭环已通（T10.6b/T10.8/T10.9），未提交工作树中有 Agent J/K/L 的产物待验收 commit。

---

## 1. 项目概况

### 1.1 一句话定位

**XinMatch** 是一个开源的粉末 X 射线衍射（XRPD）物相分析平台，对标商业软件 Match!，采用净室实现（clean-room）策略——只参考公开文档与已发表算法，不反编译、不复用专有代码。数据基础是 CC0 公共领域的 [COD](https://www.crystallography.net/cod/) 数据库。

### 1.2 功能边界

| 类别 | 功能 |
|---|---|
| **定性** | 物相鉴定（Search-Match）：峰关联 + FoM 排序 + 候选剪枝 |
| **定量** | RIR、内标法、DOC 非晶、Rietveld 定量（委托 GSAS-II） |
| **预处理** | 平滑、SNIP 背景、Kα₂ 剥离、零点校正 |
| **寻峰** | 导数法 + 峰形拟合（pseudo-Voigt） |
| **精修** | **不自研**，委托 GSAS-II；GUI 参考 MAUD 向导式 |
| **指标化** | Treor / Dicvol |
| **微结构** | Scherrer、Williamson-Hall、微观应变 |
| **报告** | HTML / Markdown / 文本 / PDF / PNG / SVG |
| **GUI** | PySide6 + pyqtgraph |
| **CLI** | 一键流水线 + Python API |

### 1.3 架构原则

1. **Kernel / GUI 解耦**：`xinmatch/core/` 纯计算（numpy + dataclass），无 GUI 依赖；`xinmatch/ui/` 是薄层。
2. **净室实现**：规格来自公开文档 + 已发表算法 + 黑箱文件格式观察。
3. **开放数据**：参考库基于 COD（CC0）。
4. **小步可验**：每个任务带 pytest 验收标准，AI agent 可独立构建/测试/调试。
5. **精修外包**：Le Bail / Rietveld / 残差 / 峰形 / 结构因子 / 策略化精修**全部委托 GSAS-II**，XinMatch 只做项目构造 + 参数暴露 + 结果解析 + GUI 交互。

---

## 2. 路线图概览（P0–P16）

详见 [ROADMAP_v3.md](../ROADMAP_v3.md)。摘要：

| Phase | 主题 | 完成度 |
|---|---|---|
| P0 | 知识基座 + 黄金基线 | 🟡 30%（T0.3/T0.4 是最大短板，需人工跑 Match!） |
| P1 | 核心数据模型 | ✅ 100% |
| P2 | I/O | ✅ 80%（Bruker `.raw` 待补） |
| P3 | 预处理 | ✅ 100% |
| P4 | 寻峰 | ✅ 100% |
| P5 | 参考数据库 | ✅ 100% |
| P6 | Search-Match | ✅ 100% |
| P7 | Restraints | ✅ 100% |
| P8 | 定量 | ✅ 75%（T8.3 Rietveld 待 GSAS-II 闭环） |
| P9 | 指标化 | ✅ 100% |
| P10 | 精修 | ✅ 生产闭环已通（T10.6b/T10.8/T10.9） |
| P11 | 微结构 | ✅ 100% |
| P12 | 报告 | ✅ 100% |
| P13 | GUI | 🟡 25%（骨架完成，表格/向导/主题待做） |
| P14 | CLI | 🟡 50%（批处理/串口待做） |
| P15 | 打包 | ⬜ 0% |
| P16 | 3D 可视化 | ⬜ 0% |

---

## 3. 任务拆分标准

### 3.1 颗粒度原则

- **单任务可独立验收**：每个任务 ID（如 T6.8）有明确的 pytest 通过条件或数值阈值。
- **单 Agent 工作量**：1 个任务 ≈ 1 个 Agent 一次会话可完成（数小时），含代码 + 测试 + ruff + 自检。
- **无冲突并行**：拆分时按目录/模块隔离，避免多 Agent 同时改同一文件。
- **依赖串行**：如 T8.3 必须等 T10.6b/T10.8/T10.9（GSAS-II 闭环）。

### 3.2 验收边界（每个任务必须满足）

| 验收维度 | 要求 |
|---|---|
| **代码** | 实现路径与 ROADMAP 指定一致；遵循已有 dataclass 模型；`from __future__ import annotations` |
| **测试** | pytest 全过；数值任务带合成回归测试；外部依赖（GSAS-II/FullProf）用 `pytest.mark.skipif` 守卫 |
| **Lint** | `ruff check` 全绿 |
| **文档** | STATUS.md 对应行从 ⬜ 改为 ✅，并附实现要点 |
| **Commit** | 单任务单 commit，消息格式 `feat: implement Txx.x ...` |

### 3.3 并行 Agent 拆分模板

典型一轮并行（3 个 Agent）：

```
Agent X — 模块 A（如 search/）   ← 改 core/search/*.py + tests/search/
Agent Y — 模块 B（如 refine/）   ← 改 core/refine/*.py + tests/refine/
Agent Z — 模块 C（如 quant/）     ← 改 core/quant/*.py + tests/quant/
```

**关键约束**：
- 三个 Agent 的工作目录不重叠（已发生的成功案例：search+refine+quant、search+refine+micro）
- 每个 Agent 在自己的子目录跑 `pytest tests/<sub>/` 全过后再 commit
- **全量 pytest 由主 Agent 统一跑**，避免并行 Agent 同时跑全量导致超时

---

## 4. 已完成进展（按 commit 时间）

### 4.1 Git 历史

```
ca08110  项目骨架初始化
68c1d7a  T1 核心数据模型
1f6be84  T2 I/O + T3/T4 预处理寻峰 + T5 数据库（3 agent 并行）
b20f60d  更新 STATUS.md
e3216a1  T6 检索 + T7 限制 + T8.1 RIR + T11.1 Scherrer（3 agent）
266e83b  T6.3-7 主循环 + T9 指标化 + T12 报告（3 agent）
c444cec  T6.0/T6.6 + T10 精修内核 + T14 CLI/API（3 agent）
1b7d54b  T6.8 残差FoM + T6.9 L3验收 + T6.10 权重微调（Agent G）
5db0352  T10.5 残差 + T10.6b GSAS-II适配 + T10.7 策略化（Agent H）
eb977d8  T8.2 内标法 + T8.4 DOC + T11.2 W-H微观应变（Agent I）
49c327c  docs: 路线图澄清 + 样品清单
8f81947  docs(ROADMAP_v3): 精修架构决策——委托 GSAS-II
```

### 4.2 已完成的核心模块

| 模块 | 文件 | 验收要点 |
|---|---|---|
| 数据模型 | `core/model/*.py` | Pattern/Peak/Entry/Phase/Restraints/Project 全 dataclass |
| I/O | `core/io/*.py` | 6 类格式 + 自动检测 + 统一 `load_pattern()` |
| 预处理 | `core/preprocess/*.py` | 平滑+SNIP+Rachinger+零点+自动流水线 |
| 寻峰 | `core/peak/*.py` | 导数法+pseudo-Voigt 拟合 |
| 数据库 | `core/db/*.py` | SQLite + 倒排索引 + COD→SQLite 构建器 |
| Search-Match | `core/search/*.py` | 贪心+匈牙利关联、5 分量 FoM、PFSM、L3 验收 11/13 |
| Restraints | `core/search/restraints_apply.py` | 三态元素过滤（红/黄/绿） |
| RIR 定量 | `core/quant/rir.py` | 绝热法 + 参考比 |
| 内标法 | `core/quant/internal_standard.py` | CPD-1c CaF₂ 误差 < 0.12 wt% |
| DOC 非晶 | `core/quant/doc.py` | SNIP+形态学开运算+SavGol；3-2 玻璃误差 4.81 wt% |
| 指标化 | `core/index/*.py` | Treor + Dicvol + Smith-Snyder/de Wolff FOM |
| Scherrer/W-H | `core/micro/crystallite_size.py`, `microstrain.py` | 合成 D/ε 回归 < 10% 误差 |
| 报告 | `core/report/*.py` | HTML/MD/TXT/PDF/PNG/SVG |
| 精修 GSAS-II 闭环 | `core/refine/gsas2_adapter.py` + `gsas2_project.py` + `gsas2_parse.py` | Protocol + Local fallback + .gss+.lst+.prf+精修CIF 解析；CPD-1c 三相机实测 Rwp≈59% |
| CLI | `cli/*.py` | 一键流水线 + Python API |
| GUI 骨架 | `ui/app.py`, `main_window.py`, `pattern_view.py` | QApplication 工厂 + 主窗口 + pyqtgraph 视图 |

### 4.3 测试与质量

- **pytest**：661+ passed, 1 skipped, 1 xfailed（截至最新已 commit 状态）
- **ruff**：全绿
- **慢测试隔离**：5 阶段 Rietveld turn-on 测试每轮 7–21 分钟，需独立跑（`pytest tests/refine/test_turn_on.py`）

### 4.4 未提交工作树（待 commit）

> ⚠️ Agent J/K/L 在最近一轮并行中完成了代码但未 commit，工作树有未暂存改动：

| Agent | 任务 | 文件 | 测试结果 |
|---|---|---|---|
| J | T10.8 GSAS-II 项目构造器 | `xinmatch/core/refine/gsas2_project.py` (20KB) + fixtures | 11 passed |
| K | T10.9 GSAS-II 结果解析 | `xinmatch/core/refine/gsas2_parse.py` (20KB) + fixtures | 17 passed |
| L | T13.0/T13.1/T13.2 GUI 骨架 | `xinmatch/ui/app.py`, `main_window.py`, `pattern_view.py` | 13 passed |
| 额外 | T0.8 P 值反推框架 | `tools/build_baseline.py` + `tests/test_build_baseline.py` | 未验证 |

**已知临时文件需清理**：`docs/project_overview.html`、`pytest_result.txt`

---

## 5. 后续计划（按优先级）

### 5.1 🔴 第一优先：固化 Agent J/K/L 成果

1. 跑全量 pytest 确认无回归（用户上次跑时报告"python.exe ?? 报错"，子模块测试均通过，需排查全量报错来源）
2. 删除临时文件 `docs/project_overview.html`、`pytest_result.txt`
3. commit Agent J/K/L 的工作（建议拆 3 个 commit：J/K 各一个，L 一个）
4. 更新 STATUS.md 中 T10.8/T10.9/T13.0/T13.1/T13.2 状态（已改 ✅ 但未 commit）

### 5.2 🔴 第二优先：升级 L3 黄金基线验收

用户已用 Match! 手动跑完 13 个样品（`D:\Project\XRD\test_xrd\txt\`），导出两份候选 CSV：

| 基线 | 路径 | 用途 |
|---|---|---|
| **精准** | `D:\Project\XRD\test_xrd\match-candidate list-jingzhun\` | 主基线：Top-N 命中率比较 |
| **宽松** | `D:\Project\XRD\test_xrd\match-candidate list-alloption\` | 副基线：复现 Match! 干扰相剔除行为 |

CSV 字段含 `Entry;Formula sum;Name;P(peakpos.);P(I/I0);P(#peaks);FoM`，与 XinMatch FoM 模块对应。

**升级路径**（小改动）：
1. 加 `MatchBaselineLoader`：解析 CSV → `(entry_id, fom)` 排序列表
2. 在 [tools/run_acceptance.py](../tools/run_acceptance.py) 加 `match_top1_agreement` / `match_top5_overlap` 指标
3. 阈值：Top-1 ≥ 80%、Top-5 交集 ≥ 60%（对标 ExtMatch L3）

**注意**：Match! 用 SMPF（Search-Match using Profile Fitting）模式，不做传统寻峰，`P(#peaks)` 全为 0；比较以 `FoM` 总分为主。

### 5.3 🟡 第三优先：完成 T0.3/T0.4 标准样品集

T0.3/T0.4 是 L3 兼容性验收的唯一阻塞项，**只能人工**：
- 在 Match! 中跑 20–30 个标准样品，导出候选 CSV 到 `tests/baseline/match/`
- 当前只有 13 个（在 `test_xrd/txt/`），数量略少但已可启动黄金基线

### 5.4 🟡 第四优先：T13 GUI 续做

P13 完成度 25%，剩余：

| 任务 | 内容 |
|---|---|
| T13.3 | 峰 / 候选 / 匹配列表表格 |
| T13.4 | 周期表元素选择器（三态：红/黄/绿） |
| T13.5 | 对话框（导入 / 实验 / 选项） |
| T13.6 | 快捷键映射（对标 Match!） |
| T13.7 | 主题（浅色/深色） |
| **T13.8** | **精修向导 GUI**（MAUD 风格，委托 GSAS-II） |

### 5.5 🟢 第五优先：杂项

- T2.4 Bruker `.raw` 完整支持
- T8.3 Rietveld 定量（依赖 GSAS-II 闭环已完成，可启动）
- T14.3 批处理脚本（JSON/YAML 配置）
- T14.4 串口仪器控制
- Phase 15 打包（PyInstaller / Nuitka）
- Phase 16 3D 结构可视化（QWebEngineView + 3Dmol.js）

---

## 6. 经验教训与已踩的坑

### 6.1 架构决策

#### ✅ 正确决策

1. **委托 GSAS-II 而非自研精修**：Le Bail/Rietveld 是几十年的算法积累，自研只会做"差强人意"的版本。GSAS-II 是 Python 编写，可通过 `GSASIIscriptable` API 嵌入式集成（不像 FullProf 需要外部进程）。这与 Match! 集成 FullProf 的模式一致。
2. **Kernel/GUI 解耦**：core 层完全无 GUI 依赖，单元测试可在 offscreen 模式跑，大幅降低 CI 复杂度。
3. **FoM 权重用 NNLS+网格反推**：从 Match! 导出的 CSV 反推权重，R²=0.9913 → 0.9971，证明已发表权重在搜索范围内最优。
4. **三态元素过滤（红/黄/绿）**：把 Restraints 从布尔过滤升级为加权评分，更符合 Match! 实际行为。

#### ⚠️ 教训

1. **Agent J/K/L 没 commit 就退出**：尽管代码完整且子模块测试全过，但工作树留下一堆未提交改动，给接手者造成混乱。**改进**：每个 Agent 完成后必须 commit，或主 Agent 在汇总时统一 commit。
2. **慢测试与快测试混合跑**：5 阶段 Rietveld turn-on 每轮 7–21 分钟，混在全量 pytest 会导致 183s 变成 20+ 分钟。**改进**：慢测试用 `pytest.mark.slow` 标记，CI 默认跳过。
3. **L3 验收基线缺失导致代理验收**：T6.9 本应用 Match! 黄金基线，但因 T0.3/T0.4 未做，只能用"已知物相命中率"做代理（11/13 通过，2 失败因 COD 缺 LiFePO4/NCM811）。**改进**：现在用户已手动跑完 Match! 基线，应立即升级。
4. **COD 数据缺失**：LiFePO4/NCM811 在 COD-Inorg 2025.12.01 中没有完美匹配项，导致 1-1 和 5-x 系列样品失败。**改进**：可考虑补充 AMCSD 或用户自建数据库。

### 6.2 工程实践

#### 并行 Agent 协作

- ✅ **目录隔离**：按 `core/<sub>/` 拆分，三个 Agent 改不同子目录，无冲突（成功案例：search+refine+quant、search+refine+micro）
- ✅ **统一 commit 节奏**：每个 Agent 完成后跑子模块 pytest，全过再 commit；主 Agent 统一跑全量
- ⚠️ **避免同时跑全量 pytest**：三个 Agent 同时跑全量会导致超时与资源争抢
- ⚠️ **Agent 必须 commit**：J/K/L 的代码虽好，但没 commit 等于"未交付"

#### 测试策略

- ✅ **合成回归测试**：每个数值算法用合成数据（已知 D/ε、已知 wt%）做回归，避免依赖外部 GSAS-II/Match!
- ✅ **skipif 守卫外部依赖**：`@pytest.mark.skipif(not GSAS2_AVAILABLE)` 让 CI 在无 GSAS-II 环境下仍能跑
- ✅ **fixture 真实化**：GSAS-II 解析模块用真实捕获的 `.lst`/`.prf`/`.gpx` 做 fixture，比合成更可信
- ⚠️ **xfail 标记已知限制**：内标法对择优取向敏感（CPD-1c ZnO），用 `xfail` 标记而非"硬通过"

#### 数据库与基线

- ✅ **样品索引文档化**：`tests/fixtures/SAMPLE_INDEX.md` 列出 test_xrd/XRData 三大样品源
- ✅ **三大样品源**：
  - `D:\Project\XRD\test_xrd\` — 13 样品，含物相结果 + wt% + 元素限定
  - `D:\Project\XRD\XRData\IUCr\` — IUCr CPD 国际标样（全 wt%）
  - `D:\Project\XRD\XRData\csuHJW\` — 44+ 组真实样品
- ⚠️ **Match! SMPF 模式不寻峰**：`P(#peaks)=0.0000`，比较以 `FoM` 总分为主

### 6.3 路线图演化

#### 关键架构决策（2026-10-08）

**原计划**：T10.1–T10.7 自研精修全套（Le Bail/Rietveld/残差/峰形/结构因子/策略化精修）

**调整后**：
- T10.1–T10.5、T10.7 标注为 **"reference only"**（仅交叉验证，不进生产）
- T10.6 FullProf → **❌ 不做**
- **T10.6b（GSAS-II 适配层）** → 生产精修唯一入口
- 新增 **T10.8**（GSAS-II 项目构造器）、**T10.9**（GSAS-II 结果解析）、**T13.8**（MAUD 风格精修向导 GUI）

**理由**：
- 对标 Match! 集成 FullProf 的模式，XinMatch 选择集成 GSAS-II
- GSAS-II 是 Python 编写，可通过 `GSASIIscriptable` API 嵌入式集成
- GUI 参考 MAUD 的向导式交互（比 GSAS-II 原生 GUI 直观）
- XinMatch 只做交互体验，不做任何精修计算

### 6.4 已知简化点（来自 project_memory）

1. **FoM P 值精确定义**：待 T0.8 用 baseline CSV 反推（已建框架 `tools/build_baseline.py`）
2. **RIR 结构计算**（CIF→I/Ic）未实现，当前只做主峰强度比
3. **Scherrer 仪器展宽校正**：T11.2 已实现 Gaussian quadrature（β_sample²=β_obs²−β_inst²），用 LaB6 标样插值
4. **FoM 权重多选项场景**：当前是默认选项下的权重（R²=0.9971），多选项场景待扩

---

## 7. 参考软件路径（本机已安装）

| 软件 | 路径 | 用途 |
|---|---|---|
| **GSAS-II** | `C:\gsas2main\GSAS-II` | 生产精修集成（`GSASII\GSASIIscriptable.py` 可用） |
| **MAUD** | `C:\MAUD3` / `C:\MAUD2` | GUI 交互参考（向导式） |
| **FullProf** | `C:\FullProf_Suite` | 已装但不选用 |
| **Match!** | `C:\Program Files\Match4` | 工作流参考 + 黄金基线来源 |
| **COD 数据库** | `C:\Program Files\Match4\RefDB_COD` | COD-Inorg 2025.12.01 |

---

## 8. 常用命令速查

### 8.1 测试

```powershell
# 全量测试（排除慢测试）
python -m pytest --ignore=tests/refine/test_turn_on.py --tb=short

# 单子模块
python -m pytest tests/search/ -v
python -m pytest tests/refine/ -v --ignore=tests/refine/test_turn_on.py
python -m pytest tests/quant/ tests/micro/ -v
python -m pytest tests/ui/ -v

# 慢测试单独跑
python -m pytest tests/refine/test_turn_on.py -v --tb=short

# L3 验收
python tools/run_acceptance.py
```

### 8.2 Lint

```powershell
ruff check .
```

### 8.3 Git（git 不在 PATH，需手动加）

```powershell
$env:Path = "C:\Program Files\Git\bin;$env:Path"
git -C "d:\Project\XRD\XinMatch" status
git -C "d:\Project\XRD\XinMatch" log --oneline -10
git -C "d:\Project\XRD\XinMatch" add <files>
git -C "d:\Project\XRD\XinMatch" commit -m "feat: ..."
```

### 8.4 GUI 启动

```powershell
python -m xinmatch.ui.app
# 或
python -c "from xinmatch.ui.app import main; main()"
```

### 8.5 CLI 流水线

```powershell
python -m xinmatch.cli <subcommand>
```

---

## 9. 关键文件索引

| 类别 | 路径 |
|---|---|
| README | [README.md](../README.md) |
| 路线图 | [ROADMAP_v3.md](../ROADMAP_v3.md) |
| 状态表 | [docs/STATUS.md](STATUS.md) |
| FoM 模型 | [FOM_MODEL.md](../FOM_MODEL.md) |
| 样品索引 | [tests/fixtures/SAMPLE_INDEX.md](../tests/fixtures/SAMPLE_INDEX.md) |
| 项目记忆（项目内镜像） | [.trae/projects/XinMatch/project_memory.md](../.trae/projects/XinMatch/project_memory.md) |
| L3 验收脚本 | [tools/run_acceptance.py](../tools/run_acceptance.py) |
| 权重微调脚本 | [tools/tune_weights.py](../tools/tune_weights.py) |
| P 值反推框架 | [tools/build_baseline.py](../tools/build_baseline.py) |
| Match! 黄金基线（精准） | `D:\Project\XRD\test_xrd\match-candidate list-jingzhun\` |
| Match! 黄金基线（宽松） | `D:\Project\XRD\test_xrd\match-candidate list-alloption\` |

---

## 10. 接手者行动清单

按建议顺序：

1. **立即**：跑全量 pytest 排查"python.exe ?? 报错"来源；清理临时文件；commit Agent J/K/L 的工作（拆 3 个 commit）
2. **短期**：升级 T6.9 L3 验收为黄金基线（用 Match! CSV 比较 Top-N 命中率）
3. **中期**：续做 T13.3–T13.8 GUI；T8.3 Rietveld 定量（GSAS-II 闭环已通）
4. **长期**：T0.3/T0.4 标准样品集扩充到 20–30 个；T14.3/T14.4 批处理+串口；Phase 15 打包；Phase 16 3D 可视化

**重要约束**：
- 不要自研精修算法——所有 Le Bail/Rietveld/残差/峰形计算委托 GSAS-II
- 不要复制 Match! 视觉资源——图标/文档一律原创或用开源图标（KDE Breeze / Lucide）
- 不要删除已有 reference-only 精修代码——它们用于交叉验证 GSAS-II 输出是否合理
- 不要跳过 ruff 检查——CI 要求全绿

---

**祝项目顺利推进。**
