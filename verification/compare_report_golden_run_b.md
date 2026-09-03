# MATLAB golden vs Python comparison

golden: verification/golden_run_b.json
config: {'filetype': 'lab_txt', 'filename': 'data/tx_nrz_prbs7_lab.txt', 'osr': 128, 'symbol_rate': 53125000000.0, 'modulation': 'NRZ', 'prbs_pattern': 'PRBS7', 'pattern_length': 127, 'repeat_pattern_num': 1, 'gray_coding': 'on', 'pre_cursor_fit': 2, 'total_cursor_fit': 8, 'pre_cursor_ffe': 2, 'total_cursor_ffe': 4, 'dfe_tap_num': 1, 'shift_vec': (-2, -1, 1, 2)}

| item | kind | result | py | golden |
|---|---|---|---|---|
| osr | scalar | PASS | 128.0 | 128.0 |
| symbol_rate | scalar | PASS | 53125000000.0 | 53125000000.0 |
| slice_target | scalar | PASS | 1.0 | 1.0 |
| slice_levels | vector | PASS | 0.0 | max|ref|=2 |
| fit_results.vf | scalar | PASS | 1.1287020235593412 | 1.1287020235593386 |
| fit_results.pmax | scalar | PASS | 1.000675841316118 | 1.000675841316117 |
| fit_results.pulsePeakRatio | scalar | PASS | 0.886572204558033 | 0.8865722045580341 |
| fit_results.eRms | scalar | PASS | 0.004898354358233831 | 0.004898354358231517 |
| fit_results.eRmsRatio | scalar | PASS | 0.004434075420455954 | 0.004434075420453575 |
| fit_results.SNDRold | scalar | PASS | 46.18358146483477 | 46.18358146483941 |
| fit_results.SNDR | scalar | PASS | 46.018220709541055 | 46.01822070954572 |
| fit_results.SNDRold_peak | scalar | PASS | 46.37144699070342 | 46.371446990707526 |
| fit_results.SNR_ISI | scalar | PASS | nan | nan |
| fit_results.nyquist_loss | scalar | PASS | 3.3284512619349744 | 3.328451261935006 |
| fit_results.nyquist_loss_inner | scalar | PASS | 3.334352686146313 | 3.3343526861463295 |
| fit_results.alignment_shift | scalar | PASS | 0.0 | 0.0 |
| fit_results.firNum | vector | PASS | 8.613141818076864e-16 | max|ref|=0.998965 |
| fit_results.firNumNorm | vector | PASS | 9.39631204580881e-16 | max|ref|=1.21109 |
| fit_results.firNumDFE | vector | PASS | 4.392273030026322e-16 | max|ref|=0.999961 |
| fit_results.firNumDFENorm | vector | PASS | 7.774734744470428e-16 | max|ref|=0.999592 |
| fit_results.DFEtapWeight | vector | PASS | 5.246029830599334e-15 | max|ref|=0.179886 |
| fit_results.pSampled | vector | PASS | 1.5541701370562834e-15 | max|ref|=1.00009 |
| fit_results.xp | vector | PASS | 9.43689570931383e-16 | max|ref|=1 |
| fit_results.w | vector | PASS | 4.392273030026322e-16 | max|ref|=0.999961 |
| fit_results.timebase | vector | PASS | 1.7199205495843283e-16 | max|ref|=1.50294e-10 |
| fit_results.timebaseSampled | vector | PASS | 1.9617843768696243e-16 | max|ref|=1.31765e-10 |
| fit_results.p | vector | PASS | 6.299588811428327e-13 | max|ref|=1.00068 |
| fit_results.e | vector | PASS | 1.6270637168388864e-10 | max|ref|=0.139477 |
| fit_results.l | vector | PASS | 1.6035247209768166e-12 | max|ref|=1.31258 |
| fit_results.P3 | vector | PASS | 8.603441830132997e-16 | max|ref|=1.00009 |
| sndr_const.ffe.sndr | scalar | PASS | 17.76287051784733 | 17.76287051784727 |
| sndr_const.ffe.raw_sndr_results | vector | PASS | 9.302365461426378e-13 | max|ref|=17.7629 |
| sndr_const.ffe.rlm_results.V3 | scalar | PASS | 0.9881085307911053 | 0.9881085307911072 |
| sndr_const.ffe.rlm_results.V2 | scalar | PASS | nan | nan |
| sndr_const.ffe.rlm_results.V1 | scalar | PASS | -0.010704127835042892 | -0.01070412783504294 |
| sndr_const.ffe.rlm_results.V0 | scalar | PASS | -1.0117375025074118 | -1.0117375025074133 |
| sndr_const.ffe.rlm_results.RLMbj | scalar | PASS | 1.5016656652631588 | 1.5016656652631584 |
| sndr_const.ffe.rlm_results.swingScale | scalar | PASS | nan | nan |
| sndr_const.ffe.rlm_results.RLMbs | scalar | PASS | -0.003331330526317438 | -0.0033313305263167866 |
| sndr_const.ffe.constellation_eq | vector | PASS | 1.577352144999194e-13 | max|ref|=1.44853 |
| sndr_const.ffe.constellation_uneq | vector | PASS | 1.4161740845609483e-13 | max|ref|=1.32411 |
| sndr_const.ffe.re_interleaved_signal | vector | PASS | 2.0866776242386142e-11 | max|ref|=1.45818 |
| sndr_const.ffe_and_dfe.sndr | scalar | PASS | 20.06339400207386 | 20.063394002073814 |
| sndr_const.ffe_and_dfe.raw_sndr_results | vector | PASS | 1.602523421003505e-12 | max|ref|=20.0634 |
| sndr_const.ffe_and_dfe.rlm_results.V3 | scalar | PASS | 0.9870640617170687 | 0.9870640617170692 |
| sndr_const.ffe_and_dfe.rlm_results.V2 | scalar | PASS | 0.16622211835675996 | 0.16622211835676104 |
| sndr_const.ffe_and_dfe.rlm_results.V1 | scalar | PASS | nan | nan |
| sndr_const.ffe_and_dfe.rlm_results.V0 | scalar | PASS | -1.0149615590038787 | -1.0149615590038787 |
| sndr_const.ffe_and_dfe.rlm_results.RLMbj | scalar | PASS | 1.2300171409365626 | 1.230017140936561 |
| sndr_const.ffe_and_dfe.rlm_results.swingScale | scalar | PASS | nan | nan |
| sndr_const.ffe_and_dfe.rlm_results.RLMbs | scalar | PASS | 0.5399657181268753 | 0.5399657181268778 |
| sndr_const.ffe_and_dfe.constellation_eq | vector | PASS | 1.3885034365769288e-13 | max|ref|=1.32331 |
| sndr_const.ffe_and_dfe.constellation_uneq | vector | PASS | 1.3877237812930426e-13 | max|ref|=1.32405 |
| sndr_const.ffe_and_dfe.re_interleaved_signal | vector | PASS | 1.8554503145362496e-11 | max|ref|=1.32887 |
| tf_calc.tf | vector | PASS | 1.158637960064702e-12 | max|ref|=119.462 |
| tf_calc.freq | vector | PASS | 0.0 | max|ref|=6.8e+12 |
| tf_calc.nyquist_loss | scalar | PASS | -2.390165475542671 | -2.3901654755426724 |
| tf_calc.idx_3dB | vector | PASS | 0.0 | max|ref|=5 |
| tf_calc.bw_3dB | vector | PASS | 1.4951863050061652e-15 | max|ref|=3.06158e+10 |
| eye.uneq.x_opening | scalar | PASS | 0.996078431372549 | 0.996078431372549 |
| eye.uneq.min_y | scalar | PASS | 1.3519071118370283 | 1.3519071118370283 |
| eye.uneq.max_y | scalar | PASS | 2.639773610497373 | 2.639773610497373 |
| eye.uneq.ratio | scalar | PASS | 1.9526294280014087 | 1.9526294280014087 |
| eye.eq.x_opening | scalar | PASS | 0.996078431372549 | 0.996078431372549 |
| eye.eq.min_y | scalar | PASS | 1.9319165393546363 | 1.9319165393546414 |
| eye.eq.max_y | scalar | PASS | 2.907774321832341 | 2.90777432183234 |
| eye.eq.ratio | scalar | PASS | 1.5051241927892463 | 1.5051241927892418 |
| stream_input_interp | vector | PASS | 1.8559116392339764e-11 | max|ref|=1.32909 |
| stream_decision_interp | vector | PASS | 0.0 | max|ref|=1 |
| stream_decision_upsampled | vector | PASS | 0.0 | max|ref|=1 |
| stream_input | vector | PASS | 1.8559116392339764e-11 | max|ref|=1.32909 |
| stream_decision | vector | PASS | 0.0 | max|ref|=1 |

## Result: ALL PASS