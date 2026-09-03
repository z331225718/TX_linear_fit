function [Results] = calcRLM(normalizedConstellation)

    % Basic definition used in common Xilinx guides

    slice_p=2/3;
    slice_z = 0;
    slice_n = -slice_p;

    V3 = mean(normalizedConstellation(normalizedConstellation>slice_p));
    V2 = normalizedConstellation(normalizedConstellation>slice_z)
    V2 = mean(V2(V2<slice_p));
    V1 = normalizedConstellation(normalizedConstellation<slice_z)
    V1 = mean(V1(V1>slice_n));
    V0 = mean(normalizedConstellation(normalizedConstellation<slice_n));

    Results.V3 = V3;    
    Results.V2 = V2;
    Results.V1 = V1;
    Results.V0 = V0;
    Results.RLMbj = 3*min([V3-V2,V2-V1,V1-V0])/(V3-V0);

    Results.swingScale = (V3-V0)/(V2-V1);

    %IEEE 802.3bs spec, page 335
    Vmid = (V0+V3)/2;
    ES1 = (V1-Vmid)/(V0-Vmid);
    ES2 = (V2-Vmid)/(V3-Vmid);

    Results.RLMbs = min([3*ES1 3*ES2 (2-3*ES1) (2-3*ES2)]);
end
