// Integration test for ggml_cuda_ram_restore_all(): real decommit, reload from a backing
// file, whole-tensor comparison (what prefill staging reads), counters, ceiling, failure.
// Modeled on qwen_ram_decode_opt_20260920/tests/ram_store_test.cpp (read-only reference).

#include "ggml-alloc.h"
#include "ggml.h"
#include "moe-ram-store.cuh"

#include <array>
#include <cstring>
#include <fstream>
#include <stdexcept>
#include <string>
#include <vector>

static void require(bool value, const char * message) {
    if (!value) throw std::runtime_error(message);
}

static size_t align_up(size_t value, size_t alignment) {
    return (value + alignment - 1) & ~(alignment - 1);
}

using triple = std::array<ggml_tensor *, 3>;

static void make_cold(const triple & banks, int expert) {
    auto & registry = ggml_cuda_ram_store_registry_get();
    std::lock_guard<std::mutex> lock(registry.mutex);
    uint64_t released = 0;
    ggml_cuda_ram_store_tensor * state[3] = {};
    for (int bank = 0; bank < 3; ++bank) {
        auto found = registry.tensors.find(banks[bank]);
        require(found != registry.tensors.end(), "unregistered tensor");
        require(ggml_cuda_ram_store_drop(found->second, expert, &released), "decommit failed");
        state[bank] = &found->second;
    }
    ggml_cuda_ram_store_publish_cold(registry, state, expert);
    registry.decommitted_bytes += released;
    registry.resident_ceiling = registry.resident_bytes; // what evict_locked leaves behind
}

static bool interior_committed(const ggml_tensor * tensor, int expert) {
    MEMORY_BASIC_INFORMATION page{};
    const char * inside = static_cast<const char *>(tensor->data) + size_t(expert)*tensor->nb[2] + 4096;
    require(VirtualQuery(inside, &page, sizeof(page)) != 0, "VirtualQuery failed");
    return page.State == MEM_COMMIT;
}

int main() {
    char temp_dir[MAX_PATH] = {};
    char path[MAX_PATH] = {};
    require(GetTempPathA(MAX_PATH, temp_dir) != 0, "GetTempPath failed");
    require(GetTempFileNameA(temp_dir, "rst", 0, path) != 0, "GetTempFileName failed");
    _putenv_s("LLAMA_MOE_RAM_EVICT", "0");
    _putenv_s("LLAMA_MOE_RAM_CONTROL_FILE", "");

    ggml_context * ctx = nullptr;
    ggml_backend_buffer_t buffer = nullptr;
    int result = 0;
    try {
        ggml_init_params params = { ggml_tensor_overhead()*8, nullptr, true };
        ctx = ggml_init(params);
        require(ctx != nullptr, "ggml_init failed");
        // 63x65 floats per expert: the stride is not a page multiple, so every expert has
        // zeroed shared edges as well as a decommitted interior.
        const int n_experts = 8;
        std::array<triple, 2> layers;
        const char * names[3] = {"ffn_up_exps.weight", "ffn_gate_exps.weight", "ffn_down_exps.weight"};
        for (int layer = 0; layer < 2; ++layer) {
            for (int bank = 0; bank < 3; ++bank) {
                layers[layer][bank] = ggml_new_tensor_3d(ctx, GGML_TYPE_F32, 63, 65, n_experts);
                ggml_format_name(layers[layer][bank], "blk.%d.%s", layer, names[bank]);
            }
        }
        buffer = ggml_backend_alloc_ctx_tensors_from_buft(ctx, ggml_backend_cuda_ram_buffer_type());
        require(buffer != nullptr, "RAM_STORE allocation failed");

        const size_t bytes = ggml_nbytes(layers[0][0]);
        const size_t slot = align_up(bytes, 4096);
        std::vector<char> backing(slot*6, 0);
        for (int layer = 0; layer < 2; ++layer) {
            for (int bank = 0; bank < 3; ++bank) {
                char * source = static_cast<char *>(layers[layer][bank]->data);
                for (size_t i = 0; i < bytes; ++i) source[i] = char((layer*131 + bank*71 + i*13 + (i >> 9)) & 0x7f);
                memcpy(backing.data() + slot*(layer*3 + bank), source, bytes);
            }
        }
        {
            std::ofstream file(path, std::ios::binary | std::ios::trunc);
            require(file.good(), "backing create failed");
            file.write(backing.data(), std::streamsize(backing.size()));
            require(file.good(), "backing write failed");
        }
        require(SetFileAttributesA(path, FILE_ATTRIBUTE_READONLY), "backing readonly failed");
        for (int layer = 0; layer < 2; ++layer) {
            for (int bank = 0; bank < 3; ++bank) {
                require(ggml_cuda_ram_register_file(layers[layer][bank], path, slot*(layer*3 + bank)), "register failed");
            }
        }
        auto & registry = ggml_cuda_ram_store_registry_get();
        const uint64_t full_resident = registry.resident_bytes;

        // 1. nothing absent: no work, no SSD read
        require(ggml_cuda_ram_restore_all() == 0, "restore_all with nothing absent must return 0");
        require(registry.counters.ssd_reads == 0, "restore_all read the file with nothing absent");

        // 2. five absent triples over two layers come back byte for byte
        const uint64_t tick_before = registry.tensors.at(layers[0][0]).last_used[1];
        make_cold(layers[0], 1); make_cold(layers[0], 2); make_cold(layers[0], 5);
        make_cold(layers[1], 0); make_cold(layers[1], 7);
        require(registry.missing_groups == 5 && ggml_cuda_ram_has_missing(), "cold group counter mismatch");
        require(!interior_committed(layers[0][0], 2) && !interior_committed(layers[1][2], 7), "interior was not decommitted");
        require(ggml_cuda_ram_restore_all() == 5, "restore_all did not restore the five absent triples");
        require(!ggml_cuda_ram_has_missing() && registry.missing_groups == 0, "restore_all left the missing guard set");
        require(registry.resident_bytes == full_resident, "resident byte accounting differs after restore");
        require(registry.resident_ceiling >= registry.resident_bytes, "ceiling left below resident after restore");
        require(registry.counters.restores == 5 && registry.counters.ssd_reads == 15, "restore counters mismatch");
        require(registry.tensors.at(layers[0][0]).last_used[1] == tick_before, "restore_all changed the LRU order");
        for (int layer = 0; layer < 2; ++layer) {
            for (int bank = 0; bank < 3; ++bank) {
                require(memcmp(layers[layer][bank]->data, backing.data() + slot*(layer*3 + bank), bytes) == 0,
                    "whole tensor differs from backing after restore");
            }
        }

        // 3. a failed reload keeps the triple cold and decommitted, and nothing escapes
        make_cold(layers[1], 3);
        const HANDLE real = registry.tensors.at(layers[1][0]).file->handle;
        registry.tensors.at(layers[1][0]).file->handle = INVALID_HANDLE_VALUE;
        require(ggml_cuda_ram_restore_all() == -1, "restore_all must report a failed reload");
        require(ggml_cuda_ram_has_missing() && registry.missing_groups == 1, "failed reload cleared the guard");
        for (const auto * tensor : layers[1]) require(!registry.tensors.at(tensor).resident[3], "failed reload published a partial triple");
        require(!interior_committed(layers[1][1], 3), "failed reload left pages committed");

        // 4. and it succeeds once the file is readable again
        registry.tensors.at(layers[1][0]).file->handle = real;
        require(ggml_cuda_ram_restore_all() == 1 && !ggml_cuda_ram_has_missing(), "retry after failure did not restore");
        for (int bank = 0; bank < 3; ++bank) {
            require(memcmp(layers[1][bank]->data, backing.data() + slot*(3 + bank), bytes) == 0, "tensor differs after retry");
        }
        printf("ram_store_restore_test: PASS\n");
    } catch (const std::exception & error) {
        fprintf(stderr, "ram_store_restore_test: FAIL: %s\n", error.what());
        result = 1;
    }
    if (buffer) ggml_backend_buffer_free(buffer);
    if (ctx) ggml_free(ctx);
    SetFileAttributesA(path, FILE_ATTRIBUTE_NORMAL);
    DeleteFileA(path);
    return result;
}
