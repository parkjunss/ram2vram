"""Shared, isolated paths for the RAM2VRAM desktop and model preparation."""
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "desktop" / "strata"
STATE = ROOT / ".ram2vram-desktop"


def environment():
    env = dict(os.environ)
    env.update({
        "STRATA_HOME": str(STATE),
        "STRATA_DESKTOP_DATA_DIR": str(STATE),
        "STRATA_SETTINGS_FILE": str(STATE / "app-settings.json"),
        "STRATA_COMPONENTS_DIR": str(STATE / "components"),
        "STRATA_PROFILE_DIR": str(STATE / "profiles"),
        "STRATA_RUNTIME_DIR": str(STATE / "runtime"),
        "STRATA_TUNE_DIR": str(STATE / "tuning"),
        "STRATA_TIMESKIP_DIR": str(STATE / "time-skip"),
        "STRATA_MODELS_DIR": str(ROOT / "models" / "qwen38"),
        "STRATA_WORKSPACE": str(ROOT),
        "PYTHONUTF8": "1",
    })
    return env
