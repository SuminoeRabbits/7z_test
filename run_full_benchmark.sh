#!/bin/bash
#
# run_full_benchmark.sh
#
# Unified driver script to run the full 7z benchmark matrix (compression × threads)
# and aggregate results into Markdown and CSV tables.
#
# Usage:
#   bash run_full_benchmark.sh [--iterations N] [--cooldown S]
#
# Examples:
#   bash run_full_benchmark.sh
#   bash run_full_benchmark.sh --iterations 3 --cooldown 0.5
#

set -e

# Load bench.conf for defaults if present (defines DEFAULT_ITERATIONS)
if [ -f ./bench.conf ]; then
  # shellcheck disable=SC1091
  source ./bench.conf
fi

# Configuration
ITERATIONS=${ITERATIONS:-${DEFAULT_ITERATIONS:-1}}
COOLDOWN=${COOLDOWN:-0.5}
RESULTS_DIR="results"
COMPRESSION_LEVELS=(1 5 9)
THREAD_COUNTS=(1 2 4 8 16)

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --iterations)
      ITERATIONS="$2"
      shift 2
      ;;
    --cooldown)
      COOLDOWN="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

echo "Starting full 7z benchmark matrix..."
echo "  Compression levels: ${COMPRESSION_LEVELS[@]}"
echo "  Thread counts: ${THREAD_COUNTS[@]}"
echo "  Iterations per config: $ITERATIONS"
echo "  Cooldown between runs: $COOLDOWN seconds"
echo ""

# Run benchmark matrix
for mx in "${COMPRESSION_LEVELS[@]}"; do
  for mmt in "${THREAD_COUNTS[@]}"; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Running: mx=$mx mmt=$mmt ($(($ITERATIONS)) iterations)"
    python3 bench-7z.py --mx "$mx" --mmt "$mmt" --md 26 --iterations "$ITERATIONS" --cooldown "$COOLDOWN" --outdir "$RESULTS_DIR"
  done
done

echo ""
echo "Benchmark matrix complete. Aggregating results..."

# Aggregate results
python3 aggregate_results.py --results-dir "$RESULTS_DIR" --out-md "$RESULTS_DIR/aggregate.md" --out-csv "$RESULTS_DIR/aggregate.csv"

echo ""
echo "✓ Full benchmark finished!"
echo "  Results: $RESULTS_DIR/"
echo "  Markdown table: $RESULTS_DIR/aggregate.md"
echo "  CSV table: $RESULTS_DIR/aggregate.csv"
