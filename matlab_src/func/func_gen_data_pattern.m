% origin_ddata -origin pre-FEC data
% ddata -FEC encoded data
% txdata- TX FEC encoded data

function [origin_ddata,ddata,txdata]=func_gen_data_pattern(data_pattern,signal_type,seed_type,num_symbols,fec_ena,fec_mode)

% Determine number of bits to generate
if (strcmp(signal_type,'PAM4')==1)
    num_bits = 2*num_symbols;
else
    num_bits = num_symbols;
end

% Clock,Half-Clock,Random,PRBS7,PRBS9,PRBS12,PRBS15,PRBS23,PRBS31
if (strcmp(data_pattern,'Clock')==1)
    count = 1:num_bits;
    data = rem(count,2);
elseif (strcmp(data_pattern,'Half-Clock')==1)
    count = 1:num_bits;
    data = floor(rem(count,4)/2);
elseif (strcmp(data_pattern,'PRBS7')==1)
    seed = [1 0 0 0 0 0 1]
    poly = [7 6];
    data = [func_prbs(seed,poly,num_bits) 0];
    data = data(1:end-1);

    %Random circular shift to change the pattern
    if (strcmp(seed_type,'random')==1)
        data = circshift(data,floor(rand*num_bits));
    end
elseif (strcmp(data_pattern,'PRBS9')==1)
    seed = [1 0 0 0 0 0 0 0 1];
    poly = [9 5];
    data = [func_prbs(seed,poly,num_bits) 0];
    data = data(1:end-1);
    
    %Random circular shift to change the pattern
    if (strcmp(seed_type,'random')==1)
        data = circshift(data,floor(rand*num_bits));
    end
    
elseif (strcmp(data_pattern,'PRBS11')==1)
    seed = [1 0 0 0 0 0 0 0 0 0 1];
    poly = [11 9];
    data = [func_prbs(seed,poly,num_bits) 0];
    data = data(1:end-1);
    
    %Random circular shift to change the pattern
    if (strcmp(seed_type,'random')==1)
        data = circshift(data,floor(rand*num_bits));
    end
elseif (strcmp(data_pattern,'PRBS13')==1)
    seed = [1 0 0 0 0 0 0 0 0 0 0 0 1];
    poly = [13 12 2 1];
    data = [func_prbs(seed,poly,num_bits) 0];
    data = data(1:end-1);
    
    %Random circular shift to change the pattern
    if (strcmp(seed_type,'random')==1)
        data = circshift(data,floor(rand*num_bits));
    end
elseif (strcmp(data_pattern,'PRBS15')==1)
    seed = [1 0 0 0 0 0 0 0 0 0 0 0 0 0 1];
    poly = [15,14];
    data = [func_prbs(seed,poly,num_bits) 0];
    data = data(1:end-1);
    
    %Random circular shift to change the pattern
    if (strcmp(seed_type,'random')==1)
        data = circshift(data,floor(rand*num_bits));    
    end
elseif (strcmp(data_pattern,'PRBS23')==1)
    seed = [1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 1];
    poly = [23 18];
    data = [func_prbs(seed,poly,num_bits) 0];
    data = data(1:end-1);
    
    %Random circular shift to change the pattern    
    if (strcmp(seed_type,'random')==1)
        data = circshift(data,floor(rand*num_bits));
    end
    
elseif (strcmp(data_pattern,'PRBS31')==1)
    seed = [1 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 1]
    poly = [31 28];
    data = [func_prbs(seed,poly,num_bits) 0];
    data = data(1:end-1);
    
    %Random circular shift to change the pattern
    if (strcmp(seed_type,'random')==1)
        data = circshift(data,floor(rand*num_bits));    
    end
    
elseif (strcmp(data_pattern,'Random')==1)
    data = rand(1,num_bits);
    data = sign(data-0.5)/2;
    data = data+0.5;
else
    error('Invalid data pattern');
    return;
end

%repeat the data to achieve num_bits
data_out = data;
for ii = 1:1:floor(num_bits/length(data))-1
    data_out = [data_out data];
end

%compute the missing number of wraps required to always send in enough FEC
%blocks to satisfy num_symbols
if (fec_ena ==1)
    if(strcmp(fec_mode,'KR4')==1|| strcmp(fec_mode,'KP4')==1)
        additional_bits_for_whole_fec_blocks = mod(length(data_out),5140);
        additional_prbs_repeats_for_whole_fec_blocks = ceil(additional_bits_for_whole_fec_blocks/length(data));
    end
else
    additional_bits_for_whole_fec_blocks = 0;
    additional_prbs_repeats_for_whole_fec_blocks = 0;
end
% Add additional prbs pattern to ensure whole FEC block
for ii=1:1:additional_prbs_repeats_for_whole_fec_blocks
    data_out = [data_out data];
end

%reassign data to data_out
data=data_out;

% Set orgin_ddata
origin_ddata = [zeros(1,num_bits-length(data)) data];

%%%
%%% FEC Encode if Enabled
%%%
if (fec_ena ==1)
    [encoded_data,num_tx_encoded_bits] = func_fec_encode(fec_mode,data);

else
    % no fec ,assign to original sig_tx
    encoded_data = data;
    
end

if (strcmp(signal_type,'PAM4')==1)
    tdata(1:round(length(encoded_data)/2))=0
    % Encode binary signal to PAM4 levels
    for i=1:2:length(encoded_data)-1
        if(encoded_data(i:i+1)==[1 0])
            tdata(ceil(i/2))=+1;
        elseif(encoded_data(i:i+1)==[1 1])
            tdata(ceil(i/2))=+1/3;
        elseif(encoded_data(i:i+1)==[0 1])
            tdata(ceil(i/2))=-1/3;
        elseif(encoded_data(i:i+1)==[0 0])
            tdata(ceil(i/2))=-1;
        end
    end
elseif (strcmp(signal_type,'NRZ')==1)
    tdata = 2*(encoded_data-0.5);
else
    error('Invalid Signal Type Entered');
    return;
end

% Repeat pattern to meet total desired number of symbols
if(num_symbols<=length(tdata))
    txdata = tdata(1:num_symbols);
else
    txdata=tdata;
    for i = 1:1:floor(num_symbols/length(tdata))-1
        txdata = [txdata tdata];
    end
    if (num_symbols>length(txdata))
        txdata(end+1:end+(num_symbols-length(txdata)))=tdata(1:(num_symbols-length(txdata)));
    end
end

%Repeat pattern to meet total desired number of symbols
if(num_bits<=length(data))
    ddata = encoded_data(1:num_bits);
else
    ddata = data;
    for i=1:1:floor(num_bits/length(data))-1
        ddata = [ddata encoded_data];
    end
    if (num_bits>length(encoded_data))
        ddata(end+1:end+(num_bits-length(data)))=encoded_data(1:(num_bits-length(encoded_data)));
        
    end
end

end

