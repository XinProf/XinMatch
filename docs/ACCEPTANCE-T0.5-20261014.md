# T0.5 术语映射表 — 验收文档（2026-10-14）

> 任务：建立术语映射表：参考软件 术语 ↔ XinMatch ↔ 标准晶体学术语。
> 产物：`docs/TERMINOLOGY.md`。提交：`(待回填)`

## 一、执行路径

1. **参考软件术语源**：从 4.3 Build 360 帮助容器 `Match4.qch` 的 `IndexTable` 提取 **3,514 个索引关键词** + 166 个主题标题（探针 `t05_terms_probe.py`）——对应 ROADMAP 要求的「INDEX_KEYWORDS.txt 高频词」（该文件在 T0.1 后未入库，现以 IndexTable 等价覆盖且更新到最新版）。
2. **XinMatch 术语源**：UI 文案（`xinmatch/ui/` 73 处控件文本，含中文标签）+ CLI 命令（import/process/search/quantify/report/run/batch/instrument）+ 核心模块名。
3. **标准术语**：遵循 IUCr / ICDD / CIF 惯例（如 RIR/I-Ic、DoC、2θ 位移校正、Savitzky-Golay 等）。
4. 构建 `docs/TERMINOLOGY.md`：9 个功能域 × 三层映射（参考软件 ↔ XinMatch ↔ 标准术语）+ 状态备注。

## 二、确认项清单

| # | 确认项 | 结果 | 证据 |
|---|---|---|---|
| 1 | 参考软件高频词全量覆盖 | ✅ | IndexTable 频次 ≥3 的功能语义词全部入表；纯界面词（delete input field 等）显式声明不入表 |
| 2 | XinMatch 术语来自真实代码 | ✅ | 73 处 UI 控件文本 + 8 个 CLI 子命令逐一核对（Grep 输出） |
| 3 | 标准术语符合领域惯例 | ✅ | RIR/DoC/Le Bail/Rietveld/FoM 等按 IUCr/ICDD 表述 |
| 4 | 状态标注诚实（已实现/规划/无） | ✅ | 每行 `[x]/[规划]/[—]` 标注；与 STATUS.md 路线图一致（如 DoC、Indexing 为规划） |
| 5 | GUI 与文档统一的基础 | ✅ | XinMatch 侧以 UI 实际文案为准（如「限制条件」「峰列表」） |

## 三、诚实边界

- **非逐词全量映射**：3,514 词含大量纯界面/流程词（无领域语义），映射表覆盖功能语义词；未全覆盖的类别已显式声明。
- **XinMatch 侧术语以现行 UI 为准**：部分模块尚无 GUI（如批处理/串口采集走 CLI），表中以其 CLI 名标注；后续 GUI 落地时需同步更新本表。
- **标准术语为领域惯例归纳**：非引用具体标准文献条款；如需逐词溯源（如 ISO/IUCr 定义出处）可另立子任务。

## 四、为什么本次验收费时可控

T0.5 为纯文档任务：验收 = 关键词提取统计（3,514 词自动）+ UI/CLI 术语代码核对（Grep）+ 映射表逐行核对；无测试依赖，全程 <2 分钟。
