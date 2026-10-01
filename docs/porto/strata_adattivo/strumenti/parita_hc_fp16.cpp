// Mirror coverage, including gr_write_norm_rs: preserve BF16 and compare FP16 with the unfused path.
#include "strata/prefill/kernels.hpp"
#include <cuda_runtime.h>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <vector>

void ck(cudaError_t e) { if(e != cudaSuccess) { std::fprintf(stderr,"%s\n",cudaGetErrorString(e)); std::exit(2); } }
template<class T> T* alloc(size_t n) { T* p; ck(cudaMalloc(&p,n*sizeof(T))); return p; }
template<class T> std::vector<T> read(T* p,size_t n) { std::vector<T> v(n); ck(cudaMemcpy(v.data(),p,n*sizeof(T),cudaMemcpyDeviceToHost)); return v; }

int main() {
    using namespace strata::prefill;
    int bad=0,cases=0;
    for (int T : {1,7,128}) {
        const size_t n=(size_t)T*10240;
        std::vector<float> r(n),w(10240),bo((size_t)T*2560),inj((size_t)T*4);
        for(size_t i=0;i<n;++i) r[i]=std::sin((float)i*.017f)*3;
        for(size_t i=0;i<w.size();++i) w[i]=.5f+(float)(i%37)*.03f;
        for(size_t i=0;i<bo.size();++i) bo[i]=std::cos((float)i*.021f);
        for(size_t i=0;i<inj.size();++i) inj[i]=(float)(i%11)*.1f-.5f;
        float *dR=alloc<float>(n),*dW=alloc<float>(w.size()),*dB=alloc<float>(bo.size()),*dI=alloc<float>(inj.size());
        float *dX=alloc<float>(n),*dS=alloc<float>((size_t)T*4);
        uint16_t *dBF=alloc<uint16_t>(n),*dHF=alloc<uint16_t>(n),*dRef=alloc<uint16_t>(n);
        ck(cudaMemcpy(dW,w.data(),w.size()*4,cudaMemcpyHostToDevice));
        ck(cudaMemcpy(dB,bo.data(),bo.size()*4,cudaMemcpyHostToDevice));
        ck(cudaMemcpy(dI,inj.data(),inj.size()*4,cudaMemcpyHostToDevice));
        auto reset=[&]{ck(cudaMemcpy(dR,r.data(),n*4,cudaMemcpyHostToDevice)); ck(cudaMemset(dHF,0xA5,n*2));};
        for(int mode=0;mode<3;++mode) {
            reset();
            if(mode==0) gr_norm(dR,dW,1e-6f,dX,dBF,T,nullptr);
            if(mode==1) gr_norm_rs(dR,dW,1e-6f,dS,dBF,T,nullptr);
            if(mode==2) gr_write_norm_rs(dR,dB,dI,4,dW,1e-6f,dS,dBF,T,nullptr);
            auto old=read(dBF,n);
            reset();
            if(mode==2) gr_write(dR,dB,dI,4,T,nullptr);
            gr_norm(dR,dW,1e-6f,dX,dBF,T,nullptr);
            to_f16(dX,dRef,n,nullptr);
            auto ref=read(dRef,n);
            reset();
            if(mode==0) gr_norm(dR,dW,1e-6f,dX,dBF,T,nullptr,dHF);
            if(mode==1) gr_norm_rs(dR,dW,1e-6f,dS,dBF,T,nullptr,dHF);
            if(mode==2) gr_write_norm_rs(dR,dB,dI,4,dW,1e-6f,dS,dBF,T,nullptr,dHF);
            bool bf=read(dBF,n)==old,hf=read(dHF,n)==ref;
            ++cases; bad+=!bf||!hf;
            std::printf("T=%d norm_mode=%d BF16=%s FP16=%s\n",T,mode,bf?"PASS":"FAIL",hf?"PASS":"FAIL");
        }
        const size_t lr=(size_t)T*320;
        std::vector<float> silu_input(lr,4.0f);
        ck(cudaMemcpy(dB,silu_input.data(),lr*4,cudaMemcpyHostToDevice));
        gr_silu(dB,dBF,T,nullptr);
        auto old=read(dBF,lr);
        ck(cudaMemset(dHF,0xA5,lr*2));
        gr_silu(dB,dBF,T,nullptr,dHF);
        bool bf=read(dBF,lr)==old;
        auto hf=read(dHF,lr);
        // Check the new mirror is populated for every row, including the tail.
        to_f16(dB,dRef,lr,nullptr);
        // SiLU(4 / HC) = sigmoid(1), rounded to FP16 (0x39d9).
        bool written=true; for(auto v:hf) written &= v==0x39d9;
        ++cases; bad+=!bf||!written;
        std::printf("T=%d silu BF16=%s FP16_written=%s\n",T,bf?"PASS":"FAIL",written?"PASS":"FAIL");
        for(void* p:{(void*)dR,(void*)dW,(void*)dB,(void*)dI,(void*)dX,(void*)dS,(void*)dBF,(void*)dHF,(void*)dRef}) cudaFree(p);
    }
    std::printf("cases=%d failures=%d\n",cases,bad);
    return bad?1:0;
}
