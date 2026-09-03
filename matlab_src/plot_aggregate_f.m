function plot_aggregate_f(input_file_vec,num_of_row,num_of_col,output_path,options)
    arguments
        input_files_vec
        num_of_row
        num_of_col
        output_path
        options.fig_loc
    end

    if(num_of_col ==4)
        width_tot =1720;
        xshift = 20 + [0 width_tot/4 width_tot/2 width_tot/4*3]
    elseif(num_of_col ==3)
        width_tot =1300;
        xshift = 20 + [0 width_tot/3 width_tot/3*2];
    elseif(num_of_col ==2)
        width_tot =860;
        xshift = 20 + [0 width_tot/2]; 
    end

    xsize = 400;
    height_tot_temp = 0;
    i=1;
    for idx_row = 1:num_of_row
        for idx_col = 1:num_of_col
            image_loaded = imread(input_files_vec{i});
            image_loaded_size = size(image_loaded);
            aspect_ratio = image_loaded_size(2)/image_loaded_size(1);
            if (xsize/aspect_ratio>height_tot_temp)
                height_tot_temp = xsize/aspect_ratio;
            end
            i = i+1;
        end
    end

    height_tot = round(height_tot_temp*2.23);
    row_yshift = [-40 -40];
    ysize_max = height_tot_temp;

    if isfield(options,"fig_loc")
        fh1 = figure('units','pixel','Position',[options.fig_loc width_tot height_tot]);
    else
        fh1 = figure('units','pixel','Position',[0 100 width_tot height_tot]);
    end
    
    i=1;
    for idx_row = 1:num_of_row
        for idx_col = 1:num_of_col
            sfh_temp = subplot(num_of_row,num_of_col,i,'Parent',fh1,'units','pixel');
            sfh_temp = load_adjust_fig_v2_f(input_files_vec{i},sfh_temp,xsize,xshift(idx_col),row_yshift(idx_row),ysize_max);
            i = i+1;
        end
    end
    
    f = gcf;
    exportgraphics(f,output_path,'Resolution',500);
end