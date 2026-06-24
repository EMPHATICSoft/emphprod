## THIS REQUIRES A SPECIAL VERSION OF GEOMETRY.CXX TO RUN ##

emphprod/emphgridutils/bin/submit_emph_art.py gen \
  emphprod/emphgridutils/bin/generateMCJob.sh \
  --njobs 10 \
  --run-number 2408 \
  --first-subrun 1 \
  --nEvts 10 \
  --memory 4GB \
  --disk 3GB \
  --particle pion \
  --template emphprod/emphgridutils/bin/g4gen_caf_job.fcl \
  --payload-tarball /pnfs/emphatic/persistent/users/manueld/emph_latest.tar \
  --output /pnfs/emphatic/scratch/users/manueld/tests \
