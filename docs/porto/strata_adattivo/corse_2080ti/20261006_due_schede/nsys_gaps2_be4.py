import sqlite3, collections, statistics as st
c=sqlite3.connect(r'D:\ds4_work\strata\nsys_dual_be4.sqlite')
names={i:v for i,v in c.execute("select id,value from StringIds")}
for dev in (0,1):
    ks=c.execute("select start,end,shortName,streamId from CUPTI_ACTIVITY_KIND_KERNEL where deviceId=? order by start",(dev,)).fetchall()
    bursts=[];cur=[ks[0]];mx=ks[0][1]
    for k in ks[1:]:
        if k[0]-mx>300_000: bursts.append(cur);cur=[]
        cur.append(k);mx=max(mx,k[1])
    bursts.append(cur)
    win=[b for b in bursts if (700<=len(b)<800 if dev==0 else 1300<=len(b)<1700)]
    gapby=collections.Counter(); gapn=collections.Counter()
    small_t=[];small_n=[];all_t=[]
    hist=collections.Counter()
    for b in win:
        # device-level idle gaps (nothing running), attributed to (prev ending kernel -> next kernel)
        mx=b[0][1]; prevk=b[0]
        for k in b[1:]:
            if k[0]>mx:
                g=k[0]-mx
                hist[min(int(g/1000),20)]+=1
                gapby[(names[prevk[2]],names[k[2]])]+=g; gapn[(names[prevk[2]],names[k[2]])]+=1
            if k[1]>=mx: mx=k[1]; prevk=k
        d=[k[1]-k[0] for k in b if names[k[2]]!='wait_flag_ge_kernel']
        small=[x for x in d if x<5000]
        small_t.append(sum(small)); small_n.append(len(small)); all_t.append(sum(d))
    nw=len(win)
    print(f"\n== dev{dev}: idle gaps per window by (prev->next), us/window:")
    for kk,v in gapby.most_common(12): print(f"   {v/nw/1e3:7.1f} us  n/win {gapn[kk]/nw:5.1f}  {kk[0]} -> {kk[1]}")
    print("  gap size hist (us bucket: count/window):", {k:round(v/nw,1) for k,v in sorted(hist.items())})
    print(f"  kernels <5us (non-wait): {st.mean(small_n):.0f}/window, sum {st.mean(small_t)/1e3:.0f} us; all non-wait kernel time (sum, not union) {st.mean(all_t)/1e3:.0f} us")
