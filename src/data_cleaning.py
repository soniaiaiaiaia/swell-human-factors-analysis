from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from config import (
    ANALYSIS_COLUMNS,
    BEHAVIOR_FEATURES,
    CONDITION_LABELS,
    PHYSIOLOGY_FEATURES,
    PROCESSED_DIR,
    RAW_FILE,
    SUBJECTIVE_FEATURES,
    ensure_output_dirs,
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_and_clean(path: Path) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name="SWELLdata")
    missing = [column for column in ANALYSIS_COLUMNS if column not in raw.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    data = raw.loc[:, ANALYSIS_COLUMNS].copy()
    for column in ANALYSIS_COLUMNS[4:]:
        data[column] = pd.to_numeric(data[column], errors="coerce")
        data[column] = data[column].replace(999, np.nan)

    data["ConditionLabel"] = data["Condition"].map(CONDITION_LABELS)
    data["timestamp"] = pd.to_datetime(
        data["timestamp"].astype(str), format="%Y%m%dT%H%M%S%f", errors="coerce"
    )
    return data


def validate_structure(data: pd.DataFrame) -> dict:
    work = data[data["Condition"].isin(["N", "I", "T"])].copy()
    participant_condition = work[["PP", "Condition", "Blok"]].drop_duplicates()
    subjective_unique = (
        work.groupby(["PP", "Condition"])[SUBJECTIVE_FEATURES]
        .nunique(dropna=True)
        .max()
    )

    if work["PP"].nunique() != 25:
        raise ValueError("Expected 25 participants in the released feature table.")
    if len(work) != 2688:
        raise ValueError("Expected 2,688 non-relaxation minute rows.")
    if len(participant_condition) != 75:
        raise ValueError("Expected 75 participant-condition blocks.")
    if (subjective_unique > 1).any():
        raise ValueError("Subjective ratings vary within a participant-condition block.")

    order_table = (
        participant_condition.sort_values(["PP", "Blok"])
        .groupby("PP")["Condition"]
        .agg("".join)
        .value_counts()
        .to_dict()
    )
    missingness = {
        column: float(work[column].isna().mean())
        for column in BEHAVIOR_FEATURES + PHYSIOLOGY_FEATURES + SUBJECTIVE_FEATURES
    }
    return {
        "source_sha256": None,
        "rows_all": int(len(data)),
        "rows_work": int(len(work)),
        "rows_relaxation": int((data["Condition"] == "R").sum()),
        "participants": int(work["PP"].nunique()),
        "participant_condition_blocks": int(len(participant_condition)),
        "condition_rows": {
            str(key): int(value)
            for key, value in work["Condition"].value_counts().sort_index().items()
        },
        "condition_orders": {str(key): int(value) for key, value in order_table.items()},
        "missingness_proportion": missingness,
        "subjective_rows_are_repeated_within_block": True,
        "neutral_always_block_1": bool(
            (participant_condition.loc[participant_condition["Condition"] == "N", "Blok"] == 1).all()
        ),
    }


def participant_condition_table(work: pd.DataFrame) -> pd.DataFrame:
    subjective = work.groupby(["PP", "Condition"])[SUBJECTIVE_FEATURES].first()
    objective = work.groupby(["PP", "Condition"])[
        BEHAVIOR_FEATURES + PHYSIOLOGY_FEATURES
    ].mean()
    block = work.groupby(["PP", "Condition"])["Blok"].first()
    result = pd.concat([block, subjective, objective], axis=1).reset_index()
    result["ConditionLabel"] = result["Condition"].map(CONDITION_LABELS)
    return result


def run(input_path: Path = RAW_FILE, output_dir: Path = PROCESSED_DIR) -> None:
    ensure_output_dirs()
    data = load_and_clean(input_path)
    qc = validate_structure(data)
    qc["source_sha256"] = sha256(input_path)
    work = data[data["Condition"].isin(["N", "I", "T"])].copy()

    output_dir.mkdir(parents=True, exist_ok=True)
    work.to_csv(output_dir / "minute_work.csv", index=False)
    participant_condition_table(work).to_csv(
        output_dir / "participant_condition.csv", index=False
    )
    with (output_dir / "qc_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(qc, handle, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean and validate SWELL-KW feature data.")
    parser.add_argument("--input", type=Path, default=RAW_FILE)
    parser.add_argument("--output-dir", type=Path, default=PROCESSED_DIR)
    args = parser.parse_args()
    run(args.input, args.output_dir)

