## XinMatch v3.6.3 — 元素限定四态 + 闭环（口径对齐 PolyXRD）

> 基线 `v3.6.2`（源码 `41279d4`）｜本版动两条：**元素约束**链路与
> **默认检索模式**。
> `ElementState` 扩到四态、新增闭环开关、预筛多一条「至少含一个」通路；
> 物相鉴定默认从「峰列表 FoM（寻峰）」改为「**FPFM 全谱拟合（不寻峰）**」。
>
> **旧用法逐位不变**：`closed_world` 默认 `False`、新增的 `HAS` / `MAYBE`
> 不被旧存档使用，所以「只标必有/没有」的行为与 v3.6.2 完全一致；
> 基准数字（真实谱相召回 30/43 等）不动 —— 快速录入生成的补集约束
> （113 个 `EXCLUDE`）与闭环写法换算出的 `elements_excluded` 是同一个集合。
>
> v3.6.1 / v3.6.2 的安装包均**未人工验收、未打 tag、未发布**；本版尚未构建二进制。

### 一、要解决的问题

用户原话：

> 元素周期表的元素限定逻辑参考 `D:\Project\XRD\PolyXRD` 实现

XinMatch v3.6.2 之前只有三态，两个真实短板：

1. **没有「至少含一个」**。用户想表达「样品是 MgO 或 CaO 或 CaCO3 这一族」，
   只能把 Mg、Ca、C、O **全标成「必有」** —— 而那是 AND 语义，结果只剩
   CaMg(CO3)2，恰好把最常见的单组分相挡在门外。
2. **没有闭环**。「只允许样品里检出的这几个元素」只能写成「其余 113 个元素
   全部标为没有」（v1.4 的「其余元素排除」快捷录入），逐点 118 个按钮不现实，
   而且打开周期表弹窗会看到 113 个红框，反而看不出自己选了什么。

PolyXRD 的四态 + `closed_world` 正好补这两块
（`src/polyxrd/utils/formula_parser.py::elements_match_filter` +
`src/polyxrd/views/widgets/element_periodic_table.py`）。

### 二、语义（与 PolyXRD 逐条对齐）

记 S = 物相元素集，P / H / M / E = 必有 / 含有 / 可能 / 没有：

| 类别 | 判定式 | 含义 | 预筛落地 |
|---|---|---|---|
| 必有 P | `P ⊆ S` | 每个都必须出现（AND） | `elements_allowed` |
| 含有 H | `S ∩ H ≠ ∅` | 至少含其中一个（OR） | `elements_any`（**新增**） |
| 可能 M | 无强制条件 | 只放宽闭环的允许池 | 只参与池计算 |
| 没有 E | `S ∩ E = ∅` | 含任一即淘汰 | `elements_excluded` |

两条附加规则，都容易漏：

* **必有已满足时不再要求「含有」**。否则纯金属这类单元素相永远进不了候选。
* **闭环**：`P∪H∪M` 非空时，未指定元素一律当作「没有」，等价于
  `S ⊆ P∪H∪M`。三者全空 = 全库检索；只勾「没有」= 开放世界（只排除这些元素）。

### 三、做了什么

#### ① `core` —— 模型与判据（`xinmatch/core/model/restraints.py`）

`ElementState` 由三值扩到五值，**旧值不变**（`red` / `yellow` / `green`），
新增 `HAS = "has"` 与 `MAYBE = "maybe"`，所以旧 `.xinm` 存档、YAML、
`Restraints.from_dict` 全部照常加载。

```python
class ElementState(str, Enum):
    EXCLUDE  = "red"      # 没有
    OPTIONAL = "yellow"   # 不限制（闭环开启时视同「没有」）
    REQUIRED = "green"    # 必有（AND）
    HAS      = "has"      # 含有（OR，至少含一个）
    MAYBE    = "maybe"    # 可能（只放宽闭环允许池）
```

`Restraints` 新增 `closed_world: bool = False`（进 `to_dict` / `from_dict`，
旧存档缺这个键 → 默认 `False`）；
`passes_elements(entry_elements, *, closed_world=False)` 重写为四态判据。

#### ② `core` —— 唯一的换算点 `element_constraint_sets()`

```python
required, any_of, excluded = element_constraint_sets(restraints)
# → prescreen(elements_allowed=required, elements_any=any_of,
#             elements_excluded=excluded)
```

闭环不新开通路：它把「118 元素 − 允许池」直接补进 `excluded`
（`S ⊆ 池` ⟺ `S ∩ 池外 = ∅`），复用既有的 `element_inv` 倒排过滤。
预筛、SQL 直查（`query_filter.search_by_elements`）、基准脚本
（`tools/bench_iucr._pools`）**三处都调这一个函数**，口径不可能漂移。

#### ③ `core` —— 预筛新增 `elements_any`

`XinDBReader.element_union_filter()`：含有 *elements* 中**至少一个**的物相。
与 `element_filter`（必须全含）是一对对偶。`prescreen(..., elements_any=…)`
把它与另外两条通路取交集。

#### ④ GUI —— 四态周期表（`xinmatch/ui/periodic_table.py`）

* 点击顺序改成 PolyXRD 的「不限制 → 含有 → 可能 → 没有 → **必有**」——
  「必有」置于**末位**：它过滤最狠，误点一次只是回到起点，而不是把候选清空。
* 四态**不只靠颜色**：线型 + 线宽 + 字重三重编码（红绿色盲友好，缩图与黑白打印也能分）

  | 状态 | 背景 | 边框 |
  |---|---|---|
  | 不限制 | `#f7f8f9` | 1 px 实线 灰 |
  | 含有 | `#e8f5e9` | 2 px 实线 绿 + 加粗 |
  | 可能 | `#fff8e1` | 2 px **点线** 琥珀 |
  | 没有 | `#fbdede` | 2 px **虚线** 红 + 加粗 |
  | 必有 | `#d8f0de` | **3 px** 实线 深绿 + 加粗 |

* 图例只列四种生效状态（`LEGEND_ORDER`），常显在网格上方。
* 新增 `grouped()`（按状态分组，摘要行与测试共用）、
  `apply_light_elements()`（一键把 O/C/H/N/S 标为「含有」，
  **只填未标的格子**，用户已明确标过的一律不动）。

#### ⑤ GUI —— 面板新增两项

| 控件 | 行为 |
|---|---|
| 复选框「限定在所选元素内」 | 闭环开关。旁边常显一行提示：`闭环已开启：允许池 N 个元素，其余 118−N 个一律视为没有`；只开闭环而不标任何元素时提示「等价于全库检索」，避免用户以为自己在过滤 |
| 按钮「补轻元素」 | O / C / H / N / S → 「含有」。EDX/EDS 常测不出轻元素，而氧化物 / 碳酸盐 / 氢氧化物在水合、风化样品里极常见，漏填会把整类相排除 |

摘要行改为四态分组着色（`必有 / 含有 / 可能 / 没有`，颜色与按钮同源），
超过 12 个元素截断为前 12 个加省略号。

#### ⑥ 文案统一

`必含 → 必有`、`排除 → 没有`（与 PolyXRD 一致，也与「含有 / 可能」构成同一套词）。
涉及周期表 tooltip、摘要行、弹窗提示、主窗口功能提示、`main_window` 的
「限制条件」说明。

#### ⑦ 物相鉴定默认改用 FPFM 全谱拟合（用户要求）

`DEFAULT_SEARCH_MODE = SEARCH_MODE_FPFM_FULL`。下拉框**选项顺序不变**
（「峰列表 FoM」仍是第 0 项），默认项靠 `findData(DEFAULT_SEARCH_MODE)` 选中，
不靠「第 0 项恰好是默认」这种隐式约定；用户随时能一键切回寻峰模式。

这里有一处**必须让用户看见的交互**：FPFM 检索链（`core/search/fpfm.py`）没有
`restraints` 形参，元素四态 / 闭环到不了预筛 —— 也就是「样品元素」设了也不生效。
默认改成 FPFM 后，这个组合会变成常态，所以工具栏的「样品元素」按钮在
**有约束 + FPFM** 时追加常显后缀 `｜FPFM 下不生效`（不弹模态框，
遵循「常显状态 + 非阻塞提示」）；切回峰列表 FoM 后缀自动消失。
检索时原本那条 8 秒状态栏提示保留。

> ⚠️ 因此：**要用元素限定做化学先验，请先把工具栏下拉框切回「峰列表 FoM（寻峰）」**。
> 这是 FPFM 检索链的结构限制，不是界面 bug；本版没有改动 FPFM 内核。

### 四、踩到的坑

1. **`min-width` 作用于内容矩形，而边框宽度逐态不同**。
   旧代码三态统一 2 px 边框，`min_w = cell_w − 2·2` 恰好成立；
   改成 1/2/3 px 后，同一个 `min_w` 会让「不限制」的 `minimumSize()`
   比 `setFixedSize()` 小 4 px —— 布局一旦重算尺寸就把它压小、符号被裁。
   修法：按**本态宽度**扣减（`min_w = cell_w − 2·border`），
   这才是 QSS min-* 的真实语义。

2. **「必有已满足则丢弃含有」必须落在换算点**，不能只写在
   `passes_elements`。预筛会把 `elements_allowed` 与 `elements_any`
   取交集；只在单条判据里放行，端到端仍然被 AND 一次，用户看到的现象是
   「我明明写了必有 O，只含 O 的相却不见了」。
   回归用例：`test_must_have_suppresses_the_any_of_filter`。

3. **`elements_any` 的未知元素必须「跳过」而不是「清空」**，
   与 `elements_allowed` 相反：后者遇到库里没有的元素要返回全 `False`
   （不可能满足），前者它只是**没有发言权**（不可能担保）。
   把这个方向搞反，一个拼错的符号会静默清空结果。

4. **`Restraints.elements` 是字典，重叠优先级规则不可达**。
   PolyXRD 的扁平列表 API 需要「必有 > 含有 > 可能 > 没有」去重；
   这里一个元素只有一个状态（`set_element` 后写覆盖先写），
   照抄去重只会留下没有测试覆盖的死分支。改成在 docstring 里说明这条差异。

5. **补集写法与闭环写法等价，但不是处处逐位相同**。
   唯一差异是**元素集为空**的退化物相：闭环形式还要求「至少命中一个允许池
   元素」，补集形式不要求。真实库里不存在零元素物相，所以检索上等价
   （PolyXRD 的 `test_empty_elements_phase_excluded_when_closed` 站在闭环一侧）。
   保留补集写法给 CLI `--sample-elements` 共用，两条路径由
   `test_closed_world_equals_the_complement_restraint` 钉住。

6. **旧的 `lastfailed` 缓存会误导**。`.pytest_cache/v/cache/lastfailed`
   里残留着旧目录结构下的条目（`tests/ui/test_smpf_kalpha2.py` 等文件已不存在），
   `--lf` 只会选中确实还存在的那些。判绿仍按进度行字符统计 + `--collect-only`
   对账，不要看这个文件。

### 五、验证

| 项 | 结果 |
|---|---|
| `ruff check .` | All checks passed! |
| `mypy xinmatch/core` | Success: no issues found in 99 source files |
| `tests/test_version_consistency.py` | 5 passed |
| 全量回归 | **1867 = 1862 passed / 4 skipped / 1 xfailed / 0 F / 0 E**（基线 1809 + 元素四态 55 + 默认模式 3），`--collect-only` 求和 **1867** 精确对账 |

`exit code` 仍可能为 1：pytest 退出时清理 `pytest-of-Administrator` 临时目录
（>50 个文件）会被沙箱钩子拒删并打印 `[safe-delete]…` JSON —— 那是钩子输出，
不是测试失败；判绿看进度行字符统计。**注意**：该钩子会在 `[100%]` 之后
截断 pytest 的汇总段，`-q` 的 `=== FAILURES ===` 与最后一行统计可能不落盘，
所以失败必须靠进度行里的 `F` / `E` 计数定位（再单文件复跑）。

新增用例 58 项：

| 文件 | 数量 | 内容 |
|---|---|---|
| `tests/model/test_element_filter_four_state.py` | 25 | PolyXRD 的 11 条语义断言 + 换算点 + 序列化兼容 + 与补集写法等价 |
| `tests/db/test_prescreen_element_any.py` | 17 | `element_union_filter` 语义、未知元素方向、预筛交集、`HAS`/`MAYBE`/闭环端到端 |
| `tests/ui/test_periodic_table.py` | +10 | 五态循环、tooltip 全循环、四态视觉可分、图例、`grouped`、补轻元素、闭环开关与提示 |
| `tests/ui/test_element_restraints.py` | +3 | 闭环开关传进 `Restraints`、快速录入不误开闭环 |
| `tests/ui/test_search_mode.py` | +3 | FPFM 为默认且下拉框选中项一致、多窗口一致、可一键切回 FoM、有约束时 FPFM 常显提示（切回即消失） |

### 六、关键设计决定

* **不新建「元素约束引擎」**。预筛原本就有 `elements_allowed` /
  `elements_excluded` 两条通路，四态只需要补 `elements_any` 一条；
  闭环用补集复用 `elements_excluded`。核心改动是「多一条 OR 通路 + 一个换算点」，
  不是重写检索链。
* **`OPTIONAL` 与 `MAYBE` 是两个状态**，不是同义词。开放世界里两者都不产生
  硬条件（都只给 +0.1 的弱加分）；一旦打开闭环，`MAYBE` 进允许池、
  `OPTIONAL` 被当作「没有」。这正是 PolyXRD `NONE` / `MAYBE` 的区别，
  也是「只允许检出元素」能用一个开关表达的原因。
* **闭环默认关闭**。默认开会让所有老用户的「标一个必有」变成「只允许这一个元素」，
  直接把候选清空。默认关闭 + 面板常显提示，才是可接受的迁移路径。
* **默认检索模式改用 FPFM 是界面默认值变更，不是检索内核变更**。
  两条检索链一行未动；把「默认」表达成显式常量 + `findData()` 选中，
  而不是偷偷调选项顺序，这样按 index 切换的既有测试与用户既有操作习惯
  都不会被打破。
* **FPFM 不消费元素约束这件事必须常显**。默认切到 FPFM 后，
  「设了样品元素却不生效」会从边缘情况变成常态；用工具栏按钮后缀提示，
  而不是弹模态框或只留一条 8 秒状态栏消息。

* **闭环开关不放在弹窗里**。它决定的是检索范围，而非某个元素的状态；
  与「启用元素过滤」同级，常显在面板上。

### 七、升级注意

* 旧 `.xinm` 存档 / YAML 里的 `{"red","yellow","green"}` 全部照常读入；
  新建档会多写一个 `closed_world` 键（旧版本读到会忽略，不影响打开）。
* 界面上原来叫「必含 / 排除」的地方现在叫「必有 / 没有」，**语义未变**。
* **Open 之后直接点 Search-Match 现在走 FPFM 全谱拟合**（不寻峰、不覆盖峰列表）。若你的工作流依赖峰列表或元素限定，请先把工具栏下拉框切回「峰列表 FoM（寻峰）」——工具栏「样品元素」按钮会在有约束时提醒 `｜FPFM 下不生效`。
* 想复现 v3.6.2 的行为：不写 `HAS` / `MAYBE`、不开闭环即可，逐位一致。
