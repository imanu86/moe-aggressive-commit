# PR #1030: cache elastica automatica con nucleo su upstream 0.1.39 (6/10/2026)

- PR: https://github.com/Niko1221/Strata/pull/1030 (head imanu86:contrib/elastic-core-0139 = b87e665, base upstream 6f32ec0)
- Prove pubbliche: https://github.com/imanu86/Strata-2080Ti/tree/evidence/elastic-cache (58c6708)
- Messaggio a Niko: https://github.com/Niko1221/Strata/pull/1030#issuecomment-6009041597
- Correzione del link privato su #614: https://github.com/Niko1221/Strata/pull/614#issuecomment-6009041838

Port ricostruito dalla versione 0.1.39 del fork (expert_cache con elastic_grow/elastic_shrink, che non collidono con
grow/shrink di #533), prefill dal patch del 3/10, generate.cpp a mano (core/coda nel prestito e negli scambi, esclusione
reciproca con --vram-elastic). Verifiche: CTest 4/4; senza --elastic identica bit per bit a upstream (teacher forcing a
posizionamento fisso, code ed explain); 131k con --elastic L01 49,4 / L02 45,8 t/s, upstream 47,3 / 46,3 (rumore),
la cache e' cresciuta di 300 esperti. Worktree: C:\Users\imanu\source\repos\Strata-elastic-pr e Strata-elastic-evidence.
