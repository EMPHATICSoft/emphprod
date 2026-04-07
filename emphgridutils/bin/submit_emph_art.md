# submit_emph_art.py Quick Guide

## Purpose

`submit_emph_art.py` submits EMPHATIC ART jobs to the grid in two modes:

- `gen`: generation workflow
- `reco`: reconstruction workflow

The script creates one payload tarball (code + build, excluding `.git`), submits with `jobsub_submit --tar_file_name dropbox://... --use-cvmfs-dropbox`, generates a worker wrapper, and runs `jobsub_submit`.

## Common Pattern

1. Validate local inputs and required commands.
2. Create output directory in `/pnfs/emphatic/persistent/...`.
3. Create or reuse a single payload tarball containing both code and build directories.
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

- `--code-dir PATH`: source payload directory used to build the payload tarball; if omitted, the script reads `$EMPH_CODE_DIR`; this path must contain `setup/setup_emphatic.sh` (or `emphaticsoft/setup/setup_emphatic.sh`)
- `--build-dir PATH`: build payload directory used to build the payload tarball; if omitted, the script reads `$EMPH_BUILD_DIR`
- `--payload-tarball PATH`: reuse an existing payload tarball instead of creating one from `--code-dir`/`--build-dir`
- `--user USERNAME`: grid username override
- `--dry-run`: do not submit, only prepare/print
- `--print-jobsub` or `--print_jobsub`: print full command argv
- `--print-env` (alias: `--show-env`): print selected environment values before submit
- `--test`: shortcut for `--dry-run --print-jobsub`
- `--smoke-test`: do one real submission (`-N 1`) and force ART to run only 3 events

Generator options:

- `--output PATH`: output directory (must be under `/pnfs/emphatic/persistent`)
- `--outfile NAME`: art output filename
- `--wrapper NAME`: generated worker wrapper filename

Reconstruction options:

- `--stdin`: read additional input file paths from stdin
- `--input-list NAME`: generated input list filename used by worker jobs; it is written into the local staging directory
- `--output PATH`, `--outfile NAME`, `--wrapper NAME`

## Notes

- If you do not pass `--payload-tarball`, either pass `--code-dir` and `--build-dir` or define both environment variables before running:

```bash
export EMPH_CODE_DIR=/path/to/emphaticsoft
export EMPH_BUILD_DIR=/path/to/build
```

- Worker setup order is:
  1. `source setup_emphatic.sh`
  2. `source setup_for_grid.sh`
  3. `source setup_emphaticsoft` from the build area (if present)

  This avoids using `setup_for_development` on read-only CVMFS payloads.

- Use `--dry-run --print-jobsub` first when trying a new command. This lets you confirm what would be submitted before sending real jobs.
- In dry-run output, confirm payload arguments are present: `--tar_file_name dropbox://...` and `--use-cvmfs-dropbox`.
- `--smoke-test` injects `EMPH_TEST_EVENTS=3` into the worker environment, and the wrapper translates that to `art -n 3 ...`.
- Generated wrapper scripts and reconstruction input lists are written into a dedicated local staging directory under `staging_dir/`.
- At the end of preparation/submission, the script prints that staging path so you can remove it when you are done.
- If setup fails on a worker node, the generated wrapper prints clear diagnostics (missing files, missing environment variables, and whether `art` is available).
- If generation fails with `phase1c_Unknown.gdml`, geometry is being selected from RunHistory with an unresolved target for that run. Use a run with valid RunHistory DB metadata or override `GeometryService` in the FHiCL to use explicit `GDMLFile`.
- Prefer calling `submit_emph_art.py` directly.
- `submitGenerator.sh` and `submitReconstruction.sh` still work for now, but they are temporary compatibility wrappers and will be removed later.
