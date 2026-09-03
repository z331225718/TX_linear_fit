# TX_linear_fit：MATLAB → Python 完整复刻计划

## 0. 目标与验收

把 matlab_src/ 下 TX 线性拟合/均衡工具用 Python 脚本完整复刻（numpy + scipy + matplotlib，
“脚本项目”风格，不做重工程化封装）。同一份 waveform 输入 + 同一组参数时：
- 核心数值输出一致：pulse 拟合、FFE/DFE 抽头、SNDR/RLM、TF、眼图指标；
- 数据文件一致：results/*.png 命名、txcross.csv / txhist.csv；
- 图形与 MATLAB 输出尽可能一致（跨渲染器不可能逐像素保证，见 §6、§9）。

## 1. 源文件清单与角色映射

| MATLAB | 作用 | Python 复刻 |
|---|---|---|
| tb_run.m / lab_tx_linear_fit_f.m | 顶层流程、参数、8 张图 + summary | run_tx_linear_fit.py（argparse 入口，复刻全部 options 与默认值） |
| process_input_f.m | 读 scope 文本（time,voltage）或 csv（仅电压），等 'Data, ' 行后逐行解析 | process_input.py |
| func/func_prbs.m | PRBS 序列（含 2^23 截断、反馈 b 的迭代细节） | pattern.py: prbs() |
| func/func_gen_data_pattern.m | 位流→PAM4/NRZ 电平、重复到 pattern_length | pattern.py: gen_data_pattern() |
| pulse_response_tool_c.m (911 行 classdef) | 核心类：裁剪、插值、同步、线性拟合、TF、星座 SNDR、眼图、各 plot_* | pulse_response_tool.py（同构类/函数集合） |
| fit_pulse_response_f.m | 最小二乘脉冲拟合 + FFE/DFE 抽头 + SNDR/SNR_ISI/Nyquist | fit_pulse_response.py |
| func/calcRLM.m | RLM_bj / RLM_bs | calc_rlm.py |
| calc_eye_info_f.m | 眼宽/眼高/交叉统计，写 txcross.csv、txhist.csv | eye_info.py |
| func/func_eyediag.m | 持久化眼图（分块线性插值 + hist 计数 + 固定 256 色映射） | eye_persistence.py |
| plot_aggregate_f.m / load_adjust_fig_v2.m | 2×4 拼图 + 间距/长宽比摆放 | summary_plot.py |

主线实际调用链（lab_tx_linear_fit_f）：
process_input → 去均值化(取负、时间归零) → interp1 spline 到 osr 网格 → repeat
→ config_input_stream_f（裁剪到首超阈值点前 osr 个样本；再做一次“单位网格”spline 插值）
→ config_decision_stream_f（PRBS 生成/同步/xcorr 对齐/翻转极性/降采样判决）
→ config_linear_fit_pulse_f → apply_linear_fit_pulse_f（fit + 移位搜索对齐）
→ plot_linear_fit_error_f → calc_constellation_sndr_f → calc_tf_from_linear_fit_data_f
→ 其余 plot_*（各自 exportgraphics 到 results/*.png）→ plot_aggregate_f 拼图。
config_adc_noise_stream_f / plot_adc_noise_spectrum_f 不在主线内，仍一并对齐（低优先级）。

## 2. 参数与默认值（复刻 arguments 块）

osr=128, repeat_pattern_num=1, dfe_tap_num=1, shift_vec=[-2 -1 1 2],
summary_plot_filename='tx_summary', eye_ylim=[-0.7 0.7], eye_ytick=-1:0.1:1,
close_plots='no'；symbol_rate/modulation/prbs_pattern/pattern_length/filetype(filename)
为必传。命令行字符串→数值的转换分支（含 eye_ytick 的 ':' 解析）也一并复刻。
flow: time_vec 存在则 time=time-time(0)，网格 0:1/(sr*osr):time(end)，interp1 'spline'
取 -data，之后 repmat(repeat_pattern_num)。time_vec 为空（csv 型）则跳过插值直接 repmat。

## 3. 逐段移植要点与 MATLAB 语义陷阱（保真关键）

1. **列主序**：fit 中 Y=reshape(data,osr,S)、e/l/p 的 reshape 展开全部按列；numpy 必须
   order='F'（p 的排列决定主抽头相位，错序=错误结果）。
2. **xcorr(decisions_up, stream)**（config_decision_stream_f）：默认 'none'，长度
   L1+L2-1、以最长向量为轴构造 lags；实现 matlab_xcorr 并做单测。取 |d| 最大 lag，
   用 circshift(decisions_up, -idx(midx)) 同步；d(midx)<0 则整体翻转极性。该处若存在
   两个相近峰值，浮点差异可能翻 lag → 验证时检查“峰值裕度”，无裕度则 fail closed 报告。
3. **interp1**：'spline'= not-a-knot（scipy.interpolate.CubicSpline 默认一致）；
   'linear' 与 np.interp 一致但默认不外推 → 超出范围产生 NaN，须复刻 NaN 传播；
   '*linear'（func_eyediag 内）按网格内取值，无外推问题。config_input_stream_f 的
   timeBaseUntrim 用 samplePeriod 而 rawTimeBase 用 rawSamplePeriod（数值上相等但保留原写法）。
4. **circshift → np.roll**（方向一致：正 k 向右）。
5. **filter(b,1,x) → scipy.signal.lfilter**；**rms(x)=sqrt(mean(x²))**。
6. **freqz(p)**：MATLAB 默认 512 点 [0,π)；用 scipy.signal.freqz(b,[1],worN=512) 对齐
   （nyquist_loss、nyquist_loss_inner 依赖它）。
7. **hist(x,hvec)（func_eyediag）**：hvec 是 bin 中心且间距 0.001 → 按 histc 规则
   [edge_k, edge_{k+1}) 计数（内部 4 段 Nsize/OSRup 处理、ceil(60*max)/60 取整都照搬）。
8. **fit_pulse_response_f**：逐行对齐，包括
   - P = Y*X'*inv(X*X')（保持同一矩阵乘法次序；用 numpy 复刻 inv 求解）；
   - 主抽头判定 above=p>pmax/1.01 取**第一个** true（max(above) 返回首个最大）；
   - initialSample=rem(tx,osr)+1；pSampled=p[initialSample::osr]；
   - eRms 在 10%~90% 区间截取；SNR_ISI 需 pmax 索引 +11 ≤ 长度，否则 NaN + fprintf 警告；
   - P3 列构造中 1 基索引与置零规则（i-T_DW 相关），DFE 版 xp 注入
     pSampled(pmax+zz)/pSampled(pmax)，firNumDFENorm 除以 sum(abs(w))；
   - fit 输出 16+ 个字段全部保留（时间基归零）。
9. **apply_linear_fit_pulse_f**：先默认 fit，取 firNum 最大处索引 I；I≠t_dw+1 时依次试
   shift_vec 各移位（circshift 判决），命中即停并记录 alignment_shift；都不中则 error
   （Python 复刻同样抛错）。
10. **constellation_sndr_helper_f**：逐相位(zz=1..osr)抽取 vertical=stream[zz-1::osr]，
    filter 后去均值；slice 判决电平 ±2/3(±2·slice_target)、±1/3(PAM4 默认 target=1/3)；
    dfe_vec=Σ circshift(decisions,d)·w_d；SNDR=20log10(rms(dec)/rms(滤波后-判决))，
    取 osr 个相位里最大值并记录 bestphase、winning 序列与 filterConstellationArray
    （列=相位，最后整列按列主序平铺为 re_interleaved_signal —— 这就是
    “Equalized Eye Diagram”数据源）。raw_sndr_results/sndr/rlm 一并返回。
    NRZ 时 slice_target=1、slice_levels=[2 0 -2]（text/绘图用）。
11. **calc_tf_from_linear_fit_data_f**：理想梯形脉冲(线性外推插值) → tf=|FFT(p)|/|FFT(ideal)|
    先归一化，再用 >1e-6 的 fft_pulse 掩膜做线性插值平滑、二次归一化；nyquist_loss 在
    sr/2 插值；bw_3dB 为 20log10(tf) 首次 < -3 处线性插值（找不到时与 MATLAB 相同的空值行为）。
12. **calc_eye_info_f**：窗口化到 settle_ui 之后，num_ui=floor(L/osr)-5，逐行
    x(k·osr .. (k+2)osr-1)；零交叉直方图找最长连续“无交叉”区段求眼宽（注意 t1/t2 更新
    只在退出零段时发生、平局保留首个最大段的逻辑，以及全零退化分支 t1=中/t2=中+1）；
    eye_mid_index=floor((t1+t2)/2) 处 2·min/max|…| 求眼高与比值；同法写 txcross.csv /
    txhist.csv（2 次眼图调用会覆盖 → 最终内容对应 Equalized 眼）。绘图偏移
    eyediag_offset 的环绕取法照搬。
13. **func_eyediag**：分块长度 Nsize=osr_act·floor(…)、OSRup=1/round(320/OSR)，
    hist 累积、image() 用 256 色 map（白→绿→蓝→品红→红→橙→黄→白）和
    ceil(N/max(N)·256·sat) 计数灰度；Python 用 imshow+自制 colormap，坐标
    x=Tsym·(-0.5+[0..Nc-1]/(Nc-1))、YDir normal。
14. **calcRLM**：V3/V2/V1/V0 分层均值（严格 >、区间取法照抄）→ RLMbj、swingScale、
    Vmid、ES1/ES2、RLMbs=min([3ES1 3ES2 2-3ES1 2-3ES2])。
15. **PRBS**：func_prbs 的 lim=min(2^n-2, n+1) 且 2^23 封顶；每拍 b 链式 xor、右移、
    c(k+1,:)=s、取第 n 列作为输出（首行为初始 seed）；gen_data_pattern 的
    “data=[prbs 0]; data(1:end-1)” 与固定长度重复/补零逻辑照搬；'fixed' seed_type
    不做随机循环移位。

## 4. 图形层复刻（8 张 png + 拼图）

每张图对应 MATLAB plot_* 的 figure 尺寸、子图、线型/颜色、grid、字号 14、图例文本
（含 %% 数字串：sprintf %.1f/%.2f/%3.3g 等格式逐一复刻）、标题与坐标轴范围默认逻辑
（未传 xlim/ylim 时的默认分支，包括 plot_eye_diagram 里引用外部变量的死代码分支 ——
    主流程恒传 ylim，因此按 MATLAB 实际执行路径即“传了 ylim”处理）。
文件名与 MATLAB 导出名一致：linear_fit_error.png / constellation_hist.png /
eye_Unequalized.png / eye_Equalized.png / ffe_coeff.png / ffe_resp.png / tf.png /
linear_fit_pulse.png，最后 plot_aggregate_f 拼成 tx_summary.png（2 行 4 列、xsize=400、
height=round(2.23·max aspect 高)、500 dpi exportgraphics 的近似等价物）。

## 5. 一致性验证（验收门禁）

前提问题见 §9（需要参考波形 + MATLAB 参考输出）。
- **V1 单元保真**：对每个纯函数（prbs/gen_data_pattern/process_input/fit/calcRLM/
  calc_eye_info/eye_persistence 计数层）以固定合成输入（确定性、无 RNG）比对 MATLAB
  golden（若用户能提供 .mat/.csv golden）或与独立手算/代数恒等式（如 L=P·X、残差定义）
  交叉验证。
- **V2 端到端**：同一份 waveform + 同一参数分别过 MATLAB 与 Python，比较：
  数值字段（逐项 max|Δ|、相对误差表，写入 verification/compare_report.md）、
  txcross.csv/txhist.csv 逐元素、8 png + tx_summary.png 尺寸/文件存在性；
  PNG 以像素差(容差)辅助评估但不作为硬门槛。
- **V3 数值断言清单**：firNum/firNumNorm/firNumDFE*/DFEtapWeight/vf/pmax/
  pulsePeakRatio/eRms/eRmsRatio/SNDRold/SNDR/SNDRold_peak/SNR_ISI/nyquist_loss(_inner)/
  timebaseSampled、tf/freq/bw_3dB/nyquist_loss、sndr(逐相位)/bestphase/RLM 两组、
  eye_x_opening/min/max_eye_y_opening/ratio、alignment_shift。
  判定阈值默认：指标 ≤1e-9 相对误差（含全部 p/e/l 向量逐元素）。
- MATLAB 在本机可用时：写 capture_golden.m 一键导出 golden；不可用时向用户提供
  golden 采集脚本 + 离线比对工具 verify_against_golden.py。

## 6. 已知边界（fail-closed 项）

1. MATLAB/Matplotlib 渲染管线不同，PNG 无法逐像素一致 —— 数值与数据文件是硬指标，
   图形是软指标；若用户坚持逐像素，先明确不可行并给出替代验收（见问题 3）。
2. 浮点运算次序差异（xcorr/FFT/LAPACK）一般在 1e-15~1e-12，但 argmax/符号判断存在
   平局敏感性 → 比较报告中输出“关键选择裕度”，不达标即报错而不是悄悄继续。
3. 仓库快照本身有不一致（见 §7），按“作者意图”的最小解释实现，并单列偏差清单。
4. 无真实 waveform 与 MATLAB 参考前，V2 无法执行；先以“仿真级确定性输入”跑通并交付
   全部比对工具，等用户提供真数据后一键复验。

## 7. 快照代码问题清单（实现时按意图修正并记录）

- lab_tx_linear_fit_f.m L86 把 filetype 当位置参数传给 process_input_f（其形参是
  lab_txt_data_filename / lab_csv_data_filename）→ Python 按 filetype 选择分支。
- plot_aggregate_f.m L50 调用 load_adjust_fig_v2_f（不存在）。MATLAB 按文件名派发函数：
  load_adjust_fig_v2.m 的**可调用名是文件名 load_adjust_fig_v2**（其主函数内部名 load_adjust_fig
  不一致仅触发编辑器提示，不影响按文件名调用）。意图修正 = 把调用改为 load_adjust_fig_v2(...)
  （6 参数与定义一一对应）；MATLAB golden 副本同步改名。Python 直接实现该摆放逻辑。
- process_input_f.m L80 引用未定义变量 nosie_data（noise 分支）→ 该分支不在主线，实现
  为同样不可用/报错即可，并在 README 注明。
- tb_run.m 只传 filetype，缺 symbol_rate/modulation 等必填参数（MATLAB 会运行时报错）→
  Python 入口对必填参数做明确校验，错误信息可读。
- calc_eye_info_f 会在当前目录写 txcross.csv / txhist.csv（两次眼图调用互相覆盖）→
  保留相同行为与最终内容（Equalized 那次），写入位置同 cwd 的 results/ 输出规则。
- func_eyediag 中 exist('intitle','var') 恒假（无 intitle 变量）→ 不画 title，照搬。

## 8. 目录结构

    TX_linear_fit/
      matlab_src/                 # 只读参考，不改
      python/
        run_tx_linear_fit.py      # 入口（≈lab_tx_linear_fit_f）
        process_input.py  pattern.py  pulse_response_tool.py
        fit_pulse_response.py  calc_rlm.py  eye_info.py
        eye_persistence.py  summary_plot.py
        requirements.txt          # numpy scipy matplotlib
        tests/                    # V1 单元保真 + V2 端到端脚本
      verification/               # golden、对比报告、证据（输入哈希/配置/平台）
      PLAN.md  README.md

## 9. 实施顺序

S1 参数冻结：确认问题 1-4 的答案（波形来源、MATLAB 可用性、等价口径、意图修正许可）。
S2 pattern/prbs/process_input + V1 测试。
S3 fit_pulse_response + 核心数值（fit/对齐/星座/RLM/TF/眼指标）+ V1 测试。
S4 图形层（8 图 + 拼图 + csv 输出）。
S5 端到端比对工具 + 报告（若有 MATLAB/真实波形立即跑 V2）。
S6 README + 偏差清单 + 交付总结。

## 10. 待确认问题（见会话提问）

1) 真实 waveform 文件与完整参数能否提供/何时提供？
2) 本机是否有 MATLAB 可用于产出 golden 参考输出？
3) “输出一模一样”的验收口径（数值硬指标+图形近似 vs 图形也要求逐像素）？
4) 是否允许按作者意图修正快照里的接线 bug（推荐），还是要求逐字忠实复刻？
