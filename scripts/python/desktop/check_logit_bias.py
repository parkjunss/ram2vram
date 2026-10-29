"""Probe the current engine through the agent with one synthetic request; restore settings."""
import json
import urllib.request
import uuid
from configure_app import APP, api

def main():
    previous = api('/api/workspace/generation')
    try:
        api('/api/workspace/generation', {**previous, 'logit_bias': {'0': 0.01}, 'max_tokens': 64})
        request = urllib.request.Request(APP + '/api/chat/stream', data=json.dumps({
            'sessionId': 'bias-probe-' + uuid.uuid4().hex, 'workspaceId': 'root',
            'mode': 'plan', 'thinking': 'off', 'message': '도구를 사용하지 말고 안녕하세요 한 단어만 답하세요.'
        }).encode(), headers={'Content-Type': 'application/json'})
        frames = []
        with urllib.request.urlopen(request, timeout=180) as response:
            for line in response:
                if line.strip(): frames.append(json.loads(line))
        print(json.dumps([f for f in frames if f.get('type') in ('error', 'delta', 'done')], ensure_ascii=False))
    finally:
        api('/api/workspace/generation', previous)

if __name__ == '__main__':
    main()
