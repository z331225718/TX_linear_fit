# MATLAB golden vs Python comparison

golden: verification/golden_run.json
config: {'filetype': 'lab_txt', 'filename': 'data/tx_pam4_prbs13_lab.txt', 'osr': 32, 'symbol_rate': 32000000000.0, 'modulation': 'PAM4', 'prbs_pattern': 'PRBS13', 'pattern_length': 8191, 'repeat_pattern_num': 1, 'gray_coding': 'on', 'pre_cursor_fit': 2, 'total_cursor_fit': 8, 'pre_cursor_ffe': 2, 'total_cursor_ffe': 4, 'dfe_tap_num': 1, 'shift_vec': (-2, -1, 1, 2)}

| item | kind | result | py | golden |
|---|---|---|---|---|
| osr | scalar | PASS | 32.0 | 32.0 |
| symbol_rate | scalar | PASS | 32000000000.0 | 32000000000.0 |
| slice_target | scalar | PASS | 0.3333333333333333 | 0.3333333333333333 |
| slice_levels | vector | PASS | 0.0 | max|ref|=0.666667 |
| fit_results.vf | scalar | PASS | 1.1299568199518006 | 1.129956819951635 |
| fit_results.pmax | scalar | PASS | 1.0001665743118 | 1.0001665743116623 |
| fit_results.pulsePeakRatio | scalar | PASS | 0.8851369863447198 | 0.8851369863447277 |
| fit_results.eRms | scalar | PASS | 0.007992372753120083 | 0.007992372752926582 |
| fit_results.eRmsRatio | scalar | PASS | 0.007072594815784162 | 0.007072594815616709 |
| fit_results.SNDRold | scalar | PASS | 39.57333363623026 | 39.57333363643168 |
| fit_results.SNDR | scalar | PASS | 41.94863420413175 | 41.94863420433748 |
| fit_results.SNDRold_peak | scalar | PASS | 39.57362107599936 | 39.5736210762096 |
| fit_results.SNR_ISI | scalar | PASS | nan | nan |
| fit_results.nyquist_loss | scalar | PASS | 3.328178688246223 | 3.328178688246391 |
| fit_results.nyquist_loss_inner | scalar | PASS | 3.3280130447484684 | 3.3280130447486704 |
| fit_results.alignment_shift | scalar | PASS | 0.0 | 0.0 |
| fit_results.firNum | vector | PASS | 1.4016689313584025e-13 | max|ref|=0.998803 |
| fit_results.firNumNorm | vector | PASS | 6.877929812829654e-15 | max|ref|=1.21081 |
| fit_results.firNumDFE | vector | PASS | 1.3957409125188314e-13 | max|ref|=0.999863 |
| fit_results.firNumDFENorm | vector | PASS | 9.881841301071946e-15 | max|ref|=0.999913 |
| fit_results.DFEtapWeight | vector | PASS | 1.4960547904263897e-14 | max|ref|=0.179959 |
| fit_results.pSampled | vector | PASS | 1.3876061970445632e-13 | max|ref|=1.00012 |
| fit_results.xp | vector | PASS | 2.6922908347160046e-15 | max|ref|=1 |
| fit_results.w | vector | PASS | 1.3957409125188314e-13 | max|ref|=0.999863 |
| fit_results.timebase | vector | PASS | 2.0842346143068416e-16 | max|ref|=2.48047e-10 |
| fit_results.timebaseSampled | vector | PASS | 1.1816865893614682e-16 | max|ref|=2.1875e-10 |
| fit_results.p | vector | PASS | 2.4047643841154524e-11 | max|ref|=1.00017 |
| fit_results.e | vector | PASS | 1.2997836196160956e-09 | max|ref|=0.144025 |
| fit_results.l | vector | PASS | 4.085176688894531e-11 | max|ref|=1.31059 |
| fit_results.P3 | vector | PASS | 1.3876061970445632e-13 | max|ref|=1.00012 |
| sndr_const.ffe.sndr | scalar | PASS | 17.771180276336388 | 17.771180276336835 |
| sndr_const.ffe.raw_sndr_results | vector | PASS | 7.33565659133459e-12 | max|ref|=17.7712 |
| sndr_const.ffe.rlm_results.V3 | scalar | PASS | 0.9985571152573366 | 0.9985571152574776 |
| sndr_const.ffe.rlm_results.V2 | scalar | PASS | 0.3327155726736546 | 0.33271557267369917 |
| sndr_const.ffe.rlm_results.V1 | scalar | PASS | -0.3329463443702236 | -0.332946344370268 |
| sndr_const.ffe.rlm_results.V0 | scalar | PASS | -0.9991394942659246 | -0.9991394942660666 |
| sndr_const.ffe.rlm_results.RLMbj | scalar | PASS | 0.9996441609860889 | 0.9996441609860808 |
| sndr_const.ffe.rlm_results.swingScale | scalar | PASS | 3.0010678970411635 | 3.001067897041188 |
| sndr_const.ffe.rlm_results.RLMbs | scalar | PASS | 0.9991161419009941 | 0.9991161419009844 |
| sndr_const.ffe.constellation_eq | vector | PASS | 3.5593432385987373e-12 | max|ref|=1.45167 |
| sndr_const.ffe.constellation_uneq | vector | PASS | 3.215937907449085e-12 | max|ref|=1.32905 |
| sndr_const.ffe.re_interleaved_signal | vector | PASS | 1.991558710247582e-10 | max|ref|=1.46827 |
| sndr_const.ffe_and_dfe.sndr | scalar | PASS | 20.095585814602828 | 20.095585814604245 |
| sndr_const.ffe_and_dfe.raw_sndr_results | vector | PASS | 2.542162583147262e-11 | max|ref|=20.0956 |
| sndr_const.ffe_and_dfe.rlm_results.V3 | scalar | PASS | 0.999555226231074 | 0.9995552262312128 |
| sndr_const.ffe_and_dfe.rlm_results.V2 | scalar | PASS | 0.3328812085793827 | 0.3328812085794294 |
| sndr_const.ffe_and_dfe.rlm_results.V1 | scalar | PASS | -0.33352796761695447 | -0.3335279676169972 |
| sndr_const.ffe_and_dfe.rlm_results.V0 | scalar | PASS | -1.0001942103180739 | -1.0001942103182175 |
| sndr_const.ffe_and_dfe.rlm_results.RLMbj | scalar | PASS | 0.9997390133230705 | 0.9997390133230636 |
| sndr_const.ffe_and_dfe.rlm_results.swingScale | scalar | PASS | 3.0007831644262697 | 3.0007831644262906 |
| sndr_const.ffe_and_dfe.rlm_results.RLMbs | scalar | PASS | 0.9997273494359409 | 0.9997273494359469 |
| sndr_const.ffe_and_dfe.constellation_eq | vector | PASS | 3.2231745377116743e-12 | max|ref|=1.32899 |
| sndr_const.ffe_and_dfe.constellation_uneq | vector | PASS | 3.215937907449085e-12 | max|ref|=1.32905 |
| sndr_const.ffe_and_dfe.re_interleaved_signal | vector | PASS | 1.7794128002779164e-10 | max|ref|=1.33894 |
| tf_calc.tf | vector | PASS | 2.6909451238428624e-11 | max|ref|=29.0679 |
| tf_calc.freq | vector | PASS | 0.0 | max|ref|=1.024e+12 |
| tf_calc.nyquist_loss | scalar | PASS | -2.501789592546012 | -2.5017895925466114 |
| tf_calc.idx_3dB | vector | PASS | 0.0 | max|ref|=5 |
| tf_calc.bw_3dB | vector | PASS | 1.487915659213789e-13 | max|ref|=1.78183e+10 |
| eye.uneq.x_opening | scalar | PASS | 0.9841269841269841 | 0.9841269841269841 |
| eye.uneq.min_y | scalar | PASS | 0.029125769895983013 | 0.029125769895983013 |
| eye.uneq.max_y | scalar | PASS | 2.6530308302353247 | 2.6530308302353247 |
| eye.uneq.ratio | scalar | PASS | 91.08877944549123 | 91.08877944549123 |
| eye.eq.x_opening | scalar | PASS | 0.9841269841269841 | 0.9841269841269841 |
| eye.eq.min_y | scalar | PASS | 0.34985339372555063 | 0.34985339372555374 |
| eye.eq.max_y | scalar | PASS | 2.8886623787207064 | 2.888662378720696 |
| eye.eq.ratio | scalar | PASS | 8.256779641208153 | 8.25677964120805 |
| stream_input_interp | vector | PASS | 1.7794213119604483e-10 | max|ref|=1.33907 |
| stream_decision_interp | vector | PASS | 0.0 | max|ref|=1 |
| stream_decision_upsampled | vector | PASS | 0.0 | max|ref|=1 |
| stream_input | vector | PASS | 1.7794213119604483e-10 | max|ref|=1.33907 |
| stream_decision | vector | PASS | 0.0 | max|ref|=1 |
| input.time_vec | vector | PASS | 0.0 | max|ref|=5.11937e-07 |
| input.data_vec | vector | PASS | 0.0 | max|ref|=1.33907 |
| input.time_vec (py parse) | vector | PASS | 0.0 | max|ref|=5.11937e-07 |
| input.data_vec (py parse) | vector | PASS | 0.0 | max|ref|=1.33907 |
| pattern.prbs13_pam4.od | vector | PASS | 0.0 | max|ref|=1 |
| pattern.prbs13_pam4.dd | vector | PASS | 0.0 | max|ref|=1 |
| pattern.prbs13_pam4.tx | vector | PASS | 0.0 | max|ref|=1 |
| pattern.prbs7_pam4.od | vector | PASS | 0.0 | max|ref|=1 |
| pattern.prbs7_pam4.dd | vector | PASS | 0.0 | max|ref|=1 |
| pattern.prbs7_pam4.tx | vector | PASS | 0.0 | max|ref|=1 |
| pattern.prbs7_nrz.od | vector | PASS | 0.0 | max|ref|=1 |
| pattern.prbs7_nrz.dd | vector | PASS | 0.0 | max|ref|=1 |
| pattern.prbs7_nrz.tx | vector | PASS | 0.0 | max|ref|=1 |
| pattern.prbs15_pam4.od | vector | PASS | 0.0 | max|ref|=1 |
| pattern.prbs15_pam4.dd | vector | PASS | 0.0 | max|ref|=1 |
| pattern.prbs15_pam4.tx | vector | PASS | 0.0 | max|ref|=1 |
| pattern.prbs31_nrz.od | vector | PASS | 0.0 | max|ref|=1 |
| pattern.prbs31_nrz.dd | vector | PASS | 0.0 | max|ref|=1 |
| pattern.prbs31_nrz.tx | vector | PASS | 0.0 | max|ref|=1 |
| pattern.prbs13_pam4_gray_off | vector | PASS | 0.0 | max|ref|=1 |

## Result: ALL PASS