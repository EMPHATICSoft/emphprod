#!/usr/bin/env python3
"""Core helpers for EMPHATIC grid submissions.

This module contains reusable functionality used by ``submit_emph_art.py``:
- payload/output preparation
- worker wrapper rendering
- command construction/execution helpers
- simple logging and validation primitives
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

OUT_DIR_TAG = "ROOT_OUTPUT"


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


def render_worker_setup(ctx: WrapperContext) -> str:
    """Render worker-node shell setup from a checked-in template file."""
    template_path = Path(__file__).with_name("worker_setup.sh.template")
    if not template_path.is_file():
        raise SubmissionError(f"Missing worker node setup template: {template_path}")
    content = template_path.read_text()
    return content.replace("__OUTPUT_TAG__", ctx.output_tag)


def write_wrapper_script(path: Path, prologue: str, body_lines: Sequence[str]) -> None:
    """Write executable worker wrapper script from prologue and mode-specific body."""
    content = prologue + "\n" + "\n".join(body_lines) + "\n"
    path.write_text(content)
    path.chmod(0o755)


def basic_jobsub_args(
    host_out_dir: Path,
    code_dir: Path,
    build_dir: Path,
    test_events: int | None = None,
) -> list[str]:
    """Return standard EMPHATIC ``jobsub_submit`` arguments shared by all modes."""
    args = [
        "-d",
        OUT_DIR_TAG,
        str(host_out_dir),
        "-l",
        "+SingularityImage=\"/cvmfs/singularity.opensciencegrid.org/fermilab/fnal-wn-sl7:latest\"",
        "--tar_file_name",
        f"tardir://{code_dir}",
        "--tar_file_name",
        f"tardir://{build_dir}",
        "--use-cvmfs-dropbox",
    ]
    if test_events is not None:
        args.extend(["-e", f"EMPH_TEST_EVENTS={test_events}"])
    return args


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
