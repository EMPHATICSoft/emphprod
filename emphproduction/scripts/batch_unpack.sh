#!/bin/sh
if [ ${#} -gt 2 ] || [ ${#} = 0 ]; then
	echo "Usage: \n${0} RUN SUBRUN\n${0} RUN"
	exit 1
fi

FCL=$(mktemp XXXX.fcl)
trap 'rm "$FCL"' EXIT

USER=${USER:=nknutson}
EMPHATIC_SOFT=${EMPHATIC_SOFT:=/exp/emph/app/users/${USER}/emphaticsoft}
OUTPUT_DIR=${OUTPUT_DIR:="/exp/emph/data/users/${USER}"}
TAG=${TAG:=$(cd "${EMPHATIC_SOFT}" && git describe --exact-match --tags)}
[ -z ${TAG} ] && { echo "Error: unable to determine tag"; exit 1; }

RUN=${1}
case ${RUN} in
	[0-9][0-9][0-9])
		exit
		;;
	1[0-9][0-9][0-9])
		SUBRUN=${2}
		DATA_DIR='/exp/emph/data/raw/June2022/OutputData'
		SSD_DIR="/exp/emph/data/production/prod5/ssdMerged/${RUN}"
		;;
	2[0-9][0-9][0-9])
		SUBRUN=$(printf "%04.f" ${2})
		DATA_DIR='/exp/emph/data/raw/Mar2023/OutputData'
		SSD_DIR='/exp/emph/data/users/lackey32/unpack1c/ssdMerged'
		;;
esac
OUTPUT_DIR="${OUTPUT_DIR}/${RUN}"
if [ ${#} = 2 ]; then
	[ -z "$(ls ${DATA_DIR}/emdaq_otsdaq_rootOutput_r${RUN}_s${SUBRUN}_*)" ] && { exit 1; }
	mkdir -p ${OUTPUT_DIR}
	for file in ${DATA_DIR}/emdaq_otsdaq_rootOutput_r${RUN}_s${SUBRUN}_*; do
		LOG=$(mktemp "XXXX.log")
		sed -e "s|fileNames: .*|fileNames: [\"${file}\"]|" -e "s|SSDFilePrefix: .*|SSDFilePrefix: \"${SSD_DIR}/\"|" "${EMPHATIC_SOFT}/RawDataUnpacker/daq2rawdigit_job.fcl" > "${FCL}"
		nice -n 20 art -c "${FCL}" -o "${OUTPUT_DIR}/emphdata_${TAG}_r${RUN}_s${SUBRUN}.artdaq.root" | tee --append "${LOG}"
	done
	SUBRUN=$(printf "%04.f" ${2})
	mv "daq2root_${RUN}_${SUBRUN}.root" "${OUTPUT_DIR}/"
	mv "${LOG}" "${OUTPUT_DIR}/${TAG}_r${RUN}_s${SUBRUN}.${LOG}"
elif [ ${#} = 1 ]; then
	[ -z "$(ls ${DATA_DIR}/emdaq_otsdaq_rootOutput_r${RUN}_s*_*)" ] && { exit 1; }
	mkdir -p ${OUTPUT_DIR}
	for file in ${DATA_DIR}/emdaq_otsdaq_rootOutput_r${RUN}_s*_*; do
		SUBRUN=${file##*_s}; SUBRUN=${SUBRUN%%_*}
		LOG=$(mktemp "XXXX.log")
		sed -e "s|fileNames: .*|fileNames: [\"${file}\"]|" -e "s|SSDFilePrefix: .*|SSDFilePrefix: \"${SSD_DIR}/\"|" "${EMPHATIC_SOFT}/RawDataUnpacker/daq2rawdigit_job.fcl" > "${FCL}"
		nice -n 20 art -c "${FCL}" -o "${OUTPUT_DIR}/emphdata_${TAG}_r${RUN}_s${SUBRUN}.artdaq.root" | tee --append ${LOG}
		SUBRUN=$(printf "%04.f" ${2})
		mv "daq2root_${RUN}_${SUBRUN}.root" "${OUTPUT_DIR}/"
		mv "${LOG}" "${OUTPUT_DIR}/${TAG}_r${RUN}_s${SUBRUN}.${LOG}"
	done
else
	echo "Usage: ./${0} <RUN> [Optional: <SUBRUN>]"
	exit 1
fi
