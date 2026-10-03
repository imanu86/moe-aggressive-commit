from pathlib import Path
import difflib,hashlib,json,subprocess
R=Path(__file__).resolve().parent/'checkpoint038_20261003'; S=R/'source'
assert (R/'strata-baseline.exe').exists(), 'Finish the untouched baseline first'
def change(rel,edits):
    p=S/rel; t=p.read_text(encoding='utf-8-sig')
    assert hashlib.sha256(p.read_bytes()).hexdigest()==json.loads((R/'provenance.json').read_text())['original_files'][rel]
    for old,new in edits:
        assert t.count(old)==1,(rel,old,t.count(old)); t=t.replace(old,new)
    p.write_text(t,encoding='utf-8',newline='\n')
change('include/strata/prefill/prefill.hpp',[(
    '    std::function<bool()> should_stop;\n',
    '    std::function<bool()> should_stop;\n\n'
    '    /// Clip chunks at align_origin + k * align_every, so conversation checkpoints do not drift past the grid.\n'
    '    /// 0 keeps fixed-size chunks. Layer-split callers leave it disabled.\n'
    '    int64_t align_every = 0;\n'
    '    int64_t align_origin = 0;\n')])
change('src/prefill/prefill.cpp',[
    ('    auto ple_gather = [&m, &ss, tokens, n, prev0](int64_t c0, int buf, std::string& e) -> bool {\n        const int64_t T = std::min(m.T, n - c0);',
     '    auto chunk_len = [this, &m, n, pos0](int64_t c0) -> int64_t {\n'
     '        int64_t T = std::min(m.T, n - c0);\n'
     '        const int64_t p = pos0 + c0;\n'
     '        if (align_every > 0 && p >= align_origin) {\n'
     '            const int64_t edge = align_origin + ((p - align_origin) / align_every + 1) * align_every;\n'
     '            T = std::min(T, edge - p);\n'
     '        }\n'
     '        return T;\n'
     '    };\n'
     '    auto ple_gather = [&m, &ss, tokens, n, prev0, &chunk_len](int64_t c0, int buf, std::string& e) -> bool {\n        const int64_t T = chunk_len(c0);'),
    ('    for (int64_t c0 = 0; c0 < n; c0 += m.T) {',
     '    int64_t T_step = 0, c0_last = 0;\n    for (int64_t c0 = 0; c0 < n; c0 += T_step) {'),
    ('        const int64_t T = std::min(m.T, n - c0), p0 = pos0 + c0;',
     '        const int64_t T = chunk_len(c0), p0 = pos0 + c0;\n        T_step = T;\n        c0_last = c0;'),
    ('            if (c0 + m.T < n) {','            if (c0 + T < n) {'),
    ('c1 = c0 + m.T, b = ple_buf ^ 1','c1 = c0 + T, b = ple_buf ^ 1'),
    ('        const int64_t last = (n - 1) % m.T;',
     '        const int64_t last = (n - 1) - c0_last;')])
change('src/program/generate.cpp',[(
    '            pp_next_check = reread_to > 0 ? INT64_MAX : resume + o.prompt_cache_every;',
    '            pp_next_check = reread_to > 0 ? INT64_MAX : resume + o.prompt_cache_every;\n'
    '            // A layer split passes fixed chunks between stages; keep its existing geometry.\n'
    '            sp.align_every = (reread_to > 0 || multi_gpu || o.prompt_cache_every <= 0) ? 0 : o.prompt_cache_every;\n'
    '            sp.align_origin = resume;')])
patch=''
for rel in json.loads((R/'provenance.json').read_text())['original_files']:
    old=(R/'original'/rel).read_text(encoding='utf-8-sig').splitlines(keepends=True)
    new=(S/rel).read_text(encoding='utf-8').splitlines(keepends=True)
    patch+='diff --git a/'+rel+' b/'+rel+'\n'+''.join(difflib.unified_diff(old,new,fromfile='a/'+rel,tofile='b/'+rel))
(R/'checkpoint-grid.patch').write_text(patch,encoding='utf-8',newline='\n')
subprocess.run(['git','apply','--no-index','--check',str((R/'checkpoint-grid.patch').resolve())],cwd=R/'original',check=True)
(R/'patch-provenance.json').write_text(json.dumps({'original_author_commit':'9f1546305ffa883403f71c3c0c2a044f0540d903','original_coauthor':'Claude Opus 5.5 <noreply@anthropic.com>','port_author':'Codex',
    'patch_sha256':hashlib.sha256((R/'checkpoint-grid.patch').read_bytes()).hexdigest(),
    'scope':list(json.loads((R/'provenance.json').read_text())['original_files'])},indent=2))
print('PATCH_READY',flush=True)
