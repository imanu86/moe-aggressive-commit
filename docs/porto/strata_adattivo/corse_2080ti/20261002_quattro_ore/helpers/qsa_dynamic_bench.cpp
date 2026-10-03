// Replay unchanged graphs across the live-register boundary and compare every selected ID.
#include "strata/kernels/qsa.hpp"
#include "strata/kernels/qsa_select.hpp"
#include <cuda_runtime.h>
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <random>
#include <vector>
namespace k = strata::kernels;
void ck(cudaError_t e) { if(e!=cudaSuccess){std::fprintf(stderr,"CUDA: %s\n",cudaGetErrorString(e));std::exit(2);} }
struct Graph {
    cudaGraph_t g{}; cudaGraphExec_t exec{};
    ~Graph(){if(exec)cudaGraphExecDestroy(exec);if(g)cudaGraphDestroy(g);}
};
int main(){
    int count=0; if(cudaGetDeviceCount(&count)!=cudaSuccess||!count){std::puts("SKIP no CUDA");return 77;}
    cudaDeviceProp prop{};ck(cudaGetDeviceProperties(&prop,0));
    if(prop.major!=7||prop.minor!=5){std::puts("SKIP requires real sm75");return 77;}
    const char* enabled=std::getenv("STRATA_TOPK_DYNAMIC");
    if(!enabled||std::atoi(enabled)!=1){std::fputs("Requires STRATA_TOPK_DYNAMIC=1\n",stderr);return 2;}
    constexpr int64_t stride=262144/4+2,maxq=11;
    const auto shape=k::qsa_real_shapes();const int64_t cap=k::qsa_selection_width(k::kTopkMaxCells,shape);
    float* ds{};int32_t *dt{},*da{},*db{};cudaStream_t stream{};
    ck(cudaStreamCreate(&stream));ck(cudaMalloc(&ds,maxq*stride*sizeof(float)));
    ck(cudaMalloc(&dt,maxq*k::kStepCount*sizeof(int32_t)));
    ck(cudaMalloc(&da,maxq*cap*sizeof(int32_t)));ck(cudaMalloc(&db,maxq*cap*sizeof(int32_t)));
    std::vector<float> scores(maxq*stride);std::vector<int32_t> steps(maxq*k::kStepCount),a(maxq*cap),b(maxq*cap);
    auto fill=[&](int64_t ctx,int64_t nq,int mode,bool mixed){
        std::fill(scores.begin(),scores.end(),-999.f);std::fill(steps.begin(),steps.end(),0);
        std::mt19937 rng(742913);std::uniform_real_distribution<float> random(0.f,200.f);
        for(int64_t q=0;q<nq;++q){
            int64_t pos=ctx-nq+q;if(mixed)pos=(q%2?250021:131071);
            auto* st=steps.data()+q*k::kStepCount;st[k::kStepPos]=(int32_t)pos;
            st[k::kStepNKv]=(int32_t)(pos+1);st[k::kStepNBid]=(int32_t)((pos+1)/shape.idx_block);
            st[k::kStepWidth]=(int32_t)k::qsa_selection_width(pos+1,shape);
            for(int64_t j=0;j<=st[k::kStepNBid];++j)scores[q*stride+j]=mode==1?0.f:mode==2?float(j%7):random(rng);
            if((pos+1)%shape.idx_block)scores[q*stride+st[k::kStepNBid]]+=1e9f;
        }
        ck(cudaMemcpyAsync(ds,scores.data(),scores.size()*sizeof(float),cudaMemcpyHostToDevice,stream));
        ck(cudaMemcpyAsync(dt,steps.data(),steps.size()*sizeof(int32_t),cudaMemcpyHostToDevice,stream));
        ck(cudaStreamSynchronize(stream));
    };
    int cases=0;
    for(int64_t nq:{1,2,3,4,6,8,11}){
        fill(131072,nq,0,false);
        // Prime the device-query caches before capture; each graph keeps the same pointers and dimensions.
        k::qsa_block_topk(ds,dt,nq,stride,cap,shape,db,stream);ck(cudaStreamSynchronize(stream));
        Graph ref,dyn;
        ck(cudaStreamBeginCapture(stream,cudaStreamCaptureModeGlobal));
        k::qsa_block_topk_ref(ds,dt,nq,stride,cap,shape,da,stream);
        ck(cudaStreamEndCapture(stream,&ref.g));ck(cudaGraphInstantiate(&ref.exec,ref.g,nullptr,nullptr,0));
        ck(cudaStreamBeginCapture(stream,cudaStreamCaptureModeGlobal));
        k::qsa_block_topk(ds,dt,nq,stride,cap,shape,db,stream);
        ck(cudaStreamEndCapture(stream,&dyn.g));ck(cudaGraphInstantiate(&dyn.exec,dyn.g,nullptr,nullptr,0));
        size_t nodes=0;ck(cudaGraphGetNodes(dyn.g,nullptr,&nodes));
        if(nodes!=2){std::fprintf(stderr,"FAIL dynamic graph has %zu nodes, expected two guarded kernels\n",nodes);return 1;}
        std::printf("GRAPH nq=%lld dynamic_nodes=%zu\n",(long long)nq,nodes);
        auto check=[&](int64_t ctx,int mode,bool mixed){
            fill(ctx,nq,mode,mixed);
            ck(cudaMemsetAsync(da,0xcc,a.size()*sizeof(int32_t),stream));ck(cudaMemsetAsync(db,0x55,b.size()*sizeof(int32_t),stream));
            ck(cudaGraphLaunch(ref.exec,stream));ck(cudaGraphLaunch(dyn.exec,stream));ck(cudaStreamSynchronize(stream));
            ck(cudaMemcpy(a.data(),da,a.size()*sizeof(int32_t),cudaMemcpyDeviceToHost));
            ck(cudaMemcpy(b.data(),db,b.size()*sizeof(int32_t),cudaMemcpyDeviceToHost));
            for(int64_t q=0;q<nq;++q){
                const int width=steps[q*k::kStepCount+k::kStepWidth],nkv=steps[q*k::kStepCount+k::kStepNKv];
                for(int i=0;i<width;++i)if(a[q*cap+i]!=b[q*cap+i]||b[q*cap+i]<0||b[q*cap+i]>=nkv){
                    std::fprintf(stderr,"FAIL ctx=%lld nq=%lld mode=%d mixed=%d q=%lld id=%d ref=%d dyn=%d\n",(long long)ctx,(long long)nq,mode,int(mixed),(long long)q,i,a[q*cap+i],b[q*cap+i]);std::exit(1);
                }
            }
            ++cases;std::printf("PARITY ctx=%lld nq=%lld mode=%d mixed=%d bitwise\n",(long long)ctx,(long long)nq,mode,int(mixed));
        };
        for(int64_t ctx:{1111,8192,32768,65536,131072,135164,135168,135172,250022,262144})for(int mode=0;mode<3;++mode)check(ctx,mode,false);
        if(nq>1)for(int mode=0;mode<3;++mode)check(250022,mode,true);
        if(nq!=1 && nq!=8)continue;
        cudaEvent_t e0{},e1{};ck(cudaEventCreate(&e0));ck(cudaEventCreate(&e1));
        auto time=[&](Graph& g){
            ck(cudaEventRecord(e0,stream));for(int i=0;i<50;++i)ck(cudaGraphLaunch(g.exec,stream));
            ck(cudaEventRecord(e1,stream));ck(cudaEventSynchronize(e1));float ms{};ck(cudaEventElapsedTime(&ms,e0,e1));return double(ms)*1000/50;
        };
        for(int64_t ctx:{20000,65536,131072,250022}){
            fill(ctx,nq,0,false);for(int i=0;i<10;++i){ck(cudaGraphLaunch(ref.exec,stream));ck(cudaGraphLaunch(dyn.exec,stream));}ck(cudaStreamSynchronize(stream));
            for(int rep=0;rep<3;++rep){double a1=time(ref),d=time(dyn),a2=time(ref);
                std::printf("TIMING ctx=%lld nq=%lld rep=%d ref1_us=%.3f dynamic_us=%.3f ref2_us=%.3f\n",(long long)ctx,(long long)nq,rep,a1,d,a2);
            }
        }
        ck(cudaEventDestroy(e0));ck(cudaEventDestroy(e1));
    }
    ck(cudaFree(ds));ck(cudaFree(dt));ck(cudaFree(da));ck(cudaFree(db));ck(cudaStreamDestroy(stream));
    std::printf("PASS %d captured-replay cases, selected IDs bitwise; capacity262144 including mixed boundaries\n",cases);
    return 0;
}
