## XinMatch v3.0.0 — `.xinDB` 单一格式收口 · COD-Inorg 内置默认库 · 内部版红字标识

> 基线 `v2.0.0`｜全量回归 **1570 passed / 4 skipped / 1 xfail**（`pytest tests`，12m14s，EXIT=0）

### 一、默认库换成 COD-Inorg（`*.xinDB`），并**打进便携包**

| 项 | v2.0.0 | v3.0.0 |
|---|---|---|
| 默认库 | `data/cod_inorganics.db`（v2 SQLite，712 MB） | `COD-Inorg-20261020.xinDB`（v3 列存，113 MB） |
| 便携包能否直接检索 | 不能（须另下 512 MB 库包再挂载） | **能**（`<exe>/data/` 已内置） |
| 库来源解析 | 硬编码 | `XINMATCH_XINDB_DIR` → `<exe>/data` → `<exe>/_internal/data` → `../XinMatch-DataBase/data`（源码态） |

* 库注册表 `core/db/multi_db.py` 全量重写为 v3-only：`KIND_XINDB` + 四个内置 id
  （`xindb_cod_inorg` 默认 / `xindb_cod_full` / `xindb_pcod_inorg` / `xindb_tcod_inorg`），
  按 `<Prefix>-<YYYYMMDD>.xinDB` 取**最新快照**；`open_library()` / `open_search_database()`
  返回只读 `XinDBReader`。
* `xinmatch.spec` 新增 `_find_bundled_xindb()` 把默认库收进 `data/`；
  `tools/build_exe.ps1` 把库从 PyInstaller 6 的 `_internal/data` 移到 `<exe>/data`（用户可直接替换）。

### 二、旧格式运行期代码**删除**（不是弃用）

* 删除 `core/db/polyxrd.py`（PolyXRD `phases` dump 转换层）与 `core/db/pdf2_index.py`（PDF-2 转换层）。
* `ui/dialogs/library_dialog.py` **720 → 约 300 行**：只做 列表 / 挂载 / 卸载 / 刷新，
  构建线程与建索引线程全部移除；`PDF-2 源目录` 配置项删除。
* CLI `libraries` 只剩 `--add` / `--remove`（`--build` / `--force` / `--no-build` 移除）。
* `core/batch.py`、顶层 API `identify_phase` / `full_analysis` 从裸 `sqlite3.connect` 改走
  `open_search_database()` —— 否则会落到已删除的 v2 行表路径。
* 删除 10 个 v2 专用测试文件；新增 `tests/xindb_support.py`（`write_xindb` 造真实 `.xinDB`）。

### 三、内部评估版：状态栏**红色加粗**「内部评估版本」

* `_build_statusbar()` 用控件级 stylesheet：`color: #d32f2f; font-weight: bold; padding: 0 6px;`，
  `objectName = internalBuildLabel`，`addPermanentWidget(label, 1)` 贴状态栏最右端。
* 为什么挂控件而不是全局 QSS：状态栏随主题重刷，控件级规则优先级更高，换主题不掉色。

### 四、附件说明

| 附件 | 内容 |
|---|---|
| `XinMatch-Setup-3.0.0.exe` | 正式版安装包（**含注册机制**，状态栏显示 `已注册：<单位>` / `未注册`），**内置 COD-Inorg 库** |
| `XinMatch-Internal-3.0.0.zip` | 便携包 = **内部评估版**（免安装、无注册机制，状态栏**红字**「内部评估版本」），**内置 COD-Inorg 库** |
| `XinMatch-Databases-COD-Inorg-3.0.0.zip` | COD 无机物库独立包（`*.xinDB`，给已有程序换库/补库） |
| `SHA256SUMS.txt` | 以上附件的 SHA-256 |

### 五、升级提示

* 从 v2.0.0 升级：**旧的 `.db` / `.sqlite` 参考库不再可用**（挂载会被明确拒绝并提示格式已移除）。
  请改用 `COD-Inorg-*.xinDB`（本版已内置；PCOD / TCOD 在
  [XinMatch-DataBase](https://github.com/PolyXRD/XinMatch-DataBase) 的 Releases 分发）。
* 其它 `*.xinDB` 库仍可从任意文件夹挂载：`设置 → 参考数据库…` 或 `xinmatch libraries --add <path>`。
