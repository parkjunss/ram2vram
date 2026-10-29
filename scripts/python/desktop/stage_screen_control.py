"""Stage screen-control host sources without replacing the executable or user data."""
import shutil
from runtime import ROOT, SOURCE

FILES = [
    'index.mjs', 'workspace-skills.mjs', 'agent/profile.mjs',
    'agent/tools-catalog.mjs', 'agent/plugins/strata-gate.mjs',
    'agent/desktop-control.mjs', 'agent/desktop-control.ps1',
    'agent/desktop-mcp.mjs', 'agent/desktop-native.cs',
]

if __name__ == '__main__':
    for name in FILES:
        destination = ROOT / 'desktop/dist/host/server' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SOURCE / 'apps/host/server' / name, destination)
    print('Screen-control server staged. Restart the app to load it.')
