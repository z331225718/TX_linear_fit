function capture_golden()
% Capture golden numeric outputs of the (intent-fixed) MATLAB tool for
% Python-side comparison. Run:  matlab -batch "capture_golden"
root = fileparts(fileparts(mfilename('fullpath')));   % repo root = TX_linear_fit
cd(root);
% NOTE: addpath PREPENDS, so add base dirs first and the golden override LAST
addpath(fullfile(root,'matlab_src'));
addpath(fullfile(root,'matlab_src','func'));
addpath(fullfile(root,'matlab_golden'));
mkdir('verification');

fprintf('MATLAB release: %s\n', version('-release'));

cfg.filetype = 'lab_txt';
cfg.filename = fullfile(root,'data','tx_pam4_prbs13_lab.txt');
cfg.osr = 32;
cfg.symbol_rate = 32e9;
cfg.modulation = 'PAM4';
cfg.prbs_pattern = 'PRBS13';
cfg.pattern_length = 8191;
cfg.gray_coding = 'on';
cfg.pre_cursor_fit = 2;
cfg.total_cursor_fit = 8;
cfg.pre_cursor_ffe = 2;
cfg.total_cursor_ffe = 4;

R.config = cfg;
R.cfg_shift_vec = [-2 -1 1 2];

% ---- pattern generation goldens (func_gen_data_pattern, seed 'fixed') ----
pat = struct();
[od,dd,tx] = func_gen_data_pattern('PRBS13','PAM4','fixed',8191,0,0);
pat.prbs13_pam4.od = reshape(od,1,[]); pat.prbs13_pam4.dd = reshape(dd,1,[]); pat.prbs13_pam4.tx = reshape(tx,1,[]);
[od,dd,tx] = func_gen_data_pattern('PRBS7','PAM4','fixed',127,0,0);
pat.prbs7_pam4.od = reshape(od,1,[]); pat.prbs7_pam4.dd = reshape(dd,1,[]); pat.prbs7_pam4.tx = reshape(tx,1,[]);
[od,dd,tx] = func_gen_data_pattern('PRBS7','NRZ','fixed',127,0,0);
pat.prbs7_nrz.od = reshape(od,1,[]); pat.prbs7_nrz.dd = reshape(dd,1,[]); pat.prbs7_nrz.tx = reshape(tx,1,[]);
[od,dd,tx] = func_gen_data_pattern('PRBS15','PAM4','fixed',32767,0,0);
pat.prbs15_pam4.od = reshape(od,1,[]); pat.prbs15_pam4.dd = reshape(dd,1,[]); pat.prbs15_pam4.tx = reshape(tx,1,[]);
[od,dd,tx] = func_gen_data_pattern('PRBS31','NRZ','fixed',1500,0,0);
pat.prbs31_nrz.od = reshape(od,1,[]); pat.prbs31_nrz.dd = reshape(dd,1,[]); pat.prbs31_nrz.tx = reshape(tx,1,[]);
% gray-off remap (the snippet inside config_decision_stream_f)
[~,ddata2,~] = func_gen_data_pattern('PRBS13','PAM4','fixed',8191,0,0);
pam_mapping = [];
for ii = 1:length(ddata2)/2
    if(ddata2(2*ii-1:2*ii)==[0 0]); pam_mapping = [pam_mapping 0];
    elseif (ddata2(2*ii-1:2*ii)==[0 1]); pam_mapping = [pam_mapping 1];
    elseif (ddata2(2*ii-1:2*ii)==[1 0]); pam_mapping = [pam_mapping 2];
    elseif (ddata2(2*ii-1:2*ii)==[1 1]); pam_mapping = [pam_mapping 3]; end
end
pat.prbs13_pam4_gray_off = (pam_mapping*2-3)/3;
R.pattern = pat;

% ---- process_input golden ----
try
    lab_data = process_input_f('lab_txt_data_filename', cfg.filename);
    R.input.time_vec = reshape(lab_data.time_vec,1,[]);
    R.input.data_vec = reshape(lab_data.data_vec,1,[]);
catch e
    error('process_input failed: %s', e.message);
end

% ---- main tool run ----
res = lab_tx_linear_fit_f('filetype',cfg.filetype,'filename',cfg.filename,...
    'osr',cfg.osr,'symbol_rate',cfg.symbol_rate,'modulation',cfg.modulation,...
    'prbs_pattern',cfg.prbs_pattern,'pattern_length',cfg.pattern_length,...
    'gray_coding',cfg.gray_coding,...
    'pre_cursor_fit',cfg.pre_cursor_fit,'total_cursor_fit',cfg.total_cursor_fit,...
    'pre_cursor_ffe',cfg.pre_cursor_ffe,'total_cursor_ffe',cfg.total_cursor_ffe,...
    'dfe_tap_num',1,'shift_vec',[-2 -1 1 2]);
prt = res.prt;

% ---- dump prt state ----
T = struct();
T.osr = prt.osr_input;
T.symbol_rate = prt.symbol_rate_input;
T.modulation = prt.modulation;
T.prbs_pattern = prt.prbs_pattern;
T.slice_levels = reshape(prt.slice_levels,1,[]);
T.slice_target = prt.slice_target;
T.fit_spec = prt.fit_spec;
T.stream_input_interp = reshape(prt.stream_input_interp,1,[]);
T.stream_decision_interp = reshape(prt.stream_decision_interp,1,[]);
T.stream_decision_upsampled = reshape(prt.stream_decision_upsampled,1,[]);
T.stream_input = reshape(prt.stream_input,1,[]);
T.stream_decision = reshape(prt.stream_decision,1,[]);

fr = prt.fit_results;
FR = struct();
FR.firNum = reshape(fr.firNum,1,[]);
FR.firNumNorm = reshape(fr.firNumNorm,1,[]);
FR.firNumDFE = reshape(fr.firNumDFE,1,[]);
FR.firNumDFENorm = reshape(fr.firNumDFENorm,1,[]);
FR.DFEtapWeight = reshape(fr.DFEtapWeight,1,[]);
FR.vf = fr.vf; FR.pmax = fr.pmax; FR.pulsePeakRatio = fr.pulsePeakRatio;
FR.eRms = fr.eRms; FR.eRmsRatio = fr.eRmsRatio;
FR.SNDRold = fr.SNDRold; FR.SNDR = fr.SNDR; FR.SNDRold_peak = fr.SNDRold_peak;
FR.SNR_ISI = fr.SNR_ISI;
FR.e = reshape(fr.e,1,[]); FR.l = reshape(fr.l,1,[]); FR.p = reshape(fr.p,1,[]);
FR.w = reshape(fr.w,1,[]); FR.P3 = fr.P3;
FR.pSampled = reshape(fr.pSampled,1,[]); FR.xp = reshape(fr.xp,1,[]);
FR.nyquist_loss = fr.nyquist_loss; FR.nyquist_loss_inner = fr.nyquist_loss_inner;
FR.timebase = reshape(fr.timebase,1,[]); FR.timebaseSampled = reshape(fr.timebaseSampled,1,[]);
FR.alignment_shift = fr.alignment_shift;
T.fit_results = FR;

tc = prt.tf_calc;
TC = struct();
TC.tf = reshape(tc.tf,1,[]); TC.freq = reshape(tc.freq,1,[]);
TC.nyquist_loss = tc.nyquist_loss;
TC.idx_3dB = tc.idx_3dB; TC.bw_3dB = tc.bw_3dB;
T.tf_calc = TC;

for mode = {'ffe','ffe_and_dfe'}
    m = mode{1};
    sc = prt.sndr_const.(m);
    SC = struct();
    SC.raw_sndr_results = reshape(sc.raw_sndr_results,1,[]);
    SC.sndr = sc.sndr;
    SC.rlm_results = sc.rlm_results;
    SC.constellation_eq = reshape(sc.constellation_eq,1,[]);
    SC.constellation_uneq = reshape(sc.constellation_uneq,1,[]);
    SC.re_interleaved_signal = reshape(sc.re_interleaved_signal,1,[]);
    T.sndr_const.(m) = SC;
end

% ---- eye info metrics (same calls plot_eye_diagram makes) ----
uiSample = prt.osr_input;
samplePeriod = 1/(prt.symbol_rate_input*uiSample);
Tbaud = 2*uiSample*samplePeriod;
eye = struct();
% NOTE: snapshot calc_eye_info_f is truncated (no plot tail) - only 5
% outputs are assigned; requesting 7 errors out.
[eye.xu,eye.minu,eye.maxu,eye.midu,eye.ratu] = calc_eye_info_f(prt.stream_input_interp,uiSample,Tbaud,100,[],[],[]);
[eye.xe,eye.mine,eye.maxe,eye.mide,eye.rate] = calc_eye_info_f(prt.sndr_const.ffe.re_interleaved_signal,uiSample,Tbaud,100,[],[],[]);
eye.xe=eye.xe; eye.mine=eye.mine; eye.maxe=eye.maxe; eye.mide=eye.mide; eye.rate=eye.rate;
T.eye = eye;

R.tool = T;

% ---- dump json ----
outfile = fullfile(root,'verification','golden_run.json');
txt = jsonencode(R);
fid = fopen(outfile,'w');
fprintf(fid,'%s', txt);
fclose(fid);
fprintf('golden written: %s (%d bytes)\n', outfile, numel(txt));
end
