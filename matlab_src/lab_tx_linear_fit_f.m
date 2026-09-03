function [] = lab_tx_linear_fit_f(options)
arguments
    options.filetype %can read txt files(With time/voltage) or csv file with only voltage saved
    options.filename %name of the file
    options.osr=128 %oversampling rate
    options.symbol_rate
    options.modulation
    options.prbs_pattern
    options.pattern_length
    options.repeat_pattern_num=1
    options.gray_coding
    options.pre_cursor_fit
    options.total_cursor_fit
    options.pre_cursor_ffe
    options.total_cursor_ffe
    options.dfe_tap_num=1
    options.shift_vec = [-2 -1 1 2];
    options.summary_plot_filename = 'tx_summary'
    options.eye_ylim = [-0.7 0.7]
    options.eye_ytick = -1:0.1:1;
    options.close_plots='no';
end

%=============================================================================
% Args from command line are interpreted as String types converted to double
%=============================================================================
if(ischar(options.osr))
    options.osr = str2double(options.osr);
end
if(ischar(options.symbol_rate))
    options.symbol_rate = str2double(options.symbol_rate);
end
if(ischar(options.pattern_length))
    options.pattern_length = str2double(options.pattern_length);
end
if(ischar(options.repeat_pattern_num))
    options.repeat_pattern_num = str2double(options.repeat_pattern_num);
end
if(ischar(options.pre_cursor_fit))
    options.pre_cursor_fit = str2double(options.pre_cursor_fit);
end
if(ischar(options.total_cursor_fit))
    options.total_cursor_fit = str2double(options.total_cursor_fit);
end
if(ischar(options.pre_cursor_ffe))
    options.pre_cursor_ffe = str2double(options.pre_cursor_ffe);
end
if(ischar(options.total_cursor_ffe))
    options.total_cursor_ffe = str2double(options.total_cursor_ffe);
end
if(ischar(options.dfe_tap_num))
    options.dfe_tap_num = str2double(options.dfe_tap_num);
end
if(ischar(options.shift_vec))
    %convert command seperated string to vector
    options.shift_vec = cell2mat(cellfun(@str2num, split(a),'uniform',0));
end

if(ischar(options.eye_ylim))
        %convert command seperated string to vector
    options.eye_ylim = cell2mat(cellfun(@str2num, split(options.eye_ylim),'uniform',0));
end
if(ischar(options.eye_ytick))
    %convert command seperated string to vector
    if contains(options.eye_ytick,':')
        tmp_ytick = cell2mat(cellfun(@str2num, split(options.eye_ytick,':'),'uniform',0));
        if length(tmp_ytick)==3
            options.eye_ytick = tmp_ytick(1):tmp_ytick(2):tmp_ytick(3);
        else
            options.eye_ytick = tmp_ytick(1):tmp_ytick(2);
        end
    else
        options.eye_ytick = cell2mat(cellfun(@str2num, split(options.eye_ytick),'uniform',0));
    end
end
set(0,'defaultfigurecolor',[1 1 1]);

symbol_rate = options.symbol_rate;
sim_rate = options.osr;

if(~exist('results','dir'))
    mkdir('results');
end

disp('Reading Scope File Started');
[lab_data] = process_input_f(options.filetype,options.filename);
disp('Reading Scope File Completed');
% Lab Data Remapping
data_vec =lab_data.data_vec;

if(isempty(lab_data.time_vec))
    data_vec_interp = data_vec;
    data_vec_interp = repmat(data_vec_interp,1,options.repeat_pattern_num);
else
    time_vec = lab_data.time_vec-lab_data.time_vec(1);
    time_vec_interp = 0:1/symbol_rate/sim_rate:time_vec(end);
    data_vec_interp = interp1(time_vec,-1*data_vec,time_vec_interp);
    data_vec_interp = repmat(data_vec_interp,1,options.repeat_pattern_num);
end

%====Setup the Linear Fit Pulse Object =======================
clear prt;

prt = pulse_response_tool_c('osr',sim_rate,'symbol_rate',symbol_rate)
prt = prt.config_input_stream_f(data_vec_interp);
prt = prt.config_decision_stream_f('modulation',options.modulation,'prbs_pattern',options.prbs_pattern,'pattern_length',options.pattern_length,'gray_coding',options.gray_coding);
prt = prt.config_linear_fit_pulse_f('pre_cursor_fit',options.pre_cursor_fit,'pre_cursor_ffe',options.pre_cursor_ffe,'total_cursor_fit',options.total_cursor_fit,'total_cursor_ffe',options.total_cursor_ffe,'dfe_tap_num',options.dfe_tap_num);
prt = prt.apply_linear_fit_pulse_f('shift_vec',options.shift_vec);
prt.plot_linear_fit_error_f('size',[100 800 700 600])

prt = prt.calc_constellation_sndr_f();
prt = prt.calc_tf_from_linear_fit_data_f();

prt.plot_constellation_hist_f('size',[800 800 700 600],'ylim',options.eye_ylim,'ytick',options.eye_ytick);
prt.plot_eye_diagram(prt.stream_input_interp,'size',[1500 800 700 600],'ylim',options.eye_ylim,'ytick',options.eye_ytick,'title',['Unequalized Eye Diagram']);
prt.plot_eye_diagram(prt.sndr_const.ffe.re_interleaved_signal,'size',[2200 800 700 600],'ylim',options.eye_ylim,'ytick',options.eye_ytick,'title',['Equalized Eye Diagram']);

prt.plot_ffe_coeff_f('xlim',[-4 16],'size',[100 100 700 600]);
prt.plot_ffe_resp_f('size',[800 100 700 600]);
prt.plot_tf_f('xlim',[1e8 400e9],'size',[1500 100 700 600]);
prt.plot_linear_fit_pulse_f('xlim',[-10 20],'size',[2200 100 700 600]);

%Merge Figures
input_files_vec = {
    ['results/linear_fit_error.png'];
    ['results/constellation_hist.png'];
    ['results/eye_Unequalized.png'];
    ['results/eye_Equalized.png'];
    ['results/ffe_coeff.png'];
    ['results/ffe_resp.png'];
    ['results/tf.png'];
    ['results/linear_fit_pulse.png']};

num_of_row = 2;
num_of_col = 4;
fig_location = [0 100];
plot_aggregate_f(input_files_vec,num_of_row,num_of_col,['results/' options.summary_plot_filename '.png'],'fig_loc',fig_location);

if(strcmp(options.close_plots,'yes'))
    close all;
end
end