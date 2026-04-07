#!/bin/bash
# submitReconstruction.sh: Deprecated wrapper around submit_emph_art.py

set -euo pipefail

if [[ ${1:-} == "-h" || ${1:-} == "--help" || $# -lt 1 ]]; then
  echo "DEPRECATED: Use emphgridutils/bin/submit_emph_art.py reco ..."
  echo "Usage: submitReconstruction.sh template.fcl outputDir input.root [moreInput.root...]"
  echo "Usage: submitReconstruction.sh template.fcl [outputDir] #Reads file list from stdin"
  echo "- This wrapper forwards to submit_emph_art.py reconstruction."
  exit 1
fi

echo "WARNING: submitReconstruction.sh is deprecated. Use submit_emph_art.py reco instead." >&2

configFile=$1

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
python_cli="${script_dir}/submit_emph_art.py"

if [[ ! -f ${python_cli} ]]; then
  echo "submit_emph_art.py not found at ${python_cli}" >&2
  exit 2
fi

if [[ ! -x ${python_cli} ]]; then
  chmod +x "${python_cli}"
fi

if [[ $# -ge 3 ]]; then
  outputDir=$2
  shift 2
  exec "${python_cli}" reco "${configFile}" "$@" --output "${outputDir}"
fi

if [[ $# -eq 2 ]]; then
  outputDir=$2
  exec "${python_cli}" reco "${configFile}" --output "${outputDir}" --stdin
fi

exec "${python_cli}" reco "${configFile}" --stdin
