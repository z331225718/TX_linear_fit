function seq = func_prbs(s,t,num_smpls)
    % z = prbs(init,g)
    %2^n-1 bit PRBS based on initial string 'init'
    %and polynomial represented by vector g (e.g. g=[7,1] =>x^7+x+1).

    n = length(s);
    lim = min(2^n-2,num_smpls+1);
    if (lim>2^23)
        lim= 2^23;
    end

    c=zeros(lim,n);
    c(1,:)=s;
    m=length(t);
    for k=1:lim
        b(1) = xor(s(t(1)),s(t(2)));
        if m>2
            for i=1:m-2
                b(i+1) = xor(s(t(i+2)),b(i));
            end
        end
        j = 1:n-1;
        s(n+1-j) = s(n-j);
        s(1) = b(m-1);
        c(k+1,:)=s;
    end
    seq = c(:,n)';