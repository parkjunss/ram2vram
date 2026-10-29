"""Assemble the built Windows app and public runtimes, never user state."""
from pathlib import Path
import json
import shutil
from runtime import ROOT, SOURCE


def main():
    desktop = SOURCE / "apps/desktop/src-tauri"
    binary = desktop / "target/release/strata-desktop.exe"
    sources = {
        "host/dist": SOURCE / "apps/host/dist",
        "host/server": SOURCE / "apps/host/server",
        "node": desktop / "resources/node",
        "control": desktop / "resources/control",
        "harness": desktop / "resources/harness",
    }
    for path in [binary, *sources.values()]:
        if not path.exists():
            raise SystemExit(f"Missing build input: {path}")
    destination = ROOT / "desktop/dist"
    destination.mkdir(parents=True, exist_ok=True)
    for relative, source in sources.items():
        shutil.copytree(source, destination / relative, dirs_exist_ok=True)
    shutil.copy2(SOURCE / "apps/host/package.json", destination / "host/package.json")
    shutil.copy2(SOURCE / "LICENSE", destination / "STRATA-LICENSE.txt")
    shutil.copy2(binary, destination / "RAM2VRAM.exe")
    (destination / "ram2vram.json").write_text(
        json.dumps({"workspaceRoot": str(ROOT)}, indent=2) + "\n", encoding="utf-8")
    print(destination / "RAM2VRAM.exe")


if __name__ == "__main__":
    main()
