function [eye_x_opening,min_eye_y_opening,max_eye_y_opening,eye_mid_index,eye_y_opening_ratio,fig_handle,ax] = calc_eye_info_f(x1,OSR,Tbaud,settle_ui,figname,fignum1,Config)
    
    max_len = 5e4;
    x1 = x1(1:min(max_len,length(x1)));

    data_rate = 1/Tbaud;
    eyediag_size=2;

    num_x1 = length(x1);
    x =x1(settle_ui*OSR:end);

    L = length(x);
    num_ui = floor(L/OSR)-5;
    if (num_ui<1) error(['Error :No data to analyze in eye-diagram after clipping! Review clipping settings or run-length of data!']);
    end

    t = 0:1/OSR:(eyediag_size-1/OSR);

    %Initializze vectors

    txeye = zeros(num_ui,eyediag_size*OSR);
    cdr_eye = zeros(num_ui,eyediag_size*OSR);
    
    for k = 1:1:num_ui
        txeye(k,:) = x(round(k*OSR):round((k+eyediag_size)*OSR-1));
    end

    %%%%%%% Determines Zero Crossings %%%%%%%%%%%%%
    txcross = diff(sign(txeye)')';
    mat_dem = size(txcross);
    
    num_eye_wraps = mat_dem(1);
    num_eye_pts_per_wrap = mat_dem(2);

    for i =1:1:num_eye_pts_per_wrap
        txhist(i) = sum(abs(txcross(:,i)/2));
    end

    csvwrite('txcross.csv',txcross);
    csvwrite('txhist.csv',txhist);

    %%%%%%%% Calculate eye opening %%%%%%%%%%
    found_zero = 0;
    count_zero = 0;
    index_zero_start = 0;
    index_zero_end = 0;
    count_zero_max = 0;
    t2 = 0;
    t1=0;

    for i=1:1:num_eye_pts_per_wrap
        if(txhist(i)==0)
            if(found_zero==0)
            index_zero_start=i;
            end
            found_zero=1;
            count_zero=count_zero+1;
        else
            if (found_zero==1)
                index_zero_end=i;
            end
            found_zero=0;
            if(count_zero>count_zero_max)
                    count_zero_max=count_zero;
                    t2=index_zero_end;
                    t1 = index_zero_start;
            end
            count_zero=0;
        end
    end
    if(t1==0 && t2==0) 
        t1=floor(num_eye_pts_per_wrap/2);
        t2 = floor(num_eye_pts_per_wrap/2)+1;
    end
    eye_x_opening=eyediag_size*(t2-t1)/num_eye_pts_per_wrap;

    %%%%%% Calculate eye height
    eye_mid_index = floor((t2+t1)/2);
    min_eye_y_opening = 2*min(abs(txeye(:,eye_mid_index)));
    max_eye_y_opening = 2*max(abs(txeye(:,eye_mid_index)));
    eye_y_opening_ratio = max_eye_y_opening/min_eye_y_opening;


    %%%%% Plot Eye Diagram

    if(eye_mid_index>num_eye_pts_per_wrap/2)
        eyediag_offset = floor(eye_mid_index-num_eye_pts_per_wrap/2);
    else
        eyediag_offset = floor(num_eye_pts_per_wrap+eye_mid_index-num_eye_pts_per_wrap/2);
    end

    for k =1:1:num_ui
        cdr_eye(k,:) = x(k*OSR+eyediag_offset:(k+eyediag_size)*OSR+eyediag_offset-1);
    end

    str_data_rate = num2str(1/(Tbaud)/1e9*2,'%3.3g');
    text1 = [str_data_rate,'Gbps'];

