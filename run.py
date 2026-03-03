#!/usr/bin/env python3
"""
RCU verification script using GenMC tool.
Runs tests in parallel using multiprocessing.
"""

import subprocess
import os
import sys
import time
import re
import csv
import multiprocessing
from dataclasses import dataclass
from typing import List, Tuple, Optional
from pathlib import Path
from tqdm import tqdm

# Configuration
TOOL = os.path.expanduser("~/weazer/genmc-tool/genmc")
N = 10000
RCU_DIR = Path(__file__).parent
RCU_VERSION_DIR = RCU_DIR / "valtree" / "v3.0"

# Common flags
COMMON_FLAGS = [
    "--disable-estimation",
    "--disable-sr",
    "--disable-ipr",
    "--count-distinct-execs",
    "--disable-function-inliner",
]

# Flag configurations
VERIF_FLAGS = COMMON_FLAGS.copy()

RANDOM_FLAGS = COMMON_FLAGS + [
    "--fuzz",
    f"--fuzz-max={N}",
    "--mutation-policy=no-mutation",
]

FUZZ_FLAGS = COMMON_FLAGS + [
    "--fuzz",
    f"--fuzz-max={N}",
    "--use-queue",
    "--mutation-policy=revisit",
    "--is-interesting=new",
    "--fuzz-value-noblock=true",
    "--num-mutation=3",
    "--insert-rand=30",
    "-fuzz-corpus=20",
]

# Test definitions: (test_define, unroll)
TESTS = [
    # ("ASSERT_0", 5),
    ("FORCE_FAILURE_1", 5),
    ("FORCE_FAILURE_2", 5),
    ("FORCE_FAILURE_3", 5),
    ("FORCE_FAILURE_4", 5),
    ("FORCE_FAILURE_5", 5),
    ("FORCE_FAILURE_6", 19),  # This one needs unroll=19
]

FLAG_CONFIGS = {
    "random": RANDOM_FLAGS,
    "fuzz": FUZZ_FLAGS,
    "verif": VERIF_FLAGS,
}

# Default timeout: 30 minutes
DEFAULT_TIMEOUT = 1800


def parse_output(output: str) -> dict:
    """
    Parse GenMC output and extract relevant fields.
    
    Returns dict with:
        - complete_execs: Number of complete executions explored
        - blocked_execs: Number of blocked executions seen
        - distinct_graphs: Number of distinct graphs (if available)
        - total_graphs: Total number of graphs (if available)
        - wall_clock: Wall-clock time in seconds
        - verified: Whether verification completed successfully
        - error: Error type if any (e.g., "Non-atomic race", "Safety violation")
    """
    result = {
        "complete_execs": None,
        "blocked_execs": None,
        "distinct_graphs": None,
        "total_graphs": None,
        "wall_clock": None,
        "verified": False,
        "error": None,
    }
    
    for line in output.splitlines():
        # Number of complete executions explored: 14692
        if "Number of complete executions explored:" in line:
            m = re.search(r"Number of complete executions explored:\s*(\d+)", line)
            if m:
                result["complete_execs"] = int(m.group(1))
        
        # Number of blocked executions seen: 2626
        elif "Number of blocked executions seen:" in line:
            m = re.search(r"Number of blocked executions seen:\s*(\d+)", line)
            if m:
                result["blocked_execs"] = int(m.group(1))
        
        # Number of distinct graphs: 261 (/346 = 75.43%)
        elif "Number of distinct graphs:" in line:
            m = re.search(r"Number of distinct graphs:\s*(\d+)\s*\(/(\d+)", line)
            if m:
                result["distinct_graphs"] = int(m.group(1))
                result["total_graphs"] = int(m.group(2))
        
        # Total wall-clock time: 2703.59s
        elif "Total wall-clock time:" in line:
            m = re.search(r"Total wall-clock time:\s*([\d.]+)s", line)
            if m:
                result["wall_clock"] = float(m.group(1))
        
        # Verification complete.
        elif "Verification complete" in line:
            result["verified"] = True
        
        # Error detection
        elif "Non-atomic race" in line:
            result["error"] = "Non-atomic race"
        elif "Safety violation" in line:
            result["error"] = "Safety violation"
        elif "Error:" in line:
            if result["error"] is None:
                result["error"] = line.strip()
    
    return result


def run_single_test(args: Tuple) -> dict:
    """
    Run a single test case.
    
    Args:
        args: Tuple of (flag_name, test_define, flags, unroll, run_id, timeout)
    
    Returns:
        dict with test results
    """
    flag_name, test_define, flags, unroll, run_id, timeout = args
    
    cmd = [
        TOOL,
        *flags,
        f"--unroll={unroll}",
        "--",
        f"-D{test_define}",
        f"-I{RCU_VERSION_DIR}",
        "-std=c11",
        str(RCU_DIR / "valtree" / "litmus_v3.c"),
    ]
    
    result = {
        "flag_name": flag_name,
        "test_name": test_define,
        "run_id": run_id,
        "timeout": False,
        "complete_execs": None,
        "blocked_execs": None,
        "distinct_graphs": None,
        "total_graphs": None,
        "wall_clock": None,
        "verified": False,
        "error": None,
    }
    
    proc = subprocess.Popen(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        # Parse stdout (GenMC outputs stats to stdout)
        parsed = parse_output(stdout)
        # Also check stderr in case some output goes there
        if parsed["wall_clock"] is None:
            parsed_stderr = parse_output(stderr)
            for k, v in parsed_stderr.items():
                if parsed[k] is None and v is not None:
                    parsed[k] = v
        
        result.update(parsed)
        
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()  # Clean up
        result["timeout"] = True
        result["error"] = "TIMEOUT"
    except Exception as e:
        result["error"] = str(e)
    
    return result


class CSVLogger:
    """Logger that writes results to CSV file."""
    
    def __init__(self, output_file: Path):
        self.output_file = output_file
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.output_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "flag_name", "test_name", "run_id", "timeout",
                "complete_execs", "blocked_execs", "distinct_graphs", "total_graphs",
                "wall_clock", "verified", "error"
            ])
    
    def log(self, result: dict):
        with open(self.output_file, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                result["flag_name"],
                result["test_name"],
                result["run_id"],
                result["timeout"],
                result["complete_execs"],
                result["blocked_execs"],
                result["distinct_graphs"],
                result["total_graphs"],
                result["wall_clock"],
                result["verified"],
                result["error"],
            ])


def generate_tasks(repeat: int, timeout: int, 
                   flag_filter: Optional[List[str]] = None,
                   test_filter: Optional[List[str]] = None) -> List[Tuple]:
    """Generate all test tasks."""
    tasks = []
    for flag_name, flags in FLAG_CONFIGS.items():
        if flag_filter and flag_name not in flag_filter:
            continue
        for test_define, unroll in TESTS:
            if test_filter and test_define not in test_filter:
                continue
            for run_id in range(1, repeat + 1):
                tasks.append((flag_name, test_define, flags, unroll, run_id, timeout))
    return tasks


def main():
    import argparse
    parser = argparse.ArgumentParser(description="RCU verification with GenMC")
    parser.add_argument(
        "-r", "--repeat",
        type=int,
        default=30,
        help="Number of times to repeat each test (default: 30)"
    )
    parser.add_argument(
        "-j", "--jobs",
        type=int,
        default=None,
        help="Number of parallel jobs (default: CPU count)"
    )
    parser.add_argument(
        "-t", "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"Timeout per test in seconds (default: {DEFAULT_TIMEOUT} = 30 min)"
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default="results.csv",
        help="Output CSV file (default: results.csv)"
    )
    parser.add_argument(
        "--flags",
        nargs="+",
        choices=list(FLAG_CONFIGS.keys()),
        default=None,
        help="Which flag configurations to run (default: all)"
    )
    parser.add_argument(
        "--tests",
        nargs="+",
        default=None,
        help="Which tests to run (e.g., ASSERT_0 FORCE_FAILURE_1)"
    )
    args = parser.parse_args()
    
    # Determine number of workers
    cpu_total = multiprocessing.cpu_count()
    workers = args.jobs if args.jobs else cpu_total
    print(f"Starting pool with {workers} workers (cpu_count={cpu_total})")
    
    # Generate tasks
    tasks = generate_tasks(
        repeat=args.repeat,
        timeout=args.timeout,
        flag_filter=args.flags,
        test_filter=args.tests,
    )
    
    total_tasks = len(tasks)
    print(f"Total tasks: {total_tasks}")
    print(f"Timeout per test: {args.timeout}s ({args.timeout // 60} min)")
    print(f"Output file: {args.output}")
    print()
    
    # Setup logger
    output_path = RCU_DIR / args.output
    logger = CSVLogger(output_path)
    
    # Run tests in parallel with progress bar
    start_time = time.time()
    
    with multiprocessing.Pool(processes=workers) as pool:
        for result in tqdm(pool.imap_unordered(run_single_test, tasks), total=total_tasks):
            logger.log(result)
    
    total_time = time.time() - start_time
    print(f"\nTotal wall-clock time: {total_time:.2f}s ({total_time/60:.1f} min)")
    print(f"Results saved to: {output_path}")


if __name__ == "__main__":
    main()

