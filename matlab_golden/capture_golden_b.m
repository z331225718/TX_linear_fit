function capture_golden_b()
% Second golden config: NRZ PRBS7, osr=128 (default oversampling path).
root = fileparts(fileparts(mfilename('fullpath')));
cd(root);
addpath(fullfile(root,'matlab_src'));
addpath(fullfile(root,'matlab_src','func'));
addpath(fullfile(root,'matlab_golden'));
mkdir('verification');

cfg.filetype = 'lab_txt';
cfg.filename = fullfile(root,'data','tx_nrz_prbs7_lab.txt');
cfg.osr = 128;
cfg.symbol_rate = 53.125e9;
cfg.modulation = 'NRZ';
cfg.prbs_pattern = 'PRBS7';
cfg.pattern_length = 127;
cfg.gray_coding = 'on';
cfg.pre_cursor_fit = 2;
cfg.total_cursor_fit = 8;
cfg.pre_cursor_ffe = 2;
cfg.total_cursor_ffe = 4;

res = lab_tx_linear_fit_f('filetype',cfg.filetype,'filename',cfg.filename,...
    'osr',cfg.osr,'symbol_rate',cfg.symbol_rate,'modulation',cfg.modulation,...
    'prbs_pattern',cfg.prbs_pattern,'pattern_length',cfg.pattern_length,...
    'gray_coding',cfg.gray_coding,...
    'pre_cursor_fit',cfg.pre_cursor_fit,'total_cursor_fit',cfg.total_cursor_fit,...
    'pre_cursor_ffe',cfg.pre_cursor_ffe,'total_cursor_ffe',cfg.total_cursor_ffe,...
    'dfe_tap_num',1,'shift_vec',[-2 -1 1 2]);
prt = res.prt;

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
for fld = {'firNum','firNumNorm','firNumDFE','firNumDFENorm','DFEtapWeight', ...
           'vf','pmax','pulsePeakRatio','eRms','eRmsRatio','SNDRold','SNDR', ...
           'SNDRold_peak','SNR_ISI','e','l','p','w','pSampled','xp', ...
           'nyquist_loss','nyquist_loss_inner','timebase','timebaseSampled', ...
           'alignment_shift'}
    f = fld{1};
    if isnumeric(fr.(f))
        FR.(f) = reshape(fr.(f),1,[]);
    else
        FR.(f) = fr.(f);
    end
end
FR.P3 = fr.P3;   % keep matrix layout identical to capture_golden (A)
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

uiSample = prt.osr_input;
samplePeriod = 1/(prt.symbol_rate_input*uiSample);
Tbaud = 2*uiSample*samplePeriod;
eye = struct();
[eye.xu,eye.minu,eye.maxu,eye.midu,eye.ratu] = calc_eye_info_f(prt.stream_input_interp,uiSample,Tbaud,100,[],[],[]);
[eye.xe,eye.mine,eye.maxe,eye.mide,eye.rate] = calc_eye_info_f(prt.sndr_const.ffe.re_interleaved_signal,uiSample,Tbaud,100,[],[],[]);

T.eye = eye;
R.config = cfg;
R.tool = T;

outfile = fullfile(root,'verification','golden_run_b.json');
txt = jsonencode(R);
fid = fopen(outfile,'w');
fprintf(fid,'%s', txt);
fclose(fid);
fprintf('golden B written: %s (%d bytes)\n', outfile, numel(txt));
end
