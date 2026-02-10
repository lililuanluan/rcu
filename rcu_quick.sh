#!/bin/bash

# Quick RCU test suite for GenMC - Selected key tests
# Tests various RCU implementations across kernel versions

set -e

GENMC="../../genmc"
FUZZ_MAX="${FUZZ_MAX:-50}"
UNROLL=5

echo "╔════════════════════════════════════════════════════════╗"
echo "║     GenMC RCU Test Suite - Quick Mode                 ║"
echo "╚════════════════════════════════════════════════════════╝"
echo "FUZZ_MAX=$FUZZ_MAX (快速模式: --fuzz-max=50)"
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
    echo "📝 $name"
    echo "   Kernel: $kernel_version | File: $test_file"
    if [ -n "$extra_flags" ]; then
        echo "   Flags: $extra_flags"
    fi
    
    if timeout 120 ${GENMC} --fuzz --fuzz-max=${FUZZ_MAX} \
        --mutation-policy=no-mutation \
        --disable-estimation --disable-race-detection --disable-sr --disable-ipr \
        --count-distinct-execs --unroll=${UNROLL} \
        -- -I./valtree/${kernel_version} -std=c11 ${extra_flags} valtree/${test_file} 2>&1 | \
        grep -E "Verification complete|No errors detected|errors detected|errors found" | head -5
    then
        : # Success
    else
        echo "   ⚠️  Timeout or error"
    fi
    echo
}

# Test 1: gp_end_bug (different kernel versions)
echo "╔════════════════════════════════════════════════════════╗"
echo "║ 1️⃣  gp_end_bug.c - RCU grace period ending              ║"
echo "╚════════════════════════════════════════════════════════╝"
echo

run_test "gp_end_bug - v2.6.31.1" "v2.6.31.1" "gp_end_bug.c"
run_test "gp_end_bug - v3.0" "v3.0" "gp_end_bug.c" "-DKERNEL_VERSION_3"

# Test 2: init_bug
echo
echo "╔════════════════════════════════════════════════════════╗"
echo "║ 2️⃣  init_bug.c - Grace period initialization           ║"
echo "╚════════════════════════════════════════════════════════╝"
echo

run_test "init_bug.c" "v2.6.31.1" "init_bug.c" "-DCONFIG_NR_CPUS=3 -DCONFIG_RCU_FANOUT=2 -DFQS_NO_BUG"

# Test 3: litmus_v3.c tests
echo
echo "╔════════════════════════════════════════════════════════╗"
echo "║ 3️⃣  litmus_v3.c - v3.0 Grace Period Guarantee          ║"
echo "╚════════════════════════════════════════════════════════╝"
echo

run_test "litmus_v3.c - 正常执行" "v3.0" "litmus_v3.c"
run_test "litmus_v3.c - ASSERT_0 (应检测bug)" "v3.0" "litmus_v3.c" "-DASSERT_0"
run_test "litmus_v3.c - FORCE_FAILURE_1" "v3.0" "litmus_v3.c" "-DFORCE_FAILURE_1"

# Test 4: litmus.c (v3.19+)
echo
echo "╔════════════════════════════════════════════════════════╗"
echo "║ 4️⃣  litmus.c - v3.19+ Grace Period Guarantee           ║"
echo "╚════════════════════════════════════════════════════════╝"
echo

run_test "litmus.c - v3.19 正常执行" "v3.19" "litmus.c"
run_test "litmus.c - v3.19 ASSERT_0" "v3.19" "litmus.c" "-DASSERT_0"
run_test "litmus.c - v4.3 正常执行" "v4.3" "litmus.c"

# Test 5: publish.c
echo
echo "╔════════════════════════════════════════════════════════╗"
echo "║ 5️⃣  publish.c - Publish-Subscribe Guarantee            ║"
echo "╚════════════════════════════════════════════════════════╝"
echo

run_test "publish.c - v3.19" "v3.19" "publish.c"

echo
echo "╔════════════════════════════════════════════════════════╗"
echo "║             ✅ Test Suite Completed!                   ║"
echo "╚════════════════════════════════════════════════════════╝"
