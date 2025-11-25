#!/bin/sh
for file in /exp/emph/data/raw/Mar2023/OutputData/emdaq_otsdaq_rootOutput_r2328_s*; do
	#echo $file
	sed -e "s|fileNames: .*|fileNames: [\"$file\"]|" '/exp/emph/app/users/nknutson/emphaticsoft/RawDataUnpacker/daq2rawdigit_job.fcl' > tmp.fcl
	art -c tmp.fcl || exit 1
done
