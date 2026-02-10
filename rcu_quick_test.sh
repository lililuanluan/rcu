#!/bin/sh

# Simplified RCU test script with C11 atomics

# Run GenMC with smaller bounds for quick testing
../../genmc  --fuzz --fuzz-max=1000  --mutation-policy=no-mutation  --disable-estimation --disable-race-detection --disable-sr --disable-ipr --count-distinct-execs  --unroll=5 --  -I./valtree/v3.19 -std=c11  valtree/litmus.c
