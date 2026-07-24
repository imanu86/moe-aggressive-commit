// Portable DS4 teacher extractor used by make_teacher_outputs.py --backend gcc.
//
// The tensor geometry, GGUF addressing, dequantization calls, and scalar
// reference forward intentionally match ste_trainer/ste_backend.cpp.  Keep
// floating-point contraction disabled in the build command: teacher weights
// must be bit-identical across the MSVC and GCC builds.

#include <algorithm>
#include <array>
#include <chrono>
#include <cctype>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

#include "ds4_q1_ref.h"

namespace fs = std::filesystem;
using Clock = std::chrono::steady_clock;

static constexpr int N_EMBD = 4096;
static constexpr int N_MID = 2048;
static constexpr int N_EXPERT = 256;

[[noreturn]] static void fail(const std::string &message) {
    throw std::runtime_error(message);
}

static double seconds_since(Clock::time_point start) {
    return std::chrono::duration<double>(Clock::now() - start).count();
}

static std::string read_text(const fs::path &path) {
    std::ifstream stream(path, std::ios::binary);
    if (!stream) {
        fail("cannot open " + path.string());
    }
    std::ostringstream contents;
    contents << stream.rdbuf();
    return contents.str();
}

static size_t find_key(const std::string &json, const std::string &key) {
    const std::string needle = "\"" + key + "\"";
    size_t position = json.find(needle);
    if (position == std::string::npos) {
        fail("missing JSON key: " + key);
    }
    position = json.find(':', position + needle.size());
    if (position == std::string::npos) {
        fail("missing JSON colon: " + key);
    }
    return position + 1;
}

static std::string json_string(const std::string &json, const std::string &key) {
    size_t position = find_key(json, key);
    while (position < json.size() && std::isspace(static_cast<unsigned char>(json[position]))) {
        ++position;
    }
    if (position >= json.size() || json[position] != '"') {
        fail("JSON key is not a string: " + key);
    }
    std::string value;
    for (++position; position < json.size(); ++position) {
        const char current = json[position];
        if (current == '"') {
            return value;
        }
        if (current != '\\') {
            value.push_back(current);
            continue;
        }
        if (++position >= json.size()) {
            break;
        }
        const char escaped = json[position];
        if (escaped == '"' || escaped == '\\' || escaped == '/') {
            value.push_back(escaped);
        } else if (escaped == 'n') {
            value.push_back('\n');
        } else if (escaped == 'r') {
            value.push_back('\r');
        } else if (escaped == 't') {
            value.push_back('\t');
        } else {
            fail("unsupported JSON escape in " + key);
        }
    }
    fail("unterminated JSON string: " + key);
}

static long long json_integer(const std::string &json, const std::string &key) {
    size_t position = find_key(json, key);
    while (position < json.size() && std::isspace(static_cast<unsigned char>(json[position]))) {
        ++position;
    }
    char *end = nullptr;
    const long long value = std::strtoll(json.c_str() + position, &end, 10);
    if (end == json.c_str() + position) {
        fail("JSON key is not an integer: " + key);
    }
    return value;
}

static bool json_boolean(const std::string &json, const std::string &key) {
    size_t position = find_key(json, key);
    while (position < json.size() && std::isspace(static_cast<unsigned char>(json[position]))) {
        ++position;
    }
    if (json.compare(position, 4, "true") == 0) {
        return true;
    }
    if (json.compare(position, 5, "false") == 0) {
        return false;
    }
    fail("JSON key is not boolean: " + key);
}

static std::string json_escape(const std::string &value) {
    std::string escaped;
    for (const char current : value) {
        if (current == '\\' || current == '"') {
            escaped.push_back('\\');
            escaped.push_back(current);
        } else if (current == '\n') {
            escaped += "\\n";
        } else {
            escaped.push_back(current);
        }
    }
    return escaped;
}

struct Options {
    int layer = -1;
    int expert = -1;
    std::string teacher;
    std::string out;
    std::vector<std::string> traces;
};

static void usage() {
    std::cout
        << "Portable single-expert DS4 teacher extractor\n\n"
        << "Required: --layer N --expert N --traces MANIFEST [--traces MANIFEST ...]\n"
        << "          --teacher GGUF --out DIR\n";
}

static Options parse_args(int argc, char **argv) {
    Options options;
    auto value = [&](int &index) -> std::string {
        if (++index >= argc) {
            fail(std::string("missing value for ") + argv[index - 1]);
        }
        return argv[index];
    };
    for (int index = 1; index < argc; ++index) {
        const std::string argument = argv[index];
        if (argument == "--help" || argument == "-h") {
            usage();
            std::exit(0);
        } else if (argument == "--layer") {
            options.layer = std::stoi(value(index));
        } else if (argument == "--expert") {
            options.expert = std::stoi(value(index));
        } else if (argument == "--traces") {
            options.traces.push_back(value(index));
        } else if (argument == "--teacher") {
            options.teacher = value(index);
        } else if (argument == "--out") {
            options.out = value(index);
        } else {
            fail("unknown argument: " + argument);
        }
    }
    if (options.layer < 0 || options.expert < 0 || options.expert >= N_EXPERT ||
        options.traces.empty() || options.teacher.empty() || options.out.empty()) {
        fail("--layer, --expert, --traces, --teacher, and --out are required");
    }
    return options;
}

#pragma pack(push, 1)
struct TraceHeader {
    char magic[8];
    uint32_t version;
    uint32_t header_bytes;
    uint32_t dtype;
    uint32_t dim;
    uint32_t max_samples;
    uint32_t samples;
    uint32_t vector_bytes;
    uint32_t reserved0;
    uint64_t payload_bytes;
    uint64_t byte_budget;
    uint64_t reserved1;
};
#pragma pack(pop)
static_assert(sizeof(TraceHeader) == 64, "trace header size");

struct TraceData {
    std::vector<float> x;
    size_t sample_count = 0;
};

static TraceData load_traces(const Options &options) {
    std::vector<fs::path> manifests;
    manifests.reserve(options.traces.size());
    for (const std::string &trace : options.traces) {
        const fs::path path(trace);
        if (!fs::exists(path)) {
            fail("trace does not exist: " + trace);
        }
        manifests.push_back(fs::weakly_canonical(path));
    }
    std::sort(manifests.begin(), manifests.end());
    manifests.erase(std::unique(manifests.begin(), manifests.end()), manifests.end());

    TraceData data;
    for (const fs::path &manifest_path : manifests) {
        const std::string manifest = read_text(manifest_path);
        if (json_string(manifest, "schema") != "ds4_expert_recovery_manifest_v1" ||
            json_string(manifest, "status") != "complete") {
            fail("unsupported/incomplete trace manifest: " + manifest_path.string());
        }
        if (!json_boolean(manifest, "input_only") ||
            json_boolean(manifest, "teacher_output_captured")) {
            fail("trace is not input-only: " + manifest_path.string());
        }
        if (json_string(manifest, "teacher_output_reconstruction") !=
            "offline_exact_iq2_from_captured_input") {
            fail("unexpected teacher reconstruction contract: " + manifest_path.string());
        }
        if (json_string(manifest, "dtype") != "float32-le" ||
            json_integer(manifest, "header_bytes") != 64 ||
            json_integer(manifest, "vector_dim") != N_EMBD ||
            json_integer(manifest, "vector_bytes_per_sample") != N_EMBD * 4 ||
            json_integer(manifest, "layer") != options.layer ||
            json_integer(manifest, "expert") != options.expert) {
            fail("trace geometry/dtype/target mismatch: " + manifest_path.string());
        }

        const int samples = static_cast<int>(json_integer(manifest, "sample_count"));
        if (samples <= 0) {
            fail("empty trace: " + manifest_path.string());
        }
        const fs::path binary_path =
            manifest_path.parent_path() / json_string(manifest, "binary_file");
        const uint64_t expected_size = static_cast<uint64_t>(json_integer(manifest, "binary_bytes"));
        if (fs::file_size(binary_path) != expected_size) {
            fail("trace byte-size mismatch: " + manifest_path.string());
        }

        std::ifstream binary(binary_path, std::ios::binary);
        TraceHeader header{};
        binary.read(reinterpret_cast<char *>(&header), sizeof(header));
        if (!binary || std::memcmp(header.magic, "DS4ERTR1", 8) != 0 ||
            header.version != 1 || header.header_bytes != 64 || header.dtype != 1 ||
            header.dim != N_EMBD || header.samples != static_cast<uint32_t>(samples) ||
            header.vector_bytes != N_EMBD * 4 ||
            header.payload_bytes != static_cast<uint64_t>(samples) * N_EMBD * 4 ||
            header.reserved0 != 0 || header.reserved1 != 0) {
            fail("invalid trace binary header: " + binary_path.string());
        }

        const size_t base = data.x.size();
        data.x.resize(base + static_cast<size_t>(samples) * N_EMBD);
        binary.read(
            reinterpret_cast<char *>(data.x.data() + base),
            static_cast<std::streamsize>(static_cast<size_t>(samples) * N_EMBD * 4));
        if (!binary || binary.peek() != EOF) {
            fail("trace binary payload mismatch: " + binary_path.string());
        }
        data.sample_count += static_cast<size_t>(samples);
    }
    if (data.sample_count < 3) {
        fail("at least three samples are required");
    }
    for (const float value : data.x) {
        if (!std::isfinite(value)) {
            fail("non-finite activation found");
        }
    }
    return data;
}

struct TensorInfo {
    std::string name;
    std::array<uint64_t, 4> dims{};
    uint32_t ndims = 0;
    uint32_t type = 0;
    uint64_t offset = 0;
};

struct ModelInfo {
    uint64_t data_start = 0;
    TensorInfo gate;
    TensorInfo up;
    TensorInfo down;
};

static uint32_t read_u32(std::ifstream &stream) {
    uint32_t value;
    stream.read(reinterpret_cast<char *>(&value), 4);
    if (!stream) {
        fail("unexpected GGUF EOF");
    }
    return value;
}

static uint64_t read_u64(std::ifstream &stream) {
    uint64_t value;
    stream.read(reinterpret_cast<char *>(&value), 8);
    if (!stream) {
        fail("unexpected GGUF EOF");
    }
    return value;
}

static void skip_bytes(std::ifstream &stream, uint64_t count) {
    stream.seekg(static_cast<std::streamoff>(count), std::ios::cur);
    if (!stream) {
        fail("GGUF seek failed");
    }
}

static uint64_t scalar_size(uint32_t type) {
    static const uint8_t sizes[13] = {1, 1, 2, 2, 4, 4, 4, 1, 0, 0, 8, 8, 8};
    if (type >= 13 || sizes[type] == 0) {
        fail("unsupported GGUF metadata type");
    }
    return sizes[type];
}

static std::string read_string(std::ifstream &stream) {
    const uint64_t length = read_u64(stream);
    if (length > (1u << 24)) {
        fail("absurd GGUF string");
    }
    std::string value(static_cast<size_t>(length), '\0');
    stream.read(value.data(), static_cast<std::streamsize>(length));
    if (!stream) {
        fail("GGUF string EOF");
    }
    return value;
}

static void skip_value(std::ifstream &stream, uint32_t type) {
    if (type == 8) {
        skip_bytes(stream, read_u64(stream));
        return;
    }
    if (type == 9) {
        const uint32_t element_type = read_u32(stream);
        const uint64_t count = read_u64(stream);
        if (element_type == 8) {
            for (uint64_t index = 0; index < count; ++index) {
                skip_bytes(stream, read_u64(stream));
            }
            return;
        }
        if (element_type == 9) {
            fail("nested GGUF array");
        }
        skip_bytes(stream, scalar_size(element_type) * count);
        return;
    }
    skip_bytes(stream, scalar_size(type));
}

static ModelInfo parse_model(const fs::path &path, int layer) {
    std::ifstream stream(path, std::ios::binary);
    if (!stream) {
        fail("cannot open GGUF: " + path.string());
    }
    if (read_u32(stream) != 0x46554747u || read_u32(stream) != 3) {
        fail("expected GGUF v3");
    }
    const uint64_t tensor_count = read_u64(stream);
    const uint64_t metadata_count = read_u64(stream);
    for (uint64_t index = 0; index < metadata_count; ++index) {
        (void)read_string(stream);
        skip_value(stream, read_u32(stream));
    }

    const std::string prefix = "blk." + std::to_string(layer) + ".";
    ModelInfo model;
    for (uint64_t index = 0; index < tensor_count; ++index) {
        TensorInfo tensor;
        tensor.name = read_string(stream);
        tensor.ndims = read_u32(stream);
        if (tensor.ndims < 1 || tensor.ndims > 4) {
            fail("bad GGUF tensor rank");
        }
        for (uint32_t dimension = 0; dimension < tensor.ndims; ++dimension) {
            tensor.dims[dimension] = read_u64(stream);
        }
        tensor.type = read_u32(stream);
        tensor.offset = read_u64(stream);
        if (tensor.name == prefix + "ffn_gate_exps.weight") {
            model.gate = tensor;
        } else if (tensor.name == prefix + "ffn_up_exps.weight") {
            model.up = tensor;
        } else if (tensor.name == prefix + "ffn_down_exps.weight") {
            model.down = tensor;
        }
    }
    const uint64_t position = static_cast<uint64_t>(stream.tellg());
    model.data_start = (position + 31u) & ~31u;
    if (model.gate.name.empty() || model.up.name.empty() || model.down.name.empty()) {
        fail("missing requested expert tensors in " + path.string());
    }
    return model;
}

struct Expert {
    std::vector<float> gate;
    std::vector<float> up;
    std::vector<float> down;
};

static std::vector<float> decode_tensor(
    std::ifstream &stream,
    const ModelInfo &model,
    const TensorInfo &tensor,
    int expert,
    bool down) {
    const int columns = down ? N_MID : N_EMBD;
    const int rows = down ? N_EMBD : N_MID;
    if (tensor.ndims != 3 ||
        tensor.dims[0] != static_cast<uint64_t>(columns) ||
        tensor.dims[1] != static_cast<uint64_t>(rows) ||
        tensor.dims[2] != N_EXPERT) {
        fail("expert tensor geometry mismatch: " + tensor.name);
    }
    if (tensor.type != DS4_Q1_REF_TYPE_IQ2_XXS &&
        tensor.type != DS4_Q1_REF_TYPE_Q2_K) {
        fail("teacher tensor type unsupported: " + tensor.name);
    }
    const size_t row_bytes = ds4_q1_ref_row_size(static_cast<int>(tensor.type), columns);
    if (row_bytes == 0) {
        fail("unsupported tensor row size");
    }
    const uint64_t expert_bytes = static_cast<uint64_t>(row_bytes) * rows;
    stream.seekg(
        static_cast<std::streamoff>(
            model.data_start + tensor.offset + expert_bytes * static_cast<uint64_t>(expert)),
        std::ios::beg);
    if (!stream) {
        fail("expert tensor seek failed");
    }

    std::vector<uint8_t> source(row_bytes);
    std::vector<float> output(static_cast<size_t>(rows) * columns);
    for (int row = 0; row < rows; ++row) {
        stream.read(reinterpret_cast<char *>(source.data()), static_cast<std::streamsize>(row_bytes));
        if (!stream) {
            fail("short expert tensor payload");
        }
        const int result = ds4_q1_ref_dequant_row(
            static_cast<int>(tensor.type),
            source.data(),
            columns,
            output.data() + static_cast<size_t>(row) * columns);
        if (result != 0) {
            fail("reference dequant failed");
        }
    }
    return output;
}

static Expert decode_expert(
    const fs::path &path,
    int layer,
    int expert,
    ModelInfo *model_info) {
    *model_info = parse_model(path, layer);
    std::ifstream stream(path, std::ios::binary);
    if (!stream) {
        fail("cannot reopen GGUF");
    }
    Expert result;
    result.gate = decode_tensor(stream, *model_info, model_info->gate, expert, false);
    result.up = decode_tensor(stream, *model_info, model_info->up, expert, false);
    result.down = decode_tensor(stream, *model_info, model_info->down, expert, true);
    return result;
}

static float silu(float value) {
    return value / (1.0f + ::expf(-value));
}

static void forward_expert(
    const float *input,
    int sample_count,
    const Expert &weights,
    std::vector<float> &output) {
    auto linear = [&](
        const float *linear_input,
        int count,
        const std::vector<float> &matrix,
        int rows,
        int columns,
        float *linear_output) {
#pragma omp parallel for schedule(static)
        for (int row = 0; row < rows; ++row) {
            for (int sample = 0; sample < count; ++sample) {
                float sum = 0.0f;
                const float *x = linear_input + static_cast<size_t>(sample) * columns;
                const float *w = matrix.data() + static_cast<size_t>(row) * columns;
                for (int column = 0; column < columns; ++column) {
                    sum += x[column] * w[column];
                }
                linear_output[static_cast<size_t>(sample) * rows + row] = sum;
            }
        }
    };

    std::vector<float> gate(static_cast<size_t>(sample_count) * N_MID);
    std::vector<float> up(static_cast<size_t>(sample_count) * N_MID);
    std::vector<float> hidden(static_cast<size_t>(sample_count) * N_MID);
    output.resize(static_cast<size_t>(sample_count) * N_EMBD);
    linear(input, sample_count, weights.gate, N_MID, N_EMBD, gate.data());
    linear(input, sample_count, weights.up, N_MID, N_EMBD, up.data());
#pragma omp parallel for schedule(static)
    for (int64_t index = 0; index < static_cast<int64_t>(sample_count) * N_MID; ++index) {
        hidden[static_cast<size_t>(index)] =
            silu(gate[static_cast<size_t>(index)]) * up[static_cast<size_t>(index)];
    }
    linear(hidden.data(), sample_count, weights.down, N_EMBD, N_MID, output.data());
}

static void write_raw(const fs::path &path, const std::vector<float> &values) {
    std::ofstream stream(path, std::ios::binary);
    if (!stream) {
        fail("cannot create " + path.string());
    }
    stream.write(
        reinterpret_cast<const char *>(values.data()),
        static_cast<std::streamsize>(values.size() * sizeof(float)));
    if (!stream) {
        fail("raw write failed: " + path.string());
    }
}

int main(int argc, char **argv) {
    try {
        const auto wall_start = Clock::now();
        const Options options = parse_args(argc, argv);
        const fs::path output_dir = fs::absolute(options.out);
        fs::create_directories(output_dir);

        TraceData traces = load_traces(options);
        const auto decode_start = Clock::now();
        ModelInfo model;
        Expert teacher =
            decode_expert(options.teacher, options.layer, options.expert, &model);
        const double decode_seconds = seconds_since(decode_start);

        const auto forward_start = Clock::now();
        std::vector<float> teacher_output;
        forward_expert(
            traces.x.data(),
            static_cast<int>(traces.sample_count),
            teacher,
            teacher_output);
        const double forward_seconds = seconds_since(forward_start);

        const fs::path teacher_raw = output_dir / "teacher_y.f32le";
        write_raw(teacher_raw, teacher_output);
        write_raw(output_dir / "teacher_gate.f32le", teacher.gate);
        write_raw(output_dir / "teacher_up.f32le", teacher.up);
        write_raw(output_dir / "teacher_down.f32le", teacher.down);

        std::ofstream metadata(output_dir / "teacher_y.meta.json", std::ios::binary);
        metadata
            << std::setprecision(17)
            << "{\"schema\":\"ds4_teacher_outputs_raw_v1\","
            << "\"layer\":" << options.layer
            << ",\"expert\":" << options.expert
            << ",\"sample_count\":" << traces.sample_count
            << ",\"shape\":[" << traces.sample_count << "," << N_EMBD << "]"
            << ",\"dtype\":\"float32-le\",\"raw_file\":\"teacher_y.f32le\""
            << ",\"weight_files\":{\"gate\":\"teacher_gate.f32le\","
            << "\"up\":\"teacher_up.f32le\",\"down\":\"teacher_down.f32le\"}"
            << ",\"teacher\":\""
            << json_escape(fs::absolute(options.teacher).string()) << "\""
            << ",\"source_types\":{\"teacher\":["
            << model.gate.type << "," << model.up.type << "," << model.down.type << "]}"
            << ",\"decode_seconds\":" << decode_seconds
            << ",\"forward_seconds\":" << forward_seconds
            << ",\"decode_forward_seconds\":" << decode_seconds + forward_seconds
            << ",\"wall_seconds\":" << seconds_since(wall_start)
            << "}\n";
        if (!metadata) {
            fail("metadata write failed");
        }

        std::cout << "teacher_y raw: " << teacher_raw.string() << "\n";
        std::cout << "samples: " << traces.sample_count << " shape: ["
                  << traces.sample_count << "," << N_EMBD << "]\n";
        std::cout << "decode_seconds: " << decode_seconds
                  << " forward_seconds: " << forward_seconds << "\n";
        return 0;
    } catch (const std::exception &error) {
        std::cerr << "teacher_backend: " << error.what() << "\n";
        return 1;
    }
}
