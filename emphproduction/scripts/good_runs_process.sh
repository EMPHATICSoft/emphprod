#!/bin/sh
[ -f ./batch_unpack.sh ] || { echo "Error: need batch_unpack.sh"; exit 1; }
grep 'good' GoodRunsList.txt | sed 's/good//' | while read -r line; do
	RUN=$(echo ${line} | cut -f 1 -d ' ')
	SUBRUN=$(echo ${line} | cut -f 2 -d ' ')
	./batch_unpack.sh ${RUN} ${SUBRUN}
done
