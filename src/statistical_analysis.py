from __future__ import annotations

import math
import warnings

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.formula.api import mixedlm
from statsmodels.stats.multitest import multipletests

from config import (
    BEHAVIOR_PRIMARY,
    PHYSIOLOGY_FEATURES,
    PROCESSED_DIR,
    SEED,
    TABLE_DIR,
    ensure_output_dirs,
)


OUTCOMES = {
    "Subjective": {
        "NasaTLX": "identity",
        "MentalEffort": "identity",
        "Stress": "identity",
    },
    "Behavior": {
        "SnKeyStrokes": "log1p",
        "SnMouseAct": "log1p",
        "SnAppChange": "log1p",
        "SnTabfocusChange": "log1p",
        "SnErrorKeys": "log1p",
    },
    "Physiology": {
        "HR": "identity",
        "RMSSD": "log",
        "SCL": "log",
    },
}


def _transform(series: pd.Series, transform: str) -> pd.Series:
    if transform == "identity":
        return series
    if transform == "log1p":
        return np.log1p(series.clip(lower=0))
    if transform == "log":
        return np.log(series.where(series > 0))
    raise ValueError(transform)


def _paired_dz(data: pd.DataFrame, outcome: str, condition: str) -> tuple[float, int]:
    wide = data.pivot(index="PP", columns="Condition", values=outcome)
    pair = wide[[condition, "N"]].dropna()
    difference = pair[condition] - pair["N"]
    if len(difference) < 3 or difference.std(ddof=1) == 0:
        return np.nan, len(difference)
    return float(difference.mean() / difference.std(ddof=1)), len(difference)


def fit_condition_models(blocks: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    contrasts: list[dict] = []
    diagnostics: list[dict] = []
    for domain, outcomes in OUTCOMES.items():
        for outcome, transform in outcomes.items():
            data = blocks[["PP", "Condition", outcome]].dropna().copy()
            data["model_value"] = _transform(data[outcome], transform)
            data = data.replace([np.inf, -np.inf], np.nan).dropna(subset=["model_value"])
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                model = mixedlm(
                    'model_value ~ C(Condition, Treatment(reference="N"))',
                    data,
                    groups=data["PP"],
                ).fit(reml=True, method="powell", maxiter=2000, disp=False)

            diagnostics.append(
                {
                    "domain": domain,
                    "outcome": outcome,
                    "transform": transform,
                    "n_rows": len(data),
                    "n_participants": data["PP"].nunique(),
                    "converged": bool(model.converged),
                    "random_intercept_variance": float(model.cov_re.iloc[0, 0]),
                    "residual_variance": float(model.scale),
                    "log_likelihood": float(model.llf),
                }
            )

            means = data.groupby("Condition")[outcome].mean()
            for condition in ("I", "T"):
                label = f'C(Condition, Treatment(reference="N"))[T.{condition}]'
                estimate = float(model.fe_params[label])
                se = float(model.bse_fe[label])
                dz, n_pairs = _paired_dz(data, outcome, condition)
                contrasts.append(
                    {
                        "domain": domain,
                        "outcome": outcome,
                        "transform": transform,
                        "contrast": f"{condition} - N",
                        "n_rows": len(data),
                        "n_participants": data["PP"].nunique(),
                        "n_complete_pairs": n_pairs,
                        "estimate": estimate,
                        "SE": se,
                        "CI_low": estimate - 1.96 * se,
                        "CI_high": estimate + 1.96 * se,
                        "p_raw": float(model.pvalues[label]),
                        "neutral_mean_raw": float(means.get("N", np.nan)),
                        "condition_mean_raw": float(means.get(condition, np.nan)),
                        "raw_mean_difference": float(
                            means.get(condition, np.nan) - means.get("N", np.nan)
                        ),
                        "paired_dz": dz,
                        "model_percent_change": (
                            (math.exp(estimate) - 1) * 100
                            if transform in {"log", "log1p"}
                            else np.nan
                        ),
                    }
                )

    table = pd.DataFrame(contrasts)
    table["p_holm_within_outcome"] = np.nan
    for _, index in table.groupby(["domain", "outcome"]).groups.items():
        table.loc[index, "p_holm_within_outcome"] = multipletests(
            table.loc[index, "p_raw"], method="holm"
        )[1]
    return table, pd.DataFrame(diagnostics)


def descriptives(blocks: pd.DataFrame) -> pd.DataFrame:
    outcomes = [outcome for domain in OUTCOMES.values() for outcome in domain]
    rows: list[dict] = []
    for outcome in outcomes:
        for condition, group in blocks.groupby("Condition"):
            values = group[outcome].dropna()
            rows.append(
                {
                    "outcome": outcome,
                    "condition": condition,
                    "n": len(values),
                    "mean": values.mean(),
                    "sd": values.std(ddof=1),
                    "median": values.median(),
                    "q25": values.quantile(0.25),
                    "q75": values.quantile(0.75),
                }
            )
    return pd.DataFrame(rows)


def repeated_measures_correlation(
    data: pd.DataFrame, outcome: str, feature: str, rng: np.random.Generator
) -> dict:
    subset = data[["PP", outcome, feature]].dropna().copy()
    subset["y_centered"] = subset[outcome] - subset.groupby("PP")[outcome].transform("mean")
    subset["x_centered"] = subset[feature] - subset.groupby("PP")[feature].transform("mean")
    r = float(stats.pearsonr(subset["x_centered"], subset["y_centered"]).statistic)
    n = len(subset)
    participants = subset["PP"].nunique()
    df = n - participants - 1
    t_value = r * math.sqrt(df / max(1e-12, 1 - r**2))
    p_value = float(2 * stats.t.sf(abs(t_value), df))

    ids = subset["PP"].unique()
    centered = {
        participant: (
            group["x_centered"].to_numpy(),
            group["y_centered"].to_numpy(),
        )
        for participant, group in subset.groupby("PP")
    }
    boot = []
    for _ in range(2000):
        sampled = rng.choice(ids, size=len(ids), replace=True)
        x_sample = np.concatenate([centered[participant][0] for participant in sampled])
        y_sample = np.concatenate([centered[participant][1] for participant in sampled])
        if x_sample.std(ddof=1) > 0 and y_sample.std(ddof=1) > 0:
            boot.append(stats.pearsonr(x_sample, y_sample).statistic)
    low, high = np.quantile(boot, [0.025, 0.975])
    return {
        "outcome": outcome,
        "feature": feature,
        "n_rows": n,
        "n_participants": participants,
        "df": df,
        "r_rm": r,
        "CI_low": low,
        "CI_high": high,
        "p_raw": p_value,
    }


def within_person_associations(blocks: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    rows = []
    features = BEHAVIOR_PRIMARY + PHYSIOLOGY_FEATURES
    for outcome in ("MentalEffort", "Stress", "NasaTLX"):
        for feature in features:
            rows.append(repeated_measures_correlation(blocks, outcome, feature, rng))
    table = pd.DataFrame(rows)
    table["p_fdr_within_outcome"] = np.nan
    for _, index in table.groupby("outcome").groups.items():
        table.loc[index, "p_fdr_within_outcome"] = multipletests(
            table.loc[index, "p_raw"], method="fdr_bh"
        )[1]
    return table


def run() -> None:
    ensure_output_dirs()
    blocks = pd.read_csv(PROCESSED_DIR / "participant_condition.csv")
    contrasts, diagnostics = fit_condition_models(blocks)
    contrasts.to_csv(TABLE_DIR / "condition_contrasts.csv", index=False)
    diagnostics.to_csv(TABLE_DIR / "model_diagnostics.csv", index=False)
    descriptives(blocks).to_csv(TABLE_DIR / "condition_descriptives.csv", index=False)
    within_person_associations(blocks).to_csv(
        TABLE_DIR / "within_person_correlations.csv", index=False
    )


if __name__ == "__main__":
    run()
