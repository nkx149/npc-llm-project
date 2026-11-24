"""Filesystem locations, resolved from the project root (not the working directory).

Imports nothing of ours.
"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"

PERSONAS_DIR = DATA_DIR / "CharacterPersonas"
RUNTIME_CONFIG_PATH = DATA_DIR / "model_configs" / "runtime.yaml"
SAVES_DIR = DATA_DIR / "saves"
