#!/bin/sh

FCL=$(mktemp XXXX.fcl)
trap 'rm "$FCL"' EXIT

USER=${USER:=nknutson}
EMPHATIC_SOFT=${EMPHATIC_SOFT:=/exp/emph/app/users/${USER}/emphaticsoft}
TAG=${TAG:=$(cd "${EMPHATIC_SOFT}" && git describe --exact-match --tags)}
[ -z ${TAG} ] && { echo "Error: unable to determine tag"; exit 1; }

if [ ${#} = 2 ]; then
	RUN=${1}
	SUBRUN=$(printf "%04.f" ${2})
	[ -z "$(ls /exp/emph/data/raw/Mar2023/OutputData/emdaq_otsdaq_rootOutput_r${RUN}_s${SUBRUN}_*)" ] && { exit 1; }
	OUTPUT_DIR="/exp/emph/data/users/${USER}/${RUN}"
	mkdir -p ${OUTPUT_DIR}
	for file in /exp/emph/data/raw/Mar2023/OutputData/emdaq_otsdaq_rootOutput_r${RUN}_s${SUBRUN}_*; do
		LOG=$(mktemp "XXXX.log")
		sed -e "s|fileNames: .*|fileNames: [\"${file}\"]|" "/exp/emph/app/users/${USER}/emphaticsoft/RawDataUnpacker/daq2rawdigit_job.fcl" > "${FCL}"
		nice -n 20 art -c "${FCL}" -o "${OUTPUT_DIR}/emphdata_${TAG}_r${RUN}_s${SUBRUN}.artdaq.root" | tee --append "${LOG}"
	done
	mv "${LOG}" "${OUTPUT_DIR}/${TAG}_r${RUN}_s${SUBRUN}.${LOG}"
elif [ ${#} = 1 ]; then
	RUN=${1}
	[ -z "$(ls /exp/emph/data/raw/Mar2023/OutputData/emdaq_otsdaq_rootOutput_r${RUN}_s*_*)" ] && { exit 1; }
	OUTPUT_DIR="/exp/emph/data/users/${USER}/${RUN}"
	mkdir -p ${OUTPUT_DIR}
	for file in /exp/emph/data/raw/Mar2023/OutputData/emdaq_otsdaq_rootOutput_r${RUN}_s*_*; do
		SUBRUN=${file##*_s}; SUBRUN=${SUBRUN%%_*}
		LOG=$(mktemp "XXXX.log")
		sed -e "s|fileNames: .*|fileNames: [\"${file}\"]|" "/exp/emph/app/users/${USER}/emphaticsoft/RawDataUnpacker/daq2rawdigit_job.fcl" > "${FCL}"
		nice -n 20 art -c "${FCL}" -o "${OUTPUT_DIR}/emphdata_${TAG}_r${RUN}_s${SUBRUN}.artdaq.root" | tee --append ${LOG}
		mv "${LOG}" "${OUTPUT_DIR}/${TAG}_r${RUN}_s${SUBRUN}.${LOG}"
	done
else
	echo "Usage: ./${0} <RUN> [Optional: <SUBRUN>]"
	exit 1
fi
