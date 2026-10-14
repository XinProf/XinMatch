# T2.4 Bruker RAW 完整支持 — 验收文档（2026-10-14）

> 任务来源：路线图 T2.4（🟡，`.raw` TODO）→ 本迭代完成 v3/v4 并闭环 v1 结论。
> 提交：`(待回填)`

## 一、任务范围与关键探查结论

ROADMAP T2.4 验收：「至少覆盖 Bruker RAW v1/v2/v3 各 1 个样本」。探查（GSAS-II 官方文档化导入器 `G2pwd_BrukerRAW` + PRONOM 签名库 + 本机 170+ 个真实 .raw 样本 magic 统计）后定案：

| 版本 | magic | 结论 | 依据 |
|---|---|---|---|
| v1 | `RAW `（4 字节） | ⛔ **不可实现** | **GSAS-II 官方导入器明确拒绝**（`Read of Bruker "RAW " (pre-version #) file not supported`）；PRONOM 无 v1 签名；无任何公开格式文档；本机 170+ 真实样本中 0 个 v1 文件 |
| v2 | `RAW2` | ✅ 已有（`rigaku.py::read_raw2`，IUCr 真实样本测试在册） | 布局与 GSAS-II ver.2 完全一致（偏移级核对） |
| v3 | `RAW1.01` | ✅ **本次实现** | GSAS-II 文档化布局 + **本机真实样本 data035 验证**（10 块 × 147 点，文件被完全消费） |
| v4 | `RAW4.00` | ✅ **本次实现**（超出点名，顺手覆盖现役 Bruker D8 新格式） | GSAS-II 文档化布局；合成样本 round-trip；无真实样本（诚实声明） |

**「能否复用 gsas2 项目的」——探查答案**：GSAS-II 提供的是**格式布局的公开文档**（readthedocs 模块源码 + GADDS 参考手册），且其对 v1 的态度 = 不支持。本实现为 clean-room 自研（按公开布局重写、不复制 GSAS-II 代码，规避其许可条款不确定性，符合项目既定「clean-room implementation guided by publicly documented workflows」原则），模块 docstring 注明布局来源。

## 二、交付物

| 文件 | 内容 |
|---|---|
| `xinmatch/core/io/bruker_raw.py`（新） | `read_bruker_raw_v3(path, block=0)`：RAW1.01 固定头 + 多块容器（headLen/nSteps/start/step 偏移 + 单块 +40/多块 +extra 语义），返回 Pattern（轴/强度/波长/anode/Ka1/Ka2/半径元数据）；`read_bruker_raw_v4(path)`：RAW4.00 段式容器（segtype 30 光源段解析 Ka/anode、segtype 0 粉末 bank 解析轴/强度/发生器参数），返回第一个 powder bank |
| `xinmatch/core/io/detect.py` | `.raw` magic 检测新增 `RAW1.01 → FMT_RAW3`、`RAW4.00 → FMT_RAW4`（文本型 .raw 仍走文本路径，v1 `RAW ` 显式注释不支持） |
| `xinmatch/core/io/__init__.py` | `_READERS` 注册 `FMT_RAW3/RAW4`，`load_pattern` 全自动分发 |
| `tests/io/_samples.py` | `write_raw3`（单块/多块，head_len 字段遵循真实惯例 304 或 304−40）、`write_raw4`（段式生成器） |
| `tests/io/test_bruker_raw.py`（新，12 用例） | v3/v4 合成 round-trip、多块选块、越界报错、坏 magic 报错、detect/dispatch、v4 无 bank 报错、**真实 RAW1.01 样本验收** |

## 三、确认项清单

| # | 确认项 | 结果 | 证据 |
|---|---|---|---|
| 1 | v3 固定头偏移正确（radius/anode/Ka 系） | ✅ | 合成 round-trip：radius 250.0、anode "Cu"、ka1=1.5406 全回收 |
| 2 | v3 多块容器推进正确 | ✅ | **真实 data035**：10 块逐块 head_len=304/nSteps=147/start=57.75°/step=0.03°，末位 pos=9632 = 文件大小（完全消费）；探针与单测双重验证 |
| 3 | v3 block 选择与越界护栏 | ✅ | block 0/3/9 均正确选块；block=5（2 块文件）抛 ValueError |
| 4 | v3 真实谱峰位合理 | ✅ | data035 最强峰 59.64°（WC(200)/(102) 区），单测断言 59.4–60.2° 通过 |
| 5 | v4 段式容器解析（seg30 光源段 + seg0 数据段） | ✅ | 合成 round-trip：scan_type/start/step/Nsteps/kV/mA/usedWave/ka1 全回收；无 powder bank 时清晰报错 |
| 6 | detect 分发（FMT_RAW3/RAW4 → reader） | ✅ | `detect_format` + `load_pattern` 双路径 4 用例通过 |
| 7 | 坏 magic / 截断护栏 | ✅ | v3/v4 各自拒绝对方 magic；块截断、轴非法均抛 ValueError |
| 8 | 全量 io 回归 | ✅ | `pytest tests/io` = **100 passed / 0 failed**（含既有 RAW2/Rigaku/岛津/文本格式，无回归） |
| 9 | ruff / mypy | ✅ | 本轮 5 文件 ruff 全绿；mypy 本轮文件零错误 |

## 四、诚实边界

- **v1 未实现**：无公开格式文档 + GSAS-II 官方拒绝（同上表）。若用户能提供一份真实 `RAW ` 样本，可据二进制逆向另立任务。
- **v4 无真实样本**：仅合成 round-trip + 布局参照 GSAS-II 文档化实现。Bruker D8 用户如有 RAW4.00 文件可补充真实验收。
- **v3 多块语义**：残余应力/织构谱每个块是同一 2θ 窗口的不同 ψ 段；`load_pattern` 单谱语义返回 block 0（GSAS-II 同款默认），完整多块数据集处理留后续（与参考软件多段导入对标的独立功能）。

## 五、为什么本次验收费时可控

T2.4 为纯 I/O 新模块（不触碰检索/拟合/定量路径）：验证 = 12 个专项测试（含 1 个真实样本）+ tests/io 全量 100 用例回归，耗时 <2 分钟；无全量核心回归（84min）需求（与 T14.3/T14.4 同先例：增量 I/O 模块按相关套件验收）。
