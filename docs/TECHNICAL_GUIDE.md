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

它适合用于 Python/MATLAB 结果复核、发送端波形诊断、参数敏感性分析和实验数据归档。
它不能替代 VNA 的 S 参数测量，也不会仅凭一份波形证明 IEEE 802.3 或 OIF CEI 合规。

## 2. 符号与参数

| 符号/参数 | 含义 | 代码参数 |
|---|---|---|
| $R_s$ | 符号率，单位 baud | `symbol_rate` |
| UI | 一个符号周期，$T_{UI}=1/R_s$ | - |
| $M$ | 每 UI 的分析采样数，即 OSR | `osr` |
| $N$ | 参与拟合的符号数 | 由输入长度决定 |
| $N_p$ | 拟合脉冲包含的总 UI 数 | `total_cursor_fit` |
| $D_p$ | 拟合窗口中主光标之前的 UI 数 | `pre_cursor_fit` |
| $N_w$ | 分析 FFE 的总 tap 数 | `total_cursor_ffe` |
| $D_w$ | FFE 主 tap 之前的 tap 数 | `pre_cursor_ffe` |
| $N_{DFE}$ | DFE post-cursor tap 数 | `dfe_tap_num` |
| $y(k)$ | 示波器采集并重采样后的波形 | `stream_input_interp` |
| $x(n)$ | 与波形对齐的理想符号 | `stream_decision_interp` |
| $p(k)$ | 线性拟合得到的脉冲响应 | `fit_results['p']` |
| $e(k)$ | 实测波形与线性模型之差 | `fit_results['e']` |

这里的 FFE 是**分析侧逆滤波器**。GUI 默认 18 tap 表示用 18 个系数观察可恢复性，
并不表示 DUT 的发送端硬件一定有 18 个 tap，也不等同于协议中的 TX FIR tap 数。

## 3. 分析流程

### 3.1 输入与 OSR

带时间轴时，程序先取相邻采样间隔的中位数 $\widetilde{\Delta t}$，计算

$$
M_{native}=\frac{1}{R_s\widetilde{\Delta t}},\qquad
M_{effective}=\frac{N_s-1}{(t_{end}-t_0)R_s}.
$$

二者分别描述局部采样网格和整段记录的平均采样密度。自动模式把两者取最近整数，
仅在结果一致、$M\ge 2$ 且 $M_{native}$ 距最近整数不超过 10% 时接受。程序还根据
$\Delta t/\widetilde{\Delta t}$ 的整数倍估计缺失采样比例，并将诊断信息写入报告。

确定 $M$ 后，带时间轴波形会线性插值到

$$
t_k=\frac{k}{M R_s}.
$$

只有电压值的文件无法从自身判断采样率，因此必须手动指定 OSR。对带时间轴数据手动
指定 OSR 会强制使用该分析网格，只有在明确知道需要重采样时才应这样做。

### 3.2 码型生成与同步

PAM4 使用四个归一化电平。当前 Gray 映射为：

| 输入比特 `(A,B)` | PAM4 符号 | 归一化电平 |
|---|---:|---:|
| `00` | 0 | $-1$ |
| `01` | 1 | $-1/3$ |
| `11` | 2 | $+1/3$ |
| `10` | 3 | $+1$ |

PRBS13 使用多项式

$$
G(x)=1+x+x^2+x^{12}+x^{13},
$$

其周期为 $2^{13}-1=8191$。这一多项式和 Gray 映射与 OIF CEI-05.3 的
QPRBS13-CEI 定义一致。工具使用固定非零种子，波形与本地序列的符号相位随后由互相关
确定。正式合规测量仍应核对目标规范要求的发生器方向、种子、bit pairing 和序列示例。

程序把理想符号按每个符号重复 $M$ 次，与实测波形做互相关，选择绝对相关峰值对应的
延迟；若相关峰为负，则自动翻转实测波形极性。首次拟合后，如果 FFE 最大 tap 没有落在
期望的主 tap 位置，还会依次尝试 `-2,-1,+1,+2` UI 的符号移位。

## 4. 线性拟合算法

### 4.1 从卷积模型到矩阵模型

把波形按 UI 折叠为 $M\times N$ 矩阵：

$$
Y_{m,n}=y(nM+m),\qquad 0\le m<M.
$$

将符号序列循环移动 $D_p$ 个 UI，构造包含 $N_p$ 组循环移位符号和一行常数 1 的
设计矩阵 $X\in\mathbb{R}^{(N_p+1)\times N}$。于是模型可写成

$$
Y\approx PX.
$$

$P$ 的前 $N_p$ 列是各 UI 的相位采样响应，最后一列吸收直流偏置。最小二乘问题为

$$
\hat P=\arg\min_P\lVert Y-PX\rVert_F^2.
$$

对目标函数求导并令其为零：

$$
2(PXX^T-YX^T)=0,
$$

在 $XX^T$ 可逆时得到

$$
\boxed{\hat P=YX^T(XX^T)^{-1}}.
$$

拟合波形与残差为

$$
L=\hat PX,\qquad E=L-Y.
$$

将 $\hat P$ 的前 $N_p$ 列按列展开，得到长度为 $M N_p$ 的 $p(k)$；同样按列展开
$E$ 得到 $e(k)$。代码保留显式正规方程和严格矩阵求逆，以复现参考实现的数值顺序，
不会在奇异时悄悄改用伪逆。

### 4.2 脉冲指标

稳态电压、脉冲峰值及其比值为

$$
v_f=\frac{1}{M}\sum_k p(k),\qquad
p_{max}=\max_k p(k),\qquad
R_{peak}=\frac{p_{max}}{v_f}.
$$

当前工具用全速率残差中间 80% 的 RMS 作为 $e_{RMS,fit}$，避免记录首尾过渡影响：

$$
SNDR_{fit}=20\log_{10}\frac{p_{max}}{e_{RMS,fit}}.
$$

报告中的 `SNDR (Fit)` 指的就是这个值。还有一个需要留意的兼容行为：报告字段
`eRms` 保存的是主采样相位残差的中间 80% RMS，而 `eRmsRatio` 和 `SNDR` 使用的是
全速率残差 RMS，因此不能用报告中的 `pmax/eRms` 反算出完全相同的 `SNDR`。

工具还将脉冲按主峰相位抽样为 $p_s(i)$，忽略主峰之后的前 10 个 post-cursor，
用其余尾部能量定义诊断指标：

$$
SNR_{ISI}=20\log_{10}
\frac{\max_i p_s(i)}{\sqrt{\sum_{i>i_{peak}+10}p_s^2(i)}}.
$$

它只描述有限拟合窗口末端的残余 ISI，不是通用噪声 SNR。

## 5. FFE 与 DFE

### 5.1 FFE 最小二乘解

从符号间隔脉冲 $p_s$ 构造 Toeplitz 型卷积矩阵 $P_3$，令目标向量 $x_p$ 在
$D_p+1$ 位置为 1、其余为 0。FFE 的目标是让均衡脉冲尽量接近单位脉冲：

$$
\hat w=\arg\min_w\lVert P_3w-x_p\rVert_2^2.
$$

同样由正规方程得到

$$
\boxed{\hat w=(P_3^TP_3)^{-1}P_3^Tx_p}.
$$

`firNum` 是 $\hat w$，无 DFE 时用于画眼图的归一化系数为

$$
firNumNorm_i=\frac{w_i}{\sum_j w_j}.
$$

这个归一化只保证直流增益 $\sum_i firNumNorm_i=1$，不限制单个系数幅度。如果正负 tap
互相抵消，使 $\sum_iw_i$ 很小，某个归一化 tap 完全可能大于 1 或小于 -1。这不是数组
越界或自动饱和，而是无硬件约束的数学逆滤波结果；系数过大通常意味着噪声增强、脉冲
窗口不足或通道存在难以逆转的深衰减。

### 5.2 DFE 目标

启用 $N_{DFE}$ 个 tap 时，程序不再要求前 $N_{DFE}$ 个 post-cursor 在 FFE 输出中为
零，而是把目标设为

$$
x_p(D_p+j)=\frac{p_s(i_{peak}+j)}{p_s(i_{peak})},\qquad
1\le j\le N_{DFE}.
$$

这些值同时作为 `DFEtapWeight`，在硬判决后从当前样本中减去历史符号贡献。FFE+DFE
分支使用 $\sum_i|w_i|=1$ 的归一化。HTML 中的 Equalized Eye Diagram 使用 FFE-only
波形；FFE+DFE 主要用于 RLM 诊断。

### 5.3 为什么会出现 Singular matrix

正规方程要求 $P_3$ 满列秩。以下情况会导致或放大奇异性：

- `total_cursor_ffe > total_cursor_fit`，未知 FFE tap 比可用脉冲约束更多；
- PRBS、符号率、OSR 或波形同步设置错误，导致拟合脉冲退化；
- 脉冲窗口太短，重要前后游标落在窗口之外；
- 通道零点或高度相关的列使 $P_3^TP_3$ 病态。

程序先强制 `total_cursor_fit >= total_cursor_ffe`，若数据本身仍不足以形成满秩矩阵，
会报告矩阵秩并要求增大 pulse fit 窗口或减少 FFE tap。这样比伪逆给出一个表面可用但
不可解释的结果更可靠。

## 6. RLM 公式与推导

### 6.1 电平提取

在最佳 FFE 采样相位上，程序用阈值 $-2/3,0,+2/3$ 将 PAM4 constellation 分组，
分别求四组均值得到

$$
V_0<V_1<V_2<V_3.
$$

若某一电平没有样本，相应 RLM 为 `n/a`。正式标准测量还要求指定测试码型、滤波器、
测试点和中心采样方法；这里的分组来自分析侧最佳相位。

### 6.2 Min Adjacent Spacing

令三个相邻间距为

$$
d_0=V_1-V_0,\quad d_1=V_2-V_1,\quad d_2=V_3-V_2.
$$

总摆幅为 $V_3-V_0=d_0+d_1+d_2$，理想等间距为总摆幅的 $1/3$，所以最小眼高相对
理想眼高的比例是

$$
\boxed{RLM_{adj}=\frac{3\min(d_0,d_1,d_2)}{V_3-V_0}}.
$$

报告名称为 `RLM (Min Adjacent Spacing)`，内部字段名为 `RLMbj`。这个名称没有把它
伪装成当前 IEEE 802.3bs 定义。

### 6.3 IEEE 802.3bs / OIF CEI 定义

先用外层电平定义中点：

$$
V_{mid}=\frac{V_0+V_3}{2}.
$$

再把两个内层电平归一化，使外层对应 $-1$ 与 $+1$：

$$
ES_1=\frac{V_1-V_{mid}}{V_0-V_{mid}},\qquad
ES_2=\frac{V_2-V_{mid}}{V_3-V_{mid}}.
$$

IEEE 802.3bs 公开任务组材料和 OIF CEI-05.3 16.C.4.3 给出的定义相同：

$$
\boxed{RLM=\min(3ES_1,3ES_2,2-3ES_1,2-3ES_2)}.
$$

理想 PAM4 中 $ES_1=ES_2=1/3$，四项都等于 1，因此 $RLM=1$。在通常的
$0\le ES_i\le2/3$ 范围内，单个内层电平的两项可改写为

$$
\min(3ES_i,2-3ES_i)=1-3\left|ES_i-\frac13\right|.
$$

所以该公式等价于由两个内层电平中**偏离理想位置最严重的一个**决定 RLM。它既惩罚
向中间压缩，也惩罚向外偏移，与只看三个相邻间距最小值的 $RLM_{adj}$ 并非同一指标。

## 7. 协议 SNDR 与工具 SNDR

OIF CEI-05.3 的 CEI-112G PAM4 章节使用

$$
\boxed{SNDR_{std}=10\log_{10}
\frac{p_{max}^2}{\sigma_e^2+\sigma_n^2}}.
$$

$p_{max}$ 是电压幅度，平方后与信号功率成正比；互不相关的拟合误差和随机噪声按方差
相加，因此总损伤功率为 $\sigma_e^2+\sigma_n^2$。功率比使用 $10\log_{10}$，这就得到
上式；若分母先合成为等效 RMS 幅度，才可以等价地写成 $20\log_{10}$ 的幅度比。

$\sigma_e$ 是线性拟合误差的标准差，$\sigma_n$ 则是在至少 6 个相同 PAM4 符号连续
区间内、固定相位处测得的独立噪声项。IEEE 802.3 发送端 SNDR 的公开任务组材料也给出
同样的信号功率除以误差与噪声功率之和的结构。

当前报告的 `SNDR (Fit)` 没有单独测量 $\sigma_n$，并以中间 80% 残差 RMS 代替规定的
完整测量流程，因此是

$$
SNDR_{fit}=10\log_{10}\frac{p_{max}^2}{e_{RMS,fit}^2}.
$$

只有在 $\sigma_n=0$ 且 $e_{RMS,fit}=\sigma_e$ 的假设下，两式才代数等价。因此报告不
套用协议 SNDR 限值。CLI 还会输出 `SNDR ffe` 和 `SNDR ffe_and_dfe`：它们是在每个
采样相位上完成均衡、硬判决后，以“判决符号 RMS / 判决误差 RMS”计算并选择最佳相位的
constellation 指标。分子、分母、滤波和判决均不同，不能与 `SNDR (Fit)` 横向比较；
为避免误解，这两个值不显示在 HTML 报告中。

## 8. 测量派生传递函数

程序构造一个幅度为 $\max|p(k)|$、持续 1 UI、上升下降时间为 1 fs 的理想梯形脉冲
$p_{ideal}(k)$，定义

$$
H(f)=\frac{|FFT\{p(k)\}|}{|FFT\{p_{ideal}(k)\}|},\qquad H(0)=1.
$$

理想脉冲频谱的零点会导致除零，程序先保留非零频点，再线性插值平滑分母。报告中的
Nyquist 值为

$$
H_{Nq,dB}=20\log_{10}|H(R_s/2)|,
$$

`BW 3dB` 是 $20\log_{10}|H(f)|$ 首次低于 -3 dB 的插值交点。这里的 $H(f)$ 同时包含
发送端、采集链路和有限拟合窗口的影响；它不是混合模 S 参数 $S_{DD21}$，不能替代协议
的 channel insertion loss。数值为正时表示相对 DC 有高频提升，不应称为正的“损耗”。

## 9. 眼宽算法

报告同时保留两种横向眼开度：

**Central 99% eye width** 是主指标。程序在相邻样本异号时用线性插值求零交叉相位：

$$
\phi_i=\left(k-\frac{y_k}{y_{k+1}-y_k}\right)\bmod M.
$$

用圆均值求 crossing 相位中心，把相位展开到 $[-M/2,M/2)$，取 0.5% 与 99.5% 分位点
$q_{0.005},q_{0.995}$，得到

$$
\boxed{W_{99}=1-\frac{q_{0.995}-q_{0.005}}{M}}\quad\text{UI}.
$$

最后将结果裁剪到 $[0,1]$。PAM4 下这测量的是跨越零阈值的中间眼，不是三个眼分别的
协议眼宽。换算到时间为

$$
W_{ps}=W_{UI}\frac{10^{12}}{R_s}.
$$

例如 53.125 GBd 时 1 UI 约为 18.824 ps，4 ps 约为 0.2125 UI。

**Strict eye width** 把波形折叠到 2 UI，在离散采样点上寻找最长的零交叉计数为零的
连续区间。它受 OSR 量化且容易被单个稀有 crossing 压缩，只作为兼容诊断保留。

## 10. 与 IEEE 802.3 / OIF CEI 的边界

线性拟合、RLM 与 SNDR 的数学骨架来自相同的发送端测量思想，但具体 PHY 会覆盖参数。
以 53.125 GBd 所在的 OIF CEI-112G 范围为例，CEI-05.3 使用的线性拟合窗口并不统一：

| OIF CEI-05.3 接口 | 章节 | $N_p$ | $D_p$ | TX FIR 功能模型 |
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
| $N_p,D_p$ | 用户可配，GUI 默认 32/4 | 由目标 PHY 条款指定 |
| FFE tap | 分析侧可配，默认 18 | TX FIR 模型及允许范围由条款指定 |
| SNDR 噪声项 | 不单独测 $\sigma_n$ | 按条款独立测量并合成功率 |
| 夹具/通道 | 包含在输入波形中 | 按条款去嵌、校准或保留 |
| 结论 | 诊断指标 | 规定限值与 pass/fail 流程 |

IEEE 802.3 的 $N_p,D_p$、滤波器、测试点和限值同样会随 PHY 条款及修订变化。不要把
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
- 必须满足 `pre_cursor_fit + dfe_tap_num < total_cursor_fit`、
  `pre_cursor_ffe < total_cursor_ffe` 和 `total_cursor_fit >= total_cursor_ffe`。
- 增加 FFE tap 并不总会改善结果。过长的无约束逆滤波器可能用很大正负系数追逐噪声。
- 要复现协议条款时，先按目标接口设置 $N_p,D_p$ 和采集滤波器，再谈限值；不要从
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
   给出 $V_{mid}$、$ES_1$、$ES_2$ 与 RLM 公式的公开任务组材料。
3. [IEEE P802.3ck: transmitter SNDR background](https://www.ieee802.org/3/ck/public/adhoc/oct02_19/diminico_3ck_adhoc_100219.pdf)，
   展示 $p_{max}$、$\sigma_e$、$\sigma_n$ 的 SNDR 结构；任务组材料不是标准正文。
4. [OIF Implementation Agreements](https://www.oiforum.com/technical-work/implementation-agreements-ias/)，
   OIF 发布版本索引。
5. [OIF-CEI-05.3 Common Electrical I/O](https://www.oiforum.com/wp-content/uploads/OIF-CEI-05.3.pdf)，
   重点参见 10.3.1.6.4-10.3.1.6.5（矩阵拟合与 FFE）、16.C.1/16.C.3/16.C.4.3
   （Gray mapping、QPRBS13-CEI、RLM）及 24/26/27.3.1.6（CEI-112G XSR/MR/LR）。

文档按 2026-09-05 可公开获取的版本核对。标准条款和限值可能随修订变化。
