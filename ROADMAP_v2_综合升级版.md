# XinMatch 实施路线图 v2.0（综合升级版）

> **开放版 Match! —— Powder XRD 物相分析平台**
> **方法论**：净室设计（Clean Room Design）—— 规格来自官方文档 + 黑盒观察 + 公开算法，代码从零实现
> **技术栈**：Python 3.11 + PySide6 (Qt6) + NumPy/SciPy + pyqtgraph + SQLite + gemmi
> **兼容性目标**：L1 文件格式 100% / L2 数据库对齐 / L3 算法 Top-10 命中率 ≥ 80% / L4 UI 工作流一致

---

## 📋 本版新增与升级要点

基于已有项目资产（169篇官方文档、功能地图、技术栈勘察报告）的补充：

| 升级项 | v1 旧版 | v2 升级版 | 来源 |
|--------|---------|-----------|------|
| **方法论** | 逆向工程 | 净室设计（合法合规） | 技术栈分析报告 §1 |
| **Phase 0** | 无 | 知识基座 + 黄金基线 | ROADMAP Phase 0 |
| **兼容性定义** | 模糊 | L1-L4 四层清晰定义 | 技术栈分析报告 §5 |
| **技术栈** | Python + Web (Electron) | Python + PySide6 (原生Qt) | 技术栈分析报告 §4 |
| **阶段数** | 7个阶段 | 15个细粒度阶段 | ROADMAP |
| **文件格式** | 7种 | **33种**（22厂商 + 6自由 + 结构） | FUNCTION_MAP + 格式文档 |
| **核心算法** | 基础FoM | FoM 6项判据 + PFSM 全谱匹配 | searchmatch_fom.md / PFSM_details.md |
| **限制条件** | 简单过滤 | 9类 Restraints + 三态语义（红/黄/绿） | restraints*.md（9篇） |
| **指标化** | 无 | Treor + Dicvol 两种算法 | indexing*.md（4篇） |
| **精修** | FullProf集成 | Le Bail + 自研Rietveld + FullProf适配 | LeBail.md / Rietveld*.md |
| **微结构** | 无 | Scherrer晶粒尺寸 + Williamson-Hall + DOC | crystallite_size.md / doc.md |
| **定量方法** | I/Ic | RIR法 + 内标法 + Rietveld定量 | quant_analysis_*.md（3篇） |
| **验收标准** | 主观描述 | 标准样品集 + Match!基线对比 | ROADMAP T0.3/T0.4 |
| **架构原则** | 前后端分离 | 内核与GUI完全解耦 | 技术栈分析报告 §4.3 |
| **AI Agent协作** | 粗粒度 | 50+独立可验证子任务 | ROADMAP 全部T#任务 |

---

## 🎯 四层兼容性目标（L1 → L4）

> 不追求 100% 逐位兼容，按层设定可达目标

| 层级 | 目标 | 可行性 | 验收指标 |
|------|------|--------|---------|
| **L1 文件格式兼容** | 能读 Match! 支持的全部格式，能写 Match! 可读文件 | ⭐⭐⭐⭐⭐ | 33 种格式双向 round-trip 测试通过 |
| **L2 参考数据库兼容** | 覆盖 COD（CC0）；ICDD PDF 设计为「用户自带授权数据」插件 | ⭐⭐⭐⭐ | COD 条目数、28个检索字段对齐 |
| **L3 算法结果兼容** | FoM 数值无法一致（权重未公开），但**排序质量**必须可比 | ⭐⭐⭐ | 标准样品集上 **Top-10 命中率 ≥ Match! 的 80%** |
| **L4 UI/工作流兼容** | 术语、菜单结构、快捷键、操作路径一致 | ⭐⭐⭐⭐ | 用户可按 Match! 手册操作 XinMatch |

> **L3 关键判断**：FoM 内部权重未公开且用户不可调，因此验收标准是**排序质量（Top-N 命中率）**，而非数值相等。这需要在 Phase 0 就建立「标准样品集 + Match! 基线结果」作为黄金标准。

---

## 🏗️ 技术栈与架构

### 技术选型

| 层 | 选型 | 理由 |
|----|------|------|
| **语言** | Python 3.11+ | 科学计算生态最强；GSAS-II 同栈；C 扩展可后补 |
| **GUI** | **PySide6 (Qt 6, LGPL)** | 与 Match! 同源 Qt → 外观/交互/快捷键天然贴近；LGPL 可商用 |
| **图谱渲染** | **pyqtgraph** | XRD 谱可达数万点，需 OpenGL 级缩放/拖拽；matplotlib 交互不够 |
| **3D 可视化** | PyVista / mayavi（可选） | 晶体结构 3D 显示 |
| **数值计算** | NumPy + SciPy | `scipy.optimize.least_squares` 精修；`scipy.signal` 平滑/寻峰 |
| **CIF 解析** | **gemmi** (MIT) | 晶体学标准库，高性能，支持 mmCIF/PDBx |
| **拟合内核** | lmfit（可选） | 参数约束语法友好，适合精修参数管理 |
| **数据库** | SQLite + SQLAlchemy | 单文件易分发；Profex 的 cod.db3 即为 SQLite |
| **计算加速** | Numba / Cython（二期） | FoM 遍历数十万条 entry，纯 Python 会慢 |
| **测试** | pytest + hypothesis | 算法需数值回归测试 |
| **打包** | PyInstaller / Nuitka | 目标同样是 Windows x64 单机 |

### 架构分层（关键：内核与 GUI 完全解耦）

```
XinMatch/
├── core/                    # 纯计算内核 · 零 GUI 依赖 · 可 CLI 调用 · 可单测
│   ├── model/               # 数据模型：Pattern / Peak / Phase / Entry / Restraints / Project
│   ├── io/                  # 33 种衍射格式 + CIF + MTU + 项目文件
│   ├── preprocess/          # 平滑 背景 Kα2剥离 零点 位移 Trim 分辨率提升
│   ├── peak/                # 寻峰 Profile Fitting 峰编辑
│   ├── db/                  # 参考数据库 SQLite 构建 + 倒排索引 + 检索
│   ├── search/              # FoM Search-Match PFSM Restraints
│   ├── index/               # Treor / Dicvol 指标化
│   ├── refine/              # Le Bail / Rietveld（+ FullProf 适配层）
│   ├── quant/               # RIR / 内标 / Rietveld 定量
│   ├── micro/               # Scherrer 晶粒尺寸 / 微观应变 / 结晶度 DOC
│   └── report/              # 报告数据模型 + 渲染
├── ui/                      # PySide6 GUI（只做展示与事件，不含算法）
├── cli/                     # 批处理 / 脚本接口（对标 Batch Scripting）
├── tests/                   # fixtures + 数值回归基线 + Match! 黄金标准
└── docs/                    # 规格文档库（169篇官方帮助 + 术语表 + 功能地图）
```

**为什么要解耦**：让每个 AI agent 能在无 GUI 环境下独立开发+验证一个 `core/` 模块（输入数组 → 输出数组 → pytest 断言）。GUI 最后统一接入。这是「小步骤可验证」能成立的前提。

---

## 📅 15 阶段详细实施计划

---

### Phase 0 · 知识基座与黄金基线

> **不做完 Phase 0 就不要开工写代码**，否则后面无法验证。
> 参考资产：`docs/match4_help/*.md`（169篇）、`docs/FUNCTION_MAP.md`、`docs/INDEX_KEYWORDS.txt`

| ID | 任务 | 输出 | 验收标准 | 优先级 |
|----|------|------|---------|--------|
| **T0.1** | 官方文档库提取（✓已完成） | `docs/match4_help/*.md`（169篇）、`FUNCTION_MAP.md` | 627 KB，主题完整 | ✅ 完成 |
| **T0.2** | 最新版 vs 4.2.329 版本差异分析 | `docs/version_diff_4.2.329_vs_latest.md` | 新增/变更主题清单完整，含 `whats_new_*` | 🔴 高 |
| **T0.3** | 建立**标准样品集**（20-30个已知组成的实测XRD数据） | `tests/fixtures/patterns/` + `tests/fixtures/ground_truth.json` | ≥20个样品，覆盖：单相、两相、三相、含非晶、含微量相(<5%)、重叠峰严重 | 🔴 最高 |
| **T0.4** | 用 Match! 跑标准样品集，记录**黄金基线** | `tests/baseline/match4_baseline.json` | 每个样品：候选列表 Top-20 FoM、选中相、定量结果 | 🔴 最高 |
| **T0.5** | 建立**术语映射表**：Match! 术语 ↔ XinMatch ↔ 标准晶体学术语 | `docs/TERMINOLOGY.md` | 覆盖 `INDEX_KEYWORDS.txt` 高频词，GUI 与文档统一 | 🟡 中 |
| **T0.6** | 搭建项目骨架 + CI（pytest、ruff、mypy）+ 进度表 | `pyproject.toml`、目录结构、空模块 | `pytest` 可运行、`ruff` 无错误、`docs/STATUS.md` 就绪 | 🔴 高 |

**Phase 0 验收**：`pytest tests/baseline --collect-only` → 标准样品集与基线齐备

---

### Phase 1 · 核心数据模型（`core/model/`）

| ID | 任务 | 输出 | 验收标准 | 优先级 |
|----|------|------|---------|--------|
| **T1.1** | `Pattern` 数据类：2θ 数组、强度数组、波长、步长、元数据 | `core/model/pattern.py` | 支持切片、插值重采样、单位转换（2θ↔d↔Q）；round-trip 序列化无损 | 🔴 高 |
| **T1.2** | `Peak` 数据类：2θ、强度、FWHM、d、hkl、关联状态、标记状态 | `core/model/peak.py` | 支持峰列表增删改、排序、按 2θ 窗口查询（二分查找） | 🔴 高 |
| **T1.3** | `Entry`（参考库条目）：分子式、矿物名、晶胞、空间群、d-I 峰表、文献、质量标记 | `core/model/entry.py` | 能从 CIF 构造；d-I 表按强度降序 | 🔴 高 |
| **T1.4** | `Phase`（已选物相）：关联 Entry、缩放因子、2θ 偏移、峰关联表 | `core/model/phase.py` | 支持计算该相贡献的衍射谱 | 🟡 中 |
| **T1.5** | `Restraints`（限制条件）：元素红/黄/绿三态、晶系、空间群、密度、颜色、年份、作者 | `core/model/restraints.py` | 三态语义与 Match! 一致（红=排除 黄=可选 绿=必须含） | 🔴 高 |
| **T1.6** | `Project`（工程）：多图谱、峰列表、候选列表、已选相、参数、撤销栈 | `core/model/project.py` | 支持 undo/redo；可序列化为 `.xinmatch.json` | 🟡 中 |

**Phase 1 验收**：`pytest tests/model -q` → 数据模型全绿

---

### Phase 2 · 衍射数据 I/O（`core/io/`）—— L1 文件格式兼容

> 参考规格：`docs/match4_help/import_diffraction-data_file-formats.md`
> **共 33 种格式**：22种厂商格式 + 6种自由格式 + 结构数据格式

| ID | 任务 | 输出 | 验收标准 | 优先级 |
|----|------|------|---------|--------|
| **T2.0** | 格式自动识别器：按扩展名 + 魔数 + 内容嗅探 | `core/io/detect.py` | 对 33 种格式各 1 个样本，识别准确率 100% | 🔴 高 |
| **T2.1** | 自由格式（6种）：DBWS `.rfl/.dat`、ASCII profile 三变体、2列峰表、ENDEAVOUR | `core/io/free.py` | round-trip：读入→写出→再读，数值最大误差 <1e-9 | 🔴 高 |
| **T2.2** | PANalytical/Philips：`.rd`、`.udf`、`.udi` | `core/io/panalytical.py` | 用 `Tutorial/quickstart.rd`、`aragonite.udi` 验证 | 🔴 高 |
| **T2.3** | Bruker/Siemens：`.raw`(v1/v2/v3)、`.dif`、`.uxd`、`.brml`(XML) | `core/io/bruker.py` | 每个子格式 ≥1 样本通过解析 | 🟡 中 |
| **T2.4** | Rigaku `.ras`/`.raw`、Stoe `.raw`/`.pks`、Shimadzu `.raw`、SCINTAG、MDI `.mdi` | `core/io/vendors_a.py` | 每格式 ≥1 样本通过解析 | 🟡 中 |
| **T2.5** | 其余：INEL `.dat`、GNR `.esg`、Sietronics `.cpi`、`.xrdml`、`.gdf`、XPowder `.plv`、JEOL/TXRD `.txt` | `core/io/vendors_b.py` | 每格式 ≥1 样本通过解析 | 🟢 低 |
| **T2.6** | CIF 读取（用 `gemmi`）：晶胞、空间群、原子坐标 → `Entry` | `core/io/cif.py` | 用 `Tutorial/calcite.cif` 验证；能生成 d-I 峰表 | 🔴 高 |
| **T2.7** | **.mtu 用户数据库** 读写（Match! 私有格式逆向） | `core/io/mtu.py` | 能读取 Tutorial 示例；round-trip 基本一致 | 🟡 中 |
| **T2.8** | 导出器：峰表、profile、参考谱、候选列表、答案集、CIF | `core/io/exporters.py` | 每种导出格式能被读回且数值一致 | 🔴 高 |
| **T2.9** | 格式兼容回归套件：统一入口 `load_pattern(path)` | `tests/io/test_all_formats.py` | 全部样本文件 ✅ 通过；新格式按模板添加 | 🔴 高 |

**Phase 2 验收**：`pytest tests/io -q` → 33 种格式 round-trip 全绿

---

### Phase 3 · 原始数据预处理（`core/preprocess/`）

> 参考：`rawdata-proc*.md`（10 篇）

| ID | 任务 | 输出 | 验收标准 | 优先级 |
|----|------|------|---------|--------|
| **T3.1** | 平滑：移动平均、Savitzky-Golay（`scipy.signal`） | `smoothing.py` | 合成高斯峰加噪后平滑，峰位偏移 <0.005° | 🔴 高 |
| **T3.2** | 背景测定：自动（迭代多项式/形态学）+ 手动控制点 + 背景导入 | `background.py` | 对 `LaB6_Cu_Ka1.dat` 自动背景不切掉任何衍射峰 | 🔴 高 |
| **T3.3** | 背景扣除 | `background.py` | 净强度 = 原强度 − 背景，无负值异常 | 🔴 高 |
| **T3.4** | Kα2 剥离（Rachinger 法 + 改进法），强度比 0.5 | `alpha2.py` | 合成双峰谱剥离后与纯 Kα1 相似度 >0.98 | 🔴 高 |
| **T3.5** | 零点校正（zero point shift） | `zeropoint.py` | 用 LaB6/NIST SRM 校正，残差 <0.01° | 🟡 中 |
| **T3.6** | 试样位移误差校正（specimen displacement） | `specimen_displacement.py` | 位移 0.1 mm 时校正后峰位误差 <0.01° | 🟡 中 |
| **T3.7** | 谱图裁剪 Trim / 分辨率提升（插值） | `trim.py` `resolution.py` | 边界正确；插值不改变峰面积 >1% | 🟡 中 |
| **T3.8** | **自动处理流水线**（Automatic Raw Data Processing） | `auto_pipeline.py` | 一键跑完，输出可复现（相同输入→相同输出） | 🔴 高 |

**Phase 3 验收**：对 `LaB6_Cu_Ka1.dat` 跑自动流水线 → 峰位与 NIST 标准值偏差 <0.01°

---

### Phase 4 · 寻峰与 Profile Fitting（`core/peak/`）

> 参考：`rawdata-proc_peaksearch.md`、`profilefitting*.md`、`peaklist*.md`

| ID | 任务 | 输出 | 验收标准 | 优先级 |
|----|------|------|---------|--------|
| **T4.1** | 寻峰：二阶导数法 + 信噪比阈值 + 灵敏度参数 | `peak_search.py` | 合成谱召回率 >95%，假峰 <5% | 🔴 最高 |
| **T4.2** | 峰位精修：重心法 / 抛物线拟合 / 高斯拟合 | `peak_refine.py` | 峰位精度 <0.002° | 🔴 高 |
| **T4.3** | 峰形函数库：Gaussian、Lorentzian、**pseudo-Voigt**、Pearson VII | `shapes.py` | 与解析解对比误差 <1e-6；FWHM↔η 参数互换自洽 | 🔴 高 |
| **T4.4** | Profile Fitting：多峰同时最小二乘拟合 | `profile_fit.py` | 合成 5 峰谱拟合 Rwp <2%；收敛稳定 | 🔴 高 |
| **T4.5** | 峰编辑：手动增/删/改峰、峰关联标记、删除所有峰 | `peak_edit.py` | 操作幂等；与 `Project` undo 栈集成 | 🟡 中 |
| **T4.6** | 由峰数据计算谱（Profile calculation from peak data） | `peak_to_profile.py` | 峰面积守恒误差 <1% | 🟡 中 |

**Phase 4 验收**：合成谱拟合测试 → Rwp < 2%

---

### Phase 5 · 参考数据库（`core/db/`）—— 无需逆向，用开放数据

> 数据源：COD（CC0）。参考 schema 可借鉴 Profex 的 `cod-250127.db3`
> 28 个检索字段：元素 / 晶胞参数 / d 值 / 分子式 / 矿物名 / 作者 / 期刊 / 年份 / 空间群 / 颜色 / 压力 / 温度 / 密度

| ID | 任务 | 输出 | 验收标准 | 优先级 |
|----|------|------|---------|--------|
| **T5.1** | COD → SQLite 构建器：解析 CIF/MySQL dump，抽取 `Entry` 字段 | `core/db/build_cod.py` | 全量构建成功；条目数 ≥ COD 官方数（约 50 万） | 🔴 高 |
| **T5.2** | 表结构设计：entries / peaks(d-I) / elements / cells / authors / minerals + 索引 | `core/db/schema.sql` | 单条查询 <5 ms；覆盖 Match! 的 28 个检索字段 | 🔴 高 |
| **T5.3** | **倒排索引**：元素组合 → entry id 集合；d 值区间索引 | `core/db/index_build.py` | 典型检索 <100 ms | 🔴 高 |
| **T5.4** | d 值检索（核心）：给定峰列表 → 候选 entry（容差窗口） | `core/db/query_peaks.py` | 用 LaB6 标样，正确 entry 必在前 100 名内 | 🔴 最高 |
| **T5.5** | 多字段组合检索：元素、晶系、空间群、颜色、密度、年份、作者、矿物名 | `core/db/query_filter.py` | 各字段单独测试通过；组合查询正确 | 🟡 中 |
| **T5.6** | **用户数据库 UDB**：增删查改、导入/导出 `.mtu`、CIF 导入 | `core/db/user_db.py` | 自建库可持久化；round-trip 一致 | 🟡 中 |
| **T5.7** | 数据库管理：多库切换、合并、重命名、删除 | `core/db/manager.py` | 多库并存无冲突 | 🟡 中 |
| **T5.8** | **ICDD PDF 适配层**（插件式，不含数据） | `core/db/pdf_plugin.py` | 接口清晰；用 COD 实现参考实现 | 🟢 低 |

**Phase 5 验收**：LaB6 检索 → 正确 entry 进 Top-100

---

### Phase 6 · Search-Match 引擎（`core/search/`）—— **项目核心**

> 参考：`searchmatch*.md`（13 篇）、`candselect*.md`、`candidate_list*.md`
> **FoM 6 项判据**（加权求和）：①2θ差 ②强度差 ③关联峰数-总峰数差 ④关联峰数-应关联数差 ⑤强度缩放因子 ⑥内部推导权重

| ID | 任务 | 输出 | 验收标准 | 优先级 |
|----|------|------|---------|--------|
| **T6.1** | **峰关联算法**：实验峰 ↔ 参考峰配对，贪心/匈牙利算法 | `correlate.py` | 合成数据 100% 正确配对；重叠峰处理稳定 | 🔴 最高 |
| **T6.2** | **FoM 判据实现**（6 项）：每项单独实现 + 加权求和 | `fom_criteria.py` | 每项单测通过；权重可配置（默认一组合理值） | 🔴 最高 |
| **T6.3** | 加权求和 + 排序，产出候选列表 | `fom.py` | 输出稳定可复现 | 🔴 高 |
| **T6.4** | **峰基 Search-Match**：遍历参考库 → FoM → Top-N 候选 | `search_match.py` | 50 万条目单次全检索 <30 s（Numba 优化后 <5 s） | 🔴 最高 |
| **T6.5** | **标记峰 Search-Match**（对标 Ctrl+Shift+M） | `search_marked.py` | 与 T6.4 共享核心，语义一致 | 🟡 中 |
| **T6.6** | **PFSM（全谱匹配）**：对每条候选算全谱 → 拟合缩放 + 2θ偏移 → Rwp 降低量为 FoM | `pfsm.py` | 与 T6.4 在标准样品集上排序相关性 >0.7 | 🔴 高 |
| **T6.7** | 候选列表模型：排序、筛选、多选、「显示未关联峰」、条目详情 | `candidate_list.py` | 与 `Project` 集成 | 🟡 中 |
| **T6.8** | 已选相后自动重算 FoM（残差峰驱动） | `residual_update.py` | 选中一相后，剩余候选 FoM 更新正确 | 🟡 中 |
| **T6.9** | ⭐ **L3 黄金验收**：标准样品集 vs Match! 基线 Top-10 命中率 | `tests/search/test_baseline.py` | **Top-10 命中率 ≥ Match! 基线的 80%** | 🔴 最高 |
| **T6.10** | 权重标定：用标准样品集反推一组最优默认权重（网格搜索/贝叶斯） | `tune_weights.py` | 命中率提升有量化记录 | 🟡 中 |

**Phase 6 验收**：`pytest tests/search/test_baseline.py` → **Top-10 命中率 ≥ 基线 80%**

---

### Phase 7 · 限制条件 Restraints（`core/search/restraints.py`）

> 参考：`restraints*.md`（9 篇）
> **三态语义**：🔴红=排除 / 🟡黄=可选 / 🟢绿=必须含

| ID | 任务 | 输出 | 验收标准 | 优先级 |
|----|------|------|---------|--------|
| **T7.1** | 元素组成限制（三态语义）+ 与倒排索引结合剪枝 | `restr_elements.py` | 设「排除某元素」后该元素条目 100% 剔除 | 🔴 高 |
| **T7.2** | 晶系 / 空间群限制 | `restr_crystal.py` | 过滤正确 | 🟡 中 |
| **T7.3** | 衍射限制 d 值/峰位 | `restr_diffraction.py` | 加入指定峰位后候选必含该峰 | 🟢 低 |
| **T7.4** | 物理性质：密度、颜色 | `restr_properties.py` | 区间过滤正确 | 🟢 低 |
| **T7.5** | 文献限制：作者、期刊、年份、CODEN | `restr_bibliography.py` | 匹配正确 | 🟢 低 |
| **T7.6** | 子文件限制（无机/有机/质量标记，对标 `.mtb` 位图语义） | `restr_subfile.py` | 分类正确 | 🟡 中 |
| **T7.7** | 组合应用 + 剪枝性能（限制应在检索**前**生效） | `apply.py` | 加限制后检索不慢于无限制 | 🔴 高 |

**Phase 7 验收**：各限制条件单元测试 + 组合检索性能测试通过

---

### Phase 8 · 定量分析（`core/quant/`）

> 参考：`quant_analysis_*.md`（3 篇）

| ID | 任务 | 输出 | 验收标准 | 优先级 |
|----|------|------|---------|--------|
| **T8.1** | **RIR（Reference Intensity Ratio）法**：I/Ic 归一 + 绝热法 | `rir.py` | 二元混合物（50/50）定量误差 <3 wt% | 🔴 高 |
| **T8.2** | 内标法（已知量内标物） | `internal_standard.py` | 误差 <2 wt% | 🟡 中 |
| **T8.3** | 基于 Rietveld 的定量（依赖 Phase 10） | `rietveld_quant.py` | 误差 <1.5 wt% | 🟡 中 |
| **T8.4** | 非晶含量/结晶度 DOC（Degree of Crystallinity） | `doc.py` | 与已知结晶度样品对比误差 <5% | 🟢 低 |

**Phase 8 验收**：标准混合样品定量误差 < 3 wt%

---

### Phase 9 · 指标化 Indexing（`core/index/`）

> 参考：`indexing*.md`（4 篇）。Treor / Dicvol 为公开发表算法，有开源实现可参考。

| ID | 任务 | 输出 | 验收标准 | 优先级 |
|----|------|------|---------|--------|
| **T9.1** | 峰位 → d 值 → 晶面指标候选；七晶系面间距公式 | `lattice.py` | 各晶系公式与标准教科书一致（单测） | 🟡 中 |
| **T9.2** | **Treor** 试探法（trial-and-error）实现 | `treor.py` | 已知结构（如 LaB6 立方）指标化成功 | 🟡 中 |
| **T9.3** | **Dicvol** 二分法穷举实现 | `dicvol.py` | 同上；给出 M(n)/F(n) 品质因数 | 🟡 中 |
| **T9.4** | 结果排序、去同构解、与参考库对照验证 | `solutions.py` | 正确解排在前 5 | 🟡 中 |

**Phase 9 验收**：LaB6 等已知结构样品指标化成功，正确解排前 5

---

### Phase 10 · 精修（`core/refine/`）

> 参考：`Rietveld*.md`、`LeBail.md`、`refinements_FullProf.md`

| ID | 任务 | 输出 | 验收标准 | 优先级 |
|----|------|------|---------|--------|
| **T10.1** | 峰形模型：pseudo-Voigt + 不对称 + Caglioti 宽度模型（U,V,W）+ 轴向发散 | `peak_model.py` | 与文献公式一致 | 🔴 高 |
| **T10.2** | 结构因子计算：原子散射因子（国际表近似）、温度因子、多重性、Lorentz-Polarization | `structure_factor.py` | 与已知计算谱对比 R <1% | 🔴 高 |
| **T10.3** | **Le Bail 分解**：迭代分配重叠峰强度 | `le_bail.py` | 收敛；Rwp <10% | 🟡 中 |
| **T10.4** | **Rietveld 精修**：最小二乘 + 参数约束（缩放、晶胞、峰宽、零点、原子坐标/占位/Uiso） | `rietveld.py` | 标准样品 Rwp <8%，Rp <6%，χ² 合理 | 🟡 中 |
| **T10.5** | 残差计算与残差峰分析（Peak Residuals） | `residuals.py` | 残差谱正确 | 🟢 低 |
| **T10.6** | **FullProf 适配层**：生成 .pcr、调用 FullProf、解析结果 | `fullprof_adapter.py` | 能驱动已安装的 FullProf 完成一轮精修 | 🔴 高 |
| **T10.7** | 策略化精修（参数逐步开启，Parameter Turn-On） | `turn_on.py` | 参数顺序可配；收敛率提升有记录 | 🟡 中 |

**Phase 10 验收**：标准样品 Rietveld 精修 Rwp < 8%

---

### Phase 11 · 微结构分析（`core/micro/`）

> 参考：`crystallite_size.md`、`doc.md`

| ID | 任务 | 输出 | 验收标准 | 优先级 |
|----|------|------|---------|--------|
| **T11.1** | Scherrer 晶粒尺寸（含仪器宽度校正，Instrumental Standards） | `crystallite_size.py` | 用 LaB6 标样校正后，NIST 标样尺寸误差 <15% | 🟡 中 |
| **T11.2** | 微观应变（Williamson-Hall 图） | `microstrain.py` | 线性拟合正确 | 🟢 低 |
| **T11.3** | 结晶度 DOC（若 T8.4 未实现） | `doc.py` | 见 T8.4 | 🟢 低 |

**Phase 11 验收**：NIST 标样晶粒尺寸误差 < 15%

---

### Phase 12 · 报告与导出（`core/report/`）

> 参考：`report_*.md`、`export*.md`

| ID | 任务 | 输出 | 验收标准 | 优先级 |
|----|------|------|---------|--------|
| **T12.1** | 报告数据模型：样品信息、实验条件、峰表、候选列表、已选相、定量结果、R 因子 | `report_model.py` | 覆盖 Match! 报告的全部章节 | 🟡 中 |
| **T12.2** | 渲染器：HTML（默认）+ PDF（WeasyPrint）+ 纯文本 | `render.py` | 三种格式均可生成且内容一致 | 🟡 中 |
| **T12.3** | 图谱图片导出（PNG/SVG/EPS，高 DPI） | `figure_export.py` | 300 dpi 输出清晰；SVG 矢量可用 | 🟡 中 |
| **T12.4** | 剪贴板/图片复制（对标 Copy Pattern Graphics） | `clipboard.py` | Windows 剪贴板写入成功 | 🟢 低 |

**Phase 12 验收**：完整样品分析报告三格式生成成功

---

### Phase 13 · GUI（`ui/` · PySide6）

> **只有到这一步才碰 GUI**。前面所有 `core/` 已可 CLI 验证。
> ⚠️ **图标与视觉资源必须原创或使用开源图标（如 KDE Breeze / Lucide）**，不得复制 Match! 资源。

| ID | 任务 | 输出 | 验收标准 | 优先级 |
|----|------|------|---------|--------|
| **T13.1** | 主窗口骨架：菜单栏（对标 Match! 菜单结构）、工具栏、状态栏、四个停靠面板 | `ui/main_window.py` | 菜单项与 `FUNCTION_MAP.md` 一一对应 | 🔴 高 |
| **T13.2** | **图谱视图（pyqtgraph）**：多谱叠放、垂直/水平偏移、缩放/拖拽/追踪、图例 | `ui/pattern_view.py` | 5 万点实时缩放不掉帧；十字光标追踪 | 🔴 最高 |
| **T13.3** | 峰列表 / 候选列表 / 匹配列表 三个表格（排序、右键菜单、双击选中） | `ui/tables.py` | 交互与 Match! 一致 | 🔴 高 |
| **T13.4** | **周期表元素选择控件**（Restraints/Composition，红/黄/绿三态） | `ui/periodic_table.py` | 118 元素，三态切换 + Toggle 按钮 | 🟡 中 |
| **T13.5** | 各功能对话框：导入选项、实验详情、选项设置（15 类）、颜色线型设置 | `ui/dialogs/` | 每类设置可持久化到配置文件 | 🟡 中 |
| **T13.6** | 快捷键映射（对标 `function_keys.md`：Ctrl+M、Ctrl+Shift+M…） | `ui/shortcuts.py` | 全部列出并生效 | 🟡 中 |
| **T13.7** | 样式主题：浅色/深色，图标用开源图标库 | `ui/theme.py` | 两种主题无控件不可读 | 🟢 低 |

**Phase 13 验收**：人工按 Match! 手册操作 XinMatch 完成一次完整物相分析 → 结果一致

---

### Phase 14 · 批处理与脚本（`cli/`）

> 参考：`batch_scripting.md`

| ID | 任务 | 输出 | 验收标准 | 优先级 |
|----|------|------|---------|--------|
| **T14.1** | CLI：`xinmatch import → process → search → quantify → report` 一条龙 | `cli/main.py` | 对标准样品集批量跑通，输出 JSON/报告 | 🟡 中 |
| **T14.2** | Python API（供二次开发） | `xinmatch/__init__.py` | 文档字符串完整；有 3 个示例脚本 | 🟡 中 |
| **T14.3** | 批处理脚本（JSON/YAML 配置驱动） | `cli/batch.py` | 配置可复现全流程 | 🟢 低 |

**Phase 14 验收**：命令行批处理 10 个样品 → 全部成功并输出报告

---

### Phase 15 · 打包与发布

| ID | 任务 | 输出 | 验收标准 | 优先级 |
|----|------|------|---------|--------|
| **T15.1** | PyInstaller/Nuitka 打包 Windows x64 安装包 | `dist/` + Inno Setup 脚本 | 干净虚拟机可安装运行 | 🔴 高 |
| **T15.2** | 数据库分发：COD SQLite 单独下载（体积大，不放安装包） | 下载器 | 首次启动引导下载 | 🟡 中 |
| **T15.3** | 用户文档（基于自写内容，**不复制** Match! 手册） | `docs/user_guide/` | 覆盖全部功能 | 🟡 中 |
| **T15.4** | 开源协议与合规审查：确认全部依赖许可 | `LICENSE`、`NOTICE` | 无 GPL 传染性依赖（避免引入 GPL 库） | 🔴 高 |
| **T15.5** | Linux / macOS 打包（可选） | 各平台安装包 | 基本功能可用 | 🟢 低 |

**Phase 15 验收**：Windows 安装包在干净虚拟机上安装运行成功

---

## 🔀 关键路径与并行建议

```
T0 ──> T1 ──> T2 ──> T3 ──> T4 ──┐
                                  ├──> T5 ──> T6 ──> T9 ──> T10 ──> T8 ──> T11
              T1 ──> T7 ──────────┘                                        │
                                                                           v
                                                            T12 ──> T13 ──> T14 ──> T15
```

**可并行（互不阻塞，适合多 Agent 同时开工）**：
- **组 A**：T2（I/O，纯解析，无依赖）—— 33 种格式可再细分给 2-3 个 Agent
- **组 B**：T3 + T4（预处理 + 寻峰）—— 信号处理方向
- **组 C**：T5（数据库）—— 可先于 T6 完成，schema 设计独立
- **组 D**：T9（指标化）—— 算法独立，晶体学方向
- **组 E**：T10.1/T10.2（峰形模型 + 结构因子）—— 精修基础，可与 T6 并行

**必须串行**：
- T6（Search-Match）依赖 T4 的峰 + T5 的库
- T8 的 Rietveld 定量依赖 T10
- T13（GUI）依赖所有 core 模块

---

## 🤖 AI Agent 协作开发指南

### Agent 任务模板（每个 T# 任务）

```
【任务编号】T#.#
【任务描述】<清晰的功能描述>
【必读文档】
1. docs/00_TECH_STACK_ANALYSIS.md（技术栈与合规边界）
2. docs/FUNCTION_MAP.md（功能清单索引）
3. docs/match4_help/<相关主题>.md（官方规格）

【硬约束】
- 禁止反汇编/反编译 Match!.exe，禁止逆向授权机制
- 代码放进 core/<模块>/，不得依赖 GUI
- 函数签名：输入/输出都用 numpy 数组或 dataclass
- 每个函数必须有 docstring：对应 Match! 功能 + 算法来源（文献/公式）
- 必须写 pytest 测试

【输入输出】
- 输入：<数据结构/文件格式>
- 输出：<数据结构/文件格式>

【验收标准】
- <明确的通过/失败标准>
- <至少5个测试用例，含边界情况>

【交付】
- 实现文件 + 测试文件 + 更新 docs/STATUS.md
- 报告：实现了什么、测试是否通过、与 Match! 规格的差异点
```

### Agent 角色分工建议

| 角色 | 负责阶段 | 技能要求 | 任务示例 |
|------|---------|---------|---------|
| **数据格式工程师** | Phase 2 | Python, 二进制解析, 格式逆向 | T2.1-T2.5 各厂商格式解析 |
| **信号处理工程师** | Phase 3, 4 | Python, NumPy, SciPy, 信号处理 | T3 平滑/背景/Kα2, T4 寻峰/拟合 |
| **数据库工程师** | Phase 5 | SQL, SQLite, 索引优化, 数据工程 | T5 数据库设计 + COD 导入 + 倒排索引 |
| **算法工程师（核心）** | Phase 6 | Python, 优化算法, 晶体学基础 | T6 FoM + Search-Match + PFSM |
| **晶体学家** | Phase 9, 10, 11 | 晶体学, XRD 物理, 精修 | T9 指标化, T10 Rietveld, T11 微结构 |
| **定量分析工程师** | Phase 8 | 分析化学, XRD 定量方法 | T8 RIR/内标/Rietveld定量 |
| **GUI 工程师** | Phase 13 | PySide6, pyqtgraph, Qt | T13 全部 UI 模块 |
| **测试工程师** | 全阶段 | pytest, 数值回归测试, 对比验证 | 所有模块的测试与基线验证 |

---

## ⚠️ 风险登记

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| FoM 内部权重未公开 → 排序无法 100% 复现 | L3 兼容性受限 | 高 | 以 Top-N 命中率验收；T6.10 用数据标定权重 |
| COD 数据质量参差（含错误条目） | 误匹配 | 中 | 建立质量标记字段，默认过滤低质量条目 |
| 缺少真实多样品测试数据 | 无法验证 | 中 | **T0.3 是最高优先级**，务必先做 |
| pyqtgraph 大数据性能 | 交互卡顿 | 中 | 降采样（LTTB 算法）+ OpenGL |
| 50 万条目全检索性能 | 慢 | 高 | 倒排索引剪枝 + Numba + 预过滤（强峰必中） |
| 引入 GPL 依赖导致协议冲突 | 法律风险 | 低 | T15.4 严格审查；优先 MIT/BSD/LGPL |
| 误复制 Match! 视觉资源 | 版权风险 | 低 | 图标/文档一律原创，用开源图标库 |

---

## 🚀 立即可以开始的第一步（按优先级排序）

1. **T0.3 + T0.4（最高优先级）**：建标准样品集 + 跑 Match! 基线
   - 没有这个，Phase 6 无法验收
   - 可先从 Tutorial 自带样例 + 公开数据开始

2. **T0.2**：安装最新版到独立目录，跑 `tools/extract_help.py` 看版本差异
   - 确保目标是最新版功能

3. **并行启动组 A（T2 I/O）**：
   - 纯解析工作，规格文档已就位
   - AI agent 可立即开工，33 种格式可分配给 2-3 个 Agent 并行

4. **并行启动组 C（T5 数据库）**：
   - 数据库 schema 设计 + COD 导入
   - 不依赖其他模块，可提前完成

---

## 📚 已有资产清单（非常宝贵！）

| 资产 | 路径 | 说明 |
|------|------|------|
| 169 篇规格文档（Markdown, 627 KB） | `docs/match4_help/*.md` | 从 `Match4.qch` 提取，**可直接投喂 AI agent** |
| 功能清单索引 | `docs/FUNCTION_MAP.md` | 17 个模块分类，带链接 |
| 4076 条索引关键词 | `docs/INDEX_KEYWORDS.txt` | 术语表，用于统一 XinMatch 术语 |
| 技术栈勘察报告 | `docs/00_TECH_STACK_ANALYSIS.md` | 深度分析 + 合规边界 + 选型建议 |
| 原始 ROADMAP | `ROADMAP.md` | 15 阶段详细任务分解 |
| 提取脚本 | `tools/extract_help.py` | 换安装目录即可重新提取，支持版本 diff |

---

*文档版本：v2.0（综合升级版）*
*创建日期：2026-10-06*
*基于资产：技术栈勘察报告 + ROADMAP v1 + 169 篇官方文档 + FUNCTION_MAP*
