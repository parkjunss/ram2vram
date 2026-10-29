"""Prepare the pinned Qwen3.8 image encoder without rerunning text-model setup."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
import urllib.request
from runtime import ROOT, STATE

NAME = 'mmproj-Qwen3.8-Flash-Next-BF16.gguf'
SIZE = 907543008
SHA256 = 'b1a82259702816a5330d7bd7607cd9676b11780e79ff7348c21103ff3ce49bd0'
URL = 'https://huggingface.co/ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF/resolve/ed59f92082b1e93c0e96d60a8b11aab089b52f09/' + NAME

def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def main():
    destination = ROOT / 'models/qwen38/models' / NAME
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        part = destination.with_suffix('.gguf.part')
        offset = part.stat().st_size if part.exists() else 0
        if offset < SIZE:
            request = urllib.request.Request(URL, headers={'Range': f'bytes={offset}-'} if offset else {})
            with urllib.request.urlopen(request, timeout=60) as response:
                append = offset > 0 and response.status == 206
                if append and not response.headers.get('Content-Range', '').startswith(f'bytes {offset}-'):
                    raise RuntimeError('Unexpected download range')
                with part.open('ab' if append else 'wb') as output:
                    count = offset if append else 0
                    last = time.monotonic()
                    while chunk := response.read(4 * 1024 * 1024):
                        output.write(chunk)
                        count += len(chunk)
                        if count > SIZE:
                            raise RuntimeError('Encoder exceeded pinned size')
                        if time.monotonic() - last > 10:
                            print(f'Encoder download: {count * 100 / SIZE:.1f}%', flush=True)
                            last = time.monotonic()
        if part.stat().st_size != SIZE or digest(part) != SHA256:
            raise RuntimeError('Encoder size or SHA256 mismatch; config was not changed')
        part.replace(destination)
    if destination.stat().st_size != SIZE or digest(destination) != SHA256:
        raise RuntimeError('Installed encoder does not match pinned file')
    config = STATE / 'install/strata-iq2_xs.json'
    value = json.loads(config.read_text(encoding='utf-8-sig'))
    encoder = STATE / 'components/engine/0.1.52-windows-x86_64-cuda-cuda13/strata-vision.exe'
    if not encoder.is_file():
        raise RuntimeError('Expected installed vision reader is missing')
    args = value['args']
    model = Path(args[args.index('--native') + 1])
    if not model.is_file():
        raise RuntimeError('Native model vocabulary file is missing')
    backup = STATE / 'recovery' / time.strftime('%Y%m%d-%H%M%S-vision')
    backup.mkdir(parents=True, exist_ok=True)
    shutil.copy2(config, backup / config.name)
    value['vision'] = {'exe': str(encoder), 'mmproj': str(destination), 'model': str(model),
                       'gpu': False, 'max_tokens': 300, 'threads': min(16, max(1, (os.cpu_count() or 2) // 2))}
    value['ui_vision_enabled'] = True
    value['ui_vision_device'] = 'cpu'
    temp = config.with_suffix('.vision-tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(config)
    print('Pinned encoder verified; CPU vision configured. Existing engine arguments preserved.', flush=True)

if __name__ == '__main__':
    main()
