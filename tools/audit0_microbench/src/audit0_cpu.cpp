#include <windows.h>
#include <intrin.h>
#include <immintrin.h>

#include <algorithm>
#include <array>
#include <atomic>
#include <charconv>
#include <cmath>
#include <condition_variable>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <mutex>
#include <numeric>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <thread>
#include <vector>

namespace {

constexpr uint32_t kGgufMagic = 0x46554747u;
constexpr uint32_t kQ1Type = 41u;
constexpr uint64_t kQ1Elements = 128u;
constexpr uint64_t kQ1Bytes = 18u;
constexpr uint64_t kMaxLoadedBytes = 3500ull * 1024ull * 1024ull;

struct Options {
    std::filesystem::path sidecar =
        LR"(D:\ds4_work\q1_pilot_data\sidecar_L15_prod.gguf)";
    std::filesystem::path real_experts_tsv =
        LR"(D:\ds4_work\q1_pilot_data\gptq_campaign\results.tsv)";
    uint32_t layer = 15;
    uint32_t expert_count = 32;
    uint32_t reps = 101;
    uint32_t warmups = 32;
    std::vector<uint32_t> explicit_experts;
};

[[noreturn]] void fail(const std::string &message) {
    throw std::runtime_error(message);
}

uint32_t parse_u32(std::string_view text, const char *name) {
    uint32_t value = 0;
    const auto result = std::from_chars(text.data(), text.data() + text.size(), value);
    if (result.ec != std::errc{} || result.ptr != text.data() + text.size()) {
        fail(std::string("invalid ") + name + ": " + std::string(text));
    }
    return value;
}

std::vector<uint32_t> parse_expert_csv(std::string_view text) {
    std::vector<uint32_t> result;
    size_t start = 0;
    while (start < text.size()) {
        const size_t comma = text.find(',', start);
        const size_t end = comma == std::string_view::npos ? text.size() : comma;
        if (end == start) fail("empty expert id in --experts");
        result.push_back(parse_u32(text.substr(start, end - start), "expert id"));
        start = end + 1;
    }
    if (result.empty()) fail("--experts must not be empty");
    return result;
}

Options parse_options(int argc, char **argv) {
    Options options;
    for (int i = 1; i < argc; ++i) {
        const std::string_view arg(argv[i]);
        const auto take = [&](std::string_view prefix) -> std::string_view {
            if (!arg.starts_with(prefix)) return {};
            return arg.substr(prefix.size());
        };
        if (arg == "--help") {
            std::cout
                << "audit0_cpu [--sidecar=PATH] [--real-experts-tsv=PATH]\n"
                << "           [--layer=N] [--expert-count=N] [--experts=CSV]\n"
                << "           [--reps=N] [--warmups=N]\n";
            std::exit(0);
        } else if (arg.starts_with("--sidecar=")) {
            options.sidecar = std::filesystem::path(take("--sidecar="));
        } else if (arg.starts_with("--real-experts-tsv=")) {
            options.real_experts_tsv =
                std::filesystem::path(take("--real-experts-tsv="));
        } else if (arg.starts_with("--layer=")) {
            options.layer = parse_u32(take("--layer="), "layer");
        } else if (arg.starts_with("--expert-count=")) {
            options.expert_count =
                parse_u32(take("--expert-count="), "expert count");
        } else if (arg.starts_with("--experts=")) {
            options.explicit_experts = parse_expert_csv(take("--experts="));
        } else if (arg.starts_with("--reps=")) {
            options.reps = parse_u32(take("--reps="), "reps");
        } else if (arg.starts_with("--warmups=")) {
            options.warmups = parse_u32(take("--warmups="), "warmups");
        } else {
            fail("unknown argument: " + std::string(arg));
        }
    }
    if (options.reps < 100) fail("--reps must be at least 100");
    if (options.expert_count < 32 && options.explicit_experts.empty()) {
        fail("--expert-count must be at least 32");
    }
    if (options.warmups == 0) fail("--warmups must be positive");
    return options;
}

class BinaryReader {
public:
    explicit BinaryReader(const std::filesystem::path &path) : stream_(path, std::ios::binary) {
        if (!stream_) fail("cannot open GGUF: " + path.string());
    }

    template <typename T>
    T read() {
        T value{};
        stream_.read(reinterpret_cast<char *>(&value), sizeof(value));
        if (!stream_) fail("truncated GGUF header");
        return value;
    }

    std::string read_string() {
        const uint64_t length = read<uint64_t>();
        if (length > (1ull << 30)) fail("unreasonable GGUF string length");
        std::string result(static_cast<size_t>(length), '\0');
        if (length != 0) {
            stream_.read(result.data(), static_cast<std::streamsize>(length));
            if (!stream_) fail("truncated GGUF string");
        }
        return result;
    }

    void skip(uint64_t bytes) {
        if (bytes > static_cast<uint64_t>(std::numeric_limits<std::streamoff>::max())) {
            fail("GGUF skip is too large");
        }
        stream_.seekg(static_cast<std::streamoff>(bytes), std::ios::cur);
        if (!stream_) fail("truncated GGUF value");
    }

    uint64_t position() {
        const auto position = stream_.tellg();
        if (position < 0) fail("GGUF tell failed");
        return static_cast<uint64_t>(position);
    }

private:
    std::ifstream stream_;
};

uint64_t checked_mul(uint64_t a, uint64_t b, const char *what) {
    if (a != 0 && b > std::numeric_limits<uint64_t>::max() / a) {
        fail(std::string("overflow computing ") + what);
    }
    return a * b;
}

uint64_t scalar_type_size(uint32_t type) {
    switch (type) {
        case 0: case 1: case 7: return 1;
        case 2: case 3: return 2;
        case 4: case 5: case 6: return 4;
        case 10: case 11: case 12: return 8;
        default: fail("unsupported scalar GGUF metadata type " + std::to_string(type));
    }
}

void skip_metadata_value(BinaryReader &reader, uint32_t type) {
    if (type <= 7 || (type >= 10 && type <= 12)) {
        reader.skip(scalar_type_size(type));
    } else if (type == 8) {
        (void)reader.read_string();
    } else if (type == 9) {
        const uint32_t element_type = reader.read<uint32_t>();
        const uint64_t count = reader.read<uint64_t>();
        if (element_type <= 7 || (element_type >= 10 && element_type <= 12)) {
            reader.skip(checked_mul(count, scalar_type_size(element_type), "metadata array"));
        } else {
            for (uint64_t i = 0; i < count; ++i) {
                skip_metadata_value(reader, element_type);
            }
        }
    } else {
        fail("unsupported GGUF metadata type " + std::to_string(type));
    }
}

struct TensorInfo {
    std::string name;
    std::vector<uint64_t> dimensions;
    uint32_t type = 0;
    uint64_t relative_offset = 0;
    uint64_t absolute_offset = 0;
    uint64_t bytes = 0;
    uint64_t row_bytes = 0;
    uint64_t expert_bytes = 0;
};

struct GgufInfo {
    uint32_t version = 0;
    uint64_t file_bytes = 0;
    uint64_t data_start = 0;
    uint32_t alignment = 32;
    TensorInfo gate;
    TensorInfo up;
    TensorInfo down;
};

uint64_t align_up(uint64_t value, uint64_t alignment) {
    if (alignment == 0 || (alignment & (alignment - 1)) != 0) {
        fail("GGUF alignment is not a nonzero power of two");
    }
    const uint64_t mask = alignment - 1;
    if (value > std::numeric_limits<uint64_t>::max() - mask) {
        fail("GGUF alignment overflow");
    }
    return (value + mask) & ~mask;
}

GgufInfo parse_gguf(const std::filesystem::path &path, uint32_t layer) {
    BinaryReader reader(path);
    if (reader.read<uint32_t>() != kGgufMagic) fail("not a GGUF file");

    GgufInfo result;
    result.version = reader.read<uint32_t>();
    if (result.version < 2 || result.version > 3) {
        fail("unsupported GGUF version " + std::to_string(result.version));
    }
    const uint64_t tensor_count = reader.read<uint64_t>();
    const uint64_t metadata_count = reader.read<uint64_t>();
    if (tensor_count > 1000000 || metadata_count > 1000000) {
        fail("unreasonable GGUF header counts");
    }

    for (uint64_t i = 0; i < metadata_count; ++i) {
        const std::string key = reader.read_string();
        const uint32_t type = reader.read<uint32_t>();
        if (key == "general.alignment") {
            if (type != 4) fail("general.alignment is not UINT32");
            result.alignment = reader.read<uint32_t>();
        } else {
            skip_metadata_value(reader, type);
        }
    }

    const std::string prefix = "blk." + std::to_string(layer) + ".";
    const std::string gate_name = prefix + "ffn_gate_exps.weight";
    const std::string up_name = prefix + "ffn_up_exps.weight";
    const std::string down_name = prefix + "ffn_down_exps.weight";
    std::vector<TensorInfo> matches;
    matches.reserve(3);
    for (uint64_t i = 0; i < tensor_count; ++i) {
        TensorInfo tensor;
        tensor.name = reader.read_string();
        const uint32_t dimensions = reader.read<uint32_t>();
        if (dimensions == 0 || dimensions > 8) fail("invalid GGUF tensor rank");
        tensor.dimensions.resize(dimensions);
        for (uint32_t d = 0; d < dimensions; ++d) {
            tensor.dimensions[d] = reader.read<uint64_t>();
        }
        tensor.type = reader.read<uint32_t>();
        tensor.relative_offset = reader.read<uint64_t>();
        if (tensor.name == gate_name || tensor.name == up_name || tensor.name == down_name) {
            matches.push_back(std::move(tensor));
        }
    }
    result.data_start = align_up(reader.position(), result.alignment);
    result.file_bytes = std::filesystem::file_size(path);
    if (matches.size() != 3) fail("did not find all three layer expert tensors");

    for (auto &tensor : matches) {
        if (tensor.type != kQ1Type) {
            fail(tensor.name + " is type " + std::to_string(tensor.type) +
                 ", expected Q1_0 type 41");
        }
        if (tensor.dimensions.size() != 3) fail(tensor.name + " is not rank 3");
        const uint64_t in_dim = tensor.dimensions[0];
        const uint64_t out_dim = tensor.dimensions[1];
        const uint64_t experts = tensor.dimensions[2];
        if (in_dim == 0 || out_dim == 0 || experts == 0 ||
            in_dim % kQ1Elements != 0) {
            fail(tensor.name + " has invalid Q1_0 dimensions");
        }
        tensor.row_bytes = checked_mul(in_dim / kQ1Elements, kQ1Bytes, "row bytes");
        tensor.expert_bytes = checked_mul(out_dim, tensor.row_bytes, "expert bytes");
        tensor.bytes = checked_mul(experts, tensor.expert_bytes, "tensor bytes");
        tensor.absolute_offset = result.data_start + tensor.relative_offset;
        if (tensor.absolute_offset > result.file_bytes ||
            tensor.bytes > result.file_bytes - tensor.absolute_offset) {
            fail(tensor.name + " extends past the GGUF file");
        }
        if (tensor.name == gate_name) result.gate = tensor;
        else if (tensor.name == up_name) result.up = tensor;
        else result.down = tensor;
    }

    if (result.gate.dimensions != result.up.dimensions) {
        fail("gate and up dimensions differ");
    }
    if (result.gate.dimensions[0] != result.down.dimensions[1] ||
        result.gate.dimensions[1] != result.down.dimensions[0] ||
        result.gate.dimensions[2] != result.down.dimensions[2]) {
        fail("gate/up/down dimensions are not a transposed FFN triplet");
    }
    return result;
}

std::vector<uint32_t> load_real_expert_ids(const Options &options, uint64_t available) {
    std::vector<uint32_t> ids;
    if (!options.explicit_experts.empty()) {
        ids = options.explicit_experts;
    } else {
        std::ifstream stream(options.real_experts_tsv);
        if (!stream) {
            fail("cannot open GPTQ campaign TSV: " + options.real_experts_tsv.string());
        }
        std::string line;
        if (!std::getline(stream, line) || !line.starts_with("expert\t")) {
            fail("unexpected GPTQ campaign TSV header");
        }
        while (ids.size() < options.expert_count && std::getline(stream, line)) {
            const size_t tab = line.find('\t');
            const std::string_view first(line.data(), tab == std::string::npos ? line.size() : tab);
            ids.push_back(parse_u32(first, "campaign expert id"));
        }
        if (ids.size() < options.expert_count) {
            fail("campaign TSV has fewer requested expert rows");
        }
    }

    std::set<uint32_t> unique;
    for (const uint32_t id : ids) {
        if (id >= available) fail("expert id is outside tensor extent: " + std::to_string(id));
        if (!unique.insert(id).second) fail("duplicate expert id: " + std::to_string(id));
    }
    if (ids.size() < 32) fail("at least 32 real experts are required");
    return ids;
}

struct CpuInfo {
    std::string vendor;
    std::string brand;
    bool avx_os = false;
    bool avx2 = false;
    bool fma = false;
    bool f16c = false;
    bool avx512f = false;
    bool avx512dq = false;
    bool avx512bw = false;
    bool avx512vl = false;
    uint32_t logical = 0;
    uint32_t physical = 0;
};

CpuInfo query_cpu() {
    CpuInfo result;
    int registers[4]{};
    __cpuid(registers, 0);
    const int max_basic = registers[0];
    char vendor[13]{};
    std::memcpy(vendor + 0, &registers[1], 4);
    std::memcpy(vendor + 4, &registers[3], 4);
    std::memcpy(vendor + 8, &registers[2], 4);
    result.vendor = vendor;

    __cpuid(registers, 1);
    const bool osxsave = (registers[2] & (1 << 27)) != 0;
    const bool avx = (registers[2] & (1 << 28)) != 0;
    result.fma = (registers[2] & (1 << 12)) != 0;
    result.f16c = (registers[2] & (1 << 29)) != 0;
    const uint64_t xcr0 = osxsave ? _xgetbv(0) : 0;
    result.avx_os = osxsave && avx && (xcr0 & 0x6) == 0x6;

    if (max_basic >= 7) {
        __cpuidex(registers, 7, 0);
        result.avx2 = result.avx_os && (registers[1] & (1 << 5)) != 0;
        const bool zmm_os = (xcr0 & 0xe6) == 0xe6;
        result.avx512f = zmm_os && (registers[1] & (1 << 16)) != 0;
        result.avx512dq = zmm_os && (registers[1] & (1 << 17)) != 0;
        result.avx512bw = zmm_os && (registers[1] & (1 << 30)) != 0;
        result.avx512vl = zmm_os && (registers[1] & (1u << 31)) != 0;
    }

    __cpuid(registers, 0x80000000);
    const uint32_t max_extended = static_cast<uint32_t>(registers[0]);
    if (max_extended >= 0x80000004u) {
        char brand[49]{};
        for (uint32_t leaf = 0; leaf < 3; ++leaf) {
            __cpuid(registers, static_cast<int>(0x80000002u + leaf));
            std::memcpy(brand + leaf * 16, registers, 16);
        }
        result.brand = brand;
        const size_t first = result.brand.find_first_not_of(' ');
        if (first != std::string::npos) result.brand.erase(0, first);
    }

    result.logical = GetActiveProcessorCount(ALL_PROCESSOR_GROUPS);
    DWORD bytes = 0;
    GetLogicalProcessorInformationEx(RelationProcessorCore, nullptr, &bytes);
    if (GetLastError() == ERROR_INSUFFICIENT_BUFFER && bytes != 0) {
        std::vector<uint8_t> buffer(bytes);
        if (GetLogicalProcessorInformationEx(
                RelationProcessorCore,
                reinterpret_cast<PSYSTEM_LOGICAL_PROCESSOR_INFORMATION_EX>(buffer.data()),
                &bytes)) {
            size_t offset = 0;
            while (offset < bytes) {
                const auto *entry =
                    reinterpret_cast<const SYSTEM_LOGICAL_PROCESSOR_INFORMATION_EX *>(
                        buffer.data() + offset);
                if (entry->Relationship == RelationProcessorCore) ++result.physical;
                if (entry->Size == 0) break;
                offset += entry->Size;
            }
        }
    }
    return result;
}

float half_to_float_scalar(uint16_t value) {
    const uint32_t sign = static_cast<uint32_t>(value & 0x8000u) << 16;
    uint32_t exponent = (value >> 10) & 0x1fu;
    uint32_t mantissa = value & 0x03ffu;
    uint32_t bits = 0;
    if (exponent == 0) {
        if (mantissa == 0) {
            bits = sign;
        } else {
            int shift = 0;
            while ((mantissa & 0x0400u) == 0) {
                mantissa <<= 1;
                ++shift;
            }
            mantissa &= 0x03ffu;
            const uint32_t fexp = static_cast<uint32_t>(127 - 14 - shift);
            bits = sign | (fexp << 23) | (mantissa << 13);
        }
    } else if (exponent == 31) {
        bits = sign | 0x7f800000u | (mantissa << 13);
    } else {
        bits = sign | ((exponent + (127 - 15)) << 23) | (mantissa << 13);
    }
    float result = 0.0f;
    std::memcpy(&result, &bits, sizeof(result));
    return result;
}

alignas(32) std::array<std::array<float, 8>, 256> g_sign_lut{};

void initialize_sign_lut() {
    for (uint32_t byte = 0; byte < 256; ++byte) {
        for (uint32_t bit = 0; bit < 8; ++bit) {
            g_sign_lut[byte][bit] = (byte & (1u << bit)) ? 1.0f : -1.0f;
        }
    }
}

using DotFunction = float (*)(const uint8_t *, const float *, uint64_t);

template <bool UseF16c>
__forceinline float decode_scale(const uint8_t *block) {
    uint16_t bits = 0;
    std::memcpy(&bits, block, sizeof(bits));
    if constexpr (UseF16c) {
        const __m128i packed = _mm_cvtsi32_si128(bits);
        return _mm_cvtss_f32(_mm_cvtph_ps(packed));
    }
    return half_to_float_scalar(bits);
}

template <bool UseF16c>
float dot_q1_avx2(const uint8_t *row, const float *input, uint64_t input_size) {
    __m256 sums[4] = {
        _mm256_setzero_ps(), _mm256_setzero_ps(),
        _mm256_setzero_ps(), _mm256_setzero_ps()
    };
    const uint64_t blocks = input_size / kQ1Elements;
    for (uint64_t block_index = 0; block_index < blocks; ++block_index) {
        const uint8_t *block = row + block_index * kQ1Bytes;
        const __m256 scale = _mm256_set1_ps(decode_scale<UseF16c>(block));
        const uint8_t *signs = block + 2;
        const float *x = input + block_index * kQ1Elements;
        for (uint32_t byte = 0; byte < 16; byte += 4) {
            const __m256 w0 = _mm256_mul_ps(
                _mm256_load_ps(g_sign_lut[signs[byte + 0]].data()), scale);
            const __m256 w1 = _mm256_mul_ps(
                _mm256_load_ps(g_sign_lut[signs[byte + 1]].data()), scale);
            const __m256 w2 = _mm256_mul_ps(
                _mm256_load_ps(g_sign_lut[signs[byte + 2]].data()), scale);
            const __m256 w3 = _mm256_mul_ps(
                _mm256_load_ps(g_sign_lut[signs[byte + 3]].data()), scale);
            sums[0] = _mm256_add_ps(
                sums[0], _mm256_mul_ps(_mm256_loadu_ps(x + (byte + 0) * 8), w0));
            sums[1] = _mm256_add_ps(
                sums[1], _mm256_mul_ps(_mm256_loadu_ps(x + (byte + 1) * 8), w1));
            sums[2] = _mm256_add_ps(
                sums[2], _mm256_mul_ps(_mm256_loadu_ps(x + (byte + 2) * 8), w2));
            sums[3] = _mm256_add_ps(
                sums[3], _mm256_mul_ps(_mm256_loadu_ps(x + (byte + 3) * 8), w3));
        }
    }
    const __m256 sum01 = _mm256_add_ps(sums[0], sums[1]);
    const __m256 sum23 = _mm256_add_ps(sums[2], sums[3]);
    const __m256 sum = _mm256_add_ps(sum01, sum23);
    __m128 lanes = _mm_add_ps(_mm256_castps256_ps128(sum), _mm256_extractf128_ps(sum, 1));
    lanes = _mm_hadd_ps(lanes, lanes);
    lanes = _mm_hadd_ps(lanes, lanes);
    return _mm_cvtss_f32(lanes);
}

float dot_q1_scalar(const uint8_t *row, const float *input, uint64_t input_size) {
    float sum = 0.0f;
    const uint64_t blocks = input_size / kQ1Elements;
    for (uint64_t block_index = 0; block_index < blocks; ++block_index) {
        const uint8_t *block = row + block_index * kQ1Bytes;
        const float scale = decode_scale<false>(block);
        for (uint32_t i = 0; i < 128; ++i) {
            const uint32_t bit = (block[2 + i / 8] >> (i & 7)) & 1u;
            sum += input[block_index * 128 + i] * (bit ? scale : -scale);
        }
    }
    return sum;
}

struct ExpertWeights {
    uint32_t id = 0;
    std::vector<uint8_t> gate;
    std::vector<uint8_t> up;
    std::vector<uint8_t> down;
};

void read_exact(
        std::ifstream &stream,
        uint64_t offset,
        std::vector<uint8_t> &destination) {
    if (offset > static_cast<uint64_t>(std::numeric_limits<std::streamoff>::max()) ||
        destination.size() >
            static_cast<size_t>(std::numeric_limits<std::streamsize>::max())) {
        fail("file read exceeds stream limits");
    }
    stream.seekg(static_cast<std::streamoff>(offset), std::ios::beg);
    stream.read(
        reinterpret_cast<char *>(destination.data()),
        static_cast<std::streamsize>(destination.size()));
    if (!stream) fail("failed reading expert payload from GGUF");
}

std::vector<ExpertWeights> load_experts(
        const std::filesystem::path &path,
        const GgufInfo &gguf,
        const std::vector<uint32_t> &ids) {
    const uint64_t per_expert =
        gguf.gate.expert_bytes + gguf.up.expert_bytes + gguf.down.expert_bytes;
    const uint64_t total = checked_mul(ids.size(), per_expert, "loaded expert bytes");
    if (total > kMaxLoadedBytes) {
        fail("requested expert payload exceeds the 3.5 GiB audit cap");
    }

    std::ifstream stream(path, std::ios::binary);
    if (!stream) fail("cannot reopen GGUF payload");
    std::vector<ExpertWeights> experts;
    experts.reserve(ids.size());
    for (const uint32_t id : ids) {
        ExpertWeights expert;
        expert.id = id;
        expert.gate.resize(static_cast<size_t>(gguf.gate.expert_bytes));
        expert.up.resize(static_cast<size_t>(gguf.up.expert_bytes));
        expert.down.resize(static_cast<size_t>(gguf.down.expert_bytes));
        read_exact(stream, gguf.gate.absolute_offset + id * gguf.gate.expert_bytes, expert.gate);
        read_exact(stream, gguf.up.absolute_offset + id * gguf.up.expert_bytes, expert.up);
        read_exact(stream, gguf.down.absolute_offset + id * gguf.down.expert_bytes, expert.down);
        experts.push_back(std::move(expert));
    }
    return experts;
}

struct Job {
    const ExpertWeights *weights = nullptr;
};

class Executor {
public:
    Executor(
            uint32_t threads,
            uint64_t input_dim,
            uint64_t mid_dim,
            uint64_t output_dim,
            uint64_t gate_row_bytes,
            uint64_t down_row_bytes,
            DotFunction dot)
        : thread_count_(threads),
          input_dim_(input_dim),
          mid_dim_(mid_dim),
          output_dim_(output_dim),
          gate_row_bytes_(gate_row_bytes),
          down_row_bytes_(down_row_bytes),
          dot_(dot),
          input_(static_cast<size_t>(input_dim)),
          mid_(static_cast<size_t>(mid_dim)),
          output_(static_cast<size_t>(output_dim)) {
        for (uint64_t i = 0; i < input_dim_; ++i) {
            input_[static_cast<size_t>(i)] =
                0.75f * std::sin(static_cast<float>(i) * 0.0137f) +
                0.25f * std::cos(static_cast<float>(i) * 0.0311f);
        }
        workers_.reserve(thread_count_);
        for (uint32_t i = 0; i < thread_count_; ++i) {
            workers_.emplace_back([this, i] { worker_loop(i); });
        }
    }

    ~Executor() {
        {
            std::lock_guard lock(mutex_);
            stopping_ = true;
            ++generation_;
        }
        start_.notify_all();
        for (auto &worker : workers_) worker.join();
    }

    Executor(const Executor &) = delete;
    Executor &operator=(const Executor &) = delete;

    void run(const ExpertWeights &weights) {
        std::unique_lock lock(mutex_);
        phase_done_.store(0, std::memory_order_relaxed);
        workers_done_.store(0, std::memory_order_relaxed);
        job_.weights = &weights;
        ++generation_;
        start_.notify_all();
        finished_.wait(lock, [this] {
            return workers_done_.load(std::memory_order_acquire) == thread_count_;
        });
    }

    const std::vector<float> &input() const { return input_; }
    const std::vector<float> &output() const { return output_; }

private:
    void worker_loop(uint32_t worker_id) {
        uint64_t seen_generation = 0;
        for (;;) {
            Job local;
            {
                std::unique_lock lock(mutex_);
                start_.wait(lock, [this, seen_generation] {
                    return stopping_ || generation_ != seen_generation;
                });
                if (stopping_) return;
                seen_generation = generation_;
                local = job_;
            }

            const uint64_t mid_begin = mid_dim_ * worker_id / thread_count_;
            const uint64_t mid_end = mid_dim_ * (worker_id + 1) / thread_count_;
            for (uint64_t row = mid_begin; row < mid_end; ++row) {
                const float gate = dot_(
                    local.weights->gate.data() + row * gate_row_bytes_,
                    input_.data(), input_dim_);
                const float up = dot_(
                    local.weights->up.data() + row * gate_row_bytes_,
                    input_.data(), input_dim_);
                mid_[static_cast<size_t>(row)] =
                    (gate / (1.0f + std::exp(-gate))) * up;
            }

            phase_done_.fetch_add(1, std::memory_order_release);
            uint32_t spins = 0;
            while (phase_done_.load(std::memory_order_acquire) != thread_count_) {
                _mm_pause();
                if ((++spins & 0x3fffu) == 0) SwitchToThread();
            }

            const uint64_t out_begin = output_dim_ * worker_id / thread_count_;
            const uint64_t out_end = output_dim_ * (worker_id + 1) / thread_count_;
            for (uint64_t row = out_begin; row < out_end; ++row) {
                output_[static_cast<size_t>(row)] = dot_(
                    local.weights->down.data() + row * down_row_bytes_,
                    mid_.data(), mid_dim_);
            }

            if (workers_done_.fetch_add(1, std::memory_order_acq_rel) + 1 ==
                thread_count_) {
                std::lock_guard lock(mutex_);
                finished_.notify_one();
            }
        }
    }

    uint32_t thread_count_;
    uint64_t input_dim_;
    uint64_t mid_dim_;
    uint64_t output_dim_;
    uint64_t gate_row_bytes_;
    uint64_t down_row_bytes_;
    DotFunction dot_;
    std::vector<float> input_;
    std::vector<float> mid_;
    std::vector<float> output_;
    std::vector<std::thread> workers_;
    std::mutex mutex_;
    std::condition_variable start_;
    std::condition_variable finished_;
    Job job_;
    bool stopping_ = false;
    uint64_t generation_ = 0;
    std::atomic<uint32_t> phase_done_{0};
    std::atomic<uint32_t> workers_done_{0};
};

double percentile_sorted(const std::vector<double> &sorted, double q) {
    const double index = q * static_cast<double>(sorted.size() - 1);
    const size_t lo = static_cast<size_t>(index);
    const size_t hi = std::min(lo + 1, sorted.size() - 1);
    const double fraction = index - static_cast<double>(lo);
    return sorted[lo] * (1.0 - fraction) + sorted[hi] * fraction;
}

struct TimingResult {
    uint32_t threads = 0;
    double median_us = 0.0;
    double p10_us = 0.0;
    double p90_us = 0.0;
    double min_us = 0.0;
    double max_us = 0.0;
    double mean_us = 0.0;
    double checksum = 0.0;
};

volatile uint64_t g_touch_sink = 0;

void touch_all_experts(const std::vector<ExpertWeights> &experts) {
    uint64_t sum = 0;
    const auto touch = [&](const std::vector<uint8_t> &bytes) {
        for (size_t i = 0; i < bytes.size(); i += 4096) sum += bytes[i];
        if (!bytes.empty()) sum += bytes.back();
    };
    for (const auto &expert : experts) {
        touch(expert.gate);
        touch(expert.up);
        touch(expert.down);
    }
    g_touch_sink = sum;
}

TimingResult benchmark(
        uint32_t threads,
        uint32_t warmups,
        uint32_t reps,
        const GgufInfo &gguf,
        const std::vector<ExpertWeights> &experts,
        DotFunction dot) {
    Executor executor(
        threads,
        gguf.gate.dimensions[0],
        gguf.gate.dimensions[1],
        gguf.down.dimensions[1],
        gguf.gate.row_bytes,
        gguf.down.row_bytes,
        dot);

    touch_all_experts(experts);
    for (uint32_t i = 0; i < warmups; ++i) {
        executor.run(experts[i % experts.size()]);
    }

    LARGE_INTEGER frequency{};
    if (!QueryPerformanceFrequency(&frequency)) fail("QueryPerformanceFrequency failed");
    std::vector<double> timings;
    timings.reserve(reps);
    for (uint32_t i = 0; i < reps; ++i) {
        LARGE_INTEGER begin{}, end{};
        QueryPerformanceCounter(&begin);
        executor.run(experts[i % experts.size()]);
        QueryPerformanceCounter(&end);
        timings.push_back(
            static_cast<double>(end.QuadPart - begin.QuadPart) * 1.0e6 /
            static_cast<double>(frequency.QuadPart));
    }

    TimingResult result;
    result.threads = threads;
    result.mean_us =
        std::accumulate(timings.begin(), timings.end(), 0.0) / timings.size();
    std::sort(timings.begin(), timings.end());
    result.min_us = timings.front();
    result.max_us = timings.back();
    result.p10_us = percentile_sorted(timings, 0.10);
    result.median_us = percentile_sorted(timings, 0.50);
    result.p90_us = percentile_sorted(timings, 0.90);
    result.checksum = std::accumulate(
        executor.output().begin(), executor.output().end(), 0.0);
    return result;
}

std::string join_ids(const std::vector<uint32_t> &ids) {
    std::ostringstream output;
    for (size_t i = 0; i < ids.size(); ++i) {
        if (i != 0) output << ',';
        output << ids[i];
    }
    return output.str();
}

std::string dims(const TensorInfo &tensor) {
    std::ostringstream output;
    output << '[';
    for (size_t i = 0; i < tensor.dimensions.size(); ++i) {
        if (i != 0) output << ',';
        output << tensor.dimensions[i];
    }
    output << ']';
    return output.str();
}

}  // namespace

int main(int argc, char **argv) {
    try {
        const Options options = parse_options(argc, argv);
        const CpuInfo cpu = query_cpu();
        std::cout << std::boolalpha;
        std::cout << "AUDIT0_CPU schema=1\n";
        std::cout << "cpu_vendor=" << cpu.vendor << '\n';
        std::cout << "cpu_brand=" << cpu.brand << '\n';
        std::cout << "cpu_physical_cores=" << cpu.physical << '\n';
        std::cout << "cpu_logical_processors=" << cpu.logical << '\n';
        std::cout << "cpuid_avx_os=" << cpu.avx_os << '\n';
        std::cout << "cpuid_avx2=" << cpu.avx2 << '\n';
        std::cout << "cpuid_fma=" << cpu.fma << '\n';
        std::cout << "cpuid_f16c=" << cpu.f16c << '\n';
        std::cout << "cpuid_avx512f=" << cpu.avx512f << '\n';
        std::cout << "cpuid_avx512dq=" << cpu.avx512dq << '\n';
        std::cout << "cpuid_avx512bw=" << cpu.avx512bw << '\n';
        std::cout << "cpuid_avx512vl=" << cpu.avx512vl << '\n';
        if (!cpu.avx2) fail("AVX2 or OS AVX state is unavailable");

        initialize_sign_lut();
        const GgufInfo gguf = parse_gguf(options.sidecar, options.layer);
        const std::vector<uint32_t> ids =
            load_real_expert_ids(options, gguf.gate.dimensions[2]);
        const uint64_t per_expert =
            gguf.gate.expert_bytes + gguf.up.expert_bytes + gguf.down.expert_bytes;
        const std::vector<ExpertWeights> experts =
            load_experts(options.sidecar, gguf, ids);

        std::cout << "sidecar=" << options.sidecar.string() << '\n';
        std::cout << "sidecar_bytes=" << gguf.file_bytes << '\n';
        std::cout << "gguf_version=" << gguf.version << '\n';
        std::cout << "gguf_data_start=" << gguf.data_start << '\n';
        std::cout << "gguf_alignment=" << gguf.alignment << '\n';
        std::cout << "layer=" << options.layer << '\n';
        std::cout << "gate_type=" << gguf.gate.type << '\n';
        std::cout << "gate_dims=" << dims(gguf.gate) << '\n';
        std::cout << "up_type=" << gguf.up.type << '\n';
        std::cout << "up_dims=" << dims(gguf.up) << '\n';
        std::cout << "down_type=" << gguf.down.type << '\n';
        std::cout << "down_dims=" << dims(gguf.down) << '\n';
        std::cout << "matrix_expert_bytes=" << gguf.gate.expert_bytes << ','
                  << gguf.up.expert_bytes << ',' << gguf.down.expert_bytes << '\n';
        std::cout << "q1_expert_bytes=" << per_expert << '\n';
        std::cout << "loaded_experts=" << experts.size() << '\n';
        std::cout << "loaded_bytes=" << per_expert * experts.size() << '\n';
        std::cout << "expert_ids=" << join_ids(ids) << '\n';
        std::cout << "campaign_tsv=" << options.real_experts_tsv.string() << '\n';
        std::cout << "reps=" << options.reps << '\n';
        std::cout << "warmups=" << options.warmups << '\n';
        std::cout << "kernel=AVX2_fused_Q1_0_dequant_GEMV_float_activation\n";
        std::cout << "half_decode=" << (cpu.f16c ? "F16C" : "scalar") << '\n';

        const DotFunction dot =
            cpu.f16c ? &dot_q1_avx2<true> : &dot_q1_avx2<false>;
        std::vector<float> validation_input(
            static_cast<size_t>(gguf.gate.dimensions[0]));
        for (size_t i = 0; i < validation_input.size(); ++i) {
            validation_input[i] = std::sin(static_cast<float>(i) * 0.017f);
        }
        const float reference = dot_q1_scalar(
            experts.front().gate.data(), validation_input.data(), validation_input.size());
        const float candidate = dot(
            experts.front().gate.data(), validation_input.data(), validation_input.size());
        const double error = std::abs(static_cast<double>(reference) - candidate);
        const double tolerance = 2.0e-4 * std::max(1.0, std::abs(static_cast<double>(reference)));
        std::cout << std::setprecision(9);
        std::cout << "validation_scalar=" << reference << '\n';
        std::cout << "validation_avx2=" << candidate << '\n';
        std::cout << "validation_abs_error=" << error << '\n';
        std::cout << "validation_tolerance=" << tolerance << '\n';
        if (!(error <= tolerance)) fail("AVX2 Q1_0 dot failed scalar validation");

        std::cout << std::fixed << std::setprecision(3);
        for (const uint32_t threads : {1u, 4u, 8u, 12u}) {
            const TimingResult result = benchmark(
                threads, options.warmups, options.reps, gguf, experts, dot);
            const bool leaves_four =
                cpu.physical >= threads && cpu.physical - threads >= 4;
            std::cout
                << "RESULT threads=" << result.threads
                << " leaves_4_physical_cores=" << leaves_four
                << " median_us=" << result.median_us
                << " p10_us=" << result.p10_us
                << " p90_us=" << result.p90_us
                << " min_us=" << result.min_us
                << " max_us=" << result.max_us
                << " mean_us=" << result.mean_us
                << " checksum=" << result.checksum
                << '\n';
        }
        std::cout << "AUDIT0_CPU status=PASS\n";
        return 0;
    } catch (const std::exception &error) {
        std::cerr << "AUDIT0_CPU status=FAIL error=" << error.what() << '\n';
        return 1;
    }
}
