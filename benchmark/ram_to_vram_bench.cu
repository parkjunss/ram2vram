#include <cuda_runtime.h>

#include <algorithm>
#include <chrono>
#include <cstdlib>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>

#define CUDA_CHECK(call)                                                        \
    do {                                                                        \
        cudaError_t err__ = (call);                                             \
        if (err__ != cudaSuccess) {                                             \
            std::cerr << "CUDA error: " << cudaGetErrorString(err__)            \
                      << " (" << static_cast<int>(err__) << ")"                  \
                      << " at " << __FILE__ << ":" << __LINE__ << '\n';         \
            std::exit(EXIT_FAILURE);                                            \
        }                                                                       \
    } while (0)

struct Options {
    std::size_t totalMiB = 1024;  // total host/device buffer size
    int iterations = 20;
    bool writeCombined = false;
};

static Options parseArgs(int argc, char** argv) {
    Options o;

    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];

        if (arg == "--size-mib" && i + 1 < argc) {
            o.totalMiB = std::stoull(argv[++i]);
        } else if (arg == "--iterations" && i + 1 < argc) {
            o.iterations = std::stoi(argv[++i]);
        } else if (arg == "--wc") {
            o.writeCombined = true;
        } else if (arg == "--help" || arg == "-h") {
            std::cout
                << "Usage: ram_to_vram_bench [options]\n"
                << "  --size-mib N      Total transfer buffer size in MiB (default: 1024)\n"
                << "  --iterations N    Timed repetitions (default: 20)\n"
                << "  --wc              Use cudaHostAllocWriteCombined\n"
                << "\nExample:\n"
                << "  ram_to_vram_bench --size-mib 2048 --iterations 30 --wc\n";
            std::exit(EXIT_SUCCESS);
        } else {
            throw std::runtime_error("Unknown/invalid argument: " + arg);
        }
    }

    if (o.totalMiB < 2) {
        throw std::runtime_error("--size-mib must be >= 2");
    }
    if (o.iterations <= 0) {
        throw std::runtime_error("--iterations must be > 0");
    }

    return o;
}

static double gibPerSecond(std::size_t bytes, int iterations, double seconds) {
    const double gib =
        static_cast<double>(bytes) * static_cast<double>(iterations) /
        (1024.0 * 1024.0 * 1024.0);
    return gib / seconds;
}

static double gbPerSecond(std::size_t bytes, int iterations, double seconds) {
    const double gb =
        static_cast<double>(bytes) * static_cast<double>(iterations) / 1.0e9;
    return gb / seconds;
}

// One stream: entire buffer is copied serially.
static double benchmarkOneStream(
    void* dBuffer,
    const void* hBuffer,
    std::size_t bytes,
    int iterations)
{
    cudaStream_t stream{};
    CUDA_CHECK(cudaStreamCreateWithFlags(&stream, cudaStreamNonBlocking));

    // Warm-up.
    for (int i = 0; i < 3; ++i) {
        CUDA_CHECK(cudaMemcpyAsync(
            dBuffer, hBuffer, bytes, cudaMemcpyHostToDevice, stream));
    }
    CUDA_CHECK(cudaStreamSynchronize(stream));

    const auto begin = std::chrono::steady_clock::now();

    for (int i = 0; i < iterations; ++i) {
        CUDA_CHECK(cudaMemcpyAsync(
            dBuffer, hBuffer, bytes, cudaMemcpyHostToDevice, stream));
    }

    CUDA_CHECK(cudaStreamSynchronize(stream));

    const auto end = std::chrono::steady_clock::now();
    CUDA_CHECK(cudaStreamDestroy(stream));

    return std::chrono::duration<double>(end - begin).count();
}

// Two streams: the buffer is split in half and both H2D copies are queued
// independently. Reported throughput is AGGREGATE throughput across both streams.
static double benchmarkTwoStreams(
    void* dBuffer,
    const void* hBuffer,
    std::size_t bytes,
    int iterations)
{
    cudaStream_t stream0{}, stream1{};
    CUDA_CHECK(cudaStreamCreateWithFlags(&stream0, cudaStreamNonBlocking));
    CUDA_CHECK(cudaStreamCreateWithFlags(&stream1, cudaStreamNonBlocking));

    const std::size_t firstBytes = bytes / 2;
    const std::size_t secondBytes = bytes - firstBytes;

    auto* d0 = static_cast<unsigned char*>(dBuffer);
    auto* d1 = d0 + firstBytes;

    auto* h0 = static_cast<const unsigned char*>(hBuffer);
    auto* h1 = h0 + firstBytes;

    // Warm-up.
    for (int i = 0; i < 3; ++i) {
        CUDA_CHECK(cudaMemcpyAsync(
            d0, h0, firstBytes, cudaMemcpyHostToDevice, stream0));
        CUDA_CHECK(cudaMemcpyAsync(
            d1, h1, secondBytes, cudaMemcpyHostToDevice, stream1));
    }
    CUDA_CHECK(cudaStreamSynchronize(stream0));
    CUDA_CHECK(cudaStreamSynchronize(stream1));

    const auto begin = std::chrono::steady_clock::now();

    for (int i = 0; i < iterations; ++i) {
        CUDA_CHECK(cudaMemcpyAsync(
            d0, h0, firstBytes, cudaMemcpyHostToDevice, stream0));
        CUDA_CHECK(cudaMemcpyAsync(
            d1, h1, secondBytes, cudaMemcpyHostToDevice, stream1));
    }

    CUDA_CHECK(cudaStreamSynchronize(stream0));
    CUDA_CHECK(cudaStreamSynchronize(stream1));

    const auto end = std::chrono::steady_clock::now();

    CUDA_CHECK(cudaStreamDestroy(stream0));
    CUDA_CHECK(cudaStreamDestroy(stream1));

    return std::chrono::duration<double>(end - begin).count();
}

int main(int argc, char** argv) {
    try {
        const Options opt = parseArgs(argc, argv);

        int device = 0;
        CUDA_CHECK(cudaGetDevice(&device));

        cudaDeviceProp prop{};
        CUDA_CHECK(cudaGetDeviceProperties(&prop, device));

        std::cout << "=== CUDA RAM -> VRAM Benchmark ===\n";
        std::cout << "GPU               : " << prop.name << '\n';
        std::cout << "Compute capability: " << prop.major << '.' << prop.minor << '\n';
        std::cout << "asyncEngineCount  : " << prop.asyncEngineCount << '\n';
        std::cout << "PCI bus/device    : " << prop.pciBusID
                  << ":" << prop.pciDeviceID << '\n';
        std::cout << "Buffer            : " << opt.totalMiB << " MiB\n";
        std::cout << "Iterations        : " << opt.iterations << '\n';
        std::cout << "Pinned mode       : "
                  << (opt.writeCombined ? "WriteCombined" : "Default") << "\n\n";

        const std::size_t bytes = opt.totalMiB * 1024ULL * 1024ULL;

        void* hBuffer = nullptr;
        void* dBuffer = nullptr;

        unsigned int hostFlags = cudaHostAllocDefault;
        if (opt.writeCombined) {
            hostFlags |= cudaHostAllocWriteCombined;
        }

        std::cout << "Allocating pinned system RAM...\n";
        CUDA_CHECK(cudaHostAlloc(&hBuffer, bytes, hostFlags));

        std::cout << "Allocating VRAM...\n";
        CUDA_CHECK(cudaMalloc(&dBuffer, bytes));

        // Touch host pages so allocation/page initialization does not pollute timing.
        std::memset(hBuffer, 0x5A, bytes);

        // Initialize CUDA context and destination before timed run.
        CUDA_CHECK(cudaMemset(dBuffer, 0, bytes));
        CUDA_CHECK(cudaDeviceSynchronize());

        const double oneStreamSeconds =
            benchmarkOneStream(dBuffer, hBuffer, bytes, opt.iterations);

        const double twoStreamSeconds =
            benchmarkTwoStreams(dBuffer, hBuffer, bytes, opt.iterations);

        const double oneGBs =
            gbPerSecond(bytes, opt.iterations, oneStreamSeconds);
        const double twoGBs =
            gbPerSecond(bytes, opt.iterations, twoStreamSeconds);

        const double oneGiBs =
            gibPerSecond(bytes, opt.iterations, oneStreamSeconds);
        const double twoGiBs =
            gibPerSecond(bytes, opt.iterations, twoStreamSeconds);

        std::cout << std::fixed << std::setprecision(2);
        std::cout << "\n=== Results ===\n";
        std::cout << "1 stream H2D : "
                  << oneGBs << " GB/s  (" << oneGiBs << " GiB/s)"
                  << " | " << oneStreamSeconds << " s total\n";

        std::cout << "2 streams H2D: "
                  << twoGBs << " GB/s  (" << twoGiBs << " GiB/s)"
                  << " | " << twoStreamSeconds << " s total\n";

        std::cout << "2/1 ratio     : "
                  << (twoGBs / oneGBs) << "x\n";

        std::cout << "\nInterpretation:\n";
        std::cout
            << "- 2-stream result is aggregate RAM->VRAM throughput, not per-stream.\n"
            << "- Two H2D streams may NOT be faster than one stream; many GPUs share\n"
            << "  the same H2D copy-engine/path and ultimately the same PCIe link.\n"
            << "- If --wc improves H2D throughput, write-combined pinned RAM may be\n"
            << "  useful for one-way model-weight staging buffers.\n"
            << "- Use a large buffer (512-4096 MiB) so launch overhead is negligible.\n";

        CUDA_CHECK(cudaFree(dBuffer));
        CUDA_CHECK(cudaFreeHost(hBuffer));

        return EXIT_SUCCESS;
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << '\n';
        return EXIT_FAILURE;
    }
}
