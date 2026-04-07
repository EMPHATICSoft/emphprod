#!/usr/bin/env python3
"""Core helpers for EMPHATIC grid submissions.

This module contains reusable functionality used by ``submit_emph_art.py``:
- payload/output preparation
- worker wrapper rendering
- command construction/execution helpers
- simple logging and validation primitives
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tarfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

OUT_DIR_TAG = "ROOT_OUTPUT"
TARBALL_NAME = "myEmphaticsoft.tar.gz"


class SubmissionError(RuntimeError):
    """Raised for predictable submission configuration problems."""


def info(message: str) -> None:
    """Emit an informational log line."""
    print(f"INFO: {message}")


def warn(message: str) -> None:
    """Emit a warning log line."""
    print(f"WARNING: {message}")


@dataclass(frozen=True)
class WrapperContext:
    """Inputs required to render the worker-node wrapper prologue."""

    code_dir_name: str
    output_tag: str = OUT_DIR_TAG


def ensure_output_dir(host_out_dir: Path, dry_run: bool = False) -> None:
    """Validate and create output directory used by dropbox/job output.

    The output path is required to live under the experiment persistent pnfs area.
    """
    host_out_dir_str = str(host_out_dir)
    if "/pnfs/emphatic/persistent" not in host_out_dir_str:
        raise SubmissionError(
            "Output directory must be on /pnfs/emphatic/persistent, "
            f"but got: {host_out_dir_str}"
        )
    if host_out_dir.exists():
        raise SubmissionError(
            f"{host_out_dir_str} already exists. Delete it before submitting."
        )
    if not dry_run:
        host_out_dir.mkdir(parents=True)


def make_tarball(
    code_dir: Path,
    host_out_dir: Path,
    user: str | None = None,
    dry_run: bool = False,
) -> Path:
    """Create and copy the user payload tarball into the submission output area."""
    user_name = user or os.environ.get("USER")
    if not user_name:
        raise SubmissionError("USER environment variable is required to build safe scratch path")

    safe_scratch_dir = Path(f"/exp/emph/app/users/{user_name}")
    tarball_path = safe_scratch_dir / TARBALL_NAME

    if tarball_path.exists() and not dry_run:
        tarball_path.unlink()

    parent_dir = code_dir.parent
    root_name = code_dir.name

    if not dry_run:
        with tarfile.open(tarball_path, "w:gz") as tar:
            tar.add(parent_dir / root_name, arcname=root_name)

    dest = host_out_dir / TARBALL_NAME
    if not dry_run:
        shutil.copy2(tarball_path, dest)

    if not dry_run and not dest.exists():
        raise SubmissionError(f"Failed to copy tarball to {dest}")

    return dest


def render_wrapper_prologue(ctx: WrapperContext) -> str:
    """Render robust worker-node shell setup used before running art.

    The rendered script performs strict checks, environment setup, and early
    diagnostics so setup failures are obvious in grid logs.
    """
    out_tag = ctx.output_tag
    code_name = ctx.code_dir_name
    lines = [
        "#!/usr/bin/bash",
        "set -euo pipefail",
        "",
        "die() {",
        "  echo \"ERROR: $*\" >&2",
        "  exit 1",
        "}",
        "",
        "log() {",
        "  echo \"[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*\"",
        "}",
        "",
        "require_env() {",
        "  local var_name=$1",
        "  [[ -n ${!var_name:-} ]] || die \"Required environment variable is missing: ${var_name}\"",
        "}",
        "",
        "on_error() {",
        "  local rc=$?",
        "  echo \"ERROR: command failed at line $1 (exit code ${rc})\" >&2",
        "  echo \"PWD=$(pwd)\" >&2",
        "  echo \"PATH=${PATH}\" >&2",
        "  type -a art >&2 || true",
        "  exit ${rc}",
        "}",
        "trap 'on_error ${LINENO}' ERR",
        "",
        "require_env INPUT_TAR_DIR_LOCAL",
        f"require_env CONDOR_DIR_{out_tag}",
        "require_env CONDOR_DIR_INPUT",
        "require_env PROCESS",
        "",
        f"payload_dir=${{INPUT_TAR_DIR_LOCAL}}/{code_name}",
        "setup_emphatic=${payload_dir}/emphaticsoft/setup/setup_emphatic.sh",
        "setup_for_grid=${payload_dir}/emphaticsoft/setup/setup_for_grid.sh",
        "",
        "[[ -f ${setup_emphatic} ]] || die \"Missing setup script: ${setup_emphatic}\"",
        "[[ -f ${setup_for_grid} ]] || die \"Missing setup script: ${setup_for_grid}\"",
        "",
        "if [[ -d ${payload_dir}/opt/build ]]; then",
        "  build_dir=${payload_dir}/opt/build",
        "elif [[ -d ${payload_dir}/build ]]; then",
        "  build_dir=${payload_dir}/build",
        "else",
        "  die \"Could not find build directory under ${payload_dir} (checked opt/build and build)\"",
        "fi",
        "",
        "log \"Sourcing setup_emphatic.sh from ${setup_emphatic}\"",
        "source ${setup_emphatic}",
        "log \"Finished setup_emphatic.sh\"",
        "",
        "cd ${build_dir}",
        "log \"Changed directory to build area: ${build_dir}\"",
        "",
        "log \"Sourcing setup_for_grid.sh from ${setup_for_grid}\"",
        "source ${setup_for_grid}",
        "log \"Finished setup_for_grid.sh\"",
        "",
        "if [[ -f setup_emphaticsoft ]]; then",
        "  log \"Sourcing local setup_emphaticsoft from build area\"",
        "  source setup_emphaticsoft",
        "else",
        "  log \"setup_emphaticsoft not found in build area; skipping\"",
        "fi",
        "",
        "command -v art >/dev/null 2>&1 || die \"'art' not found after setup. Check setup_emphatic.sh/setup_for_grid.sh and payload build products.\"",
        "log \"art found at: $(command -v art)\"",
        "",
        f"cd ${{CONDOR_DIR_{out_tag}}}",
        "mkdir -p job_${PROCESS}",
        "cd job_${PROCESS}",
        "log \"Running in output directory: $(pwd)\"",
    ]
    return "\n".join(lines) + "\n"


def write_wrapper_script(path: Path, prologue: str, body_lines: Sequence[str]) -> None:
    """Write executable worker wrapper script from prologue and mode-specific body."""
    content = prologue + "\n" + "\n".join(body_lines) + "\n"
    path.write_text(content)
    path.chmod(0o755)


def basic_jobsub_args(host_out_dir: Path) -> list[str]:
    """Return standard EMPHATIC ``jobsub_submit`` arguments shared by all modes."""
    return [
        "-d",
        OUT_DIR_TAG,
        str(host_out_dir),
        "-l",
        "+SingularityImage=\"/cvmfs/singularity.opensciencegrid.org/fermilab/fnal-wn-sl7:latest\"",
        "--tar_file_name",
        f"dropbox://{host_out_dir}/{TARBALL_NAME}",
        "--use-cvmfs-dropbox",
    ]


def ensure_command_available(command: str) -> None:
    """Raise ``SubmissionError`` if command is not found on current PATH."""
    if shutil.which(command) is None:
        raise SubmissionError(f"Required command not found in PATH: {command}")


def command_to_string(cmd: Sequence[str]) -> str:
    """Return human-readable argv representation for debug printing."""
    return "argv=" + repr(list(cmd))


def run_command(cmd: Sequence[str], dry_run: bool = False, print_cmd: bool = True) -> None:
    """Run a command safely without shell evaluation.

    Commands are always executed with ``shell=False`` and list-style argv to
    avoid shell injection behavior.
    """
    if print_cmd:
        print(command_to_string(cmd))
    if dry_run:
        return
    subprocess.run(cmd, check=True, shell=False)


def convert_pnfs_to_xrootd(path: str) -> str:
    """Translate pnfs ROOT paths to xrootd URIs for worker-node readability."""
    prefix = "/pnfs/emphatic/"
    if path.startswith(prefix) and path.endswith(".root"):
        suffix = path[len(prefix):]
        return f"root://fndca1.fnal.gov:1094///pnfs/fnal.gov/usr/emphatic/{suffix}"
    return path
