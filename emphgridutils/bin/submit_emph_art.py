#!/usr/bin/env python3
"""Submit EMPHATIC ART jobs to the grid.

This CLI has two modes:
- ``gen``: submit generation jobs (no input ROOT file list).
- ``reco``: submit reconstruction jobs (explicit input list or stdin).

The high-level flow in both modes is:
1. Validate arguments and required local tools.
2. Create output directory and define payload transfers.
3. Build a worker-node wrapper script.
4. Assemble ``jobsub_submit`` arguments and run (or print in dry-run).
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path
from typing import Sequence

from submit_emph_art_core import (
    SubmissionError,
    WrapperContext,
    basic_jobsub_args,
    command_to_string,
    convert_pnfs_to_xrootd,
    create_payload_tarball,
    ensure_command_available,
    ensure_output_dir,
    info,
    render_worker_setup,
    run_command,
    warn,
    write_wrapper_script,
)

CODE_DIR_ENV = "EMPH_CODE_DIR"
BUILD_DIR_ENV = "EMPH_BUILD_DIR"
STAGING_ROOT = "staging_dir"


class HelpFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawTextHelpFormatter):
    """Show defaults while preserving manual line breaks in help text."""


def print_env(args: argparse.Namespace) -> None:
    """Print a focused environment summary useful for submission debugging."""
    keys = [
        "USER",
        "PATH",
        CODE_DIR_ENV,
        BUILD_DIR_ENV,
        "INPUT_TAR_DIR_LOCAL",
        "CONDOR_DIR_INPUT",
        "CONDOR_DIR_ROOT_OUTPUT",
    ]
    print("=== Environment Summary ===")
    print(f"CODE_DIR={args.code_dir}")
    print(f"BUILD_DIR={args.build_dir}")
    print(f"PAYLOAD_TARBALL={args.payload_tarball}")
    for key in keys:
        print(f"{key}={os.environ.get(key, '<unset>')}")


def create_local_staging_dir(mode: str) -> Path:
    """Create a dedicated local staging directory for generated submission artifacts."""
    staging_root = Path.cwd() / STAGING_ROOT
    staging_root.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=f"{mode}_", dir=staging_root))


def stage_local_file(staging_dir: Path, requested_name: str) -> Path:
    """Place a generated local artifact into the staging directory using only its basename."""
    return staging_dir / Path(requested_name).name


def print_staging_dir(staging_dir: Path) -> None:
    """Tell the user where generated local artifacts were written."""
    info(f"Local staging directory: {staging_dir}")
    info("Remove that directory when you no longer need the generated wrapper/input-list/payload-tarball files")


def consolidate_debug_modes(args: argparse.Namespace) -> None:
    """Apply shorthand debug flags.

    Rule:
    - `--test` means "show me exactly what would be submitted, but do not submit".
    - `--print-env` prints diagnostics without submission.
    """
    if args.print_env:
        args.dry_run = True

    if not args.test:
        if args.smoke_test:
            args.print_jobsub = True
            info("Smoke-test mode enabled: real submit with one job and 3 events")
        return

    # `--test` is a convenience alias for safe inspection mode.
    args.dry_run = True
    args.print_jobsub = True
    info("Test mode enabled: using --dry-run and --print-jobsub")


def validate_common_inputs(args: argparse.Namespace) -> None:
    """Validate shared prerequisites used by both submission modes."""
    if args.payload_tarball is not None:
        args.payload_tarball = args.payload_tarball.resolve()
        if not args.payload_tarball.exists():
            raise SubmissionError(f"Payload tarball does not exist: {args.payload_tarball}")
        if not args.payload_tarball.is_file():
            raise SubmissionError(f"Payload tarball is not a file: {args.payload_tarball}")
    else:
        args.code_dir = args.code_dir.resolve()
        args.build_dir = args.build_dir.resolve()

        if not args.code_dir.exists():
            raise SubmissionError(f"Code directory does not exist: {args.code_dir}")
        if not args.code_dir.is_dir():
            raise SubmissionError(f"Code directory is not a directory: {args.code_dir}")
        setup_candidate_a = args.code_dir / "setup" / "setup_emphatic.sh"
        setup_candidate_b = args.code_dir / "emphaticsoft" / "setup" / "setup_emphatic.sh"
        if not setup_candidate_a.is_file() and not setup_candidate_b.is_file():
            raise SubmissionError(
                "--code-dir must contain setup/setup_emphatic.sh (or emphaticsoft/setup/setup_emphatic.sh)"
            )

        if not args.build_dir.exists():
            raise SubmissionError(f"Build directory does not exist: {args.build_dir}")
        if not args.build_dir.is_dir():
            raise SubmissionError(f"Build directory is not a directory: {args.build_dir}")

    if not args.user:
        raise SubmissionError("Grid user is undefined. Set USER or pass --user.")

    for command in ("bash", "jobsub_submit"):
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


def resolve_payload_tarball(args: argparse.Namespace, staging_dir: Path) -> Path:
    """Return payload tarball path, creating one when not supplied explicitly."""
    if args.payload_tarball is not None:
        info(f"Using existing payload tarball: {args.payload_tarball}")
        return args.payload_tarball

    payload_tarball = create_payload_tarball(staging_dir, args.code_dir, args.build_dir)
    info(f"Created payload tarball: {payload_tarball}")
    return payload_tarball


def build_generator_jobsub_command(
    args: argparse.Namespace,
    host_out_dir: Path,
    wrapper_path: Path,
    payload_tarball: Path,
) -> list[str]:
    """Build the full ``jobsub_submit`` argv for generator mode."""
    n_jobs = 1 if args.smoke_test else args.njobs
    test_events = 3 if args.smoke_test else None
    return [
        "jobsub_submit",
        "-N",
        str(n_jobs),
        "-f",
        f"dropbox://{args.generator.resolve()}",
        "-f",
        f"dropbox://{args.template.resolve()}",
        *basic_jobsub_args(host_out_dir, payload_tarball, test_events=test_events),
        f"file://{wrapper_path}",
    ]


def build_reconstruction_jobsub_command(
    args: argparse.Namespace,
    host_out_dir: Path,
    wrapper_path: Path,
    file_list: Path,
    n_jobs: int,
    payload_tarball: Path,
) -> list[str]:
    """Build the full ``jobsub_submit`` argv for reconstruction mode."""
    effective_jobs = 1 if args.smoke_test else n_jobs
    test_events = 3 if args.smoke_test else None
    return [
        "jobsub_submit",
        "-N",
        str(effective_jobs),
        "-f",
        f"dropbox://{args.config.resolve()}",
        "-f",
        f"dropbox://{file_list}",
        *basic_jobsub_args(host_out_dir, payload_tarball, test_events=test_events),
        f"file://{wrapper_path}",
    ]


def submit_generator(args: argparse.Namespace) -> None:
    """Run the generator submission workflow."""
    validate_common_inputs(args)
    validate_generator_inputs(args)

    host_out_dir = args.output.resolve()
    info(f"Preparing generator submission to {host_out_dir}")
    ensure_output_dir(host_out_dir, dry_run=args.dry_run)

    staging_dir = create_local_staging_dir("gen")
    payload_tarball = resolve_payload_tarball(args, staging_dir)
    wrapper_path = stage_local_file(staging_dir, args.wrapper)
    prologue = render_worker_setup(WrapperContext())
    # Worker-node actions after setup: render fcl then run art.
    body = [
        "ART_EVENT_ARGS=()",
        "if [[ -n ${EMPH_TEST_EVENTS:-} ]]; then ART_EVENT_ARGS=(-n \"${EMPH_TEST_EVENTS}\"); fi",
        f"bash ${{CONDOR_DIR_INPUT}}/{args.generator.name} ${{CONDOR_DIR_INPUT}}/{args.template.name} > config_${{PROCESS}}.fcl || exit 2",
        "echo \"***** finished generating template config file *****\"",
        f"art ${{ART_EVENT_ARGS[@]}} -c config_${{PROCESS}}.fcl -o {args.outfile} || exit 3",
        "echo \"***** finished ART job *****\"",
    ]
    write_wrapper_script(wrapper_path, prologue, body)
    print_staging_dir(staging_dir)

    cmd = build_generator_jobsub_command(args, host_out_dir, wrapper_path, payload_tarball)
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
    info(f"Preparing reconstruction submission to {host_out_dir}")
    ensure_output_dir(host_out_dir, dry_run=args.dry_run)

    staging_dir = create_local_staging_dir("reco")
    payload_tarball = resolve_payload_tarball(args, staging_dir)
    file_list = stage_local_file(staging_dir, args.input_list)
    if not args.dry_run:
        file_list.write_text("\n".join(inputs) + "\n")

    wrapper_path = stage_local_file(staging_dir, args.wrapper)
    prologue = render_worker_setup(WrapperContext())
    # Worker-node actions after setup: pick job-specific input then run art.
    body = [
        "ART_EVENT_ARGS=()",
        "if [[ -n ${EMPH_TEST_EVENTS:-} ]]; then ART_EVENT_ARGS=(-n \"${EMPH_TEST_EVENTS}\"); fi",
        f"INPUT_FILE=$(head -n $((PROCESS+1)) ${{CONDOR_DIR_INPUT}}/{file_list.name} | tail -n -1) || exit 2",
        "echo \"***** finished finding input file *****\"",
        f"art ${{ART_EVENT_ARGS[@]}} -c {args.config.name} -o {args.outfile} ${{INPUT_FILE}} || exit 3",
        "echo \"***** finished ART job *****\"",
    ]
    write_wrapper_script(wrapper_path, prologue, body)
    print_staging_dir(staging_dir)

    cmd = build_reconstruction_jobsub_command(
        args,
        host_out_dir,
        wrapper_path,
        file_list,
        len(inputs),
        payload_tarball,
    )
    if args.print_jobsub:
        print(command_to_string(cmd))
    run_command(cmd, dry_run=args.dry_run, print_cmd=not args.print_jobsub)


def add_common_groups(parser: argparse.ArgumentParser) -> None:
    """Attach environment/debug groups shared by both subcommands."""
    environment_args = parser.add_argument_group(
        "Environment options", "Configure local code payload and identity."
    )
    environment_args.add_argument(
        "--code-dir",
        dest="code_dir",
        type=Path,
        default=None,
        help=(
            "Source tree included in the local payload tarball (with .git excluded). "
            f"If omitted, read from ${CODE_DIR_ENV}. Must contain "
            "setup/setup_emphatic.sh or emphaticsoft/setup/setup_emphatic.sh."
        ),
    )
    environment_args.add_argument(
        "--build-dir",
        dest="build_dir",
        type=Path,
        default=None,
        help=(
            "Build tree included in the local payload tarball (with .git excluded). "
            f"If omitted, read from ${BUILD_DIR_ENV}."
        ),
    )
    environment_args.add_argument(
        "--payload-tarball",
        dest="payload_tarball",
        type=Path,
        default=None,
        help=(
            "Use an existing payload tarball instead of creating one from --code-dir/--build-dir. "
            "When set, code/build directory options are ignored for payload creation."
        ),
    )
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
    debugging_args.add_argument(
        "--smoke-test",
        dest="smoke_test",
        action="store_true",
        help="Submit one real test job and force ART to run only 3 events",
    )


def build_common_parser() -> argparse.ArgumentParser:
    """Build a parent parser containing options shared by all subcommands."""
    parser = argparse.ArgumentParser(add_help=False, formatter_class=HelpFormatter)
    add_common_groups(parser)
    return parser


def build_parser() -> argparse.ArgumentParser:
    """Build top-level CLI parser and subcommands."""
    common_parser = build_common_parser()
    parser = argparse.ArgumentParser(
        description="EMPHATIC grid submission utility",
        parents=[common_parser],
        formatter_class=HelpFormatter,
        epilog=(
            "Environment defaults:\n"
            f"  --code-dir falls back to ${CODE_DIR_ENV}\n"
            f"  --build-dir falls back to ${BUILD_DIR_ENV}\n\n"
            "Run '<subcommand> --help' for mode-specific options."
        ),
    )

    subparsers = parser.add_subparsers(dest="mode", required=True)

    gen = subparsers.add_parser(
        "gen",
        parents=[common_parser],
        help="Submit generation jobs",
        description="Submit generator jobs that build per-process FHiCL and run art without an input ROOT list.",
        formatter_class=HelpFormatter,
    )
    gen_required = gen.add_argument_group("Required arguments")
    gen_required.add_argument(
        "template",
        type=Path,
        nargs="?",
        default=Path(__file__).parent / "g4gen_template.fcl",
        help="Template FHiCL file passed to the generator helper",
    )
    gen_required.add_argument(
        "generator",
        type=Path,
        help="Executable helper that writes a process-specific FHiCL to stdout",
    )
    gen_required.add_argument(
        "njobs",
        type=int,
        help="Number of grid jobs to submit in parallel",
    )

    gen_job = gen.add_argument_group("Job control options")
    gen_job.add_argument(
        "--output",
        type=Path,
        default=Path(f"/pnfs/emphatic/persistent/users/{os.environ.get('USER', 'unknown')}/testSimulation"),
        help="Output directory for grid job products; must not already exist",
    )
    gen_job.add_argument(
        "--outfile",
        default="testSimulation.root",
        help="ROOT filename written by art on the worker node",
    )
    gen_job.add_argument(
        "--wrapper",
        default="basicSimulation.sh",
        help="Wrapper filename written into the local staging directory",
    )
    gen.set_defaults(handler=submit_generator)

    reco = subparsers.add_parser(
        "reco",
        parents=[common_parser],
        help="Submit reconstruction jobs",
        description="Submit reconstruction jobs over explicit inputs or paths read from stdin.",
        formatter_class=HelpFormatter,
    )
    reco_required = reco.add_argument_group("Required arguments")
    reco_required.add_argument(
        "config",
        type=Path,
        help="FHiCL configuration file passed to art",
    )
    reco_required.add_argument(
        "inputs",
        nargs="*",
        help="Input ROOT files; omit these if using --stdin",
    )

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
        help="Output directory for grid job products; must not already exist",
    )
    reco_job.add_argument(
        "--outfile",
        default="testReconstruction.root",
        help="ROOT filename written by art on the worker node",
    )
    reco_job.add_argument(
        "--wrapper",
        default="basicReconstruction.sh",
        help="Wrapper filename written into the local staging directory",
    )
    reco_job.add_argument(
        "--input-list",
        default="fileList.txt",
        help="Input-list filename written into the local staging directory",
    )
    reco.set_defaults(handler=submit_reconstruction)

    return parser


def main() -> int:
    """CLI entrypoint returning process-style exit code."""
    parser = build_parser()
    args = parser.parse_args()
    if args.test and args.smoke_test:
        parser.error("Use only one of --test or --smoke-test")

    if args.payload_tarball is None:
        if args.code_dir is None:
            code_dir_env = os.environ.get(CODE_DIR_ENV)
            if not code_dir_env:
                parser.error(
                    f"Pass --payload-tarball, or pass --code-dir, or set {CODE_DIR_ENV}"
                )
            args.code_dir = Path(code_dir_env)

        if args.build_dir is None:
            build_dir_env = os.environ.get(BUILD_DIR_ENV)
            if not build_dir_env:
                parser.error(
                    f"Pass --payload-tarball, or pass --build-dir, or set {BUILD_DIR_ENV}"
                )
            args.build_dir = Path(build_dir_env)

    consolidate_debug_modes(args)

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
