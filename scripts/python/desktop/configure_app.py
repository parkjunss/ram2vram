"""Load the prepared Qwen3.8 model through the desktop's native lifecycle."""
import json
import time
import urllib.request

APP = "http://127.0.0.1:47832"


def api(path, data=None, method=None):
    request = urllib.request.Request(APP + path,
        data=None if data is None else json.dumps(data).encode(),
        headers={"Content-Type": "application/json"}, method=method)
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def main():
    state = api("/api/native?refresh=1")
    models = (state.get("installed") or {}).get("models", [])
    chosen = next((m for m in models if m.get("model", "").upper() == "IQ2_XS"), None)
    if chosen is None:
        raise SystemExit("Qwen3.8 IQ2_XS is not installed in this app's state. Finish prepare_model.py first.")
    ready = next((i for i in state.get("instances", [])
                  if i.get("model") == chosen["model"] and i.get("status") == "ready"), None)
    if ready is None:
        job = api("/api/native/operations", {"kind": "load", "args": {
            "model": chosen["model"], "vision": "no", "values": {"parallel": 1}}})
        print("Loading Qwen3.8 in the desktop...", flush=True)
        deadline = time.monotonic() + 900
        while time.monotonic() < deadline:
            state = api("/api/native")
            current = next((j for j in state.get("jobs", []) if j["id"] == job["id"]), None)
            if current and current.get("state") == "error":
                raise RuntimeError(current.get("error", "Model load failed"))
            ready = next((i for i in state.get("instances", [])
                          if i.get("model") == chosen["model"] and i.get("status") == "ready"), None)
            if ready:
                break
            time.sleep(2)
        if ready is None:
            raise TimeoutError("Model did not become ready in 15 minutes")
    api("/api/setup/complete", {})
    print(json.dumps({"model": ready["model"], "instance": ready["id"],
                      "status": ready["status"], "app": APP}))


if __name__ == "__main__":
    main()
