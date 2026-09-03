function probe1()
% S0 probe: pin down MATLAB semantics needed for exact Python port
NL = char(10);
disp('=== P1 xcorr unequal lengths ===');
a = [1 2 3 4]; b = [0.5 1.5 2.5];
[d, lag] = xcorr(a,b);
fprintf(['len(d)=%d len(lag)=%d' NL], numel(d), numel(lag));
for k=1:numel(d)
  fprintf(['%2d: d=% .12f lag=% d' NL], k, d(k), lag(k));
end
disp('=== P2 xcorr equal lengths ===');
c2 = xcorr(a,a);
fprintf(['len=%d first=%g center=%g last=%g' NL], numel(c2), c2(1), c2(4), c2(7));
disp('=== P3 xcorr unequal (longer first) ===');
[d2, lag2] = xcorr(b,a);
for k=1:numel(d2)
  fprintf(['%2d: d=% .12f lag=% d' NL], k, d2(k), lag2(k));
end
disp('=== P4 extractBefore empty pattern ===');
s='Unequalized Eye Diagram';
try
  r = extractBefore(s,'');
  fprintf(['ok len=%d text=[%s]' NL], numel(r), r);
catch e
  fprintf(['ERROR %s' NL], e.message);
end
disp('=== P5 freqz default 512 ===');
[h,w]=freqz([1 2 1],1);
fprintf(['n=%d w1=%.12g w2=%.12g wend=%.12g wprev=%.12g' NL], numel(w), w(1), w(2), w(end), w(end-1));
disp('=== P6 hist with centers + outliers ===');
x=[0.0012 0.0018 0.0021 0.0029 0.0032 0.005 1.5 -0.3 0.001 0.0020001 0.0030001];
hvec=0.001:0.001:0.006;
c=hist(x,hvec);
fprintf(['centers: %s' NL], num2str(hvec,'%.3f '));
fprintf(['counts : %s' NL], num2str(c));
disp('=== P7 csvwrite format ===');
if exist('csvwrite','file')
  csvwrite('verification/probe_csvtest.csv',[1.5 -2.25; 0 3.333333333333333e-5; 7 8]);
else
  disp('csvwrite NOT available');
end
disp('=== P8 interp1 spline (evaluate) ===');
t=0:0.1:1; y=sin(2*t)+0.1*cos(5*t); tq=0.05:0.1:0.95;
yi=interp1(t,y,tq,'spline');
fprintf(['%0.17g' NL], yi);
disp('=== P9 interp1 linear extrap default ===');
fprintf(['oob=%.6g oob2=%.6g' NL], interp1([0 1],[0 1],2), interp1([0 1],[0 1],-0.5));
disp('=== P10 round / rem ===');
fprintf(['round(2.5)=%d round(3.5)=%d round(-2.5)=%d round(0.5)=%d' NL], round(2.5), round(3.5), round(-2.5), round(0.5));
fprintf(['rem(8,3)=%d rem(6,3)=%d rem(3,8)=%d' NL], rem(8,3), rem(6,3), rem(3,8));
disp('=== P11 jsonencode ===');
disp(jsonencode(struct('a',1.234567890123456e-5,'v',[1 2 3],'nan',NaN,'inf',Inf)));
disp('=== P12 filter ref ===');
fprintf(['f=%0.17g,%0.17g,%0.17g' NL], filter([1 -0.5],1,[1 2 3 4]));
disp('=== P13 rms ===');
fprintf(['rms=%0.17g' NL], rms([1 2 3]));
disp('=== P14 str2num variants ===');
fprintf(['a=%.6g b=%.6g c=%.6g d=%.6g e=%.6g' NL], str2num(' 1.5'), str2num('1.5 '), str2num('-1'), str2num(' 1.2e-3, 2.3'), str2num('0.001015625'));
disp('=== P16 xcorr lengths: L20xL12 and L12xL20 ===');
rng(1); x1 = randn(20,1); x2 = randn(12,1);
[d3, lag3] = xcorr(x1, x2);
fprintf(['L20xL12 -> len=%d firstlag=%d' NL], numel(d3), lag3(1));
[d4, lag4] = xcorr(x2, x1);
fprintf(['L12xL20 -> len=%d firstlag=%d' NL], numel(d4), lag4(1));
[nn,ll] = xcorr(x1,x2,12);
fprintf(['maxlag=12 -> len=%d' NL], numel(nn));
disp('=== P17 max ties index ===');
mx = [1 2 2];
fprintf(['max idx=%d' NL], find(mx==max(mx),1));
disp('=== P18 reshape column-major sanity ===');
fprintf(['r=%s' NL], num2str(reshape(1:6,2,3),'%d '));
disp('DONE');
end
