# TX Linear Fit 技术原理与使用指南

本文介绍 TX Linear Fit 的用途、当前 Python 实现的数学模型、它与 IEEE 802.3 / OIF CEI
发送端测试方法的关系，以及 GUI、CLI 的实际用法。

> [!IMPORTANT]
> 本工具是波形分析与算法验证工具，不是完整的一致性测试系统。`neutral`、`ieee8023`
> 和 `oif` 只改变报告中的语义标签，不会自动选择协议参数、加入限值或给出 pass/fail。
> 正式认证应以目标 PHY、测试点、标准版本、夹具去嵌、规定滤波器和仪器流程为准。

## 1. 工具解决什么问题

工具接收示波器采集的已知周期码型波形，重建理想符号序列，并完成以下分析：

1. 从时间轴和符号率自动确定分析 OSR（samples/UI），或对无时间轴数据使用手动 OSR。
2. 将实测波形与 PRBS 序列同步，提取有限长度的线性脉冲响应。
3. 计算拟合残差、稳态电压、脉冲峰值、拟合 SNDR 和残余 ISI 指标。
4. 求解一个分析侧 FFE，并可附加决策反馈 DFE，观察均衡后的 constellation、RLM 和眼图。
5. 从拟合脉冲估算测量派生传递函数、Nyquist 频点幅度和 3 dB 带宽。
6. 生成 PNG、CSV 和一个可独立打开的自包含 HTML 报告。

它适合用于发送端波形诊断、Python 算法验证、参数敏感性分析和实验数据归档。
它不能替代 VNA 的 S 参数测量，也不会仅凭一份波形证明 IEEE 802.3 或 OIF CEI 合规。

## 2. 符号与参数

| 符号/参数 | 含义 | 代码参数 |
|---|---|---|
| `R_s` | 符号率，单位 baud | `symbol_rate` |
| UI | 一个符号周期，`T_UI = 1/R_s` | - |
| `M` | 每 UI 的分析采样数，即 OSR | `osr` |
| `N_s` | 输入记录的采样点数 | 由输入文件决定 |
| `N` | 参与拟合的符号数 | 由输入长度决定 |
| `N_p` | 拟合脉冲包含的总 UI 数 | `total_cursor_fit` |
| `D_p` | 拟合窗口中主光标之前的 UI 数 | `pre_cursor_fit` |
| `N_w` | 分析 FFE 的总 tap 数 | `total_cursor_ffe` |
| `D_w` | FFE 主 tap 之前的 tap 数 | `pre_cursor_ffe` |
| `N_DFE` | DFE post-cursor tap 数 | `dfe_tap_num` |
| `y[k]` | 示波器采集并重采样后的波形 | `stream_input_interp` |
| `x[n]` | 与波形对齐的理想符号 | `stream_decision_interp` |
| `p[k]` | 线性拟合得到的脉冲响应 | `fit_results['p']` |
| `e[k]` | 实测波形与线性模型之差 | `fit_results['e']` |

为保证 Codex、终端和普通 Markdown 阅读器都能直接显示，本文不用 LaTeX 数学扩展。公式
采用 Unicode 数学符号和等宽文本块：大写字母表示矩阵，小写字母表示标量或向量，`(·)ᵀ`
表示转置，`‖·‖₂` 和 `‖·‖_F` 分别表示 Euclidean 范数与 Frobenius 范数。

这里的 FFE 是**分析侧逆滤波器**。GUI 默认 18 tap 表示用 18 个系数观察可恢复性，
并不表示 DUT 的发送端硬件一定有 18 个 tap，也不等同于协议中的 TX FIR tap 数。

## 3. 分析流程

### 3.1 输入与 OSR

带时间轴时，程序先用相邻采样间隔估计标称采样周期，再计算局部与整段记录的采样密度：

```text
Δt̃          = median { t[k+1] - t[k] },  0 ≤ k < N_s - 1
M_native    = 1 / (R_s · Δt̃)
M_effective = (N_s - 1) / { R_s · [t[N_s-1] - t[0]] }
```

二者分别描述局部采样网格和整段记录的平均采样密度。自动模式把两者取最近整数，
仅在结果一致、`M ≥ 2` 且 `M_native` 距最近整数不超过 10% 时接受。程序还根据
`Δt/Δt̃` 的整数倍估计缺失采样比例，并将诊断信息写入报告。

确定整数 OSR `M` 后，带时间轴波形会线性插值到均匀分析网格：

```text
t_grid[k] = t[0] + k / (M · R_s),  k = 0, 1, ..., N_grid - 1
```

其中 `N_grid` 是重采样后的点数。

只有电压值的文件无法从自身判断采样率，因此必须手动指定 OSR。对带时间轴数据手动
指定 OSR 会强制使用该分析网格，只有在明确知道需要重采样时才应这样做。

### 3.2 码型生成与同步

PAM4 使用四个归一化电平。当前 Gray 映射为：

| 输入比特 `(A,B)` | PAM4 符号 | 归一化电平 |
|---|---:|---:|
| `00` | 0 | -1 |
| `01` | 1 | -1/3 |
| `11` | 2 | +1/3 |
| `10` | 3 | +1 |

PRBS13 使用多项式

```text
G(x) = 1 + x + x² + x¹² + x¹³
```

其周期为 `2¹³ - 1 = 8191`。这一多项式和 Gray 映射与 OIF CEI-05.3 的
QPRBS13-CEI 定义一致。工具使用固定非零种子，波形与本地序列的符号相位随后由互相关
确定。正式合规测量仍应核对目标规范要求的发生器方向、种子、bit pairing 和序列示例。

程序把理想符号按每个符号重复 `M` 次，与实测波形做互相关，选择绝对相关峰值对应的
延迟；若相关峰为负，则自动翻转实测波形极性。首次拟合后，如果 FFE 最大 tap 没有落在
期望的主 tap 位置，还会依次尝试 `-2,-1,+1,+2` UI 的符号移位。

## 4. 线性拟合算法

### 4.1 从卷积模型到矩阵模型

把波形按 UI 折叠为 `M × N` 数据矩阵 `Y`：

```text
Y[m,n] = y[nM + m],  0 ≤ m < M,  0 ≤ n < N
```

将符号序列循环移动 `D_p` 个 UI，构造包含 `N_p` 组循环移位符号和一行常数 1 的
设计矩阵 `X`，其尺寸为 `(N_p+1) × N`。矩阵元素定义为

```text
X[r,n] = x[mod(n + D_p - r, N)]    当 0 ≤ r < N_p
X[r,n] = 1                          当 r = N_p
                                         0 ≤ n < N
```

于是线性模型可写成

```text
Y ≈ PX
shape(P) = M × (N_p+1)
```

`P` 的前 `N_p` 列是各 UI 的相位采样响应，最后一列吸收直流偏置。以残差能量
为代价函数，最小二乘问题为

```text
P̂ = arg min_P J(P)
J(P) = ‖Y - PX‖_F²
```

将范数写成迹并对 `P` 求导：

```text
J(P)   = tr[(Y - PX)(Y - PX)ᵀ]
∂J/∂P = 2(PXXᵀ - YXᵀ)
```

令梯度为零；当 `XXᵀ` 可逆时，正规方程给出

```text
P̂ = YXᵀ(XXᵀ)⁻¹
```

拟合波形与代码采用的残差（拟合值减实测值）为

```text
Ŷ = P̂X
E = Ŷ - Y
```

将 `P̂` 的前 `N_p` 列按列展开，得到长度为 `M·N_p` 的 `p`，即

```text
p[m + Mr] = P̂[m,r],  0 ≤ m < M,  0 ≤ r < N_p
```

同样按列展开 `E` 得到 `e`。代码保留显式正规方程和
严格矩阵求逆，以保持当前算法的数值求解顺序，
不会在奇异时悄悄改用伪逆。

### 4.2 脉冲指标

稳态电压、脉冲峰值及其比值为

```text
v_f    = (1/M) · Σ p[k],  k = 0 ... M·N_p-1
p_max  = max p[k]
r_peak = p_max / v_f
```

令 `I_80` 表示全速率残差中央 80% 样本的索引集合。当前工具使用

```text
e_RMS,fit = √{ (1/|I_80|) · Σ e[k]² },  k ∈ I_80

SNDR_fit [dB] = 20 log₁₀(p_max / e_RMS,fit)
```

报告中的 `SNDR (Fit)` 指的就是这个值。还有一个需要留意的实现细节：报告字段
`eRms` 保存的是主采样相位残差的中间 80% RMS，而 `eRmsRatio` 和 `SNDR` 使用的是
全速率残差 RMS，因此不能用报告中的 `pmax/eRms` 反算出完全相同的 `SNDR`。

工具还将脉冲按主峰相位抽样为 `p_s[i]`，忽略主峰之后的前 10 个 post-cursor，
用其余尾部能量定义诊断指标：

```text
i_peak = arg max_i p_s[i]

                         p_s[i_peak]
SNR_ISI [dB] = 20 log₁₀ ──────────────────────────────────
                         √{Σ p_s[i]², i=i_peak+11...N_p-1}
```

它只描述有限拟合窗口末端的残余 ISI，不是通用噪声 SNR。

## 5. FFE 与 DFE

### 5.1 FFE 最小二乘解

从符号间隔脉冲 `p_s` 构造 Toeplitz 型卷积矩阵 `P3`，令目标向量 `x_p` 的第 `D_p+1`
个元素（按 1-based 计数）为 1、其余为 0。FFE 的目标是让
均衡脉冲尽量接近单位脉冲：

```text
ŵ = arg min_w ‖P3w - x_p‖₂²
```

令梯度为零，可得 FFE 正规方程及其闭式解：

```text
P3ᵀP3 ŵ = P3ᵀx_p
ŵ        = (P3ᵀP3)⁻¹P3ᵀx_p
```

`firNum` 是 `ŵ`，无 DFE 时用于画眼图的归一化系数为

```text
w_norm[i] = ŵ[i] / Σ ŵ[j],  j = 0 ... N_w-1
```

这里的 `w_norm[i]` 对应 `firNumNorm[i]`。这个归一化只保证直流增益
`Σ w_norm[i] = 1`，不限制单个系数幅度。如果正负 tap 互相抵消，使
`Σ ŵ[i]` 很小，某个归一化 tap 完全可能大于 1 或小于 -1。这不是数组
越界或自动饱和，而是无硬件约束的数学逆滤波结果；系数过大通常意味着噪声增强、脉冲
窗口不足或通道存在难以逆转的深衰减。

### 5.2 DFE 目标

启用 `N_DFE` 个 tap 时，程序不再要求前 `N_DFE` 个 post-cursor 在 FFE 输出中为
零，而是把目标设为

```text
x_p[D_p+j] = p_s[i_peak+j] / p_s[i_peak],  j = 1 ... N_DFE
```

这些值同时作为 `DFEtapWeight`，在硬判决后从当前样本中减去历史符号贡献。FFE+DFE
分支使用 `Σ |ŵ[i]| = 1` 的归一化。HTML 中的 Equalized Eye Diagram 使用 FFE-only
波形；FFE+DFE 主要用于 RLM 诊断。

若 `z_FFE[n]` 是 FFE 输出，`Q(·)` 是 PAM4 slicer，当前实现的反馈
步骤可写为

```text
â[n]           = Q(z_FFE[n])
z_after_DFE[n] = z_FFE[n] - Σ b[j]â[n-j],  j = 1 ... N_DFE
b[j]           = x_p[D_p+j]
```

### 5.3 为什么会出现 Singular matrix

正规方程要求 `P3` 满列秩。以下情况会导致或放大奇异性：

- `total_cursor_ffe > total_cursor_fit`，未知 FFE tap 比可用脉冲约束更多；
- PRBS、符号率、OSR 或波形同步设置错误，导致拟合脉冲退化；
- 脉冲窗口太短，重要前后游标落在窗口之外；
- 通道零点或高度相关的列使 `P3ᵀP3` 病态。

程序先强制 `total_cursor_fit >= total_cursor_ffe`，若数据本身仍不足以形成满秩矩阵，
会报告矩阵秩并要求增大 pulse fit 窗口或减少 FFE tap。这样比伪逆给出一个表面可用但
不可解释的结果更可靠。

## 6. RLM 公式与推导

### 6.1 电平提取

在最佳 FFE 采样相位上，程序用阈值 `-2/3, 0, +2/3` 将 PAM4 constellation 分组，
分别求四组均值得到

```text
V[-1] < V[-1/3] < V[+1/3] < V[+1]
```

代码字段 `V0`、`V1`、`V2`、`V3` 依次对应这四个均值。

若某一电平没有样本，相应 RLM 为 `n/a`。正式标准测量还要求指定测试码型、滤波器、
测试点和中心采样方法；这里的分组来自分析侧最佳相位。

### 6.2 Min Adjacent Spacing

令三个相邻间距为

```text
d_L = V[-1/3] - V[-1]
d_M = V[+1/3] - V[-1/3]
d_U = V[+1]   - V[+1/3]
```

总摆幅为 `V[+1] - V[-1] = d_L + d_M + d_U`，理想等间距为总摆幅的 `1/3`，所以最小
眼高相对理想眼高的比例是

```text
          min(d_L, d_M, d_U)     3 · min(d_L, d_M, d_U)
RLM_adj = ──────────────────── = ────────────────────────
            [V[+1]-V[-1]]/3           V[+1]-V[-1]
```

报告名称为 `RLM (Min Adjacent Spacing)`，内部字段名为 `RLMbj`。这个名称没有把它
伪装成当前 IEEE 802.3bs 定义。

### 6.3 IEEE 802.3bs / OIF CEI 定义

先用外层电平定义中点：

```text
V_mid = [V[-1] + V[+1]] / 2
```

再把两个内层电平归一化，使外层对应 `-1` 与 `+1`：

```text
ES1 = (V[-1/3] - V_mid) / (V[-1] - V_mid)
ES2 = (V[+1/3] - V_mid) / (V[+1] - V_mid)
```

IEEE 802.3bs 公开任务组材料和 OIF CEI-05.3 16.C.4.3 给出的定义相同：

```text
RLM = min(3·ES1, 3·ES2, 2-3·ES1, 2-3·ES2)
```

理想 PAM4 中 `ES1 = ES2 = 1/3`，四项都等于 1，因此 `RLM = 1`。在通常的
`0 ≤ ES_i ≤ 2/3` 范围内，单个内层电平的两项可
改写为

```text
min(3·ES_i, 2-3·ES_i) = 1 - 3·|ES_i - 1/3|
```

所以该公式等价于由两个内层电平中**偏离理想位置最严重的一个**决定 RLM。它既惩罚
向中间压缩，也惩罚向外偏移，与只看三个相邻间距最小值的 `RLM_adj` 并非同一指标。

## 7. 协议 SNDR 与工具 SNDR

OIF CEI-05.3 的 CEI-112G PAM4 章节使用

```text
                           p_max²
SNDR_std [dB] = 10 log₁₀ ─────────
                         σ_e² + σ_n²
```

`p_max` 是电压幅度，平方后与信号功率成正比；互不相关的拟合误差和随机噪声按方差
相加，因此总损伤功率为 `σ_e² + σ_n²`。功率比使用 `10 log₁₀`，这就得到上式；若分母
先合成为等效 RMS 幅度，才可以等价地写成 `20 log₁₀` 的幅度比。

`σ_e` 是线性拟合误差的标准差，`σ_n` 则是在至少 6 个相同 PAM4 符号连续
区间内、固定相位处测得的独立噪声项。IEEE 802.3 发送端 SNDR 的公开任务组材料也给出
同样的信号功率除以误差与噪声功率之和的结构。

当前报告的 `SNDR (Fit)` 没有单独测量 `σ_n`，并以中间 80% 残差 RMS 代替规定的
完整测量流程，因此是

```text
                           p_max²
SNDR_fit [dB] = 10 log₁₀ ──────────
                          e_RMS,fit²
```

只有在 `σ_n = 0` 且 `e_RMS,fit = σ_e` 的假设下，两式才代数等价。因此报告不
套用协议 SNDR 限值。CLI 还会输出 `SNDR ffe` 和 `SNDR ffe_and_dfe`：它们是在每个
采样相位上完成均衡、硬判决后，以“判决符号 RMS / 判决误差 RMS”计算并选择最佳相位的
constellation 指标。分子、分母、滤波和判决均不同，不能与 `SNDR (Fit)` 横向比较；
为避免误解，这两个值不显示在 HTML 报告中。

## 8. 测量派生传递函数

程序构造一个幅度为 `max |p[k]|`、持续 1 UI、上升下降时间为 1 fs 的理想梯形脉冲
`p_ideal[k]`。令 `DFT{·}` 表示离散 Fourier 变换，先计算原始
幅频比，再归一化直流增益：

```text
P(f)       = DFT{p[k]}
P_ideal(f) = DFT{p_ideal[k]}
H̃(f)       = |P(f)| / |P_ideal(f)|
H(f)       = H̃(f) / H̃(0),  H(0) = 1
```

理想脉冲频谱的零点会导致除零，程序先保留非零频点，再线性插值平滑分母。报告中的
Nyquist 值为

```text
H_Nq [dB] = 20 log₁₀ |H(R_s/2)|
```

`BW 3dB` 是幅频响应第一次穿越 `-3 dB` 的插值频点：

```text
f_3dB = inf { f > 0 : 20 log₁₀|H(f)| ≤ -3 }
```

这里的 `H(f)` 同时包含发送端、采集链路和有限拟合窗口的影响；它不是混合模 S 参数
`S_DD21`，不能替代协议
的 channel insertion loss。数值为正时表示相对 DC 有高频提升，不应称为正的“损耗”。

## 9. 眼宽算法

报告同时保留两种横向眼开度：

**Central 99% eye width** 是主指标。程序在相邻样本异号时用线性插值求零交叉相位：

```text
φ[i] = mod(k - y[k] / (y[k+1] - y[k]), M)
```

用圆均值 `φ_mean` 求 crossing 相位中心，再将每个相位展开到 `[-M/2, M/2)`：

```text
φ_mean = [M/(2π)] · arg { Σ exp(j·2π·φ[i]/M) }
δ[i]   = mod(φ[i] - φ_mean + M/2, M) - M/2
```

令 `Q_α{δ}` 表示展开后相位的 `α` 分位点，则中央 99% crossing
跨度及剩余眼宽为

```text
Δ_99      = Q_0.995{δ} - Q_0.005{δ}
W_99 [UI] = min { 1, max[0, 1 - Δ_99/M] }
T_99      = W_99 · T_UI = W_99/R_s
T_99 [ps] = 10¹² · W_99/R_s
```

PAM4 下这测量的是跨越零阈值的中间眼，不是三个眼分别的协议眼宽。

例如 53.125 GBd 时 1 UI 约为 18.824 ps，4 ps 约为 0.2125 UI。

**Strict eye width** 把波形折叠到 2 UI，在离散采样点上寻找最长的零交叉计数为零的
连续区间。它受 OSR 量化且容易被单个稀有 crossing 压缩，只作为补充诊断保留。

## 10. 与 IEEE 802.3 / OIF CEI 的边界

线性拟合、RLM 与 SNDR 的数学骨架来自相同的发送端测量思想，但具体 PHY 会覆盖参数。
以 53.125 GBd 所在的 OIF CEI-112G 范围为例，CEI-05.3 使用的线性拟合窗口并不统一：

| OIF CEI-05.3 接口 | 章节 | `N_p` | `D_p` | TX FIR 功能模型 |
|---|---:|---:|---:|---:|
| CEI-112G-XSR-PAM4 | 24.3.1.6.1 | 4 | 2 | 3 tap |
| CEI-112G-MR-PAM4 | 26.3.1.6.1 | 19 | 4 | 5 tap |
| CEI-112G-LR-PAM4 | 27.3.1.6.1 | 29 | 4 | 5 tap |

GUI 默认 `Np=32, Dp=4, Nw=18` 是为了保留较长的 pulse tail，并给 18-tap 分析 FFE
足够的方程约束。它不是上表任一协议 profile。正式复现某个条款时至少还要核对：

| 项目 | 当前工具 | 正式协议测量 |
|---|---|---|
| 测试码型 | 用户选择的固定 PRBS | 指定 PRBS13Q/QPRBS13-CEI、周期与对齐 |
| OSR | 时间轴自动整数化或手动设置 | 条款规定的最低有效采样要求及插值方式 |
| 测量带宽 | 使用输入文件已有带宽 | 规定 Bessel-Thomson 滤波器或等效补偿 |
| 测试点 | 文件所代表的位置 | 指定 package ball、bump、TP0/TP2 等 |
| `N_p, D_p` | 用户可配，GUI 默认 32/4 | 由目标 PHY 条款指定 |
| FFE tap | 分析侧可配，默认 18 | TX FIR 模型及允许范围由条款指定 |
| SNDR 噪声项 | 不单独测 `σ_n` | 按条款独立测量并合成功率 |
| 夹具/通道 | 包含在输入波形中 | 按条款去嵌、校准或保留 |
| 结论 | 诊断指标 | 规定限值与 pass/fail 流程 |

IEEE 802.3 的 `N_p, D_p`、滤波器、测试点和限值同样会随 PHY 条款及修订变化。不要把
`--profile ieee8023` 当成自动配置；它目前只是报告标签。

## 11. GUI 用法

安装依赖后启动：

```powershell
python python_src/gui.py
```

使用步骤：

1. 选择 `.txt` 或 `.csv` 输入文件和输出目录。
2. 输入符号率。默认 `53.125 GBd`，这里是 symbol rate，不是 PAM4 bit rate。
3. 选择 NRZ/PAM4 和 PRBS7/13/15。GUI 自动使用完整周期长度。
4. 带时间轴的 `.txt` 保持 OSR 为“自动”；只有电压值的 `.csv` 切换为“手动”。
5. 根据需要修改 pulse fit、FFE 和 DFE tap 数，点击“开始分析”。
6. 默认会生成并打开 `tx_linear_fit_report.html`。

GUI 默认值：

| 参数 | 默认值 |
|---|---:|
| 符号率 | 53.125 GBd |
| 调制 / 码型 | PAM4 / PRBS13 |
| OSR | auto |
| Pulse fit | 4 个前游标，32 个总 UI |
| FFE | 4 个前游标，18 个总 tap |
| DFE | 1 tap |

GUI 不显示重复次数、协议 profile 和序列长度等低频使用参数。PRBS31 的完整周期过长，
只在 CLI 中提供，并应按实际采集长度设置有界的 `--pattern_length`。

## 12. CLI 用法

带时间轴的 PAM4 示例：

```powershell
python python_src/run_tx_linear_fit.py `
  --filetype lab_txt `
  --filename "C:\path\to\Waveform.txt" `
  --symbol_rate 53.125e9 `
  --modulation PAM4 `
  --prbs_pattern PRBS13 `
  --pattern_length 8191 `
  --pre_cursor_fit 4 `
  --total_cursor_fit 32 `
  --pre_cursor_ffe 4 `
  --total_cursor_ffe 18 `
  --dfe_tap_num 1 `
  --output-dir outputs\run
```

只有电压值的输入必须指定 OSR：

```powershell
python python_src/run_tx_linear_fit.py `
  --filetype lab_csv `
  --filename "C:\path\to\Waveform.csv" `
  --osr 16 `
  --symbol_rate 53.125e9 `
  --modulation PAM4 `
  --prbs_pattern PRBS13 `
  --pattern_length 8191 `
  --pre_cursor_fit 4 `
  --total_cursor_fit 32 `
  --pre_cursor_ffe 4 `
  --total_cursor_ffe 18 `
  --dfe_tap_num 1 `
  --output-dir outputs\run
```

默认生成报告、PNG 和 CSV，并尝试打开 HTML。常用控制项：

| 选项 | 作用 |
|---|---|
| `--no-open` | 生成报告但不打开浏览器 |
| `--no-report` | 不生成 HTML |
| `--plots 0` | 不渲染 PNG |
| `--report PATH` | 指定额外的 HTML 名称或路径 |
| `--profile neutral\|ieee8023\|oif` | 只设置报告语义标签，不加载限值 |

查看全部参数：

```powershell
python python_src/run_tx_linear_fit.py --help
```

## 13. 输入与输出

`lab_txt` 在精确的 `Data, ` 行之后读取 `time,voltage`。下例用 `<SPACE>` 显示行末的
一个 ASCII 空格：

```text
Scope export header
Data,<SPACE>
0.000000000000e+00,0.0123
1.176470588235e-12,0.0187
```

`lab_csv` 在同一标记之后每行只读取一个电压值；`<SPACE>` 同样表示一个 ASCII 空格：

```text
Scope export header
Data,<SPACE>
0.0123
0.0187
```

每次运行的产物位于输出目录：

- `tx_linear_fit_report.html`：图片已内嵌，可独立移动和打开；
- `results/*.png`：拟合、pulse、FFE、传递函数与眼图；
- `txcross.csv`、`txhist.csv`：均衡眼图的 crossing 统计。

## 14. 参数选择建议

- 优先使用带时间轴的原始数据与自动 OSR。若报告的 native/effective samples/UI 不一致，
  先核对符号率、时间单位、丢点和采集导出格式。
- `pre_cursor_fit` 应覆盖可见前游标，`total_cursor_fit` 应覆盖主要 pulse tail。
- 拟合窗口、FFE 和 DFE 参数必须满足下式：

```text
0 ≤ D_p
D_p + N_DFE < N_p
0 ≤ D_w < N_w ≤ N_p
```

- 增加 FFE tap 并不总会改善结果。过长的无约束逆滤波器可能用很大正负系数追逐噪声。
- 要复现协议条款时，先按目标接口设置 `N_p, D_p` 和采集滤波器，再谈限值；不要从
  GUI 默认值反推标准配置。
- 比较两次运行时，固定码型、符号率、OSR、窗口、tap 数和输入处理，否则指标不可比。

## 15. 代码对应关系

| 内容 | 实现 |
|---|---|
| 统一分析流程、OSR、参数校验 | [`application.py`](../python_src/application.py) |
| PRBS 与 PAM4/NRZ 映射 | [`pattern.py`](../python_src/pattern.py) |
| 示波器文本解析 | [`process_input.py`](../python_src/process_input.py) |
| 矩阵拟合、FFE/DFE 系数 | [`fit_pulse_response.py`](../python_src/fit_pulse_response.py) |
| 同步、均衡、constellation 与传递函数 | [`pulse_response_tool.py`](../python_src/pulse_response_tool.py) |
| RLM | [`calc_rlm.py`](../python_src/calc_rlm.py) |
| 眼宽与 crossing | [`eye_info.py`](../python_src/eye_info.py) |
| HTML 报告 | [`report.py`](../python_src/report.py) |
| GUI / CLI | [`gui.py`](../python_src/gui.py)、[`run_tx_linear_fit.py`](../python_src/run_tx_linear_fit.py) |

## 16. 参考资料

以下均为标准组织的官方页面或公开任务组材料；正式测试应查阅目标标准的当前完整文本。

1. [IEEE Std 802.3-2022, IEEE Standard for Ethernet](https://standards.ieee.org/ieee/802.3/10422/)，
   当前基础标准页面与修订入口。
2. [IEEE P802.3bs: PAM4 transmitter linearity / RLM change material](https://www.ieee802.org/3/bs/public/16_03/healey_3bs_02_0316.pdf)，
   给出 `V_mid`、`ES1`、`ES2` 与 RLM 公式的公开任务组材料。
3. [IEEE P802.3ck: transmitter SNDR background](https://www.ieee802.org/3/ck/public/adhoc/oct02_19/diminico_3ck_adhoc_100219.pdf)，
   展示 `p_max`、`σ_e`、`σ_n` 的 SNDR 结构；任务组材料不是标准正文。
4. [OIF Implementation Agreements](https://www.oiforum.com/technical-work/implementation-agreements-ias/)，
   OIF 发布版本索引。
5. [OIF-CEI-05.3 Common Electrical I/O](https://www.oiforum.com/wp-content/uploads/OIF-CEI-05.3.pdf)，
   重点参见 10.3.1.6.4-10.3.1.6.5（矩阵拟合与 FFE）、16.C.1/16.C.3/16.C.4.3
   （Gray mapping、QPRBS13-CEI、RLM）及 24/26/27.3.1.6（CEI-112G XSR/MR/LR）。

文档按 2026-09-05 可公开获取的版本核对。标准条款和限值可能随修订变化。
