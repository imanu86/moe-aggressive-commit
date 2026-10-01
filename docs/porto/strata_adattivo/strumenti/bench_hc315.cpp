// Tempi HC per variante, con geometria reale; test breve, senza modello o carichi esterni.
#include "strata/kernels/fused_gr.hpp"
#include <cuda_runtime.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <random>
#include <vector>

static void ck(cudaError_t e) {
    if (e != cudaSuccess) { std::fprintf(stderr, "%s\n", cudaGetErrorString(e)); std::exit(2); }
}

int main() {
    using namespace strata::kernels;
    constexpr int N=2560, HC=4, D=N*HC, LR=320, TM=8;
    std::mt19937 rng(315);
    std::uniform_real_distribution<float> dist(-0.25f,0.25f);
    auto floats = [&](int n) {
        std::vector<float> h(n); for (float& x : h) x=dist(rng);
        float* d=nullptr; ck(cudaMalloc(&d,n*sizeof(float)));
        ck(cudaMemcpy(d,h.data(),n*sizeof(float),cudaMemcpyHostToDevice)); return d;
    };
    auto weights = [&](int n) {
        std::vector<uint16_t> h(n);
        for (auto& x:h) { float f=dist(rng); uint32_t u; std::memcpy(&u,&f,4); x=(uint16_t)(u>>16); }
        uint16_t* d=nullptr; ck(cudaMalloc(&d,n*sizeof(uint16_t)));
        ck(cudaMemcpy(d,h.data(),n*sizeof(uint16_t),cudaMemcpyHostToDevice)); return d;
    };
    auto wn=floats(D), R=floats(TM*D), bo=floats(TM*N), ip=floats(TM*HC);
    auto wd=weights(LR*D), wu=weights(D*LR), wi=weights(HC*D);
    auto ro=floats(TM*D), lo=floats(TM*LR), rs=floats(TM*HC), inj=floats(TM*HC), mixed=floats(TM*N), xn=floats(TM*D);
    FusedGrArgs a[TM];
    for (int t=0;t<TM;++t) {
        auto& x=a[t]; x.R=R+t*D; x.R_out=ro+t*D; x.apply=true;
        x.bo_prev=bo+t*N; x.inj_prev=ip+t*HC;
        x.w_norm=wn; x.w_down=wd; x.w_up=wu; x.w_inject=wi;
        x.lo=lo+t*LR; x.rs=rs+t*HC; x.inject_out=inj+t*HC; x.mixed=mixed+t*N;
    }
    fused_gr_check();
    cudaStream_t stream; ck(cudaStreamCreateWithFlags(&stream,cudaStreamNonBlocking));
    cudaEvent_t begin,end; ck(cudaEventCreate(&begin)); ck(cudaEventCreate(&end));
    for (int T : {1,2,4,8}) {
        for (int i=0;i<20;++i) fused_gr_read_multi(a,T,xn,stream);
        ck(cudaStreamSynchronize(stream));
        for (int round=0;round<3;++round) {
            ck(cudaEventRecord(begin,stream));
            for (int i=0;i<200;++i) fused_gr_read_multi(a,T,xn,stream);
            ck(cudaEventRecord(end,stream)); ck(cudaEventSynchronize(end));
            float ms; ck(cudaEventElapsedTime(&ms,begin,end));
            std::printf("variant=%d tokens=%d repeat=%d us_per_call=%.3f\n",fused_gr_variant(),T,round,ms*1000/200);
        }
    }
    ck(cudaEventDestroy(begin)); ck(cudaEventDestroy(end)); ck(cudaStreamDestroy(stream));
    for (auto p : {wn,R,bo,ip,ro,lo,rs,inj,mixed,xn}) ck(cudaFree(p));
    for (auto p : {wd,wu,wi}) ck(cudaFree(p));
    return 0;
}
