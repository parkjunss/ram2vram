"""Actual model-to-tool checks using only generated data and a public query."""
import argparse
import json
import secrets
import urllib.request
import uuid
from configure_app import APP, api
from runtime import STATE
from pathlib import Path

QUERY = "Python official documentation pathlib Path.read_text"


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--web", action="store_true")
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--deny-write", action="store_true")
    mode.add_argument("--command", action="store_true")
    args = parser.parse_args()
    nonce = "RAM2VRAM_TOOL_OK_" + secrets.token_hex(10)
    fixture = STATE / "smoke-input.txt"
    fixture.write_text(nonce + "\n", encoding="utf-8")
    output = STATE / ("smoke-output-" + uuid.uuid4().hex + ".txt")
    command = f"Write-Output '{nonce}'"
    message = (f"Search the web for exactly this query: {QUERY}. Use the web search tool once, "
               "then briefly summarize the results and cite one source URL. Do not use other tools or delegate."
               if args.web else
               f"Use the read file tool to read {fixture.as_posix()}. Reply with only its exact first line. "
               "Do not change files, execute commands, search the web or delegate.")
    if args.write or args.deny_write:
        message = (f"Use the write file tool to create {output.as_posix()} containing exactly {nonce}. "
                   "If approval is denied, stop and say it was denied. Do not use shell, web or other paths. Do not delegate.")
    elif args.command:
        message = f"Use the PowerShell tool once to run exactly: {command}. Reply with its output. Do not use other tools or delegate."
    session = "ram2vram-smoke-" + uuid.uuid4().hex
    payload = {"sessionId": session, "workspaceId": "root", "mode": "manual",
               "thinking": "off", "message": message}
    request = urllib.request.Request(APP + "/api/chat/stream", data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
    frames, approvals = [], 0
    try:
        with urllib.request.urlopen(request, timeout=600) as response:
            for line in response:
                if not line.strip():
                    continue
                frame = json.loads(line)
                frames.append(frame)
                tool = frame.get("tool", {})
                if frame.get("type") == "agent-tool":
                    print(tool.get("name"), tool.get("state"), flush=True)
                    if tool.get("state") == "proposed":
                        approvals += 1
                        tool_args = tool.get("args", {})
                        allowed = (args.web and tool.get("name") == "web_search"
                                   and QUERY in json.dumps(tool_args))
                        if args.write and tool.get("name") == "write":
                            target = tool_args.get("file_path", tool_args.get("path", ""))
                            allowed = (Path(target).resolve() == output.resolve()
                                       and tool_args.get("content", "").strip() == nonce)
                        if args.command and tool.get("name") == "pwsh":
                            allowed = tool_args.get("command", "").strip() == command
                        api("/api/chat/approval", {"sessionId": session,
                            "toolId": tool["id"], "decision": "approve" if allowed else "deny"})
                        if not allowed and not args.deny_write:
                            raise RuntimeError("Unexpected tool requested approval; denied")
                if frame.get("type") == "error":
                    raise RuntimeError(str(frame))
    finally:
        (STATE / "logs").mkdir(exist_ok=True)
        kind = "web" if args.web else "write" if args.write else "deny-write" if args.deny_write else "command" if args.command else "read"
        (STATE / "logs" / (kind + "-smoke.json")).write_text(
            json.dumps(frames, ensure_ascii=False, indent=2), encoding="utf-8")
    answer = "".join(f.get("text", "") for f in frames if f.get("type") == "delta")
    completed = [f["tool"] for f in frames if f.get("type") == "agent-tool"
                 and f.get("tool", {}).get("state") == "done"]
    assert any(f.get("type") == "start" and f.get("agent") for f in frames), "Agent fallback"
    assert any(f.get("type") == "done" for f in frames), "Incomplete turn"
    if args.write:
        assert approvals > 0, "Write did not ask for approval"
        assert output.read_text(encoding="utf-8").strip() == nonce, "Incorrect write result"
    elif args.deny_write:
        assert approvals > 0, "Write did not ask for approval"
        assert not output.exists(), "Denied write changed the filesystem"
        assert any(f.get("tool", {}).get("state") == "denied" for f in frames), "No denial result"
    elif args.command:
        assert any(t.get("name") == "pwsh" for t in completed), "Command did not complete"
        assert nonce in answer, "Command output not returned"
    elif args.web:
        assert any(t.get("name") == "web_search" and "http" in str(t.get("result"))
                   for t in completed), "No successful web results"
        assert "http" in answer, "No source URL in answer"
    else:
        assert any(t.get("name") == "read" for t in completed), "No successful file read"
        assert nonce in answer, "Model did not return the generated file contents"
    print("PASS:", kind, flush=True)
    print(answer[:2000])


if __name__ == "__main__":
    main()
