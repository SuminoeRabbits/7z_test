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
