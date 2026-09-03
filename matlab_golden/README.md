# matlab_golden — 意图修正副本 + 采集脚本

与 matlab_src/ 的差异仅 4 处（另加一个返回参数），全部在文件内以
GOLDEN FIX 注释标出：

| 文件 | 修正 |
|---|---|
| lab_tx_linear_fit_f.m | process_input_f 按 filetype 分派；末尾返回 results（prt） |
| plot_aggregate_f.m | L50 调用名改为 load_adjust_fig_v2 |
| load_adjust_fig_v2.m | 函数名与文件名一致 |
| pulse_response_tool_c.m | 眼图导出名固定 eye_Unequalized/eye_Equalized.png |

## 运行（在仓库根目录）

    matlab -batch "capture_golden"

或带路径：

    matlab -batch "cd('C:/Users/z3312/code/TX_linear_fit'); capture_golden"

## 输出

- results/*.png + tx_summary.png（与原版一致的 9 张图）
- verification/golden_run.json：全量数值（fit_results/sndr/rlm/tf/eye 指标、
  stream 中间量、pattern golden、process_input 解析结果）
- 仓库根目录 txcross.csv / txhist.csv（calc_eye_info_f 副作用，最后一版 = 均衡眼）

capture_golden.m 在函数内 addpath(matlab_golden) 优先于 matlab_src，因此
修正副本覆盖原文件而不改动 matlab_src/。
