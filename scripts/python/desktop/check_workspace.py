"""Run workspace and real Harness context/skill regressions with a synthetic model."""
import os
from pathlib import Path
import subprocess
from runtime import ROOT, STATE

def main():
    temporary = STATE / 'test-temp'
    temporary.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, TEMP=str(temporary), TMP=str(temporary),
               STRATA_HARNESS_DIR=str(ROOT / 'desktop/dist/harness'))
    tests = ['desktop/workspace-ui/test-core.mjs', 'desktop/workspace-ui/test-generation.mjs',
             'desktop/workspace-ui/test-context-skills.mjs']
    tests += ['desktop/strata/apps/host/tests/' + name + '.test.mjs' for name in
              ['agent-context', 'agent-skills', 'skills-used']]
    result = subprocess.run(['node', '--test', *tests], cwd=ROOT, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding='utf-8', errors='replace')
    log = STATE / 'logs/workspace-regressions.txt'
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(result.stdout, encoding='utf-8')
    print(result.stdout[-14000:] if result.returncode else result.stdout[-1800:])
    return result.returncode

if __name__ == '__main__':
    raise SystemExit(main())
