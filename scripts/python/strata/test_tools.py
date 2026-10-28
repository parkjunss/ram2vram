"""End-to-end: Qwen must read a random local fixture through Strata's tool loop."""
from pathlib import Path
import json
import secrets
import urllib.request
import uuid
from launch import APP, CONNECTION, MODEL, ROOT, STATE, api

fixture = STATE / "smoke-input.txt"
nonce = "STRATA_TOOL_OK_" + secrets.token_hex(8)
fixture.write_text(nonce + "\n", encoding="utf-8")
connection = next(c for c in api(APP, "/api/model-providers")["connections"] if c["name"] == CONNECTION)
payload = {
    "sessionId": "ram2vram-smoke-" + uuid.uuid4().hex,
    "workspaceId": "root", "mode": "manual", "thinking": "off",
    "remoteModel": {"connectionId": connection["id"], "modelId": MODEL},
    "message": f"Use your file-reading tool to read {fixture.as_posix()}. Reply with only the exact first line. Do not change any files, run commands, search the web or delegate.",
}
request = urllib.request.Request(APP + "/api/chat/stream", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
frames = []
with urllib.request.urlopen(request, timeout=600) as response:
    for line in response:
        if not line.strip():
            continue
        frame = json.loads(line)
        frames.append(frame)
        if frame.get("type") in ("agent-tool", "error", "notice", "done", "start"):
            print(json.dumps(frame, ensure_ascii=True)[:2500], flush=True)
        if frame.get("type") == "agent-tool" and "proposed" in json.dumps(frame):
            api(APP, "/api/chat/stop", {"sessionId": payload["sessionId"]})
            raise RuntimeError("Read-only test unexpectedly required approval; no approval was granted.")
log = STATE / "logs/tool-smoke.json"
log.write_text(json.dumps(frames, ensure_ascii=False, indent=2), encoding="utf-8")
answer = "".join(f.get("text", "") for f in frames if f.get("type") == "delta")
assert any(f.get("type") == "start" and f.get("agent") for f in frames), "Agent fallback"
assert any(f.get("type") == "agent-tool" and "done" in json.dumps(f) for f in frames), "No successful tool call"
assert not any(f.get("type") == "error" for f in frames), "Agent reported an error"
assert nonce in answer, f"File contents were not returned: {answer}"
print("PASS: Qwen -> Strata file tool -> local file -> Qwen response", flush=True)
