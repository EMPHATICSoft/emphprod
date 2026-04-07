#!/usr/bin/env python3
"""Submit EMPHATIC ART jobs to the grid.

This CLI has two modes:
- ``gen``: submit generation jobs (no input ROOT file list).
- ``reco``: submit reconstruction jobs (explicit input list or stdin).

The high-level flow in both modes is:
1. Validate arguments and required local tools.
2. Create output directory and tarball payload.
3. Build a worker-node wrapper script.
4. Assemble ``jobsub_submit`` arguments and run (or print in dry-run).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Sequence

from submit_emph_art_core import (
    SubmissionError,
    WrapperContext,
    basic_jobsub_args,
    command_to_string,
    convert_pnfs_to_xrootd,
    ensure_command_available,
    ensure_output_dir,
    info,
    make_tarball,
    render_wrapper_prologue,
    run_command,
    warn,
    write_wrapper_script,
)


def default_code_dir() -> Path:
    """Return the default top-level code directory to tar for worker payloads."""
    # script path is emphprod/emphgridutils/bin/submit_emph_art.py
    # the repository root payload directory is three levels above this script
    return Path(__file__).resolve().parents[3]


def print_env(args: argparse.Namespace) -> None:
    """Print a focused environment summary useful for submission debugging."""
    keys = [
        "USER",
        "PATH",
        "INPUT_TAR_DIR_LOCAL",
        "CONDOR_DIR_INPUT",
        "CONDOR_DIR_ROOT_OUTPUT",
    ]
    print("=== Environment Summary ===")
    print(f"CODE_DIR={args.code_dir}")
    for key in keys:
        print(f"{key}={os.environ.get(key, '<unset>')}")


def normalize_debug_modes(args: argparse.Namespace) -> None:
    """Normalize convenience flags into their canonical debug behavior."""
    if args.test:
        info("--test requested, enabling dry-run mode")
        args.dry_run = True
        args.print_jobsub = True


def validate_common_inputs(args: argparse.Namespace) -> None:
    """Validate shared prerequisites used by both submission modes."""
    if not args.code_dir.exists():
        raise SubmissionError(f"Code directory does not exist: {args.code_dir}")
    if not args.code_dir.is_dir():
        raise SubmissionError(f"Code directory is not a directory: {args.code_dir}")
    if not args.user:
        raise SubmissionError("Grid user is undefined. Set USER or pass --user.")

    for command in ("bash", "tar", "jobsub_submit"):
        ensure_command_available(command)


def validate_generator_inputs(args: argparse.Namespace) -> None:
    """Validate generator-specific input arguments."""
    if not args.template.exists():
        raise SubmissionError(f"Template config not found: {args.template}")
    if not args.generator.exists():
        raise SubmissionError(f"Generator script not found: {args.generator}")
    if args.njobs < 1:
        raise SubmissionError(f"njobs must be >= 1, got {args.njobs}")


def validate_reconstruction_inputs(args: argparse.Namespace, inputs: Sequence[str]) -> None:
    """Validate reconstruction-specific arguments after stdin/CLI merge."""
    if not args.config.exists():
        raise SubmissionError(f"Config file not found: {args.config}")
    if not inputs:
        raise SubmissionError("At least one input ROOT file is required for reconstruction")


def build_generator_jobsub_command(args: argparse.Namespace, host_out_dir: Path, wrapper_path: Path) -> list[str]:
    """Build the full ``jobsub_submit`` argv for generator mode."""
    return [
        "jobsub_submit",
        "-N",
        str(args.njobs),
        "-f",
        f"dropbox://{args.generator.resolve()}",
        "-f",
        f"dropbox://{args.template.resolve()}",
        *basic_jobsub_args(host_out_dir),
        f"file://{wrapper_path}",
    ]


def build_reconstruction_jobsub_command(
    args: argparse.Namespace,
    host_out_dir: Path,
    wrapper_path: Path,
    file_list: Path,
    n_jobs: int,
) -> list[str]:
    """Build the full ``jobsub_submit`` argv for reconstruction mode."""
    return [
        "jobsub_submit",
        "-N",
        str(n_jobs),
        "-f",
        f"dropbox://{args.config.resolve()}",
        "-f",
        f"dropbox://{file_list}",
        *basic_jobsub_args(host_out_dir),
        f"file://{wrapper_path}",
    ]


def submit_generator(args: argparse.Namespace) -> None:
    """Run the generator submission workflow."""
    validate_common_inputs(args)
    validate_generator_inputs(args)

    host_out_dir = args.output.resolve()
    code_dir = args.code_dir.resolve()

    info(f"Preparing generator submission to {host_out_dir}")
    ensure_output_dir(host_out_dir, dry_run=args.dry_run)
    make_tarball(code_dir, host_out_dir, user=args.user, dry_run=args.dry_run)

    wrapper_path = Path(args.wrapper).resolve()
    prologue = render_wrapper_prologue(WrapperContext(code_dir_name=code_dir.name))
    # Worker-node actions after setup: render fcl then run art.
    body = [
        f"bash ${{CONDOR_DIR_INPUT}}/{args.generator.name} ${{CONDOR_DIR_INPUT}}/{args.template.name} > config_${{PROCESS}}.fcl || exit 2",
        "echo \"***** finished generating template config file *****\"",
        f"art -c config_${{PROCESS}}.fcl -o {args.outfile} || exit 3",
        "echo \"***** finished ART job *****\"",
    ]
    write_wrapper_script(wrapper_path, prologue, body)

    cmd = build_generator_jobsub_command(args, host_out_dir, wrapper_path)
    if args.print_jobsub:
        print(command_to_string(cmd))
    run_command(cmd, dry_run=args.dry_run, print_cmd=not args.print_jobsub)


def submit_reconstruction(args: argparse.Namespace) -> None:
    """Run the reconstruction submission workflow."""
    validate_common_inputs(args)

    # Combine explicit CLI inputs with optional stdin list.
    input_values = list(args.inputs)
    if args.stdin:
        input_values.extend(
            line.strip() for line in sys.stdin if line.strip()
        )

    # Convert local pnfs paths to xrootd so worker nodes can read them.
    inputs = [convert_pnfs_to_xrootd(item) for item in input_values]
    validate_reconstruction_inputs(args, inputs)

    host_out_dir = args.output.resolve()
    code_dir = args.code_dir.resolve()

    info(f"Preparing reconstruction submission to {host_out_dir}")
    ensure_output_dir(host_out_dir, dry_run=args.dry_run)
    make_tarball(code_dir, host_out_dir, user=args.user, dry_run=args.dry_run)

    file_list = Path(args.input_list).resolve()
    if not args.dry_run:
        file_list.write_text("\n".join(inputs) + "\n")

    wrapper_path = Path(args.wrapper).resolve()
    prologue = render_wrapper_prologue(WrapperContext(code_dir_name=code_dir.name))
    # Worker-node actions after setup: pick job-specific input then run art.
    body = [
        f"INPUT_FILE=$(head -n $((PROCESS+1)) ${{CONDOR_DIR_INPUT}}/{file_list.name} | tail -n -1) || exit 2",
        "echo \"***** finished finding input file *****\"",
        f"art -c {args.config.name} -o {args.outfile} ${{INPUT_FILE}} || exit 3",
        "echo \"***** finished ART job *****\"",
    ]
    write_wrapper_script(wrapper_path, prologue, body)

    cmd = build_reconstruction_jobsub_command(args, host_out_dir, wrapper_path, file_list, len(inputs))
    if args.print_jobsub:
        print(command_to_string(cmd))
    run_command(cmd, dry_run=args.dry_run, print_cmd=not args.print_jobsub)


def add_common_groups(parser: argparse.ArgumentParser) -> None:
    """Attach environment/debug groups shared by both subcommands."""
    environment_args = parser.add_argument_group(
        "Environment options", "Configure local code payload and identity."
    )
    environment_args.add_argument("--code-dir", dest="code_dir", type=Path, default=default_code_dir())
    environment_args.add_argument("--user", default=os.environ.get("USER"))

    debugging_args = parser.add_argument_group(
        "Debugging options", "Print extra diagnostics and avoid submission when requested."
    )
    debugging_args.add_argument("--dry-run", action="store_true", help="Build artifacts and print commands, but do not submit")
    debugging_args.add_argument(
        "--print-jobsub",
        "--print_jobsub",
        dest="print_jobsub",
        action="store_true",
        help="Print full jobsub command",
    )
    debugging_args.add_argument(
        "--print-env",
        "--show-env",
        dest="print_env",
        action="store_true",
        help="Print selected environment values before submission",
    )
    debugging_args.add_argument("--test", action="store_true", help="Alias for --dry-run with --print-jobsub")


def build_parser() -> argparse.ArgumentParser:
    """Build top-level CLI parser and subcommands."""
    parser = argparse.ArgumentParser(description="EMPHATIC grid submission utility")

    subparsers = parser.add_subparsers(dest="mode", required=True)

    gen = subparsers.add_parser("gen", help="Submit generation jobs")
    add_common_groups(gen)
    gen_required = gen.add_argument_group("Required arguments")
    gen_required.add_argument("template", type=Path)
    gen_required.add_argument("generator", type=Path)
    gen_required.add_argument("njobs", type=int)

    gen_job = gen.add_argument_group("Job control options")
    gen_job.add_argument(
        "--output",
        type=Path,
        default=Path(f"/pnfs/emphatic/persistent/users/{os.environ.get('USER', 'unknown')}/testSimulation"),
    )
    gen_job.add_argument("--outfile", default="testSimulation.root")
    gen_job.add_argument("--wrapper", default="basicSimulation.sh")
    gen.set_defaults(handler=submit_generator)

    reco = subparsers.add_parser("reco", help="Submit reconstruction jobs")
    add_common_groups(reco)
    reco_required = reco.add_argument_group("Required arguments")
    reco_required.add_argument("config", type=Path)
    reco_required.add_argument("inputs", nargs="*", help="Input ROOT files")

    reco_support = reco.add_argument_group("Support options")
    reco_support.add_argument(
        "--stdin",
        action="store_true",
        help="Read input file paths from stdin (one per line)",
    )

    reco_job = reco.add_argument_group("Job control options")
    reco_job.add_argument(
        "--output",
        type=Path,
        default=Path(f"/pnfs/emphatic/persistent/users/{os.environ.get('USER', 'unknown')}/testReconstruction"),
    )
    reco_job.add_argument("--outfile", default="testReconstruction.root")
    reco_job.add_argument("--wrapper", default="basicReconstruction.sh")
    reco_job.add_argument("--input-list", default="fileList.txt", help="Name of generated input list file sent with the job")
    reco.set_defaults(handler=submit_reconstruction)

    return parser


def main() -> int:
    """CLI entrypoint returning process-style exit code."""
    parser = build_parser()
    args = parser.parse_args()
    normalize_debug_modes(args)

    if args.print_env:
        print_env(args)
    if args.mode == "reco" and not args.stdin and not args.inputs:
        warn("No reconstruction inputs passed; use --stdin or provide file paths")

    try:
        args.handler(args)
    except SubmissionError as exc:
        print(f"ERROR: {exc}")
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
