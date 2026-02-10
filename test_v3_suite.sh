#!/bin/bash

# litmus_v3.c Test Suite
# Tests the RCU grace period guarantee for kernel v3.0

set -e

GENMC="../../genmc"
KERNEL_VERSION="v3.0"
UNROLL=5
FUZZ_MAX=100

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

cd /home/luanli/michalis/genmc-tool/bench/rcu

echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║      Testing litmus_v3.c - RCU v3.0 Test Suite       ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo

# Helper function to run test
run_test() {
    local name="$1"
    local define="$2"
    local expect_pass="$3"
    
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}Test: $name${NC}"
    if [ -n "$define" ]; then
        echo "Flag: $define"
    fi
    echo "Expected: $expect_pass"
    echo
    
    local cmd_opts=""
    if [ -n "$define" ]; then
        cmd_opts="$define"
    fi
    
    if timeout 60 ${GENMC} --fuzz --fuzz-max=${FUZZ_MAX} \
        --mutation-policy=no-mutation \
        --disable-estimation --disable-race-detection --disable-sr --disable-ipr \
        --count-distinct-execs --unroll=${UNROLL} \
        -- -I./valtree/${KERNEL_VERSION} -std=c11 ${cmd_opts} valtree/litmus_v3.c 2>&1 | tee /tmp/test_output.log
    then
        if grep -q "No errors were detected" /tmp/test_output.log; then
            echo -e "${GREEN}✓ Result: No errors detected${NC}"
            if [ "$expect_pass" = "should PASS" ]; then
                return 0
            else
                return 1
            fi
        else
            echo -e "${RED}✗ Result: Errors detected${NC}"
            if [ "$expect_pass" = "should FAIL" ]; then
                return 0
            else
                return 1
            fi
        fi
    else
        echo -e "${RED}✗ Result: Timeout or error${NC}"
        if [ "$expect_pass" = "should FAIL" ]; then
            return 0
        else
            return 1
        fi
    fi
}

# Run tests
PASS=0
FAIL=0

echo
run_test "Normal execution" "" "should PASS"
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ PASSED${NC}"; ((PASS++))
else
    echo -e "${RED}✗ FAILED${NC}"; ((FAIL++))
fi
echo

run_test "With -DASSERT_0 (unconditional assertion)" "-DASSERT_0" "should FAIL"
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ PASSED${NC}"; ((PASS++))
else
    echo -e "${RED}✗ FAILED${NC}"; ((FAIL++))
fi
echo

run_test "With -DFORCE_FAILURE_1 (reschedule in reader)" "-DFORCE_FAILURE_1" "should FAIL"
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ PASSED${NC}"; ((PASS++))
else
    echo -e "${RED}✗ FAILED${NC}"; ((FAIL++))
fi
echo

run_test "With -DFORCE_FAILURE_2" "-DFORCE_FAILURE_2" "should FAIL"
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ PASSED${NC}"; ((PASS++))
else
    echo -e "${RED}✗ FAILED${NC}"; ((FAIL++))
fi
echo

# Summary
echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║ Test Summary${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo
echo -e "Passed: ${GREEN}$PASS${NC}"
echo -e "Failed: ${RED}$FAIL${NC}"
echo "Total: $((PASS + FAIL))"
echo

if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed!${NC}"
    exit 1
fi
