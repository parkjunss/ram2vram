"""Focused upstream regression checks with writable, isolated Windows temp."""
import os
from pathlib import Path
import subprocess
from runtime import SOURCE, STATE, environment


def main():
    temporary = STATE / "test-temp"
    temporary.mkdir(parents=True, exist_ok=True)
    logs = STATE / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    env = environment()
    env.update(TEMP=str(temporary), TMP=str(temporary))
    if os.name == "nt":
        env["PSMODULEPATH"] = str(Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32/WindowsPowerShell/v1.0/Modules")
    names = ["model-providers", "web-search", "web-ask", "agent-modes",
             "agent-tools-settings", "platform-paths"]
    node = SOURCE / "apps/desktop/src-tauri/resources/node/node.exe"
    result = subprocess.run([str(node), "--test", "--test-reporter=spec",
                             *[f"tests/{name}.test.mjs" for name in names]],
                            cwd=SOURCE / "apps/host", env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            encoding="utf-8", errors="replace")
    (logs / "host-checks.txt").write_text(result.stdout, encoding="utf-8")
    print(result.stdout[-12000:] if result.returncode else result.stdout[-1500:])
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
