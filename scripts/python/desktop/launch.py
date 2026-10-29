"""Launch the compiled native desktop with its own state and workspace."""
import subprocess
from runtime import ROOT, STATE, environment


def main():
    binary = ROOT / "desktop/dist/RAM2VRAM.exe"
    if not binary.is_file():
        raise SystemExit("Desktop build is missing. See docs/desktop/Spec.md.")
    STATE.mkdir(parents=True, exist_ok=True)
    return subprocess.call([str(binary)], cwd=ROOT, env=environment())


if __name__ == "__main__":
    raise SystemExit(main())
