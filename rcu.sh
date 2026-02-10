#!/bin/bash

# Comprehensive RCU test suite for GenMC
# Tests various RCU implementations across kernel versions

set -e

GENMC="../../genmc"
FUZZ_MAX="${FUZZ_MAX:-100}"
UNROLL=5

echo "============================================================"
echo "GenMC RCU Test Suite"
echo "============================================================"
echo "FUZZ_MAX=$FUZZ_MAX"
echo "UNROLL=$UNROLL"
echo

# Test helper function
run_test() {
    local name="$1"
    local kernel_version="$2"
    local test_file="$3"
    shift 3
    local extra_flags="$@"
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Test: $name"
    echo "Kernel: $kernel_version"
    echo "File: $test_file"
    if [ -n "$extra_flags" ]; then
        echo "Flags: $extra_flags"
    fi
    echo
    
    timeout 120 ${GENMC} --fuzz --fuzz-max=${FUZZ_MAX} \
        --mutation-policy=no-mutation \
        --disable-estimation --disable-race-detection --disable-sr --disable-ipr \
        --count-distinct-execs --unroll=${UNROLL} \
        -- -I./valtree/${kernel_version} -std=c11 ${extra_flags} valtree/${test_file} 2>&1 | \
        tail -20
    echo
}

# Test 1: gp_end_bug tests (v2.6.31.1)
echo "╔════════════════════════════════════════════════════════╗"
echo "║ gp_end_bug.c tests (RCU grace period ending)           ║"
echo "╚════════════════════════════════════════════════════════╝"
echo

run_test "gp_end_bug.c - v2.6.31.1" "v2.6.31.1" "gp_end_bug.c"

run_test "gp_end_bug.c - v2.6.32.1" "v2.6.32.1" "gp_end_bug.c"

run_test "gp_end_bug.c - v3.0 with KERNEL_VERSION_3" "v3.0" "gp_end_bug.c" "-DKERNEL_VERSION_3"

# Test 2: init_bug tests
echo
echo "╔════════════════════════════════════════════════════════╗"
echo "║ init_bug.c test (grace period initialization)         ║"
echo "╚════════════════════════════════════════════════════════╝"
echo

run_test "init_bug.c - v2.6.31.1 with CONFIG options" "v2.6.31.1" "init_bug.c" \
    "-DCONFIG_NR_CPUS=3 -DCONFIG_RCU_FANOUT=2 -DFQS_NO_BUG"

# Test 3: publish tests
echo
echo "╔════════════════════════════════════════════════════════╗"
echo "║ publish.c tests (publish-subscribe guarantee)         ║"
echo "╚════════════════════════════════════════════════════════╝"
echo

run_test "publish.c - v3.19" "v3.19" "publish.c"

run_test "publish.c - v3.19 with ORDERING_BUG" "v3.19" "publish.c" "-DORDERING_BUG"

# Test 4: litmus_v3.c tests (v3.0 grace period guarantee)
echo
echo "╔════════════════════════════════════════════════════════╗"
echo "║ litmus_v3.c tests (v3.0 grace period guarantee)       ║"
echo "╚════════════════════════════════════════════════════════╝"
echo

run_test "litmus_v3.c - normal" "v3.0" "litmus_v3.c"

run_test "litmus_v3.c - ASSERT_0" "v3.0" "litmus_v3.c" "-DASSERT_0"

run_test "litmus_v3.c - FORCE_FAILURE_1" "v3.0" "litmus_v3.c" "-DFORCE_FAILURE_1"

run_test "litmus_v3.c - FORCE_FAILURE_2" "v3.0" "litmus_v3.c" "-DFORCE_FAILURE_2"

run_test "litmus_v3.c - FORCE_FAILURE_3" "v3.0" "litmus_v3.c" "-DFORCE_FAILURE_3"

# Test 5: litmus.c tests (v3.19+ grace period guarantee)
echo
echo "╔════════════════════════════════════════════════════════╗"
echo "║ litmus.c tests (v3.19+ grace period guarantee)        ║"
echo "╚════════════════════════════════════════════════════════╝"
echo

run_test "litmus.c - v3.19 normal" "v3.19" "litmus.c"

run_test "litmus.c - v3.19 ASSERT_0" "v3.19" "litmus.c" "-DASSERT_0"

run_test "litmus.c - v3.19 FORCE_FAILURE_1" "v3.19" "litmus.c" "-DFORCE_FAILURE_1"

run_test "litmus.c - v4.3 normal" "v4.3" "litmus.c"

echo
echo "============================================================"
echo "Test suite completed!"
echo "============================================================"