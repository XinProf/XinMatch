## XinMatch v3.3.0 — 少线相标记：候选列表 ★ 强线锚定

> 基线 `v3.2.0`｜本次为**小版本**（新增判据 + 界面标记），参考库格式、FoM 权重、
> P 值定义、命令行与配置**全部不变**；检索排序与 v3.2.0 逐项相同。引擎只多了
> 一个默认关闭的排序开关和一条只读的标记通道。

### 一、要解决的问题

FoM 里的 `P(npeaks)` 按**条数**计——一个候选解释了多少个实测峰、占总峰数的比例。
在多相样品的残差谱上，这条判据天然偏向"线多"的卡片：一张 40~150 条反射的金属间
化合物可以把残差里的弱峰大量"撞"上，而真正该被认出来的**少线相**（金属 Fe 6 条、
NaCl 17 条、KCl 约 9 条）只解释两三个峰，`P(npeaks)` 很低，于是永远排在后面。

实测（`docs/基准报告-物相检索-v3.md` §11.3）：

* `synth_07` 的真 KCl **在 1000 深的候选池里根本不存在**；
* `synth_10` 的金属 Fe 第 1 轮 rank **#94/1000**，`P(2θ)` 0.998、`P(I/I₀)` 0.99、
  最强线正好落在 **1.00×** 最强残差峰上；
* `synth_07` 的 NaCl rank 10，`P(2θ)` 0.991，最强线同样命中残差主峰。

也就是说：这些相在**位置**与**最强线**上是完全正确的，只是"票数"不够。

### 二、核心能力

| 能力 | 说明 |
|---|---|
| 强线锚定判据 `AnchorPolicy` | 最强参考线命中 ≥0.30×最强残差峰 + `P(2θ)`≥0.98 + 匹配对≥2 + `P(ncorr)`≥0.50 + 参考反射数 ≤20 |
| 候选标记 | `ResidualSearchResult.anchored_ids` 列出通过判据的条目；候选表第一列色带显示 `★`，悬停给出判据解释，状态栏报「★ N 条最强线命中强残差峰」 |
| 可选重排（默认关） | `search_residual(..., promote_anchored=True)` 把这些候选移到列表最前（仍按 FoM 降序），供离线实验 |
| 线数护栏 | 参考反射数 > 20 的候选**永不**标记——它正是霸榜机制本身 |

### 三、关键设计决定（以及为什么）

1. **先试打分、再试排序，最后只敢标记**
   先是按任务原文改 `P(npeaks)`：换成"实测侧强度覆盖"、与 FoM 混合、加位置门控、
   近平局 ε 重排、整族排除姊妹卡、把 `ncorr` 也换成强度覆盖 —— **八种变体全部 ≤ 基线
   10/13**（§11.2）。结论：打分层改不动这件事，因为"多而杂"的假卡与"少而精"的真相
   在同一个指标上互为镜像。于是转向**不改分、只额外看一眼**的锚定判据。

2. **为什么线数护栏而不是"更强的最强线"**
   合成谱上锚定把 `synth_07` 从 0/2 直接救成 2/2（序贯 10/13 → **11/13**、相召回
   19/24 → **21/24**）。但没有线数护栏时，`synth_02` 的假密集卡也满足"最强线命中"，
   把 2/2 打成 1/2。护栏取 20 条：Fe 6、KCl 9、NaCl 17、CaF₂ 17 全在内，40~150 条
   的卡全在外。

3. **为什么默认不重排（本版最重要的决定）**
   真实 12 组谱上，重排丢了 `3-2`：第 2 轮榜首 6 张全是真 Al₂O₃，锚定把第 7 名
   `Bi1.284O2.988Y0.684` 抬到首位——它的 `P(2θ)` **0.984**，比真 CaF₂ 的 0.928
   **还准**，`P(ncorr)` 0.588 也够，17 条反射也够。误确认后残差被污染，CaF₂
   连跑 5 轮也找不回来（不是"多花一轮"）。序贯完整回收 5/12 → 4/12。
   单线 / 双线（Hanawalt 式最强两条都命中）/ 双线+强度比 三种变体的八项指标
   **完全相同**，说明不是阈值没调好，而是这条规则在真实谱上判别力不够。

   根因：合成谱用同一批参考强度重建，"参考相对强度 ↔ 实测相对强度"精确成立；
   真实谱没有这个关系，少线相的 `P(I/I₀)` 天然趋近 0，锚定只能靠位置和线数——
   而 `3-2` 那个假卡在位置和线数上都是"好"的。**合成尺子在这条规则上系统性高估。**

   所以本版把它降级为**标记**：引擎排序与 v3.2.0 逐项相同（真实谱 Top-1 10/12、
   Top-5 12/12、序贯 5/12、卡召回 24/43、族级 27/43），用户自己决定看不看第 7 名
   那个 ★，引擎不替他决定。

4. **标记不占新列**
   `★` 画在原有的第一列（配色带）里，`DisplayRole` 返回 `★`、`ToolTipRole` 解释判据，
   排序键变成 1/0，所以点列头可以把所有 ★ 候选聚到一起看。列数、列序、既有快捷键
   全部不变。

### 四、界面

* 候选列表：通过强线锚定的行，第一列色带显示 `★`（与已确认相的配色可同存）；
  悬停提示「最强参考线落在强残差峰上，且位置精度高、自身反射解释过半……即使排名
  靠后也值得看一眼——确认前请核对参考线条」。
* 状态栏：剩余峰检索完成的提示追加「★ N 条最强线命中强残差峰（少线相，排名靠后
  也值得核对）」。
* 整谱检索（非序贯）不产生标记，行为与 v3.2.0 完全相同。

### 五、兼容性

* 无新增依赖，无 schema 变更，`.xinDB` 库原样可用。
* `search_residual()` 新增关键字参数 `promote_anchored`（默认 `False`）与
  `anchor_policy`（默认 `None` = `DEFAULT_ANCHOR_POLICY`）；两者都**不会**透传给
  `search_match`，自定义 `search_fn` 的 `kwargs` 与旧版逐字节相同。
* `ResidualSearchResult` 新增字段 `anchored_ids`（默认空列表），旧构造方式不受影响。
* `CandidateListTable.set_candidates()` / `MainWindow.set_candidates()` 新增关键字参数
  `anchored_ids`（默认 `None` = 不标记）。位置参数签名不变。
* `xinmatch.core.search.sequential` 新增导出：`AnchorPolicy`、`DEFAULT_ANCHOR_POLICY`、
  `DEFAULT_ANCHOR_ALPHA` / `_PEAKPOS` / `_MIN_PAIRS` / `_MIN_NCORR` / `_MAX_REFLECTIONS`。

### 六、验收

* 静态门：`ruff check xinmatch tests` 全通过；`mypy xinmatch` 121 文件
  `Success: no issues found`。
* 全量 `pytest`（`addopts` 默认排除 `slow`）：**1488 项 / 1483 passed / 4 skipped /
  1 xfailed / 0 failed**（15m27s）。
* 基准（COD-Inorg 78,035 相）—— **默认口径与 v3.2.0 逐项相同**：

  | 口径 | v3.2.0 | v3.3.0 默认 | v3.3.0 `promote_anchored=True` |
  |---|---:|---:|---:|
  | 合成 `synthetic_v3` 序贯完整（相位级） | 10/13 | 10/13 | **11/13** |
  | 合成 `synthetic_v3` 序贯相召回 | 19/24 | 19/24 | **21/24** |
  | 真实 12 组整谱 Top-1 / Top-5 | 10/12 · 12/12 | 10/12 · 12/12 | 10/12 · 12/12 |
  | 真实 12 组卡召回 / 族级召回 | 24/43 · 27/43 | 24/43 · 27/43 | 24/43 · 27/43 |
  | 真实 12 组序贯完整（3 轮） | 5/12 | 5/12 | 4/12 |
  | 真实 12 组序贯完整（5 轮） | 6/12 | 6/12 | 5/12 |
  | 真实 12 组序贯内相召回 | 23/43 | 23/43 | 22/43 |

  合成增益 100 % 来自 `synth_07`（NaCl 从 rank 10 抬到首位，`0/2 → 2/2`），
  真实损失 100 % 来自 `3-2`（Bi-Y-O 假卡占位，CaF₂ 丢失）。这就是默认关闭的全部理由，
  数据与诊断见 `docs/基准报告-物相检索-v3.md` §11.5。

* 新增测试：`tests/search/test_sequential.py` 新增 9 项（默认不重排但标记、重排开关、
  密集卡不被标记、`ncorr`/位置/锚点强度三条判据各自能否决、单对不算证据、
  `pairs=[]` / `p_values={}` 不崩、重排后 `pairs` 仍映射回原始峰索引）；
  `tests/ui/test_tables.py` 新增 2 项（★ 标记与 tooltip、折叠后标记随变体展开恢复）；
  `tests/ui/test_sequential_ui.py` 新增 1 项（剩余峰结果携带 `anchored_ids` →
  候选表标记 + 状态栏提示）。

### 七、发布产物

| 附件 | 字节 | SHA-256 |
|---|---:|---|
| `XinMatch-Setup-3.3.0.exe` | 254,071,430 | `6e93c548dbd09ad82dcb3a3e59c8b41218d3a9a11515e45acc62b519f9770791` |
| `XinMatch-Internal-3.3.0.zip` | 353,728,377 | `71f410fbef7eedad7dab785f0703d24af3fc7d10d0bc29d696fe7ba947c144c4` |
| `SHA256SUMS.txt` | 190 | 上面两个哈希的清单 |

两个二进制都内置 `COD-Inorg-20261020.xinDB`（113 MiB / 78,035 相），解压或安装即可检索；
更大的扩展库仍从
[`XinMatch-DataBase`](https://github.com/PolyXRD/XinMatch-DataBase) 挂载。

### 八、二进制稳健性验收（5 轮，全部通过）

对**实际发布的产物**跑 `tools/verify_binary.py`
（`python -m tools.verify_binary --setup … --zip … --workdir …`），原始结果
`.scratch/binary_verify_330.json`：

| # | 检查 | 实测结果 |
|---|---|---|
| 1 | SHA-256 一致性 | 算哈希 → 写 `SHA256SUMS.txt` → 解析回读并重新哈希比对，一致 ✅ |
| 2 | 便携模式启动 | 解包 exit 0 → `variant.txt=internal`、内置 `COD-Inorg-20261020.xinDB` 118,640,640 B、随包 `logo_256.png` 与源码逐字节一致；冻结 CLI `libraries --json`（默认库 `entries=78035 / available=true`）与 `import --help` 均 exit 0 ✅ |
| 3 | 冻结 GUI 冒烟 | `REG` → `variant=internal, registration_enabled=false, 内部评估版本`；`LIBS` → 10 条库记录；`ABOUT` → 渲染出 About 对话框 PNG（9,117 B）；另连续 3 次冷启动均 exit 0 ✅ |
| 4 | 静默安装 | `/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /CURRENTUSER /DIR=…` → exit 0，落地 `XinMatch.exe` + `data\COD-Inorg-20261020.xinDB`，`variant.txt=release` ✅ |
| 5 | 安装后启动 | 安装目录冻结 CLI `libraries --json` exit 0；**真实谱端到端检索** `search 5-1.txt --db <安装目录内置库> --top-n 5 --json` → 118 峰 / 5 候选 / 榜首 `96-210-0189`（方解石，与基准一致）；release GUI 钩子 `variant=release, registration_enabled=true, 未注册` ✅ |

> 本轮踩到一个**验收工具自身的坑**并已修掉：`--workdir` 传相对路径时，轮 3/4 会把
> 相对路径当环境变量 / `/LOG=` 参数交给子进程（子进程 cwd 就是 work 目录），解析成
> 不存在的路径 → 冻结 GUI 里写文件抛 `FileNotFoundError` 被 Qt 吞掉、事件循环继续跑，
> 表现为「自测 120 s 超时」＋「静默安装 rc=1」，极易误判成产物有问题。
> `verify_binary.main()` 现在把所有输入路径先 `resolve()`。

人工双击验收仍建议由使用者做一次（自动化只覆盖离屏路径）。
