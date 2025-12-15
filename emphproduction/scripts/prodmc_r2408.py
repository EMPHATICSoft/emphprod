#!/usr/bin/env python3

import argparse
import subprocess
from pathlib import Path
from datetime import datetime
# import smtplib
# from email.message import EmailMessage
import sys
import os

########################
# CLI
########################
def parse_args():
    p = argparse.ArgumentParser("ART subrun driver")
    p.add_argument("--run", type=int, required=True)
    p.add_argument("--start-subrun", type=int, default=1)
    p.add_argument("--end-subrun", type=int, required=True)
    p.add_argument("-n", "--events", type=int, default=10000)
    p.add_argument("--gen-fcl", type=Path, default=Path("g4gen_job.fcl"))
    p.add_argument("--reco-fcl", type=Path, default=Path("prod_reco_caf_job.fcl"))
    p.add_argument("--logdir", type=Path, default=Path("logs"))
    p.add_argument("--tmpdir", type=Path, default=Path("tmp_fcl"))
    p.add_argument("--outdir", type=Path, default=Path("."), help="Output directory for ROOT files (default: current directory)")
    # p.add_argument("--email")
    # p.add_argument("--smtp-server", default="localhost")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--workdir", type=Path, help="Working directory to run in (default: current directory)")
    return p.parse_args()

# Stray text files produced by ART / artdaq
STRAY_FILE_PATTERNS = [
    "G4EMPH*.txt", "*hist.root"
]

########################
# Utilities
########################
def run(cmd, logfile, dry_run=False):
    print(cmd)
    if dry_run:
        return

    with open(logfile, "w") as log:
        subprocess.run(
            cmd,
            shell=True,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=True,
        )

def send_email(args, subject, body):
    if not args.email:
        return

    msg = EmailMessage()
    msg["From"] = args.email
    msg["To"] = args.email
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP(args.smtp_server) as s:
        s.send_message(msg)

def cleanup_new_files(patterns, dry_run=False):
    stray_files = []
    for pattern in patterns:
        stray_files.extend(Path(".").glob(pattern))
    
    for path in stray_files:
        print(f"Cleaning up {path}")
        if not dry_run:
            path.unlink()


########################
# Subrun logic
########################
def process_subrun(args, subrun):
    subrun_padded = f"{subrun:04d}"

    # Define expected output files
    # TODO: Remove hard-coding 
    gen_out = args.outdir / f"emphmc_r{args.run}_s{subrun_padded}.v6.01.00.artdaq.root"
    gen_out_unpadded = args.outdir / f"emphmc_r{args.run}_s{subrun}.v6.01.00.artdaq.root"
    reco_out = args.outdir / f"emphmc_r{args.run}_s{subrun_padded}.v6.01.00.artdaq.caf.root"
    hist_file = args.outdir / f"emphmc_r{args.run}_s{subrun}.v6.01.00.artdaq_reco_cafmaker_hist.root"

    # Skip if reco output already exists
    if reco_out.exists():
        print(f"Skipping subrun {subrun_padded} (already processed)")
        return

    print(f"\n=== Subrun {subrun_padded} started at {datetime.now()} ===")

    # Check if generation output already exists
    local_gen_out = Path(f"emphmc_r{args.run}_s{subrun_padded}.artdaq.root")
    final_gen_out = gen_out if args.outdir != Path(".") else local_gen_out
    
    if gen_out.exists():
        print(f"Generation output already exists: {gen_out}")
        final_gen_out = gen_out
    elif local_gen_out.exists() and args.outdir == Path("."):
        print(f"Generation output already exists: {local_gen_out}")
        final_gen_out = local_gen_out
    else:
        # Need to run generation step
        print("Running generation step...")
        
        # Prepare temporary generation FCL
        tmp_fcl = args.tmpdir / f"g4gen_r{args.run}_s{subrun_padded}.fcl"
        tmp_fcl.write_text(
            args.gen_fcl.read_text() +
            f"\nsource.firstSubRun: {subrun}\n"
        )

        # Generation + Digitization
        run(
            f"art -c {tmp_fcl} -n {args.events}",
            args.logdir / f"g4gen_r{args.run}_s{subrun_padded}.log",
            args.dry_run
        )

        # Handle output files - ART creates them as emphmc_r{run}_s{subrun}.v6.01.00.artdaq.root
        if not args.dry_run:
            # ART creates file with unpadded subrun number
            art_gen_out = Path(f"emphmc_r{args.run}_s{subrun}.v6.01.00.artdaq.root")
            
            if art_gen_out.exists():
                print(f"Found generation output: {art_gen_out}")
                
                if args.outdir != Path("."):
                    art_gen_out.rename(gen_out)
                    final_gen_out = gen_out
                else:
                    # If staying in current directory, rename to padded version for consistency
                    art_gen_out.rename(local_gen_out)
                    final_gen_out = local_gen_out
            else:
                # List all .root files to help debug
                all_root_files = list(Path(".").glob("*.root"))
                print(f"Expected generation output not found: {art_gen_out}")
                print(f"All .root files: {all_root_files}")
                raise RuntimeError(f"Missing generation output for subrun {subrun_padded}")

        # Check generation output exists (in final location)  
        if not args.dry_run and not final_gen_out.exists():
            raise RuntimeError(f"Missing generation output for subrun {subrun_padded}")

    # Cleanup stray text files
    cleanup_new_files(STRAY_FILE_PATTERNS, args.dry_run)

    # Reco / CAF - use the final location of gen_out
    final_gen_out = gen_out if args.outdir != Path(".") else local_gen_out
    run(
        f"art -c {args.reco_fcl} {final_gen_out}",
        args.logdir / f"reco_r{args.run}_s{subrun_padded}.log",
        args.dry_run
    )

    # Move reco output to output directory if needed
    local_reco_out = Path(f"emphmc_r{args.run}_s{subrun_padded}.v6.01.00.artdaq.caf.root")
    if not args.dry_run and local_reco_out.exists() and args.outdir != Path("."):
        local_reco_out.rename(reco_out)

    # Check reco output exists (in final location)
    final_reco_out = reco_out if args.outdir != Path(".") else local_reco_out
    if not final_reco_out.exists() and not args.dry_run:
        raise RuntimeError(f"Missing reco output for subrun {subrun_padded}")

    # Cleanup unwanted histogram file
    cleanup_new_files(STRAY_FILE_PATTERNS, args.dry_run)

    print(f"=== Subrun {subrun_padded} finished ===")
    print(f"Generation output: {gen_out}")
    print(f"Reco output:       {reco_out}")

########################
# Main
########################
def main():
    args = parse_args()

    # Change to working directory if specified
    if args.workdir:
        original_dir = Path.cwd()
        print(f"Changing to working directory: {args.workdir}")
        if not args.dry_run:
            os.chdir(args.workdir)

    args.logdir.mkdir(exist_ok=True)
    args.tmpdir.mkdir(exist_ok=True)
    args.outdir.mkdir(exist_ok=True)

    start = datetime.now()

    for subrun in range(args.start_subrun, args.end_subrun + 1):
        process_subrun(args, subrun)

    # send_email(
    #     args,
    #     f"ART subruns COMPLETE (r{args.run})",
    #     f"""Run {args.run} completed successfully.
    #         Subruns: {args.start_subrun}–{args.end_subrun}
    #         Start:   {start}
    #         End:     {datetime.now()}
    #         Dry-run: {args.dry_run}
    #         Generation Output: emphmc_r{args.run}_s{{subrun}}.artdaq.root
    #         Reco Output:       reco_r{args.run}_s{{subrun}}.artdaq.v6.01.00_caf.root
    #     """
    # )
    print(f"Run {args.run} completed successfully at {datetime.now()}")

########################
# Entry point
########################
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # One clean failure point
        print(f"ART job FAILED at {datetime.now()}: {e}")
        # args = parse_args()
        # send_email(
        #     args,
        #     f"ART job FAILED (r{args.run})",
        #     f"Failure at {datetime.now()}:\n\n{e}"
        # )
        raise
