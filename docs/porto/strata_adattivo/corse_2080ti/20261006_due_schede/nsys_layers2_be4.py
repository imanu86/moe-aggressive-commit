import sqlite3, collections, statistics as st
c=sqlite3.connect(r'D:\ds4_work\strata\nsys_dual_be4.sqlite')
names={i:v for i,v in c.execute("select id,value from StringIds")}
for dev in (0,1):
    ks=c.execute("select start,end,shortName from CUPTI_ACTIVITY_KIND_KERNEL where deviceId=? order by start",(dev,)).fetchall()
    bursts=[];cur=[ks[0]];mx=ks[0][1]
    for k in ks[1:]:
        if k[0]-mx>300_000: bursts.append(cur);cur=[]
        cur.append(k);mx=max(mx,k[1])
    bursts.append(cur)
    win=[b for b in bursts if (700<=len(b)<800 if dev==0 else 1300<=len(b)<1700)]
    A={t:collections.defaultdict(float) for t in ('GDN','QSA')}; N=collections.Counter()
    for b in win:
        # sweep: elementary time slices labelled idle / wait-only / kernel
        ev=[]
        for i,k in enumerate(b):
            w=names[k[2]]=='wait_flag_ge_kernel'
            ev.append((k[0],1,w,i)); ev.append((k[1],-1,w,i))
        ev.sort(key=lambda e:(e[0],-e[1]))
        # layer index of each kernel
        lid=[];l=0
        for k in b:
            lid.append(l)
            if names[k[2]]=='combine_k10_vec4': l+=1
        nl=l
        typ=['GDN']*(nl+1)
        for i,k in enumerate(b):
            if names[k[2]]=='attn_chunk_kernel': typ[lid[i]]='QSA'
        act=0;actw=0;t=ev[0][0];lastl=0
        for (x,d,w,i) in ev:
            dt=x-t
            if dt>0 and 1<=lastl<nl:   # skip prelude layer 0 and the tail after the last layer
                cat='idle' if act==0 else ('wait' if act==actw else 'kernel')
                A[typ[lastl]][cat]+=dt
            t=x
            if d>0: act+=1; actw+=w; lastl=lid[i]
            else: act-=1; actw-=w
        for L in range(1,nl): N[typ[L]]+=1
    for ty in ('GDN','QSA'):
        a=A[ty];n=N[ty];tot=sum(a.values())
        print(f"dev{dev} {ty}: {n} layers, wall {tot/n/1e3:.1f} us = kernel {a['kernel']/n/1e3:.1f} ({a['kernel']/tot*100:.0f}%) + idle {a['idle']/n/1e3:.1f} ({a['idle']/tot*100:.1f}%) + flag-wait-only {a['wait']/n/1e3:.1f} ({a['wait']/tot*100:.1f}%)")
