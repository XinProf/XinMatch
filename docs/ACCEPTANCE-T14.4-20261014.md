# T14.4 串口仪器控制 — 验收文档（2026-10-14）

> 任务来源：路线图 Phase 14 最后一项（⬜）→ 本迭代完成。
> 提交：`0b3a3b0`（已推送 GitHub master，0/0 同步）
> 前置依赖：`pyserial>=3.5`（已加入 pyproject 正式依赖，venv 实测 3.5）。

## 一、任务范围

ROADMAP T14.4：「串口仪器控制（对应参考软件 Qt5SerialPort 能力，P2 可选）：串口配置、数据采集、实时图谱。验收：能接收串口数据流并实时绘制。」

本轮交付（core + CLI，GUI 采集面板留后续，见边界声明）：

| 层 | 交付物 | 说明 |
|---|---|---|
| core | `xinmatch/core/instrument/serial_port.py` | 端口扫描 `list_serial_ports()` + 安全打开 `open_serial()`（pyserial 懒加载，缺失时清晰报错；URL 协议兼容 `loop://`） |
| core | `xinmatch/core/instrument/collector.py` | `parse_point`（多种分隔符/科学计数/注释行容错）、`iter_lines`（EOF/stop_event/max_lines 停止）、`SerialCollector`（流式解析 + `on_point` 实时回调 + 累计 points + 两列 ASCII 落盘） |
| core | `xinmatch/core/instrument/__init__.py` | 公开 API 汇总（零 pyserial 硬依赖——import 包不需要串口栈） |
| CLI | `xinmatch instrument scan` | 枚举串口（JSON/文本） |
| CLI | `xinmatch instrument collect --port … [--baud --bytesize --parity --stopbits --timeout --seconds --max-points --out --verbose --live-plot]` | 流式采集；`--live-plot` 实时绘制（matplotlib 懒加载，缺失自动降级为进度提示，采集不中断） |

## 二、确认项清单（逐项给出证据）

| # | 确认项 | 结果 | 证据 |
|---|---|---|---|
| 1 | 端口扫描在无串口硬件的机器上不崩溃 | ✅ | CLI 实跑 `instrument scan --json` → `{"ports": [], "count": 0}`，exit 0 |
| 2 | 串口打开对不存在的端口抛清晰异常 | ✅ | `test_open_serial_missing_port_raises`：`COM_DOES_NOT_EXIST_ZZZ` → OSError（SerialException 为其子类） |
| 3 | `open_serial` 兼容 pyserial URL 协议（`loop://` 回环） | ✅ | `test_open_serial_loopback_url`：写 `hello` 读回 `hello`（真实串口栈） |
| 4 | 数据行解析覆盖常见仪器输出格式 | ✅ | 参数化测试 9 种格式：逗号/空格/TAB/全角逗号/分号/科学计数/带表头行/尾部杂质；注释行（`#`/`//`/`;`）、空行、单数、纯文本 → 跳过 |
| 5 | 采集器计数正确（原始行/解析点数/跳过数） | ✅ | `test_collect_parses_points_and_counts_skips`：5 行 → 3 点 + 2 跳过 |
| 6 | 流式回调（实时绘制的接入点）按点触发 | ✅ | `test_collect_invokes_on_point_inline`：回调收到与 `points` 完全一致的点序列 |
| 7 | 停止条件：EOF / max_points / stop_event | ✅ | 三个独立用例分别验证 |
| 8 | 落盘文件为两列 ASCII，且能被 XinMatch 自身导入 | ✅ | `test_collector_datafile_roundtrip_via_load_pattern`：`load_pattern` 回读 3 点，two_theta/intensity 长度=3 |
| 9 | CLI 端到端：文件写出 + 汇总字段 | ✅ | `test_instrument_collect_writes_file`：raw_lines=5 / points=3 / skipped=2 / first/last 点正确 / 文件 3 行 |
| 10 | CLI `--max-points` 截断 | ✅ | 100 行输入 → 恰好 4 点 |
| 11 | CLI 无 `--out` 时 stdout 逐点输出 | ✅ | `test_instrument_collect_stdout_mode`：2 行两列输出 |
| 12 | `--live-plot` 双路径不破坏采集 | ✅ | `test_instrument_collect_live_plot`：有 matplotlib → Agg 后端绘制不崩溃、数据仍落盘；无 matplotlib → 降级 warning + 采集继续（3 点均保存） |
| 13 | 相关测试全绿 | ✅ | `tests/instrument`（37）+ `tests/test_batch_core.py` + `tests/cli/test_cli.py`（28）= **65 passed / 0 failed**；`tests/test_batch_runner.py` 4/4（batch.py 注解修复回归） |
| 14 | ruff 全绿（本轮文件） | ✅ | `xinmatch/core/instrument/*`、`xinmatch/core/batch.py`、`xinmatch/cli/main.py`、`tests/instrument/*` → All checks passed |
| 15 | mypy 本轮零新增错误 | ✅ | 全仓 `mypy xinmatch` 仅剩 12 处已声明存量（smoothing 2 / background 2 / entry 2 / fom_criteria 3 / colors_dialog 1 / periodic_table 2，STATUS.md 已登记，均非本轮引入）；instrument/batch/main 零错误 |
| 16 | 顺带清偿 T14.3 欠账 | ✅ | `batch.py` 3 处 mypy 错误（`pattern_path` 窄化、`peaks` 注解、`_resolve(config_dir→base_dir)`）已修，`test_batch_core`/`test_batch_runner`/`tests/cli` 全绿 |

## 三、为什么这次验收快（对照用户上次对验收费时的反馈）

T6.0 验收耗时的两大来源——① 13 真实谱 + 13 合成谱 × 150 候选全谱最小二乘的算力时间；② pytest 沙盒收尾钩子拦截临时目录清理导致的判定成本——**本次均不适用**：

1. **零真实谱/零全谱拟合**：T14.4 是纯 I/O 与文本解析功能（新模块），不触碰任何检索/拟合/定量算法路径，无需逐谱验收。
2. **无全量核心回归（84min）**：改动面 = 4 个新文件 + 2 个已有文件（main.py 加子命令、batch.py 仅 3 行类型注解等价修复），全部是增量代码，与核心算法无共享状态。验证等价于「新功能全套测试 + 被改文件回归」，即上述 65 + 4 用例。**T14.3 同规模先例（仅相关测试 32 passed 即交付）**。
3. **沙盒判定成本为零**：本套件无临时目录堆积触发钩子，pytest 正常收尾、退出码 0。

## 四、诚实边界（未做/留后续）

| 项 | 状态 | 说明 |
|---|---|---|
| GUI 串口采集面板（配置对话框 + 实时图谱） | ⏸ 留后续 | ROADMAP「实时图谱」在 CLI 层以 `--live-plot` 落地（matplotlib 实时追加）；core 的 `on_point` 流式回调即 GUI 实时绘制的标准接入点（PySide6 信号槽可直接订阅）。未做 GUI 面板的原因：本机无真实串口仪器可验收、P2 可选优先级低、且 P13 GUI 改动需单独迭代。 |
| 真实硬件联调 | ⏸ 留用户环境 | 解析协议按通用「两列数值 ASCII 流」设计（覆盖逗号/空格/TAB/全角逗号/科学计数）；若用户仪器为二进制协议或带专有帧头，需按实测报文扩展 `parse_point`（core 单函数，扩展点单一）。 |
| `scan` 在无 pyserial 环境 | ✅ 已处理 | 返回空列表 + warning（`list_serial_ports`），不抛异常。 |

## 五、验证方式与覆盖范围

- 验证命令：`pytest tests/instrument tests/test_batch_core.py tests/cli/test_cli.py tests/test_batch_runner.py`（69 passed）；`ruff check`（本轮文件）；`mypy xinmatch`（12 处存量，零新增）；CLI 实跑 `instrument scan --json` / `instrument collect --help`。
- 覆盖：解析 9 格式 + 6 类跳过；停止条件 3 种；回调流；落盘往返（经 `load_pattern` 真导入）；CLI 端到端 5 用例；live-plot 双路径。
- 未覆盖（如实）：真实串口硬件联调（本机无仪器）；GUI 面板（留后续）；二进制/专有协议报文（需实测报文样本）。
