function FitResults = fit_pulse_response_f(data,decisions,FitSpec)
    decisions = circshift(decisions,0);
    UISAMPLES = FitSpec.osr_input;
    numSymbols = FitSpec.num_symbols;
    DATARATE = FitSpec.symbol_rate_input;
    T_DP = FitSpec.t_dp;
    T_NP = FitSpec.t_np;
    T_DW = FitSpec.t_dw;
    T_NW = FitSpec.t_nw;
    T_DFE_TAPS = FitSpec.t_dfe_taps;
    
    %Bulid UI folded data matrix
    Y = zeros(UISAMPLES,numSymbols);
    Y = reshape(data(1:UISAMPLES*numSymbols),UISAMPLES,numSymbols);
    %Bulid symbol matrix
    xr = [decisions(T_DP+1:end) decisions(1:T_DP)];
    X = zeros(T_NP+1,length(xr));

    for i = 1:T_NP
        X(i,:) = circshift(xr,i-1);
    end
    X(T_NP+1,:) = ones(1,length(decisions));

    %calculate linear fit pusle response matrix
    P = Y*X'*inv(X*X');
    %calculate linear fit error matrix
    E = P*X-Y;
    %Unfold into error vector
    e = reshape(E,1,size(E,1).*size(E,2));
    %Unfold linearied response
    L = P*X;

    l = reshape(L,1,size(L,1).*size(L,2));
    
    %Extrac P1 vector and unfold calculate pulse response fit.
    P1 = P(:,1:T_NP);
    p = reshape(P1,1,size(P1,1).*size(P1,2));

    %calculate driver figures of merit
    vf = sum(p)/UISAMPLES;
    pmax=max(p);
    pulsePeakRatio = pmax/vf;
    eRms = rms(e(floor(0.1*length(e)):floor(0.9*length(e))));
    eRmsRatio = eRms/vf;
    SNDRold =20*log10(rms(data)/eRms);
    SNDR = 20*log10(pmax/eRms);
    
    %create sampled pulse response
    %Positioning at the front of the pulse plateay seems to produce most repeatable results
    above = p>(max(p)/1.01);
    [~,ind] = max(above);
    tx = ind;%-UISAMPLES/10;
    initialSample = rem(tx,UISAMPLES)+1;
    pSampled = p(initialSample:UISAMPLES:end);

    for zz = initialSample:initialSample
        e_sampled = e(zz:UISAMPLES:end);
        eRms = rms(e_sampled(floor(0.1*length(e_sampled)):floor(0.9*length(e_sampled))));
        
        SNDRold_peak = 20*log10(rms(data(zz:UISAMPLES:end))/eRms);
    end

    %calculate SNR_ISI
    NB=10;%consider making programmable,but will cause interop issues.
    [pmaxSampled,pmaxSampledIndex] = max(pSampled);
    if pmaxSampledIndex+NB+1<=length(pSampled)
        snrIsiCursors = pSampled(pmaxSampledIndex+NB+1:end);
        rssNonPrimary = sqrt(sum(snrIsiCursors.^2));
        SNR_ISI = 20*log10(pmaxSampled/rssNonPrimary);
    else
        fprintf('Warning extracted pulse not long enough to calculate SNR ISI\n')
        SNR_ISI = NaN;
    end

    for i =1:T_NW
        P3(:,i) = circshift(pSampled,i-1-T_DW)';
        P3(T_NW+i-T_DW:T_NP,i)=0;
        P3(1:i-T_DW-1,i) = 0;
    end

    %create xp impulse vector
    xp = zeros(T_NP,1)
    xp(T_DP+1) =1;

    %calculate equalizer filter coefficients
    w = inv(P3.'*P3)*P3.'*xp;
    firNum = w';
    firNumNorm = firNum/sum(w');

    %Add FFE calculation assuming DFE
    %create xp impulse vector
    xp = zeros(T_NP,1)
    xp(T_DP+1) =1;

    for zz =1:T_DFE_TAPS
        xp(T_DP+1+zz) =pSampled(pmaxSampledIndex+zz)/pSampled(pmaxSampledIndex);
        DFEtapWeight(zz) = xp(T_DP+zz+1)
    end
    %calculate equalizer filter coefficients
    w = inv(P3.'*P3)*P3.'*xp;
    firNumDFE = w';
    firNumDFENorm = firNumDFE/sum(abs(w'));

    timebase = 0:1/(UISAMPLES*DATARATE):(length(p)-1)*(1/(UISAMPLES*DATARATE));
    timebaseSampled = timebase(initialSample:UISAMPLES:length(p));

    %calculate Nyquist loss
    [h ~] =freqz(pSampled);
    nyquist_loss = 20*log10(abs(h(1))/abs(h(end)));

    %calculate Nyquist loss including 2 pre-cursir,4 post-cursor
    [~,index] =max(pSampled)

    try
        pSampledInner = pSampled(index-2:index+4);
        [h ~] =freqz(pSampledInner);
        nyquist_loss_inner = 20*log10(abs(h(1))/abs(h(end)));
    catch
        warning 'Warning, insufficient FIR taps for inner Nyquist loss calculation'
        nyquist_loss_inner = -99;
    end

    FitResults.firNum = firNum;
    FitResults.firNumNorm = firNumNorm;
    FitResults.firNumDFE = firNumDFE;
    FitResults.firNumDFENorm = firNumDFENorm;
    if(exist('DFEtapWeight'))
        FitResults.DFEtapWeight = DFEtapWeight;
    else
        FitResults.DFEtapWeight = 0;
    end
    FitResults.vf = vf;
    FitResults.pmax = pmax;
    FitResults.pulsePeakRatio = pulsePeakRatio;
    FitResults.eRms = eRms;
    FitResults.eRmsRatio = eRmsRatio;
    FitResults.SNDRold = SNDRold;
    FitResults.SNDR = SNDR;
    FitResults.SNDRold_peak = SNDRold_peak;
    FitResults.SNR_ISI = SNR_ISI;
    FitResults.e=e;
    FitResults.l = l;
    FitResults.p = p;
    FitResults.w = w;
    FitResults.P3 = P3;
    FitResults.pSampled = pSampled;
    FitResults.xp = xp;
    FitResults.nyquist_loss = nyquist_loss;
    FitResults.nyquist_loss_inner = nyquist_loss_inner;
    FitResults.timebase = timebase - timebaseSampled(1);
    FitResults.timebaseSampled = timebaseSampled-timebaseSampled(1);
end
