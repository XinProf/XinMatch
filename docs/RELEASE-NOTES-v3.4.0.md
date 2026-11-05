## XinMatch v3.4.0 — 导出物相分析状态（.xinm）：与 XinRefinement 1.1.0 打通

> 基线 `v3.3.0`｜本次为**互通版本**：新增一个导出入口、一份文件格式契约、一条 CIF 回取链。
> 参考库格式、FoM 权重、排序口径、P 值定义、命令行全部不变。

### 一、要解决的问题

检索做完，结论只活在 XinMatch 里。想去 XinRefinement 做全谱拟合，得手工做三件事：
重新导入谱图、逐个把已鉴定相的 CIF 找回来、记住波长。

第二件事最要命。COD 归档是 52 万个文件按 id 分层散开的
（`COD/9/00/82/9008220.cif`），库里只存 `96-900-8220` 这个 ref_id，不存路径也不存内容。
用户要么凭经验翻目录，要么去网站上一条条下——两种做法都会挂错相，而挂错相的精修
**照样收敛**，只是 Rwp 白高、定量白做。

### 二、核心能力

| 能力 | 说明 |
|---|---|
| **导出物相分析（.xinm）** | 文件菜单新入口；一次打包锚点谱图 + 已选物相的 CIF + 峰表 + 元数据，供 XinRefinement「导入 XinMatch 物相分析」一键装载 |
| 容器格式 | zip：`manifest.json` + `pattern/pattern.csv` + `cifs/*.cif`；`format:"xinm"` / `version:1`，字段只加不减 |
| 谱图规范化 | 两列 CSV（`two_theta,intensity`），`%.10g`——float64 往返相对误差 ≤1e-9，10 万点约 2 MB |
| CIF 回取桥 | `96-900-8220` → COD id `9008220` → `{id[0]}/{id[1:3]}/{id[3:5]}/{id:07d}.cif`；按「环境变量 → 当前档案根 → 历史根」逐根探测 |
| 降级不阻断 | 某相 CIF 回取失败 → 该相 `structural=false` + `reason` 文案，导出照常完成；精修侧列为「仅参照」，可手动补 CIF |
| 版权边界 | **不打包任何 ICDD/PDF2 衍生数据文件**；`source="pdf2"` 只写 id 与峰表元数据（与 DB Manager「请确认已获得正版授权」同一原则） |
| 候选摘要 | 前 20 个未选候选只带 name / entry_id / source，不嵌 CIF（控制体积），供精修侧提示「还可补相」 |

### 三、关键设计决定（以及为什么）

1. **zip 容器而不是单个 JSON**
   10 万点谱图 float 列表 JSON 化约 4 MB+ 且解析慢；CSV 约 2 MB、可流式读写。
   CIF 是文本，直接塞 zip 里按成员名取，比 base64 进 JSON 省 33% 且不污染 manifest。

2. **不新造 `xinm_cif_bridge.py`，复用 `core/refine/cif_store.py`**
   计划里原本单列一个桥接模块。实做时发现 `cif_store` 早有完整链路（结构查看在用）：
   ref_id → COD id → 归档路径。再造一层属于重复实现，也容易两处布局口径漂移。
   本次只给它补了**多根探测**（见第 5 条）。

3. **`%.10g` 而不是 `%.6g`**
   计划草稿写的是 `%.6g`。实测 `%.6g` 对 float64 无法零往返（相对误差约 1e-7），
   而谱图往返要参与基线扣除与残差计算，宁可多 4 位有效数字。`%.10g` 下 10 万点
   仍 < 3 MB，往返逐位一致。

4. **只判「能不能拿到 CIF」，不判「该不该给」**
   导出侧不做结构合理性检查（有没有原子坐标、占位是否和为 1）——那是精修侧导入时的活。
   导出只回答一个问题：这个 entry 的 CIF 在不在本地档案里。拿得到就打，拿不到就标记。

5. **档案根多探测，而不是写死一个路径**
   `DEFAULT_COD_ROOT` 原来硬编码 `PolyXRD\cod\cif`，机器迁移后该目录已不存在
   （档案现居 `sync-COD\COD`）。写死会让「CIF 全部回取失败」表现得像「数据库坏了」。
   现在按 `XINMATCH_COD_ROOT` → 当前根 → 历史根 顺序取第一个存在的目录，逐根尝试。

6. **扫描范围与步长在导出侧规范化**
   谱图 meta 里常常没有 `tmin/tmax`，`step` 又带着 `0.019999999999999574` 这种浮点尾巴。
   导出一律回填真实首末 2θ（6 位小数）并 `round(step, 6)`——下游会把它写进画布与报告头，
   契约里写的字段就该有干净的值，而不是 `null` 和浮点噪声。

### 四、界面

* 菜单：`文件(F) → 导出物相分析（.xinm）…`（位于导出报告之后、分隔线之上）。
* 前置校验：无谱图 → 「尚未载入实验衍射谱」；无已选候选 → 「请先运行 Search-Match 并选择相」。
* 完成提示：`已导出 N 相（M 个含结构 CIF），谱图 P 点 → analysis.xinm`。
* CIF 回取失败不弹错、不中断——计数会小于相数，落盘状态在 manifest 里可查。

### 五、兼容性

| 项 | 状态 |
|---|---|
| 参考库格式（`.xinDB` schema v3） | 不变，v3.3.0 的库直接可用 |
| FoM 权重 / 排序 / P 值定义 | 不变，检索结果与 v3.3.0 逐项相同 |
| 命令行 / 配置文件 | 不变，无新增子命令 |
| 注册机制 / 双变体 | 不变（release 含注册、internal 红字标识） |
| 新增产物 | `.xinm`，独立文件，不影响既有工程与报告 |

### 六、验收

* 单测：`tests/io/test_xinm.py` 6 项——manifest 字段、CSV 往返、无候选摘要、
  无法解析 id 的降级、无谱图报错、**真实档案锚点**（`96-900-8220` 锐钛矿命中）。
* 全量：**1494 项，1489 通过 / 5 跳过 / 0 失败**。
* 真实样品联通（`test_xrd/txt/5-1.txt` 方解石 + COD `96-210-0189`）：
  导出 5751 点 / 1 CIF / 23.3 KB → XinRefinement 侧 `read_xinm` 读回 5751 点、
  1 个含结构相、CIF 3,580 B、`app.version=3.4.0`。
* 跨仓库：XinRefinement 侧 `tests/test_xinm_import.py` 直接调用本仓库导出器做 round-trip；
  S1 端到端「导出 → 导入 → 精修」Rwp **3.409617019598457**，与手动导入同谱图/CIF
  的结果逐位一致，且保存 `.xinr` 后删除源谱图与 `.xinm` 仍能复现。

### 七、发布产物

| 附件 | 字节 | SHA-256 |
|---|---:|---|
| `XinMatch-Setup-3.4.0.exe` | 254,139,154 | `4962defa7d0e4cf702db200c0b3366243b7ea09f95fafe4d7a39fab7ef0c7f19` |
| `XinMatch-Internal-3.4.0.zip` | 368,486,794 | `fb82ce897bf4227aa79420fce3359772001809ee274be64f356ace9aa7ff3a08` |
| `SHA256SUMS.txt` | — | 上面两个哈希的清单 |

两个二进制都内置 `COD-Inorg-20261020.xinDB`（113 MiB / 78,035 相），解压或安装即可检索；
更大的扩展库仍从
[`XinMatch-DataBase`](https://github.com/PolyXRD/XinMatch-DataBase) 挂载。
导入 `.xinm` 的对端版本是 **XinRefinement 1.1.0**，两版需配套发布。

### 八、二进制稳健性验收（5 轮，全部通过）

对**实际发布的产物**跑 `tools/verify_binary.py`，原始结果
`.scratch/binary_verify_340.json`（`all_pass=true`）：

| # | 检查 | 实测结果 |
|---|---|---|
| 1 | SHA-256 一致性 | 算哈希 → 写 `SHA256SUMS.txt` → 解析回读并重新哈希比对，一致 ✅ |
| 2 | 便携模式启动 | 解包 exit 0 → `variant.txt=internal`、内置 `COD-Inorg-20261020.xinDB` 118,640,640 B / 78,035 相、随包 `logo_256.png` 与源码逐字节一致；`libraries --json` 与 `import --help` 均 exit 0 ✅ |
| 3 | 冻结 GUI 冒烟 | `REG` → `variant=internal, registration_enabled=false, 内部评估版本`；`LIBS` → 10 条库记录；`ABOUT` → 渲染出 About 对话框 PNG ✅ |
| 4 | 静默安装 | `/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /CURRENTUSER` → exit 0，落地 `XinMatch.exe` + `data\COD-Inorg-20261020.xinDB`，`variant.txt=release` ✅ |
| 5 | 安装后启动 | 安装目录冻结 CLI `libraries --json` exit 0；真实谱端到端检索 `5-1.txt` → 118 峰 / 5 候选 / 榜首 `96-210-0189`（方解石，与 v3.3.0 一致）；release GUI 钩子 `variant=release, registration_enabled=true, 未注册` ✅ |

本轮顺带修掉一个**版本号显示缺陷**（v3.3.0 起就存在，不在联合计划范围内但会污染
`.xinm` 的 `app.version`）：冻结包里没有 `pyproject.toml`，而开发机的
`site-packages` 残留 `xinmatch-1.7.1.dist-info`，`importlib.metadata` 会把它当真版本，
于是 About 对话框与 `.xinm` manifest 都写成 1.7.1。现在冻结态直接返回
`__init__._FALLBACK_VERSION`，并由 `xinmatch.spec` 在构建时断言它等于 `APP_VERSION`
（不同步就构建失败）；同时 CLI 新增 `--version` / `-V`（此前 `--version` 会打开 GUI）。

人工双击验收仍建议由使用者做一次（自动化只覆盖离屏路径）。

