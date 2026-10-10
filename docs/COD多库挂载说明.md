# XinMatch 参考数据库多库挂载说明（v1.0.0）

> 落地范围：`xinmatch/core/db/multi_db.py`（注册表/只读打开）+ `xinmatch/core/db/pdf2_index.py`
> （PDF-2 侧车索引构建器）+ `tools/build_cod_full_xinmatch.py`（COD 全库构建入口）
> + `xinmatch/ui/dialogs/library_dialog.py`（GUI 库选择）+ 配置键 `reference_db.selected_library_id`。

## 1. 结论先行

- **参考软件 打包库（`D:\Project\XRD\Match-COD\`）无法直接挂载**：每个库（COD_20260602、
  COD-Inorganics_20260602、Cements_20201127、Minerals_AMCSD_20260602）仅有 48 个
  参考软件 专有二进制索引文件（`.mti/.mqn/.mqs/.mtb/.mtn/.mtu`），**不含 CIF、不含 SQLite**；
  净室约束禁止逆向其私有格式，故不进注册表、不实现任何 参考软件 读取。
- **等效替代**：参考软件 库与 PolyXRD 的 COD dump 同源（同一 COD 归档导出），
  XinMatch 直接使用 PolyXRD 的 SQLite dump（只读挂载），数据覆盖面一致且格式开放。

## 2. 三库现状与规模（实测）

| 库 | 源文件 | 条目数 | 峰来源 | 状态 |
|---|---|---|---|---|
| COD 全库 | `PolyXRD\cod_data\cod_index.sqlite`（452 MB） | 113,223 | 无峰表，需 CIF 计算（gemmi） | 已提供构建入口 |
| COD 无机物 | `data/cod_inorganics.db`（默认随包，537 MB） | **71,199** | 已建峰索引 | 随包可用 |
| PDF-2 2004 | `PolyXRD\cod_data\PDF2_2004.sqlite`（214 MB） | **163,834** | 内嵌 `peaks_d/peaks_i` | 侧车索引已建 |

COD 全库 CIF 归档：`D:\Project\XRD\PolyXRD\cod\cif`（522,545 个 CIF）。

## 3. 挂载机制

- **注册表**：`multi_db.list_libraries()` 返回 `cod_inorganics`（默认）/ `pdf2_2004` / `cod_full`
  三条 `LibraryRecord`（id、显示名、kind、路径、条目数（惰性）、可用性 + 不可用原因、note）。
- **只读打开**：`multi_db.open_library(id)` 返回只读（`mode=ro` + `query_only=ON`）的
  XinMatch-schema 连接，可直接喂 `search_match` / `fetch_entries_by_ids`；
  不可用抛 `LibraryNotAvailableError`（消息即友好原因）。
- **路径解析**：开发态 `parents[3]/data/`；冻结态 `sys.executable` 同级 `data/`（与 dist 布局一致）。
- **GUI**：菜单「设置 → 参考数据库…」表格列出三库（名称/条目数/路径/状态，不可用置灰显示原因），
  单选切换并持久化到 YAML 配置 `reference_db.selected_library_id`；
  `MainWindow.open_search_library()` 在所选库不可用时弹警告并回退默认库，保证检索始终可用。

## 4. PDF-2 2004 直接挂载（已打通并验证）

- 源库只读（`mode=ro`，带 `-wal/-shm` 侧车时绝不写源）；构建**侧车搜索索引**到
  `%USERPROFILE%\.xinmatch\indexes\pdf2_2004_xinmatch.db`（可用 `XINMATCH_USER_DATA` 覆盖），
  不入源目录。
- 决策：`entry_id = ref_id`（163,834 行零 NULL 且唯一，与 `display_id` 等价）；
  `mineral_name = mineral` 非空否则 `name`；峰为 `peaks_d/peaks_i` 逗号串，取最强 100、按强度降序。
- 实测：**163,834/163,834 条（0 跳过）、7,921,637 峰、构建 173.8 s、产物 693 MB**；
  真实条目核验：石英 `PDF2-010649` 最强峰 3.35 Å、方解石 3.04 Å、刚玉 2.55 Å，均正确；
  `open_library("pdf2_2004")` + 检索链路可用。
- 重建：`python -m xinmatch.core.db.pdf2_index`（一次性，约 3 分钟）。

## 5. COD 全库构建（已全量完成）

- `tools/build_cod_full_xinmatch.py`：CIF 归档 → XinMatch-schema DB（entries+peaks），
  支持 `--out / --start / --limit / --resume`、增量写入、进度日志、条/min 与 ETA
  （断点续跑水位表 `build_progress`）。
- **全量实测（2026-10-09 已入库，commit 7a88494）**：`data/cod_full.db`（941.8 MB）
  **entries=112,734 / peaks=10,979,059 / elements=527,398**，schema 与默认库一致
  （entries/peaks/elements/element_combo/build_progress），可直接被 search 查询与挂载。
- 300 条切片吞吐 ≈1,472 条/min；全量约 2 小时内完成（含大胞相反射较多的耗时）。
- **检索质量结论（2026-10-10 核验）**：用全库 112,734 条重跑 L3 黄金基线，Top-1 一致率
  反降至 1/13（无机库为 9/13）——全库含大量重复/低质量卡片（同一物相多卡片、实验与
  理论条目并存）稀释 FoM 排序。**默认检索保持精选无机库 `data/cod_inorganics.db`
  （71,199），全库仅作覆盖性挂载/人工查阅**，不作为默认搜索库。
- 用法示例：

```powershell
# 后台全量（断点续跑）
python -m tools.build_cod_full_xinmatch --out data\cod_full.db
# 先跑一小段验证
python -m tools.build_cod_full_xinmatch --limit 500 --out data\cod_full.db
```

## 6. 许可提示

- **PDF-2 2004 为 ICDD 商业授权数据**：侧车索引与检索结果仅供本地使用，不得随 XinMatch
  再分发；`PDF2_2004.sqlite` 来自用户自有授权的 PolyXRD dump。
- COD 数据遵循其公开许可（CIF 归档来源不变）。
- 参考软件 专有库（`.mti` 等）不复制、不逆向、不随包。

## 7. 后续建议（不在本版本范围）

1. ~~GUI 提供 PDF-2 源路径 / 侧车索引重建按钮~~ ✅ 已完成（2026-10-09，体验修订轮）：参考数据库对话框「PDF-2 源路径…」，持久化 `config.yaml` 的 `pdf2_source_dir`。
2. ~~COD 全库一键后台构建任务（带进度条与断点续跑，产物自动注册）~~ ✅ 已完成：对话框「构建 COD 全库…」后台线程 + 进度条/日志 + 可取消，全量产物已注册（见第 5 节）。
3. 将 `COD_inorganics.sqlite`（与默认库同源）注册为可选挂载，供不随包分发的部署场景。
4. 全库检索质量治理（去重/优选卡片）以让 COD 全库也可作为搜索库——当前结论是保持无机库为默认搜索库。
4. 检索前可选库的连接复用与预热（首次打开 71k/163k 条库的索引加载耗时优化）。
