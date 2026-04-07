# submit_emph_art.py Quick Guide

## Purpose

`submit_emph_art.py` submits EMPHATIC ART jobs to the grid in two modes:

- `gen`: generation workflow
- `reco`: reconstruction workflow

The script prepares a tarball payload, creates a robust worker wrapper, and runs `jobsub_submit`.

## Common Pattern

1. Validate local inputs and required commands.
2. Create output directory in `/pnfs/emphatic/persistent/...`.
3. Tar the chosen code directory and copy tarball to output area.
4. Generate worker wrapper script.
5. Submit to grid (or print only in dry-run/test mode).

## Basic Commands

Generator mode:

```bash
emphgridutils/bin/submit_emph_art.py gen \
  emphgridutils/bin/g4gen_template.fcl \
  emphgridutils/bin/generateMCJob.sh \
  20 \
  --output /pnfs/emphatic/persistent/users/$USER/prod6/testSimulation
```

Reconstruction mode with explicit inputs:

```bash
emphgridutils/bin/submit_emph_art.py reco \
  emphproduction/scripts/g4gen_prod6.01.job.fcl \
  /pnfs/emphatic/persistent/users/$USER/prod6/input/subrun_0001.root \
  /pnfs/emphatic/persistent/users/$USER/prod6/input/subrun_0002.root \
  --output /pnfs/emphatic/persistent/users/$USER/prod6/testReconstruction
```

Reconstruction mode reading inputs from stdin:

```bash
cat filelist.txt | emphgridutils/bin/submit_emph_art.py reco emphproduction/scripts/g4gen_prod6.01.job.fcl --stdin
```

## Most Useful Options

Shared options:

- `--code-dir PATH`: top-level directory to tar and ship (default is repo root)
- `--user USERNAME`: grid username override
- `--dry-run`: do not submit, only prepare/print
- `--print-jobsub` or `--print_jobsub`: print full command argv
- `--print-env` (alias: `--show-env`): print selected environment values before submit
- `--test`: shortcut for `--dry-run --print-jobsub`

Generator options:

- `--output PATH`: output directory (must be under `/pnfs/emphatic/persistent`)
- `--outfile NAME`: art output filename
- `--wrapper NAME`: generated worker wrapper filename

Reconstruction options:

- `--stdin`: read additional input file paths from stdin
- `--input-list NAME`: generated input list filename used by worker jobs
- `--output PATH`, `--outfile NAME`, `--wrapper NAME`

## Notes

- Use `--dry-run --print-jobsub` first when trying a new command. This lets you confirm what would be submitted before sending real jobs.
- If setup fails on a worker node, the generated wrapper prints clear diagnostics (missing files, missing environment variables, and whether `art` is available).
- Prefer calling `submit_emph_art.py` directly.
- `submitGenerator.sh` and `submitReconstruction.sh` still work for now, but they are temporary compatibility wrappers and will be removed later.
