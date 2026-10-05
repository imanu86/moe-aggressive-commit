"""STRATA_ELASTIC_CORE_ADAPT=1: the elastic core keeps its size (never shrunk, never lent) but its experts become
swap victims for the adaptive tier, like the tail's. Default off = the frozen core of 50a37fa."""
import sys
from pathlib import Path

root = Path(sys.argv[1])
p = root / 'src' / 'program' / 'generate.cpp'
s = p.read_bytes().decode('utf-8')
assert '\r\n' not in s
old = """                    else if (r[e] >= el_core) vict.emplace_back(u[e], e);   // fork: the core never leaves"""
new = """                    // fork: the core never leaves - unless STRATA_ELASTIC_CORE_ADAPT=1, where the core keeps its
                    // size (never shrunk, never lent) but its experts are swap victims like the tail's
                    else if (r[e] >= el_core || core_adapt) vict.emplace_back(u[e], e);"""
assert s.count(old) == 1, s.count(old)
s = s.replace(old, new)
anchor = """        auto adapt = [&]() -> bool {
            if (!pending.empty()) return true;   // the previous swaps are still in flight"""
assert s.count(anchor) == 1, s.count(anchor)
s = s.replace(anchor, """        static const bool core_adapt = [] {
            const char* v = std::getenv("STRATA_ELASTIC_CORE_ADAPT");
            const bool on = v != nullptr && v[0] == '1';
            if (on) std::fprintf(stderr, "strata serve: STRATA_ELASTIC_CORE_ADAPT: the core's experts are swappable\\n");
            return on;
        }();
""" + anchor)
p.write_bytes(s.encode('utf-8'))
print('patched', p)
