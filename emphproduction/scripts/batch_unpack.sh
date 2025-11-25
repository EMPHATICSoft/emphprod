#!/bin/sh

FCL=$(mktemp XXXX.fcl)
LOG=$(mktemp XXXX.log)
trap 'rm "$FCL"' EXIT

if [ ${#} = 2 ]; then
	RUN=${1}
	SUBRUN=$(printf "%04d" ${2})
	for file in /exp/emph/data/raw/Mar2023/OutputData/emdaq_otsdaq_rootOutput_r${RUN}_s${SUBRUN}_*; do
		sed -e "s|fileNames: .*|fileNames: [\"${file}\"]|" '/exp/emph/app/users/nknutson/emphaticsoft/RawDataUnpacker/daq2rawdigit_job.fcl' > "${FCL}"
		art -c "${FCL}" | tee --append "${LOG}"
	done
	mv "${LOG}" "r${RUN}_s${SUBRUN}.${LOG}"
elif [ ${#} = 1 ]; then
	RUN=${1}
	for file in /exp/emph/data/raw/Mar2023/OutputData/emdaq_otsdaq_rootOutput_r${RUN}_s*_*; do
		sed -e "s|fileNames: .*|fileNames: [\"${file}\"]|" '/exp/emph/app/users/nknutson/emphaticsoft/RawDataUnpacker/daq2rawdigit_job.fcl' > "${FCL}"
		art -c "${FCL}" | tee --append ${LOG}
	done
	mv "${LOG}" "r${RUN}.${LOG}"
else
	echo "Usage: ./${0} <RUN> [Optional: <SUBRUN>]"
fi
