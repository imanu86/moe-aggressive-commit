from pathlib import Path
import re,json,hashlib
BASE=Path(__file__).resolve().parent;R=BASE/'daily038_alignment_20261003';S=R/'source'
p=S/'src/prefill/prefill.cpp';s=p.read_text(encoding='utf-8')
pattern=r'^<<<<<<< daily036-sm75\n(.*?)^\|\|\|\|\|\|\| upstream036\n(.*?)^=======\n(.*?)^>>>>>>> upstream038-elastic\n'
def resolve(m):
    assert 'ple_copied' in m[1] and 'the PLE rows\' upload failed' in m[3]
    return m[3] # upstream error checks and uncut chunk geometry; grid is removed
s,count=re.subn(pattern,resolve,s,flags=re.S|re.M);assert count==1
p.write_text(s,encoding='utf-8',newline='\n')
p=S/'src/program/generate.cpp';s=p.read_text(encoding='utf-8')
needle='        const int64_t reserve = (((int64_t) o.vram_reserve_mib + prefill_mib) << 20) + mtp_bind;'
assert s.count(needle)==1
s=s.replace(needle,'''        const int64_t sm75_extra = prefill_mib > 0 ? sm75_prompt_extra_bytes(g, o.prefill_chunk, 0) : 0;
        const int64_t reserve = (((int64_t) o.vram_reserve_mib + prefill_mib) << 20) + mtp_bind + sm75_extra;''')
s=s.replace('((int64_t) free_b - mtp_bind - min_slots * blob)', '((int64_t) free_b - mtp_bind - sm75_extra - min_slots * blob)')
s=s.replace('((((int64_t) r + prefill_mib) << 20) + mtp_bind)', '((((int64_t) r + prefill_mib) << 20) + mtp_bind + sm75_extra)')
p.write_text(s,encoding='utf-8',newline='\n')
rej=S/'src/program/generate.cpp.rej';rej.rename(R/'budget-rejected-original.rej')
p=S/'CMakeLists.txt';s=p.read_text(encoding='utf-8');needle='  set(_strata_mmq_types';at=s.index(needle)
s=s[:at]+'''  option(STRATA_PARITY_POOL_QUANT "Build the native expert pool quantization parity check" OFF)
  if(STRATA_BUILD_TESTS OR STRATA_PARITY_POOL_QUANT)
    add_executable(pool_quant_parity src/kernels/cpu/pool_quant_parity.cpp)
    target_link_libraries(pool_quant_parity PRIVATE strata_kernels_cpu)
  endif()
'''+s[at:]
needle='  # #296\'s real-weight checks';at=s.index(needle)
s=s[:at]+'''  if(STRATA_ENABLE_CUDA AND STRATA_BUILD_TESTS)
    add_executable(native_expert_bench src/kernels/native_expert_bench.cpp)
    target_include_directories(native_expert_bench PRIVATE ${_strata_gpu_include_directories})
    target_link_libraries(native_expert_bench PRIVATE strata_kernels strata_kernels_cpu strata_artifact ${_strata_gpu_runtime_target})
  endif()
'''+s[at:];p.write_text(s,encoding='utf-8',newline='\n')
for p in S.rglob('*'):
    if p.is_file() and p.suffix in ('.cpp','.hpp','.cu'):
        s=p.read_text(encoding='utf-8-sig');assert not re.search(r'^<<<<<<<|^>>>>>>>|^\|\|\|\|\|\|\|',s,re.M),p
for name in ('src/prefill/prefill.cpp','src/program/generate.cpp','include/strata/prefill/prefill.hpp'):assert 'align_every' not in (S/name).read_text(encoding='utf-8')
meta={'upstream':'99f3dbd0b21d1401b3769e0c0d963913607f380b','old_daily':'2c394674ed933a817741506b0b35e370f4d45c21','grid_removed':True,'elastic':'final038 VMM port with cap_T token buffers','checkpoint_tail':'PR614 source; optional flag on in new Daily config','conflict_resolution':'PLE upload: upstream038 errors retained; obsolete grid next-chunk override discarded','small_card_accounting':'SM75 extra own-prefill bytes retained also in upstream038 adaptive reserve fallback','files':{p.relative_to(S).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in S.rglob('*') if p.is_file()}}
(R/'preparation.json').write_text(json.dumps(meta,indent=2));print('SOURCE READY',len(meta['files']),'files; grid absent')
