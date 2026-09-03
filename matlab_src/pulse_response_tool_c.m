classdef pulse_response_tool_c
    properties
        symbol_rate_input
        modulation
        prbs_pattern
        osr_input
        stream_input
        stream_input_interp
        stream_decision
        stream_decision_interp
        stream_decision_upsampled
        noise_spectrum
        slice_levels
        slice_target
        fit_spec
        fit_results
        sndr_const
        tf_calc
    end
    
    methods
        function obj = pulse_response_tool_c(options)
            arguments
                options.osr
                options.symbol_rate
            end
            obj.osr_input = options.osr;
            obj.symbol_rate_input = options.symbol_rate;
        end
        
        function obj = config_input_stream_f(obj,input_data,options)
            arguments
                obj
                input_data
                options.sample_start_index=1
                options.sample_stop_index=length(input_data)
                options.polarity =1;
            end
            sig_input = input_data(options.sample_start_index:options.sample_stop_index);
            obj.stream_input = sig_input(:).';

            %Trim the data to avoid the long delay caused by the channel and afe blocks
            [~,idx_trim] = find(abs(obj.stream_input)>0.1*max(abs(obj.stream_input)),1,'first');
            try
                obj.stream_input = obj.stream_input(idx_trim-obj.osr_input:end);
            catch
                obj.stream_input = obj.stream_input(idx_trim:end);
            end
            obj.stream_input = obj.stream_input(:).';

            %Create time and data vectors
            uiSample = obj.osr_input;%UI period in samples for the analysis timebase
            samplePeriod = 1/(obj.symbol_rate_input*uiSample);
            rawSamplePeriod = 1/(obj.symbol_rate_input*obj.osr_input);
            timeBaseUntrim = 0:samplePeriod:(length(obj.stream_input)-1)*rawSamplePeriod;
            rawTimeBase = 0:rawSamplePeriod:(length(obj.stream_input)-1)*rawSamplePeriod;
            rawSinkData = options.polarity*obj.stream_input;
            obj.stream_input_interp = interp1(rawTimeBase,rawSinkData,timeBaseUntrim,'spline');
            obj.stream_input_interp = obj.stream_input_interp(:).';
        end

        function obj = config_decision_stream_f(obj,options)
            arguments
                obj
                options.modulation %NRZ or PAM4
                options.prbs_pattern %PRBS7,11,13,etc
                options.pattern_length
                options.gray_coding
            end
            %Generate pattern for synchronization
            obj.modulation = options.modulation;
            obj.prbs_pattern = options.prbs_pattern;
            prbs_length = str2double(options.prbs_pattern(isstrprop(options.prbs_pattern,'digit')));
            pattern_length = options.pattern_length;
            [~,ddata,txdata] = func_gen_data_pattern(options.prbs_pattern,options.modulation,'fixed',pattern_length,0,0);

            %if Grey Coding is off change Mapping
            if(strcmp(options.gray_coding,'off')==1 && strcmp(options.modulation,'NRZ')==0)
                pam_mapping = [];
                for ii = 1:length(txdata)
                    if(ddata(2*ii-1:2*ii)==[0 0])
                        pam_mapping = [pam_mapping 0];
                    elseif (ddata(2*ii-1:2*ii)==[0 1])
                        pam_mapping = [pam_mapping 1];
                    elseif (ddata(2*ii-1:2*ii)==[1 0])
                        pam_mapping = [pam_mapping 2];
                    elseif (ddata(2*ii-1:2*ii)==[1 1])
                        pam_mapping = [pam_mapping 3];
                    end
                end
                pam_data = (pam_mapping*2-3)/3;
                txdata = pam_data;
            end

            obj.stream_decision = txdata(:);%PAM4:[-1 -1/3 1/3 1]
            repeat_pattern = ceil(length(obj.stream_input)/(obj.osr_input*length(obj.stream_decision)));
            obj.stream_decision = repmat(obj.stream_decision,repeat_pattern,1);
            obj.stream_decision = obj.stream_decision(:).';

            % Align decisions with dataTrimInterp
            decisions_rep = repmat(obj.stream_decision,obj.osr_input,1);
            decisions_up = decisions_rep(:).';
            [d,idx] = xcorr(decisions_up,obj.stream_input_interp);
            [~,midx] = max(abs(d));
            if(d(midx)<0)
                obj.stream_input_interp = -1*obj.stream_input_interp;
                obj.stream_input = -1*obj.stream_input;
            end
            decisions_up_sync = circshift(decisions_up,-idx(midx));
            decisions = decisions_up_sync(1:obj.osr_input:end);
            numSymbolsSink = floor(length(obj.stream_input_interp(1:end))/obj.osr_input);
            obj.stream_decision_interp = decisions(1:numSymbolsSink);
            obj.stream_decision_interp = obj.stream_decision_interp(:).';
            obj.stream_decision_upsampled = decisions_up_sync;
            if strcmp(options.modulation,'NRZ') || strcmp(options.modulation,'nrz') || strcmp(options.modulation,'Nrz')
                obj.slice_levels = [2 0 -2];
                obj.slice_target = 1; %NRZ target set by +1 -1 reference levels
            else
                obj.slice_levels = [2/3 0 -2/3];
                obj.slice_target = 1/3; %PAM4 target set by +1 +1/3 -1/3 -1 reference levels
            end
        end

        function obj = config_linear_fit_pulse_f(obj,options)
            arguments
                obj
                options.pre_cursor_fit %Pre-cursor pulse fit
                options.pre_cursor_ffe %Pre-cursor of derived FFE
                options.total_cursor_fit %Total UI of pulse fit
                options.total_cursor_ffe %Total Taps of derived FFE
                options.dfe_tap_num = 0
                options.num_symbols = length(obj.stream_decision_interp)

            end

            obj.fit_spec.t_dp = options.pre_cursor_fit;
            obj.fit_spec.t_dw = options.pre_cursor_ffe;
            obj.fit_spec.t_np = options.total_cursor_fit;
            obj.fit_spec.t_nw = options.total_cursor_ffe;
            obj.fit_spec.t_dfe_taps = options.dfe_tap_num;
            obj.fit_spec.num_symbols = options.num_symbols;
        end

        function obj = config_adc_noise_stream_f(obj,data_in,options)
            arguments
                obj
                data_in
                options.num_samples %samples for pulse extraction
                options.buffer_deep %eg. 2 or 25
                options.num_branches %number of branches for captured ADC data,64 or 32
                options.avg_f=20
            end

            data = data_in.data_vec;
            num_samples = options.num_samples;
            buffer_deep = options.buffer_deep;
            num_branches = options.num_branches;
            symbol_rate = obj.symbol_rate_input;

            patches = ceil(num_samples/(buffer_deep*num_branches));
            sample_start = 1;
            data_source = [];
            for ii = 1:patches
                data_trunc = data(sample_start+(ii-1)*buffer_deep:sample_start+ii*buffer_deep-1,:)';
                data_trunc = data_trunc-mean(data)';
                data_vec = reshape(data_trunc,[num_branches*buffer_deep,1])/128;%reshape data to 1 dimension
                data_source = [data_source data_vec'];
            end
            error_info = data_source(1:2^13);
            error_autocor = xcorr(error_info)/(symbol_rate/(length(error_info)));
            error_freq = 0:symbol_rate/(length(error_autocor)):(symbol_rate-symbol_rate/(length(error_autocor)));
            error_spec = 20*log10(abs(fft(error_autocor)));

            avg_f = options.avg_f;
            no_pts = floor(length(error_freq)/(2*avg_f));
            obj.noise_spectrum.error_freq_avg = error_freq(1:avg_f:no_pts*avg_f);
            obj.noise_spectrum.error_spec_avg = sum(reshape(error_spec(1:no_pts*avg_f),[avg_f,no_pts]),1)/avg_f;
        end







        function obj = apply_linear_fit_pulse_f(obj,options)
            arguments
                obj
                options.shift_vec = [-2 -1 1 2];
            end
            obj.fit_spec.osr_input = obj.osr_input;
            obj.fit_spec.symbol_rate_input = obj.symbol_rate_input;

            %will also try shifting the data one bit left and one bit right to help with alignment issues
            proper_alignment_found = 0;
            obj.fit_results = fit_pulse_response_f(obj.stream_input_interp,obj.stream_decision_interp,obj.fit_spec);
            [~,I] = max(obj.fit_results.firNum);
            if(I~=(obj.fit_spec.t_dw+1))
                for zz = 1:length(options.shift_vec)
                    obj.fit_results = fit_pulse_response_f(obj.stream_input_interp,circshift(obj.stream_decision_interp,options.shift_vec(zz)),obj.fit_spec);
                    [~,I] = max(obj.fit_results.firNum);
                    if(I==(obj.fit_spec.t_dw+1))
                        proper_alignment_found = 1;
                        obj.fit_results.alignment_shift = options.shift_vec(zz);
                        break;
                    end
                end
            else
                proper_alignment_found = 1;
                obj.fit_results.alignment_shift = 0;
            end
            if(proper_alignment_found==0)
                error('Alignment error: Unable to find proper alignment for pulse fit');
            end
        end

        function obj = calc_tf_from_linear_fit_data_f(obj,options)
            arguments
                obj
                options.rise_fall_time = 1e-15
            end

            %Mapping - Remove in Future

            UISAMPLES = obj.osr_input;
            p = obj.fit_results.p;
            DATARATE = obj.symbol_rate_input;
            
            ideal_pulse = [ones(1,UISAMPLES)*max(abs(p)) zeros(1,length(p)-UISAMPLES)];
            
            time_vec_ref = 0:1/DATARATE/UISAMPLES:(length(p)-1)*(1/DATARATE/UISAMPLES);
            ideal_pulse_time = [0 options.rise_fall_time 1/DATARATE-options.rise_fall_time 1/DATARATE time_vec_ref(end)];
            ideal_pulse_raw = [0 max(abs(p)) max(abs(p)) 0 0];

            ideal_pulse = interp1(ideal_pulse_time,ideal_pulse_raw,time_vec_ref,'linear','extrap');

            tx_tf.tf = abs(fft(p))./abs(fft(ideal_pulse));
            tx_tf.tf = tx_tf.tf/tx_tf.tf(1)
            tx_tf.freq = [1:length(p)]/length(p)*UISAMPLES*DATARATE;

            %patch notches in fft of ideal pulse since they make the TF have spikes
            fft_pulse=abs(fft(ideal_pulse));
            fft_pulse_clip=fft_pulse(fft_pulse>1e-6);
            fft_pulse_clip_freq = tx_tf.freq(fft_pulse>1e-6);
            fft_pulse_smooth = interp1(fft_pulse_clip_freq,fft_pulse_clip,tx_tf.freq,'linear');

            tx_tf.tf = abs(fft(p))./fft_pulse_smooth;
            tx_tf.tf = tx_tf.tf/tx_tf.tf(1);
            tx_tf.nyquist_loss = 20*log10(interp1(tx_tf.freq,tx_tf.tf,obj.symbol_rate_input/2));
            tx_tf.idx_3dB=find(20*log10(tx_tf.tf)<-3,1,'first');

            if tx_tf.idx_3dB>1
                tx_tf.bw_3dB = interp1(20*log10(tx_tf.tf(tx_tf.idx_3dB-1:tx_tf.idx_3dB)),tx_tf.freq(tx_tf.idx_3dB-1:tx_tf.idx_3dB),20*log10(tx_tf.tf(1))-3);
            else
                tx_tf.bw_3dB =tx_tf.freq(tx_tf.idx_3dB);
            end
            obj.tf_calc = tx_tf;
        end



        function obj = calc_constellation_sndr_f(obj)
            obj.sndr_const.ffe = obj.constellation_sndr_helper_f('dfe_status','off');
            obj.sndr_const.ffe_and_dfe = obj.constellation_sndr_helper_f('dfe_status','calc');
        end

        function [sndr_const] = constellation_sndr_helper_f(obj,options)
            arguments
                obj
                options.dfe_status = 'off';
                options.dfe_external = [];
            end

            if(strcmp(options.dfe_status,'calc')==1)
                dfe_tap_weights = obj.fit_results.DFEtapWeight;
                dfe_en =1;
            elseif(strcmp(options.dfe_status,'off')==1)
                dfe_tap_weights = 0;
                dfe_en =0;
            elseif(strcmp(options.dfe_status,'fixed')==1)
                dfe_tap_weights = options.dfe_external;
                dfe_en =1;
            end
            const_sndr = 0;
            uiSample = obj.osr_input;
            for zz=1:uiSample
                verticalConstellation = obj.stream_input_interp(zz:uiSample:end);
                if(dfe_en==0)
                    filterConstellation = filter(obj.fit_results.firNum,1,verticalConstellation);
                    filterConstellationUnity = filter(obj.fit_results.firNumNorm,1,verticalConstellation);
                else
                    filterConstellation = filter(obj.fit_results.firNumDFE,1,verticalConstellation);
                    filterConstellationUnity = filter(obj.fit_results.firNumDFENorm,1,verticalConstellation);
                end
                filterConstellation = filterConstellation-mean(filterConstellation);
                filterConstellationArray(1:length(filterConstellationUnity),zz) = filterConstellationUnity;
                slice_p = 2*obj.slice_target;
                slice_z = 0;
                slice_n = -2*obj.slice_target;
                decision_p = filterConstellation > slice_p;
                decision_z = filterConstellation > slice_z;
                decision_n = filterConstellation > slice_n;
                %scales the decisions to map -3 -1 1 3
                decisions = (2*obj.slice_target)*(decision_p+decision_z+decision_n-1.5*ones(1,length(decision_p)));
                lengthFir = length(obj.fit_results.firNum);
                lengthDec = length(decisions);
                lengthConst = length(filterConstellation);
                dfe_vec = zeros(1,length(decisions));
                for dfe_loop=1:length(dfe_tap_weights)
                    delayed_decisions = circshift(decisions,dfe_loop);
                    dfe_vec = dfe_vec+delayed_decisions.*dfe_tap_weights(dfe_loop);
                end
                filterConstellation = filterConstellation - dfe_vec;

                lengthFir = length(obj.fit_results.firNum);
                lengthDec = length(decisions);
                lengthConst = length(filterConstellation);
                sndr(zz) = 20*log10(rms(decisions(lengthFir:end))/rms(filterConstellation(lengthFir:end-(lengthConst-lengthDec))-decisions(lengthFir:end)));

                if sndr(zz)>const_sndr
                    const_sndr = sndr(zz);
                    goodConstellationUnity = filterConstellationUnity;
                    goodConstellation = filterConstellation;
                    goodUnequalized = verticalConstellation;
                    winning_fir = obj.fit_results.firNum;
                    [~,ScoreResults.bestphase] = max(sndr);
                end

                arraySize = size(filterConstellationArray);
                reInterleavedSignal = zeros(1,arraySize(1)*arraySize(2));
                for zz =1:arraySize(1)
                    for kk = 1:arraySize(2)
                        reInterleavedSignal((zz-1)*arraySize(2)+kk) = filterConstellationArray(zz,kk);
                    end
                end

                sndr_const.raw_sndr_results = sndr;
                [RLMResults] = calcRLM(goodConstellation);
                sndr_const.sndr = const_sndr;
                sndr_const.rlm_results = RLMResults;
                sndr_const.constellation_eq = goodConstellationUnity;
                sndr_const.constellation_uneq = goodUnequalized;
                sndr_const.re_interleaved_signal = reInterleavedSignal;
                
            end
        end

        function [] = plot_tf_f(obj,options)
            arguments
                obj
                options.size = [500 500 800 600];
                options.xscale = 'log';
                options.yscale = 'lin';
                options.xlim;
                options.ylim;
                options.xtick;
                options.ytick;
                options.title;
                options.legend_loc;
                options.annotate_loss = false
            end

            figure1 = figure('Units','pixels','Position',options.size);
            
            axes1 = subplot(1,1,1,'Parent',figure1,'YAxisLocation','left','YGrid','on',...
                'YColor',[0 0 0],...
                'XMinorTick','on',...
                'YMinorTick','on',...
                'XMinorGrid','on',...
                'YMinorGrid','off',...
                'XGrid','on',...
                'YGrid','on',...
                'xscale',options.xscale,...
                'yscale',options.yscale,...
                'FontSize',14,'linewidth',2);
            
            box(axes1,'on');
            hold(axes1,'on');

            plot(obj.tf_calc.freq,20*log10(abs(obj.tf_calc.tf)),'LineWidth',3,'DisplayName','Transfer Function','Parent',axes1);

            if(options.annotate_loss==true)
                if(strcmp(obj.modulation,'NRZ')==1)
                    freq_ind = find(obj.tf_calc.freq>=obj.symbol_rate_input/2,1,'first');
                    text(obj.tf_calc.freq(freq_ind)+3,20*log10(abs(obj.tf_calc.tf(freq_ind))),[num2str(round(20*log10(abs(obj.tf_calc.tf(freq_ind)))*10)/10) 'dB'],'Fontsize',14);
                elseif(strcmp(obj.modulation,'PAM4')==1)
                    freq_ind = find(obj.tf_calc.freq>=obj.symbol_rate_input/2,1,'first');
                    text(obj.tf_calc.freq(freq_ind)+3,20*log10(abs(obj.tf_calc.tf(freq_ind))),[num2str(round(20*log10(abs(obj.tf_calc.tf(freq_ind)))*10)/10) 'dB'],'Fontsize',14);
                end
            end

            if isfield(options,"xlim")
                xlim(options.xlim)
            end
            if isfield(options,"ylim")
                ylim(options.ylim)
            end
            if isfield(options,"title")
                title(options.title)
            else
                title(['3dB Freq:' num2str(obj.tf_calc.bw_3dB./1e9) 'GHz']);
            end
            if isfield(options,'xtick')
                set(gca,'xtick',options.xtick)
            end
            if isfield(options,'ytick')
                set(gca,'ytick',options.ytick)
            end
            xlabel('Frequency(Hz)');
            ylabel('Transfer Function (dB)');
            exportgraphics(axes1,'results/tf.png','Resolution',500)

        end

        function [] = plot_linear_fit_pulse_f(obj,options)
            arguments
                obj
                options.size = [500 500 800 600];
                options.xscale = 'lin';
                options.yscale = 'lin';
                options.xlim;
                options.ylim;
                options.xtick;
                options.ytick;
                options.title;
                options.legend_loc='best';
            end

            figure1 = figure('Units','pixels','Position',options.size);
            axes1 = subplot(1,1,1,'Parent',figure1,'YAxisLocation','left','YGrid','on',...
                'YColor',[0 0 0],...
                'XMinorTick','off',...
                'YMinorTick','off',...
                'XMinorGrid','off',...
                'YMinorGrid','off',...
                'XGrid','on',...
                'YGrid','on',...
                'xscale',options.xscale,...
                'yscale',options.yscale,...
                'FontSize',14,'linewidth',2);

                box(axes1,'on');
                hold(axes1,'on');

                [~,main_loc] = max(obj.fit_results.p);
                main_time_val = obj.fit_results.timebase(main_loc)*obj.symbol_rate_input;
                plot(obj.fit_results.timebase*obj.symbol_rate_input-main_time_val,obj.fit_results.p,'LineWidth',2,'DisplayName','Transfer Function','Parent',axes1);
                plot(obj.fit_results.timebaseSampled*obj.symbol_rate_input-main_time_val,obj.fit_results.pSampled,'o','LineWidth',2,'DisplayName','Transfer Function','Parent',axes1);

                txt_sndr = sprintf('SNDR [pmax/e_{rms}:%.1f dB',obj.fit_results.SNDR);
                txt_sndr_old = sprintf('SNDR [data_{rms}/e_{rms}:%.1f dB',obj.fit_results.SNDRold);
                txt_sndr_oldpeak = sprintf('SNDR_{peak}  [data_{rms}/e_{rms}]:%.1f dB',obj.fit_results.SNDRold_peak)

                txt_pmax = sprintf('Linear fit pulse peak (p_{max}):%.2f',obj.fit_results.pmax);
                txt_vf = sprintf('Steady-state voltage(v_f):%.2f',obj.fit_results.vf);
                txt_ratio = sprintf('p_{max}/v_f:%.2f',obj.fit_results.pulsePeakRatio);
                txt_nyqloss = sprintf('Nyquist Loss:%.1f dB',obj.fit_results.nyquist_loss);

                if isfield(options,"xlim")
                    xlim(options.xlim);
                end
                if isfield(options,"ylim")
                    ylim(options.ylim);
                end

                ylimit = get(gca,'ylim');
                ylimits = get(gca,'Ylim');
                xlimit = get(gca,'xlim');
                
                text(2,0.9*ylimit(2),txt_pmax,'FontSize',12,'FontWeight','bold')
                text(2,0.8*ylimit(2),txt_vf,'FontSize',12,'FontWeight','bold')
                text(2,0.7*ylimit(2),txt_ratio,'FontSize',12,'FontWeight','bold')
                text(2,0.6*ylimit(2),txt_sndr,'FontSize',12,'FontWeight','bold')
                text(2,0.5*ylimit(2),txt_sndr_old,'FontSize',12,'FontWeight','bold')
                text(2,0.4*ylimit(2),txt_sndr_oldpeak,'FontSize',12,'FontWeight','bold')

                text(2,0.3*ylimit(2),txt_nyqloss,'FontSize',12,'FontWeight','bold')
                text(2,0.2*ylimit(2),['RLMbj:' num2str(obj.sndr_const.ffe.rlm_results.RLMbj)],'FontSize',12,'FontWeight','bold')
                text(2,0.1*ylimit(2),['RLMbs:' num2str(obj.sndr_const.ffe.rlm_results.RLMbs)],'FontSize',12,'FontWeight','bold')

                if isfield(options,"title")
                    title(options.title);
                else
                    title(['Extracted Pulse Response']);
                end

                if isfield(options,"xtick")
                    set(gca,'xtick',options.xtick);
                end
                if isfield(options,"ytick")
                    set(gca,'ytick',options.ytick);
                end
                xlabel('Time(UI)');
                ylabel('Voltage (V)');
                exportgraphics(axes1,'results/linear_fit_pulse.png','Resolution',500);
            end

            function [] = plot_linear_fit_error_f(obj,options)
                arguments
                    obj
                    options.size = [500 500 800 600];
                    options.xscale = 'lin';
                    options.yscale = 'lin';
                    options.xlim;
                    options.ylim;
                    options.xtick;
                    options.ytick;
                    options.title;
                    options.legend_loc='best';
                    
                end
                figure1 = figure('Units','pixels','Position',options.size);
                axes1 = subplot(1,1,1,'Parent',figure1,'YAxisLocation','left','YGrid','on',...
                    'YColor',[0 0 0],...
                    'XMinorTick','off',...
                    'YMinorTick','off',...
                    'XMinorGrid','off',... 
                    'YMinorGrid','off',...
                    'XGrid','on',...
                    'YGrid','on',...
                    'xscale',options.xscale,...
                    'yscale',options.yscale,...
                    'FontSize',14,'linewidth',2);

                box(axes1,'on');
                hold(axes1,'on');
                
                time = (1:length(obj.stream_input_interp))/(obj.osr_input*obj.symbol_rate_input);

                plot(time(1:length(obj.fit_results.l)),obj.fit_results.l,'LineWidth',0.5,'DisplayName','Linear fit','Parent',axes1)
                plot(time,obj.stream_input_interp,'LineWidth',0.5,'color','k','DisplayName','Data','Parent',axes1)
                plot(time(1:length(obj.fit_results.e)),obj.fit_results.e,'color','g','LineWidth',0.5,'DisplayName','Error','Parent',axes1);

                legend(axes1,'show');
                if isfield(options,"title")
                    title(options.title);
                else
                    title(['Linear Fit Pulse Error']);
                end

                if isfield(options,"xlim")
                    xlim(options.xlim);
                else
                    xlim([min(time(1:length(obj.fit_results.l))) max(time(1:length(obj.fit_results.l)))]);
                end

                if isfield(options,"xtick")
                    set(gca,'xtick',options.xtick)
                end
                if isfield(options,"ytick")
                    set(gca,'ytick',options.ytick)
                end
                xlabel('Time(s)');
                ylabel('Voltage (V)');
                exportgraphics(axes1,'results/linear_fit_error.png','Resolution',500);
            end

            function [] = plot_ffe_resp_f(obj,options)
                arguments
                    obj;
                    options.size = [500 500 800 600];
                    options.xscale = 'lin';
                    options.yscale = 'lin';
                    options.xlim;  
                    options.ylim;  
                    options.xtick;
                    options.ytick;
                    options.title;
                    options.legend_loc='best';
                end

                figure1 = figure('Units','pixels','Position',options.size);
                axes1 = subplot(1,1,1,'Parent',figure1,'YAxisLocation','left','YGrid','on',...
                    'YColor',[0 0 0],...
                    'XMinorTick','off',...
                    'YMinorTick','off',...
                    'XMinorGrid','off',...
                    'YMinorGrid','off',...
                    'XGrid','on',...
                    'YGrid','on',...
                    'xscale',options.xscale,...
                    'yscale',options.yscale,...
                    'FontSize',14,'linewidth',2);

                box(axes1,'on');
                hold(axes1,'on');

                freq_n = 10e3;
                freq = [1:freq_n]/freq_n*obj.symbol_rate_input/2
                fir_resp = [obj.fit_results.firNumNorm]*[exp((0:length(obj.fit_results.firNumNorm)-1).'*-1i*2*pi*(freq)/obj.symbol_rate_input)];
                fir_boost_nyq = 20*log10(abs(fir_resp(end)/abs(fir_resp(1))));

                plot(freq./1e9,20*log10(abs(fir_resp)),'LineWidth',3,'color',[0 0 1],'DisplayName',['FFE TF [No DFE] Nyquist:' num2str(fir_boost_nyq,'%3.3g') 'dB'],'Parent',axes1)
                ylimit = get(gca,'ylim');
                xlimit = get(gca,'xlim');
                if(obj.fit_spec.t_dfe_taps~=0)
                    fir_resp = [obj.fit_results.firNumDFENorm]*exp((0:length(obj.fit_results.firNumDFENorm)-1).'*-1i*2*pi*(freq)/obj.symbol_rate_input)
                    fir_boost_nyq = 20*log10(abs(fir_resp(end)/abs(fir_resp(1))));
                    plot(freq./1e9,20*log10(abs(fir_resp)),'LineWidth',3,'color',[1 0 0],'DisplayName',['FFE TF [' num2str(obj.fit_spec.t_dfe_taps) '-tap DFE] Nyquist:' num2str(fir_boost_nyq,'%3.3g') 'dB'],'Parent',axes1);
                end
                legend(axes1,'show');
                
                legend('location',options.legend_loc);

                if isfield(options,"xlim")
                    xlim(options.xlim);
                else
                    xlim([0 obj.symbol_rate_input./1e9/2]);
                end
                if isfield(options,"ylim")
                    ylim(options.ylim);
                end
                if isfield(options,"title")
                    title(options.title);
                else
                    title(['FFE Transfer Function']);
                end
                if isfield(options,"xtick")
                    set(gca,'xtick',options.xtick);
                end
                if isfield(options,"ytick")
                    set(gca,'ytick',options.ytick);
                end
                xlabel('Frequency (GHz)');
                ylabel('Transfer Function (dB)');
                exportgraphics(axes1,'results/ffe_resp.png','Resolution',500);
            end

            function [] = plot_constellation_hist_f(obj,options)
                arguments
                    obj;
                    options.size = [500 500 800 600];
                    options.xscale = 'lin';
                    options.yscale = 'lin';
                    options.xlim;  
                    options.ylim;  
                    options.xtick;
                    options.ytick;
                    options.title;
                    options.legend_loc='best';
                end

                figure1 = figure('Units','pixels','Position',options.size);
                axes1 = subplot(1,1,1,'Parent',figure1,'YAxisLocation','left','YGrid','on',...
                    'YColor',[0 0 0],...
                    'XMinorTick','off',...
                    'YMinorTick','off',...
                    'XMinorGrid','off',...
                    'YMinorGrid','off',...
                    'XGrid','on',...
                    'YGrid','on',...
                    'xscale',options.xscale,...
                    'yscale',options.yscale,...
                    'FontSize',14,'linewidth',2);
                box(axes1,'on')
                hold(axes1,'on')
                a=1;
                const_uneq = obj.sndr_const.ffe.constellation_uneq(obj.osr_input:end-obj.osr_input);
                const_eq = obj.sndr_const.ffe.constellation_eq(obj.osr_input:end-obj.osr_input);
                histogram(const_uneq,'BinWidth',[0.01],'orientation','horizontal','edgecolor','none','DisplayName','Unequalized')
                histogram(const_eq,'BinWidth',[0.01],'orientation','horizontal','edgecolor','none','DisplayName',['Equalized - SNDR:' num2str(obj.sndr_const.ffe.sndr,'%.2f')],'facecolor',[1 0 0])
                legend(axes1,'show')

                legend('location',options.legend_loc);

                if isfield(options,"xlim")
                    xlim(options.xlim);
                end
                if isfield(options,"ylim")
                    ylim(options.ylim);
                else
                    ylim([min(min(const_uneq),min(const_eq)) max(max(const_uneq),max(const_eq))])
                end

                if isfield(options,"title")
                    title(options.title);
                else
                    title(['Constellation Histogram']);
                end
                if isfield(options,"xtick")
                    set(gca,'xtick',options.xtick);
                end
                if isfield(options,"ytick")
                    set(gca,'ytick',options.ytick);
                end
                ylabel('Voltage (V)')
                xlabel('Number of Occurances');
                exportgraphics(axes1,'results/constellation_hist.png','Resolution',500);
            end

            function [] = plot_ffe_coeff_f(obj,options)
                arguments
                    obj;
                    options.size = [500 500 700 600];
                    options.xscale = 'lin';
                    options.yscale = 'lin';
                    options.xlim;  
                    options.ylim;  
                    options.xtick;
                    options.ytick;
                    options.title;
                    options.legend_loc='best';
                end
                a=1;

                color_vec = [0 0 1;1 0 0]
                ffe_array =obj.fit_results.firNumNorm;
                [~,main_loc] = max(ffe_array);
                pre_vec = ffe_array(1:main_loc-1)
                main_vec = ffe_array(main_loc);
                post_vec = ffe_array(main_loc+1:end)

                ffe_vec{1} = ffe_array;
                if(obj.fit_spec.t_dfe_taps ~=0)
                    ffe_vec{2} = obj.fit_results.firNumDFENorm;
                end
                figure1 = figure('Units','pixels','Position',options.size);
                axes1 = subplot(1,1,1,'Parent',figure1,'YAxisLocation','left','YGrid','on',...
                    'YColor',[0 0 0],...
                    'XMinorTick','off',...
                    'YMinorTick','off',...
                    'XMinorGrid','off',...
                    'YMinorGrid','off',...
                    'XGrid','on',...
                    'YGrid','on',...
                    'xscale','lin',...
                    'FontSize',14,'linewidth',2);
                box(axes1,'on')
                hold(axes1,'on')

                for zz = 1:length(ffe_vec)
                    bar_vec(zz,:) = ffe_vec{zz};
                end

                b  = bar([-1*length(pre_vec):length(post_vec)],bar_vec.');
                set(gca,'xtick',[-1*length(pre_vec):2:length(post_vec)])

                for zz = 1:length(ffe_vec)
                    b(zz).FaceColor = color_vec(zz,:);
                    if(zz==1)
                        b(zz).DisplayName = 'FFE Taps';
                    else
                        b(zz).DisplayName = ['FFE + ' num2str(obj.fit_spec.t_dfe_taps) '-tap DFE'];
                    end
                end

                legend(axes1,'show')

                if isfield(options,"xlim")
                    xlim(options.xlim);
                end
                if isfield(options,"ylim")
                    ylim(options.ylim);
                end

                if isfield(options,"title")
                    title(options.title);
                else
                    title(['Normalized FFE Taps [Pre:' num2str(length(pre_vec)) ',Post:' num2str(length(post_vec)) ']']);
                end

                if isfield(options,'xtick')
                    set(gca,'xtick',options.xtick);
                end
                if isfield(options,'ytick')
                    set(gca,'ytick',options.ytick);
                end
                xlabel('Tap location');
                ylabel('Normalized Tap Weight');
                exportgraphics(axes1,'results/ffe_coeff.png','Resolution',500);
            end

            function [] = plot_eye_diagram(obj,data_vec,eye_config,options)
                arguments
                    obj;
                    data_vec;
                    eye_config.skip_ui =100;
                    eye_config.eye_delay_ui = 49;
                    eye_config.eye_num_ui =2;
                    options.size = [500 500 800 600];
                    options.xscale = 'lin';
                    options.yscale = 'lin';
                    options.xlim;  
                    options.ylim;  
                    options.xtick;
                    options.ytick;
                    options.title;
                    options.legend_loc='best';
                end
                figure1 = figure('Units','pixels','Position',options.size);
                axes1 = subplot(1,1,1,'Parent',figure1,'YAxisLocation','left','YGrid','on',...
                    'YColor',[0 0 0],...
                    'XMinorTick','off',...
                    'YMinorTick','off',...
                    'XMinorGrid','off',...
                    'YMinorGrid','off',...
                    'XGrid','on',...
                    'YGrid','on',...
                    'xscale',options.xscale,...
                    'yscale',options.yscale,...
                    'FontSize',14,'linewidth',2);
                box(axes1,'on');
                hold(axes1,'on');
                
                uiSample = obj.osr_input;
                samplePeriod = 1/(obj.symbol_rate_input*uiSample);

                func_eyediag(data_vec,eye_config.skip_ui,eye_config.eye_delay_ui,...
                eye_config.eye_num_ui*uiSample,obj.symbol_rate_input/eye_config.eye_num_ui,2*uiSample*samplePeriod,'PAM',1,'color','De-Embed',figure1)
                
                [eye_x_opening,min_eye_y_opening,max_eye_y_opening,eye_mid_index,eye_y_opening_ratio] = calc_eye_info_f(data_vec,uiSample,2*uiSample*samplePeriod,eye_config.skip_ui,[],[],[]);

                str_eye_x_opening = num2str(sprintf('%2.3f',eye_x_opening));
                str_min_eye_y_opening = num2str(sprintf('%2.3f',min_eye_y_opening));
                str_max_eye_y_opening = num2str(sprintf('%2.3f',max_eye_y_opening));
                str_eye_y_opening_ratio = num2str(sprintf('%2.3f',eye_y_opening_ratio));

                xlimit = get(gca,'xlim');
                text2 = ['Min X-Eye Opening(pp)=' str_eye_x_opening 'UI           Min Y-Eye Opening(pp)=' str_min_eye_y_opening 'Vpp'];
                text(xlimit(1)+xlimit(2)/20,-0.5,text2,'FontSize',11);

                text3 = ['Max Amplitude(pp)=' str_max_eye_y_opening 'VPP          Max-Amp/Eye-Opening Ratio=' str_eye_y_opening_ratio];
                text(xlimit(1)+xlimit(2)/20,-0.6,text3,'FontSize',11);
                set(gca,'FontSize',14)
                set(gca,'linewidth',2)

                if isfield(options,"xlim")
                    xlim(options.xlim)
                end
                if isfield(options,"ylim")
                    ylim(options.ylim)
                else
                    ylim([min(min(const_uneq),min(const_eq)) max(max(const_uneq),max(const_eq))])
                end

                if isfield(options,"title")
                    title(options.title)
                else
                    title(['Unequalized Eye Diagram']);
                end

                if isfield(options,"xtick")
                    set(gca,'xtick',options.xtick)
                end
                if isfield(options,"ytick")
                    set(gca,'ytick',options.ytick)
                end

                ylabel('Voltage(V)');
                xlabel('Time(s)');
                exportgraphics(gca,['results/eye_' extractBefore(options.title,'') '.png'],'Resolution',500);
            end

            function [] = plot_adc_noise_spectrum_f(obj,options)
                arguments
                    obj;
                    options.size = [500 500 700 600];
                    options.xscale = 'lin';
                    options.yscale = 'lin';
                    options.xlim;  
                    options.ylim = [-150 -100];
                    options.xtick;
                    options.ytick;
                    options.title;
                    options.legend_loc='best';
                end

                figure1 = figure('Units','pixels','Position',options.size);
                axes1 = subplot(1,1,1,'Parent',figure1,'YAxisLocation','left','YGrid','on',...
                    'YColor',[0 0 0],...
                    'XMinorTick','off',...
                    'YMinorTick','off',...
                    'XMinorGrid','off',...
                    'YMinorGrid','off',...
                    'XGrid','on',...
                    'YGrid','on',...
                    'xscale','lin',...
                    'FontSize',14,'linewidth',2);

                box(axes1,'on');
                hold(axes1,'on');

                plot(obj.noise_spectrum.error_freq_avg/1e9,obj.noise_spectrum.error_spec_avg,'LineWidth',2,'color',[0 0 1],'Parent',axes1);

                if isfield(options,"xlim")
                    xlim(options.xlim)
                else
                    xlim([min(obj.noise_spectrum.error_freq_avg/1e9) max(obj.noise_spectrum.error_freq_avg/1e9)]);
                end
                if isfield(options,"ylim")
                    ylim(options.ylim)
                end

                if isfield(options,"title")
                    title(options.title);
                end

                if isfield(options,"xtick")
                    set(gca,'xtick',options.xtick);
                end
                if isfield(options,"ytick")
                    set(gca,'ytick',options.ytick);
                end

                ylabel('PSD [dBV/Hz]')
                xlabel('Frequency [GHz]')

            end
        end
    end
    