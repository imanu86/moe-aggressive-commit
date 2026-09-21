// Test autonomo della politica M3 (banda morta, ripartenza, prefill senza svuotamento). Niente GPU.
//   cl /nologo /std:c++17 /EHsc /I<source>\src /I<overlay>\src policy_m3_test.cpp
#include "llama-moecache-policy-m3.h"

#include <cstdio>
#include <cstdlib>

static int failures = 0;

#define CHECK_EQ(got, want) do { \
    const long long g_ = (long long) (got), w_ = (long long) (want); \
    if (g_ != w_) { ++failures; std::printf("FAIL riga %d: %s = %lld, atteso %lld\n", __LINE__, #got, g_, w_); } \
} while (0)

int main() {
    const int64_t MiB = 1024 * 1024;
    const uint64_t bps = 83814400;          // bytes_per_slot del log del 21/9 (79,9 MiB)
    const uint64_t transient = 64 * MiB;
    const int32_t mn = 30, mx = 512;
    const llama_moe_band band;              // 256 MiB di cuscino, crescita minima 4 slot

    // 1) dentro la banda non si tocca niente: [transient, transient + cuscino + 4 slot)
    const int64_t top = int64_t(transient) + int64_t(band.cushion_bytes) + 4 * int64_t(bps);
    for (int64_t h = int64_t(transient); h < top; h += 8 * MiB) {
        CHECK_EQ(llama_moe_choose_capacity_banded(66, mn, mx, bps, h, h, transient, band, true), 66);
    }

    // 2) riserva violata: M2 scende di 1 (66 -> 65), M3 scende fino a lasciare il cuscino (-> 62)
    CHECK_EQ(llama_moe_choose_capacity(66, mn, mx, bps, 32 * MiB, 0, transient), 65);
    CHECK_EQ(llama_moe_choose_capacity_banded(66, mn, mx, bps, 32 * MiB, 32 * MiB, transient, band, true), 62);
    //    e dopo la discesa il margine atteso sta dentro la banda: nessuna ricrescita immediata
    const int64_t dopo = 32 * MiB + 4 * int64_t(bps);
    CHECK_EQ(llama_moe_choose_capacity_banded(62, mn, mx, bps, dopo, dopo, transient, band, true), 62);

    // 3) la riduzione scatta ESATTAMENTE dove scattava in M2 (un byte sotto il transiente)
    CHECK_EQ(llama_moe_choose_capacity_banded(66, mn, mx, bps, int64_t(transient), int64_t(transient), transient, band, true), 66);
    CHECK_EQ(llama_moe_choose_capacity_banded(66, mn, mx, bps, int64_t(transient) - 1, int64_t(transient) - 1, transient, band, true) < 66, 1);

    // 4) crescita: solo da 4 slot in su, col cuscino intatto, e solo sul margine stabile
    CHECK_EQ(llama_moe_choose_capacity_banded(60, mn, mx, bps, top, top, transient, band, true), 64);
    CHECK_EQ(llama_moe_choose_capacity_banded(60, mn, mx, bps, top - 1, top - 1, transient, band, true), 60);
    CHECK_EQ(llama_moe_choose_capacity_banded(60, mn, mx, bps, top, top, transient, band, false), 60);
    CHECK_EQ(llama_moe_choose_capacity_banded(60, mn, mx, bps, top + 10 * int64_t(bps), top, transient, band, true), 64);
    CHECK_EQ(llama_moe_choose_capacity_banded(60, mn, mx, bps, top, top - 1, transient, band, true), 60);
    CHECK_EQ(llama_moe_choose_capacity_banded(510, mn, mx, bps, 100 * int64_t(bps), 100 * int64_t(bps), transient, band, true), 510); // +2 al massimo: non vale uno svuotamento

    // 5) il cuscino non costa la cache intera: il minimo resta se rispetta la riserva
    CHECK_EQ(llama_moe_choose_capacity_banded(31, mn, mx, bps, 0, 0, transient, band, true), 30);
    CHECK_EQ(llama_moe_choose_capacity_banded(30, mn, mx, bps, -100 * MiB, -100 * MiB, transient, band, true), 0);
    //    decode senza cache: si risale al minimo quando M2 l'avrebbe concesso, anche senza cuscino
    const int64_t h_min = int64_t(transient) + 30 * int64_t(bps);
    CHECK_EQ(llama_moe_choose_capacity_banded(0, mn, mx, bps, h_min, h_min, transient, band, true), 30);
    CHECK_EQ(llama_moe_choose_capacity_banded(0, mn, mx, bps, h_min - 1, h_min - 1, transient, band, true), 0);

    // 6) jitter misurato (±150 MiB attorno a 350 MiB di margine): zero ridimensionamenti
    {
        int resize = 0;
        unsigned seed = 12345;
        for (int i = 0; i < 100000; ++i) {
            seed = seed * 1664525u + 1013904223u;
            const int64_t h = 350 * MiB + (int64_t(seed >> 8) % (301 * MiB)) - 150 * MiB;
            if (llama_moe_choose_capacity_banded(63, mn, mx, bps, h, h, transient, band, true) != 63) ++resize;
        }
        CHECK_EQ(resize, 0);
    }

    // 7) con cuscino 0 e crescita minima 1 la decisione coincide con M2
    {
        const llama_moe_band m2{0, 1};
        for (int64_t h = -512 * MiB; h < 2048 * MiB; h += 7 * MiB) {
            CHECK_EQ(llama_moe_choose_capacity_banded(66, mn, mx, bps, h, h, transient, m2, true),
                     llama_moe_choose_capacity(66, mn, mx, bps, h, 0, transient));
        }
    }

    // 8) ripartenza dopo il prefill
    const uint64_t ws = 128 * MiB;
    const auto vuoto = [&](int slots) { // margine a cache vuota che da' esattamente `slots` di capacita' fresca
        return int64_t(ws) + int64_t(band.cushion_bytes) + int64_t(transient) + int64_t(slots) * int64_t(bps);
    };
    CHECK_EQ(llama_moe_restart_capacity(0,  mn, mx, bps, vuoto(65), transient, ws, band), 65);  // nessuna storia
    CHECK_EQ(llama_moe_restart_capacity(66, mn, mx, bps, vuoto(65), transient, ws, band), 66);  // condizioni invariate: ultima taglia buona
    CHECK_EQ(llama_moe_restart_capacity(63, mn, mx, bps, vuoto(65), transient, ws, band), 63);
    CHECK_EQ(llama_moe_restart_capacity(67, mn, mx, bps, vuoto(65), transient, ws, band), 65);  // mangerebbe piu' di meta' cuscino
    CHECK_EQ(llama_moe_restart_capacity(70, mn, mx, bps, vuoto(65), transient, ws, band), 65);  // la VRAM si e' ristretta
    CHECK_EQ(llama_moe_restart_capacity(55, mn, mx, bps, vuoto(65), transient, ws, band), 65);  // la VRAM si e' allargata
    CHECK_EQ(llama_moe_restart_capacity(66, mn, mx, bps, vuoto(20), transient, ws, band), 30);  // mai sotto il minimo di M2
    CHECK_EQ(llama_moe_restart_capacity(66, mn, mx, bps, -1, transient, ws, band), 30);
    CHECK_EQ(llama_moe_restart_capacity(66, mn, 60, bps, vuoto(65), transient, ws, band), 60);  // tetto di LLAMA_MOE_ELASTIC_MAX

    // 9) prefill con la cache al suo posto
    const uint64_t area = 462 * MiB, margine = 256 * MiB, anello = 1200 * MiB;
    CHECK_EQ(llama_moe_keep_cache_for_workspace(4096 * MiB, 0, transient, margine, 0), 0);           // taglia sconosciuta
    CHECK_EQ(llama_moe_keep_cache_for_workspace(int64_t(area + transient + margine), area, transient, margine, 0), 1);
    CHECK_EQ(llama_moe_keep_cache_for_workspace(int64_t(area + transient + margine) - 1, area, transient, margine, 0), 0);
    CHECK_EQ(llama_moe_keep_cache_for_workspace(int64_t(area + transient + margine), area, transient, margine, anello), 0);
    CHECK_EQ(llama_moe_keep_cache_for_workspace(int64_t(area + transient + margine + anello), area, transient, margine, anello), 1);
    CHECK_EQ(llama_moe_keep_cache_for_workspace(350 * MiB, area, transient, margine, 0), 0);          // il caso a regime del log: si svuota
    CHECK_EQ(llama_moe_keep_cache_for_workspace(-1, area, transient, margine, 0), 0);

    std::printf(failures ? "policy_m3_test: %d FALLITI\n" : "policy_m3_test: PASS\n", failures);
    return failures ? 1 : 0;
}
