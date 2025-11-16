#!/usr/bin/env python3
"""
aggregate_results.py

Scan `results/` for JSON result files produced by `bench-7z.py` and generate a combined
Markdown table and CSV for easy comparison across platforms/configurations.

Usage:
  python3 aggregate_results.py --results-dir results --out-md results/aggregate.md --out-csv results/aggregate.csv

The script is defensive: if fields are missing it leaves empty cells.
"""

import argparse
import json
import os
import csv
from pathlib import Path


def collect_json_files(results_dir):
    files = []
    for p in Path(results_dir).rglob('*.json'):
        # skip files under results/raw/ if present
        if 'raw' in p.parts:
            continue
        files.append(p)
    return sorted(files)


def safe_get(d, *keys, default=''):
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k, default)
    return cur


def row_from_json(path):
    try:
        data = json.loads(path.read_text())
    except Exception as e:
        return None

    info = data.get('platform', {}).get('info', {})
    params = data.get('params', {})
    stats = data.get('stats', {})

    row = {
        'file': path.name,
        'platform_node': safe_get(info, 'hostname') or safe_get(info, 'uname', 'node') or '',
        'cpu_model': safe_get(info, 'model_name') or '',
        'physical_cores': safe_get(info, 'cores_per_socket') or '',
        'logical_cores': safe_get(info, 'logical_cpus') or '',
        'ht': safe_get(info, 'ht'),
        'mx': params.get('mx', ''),
        'mmt': params.get('mmt', ''),
        'md': params.get('md', ''),
        'iterations': params.get('iterations', ''),
        'avg_s': safe_get(stats, 'elapsed', 'mean') if isinstance(safe_get(stats, 'elapsed'), dict) else '',
        'stddev_s': safe_get(stats, 'elapsed', 'stdev') if isinstance(safe_get(stats, 'elapsed'), dict) else '',
        'throughput_MB_s': safe_get(stats, 'throughput_MB_s', 'mean') if isinstance(safe_get(stats, 'throughput_MB_s'), dict) else '',
    }
    return row


def write_markdown(rows, out_md):
    headers = ['file', 'platform_node', 'cpu_model', 'physical_cores', 'logical_cores', 'ht', 'mmt', 'mx', 'iterations', 'md', 'avg_s', 'stddev_s', 'throughput_MB_s']
    lines = []
    lines.append('| ' + ' | '.join(headers) + ' |')
    lines.append('|' + '|'.join(['---'] * len(headers)) + '|')
    for r in rows:
        vals = [str(r.get(h, '')) for h in headers]
        lines.append('| ' + ' | '.join(vals) + ' |')

    Path(out_md).write_text('\n'.join(lines) + '\n')


def write_csv(rows, out_csv):
    headers = ['file', 'platform_node', 'cpu_model', 'physical_cores', 'logical_cores', 'ht', 'mmt', 'mx', 'iterations', 'md', 'avg_s', 'stddev_s', 'throughput_MB_s']
    with open(out_csv, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, '') for k in headers})


def main():
    parser = argparse.ArgumentParser(description='Aggregate bench-7z JSON results into Markdown/CSV')
    parser.add_argument('--results-dir', default='results', help='Directory to scan for JSON result files')
    parser.add_argument('--out-md', default='results/aggregate.md', help='Output Markdown file')
    parser.add_argument('--out-csv', default='results/aggregate.csv', help='Output CSV file')
    args = parser.parse_args()

    files = collect_json_files(args.results_dir)
    if not files:
        print('No JSON result files found in', args.results_dir)
        return

    rows = []
    for p in files:
        r = row_from_json(p)
        if r:
            rows.append(r)

    # sort rows for readability
    rows.sort(key=lambda x: (str(x.get('platform_node', '')), int(x.get('mx') or 0), int(x.get('mmt') or 0)))

    os.makedirs(os.path.dirname(args.out_md), exist_ok=True)
    write_markdown(rows, args.out_md)
    write_csv(rows, args.out_csv)

    print(f'Wrote aggregated Markdown to {args.out_md} and CSV to {args.out_csv}')


if __name__ == '__main__':
    main()
