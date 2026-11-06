## XinMatch v3.5.0 — 元素「必须不含」约束可用、版本号单一真相源

> 基线 `v3.4.0`（提交 `c39e3b0`）｜本次是**缺陷收口 + 工程治理**版本。
> 参考库格式、FoM 权重、P 值定义、命令行接口全部不变；**检索默认行为逐项不变**
> （合成基准 11/13·12/13·10/13·19/24 已复核）。

### 一、要解决的问题

三件事，前两件是「界面说有、实际没有」，第三件是「同一个数字写了四遍」。

1. **三态元素约束的红色分支从未生效。** 周期表能标红、摘要会显示「排除：Bi」，
   但从 1.x 到 3.4，`ElementState.EXCLUDE` 在**全仓的引用数为 0**：检索入口
   `main_window._do_search` 调 `search_match` 时不传 `restraints`，预筛也没有这条
   通路。用户以为「样品里没有 Bi」已经生效，实际什么都没发生 —— 基准报告 §11.5
   的 `3-2` `Bi-Y-O` 假卡（pos 0.984，比真 CaF₂ 的 0.928 还准）只能靠肉眼剔。
2. **版本号四处各写一遍然后漂移。** `pyproject.toml` 写 3.4.1、
   `__init__._FALLBACK_VERSION` 写 3.4.0（**冻结 exe 报的就是这个**）、
   `xinmatch.spec` 写 3.4.0、`xinmatch_setup.iss` 里 10 处写 3.4.0。
   后果不是「显示不好看」：exe 的 About 报 3.4.0、源码跑报 3.4.1、安装包名固定
   `XinMatch-Setup-3.4.0.exe`，用户报 bug 时给的版本号对不上 tag。
   每次发版都靠人工清单「11 处一起改」，`docs/ACCEPTANCE-*.md` 里逐条写着。
3. **P1「预筛排序连续化」需要一个结论。** §14.5 判断「二值主峰判据信息量不足，
   应改强度加权覆盖率」，方向一直没验证过。

### 二、核心能力

| 能力 | 说明 |
|---|---|
| **元素「必须不含」约束** | 周期表红色元素真正参与检索：在预筛层用 `element_inv` 倒排剔除含该元素的相，与「必含」（绿色）取交集 |
| 三个入口一致 | GUI（限制条件面板）、`search_match(restraints=...)`、`search_match_v3(elements_excluded=...)` 走同一条通路 |
| 未知元素的相反语义 | 拼错的元素符号在「必须含」方向清空结果（约束不可能满足），在「必须不含」方向**什么都不排除**（不可能含有 ≠ 不可能满足） |
| FPFM 模式明说 | 全谱拟合链路没有 restraints 形参，选中元素又切到 FPFM 时状态栏直接提示，不静默失效 |
| **版本号单一真相源** | `pyproject.toml` 唯一；spec 从它推导，iss 只剩一处默认值并由构建脚本 `ISCC /DAppVersion=` 覆盖 |
| 版本一致性测试 | 5 项检查（pyproject / `_FALLBACK_VERSION` / iss 默认值 / iss 无其他字面量 / spec 不得写死），任一处漂移即测试失败 |
| 构建自检 | `tools/build_exe.ps1` 构建后读 exe 的 `FileVersion` 与目标版本比对；新增 `-Installer` 一条命令出安装包 |

### 三、关键设计决定（以及为什么）

1. **排除走 `element_inv` 倒排，不走 `entries.elem_mask`**
   mask 是单个 64 位有符号整数，建库时按 **63 位截断**（`_MAX_STORABLE_MASK`）。
   W、Pb、Bi、U、Ta、Au、Pt、Gd 等 27 % 的相落在 bit 63 之外，用 mask 筛会静默
   漏判。`element_index()` 早就是这个原因改走倒排，排除方向沿用同一条路。

2. **未知元素在排除方向返回全 `True`**
   与「必须含」刻意相反。「必须含 La」而库里没有 La → 结果必须为空（约束不可能
   满足）；「必须不含 Zz」而库里没有 Zz → 不该排除任何相。把两者写成同一种处理，
   会让一个拼写错误变成「检索无结果」这种最难排查的现象。

3. **GUI 在读面板状态的位置上，必须是 GUI 线程**
   `_do_search` 跑在工作线程，在 worker 里读 `PeriodicTablePanel.states()` 属于跨线程
   访问 QWidget，Windows 上会随机崩。所以 `_current_restraints()` 在
   `_run_search_match`（GUI 线程）里先取好，再把不可变的 `Restraints` 带进线程。

4. **预筛排序做成开关，不改默认**
   实测把后两键换位（命中数提前）后：真实谱 Top-1 10/12→**11/12**、卡级相召回
   19/43→**23/43**（族级 25/43），但合成谱 Top-1 11/13→8/13、序贯 10/13→5/13。
   根因是尺子不同源：合成谱用库内同一批参考强度反演，强度形判据天然占优。
   「Top-1/Top-5 不退化」是硬验收口径，两种口径互有胜负属于产品裁定，所以落成
   `XinDBReader(prescreen_order="intensity"|"hits")`，**默认仍是 `"intensity"`**。
   详见基准报告 §16。

5. **顺手证伪了一条旧建议**
   §14.5 建议改「强度加权覆盖率」这类连续量。实测池内召回（800 席 / 67 真相位）：
   `2·main_hit+命中率` 50/67、`+0.3·whits` 49/67、去掉主峰门控 41/67，
   全都低于「二值门控 + 命中数」的 51/67。**门控是载荷，不是缺陷**：
   它回答的「我的最强线是不是样品的强峰」在多相谱里恰恰是最强的单一判别特征。

6. **版本号不再靠清单，靠机制**
   spec 从 `pyproject.toml` 推导（原有 guard 比对 `_FALLBACK_VERSION` 继续生效），
   iss 只保留 `#ifndef AppVersion` 一处默认值、其余全部 `{#AppVersion}`，
   构建脚本用 `/DAppVersion=` 注入；再用 `tests/test_version_consistency.py` 把
   「三处必须逐字相同」变成测试。这样下次 bump 只需要改 2 个文件（pyproject +
   `_FALLBACK_VERSION`），而不是照清单改 11 处。

### 四、随版本一起发出的数据侧修正

这些改了库内容、不改代码行为，已在 3.4.1 的库文件里生效，3.5.0 一并说明：

| 项 | 内容 | 验证 |
|---|---|---|
| COD-Inorg 417 条空式卡 | 对称展开位点 → `formula_from_sites` 派生化学式，原地补丁只改元数据 | 四步等价性证明：全量重解析 diff / 护栏写入 / `validate_xindb` + 逐 chunk 哈希 + 抽样重建 / 写后 diff 归零 |
| COD-Full 440 条空式卡 | 同上（含 4 张垃圾式），空式归零 | 130 chunk 哈希全等、48/48 抽样重建逐字节一致、双基准 JSON 逐字段全等 |
| PDF-2 57 条截断卡 | `X7` 续行不再被覆盖（`formula_lines` + 收窄的 `display_formula`），57 张 `)2` / `]n` 尾巴修好 | E2 无元素 WARN 93→36（剩 36 是源数据固有，**不编造**）；40 chunk 哈希全等 |

3.4.1 的 `same_phase` 修复（空白式卡不再「万能匹配」）也在本版本内：它让真实谱的
组成级召回数字**下降**且更接近事实 —— 旧数字是被假匹配抬高的，属于口径修正而非能力退化。

### 五、验证

| 项 | 结果 |
|---|---|
| `pytest`（全量） | 见 §六 实测，0 失败 |
| `ruff` | All checks passed |
| `mypy`（改动模块） | Success: no issues found |
| 合成基准（默认口径） | 相位级 Top-1 11/13、Top-5 12/13、序贯 10/13、相召回 19/24 —— 与 3.4.x 逐项相同 |
| 元素约束（真实 13 组，理想 XRF 设定） | Top-1 10/12 → 12/12；逐相名次 21 升 / 17 平 / 4 降 / 1 挤出 |
| 版本一致性 | 5 项测试全过；XinMatch 与 XinRefinement 两侧都补了同样的闸 |

### 六、升级注意

* **默认行为不变**：不使用「限制条件」面板的用户，检索结果与 3.4.x 逐位相同。
* 若要让红色元素生效，请在「限制条件」标签页勾选元素并把状态点到红色，再运行
  Search-Match（仅峰列表 FoM 模式；FPFM 会提示不参与）。
* 安装包文件名变成 `XinMatch-Setup-3.5.0.exe`；旧版 `data\*.xinDB` 参考库可直接沿用。
* 想试新排序口径：`XinDBReader(path, prescreen_order="hits")` 或写脚本对比，
  注意它对合成谱与真实谱的影响方向相反（报告 §16.3）。

### 七、复现

```bash
# 合成 / 真实基准（默认口径）
python -m tools.bench_pattern_set  --patterns D:\Project\XRD\test_xrd\synthetic_v3 \
    --library <COD-Inorg.xinDB> --out .scratch/bench_syn.json
python -m tools.bench_real_samples --patterns D:\Project\XRD\test_xrd\txt \
    --library <COD-Inorg.xinDB> --out .scratch/bench_real.json

# 排序口径 2×2（临时改写源码，跑完自动还原）
python .scratch/_probe_ab_prescreen.py --which syn
python .scratch/_probe_ab_prescreen.py --which real

# 元素「必须不含」在真实谱上的名次变化
python .scratch/_probe_exclude_bench.py
```
