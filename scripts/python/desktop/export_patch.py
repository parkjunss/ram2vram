"""Refresh the reproducible vendor patch, preserving its existing file scope."""
import re
import subprocess
from runtime import ROOT, SOURCE

patch = ROOT / 'desktop/ram2vram.patch'
paths = set(re.findall(r'^diff --git a/(\S+) b/\S+$', patch.read_text(encoding='utf-8'), re.M))
paths.update([
    'apps/host/server/agent/profile.mjs', 'apps/host/server/agent/tools-catalog.mjs',
    'apps/host/server/agent/plugins/strata-gate.mjs', 'apps/host/server/index.mjs',
    'apps/host/server/workspace-skills.mjs',
    *['apps/host/server/agent/' + name for name in
      ['desktop-control.mjs', 'desktop-control.ps1', 'desktop-mcp.mjs', 'desktop-native.cs']],
    'apps/host/tests/workspace-desktop.test.mjs', 'apps/host/tests/workspace-desktop-harness.test.mjs',
    'apps/host/tests/agent-tools-settings.test.mjs',
])
tracked = set(subprocess.check_output(['git', 'ls-files'], cwd=SOURCE, text=True).splitlines())
result = subprocess.check_output(['git', 'diff', '--binary', 'HEAD', '--', *sorted(paths & tracked)], cwd=SOURCE)
for path in sorted(paths - tracked):
    diff = subprocess.run(['git', 'diff', '--no-index', '--binary', '--', '/dev/null', path], cwd=SOURCE, capture_output=True)
    if diff.returncode not in (0, 1):
        raise RuntimeError(diff.stderr.decode('utf-8', errors='replace'))
    result += diff.stdout
patch.write_bytes(result)
subprocess.run(['git', 'apply', '--reverse', '--check', str(patch)], cwd=SOURCE, check=True)
print(f'Patch refreshed and reverse-checked: {len(paths)} scoped files')
