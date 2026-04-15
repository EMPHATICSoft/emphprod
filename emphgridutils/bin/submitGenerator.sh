#!/bin/bash
# submitGenerator.sh: Deprecated wrapper around submit_emph_art.py

set -euo pipefail

if [[ ${1:-} == "-h" || ${1:-} == "--help" || $# < 3 ]]; then
  echo "DEPRECATED: Use emphgridutils/bin/submit_emph_art.py gen ..."
  echo "Usage: submitGenerator.sh template.fcl generator.sh nJobs [output directory]"
  echo "- generator.sh takes template.fcl as input and prints the job-specific"
  echo "configuration to stdout. submit_emph_art.py now controls run/subrun"
  echo "assignment at the CLI."
  echo "- nJobs is an integer number of jobs to run in parallel."
  echo "- This wrapper forwards to submit_emph_art.py generator."
  exit 1
fi

echo "WARNING: submitGenerator.sh is deprecated. Use submit_emph_art.py gen instead." >&2

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
python_cli="${script_dir}/submit_emph_art.py"

if [[ ! -f ${python_cli} ]]; then
  echo "submit_emph_art.py not found at ${python_cli}" >&2
  exit 2
fi

if [[ ! -x ${python_cli} ]]; then
  chmod +x "${python_cli}"
fi

templateConfig=$1
generatorScript=$2
nJobs=$3

if [[ $# -ge 4 ]]; then
  exec "${python_cli}" gen "${generatorScript}" --njobs "${nJobs}" --template "${templateConfig}" --output "$4"
fi

exec "${python_cli}" gen "${generatorScript}" --njobs "${nJobs}" --template "${templateConfig}"
