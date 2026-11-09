# XinMatch 逆向分析：参考软件 4 技术栈勘察报告

> 目标软件：参考商业粉末 XRD 物相分析软件（Version 4.2 Build 329, Win64）
> 厂商：Crystal Impact, H. Putz & K. Brandenburg GbR, Bonn, Germany
> 勘察日期：2026-10-06 ｜ 勘察对象：`参考软件安装目录`（4.2.329）+ 最新版安装包（374 MB）

---

## 0. 结论先行

| 维度 | 结论 |
|---|---|
| **是什么** | 粉末 X 射线衍射（XRPD）物相定性/定量分析软件，非 EBSD/电子衍射 |
| **GUI 框架** | **Qt 5.15.2**（MSVC 2019, 64-bit），QtWidgets + QtWebEngine + QtCharts + QtHelp |
| **主程序规模** | `参考软件主程序` 15.1 MB（单文件，无符号、无 PDB） |
| **许可证** | EULA **明文禁止反汇编/反编译**（见 §1） |
| **数据库** | 自研私有倒排索引格式（`.mti/.mqn/.mqs/.mtb`），469 MB，28 个检索字段 |
| **最高效的逆向路径** | **不是反汇编，而是「官方文档 + 黑盒 + 公开算法 + 开放数据」**（见 §4） |
| **数据库这层** | **完全不需要逆向** —— COD 是 CC0 开放数据，可直接用官方源 |

---

## 1. 合规边界（必须先定，决定技术路线）

安装目录下的 `license_info.txt` **第 2 条 b 款**原文：

> **"Reverse engineering: You are not permitted to disassemble or reverse compile the Software Product for the purpose of reverse engineering."**

因此本项目**明确不做**两件事：

| ❌ 不做 | 原因 |
|---|---|
| 反汇编 / 反编译 `参考软件主程序` | EULA 明文禁止；且这是合同条款，用户安装时已同意 |
| 逆向 / 绕过 `LicenseManager.exe`（60 天试用、授权校验） | 与构建开源替代品无关，且不可规避 |

（补充背景：德国法下为**互操作性**目的的逆向受 `UrhG §69e` 保护，且 `§69g(2)` 规定与之抵触的合同条款无效——所以严格讲该条款在德国未必可执行。但这是你自己的法律判断，且**即便合法，反汇编也是性价比最低的路线**，理由见 §4.1。）

本项目**明确要做**的四件事，全部合法且效率更高：

| ✅ 做法 | 依据 |
|---|---|
| 读取安装目录下的官方文档（`Manual.pdf` 165 页、`参考软件官方帮助数据库(.qch)` 帮助系统） | 文档是随软件分发的用户文档，读取不构成逆向 |
| 黑盒行为观察：运行软件 → 输入数据 → 记录输出 | 纯观察，不涉及二进制 |
| 分析**数据文件格式**（`.rd/.udi/.mtu/.raw/.xrdml`…） | 互操作性目的；且用于读写用户自己的数据 |
| 用**公开发表的学术算法**重新实现（Rietveld / Le Bail / Treor / Dicvol / RIR / Scherrer） | 算法本身是公开科学知识，不受软件著作权保护 |

> 这套方法就是业界所称的 **净室设计（Clean Room Design）**：规格来自文档与可观察行为，代码从零书写。
> 先例：Wine（Windows API）、ReactOS、Linux 的 Samba、GSAS-II、Profex。

---

## 2. 技术栈勘察结果（实测）

### 2.1 运行时依赖

```
Qt5Core.dll / Qt5Gui.dll / Qt5Widgets.dll   ← Qt 5.15.2，编译日期 2020-11-06
Qt5WebEngineCore.dll (102 MB)               ← 报告/帮助用内嵌 Chromium 渲染
Qt5Charts.dll                               ← 图表
Qt5Help.dll + 参考软件官方帮助数据库(.qch)/.qhc               ← 帮助系统（SQLite 格式）
Qt5Sql.dll + qsqlite/qsqlodbc/qsqlpsql      ← 数据库访问
Qt5PrintSupport.dll / Qt5Svg.dll
D3Dcompiler_47.dll / libGLESv2.dll / opengl32sw.dll   ← ANGLE 软件渲染
VC_redist.x64.exe                           ← MSVC 2019 运行库
```
`qt.conf`: `[Platforms] WindowsArguments = dpiawareness=0`

**判定**：C++ / Qt Widgets / MSVC 2019 / 单进程单体架构。这是 2003 年延续至今的老代码库（Readme 版权 2003-2025）。

### 2.2 进程结构

```
参考软件主程序          主程序（15.1 MB）
LicenseManager.exe  独立授权管理进程（1.1 MB）
assistant.exe       Qt Assistant（帮助查看器）
QtWebEngineProcess.exe  Chromium 子进程
```

### 2.3 参考数据库 `RefDB_COD/`（469 MB，48 个文件）

Crystal Impact 自研的**倒排索引**数据库，扩展名规律清晰：

| 扩展名 | 作用 | 示例文件 |
|---|---|---|
| `.mti` | **索引表**（倒排索引 / 数值索引） | `ele.mti`(元素) `cella/b/c.mti`(晶胞) `dcalc/dmeas.mti`(d值) |
| `.mqs` | **字符串池**（换行分隔的去重字符串） | `author.mqs` `formstr.mqs` `mineral.mqs` |
| `.mqn` | **编号表**（指向 `.mqs` 的整数偏移，文本） | `author.mqn` |
| `.mtb` | **位图**（标记位，如是否无机） | `inorg.mtb` `ecc.mtb` `qualsub.mtb` |
| `.mtn` | **元信息**（数据库描述） | `MatchRefDBInfo.mtn` |
| `.mtu` | 用户数据库模板 | 1 个 |

**文件实测计数**：`26 .mti` + `8 .mqn` + `8 .mqs` + `4 .mtb` + `1 .mtn` + `1 .mtu` = **48 个**。

**32 个检索字段**（文件名去重后）：
```
author  cella cellal cellb cellbe cellc cellga  coden  color  crysys
dbcont  dcalc dmeas  ecc   elc    ele   entry_seq  formstr  inorg
journal MatchRefDBInfo  mineral name  patternindex  peakindex  pressure
qualsub seq_fpoint  sgrsym  temperature  user_database  year
```

即：**元素组合 / 晶胞参数 / d 值 / 分子式 / 矿物名 / 作者 / 期刊 / 年份 / 空间群 / 颜色 / 压力 / 温度 / 密度** 的多维倒排检索 + 无机/有机等位图过滤。这是 ICDD 经典检索逻辑的私有实现。

> **战略结论**：这层**不需要逆向**。COD 数据库本身是 **CC0 公开数据**，你已有 `cod-cifs-mysql.txz`（官方 dump）和 Profex 的 `cod-250127.db3`（SQLite, 1.4 GB，由 Nicola Döbelin 公开维护）。
> XinMatch 直接用 COD 官方源自建 SQLite + 索引，** legally clean 且数据更新更及时**。

### 2.4 支持的衍射数据格式（官方文档实测，33 种）

**厂商格式（22）**：Bruker/Siemens `.raw` `.dif`、Bruker AXS `.brml`、DRON/G670 `.gdf`、GNR `.esg`、INEL `.dat`、Jade/MDI/SCINTAG `.mdi`、JEOL `.txt`、PANalytical/Philips `.rd` `.udf` `.udi`、Rigaku `.ras` `.raw`、SCINTAG `.raw/.rd`、Shimadzu `.raw`、Siemens `.uxd`、Sietronics `.cpi`、Stoe `.raw` `.pks`、TXRD `.txt`、XPowder `.plv`、`.xrdml`

**自由格式（6）**：DBWS `.rfl/.dat`、ASCII profile 三种变体、ENDEAVOUR peak list

**结构数据**：CIF、ICSD/Retrieve、参考软件 用户库 `.mtu`

### 2.5 功能模块（169 个帮助主题，自动分类）

### 2.5.1 功能权重（由 4076 条帮助索引关键词统计，合法替代二进制字符串提取）

| 术语 | 次数 | 术语 | 次数 |
|---|---|---|---|
| peak | 503 | crystal | 134 |
| pattern | 349 | refine | 125 |
| match | 257 | background | 117 |
| database | 229 | import | 107 |
| index | 212 | FullProf | 88 |
| Rietveld | 202 | PDF | 83 |
| phase | 193 | size | 67 |
| diffraction | 191 | candidate | 64 |
| export | 174 | report | 62 |
| entry | 164 | structure | 56 |
| search | 156 | quantitative | 54 |
| profile | 144 | restraints | 46 |

→ 印证 **峰处理 + 图谱匹配 + 数据库检索** 为三大核心。
（与另一方案的二进制字符串统计排名高度相关，且 `quantitative`=54、`I/Ic`=26 两项数值完全相同，详见 `01_方案对比与补充.md` §三。）

| 模块 | 主题数 | 模块 | 主题数 |
|---|---|---|---|
| 数据导入 | 10 | 用户数据库 UDB | 5 |
| **数据导出** | **16** | 指标化 Indexing（Treor/Dicvol） | 4 |
| 原始数据预处理 | 10 | Rietveld / Le Bail | 6 |
| 寻峰与峰列表 | 4 | 定量分析（RIR/内标/Rietveld） | 3 |
| Profile Fitting | 4 | 微结构（晶粒尺寸/结晶度 DOC） | 2 |
| **Search-Match 定性分析** | **13** | 报告与打印 | 4 |
| 限制条件 Restraints | 9 | **选项与设置** | **22** |
| 参考数据库 | 11 | 图形与交互 | 5 |
| | | 其他与基础（批处理、撤销等） | 41 |

### 2.6 核心算法（官方文档已披露原理）

**FoM（Figure-of-Merit）—— 峰基法**，加权求和 6 项判据：
1. 关联峰的 2θ 差值
2. 关联峰的强度差值
3. 已关联峰数 vs 未知谱总峰数之差
4. 已关联峰数 vs 应关联峰数之差
5. 参考峰强度的最优缩放因子
6. 权重由用户在 Search-Match 选项中设定的参数**内部推导**（用户不可直接调）

**FoM —— PFSM（Profile Fitting Search-Match）**：
对每条候选计算全谱 → 拟合强度缩放因子 + 2θ 偏移 → 取 **Rwp 降低量**作为 FoM。

**其余**：Le Bail 分解、Rietveld（调用外部 FullProf）、Treor/Dicvol 指标化、RIR 与内标定量、Scherrer 晶粒尺寸、结晶度 DOC。

---

## 3. 反汇编路线的成本测算（为什么不走这条路）

| 障碍 | 具体代价 |
|---|---|
| 无符号、无 PDB | `参考软件主程序` 15.1 MB，静态链接 Qt 部分符号，但业务符号全部缺失 |
| C++ 虚表 + RTTI | 类继承关系需逐个重建，Qt moc 信号槽为字符串表间接调用 |
| 20+ 年累积代码 | 版权 2003-2025，大量历史分支、兼容代码、死代码 |
| Qt 5.15 静态/动态混合 | 需先剥离 Qt 库函数（约 90% 的反汇编体量是 Qt 框架而非业务逻辑） |
| 有效业务代码定位 | 需在 15 MB 中定位真正的物相分析逻辑，比例可能 <5% |
| **综合** | **收益极低、法律风险明确、工期以人年计** |

对照：官方文档已给出 FoM 判据构成、PFSM 原理、工作流、全部参数含义 —— **信息密度远高于反汇编得到的东西**。

---

## 4. 推荐技术栈

### 4.1 选型

| 层 | 选型 | 理由 |
|---|---|---|
| 语言 | **Python 3.11+** | 科学计算生态最强；GSAS-II 同栈；C 扩展可后补 |
| GUI | **PySide6 (Qt 6, LGPL)** | 与 参考软件 同源 Qt → 外观/交互/快捷键天然贴近；LGPL 可商用 |
| 图谱渲染 | **pyqtgraph** | XRD 谱可达数万点，需 OpenGL 级缩放/拖拽；matplotlib 交互不够 |
| 数值 | **NumPy + SciPy** | `scipy.optimize.least_squares` 做精修；`scipy.signal` 做平滑/寻峰 |
| 加速（二期） | **Numba / Cython** | FoM 需遍历数十万条 entry，纯 Python 会慢 |
| 参考数据库 | **SQLite**（自建模 + 索引） | Profex 的 `cod.db3` 即为 SQLite，schema 可借鉴；单文件易分发 |
| CIF 解析 | **gemmi** | 晶体学标准库，MIT 许可，支持 mmCIF/PDBx |
| 拟合内核（可选） | **lmfit** | 参数约束语法友好，适合精修参数管理 |
| 测试 | **pytest + hypothesis** | 算法需数值回归测试 |
| 打包 | **PyInstaller / Nuitka** | 目标同样是 Windows x64 单机 |

### 4.2 为什么不用 C++ / Qt 复刻

虽然 参考软件 是 Qt/C++，但你做的是**新产品**而非**克隆**。Python 开发速度 3-5 倍，且核心热路径可用 Numba/Cython/C 扩展逐点优化。**先用 Python 打通算法正确性，再对瓶颈做加速** —— 这是唯一现实的工期路径。

### 4.3 架构分层（关键：内核与 GUI 解耦）

```
XinMatch/
├── core/                 # 纯计算内核 · 零 GUI 依赖 · 可 CLI 调用 · 可单测
│   ├── model/            Pattern / Peak / Phase / Entry / Restraints / Project
│   ├── io/               33 种衍射格式 + CIF + MTU + 项目文件
│   ├── preprocess/       平滑 背景 Kα2剥离 零点 位移 Trim 分辨率提升
│   ├── peak/             寻峰 Profile Fitting 峰编辑
│   ├── db/               参考数据库 SQLite 构建 + 倒排索引 + 检索
│   ├── search/           FoM Search-Match PFSM Restraints
│   ├── index/            Treor / Dicvol 指标化
│   ├── refine/           Le Bail / Rietveld（+ FullProf 适配层）
│   ├── quant/            RIR / 内标 / Rietveld 定量
│   ├── micro/            Scherrer 晶粒尺寸 / 微观应变 / 结晶度 DOC
│   └── report/           报告数据模型
├── ui/                   # PySide6 GUI（只做展示与事件，不含算法）
├── cli/                  # 批处理 / 脚本接口（对标 Batch Scripting）
├── tests/                # fixtures + 数值回归基线
└── docs/                 # 本目录：规格文档库
```

**为什么要解耦**：让每个 AI agent 能在无 GUI 环境下独立开发+验证一个 `core/` 模块（输入数组 → 输出数组 → pytest 断言）。GUI 最后统一接入。这是"小步骤可验证"能成立的前提。

---

## 5. "全兼容"的现实定义

不要追求 100% 逐位兼容。按 4 层拆解，**逐层设定可达目标**：

| 层级 | 目标 | 可行性 | 验收指标 |
|---|---|---|---|
| **L1 文件格式兼容** | 能读 参考软件 支持的格式，能写 参考软件 可读的文件 | ⭐⭐⭐⭐⭐ | 33 种格式双向 round-trip 测试通过 |
| **L2 参考数据库兼容** | 覆盖 COD；ICDD PDF 设计为「用户自带授权数据」插件 | ⭐⭐⭐⭐ | COD 条目数、检索字段对齐 |
| **L3 算法结果兼容** | FoM **数值**不可能一致（权重未公开），但**排序**必须可比 | ⭐⭐⭐ | 标准样品集上 **Top-10 命中率 ≥ 参考软件 的 80%** |
| **L4 UI/工作流兼容** | 术语、菜单结构、快捷键、操作路径一致 | ⭐⭐⭐⭐ | 用户可按 参考软件 手册操作 XinMatch |

> **L3 的关键判断**：FoM 绝对值无法复现（内部权重未公开且用户不可调）。
> 因此验收标准必须定为 **排序质量（Top-N 命中率 / 召回率）**，而非数值相等。
> 这需要在 Phase 0 就建立"标准样品集 + 参考软件 基线结果"作为黄金标准。

---

## 6. 工期估算

| 阶段 | 内容 | 人工全职 | AI 并行 + 人审 |
|---|---|---|---|
| P0 知识基座 | 文档提取、格式样本、基线建立 | 1 月 | 1-2 周 |
| P1-P5 内核 | I/O、预处理、寻峰、数据库、Search-Match | 6-9 月 | 2-3 月 |
| P6-P9 高级 | 定量、指标化、精修、微结构 | 6-9 月 | 2-3 月 |
| P10-P12 产品化 | GUI、报告、批处理、打包 | 3-4 月 | 1-2 月 |
| **合计** | | **16-23 月** | **6-10 月** |

---

## 附录 A：本次勘察已产出的资产

| 资产 | 路径 | 说明 |
|---|---|---|
| 169 篇规格文档（Markdown, 627 KB） | `docs/third-party-help/*.md` | 从 `参考软件官方帮助数据库(.qch)` 解密提取，**可直接投喂 AI agent** |
| 功能清单索引 | `docs/FUNCTION_MAP.md` | 17 个模块分类，带链接 |
| 4076 条索引关键词 | `docs/INDEX_KEYWORDS.txt` | 术语表，用于统一 XinMatch 术语 |
| 提取脚本（可复用于新版） | `tools/extract_help.py` | 换安装目录即可重新提取 |

**对最新版安装包**：安装后重跑 `python tools/extract_help.py "<新安装目录>"`，即可自动 diff 出版本间功能差异（`whats_new`）。
