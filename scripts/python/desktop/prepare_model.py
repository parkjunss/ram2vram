"""Prepare the selected original Qwen3.8 pack using the pinned Strata CLI."""
import argparse
import subprocess
import sys
from runtime import ROOT, SOURCE, STATE, environment


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--plan", action="store_true")
    mode.add_argument("--stop", action="store_true", help="Stop only the preparation profile")
    args = parser.parse_args()
    if args.stop:
        return subprocess.call([sys.executable, "-X", "utf8", str(SOURCE / "strata.py"),
            "launch", "--stop", "--preset", "RAM2VRAM Qwen3.8 IQ2_XS"],
            cwd=SOURCE, env=environment())
    command = [sys.executable, "-X", "utf8", str(SOURCE / "strata.py"),
               "launch", "--family", "qwen", "--model", "IQ2_XS",
               "--data-dir", str(ROOT / "models" / "qwen38"),
               "--context", "32k", "--parallel", "1", "--vision", "off",
               "--port", "8082", "--access", "local", "--set", "pcie_frac=1",
               "--save-preset", "RAM2VRAM Qwen3.8 IQ2_XS"]
    command += ["--plan", "--output", "json"] if args.plan else ["--yes", "--no-tui"]
    if not args.plan:
        STATE.mkdir(parents=True, exist_ok=True)
    return subprocess.call(command, cwd=SOURCE, env=environment())


if __name__ == "__main__":
    raise SystemExit(main())
