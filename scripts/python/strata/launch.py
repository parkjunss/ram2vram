"""Use the installed Strata host/tools with this project's llama.cpp server."""
from pathlib import Path
import json
import os
import secrets
import subprocess
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
INSTALL = Path(os.environ.get("RAM2VRAM_STRATA_INSTALL", "C:/tools/Strata"))
STATE = ROOT / ".strata-ram2vram"
MODEL = "qwen3.6-35b-a3b"
LLM = "http://127.0.0.1:8081"
APP = "http://127.0.0.1:8795"
CONNECTION = "RAM2VRAM Qwen3.6 (local)"
CONTEXT = 65536
MAX_OUTPUT = 8192


def api(base, path, data=None, method=None):
    request = urllib.request.Request(
        base + path, data=None if data is None else json.dumps(data).encode(),
        headers={"Content-Type": "application/json"}, method=method,
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)


def reachable(base, path):
    try:
        return api(base, path)
    except (urllib.error.URLError, TimeoutError):
        return None


def wait_ready(process, base, path, seconds=120):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Process exited ({process.returncode}); see {STATE / 'logs'}")
        result = reachable(base, path)
        if result is not None:
            return result
        time.sleep(0.5)
    raise RuntimeError(f"Timed out waiting for {base}; see {STATE / 'logs'}")


def configure():
    connections = api(APP, "/api/model-providers")["connections"]
    existing = next((c for c in connections if c["name"] == CONNECTION), None)
    if existing:
        models = [dict(m, contextMax=CONTEXT, maxOutput=MAX_OUTPUT) if m["id"] == MODEL else m for m in existing["models"]]
        if models != existing["models"]:
            api(APP, "/api/model-providers", {**existing, "models": models})
    else:
        api(APP, "/api/model-providers", {
            "kind": "custom", "name": CONNECTION, "protocol": "openai-chat",
            "baseUrl": LLM + "/v1", "models": [{
                "id": MODEL, "name": "Qwen3.6-35B-A3B / RAM2VRAM",
                "contextMax": CONTEXT, "maxOutput": MAX_OUTPUT, "vision": False, "reasoning": True,
            }],
        })
        api(APP, "/api/agent/tools", {
            "groups": {"helpers": False, "goals": False, "jobs": True},
        }, "PUT")
        api(APP, "/api/setup/step", {"step": 1, "flowVersion": 2, "dismissed": True})
    return api(APP, "/api/agent/status")


def main():
    node = INSTALL / "node/node.exe"
    host = INSTALL / "host/server/index.mjs"
    engine = ROOT / "llama.cpp-hybrid-cache/build/bin/llama-server.exe"
    weights = ROOT / "models/Qwen3.6-35B-A3B-UD-Q4_K_M.gguf"
    for path in (node, host, engine, weights, INSTALL / "harness/lib/bin.js"):
        if not path.is_file():
            raise RuntimeError(f"Required file missing: {path}")
    (STATE / "logs").mkdir(parents=True, exist_ok=True)
    children, logs = [], []
    host_process = None
    shutdown_token = secrets.token_hex(32)

    def start(args, name, env=None):
        log = (STATE / "logs" / name).open("wb")
        logs.append(log)
        child = subprocess.Popen(
            [str(a) for a in args], cwd=ROOT, env=env,
            stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        children.append(child)
        return child

    try:
        props = reachable(LLM, "/props")
        if props is not None:
            if props.get("model_alias") != MODEL or props.get("default_generation_settings", {}).get("n_ctx", 0) < CONTEXT:
                raise RuntimeError(f"Port 8081 has a different model or a context smaller than {CONTEXT}. Stop that server first, then rerun this launcher.")
        else:
            print(f"Starting Qwen3.6 with {CONTEXT} context tokens and 8GiB expert cache...", flush=True)
            process = start([
                engine, "-m", weights, "--alias", MODEL, "-ngl", "99", "--cpu-moe",
                "--moe-cache", "8192", "-c", str(CONTEXT), "--parallel", "1", "--jinja",
                "--reasoning", "off", "--temp", "0.7", "--top-p", "0.8", "--top-k", "20",
                "--host", "127.0.0.1", "--port", "8081", "-lv", "4",
            ], "qwen-server.log")
            wait_ready(process, LLM, "/health")
        if reachable(APP, "/api/model-providers") is not None:
            raise RuntimeError("Port 8795 is already in use. Open http://127.0.0.1:8795 or close the existing Strata launcher first.")
        env = dict(os.environ)
        env.update({
            "STRATA_HOME": str(STATE), "STRATA_WORKSPACE": str(ROOT),
            "STRATA_PORT": "8795", "STRATA_BIND": "127.0.0.1",
            "STRATA_HARNESS_DIR": str(INSTALL / "harness"),
            "STRATA_CONTROL_DIR": str(INSTALL / "control"),
            "STRATA_COMPONENTS_DIR": str(STATE / "components"),
            "STRATA_SETTINGS_FILE": str(STATE / "app-settings.json"),
            "STRATA_RUNTIME_DIR": str(STATE / "runtime"),
            "STRATA_TUNE_DIR": str(STATE / "tuning"),
            "STRATA_TIMESKIP_DIR": str(STATE / "time-skip"),
            "STRATA_MODELS_DIR": str(ROOT / "models"),
            "STRATA_NO_ACQUIRE": "1", "STRATA_NO_BUNDLED_ENGINE": "1",
            "STRATA_NO_REPAIR_ACCESS": "1",
            "STRATA_UI_MODE": "browser",
            "STRATA_SHUTDOWN_TOKEN": shutdown_token,
            "STRATA_EXIT_WITH_PARENT": "1",
        })
        host_process = start([node, host, "--dist", INSTALL / "host/dist"], "strata-host.log", env)
        wait_ready(host_process, APP, "/api/model-providers")
        status = configure()
        print(f"Strata: {APP}\nWorkspace: {ROOT}\nAgent: {status.get('state', 'see Settings')}\nKeep this launcher running. Ctrl+C stops the processes it started.", flush=True)
        while host_process.poll() is None:
            for child in children:
                if child.poll() is not None:
                    raise RuntimeError(f"A process exited ({child.returncode}); see logs")
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping project Strata...", flush=True)
    finally:
        if host_process is not None and host_process.poll() is None:
            try:
                request = urllib.request.Request(
                    APP + "/api/control/shutdown", data=b"{}",
                    headers={"Content-Type": "application/json", "x-strata-shutdown": shutdown_token},
                )
                with urllib.request.urlopen(request, timeout=10):
                    pass
                host_process.wait(timeout=50)
            except (OSError, subprocess.TimeoutExpired):
                pass
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
        for log in logs:
            log.close()


if __name__ == "__main__":
    main()
