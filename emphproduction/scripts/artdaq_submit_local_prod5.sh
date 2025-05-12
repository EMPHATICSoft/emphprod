#!/bin/bash

tag=v05.00

# setup 
cd /exp/emph/app/users/gsdavies/prod5/build

source /exp/emph/app/users/gsdavies/prod5/emph-${tag}/setup/setup_emphatic.sh
source /exp/emph/app/users/gsdavies/prod5/emph-${tag}/ups/setup_for_development -p

# move to working directory
cd /exp/emph/app/users/gsdavies/prod5

#1c
DATA_DIR=/exp/emph/data/raw/Mar2023/OutputData
# Use Teresa's ssd merged files. Pretty sure don't need to redo this.
# We should consolidate them at any rate.
# This is for 1c data
SSD_DIR=/exp/emph/data/users/lackey32/unpack1c/ssdMerged

#1b
#DATA_DIR=/exp/emph/data/raw/June2022/OutputData/
#SSD_DIR=/exp/emph/data/production/prod5/ssdMerged


#common
ARTDAQ_DIR=/exp/emph/data/production/prod5/artdaq

# 1a: 400, 500, 600
# 1b: 1000, 1100, 1200, 1300
# 1c: 2000, 2100, ...

#copy run number files from Teresa.
# we can just add this to the emphprod directory
for RUN_NUM in $(cat /exp/emph/app/users/gsdavies/prod5/prod/runNumbers.txt)
do
    # First check the run data dir has any files
    shopt -s nullglob dotglob
    #files=(${SSD_DIR}/${RUN_NUM}/Run${RUN_NUM}*)
    files=(${SSD_DIR}/Run${RUN_NUM}*)
    emdaqfiles=(${DATA_DIR}/emdaq*r${RUN_NUM}*)
    nSubruns=${#emdaqfiles[@]}
    
    if [ $nSubruns -gt 0 ]; then
	echo "We have files!"
	echo "Run $RUN_NUM, # of Subruns: $nSubruns"
	echo "Proceed."
	# And make the output directory
	mkdir -p ${ARTDAQ_DIR}/${RUN_NUM}
    else
	echo "No files. Sad face."
	echo "Skipping ${RUN_NUM}."
	continue
    fi
    for SUBRUN_NUM in $(seq 1 $nSubruns)
    do
	echo "Subrun: $SUBRUN_NUM"
	# Assumes files end with _X.dat
	QUERY="_${SUBRUN_NUM}.dat"
	if [[ "${files[*]}" =~ "${QUERY}" ]]; then
	    echo "exists"
	else
	    #echo "nope ${SSD_DIR}/${RUN_NUM}/Run${RUN_NUM}${QUERY} doesn't exist."
	    echo "nope ${SSD_DIR}/Run${RUN_NUM}${QUERY} doesn't exist."
	    continue
	fi
	# SUBRUN_NUM=$(echo 00000${SUBRUN_NUM} | tail -c 5)
	SUBRUN="$(printf '%04d' "$SUBRUN_NUM")"
	echo "SUBRUN is " $SUBRUN

	# Check output file doesn't already exist
	if [ -f ${ARTDAQ_DIR}/${RUN_NUM}/emphdata_${tag}_r${RUN_NUM}_s${SUBRUN_NUM}.artdaq.root ]; then
	    echo "Expected output: ${ARTDAQ_DIR}/${RUN_NUM}/emphdata_${tag}_r${RUN_NUM}_s${SUBRUN_NUM}.artdaq.root"
	    echo "...already exists. Skipping."
	    continue;
	fi

	
	# find the equivalent emdaq_otsdaq file
	EMDAQ_ARTFILE=$(find ${DATA_DIR} -maxdepth 1 -name "emdaq*r${RUN_NUM}_s${SUBRUN}_*" -exec basename {} \;)
	echo
	echo ${DATA_DIR}/${EMDAQ_ARTFILE}
	echo
	# Check result is a real file
	if [ -f ${DATA_DIR}/${EMDAQ_ARTFILE} ]; then
	    echo "${DATA_DIR}/${EMDAQ_ARTFILE} exists. Proceed"
	else
	    echo "r${RUN_NUM}_s${SUBRUN} does NOT exist. Skip."
	    continue
	fi

	# copy steering job fcl to temp area
	# we'll be editing it on the fly for each job
	cp /exp/emph/app/users/gsdavies/prod5/build/fcl/daq2rawdigit_job.fcl /tmp/

	# env var. for job fcl
	JOBFCL=/tmp/daq2rawdigit_job.fcl

        #source.SSDFilePrefix: "${SSD_DIR}/${RUN_NUM}/"
	#1b,1c
	cat >>${JOBFCL} <<EOF
         source.fileNames: ["${DATA_DIR}/${EMDAQ_ARTFILE}"]
         source.channelMapFileName: "ChannelMap_Mar23.txt"
         source.SSDFilePrefix: "${SSD_DIR}/"
         outputs.out1.fileName: "${ARTDAQ_DIR}/${RUN_NUM}/emphdata_${tag}_r%r_s${SUBRUN_NUM}.artdaq.root"
EOF
	
	LOGFILE=${ARTDAQ_DIR}/${RUN_NUM}/logs/prod5_artdaq_${RUN_NUM}_${SUBRUN_NUM}.log
	mkdir -p ${ARTDAQ_DIR}/${RUN_NUM}/logs
	echo
        echo "Running the art job on Run ${RUN_NUM}, SubRun ${SUBRUN_NUM}..."
	echo "Log saved to ${LOGFILE}"
        # run the job
	art -c ${JOBFCL} |& tee -a $LOGFILE
	# Cleanup
	# Remove the over-written job fcl
	rm -f ${JOBFCL}
	# We need to keep this?!
	mv daq2root_${RUN_NUM}_${SUBRUN}.root ${ARTDAQ_DIR}/${RUN_NUM}/
    done
done
