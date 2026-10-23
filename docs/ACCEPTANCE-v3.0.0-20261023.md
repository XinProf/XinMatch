# XinMatch v3.0.0 验收记录（2026-10-23）

> 版本：**3.0.0**（基线 `v2.0.0`）· 主题：**.xinDB 单一格式收口 + COD-Inorg 内置默认库 + 内部评估版红字标识**
> 全量回归：**1570 passed / 4 skipped / 1 xfail**（`python -m pytest tests -q`，12 min 14 s，EXIT=0）

---

## 一、本次交付的三件事

### 1. 默认库 = COD-Inorg（`*.xinDB`），并且**打进便携包**

| 项 | v2.0.0 | v3.0.0 |
|---|---|---|
| 默认库 | `data/cod_inorganics.db`（v2 SQLite，712 MB） | `COD-Inorg-<快照>.xinDB`（v3 列存，113 MB） |
| 便携包能不能直接检索 | 不能，必须另下 512 MB 库包再挂载 | **能**，`<exe>/data/` 已内置 |
| 库来源解析 | 硬编码 `data/cod_inorganics.db` | `XINMATCH_XINDB_DIR` → `<exe>/data` → `<exe>/_internal/data` → `../XinMatch-DataBase/data`（源码态） |

* `xinmatch.spec` 新增 `_find_bundled_xindb()`：按
  `XINMATCH_BUNDLE_XINDB` → `<repo>/data/*.xinDB` → `<repo>/../XinMatch-DataBase/data/*.xinDB`
  解析，取**最新快照**收集进 `data/`；收集不到时**只 WARNING 不中断**（构建仍可用，运行期提示挂载）。
* `tools/build_exe.ps1` 新增步骤 3：把 PyInstaller 6 收进 `_internal/data` 的库**移到 `<exe>/data`**
  （用户可直接看到/替换库文件），并打印 `Bundled library OK : data\<file> (<N> MB)`。
* `multi_db._data_dir()` 冻结态按 `<exe>/data` → `<exe>/_internal/data` 顺序解析，单跑
  `pyinstaller xinmatch.spec` 也能找到库。

### 2. 旧格式运行期代码**删除**（不是弃用）

| 删除项 | 说明 |
|---|---|
| `core/db/polyxrd.py` | PolyXRD `phases` dump → 缓存检索索引的转换层 |
| `core/db/pdf2_index.py` | PDF-2 dump → 缓存检索索引的转换层 |
| `multi_db` 的 `KIND_XINMATCH` / `KIND_PDF2` / `KIND_POLYRD` / `cod_full` / `pdf2_2004` 等 id | 只留 `KIND_XINDB` + 四个内置 id（`xindb_cod_inorg` / `xindb_cod_full` / `xindb_pcod_inorg` / `xindb_tcod_inorg`） |
| `ui/dialogs/library_dialog.py` 的构建线程 / 建索引线程 / PDF-2 源目录 | 对话框 720 行 → ~300 行，只做 列库表 / 挂载 / 卸载 / 刷新 |
| CLI `libraries --build` / `--force` / `--no-build` | 只剩 `--add` / `--remove`（列存库自包含，无"建索引"一步） |
| `core/batch.py` 的 `sqlite3.connect` | 改 `open_search_database()`（返回 `XinDBReader`） |
| 顶层 API `identify_phase` / `full_analysis` 的 `sqlite3.connect` | 同上；`search_match` 按对象类型分派 `search_match_v3` |

删除的 v2 专用测试 10 个文件：`db/test_build_cod_full_curated.py`、`db/test_polyxrd.py`、
`db/test_pdf2_source_config.py`、`ui/test_library_build.py`、`ui/test_library_dialog_external.py`、
`ui/test_external_library_mount.py`、`test_build_cod_xinmatch.py`、`test_backfill_cells.py`、
`test_backfill_hkl.py`（+ 早期已删的 `test_backfill_*` 同批）。

### 3. 内部评估版：状态栏 **红色加粗**「内部评估版本」

* 文案与判定仍在 `xinmatch/utils/build_variant.py`（`INTERNAL_STATUS_TEXT`）。
* `ui/main_window._build_statusbar()` 用控件级 stylesheet：
  `color: #d32f2f; font-weight: bold; padding: 0 6px;`，`objectName = internalBuildLabel`，
  `addPermanentWidget(label, 1)`（贴状态栏最右端，吃掉剩余空白）。
* 为什么挂在控件而不是全局 QSS：状态栏会随主题重刷样式，控件级规则优先级更高，换主题不掉色。

---

## 二、测试账目

| 类别 | 文件 | 用例数 | 结果 |
|---|---|---|---|
| 库注册表（重写） | `tests/db/test_multi_db.py` | 17 | ✅ |
| 挂载注册表（重写） | `tests/db/test_library_registry.py` | 12 | ✅ |
| 参考库对话框（重写） | `tests/ui/test_library_dialog.py` | 13 | ✅ |
| 构建变体（新增） | `tests/utils/test_build_variant.py` | 11 | ✅ |
| 内部版红字标识（新增用例） | `tests/ui/test_registration_ui.py` | +2（共 11） | ✅ |
| CLI libraries（重写） | `tests/cli/test_cli_libraries.py` | 14 | ✅ |
| CLI search/run（库夹具改 .xinDB） | `tests/cli/test_cli.py` | 25 | ✅ |
| CLI FPFM（库夹具改 .xinDB） | `tests/cli/test_cli_fpfm.py` | — | ✅ |
| 批处理（库夹具改 .xinDB） | `tests/test_batch_core.py` / `test_batch_runner.py` | — | ✅ |
| **全量** | `pytest tests` | **1570 passed / 4 skipped / 1 xfail** | ✅ EXIT=0 |

新增测试基础设施：`tests/xindb_support.py`（`write_xindb(path, entries)`）——
往后再要"造一个小参考库"，一律用它写真实 `.xinDB`，**不要**再拼 v2 的
`entries`/`peaks`/`elements` 行表（那条路径已经不存在了，会得到
`LibraryNotAvailableError: 不是 .xinDB 库`）。

## 三、关键坑（留给后续维护）

1. **`search_match` 按连接对象类型分派**：传 `sqlite3.Connection` 会静默走已删除的 v2 路径；
   统一用 `open_library()` / `open_search_database()` 拿 `XinDBReader`。
2. **测试夹具不要写 `synth.db` / `ref.db`**：v3 只认扩展名 `.xinDB`（`_is_xindb` 判后缀）。
3. **PyInstaller 6 的 datas 落在 `_internal/`**，而运行期找 `<exe>/data` —— 两处都得能解析，
   否则"开发者本机能跑、解压到别人机器就不检索"。
4. **变体标记 `variant.txt` 必须在产物里**（onedir 根目录或 `_internal/`），
   `build_exe.ps1` 构建后立刻校验内容，错值直接中断（避免内部版静默退化成注册版）。
