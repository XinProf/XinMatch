# 样品集扩充验收记录（2026-10-11）

> 依据 T0.3/T0.4 样品集扩充计划，使用参考软件（SMPF：直接原始谱上全谱拟合，未寻峰、未做峰形处理）
> 对合成谱与独立样品实测，产出候选基线。数据库：COD-Inorg 2025.12.01。
> 原始候选产物：`D:\Project\XRD\test_xrd\match-candidate list-{jingzhun,alloption}\`（本仓库归档副本：`tests/baseline/ref20261011/`）。

## 一、合成谱 13 组：真相相全部命中 ✅

| 谱 | 真相相（COD） | jingzhun 结果 | alloption 结果 |
|---|---|---|---|
| synth_01 | Al₂O₃(2300448)+ZnO(2300112)+CaF₂(2300449) | ZnO #1 FoM=1.0000 | ZnO #1 FoM=1.0000 |
| synth_02 | SiO₂(5000035)+CaCO₃(2100992) | SiO₂ #1 FoM=1.0000 | SiO₂ #1 FoM=1.0000 |
| synth_03 | TiO₂ 锐钛(5000223)+金红石(2310486) | TiO₂ #1 FoM=1.0000 | TiO₂ #1 FoM=1.0000 |
| synth_04 | Fe₂O₃(2101167)+SiO₂(5000035) | Fe₂O₃ #1 FoM=1.0000 | Fe₂O₃ #2 FoM=0.9988 |
| synth_05 | CuO(9008961)+ZnO(2300112) | CuO #1 FoM=1.0000 | CuO #1 FoM=1.0000 |
| synth_06 | BaTiO₃(2100858) | BaTiO₃ #1 FoM=1.0000 | BaTiO₃ #1 FoM=1.0000 |
| synth_07 | NaCl(9000629)+KCl(9003112) | NaCl #1 FoM=1.0000 | NaCl #2 FoM=0.9986 |
| synth_08 | CaF₂(2300449)+Al₂O₃(2300448) | Al₂O₃ #1 FoM=1.0000 | Al₂O₃ #1 FoM=1.0000 |
| synth_09 | C 石墨(9000046) | C #1 FoM=1.0000 | C #1 FoM=1.0000 |
| synth_10 | Fe(5000217)+Fe₃O₄(2101535) | Fe #1 FoM=1.0000 | Fe #1 FoM=1.0000 |
| synth_11 | CaSO₄(5000040)+CaCO₃(2100992) | CaSO₄ #1 FoM=1.0000 | CaSO₄ #1 FoM=1.0000 |
| synth_12 | MgO(5000225)+MgAl₂O₄(5000120) | MgAl₂O₄ #1 FoM=1.0000 | MgAl₂O₄ #2 FoM=0.9998 |
| synth_13 | ZrO₂(2101234) | ZrO₂ #1 FoM=1.0000 | ZrO₂ #1 FoM=1.0000 |

- **jingzhun 模式（物相全部元素）**：13/13 Top-1，FoM=1.0000 全完美。
- **alloption 模式（+周期表一、二周期及 Na/Mg）**：13/13 命中；3 组（04/07/12）Top-2/3 但 FoM≥0.9986（被同一相的其他卡片挤占，多相谱部分次相 #1 为最强相）。
- **版本说明**：本次实测使用 v3 合成谱（FWHM≥0.1°、噪音 1.2%）。v4（FWHM≥0.15°、噪音 0.3%，更接近真实实验室特征，commit 1d3c28c）已生成待复测，不阻塞验收。

## 二、铜衍射谱系列（csuHJW）

| 样品 | jingzhun (Cu,O) | alloption | 结论 |
|---|---|---|---|
| Data007 | 空白 | 空白 | 谱数据特征：93.7% 数据点为零（背底=0），仅 204 非零点/5–7 个孤立峰，SMPF 无背景与统计信息可拟合 |
| Data008 | 空白 | 空白 | 同上：87.6% 为零，404 非零点 |
| Data009 | **Cu #1 FoM=1.0000**（96-710-1265 等 13 条） | **Cu #1 FoM=1.0000** | 1003 非零点（信息量足够），铜相完美命中 |

**定性**：Data007/008 空白是**谱数据本身**（背底全零、峰极少、无统计起伏）导致全谱拟合类检索无足够信息，**非导入格式或检索设置问题**——Data009 同系列同格式出候选且完美命中可证。建议：Data007/008 不纳入检索验收基线（或后续重新采集带背底的数据）。

## 三、新增独立样品基线（参考软件候选，供后续 XinMatch 对照）

| 样品 | jingzhun Top-1 | alloption Top-1 |
|---|---|---|
| CPD-1A（IUCr 标准，氟化钙） | CaF₂ FoM=1.0000 | — |
| CPD-1B | — | — |
| CPD-2（IUCr 标准，氧化锌） | ZnO FoM=1.0000 | — |
| BAUXITE（铝土矿） | Fe₂O₃ hematite FoM=1.0000 | — |
| CORUNDUM（刚玉） | Al₂O₃ corundum FoM=1.0000 | — |
| ShiJiKong1# | Dolomite FoM=1.0000（无元素限制） | — |
| ShiJiKong2# / 4b# / 5b# | （无元素限制，候选列表已归档） | — |

## 四、归档与后续

- 参考软件候选 CSV 归档：`tests/baseline/ref20261011/{jingzhun:19 文件, alloption:23 文件}`。
- 合成谱真相清单：`D:\Project\XRD\test_xrd\synthetic\manifest.md`（仓库外，工具 `tools/generate_synthetic_patterns.py` 可复现）。
- **后续待办**：① XinMatch 自身检索合成谱仍失败（峰列表偏移/分裂/弱峰稀释，独立问题，见 STATUS T0.8 方向）；② v4 谱复测确认不退化；③ 将合成谱纳入 XinMatch 检索验证集（真相已知，可直接断言）。
