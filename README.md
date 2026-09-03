# TX_linear_fit — MATLAB → Python 复刻

把 matlab_src/ 下的 TX 线性拟合/均衡工具完整移植为 Python 脚本项目
（numpy + scipy + matplotlib，脚本风格，无重型工程化封装）。

## 目录

    matlab_src/                 原 MATLAB 源码（只读参考，不改）
    matlab_golden/              意图修正副本 + capture_golden.m（golden 采集）
    python/
      run_tx_linear_fit.py      入口（≈ lab_tx_linear_fit_f）
      process_input.py          lab_txt / lab_csv 解析（process_input_f）
      pattern.py                func_prbs + func_gen_data_pattern 移植
      fit_pulse_response.py     fit_pulse_response_f 移植
      pulse_response_tool.py    pulse_response_tool_c 数值方法移植
      calc_rlm.py               calcRLM 移植
      eye_info.py               calc_eye_info_f 移植（含 txcross.csv/txhist.csv）
      eye_persistence.py        func_eyediag 持久化眼图数值部分
      matlab_compat.py          MATLAB 语义助手（xcorr/interp1/colon/round/freqz）
      plots.py                  8 图 + tx_summary 拼图（风格近似）
      verify_against_golden.py  golden 对比工具
      gen_waveform.py           确定性合成波形生成器
      tests/test_s3.py          单元测试（pattern / process_input）
      requirements.txt
    data/                       合成波形（同一份文件供 MATLAB 与 Python 使用）
    verification/               golden、比对报告、哈希证据
    PLAN.md                     移植计划（含偏差清单与验收口径）

## 运行

    pip install -r python/requirements.txt

    # PAM4 PRBS13（golden 默认配置）
    python python/run_tx_linear_fit.py --filetype lab_txt \
        --filename data/tx_pam4_prbs13_lab.txt --symbol_rate 32e9 \
        --modulation PAM4 --prbs_pattern PRBS13 --pattern_length 8191 \
        --osr 32 --gray_coding on --pre_cursor_fit 2 --total_cursor_fit 8 \
        --pre_cursor_ffe 2 --total_cursor_ffe 4

    # NRZ PRBS7（osr=128 默认采样率路径）
    python python/run_tx_linear_fit.py --filetype lab_txt \
        --filename data/tx_nrz_prbs7_lab.txt --symbol_rate 53.125e9 \
        --modulation NRZ --prbs_pattern PRBS7 --pattern_length 127 --osr 128

输出：终端打印全部指标；results/*.png（8 图 + tx_summary）；目录写下
txcross.csv / txhist.csv（与 MATLAB 相同的副作用）。

## 与 MATLAB golden 的验证流程

1. 生成波形（确定性，无需网络/随机数）：
       python python/gen_waveform.py

2. 运行 MATLAB golden（需要本机 MATLAB；修正副本已就绪）。
   注意：在本 DSH 沙箱环境中 MATLAB 启动会被 USERPROFILE 访问拦截
   （"File system inconsistency"），需把用户目录重定向到工作区：
       $env:USERPROFILE = 'C:/Users/z3312/code/TX_linear_fit/.fake_userprofile'
       $env:APPDATA     = 'C:/Users/z3312/code/TX_linear_fit/.fake_appdata'
       $env:LOCALAPPDATA= 'C:/Users/z3312/code/TX_linear_fit/.fake_localappdata'
       $env:TEMP = $env:TMP = 'C:/Users/z3312/code/TX_linear_fit/.tmp'
       $env:MATLAB_PREFDIR = 'C:/Users/z3312/code/TX_linear_fit/.matlab_prefs'
       matlab -batch "addpath('C:/Users/z3312/code/TX_linear_fit/matlab_golden');
                      cd('C:/Users/z3312/code/TX_linear_fit'); capture_golden"
   普通环境直接运行 matlab -batch "capture_golden" 即可。capture_golden.m
   自动 addpath（注意 addpath 是前插，src/func 先加、golden 最后加），写出
   verification/golden_run.json；capture_golden_b.m 产出 NRZ/osr=128 配置的
   verification/golden_run_b.json。

3. 对比：
       python python/verify_against_golden.py --golden verification/golden_run.json \
           --filename data/tx_pam4_prbs13_lab.txt --symbol_rate 32e9 --modulation PAM4 \
           --prbs_pattern PRBS13 --pattern_length 8191 --osr 32 --gray_coding on \
           --pre_cursor_fit 2 --total_cursor_fit 8 --pre_cursor_ffe 2 --total_cursor_ffe 4
       python python/verify_against_golden.py --golden verification/golden_run_b.json \
           --filename data/tx_nrz_prbs7_lab.txt --symbol_rate 53.125e9 --modulation NRZ \
           --prbs_pattern PRBS7 --pattern_length 127 --osr 128 --gray_coding on

   比对阈值：标量/向量相对误差 ≤ 1e-9（fit_results.e 为残余类向量，容差 1e-8；
   绝对误差 ~2e-10 V，派生量 eRms/eRmsRatio 均 1e-9 内通过）；NaN 位置一致；
   输出 verification/compare_report_<golden>.md 与 compare_summary_<golden>.json。

## 验证结果（MATLAB R2024b golden，本机实测）

| 配置 | 项目数 | 通过 | 说明 |
|---|---|---|---|
| A: PAM4 PRBS13 osr=32 | 92 | 92/92 | pattern/input/全部 fit 字段/星座 SNDR+RLM(ffe & dfe)/TF/眼指标/流中间量 |
| B: NRZ PRBS7 osr=128 | 72 | 72/72 | 同上（NRZ 空带合法 NaN 已按 MATLAB min 忽略 NaN 语义对齐） |

两次 Python 运行 9 张 PNG SHA-256 一致（verification/final_hashes*.txt）。

## 已完成的意图修正（相对 matlab_src 快照，均记录在 matlab_golden/ 差异中）

1. lab_tx_linear_fit_f.m：process_input_f 调用按 filetype 分派（原代码把
   filetype 当位置参数传入，绑定到 lab_txt_data_filename）。
2. plot_aggregate_f.m：调用 load_adjust_fig_v2（按文件名派发；原调用
   load_adjust_fig_v2_f 不存在）；并把形参 input_file_vec 改为
   input_files_vec 与 arguments 块一致（原快照两处均不符，MATLAB 报错）。
3. load_adjust_fig_v2.m：函数名改为与文件名一致。
4. pulse_response_tool_c.m：眼图导出文件名按标题固定为
   eye_Unequalized.png / eye_Equalized.png（原 extractBefore(title,'')
   返回空串，与 merge 列表不一致，原样无法跑通）。
5. lab_tx_linear_fit_f.m：增加 results 输出（供 golden 采集；原签名返回 []）。
6. calc_eye_info_f（快照为截断版，无绘图尾部）只返回 5 个数值输出；
   capture 以 5 输出调用，Python 侧 eye_info 同步只复刻数值部分。

Python 侧相同语义：column-major reshape(order='F')、xcorr pad-to-N 约定、
interp1 线性/spline(not-a-knot)、NaN 外推、freqz(512, w=(0:n-1)*pi/n)、
MATLAB round（半程远离零）、logical 相加提升为 double 计数（numpy bool '+' 
是 OR，已显式 astype 修复——阶段内发现的关键陷阱）。

## 已知边界（fail-closed 项）

- 数值/数据文件是硬指标（目标 ≤1e-9 相对误差）；PNG 为内容级复刻，不承诺
  与 MATLAB 逐像素一致（用户确认：图片风格不限）。
- SNR_ISI 在 T_NP ≤ 11 时恒为 NaN（MATLAB 同逻辑，未做“修复”）。
- process_input no 分支（lab_noise_data_filename）原版引用未定义变量
  nosie_data，属已废弃路径，Python 侧同不可用（raise），README 记录。
- xcorr 峰选择的浮点平局（罕见）可能造成对齐差异——golden 的
  stream_decision_upsampled 全量回灌可检出；目前合成数据峰裕度 >2%。
