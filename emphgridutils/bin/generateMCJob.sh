#!/bin/bash

FIRST_RUN=2408
FIRST_SUBRUN=1
timestamp=$(date +%N | cut -c 1-8 - | sed -E 's/0*(.*)/\1/g') #Last 8 digits of nanoseconds because GEANT only supports seeds up to 9x10^8

template=$1
run_number=${2:-$((PROCESS + FIRST_RUN))}
subrun_number=${3:-$FIRST_SUBRUN}
nevts=${4:-10}
SEED=$((PROCESS + timestamp))

sed "s/@@RUN@@/$run_number/g" < "$template" > withRun.fcl
sed "s/@@SUBRUN@@/$subrun_number/g" < withRun.fcl > withRunSubrun.fcl
sed "s/@@NEVTS@@/$nevts/g" < withRunSubrun.fcl > withRunSubrunNevts.fcl
sed "s/@@SEED@@/$SEED/g" < withRunSubrunNevts.fcl
