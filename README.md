# TX Linear Fit

用于高速串行发送端波形的时域线性拟合工具。项目提供桌面 GUI 和 CLI，二者共用
同一套数值分析服务，可处理 NRZ/PAM4 与 PRBS7/13/15/31 波形，并生成包含脉冲
响应、FFE/DFE、传递函数、眼图及 RLM 指标的自包含 HTML 报告。

报告支持 `neutral`、`ieee8023` 和 `oif` 语义标签，但不自动加入协议限值，
也不替代正式的一致性测试。

算法、公式推导、协议边界和完整操作说明见
[《TX Linear Fit 技术原理与使用指南》](docs/TECHNICAL_GUIDE.md)。

## 环境

- Python 3.10+
- NumPy
- SciPy
- Matplotlib
- Pillow
- Tk 8.6（GUI，通常随 Python 一起安装）

安装依赖：

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r python_src/requirements.txt
```

## GUI

```powershell
python python_src/gui.py
```

GUI 默认配置：

- `53.125 GBd`
- PAM4 / PRBS13
- 根据输入时间轴自动推断 OSR
- Pulse fit：4 个前游标、32 个总游标
- FFE：4 个前游标、18 个总 tap
- DFE：1 个 tap

选择 PRBS 后，GUI 自动使用对应的完整序列长度；输入解析方式由 `.txt` 或
`.csv` 扩展名自动确定。GUI 提供 PRBS7/13/15；PRBS31 保留给 CLI，并由调用者
指定适合采集长度的 `--pattern_length`。分析完成后默认生成并打开 HTML 报告。

## CLI

带时间轴的 PAM4 波形示例：

```powershell
python python_src/run_tx_linear_fit.py `
  --filetype lab_txt `
  --filename "C:\path\to\waveform.txt" `
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

只有电压值的输入没有时间轴，必须手动提供 OSR：

```powershell
python python_src/run_tx_linear_fit.py `
  --filetype lab_csv `
  --filename "C:\path\to\waveform.csv" `
  --osr 16 `
  --symbol_rate 53.125e9 `
  --modulation PAM4 `
  --prbs_pattern PRBS13 `
  --pattern_length 8191 `
  --pre_cursor_fit 4 `
  --total_cursor_fit 32 `
  --pre_cursor_ffe 4 `
  --total_cursor_ffe 18 `
  --output-dir outputs\run
```

常用选项：

| 选项 | 说明 |
|---|---|
| `--osr N` | 手动指定 samples/UI；有可靠时间轴时可省略 |
| `--profile neutral\|ieee8023\|oif` | 报告语义标签，默认 `neutral` |
| `--plots 0` | 不生成 PNG 图 |
| `--no-report` | 不生成 HTML 报告 |
| `--no-open` | 生成报告但不自动打开浏览器 |
| `--report PATH` | 额外指定 HTML 报告路径 |

完整参数：

```powershell
python python_src/run_tx_linear_fit.py --help
```

## 输入格式

`lab_txt` 用于带时间轴的数据。在任意头信息之后需要包含一行精确的
`Data, `，后续每行格式为：

```text
time,voltage
```

`lab_csv` 用于只有电压值的数据，同样从 `Data, ` 后开始读取：

```text
voltage
```

带时间轴时，程序根据采样间隔与符号率选择最接近实际采样网格的整数 OSR，
并检查缺失采样和时间轴歧义；无法可靠推断时会要求手动指定。

## 输出

每次运行的产物都写入 `--output-dir`：

- `tx_linear_fit_report.html`：自包含 HTML 报告
- `results/*.png`：脉冲响应、拟合误差、FFE、传递函数和眼图
- `txcross.csv`、`txhist.csv`：眼图统计中间结果

运行数据、报告和图片默认不纳入 Git。

## 指标说明

- `SNDR · Fit` 是线性拟合残差得到的主 SNDR 指标。
- FFE 与 FFE+DFE 的 constellation SNDR 仅作为 CLI 诊断，不在报告中展示。
- 眼宽采用 crossing phase 的中央 99% 区间，同时给出 UI 和 ps。
- `RLM · Min Adjacent Spacing` 与 `RLM · IEEE 802.3bs` 使用不同定义，报告会明确区分。
- 传递函数由拟合脉冲推导，仅用于诊断，不能代替基于 S 参数的协议插损测量。

## 测试

测试不依赖仓库内的示波器数据或生成结果：

```powershell
python -m pytest python_src/tests -q
```

## 代码结构

```text
python_src/
  gui.py                    桌面 GUI
  run_tx_linear_fit.py      CLI 入口
  application.py            GUI/CLI 共用分析与产物服务
  pulse_response_tool.py    分析流程
  fit_pulse_response.py     脉冲响应拟合
  pattern.py                PRBS 与 NRZ/PAM4 码型
  process_input.py          示波器文本解析
  eye_info.py               眼图与眼宽指标
  eye_persistence.py        眼图持久化统计
  calc_rlm.py               RLM 计算
  plots.py                  绘图
  report.py                 HTML 报告
  requirements.txt          Python 依赖
  tests/                    自包含回归测试
```
