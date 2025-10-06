# ⚡ Benchmark Tools

Scripts để đo performance và so sánh hiệu năng của các components.

## Scripts

- **benchmark_cpu_vs_gpu.py** - So sánh performance giữa CPU và GPU
- **benchmark_performance.py** - Đo hiệu năng tổng quát của hệ thống

## Cách sử dụng

```bash
# Chạy từ project root
python tools/benchmarks/benchmark_performance.py

# Hoặc so sánh CPU vs GPU
python tools/benchmarks/benchmark_cpu_vs_gpu.py
```

## Metrics đo

- OCR processing time
- Inference speed
- Memory usage
- Throughput (documents/minute)

## Output

Kết quả thường được lưu dưới dạng:
- Console output với timing details
- JSON reports (tùy script)
- Performance comparison tables
