from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW_FILE = ROOT / "data" / "raw" / "Behavioral-features - per minute.xlsx"
RAW_FILE = Path(os.environ.get("SWELL_DATA_PATH", DEFAULT_RAW_FILE))
PROCESSED_DIR = ROOT / "data" / "processed"
TABLE_DIR = ROOT / "tables"
FIGURE_DIR = ROOT / "figures"

SEED = 20260923

CONDITION_ORDER = ["N", "I", "T"]
CONDITION_LABELS = {
    "N": "Neutral",
    "I": "Interruptions",
    "T": "Time pressure",
    "R": "Relaxation",
}

SUBJECTIVE_FEATURES = [
    "Valence_rc",
    "Arousal_rc",
    "Dominance",
    "Stress",
    "MentalEffort",
    "MentalDemand",
    "PhysicalDemand",
    "TemporalDemand",
    "Effort",
    "Performance_rc",
    "Frustration",
    "NasaTLX",
]

# Thirteen computer-interaction variables retained for prediction. The five
# excluded variables (right/double click, wheel, drag, mouse distance) are
# marked sparse or unreliable in the dataset's own feature notes.
BEHAVIOR_FEATURES = [
    "SnMouseAct",
    "SnLeftClicked",
    "SnKeyStrokes",
    "SnChars",
    "SnSpecialKeys",
    "SnDirectionKeys",
    "SnErrorKeys",
    "SnShortcutKeys",
    "SnSpaces",
    "SnAppChange",
    "SnTabfocusChange",
    "CharactersRatio",
    "ErrorKeyRatio",
]

BEHAVIOR_PRIMARY = [
    "SnKeyStrokes",
    "SnMouseAct",
    "SnAppChange",
    "SnTabfocusChange",
    "SnErrorKeys",
]

PHYSIOLOGY_FEATURES = ["HR", "RMSSD", "SCL"]

ANALYSIS_COLUMNS = (
    ["PP", "Blok", "Condition", "timestamp"]
    + SUBJECTIVE_FEATURES
    + BEHAVIOR_FEATURES
    + PHYSIOLOGY_FEATURES
)


def ensure_output_dirs() -> None:
    for path in (PROCESSED_DIR, TABLE_DIR, FIGURE_DIR):
        path.mkdir(parents=True, exist_ok=True)

