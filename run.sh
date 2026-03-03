#!/bin/bash

TOOL=~/weazer/genmc-tool/genmc

N=10000

RCU_DIR=.
RCU_VERSION_DIR=$RCU_DIR/valtree/v3.0

COMMON_FLAGS=" --disable-estimation   --disable-sr --disable-ipr --count-distinct-execs   --disable-function-inliner   "

# verification FLAGS
VERIF_FLAGS=$COMMON_FLAGS

# random FLAGS
RANDOM_FLAGS=" --fuzz --fuzz-max=${N}  --mutation-policy=no-mutation $COMMON_FLAGS "
# fuzzing flags

# fuzz mode

COMMON_FZ_FLAGS=" --fuzz  --fuzz-max=${N}   --use-queue  --mutation-policy=revisit  --is-interesting=new  --fuzz-value-noblock=true --num-mutation=3 --insert-rand=30 -fuzz-corpus=20  $COMMON_FLAGS  "

# for flags in [VERIF_FLAGS, RANDOM_FLAGS, COMMON_FZ_FLAGS]
for flags in "$VERIF_FLAGS" "$RANDOM_FLAGS" "$COMMON_FZ_FLAGS"; do
	$TOOL $flags --unroll=5 -- -DASSERT_0 -I$RCU_VERSION_DIR -std=c11 $RCU_DIR/valtree/litmus_v3.c
	$TOOL $flags --unroll=5 -- -DFORCE_FAILURE_1 -I$RCU_VERSION_DIR -std=c11 $RCU_DIR/valtree/litmus_v3.c
	$TOOL $flags --unroll=5 -- -DFORCE_FAILURE_2 -I$RCU_VERSION_DIR -std=c11 $RCU_DIR/valtree/litmus_v3.c
	$TOOL $flags --unroll=5 -- -DFORCE_FAILURE_3 -I$RCU_VERSION_DIR -std=c11 $RCU_DIR/valtree/litmus_v3.c
	$TOOL $flags --unroll=5 -- -DFORCE_FAILURE_4 -I$RCU_VERSION_DIR -std=c11 $RCU_DIR/valtree/litmus_v3.c
	$TOOL $flags --unroll=5 -- -DFORCE_FAILURE_5 -I$RCU_VERSION_DIR -std=c11 $RCU_DIR/valtree/litmus_v3.c

	$TOOL $flags --unroll=19 -- -DFORCE_FAILURE_6 -I$RCU_VERSION_DIR -std=c11 $RCU_DIR/valtree/litmus_v3.c

done
