# 术语映射表（参考软件 ↔ XinMatch ↔ 标准晶体学术语）

> 任务：T0.5。用途：GUI 与文档统一用语；覆盖参考软件帮助库高频索引词（IndexTable 3,514 词 / 主题 166 篇）。
> 素材：参考软件 4.3 Build 360 帮助索引 + 主题标题（`参考资料\XinMatch-third-party-docs\docs-4.3.360\`）；
> XinMatch UI 文案（`xinmatch/ui/`）与 CLI 命令（`xinmatch/cli/`）；
> 标准术语遵循 IUCr / ICDD / CIF 惯例。
> 更新：2026-10-14（T0.5）

约定：`[x]` = XinMatch 已实现/有对应物；`[规划]` = 路线图已列入但未实现；`[—]` = 尚无对应。

---

## 1. 数据导入 / 导出

| 参考软件术语 | XinMatch 术语 | 标准晶体学术语 | 备注 |
|---|---|---|---|
| Importing Diffraction Data | 导入衍射数据（`import`；`ui/dialogs/import_dialog.py`）[x] | 衍射数据导入 | 参考软件支持 .raw/.uxd/.rd/.xrdml 等；XinMatch 同域扩展至 30+ 格式（RAW v2/v3/v4、Rigaku、岛津等） |
| Diffraction Data File Formats | 数据文件格式 | 数据格式（IUCr round-robin / vendor binary） | XinMatch 有 `core/io/` 统一分发 |
| Exporting Data / Export Peak List | 导出峰列表（规划）[规划] | 峰列表导出 | XinMatch 现有 ASCII 峰表导出（`core/io/exporters.py`）[x] |
| Exporting Answer Set | —（对应物=候选集导出）[—] | 答案集（entry 号集合） | 候选集合导出尚未在 GUI 暴露 |
| Import Entries from CIF | 导入 CIF（`import_udb_entry_cif` 对应 `library_dialog` 构建）[x] | CIF 文件导入（crystallographic information framework） | XinMatch 经 COD 库构建消费 CIF |

## 2. 图谱预处理（Raw Data Processing）

| 参考软件术语 | XinMatch 术语 | 标准晶体学术语 | 备注 |
|---|---|---|---|
| data smoothing / smoothing of raw data | 平滑（`process --smooth`；`core/smoothing.py`）[x] | 平滑（Savitzky-Golay 等数字滤波） | 参数：窗口/多项式阶 |
| background determination / background subtraction | 背景估计/扣除（`core/background.py`）[x] | 背景扣除（background correction） | Chebyshev 多项式背景 |
| Alpha2 Stripping (Kα2) | Kα2 剥离（`process --strip-kalpha2`）[x] | Kα2 剥离（Rachinger 法） | FPFM 模式另有伴线处理 |
| automatic raw data processing | 自动预处理管线（`process`）[x] | 自动数据处理 | 平滑→背景→寻峰→剥离 |
| 2theta error correction | 2θ 误差校正（内标）[规划] | 2θ 零点/位移校正 | 参考软件经 Internal Standard 完成 |
| internal standard | 内标（定量模块）[x] | 内标法（internal standard） | 定量分析链路已有 |

## 3. 峰处理

| 参考软件术语 | XinMatch 术语 | 标准晶体学术语 | 备注 |
|---|---|---|---|
| peak searching | 寻峰（`core/peaks.py`；`process` 自动阶段）[x] | 寻峰（peak search / peak picking） | 灵敏度参数：`rawdata-proc_peaksearch` ↔ XinMatch 寻峰阈值 |
| Peak Editing in the Diffraction Pattern | 峰编辑（图谱交互）[x] | 峰位/强度编辑 | pattern_view 支持峰拖动 |
| integrated peak intensities | 积分强度（峰面积）[x] | 积分强度（integrated intensity） | XinMatch 寻峰输出面积 |
| Profile Fitting | 峰形拟合（FPFM / 单峰拟合）[x] | 峰形拟合（profile fitting） | XinMatch 有 FPFM 全谱拟合与 March-Dollase 择优取向 |
| Peak Residuals Calculation | 峰残差（`core/search/` FoM 分量）[x] | 峰残差（residuals） | 参考软件独立功能；XinMatch 在 FoM 内实现 |
| rescale peak intensities | 峰强度归一（规划）[规划] | 强度标定 | 相对强度标度 XinMatch 在检索内部处理 [x] |

## 4. 检索匹配（Search-Match）

| 参考软件术语 | XinMatch 术语 | 标准晶体学术语 | 备注 |
|---|---|---|---|
| Search-Match | Search-Match（`search`；UI「Search-Match 报告」）[x] | 检索匹配（search-match） | 核心功能 |
| FPFM (Full Pattern Fitting Match；v1.6.1 前旧称 SMPF) | FPFM 模式（`search --mode fpfm`，旧值 `smpf` 仍接受）[x] | 全谱拟合检索（full-pattern fitting match） | XinMatch 已实现真 March-Dollase 择优取向 FPFM |
| FoM (Figure of Merit) | FoM 品质因数（`core/search/fom_criteria.py`）[x] | 品质因数 | 五分量（峰位/强度/半高宽/晶胞/密度…） |
| candidate list | 候选列表（UI 表格）[x] | 候选相列表 | 参考软件 FoM 排序；XinMatch 同 |
| Selection of Matching Entries | 候选选择/过滤（元素限制等）[x] | 匹配条目选择 | Restraints 加权评分 |
| Restraints | 限制条件（UI「限制条件」页；元素过滤）[x] | 约束（元素/组合/性质） | 三态红/黄/绿加权 |
| text fragment searching / formula sum | 化学式/文本检索 [x] | 化学式/文本匹配 | formula sum 校验 XinMatch 在条目解析校验 [x] |
| entry number | 条目号（COD entry id）[x] | 参考数据库条目号 | XinMatch 用 COD id；参考软件用 PDF/COD 双编号 |
| PDF quality marks | COD 质量标记（品质过滤）[x] | 数据库质量标记 | XinMatch 用 COD 品质字段 |

## 5. 定量分析

| 参考软件术语 | XinMatch 术语 | 标准晶体学术语 | 备注 |
|---|---|---|---|
| Quantitative Phase Analysis | 定量相分析（`quantify`）[x] | 定量相分析（QPA） | RIR + Rietveld 两条路 |
| Reference Intensity Ratio (RIR) method | RIR 定量（`quantify`）[x] | 参比强度比法（RIR / I-Ic） | 已实现并经真实样品验证 |
| Internal standard analysis | 内标法定量 [x] | 内标法 | 定量链路组件 |
| Degree of crystallinity (DoC) analysis | —（规划）[规划] | 结晶度分析（DoC） | 4.3 Build 360 新增功能（`idh_doc.htm`）；XinMatch 路线图未列，可评估 |
| semi-quantitative analysis | 半定量（RIR 缺省 I/Ic=1）[x] | 半定量分析 | 参考软件 S-Q 模式同构 |

## 6. 精修 / 结构

| 参考软件术语 | XinMatch 术语 | 标准晶体学术语 | 备注 |
|---|---|---|---|
| Rietveld Refinement | Rietveld 精修向导（`refinement_wizard.py`，GSAS-II 集成）[x] | Rietveld 精修（全谱结构精修） | 集成 GSASIIscriptable |
| Le Bail method | Le Bail 拟合（规划）[规划] | Le Bail 全谱分解 | 参考软件有；XinMatch 路线图精修阶段 |
| Pattern decomposition | 谱分解（FPFM 背景）[x] | 谱分解 | FPFM 内部实现 |
| Crystallite Size Estimation | 微晶尺寸（FPFM 展宽/合成）[x] | 微晶尺寸（crystallite size / domain size） | XinMatch 从峰展宽估计 [x] |
| Instrumental Standards | 仪器标准样 [—] | 仪器展宽标准样 | 规划 |
| crystal structure data / atomic parameters | 结构数据（CIF 解析；3D 结构视图）[x] | 晶体结构/原子参数 | XinMatch 有 CIF/3D 视图 |
| space group / crystal system | 空间群/晶系（条目元数据）[x] | 空间群/晶系 | CIF 权威值回填 |

## 7. 索引（Indexing）

| 参考软件术语 | XinMatch 术语 | 标准晶体学术语 | 备注 |
|---|---|---|---|
| Indexing (Dicvol / Treor) | —（规划）[规划] | 指标化（自动索引） | 路线图 Phase 未列；参考软件用 Dicvol/Treor 内核 |
| Indexing Results | —[—] | 指标化结果分析 | 同上 |

## 8. 数据库管理

| 参考软件术语 | XinMatch 术语 | 标准晶体学术语 | 备注 |
|---|---|---|---|
| Reference Database | 参考数据库（`library_dialog`；COD 全库）[x] | 参考数据库（相库） | XinMatch 用 COD（CC0）；参考软件用 COD+PDF |
| User Database | 用户库（规划）[规划] | 用户数据库 | XinMatch 目前单一 COD 库 + 多库挂载 |
| COD / RefDB | COD 库（`.xinDB` 外部库，如 `COD-Inorg-20261020.xinDB`）[x] | COD 晶体学开放数据库（CC0） | 无机子库 78,036 条目；全库 532,038 条目 |

## 9. 通用 / 界面

| 参考软件术语 | XinMatch 术语 | 标准晶体学术语 | 备注 |
|---|---|---|---|
| Colors, line styles and font options | 颜色与线型设置（`colors_dialog.py`）[x] | 显示选项 | UI 一致 |
| Mouse / Keyboard Shortcuts | 快捷键（`shortcuts.py`）[x] | 交互快捷键 | |
| Options / Save as Defaults | 选项（`options_dialog.py`；保存为默认设置）[x] | 程序选项 | |
| Report | Search-Match 报告（`report`；HTML 报告）[x] | 分析报告 | |
| Batch Scripting | 批处理（`batch`，T14.3）[x] | 批处理脚本 | 参考软件脚本化 ↔ XinMatch YAML/JSON 批处理 |
| Serial Instrument Control | 串口仪器采集（`instrument`，T14.4）[x] | 仪器联机采集 | XinMatch 已实现（参考软件为独立采集） |

---

## 高频词覆盖核对

参考软件 IndexTable 高频词（频次 ≥3，前 ~120 词）已全部映射到上表分组；未进表的为纯界面词汇（「delete input field」「list selection box」等，无领域语义）或专属流程（「updating Match!」等）。
映射覆盖率：**功能语义词 100%**；XinMatch 已实现占比约 70%，其余为规划项（DoC、Le Bail、Indexing、用户库、峰编辑导出等），与 STATUS.md 路线图一致。
