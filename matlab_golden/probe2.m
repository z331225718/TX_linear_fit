function probe2()
NL = char(10);
fprintf(['min([1 NaN 3]) = %g' NL], min([1 NaN 3]));
fprintf(['min([NaN 1.001]) = %g' NL], min([NaN 1.001]));
fprintf(['mean([]) = %g' NL], mean([]));
x = 2*randn(1,1000);
% empty band example like NRZ (no samples in (0, 2/3))
v2 = x(x>0); v2 = mean(v2(v2<2/3));
fprintf(['v2 partial = %g' NL], v2);
r = min([1-v2, v2-(-0.333), 0.5]);
fprintf(['min result = %g' NL], r);
disp('probe2 done');
end
