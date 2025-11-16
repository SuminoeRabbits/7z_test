# 7z benchmark suite

Automated 7-Zip (`7z b`) benchmarking framework for comparing performance across compression levels, thread counts, and platforms.

## Quick Start

1. Install 7z:
```bash
sudo apt update && sudo apt install p7zip-full
```

2. Set up Python venv and run full benchmark:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
bash run_full_benchmark.sh
```

Results are saved to `results/aggregate.md` and `results/aggregate.csv`.

## Benchmark Parameters

- **Compression levels** (`-mx`): 1 (min), 5 (typ), 9 (max)
- **Thread counts** (`-mmt`): 1, 2, 4, 8, 16
- **Iterations**: controlled by `./bench.conf` (DEFAULT_ITERATIONS). Default: 1
- **Dictionary size** (`-md`): 26 (fixed)

## Single Configuration Example

```bash
python3 bench-7z.py --mx 5 --mmt 4 --md 26 --iterations 1 --outdir results
python3 aggregate_results.py --results-dir results --out-md results/aggregate.md
```

## Results Interpretation

Each JSON result file contains comprehensive benchmark data:

### JSON Structure

```json
{
  "platform": { /* system info like CPU model, RAM, etc */ },
  "7z": { "cmdline": "..." },
  "params": { "mx": 5, "mmt": 4, "md": 26, "iterations": 1 },
  "samples": [
    {
      "run": 1,
      "elapsed_s": 24.5,
      "returncode": 0,
      "throughput_MB_s": null,
      "benchmark": {
        "benchmark_table": [
          {
            "dict": 22,
            "compress": { "speed": 10763, "usage": 353, "r_u": 2965, "rating": 10471 },
            "decompress": { "speed": 136498, "usage": 398, "r_u": 2927, "rating": 11645 }
          },
          /* ... more dictionary sizes 23-26 ... */
        ],
        "averages": {
          "compress_speed": 9983, "compress_usage": 361, "compress_r_u": 2903, "compress_rating": 10472,
          "decompress_speed": 132250, "decompress_usage": 398, "decompress_r_u": 2898, "decompress_rating": 11521
        },
        "totals": { "usage": 379, "r_u": 2900, "rating": 10997 },
        "system_info": {
          "ram_mb": 15973, "cpu_threads": 4, "benchmark_threads": 4,
          "cpu_freq_1T": [1915, 1994, 1994, 1994, 1994, 1994, 1994]
        },
        "timing": {
          "kernel": { "seconds": 0.9, "percent": 1 },
          "user": { "seconds": 57.8, "percent": 96 },
          "process": { "seconds": 58.7, "percent": 97 },
          "global": { "seconds": 60.5, "percent": 100 }
        }
      },
      "raw_log": "results/raw/20251116T155122Z_mx5_mmt4_run1.log"
    }
  ],
  "stats": {
    "elapsed": { "count": 1, "mean": 24.5, "median": 24.5, "stdev": 0.0 },
    "throughput_MB_s": { "count": 0 }
  }
}
```

### Key Metrics

Each dictionary size in the benchmark table contains:
- **compress/decompress**:
  - `speed`: KiB/s (compression/decompression throughput)
  - `usage`: CPU usage percentage
  - `r_u`: MIPS per thread
  - `rating`: Total performance rating

### Aggregate Output

Output table columns:
- **mx**: Compression level (1=min, 5=typ, 9=max)
- **mmt**: Thread count
- **avg_s**: Average elapsed time (seconds)
- **stddev_s**: Standard deviation
- **throughput_MB_s**: Optional; throughput if parsed from 7z output

Example result row:
| platform_node | cpu_model | mmt | mx | iterations | md | avg_s | stddev_s |
|---|---|---:|---:|---:|---:|---:|---:|
| rpi5 | Cortex-A76 | 4 | 5 | 1 | 26 | 24.5 | 0.8 |

## Scripts

- `bench-7z.py`: Run `7z b` multiple iterations, measure time, output JSON
- `aggregate_results.py`: Scan JSON results, produce Markdown table and CSV
- `run_full_benchmark.sh`: Driver script; runs full matrix + aggregation
- `requirements.txt`: Python dependencies (currently stdlib only)

## Platform Comparison

Collect results from multiple platforms in `results/` subdirectories or run aggregator across platforms to merge tables.
