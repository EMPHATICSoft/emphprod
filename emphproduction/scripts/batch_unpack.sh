#!/bin/sh

FCL=$(mktemp XXXX.fcl)
trap 'rm "$FCL"' EXIT

if [ ${#} = 2 ]; then
	RUN=${1}
	SUBRUN=$(printf "%04.f" ${2})
	[ -z "$(ls /exp/emph/data/raw/Mar2023/OutputData/emdaq_otsdaq_rootOutput_r${RUN}_s${SUBRUN}_*)" ] && { exit 1; }
	OUTPUT_DIR="/exp/emph/data/users/nknutson/${RUN}"
	mkdir -p ${OUTPUT_DIR}
	for file in /exp/emph/data/raw/Mar2023/OutputData/emdaq_otsdaq_rootOutput_r${RUN}_s${SUBRUN}_*; do
		LOG=$(mktemp "XXXX.log")
		sed -e "s|fileNames: .*|fileNames: [\"${file}\"]|" '/exp/emph/app/users/nknutson/emphaticsoft/RawDataUnpacker/daq2rawdigit_job.fcl' > "${FCL}"
		nice -n 20 art -c "${FCL}" -o "${OUTPUT_DIR}/emphdata_r${RUN}_s${SUBRUN}.artdaq.root" | tee --append "${LOG}"
	done
	mv "${LOG}" "${OUTPUT_DIR}/r${RUN}_s${SUBRUN}.${LOG}"
elif [ ${#} = 1 ]; then
	RUN=${1}
	[ -z "$(ls /exp/emph/data/raw/Mar2023/OutputData/emdaq_otsdaq_rootOutput_r${RUN}_s*_*)" ] && { exit 1; }
	OUTPUT_DIR="/exp/emph/data/users/nknutson/${RUN}"
	mkdir -p ${OUTPUT_DIR}
	for file in /exp/emph/data/raw/Mar2023/OutputData/emdaq_otsdaq_rootOutput_r${RUN}_s*_*; do
		LOG=$(mktemp "XXXX.log")
		sed -e "s|fileNames: .*|fileNames: [\"${file}\"]|" '/exp/emph/app/users/nknutson/emphaticsoft/RawDataUnpacker/daq2rawdigit_job.fcl' > "${FCL}"
		nice -n 20 art -c "${FCL}" -o "${OUTPUT_DIR}/emphdata_r${RUN}_s${SUBRUN}.artdaq.root" | tee --append ${LOG}
		mv "${LOG}" "${OUTPUT_DIR}/r${RUN}.${LOG}"
	done
else
	echo "Usage: ./${0} <RUN> [Optional: <SUBRUN>]"
fi
