from __future__ import annotations

import json

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from config import FIGURE_DIR, PROCESSED_DIR, SEED, TABLE_DIR, ensure_output_dirs


COLORS = {"N": "#5D6B7A", "I": "#D9544D", "T": "#E39A3B"}
LABELS = {"N": "Neutral", "I": "Interruptions", "T": "Time pressure"}
ORDER = ["N", "I", "T"]


def set_style() -> None:
    sns.set_theme(style="whitegrid")
    mpl.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.titlesize": 12,
            "axes.titleweight": "bold",
            "axes.labelsize": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "grid.color": "#E9EDF2",
            "grid.linewidth": 0.7,
        }
    )


def paired_panel(ax: plt.Axes, data: pd.DataFrame, outcome: str, title: str, ylabel: str) -> None:
    wide = data.pivot(index="PP", columns="Condition", values=outcome)
    for _, row in wide.iterrows():
        values = row.reindex(ORDER).to_numpy(dtype=float)
        ax.plot(range(3), values, color="#AEB7C2", alpha=0.24, linewidth=0.8, zorder=1)
        ax.scatter(range(3), values, color="#AEB7C2", alpha=0.42, s=10, zorder=2)
    for index, condition in enumerate(ORDER):
        values = wide[condition].dropna().to_numpy()
        mean = values.mean()
        ci = 1.96 * values.std(ddof=1) / np.sqrt(len(values))
        ax.errorbar(
            index,
            mean,
            yerr=ci,
            fmt="o",
            color=COLORS[condition],
            ecolor=COLORS[condition],
            markersize=7,
            capsize=3,
            linewidth=2,
            zorder=5,
        )
    ax.set_xticks(range(3), [LABELS[item] for item in ORDER], rotation=15, ha="right")
    ax.set_title(title, loc="left")
    ax.set_ylabel(ylabel)
    ax.grid(axis="x", visible=False)


def make_condition_figures(blocks: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.6), constrained_layout=True)
    paired_panel(axes[0], blocks, "MentalEffort", "Mental effort (RSME)", "0–10 rating")
    paired_panel(axes[1], blocks, "Stress", "Perceived stress", "0–10 rating")
    paired_panel(axes[2], blocks, "NasaTLX", "Weighted NASA-TLX", "0–100 score")
    fig.suptitle("Subjective experience: one rating per participant × condition", x=0.01, ha="left", fontsize=14, fontweight="bold")
    fig.savefig(FIGURE_DIR / "subjective_conditions.png", dpi=220, bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(12, 3.6), constrained_layout=True)
    paired_panel(axes[0], blocks, "SnAppChange", "Application switching", "changes / minute")
    paired_panel(axes[1], blocks, "SnKeyStrokes", "Keyboard activity", "keystrokes / minute")
    paired_panel(axes[2], blocks, "SnMouseAct", "Mouse activity", "events / minute")
    fig.suptitle("Low-intrusion interaction signals", x=0.01, ha="left", fontsize=14, fontweight="bold")
    fig.savefig(FIGURE_DIR / "behavior_conditions.png", dpi=220, bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(12, 3.6), constrained_layout=True)
    paired_panel(axes[0], blocks, "HR", "Heart rate", "beats / minute")
    paired_panel(axes[1], blocks, "RMSSD", "Heart-rate variability", "RMSSD (s)")
    paired_panel(axes[2], blocks, "SCL", "Skin conductance level", "released dataset units")
    fig.suptitle("Physiological signals — interpret with missingness and order confounding", x=0.01, ha="left", fontsize=14, fontweight="bold")
    fig.savefig(FIGURE_DIR / "physiology_conditions.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def make_missingness_figure() -> None:
    with (PROCESSED_DIR / "qc_summary.json").open(encoding="utf-8") as handle:
        qc = json.load(handle)
    selected = ["Computer interaction", "SCL", "HR", "RMSSD"]
    values = [
        qc["missingness_proportion"]["SnKeyStrokes"] * 100,
        qc["missingness_proportion"]["SCL"] * 100,
        qc["missingness_proportion"]["HR"] * 100,
        qc["missingness_proportion"]["RMSSD"] * 100,
    ]
    fig, ax = plt.subplots(figsize=(7.2, 3.1), constrained_layout=True)
    bars = ax.barh(selected, values, color=["#3C7D8C", "#8EA3B4", "#8EA3B4", "#8EA3B4"])
    ax.set_xlim(0, 60)
    ax.set_xlabel("Missing minute rows (%)")
    ax.set_title("Sensor availability is part of the engineering decision", loc="left")
    ax.invert_yaxis()
    for bar, value in zip(bars, values):
        ax.text(value + 1, bar.get_y() + bar.get_height() / 2, f"{value:.1f}%", va="center", fontsize=10)
    ax.grid(axis="y", visible=False)
    fig.savefig(FIGURE_DIR / "sensor_missingness.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def make_model_figure() -> None:
    summary = pd.read_csv(TABLE_DIR / "model_summary_metrics.csv")
    data = summary[
        (summary["target"] == "Neutral vs stressor")
        & (summary["metric"].isin(["balanced_accuracy", "roc_auc"]))
    ].copy()
    label_map = {"balanced_accuracy": "Balanced accuracy", "roc_auc": "ROC-AUC"}
    palette = {"Behavior only": "#3C7D8C", "Physiology only": "#8EA3B4", "Combined": "#D9544D"}
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.7), constrained_layout=True, sharey=True)
    for ax, metric in zip(axes, ["balanced_accuracy", "roc_auc"]):
        subset = data[data["metric"] == metric].set_index("feature_set").loc[list(palette)]
        y = np.arange(len(subset))
        for row_index, (feature_set, row) in enumerate(subset.iterrows()):
            ax.errorbar(
                row["mean"],
                row_index,
                xerr=[[row["mean"] - row["CI_low"]], [row["CI_high"] - row["mean"]]],
                fmt="o",
                color=palette[feature_set],
                ecolor=palette[feature_set],
                markersize=7,
                elinewidth=2.2,
                capsize=4,
                zorder=3,
            )
        ax.axvline(0.5, color="#7A8490", linestyle="--", linewidth=1, label="Chance")
        ax.set_xlim(0.42, 0.74)
        ax.set_title(label_map[metric], loc="left")
        ax.set_xlabel("Mean across 25 held-out participants")
        ax.set_yticks(y, subset.index)
        ax.grid(axis="y", visible=False)
    fig.suptitle("Participant-disjoint prediction: Neutral vs stressor context", x=0.01, ha="left", fontsize=14, fontweight="bold")
    fig.savefig(FIGURE_DIR / "model_comparison.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def make_effect_forest() -> None:
    table = pd.read_csv(TABLE_DIR / "condition_contrasts.csv")
    keep = table[
        table["outcome"].isin(["MentalEffort", "Stress", "SnAppChange", "SnKeyStrokes", "HR", "SCL"])
    ].copy()
    outcome_labels = {
        "MentalEffort": "Mental effort",
        "Stress": "Perceived stress",
        "SnAppChange": "App switching",
        "SnKeyStrokes": "Keystrokes",
        "HR": "Heart rate",
        "SCL": "Skin conductance",
    }
    keep["label"] = keep["outcome"].map(outcome_labels) + " · " + keep["contrast"]
    keep = keep.iloc[::-1]
    fig, ax = plt.subplots(figsize=(7.5, 5.2), constrained_layout=True)
    colors = [COLORS["I"] if "I - N" in item else COLORS["T"] for item in keep["label"]]
    ax.scatter(keep["paired_dz"], np.arange(len(keep)), color=colors, s=50)
    ax.axvline(0, color="#7A8490", linewidth=1)
    ax.set_yticks(np.arange(len(keep)), keep["label"])
    ax.set_xlabel("Within-participant standardized difference (dᶻ; raw scale)")
    ax.set_title("Magnitude and direction of planned contrasts", loc="left")
    ax.grid(axis="y", visible=False)
    fig.savefig(FIGURE_DIR / "effect_size_forest.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def run() -> None:
    ensure_output_dirs()
    set_style()
    blocks = pd.read_csv(PROCESSED_DIR / "participant_condition.csv")
    make_condition_figures(blocks)
    make_missingness_figure()
    make_model_figure()
    make_effect_forest()


if __name__ == "__main__":
    run()
