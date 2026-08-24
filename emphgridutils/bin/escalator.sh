#!/bin/sh

[ $# -ne 1 ] && { echo "Give me a run number! Exiting"; exit 1; }
run=${1}
EMPHATIC_SOFT=${EMPHATIC_SOFT:=/exp/emph/app/users/${USER}/emphaticsoft}
EMPHATIC_BUILD=${EMPHATIC_BUILD:=/exp/emph/app/users/${USER}/build}
EMPHATIC_PROD=${EMPHATIC_PROD:=/exp/emph/app/users/${USER}/emphprod}
MILLEPEDE_FQ_DIR=${MILLEPEDE_FQ_DIR:=/cvmfs/emphatic.opensciencegrid.org/products/millepede_ii/v04_17_05/Linux64bit+3.10-2.17-e20}

JOBSUB_GROUP=${JOBSUB_GROUP:=emphatic}
htgettoken -a htvaultprod.fnal.gov -i emphatic

# Local copy of steering file
[ -s 'steer_all.txt' ] || cp ${EMPHATIC_SOFT}/Alignment/mp2/steer_all.txt steer_all.txt

# For readability
gridBin=${EMPHATIC_PROD}/emphgridutils/bin
iteration=1
subrunList="textfiles/all${run}.txt"
while true; do
	GRID_RETURN="/pnfs/emphatic/scratch/users/${USER}/alignment/iteration_${iteration}"
	# Iterate forward (calculate new alignment constants)
	jobID=$("${gridBin}/submit_emph_art.py" reco "${EMPHATIC_SOFT}/CAFMaker/prod_reco_caf_job.fcl" --stdin < "${subrunList}" --code-dir "${EMPHATIC_SOFT}" --build-dir "${EMPHATIC_BUILD}" --output "${GRID_RETURN}" | grep 'Use job id .* to retrieve output')
	jobID=${jobID#Use job id }
	jobID=${jobID%%\.[0-9]* to retrieve output}
	[ -z "${jobID}" ] && { echo 'Failed to submit jobs. Exiting.'; exit 1; }

	# Wait for jobs to finish
	holdAndRelease=0;
	while [ $(jobsub_q --jobid ${jobID} | grep -c ${jobID}) -gt 0 ]; do
		# Little loading screen :)
		while [ "${ellipses}" != '.....' ]; do
			printf '\r%s%s%s' 'Waiting for grid to finish jobs' ${ellipses} '     '
			sleep 2
			ellipses="${ellipses}."
		done; unset ellipses
		holdAndRelease=$((${holdAndRelease} + 10))
		[ ${holdAndRelease} -ge 600 ] && { # every 5 mins, hold and release jobs: rematches jobs to nodes
			jobsub_hold ${jobID};
			sleep 10;
			jobsub_release ${jobID};
			holdAndRelease=0;
		}
	done; unset holdAndRelease
	# One last delay to make sure all files get transferred nicely
	sleep 10

	# Empty the pede steering file of mille bin file entries
	sed "/m.*.bin/d" -i steer_all.txt
	# Add entries to the pede steering file
	for milleFile in $(printf '%s\n' ${GRID_RETURN}/*/*.bin | sort -rV); do
		sed "s|Cfiles|Cfiles\n${milleFile}|" -i steer_all.txt
	done

	# Scale errors on first iteration only
	factor=10
	[ ${iteration} -eq 1 ] \
			 && sed "s/.*scaleerrors .*/scaleerrors ${factor}/" -i steer_all.txt \
			 || sed "s/.*scaleerrors .*/!scaleerrors ${factor}/" -i steer_all.txt
	#Pede time!
	${MILLEPEDE_FQ_DIR}/bin/pede -i steer_all.txt
	[ -s 'millepede.res' ] || { echo "Millepede-II was unable to complete. Exiting."; exit 1; }

	# Check if residuals are small enough
	anyBigger='false'
	FIFO=$(mktemp -u) # FIFO is necessary to return global variable ${anyBigger}
	mkfifo ${FIFO} && trap "rm ${FIFO}" EXIT INT TERM
	tail -n +2 millepede.res | tr -s ' ' | cut -d ' ' -f 5,6 > ${FIFO} &
	while read -r VALUE ERROR; do
		[ -z ${VALUE} ] || [ -z ${ERROR} ] && continue;
		comparison="$(echo "${VALUE#-} > ${ERROR#-}" | bc -l 2>/dev/null)"
		[ ${comparison} -eq 1 ] && {
			anyBigger='true';
			break;
		}
	done < ${FIFO}
	[ "${anyBigger}" = 'false' ] && {
		echo "Successfully converged. Cleaning up and exiting";
		mv millepede.* "${GRID_RETURN}"; # Archive into iteration directory
		exit 1;
	}
	echo "Did not converge. Try again."
	unset anyBigger

	# Convert residual to SSD alignment file
	${EMPHATIC_SOFT}/Alignment/mp2/mp2emph.sh millepede.res true "Shifts.txt"
	# Archive into iteration directory
	mv millepede.* "${GRID_RETURN}"

	# Add alignment constants to original alignment constants
	# - why is Robert subtracting in addalign.sh?
	${EMPHATIC_SOFT}/Alignment/mp2/addalign.sh "${EMPHATIC_SOFT}/ConstBase/Align/SSDAlign_1c_${run}.txt" "Shifts.txt" "NewlyAligned.txt"
	# Archive into iteration directory
	mv 'Shifts.txt' "${GRID_RETURN}"

	[ -s "NewlyAligned.txt" ] || { echo "Failed to produce newly aligned parameters. Exiting"; exit 1; }
	# Update alignment constants and iterate
	cp "NewlyAligned.txt" "${EMPHATIC_SOFT}/ConstBase/Align/SSDAlign_1c_${run}.txt"

	# Archive into iteration directory
	mv 'NewlyAligned.txt' "${GRID_RETURN}"

	iteration=$((${iteration} + 1))
	[ $iteration -eq 10 ] && { echo "Failed to converge within ${iteration} iterations. Exiting"; exit 1; }
done
