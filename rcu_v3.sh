#!/bin/bash

# Test script for litmus_v3.c - RCU grace period guarantee test
# Tests various scenarios of RCU behavior in kernel v3.0

set -e

GENMC="../../genmc"
KERNEL_VERSION="v3.0"
UNROLL=5
FUZZ_MAX=100

echo "============================================================"
echo "Testing litmus_v3.c - RCU Grace Period Guarantee (v3.0)"
echo "============================================================"
echo

# Test 1: Normal case - should succeed (no bugs)
echo "[Test 1/4] Normal execution (should detect NO bugs)"
echo "Command: ${GENMC} --fuzz --fuzz-max=${FUZZ_MAX} ..."
echo "File: valtree/litmus_v3.c"
echo
${GENMC} --fuzz --fuzz-max=${FUZZ_MAX} \
    --mutation-policy=no-mutation \
    --disable-estimation --disable-race-detection --disable-sr --disable-ipr \
    --count-distinct-execs --unroll=${UNROLL} \
    -- -I./valtree/${KERNEL_VERSION} -std=c11 valtree/litmus_v3.c
echo

# Test 2: With ASSERT_0 - should detect assertion violation
echo "[Test 2/4] With -DASSERT_0 (should detect BUG)"
echo "Command: ${GENMC} --fuzz --fuzz-max=${FUZZ_MAX} ... -DASSERT_0"
echo "File: valtree/litmus_v3.c"
echo
${GENMC} --fuzz --fuzz-max=${FUZZ_MAX} \
    --mutation-policy=no-mutation \
    --disable-estimation --disable-race-detection --disable-sr --disable-ipr \
    --count-distinct-execs --unroll=${UNROLL} \
    -- -I./valtree/${KERNEL_VERSION} -std=c11 -DASSERT_0 valtree/litmus_v3.c
echo

# Test 3: With FORCE_FAILURE_1 - grace period not working
echo "[Test 3/4] With -DFORCE_FAILURE_1 (should detect BUG)"
echo "Command: ${GENMC} --fuzz --fuzz-max=${FUZZ_MAX} ... -DFORCE_FAILURE_1"
echo "File: valtree/litmus_v3.c"
echo
${GENMC} --fuzz --fuzz-max=${FUZZ_MAX} \
    --mutation-policy=no-mutation \
    --disable-estimation --disable-race-detection --disable-sr --disable-ipr \
    --count-distinct-execs --unroll=${UNROLL} \
    -- -I./valtree/${KERNEL_VERSION} -std=c11 -DFORCE_FAILURE_1 valtree/litmus_v3.c
echo

# Test 4: With FORCE_FAILURE_2 - should detect bug
echo "[Test 4/4] With -DFORCE_FAILURE_2 (should detect BUG)"
echo "Command: ${GENMC} --fuzz --fuzz-max=${FUZZ_MAX} ... -DFORCE_FAILURE_2"
echo "File: valtree/litmus_v3.c"
echo
${GENMC} --fuzz --fuzz-max=${FUZZ_MAX} \
    --mutation-policy=no-mutation \
    --disable-estimation --disable-race-detection --disable-sr --disable-ipr \
    --count-distinct-execs --unroll=${UNROLL} \
    -- -I./valtree/${KERNEL_VERSION} -std=c11 -DFORCE_FAILURE_2 valtree/litmus_v3.c
echo

echo "============================================================"
echo "All tests completed!"
echo "============================================================"
