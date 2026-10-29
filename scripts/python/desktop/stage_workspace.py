"""Stage the independent UI without replacing the running Strata-based app."""
import argparse
import shutil
from runtime import ROOT, SOURCE


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", action="store_true")
    args = parser.parse_args()
    for destination in (SOURCE / "apps/host/dist/workspace", ROOT / "desktop/dist/host/dist/workspace"):
        destination.mkdir(parents=True, exist_ok=True)
        for name in ("index.html", "workspace.css", "workspace-settings.css", "workspace.js", "workspace-tools.mjs", "workspace-history.mjs", "workspace-modes.mjs", "workspace-desktop.mjs", "workspace-vision.mjs", "workspace-core.mjs", "manifest.json"):
            shutil.copy2(ROOT / "desktop/workspace-ui" / name, destination / name)
    if args.binary:
        shutil.copy2(SOURCE / "apps/desktop/src-tauri/target/release/strata-desktop.exe",
                     ROOT / "desktop/dist/RAM2VRAM-Workspace.exe")
    print("Workspace UI staged" + (" with native executable" if args.binary else ""))


if __name__ == "__main__":
    main()
