# XRD 样本谱图清单（供 XinMatch 测试与验证）

> 三处原始数据目录（**只读引用，不要修改**）：
> - `D:\Project\XRD\XRData\csuHJW\` — 用户自有真实样品集（44+ 组，无 wt%）
> - `D:\Project\XRD\XRData\IUCr\` — IUCr CPD 国际标样（带 wt% 标定值，**最适合作定量验证**）
> - `D:\Project\XRD\test_xrd\` — 精选测试集（13 个样品，含物相结果 + wt% + 元素限定）
>
> 本文件由人工整理，多 Agent 共享。如需补充新样品，请按现有分组表式追加。

---

## 1. 精选测试集 `D:\Project\XRD\test_xrd\`（首选 / 含 wt% 标定）

13 个样品，覆盖单相 / 多相 / 含非晶 / 微量相 / 复杂天然矿物。物相结果见 [物相结果+wt%.txt](file:///D:/Project/XRD/test_xrd/物相结果+wt%.txt)。

### 1.1 按样品的物相组成与 wt%

| 样品 | 类型 | 物相 + wt% | 元素必含 | 备注 |
|---|---|---|---|---|
| **1-1** | 单相 | LiFePO4 (100%) | Fe, P | 锂电正极 |
| **1-2** | 单相 | NCM 811 (100%) | Ni, Co, Mn | 锂电正极 |
| **2-1** | 两相 50/50 | ZnO (50) + CaCO3 (50) | Zn, Ca | — |
| **2-2** | 双相同质 | TiO2 锐钛矿 + TiO2 金红石 | Ti | 同质异相 |
| **3-1** | 三相 | ZnO (93.59) + Al2O3 (5.04) + CaF2 (1.36) | Zn, Ca, Al | 含微量相 |
| **3-2** | 含非晶 | ZnO (19.68) + Al2O3 (30.79) + CaF2 (20.06) + 玻璃 (29.47) | Zn, Ca, Al, Si | **非晶含量验证** |
| **4-1** | 四相 | ZnO (19.94) + Al2O3 (21.27) + CaF2 (22.53) + Brucite Mg(OH)2 (36.26) | Zn, Ca, Al, Mg | 择优取向 |
| **5-1** | 多相矿物 | α-石英 + 方石英 + CaCO3 + MgCO3 + CaMg(CO3)2 (白云石) | Si, Ca, Mg | — |
| **5-2** | 多相矿物 | α-石英 + 方石英 + CaCO3 + Fe2O3 + 白云母 KAl2[AlSi3O10](OH)2 | Si, Ca, Fe, Al, K | — |
| **5-2b** | 同上无择优 | 同 5-2 | 同 5-2 | 与 5-2 对照择优取向 |
| **5-3** | 多相矿物 | SiO2 + Ca2Al2SiO7 + Ca5[PO4]3F + α-FeO(OH) + 高岭土 Al2[(OH)4/Si2O5] | Si, Ca, Al, P, Fe | — |
| **7-1** | 合成铝土矿 | Quartz (5.16) + Boehmite γ-AlO(OH) (14.93) + Anatase TiO2 (2.00) + Goethite FeO(OH) (9.98) + Kaolinite (3.02) + Gibbsite Al(OH)3 (54.90) + Hematite Fe2O3 (10.00) | Si, Al, Ti, Fe | **7 相混合** |
| **7-2** | 天然矿物 | 主要 Quartz + Feldspar + Albite + Biotite；少量 Clinochlore + Hornblende；微量 Zircon | Si, Na, K, Ca, Fe, Al, Mg | 无真值，做定性 |

### 1.2 文件格式矩阵（每个样品多格式冗余）

子目录与文件类型：

| 子目录 | 扩展名 | 含义 | 用途提示 |
|---|---|---|---|
| `txt\` | `.txt` | 两列 ASCII（2θ, I） | XinMatch `core/io/free.py` 已支持 |
| `xy\`  | `.xy` | 两列 ASCII | 同上 |
| `raw\` | `.raw` / `.RAW` | 二进制 raw | 大小写混杂；XinMatch 已识别 |
| `mdi\` | `.mdi` | Sietronics CPI 文本 | XinMatch 已支持 |
| `geshi\` | `.dat/.mdi/.raw/.txt/.xy` | 4-1 的多格式冗余 | **格式回归测试用** |
| `5\` | `.cif/.par/.lst/.mdi/.mtd/.txt` | 5-1/5-2/5-2b/5-3 各自的 参考软件 候选输出目录 | 含 **参考软件 候选 CIF** + `.par`（峰列表）+ `.mtd`（项目文件）|

辅助文件：
- `物相结果.txt` / `物相结果+wt%.txt` — 各样品 ground truth
- `元素限定.txt` — 各样品元素红/黄/绿预设（用于 Restraints 测试）
- `txt\PolyXRD_测试报告.txt` / `PolyXRD_测试报告_元素限定.txt` — 第三方程序对比基线

---

## 2. IUCr CPD 国际标样 `D:\Project\XRD\XRData\IUCr\`（黄金基线 / 全 wt%）

[物相说明](file:///D:/Project/XRD/XRData/IUCr/IUCr物相说明.txt)。**这是定量相分析（T8.x）的法定基准**。

### 2.1 标样与 wt%

| 样品 | 物相 | wt% 标定值 | 关键文件 |
|---|---|---|---|
| **CPD 1a–1h**（8 子样） | Corundum Al2O3 / Fluorite CaF2 / Zincite ZnO | 见下表 | `Must do\CPD-1A.txt`…`CPD-1H.PRN` |
| **CPD 2** | Al2O3 + ZnO + CaF2 + Brucite Mg(OH)2 | 21.27 / 19.94 / 22.53 / 36.26 | `Must do\CPD-2.txt` |
| **CPD 3** | Al2O3 + ZnO + CaF2 + Glass(SiO2) | 30.79 / 19.68 / 20.06 / 29.47 | `Must do\CPD-3.txt` |
| **CPD 4** | Al2O3 + Magnetite Fe3O4 + Zircon ZrSiO4 | 50.46 / 19.64 / 29.90 | `Must do\CPD-4.txt` |
| **Synthetic Bauxite** | 同 test_xrd 7-1 | 同 7-1 | `BAUXITE.mdi` / `BAUXITE.RAW` |
| **Granodiorite** | 同 test_xrd 7-2 | 无真值 | `GRANODIO.RAW` |
| **CPD-Y2O3** | Y2O3 | — | `CPD-Y2O3.RAW` |
| 单相标样 | Brucite / Corundum / Fluorite / Magnetite / Silica / Starch / Sucrose / Valine / Zincite / Zircon / MANNITOL / NIZATIDI / PHARM1GR / PHARM2GR | 100% | `<NAME>.RAW` |
| **Rietveld 子集** | Mg(OH)2 + ZnO + CaF2 + CaCO3 多组 | — | `Must do\Rietveld\*.txt` + 4 个 CIF |

**CPD 1a–1h 重量分配**（Al2O3 / ZnO / CaF2 wt%）：

```
1a   1.15 /  4.04 / 94.81      1b  94.31 / 1.36 /  4.33      1c   5.04 / 93.59 / 1.36
1d  13.53 / 32.89 / 53.58      1e  55.12 / 15.25 / 29.62     1f  27.06 / 55.22 / 17.72
1g  31.37 / 34.21 / 34.42      1h  35.12 / 30.19 / 34.69
```

> 注：1c 与 test_xrd 3-1 物相完全一致（同一原始样品）。

### 2.2 多格式冗余

每样品均有 4–5 种格式：
- `IUCr\<NAME>.RAW` + `IUCr\<NAME>.mdi` — Raw + Sietronics
- `IUCr\gsas\<NAME>.gss` — GSAS文本格式（**T10 精修 / GSAS-II 适配层验证用**）
- `IUCr\Must do\<NAME>.txt` / `.PRN` — 两列 ASCII（首选回归测试）
- `IUCr\tar.gz\*.tar.gz` — 7 套多格式打包归档（bruker/col/cpi/dbws/gsas/lhpm/philips/rietan/xda），可补 XinMatch 格式回归

---

## 3. 用户真实样品集 `D:\Project\XRD\XRData\csuHJW\`（44+ 组 / 部分 wt%）

> 多为 `.raw` 二进制 + 部分配套 `.txt`/`.sav`/`.mdi`/`.cif`。文件名含中文。

| 样品 | 已知物相 | 备注 |
|---|---|---|
| data001 | TiO2 双相（锐钛矿+金红石） | 同 test_xrd 2-2，`.mdi+.raw+.rpt` |
| data002 | 标准 Si | 单相标样 |
| data003–006 | AlCoO 650°C / 750°C 系列 | 同一样品多温度 |
| data007–016 | 铜衍射谱系列（10 组） | 同一样品不同条件 |
| data017 / data018 | 铜低角度 / 高角度 | 分段扫描 |
| data019 | Al-Zn-Mg 合金时效态 | — |
| data020 | 残余奥氏体钢 | **奥氏体+马氏体定量** |
| data021 | 氧化铁 | Fe2O3 / Fe3O4 |
| data022 | 黏土矿物 | 复杂层状硅酸盐 |
| **data023** | 含非晶 ZnO+CaCO3+Al2O3 | 文件名标注 wt% 25 |
| data024 | 炭原丝 | 含碳非晶 |
| data025–029 | 高聚物 1–5 | **低结晶度 DOC 验证** |
| data030 / data039 | LiMnO2 + Si | — |
| data031 | ZrB-ZrB2 | 含 `.abc` 格式 |
| data032 | Lansolazole（药物） | 含 `.is0/.is1/.is2` 串口仪器格式 |
| data033 | 单相锐钛矿 | 单相标样 |
| data034 | 7046-7P | 未知 |
| data035 | 硬质合金 WC 残余应力 | **T11 微观应变验证** |
| data036 | ZnO+CaCO3+SiO2+Al2O3 | 四相 |
| data037 | Amorphous + SiO2 | **非晶含量验证** |
| data038 | Y2O3 | 单相标样 + `.rrp` 格式 |
| data040 | NCM 811 | 同 test_xrd 1-2 |
| data041 | ZnO+CaCO3 | 含 CIF + `.lst+.par+.XLS` |
| data042 | 陶瓷 ZrSiO 1180 部分晶化 | 含 ZrO2 / ZrSiO4 CIF |
| data043 | Ni(OH)2 | 含 `(Ni,Co,Mn)(OH)2.cif` |
| data044 | Al-MgZn2 过时效态 | 含 Al / MgZn2 CIF |

---

## 4. 推荐使用场景 → 样品映射

| 测试目的 | 推荐样品 | 路径 |
|---|---|---|
| **L3 Search-Match Top-N 命中率**（T6.9） | test_xrd 全部 13 个 | `test_xrd\txt\*.txt` |
| **定量 wt% 回归**（T8.1 RIR / T8.2 内标 / T8.3 Rietveld） | IUCr CPD 1a–1h, CPD 2/3/4, test_xrd 3-1/4-1/7-1 | `IUCr\Must do\` |
| **非晶含量 DOC**（T8.4） | test_xrd 3-2, data023, data037 | — |
| **微量相检测**（<5%） | test_xrd 3-1（CaF2 1.36%）, 7-1（Anatase 2.0%） | — |
| **同质异相** | test_xrd 2-2（TiO2 双相）, data001 | — |
| **择优取向** | test_xrd 5-2 vs 5-2b | — |
| **复杂多相**（≥5 相） | test_xrd 7-1（7 相）, 5-1/5-2/5-3 | — |
| **Restraints 元素三态** | test_xrd `元素限定.txt` 13 组预设 | — |
| **指标化**（T9） | data033 单相锐钛矿, data002 标准Si, data038 Y2O3 | — |
| **Scherrer / 微观应变**（T11） | data035 WC 残余应力, data025–029 高聚物 | — |
| **Rietveld 精修**（T10） | IUCr CPD 1a-1h, `Must do\Rietveld\` | — |
| **格式回归**（T2.x） | `geshi\4-1` 多格式冗余, `IUCr\tar.gz\` 7 包 | — |
| **参考软件 候选 CIF 对照** | `test_xrd\5\*\*.cif`（已含 参考软件 选定相） | — |

---

## 5. 加载到 XinMatch 的推荐路径

```python
from xinmatch.core.io import load_pattern
from pathlib import Path

# 标准两列 ASCII（最稳）
p = load_pattern(Path(r"D:\Project\XRD\test_xrd\txt\3-1.txt"))

# Sietronics MDI
p = load_pattern(Path(r"D:\Project\XRD\test_xrd\mdi\7-1.mdi"))

# 二进制 Raw
p = load_pattern(Path(r"D:\Project\XRD\test_xrd\raw\4-1.raw"))

# GSAS 文本（用于精修）
p = load_pattern(Path(r"D:\Project\XRD\XRData\IUCr\gsas\corundum.gss"))
```

> **注意**：测试时**不要修改原始数据目录**。如需 fixtures，请在 `tests/fixtures/patterns/` 下做副本或软链。

---

*整理日期：2026-10-08*
*整理人：TraeCode Agent*
