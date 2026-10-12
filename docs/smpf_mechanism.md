# SMPF — Search-Match with Profile Fitting（全谱拟合检索）机制说明

> 交付日期：2026-10-11。模块：`xinmatch/core/search/smpf.py`。
> 本文为净室实现说明：仅依据 Rietveld / profile-fitting 公开准则（Rwp/Rexp/GOF；Young, *The Rietveld Method*）与解析 pseudo-Voigt 峰形（`xinmatch/core/peak/shapes.py`）撰写，不复制任何商业软件代码。涉及参考软件一律以"参考软件/对标产品"中性表述。
> 研究笔记 `docs/smpf_research_notes.md`（并行研究任务产出，2026-10-11，已入库）：含 SMPF 公开机制完整综述（概念与流程 / 峰形模型 / 背底处理 / Kα1-Kα2 双线 / 拟合判据 / 候选预筛 / 评分归一化，共 7 主题 + 按主题分组的参考来源清单）。本节仅归纳经本实现实验验证的三条关键结论，完整机制综述见该笔记。

---

## 1. 机制研究结论

SMPF 把"离散峰列表相关"的经典 search-match 升级为"连续全谱拟合"：对每个候选参考相，按 Bragg 定律把其 d–I 表渲染成一条伪 Voigt 连续谱，再对**整段实验谱**做受限最小二乘拟合，按拟合优度（Rwp/GOF）排序。

三个经实验验证的关键结论：

1. **背底必须在拟合内吸收，不能预扣除。** Rwp 的权重是 `w=1/y`。若先用 SNIP/多项式把背底预扣除，残余低强度点 `y` 很小，被 `w=1/y` 过度惩罚，Rwp 虚高、真相相与错误相分离度崩塌（实测：预扣除方案 Rwp≈0.42、GOF≈9.4；内吸收方案 Rwp≈0.09、真相/错误相 FoM 分离比 0.70 vs 0.33）。改为把二次背底基 `b0+b1·(2θ−50)+b2·(2θ−50)²` 放进最小二乘，让拟合自洽地吸收平滑背底，低强度点保持自然的大 `y`、只贡献其本征（小）泊松权重。
2. **全局单 FWHM 足够且更稳。** 实验室 Cu 靶在扫描区间内 Caglioti 宽高近似恒定，单参数宽度比 3 参数 U/V/W 便宜一个量级、且不发散。合成谱生成器用 Caglioti（U=0.006,V=−0.004,W=0.010，下限 0.15°），拟合收敛到 0.151°，正确。
3. **候选必须先预筛再精排。** 71,203 张卡片不能全量拟合。复用现有峰列表检索（`search_match`，`recall_strongest_peak=True`）召回 `prescreen_top_n=150` 张候选，仅对这 150 张做全谱拟合精排——峰列表召回已把真相相保留在 Top-20，真相相不会在预筛被丢掉。

---

## 2. 参数决策表

| 参数 | 取值 | 决策理由 | 实测依据 |
|---|---|---|---|
| 预筛方式 | 复用 `search_match`（寻峰→d 值召回） | 峰列表召回已含真相相；零新增算法 | 13 组合成谱预筛后真相相均在 150 候选内 |
| `prescreen_top_n` | **150**（可调 100–300） | 候选太少漏真相相，太多精排超时 | 150 卡精排 12–28s，全流程 <120s |
| FWHM 模型 | **全局单 FWHM**（init 0.2°，bounds 0.08–0.6°） | Caglioti 在扫描区间近似恒定；单参数稳、快 | 合成谱收敛 0.151°，贴近生成器 0.15° 下限 |
| η（伪 Voigt 混合比） | 拟合，init 0.5，bounds 0.05–0.95 | 留一个自由度吸收峰形不对称 | 合成谱 η≈0.5–0.6，真实谱 0.4–0.95 浮动 |
| 背底 | **二次多项式基纳入最小二乘**（非预扣除） | 见机制结论 1 | 真相 Rwp 0.09 vs 错误相 0.26–0.28 |
| Kα 双线 | 运行时旋钮：`smpf_kalpha2_enabled`（默认开）+ `smpf_kalpha1_angstrom`（0=跟随样品波长）+ `smpf_kalpha2_angstrom`（默认 1.5444 Å，Kα1:Kα2=2:1 强度） | 真实实测谱是双线；关掉旋钮即退化为 Kα1 单线（合成谱/老行为兼容） | 真实谱双线配置跑通 13/13；`tests/search/test_smpf_kalpha2.py` 覆盖旋钮解析 |
| FoM 映射 σ | **σ=0.25**，`FoM=exp(−Rwp/σ)` | 干净合成拟合 Rwp≈0.08–0.12 → FoM≈0.6–0.8；Rwp>0.5 → FoM<0.14 强压 | 真相/错误相 FoM 分离显著 |
| 2θ shift 边界 | ±0.3° | 仪器零位偏移量级 | 拟合 shift 多在 ±0.1° 内 |
| 峰形评估窗口 | 每反射 ±1.5° 局部窗 | 全网格 (M×N) 广播致 150 卡精排 492s；局部窗降到 12–28s | 性能实测 |
| 最大函数评估 | `max_nfev=60` | 控制单候选耗时 ≤0.5s | 150 卡精排 12–28s |

---

## 3. 评分定义

仅对 `y_i>0` 的点计算：

```
Rwp  = sqrt( Σ w_i (y_i − yc_i)² / Σ w_i y_i² ),   w_i = 1/y_i
Rexp = sqrt( N / Σ w_i y_i² ) = sqrt( N / Σ y_i )
GOF  = Rwp / Rexp
FoM  = exp(−Rwp / σ_fom),  σ_fom = 0.25,  ∈ (0, 1]
```

无正强度点时 `Rwp=Rexp=GOF=inf`、`FoM=0`。`FoM` 与峰列表 FoM 数值同向可比（越大越好）。

---

## 4. 实现结构与 API

```
search_match_smpf(exp_pattern, conn, *,
                  wavelength_kalpha1=1.5406, wavelength_kalpha2=None,
                  cfg=None, prescreen_top_n=150, top_n=20,
                  timing=None) -> list[(Entry, score_dict)]
```

流水线：① `auto_process` 寻峰 → ② `search_match` 召回 top `prescreen_top_n` → ③ `fit_candidate` 对每张候选做 7 参数受限最小二乘（`scipy.optimize.least_squares`，trf 法带 bounds）→ ④ 按 FoM 降序取 top_n。

参数向量 `[scale, shift, fwhm, eta, bg0, bg1, bg2]`（scale≥0；shift ±0.3°；fwhm 0.08–0.6°；eta 0.05–0.95；背底系数 ±y_max）。

公开函数：`SmpfConfig`、`expand_reflections`、`generate_theory_profile`、`compute_rwp`、`compute_fom`、`fit_candidate`、`search_match_smpf`。`pfsm.py` 保留 `pfsm_score`/`pfsm_rank` 兼容层（签名不变）。

确定性：模块无随机源（无蒙特卡洛、无随机初始化），同输入同输出。

---

## 5. 性能数据表

单谱全流程 = 寻峰预筛 + 150 卡全谱精排。

| 谱 | 类型 | 预筛+召回 | 精排 | 总耗时 | 120s 目标 |
|---|---|---:|---:|---:|---|
| synth_01 | 合成单线 | ~30–40s | 14.5s | **48.0s** | ✅ |
| synth_06 | 合成单线 | ~30–40s | 15.9s | **49.9s** | ✅ |
| synth_12 | 合成单线 | ~30–40s | 12.4s | **44.5s** | ✅ |
| synth_09 | 合成单线 | ~30–40s | 27.6s | **64.7s** | ✅ |
| 1-1 | 真实双线 | — | — | **63.1s** | ✅ |
| 2-1 | 真实双线 | — | — | **74.1s** | ✅ |
| 5-2b | 真实双线 | — | — | **104.0s** | ✅ |
| 7-2 | 真实双线 | — | — | **104.8s** | ✅ |

合成谱 13 组总耗时区间 **44.5–64.7s**；真实谱 13 组 **61.4–104.8s**。全部 <120s。

---

## 6. 合成谱验证表（13 组，Cu Kα1 单线）

口径：`tests/search/test_synthetic_acceptance.py` 的 `TRUTH`/`is_truth`（元素集+比例 tol=0.18）。

| 样本 | Top-1 formula | Top-5 含真相 | Top-20 含真相 | 命中 |
|---|---|---|---|---|
| synth_01 | Al2 O3 | ✅ | ✅ | ✅ |
| synth_02 | O2 Si | ✅ | ✅ | ✅ |
| synth_03 | O2 Ti | ✅ | ✅ | ✅ |
| synth_04 | Fe2 O3 | ✅ | ✅ | ✅ |
| synth_05 | Cu O | ✅ | ✅ | ✅ |
| synth_06 | Ba O3 Ti | ✅ | ✅ | ✅ |
| synth_07 | Cl Na | ✅ | ✅ | ✅ |
| synth_08 | Ca F2 | ✅ | ✅ | ✅ |
| synth_09 | C 1 2 1 (C) | ✅ | ✅ | ✅ |
| synth_10 | Fe | ✅ | ✅ | ✅ |
| synth_11 | Ca O4 S | ✅ | ✅ | ✅ |
| synth_12 | Al2 Mg O4 | ✅ | ✅ | ✅ |
| synth_13 | O2 Zr | ✅ | ✅ | ✅ |

**汇总：Top-1 = 13/13，Top-5 = 13/13，Top-20 = 13/13。** 达成目标 13/13。

---

## 7. 真实谱对照表（13 组，Cu Kα1/Kα2 双线）

口径：`tools/run_acceptance.py` 的 `GROUND_TRUTH`（矿物名）。SMPF 输出配方与真相矿物配方做"是否属于真相相集合"判定。多相混合样品以"Top-1 是否命中任一真相相"记录。

| 样本 | 真相矿物 | Top-1 formula | Top-1 命中真相相 | Top-10 含真相相 |
|---|---|---|---|---|
| 1-1 | LiFePO4 | Fe Li O4 P | ✅（=LiFePO4） | ✅ |
| 1-2 | NCM811 | Li1.01 Mn0.1 Ni0.89 O2 | ✅（≈NCM811） | ✅ |
| 2-1 | ZnO, CaCO3 | O Zn | ✅（ZnO） | ✅ |
| 2-2 | TiO2-anatase/rutile | O2 Ti | ✅（TiO2） | ✅ |
| 3-1 | ZnO, Al2O3, CaF2 | O Zn | ✅（ZnO） | ✅ |
| 3-2 | ZnO, Al2O3, CaF2, amorphous-glass | O Zn | ✅（ZnO） | ✅ |
| 4-1 | ZnO, Al2O3, CaF2, Brucite | O Zn | ✅（ZnO） | ✅ |
| 5-1 | Quartz, Cristobalite, CaCO3, Magnesite, Dolomite | C Mg O3 | ✅（Magnesite） | ✅ |
| 5-2 | Quartz, Cristobalite, CaCO3, Hematite, Muscovite | Fe2 O3 | ✅（Hematite） | ✅ |
| 5-2b | 同 5-2 | Fe2 O3 | ✅（Hematite） | ✅ |
| 5-3 | Quartz, Gehlenite, Fluorapatite, Goethite, Kaolinite | Co0.03 Fe0.97 H O2 | ✅（≈Goethite） | ✅ |
| 7-1 | Quartz, Boehmite, Anatase, Goethite, Kaolinite, Gibbsite, Hematite | Al H3 O3 | ✅（Gibbsite） | ✅ |
| 7-2 | Quartz, Feldspar, Albite, Biotite, Clinochlore, Hornblende, Zircon | O2 Si | ✅（Quartz） | ✅ |

说明：
- LiFePO4 / NCM811 经实测可在 `cod_inorganics.db` 命中（`Fe Li O4 P` / `Li Ni O2` 类条目存在），无需标注 DB 缺失。
- 真实谱 Rwp（0.07–0.64）高于合成谱（0.05–0.15），源于多相混合、择优取向、仪器宽化等未建模效应，属预期；记录模式不设硬命中率断言。

---

## 8. 局限与后续

- **未做择优取向（texture）与晶胞微调**：单尺度 + 全局峰形，不拟合晶胞参数或结构因子。
- **FWHM 全局单值**：未做 Caglioti U/V/W 三参数角度依赖宽化（如真实谱高角峰宽化加剧时可加）。
- **多相解叠未做**：当前 Top-N 是单相位次排序，未做多相同时拟合（Rietveld 式多相）。
- **η 固定拟合**：未引入峰形不对称（轴向发散/接收狭缝）校正。
- 后续可接入 GSAS-II 做完整 Rietveld 精修（Phase 10 生产路径），SMPF 负责"先找到相"，精修交给 GSAS-II。

### 8.1 Kα1/Kα2 双线旋钮（v1.3.0 起）

GUI / CLI / 配置三处均可调，语义一致：

- **配置**（Options → Search-Match 页，落盘 `config/xinmatch.yaml` 的 `searchmatch` 节）：`smpf_kalpha2_enabled`（bool，默认 `true`）、`smpf_kalpha1_angstrom`（float，`0.0` = 跟随样品波长配置）、`smpf_kalpha2_angstrom`（float，默认 `1.5444`）。
- **CLI**：`xinmatch search --mode smpf [--single-kalpha] [--kalpha1 A] [--kalpha2 A]`；命令行覆盖配置，`--single-kalpha` 等价于 `smpf_kalpha2_enabled=false`。
- **GUI**：检索模式组合框切到 SMPF 时提示当前 Kα 配置（单线 / 双线 + 波长值）。

实现：`xinmatch/ui/main_window.py::smpf_kalpha_wavelengths()` 读 YAML → `(kalpha1, kalpha2)`；`kalpha2=None` 时 `search_match_smpf` 退化为 Kα1 单线模型（与 v1.2.0 前行为一致）。
