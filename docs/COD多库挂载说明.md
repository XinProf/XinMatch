# XinMatch 参考数据库多库挂载说明（v3.0+）

> ⚠️ **本文档已按 v3.0.0 重构。** v3.0.0 移除了全部旧版本兼容代码：
> - PDF-2 的 `pdf2_index.py` 侧车索引（旧「参考数据库 → 建立/重建索引」按钮一并删除）；
> - 随包默认库 `data/cod_inorganics.db`；
> - 内置注册 id `pdf2_2004` / `cod_inorganics` / `cod_full`；
> - `pdf2_source_dir` GUI 配置键（`config.yaml`）与所有旧格式读取路径（PDF2 dump / COD sqlite dump）。
>
> **现行只支持 `.xinDB` v3 列存库**，通过外部库注册挂载。下文描述 v3.0+ 的现行机制；
> v1.0.0 时代的旧流程仅作为本仓库历史记录保留在 `docs/打包交付说明-v1.0.0.md` 与
> 各版本 `RELEASE-NOTES` 中，不再适用。

## 1. 现行机制

- **库形态**：所有参考库均为 `.xinDB` v3 列存（schema v3，`schema_version = 3`）。
  `reader_v3` 只校验 `REQUIRED_TABLES` + `schema_version`，所以任何按 v3 落盘的库天然可挂载。
- **两类挂载**：
  - **内置（按文件名自动发现）**：`multi_db` 从数据目录 glob 出
    `COD-Full-*.xinDB` / `PCOD-Full-*.xinDB` / `TCOD-Full-*.xinDB`，无需注册。
  - **外部（注册表持久化）**：其余库（无机子库、MP、PDF-2 等）通过
    `multi_db.add_external_library(path)` 登记到
    `~/.xinmatch/libraries.json`（`XINMATCH_USER_DATA` 可覆盖），跨会话保留。
- **默认检索库**：COD-Inorg（`COD-Inorg-20261020.xinDB`），GUI / CLI 缺省即检索它。
- **只读打开**：`multi_db.open_library(id)` 或 `open_external(path)` 返回只读连接
  （`mode=ro` + `query_only=ON`），可直接喂 `search_match` / `fetch_entries_by_ids`；
  不可用抛 `LibraryNotAvailableError`（消息即友好原因）。
- **GUI**：菜单「设置 → 参考数据库…」列出全部库（名称 / 条目数 / 路径 / 状态，不可用置灰显示原因），
  支持「添加外部库…」浏览 `.xinDB` 文件并注册；单选切换持久化到 `libraries.json`。

## 2. 当前库清单（实测）

| 库 | 文件 | 条目数 | 形态 | 状态 |
|---|---|---|---|---|
| COD 无机物（默认） | `XinMatch-DataBase/data/COD-Inorg-20261020.xinDB` | **78,036** | 外部库 | 可用 |
| COD 全库 | `XinMatch-DataBase/data/COD-Full-20261020.xinDB` | **532,038** | 内置（glob） | 可用 |
| TCOD 无机物 | `XinMatch-DataBase/data/TCOD-Inorg-20261020.xinDB` | **46,846** | 外部库 | 可用 |
| TCOD 全库 | `XinMatch-DataBase/data/TCOD-Full-20261020.xinDB` | **361,701** | 内置（glob） | 可用 |
| PCOD 无机物 | `XinMatch-DataBase/data/PCOD-Inorg-20261020.xinDB` | **1,061,953** | 外部库 | 可用 |
| PCOD 全库 | `XinMatch-DataBase/data/PCOD-Full-20261020.xinDB` | — | 内置（glob） | 待构建（缺失时置灰） |
| Materials Project | `XinMatch-DataBase/data/MP-20261031.xinDB` | **155,201** | 外部库 | 可用 |
| ICDD PDF-2 2004 | `XinMatch-DataBase/data/PDF2-20040317.xinDB` | **163,834** | 外部库（实测卡片） | 可用 |

> 数据目录 `XinMatch-DataBase/data/` 已被仓库 `.gitignore` 的 `/data/` 屏蔽——
> 这些库不入库、不随 Release 分发，用户本地挂载即可。

## 3. PDF-2 2004（实测卡片库，v3.0+ 现行形态）

PDF-2 在 v3.0 之前是「PolyXRD dump → `pdf2_index.py` 侧车索引」的挂载方式，v3.0.0 已删除。
现按 `.xinDB` v3 外挂库规范重新打包为 `PDF2-20040317.xinDB`，与 COD 家族走同一条检索链路，
差异全部写在 `meta` 里：

- `library_kind = PDF2`、`data_date = 20040317`（文件名与 meta 一致，`M3.identity` 通过）；
- `meta.peak_origin = observed`（峰是几十年文献实测的相对强度，**不是**由 CIF 算的）；
- 强度归一 `norm1000`，与计算库共用一把尺子，打分权重可比；
- 晶胞缺失写 NULL（老 Hanawalt 卡片本就无晶胞，属数据事实，不填哨兵值）；
- 峰不截断（最多 199 条原样保留）。

**版权边界**：产物不入库、不进 Release（ICDD 商品数据）。构建与验收细节见
`XinMatch-DataBase/docs/PDF2-库构建与验收.md`；旧 `PDF2_2004.sqlite`（v2 遗留）已无任何代码读取。

## 4. COD 全库构建（历史 → 现行）

- **v1.x 旧入口**：`tools/build_cod_full_xinmatch.py` 生成 `data/cod_full.db`（XinMatch-schema 行式），
  属旧格式，**v3.0.0 起不再作为挂载形态**。
- **现行**：COD 全库由 `tools/build_cod_xindb.py` 等 xinDB 建库工具链生成
  `COD-Full-*.xinDB`（列存），按文件名被 `multi_db` 自动发现，无需注册。
- 检索质量结论不变：默认检索保持精选无机库（COD-Inorg），全库仅作覆盖性挂载 / 人工查阅，
  不作为默认搜索库（全库含大量重复 / 低质量卡片，会稀释 FoM 排序）。

## 5. 许可提示

- **PDF-2 2004 为 ICDD 商业授权数据**：检索结果仅供本地使用，参考库不随 XinMatch 再分发。
- COD 数据遵循其公开许可（CC0）；MP 数据遵循 Materials Project 许可。
- 旧「参考软件 专有库」（`.mti` 等）不复制、不逆向、不随包（净室约束）。
