# FPFM（全谱拟合检索，Search-Match with Profile Fitting）机制调研笔记

> 用途：为 XinMatch 开源粉末 XRD 物相分析平台的 FPFM 检索功能提供公开原理与实现参考。
> 编写原则：仅依据公开文献、教科书与厂商公开白皮书；不复制任何商业软件代码。
> 品牌说明：文中一律不出现具体商业软件/数据库产品名，统一以"对标产品""参考检索软件""公共粉末衍射数据库"等中性表述指代。文末"参考来源"清单按真实出处列出 URL，仅供溯源。
> 编写日期：2026-10-11。

---

## 1. FPFM 概念与流程

### 1.1 定义
FPFM（全谱拟合检索 / 全谱搜索-匹配）是一种物相鉴定方法：**不依赖先从实测谱中人工/自动提取出的"峰列表"，而是直接对整条实测衍射谱做受限的最小二乘全谱拟合**。对候选卡片库中的每一相，由其晶体结构（或 d–I 峰表）生成理论衍射谱，在可调的少量全局/轮廓参数下与实测谱拟合，用拟合优度（最常用加权轮廓残差 `Rwp`）对全部候选排序，从而实现"候选生成 → 理论谱计算 → 全谱拟合 → 按优度排序"的闭环。

### 1.2 标准工作流（四阶段）
1. **候选预筛（candidate generation）**：用传统 d 值/强线索引（见第 6 节）把数万条卡片粗筛到 top-N（数十~数百条）。这是工程上把"暴力全谱拟合"压到可接受耗时的关键。
2. **理论谱计算**：对每张候选卡片，按实测仪器条件（靶波长、2θ 范围、步长）由结构因子/d–I 表生成逐点理论强度 `ycalc(2θ_i)`，叠加背底模型与 Kα1/Kα2 双线。
3. **受限全谱拟合**：对每条候选独立做一次"低配自由度"的 Rietveld/全谱拟合，只放开与鉴定相关的参数（见第 5 节）：标度因子 scale、2θ 零点/位移、峰宽（U/V/W）、pV 混合比 η、背底系数等；**不**放开原子坐标、占位、温度因子等结构参数。
4. **按拟合优度排序输出**：以 `Rwp`（或其归一化 FoM，见第 7 节）升序排列候选卡片，取 top-K 作为鉴定结果；多相体系可采用"逐相贪婪添加"策略（见 1.4）。

### 1.3 对标产品的公开能力描述（仅概括，不含代码）
- 主流参考检索软件普遍提供两类检索：经典"峰表检索"（基于提取出的 d–I 峰列表做 Hanawalt/Fink 式匹配）与"全谱/轮廓拟合检索"（profile fitting search-match）模式。后者直接以整段实测谱为输入，对候选相逐张做轮廓拟合，输出按匹配优度（FoM/Rwp）排序的候选卡片列表，并给出每条候选的标度贡献与拟合差值曲线。
- 公开白皮书描述的典型流程：先由 d 值窗口/化学成分做粗筛，再对粗筛命中的候选做"全谱拟合精排"，并支持多相逐步添加（每加入一相后重新拟合，按优度增量判断是否保留）。这与文献中"full-profile search–match"算法（Lutterotti 等，2019，见来源）的三步策略一致。
- 注意：以上均为对**公开能力描述**的概括，未参考任何产品源码。

### 1.4 多相贪婪添加策略（公开文献做法）
IUCr 2019 年公开论文描述的全谱检索算法：
- 设候选子集 S1（N 个相）与已识别子集 S2（初始为空）。
- 对 S1 中每相做一次自动 Rietveld 拟合，按 FoM 排序，把 rank-1 移入 S2。
- 再把 S2 中每相与 S1 剩余相逐一组合做拟合，优度最好的组合对应的新相移入 S2；如此循环。
- 每轮结束后做一次更精细的拟合以估算各相体积分数；若某相体积分数低于阈值（公开论文取 0.1%~0.5%）则移出 S2。
- 用"新相与 S2 中各相理论谱互相拟合的 Rwp 是否低于阈值"来判重，避免把同一相的重复条目反复加入。
- 终止条件：S1 耗尽、或连续一轮无新相超过阈值、或相数达上限。

### 1.5 关键结论
- 全谱拟合检索的本质是"**对每条候选做一次低配自由度 Rietveld 拟合，再按 Rwp 排序**"，而非峰表匹配。
- 粗筛 top-N + 全谱精排是大库（数万卡片）下唯一可落地的工程路径；公开文献也明确建议"集成传统位置检索作为预筛以减少初始相数"。
- 该方法对纳米晶、峰重叠严重的样品比峰表法更稳健，因为它不依赖可靠的单峰定位。

### 1.6 来源
- IUCr Journal of Applied Crystallography, *Full-profile search–match by the Rietveld method*（2019）：https://journals.iucr.org/j/issues/2019/03/00/nb5231/index.html （PMC 镜像：https://pmc.ncbi.nlm.nih.gov/articles/PMC6557175/ ）
- IUCr, *High-throughput powder diffraction. I. A new approach to qualitative and quantitative powder diffraction pattern analysis using full pattern profiles*（2004）：http://journals.iucr.org/j/issues/2004/02/00/mm0036/
- arXiv, *Dara: Automated multiple-hypothesis phase identification and refinement from powder X-ray diffraction*：https://arxiv.org/html/2510.19667v1
- arXiv, *MatDiffract: A Material-Informed Automated Analysis Platform for X-ray Powder Diffraction*：https://arxiv.org/html/2607.20880

---

## 2. 峰形模型

### 2.1 为什么需要峰形函数
实测衍射峰是仪器函数与样品函数（晶粒尺寸、微应变）的卷积，既非纯高斯也非纯洛伦兹。Rietveld/全谱拟合中用解析函数近似单峰轮廓，再按 hkl 叠加成全谱。

### 2.2 Gaussian 与 Lorentzian（Cauchy）
以峰位 `x0`、半高全宽 `H` 为参数（`x = 2θ - 2θ0`）：

- Gaussian：
  `G(x) = exp[ -4 ln2 · (x/H)^2 ]`
- Lorentzian（Cauchy）：
  `L(x) = 1 / [ 1 + 4 (x/H)^2 ]`
  （等价写法 `1/(1+k x^2)`，`k = 4/H^2`）

尺寸展宽近似洛伦兹型，应变展宽近似高斯型；真实峰为二者卷积。

### 2.3 Voigt 函数
Voigt 是 Gaussian 与 Lorentzian 的**严格卷积**：
`V(x) = ∫ G(x'-x0) L(x-x') dx'`
含两个独立宽度参数（高斯宽度、洛伦兹宽度），物理上最准确，但计算需数值卷积/近似（如 Faddeeva 复误差函数），代价较高。

### 2.4 Pseudo-Voigt（pV，最常用）
为避免 Voigt 的卷积开销，用**线性混合**近似：
`pV(x) = η · L(x) + (1-η) · G(x)`
- `η`：Lorentzian 混合比（0=纯高斯，1=纯洛伦兹）。
- 工程实现中通常令 L 与 G 共享同一 FWHM `H`；Voigt 与 pV 的 FWHM 之间有经验换算关系（Thompson-Cox-Hastings 关系）：
  `H_V^5 ≈ H_G^5 + 2.69269 H_G^4 H_L + 2.42843 H_G^3 H_L^2 + 4.47163 H_G^2 H_L^3 + 0.07842 H_G H_L^4 + H_L^5`
  （即由高斯/洛伦兹分量宽度反推 Voigt 等效 FWHM）。

### 2.5 Pearson VII
洛伦兹的广义形式，单形状参数 `m` 控制尾部衰减：
`P(x) = A · [ 1 + (x-x0)^2 / (m a^2) ]^{-m}`
- `m=1` → 纯 Lorentzian（重尾）；
- `m→∞` → 趋近 Gaussian；
- 中间值描述尾部介于两者之间的峰，单参数即可在 G↔L 之间连续调节。
- 归一化写法（令 `a` 正比于 FWHM，`Δq` 为半宽）：
  `P(q) = 1 / [ 1 + (2^{1/m}-1) · ((q-q0)/(Δq/2))^2 ]^m`

### 2.6 Modified Lorentzian / Intermediate Lorentzian
- **Modified Lorentzian (ML)**：洛伦兹型幂函数，指数取 2 附近，尾部比标准洛伦兹更陡。
- **Intermediate Lorentzian (IL)**：介于洛伦兹与修正洛伦兹之间的固定形状函数，指数取 3/2。APS 公开 LineFit 文档给出的归一化形式：
  `f(x) = A · sqrt(2^{2/3}-1)/(2γ) · [ 1 + (2^{2/3}-1) ((x-x0)/γ)^2 ]^{-3/2}`
  其中 `A` 为幅度、`x0` 为峰位、`γ` 为尺度参数。
- IUCr 1982 年对比研究系统比较了六类解析峰形（G、L、ML、IL、p-V、Pearson VII）在 Rietveld 精修中的表现；对 FPFM 这种"每条候选只做低配拟合"的场景，**pseudo-Voigt 是计算成本与精度的最佳折中**，应作为首选。

### 2.7 Caglioti 方程（FWHM 随 2θ 的参数化）
仪器+样品展宽合成的 FWHM 随衍射角变化，经典参数化为：
```
H^2(θ) = U tan^2θ + V tanθ + W
```
- `H`：半高全宽（单位通常为度 2θ 或弧度）；
- `U, V, W`：三个仪器/样品相关常数；
- 由标样（如 LaB6、多晶硅）在多个 2θ 位置测 FWHM，再拟合 `U tan²θ + V tanθ + W` 三点即可解出 U/V/W。
- 典型实验室 Cu 靶测角仪的量级（仅供标定参考，非硬性值）：`W` 最小（低角本征宽度），`U` 控制高角展宽，`V` 通常为负、形成 U 型曲线最低点。具体值必须由仪器标样实测。

### 2.8 η 随角度的参数化
pV 的混合比 η 也随 2θ 变化，常用二次抛物线参数化（参考 Rebuffi 等的仪器函数参数化方案）：
`η(θ) = a + b θ* + c θ*^2`（θ* 为约化角度变量），与 Caglioti 方程配对使用。在 FPFM 中可把 η 作为少量可调参数（或固定为标样值）。

### 2.9 关键结论
- FPFM 首选 **pseudo-Voigt**（计算快、形状可调、生态最广）；FWHM 用 **Caglioti U/V/W** 参数化；η 用抛物线参数化。
- Pearson VII 是单形状参数的备选；Voigt/IL/ML 物理更精细但计算更贵，FPFM 粗排阶段不必上。

### 2.10 来源
- Jana2006 公开文档 *Profile functions*（pV 定义、FWHM 换算）：https://jana.fzu.cz/docs/Powder_parameters_new.pdf
- IUCr International Tables Vol. H, Ch. 3.2（Voigt / Pearson VII 定义）：https://onlinelibrary.wiley.com/iucr/itc/Ha/ch3o2v0001/sec3o2o2o3.pdf
- IUCr IT Ch. 3.6（Caglioti 方程、pV 混合参数 tanθ 参数化）：https://onlinelibrary.wiley.com/iucr/itc/Ha/ch3o6v0001/ch3o6.pdf
- arXiv *PCrystalX*（Caglioti 方程与 U/V/W 标定）：https://arxiv.org/pdf/2204.14072v1
- IUCr *A multipurpose laboratory diffractometer…*（η 抛物线参数化）：https://onlinelibrary.wiley.com/iucr/doi/10.1107/S1600576722003089/index.html
- SD 矿业学院课件（Pearson VII m=1→L、m→∞→G）：http://ahrenkiel.sdsmt.edu/courses/Spring2021/NANO704/lectures/4_XRayDiff/4_XrayDiff_text_125.pdf
- APS LineFit 手册（Intermediate Lorentzian 解析式）：https://www-dev.aps.anl.gov/files/APS-Uploads/SECTOR8/8-ID/linefit_manual.pdf
- IUCr *Profile shape functions in Rietveld refinements*（六峰形对比，1982）：http://journals.iucr.org/paper?buy=yes&cnor=a21811

---

## 3. 背底处理

### 3.1 背底来源
实测谱背底来自： incoherent 散射、热漫散射（TDS）、样品台/容器散射、非晶相散射、空气散射等。在 FPFM 中，背底既会影响 Rwp 绝对值，也会被错误候选"利用"来压低 Rwp（见第 7 节），因此建模必须克制。

### 3.2 自动背底估计方法
| 方法 | 原理 | 特点 |
|---|---|---|
| 多项式 / Chebyshev 多项式 | 用 N 阶 Chebyshev 第一类多项式拟合背底：`I_back(i) = Σ_j P_j T'_{j-1}(2θ_i)` | Rietveld 标准做法；系数可作为拟合参数一起精修；常用阶数 8~20 阶 |
| SNIP（Sensitive Nonlinear Iterative Peak-clipping） | 迭代地把每个数据点与其邻域比较，取较小值（"削峰"），逐步逼出包络 | 不依赖峰位先验，能自适应起伏背底；常用于拟合前的背底扣除 |
| 线性内插 / 手动选点 | 在指定无峰点间线性插值 | 简单可控，但需人工选点 |
| 凸包 / 最小值包络 | 取谱线下包络 | 快速但易过扣 |

- NIST 标准物质证书中公开的 Rietveld 做法：用"十阶 Chebyshev 多项式 + 1/x 项"表示背底，并把系数与标度、展宽等一起精修。
- 公开综述提到：对表面无序强的纳米晶，常用 12~20 阶 Chebyshev 以正确归属宽峰尾部强度。

### 3.3 把背底系数作为拟合参数的做法
FPFM 的受限拟合中，背底通常以 **Chebyshev 多项式系数**形式与 scale、峰宽等一起进入最小二乘求解（线性系数可解析求解，非线性参数迭代）。好处：背底随候选一起被"吸收"，避免提前扣背底带来的偏差；风险：过阶数会让错误候选靠"拟合背底"虚低 Rwp（IUCr 2019 论文明确指出此陷阱）。
- 工程建议：背底阶数固定（如 8~12 阶）、阶数对所有候选一致，保证候选间可比；不要给每个候选单独优化阶数。

### 3.4 关键结论
- 首选 **Chebyshev 多项式背底**（系数作为线性拟合参数）；拟合前可用 SNIP 做初始估计/预扣。
- 背底阶数统一、克制，是候选间 Rwp 可比的前提。

### 3.5 来源
- HandWiki *Rietveld refinement*（Chebyshev 背底公式）：https://handwiki.org/wiki/Rietveld_refinement
- NIST SRM 676a 证书（十阶 Chebyshev + 1/x 背底）：https://tsapps.nist.gov/srmext/certificates/676a.pdf
- R alkahest 包文档（SNIP 算法说明）：https://www.stats.bris.ac.uk/R/web/packages/alkahest/refman/alkahest.html
- 公开教材站点（SNIP 伪代码示例）：https://yusukehashimotolab.github.io/AI-Knowledge-Notes/knowledge/en/MI/experimental-data-analysis-introduction/chapter-2.html
- 公开综述（12~20 阶 Chebyshev 用于纳米晶）：https://mail.eijo.in/asset/images/uploads/17712371498385.pdf

---

## 4. Kα1 / Kα2 双线

### 4.1 物理来源
Cu 靶 Kα 辐射是自旋轨道分裂的两条跃迁线（LⅢ→K 与 LⅡ→K），波长极接近，高分辨率下可见双峰：
| 谱线 | 跃迁 | 波长（Å） | 相对强度 |
|---|---|---|---|
| Kα1 | LⅢ→K (2p₃/₂→1s) | ≈1.540598 | 强（≈2） |
| Kα2 | LⅡ→K (2p₁/₂→1s) | ≈1.544426 | 弱（≈1） |

- 强度比 `Kα2 : Kα1 ≈ 0.5 : 1`（即约 1:2；该比值随原子序数缓慢变化，Cu 靶取 0.5）。
- 波长差 Δλ ≈ 0.00383 Å；常用"加权平均 Kα" λ≈1.54184 Å（=(2λ1+λ2)/3）做近似计算，但全谱拟合应直接建模双线。

### 4.2 双线角间距随 2θ 增大
由 Bragg 定律 `2d sinθ = nλ` 对 λ 求导：
`dθ/dλ = n/(2d cosθ) = tanθ / λ`
因此两条波长在同一 d 面上的角间距：
```
Δ(2θ) ≈ 2 Δθ = 2 · tanθ · (Δλ/λ)
```
即 **Δ2θ 正比于 tanθ**：低角处两线几乎重合，高角处逐渐分开甚至分裂为两个可分辨峰。这就是高角峰"不对称分裂/展宽"的来源。

### 4.3 建模方式
理论谱中每条 hkl 反射应生成**两条同形峰**：
- Kα1 峰位由 λ1 经 Bragg 定律算出；Kα2 峰位由 λ2 算出；
- 两峰峰形（pV）、FWHM 完全相同，仅强度按 1 : 0.5 缩放；
- 两峰都用同一套 Caglioti U/V/W 与 η 参数。
- 实现上可对每个 hkl 先按 λ1 算峰位，再用 `Δ(2θ)=2 tanθ·(Δλ/λ)` 偏移出 Kα2 位置。

### 4.4 关键结论
- Cu 靶 λ1≈1.540598 Å、λ2≈1.544426 Å，强度比 2:1；
- 双线角间距 `Δ2θ ≈ 2 tanθ (Δλ/λ)`，随 2θ 增大；
- 全谱拟合必须把每条反射建成两条同形、强度 2:1 的峰叠加，否则高角区系统性偏差会污染 Rwp 排序。

### 4.5 来源
- UCL 粉末衍射教学 *Generation of X-rays*（Kα 双线成因）：http://pd.chem.ucl.ac.uk/pdnn/inst1/xrays.htm
- 北得州大学课件 *Lecture 4*（Cu Kα1=1.5406 Å、Kα2=1.5444 Å）：https://sites.chemistry.unt.edu/~tgolden/courses/Lecture4%205570%20XRD%202024.pdf
- IODP 公开仪器参数 CSV（实测 Kα1=1.5405980、Kα2=1.5444260、比值 0.500）：https://publications.iodp.org/other/Oman/SUPP_MAT/F3_XRD_data/BA4A/1_RAW/CSV/10A_98_1_73_73.csv
- IUCr *The principles of X-ray diffraction*（Bragg 定律，用于推导角间距）：https://www.iucr.org/publ/50yearsofxraydiffraction/full-text/principles

---

## 5. 拟合与判据

### 5.1 加权最小二乘全谱拟合
目标：最小化残差加权平方和
```
χ² = Σ_i w_i [ y_obs(i) - y_calc(i) ]²
```
- `y_obs(i)`：第 i 个 2θ 点实测计数；
- `y_calc(i)`：第 i 点理论强度（标度 × 各 hkl 峰形叠加 + 背底）；
- 权重 `w_i = 1 / σ_i²`，计数统计下 `σ_i² ≈ y_obs(i)`（Poisson），故 `w_i ≈ 1/y_obs(i)`。

### 5.2 判据公式（Rietveld 标准判据）
- **加权轮廓残差 Rwp**：
  `Rwp = sqrt( Σ_i w_i (y_obs - y_calc)² / Σ_i w_i y_obs² )`
  （IUCr CIF 词典定义）
- **期望残差 Rexp**（仅由数据点数与权重决定的"理论最低 Rwp"）：
  `Rexp = sqrt( N_p / Σ_i w_i y_obs² )`，其中 `N_p = N - P`（数据点数 N 减去精修参数数 P；有的写法用 N）。
- **拟合优度 GOF / χ²**：
  `GOF = χ² = (Rwp / Rexp)² = Σ w_i(yobs-ycalc)² / (N-P)`
- 参考经验值（公开教材）：
  - Rwp < ~0.10（10%）对中等复杂相属可接受；
  - GOF 理想趋近 1；实际实验室数据 GOF 常在 1~5 之间；
  - 差值曲线（yobs−ycalc）应平坦、随机分布在零线附近，无系统性波浪。
- 注意：Rwp 绝对值依赖背底高低与峰数多少，**不能跨实验条件直接比大小**；同一套实测谱对不同候选拟合时，Rwp 才有排序意义。

### 5.3 FPFM 受限拟合参数与边界约束
对每条候选，只放开少量与"该相是否匹配"相关的参数（不精修结构参数）：

| 参数 | 作用 | 约束建议 |
|---|---|---|
| scale（标度因子） | 匹配该相贡献强度 | 非负；可解析/线性求解 |
| 2θ 零点 / 样品位移 Δ2θ | 峰位整体偏移 | 小范围（如 ±0.2°），固定常数而非逐峰偏移 |
| Caglioti U/V/W 或单峰宽 H | 峰宽 | 固定为仪器标样值，或仅放开 W/单一宽度 |
| pV 混合比 η | 峰形 | 固定或小范围可调 |
| 背底 Chebyshev 系数 | 吸收非晶/本底 | 阶数统一（8~12），全候选一致 |

- 边界约束做法：把物理上不该大变的参数（U/V/W、η）固定或给窄边界，只让 scale、2θ 零点、背底系数自由；这样每条候选拟合快（线性/少非线性），且候选间可比。
- 多相体系：用第 1.4 节贪婪添加，每加入一相再整体精修一次。

### 5.4 关键结论
- 判据三件套：`Rwp`（主排序）、`Rexp`（数据统计下限）、`GOF=χ²=(Rwp/Rexp)²`；
- FPFM 每条候选只精修 scale、2θ 位移、峰宽、η、背底系数，结构参数锁死；
- 参数边界收紧 + 背底阶数统一，是保证候选可比、防止错误候选靠"调背底/调宽峰"虚优的关键。

### 5.5 来源
- IUCr CIF 词典 `_pd_proc_ls_prof_wR_factor / wR_expected`（Rwp/Rexp 官方定义）：https://www.iucr.org/__data/iucr/cifdic_html/1/cif_pd.dic/Ipd_proc_ls_prof_.html
- *Powder Diffraction* (Cambridge) *R factors in Rietveld analysis: How good is good enough?*：https://resolve-he.cambridge.org/core/journals/powder-diffraction/article/r-factors-in-rietveld-analysis-how-good-is-good-enough/17439A1F889B689C495549A234D53682
- NIST *GSAS Tutorial – Rietveld Refinement*（χ²=Q/N、判据讨论）：https://www.nist.gov/el/mssd/gsas-tutorial-rietveld-refinement
- IUCr Erice 讲义 *Introduction to the Rietveld method*（Rwp<0.1 经验、GOF=Rwp/Rexp）：https://www.iucr.org/__data/iucr/powder/Erice2011/day8/d1/maud.pdf
- Am. Mineral. *Quantitative mineralogical analysis using the Rietveld full-pattern fitting method*（Rwp 公式）：https://msaweb.org/AmMin/AM78/AM78_932.pdf

---

## 6. 候选预筛

### 6.1 为什么需要预筛
全谱拟合每条候选都要跑一次最小二乘，数万卡片全做不现实。先用极廉价的峰表/索引检索把候选压到 top-N（几十~几百），再做全谱精排。

### 6.2 Hanawalt 索引
- 由 Hanawalt、Rinn、Frevel（1938）提出：用每条谱**最强的 3 根线** `(d1, d2, d3)` 表征物相。
- 检索时按最强线的 d 值分组（Hanawalt group），组内再按次强线 d 值排序；d 值区间留小重叠以容忍 d 值误差。
- 优点：强线信息量大；缺点：择优取向、峰重叠时强线不可靠。

### 6.3 Fink 索引
- 用**最长的 8 根线（最大 d 值）**而非最强线，循环排列（8 种起点）建索引。
- 适合大晶胞、低 d 值数目少、长 d 线特征性强的物相；对择优取向不如 Hanawalt 敏感。

### 6.4 d 值窗口检索
- 实测提取峰 d 值与卡片峰 d 值在容差窗口（如 ±0.01~0.02 Å 或相对容差）内匹配，统计匹配上的强线数；命中数多者入围。
- 可叠加化学成分过滤（元素包含/排除）进一步收缩候选集。

### 6.5 Smith–Snyder 品质因子 FN（初筛/数据质量 FoM）
国际晶体学会与衍射数据中心采纳的、基于峰位准确度的 FoM：
```
FN = (1 / |Δ2θ̄|) · (N / N_poss)
```
- `|Δ2θ̄|`：实测与计算 2θ 的平均绝对偏差；
- `N`：已观测到的独立衍射线数；
- `N_poss`：在第一个 N 条线对应的 2θ 范围内，按空间群允许的全部可分辨独立反射数（扣除系统消光、同族合并）。
- 经验：FN≈80–150 为高质量谱，<20 为差；FN 越大越好。该指标主要用于评价谱图质量与索引成功率，也可作初筛打分。

### 6.6 "粗筛 top-N + 全谱精排"工程实践
- 公开自动物相鉴定工作流（如 Dara、MatDiffract 等公开论文）的共同模式：
  1. 先用快速峰匹配（实测峰 ↔ 候选理论峰的 d/I 映射）算启发式命中分，粗筛 top-N；
  2. 仅对 top-N 做（受限）Rietveld/全谱精修，按精修后 Rwp 重排；
  3. 公开数据显示：粗筛 top-1 的 Rwp 分布中位数约 9.5%~10%，精修重排后最佳候选 Rwp 中位数降到约 5.3%，说明精排能显著纠正粗筛误排。
- IUCr 2019 论文也明确建议"集成传统位置检索作为预筛以减少初始相数"，把全谱拟合的暴力计算量压下来。

### 6.7 关键结论
- 预筛三层：化学成分过滤 → d 值窗口/Hanawalt/Fink 索引 → 启发式命中分取 top-N；
- Smith–Snyder `FN = (1/|Δ2θ̄|)(N/Nposs)` 是公认峰位型 FoM；
- 工程标准范式：**粗筛 top-N（廉价）+ 全谱拟合精排（昂贵但准）**。

### 6.8 来源
- 北得州大学 *Lecture 14 Qualitative Analysis*（Hanawalt/Fink/FN 定义与经验值）：https://sites.chemistry.unt.edu/~tgolden/courses/Lecture14%20XRD%202024.pdf
- 公开白皮书 *A plug-in program to perform Hanawalt or Fink search indexing*：https://www.icdd.com/assets/support/Faber-JPD2004APLUG-INPROGRAM.pdf
- IUCr IT Ch. 3.7 *Crystallographic databases and powder diffraction*（Hanawalt 历史与原理）：https://onlinelibrary.wiley.com/iucr/itc/Ha/ch3o7v0001/ch3o7.pdf
- IUCr *FN: A criterion for rating powder diffraction patterns…*（Smith-Snyder FOM 原始论文摘要）：https://journals.iucr.org/paper?a18089
- arXiv *Dara*（峰匹配预筛 + Rietveld 精修）：https://arxiv.org/html/2510.19667v1
- arXiv *MatDiffract*（top-N 精修重排前后 Rwp 分布对比）：https://arxiv.org/html/2607.20880

---

## 7. 评分归一化

### 7.1 为什么要归一化
原始 Rwp 受背底水平、峰数、扫描范围、相含量影响，直接当排名分有三个公开指出的缺陷（IUCr 2019）：
1. Rwp 不能区分仅晶胞参数略异的两个相似相；
2. Rwp 偏向强散射相（大相含量占优）；
3. 宽化相可仅靠"拟合背底"压低 Rwp。
因此需要把 Rwp 映射成候选间可比、且对这些偏差鲁棒的 FoM。

### 7.2 常见 Rwp → FoM 映射
| 映射方式 | 形式 | 特点 |
|---|---|---|
| 直接 Rwp 升序 | `score = Rwp` | 最简单；粗排可用，但有上述三缺陷 |
| 指数映射 | `score = exp(-Rwp/σ)` | 把 [0,~0.3] 的 Rwp 压到 (0,1] 区间，σ 为尺度常数；值越大越匹配，便于展示与阈值判断 |
| 线性归一化 | `score = 1 - Rwp/Rwp_max` 或 `(Rwp_worst - Rwp)/(Rwp_worst - Rwp_best)` | 同一次检索内候选间相对排序，可比；跨次检索不可比 |
| 加权改进 FoM（IUCr 2019） | 在 Rwp 基础上乘/加惩罚项：晶胞接近度、相含量权重、晶粒尺寸/微应变惩罚 | 公开文献做法，用于多相贪婪添加时的逐轮排序 |

- 指数映射 `exp(-Rwp/σ)`：σ 需按本仪器/本类样品标定（例如取期望可接受 Rwp≈0.08~0.10 处映射到 0.4~0.5），使"好匹配"得分接近 1、"差匹配"接近 0。
- 另一种公开 FoM（火星返回样品管实验）：由实测峰与数据库峰的强度差与 2θ 差加权求和映射到 [0,1]，1 为完美匹配——属峰表型归一化，可作为粗筛分。

### 7.3 候选可比性原则
- **同一轮检索内**：固定扫描范围、背底阶数、峰形模型、约束边界，所有候选用同一套拟合配置，Rwp 才能横向比。
- **跨轮/跨实验**：不要直接比 Rwp 绝对值；用相对排名或归一化到 [0,1] 的分数。
- IUCr 2019 特别指出：逐轮贪婪添加时每轮候选集不同，逐轮内的 FoM 只用于当轮排序，跟踪整体进程应看全局 Rwp / WSS（加权残差平方和）是否单调下降。

### 7.4 关键结论
- 粗排可用 Rwp 直接升序；面向用户展示时映射到 [0,1]（`exp(-Rwp/σ)` 或线性归一）更直观；
- 归一化必须在"同一拟合配置、同一轮候选集"内进行，否则不可比；
- 多相贪婪添加的逐轮排序可在 Rwp 上叠加晶胞接近度/相含量/宽化惩罚项。

### 7.5 来源
- IUCr 2019 *Full-profile search–match by the Rietveld method*（Rwp 作 FoM 的三缺陷与改进 FoM）：https://pmc.ncbi.nlm.nih.gov/articles/PMC6557175/
- *Meteoritics & Planetary Science*（[0,1] 峰表 FoM 定义）：https://onlinelibrary.wiley.com/doi/full/10.1111/maps.14105
- arXiv *MatDiffract*（精修重排后 Rwp 分布归一化对比）：https://arxiv.org/html/2607.20880
- IUCr Erice 讲义（Rwp 绝对值依赖背底与峰数）：https://www.iucr.org/__data/iucr/powder/Erice2011/day8/d1/maud.pdf

---

## 参考来源（按主题分组）

> 说明：以下 URL 均为公开可访问的文献、机构文档或教材；文中不点名任何商业软件产品，产品功能仅作中性概括。

**FPFM 流程与自动鉴定**
- IUCr J. Appl. Cryst. 2019 全谱检索方法：https://journals.iucr.org/j/issues/2019/03/00/nb5231/index.html
- PMC 镜像：https://pmc.ncbi.nlm.nih.gov/articles/PMC6557175/
- IUCr 2004 高通量全谱分析：http://journals.iucr.org/j/issues/2004/02/00/mm0036/
- arXiv Dara 自动物相鉴定：https://arxiv.org/html/2510.19667v1
- arXiv MatDiffract 自动平台：https://arxiv.org/html/2607.20880

**峰形与 Caglioti**
- Jana2006 峰形函数文档：https://jana.fzu.cz/docs/Powder_parameters_new.pdf
- IUCr IT Vol.H Ch.3.2（Voigt/Pearson VII）：https://onlinelibrary.wiley.com/iucr/itc/Ha/ch3o2v0001/sec3o2o2o3.pdf
- IUCr IT Ch.3.6（Caglioti、η 参数化）：https://onlinelibrary.wiley.com/iucr/itc/Ha/ch3o6v0001/ch3o6.pdf
- arXiv PCrystalX（U/V/W 标定）：https://arxiv.org/pdf/2204.14072v1
- IUCr 2022 仪器函数参数化（η 抛物线）：https://onlinelibrary.wiley.com/iucr/doi/10.1107/S1600576722003089/index.html
- SD 矿业学院课件（Pearson VII）：http://ahrenkiel.sdsmt.edu/courses/Spring2021/NANO704/lectures/4_XRayDiff/4_XrayDiff_text_125.pdf
- APS LineFit 手册（Intermediate Lorentzian）：https://www-dev.aps.anl.gov/files/APS-Uploads/SECTOR8/8-ID/linefit_manual.pdf
- IUCr 1982 六峰形对比：http://journals.iucr.org/paper?buy=yes&cnor=a21811

**背底处理**
- HandWiki Rietveld（Chebyshev 背底）：https://handwiki.org/wiki/Rietveld_refinement
- NIST SRM 676a 证书：https://tsapps.nist.gov/srmext/certificates/676a.pdf
- R alkahest 文档（SNIP）：https://www.stats.bris.ac.uk/R/web/packages/alkahest/refman/alkahest.html
- SNIP 伪代码教材：https://yusukehashimotolab.github.io/AI-Knowledge-Notes/knowledge/en/MI/experimental-data-analysis-introduction/chapter-2.html

**Kα 双线**
- UCL X 射线产生：http://pd.chem.ucl.ac.uk/pdnn/inst1/xrays.htm
- 北得州大学 Lecture 4：https://sites.chemistry.unt.edu/~tgolden/courses/Lecture4%205570%20XRD%202024.pdf
- IODP 仪器参数实例（λ1/λ2/比值）：https://publications.iodp.org/other/Oman/SUPP_MAT/F3_XRD_data/BA4A/1_RAW/CSV/10A_98_1_73_73.csv
- IUCr Bragg 原理：https://www.iucr.org/publ/50yearsofxraydiffraction/full-text/principles

**拟合判据**
- IUCr CIF 词典 Rwp/Rexp：https://www.iucr.org/__data/iucr/cifdic_html/1/cif_pd.dic/Ipd_proc_ls_prof_.html
- Cambridge *R factors in Rietveld analysis*：https://resolve-he.cambridge.org/core/journals/powder-diffraction/article/r-factors-in-rietveld-analysis-how-good-is-good-enough/17439A1F889B689C495549A234D53682
- NIST GSAS 教程（χ²）：https://www.nist.gov/el/mssd/gsas-tutorial-rietveld-refinement
- IUCr Erice Rietveld 讲义：https://www.iucr.org/__data/iucr/powder/Erice2011/day8/d1/maud.pdf
- Am. Mineral. Rietveld 定量分析：https://msaweb.org/AmMin/AM78/AM78_932.pdf

**候选预筛与 FoM**
- 北得州大学 Lecture 14：https://sites.chemistry.unt.edu/~tgolden/courses/Lecture14%20XRD%202024.pdf
- Hanawalt/Fink 索引白皮书：https://www.icdd.com/assets/support/Faber-JPD2004APLUG-INPROGRAM.pdf
- IUCr IT Ch.3.7 数据库与检索：https://onlinelibrary.wiley.com/iucr/itc/Ha/ch3o7v0001/ch3o7.pdf
- Smith–Snyder FN 原始论文（摘要）：https://journals.iucr.org/paper?a18089

**评分归一化**
- IUCr 2019（FoM 缺陷与改进）：https://pmc.ncbi.nlm.nih.gov/articles/PMC6557175/
- M&PS [0,1] FoM：https://onlinelibrary.wiley.com/doi/full/10.1111/maps.14105

---

## 附：对 XinMatch 实现的最小可行方案建议（基于上述公开原理）
1. 理论谱生成：对每张 d–I 卡片，按实测 λ1/λ2 双线、pV 峰形、Caglioti U/V/W（由本仪器标样标定一次）逐点叠加强度。
2. 每条候选做受限最小二乘：只解 scale、2θ 零点、背底 Chebyshev 系数（峰宽/η 固定）；用 Levenberg–Marquardt 或线性子问题解析解。
3. 预筛：化学成分 + d 值窗口命中数粗筛 top-N（如 50~200），再全谱精排。
4. 排序：精排用 Rwp；展示分用 `exp(-Rwp/σ)` 映射到百分制。
5. 多相：贪婪添加，每加一重拟合，相含量低于阈值则剔除。
