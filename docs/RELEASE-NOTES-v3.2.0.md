## XinMatch v3.2.0 — 相位级身份：候选列表折叠同相变体 + 双口径基准

> 基线 `v3.1.0`｜本次为**小版本**（功能新增 + 两处默认行为变更）：参考库格式、
> FoM 权重、命令与配置全部不变，旧工程、旧库照常使用。检索引擎只动了一处 ——
> 预筛的名额分配（§三.5），候选上限 800 → 1000。

### 一、要解决的问题

参考库里**同一个物相有几十张卡**。COD 里 BaTiO₃ 有 `96-210-0858` / `96-210-0859`，
TiO₂ 锐钛矿有 `96-500-0223` / `96-900-8214`；`top_n=40` 的实测里，`synth_01` 的
Top-40 有 18 条属 Al₂O₃ 族，`synth_02` 有 12 条属 beryl 族（调整预筛名额前是 18 条）。
这带来两个独立问题：

1. **候选列表被近重复卡淹没**。用户翻 40 行看到的其实是同一个相。`synth_02` 里方解石的
   FoM 只比榜首低 0.0017，却因为 beryl 卡占位一度排在 Top-40 之外（现在已是榜首，见
   `docs/基准报告-物相检索-v3.md` §3、§10）。
2. **基准度量把"找对了相"记成失败**。按 `entry_id` 严格判命中，落到姊妹卡就算 miss —
   同一库同一引擎，条目级 Top-1 是 7/13，相位级是 11/13。

### 二、核心能力

| 能力 | 说明 |
|---|---|
| 相位级身份 `same_phase(a, b)` | 元素集相同 + 晶胞轴长 ±1% / 角 ±1.5° + 空间群一致；**缺晶胞时**才退回化学计量比较（容差 0.25） |
| 候选折叠 | `group_same_phase()` 把已排序候选切成相位族（族代表 = 族内排名最高者），表格默认一族一行 |
| 「变体」列 | 折叠态显示 `N 条`；鼠标悬停列出族内每张卡的 `entry_id` + 晶胞六参数，`▶` 标族代表 |
| 展开 / 合并 | 右键「展开同相变体（N 条）」→ 每张卡一行，该列变为 `族内名次/族内条数`（`1/3`、`2/3`…）；再右键「合并同相变体」收回 |
| 双口径基准 | `tools/bench_pattern_set.py` 同时输出条目级（严格 id）与相位级（同相异卡算命中）汇总 |
| 合成谱换尺子 | `tools/generate_synthetic_patterns.py --peak-source v3 --library <xinDB>`：d/I 直接取自库内同一条目，消除"谱按 v2 卡生成、检索用 v3 库"的强度口径错配 |
| 预筛名额双路 | `prescreen()` 保留原有的"主峰命中 → 强度加权命中 → 命中数"排序占 80% 名额，另 20% 改按"强度加权命中 → 命中数"取，次相靠反射条数进场；默认候选上限 800 → 1000 |

### 三、关键设计决定（以及为什么）

1. **晶胞优先于化学计量做判据**
   占位度精修变体（`Al1.499 Be3 Si6 O18` vs `Al2 Be3 Si6 O18`）晶胞几乎相同、
   化学式不同；多晶型（锐钛矿 / 金红石）化学式相同、晶胞不同。用化学计量当主判据，
   会把前者判成两相、把后者合成一相 —— 两个方向都错。所以**有晶胞就以晶胞为准**，
   化学计量只在缺晶胞（唯一可用证据）时生效。

2. **贪心分组、保序**
   按排名顺序遍历，每条候选并入第一个与之同相的族的代表。这样族代表天然是族内
   最强的卡，族的次序也不变 —— 折叠后的第 1 行仍是原榜第 1 名的相，用户不需要
   重新理解排序。代价是理论上非传递（A≈B、B≈C 不一定 A≈C），在"同相异卡"这种
   一维近似下不构成实际问题。

3. **折叠只改显示，不改打分**
   折叠发生在渲染层，不触碰 `rank_candidates`。`synth_10` 里 15 条尖晶石卡把金属 Fe
   挤到 Top-1 之外这一事实没有改变（见 `docs/基准报告-物相检索-v3.md` §5、§6）——
   折叠只是让它显示成一行，所以不能把"折叠后榜单好看"当成"召回修好了"。
   `synth_02` 的方解石之所以真的回到榜首，是 §三.5 的预筛改动的功劳，不是折叠。

4. **行号不再是候选下标**
   折叠态下第 2 行可能对应第 4 条候选。所有从界面回到数据的地方都必须走映射：
   `CandidateListTable.selected_results()` / `result_at(row)` / `family_results_at(row)`
   都过了折叠表，`MainWindow._selected_candidate_results()`（精修向导、批量操作的
   入口）已切换到前者。导出与报告请用 `visible_results()`，否则行数与界面不符。

5. **预筛名额切出两成给"反射条数"**
   `prescreen` 原本按 `(主峰命中, 强度加权命中, 命中数)` 三级排序取前 N。这个判据的
   隐含假设是"真相相的最强线在实测谱里也不弱"——对次相不成立：Al₂O₃ 在 3-1 的
   实测谱里只剩较弱的线，`main_hit` 拿不到分，于是被主相及同族卡挤到 800 名外
   （`candidate_limit=8000` 时才在 rank 197 出现）。改为 80% 沿用原判据、20% 只按
   反射条数取，让"在多个 d 位置都有对应实测峰"的相能凭覆盖面进场。**没有改 FoM，
   也没有改候选池之外任何一环**——只是把名额分配从单一判据变成两条互补判据。

### 四、界面与品牌

* 候选列表新增第 11 列「变体」；右键菜单新增折叠切换项（无同相变体时显示
  「无同相变体」并置灰）。
* `family_mode_changed(bool)` 信号：折叠状态变化时发出，供状态栏 / 导出提示同步。
* **v3.2.0 起启用新 logo**：窗口图标、应用图标、安装包图标、启动图统一为
  `assets/icons/logo*.png` / `logo.ico`；启动图重新合成（`tools/compose_brand_assets.py`
  以 `assets/splash_backdrop.png` 为底，右下 logo 板 + 左下暗角 + 版本号），
  版本号运行时从 `xinmatch.__version__` 读取。

### 五、兼容性

* 无新增依赖，无 schema 变更，`.xinDB` 库原样可用。
* `CandidateListTable.set_candidates()` 新增关键字参数 `merge`（默认 `None` =
  沿用当前折叠状态，首次为折叠）。位置参数签名不变。
* **默认行为变更**：候选表默认折叠同相变体，可见行数 = 相位族数而非候选条数。
  依赖 `rowCount() == len(candidates)` 的外部脚本需改用 `visible_results()`。
* **默认参数变更**：`DEFAULT_RANK_LIMIT` / `DEFAULT_CANDIDATE_LIMIT` 由 800 改为 1000，
  预筛新增 `diversify_slots` 关键字参数（默认 `None` = 取 `limit` 的 20%，传 0 可完全
  恢复旧行为）。代价是检索耗时上升：COD-Inorg（7.8 万相）0.37 → 0.41 s（+11%），
  PCOD-Inorg（106 万相）1.50 → 1.89 s（+26%）。
* `xinmatch.__version__` 在源码树里优先读 `pyproject.toml`（此前会被仓库内残留的
  `xinmatch.egg-info/PKG-INFO` 旧版本盖住）。

### 六、参考数据库：内置默认库 + 挂载外挂库

**开箱即用**：两个二进制都内置 `COD-Inorg-20261020.xinDB`（重建版，78,035 相 /
113.1 MiB），位于 `<程序目录>\data\`。安装或解压后**不需要任何配置即可检索**；
该目录里的库可以直接替换，也可以再挂别的库。

**扩展库在姊妹仓库发布**：[PolyXRD/XinMatch-DataBase](https://github.com/PolyXRD/XinMatch-DataBase)
的 Releases 提供按来源拆分的 `.xinDB`，本 Release **不重复附带**（PCOD 单库 1.7 GB，
塞进安装包没有意义）：

| Release | 提供的库 | 用途 |
|---|---|---|
| [`20261020-rebuild`](https://github.com/PolyXRD/XinMatch-DataBase/releases/tag/20261020-rebuild) | `COD-Inorg`（同上）、`TCOD-Inorg` 4.7 万相、`PCOD-Inorg` 106 万相、`TCOD-Full` 36 万相、`COD-Full` 53 万相 | 实验库查不到时用预测/理论库兜底；Full 库含全部归档 |
| [`20261031-mp`](https://github.com/PolyXRD/XinMatch-DataBase/releases/tag/20261031-mp) | `MP-20261031.xinDB`（Materials Project） | 第一性原理结构补充 |

**挂载三步**：

1. 从上面的 Release 下载 `*.xinDB.zip` → 解压得到单个 `*.xinDB`。**文件名保持
   `<kind>-<YYYYMMDD>.xinDB` 原样**（验收器按文件名与库内 `meta` 对账，改名会判 FAIL）。
   可用 Release 里的 `SHA256SUMS.txt` 校验压缩包。
2. 放到任意目录（本地盘、NAS 只读共享都行；库是 `journal_mode=DELETE`，无 `-wal/-shm` 侧车）。
3. GUI：**「设置 → 参考数据库…」** 添加并选择；或命令行：

   ```bat
   XinMatch.exe libraries --add "D:\XRD-DB\PCOD-Inorg-20261020.xinDB" --label "PCOD 预测库"
   XinMatch.exe libraries --json
   ```

   `--add` 只登记路径、**不改动也不复制库文件**；卸载用 `libraries --remove <id>`。
   注册表写在用户目录 `~/.xinmatch/libraries.json`，升级程序不会丢。

**多库并存与代价**：可以同时挂多个库，检索时选择当前库。库越大越慢 —— 本版实测
同一条 208 峰谱，COD-Inorg（7.8 万相）0.41 s，PCOD-Inorg（106 万相）1.89 s，
因为预筛要对整张 `top_d` 矩阵做布尔运算、且候选定位需解码更多 chunk。
**建议日常用 COD-Inorg，查不到再挂 PCOD/TCOD**。旧版 v2 的 `.db` / `.sqlite`
参考库在 v3.0.0 已移除，挂载会被明确拒绝。

### 七、验收

* 静态门：`ruff check xinmatch tests tools` 全通过；`mypy` 121 文件
  `Success: no issues found`。
* 回归：全量 `pytest`（`addopts` 默认排除 `slow`）**1477 项：1472 passed / 4 skipped /
  1 xfailed / 0 failed**（13m27s，`tests/ui` 258 + `tests/search` 310 + `tests/db` 139
  为本次改动的主要覆盖面）。
* 新增测试：`tests/search/test_phase_key.py`（14 项：化学式解析、同相异卡、
  占位度变体、多晶型不合并、元素不同、空间群冲突、缺晶胞不作否定证据、缺晶胞比比值不比计数、
  族次序与代表）、`tests/ui/test_tables.py` 新增 6 项（折叠、展开/收回、选择映射、菜单切换）、
  `tests/db/test_prescreen_diversity.py`（4 项：默认份额、越界裁剪、次相从命中数半边进场、
  `diversify_slots=0` 复现旧行为）、`tests/db/test_reader_v3_fetch.py`（2 项：参数上限分批、
  超上限连接代理）。`tests/db/test_reader_v3_perf.py` 的参考 oracle 同步到新名额策略。
* 基准（COD-Inorg 78,035 相，13 组合成谱，新谱 = v3 库强度）：

  | 口径 | Top-1 | Top-5 | 序贯完整回收 | 相召回 |
  |---|---:|---:|---:|---:|
  | 条目级（严格 id） | 7/13 | 11/13 | 2/13 | 9/24 |
  | **相位级（同相异卡算命中）** | **11/13** | **12/13** | **10/13** | **19/24** |
  | 旧谱 / 相位级 | 9/13 | 10/13 | 7/13 | 15/24 |

  真正未命中的只剩 2 个：`synth_07`（稀疏谱缺区分度，整谱 T1/T5 全灭）、
  `synth_10`（金属 Fe 与尖晶石型氧化物同族，榜首先被 `96-900-6921` 占住，
  T5 命中）。`synth_02` 本轮已修好（beryl 洪水下序贯 2/2 完整回收）。

* 基准（第二组，13 组真实测量谱，`auto_process` 全链路，12 组可评）：整谱 Top-1
  **10/12**、Top-5 **12/12**；相召回 Top-20 卡级 **24/43** / 折叠后族级 **27/43**；
  序贯完整回收 **5/12**。`5-3` 单样品最能说明折叠的实质作用：卡级 1/5 → 族级 5/5。

细节与数据见 `docs/基准报告-物相检索-v3.md`；失败定位过程见
`docs/检索基准-v3-诊断-20261104.md`。

### 八、二进制稳健性验收（5 轮，全部实测通过）

对**实际发布的产物**（不是源码树）跑了 5 轮，可复跑工具 `tools/verify_binary.py`
（`python -m tools.verify_binary --setup … --zip … --workdir …`），原始结果
`.scratch/binary_verify_320.json`：

| # | 检查 | 方法与实测结果 |
|---|---|---|
| 1 | SHA-256 一致性 | 两个产物各自算哈希 → 写 `SHA256SUMS.txt` → 回读清单并**重新哈希**比对，一致 ✅ |
| 2 | 便携模式启动 | 7-Zip 解包（3556 文件 / 785 MiB）→ `variant.txt=internal`、内置 `COD-Inorg-20261020.xinDB` 118,640,640 B、随包 `logo_256.png` 与源码**逐字节一致**；冻结 CLI `libraries --json` 与 `import --help` 均 exit 0，注册表内默认库 `entries=78035 / available=true` ✅ |
| 3 | 冻结 GUI 冒烟 | offscreen 自测钩子三连：`REG` → `variant=internal, registration_enabled=false, 内部评估版本`；`LIBS` → 导出 10 条库记录；`ABOUT` → 渲染出 About 对话框 PNG（9,117 B，新 logo 可见）。另连续 3 次冷启动均 exit 0、无残留锁 ✅（中文在 offscreen 下显示为方框，是会话缺 CJK 字体，非产物问题） |
| 4 | 静默安装 | `XinMatch-Setup-3.2.0.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /CURRENTUSER /DIR=… /LOG=…` → exit 0，日志 `Installation process succeeded`，落地 3558 文件、`XinMatch.exe` + `data\COD-Inorg-20261020.xinDB`，`variant.txt=release` ✅ |
| 5 | 安装后启动 | 安装目录的冻结 CLI：`libraries --json` exit 0；**真实谱端到端检索** `search 5-1.txt --db <安装目录内置库> --top-n 5 --json` → 118 峰 / 5 候选 / 榜首 `96-210-0189`（方解石，与基准一致）；release GUI 钩子 `variant=release, registration_enabled=true, 未注册`；安装包与主程序版本资源 `ProductVersion=3.2.0` ✅ |

> 历史几版在非交互会话里 `/SILENT` 会挂起、release 变体被注册弹框阻塞；本轮加
> `/CURRENTUSER` 后两者都跑通了。人工双击验收仍建议在发布前由使用者做一次
> （自动化只覆盖离屏路径）。

### 九、发布产物

| 附件 | 字节 | SHA-256 |
|---|---:|---|
| `XinMatch-Setup-3.2.0.exe` | 254,143,458 | `350b24cfe0ffb669a1792216a5246a20ecd6c1d9461dd18843e6ead525a93590` |
| `XinMatch-Internal-3.2.0.zip` | 353,721,811 | `96e818ee29cbe5453178b7d6d793f1d408e97fc1dedcca7062a4d73016d47756` |
| `SHA256SUMS.txt` | 185 | 上面两个哈希的清单 |

两个二进制都内置 `COD-Inorg-20261020.xinDB`（重建版 78,035 相）；**扩展库请按 §六
到 `XinMatch-DataBase` 仓库挂载**，本 Release 不附带 GB 级大库。
