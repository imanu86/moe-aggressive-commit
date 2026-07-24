cmake_minimum_required(VERSION 3.24)

project(audit0_microbench LANGUAGES CXX)

option(AUDIT0_BUILD_CUDA "Build the authored-only CUDA benchmark" ON)

add_executable(audit0_cpu src/audit0_cpu.cpp)
target_compile_features(audit0_cpu PRIVATE cxx_std_20)
target_compile_definitions(audit0_cpu PRIVATE NOMINMAX WIN32_LEAN_AND_MEAN)
target_compile_options(audit0_cpu PRIVATE
    $<$<CXX_COMPILER_ID:MSVC>:/O2 /EHsc /W4 /arch:AVX2>
)

if(AUDIT0_BUILD_CUDA)
    enable_language(CUDA)
    add_executable(audit0_gpu src/audit0_gpu.cu)
    target_compile_features(audit0_gpu PRIVATE cxx_std_17)
    set_target_properties(audit0_gpu PROPERTIES
        CUDA_ARCHITECTURES 86
        CUDA_SEPARABLE_COMPILATION OFF
    )
    target_compile_options(audit0_gpu PRIVATE
        $<$<COMPILE_LANGUAGE:CUDA>:-O3 --use_fast_math --expt-relaxed-constexpr>
        $<$<COMPILE_LANGUAGE:CXX>:/O2 /EHsc /W4>
    )
endif()
