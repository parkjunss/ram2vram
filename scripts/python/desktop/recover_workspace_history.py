"""Read a backup of Workspace's LevelDB journal; never modify WebView data."""
from pathlib import Path
import datetime
import os
import json
import shutil
import struct
from runtime import STATE

def varint(data, at):
    value = 0
    for shift in range(0, 70, 7):
        byte = data[at]; at += 1
        value |= (byte & 127) << shift
        if byte < 128:
            return value, at
    raise ValueError('invalid varint')

def batches(data):
    pending = b''
    for block_start in range(0, len(data), 32768):
        block = data[block_start:block_start + 32768]; at = 0
        while at + 7 <= len(block):
            _, length, kind = struct.unpack_from('<IHB', block, at); at += 7
            if not length or at + length > len(block): break
            part = block[at:at + length]; at += length
            if kind == 1: yield part
            elif kind == 2: pending = part
            elif kind == 3: pending += part
            elif kind == 4: yield pending + part; pending = b''

def entries(batch):
    if len(batch) < 12: return
    sequence, count = struct.unpack_from('<QI', batch); at = 12
    for index in range(count):
        kind = batch[at]; at += 1
        length, at = varint(batch, at); key = batch[at:at+length]; at += length
        value = None
        if kind == 1:
            length, at = varint(batch, at); value = batch[at:at+length]; at += length
        elif kind != 0: break
        yield sequence + index, key, value

def main():
    source = Path(os.environ['LOCALAPPDATA']) / 'local.ram2vram.workspace/EBWebView/Default/Local Storage/leveldb'
    destination = STATE / 'recovery' / datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    destination.mkdir(parents=True)
    for file in source.iterdir():
        if file.is_file() and file.name != 'LOCK':
            shutil.copy2(file, destination / file.name)
    found = []
    for file in destination.glob('*.log'):
        for batch in batches(file.read_bytes()):
            try:
                for seq, key, value in entries(batch):
                    if b'ram2vram.workspace.v1' not in key or not value: continue
                    encoding = 'utf-16-le' if value[0] == 0 else 'latin-1'
                    saved = json.loads(value[1:].decode(encoding))
                    if isinstance(saved.get('sessions'), list): found.append((seq, saved))
            except (ValueError, IndexError, UnicodeError): continue
    found.sort(key=lambda row: row[0])
    if not found: print('No complete Workspace values in journal backup:', destination); return
    latest = found[-1][1]
    (destination / 'latest-chats.json').write_text(json.dumps(latest, ensure_ascii=False, indent=2), encoding='utf-8')
    merged = {}
    for _, saved in found:
        for session in saved['sessions']:
            if isinstance(session.get('id'), str):
                previous = merged.get(session['id'])
                if not previous or len(session.get('messages', [])) >= len(previous.get('messages', [])): merged[session['id']] = session
    recovered = {'active': latest.get('active'), 'sessions': list(merged.values())}
    (destination / 'recovered-chats.json').write_text(json.dumps(recovered, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'backup':str(destination),'snapshots':len(found),'latest_sessions':len(latest['sessions']),'recovered_sessions':len(merged),'message_counts':[len(s.get('messages', [])) for s in merged.values()]},ensure_ascii=False))

if __name__ == '__main__': main()
