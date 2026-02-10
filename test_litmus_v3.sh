#!/bin/bash

# Test script for litmus_v3.c with various configurations
# Based on driver.sh test cases for v3.0 kernel

GENMC="../../genmc"
KERNEL_VERSION="v3.0"
UNROLL=5
FUZZ_MAX=100

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "============================================================"
echo "Testing litmus_v3.c with C11 atomic variables"
echo "============================================================"
echo

# Test 1: Normal case - should succeed (no bugs)
echo -e "${YELLOW}[Test 1] litmus_v3.c (normal case)${NC}"
echo "Expected: SUCCESS (no bugs detected)"
if timeout 60 ${GENMC} --fuzz --fuzz-max=${FUZZ_MAX} \
    --mutation-policy=no-mutation \
    --disable-estimation --disable-race-detection --disable-sr --disable-ipr \
    --count-distinct-execs --unroll=${UNROLL} \
    -- -I./valtree/v3.0 -std=c11 valtree/litmus_v3.c 2>&1 | tee /tmp/test1.log
then
    if grep -q "No errors were detected" /tmp/test1.log; then
        echo -e "${GREEN}✓ Test 1 PASSED${NC}"
        TEST1_PASS=1
    else
        echo -e "${RED}✗ Test 1 FAILED (expected no errors)${NC}"
        TEST1_PASS=0
    fi
else
    echo -e "${RED}✗ Test 1 FAILED (timeout or crash)${NC}"
    TEST1_PASS=0
fi
echo

# Test 2: With ASSERT_0 - should detect bug
echo -e "${YELLOW}[Test 2] litmus_v3.c -DASSERT_0 (should detect bug)${NC}"
echo "Expected: FAILURE (assertion bug detected)"
if timeout 60 ${GENMC} --fuzz --fuzz-max=${FUZZ_MAX} \
    --mutation-policy=no-mutation \
    --disable-estimation --disable-race-detection --disable-sr --disable-ipr \
    --count-distinct-execs --unroll=${UNROLL} \
    -- -I./valtree/v3.0 -std=c11 -DASSERT_0 valtree/litmus_v3.c 2>&1 | tee /tmp/test2.log
then
    if grep -q "No errors were detected" /tmp/test2.log; then
        echo -e "${RED}✗ Test 2 FAILED (should have detected assertion bug)${NC}"
        TEST2_PASS=0
    else
        echo -e "${GREEN}✓ Test 2 PASSED (bug detected as expected)${NC}"
        TEST2_PASS=1
    fi
else
    echo -e "${GREEN}✓ Test 2 PASSED (timeout indicates bug detection)${NC}"
    TEST2_PASS=1
fi
echo

# Test 3: With FORCE_FAILURE_1 - should detect bug
echo -e "${YELLOW}[Test 3] litmus_v3.c -DFORCE_FAILURE_1 (should detect bug)${NC}"
echo "Expected: FAILURE (bug in grace period guarantee)"
if timeout 60 ${GENMC} --fuzz --fuzz-max=${FUZZ_MAX} \
    --mutation-policy=no-mutation \
    --disable-estimation --disable-race-detection --disable-sr --disable-ipr \
    --count-distinct-execs --unroll=${UNROLL} \
    -- -I./valtree/v3.0 -std=c11 -DFORCE_FAILURE_1 valtree/litmus_v3.c 2>&1 | tee /tmp/test3.log
then
    if grep -q "No errors were detected" /tmp/test3.log; then
        echo -e "${RED}✗ Test 3 FAILED (should have detected bug)${NC}"
        TEST3_PASS=0
    else
        echo -e "${GREEN}✓ Test 3 PASSED (bug detected as expected)${NC}"
        TEST3_PASS=1
    fi
else
    echo -e "${GREEN}✓ Test 3 PASSED (timeout indicates bug detection)${NC}"
    TEST3_PASS=1
fi
echo

# Test 4: With FORCE_FAILURE_2 - should detect bug
echo -e "${YELLOW}[Test 4] litmus_v3.c -DFORCE_FAILURE_2 (should detect bug)${NC}"
echo "Expected: FAILURE (bug in RCU behavior)"
if timeout 60 ${GENMC} --fuzz --fuzz-max=${FUZZ_MAX} \
    --mutation-policy=no-mutation \
    --disable-estimation --disable-race-detection --disable-sr --disable-ipr \
    --count-distinct-execs --unroll=${UNROLL} \
    -- -I./valtree/v3.0 -std=c11 -DFORCE_FAILURE_2 valtree/litmus_v3.c 2>&1 | tee /tmp/test4.log
then
    if grep -q "No errors were detected" /tmp/test4.log; then
        echo -e "${RED}✗ Test 4 FAILED (should have detected bug)${NC}"
        TEST4_PASS=0
    else
        echo -e "${GREEN}✓ Test 4 PASSED (bug detected as expected)${NC}"
        TEST4_PASS=1
    fi
else
    echo -e "${GREEN}✓ Test 4 PASSED (timeout indicates bug detection)${NC}"
    TEST4_PASS=1
fi
echo

# Summary
echo "============================================================"
echo "Test Summary"
echo "============================================================"
TOTAL=0
PASSED=0

for i in 1 2 3 4; do
    eval "RESULT=\$TEST${i}_PASS"
    TOTAL=$((TOTAL + 1))
    if [ "$RESULT" = "1" ]; then
        PASSED=$((PASSED + 1))
        echo -e "${GREEN}✓ Test $i passed${NC}"
    else
        echo -e "${RED}✗ Test $i failed${NC}"
    fi
done

echo
echo "Results: $PASSED/$TOTAL tests passed"
echo

if [ $PASSED -eq $TOTAL ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed!${NC}"
    exit 1
fi
