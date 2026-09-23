from __future__ import annotations

from pathlib import Path

import nbformat as nbf


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_DIR = ROOT / "notebooks"


def code(source: str):
    return nbf.v4.new_code_cell(source.strip())


def markdown(source: str):
    return nbf.v4.new_markdown_cell(source.strip())


def base_notebook(cells):
    notebook = nbf.v4.new_notebook(cells=cells)
    notebook.metadata["kernelspec"] = {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    }
    notebook.metadata["language_info"] = {"name": "python", "version": "3"}
    return notebook


def build_cleaning() -> None:
    notebook = base_notebook(
        [
            markdown(
                """
# 01 · Data cleaning and quality control

This notebook audits the public SWELL-KW feature workbook used in the case study. It does not claim ownership of data collection.

**Source:** SWELL Knowledge Work Dataset, DOI [10.17026/DANS-X55-69ZP](https://doi.org/10.17026/DANS-X55-69ZP)  
**Input:** `Behavioral-features - per minute.xlsx`, sheet `SWELLdata`

The questionnaire fields contain one post-condition value repeated on every minute. The block-level table below therefore keeps one questionnaire response and averages objective features within each participant-condition block.
"""
            ),
            code(
                """
from pathlib import Path
import os, sys, json
import pandas as pd

ROOT = Path.cwd().resolve().parent if Path.cwd().name == "notebooks" else Path.cwd().resolve()
sys.path.insert(0, str(ROOT / "src"))
from data_cleaning import load_and_clean, validate_structure, participant_condition_table, sha256

raw_path = Path(os.environ.get("SWELL_DATA_PATH", ROOT / "data" / "raw" / "Behavioral-features - per minute.xlsx"))
if not raw_path.exists():
    raise FileNotFoundError(
        "Download the public workbook from DOI 10.17026/DANS-X55-69ZP, place it in data/raw, "
        "or set SWELL_DATA_PATH."
    )
print(f"Input: {raw_path.name}")
print(f"SHA-256: {sha256(raw_path)}")
"""
            ),
            code(
                """
data = load_and_clean(raw_path)
qc = validate_structure(data)
qc["source_sha256"] = sha256(raw_path)
work = data[data["Condition"].isin(["N", "I", "T"])].copy()
blocks = participant_condition_table(work)

pd.DataFrame({
    "audit_item": ["all rows", "work rows", "relaxation rows", "participants", "participant-condition blocks"],
    "value": [len(data), len(work), (data.Condition == "R").sum(), work.PP.nunique(), len(blocks)],
})
"""
            ),
            markdown("## Experimental order audit"),
            code(
                """
order = (blocks.sort_values(["PP", "Blok"]).groupby("PP")["Condition"].agg("".join).value_counts())
print(order.to_string())
print(f"Neutral always block 1: {(blocks.loc[blocks.Condition == 'N', 'Blok'] == 1).all()}")
"""
            ),
            markdown(
                """
Neutral was always first; only interruptions and time pressure were counterbalanced. This prevents a clean separation of Neutral-versus-stressor effects from order, practice, fatigue, or sensor drift.
"""
            ),
            markdown("## Missingness and repeated subjective labels"),
            code(
                """
from config import BEHAVIOR_FEATURES, PHYSIOLOGY_FEATURES, SUBJECTIVE_FEATURES

missing = (work[BEHAVIOR_FEATURES + PHYSIOLOGY_FEATURES + SUBJECTIVE_FEATURES]
           .isna().mean().mul(100).sort_values(ascending=False)
           .rename("missing_percent").to_frame())
missing.head(12).round(1)
"""
            ),
            code(
                """
unique_within_block = work.groupby(["PP", "Condition"])[SUBJECTIVE_FEATURES].nunique(dropna=True)
print(f"Maximum unique questionnaire values within a participant-condition block: {int(unique_within_block.max().max())}")
print("One value confirms that minute-level rows must not be treated as independent questionnaire observations.")
"""
            ),
            markdown("## Write analytic files"),
            code(
                """
from data_cleaning import run
run(raw_path, ROOT / "data" / "processed")
print("Wrote minute_work.csv, participant_condition.csv, and qc_summary.json")
"""
            ),
        ]
    )
    nbf.write(notebook, NOTEBOOK_DIR / "01_data_cleaning.ipynb")


def build_statistics() -> None:
    notebook = base_notebook(
        [
            markdown(
                """
# 02 · Human-factors effects

This notebook estimates condition-associated changes in subjective workload, natural computer interaction, and physiology. Questionnaire and condition-effect models use one row per participant-condition block.

Model: `Outcome ~ Condition + (1 | Participant)`  
Planned contrasts: Interruptions minus Neutral; Time pressure minus Neutral.  
The two contrasts for each outcome receive Holm correction.
"""
            ),
            code(
                """
from pathlib import Path
import sys
import pandas as pd

ROOT = Path.cwd().resolve().parent if Path.cwd().name == "notebooks" else Path.cwd().resolve()
sys.path.insert(0, str(ROOT / "src"))
from statistical_analysis import run
run()
print("Statistical tables regenerated from participant_condition.csv")
"""
            ),
            markdown("## Planned contrasts"),
            code(
                """
contrasts = pd.read_csv(ROOT / "tables" / "condition_contrasts.csv")
display_cols = ["domain", "outcome", "contrast", "estimate", "CI_low", "CI_high", "p_holm_within_outcome", "paired_dz", "model_percent_change"]
contrasts[display_cols].round(3)
"""
            ),
            markdown(
                """
The most defensible effects are higher mental effort in both stressor conditions and more application switching during interruptions. Weighted NASA-TLX did not show a clear contrast. Heart-rate contrasts are large but are treated cautiously because HR is missing in 52.9% of work minutes and Neutral was always the first block.
"""
            ),
            markdown("## Subjective–objective associations"),
            code(
                """
associations = pd.read_csv(ROOT / "tables" / "within_person_correlations.csv")
associations.sort_values("p_raw").head(10).round(3)
"""
            ),
            markdown(
                """
None of the subjective–objective correlations survives within-outcome FDR correction. They are exploratory signals rather than validated objective workload markers.
"""
            ),
            markdown("## Portfolio figures"),
            code(
                """
from IPython.display import Image, display
for name in ["subjective_conditions.png", "behavior_conditions.png", "physiology_conditions.png", "sensor_missingness.png"]:
    display(Image(filename=str(ROOT / "figures" / name), width=900))
"""
            ),
        ]
    )
    nbf.write(notebook, NOTEBOOK_DIR / "02_human_factors_analysis.ipynb")


def build_modeling() -> None:
    notebook = base_notebook(
        [
            markdown(
                """
# 03 · Participant-disjoint multimodal modeling

The goal is to compare an inexpensive behavior-only sensing strategy with physiology-only and combined models.

- Validation: leave-one-subject-out (25 folds)
- Pipeline inside every training fold: median imputation → standardization → class-balanced L2 logistic regression
- Metrics: balanced accuracy, macro-F1, ROC-AUC, sensitivity, specificity
- Targets: three-class experimental condition (primary) and Neutral versus stressor (supplementary)

The binary target describes the manipulated condition. It is not a direct minute-specific “high workload” label.
"""
            ),
            code(
                """
from pathlib import Path
import sys
import pandas as pd

ROOT = Path.cwd().resolve().parent if Path.cwd().name == "notebooks" else Path.cwd().resolve()
sys.path.insert(0, str(ROOT / "src"))
from modeling import run
run()
print("LOSO outputs regenerated; preprocessing was fitted inside each training fold.")
"""
            ),
            markdown("## Cross-participant performance"),
            code(
                """
summary = pd.read_csv(ROOT / "tables" / "model_summary_metrics.csv")
summary.pivot_table(index=["target", "metric"], columns="feature_set", values="mean").round(3)
"""
            ),
            code(
                """
summary[summary.target.eq("Neutral vs stressor")][
    ["feature_set", "metric", "mean", "CI_low", "CI_high"]
].round(3)
"""
            ),
            markdown("## Does physiology add enough value?"),
            code(
                """
comparison = pd.read_csv(ROOT / "tables" / "model_feature_set_comparisons.csv")
comparison.round(3)
"""
            ),
            markdown(
                """
Combined sensing improves the mean ROC-AUC for Neutral versus stressor by 0.048 over behavior only, but the participant-bootstrap interval crosses zero. Balanced-accuracy gain is only 0.012 and is also uncertain. With 52.9% HR/RMSSD missingness, the current evidence does not justify physiology as a required product sensor.

The behavior-only model is modestly above chance, but it is not accurate enough for autonomous notification suppression. A defensible use would be a weak context signal combined with user control and a prospective randomized policy test.
"""
            ),
            code(
                """
from IPython.display import Image, display
display(Image(filename=str(ROOT / "figures" / "model_comparison.png"), width=900))
"""
            ),
        ]
    )
    nbf.write(notebook, NOTEBOOK_DIR / "03_workload_model.ipynb")


def main() -> None:
    NOTEBOOK_DIR.mkdir(parents=True, exist_ok=True)
    build_cleaning()
    build_statistics()
    build_modeling()
    print(f"Wrote notebooks to {NOTEBOOK_DIR}")


if __name__ == "__main__":
    main()

