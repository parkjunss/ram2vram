"""Smoke-test the running local Qwen server (default: port 8081)."""
from pathlib import Path
import json
import sys
import urllib.request

base = "http://127.0.0.1:" + (sys.argv[1] if len(sys.argv) > 1 else "8081")
with urllib.request.urlopen(base + "/health", timeout=10) as response:
    assert json.load(response)["status"] == "ok"
payload = {
    "model": "qwen3.6-35b-a3b",
    "messages": [{"role": "user", "content": "RAM과 VRAM의 차이를 한국어로 세 문장으로 설명해 주세요."}],
    "temperature": 0,
    "max_tokens": 192,
}
request = urllib.request.Request(
    base + "/v1/chat/completions",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(request, timeout=180) as response:
    result = json.load(response)
answer = result["choices"][0]["message"]["content"]
assert answer and any("\uac00" <= char <= "\ud7a3" for char in answer), result
assert not result["choices"][0]["message"].get("reasoning_content"), result
assert result["choices"][0]["finish_reason"] == "stop", result
out = Path(__file__).resolve().parents[2] / "qwen36_cache_logs" / "korean_response.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(answer)
print(json.dumps({"usage": result.get("usage"), "timings": result.get("timings")}, indent=2))
print("PASS: health, Korean response, thinking disabled, complete response")
