#!/usr/bin/env python3
"""
bench-7z.py

Python wrapper to run `7z b` multiple times per configuration and emit JSON results.

Features:
- Runs `7z b` with given -mx, -mmt, -md for N iterations (wrapper-driven iterations).
- Measures wall-clock time per run and captures raw stdout/stderr.
- Attempts to parse throughput (MB/s) if present in output.
- Writes a JSON file per configuration under results/ with metadata, samples, and aggregated stats.

Usage example:
    python3 bench-7z.py --mx 5 --mmt 4 --md 26 --iterations 1 --outdir results

This script intentionally measures elapsed time in Python (using time.perf_counter) rather than relying on /usr/bin/time for portability.
"""

import argparse
import json
import os
import subprocess
import sys
import time
import datetime
import platform
import socket
import re
from statistics import mean, median, stdev


def run_one(cmd, timeout=None):
    start = time.perf_counter()
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
    end = time.perf_counter()
    elapsed = end - start
    return elapsed, proc.returncode, proc.stdout, proc.stderr


def parse_throughput(text):
    # Try to find MB/s or KB/s tokens in the 7z output
    # Example patterns: "123.45 MB/s" or "987 KB/s"
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*MB/s", text)
    if m:
        return float(m.group(1))
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*KB/s", text)
    if m:
        return float(m.group(1)) / 1024.0
    return None


def parse_7z_benchmark_output(text):
    """
    Parse 7z benchmark output and extract detailed metrics.
    Returns a dict with:
    - benchmark_table: list of dict with Dict, Speed, Usage, R/U, Rating for compress/decompress
    - averages: dict with avg compress/decompress metrics
    - totals: dict with total metrics
    - system_info: dict with system info (RAM, CPU freqs, threads)
    - timing: dict with kernel/user/process/global times
    """
    result = {
        'benchmark_table': [],
        'averages': {},
        'totals': {},
        'system_info': {},
        'timing': {}
    }
    
    lines = text.split('\n')
    
    # Parse system info (RAM, CPU threads, etc.)
    for i, line in enumerate(lines):
        if 'RAM size:' in line:
            # Example: "RAM size:   15973 MB,  # CPU hardware threads:   4"
            m = re.search(r'RAM size:\s+([0-9]+)\s+MB', line)
            if m:
                result['system_info']['ram_mb'] = int(m.group(1))
            m = re.search(r'# CPU hardware threads:\s+(\d+)', line)
            if m:
                result['system_info']['cpu_threads'] = int(m.group(1))
        
        if 'RAM usage:' in line:
            # Example: "RAM usage:    889 MB,  # Benchmark threads:      4"
            m = re.search(r'RAM usage:\s+([0-9]+)\s+MB', line)
            if m:
                result['system_info']['ram_usage_mb'] = int(m.group(1))
            m = re.search(r'# Benchmark threads:\s+(\d+)', line)
            if m:
                result['system_info']['benchmark_threads'] = int(m.group(1))
        
        # Parse CPU frequency (1T, 2T lines)
        if 'CPU Freq' in line:
            # Example: "1T CPU Freq (MHz):  1915  1994  1994  1994  1994  1994  1994"
            match = re.match(r'(\d+T)\s+CPU Freq \(MHz\):\s+(.*)', line)
            if match:
                freqs = match.group(2).strip().split()
                key = f'cpu_freq_{match.group(1)}'
                result['system_info'][key] = [int(f.rstrip('%')) for f in freqs]
        
        # Parse timing info
        if 'Kernel  Time' in line or 'User    Time' in line or 'Process Time' in line or 'Global  Time' in line:
            # Example: "Kernel  Time =     0.900 =    1%"
            m = re.match(r'(\w+)\s+Time\s+=\s+([\d.]+)\s+=\s+(\d+)%', line)
            if m:
                result['timing'][m.group(1).lower()] = {
                    'seconds': float(m.group(2)),
                    'percent': int(m.group(3))
                }
    
    # Parse benchmark table
    # Find the header line
    header_idx = -1
    for i, line in enumerate(lines):
        if 'Dict' in line and 'Speed' in line and 'Usage' in line:
            header_idx = i
            break
    
    if header_idx >= 0:
        # Parse from header onwards
        i = header_idx + 1
        while i < len(lines):
            line = lines[i]
            
            # Skip header sub-lines and empty lines before data starts
            if line.strip() == '' or 'KiB/s' in line or 'Compressing' in line:
                i += 1
                continue
            
            # Stop at separator
            if '--' in line and '|' in line:
                i += 1
                continue
            
            # Parse average line
            if line.startswith('Avr:'):
                # Split by | to get compress and decompress parts
                parts = line.split('|')
                if len(parts) >= 1:
                    # Compress metrics
                    compress_nums = re.findall(r'\d+', parts[0][4:])
                    if len(compress_nums) >= 4:
                        result['averages']['compress_speed'] = int(compress_nums[0])
                        result['averages']['compress_usage'] = int(compress_nums[1])
                        result['averages']['compress_r_u'] = int(compress_nums[2])
                        result['averages']['compress_rating'] = int(compress_nums[3])
                
                if len(parts) >= 2:
                    # Decompress metrics
                    decompress_nums = re.findall(r'\d+', parts[1])
                    if len(decompress_nums) >= 4:
                        result['averages']['decompress_speed'] = int(decompress_nums[0])
                        result['averages']['decompress_usage'] = int(decompress_nums[1])
                        result['averages']['decompress_r_u'] = int(decompress_nums[2])
                        result['averages']['decompress_rating'] = int(decompress_nums[3])
                i += 1
                continue
            
            # Parse total line
            if line.startswith('Tot:'):
                m = re.match(r'Tot:\s+([\d\s%]+)', line)
                if m:
                    numbers = re.findall(r'[\d.]+%?', m.group(1))
                    if len(numbers) >= 3:
                        result['totals']['usage'] = int(numbers[0])
                        result['totals']['r_u'] = int(numbers[1])
                        result['totals']['rating'] = int(numbers[2])
                i += 1
                continue
            
            # Parse data lines (dictionary size lines)
            # Example: "22:       6185   100   6040   6018  |      34848   100   3001   3000"
            m = re.match(r'^(\d+):\s+(.*)', line)
            if m:
                dict_size = m.group(1)
                # Split by | to get compress and decompress parts
                parts = m.group(2).split('|')
                row = {'dict': int(dict_size)}
                
                if len(parts) >= 1:
                    # Parse compress metrics
                    compress_nums = parts[0].strip().split()
                    if len(compress_nums) >= 4:
                        row['compress'] = {
                            'speed': int(compress_nums[0]),
                            'usage': int(compress_nums[1]),
                            'r_u': int(compress_nums[2]),
                            'rating': int(compress_nums[3])
                        }
                
                if len(parts) >= 2:
                    # Parse decompress metrics
                    decompress_nums = parts[1].strip().split()
                    if len(decompress_nums) >= 4:
                        row['decompress'] = {
                            'speed': int(decompress_nums[0]),
                            'usage': int(decompress_nums[1]),
                            'r_u': int(decompress_nums[2]),
                            'rating': int(decompress_nums[3])
                        }
                
                result['benchmark_table'].append(row)
                i += 1
                continue
            
            # Stop if we hit non-data line after table started
            if line.strip() and not line[0].isspace():
                break
            
            i += 1
    
    return result


def collect_platform_info():
    info = {}
    info['os'] = platform.platform()
    info['uname'] = platform.uname()._asdict()
    info['hostname'] = socket.gethostname()
    # Try lscpu if available
    try:
        out = subprocess.check_output(['lscpu'], text=True)
        info['lscpu'] = out
        # extract physical and logical cores and model name
        m = re.search(r"CPU\(s\):\s*(\d+)", out)
        if m:
            info['logical_cpus'] = int(m.group(1))
        m = re.search(r"Thread\(s\) per core:\s*(\d+)", out)
        if m:
            info['threads_per_core'] = int(m.group(1))
        m = re.search(r"Core\(s\) per socket:\s*(\d+)", out)
        if m:
            info['cores_per_socket'] = int(m.group(1))
        m = re.search(r"Model name:\s*(.+)", out)
        if m:
            info['model_name'] = m.group(1).strip()
        # HT detection (simple heuristic)
        try:
            phys = int(info.get('cores_per_socket', 0))
            logical = int(info.get('logical_cpus', 0))
            info['ht'] = logical > phys
        except Exception:
            pass
    except Exception:
        info['lscpu'] = None
    return info


def safe_stats(values):
    if not values:
        return {'count': 0}
    s = {'count': len(values), 'mean': mean(values), 'median': median(values)}
    if len(values) > 1:
        s['stdev'] = stdev(values)
    else:
        s['stdev'] = 0.0
    return s


def main():
    parser = argparse.ArgumentParser(description='7z benchmark wrapper: run multiple iterations and emit JSON results')
    parser.add_argument('--mx', type=int, default=5, help='7z compression level (e.g. 1,5,9)')
    parser.add_argument('--mmt', type=int, default=1, help='7z thread count (e.g. 1,2,4,8,16)')
    parser.add_argument('--md', type=int, default=26, help='7z md parameter (2^n), e.g. 26')
    parser.add_argument('--iterations', type=int, default=None, help='Number of iterations (wrapper-driven). If omitted, read DEFAULT_ITERATIONS from ./bench.conf or fallback to 1')
    parser.add_argument('--outdir', type=str, default='results', help='Output directory for JSON and logs')
    parser.add_argument('--cooldown', type=float, default=0.5, help='Seconds to wait between iterations')
    parser.add_argument('--timeout', type=float, default=None, help='Per-run timeout (seconds)')
    parser.add_argument('--keep-raw', action='store_true', help='Keep raw stdout/stderr inline in JSON (can be large)')
    args = parser.parse_args()

    # Resolve iterations precedence:
    # 1) CLI --iterations
    # 2) ENV ITERATIONS or DEFAULT_ITERATIONS
    # 3) bench.conf DEFAULT_ITERATIONS (located in cwd)
    # 4) fallback 1
    iterations = args.iterations
    if iterations is None:
        # check environment
        env_it = os.environ.get('ITERATIONS') or os.environ.get('DEFAULT_ITERATIONS')
        if env_it:
            try:
                iterations = int(env_it)
            except Exception:
                iterations = None

    if iterations is None:
        cfg_path = os.path.join(os.getcwd(), 'bench.conf')
        if os.path.isfile(cfg_path):
            try:
                with open(cfg_path, 'r') as cf:
                    for line in cf:
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        if '=' in line:
                            k, v = line.split('=', 1)
                            if k.strip() == 'DEFAULT_ITERATIONS':
                                try:
                                    iterations = int(v.strip())
                                except Exception:
                                    iterations = None
                                break
            except Exception:
                iterations = None

    if iterations is None:
        iterations = 1

    args.iterations = iterations

    os.makedirs(args.outdir, exist_ok=True)
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')

    platform_info = collect_platform_info()

    config = {
        'mx': args.mx,
        'mmt': args.mmt,
        'md': args.md,
        'iterations': args.iterations,
    }

    cmd = ['7z', 'b', f'-mmt={args.mmt}', f'-mx={args.mx}', f'-md={args.md}', '-bt']

    samples = []
    raw_dir = os.path.join(args.outdir, 'raw')
    os.makedirs(raw_dir, exist_ok=True)

    for i in range(1, args.iterations + 1):
        print(f'[{i}/{args.iterations}] running: {" ".join(cmd)}')
        try:
            elapsed, rc, out, err = run_one(cmd, timeout=args.timeout)
        except subprocess.TimeoutExpired:
            print(f'Run {i} timed out')
            samples.append({'run': i, 'elapsed_s': None, 'returncode': None, 'throughput_MB_s': None, 'note': 'timeout'})
            continue

        # Try to parse throughput (legacy)
        tp = parse_throughput(out + '\n' + err)

        # Parse detailed benchmark metrics
        benchmark_data = parse_7z_benchmark_output(out)

        # Save raw output for this iteration
        raw_fname = os.path.join(raw_dir, f'{timestamp}_mx{args.mx}_mmt{args.mmt}_run{i}.log')
        with open(raw_fname, 'w') as f:
            f.write('=== STDOUT ===\n')
            f.write(out)
            f.write('\n=== STDERR ===\n')
            f.write(err)

        sample = {
            'run': i,
            'elapsed_s': round(elapsed, 6) if elapsed is not None else None,
            'returncode': rc,
            'throughput_MB_s': round(tp, 6) if tp is not None else None,
            'benchmark': benchmark_data,
            'raw_log': raw_fname if not args.keep_raw else None,
        }
        samples.append(sample)

        # cooldown
        if args.cooldown and i != args.iterations:
            time.sleep(args.cooldown)

    # compute stats for elapsed and throughput
    elapsed_vals = [s['elapsed_s'] for s in samples if s['elapsed_s'] is not None]
    tp_vals = [s['throughput_MB_s'] for s in samples if s['throughput_MB_s'] is not None]

    results = {
        'platform': {
            'collected_at': timestamp,
            'info': platform_info
        },
        '7z': {
            'cmdline': ' '.join(cmd)
        },
        'params': config,
        'samples': samples,
        'stats': {
            'elapsed': safe_stats(elapsed_vals),
            'throughput_MB_s': safe_stats(tp_vals)
        }
    }

    out_fname = os.path.join(args.outdir, f'{timestamp}_mx{args.mx}_mmt{args.mmt}.json')
    with open(out_fname, 'w') as f:
        json.dump(results, f, indent=2)

    print(f'Wrote results to {out_fname}')


if __name__ == '__main__':
    main()
