# XinMatch 实施路线图

> XinMatch —— 开放版粉末 XRD 物相分析平台
> 方法：净室设计（规格来自官方文档 + 黑盒观察，代码从零实现）
> 技术栈：Python 3.11 + PySide6 (Qt6) + NumPy/SciPy + pyqtgraph + SQLite
>
> **给 AI Agent 的执行约定**：每个任务 `T#` 都是独立可交付单元。
> Agent 开工前先读 `docs/00_TECH_STACK_ANALYSIS.md` + `docs/FUNCTION_MAP.md` + 任务指定的 `docs/third-party-help/<topic>.md`。

---

## 通用 Agent 提示词模板

```
你是 XinMatch 项目的开发 Agent。XinMatch 是粉末 X 射线衍射物相分析软件的开源实现。

【必读】
1. D:\TEMP\XinMatch\docs\00_TECH_STACK_ANALYSIS.md  （技术栈与合规边界）
2. D:\TEMP\XinMatch\docs\FUNCTION_MAP.md            （功能清单索引）
3. 本任务指定的 docs/third-party-help/<topic>.md          （官方规格，已提取为 Markdown）

【硬约束】
- 禁止反汇编/反编译 参考软件主程序，禁止逆向授权机制。规格一律取自官方文档。
- 代码放进 D:\TEMP\XinMatch\core\<模块>\，不得依赖 GUI。
- 函数签名：输入/输出都用 numpy 数组或 dataclass，禁止在算法层读写文件。
- 每个函数必须有 docstring 注明：对应 参考软件 的哪个功能 + 算法来源（文献/公式）。
- 必须写 pytest 测试，验收标准见任务书。

【交付】
- 实现文件 + 测试文件 + 更新 docs/STATUS.md 勾选本任务
- 报告：实现了什么、测试是否通过、与 参考软件 规格的差异点
```

---

## Phase 0 · 知识基座与黄金基线（所有后续阶段的验收基础）

> 这一阶段不做任何逆向，只做资料工程。**不做完 Phase 0 就不要开工写代码**，否则后面无法验证。

| ID | 任务 | 输出 | 验收标准 |
|---|---|---|---|
| **T0.1** | 提取官方文档库 | `docs/third-party-help/*.md`（169 篇）、`FUNCTION_MAP.md`、`INDEX_KEYWORDS.txt` | ✅ **已完成**（`tools/extract_help.py` 跑通，627 KB） |
| **T0.2** | 安装最新版到**独立目录**（如 `参考软件独立安装目录`），重跑提取脚本，diff 两版功能差异 | `docs/version_diff_4.2.329_vs_latest.md` | 新版本新增/变更主题的清单完整，无遗漏 `whats_new_*` |
| **T0.3** | 建立**标准样品集**：收集 20-30 个已知物相组成的实测 XRD 数据（可用 `Tutorial/` 自带样例 + 公开数据 + ICDD 标样） | `tests/fixtures/patterns/` + `tests/fixtures/ground_truth.json`（每个样品的真实物相列表） | ≥20 个样品，覆盖：单相、两相、三相、含非晶、含微量相(<5%)、重叠峰严重 |
| **T0.4** | 用 参考软件 跑标准样品集，记录**基线结果**（候选列表 Top-20 FoM、选中相、定量结果） | `tests/baseline/reference_baseline.json` | 每个样品一条记录，含排序与 FoM 值。**这是 L3 兼容性的黄金标准** |
| **T0.5** | 建立**术语映射表**：参考软件 术语 ↔ XinMatch 术语 ↔ 标准晶体学术语 | `docs/TERMINOLOGY.md` | 覆盖 `INDEX_KEYWORDS.txt` 中高频词，GUI 与文档统一使用 |
| **T0.6** | 搭建项目骨架 + CI（pytest、ruff、mypy）+ `docs/STATUS.md` 进度表 | `pyproject.toml`、目录结构、空模块 | `pytest` 可运行（0 用例通过）、`ruff` 无错误 |
| **T0.7** | 跨平台约定：路径用 `pathlib`、文本统一 UTF-8、换行符处理（注意 参考软件 不支持 CR-only 行尾） | `docs/CONVENTIONS.md` | Windows/Linux/macOS 三平台 `pytest` 均通过 |

---

## Phase 1 · 核心数据模型（`core/model/`）

| ID | 任务 | 输出 | 验收标准 |
|---|---|---|---|
| **T1.1** | `Pattern` 数据类：2θ 数组、强度数组、波长、步长、元数据（仪器、样品、日期） | `core/model/pattern.py` | 支持切片、插值重采样、单位转换（2θ↔d↔Q）；round-trip 序列化无损 |
| **T1.2** | `Peak` 数据类：2θ、强度、FWHM、d、hkl、关联状态、标记状态 | `core/model/peak.py` | 支持峰列表增删改、排序、按 2θ 窗口查询（二分查找） |
| **T1.3** | `Entry`（参考库条目）：分子式、矿物名、晶胞、空间群、d-I 峰表、文献、质量标记 | `core/model/entry.py` | 能从 CIF 构造；d-I 表按强度降序 |
| **T1.4** | `Phase`（已选物相）：关联 Entry、缩放因子、2θ 偏移、峰关联表 | `core/model/phase.py` | 支持计算该相贡献的衍射谱 |
| **T1.5** | `Restraints`（限制条件）：元素红/黄/绿三态、晶系、空间群、密度、颜色、年份、作者 | `core/model/restraints.py` | 支持序列化；三态语义与 参考软件 一致（红=排除 黄=可选 绿=必须含） |
| **T1.6** | `Project`（工程）：多图谱、峰列表、候选列表、已选相、参数、撤销栈 | `core/model/project.py` | 支持 undo/redo；可序列化为 `.xinmatch.json` |

---

## Phase 2 · 衍射数据 I/O（`core/io/`）—— 对标 L1 文件格式兼容

> 参考规格：`docs/third-party-help/import_diffraction-data_file-formats.md`

| ID | 任务 | 输出 | 验收标准 |
|---|---|---|---|
| **T2.1** | 格式自动识别器：按扩展名 + 魔数 + 内容嗅探 | `core/io/detect.py` | 对 33 种格式各 1 个样本文件，识别准确率 100% |
| **T2.2** | 自由格式：DBWS `.rfl/.dat`、ASCII profile 三变体、2 列峰表 | `core/io/free.py` | round-trip：读入→写出→再读，数值最大误差 <1e-9 |
| **T2.3** | PANalytical/Philips：`.rd`、`.udf`、`.udi` | `core/io/panalytical.py` | 用 `Tutorial/quickstart.rd`、`aragonite.udi` 验证，2θ/I 与文件一致 |
| **T2.4** | Bruker/Siemens：`.raw`(1/2/3)、`.dif`、`.uxd`、`.brml`(XML) | `core/io/bruker.py` | 至少覆盖 Bruker RAW v1/v2/v3 各 1 个样本 |
| **T2.5** | Rigaku `.ras`/`.raw`、Stoe `.raw`/`.pks`、Shimadzu `.raw`、SCINTAG、MDI `.mdi` | `core/io/vendors_a.py` | 每格式 ≥1 样本通过解析 |
| **T2.6** | 其余：INEL `.dat`、GNR `.esg`、Sietronics `.cpi`、`.xrdml`、`.gdf`、XPowder `.plv`、JEOL/TXRD `.txt` | `core/io/vendors_b.py` | 同上 |
| **T2.7** | CIF 读取（用 `gemmi`）：晶胞、空间群、原子坐标 → `Entry` | `core/io/cif.py` | 用 `Tutorial/calcite.cif` 验证；能生成 d-I 峰表 |
| **T2.8** | 导出器：峰表、profile、参考谱（峰/谱）、候选列表、答案集 | `core/io/exporters.py` | 每种导出格式能被读回且数值一致 |
| **T2.9** | **格式兼容回归套件**：统一入口 `load_pattern(path)` | `tests/io/test_all_formats.py` | 全部样本文件 ✅ 通过；新格式按模板添加即可 |

---

## Phase 3 · 原始数据预处理（`core/preprocess/`）

> 参考：`rawdata-proc*.md`（10 篇）

| ID | 任务 | 输出 | 验收标准 |
|---|---|---|---|
| **T3.1** | 平滑：移动平均、Savitzky-Golay（`scipy.signal`） | `smoothing.py` | 合成高斯峰加噪后平滑，峰位偏移 <0.005°；参数可配 |
| **T3.2** | 背景测定：自动（迭代多项式/形态学）+ 手动控制点 + 背景导入 | `background.py` | 对 `Tutorial/LaB6_Cu_Ka1.dat` 自动背景不切掉任何衍射峰 |
| **T3.3** | 背景扣除 | `background.py` | 净强度 = 原强度 − 背景，无负值异常 |
| **T3.4** | Kα2 剥离（Rachinger 法 + 改进法），支持 Kα1/Kα2 强度比 0.5 | `alpha2.py` | 合成双峰谱剥离后应与纯 Kα1 谱相似度 >0.98 |
| **T3.5** | 零点校正（zero point shift） | `zeropoint.py` | 用标样（LaB6/NIST SRM）校正，残差 <0.01° |
| **T3.6** | 试样位移误差校正（specimen displacement，与零点耦合） | `specimen_displacement.py` | 位移 0.1 mm 时校正后峰位误差 <0.01° |
| **T3.7** | 谱图裁剪 Trim / 分辨率提升（插值） | `trim.py` `resolution.py` | 边界正确；插值不改变峰面积 >1% |
| **T3.8** | **自动处理流水线**（对标 Automatic Raw Data Processing）：按配置串联上述步骤 | `auto_pipeline.py` | 一键跑完，输出可复现（相同输入→相同输出） |

---

## Phase 4 · 寻峰与 Profile Fitting（`core/peak/`）

> 参考：`rawdata-proc_peaksearch.md`、`profilefitting*.md`、`peaklist*.md`

| ID | 任务 | 输出 | 验收标准 |
|---|---|---|---|
| **T4.1** | 寻峰：二阶导数法 + 信噪比阈值 + 灵敏度参数（对标 Peak Searching Sensitivity） | `peak_search.py` | 对合成谱（已知峰位）召回率 >95%，假峰 <5% |
| **T4.2** | 峰位精修：重心法 / 抛物线拟合 / 高斯拟合 | `peak_refine.py` | 峰位精度 <0.002° |
| **T4.3** | 峰形函数库：Gaussian、Lorentzian、**pseudo-Voigt**、Pearson VII，及其面积/FWHM 换算 | `shapes.py` | 与解析解对比误差 <1e-6；FWHM↔η 参数互换自洽 |
| **T4.4** | Profile Fitting：多峰同时最小二乘拟合（`scipy.optimize.least_squares`），输出峰参数 + 拟合谱 | `profile_fit.py` | 合成 5 峰谱拟合 Rwp <2%；收敛稳定 |
| **T4.5** | 峰编辑：手动增/删/改峰、峰关联标记、删除所有峰 | `peak_edit.py` | 操作幂等；与 `Project` undo 栈集成 |
| **T4.6** | 由峰数据计算谱（Profile calculation from peak data） | `peak_to_profile.py` | 峰面积守恒误差 <1% |

---

## Phase 5 · 参考数据库（`core/db/`）—— 无需逆向，用开放数据

> 数据源：COD（CC0）。你已有 `D:\TEMP\cod-cifs-mysql.txz` 与 `D:\SOFTWARE\Profex-COD-250127\cod-250127.db3`

> ⚠️ **本阶段不逆向 参考软件 的 `.mti/.mqs/.mqn/.mtb` 索引格式。** COD 是 CC0 开放数据，
> 直接用官方源重建即可，且数据更新更及时、字段语义更清晰。仅 T5.9 做 `.mtu` 导入兼容（互操作性）。

| ID | 任务 | 输出 | 验收标准 |
|---|---|---|---|
| **T5.1** | COD → SQLite 构建器：解析 CIF/MySQL dump，抽取 `Entry` 字段 | `core/db/build_cod.py` | 全量构建成功；条目数 ≥ COD 官方数（约 50 万） |
| **T5.2** | 表结构设计：entries / peaks(d-I) / elements / cells / authors / minerals，+ 索引 | `core/db/schema.sql` | 单条查询 <5 ms；范围覆盖 参考软件 的 28 个检索字段 |
| **T5.3** | **倒排索引**：元素组合 → entry id 集合；晶胞参数/d 值区间索引 | `core/db/index_build.py` | 典型检索 <100 ms |
| **T5.4** | d 值检索（核心）：给定峰列表 → 候选 entry（容差窗口） | `core/db/query_peaks.py` | 用 LaB6 标样，正确 entry 必在前 100 名内 |
| **T5.5** | 多字段组合检索：元素、晶系、空间群、颜色、密度、年份、作者、矿物名 | `core/db/query_filter.py` | 各字段单独测试通过；组合查询正确 |
| **T5.6** | **用户数据库 UDB**：增删查改、导入/导出 `.mtu`、CIF 导入、ICSD 导入 | `core/db/user_db.py` | 自建库可持久化；round-trip 一致 |
| **T5.7** | 数据库管理：多库切换、合并、重命名、删除（对标 Reference Database Library） | `core/db/manager.py` | 多库并存无冲突 |
| **T5.8** | **ICDD PDF 适配层**（插件式，不含数据）：定义接口，用户自带授权数据可挂载 | `core/db/pdf_plugin.py` | 接口清晰；用 COD 实现一份参考实现 |
| **T5.9** | `.mtu` 导入兼容层（**互操作性**，P2 可选）。已知格式：`用户数据库文件头魔数` 魔数(20B) + 版本号 `uint16 LE`(2) + 疑似未压缩长度 `uint32 LE`(78805 > 文件 52730，存在压缩) + 数据区；字符串为 `uint16 LE` 长度前缀 + 内容 | `core/io/mtu.py` | 能读入 `Tutorial/colleague_database.mtu` 并转出 entries；原生格式仍为 SQLite/JSON |

---

## Phase 6 · Search-Match 引擎（`core/search/`）—— 项目核心

> 参考：`searchmatch*.md`（13 篇）、`candselect*.md`、`candidate_list*.md`

| ID | 任务 | 输出 | 验收标准 |
|---|---|---|---|
| **T6.0** | ⭐ **经典检索剪枝层：Hanawalt（三强线）+ Fink（八强线）**。在 FoM 全库计算**之前**把 50 万条目粗筛到数千条 | `hanawalt_fink.py` | 真实物相 100% 保留在粗筛集内；粗筛耗时 <2 s |
| **T6.1** | **峰关联算法**：实验峰 ↔ 参考峰配对（2θ 窗口 = "2theta window for peak correlation"），贪心/匈牙利算法 | `correlate.py` | 合成数据 100% 正确配对；重叠峰处理稳定 |
| **T6.2** | **FoM 判据实现**（6 项，见分析报告 §2.6）：2θ差、强度差、关联峰数差、应关联数差、缩放因子 | `fom_criteria.py` | 每项单测通过；权重可配置（默认一组合理值） |
| **T6.3** | 加权求和 + 排序，产出候选列表 | `fom.py` | 输出稳定可复现 |
| **T6.4** | **全谱 Search-Match**：遍历参考库 → FoM → Top-N 候选（性能关键，考虑 Numba/向量化） | `search_match.py` | 50 万条目单次全检索 <30 s（Numba 优化后 <5 s） |
| **T6.5** | **标记峰 Search-Match**（对标 Ctrl+Shift+M 仅对标记峰检索） | `search_marked.py` | 与 T6.4 共享核心，语义一致 |
| **T6.6** | **PFSM**：对每条候选算全谱 → 拟合缩放 + 2θ 偏移 → Rwp 降低量为 FoM | `pfsm.py` | 与 T6.4 在标准样品集上排序相关性 >0.7 |
| **T6.7** | 候选列表模型：排序、筛选、多选、"显示未关联峰"、条目详情 | `candidate_list.py` | 与 `Project` 集成 |
| **T6.8** | 已选相后自动重算 FoM（残差峰驱动） | `residual_update.py` | 选中一相后，剩余候选 FoM 更新正确 |
| **T6.9** | ⭐ **L3 验收**：在 `tests/fixtures` 上跑，与 `reference_baseline.json` 对比 **Top-10 命中率** | `tests/search/test_baseline.py` | **Top-10 命中率 ≥ 参考软件 基线的 80%** |
| **T6.10** | 权重标定：用标准样品集反推一组最优默认权重（网格搜索/贝叶斯） | `tune_weights.py` | 命中率提升有量化记录 |

---

## Phase 7 · 限制条件 Restraints（`core/search/restraints.py`）

> 参考：`restraints*.md`（9 篇）

| ID | 任务 | 输出 | 验收标准 |
|---|---|---|---|
| **T7.1** | 元素组成限制（三态语义）+ 与倒排索引结合剪枝 | `restr_elements.py` | 设"排除某元素"后该元素条目 100% 剔除 |
| **T7.2** | 晶系 / 空间群限制 | `restr_crystal.py` | 过滤正确 |
| **T7.3** | 衍射限制 d 值/峰位 | `restr_diffraction.py` | 加入指定峰位后候选必含该峰 |
| **T7.4** | 物理性质：密度、颜色 | `restr_properties.py` | 区间过滤正确 |
| **T7.5** | 文献限制：作者、期刊、年份、CODEN | `restr_bibliography.py` | 匹配正确 |
| **T7.6** | 子文件限制（无机/有机/质量标记，对标 `.mtb` 位图语义） | `restr_subfile.py` | 分类正确 |
| **T7.7** | 组合应用 + 剪枝性能（限制应在检索**前**生效） | `apply.py` | 加限制后检索不慢于无限制 |

---

## Phase 8 · 定量分析（`core/quant/`）

| ID | 任务 | 输出 | 验收标准 |
|---|---|---|---|
| **T8.1** | **RIR（Reference Intensity Ratio）法**：I/Ic 归一 + 绝热法 | `rir.py` | 二元混合物（已知配比 50/50）定量误差 <3 wt% |
| **T8.2** | 内标法（已知量内标物） | `internal_standard.py` | 误差 <2 wt% |
| **T8.3** | 基于 Rietveld 的定量（依赖 Phase 10） | `rietveld_quant.py` | 误差 <1.5 wt% |
| **T8.4** | 非晶含量/结晶度 DOC（对标 Degree of Crystallinity） | `doc.py` | 与已知结晶度样品对比误差 <5% |

---

## Phase 9 · 指标化 Indexing（`core/index/`）

> 参考：`indexing*.md`（4 篇）。Treor / Dicvol 为公开发表算法，有开源实现可参考

| ID | 任务 | 输出 | 验收标准 |
|---|---|---|---|
| **T9.1** | 峰位 → d 值 → 晶面指标候选；七晶系面间距公式 | `lattice.py` | 各晶系公式与标准教科书一致（单测） |
| **T9.2** | **Treor** 试探法（trial-and-error）实现 | `treor.py` | 已知结构（如 LaB6 立方）指标化成功 |
| **T9.3** | **Dicvol** 二分法穷举实现 | `dicvol.py` | 同上；给出 M(n)/F(n) 品质因数 |
| **T9.4** | 结果排序、去同构解、与参考库对照验证 | `solutions.py` | 正确解排在前 5 |

---

## Phase 10 · 精修（`core/refine/`）

| ID | 任务 | 输出 | 验收标准 |
|---|---|---|---|
| **T10.1** | 峰形模型：pseudo-Voigt + 不对称 + Caglioti 宽度模型（U,V,W）+ 轴向发散 | `peak_model.py` | 与文献公式一致 |
| **T10.2** | 结构因子计算：原子散射因子（国际表近似）、温度因子、多重性、Lorentz-Polarization。**用 `pymatgen` / `diffpy.structure` 作交叉验证基线**（仅验证，不作运行时依赖） | `structure_factor.py` | 自算结果与 pymatgen 偏差 <0.5%；与已知计算谱对比 R <1% |
| **T10.3** | **Le Bail 分解**：迭代分配重叠峰强度 | `le_bail.py` | 收敛；Rwp <10% |
| **T10.4** | **Rietveld 精修**：最小二乘 + 参数约束（缩放、晶胞、峰宽、零點、原子坐标/占位/Uiso） | `rietveld.py` | 标准样品 Rwp <8%，Rp <6%，χ² 合理 |
| **T10.5** | 残差计算与残差峰分析（Peak Residuals） | `residuals.py` | 残差谱正确 |
| **T10.6** | **FullProf 适配层**（对标 refinements_FullProf）：生成 .pcr、调用、解析 .out/.prf | `fullprof_adapter.py` | 能驱动已安装的 FullProf 完成一轮精修 |
| **T10.6b** | ⭐ **GSAS-II 适配层**（优先级**高于** FullProf）：GSAS-II 是 Python 编写，可嵌入式集成而非进程调用，且开源可研读作为算法参考 | `gsas2_adapter.py` | 能完成一轮精修；结果与 FullProf 交叉一致 |
| **T10.7** | 策略化精修（参数逐步开启，对标 Parameter Turn-On） | `turn_on.py` | 参数顺序可配；收敛率提升有记录 |

---

## Phase 11 · 微结构分析（`core/micro/`）

| ID | 任务 | 输出 | 验收标准 |
|---|---|---|---|
| **T11.1** | Scherrer 晶粒尺寸（含仪器宽度校正，对标 Instrumental Standards） | `crystallite_size.py` | 用 LaB6 标样校正后，NIST 标样尺寸误差 <15% |
| **T11.2** | 微观应变（Williamson-Hall 图） | `microstrain.py` | 线性拟合正确 |
| **T11.3** | 结晶度 DOC（若 T8.4 未实现） | `doc.py` | 见 T8.4 |

---

## Phase 12 · 报告与导出（`core/report/`）

| ID | 任务 | 输出 | 验收标准 |
|---|---|---|---|
| **T12.1** | 报告数据模型：样品信息、实验条件、峰表、候选列表、已选相、定量结果、R 因子 | `report_model.py` | 覆盖 参考软件 报告的全部章节 |
| **T12.2** | 渲染器：HTML（默认）+ PDF（WeasyPrint）+ 纯文本 | `render.py` | 三种格式均可生成且内容一致 |
| **T12.3** | 图谱图片导出（PNG/SVG/EPS，高 DPI） | `figure_export.py` | 300 dpi 输出清晰；SVG 矢量可用 |
| **T12.4** | 剪贴板/图片复制（对标 Copy Pattern Graphics） | `clipboard.py` | Windows 剪贴板写入成功 |

---

## Phase 13 · GUI（`ui/` · PySide6）

> 只有到这一步才碰 GUI。前面所有 `core/` 已可 CLI 验证。

| ID | 任务 | 输出 | 验收标准 |
|---|---|---|---|
| **T13.0** | ⭐ **GUI 架构决策：PySide6 原生主框架 + QWebEngineView 嵌入**（仅用于 3D 结构、报告富文本、帮助浏览）。菜单/停靠面板/表格/图谱一律原生 Qt，不用 Web 重做 | `ui/app.py` | 主界面全原生；3D 与报告区域为 Web 容器 |
| **T13.1** | 主窗口骨架：菜单栏（对标 参考软件 菜单结构）、工具栏、状态栏、四个停靠面板 | `ui/main_window.py` | 菜单项与 `FUNCTION_MAP.md` 一一对应 |
| **T13.2** | **图谱视图（pyqtgraph）**：多谱叠放、垂直/水平偏移、缩放/拖拽/追踪、图例 | `ui/pattern_view.py` | 5 万点实时缩放不掉帧；十字光标追踪 |
| **T13.3** | 峰列表 / 候选列表 / 匹配列表 三个表格（排序、右键菜单、双击选中） | `ui/tables.py` | 交互与 参考软件 一致 |
| **T13.4** | **周期表元素选择控件**（Restraints/Composition 标签页，红/黄/绿三态） | `ui/periodic_table.py` | 118 元素，三态切换 + Toggle 按钮 |
| **T13.5** | 各功能对话框：导入选项、实验详情、选项设置（15 类）、颜色线型设置 | `ui/dialogs/` | 每类设置可持久化到配置文件 |
| **T13.6** | 快捷键映射（对标 `function_keys.md`：Ctrl+M、Ctrl+Shift+M、Ctrl+Shift+K…） | `ui/shortcuts.py` | 全部列出并生效 |
| **T13.7** | 样式主题：浅色/深色，图标资源**自绘或用开源图标**（不复制 参考软件 图标） | `ui/theme.py` | 两种主题无控件不可读 |

> ⚠️ **图标与视觉资源必须原创或使用开源图标（如 KDE Breeze / Lucide）**，不得复制 参考软件 的 `参考软件图标` 或帮助文档内嵌截图。

---

## Phase 14 · 批处理与脚本（`cli/`）

| ID | 任务 | 输出 | 验收标准 |
|---|---|---|---|
| **T14.1** | CLI：`xinmatch import → process → search → quantify → report` 一条龙 | `cli/main.py` | 对标准样品集批量跑通，输出 JSON/报告 |
| **T14.2** | Python API（供二次开发） | `xinmatch/__init__.py` | 文档字符串完整；有 3 个示例脚本 |
| **T14.3** | 批处理脚本语言（对标 Batch Scripting），先支持 JSON/YAML 配置驱动 | `cli/batch.py` | 配置可复现全流程 |
| **T14.4** | 串口仪器控制（对应 参考软件 的 Qt5SerialPort 能力，P2 可选）：串口配置、数据采集、实时图谱 | `cli/instrument.py` | 能接收串口数据流并实时绘制 |

---

## Phase 15 · 打包与发布

| ID | 任务 | 输出 | 验收标准 |
|---|---|---|---|
| **T15.1** | PyInstaller/Nuitka 打包 Windows x64 安装包 | `dist/` + Inno Setup 脚本 | 干净虚拟机可安装运行 |
| **T15.2** | 数据库分发：COD SQLite 单独下载（体积大，不放安装包） | 下载器 | 首次启动引导下载 |
| **T15.3** | 用户文档（基于自写内容，**不复制** 参考软件 手册） | `docs/user_guide/` | 覆盖全部功能 |
| **T15.4** | 开源协议与合规审查：确认全部依赖许可（PySide6 LGPL、gemmi MIT、NumPy BSD…） | `LICENSE`、`NOTICE` | 无 GPL 传染性依赖（注意：避免引入 GPL 库） |
| **T15.5** | Linux（AppImage/deb）+ macOS（dmg）打包 | `dist/` 多平台产物 | 两平台可安装运行；T0.7 的跨平台约定生效 |

---

## Phase 16 · 晶体结构可视化（`ui/structure3d/`）

> 采用 **QWebEngineView + Three.js / WebGL** 嵌入 PySide6。理由：参考软件 自身也内置 QtWebEngineCore(102 MB)，
> 说明"原生壳 + Web 承载 3D"是这类软件的实际选择；且 Web 3D 生态远好于 Qt3D。

| ID | 任务 | 输出 | 验收标准 |
|---|---|---|---|
| **T16.1** | 3D 结构渲染：球棍模型、多面体模型、空间群对称操作展开、旋转/缩放/平移 | `ui/structure3d/view.py` + Web 前端 | 钙钛矿/沸石等复杂结构渲染正确，对称展开与空间群一致 |
| **T16.2** | 晶面（hkl）显示、取向切换、高质量图片导出（PNG/SVG） | `ui/structure3d/planes.py` | 指定 (111) 面显示正确 |
| **T16.3** | 与精修联动：Rietveld 精修后实时更新结构显示 | `ui/structure3d/bridge.py` | 精修一轮后结构自动刷新 |

---

## 关键路径与并行建议

```
T0 ──> T1 ──> T2 ──> T3 ──> T4 ──┐
                                  ├──> T5 ──> T6.0 ──> T6 ──> T9 ──> T10 ──> T8 ──> T11
              T1 ──> T7 ──────────┘                                                  │
                                                                                     v
                                                                  T12 ──> T13 ──> T14 ──> T15
                                                                            │
                                                                            └──> T16（3D 可视化）
```

**可并行（互不阻塞，适合多 Agent 同时开工）**：
- 组 A：T2（I/O，纯解析，无依赖）
- 组 B：T3+T4（预处理+寻峰）
- 组 C：T5（数据库，可先于 T6 完成）
- 组 D：T9（指标化，算法独立）

**必须串行**：T6（Search-Match）依赖 T4 的峰 + T5 的库；T8 的 Rietveld 定量依赖 T10。

---

## 每个阶段的"可验证"检查点

| 阶段 | 检查点命令/动作 | 通过标志 |
|---|---|---|
| P0 | `pytest tests/baseline --collect-only` | 标准样品集与 参考软件 基线齐备 |
| P1 | `pytest tests/model -q` | 数据模型全绿 |
| P2 | `pytest tests/io -q` | 33 种格式 round-trip 全绿 |
| P3 | 对 `LaB6_Cu_Ka1.dat` 跑自动流水线 | 峰位与 NIST 标准值偏差 <0.01° |
| P4 | 合成谱拟合测试 | Rwp <2% |
| P5 | LaB6 检索 | 正确 entry 进 Top-100 |
| P6 | `pytest tests/search/test_baseline.py` | **Top-10 命中率 ≥ 基线 80%** |
| P7-P11 | 各自数值回归测试 | 见各任务验收标准 |
| P13 | 人工按 参考软件 手册操作 XinMatch 完成一次完整物相分析 | 结果一致 |
| P16 | 加载一个复杂结构（如沸石），检查对称展开与晶面显示 | 与 Diamond/VESTA 显示一致 |

---

## 风险登记

| 风险 | 影响 | 缓解 |
|---|---|---|
| FoM 内部权重未公开 → 排序无法 100% 复现 | L3 兼容性受限 | 以 Top-N 命中率验收；T6.10 用数据标定权重 |
| COD 数据质量参差（含错误条目） | 误匹配 | 建立质量标记字段，默认过滤低质量条目 |
| 缺少真实多样品测试数据 | 无法验证 | **T0.3 是最高优先级**，务必先做 |
| pyqtgraph 大数据性能 | 交互卡顿 | 降采样（LTTB 算法）+ OpenGL |
| 50 万条目全检索性能 | 慢 | 倒排索引剪枝 + Numba + 预过滤（强峰必中） |
| 引入 GPL 依赖导致协议冲突 | 法律风险 | T15.4 严格审查；优先 MIT/BSD/LGPL |
| 误复制 参考软件 视觉资源 | 版权风险 | 图标/文档一律原创 |

---

## AI Agent 角色分工

| 角色 | 负责 Phase | 技能要求 | 可并行度 |
|---|---|---|---|
| **数据工程师** | P2（I/O）、P5（数据库）、T5.9 | Python、二进制格式解析、SQLite 索引设计 | 高，可 2 个 agent |
| **算法工程师（预处理）** | P3、P4 | SciPy.signal、最小二乘、峰形函数 | 中 |
| **算法工程师（检索）** | P6、P7 | 检索算法、Numba 向量化、最优化 | 中（依赖 P4+P5） |
| **算法工程师（精修）** | P9、P10、P11 | 晶体学、Rietveld/Le Bail、lmfit | 高（与检索组并行） |
| **算法工程师（定量）** | P8 | RIR、内标法、统计 | 低（依赖 P10） |
| **前端工程师** | P13、P16 | PySide6、pyqtgraph、Three.js | 中 |
| **集成工程师** | P12、P14、P15 | 报告生成、CLI、打包 | 低（收尾） |
| **测试工程师** | 全阶段 | pytest、数值回归、基线比对 | 贯穿 |

> 每个 agent 开工前**必读**：`docs/00_TECH_STACK_ANALYSIS.md`（合规边界）+ `docs/01_方案对比与补充.md`（已纠正的误区）+ 本任务对应的 `docs/third-party-help/<topic>.md`。

---

## 里程碑（时间轴按 6-10 月排，非 12-18 周）

| 里程碑 | 相对时间 | 交付物 | 验收标准 |
|---|---|---|---|
| **M0 知识基座** | 第 2-4 周 | 标准样品集 + 参考软件 基线 + 文档库 | T0.3/T0.4 完成，Phase 6 可验收 |
| **M1 数据层** | 第 8 周 | 33 种格式解析器 + 数据模型 | `pytest tests/io` 全绿 |
| **M2 预处理与寻峰** | 第 12 周 | 自动流水线 + Profile Fitting | LaB6 峰位偏差 <0.01°，Rwp <2% |
| **M3 数据库** | 第 14 周 | COD → SQLite 全量 + 倒排索引 | 单次检索 <1 s |
| **M4 物相鉴定** | 第 20 周 | Search-Match + Restraints + PFSM | **Top-10 命中率 ≥ 基线 80%** |
| **M5 高级分析** | 第 28 周 | 指标化 + Le Bail/Rietveld + 定量 + 微结构 | Rwp <8%，定量误差 <3 wt% |
| **M6 产品化** | 第 36 周 | GUI + 3D 可视化 + 报告 + CLI | 可按 参考软件 手册完成完整分析 |
| **M7 发布** | 第 40 周 | 三平台安装包 + 文档 + 合规审查 | 干净环境可安装运行 |

> 为什么不是 12-18 周：见 `docs/01_方案对比与补充.md` §2.2。参照 GSAS-II、Profex、FullProf 的实际投入，
> 12-18 周只能产出演示原型，达不到"全兼容"。

---

## 立即可以开始的第一步

1. **T0.3 / T0.4**（最高优先级）：建标准样品集 + 跑 参考软件 基线。没有这个，Phase 6 无法验收。
2. **T0.2**：安装最新版到独立目录，跑 `tools/extract_help.py` 看版本差异。
3. **并行启动组 A（T2 I/O）**：纯解析工作，规格文档已就位，AI agent 可立即开工。
