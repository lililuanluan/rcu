import argparse
import concurrent.futures
import csv
import os
import re
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from tqdm import tqdm


ROOT_DIR = Path(__file__).parent
LITMUS_FILE = ROOT_DIR / "valtree" / "litmus_v4.c"  # default, can be overridden
RCU_VERSION_DIR = ROOT_DIR / "valtree" / "v3.0"


@dataclass
class BenchmarkConfig:
    name: str
    litmus: Path
    repeat: int = 30
    timeout: int = 1800
    fuzz_max: int = 1_000_000
    unroll: int = 20
    verify_unroll_bias: int = 0
    modes: List[str] = None  # defaults to ["verify", "random", "fuzz"]
    extra_defines: List[str] = None

    def resolved_modes(self) -> List[str]:
        return self.modes or ["verify", "random", "fuzz"]

    def resolved_extra_defines(self) -> List[str]:
        return self.extra_defines or []


DEFAULT_BENCHMARKS: Dict[str, BenchmarkConfig] = {
    "litmus_v4.c": BenchmarkConfig(
        name="litmus_v4",
        litmus=ROOT_DIR / "valtree" / "litmus_v4.c",
        fuzz_max=1_000_000,
        unroll=20,
    ),
    "litmus_v9.c": BenchmarkConfig(
        name="litmus_v9",
        litmus=ROOT_DIR / "valtree" / "litmus_v9.c",
        fuzz_max=1_000_000,
        unroll=20,
    ),
    "litmus_v10.c": BenchmarkConfig(
        name="litmus_v10",
        litmus=ROOT_DIR / "valtree" / "litmus_v10.c",
        fuzz_max=1_000_000,
        unroll=20,
    ),
    "litmus_v11.c": BenchmarkConfig(
        name="litmus_v11",
        litmus=ROOT_DIR / "valtree" / "litmus_v11.c",
        fuzz_max=1_000_000,
        unroll=20,
    ),
    "litmus_v12.c": BenchmarkConfig(
        name="litmus_v12",
        litmus=ROOT_DIR / "valtree" / "litmus_v12.c",
        fuzz_max=1_000_000,
        unroll=20,
    ),
    "litmus_v13.c": BenchmarkConfig(
        name="litmus_v13",
        litmus=ROOT_DIR / "valtree" / "litmus_v13.c",
        fuzz_max=1_000_000,
        unroll=20,
    ),
    "litmus_v14.c": BenchmarkConfig(
        name="litmus_v14",
        litmus=ROOT_DIR / "valtree" / "litmus_v14.c",
        fuzz_max=1_000_000,
        unroll=20,
    ),
    "litmus_v15.c": BenchmarkConfig(
        name="litmus_v15",
        litmus=ROOT_DIR / "valtree" / "litmus_v15.c",
        fuzz_max=1_000_000,
        unroll=20,
    ),
}

TOOL_CANDIDATES = [
    Path(os.path.expanduser("~/weazer/genmc-tool/genmc")),
]

COMMON_FLAGS = [
    "--disable-estimation",
    "--disable-sr",
    "--disable-ipr",
    "--count-distinct-execs",
    "--disable-function-inliner",
]


def resolve_tool(explicit: Optional[str]) -> Path:
    if explicit:
        tool = Path(os.path.expanduser(explicit))
        if not tool.exists():
            raise FileNotFoundError(f"GenMC not found: {tool}")
        return tool

    for candidate in TOOL_CANDIDATES:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "Cannot find GenMC binary. Use --tool to provide an explicit path."
    )


def get_flag_configs(fuzz_max: int) -> Dict[str, List[str]]:
    return {
        "verify": COMMON_FLAGS + ["--schedule-policy=ltr"],
        "random": COMMON_FLAGS
        + [
            "--fuzz",
            f"--fuzz-max={fuzz_max}",
            "--mutation-policy=no-mutation",
        ],
        "fuzz": COMMON_FLAGS
        + [
            "--fuzz",
            f"--fuzz-max={fuzz_max}",
            "--use-queue",
            "--mutation-policy=revisit",
            "--is-interesting=new",
            "--fuzz-value-noblock=true",
            "--num-mutation=3",
            "--insert-rand=30",
            "--fuzz-corpus=20",
            "--add-max=mutated",
            "--prio-new-val",
            "--schedule-policy=wfr",
        ],
    }


def parse_output(output: str) -> Dict[str, Optional[float]]:
    result: Dict[str, Optional[float]] = {
        "complete_execs": None,
        "blocked_execs": None,
        "distinct_graphs": None,
        "total_graphs": None,
        "wall_clock": None,
        "found_bug": False,
        "verified": False,
        "error": None,
    }

    for line in output.splitlines():
        if "Number of complete executions explored:" in line:
            m = re.search(r"Number of complete executions explored:\s*(\d+)", line)
            if m:
                result["complete_execs"] = int(m.group(1))
        elif "Number of blocked executions seen:" in line:
            m = re.search(r"Number of blocked executions seen:\s*(\d+)", line)
            if m:
                result["blocked_execs"] = int(m.group(1))
        elif "Number of distinct graphs:" in line:
            m = re.search(r"Number of distinct graphs:\s*(\d+)\s*\(/(\d+)", line)
            if m:
                result["distinct_graphs"] = int(m.group(1))
                result["total_graphs"] = int(m.group(2))
        elif "Total wall-clock time:" in line:
            m = re.search(r"Total wall-clock time:\s*([\d.]+)s", line)
            if m:
                result["wall_clock"] = float(m.group(1))
        elif "Assertion violation" in line or "Safety violation" in line:
            result["found_bug"] = True
        elif "Verification complete" in line:
            result["verified"] = True
        elif "Error:" in line and result["error"] is None:
            result["error"] = line.strip()

    return result


def run_single(
    tool: Path,
    mode: str,
    flags: List[str],
    run_id: int,
    timeout: int,
    unroll: int,
    extra_defines: List[str],
    litmus_file: Path,
    benchmark: str,
) -> Dict:
    cmd = [
        str(tool),
        *flags,
        f"--unroll={unroll}",
        "--",
        *extra_defines,
        f"-I{RCU_VERSION_DIR}",
        "-std=c11",
        str(litmus_file),
    ]

    started = time.monotonic()
    result = {
        "benchmark": benchmark,
        "litmus": str(litmus_file.name),
        "mode": mode,
        "run_id": run_id,
        "timeout": False,
        "complete_execs": None,
        "blocked_execs": None,
        "distinct_graphs": None,
        "total_graphs": None,
        "wall_clock": None,
        "found_bug": False,
        "verified": False,
        "error": None,
        "hit_time": None,
    }

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        parsed = parse_output(stdout + stderr)
        result.update(parsed)
        elapsed = time.monotonic() - started
        if result["wall_clock"] is None:
            result["wall_clock"] = elapsed
        if result["found_bug"]:
            result["hit_time"] = result["wall_clock"]
        if proc.returncode != 0 and result["error"] is None and not result["found_bug"]:
            first_err = next(
                (ln.strip() for ln in stderr.splitlines() if ln.strip()), ""
            )
            result["error"] = first_err or f"EXIT_{proc.returncode}"
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        result["timeout"] = True
        result["error"] = "TIMEOUT"

    return result


def write_csv(path: Path, rows: List[Dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "benchmark",
                "litmus",
                "mode",
                "run_id",
                "timeout",
                "complete_execs",
                "blocked_execs",
                "distinct_graphs",
                "total_graphs",
                "wall_clock",
                "found_bug",
                "verified",
                "hit_time",
                "error",
            ]
        )
        for r in rows:
            writer.writerow(
                [
                    r.get("benchmark"),
                    r.get("litmus"),
                    r["mode"],
                    r["run_id"],
                    r["timeout"],
                    r["complete_execs"],
                    r["blocked_execs"],
                    r["distinct_graphs"],
                    r["total_graphs"],
                    r["wall_clock"],
                    r["found_bug"],
                    r["verified"],
                    r["hit_time"],
                    r["error"],
                ]
            )


class CSVLogger:
    """Append results to a CSV file incrementally."""

    def __init__(self, output_file: Path):
        self.output_file = output_file
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        # write header
        with open(self.output_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "benchmark",
                    "litmus",
                    "mode",
                    "run_id",
                    "timeout",
                    "complete_execs",
                    "blocked_execs",
                    "distinct_graphs",
                    "total_graphs",
                    "wall_clock",
                    "found_bug",
                    "verified",
                    "hit_time",
                    "error",
                ]
            )

    def log(self, r: Dict) -> None:
        with open(self.output_file, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    r.get("benchmark"),
                    r.get("litmus"),
                    r["mode"],
                    r["run_id"],
                    r["timeout"],
                    r["complete_execs"],
                    r["blocked_execs"],
                    r["distinct_graphs"],
                    r["total_graphs"],
                    r["wall_clock"],
                    r["found_bug"],
                    r["verified"],
                    r["hit_time"],
                    r["error"],
                ]
            )


def print_summary(
    results: List[Dict], mode_order: List[str], label: str = "SUMMARY (hit-bug latency)"
) -> None:
    print("\n" + "=" * 84)
    print(label)
    print("=" * 84)
    print(
        f"{'Mode':<10} {'Runs':<6} {'Hit':<6} {'Rate':<9} "
        f"{'Avg Hit':<12} {'Median Hit':<12} {'Avg Time':<12}"
    )
    print("-" * 84)

    avg_hit_by_mode = {}
    for mode in mode_order:
        group = [r for r in results if r["mode"] == mode]
        hits = [r["hit_time"] for r in group if r["hit_time"] is not None]
        times = [r["wall_clock"] for r in group if r["wall_clock"] is not None]

        hit_rate = (len(hits) / len(group) * 100.0) if group else 0.0
        avg_hit = statistics.mean(hits) if hits else None
        med_hit = statistics.median(hits) if hits else None
        avg_time = statistics.mean(times) if times else None
        avg_hit_by_mode[mode] = avg_hit

        avg_hit_str = f"{avg_hit:.2f}s" if avg_hit is not None else "N/A"
        med_hit_str = f"{med_hit:.2f}s" if med_hit is not None else "N/A"
        avg_time_str = f"{avg_time:.2f}s" if avg_time is not None else "N/A"
        print(
            f"{mode:<10} {len(group):<6} {len(hits):<6} {hit_rate:>6.1f}%   "
            f"{avg_hit_str:<12} {med_hit_str:<12} {avg_time_str:<12}"
        )

    print("-" * 84)
    if all(avg_hit_by_mode.get(m) is not None for m in ("verify", "random", "fuzz")):
        v = avg_hit_by_mode["verify"]
        r = avg_hit_by_mode["random"]
        f = avg_hit_by_mode["fuzz"]
        print(
            f"Ordering check (Avg Hit): verify={v:.2f}s, random={r:.2f}s, fuzz={f:.2f}s"
        )
        print(f"Target satisfied (verify > random > fuzz): {v > r > f}")
    else:
        print("Ordering check unavailable: at least one mode did not hit the bug.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run litmus_v8 with GenMC.")
    parser.add_argument("--tool", type=str, default=None, help="Path to GenMC binary")
    parser.add_argument(
        "-r", "--repeat", type=int, default=20, help="Runs per mode (default: 20)"
    )
    parser.add_argument(
        "-t", "--timeout", type=int, default=300, help="Timeout per run, seconds"
    )
    parser.add_argument(
        "-n",
        "--fuzz-max",
        type=int,
        default=10000,
        help="Max iterations in random/fuzz mode",
    )
    parser.add_argument(
        "-u", "--unroll", type=int, default=18, help="GenMC unroll bound"
    )
    parser.add_argument(
        "--verify-unroll-bias",
        type=int,
        default=4,
        help="Extra unroll added only for verify mode",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default="out/litmus_tests.csv",
        help="CSV output path (relative to repo root by default)",
    )
    parser.add_argument(
        "--litmus",
        type=str,
        default=None,
        help="Run a single litmus file with the provided CLI parameters (bypasses per-benchmark presets)",
    )
    parser.add_argument(
        "--modes",
        nargs="+",
        choices=["verify", "random", "fuzz"],
        default=["verify", "random", "fuzz"],
        help="Modes to run (default: all)",
    )
    parser.add_argument(
        "--extra-define",
        nargs="*",
        default=[],
        help="Additional preprocessor defines, e.g. FOO=1 BAR",
    )
    parser.add_argument(
        "--benchmarks",
        nargs="+",
        default=None,
        help="Names of benchmarks to run from the preset list (e.g., litmus_v9.c litmus_v10.c). If omitted, runs all presets.",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=os.cpu_count() or 4,
        help="Number of worker processes for parallel runs",
    )
    args = parser.parse_args()

    tool = resolve_tool(args.tool)

    # Build benchmark list either from single litmus override or presets
    if args.litmus:
        litmus_path = ROOT_DIR / "valtree" / args.litmus
        if not litmus_path.exists():
            raise FileNotFoundError(f"Benchmark file not found: {litmus_path}")
        benchmark_configs = [
            BenchmarkConfig(
                name=litmus_path.stem,
                litmus=litmus_path,
                repeat=args.repeat,
                timeout=args.timeout,
                fuzz_max=args.fuzz_max,
                unroll=args.unroll,
                verify_unroll_bias=args.verify_unroll_bias,
                modes=args.modes,
                extra_defines=args.extra_define,
            )
        ]
    else:
        selected = DEFAULT_BENCHMARKS
        if args.benchmarks:
            missing = [b for b in args.benchmarks if b not in DEFAULT_BENCHMARKS]
            if missing:
                raise ValueError(f"Unknown benchmarks: {', '.join(missing)}")
            selected = {
                k: v for k, v in DEFAULT_BENCHMARKS.items() if k in args.benchmarks
            }
        benchmark_configs = list(selected.values())

    output_path = (ROOT_DIR / args.output).resolve()
    logger = CSVLogger(output_path)
    results: List[Dict] = []

    print(f"Tool: {tool}")
    print(f"Include dir: {RCU_VERSION_DIR}")
    print(f"Benchmarks: {', '.join(cfg.name for cfg in benchmark_configs)}")
    print(f"Output CSV: {output_path}")
    print(f"Parallel jobs: {args.jobs}")

    tasks = []
    for cfg in benchmark_configs:
        flag_configs = get_flag_configs(cfg.fuzz_max)
        extra_defines = (
            ["-DCHECK_BUG"]
            + cfg.resolved_extra_defines()
            + [f"-D{x}" for x in args.extra_define]
        )
        modes = [m for m in ["verify", "random", "fuzz"] if m in cfg.resolved_modes()]
        if not cfg.litmus.exists():
            raise FileNotFoundError(f"Benchmark file not found: {cfg.litmus}")
        for mode in modes:
            mode_unroll = cfg.unroll + (
                cfg.verify_unroll_bias if mode == "verify" else 0
            )
            for run_id in range(1, cfg.repeat + 1):
                tasks.append(
                    (
                        tool,
                        mode,
                        flag_configs[mode],
                        run_id,
                        cfg.timeout,
                        mode_unroll,
                        extra_defines,
                        cfg.litmus,
                        cfg.name,
                    )
                )

    started = time.time()
    print(f"Total tasks: {len(tasks)}")

    with concurrent.futures.ProcessPoolExecutor(max_workers=args.jobs) as executor:
        futures = [executor.submit(run_single, *t) for t in tasks]
        for fut in tqdm(
            concurrent.futures.as_completed(futures),
            total=len(futures),
            desc="runs",
            leave=False,
        ):
            result = fut.result()
            results.append(result)
            logger.log(result)
            if result.get("error") and "error:" in str(result["error"]):
                print(f"Aborting due to compilation/runtime error: {result['error']}")
                executor.shutdown(cancel_futures=True)
                sys.exit(1)

    elapsed = time.time() - started

    # Print per-benchmark summaries
    for cfg in benchmark_configs:
        subset = [r for r in results if r.get("benchmark") == cfg.name]
        if subset:
            print_summary(subset, cfg.resolved_modes(), label=f"SUMMARY ({cfg.name})")

    print(f"\nTotal elapsed: {elapsed:.2f}s ({elapsed/60:.1f} min)")
    print(f"CSV written to: {output_path}")


if __name__ == "__main__":
    main()
