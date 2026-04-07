#!/bin/bash
#Functions that help generate files and check for common mistakes when submitting grid jobs

#Environment variables used by multiple functions
outDirTag="ROOT_OUTPUT"
tarFileName="myEmphaticsoft.tar.gz"
safeScratchDir="/exp/emph/app/users/${USER}"

#Make output directory.  It must not exist yet because overwriting files on /pnfs can take down /pnfs!
makeOutputDirectory()
{
  hostOutDir=$1

  if [[ -e ${hostOutDir} ]]; then
    echo "${hostOutDir} already exists.  You must delete it before you can send grid output there." >&2
    exit 1
  fi
  
  mkdir ${hostOutDir}
}

#Copy user's software development area to the grid
#Seems like I don't need to use resilient according to the jobsub documentation at https://cdcvs.fnal.gov/redmine/projects/jobsub/wiki/Jobsub_submit
makeTarball()
{
  codeDir=$1
  hostOutDir=$2

  #Try to update tarball if it already exists
  #TODO: Get tar --update working
  if [[ -f ${safeScratchDir}/${tarFileName} ]]
  then
  #  echo "Found existing tarball at ${safeScratchDir}/${tarFileName}.  Trying to update it for newer files!"
  #  #tarball must be unzipped to -u[pdate] it
  #  unpigz ${safeScratchDir}/${tarFileName}
  #  tar --update ${safeScratchDir}/$(basename ${safeScratchDir}/${tarFileName}).tar
  #  pigz ${safeScratchDir}/$(basename ${safeScratchDir}/${tarFileName}).tar
    rm ${safeScratchDir}/${tarFileName}
  fi
  #else
    echo "No tarball at ${safeScratchDir}/${tarFileName}, so creating a new one from ${codeDir}.  This usually takes a few minutes..."
    #Make new tarball from user's active development area
    tar -czf ${safeScratchDir}/${tarFileName} -C $(dirname ${codeDir}) $(basename ${codeDir})
  #fi
  #Put the tarball somewhere the grid can find it and document what code was used at the same time
  cp ${safeScratchDir}/${tarFileName} ${hostOutDir}/

  if [[ ! -f ${hostOutDir}/${tarFileName} ]]
  then
    echo "Tarring up ${codeDir} into ${safeScratchDir}/${tarFileName} and/or copy to /pnfs failed!" >&2
    exit 2
  fi
}

#Write the beginning of the bash script that runs on a grid node.
#Gets code from the tarball and sets up user's emphaticsoft area.
#PROCESS and CONDOR_DIR_* are provided by Fermilab's jobsub commands.
makeWrapperBoilerplate()
{
  codeDir=$1

  echo "#!/usr/bin/bash"
  echo "set -euo pipefail"
  echo ""
  echo "die() {"
  echo "  echo \"ERROR: \$*\" >&2"
  echo "  exit 1"
  echo "}"
  echo ""
  echo "log() {"
  echo "  echo \"[\$(date -u +%Y-%m-%dT%H:%M:%SZ)] \$*\""
  echo "}"
  echo ""
  echo "require_env() {"
  echo "  local var_name=\$1"
  echo "  [[ -n \${!var_name:-} ]] || die \"Required environment variable is missing: \${var_name}\""
  echo "}"
  echo ""
  echo "on_error() {"
  echo "  local rc=\$?"
  echo "  echo \"ERROR: command failed at line \$1 (exit code \${rc})\" >&2"
  echo "  echo \"PWD=\$(pwd)\" >&2"
  echo "  echo \"PATH=\${PATH}\" >&2"
  echo "  type -a art >&2 || true"
  echo "  exit \${rc}"
  echo "}"
  echo "trap 'on_error \${LINENO}' ERR"
  echo ""
  echo "require_env INPUT_TAR_DIR_LOCAL"
  echo "require_env CONDOR_DIR_${outDirTag}"
  echo "require_env CONDOR_DIR_INPUT"
  echo "require_env PROCESS"
  echo ""
  echo "payload_dir=\${INPUT_TAR_DIR_LOCAL}/$(basename ${codeDir})"
  echo "setup_emphatic=\${payload_dir}/emphaticsoft/setup/setup_emphatic.sh"
  echo "setup_for_grid=\${payload_dir}/emphaticsoft/setup/setup_for_grid.sh"
  echo ""
  echo "[[ -f \${setup_emphatic} ]] || die \"Missing setup script: \${setup_emphatic}\""
  echo "[[ -f \${setup_for_grid} ]] || die \"Missing setup script: \${setup_for_grid}\""
  echo ""
  echo "if [[ -d \${payload_dir}/opt/build ]]; then"
  echo "  build_dir=\${payload_dir}/opt/build"
  echo "elif [[ -d \${payload_dir}/build ]]; then"
  echo "  build_dir=\${payload_dir}/build"
  echo "else"
  echo "  die \"Could not find build directory under \${payload_dir} (checked opt/build and build)\""
  echo "fi"
  echo ""
  echo "log \"Sourcing setup_emphatic.sh from \${setup_emphatic}\""
  echo "source \${setup_emphatic}"
  echo "log \"Finished setup_emphatic.sh\""
  echo ""
  echo "cd \${build_dir}"
  echo "log \"Changed directory to build area: \${build_dir}\""
  echo ""
  echo "log \"Sourcing setup_for_grid.sh from \${setup_for_grid}\""
  echo "source \${setup_for_grid}"
  echo "log \"Finished setup_for_grid.sh\""
  echo ""
  echo "if [[ -f setup_emphaticsoft ]]; then"
  echo "  log \"Sourcing local setup_emphaticsoft from build area\""
  echo "  source setup_emphaticsoft"
  echo "else"
  echo "  log \"setup_emphaticsoft not found in build area; skipping\""
  echo "fi"
  echo ""
  echo "command -v art >/dev/null 2>&1 || die \"'art' not found after setup. Check setup_emphatic.sh/setup_for_grid.sh and payload build products.\""
  echo "log \"art found at: \$(command -v art)\""
  echo ""
  echo "cd \${CONDOR_DIR_${outDirTag}}"
  echo "mkdir -p job_\${PROCESS}"
  echo "cd job_\${PROCESS}"
  echo "log \"Running in output directory: \$(pwd)\""
}

#Arguments to jobsub_submit for getting emphatic user code to the grid and running in SL7
getBasicJobsubArgs()
{
  hostOutDir=$1

  echo "-d ${outDirTag} ${hostOutDir} -l '+SingularityImage=\"/cvmfs/singularity.opensciencegrid.org/fermilab/fnal-wn-sl7:latest\"' --tar_file_name dropbox://${hostOutDir}/${tarFileName} --use-cvmfs-dropbox"
}

#Check that output directory is on /pnfs
checkOutputDir()
{
  hostOutDir=$1
  if [[ ! $hostOutDir =~ /pnfs/emphatic/persistent ]]
  then
    echo "Output directory must be on /pnfs/emphatic/persistent, but it's currently set to $hostOutDir"
    echo "Use submit_emph_art.py (gen/reco) from the directory where you want output to go."
    exit 1
  fi
}
