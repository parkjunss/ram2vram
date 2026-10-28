"""Finish the Qwen download using four HTTP range requests, then verify SHA256."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib
import json
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2] / "models"
TARGET = ROOT / "Qwen3.6-35B-A3B-UD-Q4_K_M.gguf"
PARTIAL = Path(str(TARGET) + ".partial")
MANIFEST = ROOT / "qwen36-download-ranges.json"
SIZE = 22134528992
SHA256 = "ac0e2c1189e055faa36eff361580e79c5bd6f8e76bffb4ce547f167d53e31a61"
URL = "https://huggingface.co/unsloth/Qwen3.6-35B-A3B-GGUF/resolve/a483e9e6cbd595906af30beda3187c2663a1118c/Qwen3.6-35B-A3B-UD-Q4_K_M.gguf"


def verify(path):
    if path.stat().st_size != SIZE:
        raise RuntimeError("Unexpected model size")
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != SHA256:
        raise RuntimeError("Model checksum mismatch")


def fetch(item):
    start, end, name = item
    path = ROOT / name
    if path.exists() and path.stat().st_size == end - start + 1:
        return
    print(f"Downloading bytes {start}-{end}", flush=True)
    subprocess.run([
        "curl.exe", "--fail", "--location", "--silent", "--show-error",
        "--retry", "5", "--range", f"{start}-{end}", "--output", str(path), URL,
    ], check=True)
    if path.stat().st_size != end - start + 1:
        raise RuntimeError(f"Incorrect HTTP range response: {name}")
    print(f"Completed {name}", flush=True)


def main():
    ROOT.mkdir(exist_ok=True)
    if TARGET.exists():
        verify(TARGET)
        return
    if MANIFEST.exists():
        manifest = json.loads(MANIFEST.read_text())
    else:
        prefix = PARTIAL.stat().st_size if PARTIAL.exists() else 0
        if not 0 <= prefix < SIZE:
            raise RuntimeError("Unexpected partial file size")
        step = (SIZE - prefix + 3) // 4
        ranges = [[start, min(start + step, SIZE) - 1, f"qwen36.range{i}"]
                  for i, start in enumerate(range(prefix, SIZE, step))]
        manifest = {"prefix": prefix, "ranges": ranges}
        MANIFEST.write_text(json.dumps(manifest, indent=2))
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(fetch, manifest["ranges"]))
    with PARTIAL.open("r+b" if PARTIAL.exists() else "w+b") as output:
        output.truncate(manifest["prefix"])
        output.seek(manifest["prefix"])
        for _, _, name in manifest["ranges"]:
            with (ROOT / name).open("rb") as source:
                shutil.copyfileobj(source, output, 8 * 1024 * 1024)
    print("Verifying SHA256...", flush=True)
    verify(PARTIAL)
    PARTIAL.rename(TARGET)
    for _, _, name in manifest["ranges"]:
        (ROOT / name).unlink()
    MANIFEST.unlink()
    print("Model downloaded and SHA256 verified", flush=True)


if __name__ == "__main__":
    main()
