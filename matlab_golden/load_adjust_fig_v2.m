function sfh = load_adjust_fig_v2(image_path,sfh,xsize,xshift,top_row_yshift,ysize_max)
% GOLDEN FIX: renamed to match the file name (MATLAB dispatches by file name)
image_loaded = imread(image_path);
image_loaded_size =size(image_loaded);
aspect_ratio = image_loaded_size(2)/image_loaded_size(1);
sfh.Position(1) = xshift;
sfh.Position(2) = sfh.Position(2)+top_row_yshift;
sfh.Position(3) = xsize;
sfh.Position(4) = sfh.Position(3)/aspect_ratio;
yshift_center = (ysize_max-sfh.Position(4))/2;
sfh.Position = sfh.Position + [0 yshift_center 0 0];

image(image_loaded);
axis off
end
