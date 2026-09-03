function [output_vec] = process_input_f(data)
arguments
    data.lab_txt_data_filename = []
    data.lab_csv_data_filename = []
    data.lab_noise_data_filename = []
    data.lab_noise_data_branches = []
end

if(~isempty(data.lab_txt_data_filename))
    % Process lab_txt_data_filename
    fid = fopen(data.lab_txt_data_filename, 'r');
    i=1;
    tline = fgetl(fid);
    A{i} = tline;
    found_data_line =0;
    data_index = 1;
    time_vec = [];
    data_vec = [];
    while ischar(tline)
        i = i+1;
        tline = fgetl(fid);
        A{i} = tline;
        if(found_data_line == 1 && ~isempty(tline) && strcmp(tline,'-1')~=1)
            try
                time_vec(data_index) = str2num(extractBefore(A{i},','));
                data_vec(data_index) = str2num(extractAfter(A{i},','));
                data_index = data_index+1;
            catch
            end
        end

        if (strcmp(tline,'Data, '))
            found_data_line = 1;
        end

    end
    fclose(fid);

    %shift time vector to initial one to have 0 time
    output_vec.time_vec = time_vec-time_vec(1);
    output_vec.data_vec = data_vec;
end

if(~isempty(data.lab_csv_data_filename))
    % Process lab_csv_data_filename
    fid = fopen(data.lab_csv_data_filename, 'r');
    i=1;
    tline = fgetl(fid);
    A{i} = tline;
    found_data_line =0;
    data_index = 1;
    time_vec = [];
    data_vec = [];
    while ischar(tline)
        i = i+1;
        tline = fgetl(fid);
        A{i} = tline;
        if(found_data_line == 1 && ~isempty(tline) && strcmp(tline,'-1')~=1)
            try
                data_vec(data_index) = str2num(A{i});
                data_index = data_index+1;
            catch
            end
        end

        if (strcmp(tline,'Data, '))
            found_data_line = 1;
        end
    end
    fclose(fid);

    %shift time vector to initial one to have 0 time
    output_vec.time_vec =[];
    output_vec.data_vec = data_vec;
end

if(~isempty(data.lab_noise_data_filename))
    % Process lab_noise_data_filename
    noise_data = dlmread(data.lab_noise_data_filename);
    noise_data = nosie_data(:,1:data.lab_noise_data_branches);
    output_vec.data_vec = noise_data;
end
end