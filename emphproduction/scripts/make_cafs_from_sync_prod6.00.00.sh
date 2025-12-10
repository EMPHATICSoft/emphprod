#!/bin/bash

# -------------------------
# Setup
# -------------------------

tag=v06.00.00

# setup 
cd /exp/emph/app/users/abhattar/prod6.00.00/build

source /exp/emph/app/users/abhattar/prod6.00.00/emphaticsoft/setup/setup_emphatic.sh
source /exp/emph/app/users/abhattar/prod6.00.00/emphaticsoft/ups/setup_for_development -p

# Working directory
cd /exp/emph/app/users/abhattar/prod6.00.00

# -------------------------
# Directories for this task
# -------------------------

# Where the time-sync artdaq files live
ARTDAQ_DIR=/exp/emph/data/production/prod6/sync

# Where we want CAFs to go
CAF_DIR=/exp/emph/data/users/abhattar/CAFs

# CAF job FHiCL
CAF_FCL=/exp/emph/app/users/abhattar/prod6.00.00/build/fcl/prod_reco_caf_job.fcl

mkdir -p "${CAF_DIR}"

shopt -s nullglob

# ---------------------------------------------
# Loop over all run directories in ARTDAQ_DIR
# ---------------------------------------------

for RUN_NUM in $(ls "${ARTDAQ_DIR}" | grep '^[0-9]\{4\}$'); do
    RUN_ARTDAQ_DIR="${ARTDAQ_DIR}/${RUN_NUM}"

    [ -d "${RUN_ARTDAQ_DIR}" ] || continue

    echo "======================================="
    echo "Processing run ${RUN_NUM}"
    echo "ARTDAQ dir: ${RUN_ARTDAQ_DIR}"

    # All artdaq files for this run
    files=("${RUN_ARTDAQ_DIR}"/emphdata_r${RUN_NUM}_s*.artdaq.root)
    nSubruns=${#files[@]}

    if [ "${nSubruns}" -eq 0 ]; then
        echo "  No artdaq files for run ${RUN_NUM} – skipping."
        continue
    fi

    echo "  Found ${nSubruns} subrun(s)."

    # Make CAF output + log directory for this run
    RUN_CAF_DIR="${CAF_DIR}/${RUN_NUM}"
    RUN_LOG_DIR="${RUN_CAF_DIR}/logs"
    mkdir -p "${RUN_CAF_DIR}" "${RUN_LOG_DIR}"

    # -----------------------------------------
    # Loop over subruns (artdaq ROOT files)
    # -----------------------------------------
    for f in "${files[@]}"; do
        fname=$(basename "${f}")
        # fname example: emphdata_r2668_s0001.artdaq.root

        # Extract subrun "0001"
        subrun_part=${fname#*s}      # "0001.artdaq.root"
        SUBRUN=${subrun_part%%.*}    # "0001"

        echo "  -> Run ${RUN_NUM}, subrun ${SUBRUN}, file ${fname}"

        # Expected CAF name
        CAF_FILE="${RUN_CAF_DIR}/emphdata_r${RUN_NUM}_s${SUBRUN}.artdaq.${tag}_caf.root"

        if [ -f "${CAF_FILE}" ]; then
            echo "     CAF already exists (${CAF_FILE}). Skipping."
            continue
        fi

        LOGFILE="${RUN_LOG_DIR}/prod6.00.00_caf_r${RUN_NUM}_s${SUBRUN}.log"

        echo "     Writing CAFs into: ${RUN_CAF_DIR}"
        echo "     Log: ${LOGFILE}"

        # Run art
        (
            cd "${RUN_CAF_DIR}"
            art -c "${CAF_FCL}" "${f}" |& tee "${LOGFILE}"
        )

        echo "     Done subrun ${SUBRUN}."
        echo
    done

    echo "Finished run ${RUN_NUM}."
    echo
done

echo "All done with CAF production."

