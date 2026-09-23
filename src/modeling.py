from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import LabelEncoder, StandardScaler

from config import (
    BEHAVIOR_FEATURES,
    PHYSIOLOGY_FEATURES,
    PROCESSED_DIR,
    SEED,
    TABLE_DIR,
    ensure_output_dirs,
)


FEATURE_SETS = {
    "Behavior only": BEHAVIOR_FEATURES,
    "Physiology only": PHYSIOLOGY_FEATURES,
    "Combined": BEHAVIOR_FEATURES + PHYSIOLOGY_FEATURES,
}


def transform_features(data: pd.DataFrame) -> pd.DataFrame:
    transformed = data.copy()
    for feature in BEHAVIOR_FEATURES:
        if feature not in {"CharactersRatio", "ErrorKeyRatio"}:
            transformed[feature] = np.log1p(transformed[feature].clip(lower=0))
    transformed["RMSSD"] = np.log(transformed["RMSSD"].where(transformed["RMSSD"] > 0))
    transformed["SCL"] = np.log(transformed["SCL"].where(transformed["SCL"] > 0))
    return transformed


def bootstrap_mean_ci(values: np.ndarray, rng: np.random.Generator) -> tuple[float, float]:
    samples = rng.choice(values, size=(20000, len(values)), replace=True).mean(axis=1)
    return tuple(np.quantile(samples, [0.025, 0.975]))


def evaluate_target(
    data: pd.DataFrame, target_name: str, target: np.ndarray, rng: np.random.Generator
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    encoder = LabelEncoder().fit(target)
    y = encoder.transform(target)
    groups = data["PP"].to_numpy()
    splitter = LeaveOneGroupOut()
    fold_rows = []
    confusion_rows = []
    coefficient_rows = []

    for feature_set, features in FEATURE_SETS.items():
        X = data[features].to_numpy(dtype=float)
        predictions = np.empty(len(y), dtype=int)
        probabilities = np.empty((len(y), len(encoder.classes_)), dtype=float)
        coefficients = []

        for train, test in splitter.split(X, y, groups):
            pipeline = Pipeline(
                [
                    ("imputer", SimpleImputer(strategy="median")),
                    ("scaler", StandardScaler()),
                    (
                        "classifier",
                        LogisticRegression(
                            C=1.0,
                            penalty="l2",
                            solver="lbfgs",
                            class_weight="balanced",
                            max_iter=5000,
                            random_state=SEED,
                        ),
                    ),
                ]
            )
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                pipeline.fit(X[train], y[train])
            predictions[test] = pipeline.predict(X[test])
            probabilities[test] = pipeline.predict_proba(X[test])
            coefficients.append(pipeline.named_steps["classifier"].coef_)

            if len(encoder.classes_) == 2:
                auc = roc_auc_score(y[test], probabilities[test, 1])
            else:
                auc = roc_auc_score(
                    y[test],
                    probabilities[test],
                    multi_class="ovr",
                    average="macro",
                    labels=np.arange(len(encoder.classes_)),
                )
            fold_rows.append(
                {
                    "target": target_name,
                    "feature_set": feature_set,
                    "participant": groups[test][0],
                    "n_test_minutes": len(test),
                    "balanced_accuracy": balanced_accuracy_score(y[test], predictions[test]),
                    "macro_f1": f1_score(y[test], predictions[test], average="macro"),
                    "roc_auc": auc,
                }
            )

        matrix = confusion_matrix(y, predictions)
        recall = recall_score(y, predictions, average=None)
        for class_index, class_name in enumerate(encoder.classes_):
            true_negative = (
                matrix.sum()
                - matrix[class_index, :].sum()
                - matrix[:, class_index].sum()
                + matrix[class_index, class_index]
            )
            false_positive = matrix[:, class_index].sum() - matrix[class_index, class_index]
            specificity = true_negative / (true_negative + false_positive)
            confusion_rows.append(
                {
                    "target": target_name,
                    "feature_set": feature_set,
                    "class": class_name,
                    "recall_sensitivity": recall[class_index],
                    "specificity": specificity,
                    "true_count": int((y == class_index).sum()),
                    "predicted_count": int((predictions == class_index).sum()),
                }
            )
            for predicted_index, predicted_name in enumerate(encoder.classes_):
                confusion_rows.append(
                    {
                        "target": target_name,
                        "feature_set": feature_set,
                        "class": f"cell:{class_name}->{predicted_name}",
                        "recall_sensitivity": np.nan,
                        "specificity": np.nan,
                        "true_count": int(matrix[class_index, predicted_index]),
                        "predicted_count": np.nan,
                    }
                )

        coef = np.stack(coefficients)
        if len(encoder.classes_) == 2:
            for index, feature in enumerate(features):
                values = coef[:, 0, index]
                coefficient_rows.append(
                    {
                        "target": target_name,
                        "feature_set": feature_set,
                        "class": str(encoder.classes_[1]),
                        "feature": feature,
                        "mean_standardized_coefficient": values.mean(),
                        "sd_across_folds": values.std(ddof=1),
                        "positive_fold_proportion": (values > 0).mean(),
                    }
                )

    folds = pd.DataFrame(fold_rows)
    summaries = []
    for (feature_set,), subset in folds.groupby(["feature_set"]):
        for metric in ("balanced_accuracy", "macro_f1", "roc_auc"):
            values = subset[metric].to_numpy()
            low, high = bootstrap_mean_ci(values, rng)
            summaries.append(
                {
                    "target": target_name,
                    "feature_set": feature_set,
                    "metric": metric,
                    "mean": values.mean(),
                    "sd": values.std(ddof=1),
                    "CI_low": low,
                    "CI_high": high,
                    "n_participants": len(values),
                }
            )

    comparisons = []
    behavior = folds[folds["feature_set"] == "Behavior only"].set_index("participant")
    combined = folds[folds["feature_set"] == "Combined"].set_index("participant")
    for metric in ("balanced_accuracy", "macro_f1", "roc_auc"):
        difference = (combined[metric] - behavior[metric]).to_numpy()
        low, high = bootstrap_mean_ci(difference, rng)
        comparisons.append(
            {
                "target": target_name,
                "comparison": "Combined - Behavior only",
                "metric": metric,
                "mean_difference": difference.mean(),
                "CI_low": low,
                "CI_high": high,
            }
        )

    return (
        folds,
        pd.DataFrame(summaries),
        pd.DataFrame(confusion_rows),
        pd.DataFrame(coefficient_rows + comparisons),
    )


def run() -> None:
    ensure_output_dirs()
    data = pd.read_csv(PROCESSED_DIR / "minute_work.csv")
    data = transform_features(data)
    rng = np.random.default_rng(SEED)
    targets = {
        "Three-class condition": data["Condition"].to_numpy(),
        "Neutral vs stressor": np.where(data["Condition"] == "N", "Neutral", "Stressor"),
    }
    outputs = [evaluate_target(data, name, target, rng) for name, target in targets.items()]
    pd.concat([item[0] for item in outputs], ignore_index=True).to_csv(
        TABLE_DIR / "model_fold_metrics.csv", index=False
    )
    pd.concat([item[1] for item in outputs], ignore_index=True).to_csv(
        TABLE_DIR / "model_summary_metrics.csv", index=False
    )
    pd.concat([item[2] for item in outputs], ignore_index=True).to_csv(
        TABLE_DIR / "model_class_metrics.csv", index=False
    )
    coefficient_and_comparison = pd.concat(
        [item[3] for item in outputs], ignore_index=True
    )
    coefficient_and_comparison[
        coefficient_and_comparison["feature"].notna()
    ].drop(columns=["comparison", "metric", "mean_difference", "CI_low", "CI_high"]).to_csv(
        TABLE_DIR / "model_coefficients.csv", index=False
    )
    coefficient_and_comparison[
        coefficient_and_comparison["comparison"].notna()
    ].drop(
        columns=[
            "feature_set",
            "class",
            "feature",
            "mean_standardized_coefficient",
            "sd_across_folds",
            "positive_fold_proportion",
        ]
    ).to_csv(TABLE_DIR / "model_feature_set_comparisons.csv", index=False)


if __name__ == "__main__":
    run()
