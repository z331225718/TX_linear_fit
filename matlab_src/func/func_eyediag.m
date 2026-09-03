function [] = func_eyediag(data,settle_ui,Delay,OSR,data_rate,Tsym,signal_type,saturation,cmap,figname,fignum)

% eyescope(data4eye,OSR,Tsym,Delay,fignum,cmap,saturation);
%
% M-file to plotting eye diagram with persistence
%
% data4eye: input data vector
% OSR: oversampling rate = number of samples/symbol
% Tsym: symbol period
% Delay:Delay amount that you can use to adjust the center of the eye
% fignum: figure number
% cmap: colormap
% saturation: saturation of the color

    data4eye = data(settle_ui*OSR:end);
    max_x4 = ceil(60*max(data4eye))/60;
    min_x4 = floor(60*min(data4eye))/60;
    hvec = [min_x4:0.001:max_x4];
    LEN = length(data4eye);

    % implement Delay function
    delsamples = Delay;
    if delsamples>0
        data4eye = [data4eye(end-delsamples+1:end) data4eye(1:end-delsamples)];
    end
    
    OSRup = 1/(round(320/OSR));
    OSRact = OSR/OSRup;
    npieces = ceil(LEN/(32*10000*(10*OSRup)));

    Nsize = floor(LEN/npieces);
    Nsize = OSRact*floor(Nsize/OSRact);
    N = zeros(length(hvec),OSR/OSRup);

    %do interpolation and histogramming in pieces to avoid memory faults

    for i=1:npieces
        data4eye_3 = interp1([1:Nsize],data4eye((1:Nsize)+Nsize*(i-1)),[1:OSRup:Nsize],'*linear');

        for k = 1:OSR/OSRup
            N(:,k) = N(:,k)+hist(data4eye_3(k:OSR/OSRup:end),hvec)';
        end
    end

    if exist('fignum','var')
        figure(fignum);clf;
    else
        figure;clf;
    end

    r=1;g=2;b=3;
    if ~exist('cmap','var')
        cmap = 'color';
    end
    if strcmp(cmap,'color')
        map_color = zeros(256,3);
        map_color(1,r)=1;
        map_color(1,g)=1;
        map_color(1,b)=1;
        
        map_color(2:4,r) = 0;
        map_color(2:4,g) = 0.4;
        map_color(2:4,b) = 0;

        map_color(5:8,r) = 0;
        map_color(5:8,g) = 0;
        map_color(5:8,b) = 1;

        map_color(9:20,r) = 1;
        map_color(9:20,g) = 0;
        map_color(9:20,b) = 1;

        map_color(21:36,r) = 1;
        map_color(21:36,g) = 0;
        map_color(21:36,b) = 0;

        map_color(37:64,r) = 1;
        map_color(37:64,g) = 0.5;
        map_color(37:64,b) = 0;

        map_color(65:128,r) = 1;
        map_color(65:128,g) = 1;
        map_color(65:128,b) = 0;

        map_color(129:256,r) = 1;
        map_color(129:256,g) = 1;
        map_color(129:256,b) = 1;
        colormap(map_color);
    
        [Nrows,Ncols] = size(N);
        image(Tsym*(-0.5+[0:Ncols-1]/(Ncols-1)),hvec,0+ceil(N/max(max(N))*saturation*256));
        set(gca,'YDir','normal');
        grid on;
        xlabel('Time (UI)');
        ylabel('Amplitude (V)');

        if exist('intitle','var')
            if ischar(intitle)
                title(intitle);
            end
        end
    end
end
    
